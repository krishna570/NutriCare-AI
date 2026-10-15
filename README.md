# NutriCare AI — Smart Nutrition Assistant

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

1. **NutriCare - Node (8000)** → runs `npm start`
2. **NutriCare - Python RAG (5000)** → runs `python rag_service.py`

Wait until the Python window shows `Started server process` **and** finishes loading
the Chroma knowledge base (about 10–30 seconds the first time), then open:

```
http://127.0.0.1:8000
```

### Manual start (two terminals, same result)

```bat
:: Terminal 1 — Node backend (port 8000)
cd /d "D:\JNEC\Nutricare AI\backend"
npm start
```

```bat
:: Terminal 2 — Python RAG service (port 5000)
cd /d "D:\JNEC\Nutricare AI\backend"
python rag_service.py
```

> ⚠️ **Port 5000 must run `backend\rag_service.py`** — not `services\ml_api.py`
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

- Open `http://127.0.0.1:8000` — you are redirected to the dashboard
  (register first via **Login → Register**; OTP is not required).
- **Test account:** `krishna@test.com` / `123456`

What you can do on the dashboard:

| Feature | Where |
|---|---|
| 📷 Food image detection (43-class ViT, nutrition breakdown) | Upload & Analyze → Food Image |
| 🩸 Blood sugar / health report upload & analysis | Upload & Analyze |
| 🤖 Ask the RAG chat bot (answers in ~5–60 s via Ollama) | NutriCare AI Assistant |
| 🥗 Foods I Can Eat — report-based recommendations | My Food Plan → Foods I Can Eat |
| 📅 15-day daily food chart + CSV download + Print/PDF | My Food Plan → Create 15-Day Food Chart |
| 👟 Live step tracking (phone motion sensor) | Live Step Tracker |
| 👤 BMI shown in the top bar; click avatar to log out | Navbar |
| Admin: users / db info | `/Admin/admin.html` |

On a phone: the sidebar collapses behind the **☰** menu button; the 15-day chart
scrolls sideways inside its box.

---

## 5. Key API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/chat` | RAG chat (forwards user `profile` for personalised answers) |
| POST | `/api/recommend` | Foods you can eat (eat more / moderate / limit) |
| POST | `/api/plan` | 15-day food chart (proxies Python `/plan/15-day`) |
| POST | `/api/analyze-food` | Food image → nutrition |
| GET | `/api/health`, `/api/ml/health` | Service health |
| POST | Python `:5000/rag-chat`, `/predict-food`, `/food-recommend`, `/plan/15-day` | RAG / ML internals |

---

## 6. Project structure

```
Nutricare AI/
├── start.bat                  ← double-click to start both services
├── README.md                  ← this file
├── NutriCare-AI-Run-Guide.pdf ← printable step-by-step guide
├── Main/                      ← dashboard (HTML/CSS/JS)
├── Login/                     ← login + registration (OTP removed)
├── Admin/                     ← admin dashboard
├── backend/
│   ├── server.js              ← Node server (port 8000): static + API proxy
│   ├── rag_service.py         ← Python service (port 5000): RAG, ML, food plan
│   ├── services/ml_api.py     ← 43-class food classifier (loaded BY rag_service)
│   ├── data/users.json        ← user accounts (file storage)
│   └── requirements.txt
├── RAG/
│   ├── chroma_db/             ← Chroma vector DB (151,210 docs, 384-dim, L2)
│   ├── data/                  ← nutrition master CSV + QA dataset
│   └── create_database.py     ← rebuild the knowledge base (optional)
└── test_images/               ← sample food images for testing
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| *"Food chart service returned an error."* | Wrong Python file on port 5000 | Stop it; run `python rag_service.py` (see start.bat) |
| `EADDRINUSE` on 8000/5000 | Old instance still running | Close old terminal windows (or end the process on that port) |
| Chat answers slowly (5–60 s) | Ollama generation time (normal) | Wait; keep `llama3.2` installed |
| Chat says no context / weak answers | Ollama not running | Start `ollama serve`, check `ollama list` |
| Python exits on startup | Missing packages | `pip install -r backend\requirements.txt` |
| First chart/recommendation click is slow | Model + Chroma loading | Only on cold start; later calls take <1 s |
| Page opens but assets 404 | Wrong URL | Always start at `http://127.0.0.1:8000` |

---

## 8. Stop the application

Close both terminal windows started by `start.bat`, or press `Ctrl+C` inside each.

---

## Tech stack

Frontend: vanilla HTML/CSS/JS · Backend: Node.js (Express + Axios proxy) ·
AI: FastAPI + LangChain + Chroma (all-MiniLM-L6-v2) + Ollama (llama3.2) ·
ML: PyTorch ViT food classifier (43 classes) + nutrition CSV database

> ⚠️ NutriCare AI is for research and educational purposes. Recommendations come
> from a dataset classifier and are **not** a substitute for professional medical
> advice.
