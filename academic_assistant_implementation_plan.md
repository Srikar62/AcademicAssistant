# AI Academic Learning Assistant — Implementation Plan (Spark + Kafka + GenAI)

## 1. Design Goals

This plan restores the two things the original 15-idea list was built around — **Apache Spark** and **Apache Kafka** — while keeping the GenAI outputs (quizzes, summaries, mind maps, Q&A) from your later request. It's built as a real backend system, not a browser-only prototype, because the whole point is to demonstrate distributed ingestion and processing at scale.

**What each piece is actually for, so nothing gets added just to check a box:**
- **Kafka** — decouples upload from processing. Handles bursty traffic (a class uploading lecture notes the night before an exam) without blocking the API, and gives replay/retry if a processing job fails partway through a document.
- **Spark** — does the CPU-heavy, embarrassingly-parallel work: parsing, chunking, and embedding potentially thousands of chunks across many documents. This is the "why not just do it in a for-loop" justification.
- **GenAI** — the actual student-facing value: RAG-grounded Q&A, quiz generation, summarization, mind maps.

---

## 2. Architecture

```
Student Upload (PDF/PPTX/Notes)
        │
        ▼
  Upload API (FastAPI) ──► Object Storage (S3/MinIO)
        │
        ▼
  Kafka topic: documents.uploaded
        │
        ▼
  Spark Structured Streaming job
    ├─ Parse (PyMuPDF / python-pptx)
    ├─ Chunk (sentence-aware, ~400 tokens, 15% overlap)
    └─ Embed (sentence-transformers, distributed across executors)
        │
        ▼
  Vector DB (Qdrant) ◄── batched writes from Spark
        │
        ▼
  Kafka topic: documents.processed (notifies API layer)
        │
        ▼
  LLM Orchestration Layer (FastAPI service)
    ├─ /ask       → RAG retrieval + grounded answer
    ├─ /quiz      → retrieve + structured-JSON quiz generation
    ├─ /summarize → map-reduce summarization
    └─ /mindmap   → hierarchical concept extraction → Mermaid syntax
        │
        ▼
  React Frontend
```

Kafka also carries a `documents.failed` dead-letter topic — anything that throws during parsing (corrupted PDF, unsupported encoding) lands there instead of silently dropping, so failures are inspectable rather than invisible.

---

## 3. Component Breakdown

### 3.1 Upload & Ingestion
- FastAPI endpoint accepts the file, writes it to object storage, and publishes a Kafka message to `documents.uploaded` containing `{doc_id, student_id, course_id, storage_path, file_type, timestamp}`.
- The API's job ends there — it does not wait for processing. The frontend polls `/documents/{id}/status` or subscribes via WebSocket for the `processed` event.
- This is the piece that was missing from the browser-only version: uploads and processing are decoupled, so a large PPTX doesn't block the UI thread or the whole request.

### 3.2 Spark Processing Job
Runs as a Structured Streaming job consuming `documents.uploaded`, foreachBatch-style so each micro-batch can fan out parsing across the cluster:

- **Parsing UDF**: dispatches by file extension (PyMuPDF for PDF, `python-pptx` for slides, plain read for notes). Wrapped so a single corrupted file doesn't kill the batch — errors get caught, logged, and routed to `documents.failed`.
- **Chunking**: sentence-boundary-aware splitting (spaCy or NLTK sentence tokenizer), merged up to ~400 tokens with 15% overlap. PPTX gets chunked per-slide first, then merged if slides are short — this avoids the raw-XML fragmentation problem I flagged in the client-side plan, since `python-pptx` handles run-merging properly instead of manually parsing `<a:t>` elements.
- **Embedding**: `sentence-transformers` (`all-MiniLM-L6-v2` to start — swap for a stronger model later if retrieval quality needs it), batched per partition using `mapInPandas` so executors reuse a loaded model instead of reloading it per row.
- **Write**: batched upsert to Qdrant, then a completion message to `documents.processed`.

This is the direct answer to "why Spark": embedding 50 students' documents at once is trivially parallel across partitions, versus a sequential loop that gets slower with every additional document.

### 3.3 Vector Database — Qdrant
Chosen over IndexedDB (from the browser plan) specifically because:
- Supports metadata filtering (`course_id`, `student_id`) natively, so retrieval can be scoped to "this student's uploads for this course" instead of a global scan.
- Has a real ANN index, so retrieval stays fast as chunk counts grow into the tens of thousands — the linear cosine-scan problem from the client-side version doesn't reappear.
- Runs as its own service, so data persists server-side and survives across devices/browsers, which was flagged as an open question in the earlier plan — here it's just answered by the architecture.

### 3.4 LLM Orchestration Layer
Kept as a distinct FastAPI service so retrieval and generation logic aren't tangled with the ingestion pipeline.

| Endpoint | Behavior |
|---|---|
| `/ask` | embed query → top-k retrieval (metadata-filtered) → prompt with context → grounded answer with page/slide citations |
| `/summarize` | map-reduce: summarize each chunk group, then summarize the summaries — avoids the "assume it all fits in one prompt" gap from the earlier plan |
| `/quiz` | retrieve relevant chunks → structured JSON-mode generation (question, options, correct answer, explanation) → schema-validated before returning |
| `/mindmap` | LLM extracts a hierarchical node/edge structure as JSON, converted to Mermaid `mindmap` syntax server-side (not left to the LLM to freeform, which is what caused the "post-process to ensure valid syntax" hack in the client-side plan) |

LLM calls go through a real API key held server-side (env var / secrets manager) — not stored in the browser. This closes the security gap in the earlier plan where the Groq key sat in `localStorage`.

### 3.5 Frontend
React app, same functional surface as before (upload, document library, quiz/summary/mindmap views, Q&A chat) but talking to a real backend instead of doing everything client-side. Mermaid.js still renders mind maps — that choice was fine, it's the generation path behind it that changes.

---

## 4. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Ingestion queue | Kafka | Decouples upload from processing, replay on failure |
| Processing | PySpark Structured Streaming | Distributed parsing/chunking/embedding |
| Parsing | PyMuPDF, python-pptx | Robust extraction, avoids raw-XML fragility |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Matches your existing recommender-system stack; fast, good enough baseline |
| Vector DB | Qdrant | Metadata filtering, ANN index, persistent, self-hosted |
| LLM | Server-side API call (provider of choice) | Key never exposed client-side |
| Backend API | FastAPI | Async, simple to wire to Kafka producer/consumer |
| Frontend | React | Existing component plan carries over |
| Mind maps | Mermaid.js | Rendering only — generation is now schema-validated server-side |

---

## 5. Data Flow (Concrete Example)

1. Student uploads `lecture_12.pdf` → API stores it, publishes to `documents.uploaded`.
2. Spark consumes the message, extracts ~12 pages of text, produces ~40 chunks, embeds them in a batched partition job, writes to Qdrant, publishes to `documents.processed`.
3. Frontend receives the processed event, unlocks quiz/summary/Q&A actions for that document.
4. Student asks a question → `/ask` embeds the query, retrieves top-5 chunks filtered to that `doc_id`, LLM answers with page citations pulled from chunk metadata.

---

## 6. Milestones

| Phase | Tasks | Focus |
|---|---|---|
| 1. Ingestion | FastAPI upload endpoint, object storage, Kafka producer, topic setup | Get files flowing into Kafka reliably |
| 2. Spark pipeline | Parsing UDFs, chunker, embedding job, Qdrant writer, dead-letter handling | The core "why Spark" demonstration |
| 3. Retrieval | `/ask` endpoint, citation tracing, metadata filtering | Validate RAG quality before building generation on top |
| 4. Generation | `/quiz`, `/summarize`, `/mindmap` with structured-output prompting | GenAI layer |
| 5. Frontend | Upload UI, document library, generation panel, output views | Same shape as before, wired to real backend |
| 6. Load testing | Concurrent uploads, Spark batch timing vs. sequential baseline | This is your evidence for the "at scale" claim |

---

## 7. Evaluation / Demo Evidence

To make the Spark/Kafka choice legible rather than decorative, capture:
- **Throughput comparison**: time to process 50 documents via the Spark pipeline vs. a naive sequential Python loop — this is the single most convincing number for "why distributed processing."
- **Retrieval quality**: precision@k on a small hand-labeled set of questions per document.
- **End-to-end latency**: upload → "ready" time, and per-query `/ask` latency.
- **Failure handling**: demonstrate a corrupted upload landing in `documents.failed` instead of silently disappearing.

---

## 8. What Changed From the Browser-Only Version, and Why

| Issue in earlier plan | Fix here |
|---|---|
| No Spark/Kafka at all | Both reinstated as the ingestion/processing backbone |
| IndexedDB linear scan doesn't scale | Qdrant with ANN indexing and metadata filtering |
| No cross-device persistence | Server-side vector DB and object storage |
| API key in browser `localStorage` | Server-side key, never exposed to the client |
| Raw XML PPTX parsing is fragile | `python-pptx` handles run-merging correctly |
| No strategy for long documents | Map-reduce summarization, chunk-scoped retrieval |
| Mermaid syntax "post-processed to be valid" | Structured JSON extraction, converted to Mermaid server-side, not left to LLM freeform output |
