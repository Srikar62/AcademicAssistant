# 🚀 Startup Guide — AI Academic Learning Assistant

A step-by-step guide to get every component running from scratch on Windows.

---

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) |
| **WSL (Ubuntu)** | Latest | See Step 0 below |
| **Docker** | Latest | Installed inside WSL (see Step 0) |
| **Git** | Any | [git-scm.com](https://git-scm.com/) |

---

## Step 0: One-Time Setup — WSL + Docker

> **Skip this step if you already have Docker working.**

### 0a. Install WSL with Ubuntu

Open **PowerShell as Administrator** and run:

```powershell
wsl --install -d Ubuntu
```

**Restart your PC** after installation completes.

### 0b. Set up Ubuntu

After restart, the Ubuntu terminal will open automatically. Create a username and password when prompted.

### 0c. Install Docker inside WSL

Open the **Ubuntu** terminal and run:

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install docker.io docker-compose-v2 -y

# Allow running Docker without sudo
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
exit
```

Close and reopen the Ubuntu terminal, then verify:

```bash
docker --version
docker compose version
```

Both commands should print version numbers without errors.

### 0d. Start Docker service

```bash
sudo service docker start
```

> **Note:** You need to run `sudo service docker start` every time you open a new Ubuntu terminal session (WSL doesn't auto-start services).

---

## Step 1: Start Infrastructure (Kafka, Qdrant, MinIO)

Open the **Ubuntu terminal** and run:

```bash
# Start Docker if not already running
sudo service docker start

# Navigate to project directory
cd /mnt/e/AcademicAssistant

# Start all infrastructure containers
docker compose up -d
```

### Verify all 4 containers are running:

```bash
docker compose ps
```

You should see:

| Container | Status | Ports |
|-----------|--------|-------|
| academic-zookeeper | Running | 2181 |
| academic-kafka | Running | 9092 |
| academic-minio | Running | 9000, 9001 |
| academic-qdrant | Running | 6333, 6334 |

### Verify via browser:

| Service | URL | What you'll see |
|---------|-----|-----------------|
| MinIO Console | http://localhost:9001 | Login page (user: `minioadmin`, pass: `minioadmin`) |
| Qdrant Dashboard | http://localhost:6334/dashboard | Qdrant web UI |

> **Troubleshooting:** If containers fail, run `docker compose down` then `docker compose up -d` again.

---

## Step 2: Configure Environment Variables

Open a **Windows PowerShell** terminal:

```powershell
cd e:\AcademicAssistant

# Copy the template (first time only)
copy .env.example .env
```

Edit the `.env` file and set your LLM API key:

```ini
LLM_API_KEY=your-actual-api-key-here
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-70b-versatile
LLM_BASE_URL=https://api.groq.com/openai/v1
```

> **Get a free API key** from [Groq Console](https://console.groq.com).
> Alternatively, use OpenAI, Together AI, or any OpenAI-compatible provider.

---

## Step 3: Start the Backend (FastAPI)

Open a **new Windows PowerShell** terminal:

```powershell
cd e:\AcademicAssistant

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the API server
uvicorn backend.app.main:app --reload --port 8000
```

### Verify backend is running:

| URL | Expected |
|-----|----------|
| http://localhost:8000 | `{"service": "AI Academic Learning Assistant", "status": "running"}` |
| http://localhost:8000/docs | Swagger UI (interactive API documentation) |
| http://localhost:8000/health | `{"status": "ok"}` |

> **Keep this terminal open.** The backend must stay running.

---

## Step 4: Start the Spark Processing Pipeline

Open a **new Windows PowerShell** terminal:

```powershell
cd e:\AcademicAssistant

# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Start the standalone processor (no Spark cluster needed)
python -m spark.processing_job standalone
```

You should see:

```
Starting standalone consumer (no Spark) …
Listening on 'documents.uploaded' …
```

> **Keep this terminal open.** This processes uploaded documents into embeddings.
>
> **Without this running**, file uploads will succeed but documents will stay in "uploaded" status and won't be searchable.

---

## Step 5: Start the Frontend (React)

Open a **new Windows PowerShell** terminal:

```powershell
cd e:\AcademicAssistant\frontend

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev

```

You should see:

```
  VITE v5.x.x  ready in XXXms

  ➜  Local:   http://localhost:5173/
```

### Open the app:

👉 **http://localhost:5173** in your browser.

---

## All Running — Summary

You should have **4 terminals** open:

```
┌──────────────────────────────────────────────────────────┐
│  Terminal 1: Ubuntu (WSL)                                │
│  $ sudo service docker start                             │
│  $ cd /mnt/e/AcademicAssistant && docker compose up -d   │
│  (runs in background — you can close this terminal)      │
├──────────────────────────────────────────────────────────┤
│  Terminal 2: PowerShell — FastAPI Backend                 │
│  > .\venv\Scripts\Activate.ps1                           │
│  > uvicorn backend.app.main:app --reload --port 8000     │
│  ✅ Running at: http://localhost:8000                     │
├──────────────────────────────────────────────────────────┤
│  Terminal 3: PowerShell — Spark Pipeline                 │
│  > .\venv\Scripts\Activate.ps1                           │
│  > python -m spark.processing_job standalone              │
│  ✅ Listening for Kafka messages...                       │
├──────────────────────────────────────────────────────────┤
│  Terminal 4: PowerShell — React Frontend                 │
│  > cd frontend && npm run dev                            │
│  ✅ Running at: http://localhost:5173                     │
└──────────────────────────────────────────────────────────┘
```

---

## Using the Application

### 1. Upload a Document
- Go to http://localhost:5173
- Click **Upload** in the sidebar
- Drag-and-drop a PDF, PPTX, TXT, or MD file

### 2. Wait for Processing
- Click **Documents** in the sidebar
- Your document status will change: `uploaded → processing → processed`
- This takes a few seconds (depends on file size)

### 3. Use AI Study Tools
Once the document shows **"processed"**, click on it and choose:

| Tool | What it does |
|------|-------------|
| 💬 **Ask Questions** | Chat with your document — get answers with page-level citations |
| 🧠 **Generate Quiz** | Auto-create MCQ quizzes to test your knowledge |
| 📋 **Summarize** | Get a concise summary with key highlights |
| 🗺️ **Mind Map** | Visualize concepts as an interactive mind map |

---

## Running Tests

```powershell
cd e:\AcademicAssistant
.\venv\Scripts\Activate.ps1

# Run all 99 tests
python -m pytest -v

# Run only backend tests
python -m pytest backend/tests/ -v

# Run only Spark pipeline tests
python -m pytest spark/tests/ -v

# Run integration tests with benchmark output
python -m pytest tests/test_integration.py -v -s
```

---

## Stopping Everything

```powershell
# Stop the frontend:  Ctrl+C in Terminal 4
# Stop the Spark pipeline:  Ctrl+C in Terminal 3
# Stop the backend:  Ctrl+C in Terminal 2
```

Then in the **Ubuntu terminal**:

```bash
cd /mnt/e/AcademicAssistant

# Stop containers (keep data)
docker compose down

# Stop containers AND delete all stored data
docker compose down -v
```

---

## Quick Reference — Ports

| Port | Service | URL |
|------|---------|-----|
| 2181 | Zookeeper | — |
| 5173 | React Frontend | http://localhost:5173 |
| 6333 | Qdrant API | http://localhost:6333 |
| 6334 | Qdrant Dashboard | http://localhost:6334/dashboard |
| 8000 | FastAPI Backend | http://localhost:8000 |
| 9000 | MinIO API | — |
| 9001 | MinIO Console | http://localhost:9001 |
| 9092 | Kafka Broker | — |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `docker: command not found` | Run inside WSL Ubuntu, not PowerShell. Run `sudo service docker start` first. |
| `Cannot connect to the Docker daemon` | Run `sudo service docker start` in Ubuntu terminal |
| `port 8000 already in use` | Kill the process: `netstat -ano \| findstr 8000` then `taskkill /PID <pid> /F` |
| `port 5173 already in use` | Vite auto-picks next port — check terminal output |
| Docker containers won't start | `docker compose down` then `docker compose up -d` |
| MinIO connection refused | Make sure Docker containers are running: `docker compose ps` |
| `LLM_API_KEY` errors | Set your real API key in `.env` — Q&A/Quiz/Summary/MindMap need it |
| Upload works but doc stays "uploaded" | Start the Spark pipeline (Step 4) |
| `ModuleNotFoundError` | Activate venv: `.\venv\Scripts\Activate.ps1` |
| Frontend shows "Network Error" | Make sure the backend is running on port 8000 |
| WSL Ubuntu terminal closes immediately | Open from Start Menu → search "Ubuntu" |
