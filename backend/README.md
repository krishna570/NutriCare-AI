# NutriCare AI - MongoDB Backend Guide

This backend provides MongoDB database persistence for NutriCare AI User Registration, Login Authentication, and the Admin Panel.

---

## 1. Prerequisites: MongoDB

Make sure MongoDB is installed and running on your system, or use a free cloud MongoDB Atlas cluster.

### Option A: Local MongoDB Community Server
1. Download & install MongoDB Community Server from [mongodb.com](https://www.mongodb.com/try/download/community).
2. Start the MongoDB service:
   ```cmd
   net start MongoDB
   ```
   Or start `mongod` in terminal. The default URI is `mongodb://localhost:27017`.

### Option B: MongoDB Atlas (Cloud)
1. Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas).
2. Copy your connection string into `backend/.env`:
   ```env
   MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/nutricare_db?retryWrites=true&w=majority
   ```

---

## 2. Running the Backend

Two processes make up the app — run **both**:

| Process | Command | Port | Serves |
|---|---|---|---|
| Node.js Express | `npm start` | 8000 | Frontend pages + `/api/*` (auth, admin, chat, food) |
| Python RAG + ML service | `python rag_service.py` | 5000 | `/rag-chat`, `/predict-food`, `/predict` |

### Option A — Python FastAPI (auth only, replaces Node on port 8000)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```
API Documentation will be available at `http://127.0.0.1:8000/docs`.

> Note: this option does **not** expose the RAG / food-image endpoints —
> it conflicts with the Node server on port 8000, so run it *instead of*
> `npm start`, never alongside it.

### Option B — Node.js Express (recommended) + Python RAG/ML service
```bash
cd backend
npm install
npm start                 # terminal 1 → http://127.0.0.1:8000 (frontend + API)
python rag_service.py     # terminal 2 → http://127.0.0.1:5000 (RAG + ML)
```

The Python service auto-discovers the ChromaDB knowledge base in
`RAG/chroma_db` and the first installed Ollama model (if Ollama is running),
and it serves:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | RAG / ChromaDB / LLM status |
| `POST` | `/rag-chat` | RAG question → grounded answer + sources |
| `POST` | `/predict-food` | NutriCare ViT food image classifier |
| `POST` | `/predict` | Combined ML model (energy / diabetes / hypertension / obesity) |

Build or refresh the knowledge base with:
```bash
cd RAG
python create_database.py   # only needed once, or after changing the CSVs
```

---

## 3. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Check MongoDB connection and server status |
| `POST` | `/api/register` | Register new user into MongoDB database |
| `POST` | `/api/login` | Authenticate email & password from MongoDB |
| `GET` | `/api/admin/users` | List all registered user records for Admin Panel |
| `GET` | `/api/admin/stats` | Compute KPI metrics (total users, average BMI, categories) |
| `DELETE` | `/api/admin/users/{id}` | Delete a user record from MongoDB |
| `GET` | `/api/admin/db-info` | Database schema shown in the Admin panel |
| `POST` | `/api/chat` | Chat → Python RAG service (falls back to built-in answers) |
| `POST` | `/api/food/predict` | Food image → Python ViT classifier |
