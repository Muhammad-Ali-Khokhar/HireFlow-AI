# 🤖 HireFlow AI

**HireFlow AI** is an intelligent, agentic recruitment automation platform built using **LangGraph**, **LangChain**, and **FastAPI**.
It streamlines the entire hiring process — from **CV parsing** to **candidate evaluation**, **HR communication**, and **interview scheduling** — powered by AI agents.

---

## 🚀 Features

* 🤠 **Automated Resume Parsing:** Extracts candidate data directly from uploaded CVs (PDF, DOCX, etc.).
* ⚙️ **Agentic Shortlisting:** Uses LLMs to intelligently rank and filter candidates based on job descriptions.
* 📩 **Smart HR Notifications:** Automatically drafts and sends personalized emails to HR with top candidates and suggested screening questions.
* 🖓️ **Calendar Integration:** Schedules interviews with selected candidates via Google Calendar.
* 🗣️ **Voice Analysis:** Processes HR–candidate call recordings using speech-to-text (STT) and evaluates responses.
* 📊 **End-to-End Workflow:** Fully autonomous pipeline — from candidate upload → evaluation → scheduling.

---

## 🏷️ Tech Stack

* **LangGraph** – for agent orchestration and flow control
* **LangChain** – for LLM integration and reasoning
* **FastAPI** – lightweight backend server
* **Google API (Gmail + Calendar)** – for communication and scheduling
* **Speech-to-Text (STT)** – for call transcription and analysis

---

## ⚙️ Setup and Installation

Follow these steps to run **HireFlow AI** locally:

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/<your-username>/HireFlow-AI.git
cd HireFlow-AI
```

### 2️⃣ Create and Activate Virtual Environment

**For Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**For macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Set Up Google Authentication

To use Gmail and Google Calendar APIs, you need to authenticate:

1. Place your `credentials.json` file (from Google Cloud Console) in the project root.
2. Run the authentication script:

   ```bash
   python auth_gmail.py
   ```
3. This will open a browser window for Google sign-in.
4. Once authenticated, a `token.json` file will be created automatically — used for future API access.

---

### 5️⃣ Run the Application

Navigate to the `app` folder and start the FastAPI server:

```bash
cd app
uvicorn app.main:app --reload --port 8000
```

The app will be live at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

You can access API docs at:
👉 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---