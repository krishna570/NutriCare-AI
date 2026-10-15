NutriCare AI — Smart Nutrition Assistant
<p align="center">
  <img src="gif/baymax.gif" alt="Baymax nutrition assistant" width="200">
</p>

<p align="center">
  <strong>AI-powered food recognition, nutrition insights, and personalized food recommendations.</strong>
</p>

NutriCare AI is a full-stack nutrition and health assistant that combines food-image classification, health-report analysis, Retrieval-Augmented Generation (RAG), and personalized food recommendations. It also supports generating a 15-day food chart with CSV export and print/PDF options.
A printable step-by-step setup guide is available in [NutriCare-AI-Run-Guide.pdf](NutriCare-AI-Run-Guide.pdf).
Disclaimer: NutriCare AI is intended for research and educational purposes. Its outputs are not a substitute for professional medical advice, diagnosis, or treatment.

Table of Contents
- Features
- Prerequisites
- Installation
- Start the Application
- Verify the Services
- Using the Application
- API Endpoints
- Project Structure
- Troubleshooting
- Technology Stack
Features
- Food image detection: Classifies food images across 43 categories using a Vision Transformer (ViT) model.
- Nutrition information: Retrieves nutrition information from the project's structured nutrition dataset.
- Health-report analysis: Supports uploading and analyzing blood sugar or health reports.
- RAG-powered assistant: Answers nutrition-related questions using a retrieval-based knowledge base.
- Personalized food recommendations: Provides food suggestions informed by a user's health profile and available report information.
- 15-day food chart: Generates a daily food chart with CSV export and print/PDF options.
- Live step tracker: Supports step tracking using compatible phone motion sensors.
- BMI display: Shows BMI in the application interface.
- Admin dashboard: Provides administrative views for users and database information.
Nutrition values depend on the available dataset and selected food classification. The system should not be treated as a medical diagnostic tool or as a precise measurement of portion size.

Prerequisites
Requirement	Purpose	Check
Node.js 18 or newer (project previously tested with v24)	Node.js backend on port 8000	node -v
Python 3.13	RAG and ML service on port 5000	python --version
Ollama	Runs the local language model used by the chat assistant	ollama --version
Ollama model llama3.2	Generates chat responses	ollama list
Python dependencies	RAG, API, and ML functionality	pip install -r backend/requirements.txt


Make sure you run commands from the project root unless the command says otherwise.
First-time installation
Open PowerShell in the project folder:
cd "D:\JNEC\Nutricare AI"
npm install
pip install -r backend\requirements.txt
ollama pull llama3.2
If ollama list already shows llama3.2, you do not need to download it again.
Start the Application
Option 1: Use the startup script
If start.bat is present in the project root, double-click it to start both services.
It should open two terminal windows:
1. Node backend — port 8000, started with npm start.
2. Python RAG service — port 5000, started with python rag_service.py.
Wait for the Python service to finish loading the Chroma knowledge base. The first startup may take longer than subsequent starts.
Then open:
http://127.0.0.1:8000
Option 2: Start each service manually
Open two PowerShell terminals.
Terminal 1 — Node backend
cd "D:\JNEC\Nutricare AI\backend"
npm start
Terminal 2 — Python RAG service
cd "D:\JNEC\Nutricare AI\backend"
python rag_service.py
Important: The Python service on port 5000 should run backend/rag_service.py. The project documentation identifies this as the service that exposes /rag-chat, /predict-food, /food-recommend, and /plan/15-day. Running a different Python file may cause chat, prediction, or food-chart features to fail.
Verify the Services
Open these URLs after both services start:
URL	Expected result
http://127.0.0.1:8000/api/health	JSON health response, expected status ok
http://127.0.0.1:8000/api/ml/health	ML service status and knowledge-base information
http://127.0.0.1:8000/Main/index.html	Dashboard page
http://127.0.0.1:5000/	Python service response, if configured


You can also check the services from PowerShell:
curl.exe http://127.0.0.1:8000/api/health
curl.exe http://127.0.0.1:5000/
The exact response fields may depend on the current implementation.
Using the Application
1. Start both backend services.
2. Open http://127.0.0.1:8000 in your browser.
3. Register or sign in through the Login page.
4. Open the dashboard and choose the feature you want to use.
Feature	Where to find it
Food image detection and nutrition information	Upload & Analyze → Food Image
Blood sugar or health-report upload and analysis	Upload & Analyze
RAG nutrition chatbot	NutriCare AI Assistant
Report-based food recommendations	My Food Plan → Foods I Can Eat
15-day food chart, CSV export, and print/PDF	My Food Plan → Create 15-Day Food Chart
Live step tracking	Live Step Tracker
BMI and logout	Top navigation bar / profile avatar
Administrative dashboard	/Admin/admin.html


On smaller screens, the sidebar may collapse behind the menu button, and wide tables may require horizontal scrolling.
Security note: Do not publish real user credentials or private user records in the README, source control, screenshots, or test fixtures. Use a local test account that is created through the registration flow, and do not share its password publicly.
API Endpoints
The following endpoints are described by the project's current documentation. Confirm their request schemas in the source code if you are integrating another client.
Method	Endpoint	Purpose
POST	/api/chat	RAG chat; may forward a user profile for personalization
POST	/api/recommend	Food recommendations
POST	/api/plan	Requests a 15-day food chart
POST	/api/analyze-food	Food image analysis and nutrition lookup
GET	/api/health	Node service health
GET	/api/ml/health	Python/ML service health
POST	/rag-chat on port 5000	Python RAG chat endpoint
POST	/predict-food on port 5000	Python food prediction endpoint
POST	/food-recommend on port 5000	Python recommendation endpoint
POST	/plan/15-day on port 5000	Python food-chart endpoint


Base URLs for local development:
- Node backend: http://127.0.0.1:8000
- Python service: http://127.0.0.1:5000
Project Structure
The following is a simplified overview. Some files or folders may differ as the project evolves.
Nutricare AI/
├── start.bat                    # Starts both services, if configured
├── README.md                    # Project documentation
├── NutriCare-AI-Run-Guide.pdf   # Printable setup guide
├── gif/
│   └── baymax.gif               # README animation
├── Main/                        # Dashboard (HTML/CSS/JavaScript)
├── Login/                       # Login and registration
├── Admin/                       # Admin dashboard
├── backend/
│   ├── server.js                # Node server and API proxy
│   ├── rag_service.py           # Python RAG, ML, and food-plan service
│   ├── services/
│   │   └── ml_api.py            # Food classifier integration
│   └── requirements.txt         # Python dependencies
├── RAG/
│   ├── chroma_db/               # Local vector database, if stored here
│   ├── data/                    # Nutrition and QA datasets
│   └── create_database.py       # Optional knowledge-base builder
└── test_images/                 # Sample images for testing
Generated databases, model weights, environment files, and user-specific data may be kept locally and excluded from Git using .gitignore.
Troubleshooting
Problem	Possible cause	What to try
Food chart or chat service returns an error	Python service is not running or the wrong file is running	Start python rag_service.py from the backend folder
EADDRINUSE on port 8000 or 5000	Another process is using the port	Stop the old service terminal before restarting
Chat responses are slow	Local language-model generation or cold start	Check that Ollama is running and llama3.2 is installed
Chat returns weak or missing context	Model or knowledge base did not load correctly	Check Python and Ollama terminal logs
Python exits during startup	Missing Python dependencies or incompatible environment	Run pip install -r backend\requirements.txt and review the error
First recommendation or chart request is slow	Model or Chroma database is loading	Wait for startup to finish and check the service logs
Browser shows 404 for pages or assets	Incorrect URL or service root	Start at http://127.0.0.1:8000 and check the requested path
Baymax GIF is missing on GitHub	Incorrect file path, filename, or file not committed	Confirm gif/baymax.gif exists and is pushed to GitHub


Stop the application
Close the terminal windows started by start.bat, or press Ctrl+C in each terminal.
Technology Stack
- Frontend: HTML, CSS, JavaScript
- Backend: Node.js, Express, Axios
- AI / RAG: FastAPI, LangChain, ChromaDB, all-MiniLM-L6-v2, Ollama with llama3.2
- Food classification: PyTorch Vision Transformer (ViT), 43 food classes
- Nutrition data: Structured CSV dataset
- Local development: Node.js and Python services
Disclaimer
NutriCare AI is a research and educational project. Food classification and dataset-based nutrition information can be incomplete or incorrect. Health-report analysis and food recommendations must not replace advice from a qualified healthcare professional. Seek professional guidance for medical conditions, dietary restrictions, or changes to treatment.