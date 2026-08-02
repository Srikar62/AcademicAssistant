# 🎓 AI Academic Learning Assistant

An AI-powered study tool that transforms your academic documents into interactive learning experiences. Upload lecture slides, PDFs, or notes and instantly get **AI Q&A**, **quizzes**, **summaries**, and **mind maps** — powered by a distributed processing pipeline.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📤 **Smart Upload** | Drag-and-drop upload for PDF, PPTX, TXT, and Markdown files |
| 💬 **AI Q&A** | Ask questions about your documents with page/slide-level citations |
| 🧠 **Quiz Generation** | Auto-generated multiple-choice quizzes with explanations |
| 📋 **Summarization** | Map-reduce summaries with configurable length and key points |
| 🗺️ **Mind Maps** | Hierarchical concept visualization rendered with Mermaid.js |
| ⚡ **Distributed Processing** | Spark Structured Streaming for scalable document ingestion |

---

## 🏗️ Architecture

```
┌──────────┐     ┌───────┐     ┌──────────────┐     ┌────────┐
│ React UI │────▶│FastAPI│────▶│    Kafka      │────▶│ Spark  │
│ (Vite)   │◀────│Backend│     │ (msg broker)  │     │Pipeline│
└──────────┘     └───┬───┘     └──────────────┘     └───┬────┘
                     │                                    │
                     │         ┌──────────┐               │
                     └────────▶│  MinIO   │◀──────────────┘
                     │         │(S3 store)│
                     │         └──────────┘
                     │
                     │         ┌──────────┐
                     └────────▶│  Qdrant  │◀──────────────┘
                               │(vectors) │
                               └──────────┘
```

### Data Flow

1. **Upload** — User uploads a document via the React frontend
2. **Store** — FastAPI stores the file in MinIO (S3-compatible) and publishes a message to Kafka
3. **Process** — Spark Structured Streaming consumes the message, downloads the file, and:
   - **Parses** it (PDF via PyMuPDF, PPTX via python-pptx, TXT/MD directly)
   - **Chunks** the text (sentence-aware, ~400 tokens, 15% overlap)
   - **Embeds** chunks using `all-MiniLM-L6-v2` (384-dim vectors)
   - **Stores** embedded chunks in Qdrant with full metadata
4. **Retrieve** — When a user asks a question, the backend:
   - Embeds the query with the same model
   - Searches Qdrant for similar chunks (filtered by doc/course/student)
   - Sends the context to an LLM for a grounded answer with citations
5. **Generate** — Quiz, summary, and mind map endpoints follow the same RAG pattern

---

## 📁 Project Structure

```
AcademicAssistant/
├── backend/                    # FastAPI API server
│   ├── app/
│   │   ├── main.py             # App entry, lifespan hooks, route registration
│   │   ├── config.py           # Pydantic settings (env-based)
│   │   ├── routers/
│   │   │   ├── upload.py       # POST /upload
│   │   │   ├── documents.py    # GET /documents, /documents/{id}
│   │   │   ├── ask.py          # POST /ask (RAG Q&A)
│   │   │   ├── quiz.py         # POST /quiz
│   │   │   ├── summarize.py    # POST /summarize
│   │   │   └── mindmap.py      # POST /mindmap
│   │   ├── services/
│   │   │   ├── minio_service.py
│   │   │   ├── kafka_service.py
│   │   │   ├── qdrant_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── llm_client.py
│   │   │   └── document_service.py
│   │   ├── models/             # Pydantic schemas
│   │   └── utils/              # Prompts, validators, Mermaid converter
│   └── tests/
│       ├── test_upload.py      # 14 tests
│       ├── test_ask.py         # 13 tests
│       └── test_generation.py  # 30 tests
├── spark/                      # Spark processing pipeline
│   ├── config.py               # Standalone Spark config
│   ├── processing_job.py       # Main job (Spark Streaming + standalone mode)
│   ├── parsers/                # PDF, PPTX, Text parsers
│   ├── chunker.py              # Sentence-aware chunking
│   ├── embedder.py             # sentence-transformers wrapper
│   ├── qdrant_writer.py        # Batched Qdrant upsert
│   └── tests/
│       └── test_pipeline.py    # 26 tests
├── frontend/                   # React SPA (Vite)
│   ├── src/
│   │   ├── App.jsx             # Root component + navigation
│   │   ├── components/         # Upload, Library, Chat, Quiz, Summary, MindMap
│   │   ├── services/api.js     # Backend API client
│   │   └── index.css           # Design system
│   └── package.json
├── tests/
│   └── test_integration.py     # 16 E2E + failure + benchmark tests
├── docker-compose.yml          # Kafka, Qdrant, MinIO
└── .env.example                # Environment template
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Docker & Docker Compose**

### 1. Clone and configure

```bash
git clone <repository-url>
cd AcademicAssistant

# Copy environment template and edit as needed
cp .env.example .env
```

### 2. Start infrastructure

```bash
docker-compose up -d
```

This starts:
- **Kafka** (port 9092) + Zookeeper (port 2181)
- **Qdrant** (port 6333, dashboard at 6334)
- **MinIO** (port 9000, console at 9001, user: `minioadmin`)

### 3. Set up the backend

```bash
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install fastapi uvicorn python-multipart pydantic-settings
pip install minio kafka-python
pip install PyMuPDF python-pptx nltk qdrant-client numpy pandas
pip install sentence-transformers
pip install httpx

# Run the API server
uvicorn backend.app.main:app --reload --port 8000
```

### 4. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and proxies API calls to the backend.

### 5. (Optional) Start the Spark processing job

```bash
# Standalone mode (no Spark cluster needed)
python -m spark.processing_job standalone

# With a Spark cluster
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 \
    spark/processing_job.py spark
```

---

## 🔧 Configuration

All settings are read from environment variables (`.env` file). Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant gRPC port |
| `QDRANT_COLLECTION` | `academic_chunks` | Vector collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `EMBEDDING_DIMENSION` | `384` | Vector dimension |
| `LLM_API_KEY` | — | API key for the LLM provider |
| `LLM_PROVIDER` | `groq` | LLM provider name |
| `LLM_MODEL` | `llama-3.1-70b-versatile` | Model identifier |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible API URL |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `ALLOWED_EXTENSIONS` | `.pdf,.pptx,.txt,.md` | Accepted file types |

---

## 📡 API Reference

The API is auto-documented via FastAPI's built-in Swagger UI:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Readiness probe |
| `POST` | `/upload` | Upload a document (multipart) |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Get document status |
| `POST` | `/ask` | RAG-powered Q&A with citations |
| `POST` | `/quiz` | Generate a multiple-choice quiz |
| `POST` | `/summarize` | Map-reduce summarization |
| `POST` | `/mindmap` | Generate a mind map (Mermaid syntax) |

### Example: Ask a Question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is supervised learning?",
    "doc_id": "abc-123",
    "top_k": 5
  }'
```

Response:
```json
{
  "answer": "Supervised learning uses labeled data to train models [Source: Page 3]...",
  "citations": [
    {
      "source_label": "Page 3",
      "doc_id": "abc-123",
      "original_filename": "lecture.pdf",
      "page_number": 3,
      "relevance_score": 0.92
    }
  ],
  "chunks_used": 5
}
```

---

## 🧪 Testing

```bash
# Run all tests (99 total — auto-discovers from pyproject.toml testpaths)
python -m pytest -v

# Run only unit tests
python -m pytest backend/tests/ spark/tests/ -v

# Run integration & benchmarks (with benchmark output)
python -m pytest tests/test_integration.py -v -s

# Run a specific test class
python -m pytest tests/test_integration.py::TestEndToEndPipeline -v
```

### Test Coverage

| Suite | Tests | Scope |
|-------|-------|-------|
| `backend/tests/test_upload.py` | 14 | Upload, documents, health endpoints |
| `backend/tests/test_ask.py` | 13 | RAG Q&A, citations, error handling |
| `backend/tests/test_generation.py` | 30 | Quiz, summary, mindmap, Mermaid converter |
| `spark/tests/test_pipeline.py` | 26 | Parsers, chunker, embedder, Qdrant writer |
| `tests/test_integration.py` | 16 | E2E flows, failure handling, benchmarks |
| **Total** | **99** | |

---

## 📊 Performance Benchmarks

Measured on local dev (mocked external services, real pipeline code):

| Component | Metric | Value |
|-----------|--------|-------|
| PDF Parse (3 pages) | avg latency | ~1.8ms |
| PPTX Parse (3 slides) | avg latency | ~7.5ms |
| Chunking (50 sections) | total time | ~25ms |
| Qdrant Upsert (200 chunks) | throughput | ~35k chunks/sec |
| Full Pipeline (per doc) | end-to-end | ~4.3ms |
| `/ask` endpoint | p50 latency | ~3.0ms |

> Note: With real services, add network RTT + model inference time (~100ms for embedding, ~1-3s for LLM).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, Vite, Mermaid.js |
| **Backend** | FastAPI, Pydantic, Uvicorn |
| **Processing** | PySpark Structured Streaming |
| **Message Queue** | Apache Kafka |
| **Object Storage** | MinIO (S3-compatible) |
| **Vector Database** | Qdrant |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`) |
| **LLM** | Groq / OpenAI API (configurable) |
| **Parsers** | PyMuPDF (PDF), python-pptx (PPTX), NLTK |

