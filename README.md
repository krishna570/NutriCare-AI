# NutriCare AI ΓÇö Smart Nutrition Assistant

A full-stack nutrition & health assistant: food-image detection, blood/health report
analysis, a RAG chat bot over a 151k-document nutrition knowledge base, personalised
food recommendations from the user's health profile, and a generated 15-day daily
food chart (with CSV export and print/PDF).

A printable step-by-step version of this guide is in
**[NutriCare-AI-Run-Guide.pdf](NutriCare-AI-Run-Guide.pdf)**.

---

## 1. What you need first (prerequisites)

| Requirement | Used for | Check with |
|---|---|---|
| **Node.js 18+** (project runs on v24) | Backend web server, port **8000** | `node -v` |
| **Python 3.13** | RAG / ML service, port **5000** | `python --version` |
| **Ollama** with `llama3.2` model | AI answers in the chat bot | `ollama list` |
| Python packages | RAG service dependencies | `pip install -r backend/requirements.txt` |

First-time setup:

```bat
cd /d "D:\JNEC\Nutricare AI"
npm install
pip install -r backend\requirements.txt
ollama pull llama3.2        ; if "ollama list" does not show it
```

---

## 2. Start the application (easiest way)

**Double-click [`start.bat`](start.bat)** in the project folder.

It opens two terminal windows:

1. **NutriCare - Node (8000)** ΓåÆ runs `npm start`
2. **NutriCare - Python RAG (5000)** ΓåÆ runs `python rag_service.py`

Wait until the Python window shows `Started server process` **and** finishes loading
the Chroma knowledge base (about 10ΓÇô30 seconds the first time), then open:

```
http://127.0.0.1:8000
```

### Manual start (two terminals, same result)

```bat
:: Terminal 1 ΓÇö Node backend (port 8000)
cd /d "D:\JNEC\Nutricare AI\backend"
npm start
```

```bat
:: Terminal 2 ΓÇö Python RAG service (port 5000)
cd /d "D:\JNEC\Nutricare AI\backend"
python rag_service.py
```

> ΓÜá∩╕Å **Port 5000 must run `backend\rag_service.py`** ΓÇö not `services\ml_api.py`
> and not `app.py`. Only `rag_service.py` provides `/rag-chat`, `/predict-food`,
> `/food-recommend` and `/plan/15-day`. If the wrong file runs, the chat and the
> food chart fail with *"Food chart service returned an error."*

---

## 3. Verify it is running

| URL | Expected |
|---|---|
| `http://127.0.0.1:8000/api/health` | JSON with `"status": "ok"` |
| `http://127.0.0.1:8000/api/ml/health` | `"python_ml_service": "online"`, `doc_count: 151210` |
| `http://127.0.0.1:8000/Main/index.html` | Dashboard loads (200) |

Or with curl:

```bat
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:5000/
```

---

## 4. Log in and use the app

- Open `http://127.0.0.1:8000` ΓÇö you are redirected to the dashboard
  (register first via **Login ΓåÆ Register**; OTP is not required).
- **Test account:** `krishna@test.com` / `123456`

What you can do on the dashboard:

| Feature | Where |
|---|---|
| ≡ƒô╖ Food image detection (43-class ViT, nutrition breakdown) | Upload & Analyze ΓåÆ Food Image |
| ≡ƒ⌐╕ Blood sugar / health report upload & analysis | Upload & Analyze |
| ≡ƒñû Ask the RAG chat bot (answers in ~5ΓÇô60 s via Ollama) | NutriCare AI Assistant |
| ≡ƒÑù Foods I Can Eat ΓÇö report-based recommendations | My Food Plan ΓåÆ Foods I Can Eat |
| ≡ƒôà 15-day daily food chart + CSV download + Print/PDF | My Food Plan ΓåÆ Create 15-Day Food Chart |
| ≡ƒæƒ Live step tracking (phone motion sensor) | Live Step Tracker |
| ≡ƒæñ BMI shown in the top bar; click avatar to log out | Navbar |
| Admin: users / db info | `/Admin/admin.html` |

On a phone: the sidebar collapses behind the **Γÿ░** menu button; the 15-day chart
scrolls sideways inside its box.

---

## 5. Key API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/chat` | RAG chat (forwards user `profile` for personalised answers) |
| POST | `/api/recommend` | Foods you can eat (eat more / moderate / limit) |
| POST | `/api/plan` | 15-day food chart (proxies Python `/plan/15-day`) |
| POST | `/api/analyze-food` | Food image ΓåÆ nutrition |
| GET | `/api/health`, `/api/ml/health` | Service health |
| POST | Python `:5000/rag-chat`, `/predict-food`, `/food-recommend`, `/plan/15-day` | RAG / ML internals |

---

## 6. Project structure

```
Nutricare AI/
Γö£ΓöÇΓöÇ start.bat                  ΓåÉ double-click to start both services
Γö£ΓöÇΓöÇ README.md                  ΓåÉ this file
Γö£ΓöÇΓöÇ NutriCare-AI-Run-Guide.pdf ΓåÉ printable step-by-step guide
Γö£ΓöÇΓöÇ Main/                      ΓåÉ dashboard (HTML/CSS/JS)
Γö£ΓöÇΓöÇ Login/                     ΓåÉ login + registration (OTP removed)
Γö£ΓöÇΓöÇ Admin/                     ΓåÉ admin dashboard
Γö£ΓöÇΓöÇ backend/
Γöé   Γö£ΓöÇΓöÇ server.js              ΓåÉ Node server (port 8000): static + API proxy
Γöé   Γö£ΓöÇΓöÇ rag_service.py         ΓåÉ Python service (port 5000): RAG, ML, food plan
Γöé   Γö£ΓöÇΓöÇ services/ml_api.py     ΓåÉ 43-class food classifier (loaded BY rag_service)
Γöé   Γö£ΓöÇΓöÇ data/users.json        ΓåÉ user accounts (file storage)
Γöé   ΓööΓöÇΓöÇ requirements.txt
Γö£ΓöÇΓöÇ RAG/
Γöé   Γö£ΓöÇΓöÇ chroma_db/             ΓåÉ Chroma vector DB (151,210 docs, 384-dim, L2)
Γöé   Γö£ΓöÇΓöÇ data/                  ΓåÉ nutrition master CSV + QA dataset
Γöé   ΓööΓöÇΓöÇ create_database.py     ΓåÉ rebuild the knowledge base (optional)
ΓööΓöÇΓöÇ test_images/               ΓåÉ sample food images for testing
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| *"Food chart service returned an error."* | Wrong Python file on port 5000 | Stop it; run `python rag_service.py` (see start.bat) |
| `EADDRINUSE` on 8000/5000 | Old instance still running | Close old terminal windows (or end the process on that port) |
| Chat answers slowly (5ΓÇô60 s) | Ollama generation time (normal) | Wait; keep `llama3.2` installed |
| Chat says no context / weak answers | Ollama not running | Start `ollama serve`, check `ollama list` |
| Python exits on startup | Missing packages | `pip install -r backend\requirements.txt` |
| First chart/recommendation click is slow | Model + Chroma loading | Only on cold start; later calls take <1 s |
| Page opens but assets 404 | Wrong URL | Always start at `http://127.0.0.1:8000` |

---

## 8. Stop the application

Close both terminal windows started by `start.bat`, or press `Ctrl+C` inside each.

---

## Tech stack

Frontend: vanilla HTML/CSS/JS ┬╖ Backend: Node.js (Express + Axios proxy) ┬╖
AI: FastAPI + LangChain + Chroma (all-MiniLM-L6-v2) + Ollama (llama3.2) ┬╖
ML: PyTorch ViT food classifier (43 classes) + nutrition CSV database

> ΓÜá∩╕Å NutriCare AI is for research and educational purposes. Recommendations come
> from a dataset classifier and are **not** a substitute for professional medical
> advice.
