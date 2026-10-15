@echo off
REM ============================================================
REM NutriCare AI - start both services
REM   Window 1: Node backend  -> http://127.0.0.1:8000
REM   Window 2: Python RAG    -> http://127.0.0.1:5000
REM Do NOT run services\ml_api.py on port 5000 - that one has
REM no /rag-chat, /food-recommend or /plan/15-day routes.
REM ============================================================

start "NutriCare - Node (8000)" cmd /k "cd /d "%~dp0backend" && npm start"
start "NutriCare - Python RAG (5000)" cmd /k "cd /d "%~dp0backend" && python rag_service.py"

echo Both services are starting...
echo When ready, open http://127.0.0.1:8000 in your browser.
timeout /t 5 >nul
