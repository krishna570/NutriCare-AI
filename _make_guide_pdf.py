# -*- coding: utf-8 -*-
"""Generate NutriCare-AI-Run-Guide.pdf - step-by-step guide to run the web app."""
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import datetime

ACCENT = (0, 145, 125)      # teal, matches app theme
DARK = (30, 45, 50)
GREY = (110, 110, 110)
WARN_BG = (255, 243, 224)
WARN_BD = (225, 145, 40)
NOTE_BG = (232, 248, 245)
CODE_BG = (242, 246, 246)
WHITE = (255, 255, 255)

OUT = r"D:\JNEC\Nutricare AI\NutriCare-AI-Run-Guide.pdf"


class Guide(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(8)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, "NutriCare AI - How to Run the Web Application",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.4)
        self.line(18, 15, self.w - 18, 15)
        self.set_y(20)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(210, 210, 210)
        self.set_line_width(0.2)
        self.line(18, self.get_y(), self.w - 18, self.get_y())
        self.set_y(-11)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5,
                  "Educational use only - not a substitute for medical advice    |    Page %d"
                  % self.page_no(),
                  align="C")


pdf = Guide(format="A4", unit="mm")
pdf.set_margins(18, 18, 18)
pdf.set_auto_page_break(True, margin=16)
pdf.add_page()


def h1(text):
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*ACCENT)
    pdf.multi_cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    y = pdf.get_y() + 0.5
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(18, y, pdf.w - 18, y)
    pdf.ln(3.5)


def h2(text):
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(0.8)


def body(text, size=10):
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 5.2, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1.2)


def bullet(label, text):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ACCENT)
    x = pdf.get_x()
    pdf.cell(6, 5.2, ">")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 5.2, label + " - " + text if label else text,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(x)
    pdf.ln(0.6)


def code(lines):
    pdf.ln(1)
    pdf.set_font("Courier", "", 9)
    pdf.set_text_color(20, 60, 55)
    pdf.set_fill_color(*CODE_BG)
    pdf.set_draw_color(200, 215, 212)
    pdf.multi_cell(0, 5, "\n".join(lines), fill=True, border=1,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)


def box(title, text, bg, bd):
    pdf.ln(1)
    pdf.set_fill_color(*bg)
    pdf.set_draw_color(*bd)
    pdf.set_line_width(0.5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*bd)
    pdf.multi_cell(0, 5.5, title, fill=True, border=1,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 5, text, fill=True, border=1,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2.5)


def table(headers, rows, widths, aligns=None):
    aligns = aligns or ["LEFT"] * len(headers)
    pdf.set_font("Helvetica", "B", 8.8)
    pdf.set_text_color(*WHITE)
    pdf.set_fill_color(*ACCENT)
    pdf.set_draw_color(205, 215, 213)
    pdf.set_line_width(0.2)
    line_h = 5
    # header
    x0, y0 = pdf.get_x(), pdf.get_y()
    hrow_h = line_h + 2
    x = x0
    for w, hd in zip(widths, headers):
        pdf.rect(x, y0, w, hrow_h, style="F")
        pdf.set_xy(x + 1.2, y0 + 1)
        pdf.multi_cell(w - 2.4, line_h, hd)
        x += w
    pdf.set_xy(x0, y0 + hrow_h)
    pdf.set_font("Helvetica", "", 8.6)
    pdf.set_text_color(*DARK)
    for i, row in enumerate(rows):
        # measure row height
        heights = []
        for w, cell in zip(widths, row):
            pdf.set_font("Helvetica", "", 8.6)
            lines = pdf.multi_cell(w - 2.4, line_h, cell, dry_run=True,
                                   output="LINES")
            heights.append(len(lines) * line_h + 2)
        rh = max(heights) + 1
        if pdf.get_y() + rh > pdf.h - 16:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 8.8)
            pdf.set_text_color(*WHITE)
            pdf.set_fill_color(*ACCENT)
            x0, y0 = pdf.get_x(), pdf.get_y()
            x = x0
            for w, hd in zip(widths, headers):
                pdf.rect(x, y0, w, hrow_h, style="F")
                pdf.set_xy(x + 1.2, y0 + 1)
                pdf.multi_cell(w - 2.4, line_h, hd)
                x += w
            pdf.set_xy(x0, y0 + hrow_h)
            pdf.set_font("Helvetica", "", 8.6)
            pdf.set_text_color(*DARK)
        x = pdf.get_x()
        y = pdf.get_y()
        if i % 2 == 1:
            pdf.set_fill_color(246, 250, 249)
            pdf.rect(x, y, sum(widths), rh, style="F")
        pdf.set_draw_color(215, 222, 220)
        cx = x
        for w, cell, al in zip(widths, row, aligns):
            pdf.set_xy(cx + 1.2, y + 1)
            pdf.multi_cell(w - 2.4, line_h, cell, align=al)
            cx += w
        # cell separators
        cx = x
        for w in widths[:-1]:
            cx += w
            pdf.line(cx, y, cx, y + rh)
        pdf.rect(x, y, sum(widths), rh)
        pdf.set_xy(x, y + rh)
    pdf.ln(3)


# ============================== TITLE ==============================
pdf.set_fill_color(*ACCENT)
pdf.rect(0, 0, pdf.w, 4, style="F")
pdf.ln(6)
pdf.set_font("Helvetica", "B", 26)
pdf.set_text_color(*DARK)
pdf.multi_cell(0, 11, "NutriCare AI", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
pdf.set_font("Helvetica", "", 13)
pdf.set_text_color(*ACCENT)
pdf.multi_cell(0, 7, "Smart Nutrition Assistant",
               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
pdf.ln(3)
pdf.set_font("Helvetica", "B", 15)
pdf.set_text_color(*DARK)
pdf.multi_cell(0, 8, "How to Run the Web Application",
               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
pdf.set_font("Helvetica", "", 11)
pdf.set_text_color(*GREY)
pdf.multi_cell(0, 6, "Step-by-step guide  -  " +
               datetime.date.today().strftime("%B %d, %Y"),
               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
pdf.ln(4)
body("The app runs TWO local services and then opens in your browser:")
code(["  Service 1  Node.js backend      port 8000  (serves the website + API)",
      "  Service 2  Python RAG / ML      port 5000  (AI chat, food detection,",
      "                                            recommendations, 15-day chart)",
      "",
      "  Browser    http://127.0.0.1:8000"])

# ============================== 1 ==============================
h1("1. Prerequisites")
table(
    ["Requirement", "Used for", "Check in a terminal"],
    [["Node.js 18+ (project runs on v24)",
      "Web server on port 8000", "node -v"],
     ["Python 3.13",
      "RAG / ML service on port 5000", "python --version"],
     ["Ollama with llama3.2",
      "AI answers in the chat bot", "ollama list"],
     ["Python packages",
      "RAG service dependencies",
      "pip install -r backend\\requirements.txt"]],
    [55, 62, 57])
box("NOTE", "Windows note: if 'node' or 'python' is not recognised, install "
    "them first from nodejs.org and python.org, then reopen the terminal.",
    NOTE_BG, ACCENT)

# ============================== 2 ==============================
h1("2. First-time setup (run once)")
body("Open a terminal in the project folder (D:\\JNEC\\Nutricare AI) and run:")
code(["cd /d \"D:\\JNEC\\Nutricare AI\"",
      "npm install",
      "pip install -r backend\\requirements.txt",
      "ollama pull llama3.2     ; only if 'ollama list' does not show it"])

# ============================== 3 ==============================
h1("3. Step 1 - Start the two services")
h2("Option A (easiest): use the start script")
body("Double-click start.bat in the project folder. It opens two windows:")
bullet("NutriCare - Node (8000)", "runs npm start")
bullet("NutriCare - Python RAG (5000)", "runs python rag_service.py")
body("Wait for the Python window to show 'Started server process' and finish "
     "loading the knowledge base (about 10-30 seconds on first start).")

h2("Option B: start manually in two terminals")
code([":: Terminal 1 - Node backend (port 8000)",
      "cd /d \"D:\\JNEC\\Nutricare AI\\backend\"",
      "npm start",
      "",
      ":: Terminal 2 - Python RAG service (port 5000)",
      "cd /d \"D:\\JNEC\\Nutricare AI\\backend\"",
      "python rag_service.py"])

box("WARNING - the most common mistake",
    "Port 5000 must run backend\\rag_service.py. Do NOT start "
    "services\\ml_api.py or app.py on port 5000 - they do not have the "
    "/rag-chat, /food-recommend or /plan/15-day routes. If the wrong file is "
    "running, the chat and the food chart fail with the message: "
    "'Food chart service returned an error.'  Fix: close that window and run "
    "'python rag_service.py' instead (or just use start.bat).",
    WARN_BG, WARN_BD)

# ============================== 4 ==============================
h1("4. Step 2 - Open the application")
body("Once both windows are running, open this URL in your browser:")
code(["http://127.0.0.1:8000"])
body("You land on the NutriCare AI dashboard. The navbar shows your name, your "
     "BMI (top bar) and the hamburger menu on phones.")

# ============================== 5 ==============================
h1("5. Step 3 - Verify everything works")
table(
    ["URL", "What you should see"],
    [["http://127.0.0.1:8000/api/health",
      "JSON with status ok (Node is up)"],
     ["http://127.0.0.1:8000/api/ml/health",
      "python_ml_service: online, doc_count 151210"],
     ["http://127.0.0.1:8000/Main/index.html",
      "Dashboard loads (HTTP 200)"],
     ["http://127.0.0.1:5000/",
      "NutriCare AI RAG Service, status online"]],
    [78, 96])
body("Quick check from the command line:")
code(["curl http://127.0.0.1:8000/api/health",
      "curl http://127.0.0.1:5000/"])

# ============================== 6 ==============================
h1("6. Step 4 - Log in")
box("TEST ACCOUNT",
    "Email: krishna@test.com      Password: 123456\n"
    "No OTP is required - registration uses the password form only "
    "(Login -> Register).", NOTE_BG, ACCENT)

# ============================== 7 ==============================
h1("7. Step 5 - Use the features")
bullet("Food image", "Upload & Analyze -> Food Image: 43-class AI detection "
       "with calories, protein, sugar, sodium, risk badges.")
bullet("Reports", "Upload a blood sugar or health report for AI analysis.")
bullet("Chat bot", "Ask anything in the NutriCare AI Assistant. Answers use "
       "the 151k-document knowledge base and your profile (about 5-60 s per "
       "answer - Ollama generation time is normal).")
bullet("Foods I Can Eat", "My Food Plan -> Foods I Can Eat: foods sorted into "
       "eat freely / moderate / limit for your BMI and conditions.")
bullet("15-day food chart", "My Food Plan -> Create 15-Day Food Chart: 15 days "
       "x 8 meals sized to your calorie target, with Download CSV and "
       "Print / PDF buttons.")
bullet("Step tracker", "Live Step Tracker uses your phone's motion sensor.")
bullet("Log out", "Click the avatar in the top bar.")
bullet("Admin", "Open http://127.0.0.1:8000/Admin/admin.html for user lists "
       "and database info.")
body("On a phone the sidebar collapses behind the Hamburger (three lines) "
     "button, and the 15-day chart scrolls sideways inside its own box.")

# ============================== 8 ==============================
h1("8. Key API endpoints")
table(
    ["Method", "Endpoint", "Purpose"],
    [["POST", "/api/chat", "RAG chat with user profile"],
     ["POST", "/api/recommend", "Foods you can eat (3 groups)"],
     ["POST", "/api/plan", "15-day food chart"],
     ["POST", "/api/analyze-food", "Food image to nutrition"],
     ["GET", "/api/health", "Node health"],
     ["GET", "/api/ml/health", "Python + Chroma health"],
     ["POST", ":5000/rag-chat", "RAG chat (internal)"],
     ["POST", ":5000/food-recommend", "Recommendations (internal)"],
     ["POST", ":5000/plan/15-day", "15-day chart (internal)"]],
    [24, 62, 88])

# ============================== 9 ==============================
h1("9. Troubleshooting")
table(
    ["Symptom", "Cause", "Fix"],
    [["'Food chart service returned an error.'",
      "Wrong Python file on port 5000",
      "Stop it and run python rag_service.py (use start.bat)"],
     ["Port already in use / EADDRINUSE",
      "An old instance is still running",
      "Close the old terminal windows, then start again"],
     ["Chat answers slowly (5-60 s)",
      "Ollama generation time (normal)",
      "Wait for the answer; keep llama3.2 installed"],
     ["Chat says no context / cannot answer",
      "Ollama is not running",
      "Start 'ollama serve' and check 'ollama list'"],
     ["Python window closes immediately",
      "Missing packages",
      "Run 'pip install -r backend\\requirements.txt'"],
     ["First chart click is slow",
      "Models + knowledge base loading (cold start)",
      "Only the first call; later calls take under 1 s"],
     ["Page loads but files 404",
      "Wrong address opened",
      "Always start at http://127.0.0.1:8000"]],
    [56, 48, 70])

# ============================== 10 ==============================
h1("10. Stop and restart")
bullet("Stop", "Close both terminal windows (or press Ctrl+C in each).")
bullet("Restart", "Run start.bat again.")
box("DISCLAIMER",
    "NutriCare AI is intended for research and educational purposes. Food "
    "recommendations come from a dataset classifier and are NOT a substitute "
    "for professional medical diagnosis or treatment.",
    WARN_BG, WARN_BD)

pdf.output(OUT)
print("WROTE", OUT)
