"""
============================================================
NutriCare AI — Python RAG + ML Service
============================================================

Runs on:  http://127.0.0.1:5000
Consumed by:  Node.js backend  (http://127.0.0.1:8000)

Endpoints:
  GET  /               health check (ChromaDB + LLM status)
  POST /rag-chat       RAG question → answer
  POST /predict-food   NutriCare ViT food image classifier (43 Indian foods)
                       (auto-falls back to nateraw/food if the local model
                       files are missing)
  POST /predict        Combined ML model
                       (energy / diabetes / hypertension / obesity)

RAG stack:
  - ChromaDB            (vector store — auto-discovers the populated
                         knowledge base built by RAG/create_database.py)
  - sentence-transformers (all-MiniLM-L6-v2 embeddings)
  - Ollama / OpenAI / Gemini (LLM — auto-detected, fully optional:
                         retrieval answers still work without an LLM)

Quick start:
  pip install -r requirements.txt
  python rag_service.py

  # Optional — pick ONE LLM backend:
  ollama serve                       # local Ollama (auto-detected)
  OPENAI_API_KEY=...                 # OpenAI GPT
  GEMINI_API_KEY=...                 # Google Gemini
============================================================
"""

import os
import re
import sys
import json
import base64
import io
import time
import datetime
from typing import Optional, List, Dict

# ------------------------------------------------------------
# Windows consoles default to cp1252 — an emoji in a log line
# used to raise UnicodeEncodeError *inside* a route and kill
# model loading. Force UTF-8 with lossy replacement instead.
# ------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))   # …/backend
PROJECT_DIR = os.path.dirname(BASE_DIR)                    # project root

PORT            = int(os.getenv("RAG_PORT", 5000))

# Empty value → auto-discover the populated ChromaDB folder.
CHROMA_PATH     = os.getenv("CHROMA_PATH", "").strip()
# Empty value → auto-pick the collection that actually holds documents.
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "").strip()

EMBED_MODEL     = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# auto | ollama | openai | gemini | none
LLM_PROVIDER    = os.getenv("LLM_PROVIDER", "auto").lower()
LLM_MODEL       = os.getenv("LLM_MODEL", "").strip()
LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "140"))
LLM_TIMEOUT     = float(os.getenv("LLM_TIMEOUT", "90"))
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")

# Retrieval cut-offs per distance metric.
#   • cosine distance  : 0 = identical, 2 = opposite  → keep < 0.9
#   • L2 distance      : MiniLM vectors are ~1.4 apart when unrelated
L2_MAX_DISTANCE       = float(os.getenv("L2_MAX_DISTANCE", "1.45"))
COSINE_MAX_DISTANCE   = float(os.getenv("COSINE_MAX_DISTANCE", "0.9"))

# Only answer instantly from the knowledge base when the top hit is
# this close (QA-style records).
DIRECT_ANSWER_L2      = float(os.getenv("DIRECT_ANSWER_L2", "0.8"))
DIRECT_ANSWER_COSINE  = float(os.getenv("DIRECT_ANSWER_COSINE", "0.35"))

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NutriCare AI – RAG Service",
    description="RAG + Food Classification service for NutriCare AI",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CHROMADB  (lazy init so the server still starts if missing)
# ============================================================

chroma_client     = None
chroma_collection = None
chroma_path_used  = None
chroma_space      = "l2"        # distance metric of the open collection
embedder          = None


def _open_client(path: str):
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False)
    )


def _has_documents(path: str) -> bool:
    """True when the ChromaDB folder already contains indexed documents."""
    try:
        client = _open_client(path)
        return any(c.count() > 0 for c in client.list_collections())
    except Exception:
        return False


def _resolve_chroma_path() -> str:
    """
    Find the knowledge base built by RAG/create_database.py.
    Priority: CHROMA_PATH env → folder that actually has documents
    → the project RAG folder → the local backend folder.
    """
    if CHROMA_PATH:
        return CHROMA_PATH

    candidates = [
        os.path.join(PROJECT_DIR, "RAG", "chroma_db"),
        os.path.join(BASE_DIR, "chroma_db"),
    ]

    existing = []
    for cand in candidates:
        if os.path.isdir(cand):
            existing.append(cand)
            if _has_documents(cand):
                return cand

    return existing[0] if existing else candidates[0]


def _collection_space(collection) -> str:
    """Detect the distance metric used by the open collection."""
    try:
        cfg = collection.configuration_json or {}
        space = (cfg.get("hnsw") or {}).get("space")
        if space:
            return str(space).lower()
    except Exception:
        pass

    meta = getattr(collection, "metadata", None) or {}
    return str(meta.get("hnsw:space", "l2")).lower()


def init_chroma():
    """
    Try to initialise ChromaDB and the embedding model.
    Silently skips if the libraries are not installed.
    """
    global chroma_client, chroma_collection, embedder, chroma_path_used, chroma_space

    try:
        from sentence_transformers import SentenceTransformer

        chroma_path_used = _resolve_chroma_path()
        chroma_client    = _open_client(chroma_path_used)

        # ---- pick the collection that actually holds documents ----
        available = {c.name: c.count() for c in chroma_client.list_collections()}

        target = COLLECTION_NAME
        if not target:
            if available:
                target = max(available, key=available.get)
            else:
                target = "nutricare_knowledge"

        if target in available and available[target] == 0 and not COLLECTION_NAME:
            # Configured collection is empty — prefer anything with data.
            populated = {n: c for n, c in available.items() if c > 0}
            if populated:
                target = max(populated, key=populated.get)

        chroma_collection = chroma_client.get_or_create_collection(
            name=target,
            metadata={"hnsw:space": "l2"}
        )
        chroma_space = _collection_space(chroma_collection)

        embedder = SentenceTransformer(EMBED_MODEL)

        print(f"✅ ChromaDB ready  — collection: '{chroma_collection.name}'  "
              f"docs: {chroma_collection.count()}  path: {chroma_path_used}")
        print(f"✅ Distance metric: {chroma_space}")
        print(f"✅ Embedding model loaded: {EMBED_MODEL}")
    except ImportError as e:
        print(f"⚠️  ChromaDB / sentence-transformers not installed ({e}). "
              f"RAG will use fallback answers.")
    except Exception as e:
        print(f"⚠️  ChromaDB init error: {e}. RAG will use fallback answers.")


@app.on_event("startup")
def startup():
    init_chroma()


# ============================================================
# RETRIEVAL HELPER
# ============================================================

def _score_for(distance: float) -> Optional[float]:
    """Map a raw distance to a 0–1 similarity score (None = discard)."""
    if chroma_space in ("cosine", "ip"):
        if distance > COSINE_MAX_DISTANCE:
            return None
        return round(1.0 - distance, 3)

    # L2 (default for the langchain-built knowledge base)
    if distance > L2_MAX_DISTANCE:
        return None
    return round(1.0 / (1.0 + distance), 3)


def _source_label(meta: Dict) -> str:
    name  = str(meta.get("Food_Name") or "").strip()
    qtype = str(meta.get("Question_Type") or "").strip()
    if name and qtype:
        return f"{name} — {qtype}"
    if name:
        return name
    return str(meta.get("source") or "NutriCare Knowledge Base")


def retrieve_context(question: str, top_k: int = 8) -> List[Dict]:
    """
    Embed the question and retrieve the top similar, de-duplicated
    documents from ChromaDB.
    Returns [{'text', 'source', 'score', 'distance', 'type', 'metadata'}].
    """
    if chroma_collection is None or embedder is None:
        return []

    try:
        total = chroma_collection.count()
        if total == 0:
            return []

        n_results = min(max(top_k * 2, top_k), total)

        q_vec = embedder.encode([question])[0].tolist()
        results = chroma_collection.query(
            query_embeddings=[q_vec],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        docs    = (results.get("documents") or [[]])[0] or []
        metas   = (results.get("metadatas")  or [[]])[0] or []
        dists   = (results.get("distances")  or [[]])[0] or []

        chunks = []
        seen   = set()

        for doc, meta, dist in zip(docs, metas, dists):
            if not doc:
                continue

            # The knowledge base contains duplicate rows — keep each
            # unique text only once so the LLM sees diverse context.
            key = " ".join(doc.split())
            if key in seen:
                continue
            seen.add(key)

            score = _score_for(dist)
            if score is None:          # too dissimilar → junk context
                continue

            meta = meta or {}
            chunks.append({
                "text":      doc,
                "source":    _source_label(meta),
                "score":     score,
                "distance":  round(float(dist), 4),
                "type":      str(meta.get("type", "")),
                "metadata":  meta
            })

            if len(chunks) >= top_k:
                break

        return chunks

    except Exception as e:
        print(f"⚠️  Retrieval error: {e}")
        return []


# ============================================================
# LLM HELPER  (auto-detects provider + installed Ollama model)
# ============================================================

_llm_state = {"provider": None, "model": None, "checked_at": 0.0}


def _ollama_models() -> List[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        return []


def _pick_model(names: List[str], wanted: str) -> str:
    if wanted:
        if wanted in names:
            return wanted
        base = wanted.split(":")[0]
        for n in names:
            if n.split(":")[0] == base:
                return n
    # Prefer the small/fast models first — big models are unusably slow on CPU.
    for pref in ("llama3.2", "llama3.1", "llama3", "llama3.2:1b", "qwen2.5:1.5",
                 "qwen2.5", "phi3", "phi", "gemma2", "gemma", "mistral"):
        for n in names:
            if n.split(":")[0].startswith(pref):
                return n
    return names[0]


def resolve_llm(force: bool = False) -> tuple:
    """
    Work out which LLM (if any) is usable right now.
    Returns (provider, model). provider == 'none' → skip the LLM.
    """
    now = time.time()
    if not force and _llm_state["provider"] and now - _llm_state["checked_at"] < 60:
        return _llm_state["provider"], _llm_state["model"]

    provider = LLM_PROVIDER
    model    = LLM_MODEL

    if provider in ("auto", "ollama"):
        names = _ollama_models()
        if names:
            provider = "ollama"
            model    = _pick_model(names, model)
        else:
            if provider == "ollama":
                print(f"⚠️  Ollama not reachable at {OLLAMA_URL} — "
                      f"answering from the knowledge base instead.")
            provider = "none"

    if provider == "openai" and not OPENAI_API_KEY:
        provider = "none"
    if provider == "gemini" and not GEMINI_API_KEY:
        provider = "none"

    _llm_state.update({"provider": provider, "model": model, "checked_at": now})
    return provider, model


def call_llm(prompt: str) -> str:
    """
    Send the assembled prompt to the configured LLM.
    Returns the answer string, or raises RuntimeError on failure.
    """
    provider, model = resolve_llm()

    if provider == "none":
        raise RuntimeError("No LLM configured.")

    # ── Ollama ───────────────────────────────────────────────
    if provider == "ollama":
        payload = {
            "model":  model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": LLM_MAX_TOKENS,
                "temperature": 0.2
            }
        }
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json=payload, timeout=LLM_TIMEOUT)
        r.raise_for_status()
        answer = r.json().get("response", "").strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty response.")
        return answer

    # ── OpenAI ───────────────────────────────────────────────
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model=model or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.2
        )
        return completion.choices[0].message.content.strip()

    # ── Google Gemini ────────────────────────────────────────
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gmodel = genai.GenerativeModel(model or "gemini-pro")
        response = gmodel.generate_content(prompt)
        return response.text.strip()

    raise RuntimeError(f"Unknown LLM provider: {provider}")


# ============================================================
# EXTRACTIVE ANSWERS  (work instantly, no LLM required)
# ============================================================

_QA_RE = re.compile(r"Question:\s*(.*?)\s*Answer:\s*(.*?)(?:\s*Food ID:|$)", re.S)

# Fields worth showing from a raw nutrition record.
_NUTRITION_FIELDS = (
    "Food Name", "Category", "Region", "Serving Size", "Energy", "Protein",
    "Total Fat", "Carbohydrate", "Total Free Sugars", "Dietary Fibre",
    "Sodium", "Potassium", "Diabetes Classification",
    "Hypertension Classification", "Obesity Classification",
    "Age Group Guidance"
)


def _parse_qa(text: str) -> Optional[Dict]:
    m = _QA_RE.search(text or "")
    if not m:
        return None
    question = " ".join(m.group(1).split())
    answer   = " ".join(m.group(2).split())
    if not answer:
        return None
    return {"question": question, "answer": answer}


def _summarize_nutrition(text: str) -> str:
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        label  = label.strip()
        value  = value.strip()
        if label in _NUTRITION_FIELDS and value and value.lower() not in ("nan", "none", "-"):
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def direct_answer(chunks: List[Dict]) -> Optional[str]:
    """
    If the top hit is a near-exact Q&A match, answer straight from it —
    no LLM latency, and always grounded in the knowledge base.
    """
    if not chunks:
        return None

    best = chunks[0]
    if best.get("type") != "qa":
        return None

    threshold = DIRECT_ANSWER_COSINE if chroma_space in ("cosine", "ip") else DIRECT_ANSWER_L2
    if best.get("distance", 999) > threshold:
        return None

    first = _parse_qa(best["text"])
    if not first:
        return None

    answers = [first["answer"]]
    for c in chunks[1:3]:
        if c.get("type") != "qa":
            continue
        if c.get("distance", 999) > threshold:
            continue
        other = _parse_qa(c["text"])
        if other and other["answer"] not in answers:
            answers.append(other["answer"])

    food = str(best["metadata"].get("Food_Name") or "").strip()
    header = "According to the NutriCare knowledge base"
    if food:
        header += f" ({food})"
    return header + ":\n\n" + "\n".join(answers)


def extractive_answer(chunks: List[Dict]) -> str:
    """Build an answer from retrieved chunks when no LLM is available."""
    if not chunks:
        return fallback_answer("")

    qa_answers = []
    for c in chunks[:3]:
        if c.get("type") == "qa":
            parsed = _parse_qa(c["text"])
            if parsed and parsed["answer"] not in qa_answers:
                qa_answers.append(parsed["answer"])
    if qa_answers:
        return ("According to the NutriCare knowledge base:\n\n" +
                "\n".join(qa_answers))

    for c in chunks[:2]:
        if c.get("type") == "nutrition":
            summary = _summarize_nutrition(c["text"])
            if summary:
                return ("According to the NutriCare knowledge base:\n\n" + summary)

    text = chunks[0]["text"].strip()
    if len(text) > 900:
        text = text[:900].rsplit("\n", 1)[0] + " …"
    return "According to the NutriCare knowledge base:\n\n" + text


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class ChatRequest(BaseModel):
    question: str
    # Optional health profile of the logged-in user so the bot can give
    # report-based food advice: {age, gender, height, weight, bmi,
    # bmi_category, conditions: ["hypertension", "diabetes", "obesity"]}
    profile: Optional[dict] = None

class FoodRequest(BaseModel):
    image_base64: str   # full data-URI  e.g. "data:image/png;base64,..."


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def health():
    try:
        provider, model = resolve_llm()
    except Exception:
        provider, model = "none", ""

    return {
        "status":        "online",
        "service":       "NutriCare AI – RAG Service",
        "chroma_ready":  chroma_collection is not None,
        "chroma_path":   chroma_path_used,
        "collection":    chroma_collection.name if chroma_collection else None,
        "distance":      chroma_space,
        "doc_count":     chroma_collection.count() if chroma_collection else 0,
        "embed_model":   EMBED_MODEL,
        "llm_provider":  provider,
        "llm_model":     model,
        "food_records":  len(load_food_records()),
        "endpoints":     ["/rag-chat", "/predict-food", "/predict",
                          "/food-recommend", "/plan/15-day"]
    }


@app.post("/rag-chat")
def rag_chat(req: ChatRequest):
    """
    Main RAG endpoint.
    1. Retrieve relevant chunks from ChromaDB.
    2. Strong Q&A match → answer straight from the knowledge base.
    3. Otherwise build a prompt and call the LLM.
    4. LLM unavailable → extractive answer from the retrieved chunks.
    Returns { success, answer, sources, via }.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty.")

    # ── 1. Retrieve context ──────────────────────────────────
    chunks = retrieve_context(question)
    sources = [
        {"source": c["source"], "score": c["score"], "distance": c["distance"]}
        for c in chunks
    ]

    # ── Report-aware personalisation (optional user profile) ───
    profile = req.profile if isinstance(req.profile, dict) else {}
    personal_note = build_personal_note(profile)

    # ── 2. Instant grounded answer for near-exact Q&A hits ───
    quick = direct_answer(chunks)
    if quick:
        print(f"✅ RAG answer (knowledge base match): {quick[:120]}")
        return {"success": True, "answer": quick, "sources": sources, "via": "rag_extract"}

    # ── 3. Build the prompt for the LLM ──────────────────────
    # If retrieval only found weakly related material, tell the LLM to
    # answer from general knowledge instead of pretending the context fits.
    good_distance = (
        0.55 if chroma_space in ("cosine", "ip") else 1.1
    )
    weak_context = (not chunks) or (chunks[0]["distance"] > good_distance)

    if chunks and not weak_context:
        context_text = "\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}"
            for c in chunks[:5]
        )
    else:
        # Weak hits are usually unrelated food records — feeding them to the
        # model only makes it hallucinate an answer around them.
        context_text = "(no relevant knowledge-base context was retrieved)"

    if weak_context:
        instructions = (
            "The knowledge base does not contain clearly relevant material for this "
            "question. Answer directly from general nutrition and health knowledge, "
            "in 2 to 4 sentences."
        )
        # Instant curated answer for common terms (HB, BMI, iron, …) when the
        # knowledge base has nothing relevant to say about them.
        curated = keyword_answer(question)
        if curated and weak_context:
            print(f"✅ RAG answer (keyword shortcut): {curated[:120]}")
            return {"success": True, "answer": curated, "sources": sources,
                    "via": "keyword_fallback"}
    else:
        instructions = (
            "Answer using the context below. If it does not contain a clear answer, "
            "say so briefly and then give a short general answer."
        )

    prompt = f"""You are NutriCare AI, a helpful, accurate, and friendly nutrition and health assistant.
{instructions}
Answer in at most 4 sentences.
{personal_note}
Context:
{context_text}

User question: {question}

Answer:"""

    # ── 4. Call the LLM (graceful fallbacks) ─────────────────
    try:
        answer = call_llm(prompt)
        provider, _ = resolve_llm()
        print(f"✅ RAG answer (LLM {provider}): {answer[:120]}")
        return {"success": True, "answer": answer, "sources": sources,
                "via": f"rag_llm:{provider}"}
    except Exception as e:
        print(f"⚠️  LLM unavailable ({e}) — answering from retrieved context.")

    if chunks:
        answer = extractive_answer(chunks)
        print(f"✅ RAG answer (knowledge base): {answer[:120]}")
        return {"success": True, "answer": answer, "sources": sources,
                "via": "rag_extract"}

    answer = fallback_answer(question)
    print(f"✅ RAG answer (keyword fallback): {answer[:120]}")
    return {"success": True, "answer": answer, "sources": sources,
            "via": "keyword_fallback"}


def fallback_answer(question: str) -> str:
    """
    Keyword-based answer when the knowledge base / LLM cannot help.
    Returns the generic helper message when nothing matches.
    """
    return keyword_answer(question) or (
        "I'm NutriCare AI. I can answer questions about nutrition, vitamins, minerals, BMI, "
        "blood reports, and healthy eating. Please try rephrasing your question, or make sure "
        "the RAG knowledge base is populated with your nutrition documents."
    )


def keyword_answer(question: str) -> Optional[str]:
    """
    Curated, instant answers for common nutrition / blood-report terms.
    Used when the knowledge base has no relevant match, so the user still
    gets a useful answer immediately (and without waiting for the LLM).
    Returns None when the question is not one of the known keywords.
    """
    q = question.lower()

    # ── Blood reports / haematology ─────────────────────────
    # HbA1c first: "hba1c" also contains the plain "hb" substring.
    if "hba1c" in q or "a1c" in q or "glycated" in q:
        return ("HbA1c (Glycated Haemoglobin) shows your average blood sugar over 2–3 months.\n\n"
                "📊 Ranges:\n• Normal: < 5.7%\n• Pre-diabetes: 5.7 – 6.4%\n• Diabetes: ≥ 6.5%\n\n"
                "Used to monitor and diagnose Type 2 diabetes.")
    if "hb" in q or "hemoglobin" in q or "haemoglobin" in q:
        return ("HB stands for Hemoglobin — the protein in red blood cells that carries "
                "oxygen through the body.\n\n📊 Normal HB:\n• Men: 13.5 – 17.5 g/dL\n"
                "• Women: 12.0 – 15.5 g/dL\n• Children: 11.0 – 16.0 g/dL\n\n"
                "Low HB indicates anaemia (often iron, B12 or folate deficiency).")
    if "wbc" in q or "white blood cell" in q or "leukocyte" in q:
        return ("WBC (White Blood Cells) are the immune system's first line of defence.\n\n"
                "📊 Normal range: 4,500 – 11,000 cells/µL\n• High → infection / inflammation\n"
                "• Low → bone-marrow issues or immunosuppression")
    if "rbc" in q or "red blood cell" in q or "erythrocyte" in q:
        return ("RBC (Red Blood Cells) carry oxygen using haemoglobin.\n\n📊 Normal count:\n"
                "• Men: 4.7 – 6.1 million/µL\n• Women: 4.2 – 5.4 million/µL\n"
                "Low RBC = anaemia, high RBC = polycythaemia / dehydration.")
    if "platelet" in q or "plt" in q:
        return ("Platelets help blood clot after an injury.\n\n📊 Normal range: "
                "150,000 – 400,000/µL\n• Low → bleeding risk\n• High → clotting risk")
    if "blood sugar" in q or "glucose" in q or "fasting sugar" in q or "diabet" in q:
        return ("Blood glucose measures the sugar in your blood.\n\n📊 Normal ranges:\n"
                "• Fasting: 70 – 100 mg/dL\n• After meals (2 h): < 140 mg/dL\n"
                "• Pre-diabetes (fasting): 100 – 125 mg/dL\n• Diabetes (fasting): ≥ 126 mg/dL\n\n"
                "Manage it with balanced meals, regular activity and less refined carbohydrate.")
    if "blood pressure" in q or "hypertension" in q:
        return ("Blood pressure is the force of blood against your artery walls.\n\n📊 Categories:\n"
                "• Normal: < 120/80\n• Elevated: 120–129 / < 80\n• High (Stage 1): 130–139 / 80–89\n"
                "• High (Stage 2): ≥ 140 / ≥ 90\n\n🥗 Manage with the DASH diet: less sodium, "
                "more potassium, fruit and vegetables.")
    if "cholesterol" in q or "ldl" in q or "hdl" in q or "triglyceride" in q:
        return ("Blood lipid panel (cholesterol):\n\n📊 Desirable ranges:\n"
                "• Total: < 200 mg/dL\n• LDL ('bad'): < 100 mg/dL\n• HDL ('good'): > 60 mg/dL\n"
                "• Triglycerides: < 150 mg/dL\n\nLower LDL with oats, fibre, healthy fats and exercise.")
    if "anaemia" in q or "anemia" in q:
        return ("Anaemia means too few healthy red blood cells or too little haemoglobin.\n\n"
                "📊 Common causes: iron deficiency (most common), vitamin B12 or folate deficiency.\n"
                "🔴 Symptoms: fatigue, pale skin, dizziness. 🥩 Treatment: iron-rich foods + "
                "Vitamin C, as advised by a doctor.")
    if "thyroid" in q or "tsh" in q:
        return ("Thyroid function:\n\n📊 TSH normal range: 0.4 – 4.0 mIU/L\n"
                "• High TSH → hypothyroidism\n• Low TSH → hyperthyroidism\n\n"
                "Iodine is essential — use iodised salt, seafood and dairy.")

    # ── Nutrition basics ────────────────────────────────────
    if "bmi" in q or "body mass index" in q:
        return ("BMI (Body Mass Index) is a measure of body fat based on height and weight. "
                "Formula: weight(kg) / height(m)². "
                "Under 18.5 = Underweight, 18.5–24.9 = Normal, 25–29.9 = Overweight, 30+ = Obese.")
    if "protein" in q:
        return ("Protein is a macronutrient essential for muscle repair, immune function, and "
                "enzyme production. The recommended daily intake is 0.8 g per kg of body weight "
                "for adults. Good sources include eggs, lean meat, legumes, and dairy.")
    if "vitamin" in q and " d" in q:
        return ("Vitamin D helps the body absorb calcium and supports bone health and immunity.\n\n"
                "📊 RDA: 600 – 800 IU/day.\n☀️ Sources: sunlight, fatty fish, fortified milk, egg yolks.\n"
                "Deficiency is very common — consider a blood test.")
    if "vitamin" in q and " b12" in q:
        return ("Vitamin B12 is essential for nerve function, DNA synthesis and red blood cell formation.\n\n"
                "📊 RDA: 2.4 µg/day.\n🥩 Sources: meat, fish, dairy, eggs (vegans should supplement).\n"
                "Deficiency causes anaemia and neurological damage.")
    if "vitamin" in q and "c" in q:
        return ("Vitamin C (ascorbic acid) is an antioxidant that supports immune health, "
                "collagen synthesis, and iron absorption. RDA: 65–90 mg/day for adults. "
                "Rich sources: citrus fruits, bell peppers, broccoli.")
    if "carb" in q or "carbohydrate" in q:
        return ("Carbohydrates are the body's main energy source.\n\n📊 Should provide 45–65% "
                "of daily calories.\n✅ Prefer complex carbs: oats, brown rice, whole wheat, "
                "vegetables.\n❌ Limit simple carbs: white bread, sugary drinks, sweets.")
    if "fat" in q or "lipid" in q:
        return ("Dietary fats provide energy, support cell growth and absorb vitamins A, D, E and K.\n\n"
                "📊 Recommended: 20–35% of daily calories.\n✅ Healthy: avocado, olive oil, nuts, fish\n"
                "❌ Limit: trans fats and excess saturated fat.")
    if "calori" in q or "kcal" in q:
        return ("Calories (kcal) measure the energy in food. Adults generally need 1,800–2,400 kcal/day "
                "depending on age, sex, and activity level. NutriCare AI tracks your daily intake "
                "through food image detection.")
    if "sugar" in q or "glucose" in q:
        return ("Sugar (glucose) is the body's primary energy source. Normal fasting blood glucose "
                "is 70–100 mg/dL. Excess sugar consumption is linked to obesity, Type 2 diabetes, "
                "and cardiovascular disease. WHO recommends limiting free sugar to <25 g/day.")
    if "iron" in q:
        return ("Iron is essential for haemoglobin production and oxygen transport. "
                "RDA: 8 mg/day (men), 18 mg/day (women). Sources: red meat, spinach, lentils, "
                "fortified cereals. Iron deficiency is the most common nutritional deficiency worldwide.")
    if "fibre" in q or "fiber" in q:
        return ("Dietary fibre supports digestive health, controls blood sugar, and reduces cholesterol. "
                "RDA: 25 g/day (women), 38 g/day (men). Sources: whole grains, fruits, vegetables, legumes.")
    if "calcium" in q:
        return ("Calcium is critical for bone and teeth health, nerve signalling, and muscle function. "
                "RDA: 1,000 mg/day for adults (1,200 mg for women 51+). Sources: dairy, fortified plant "
                "milks, leafy greens, tofu.")
    if "zinc" in q:
        return ("Zinc supports immune function, wound healing and DNA synthesis. "
                "RDA: 8–11 mg/day. Sources: meat, shellfish, legumes, seeds and nuts.")
    if "potassium" in q:
        return ("Potassium regulates fluid balance, nerve signals and muscle contractions. "
                "RDA: 2,600–3,400 mg/day. Sources: bananas, potatoes, avocado, spinach, beans.")
    if "sodium" in q or "salt" in q:
        return ("Sodium regulates fluid balance and blood pressure.\n📊 WHO limit: < 2,000 mg/day "
                "(about 5 g salt).\n⚠️ Excess sodium raises blood pressure — limit processed food.")
    if "water" in q or "hydrat" in q or "dehydrat" in q:
        return ("Water is essential for digestion, temperature regulation and joint lubrication.\n\n"
                "📊 Daily recommendation:\n• Women: ~2.7 L\n• Men: ~3.7 L\n"
                "Increase intake during exercise, heat or illness.")
    if "weight loss" in q or "lose weight" in q:
        return ("Healthy weight-loss tips:\n\n1️⃣ Calorie deficit of 300–500 kcal/day\n"
                "2️⃣ High protein to preserve muscle\n3️⃣ More fibre for fullness\n"
                "4️⃣ Limit refined carbs and added sugar\n5️⃣ 150+ min/week of activity\n"
                "6️⃣ Sleep 7–9 hours")

    # ── Greetings / capability ──────────────────────────────
    if any(g in q for g in ("hello", "hi ", "hey", "good morning", "good afternoon", "namaste")) or q.strip() in ("hi", "hey"):
        return ("Hello! 👋 I'm NutriCare AI. I can help with:\n\n🩸 Blood report values "
                "(HB, WBC, RBC, HbA1c)\n🥗 Nutrition questions (protein, vitamins, minerals)\n"
                "📊 BMI, blood sugar, cholesterol\n🍽️ Food image detection & diet tips\n\n"
                "What would you like to know?")
    if "what can you do" in q or "help" in q or "features" in q:
        return ("I'm NutriCare AI! I can:\n\n✅ Explain blood test results (HB, WBC, HbA1c…)\n"
                "✅ Nutrition info (vitamins, minerals, macros)\n✅ BMI calculation and interpretation\n"
                "✅ Blood sugar and diabetes info\n✅ Diet and healthy-eating tips\n"
                "✅ Detect food from a photo (upload an image)\n\nJust type your question!")

    return None


# ============================================================
# FOOD PREDICTION
#   1. NutriCare ViT (43 Indian foods, bundled in backend/models)
#   2. fallback → nateraw/food (101 classes, needs a download)
# ============================================================

vit_pipeline = None
vit_pipeline_failed = False


def load_vit_model():
    """Fallback image classifier (nateraw/food) — loaded lazily."""
    global vit_pipeline, vit_pipeline_failed
    if vit_pipeline is not None:
        return vit_pipeline
    if vit_pipeline_failed:
        return None
    try:
        from transformers import pipeline
        print("🍽️  Loading fallback ViT food classifier (nateraw/food)…")
        vit_pipeline = pipeline("image-classification", model="nateraw/food", top_k=5)
        print("✅ Fallback ViT food classifier loaded.")
        return vit_pipeline
    except Exception as e:
        vit_pipeline_failed = True
        print(f"⚠️  ViT model load error: {e}")
        return None


def decode_image(image_base64: str):
    """data-URI or raw base64 → PIL image."""
    from PIL import Image

    raw = image_base64
    if "," in raw:
        raw = raw.split(",", 1)[1]

    img_bytes = base64.b64decode(raw)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


# Minimal nutrition database for the fallback classifier.
NUTRITION_DB = {
    "pizza":          {"kcal": 266, "protein_g": 11, "carbs_g": 33, "fat_g": 10, "sugar_g": 3.6, "fibre_g": 2.3},
    "hamburger":      {"kcal": 295, "protein_g": 17, "carbs_g": 24, "fat_g": 14, "sugar_g": 5,   "fibre_g": 1},
    "sushi":          {"kcal": 200, "protein_g": 9,  "carbs_g": 38, "fat_g": 2,  "sugar_g": 4,   "fibre_g": 0.5},
    "salad":          {"kcal": 60,  "protein_g": 3,  "carbs_g": 10, "fat_g": 1,  "sugar_g": 4,   "fibre_g": 3},
    "french_fries":   {"kcal": 365, "protein_g": 4,  "carbs_g": 48, "fat_g": 17, "sugar_g": 0.5, "fibre_g": 3.8},
    "ice_cream":      {"kcal": 207, "protein_g": 3.5,"carbs_g": 24, "fat_g": 11, "sugar_g": 21,  "fibre_g": 0},
    "apple_pie":      {"kcal": 237, "protein_g": 2,  "carbs_g": 36, "fat_g": 11, "sugar_g": 16,  "fibre_g": 2},
    "spaghetti":      {"kcal": 158, "protein_g": 6,  "carbs_g": 31, "fat_g": 1,  "sugar_g": 1,   "fibre_g": 2},
    "fried_rice":     {"kcal": 238, "protein_g": 6,  "carbs_g": 40, "fat_g": 6,  "sugar_g": 2,   "fibre_g": 2},
    "chicken_curry":  {"kcal": 243, "protein_g": 20, "carbs_g": 10, "fat_g": 13, "sugar_g": 3,   "fibre_g": 2},
}

DEFAULT_NUTRITION = {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "sugar_g": 0, "fibre_g": 0}


def _predict_with_local_model(image_base64: str) -> Optional[Dict]:
    """NutriCare's own 43-class ViT (backend/models) — runs fully offline."""
    try:
        from services.ml_api import FoodImageRequest, predict_food as local_predict
        result = local_predict(FoodImageRequest(image_base64=image_base64))
        result["model_source"] = "nutricare_vit_43"
        return result
    except HTTPException as e:
        print(f"⚠️  Local food classifier failed: {e.detail}")
    except Exception as e:
        print(f"⚠️  Local food classifier failed: {e}")
    return None


@app.post("/predict-food")
def predict_food(req: FoodRequest):
    """
    Accepts a base64-encoded image (data-URI or raw base64).
    Returns food name, confidence, top-5 predictions, nutrition facts
    and risk flags.
    """
    # Validate the payload first so bad input still yields a 400.
    try:
        decode_image(req.image_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    # ── 1. NutriCare ViT (bundled, fast, offline) ────────────
    local_result = _predict_with_local_model(req.image_base64)
    if local_result is not None:
        return local_result

    # ── 2. Fallback: nateraw/food ────────────────────────────
    model = load_vit_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="No food classifier available. Expected the bundled model at "
                   "backend/models/NutriCare_Food_Classifier_Final, or run: "
                   "pip install transformers torch pillow"
        )

    try:
        image   = decode_image(req.image_base64)
        results = model(image)
        # pipeline(top_k=5) returns [[{label, score}, …]] for a single image
        if results and isinstance(results[0], list):
            results = results[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

    top      = results[0]
    food_key = top["label"].replace(" ", "_").lower()
    conf     = round(top["score"] * 100, 1)

    nutrition = DEFAULT_NUTRITION.copy()
    for key, data in NUTRITION_DB.items():
        if key in food_key or food_key in key:
            nutrition = data
            break

    risk_flags = {
        "high_sugar":    nutrition["sugar_g"]  > 15,
        "high_sodium":   False,   # extend when sodium data available
        "high_calories": nutrition["kcal"]      > 400,
    }

    top5 = [
        {
            "rank":       i + 1,
            "food":       r["label"].replace(" ", "_").lower(),
            "confidence": round(r["score"] * 100, 1)
        }
        for i, r in enumerate(results[:5])
    ]

    return {
        "food_name":    food_key,
        "display_name": top["label"].title(),
        "confidence":   conf,
        "nutrition":    nutrition,
        "risk_flags":   risk_flags,
        "top5":         top5,
        "model_source": "nateraw_food"
    }


# ============================================================
# COMBINED ML MODEL  (energy / diabetes / hypertension / obesity)
# ============================================================

try:
    from services.ml_api import NutritionData, predict_nutrition
    app.add_api_route("/predict", predict_nutrition, methods=["POST"])
    print("✅ /predict route registered (combined ML model).")
except Exception as e:
    print(f"⚠️  Could not register /predict route: {e}")


# ============================================================
# PERSONALISED FOOD DATA  (report → what the user can eat)
# ============================================================

MASTER_CSV = os.path.join(
    PROJECT_DIR, "RAG", "data", "NutriCare_AI_Master_ML_Ready_v18 (1).csv"
)

# Categories that never belong in a healthy daily plan.
JUNK_CATEGORIES = {
    "High-Risk Lifestyle", "Indian Sweets", "Processed Dessert",
    "Processed Food", "Sweetener", "Processed Beverage",
    "Snacks and Fast Food",
}

BREAKFAST_CATEGORIES = {
    "Indian Breakfast", "Cereals and Millets", "Egg", "Milk",
    "Dairy Product", "Fruits", "Beverage", "Beverages",
}

MAIN_CATEGORIES = {
    "Marine Fish", "Poultry", "Grain Legumes", "Vegetables", "Vegetable",
    "Green Leafy Vegetables", "Cereals and Millets", "Indian Breakfast",
    "Nuts", "Egg", "Dairy Product", "Milk",
}

SNACK_CATEGORIES = {
    "Nuts", "Fruits", "Milk", "Dairy Product", "Indian Breakfast", "Egg",
}

# Dataset classification → severity (0 = eat freely, 1 = moderate, 2 = limit)
_CLASS_RANK = {"protective": 0, "safe": 0, "monitor": 1, "restrict": 2}

CONDITION_LABELS = {
    "diabetes":    "diabetes",
    "hypertension": "high blood pressure",
    "obesity":     "obesity / excess weight",
}

_foods_cache = None


def _num(value) -> Optional[float]:
    try:
        f = float(value)
        return None if f != f else f          # NaN check
    except (TypeError, ValueError):
        return None


def _clean_name(name) -> str:
    """'Poha (Rice Flakes) (North Region)' → 'Poha (Rice Flakes)'"""
    name = str(name or "").strip()
    for region in ("National Average", "North Region", "South Region",
                   "East Region", "West Region", "Central Region",
                   "Northeast Region"):
        name = name.replace(f" ({region})", "")
    return name.strip()


def load_food_records() -> List[Dict]:
    """
    Load the master nutrition dataset (foods with diabetes / hypertension /
    obesity classifications). Loaded once, lazily.
    """
    global _foods_cache
    if _foods_cache is not None:
        return _foods_cache

    records: List[Dict] = []
    try:
        import pandas as pd

        if not os.path.isfile(MASTER_CSV):
            print(f"⚠️  Nutrition dataset not found: {MASTER_CSV}")
        else:
            df = pd.read_csv(MASTER_CSV)
            # National rows first → each food kept once, region variants skipped
            order = df.assign(
                _non_nat=~df["Region"].astype(str).str.contains("National", na=False)
            ).sort_values("_non_nat")

            seen = set()
            for _, row in order.iterrows():
                name = _clean_name(row.get("Food_Name"))
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())

                records.append({
                    "name":       name,
                    "category":   str(row.get("Category") or "").strip(),
                    "serving_g":  _num(row.get("Serving_Size_g")),
                    "kcal":       _num(row.get("Energy_kcal")),
                    "protein_g":  _num(row.get("Protein_g")),
                    "carbs_g":    _num(row.get("Carbohydrate_g")),
                    "fat_g":      _num(row.get("Total_Fat_g")),
                    "sugar_g":    _num(row.get("Total_Free_Sugars_g")),
                    "fibre_g":    _num(row.get("Dietary_Fibre_g")),
                    "sodium_mg":  _num(row.get("Sodium_mg")),
                    "potassium_mg": _num(row.get("Potassium_mg")),
                    "diabetes":   str(row.get("Diabetes_Classification") or "").strip(),
                    "hypertension": str(row.get("Hypertension_Classification") or "").strip(),
                    "obesity":    str(row.get("Obesity_Classification") or "").strip(),
                    "cooking":    str(row.get("Cooking_Method") or "").strip(),
                })

        print(f"✅ Nutrition dataset loaded — {len(records)} unique foods")
    except Exception as e:
        print(f"⚠️  Could not load nutrition dataset: {e}")

    _foods_cache = records
    return records


def resolve_conditions(profile: Dict) -> List[str]:
    """Derive the user's conditions from their report/profile."""
    conditions: List[str] = []

    raw = profile.get("conditions") or []
    if isinstance(raw, str):
        raw = [raw]

    for value in raw:
        v = str(value).strip().lower()
        if v in ("hypertension", "high bp", "high blood pressure", "bp", "htn"):
            key = "hypertension"
        elif v in ("diabetes", "sugar", "high sugar", "blood sugar", "high glucose"):
            key = "diabetes"
        elif v in ("obesity", "obese", "overweight", "weight", "weight loss", "fat"):
            key = "obesity"
        else:
            continue
        if key not in conditions:
            conditions.append(key)

    # BMI category implies a weight-management goal
    cat = str(profile.get("bmi_category") or profile.get("bmiCategory") or "").lower()
    if "obes" in cat or "overweight" in cat:
        if "obesity" not in conditions:
            conditions.append("obesity")

    return conditions


def _rank(food: Dict, condition: str) -> int:
    label = str(food.get(condition, "")).strip().lower()
    return _CLASS_RANK.get(label, 1)          # unknown → moderate


def daily_kcal_target(profile: Dict) -> int:
    """Daily energy target from the profile (Mifflin-St Jeor × 1.3)."""
    try:
        weight = float(profile.get("weight") or 0)
        height = float(profile.get("height") or 0)
        age    = float(profile.get("age") or 0)
        if weight > 0 and height > 0 and age > 0:
            male = str(profile.get("gender") or "").lower().startswith("m")
            bmr = 10 * weight + 6.25 * height - 5 * age + (5 if male else -161)
            tdee = bmr * 1.3
            cat = str(profile.get("bmi_category") or profile.get("bmiCategory") or "").lower()
            if "obes" in cat:
                tdee *= 0.8                    # weight-loss deficit
            elif "overweight" in cat:
                tdee *= 0.9
            elif "underweight" in cat:
                tdee *= 1.1
            return int(max(1200, min(3200, round(tdee / 50) * 50)))
    except (TypeError, ValueError):
        pass
    return 2000


def _pick_varied(items: List[Dict], n: int) -> List[Dict]:
    """Round-robin over categories so recommendations are diverse."""
    by_cat: Dict[str, List[Dict]] = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    picked: List[Dict] = []
    while len(picked) < n and by_cat:
        for cat in list(by_cat.keys()):
            if not by_cat[cat]:
                del by_cat[cat]
                continue
            picked.append(by_cat[cat].pop(0))
            if len(picked) >= n:
                break
    return picked


def _why(item: Dict, conditions: List[str], group: str) -> str:
    classes = item.get("classes", {})          # {condition: "Safe" | "Monitor" | …}

    def rank_of(cond: str) -> int:
        return _CLASS_RANK.get(str(classes.get(cond, "")).lower(), 1)

    if group == "limit":
        parts = [f"{CONDITION_LABELS[c]} → {classes.get(c, '')}"
                 for c in conditions if rank_of(c) == 2]
        return "Keep occasional: " + ", ".join(parts) if parts else "Keep occasional"

    if group == "moderate":
        prefix = "Moderate portions"
        mods = [f"{CONDITION_LABELS[c]}: {classes.get(c, '')}"
                for c in conditions if rank_of(c) == 1]
        if mods:
            prefix += " (" + ", ".join(mods) + ")"
    else:
        safe = [CONDITION_LABELS[c] for c in conditions if rank_of(c) == 0]
        prefix = "Safe for " + (", ".join(safe) or "balanced diets")

    bits = []
    if item.get("sodium_mg") is not None and item["sodium_mg"] <= 120:
        bits.append("low sodium")
    if item.get("sugar_g") is not None and item["sugar_g"] <= 5:
        bits.append("low sugar")
    if item.get("fibre_g") is not None and item["fibre_g"] >= 5:
        bits.append("high fibre")
    if item.get("kcal") is not None and item["kcal"] <= 200:
        bits.append(f"light ({int(item['kcal'])} kcal)")
    if item.get("protein_g") is not None and item["protein_g"] >= 15:
        bits.append("high protein")

    return prefix + (" • " + ", ".join(bits) if bits else "")


def recommend_foods(profile: Dict, per_group: int = 8) -> Optional[Dict]:
    """
    Split the dataset into foods the user can eat freely / in moderation /
    should limit — judged by the classifications for their conditions.
    """
    foods = load_food_records()
    if not foods:
        return None

    conditions = resolve_conditions(profile) or ["diabetes", "hypertension", "obesity"]

    groups = {"eat_more": [], "moderate": [], "limit": []}
    counts = {"eat_more": 0, "moderate": 0, "limit": 0}

    for food in foods:
        worst = max(_rank(food, c) for c in conditions)
        if food["category"] in JUNK_CATEGORIES:
            worst = max(worst, 1)

        item = {
            "food":      food["name"],
            "category":  food["category"],
            "kcal":      food["kcal"],
            "protein_g": food["protein_g"],
            "sodium_mg": food["sodium_mg"],
            "sugar_g":   food["sugar_g"],
            "fibre_g":   food["fibre_g"],
            "classes":   {c: str(food.get(c, "")).title() for c in conditions},
        }

        if worst == 0:
            groups["eat_more"].append(item)
        elif worst == 1:
            groups["moderate"].append(item)
        else:
            groups["limit"].append(item)

    counts = {k: len(v) for k, v in groups.items()}

    # Order by the nutrient that matters for the user's conditions
    if "hypertension" in conditions:
        key = lambda x: x["sodium_mg"] if x["sodium_mg"] is not None else 99999
    elif "diabetes" in conditions:
        key = lambda x: x["sugar_g"] if x["sugar_g"] is not None else 99999
    else:
        key = lambda x: x["kcal"] if x["kcal"] is not None else 99999

    groups["eat_more"].sort(key=key)
    groups["moderate"].sort(key=key)
    groups["limit"].sort(key=lambda x: -(x["kcal"] or 0))

    for group_name, items in groups.items():
        for item in items:
            item["why"] = _why(item, conditions, group_name)

    return {
        "conditions": conditions,
        "counts":     counts,
        "eat_more":   _pick_varied(groups["eat_more"], per_group),
        "moderate":   _pick_varied(groups["moderate"], per_group),
        "limit":      _pick_varied(groups["limit"], per_group),
    }


def build_personal_note(profile: Dict) -> str:
    """Short personalisation block injected into the RAG prompt."""
    if not profile:
        return ""

    parts = []
    age    = profile.get("age")
    gender = profile.get("gender")
    bmi    = profile.get("bmi")
    cat    = profile.get("bmi_category") or profile.get("bmiCategory")
    if age and gender:
        parts.append(f"{age}-year-old {gender}")
    if bmi:
        parts.append(f"BMI {bmi}" + (f" ({cat})" if cat else ""))

    conditions = resolve_conditions(profile)
    if conditions:
        parts.append("conditions: " + ", ".join(CONDITION_LABELS[c] for c in conditions))
    if not parts:
        return ""

    note = "\nPersonalisation (use when relevant):\n" + \
           "User profile: " + "; ".join(parts) + ".\n"

    rec = recommend_foods(profile, per_group=5)
    if rec:
        safe  = ", ".join(i["food"] for i in rec["eat_more"][:5])
        avoid = ", ".join(i["food"] for i in rec["limit"][:3])
        note += f"Safe foods for them: {safe}.\nFoods to limit: {avoid}.\n"
        note += ("When asked what to eat, recommend their safe foods and explain "
                 "how they help with their conditions (e.g. lowering weight or blood pressure).")

    return note


class RecommendRequest(BaseModel):
    profile: dict = {}


class PlanRequest(BaseModel):
    profile: dict = {}
    start_date: Optional[str] = None      # YYYY-MM-DD (defaults to tomorrow)


@app.post("/food-recommend")
def food_recommend(req: RecommendRequest):
    """Report-based food advice: eat freely / moderate / limit lists."""
    profile = req.profile or {}
    rec = recommend_foods(profile)
    if rec is None:
        raise HTTPException(
            status_code=503,
            detail="Nutrition dataset unavailable — expected RAG/data/"
                   "NutriCare_AI_Master_ML_Ready_v18 (1).csv"
        )

    conditions = rec["conditions"]
    cat = profile.get("bmi_category") or profile.get("bmiCategory") or "Not set"

    goal_bits = []
    if "obesity" in conditions:
        goal_bits.append("reduce body weight")
    if "hypertension" in conditions:
        goal_bits.append("lower blood pressure")
    if "diabetes" in conditions:
        goal_bits.append("keep blood sugar steady")

    summary = (
        f"Report review — BMI {profile.get('bmi', 'n/a')} ({cat}), focus: "
        + (", ".join(goal_bits) if goal_bits else "balanced nutrition")
        + f". {rec['counts']['eat_more']} foods are classified Safe/Protective for you, "
        + f"{rec['counts']['limit']} should be limited."
    )

    return {
        "success":  True,
        "summary":  summary,
        "profile": {
            "bmi":              profile.get("bmi"),
            "bmi_category":     cat,
            "conditions":       conditions,
            "daily_kcal_target": daily_kcal_target(profile),
        },
        "counts": rec["counts"],
        "eat_more":   rec["eat_more"],
        "moderate":   rec["moderate"],
        "limit":      rec["limit"],
    }


@app.post("/plan/15-day")
def plan_15_day(req: PlanRequest):
    """Build a 15-day daily food chart tailored to the user's report."""
    profile = req.profile or {}
    foods = load_food_records()
    if not foods:
        raise HTTPException(
            status_code=503,
            detail="Nutrition dataset unavailable — expected RAG/data/"
                   "NutriCare_AI_Master_ML_Ready_v18 (1).csv"
        )

    conditions = resolve_conditions(profile) or ["diabetes", "hypertension", "obesity"]
    target = daily_kcal_target(profile)

    def allowed(food: Dict) -> bool:
        if food["category"] in JUNK_CATEGORIES or not food.get("kcal"):
            return False
        return max(_rank(food, c) for c in conditions) == 0

    pool = [f for f in foods if allowed(f)]
    strict = bool(pool)
    if not strict:                       # ultra-strict filter too small → relax
        pool = [f for f in foods
                if f["category"] not in JUNK_CATEGORIES and f.get("kcal")]

    def sort_key(f):
        return (f["category"], f["kcal"] or 0, f["name"])

    CERIAL_CATS  = {"Cereals and Millets", "Indian Breakfast"}
    PROTEIN_CATS = {"Grain Legumes", "Marine Fish", "Poultry", "Egg"}
    VEG_CATS     = {"Vegetables", "Vegetable", "Green Leafy Vegetables"}
    BFAST_CATS   = {"Cereals and Millets", "Indian Breakfast", "Egg"}
    SIDE_CATS    = {"Milk", "Dairy Product", "Fruits", "Beverage", "Beverages"}

    def take(cats):
        items = sorted([f for f in pool if f["category"] in cats], key=sort_key)
        return items or pool

    cereal     = take(CERIAL_CATS)
    protein    = take(PROTEIN_CATS)
    veg        = take(VEG_CATS)
    bfast_main = take(BFAST_CATS)
    bfast_side = take(SIDE_CATS)
    snacks     = take(SNACK_CATEGORIES)

    try:
        start = (datetime.date.fromisoformat(req.start_date)
                 if req.start_date else datetime.date.today() + datetime.timedelta(days=1))
    except ValueError:
        start = datetime.date.today() + datetime.timedelta(days=1)

    # (slot label, food pool, share of the daily target, rotation stride)
    slot_config = (
        ("Breakfast",         bfast_main, 0.22, 3),
        ("Breakfast side",    bfast_side, 0.08, 4),
        ("Mid-morning snack", snacks,     0.10, 5),
        ("Lunch staple",      cereal,     0.20, 6),
        ("Lunch protein",     protein,    0.15, 7),
        ("Lunch vegetable",   veg,        0.05, 8),
        ("Dinner staple",     cereal,     0.12, 9),
        ("Dinner protein",    protein,    0.08, 10),
    )

    days = []
    for i in range(15):
        day_date = start + datetime.timedelta(days=i)
        used = set()
        meals = []

        for slot, slot_pool, share, stride in slot_config:
            if not slot_pool:
                continue
            index = (i * stride + len(meals)) % len(slot_pool)
            food = slot_pool[index]
            tries = 0
            while food["name"] in used and tries < len(slot_pool):
                tries += 1
                food = slot_pool[(index + tries) % len(slot_pool)]
            used.add(food["name"])

            meals.append({
                "slot":        slot,
                "food":        food["name"],
                "category":    food["category"],
                "kcal":        food["kcal"],
                "serving_g":   food["serving_g"],
                "protein_g":   food["protein_g"],
                "sodium_mg":   food["sodium_mg"],
                "target_kcal": round(target * share),
            })

        # Balance the day so the planned total lands near the calorie target
        raw_total = sum(m["kcal"] or 0 for m in meals)
        factor = (target / raw_total) if raw_total else 1.0
        factor = max(0.8, min(1.75, factor))

        for m in meals:
            base = m["kcal"] or 0
            m["kcal"] = round(base * factor)
            m["sodium_mg"] = round((m["sodium_mg"] or 0) * factor)
            if base < 50 or abs(factor - 1) < 0.1:
                m["portion"] = "1 serving"
            else:
                m["portion"] = f"{factor:.1f} servings"

        total_kcal   = round(sum(m["kcal"] or 0 for m in meals))
        total_sodium = round(sum(m["sodium_mg"] or 0 for m in meals))

        days.append({
            "day":        i + 1,
            "date":       day_date.isoformat(),
            "weekday":    day_date.strftime("%A"),
            "meals":      meals,
            "total_kcal": total_kcal,
            "sodium_mg":  total_sodium,
        })

    avg_kcal = round(sum(d["total_kcal"] for d in days) / len(days))

    cat = profile.get("bmi_category") or profile.get("bmiCategory") or "Not set"
    summary = (
        f"15-day food chart for BMI {profile.get('bmi', 'n/a')} ({cat}) — "
        f"target ≈ {target} kcal/day, chart averages {avg_kcal} kcal/day. "
        + "Only foods classified Safe/Protective for "
        + ", ".join(CONDITION_LABELS[c] for c in conditions)
        + " were used, so following it helps "
        + ("reduce weight and blood pressure" if "obesity" in conditions and "hypertension" in conditions
           else "improve your condition")
        + "."
    )

    return {
        "success":         True,
        "summary":         summary,
        "start_date":      start.isoformat(),
        "daily_kcal_target": target,
        "conditions":      conditions,
        "bmi_category":    cat,
        "strict_filter":   strict,
        "avg_kcal":        avg_kcal,
        "days":            days,
    }


# ============================================================
# INGEST HELPER  (call this once to load your documents)
# ============================================================

def ingest_documents(texts: List[str], sources: List[str]):
    """
    Call this function once to populate ChromaDB with your
    nutrition knowledge documents.

    Example:
        from rag_service import ingest_documents
        ingest_documents(
            texts=["Haemoglobin (HB) is the iron-containing protein…"],
            sources=["WHO Nutrition Guide 2023"]
        )
    """
    if chroma_collection is None or embedder is None:
        print("❌ ChromaDB not ready. Cannot ingest.")
        return

    vecs  = embedder.encode(texts).tolist()
    ids   = [f"doc_{i}" for i in range(len(texts))]
    metas = [{"source": s} for s in sources]

    chroma_collection.upsert(
        ids=ids,
        embeddings=vecs,
        documents=texts,
        metadatas=metas
    )
    print(f"✅ Ingested {len(texts)} documents into ChromaDB.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    provider, model = resolve_llm()
    print(f"🚀 NutriCare AI RAG Service  →  http://127.0.0.1:{PORT}")
    print(f"   LLM provider : {provider}  ({model or 'n/a'})")
    print(f"   ChromaDB path: {chroma_path_used or '…'}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
