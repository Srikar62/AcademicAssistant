# 🎓 AI Academic Learning Assistant — Complete Interview Preparation Handbook

> **Project in one sentence:** A distributed RAG (Retrieval-Augmented Generation) pipeline that ingests academic documents via Kafka → Spark → Qdrant and exposes AI-powered Q&A, quiz generation, summarization, and mind-map features through a FastAPI backend and React frontend.

---

# Table of Contents

1. [Project Overview & Architecture](#1-project-overview--architecture)
2. [RAG (Retrieval-Augmented Generation)](#2-rag-retrieval-augmented-generation)
3. [Apache Kafka — Message Queue](#3-apache-kafka--message-queue)
4. [Apache Spark — Distributed Processing](#4-apache-spark--distributed-processing)
5. [Document Parsing Pipeline](#5-document-parsing-pipeline)
6. [Text Chunking Strategy](#6-text-chunking-strategy)
7. [Embeddings & Sentence-Transformers](#7-embeddings--sentence-transformers)
8. [Vector Database — Qdrant](#8-vector-database--qdrant)
9. [LLM Orchestration Layer](#9-llm-orchestration-layer)
10. [Map-Reduce Summarization](#10-map-reduce-summarization)
11. [MinIO — Object Storage](#11-minio--object-storage)
12. [FastAPI Backend](#12-fastapi-backend)
13. [React Frontend](#13-react-frontend)
14. [Docker & Infrastructure](#14-docker--infrastructure)
15. [Testing Strategy](#15-testing-strategy)
16. [System Design & Scalability](#16-system-design--scalability)
17. [Design Decisions & Trade-offs](#17-design-decisions--trade-offs)
18. [50 Rapid-Fire Interview Questions](#18-50-rapid-fire-interview-questions)

---

# 1. Project Overview & Architecture

## 1.1 What is this project?

An **AI-powered academic study tool** that lets students upload lecture slides (PDF, PPTX), notes (TXT, MD), and then interact with their documents via:

| Feature | What it does |
|---------|-------------|
| 💬 **AI Q&A** | Ask questions → get grounded answers with page/slide citations |
| 🧠 **Quiz** | Auto-generate MCQ quizzes from uploaded content |
| 📋 **Summary** | Map-reduce summarization with key-point extraction |
| 🗺️ **Mind Map** | Hierarchical concept visualization via Mermaid.js |

## 1.2 High-Level Architecture

```
┌──────────────┐        ┌──────────┐        ┌─────────────┐        ┌────────────┐
│  React UI    │───────▶│ FastAPI  │───────▶│   Kafka     │───────▶│   Spark    │
│  (Vite)      │◀───────│ Backend  │        │ (msg queue) │        │  Pipeline  │
└──────────────┘        └────┬─────┘        └─────────────┘        └─────┬──────┘
                             │                                            │
                        ┌────▼─────┐                                ┌────▼─────┐
                        │  MinIO   │                                │  Qdrant  │
                        │(S3 store)│◀───────────────────────────────│(vectors) │
                        └──────────┘                                └──────────┘
```

## 1.3 Data Flow (Step-by-Step)

```
1. Student uploads lecture.pdf via React UI
       │
       ▼
2. FastAPI stores file in MinIO (S3-compatible object storage)
       │
       ▼
3. FastAPI publishes message to Kafka topic: documents.uploaded
   Payload: { doc_id, student_id, course_id, storage_path, file_type }
       │
       ▼
4. Spark Structured Streaming consumes the message
       │
       ├─── a) Download file bytes from MinIO
       ├─── b) Parse (PyMuPDF for PDF, python-pptx for PPTX)
       ├─── c) Chunk (sentence-aware, ~400 tokens, 15% overlap)
       ├─── d) Embed (all-MiniLM-L6-v2, 384-dim vectors)
       └─── e) Upsert to Qdrant (batched writes)
       │
       ▼
5. Spark publishes to Kafka topic: documents.processed
       │
       ▼
6. Student asks a question → /ask endpoint
       │
       ├─── a) Embed the query with the same model
       ├─── b) Search Qdrant (cosine similarity + metadata filters)
       ├─── c) Build prompt with retrieved context + citations
       └─── d) LLM generates grounded answer
       │
       ▼
7. Response returned with answer + page-level citations
```

⭐ **Interview Tip:** Always describe the data flow end-to-end when asked "Walk me through your project." Interviewers love it when you trace a request from the user click all the way to the LLM response.

⚠ **Common Mistake:** Don't just say "I used Kafka and Spark." Explain *why* — Kafka decouples upload from processing; Spark parallelizes the CPU-heavy embedding work.

## 1.4 Tech Stack Table

| Layer | Technology | Why This Choice |
|-------|-----------|-----------------|
| Frontend | React 18 + Vite | Fast HMR, component-based UI |
| Backend API | FastAPI + Pydantic | Async, auto-docs, type-safe |
| Message Queue | Apache Kafka | Decoupling, replay, dead-letter |
| Processing | PySpark Structured Streaming | Distributed parse/chunk/embed |
| Object Storage | MinIO (S3-compatible) | Persistent file store, presigned URLs |
| Vector Database | Qdrant | ANN index, metadata filtering |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Fast, 384-dim, good quality |
| LLM | Groq API (Llama 3.1 70B) | Free tier, fast inference |
| Parsers | PyMuPDF, python-pptx | Robust extraction |
| Containerization | Docker Compose | One-command infra setup |

---

### Summary
- This is a full-stack distributed RAG system for academic document intelligence.
- The architecture decouples upload, processing, storage, and retrieval into independent services.
- Every technology choice has a clear justification (not just "checking a box").

### Top 5 Interview Questions
1. *Walk me through the architecture of your project.*
2. *Why did you choose a distributed architecture instead of a monolithic one?*
3. *What happens when a student uploads a document?*
4. *How does data flow from upload to the student getting an answer?*
5. *What would happen if the Spark pipeline is down when someone uploads?*

### Quick Revision Bullets
- Upload → MinIO + Kafka → Spark (parse, chunk, embed) → Qdrant → RAG pipeline
- 3 Kafka topics: `documents.uploaded`, `documents.processed`, `documents.failed`
- 4 AI features: Q&A, Quiz, Summarize, Mind Map — all RAG-powered
- 99 tests total across unit, integration, and benchmarks

---

# 2. RAG (Retrieval-Augmented Generation)

## 2.1 What is RAG?

**RAG** is a pattern that enhances an LLM's responses by first *retrieving* relevant context from a knowledge base, then *generating* an answer grounded in that context.

```
┌─────────┐     ┌───────────┐     ┌────────────┐     ┌──────────┐
│  Query  │────▶│  Embed    │────▶│  Vector    │────▶│   LLM    │
│ "What   │     │  Query    │     │  Search    │     │ + Context│
│  is ML?"│     │ (384-dim) │     │ (Qdrant)   │     │  Answer  │
└─────────┘     └───────────┘     └────────────┘     └──────────┘
                                         │
                                    Top-K chunks
                                    with scores
```

## 2.2 Why is RAG Needed?

| Problem with plain LLMs | How RAG solves it |
|--------------------------|-------------------|
| Hallucinate facts | Answers grounded in retrieved documents |
| Outdated training data | Uses your *own* uploaded documents |
| No source attribution | Provides page/slide-level citations |
| No access control | Metadata filtering by student/course/doc |
| Context window limits | Only sends relevant chunks, not entire docs |

## 2.3 How RAG Works in This Project

The `/ask` endpoint implements a classic RAG pipeline:

```python
# Step 1: Embed the student's question
query_vector = embed_query(question)  # → List[float], 384 dims

# Step 2: Search Qdrant for similar chunks
chunks = qdrant_retrieval_service.search(
    query_vector=query_vector,
    top_k=5,              # retrieve 5 most relevant chunks
    doc_id=request.doc_id  # optional: scope to specific document
)

# Step 3: Build LLM prompt with context
messages = build_qa_messages(question, chunks)
# System: "Answer using ONLY the provided context..."
# User: "## Context\n{chunks}\n## Question\n{question}"

# Step 4: Call LLM
answer = llm_client.chat(messages=messages, max_tokens=2048)

# Step 5: Return with citations
return AskResponse(answer=answer, citations=[...], chunks_used=5)
```

## 2.4 Why RAG Instead of Alternatives?

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **RAG** | Grounded, citable, no re-training | Retrieval quality dependent | ✅ Chosen |
| Fine-tuning | Deep domain adaptation | Expensive, no citations, stale | ❌ Overkill |
| Full-doc prompting | Simple | Context window limit, costly | ❌ Doesn't scale |
| Keyword search + LLM | Cheap | Misses semantic matches | ❌ Poor recall |

## 2.5 Advantages of RAG

- ✅ **Grounded answers** — reduces hallucination
- ✅ **Source citations** — students can verify claims
- ✅ **No re-training** — works with any new document immediately
- ✅ **Scalable** — works with 10 or 10,000 documents
- ✅ **Cost-effective** — only embeds once, queries are fast

## 2.6 Disadvantages of RAG

- ❌ Retrieval quality depends on embedding model and chunking strategy
- ❌ Multi-hop reasoning is limited (retrieving chunks A and C when the answer needs A→B→C)
- ❌ If the answer spans many pages, top-K might miss some
- ❌ Semantic search can miss exact keyword matches (hybrid search helps)

⭐ **Interview Tip:** If asked "How do you prevent hallucination?", explain: (1) system prompt instructs the LLM to answer *only* from context, (2) citations trace every claim to a source page, (3) if no relevant chunks are found, the system returns an explicit "I couldn't find relevant content" message instead of guessing.

⚠ **Common Mistake:** Don't confuse RAG with fine-tuning. RAG retrieves and *augments* the prompt at inference time. Fine-tuning modifies the model's weights during training.

## 2.7 Interview Questions & Answers

**Q: What is RAG and why did you use it?**

> **A:** RAG stands for Retrieval-Augmented Generation. It's a pattern where, before sending a query to an LLM, we first search a knowledge base (in our case, Qdrant) for relevant document chunks, then include those chunks as context in the prompt. I used RAG because it lets the LLM answer questions grounded in the student's actual uploaded documents, with page-level citations, without needing to fine-tune the model. This means any new document is immediately queryable after our Spark pipeline processes it.

**Q: How do you handle the case where no relevant context is found?**

> **A:** If Qdrant returns zero chunks (e.g., the student asks about a topic not covered in their uploads), the `/ask` endpoint returns a helpful fallback message: "I couldn't find relevant content in your documents." This is critical — returning an empty context to the LLM would cause it to hallucinate. Our system explicitly catches this case before the LLM call.

**Q: What is the difference between RAG and fine-tuning?**

> **A:** Fine-tuning changes the model's weights by training on domain-specific data — it's expensive, requires retraining when data changes, and doesn't provide citations. RAG keeps the model unchanged and instead retrieves relevant context at query time — it's cheaper, immediately reflects new data, and every answer can cite its source chunks. For our use case (students uploading new documents daily), RAG is the clear choice.

---

### Summary
- RAG = Retrieve relevant chunks + Augment LLM prompt + Generate grounded answer
- This project uses RAG across all 4 features (Q&A, Quiz, Summary, Mind Map)
- Key benefit: grounded answers with page/slide-level citations, no re-training needed

### Top 5 Interview Questions
1. *What is RAG and why did you choose it over fine-tuning?*
2. *How do you ensure the LLM doesn't hallucinate?*
3. *What happens if no relevant chunks are retrieved?*
4. *How do you decide the value of top-K (number of chunks to retrieve)?*
5. *What are the limitations of your RAG implementation?*

### Quick Revision Bullets
- RAG = Retrieval (embed query → vector search) + Augmentation (context in prompt) + Generation (LLM answer)
- top_k=5 for Q&A, top_k=10 for quiz/mindmap, top_k=15 for summarization
- Citations built from chunk metadata (page_number, slide_number, source_label)
- System prompt enforces "answer ONLY from context" constraint

---

# 3. Apache Kafka — Message Queue

## 3.1 What is Kafka?

Apache Kafka is a **distributed event streaming platform** that acts as a durable, fault-tolerant message queue. It lets producers publish messages to topics, and consumers read them independently.

```
┌──────────┐     ┌─────────────────────────────────┐     ┌──────────┐
│ Producer │────▶│       Kafka Cluster             │────▶│ Consumer │
│ (FastAPI)│     │  ┌───────────────────────────┐  │     │ (Spark)  │
│          │     │  │ Topic: documents.uploaded  │  │     │          │
│          │     │  │ Partition 0: [m1][m2][m3]  │  │     │          │
│          │     │  │ Partition 1: [m4][m5]      │  │     │          │
│          │     │  │ Partition 2: [m6]          │  │     │          │
│          │     │  └───────────────────────────┘  │     │          │
└──────────┘     └─────────────────────────────────┘     └──────────┘
```

## 3.2 Why Kafka is Needed in This Project

| Problem without Kafka | How Kafka solves it |
|-----------------------|---------------------|
| Upload blocks while processing | Upload returns immediately; processing is async |
| A large PPTX blocks the API | Kafka decouples upload from processing |
| If Spark crashes, documents are lost | Kafka persists messages; Spark can replay |
| 50 students upload simultaneously | Kafka handles bursty traffic with buffering |
| Failed processing is invisible | Dead-letter topic (`documents.failed`) captures errors |

## 3.3 How Kafka is Used

### 3 Kafka Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `documents.uploaded` | FastAPI (upload endpoint) | Spark pipeline | Trigger document processing |
| `documents.processed` | Spark (after success) | FastAPI (status update) | Notify that doc is ready |
| `documents.failed` | Spark (on error) | Monitoring/retry | Dead-letter for failures |

### Producer Configuration (FastAPI side)

```python
KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
    acks="all",        # Wait for all replicas to acknowledge
    retries=3,         # Retry on transient failures
    max_block_ms=5000, # Don't block the API thread for too long
)
```

### Message Payload (Published on Upload)

```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "student_id": "student123",
  "course_id": "CS101",
  "storage_path": "academic-documents/student123/CS101/doc-uuid.pdf",
  "file_type": ".pdf",
  "original_filename": "lecture_12.pdf",
  "timestamp": "2026-07-24T10:30:00Z"
}
```

### Consumer Configuration (Spark side)

```python
KafkaConsumer(
    "documents.uploaded",
    bootstrap_servers="localhost:9092",
    group_id="spark-processing-group",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest",
    enable_auto_commit=True,
)
```

## 3.4 Key Kafka Concepts

| Concept | Explanation |
|---------|-------------|
| **Topic** | Named channel for messages (like a database table) |
| **Partition** | A topic is split into partitions for parallelism |
| **Offset** | Sequential ID within a partition (message position) |
| **Consumer Group** | Multiple consumers sharing a topic; each partition goes to one consumer |
| **Producer acks** | Durability guarantee: `acks=all` means all replicas acknowledged |
| **Dead-letter topic** | A topic where failed messages are routed for later inspection |

## 3.5 Why Kafka Instead of Alternatives?

| Message Queue | Pros | Cons | Verdict |
|---------------|------|------|---------|
| **Kafka** | Durable, replay, scalable, ecosystem | Heavier setup | ✅ Chosen |
| RabbitMQ | Simple, routing flexibility | No built-in replay | ❌ |
| Redis Pub/Sub | Ultra-fast, simple | No persistence, no replay | ❌ |
| SQS (AWS) | Managed, reliable | Cloud-locked, no local dev | ❌ |
| Direct function call | Zero overhead | Tight coupling, no retry | ❌ |

## 3.6 Advantages

- ✅ **Decoupling** — upload and processing are independent services
- ✅ **Replay** — if Spark crashes, it can re-consume from the last committed offset
- ✅ **Durability** — messages are persisted to disk, survive broker restarts
- ✅ **Dead-letter** — failed documents are inspectable, not silently lost
- ✅ **Scalability** — 3 partitions allow up to 3 parallel consumers

## 3.7 Disadvantages

- ❌ **Operational complexity** — requires Zookeeper (in this version), monitoring
- ❌ **Latency overhead** — adds a few ms vs direct function call
- ❌ **Overkill for small scale** — a single student uploading one file doesn't need Kafka
- ❌ **Message ordering** — only guaranteed within a partition, not across

⭐ **Interview Tip:** When they ask "Why not just call the processing function directly?", answer: "Because a 100 MB PPTX takes 30 seconds to process. Without Kafka, the HTTP request blocks for 30 seconds. With Kafka, the API returns `201 Created` immediately and the heavy work happens asynchronously. If Spark crashes mid-processing, Kafka retains the message for retry."

⚠ **Common Mistake:** Don't say "Kafka is a message queue." Technically, Kafka is a distributed *event log* / *streaming platform*. It has queue-like behavior but its core model is an append-only log with consumer offsets.

## 3.8 Interview Questions & Answers

**Q: Why did you use Kafka instead of just processing inline?**

> **A:** Kafka decouples the upload API from the processing pipeline. When a student uploads a large PDF, we don't want the HTTP request to block while Spark parses, chunks, and embeds the document — that could take 30+ seconds. With Kafka, the API stores the file in MinIO, publishes a lightweight message to `documents.uploaded`, and returns `201 Created` immediately. Spark picks up the message asynchronously. If Spark is temporarily down, the message is persisted in Kafka and will be processed when Spark recovers.

**Q: What happens if a document fails during processing?**

> **A:** The Spark pipeline wraps each document in a try/except. On failure (e.g., corrupted PDF), instead of crashing the batch, it publishes the error to `documents.failed` — our dead-letter topic. This makes failures inspectable rather than invisible. The error payload includes the `doc_id` and error message, so we can debug and potentially retry.

**Q: Explain `acks=all` in your Kafka producer.**

> **A:** `acks=all` means the producer waits until all in-sync replicas have acknowledged the message before considering the send successful. In our case with `replication_factor=1`, it effectively means the single broker has flushed the message to its log. In production with RF=3, it would mean all 3 replicas confirmed. This is the strongest durability guarantee — no message loss unless the entire cluster dies.

---

### Summary
- Kafka has 3 topics: uploaded (trigger), processed (completion), failed (dead-letter)
- Decouples upload from processing — API returns instantly
- `acks=all` + `retries=3` for durability
- Consumer group ensures each message is processed exactly once per consumer group

### Top 5 Interview Questions
1. *Why did you choose Kafka over RabbitMQ or Redis?*
2. *What is a dead-letter topic and why do you have one?*
3. *What happens if Kafka is down when a student uploads?*
4. *Explain consumer groups and how they relate to partitions.*
5. *How does Kafka guarantee message ordering?*

### Quick Revision Bullets
- 3 topics: `documents.uploaded`, `documents.processed`, `documents.failed`
- Producer: FastAPI → `acks=all`, `retries=3`
- Consumer: Spark → `group_id="spark-processing-group"`, `auto_offset_reset="latest"`
- 3 partitions per topic → up to 3 parallel consumers
- Kafka persists messages → replay on failure

---

# 4. Apache Spark — Distributed Processing

## 4.1 What is Spark?

Apache Spark is a **distributed computing framework** for processing large-scale data in parallel across a cluster.

## 4.2 Why Spark is Needed

The document processing pipeline has **embarrassingly parallel** work:
- Parsing 50 PDFs is independent per document
- Embedding 2000 text chunks can be batched across partitions
- A sequential Python loop gets slower linearly; Spark parallelizes across executors

```
Sequential (naive loop):
  doc1 → parse → chunk → embed (10s)
  doc2 → parse → chunk → embed (10s)
  ...
  doc50 → parse → chunk → embed (10s)
  Total: 500 seconds

Spark (4 executors):
  Executor 1: [doc1..doc13]  → 130s
  Executor 2: [doc14..doc25] → 120s
  Executor 3: [doc26..doc38] → 130s
  Executor 4: [doc39..doc50] → 120s
  Total: ~130 seconds (3.8x speedup)
```

## 4.3 How Spark is Used — Structured Streaming

The project uses **Spark Structured Streaming** with `foreachBatch`:

```python
# Read from Kafka as a streaming DataFrame
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "documents.uploaded")
    .option("startingOffsets", "latest")
    .load()
)

# Parse the JSON payload
parsed_df = kafka_df.select(
    from_json(col("value").cast("string"), message_schema).alias("msg")
).select("msg.*")

# Process each micro-batch
def process_batch(batch_df, batch_id):
    rows = batch_df.collect()
    for row in rows:
        result = process_document(row.asDict(), minio_client, qdrant_writer)
        # Publish result to documents.processed or documents.failed

# Start streaming
parsed_df.writeStream \
    .foreachBatch(process_batch) \
    .trigger(processingTime="10 seconds") \
    .option("checkpointLocation", "/tmp/checkpoints") \
    .start() \
    .awaitTermination()
```

## 4.4 Key Spark Concepts Used

| Concept | How It's Used |
|---------|---------------|
| **Structured Streaming** | Reads from Kafka as a continuous stream |
| **foreachBatch** | Custom processing logic per micro-batch |
| **Micro-batch** | Every 10 seconds, process all new messages |
| **Checkpoint** | Saves offset state for exactly-once recovery |
| **mapInPandas** | Used for embedding — loads model once per partition |

## 4.5 The `mapInPandas` Pattern for Embeddings

This is a key design decision worth explaining in interviews:

```python
def embed_chunks_pandas_udf(model_name="all-MiniLM-L6-v2"):
    """Returns a function for Spark's mapInPandas."""
    
    def _embed_partition(iterator):
        # Model loaded ONCE per partition (not per row!)
        model = _get_model(model_name)
        
        for pdf in iterator:
            texts = pdf["text"].tolist()
            embeddings = model.encode(texts, batch_size=64)
            pdf["embedding"] = [emb.tolist() for emb in embeddings]
            yield pdf
    
    return _embed_partition

# Usage:
result_df = chunks_df.mapInPandas(embed_fn, schema=output_schema)
```

⭐ **Interview Tip:** The `mapInPandas` pattern is the "why Spark" argument. Without it, a regular UDF would reload the 90MB embedding model *per row*. With `mapInPandas`, the model loads once per executor partition and processes all rows in that partition as a batch.

## 4.6 Standalone Mode (Fallback)

For local development without a Spark cluster, the project also has a **standalone consumer**:

```python
def run_standalone_consumer():
    consumer = KafkaConsumer("documents.uploaded", ...)
    for msg in consumer:
        result = process_document(msg.value, ...)
        # Same pipeline, just sequential
```

This reuses the exact same `process_document()` function — demonstrating clean separation between the processing logic and the execution engine.

## 4.7 Why Spark Instead of Alternatives?

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **PySpark Structured Streaming** | Distributed, Kafka-native, mapInPandas | Setup overhead | ✅ Chosen |
| Celery + Redis | Simple workers | No mapInPandas, model reload issue | ❌ |
| Python multiprocessing | Zero infra | No cluster mode, GIL issues | ❌ |
| Dask | Python-native | Weaker streaming, smaller ecosystem | ❌ |
| AWS Lambda | Serverless | Cold start, 15min timeout, 10GB limit | ❌ |

## 4.8 Advantages

- ✅ **Horizontal scaling** — add executors to process more docs in parallel
- ✅ **mapInPandas** — load ML model once per partition, batch inference
- ✅ **Kafka integration** — native `spark-sql-kafka` connector
- ✅ **Checkpointing** — exactly-once recovery on failure
- ✅ **Micro-batching** — 10-second trigger balances latency and throughput

## 4.9 Disadvantages

- ❌ **Complex setup** — JVM dependency, Spark cluster
- ❌ **Overkill for single-user** — overhead not justified for small scale
- ❌ **Memory hungry** — Spark executors need significant RAM
- ❌ **Python-JVM bridge** — PySpark adds serialization overhead

---

### Summary
- Spark Structured Streaming consumes `documents.uploaded` from Kafka
- foreachBatch with 10-second micro-batches
- mapInPandas loads embedding model once per partition (not per row)
- Standalone mode for local dev reuses the same process_document() logic
- Checkpoint directory enables exactly-once recovery

### Top 5 Interview Questions
1. *Why Spark instead of Celery or simple Python multiprocessing?*
2. *What is Structured Streaming and how does it differ from batch processing?*
3. *Explain the `mapInPandas` pattern and why you used it.*
4. *What is foreachBatch and why not use foreach?*
5. *How does checkpointing work in Spark Structured Streaming?*

### Quick Revision Bullets
- Spark reads Kafka → foreachBatch → process_document → Qdrant
- `mapInPandas` = model loaded once/partition, not once/row
- Trigger: `processingTime="10 seconds"` → micro-batches
- Checkpoint saves Kafka offsets for exactly-once processing
- Standalone mode = same logic, sequential execution, no Spark cluster

---

# 5. Document Parsing Pipeline

## 5.1 What is Document Parsing?

Converting raw file bytes (PDF, PPTX, TXT) into structured text sections with metadata (page numbers, slide titles).

## 5.2 Parser Architecture

```
              get_parser(file_type)
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   PDFParser     PPTXParser    TextParser
   (PyMuPDF)    (python-pptx)   (plain)
        │             │             │
        ▼             ▼             ▼
   List[ParsedSection]   ←── Common output format
```

### ParsedSection (Common Output)

```python
@dataclass
class ParsedSection:
    label: str         # "Page 3" or "Slide 7"
    index: int         # 0-based numeric index
    text: str          # Extracted text content
    metadata: dict     # {"page_number": 3, "total_pages": 20}
```

## 5.3 PDF Parsing (PyMuPDF / fitz)

```python
class PDFParser(BaseParser):
    def parse(self, file_bytes, filename):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        sections = []
        for page_num in range(len(doc)):
            text = doc[page_num].get_text("text").strip()
            if text:  # Skip pages with no extractable text (scanned images)
                sections.append(ParsedSection(
                    label=f"Page {page_num + 1}",
                    index=page_num,
                    text=text,
                    metadata={"page_number": page_num + 1, "total_pages": len(doc)}
                ))
        doc.close()
        return sections
```

**Why PyMuPDF over alternatives?**

| Library | Speed | Text Quality | Pros | Cons |
|---------|-------|-------------|------|------|
| **PyMuPDF (fitz)** | ⚡ Fast | High | C-based, in-memory | No OCR built-in | ✅
| PyPDF2 | Slow | Medium | Pure Python | Fragile with complex PDFs | ❌
| pdfplumber | Medium | High | Table extraction | Heavier | ❌
| Tika | Slow | High | OCR support | Needs Java server | ❌

## 5.4 PPTX Parsing (python-pptx)

```python
class PPTXParser(BaseParser):
    def parse(self, file_bytes, filename):
        prs = Presentation(io.BytesIO(file_bytes))
        for slide_idx, slide in enumerate(prs.slides):
            title = self._extract_title(slide)
            text = self._extract_slide_text(slide)
            sections.append(ParsedSection(
                label=f"Slide {slide_idx + 1}",
                metadata={"slide_number": slide_idx+1, "slide_title": title}
            ))
```

**Critical: Run-Merging**

PowerPoint internally stores text as fragmented "runs" (each with its own formatting):
```xml
<a:p>
  <a:r><a:t>Machine</a:t></a:r>
  <a:r><a:t> </a:t></a:r>
  <a:r><a:t>Learning</a:t></a:r>
</a:p>
```

Naive XML parsing would give you: `["Machine", " ", "Learning"]` → broken chunks.

`python-pptx` merges runs correctly: `"Machine Learning"` ← one clean string.

⭐ **Interview Tip:** If asked about a challenge you faced, mention the PPTX run-merging problem. It shows you understand that parsing is non-trivial and you chose the right library to handle edge cases.

## 5.5 Design Pattern: Strategy Pattern

The parser dispatch uses the **Strategy Pattern**:

```python
def get_parser(file_type: str) -> BaseParser:
    parsers = {
        ".pdf": PDFParser,
        ".pptx": PPTXParser,
        ".txt": TextParser,
        ".md": TextParser,
    }
    return parsers[file_type.lower()]()
```

**Why?**
- Open/Closed Principle: add new parsers without modifying existing code
- Same interface (`parse(file_bytes, filename) → List[ParsedSection]`) for all types
- Easy to test each parser independently

---

### Summary
- 3 parsers: PDF (PyMuPDF), PPTX (python-pptx), Text (plain read)
- Common output: `List[ParsedSection]` with label, index, text, metadata
- PPTX uses proper run-merging to avoid text fragmentation
- Strategy pattern for parser dispatch

### Top 5 Interview Questions
1. *Why did you choose PyMuPDF over PyPDF2 or Tika?*
2. *What is the run-merging problem in PPTX parsing?*
3. *What design pattern did you use for the parser dispatch?*
4. *How do you handle corrupted PDFs or PPTX files?*
5. *How would you add support for a new file type (e.g., DOCX)?*

### Quick Revision Bullets
- PDF: `fitz.open(stream=bytes)` → per-page text extraction
- PPTX: `python-pptx` → per-slide, with run-merging and table extraction
- All parsers return `List[ParsedSection]` (Strategy Pattern)
- Corrupted files → `ValueError` → caught by Spark → routed to `documents.failed`

---

# 6. Text Chunking Strategy

## 6.1 What is Text Chunking?

Splitting long documents into smaller, overlapping text pieces ("chunks") that can be individually embedded and retrieved.

## 6.2 Why Chunking is Needed

| Reason | Explanation |
|--------|-------------|
| **Embedding models have limits** | Most models handle ~512 tokens max effectively |
| **Precision** | A full-page embedding is too broad; a chunk-level embedding is more targeted |
| **Context window** | LLMs have limited context; send only relevant chunks, not entire documents |
| **Citation accuracy** | Chunk-level retrieval enables page/slide-level citations |

## 6.3 Chunking Parameters

```python
chunk_sections(
    sections=parsed_sections,
    max_tokens=400,           # Target chunk size
    overlap_fraction=0.15,    # 15% overlap = ~60 tokens
)
```

| Parameter | Value | Why |
|-----------|-------|-----|
| `max_tokens` | 400 | Below 512 limit, leaves room for query+padding |
| `overlap_fraction` | 0.15 (60 tokens) | Context continuity across chunk boundaries |

## 6.4 How Chunking Works

### Algorithm (Sentence-Aware Chunking)

```
Input: List of sentences with token counts

1. Initialize chunk_buffer = [], token_count = 0
2. For each sentence:
   a. If token_count + sentence_tokens > max_tokens AND buffer non-empty:
      → Emit current chunk
      → Compute overlap: walk backward ~60 tokens
      → Start new chunk from overlap point
   b. Add sentence to buffer, increment token_count
3. Emit final chunk

Key: NEVER break mid-sentence
```

### Visual Example

```
Document text (sentences):
  S1(50t) S2(40t) S3(80t) S4(100t) S5(60t) S6(90t) S7(70t) S8(50t)

max_tokens=400, overlap=60 tokens

Chunk 1: [S1 + S2 + S3 + S4 + S5] = 330 tokens
                                ──────
                                overlap ← S5 (60t)
Chunk 2: [S5 + S6 + S7 + S8] = 270 tokens
          ──────
          overlap from Chunk 1
```

## 6.5 PPTX-Specific Chunking

PPTX slides are natural boundaries, but some slides have very little text (e.g., title-only slides). The project merges short slides before chunking:

```python
def chunk_pptx_sections(sections, max_tokens=400, min_slide_tokens=50):
    # Step 1: Merge slides with < 50 tokens into the next slide
    merged = merge_short_slides(sections)
    
    # Step 2: Apply standard sentence-aware chunking
    return chunk_sections(merged, max_tokens)
```

```
Before merging:
  Slide 1: "Introduction" (3 tokens) ← too short
  Slide 2: "Machine Learning Overview..." (200 tokens)
  Slide 3: "Types of ML" (5 tokens) ← too short
  Slide 4: "Supervised vs Unsupervised..." (180 tokens)

After merging:
  Slide 1–2: "Introduction\n\nMachine Learning Overview..." (203 tokens)
  Slide 3–4: "Types of ML\n\nSupervised vs Unsupervised..." (185 tokens)
```

## 6.6 Token Estimation

```python
def _estimate_tokens(text: str) -> int:
    return len(text.split())  # Whitespace-based estimate
```

**Why not use the model's tokenizer?**
- Chunking runs in the Spark pipeline, before the embedding model is loaded
- Whitespace splitting is ~80% accurate and 100x faster
- Exact tokenization would require loading the tokenizer (heavy dependency)

## 6.7 Why This Chunking Instead of Alternatives?

| Strategy | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Sentence-aware + overlap** | Preserves meaning, smooth boundaries | Slightly complex | ✅ Chosen |
| Fixed-size (every N chars) | Simple | Breaks mid-sentence, poor retrieval | ❌ |
| Paragraph-based | Natural boundaries | Paragraphs vary wildly in size | ❌ |
| Recursive splitting (LangChain) | Flexible | Over-engineered for our use case | ❌ |
| Semantic chunking | Best retrieval quality | Expensive (needs embeddings to decide splits) | ❌ Too slow |

## 6.8 Advantages

- ✅ Never breaks mid-sentence
- ✅ 15% overlap preserves context across boundaries
- ✅ PPTX-specific logic handles title-only slides
- ✅ Configurable via env vars
- ✅ Fast whitespace-based token estimation

## 6.9 Disadvantages

- ❌ Whitespace token estimate ≠ exact model tokenization
- ❌ Overlap increases storage (15% more chunks)
- ❌ Fixed overlap fraction may not suit all content types
- ❌ No semantic awareness (doesn't know topic boundaries)

> **Formula: Chunk Overlap**
>
> ```
> overlap_tokens = max_tokens × overlap_fraction
>                = 400 × 0.15
>                = 60 tokens
>
> Approximate chunks per document:
>   N_chunks ≈ total_tokens / (max_tokens - overlap_tokens)
>            = total_tokens / (400 - 60)
>            = total_tokens / 340
> ```

⭐ **Interview Tip:** If asked "Why 400 tokens and 15% overlap?", say: "400 keeps us below the 512-token sweet spot of MiniLM while leaving room for the query in the embedding context. 15% overlap (~60 tokens, about 2-3 sentences) ensures that if an answer spans a chunk boundary, both adjacent chunks contain enough context for the retriever to find them."

---

### Summary
- Sentence-aware chunking: never breaks mid-sentence
- 400 tokens target, 15% overlap (~60 tokens)
- PPTX: merge short slides (< 50 tokens) before chunking
- Fast whitespace token estimation (not model tokenizer)

### Top 5 Interview Questions
1. *Why sentence-aware chunking instead of fixed-size?*
2. *What is chunk overlap and why is it important?*
3. *How did you handle short PPTX slides?*
4. *How do you estimate token counts?*
5. *What trade-offs exist between chunk size and retrieval quality?*

### Quick Revision Bullets
- max_tokens=400, overlap_fraction=0.15 → 60 tokens overlap
- NLTK `sent_tokenize` for sentence boundary detection
- PPTX: merge slides < 50 tokens with next slide
- `_estimate_tokens` = `len(text.split())` (fast, approximate)
- Chunk output: `Chunk(text, chunk_index, token_count, source_label, source_indices)`

---

# 7. Embeddings & Sentence-Transformers

## 7.1 What are Embeddings?

Embeddings are **dense vector representations** of text in a continuous vector space, where semantically similar texts are close together.

```
"What is supervised learning?"  →  [0.12, -0.34, 0.56, ..., 0.89]  (384 dims)
"Explain labeled training data" →  [0.11, -0.31, 0.55, ..., 0.87]  (384 dims)
                                     ↑ very similar vectors!

"The weather is nice today"     →  [0.78, 0.22, -0.44, ..., -0.15]  (384 dims)
                                     ↑ very different vector
```

## 7.2 Why Embeddings are Needed

| Without embeddings | With embeddings |
|-------------------|-----------------|
| Keyword match: "ML" won't find "machine learning" | Semantic: similar meaning → similar vector |
| Can't compare query to 10,000 chunks efficiently | Vector search in O(log n) with ANN index |
| No ranking by relevance | Cosine similarity gives a relevance score |

## 7.3 The Model: `all-MiniLM-L6-v2`

| Property | Value |
|----------|-------|
| **Full name** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Dimensions** | 384 |
| **Max sequence length** | 256 tokens (can handle up to 512) |
| **Model size** | ~90 MB |
| **Architecture** | 6-layer MiniLM (distilled from BERT) |
| **Training** | 1 billion sentence pairs (contrastive learning) |
| **Speed** | ~2800 sentences/sec on GPU, ~500/sec on CPU |
| **Use case** | General-purpose semantic search |

## 7.4 How Embedding Works

### Mathematical Foundation

> **Cosine Similarity Formula:**
>
> ```
>               A · B            Σ(Aᵢ × Bᵢ)
> cos(θ) = ─────────── = ──────────────────────
>           ‖A‖ × ‖B‖    √(Σ Aᵢ²) × √(Σ Bᵢ²)
>
> Range: [-1, 1]
>   1.0 = identical direction (most similar)
>   0.0 = orthogonal (unrelated)
>  -1.0 = opposite direction (antonyms, rare with normalized embeddings)
> ```

Since embeddings are **normalized** (`normalize_embeddings=True`), cosine similarity simplifies to a dot product:

> ```
> If ‖A‖ = ‖B‖ = 1 (unit vectors):
>   cos(θ) = A · B = Σ(Aᵢ × Bᵢ)
> ```

## 7.5 Code: Embedding in the Project

### API-side (single query embedding)

```python
def embed_query(query: str) -> List[float]:
    model = _get_model()  # Lazy-loaded, cached globally
    embedding = model.encode(
        query,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # Unit vector for cosine sim
    )
    return embedding.tolist()
```

### Spark-side (batch embedding with model caching)

```python
# Module-level cache: one model per executor process
_MODEL_CACHE = {}

def _get_model(model_name):
    if model_name not in _MODEL_CACHE:
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
    return _MODEL_CACHE[model_name]

def embed_chunks_batch(chunks_data, model_name, batch_size=64):
    texts = [c["text"] for c in chunks_data]
    embeddings = embed_texts(texts, model_name, batch_size)
    for chunk, emb in zip(chunks_data, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks_data
```

⭐ **Interview Tip:** Emphasize the **model caching pattern**. Loading a 90 MB model per row in Spark would be catastrophically slow. The `_MODEL_CACHE` dict ensures the model loads once per executor process. In `mapInPandas`, this means one load per partition.

## 7.6 Why `all-MiniLM-L6-v2` Instead of Alternatives?

| Model | Dims | Speed | Quality | Size | Verdict |
|-------|------|-------|---------|------|---------|
| **all-MiniLM-L6-v2** | 384 | ⚡⚡⚡ | Good | 90 MB | ✅ Chosen |
| all-mpnet-base-v2 | 768 | ⚡⚡ | Best | 420 MB | ❌ Too heavy for Spark |
| text-embedding-3-small (OpenAI) | 1536 | API | Great | API-only | ❌ Cost, latency |
| BGE-small-en | 384 | ⚡⚡⚡ | Good | 130 MB | ❌ Similar, newer |
| TF-IDF | sparse | ⚡⚡⚡⚡ | Poor | tiny | ❌ No semantics |

**Why 384 dimensions?**
- 384 dims is the sweet spot: 50% of the storage of 768-dim models, with only ~2-3% quality drop on standard benchmarks
- Qdrant storage: 384 × 4 bytes = **1.5 KB per vector** vs 768 × 4 = 3 KB

## 7.7 Important: Same Model for Indexing and Querying

```
CRITICAL: The SAME model must be used for both:
  1. Embedding document chunks (Spark pipeline)
  2. Embedding user queries (FastAPI /ask endpoint)

If different models are used, the vector spaces won't align
and cosine similarity will be meaningless.
```

⚠ **Common Mistake:** Using one model to embed documents and a different model for queries. The vectors must live in the same embedding space.

---

### Summary
- `all-MiniLM-L6-v2`: 384 dims, 90 MB, fast, good quality
- Normalized embeddings → cosine similarity = dot product
- Model cached globally (API) and per-partition (Spark)
- Same model used for both document chunks and user queries

### Top 5 Interview Questions
1. *What is the difference between sparse (TF-IDF) and dense (transformer) embeddings?*
2. *Why did you choose `all-MiniLM-L6-v2` over larger models?*
3. *What is cosine similarity and why normalize embeddings?*
4. *How did you avoid reloading the model per row in Spark?*
5. *What would happen if you used a different model for queries vs documents?*

### Quick Revision Bullets
- 384-dimensional dense vectors, normalized (unit length)
- `cos(θ) = A · B` when normalized (reduces to dot product)
- Model cached: API = module-level `_model`, Spark = `_MODEL_CACHE` dict
- `batch_size=64` for efficient batch encoding
- Same model for indexing (Spark) and querying (FastAPI) — critical

---

# 8. Vector Database — Qdrant

## 8.1 What is Qdrant?

Qdrant is a **purpose-built vector database** that stores high-dimensional vectors with associated metadata (payloads) and supports fast **Approximate Nearest Neighbor (ANN)** search.

## 8.2 Why Qdrant is Needed

| Requirement | How Qdrant Fulfills It |
|------------|------------------------|
| Store 384-dim vectors | Native vector storage with configurable dimensions |
| Fast similarity search | HNSW index for O(log n) ANN search |
| Filter by doc/student/course | Payload-based metadata filtering |
| Persist across restarts | Docker volume-backed storage |
| Scale with growing data | ANN stays fast even with 100K+ vectors |

## 8.3 How Qdrant is Used

### Collection Setup

```python
client.create_collection(
    collection_name="academic_chunks",
    vectors_config=VectorParams(
        size=384,               # Matches embedding model
        distance=Distance.COSINE  # Cosine similarity metric
    ),
)
```

### Upsert (Write)

```python
points = [
    PointStruct(
        id=str(uuid.uuid4()),
        vector=[0.12, -0.34, ...],   # 384 floats
        payload={
            "doc_id": "abc-123",
            "student_id": "student456",
            "course_id": "CS101",
            "text": "Supervised learning uses labeled data...",
            "source_label": "Page 3",
            "page_number": 3,
            "original_filename": "lecture.pdf",
            "chunk_index": 7,
        }
    )
]
client.upsert(collection_name="academic_chunks", points=points)
```

### Search (Read)

```python
results = client.query_points(
    collection_name="academic_chunks",
    query=query_vector,          # 384-dim float list
    query_filter=Filter(must=[   # Metadata filtering
        FieldCondition(key="doc_id", match=MatchValue(value="abc-123")),
        FieldCondition(key="course_id", match=MatchValue(value="CS101")),
    ]),
    limit=5,                     # top-K results
    with_payload=True,           # Return full metadata
)
```

## 8.4 HNSW (Hierarchical Navigable Small World) Index

HNSW is the ANN algorithm Qdrant uses internally:

```
Layer 2 (sparse):    A ─── B ─── C              (long-range connections)
                     │           │
Layer 1 (medium):    A ── D ── B ── E ── C       (medium connections)
                     │    │    │    │    │
Layer 0 (dense):    A─F─D─G─B─H─E─I─C─J        (all points, short connections)

Search: Start at top layer, greedily move toward query,
        drop down layers for finer resolution.
        
Time complexity: O(log n) per query
Space complexity: O(n × M) where M = connections per node
```

**Why HNSW over brute-force?**

| Method | 10K vectors | 100K vectors | 1M vectors |
|--------|-------------|-------------|-------------|
| **Brute-force** | 5ms | 50ms | 500ms |
| **HNSW (ANN)** | 1ms | 2ms | 5ms |

## 8.5 Why Qdrant Instead of Alternatives?

| Vector DB | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **Qdrant** | Rich filtering, self-hosted, Rust-fast, Docker-ready | Smaller community than Pinecone | ✅ Chosen |
| Pinecone | Managed, scalable | Cloud-only, costly, no local dev | ❌ |
| Weaviate | Multi-modal, GraphQL | Heavier, more complex | ❌ |
| ChromaDB | Simple, Python-native | Limited filtering, early-stage | ❌ |
| FAISS (library) | Ultra-fast | Not a database, no persistence, no filtering | ❌ |
| IndexedDB (browser) | No server needed | Linear scan, no ANN, no persistence across devices | ❌ Original plan |

## 8.6 Metadata Filtering — Key Feature

Qdrant lets us scope searches to specific subsets:

```python
# "Search only in this student's CS101 documents"
Filter(must=[
    FieldCondition(key="student_id", match=MatchValue(value="stu123")),
    FieldCondition(key="course_id", match=MatchValue(value="CS101")),
])
```

This is critical for **multi-tenant** scenarios where students shouldn't see each other's documents.

⭐ **Interview Tip:** Qdrant's metadata filtering is a key differentiator vs. FAISS. FAISS finds the top-K nearest neighbors globally; Qdrant can find top-K *within a specific student's CS101 documents*. This is essential for any multi-user application.

## 8.7 Batched Upserts

```python
# Write in batches of 100 to avoid overwhelming Qdrant
for i in range(0, len(points), batch_size):
    batch = points[i : i + batch_size]
    client.upsert(collection_name="academic_chunks", points=batch)
```

Why batching?
- Single large upsert may timeout
- Batches of 100 balance throughput and reliability
- Benchmarks show ~35K chunks/sec throughput

---

### Summary
- Qdrant stores 384-dim vectors with full metadata payloads
- HNSW index for O(log n) ANN search
- Metadata filtering: scope searches by doc_id, student_id, course_id
- Batched upserts (100 per batch) for reliability
- Cosine distance metric for similarity scoring

### Top 5 Interview Questions
1. *Why Qdrant instead of FAISS or Pinecone?*
2. *What is HNSW and how does it achieve sub-linear search?*
3. *How do you handle multi-tenancy in vector search?*
4. *What is the difference between exact and approximate nearest neighbor search?*
5. *How much storage does each vector require?*

### Quick Revision Bullets
- Collection: `academic_chunks`, 384 dims, cosine distance
- Each point: UUID id + 384-float vector + metadata payload
- HNSW: O(log n) search, O(n × M) space
- Metadata filter: `FieldCondition` on doc_id, student_id, course_id
- Batched upserts: 100 points/batch, ~35K chunks/sec throughput

---

# 9. LLM Orchestration Layer

## 9.1 What is the LLM Layer?

A provider-agnostic wrapper around any OpenAI-compatible chat completions API, used for Q&A, quiz generation, summarization, and mind map extraction.

## 9.2 Architecture

```python
class LLMClient:
    def __init__(self):
        self.api_key = settings.LLM_API_KEY       # Server-side only!
        self.base_url = settings.LLM_BASE_URL      # "https://api.groq.com/openai/v1"
        self.model = settings.LLM_MODEL            # "llama-3.1-70b-versatile"
        self.temperature = settings.LLM_TEMPERATURE  # 0.1

    def chat(self, messages, max_tokens) -> str:
        """Text response."""
        # POST to {base_url}/chat/completions
        
    def chat_json(self, messages, max_tokens) -> dict:
        """JSON-mode response."""
        # Same as chat() but with response_format={"type": "json_object"}
```

## 9.3 Provider Agnosticism

The client works with *any* OpenAI-compatible API:

| Provider | Base URL | Model |
|----------|---------|-------|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Together AI | `https://api.together.xyz/v1` | `meta-llama/Llama-3.1-70B` |
| Local vLLM | `http://localhost:8080/v1` | Any local model |

**Swapping providers is a config change, not a code change.**

## 9.4 Security: Server-Side API Key

```
❌ OLD (browser plan): API key in localStorage → anyone can steal it
✅ NEW (this project): API key in .env → never exposed to client
```

The React frontend calls FastAPI, which calls the LLM API. The browser never sees the API key.

## 9.5 JSON Mode for Structured Outputs

For quiz, summary, and mind map, the LLM must return structured JSON:

```python
raw = self.chat(
    messages=messages,
    response_format={"type": "json_object"},  # Forces valid JSON output
)
return json.loads(raw)
```

The project adds **server-side schema validation** on top:
- Quiz: Verify 4 options, valid correct_answer (A/B/C/D)
- Mind map: Normalize nested JSON structure, handle string children
- Summary: Validate non-empty summary text and key_points list

⭐ **Interview Tip:** JSON mode + schema validation is a strong pattern to mention. LLMs are unreliable at following exact schemas — your code should validate and normalize the output, not blindly trust it.

## 9.6 Prompt Engineering

All prompts are centralized in `utils/prompts.py`:

```python
QA_SYSTEM_PROMPT = """
You are an expert academic tutor. Answer using ONLY the provided context.
1. Base your answer entirely on the provided context chunks.
2. If the context doesn't contain enough info, say so clearly — do NOT fabricate.
3. Cite your sources using [Source: <label>] format.
4. Structure your answer with paragraphs or bullet points.
5. Use precise academic language.
"""
```

**Key principles:**
1. **Role assignment** — "You are an expert academic tutor"
2. **Grounding constraint** — "ONLY the provided context"
3. **Anti-hallucination** — "do NOT fabricate information"
4. **Citation format** — `[Source: Page 3]`
5. **Output structure** — "paragraphs or bullet points"

⚠ **Common Mistake:** Putting prompts inline in router code. Centralizing them in `prompts.py` makes them easy to iterate on, A/B test, and review.

---

### Summary
- Provider-agnostic LLM client using OpenAI-compatible API format
- API key held server-side (never exposed to browser)
- JSON mode + server-side schema validation for structured outputs
- Centralized prompt templates with role, grounding, and citation instructions

### Top 5 Interview Questions
1. *How did you make your LLM layer provider-agnostic?*
2. *How do you handle LLM outputs that don't conform to your expected schema?*
3. *What prompt engineering techniques did you use?*
4. *Why is it important to keep the API key server-side?*
5. *What is JSON mode and why is it useful?*

### Quick Revision Bullets
- `LLMClient` wraps any `/chat/completions` endpoint
- `temperature=0.1` for deterministic, factual answers
- `response_format={"type": "json_object"}` for structured outputs
- All prompts in `utils/prompts.py` — system + user message pattern
- Schema validation: quiz (4 options, A-D), mindmap (recursive tree), summary (text + key_points)

---

# 10. Map-Reduce Summarization

## 10.1 What is Map-Reduce Summarization?

A two-phase pattern for summarizing documents that are too long to fit in a single LLM context window:

```
                      MAP PHASE                    REDUCE PHASE
               ┌─────────────────┐           ┌──────────────────┐
Chunks 1-3 ───▶│ LLM: Summarize  │──▶ S1 ───▶│                  │
               └─────────────────┘           │ LLM: Synthesize  │──▶ Final
Chunks 4-6 ───▶│ LLM: Summarize  │──▶ S2 ───▶│ all summaries    │    Summary
               └─────────────────┘           │ into one + key   │    + Key
Chunks 7-9 ───▶│ LLM: Summarize  │──▶ S3 ───▶│ points           │    Points
               └─────────────────┘           └──────────────────┘
```

## 10.2 Why Map-Reduce?

| Simple approach | Problem |
|----------------|---------|
| Send all text to LLM | Exceeds context window for long docs |
| Send only first N chunks | Misses important content at the end |
| Send random chunks | Incoherent summary |

**Map-Reduce solves all three:** every chunk is summarized, and summaries are synthesized.

## 10.3 Implementation

```python
_MAP_BATCH_SIZE = 3  # Chunks per map step

# Short doc (≤3 chunks): skip map, go straight to reduce
if len(chunk_groups) <= 1:
    section_summaries = [chunk_groups[0]]
else:
    # Map: summarize each group of 3 chunks independently
    for group_text in chunk_groups:
        summary = llm_client.chat(build_summarize_map_messages(group_text))
        section_summaries.append(summary)

# Reduce: synthesize all section summaries into final output
result = llm_client.chat_json(build_summarize_reduce_messages(
    section_summaries, length="medium", topic=request.topic
))
# Returns: {"summary": "...", "key_points": ["...", "..."]}
```

## 10.4 Configurable Length

| Length | Description | Paragraphs |
|--------|-------------|------------|
| `brief` | Quick overview | 2-3 |
| `medium` | Balanced detail | 4-6 |
| `detailed` | Comprehensive | 8-10 |

## 10.5 Advantages vs Disadvantages

| ✅ Advantages | ❌ Disadvantages |
|---------------|------------------|
| Handles arbitrarily long documents | Multiple LLM calls = higher cost |
| Every section contributes | Information may be lost in map step |
| Parallelizable map step | Sequential reduce (bottleneck) |
| Configurable output length | Latency scales with doc length |

⭐ **Interview Tip:** If asked "How do you handle documents that don't fit in the LLM context window?", describe map-reduce and mention that for short documents (≤3 chunks), you skip the map step entirely — this shows you optimized for the common case.

---

### Summary
- Map phase: independently summarize groups of 3 chunks each
- Reduce phase: synthesize all section summaries into final summary + key points
- Short docs (≤3 chunks) skip map and go straight to reduce
- Output: JSON with `summary` (text) and `key_points` (list)

### Top 5 Interview Questions
1. *What is map-reduce summarization and why is it needed?*
2. *What happens for short documents?*
3. *How do you configure summary length?*
4. *What's the trade-off between map-reduce and stuffing?*
5. *Can you parallelize the map step?*

### Quick Revision Bullets
- Map batch size: 3 chunks per group
- Map: LLM summarizes each group → section summary
- Reduce: LLM synthesizes all section summaries → final summary + key points
- Short docs (≤3 chunks) → skip map, direct reduce
- Configurable: brief (2-3¶), medium (4-6¶), detailed (8-10¶)

---

# 11. MinIO — Object Storage

## 11.1 What is MinIO?

MinIO is a **self-hosted, S3-compatible object storage** server. It provides the same API as AWS S3 but runs locally.

## 11.2 Why MinIO is Needed

| Requirement | Solution |
|------------|----------|
| Store uploaded files persistently | MinIO stores raw file bytes |
| Decouple file storage from processing | Spark downloads from MinIO, not from the API |
| S3 compatibility | Easy to migrate to AWS S3 in production |
| Local development | No cloud dependency |

## 11.3 How MinIO is Used

```python
class MinIOService:
    def upload_file(self, object_name, file_data, content_type):
        self.client.put_object(
            bucket_name="academic-documents",
            object_name=object_name,
            data=io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        return f"academic-documents/{object_name}"
```

### Object Naming Convention

```
academic-documents/
├── student123/
│   ├── CS101/
│   │   ├── 550e-uuid.pdf
│   │   └── 661f-uuid.pptx
│   └── MATH201/
│       └── 772g-uuid.pdf
└── anonymous/
    └── general/
        └── 883h-uuid.txt
```

Pattern: `{student_id}/{course_id}/{doc_id}{extension}`

⭐ **Interview Tip:** This hierarchical naming convention enables efficient listing of all documents for a specific student/course without a database query.

---

### Summary
- MinIO: self-hosted S3-compatible object storage
- Stores raw files; Spark downloads from MinIO for processing
- Object path: `{student_id}/{course_id}/{doc_id}{ext}`
- Easy migration to AWS S3 in production

### Top 5 Interview Questions
1. *Why MinIO instead of storing files on the local filesystem?*
2. *What does S3-compatible mean?*
3. *How would you migrate from MinIO to AWS S3?*
4. *What is your object naming convention and why?*
5. *How do you handle upload failures?*

### Quick Revision Bullets
- Bucket: `academic-documents`
- SDK: `minio` Python client
- Startup: `ensure_bucket()` creates bucket if not exists
- Upload returns `storage_path` = `{bucket}/{object_name}`
- Spark uses `storage_path` to download file bytes

---

# 12. FastAPI Backend

## 12.1 What is FastAPI?

A modern, high-performance Python web framework based on Starlette and Pydantic. It's async-native and auto-generates OpenAPI documentation.

## 12.2 Why FastAPI?

| Feature | FastAPI | Flask | Django |
|---------|---------|-------|--------|
| Async support | ✅ Native | ❌ Add-on | ❌ Add-on |
| Auto-docs (Swagger) | ✅ Built-in | ❌ Extension | ❌ Extension |
| Type validation | ✅ Pydantic | ❌ Manual | ❌ Serializers |
| Performance | ⚡ Fast | ⚡ Medium | ⚡ Slower |
| Learning curve | Low | Low | Medium |

## 12.3 Key Design Patterns

### Lifespan Hooks (Startup/Shutdown)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    minio_service.ensure_bucket()
    kafka_service.connect()
    qdrant_retrieval_service.ensure_collection()
    yield
    # SHUTDOWN
    kafka_service.close()
```

### Singleton Services

```python
# Module-level singletons — initialized once, reused everywhere
minio_service = MinIOService()          # One MinIO client
kafka_service = KafkaService()          # One Kafka producer
qdrant_retrieval_service = QdrantRetrievalService()  # One Qdrant client
llm_client = LLMClient()               # One LLM client
```

### Pydantic Validation

```python
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    doc_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)

# FastAPI auto-validates: rejects question < 3 chars, top_k > 20, etc.
```

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # Open in dev; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 12.4 API Endpoints

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| `GET` | `/` | Health check | `{"status": "running"}` |
| `GET` | `/health` | Readiness probe | `{"status": "ok"}` |
| `POST` | `/upload` | Upload document | `UploadResponse` |
| `GET` | `/documents` | List all documents | `List[DocumentStatusResponse]` |
| `GET` | `/documents/{id}` | Document status | `DocumentStatusResponse` |
| `POST` | `/ask` | RAG Q&A | `AskResponse` |
| `POST` | `/quiz` | Generate quiz | `QuizResponse` |
| `POST` | `/summarize` | Summarize | `SummarizeResponse` |
| `POST` | `/mindmap` | Mind map | `MindMapResponse` |

## 12.5 Error Handling Strategy

| HTTP Code | When Used | Example |
|-----------|-----------|---------|
| 400 | Invalid input | Bad file type, question too short |
| 404 | Not found | No chunks for quiz/summary |
| 413 | File too large | > 50 MB upload |
| 502 | LLM error | LLM API timeout, invalid JSON response |
| 503 | Service down | Qdrant unreachable |

---

### Summary
- FastAPI: async, auto-docs (Swagger), Pydantic validation
- Lifespan hooks for startup (MinIO, Kafka, Qdrant) and shutdown
- Singleton services: one client per external service
- 9 endpoints covering health, upload, documents, and 4 AI features

### Top 5 Interview Questions
1. *Why FastAPI over Flask or Django?*
2. *What are lifespan hooks and how do you use them?*
3. *How does Pydantic validation work in FastAPI?*
4. *What is your error handling strategy?*
5. *How do you handle CORS?*

### Quick Revision Bullets
- Async framework on Starlette + Pydantic
- Lifespan: startup (ensure_bucket, connect, ensure_collection) → yield → shutdown (close)
- Singleton services: module-level instances
- Auto-docs: `/docs` (Swagger), `/redoc` (ReDoc)
- Validation: Pydantic `Field(min_length=3, ge=1, le=20)`

---

# 13. React Frontend

## 13.1 Overview

React 18 SPA built with Vite, featuring 6 main components:

| Component | Purpose |
|-----------|---------|
| Upload | Drag-and-drop file upload |
| Library | Document list with status tracking |
| Chat (Q&A) | Interactive question-answer interface |
| Quiz | MCQ quiz with answer checking |
| Summary | Formatted summary with key points |
| MindMap | Interactive Mermaid.js visualization |

## 13.2 Vite Dev Server

```javascript
// vite.config.js
export default {
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
};
```

**Why Vite?**
- ⚡ Instant HMR (Hot Module Replacement)
- 10-100x faster than Webpack
- ESM-based dev server (no bundling in dev)

## 13.3 Mermaid.js for Mind Maps

The mind map is rendered client-side using Mermaid.js, but the **syntax is generated server-side**:

```
LLM → JSON tree → Server: json_to_mermaid() → Mermaid syntax → Client: mermaid.render()
```

This is a deliberate design decision: the LLM outputs structured JSON (reliable), and deterministic code converts it to Mermaid syntax (no syntax errors).

---

### Summary
- React 18 + Vite frontend with 6 components
- Vite proxy for API calls (no CORS issues in dev)
- Mermaid.js renders mind maps from server-generated syntax
- No API keys exposed to the browser

### Top 5 Interview Questions
1. *Why Vite over Webpack?*
2. *How do you handle the Mermaid mind map rendering?*
3. *How does the frontend communicate with the backend?*
4. *Why not generate Mermaid syntax directly from the LLM?*
5. *How do you handle loading states for LLM calls?*

### Quick Revision Bullets
- React 18 + Vite (HMR, ESM-native)
- Proxy: `/api/*` → `localhost:8000`
- Mermaid: JSON → server-side conversion → Mermaid syntax → client-side render
- No API keys in browser (all LLM calls via FastAPI)

---

# 14. Docker & Infrastructure

## 14.1 Docker Compose Services

```yaml
services:
  zookeeper:    # Kafka dependency
    image: confluentinc/cp-zookeeper:7.6.0
    ports: ["2181:2181"]

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    ports: ["9092:9092"]
    depends_on: [zookeeper]

  minio:
    image: minio/minio:latest
    ports: ["9000:9000", "9001:9001"]

  qdrant:
    image: qdrant/qdrant:v1.9.1
    ports: ["6333:6333", "6334:6334"]
```

## 14.2 Health Checks

All services have Docker health checks:
- Zookeeper: `nc -z localhost 2181`
- Kafka: `kafka-topics --list`
- MinIO: `curl http://localhost:9000/minio/health/live`
- Qdrant: `curl http://localhost:6333/healthz`

## 14.3 Volumes

```yaml
volumes:
  zookeeper-data:  # Zookeeper state
  kafka-data:      # Kafka message logs
  minio-data:      # Uploaded files
  qdrant-data:     # Vector storage
```

Named volumes persist data across container restarts.

---

# 15. Testing Strategy

## 15.1 Test Suite Overview

| Suite | Tests | What It Tests |
|-------|-------|---------------|
| `backend/tests/test_upload.py` | 14 | Upload, documents, health endpoints |
| `backend/tests/test_ask.py` | 13 | RAG Q&A, citations, error handling |
| `backend/tests/test_generation.py` | 30 | Quiz, summary, mindmap, Mermaid converter |
| `spark/tests/test_pipeline.py` | 26 | Parsers, chunker, embedder, Qdrant writer |
| `tests/test_integration.py` | 16 | E2E flows, failure handling, benchmarks |
| **Total** | **99** | |

## 15.2 Testing Approach

```
Unit Tests (83)                Integration Tests (16)
├── Mock external services     ├── Test full pipeline flows
├── Test each component        ├── Test failure scenarios
│   independently              ├── Performance benchmarks
└── Fast, deterministic        └── More realistic
```

## 15.3 Key Testing Patterns

- **Dependency injection** via FastAPI's `TestClient` with `httpx`
- **Mocking** external services (MinIO, Kafka, Qdrant, LLM)
- **Parametrized tests** for different file types
- **Benchmark tests** measuring latency of each pipeline stage

---

### Summary
- 99 tests: 83 unit + 16 integration
- External services mocked for unit tests
- Integration tests cover end-to-end flows and failure cases
- Benchmark tests measure parse, chunk, embed, upsert latency

### Top 5 Interview Questions
1. *How do you test your RAG pipeline without real LLM calls?*
2. *What is your testing strategy for the Spark pipeline?*
3. *How do you mock external services in your tests?*
4. *What are your benchmark results?*
5. *How would you add a new test for a new feature?*

### Quick Revision Bullets
- 99 total tests across 5 test files
- Mock: MinIO, Kafka, Qdrant, LLM via unittest.mock
- FastAPI TestClient for HTTP endpoint testing
- Benchmarks: PDF parse ~1.8ms, chunk ~25ms, embed varies, full pipeline ~4.3ms
- pytest with `pyproject.toml` testpaths configuration

---

# 16. System Design & Scalability

## 16.1 How Would You Scale This System?

### Horizontal Scaling Plan

```
                    Load Balancer
                    ┌────┴────┐
              ┌─────┤         ├─────┐
              ▼     ▼         ▼     ▼
          FastAPI  FastAPI  FastAPI  FastAPI
          (Pod 1)  (Pod 2)  (Pod 3)  (Pod 4)
              │
              ▼
          Kafka Cluster (3 brokers, 12 partitions)
              │
              ▼
          Spark Cluster (8 executors)
              │
              ▼
          Qdrant Cluster (3 shards, 2 replicas each)
```

| Component | Scaling Strategy |
|-----------|-----------------|
| **FastAPI** | Horizontal: run N replicas behind a load balancer |
| **Kafka** | Add brokers, increase partitions (12+) |
| **Spark** | Add executors, scale dynamically with YARN/K8s |
| **Qdrant** | Sharding (split collection across nodes) + replicas |
| **MinIO** | Erasure coding, distributed mode (4+ nodes) |

## 16.2 Bottleneck Analysis

| Component | Bottleneck | Mitigation |
|-----------|-----------|------------|
| Embedding | CPU-bound model inference | GPU, batch processing, model distillation |
| LLM calls | API rate limits, latency | Caching, multiple providers, request queuing |
| Qdrant search | Large collection size | HNSW tuning (ef, m params), sharding |
| File upload | Network bandwidth | Chunked upload, compression |

## 16.3 Production Improvements

| Current (Dev) | Production |
|---------------|------------|
| `allow_origins=["*"]` | Specific frontend domain only |
| SQLite-like in-memory doc store | PostgreSQL or Redis |
| Single Kafka broker | 3-broker cluster |
| No authentication | JWT/OAuth2 |
| No rate limiting | Token-bucket rate limiter |
| `docker-compose` | Kubernetes |

---

### Summary
- Horizontal scaling: replicate FastAPI, add Spark executors, shard Qdrant
- Main bottlenecks: embedding (CPU), LLM (API limits), Qdrant (data volume)
- Production requires auth, rate limiting, proper CORS, K8s deployment

### Top 5 Interview Questions
1. *How would you scale this for 10,000 concurrent users?*
2. *What are the bottlenecks and how would you address them?*
3. *How would you deploy this to production?*
4. *How would you handle multi-tenancy at scale?*
5. *What monitoring would you add?*

### Quick Revision Bullets
- FastAPI: horizontal replicas behind LB
- Kafka: 3 brokers, 12+ partitions
- Spark: dynamic executors on K8s
- Qdrant: sharding + replicas
- Auth: JWT, rate limiting, proper CORS

---

# 17. Design Decisions & Trade-offs

## 17.1 Key Decisions Table

| Decision | What We Chose | What We Rejected | Why |
|----------|---------------|-------------------|-----|
| Message queue | Kafka | RabbitMQ, Redis | Durable replay, dead-letter support |
| Processing engine | Spark | Celery | mapInPandas for model reuse |
| Vector DB | Qdrant | FAISS, Pinecone | Metadata filtering + self-hosted |
| Embedding model | all-MiniLM-L6-v2 | all-mpnet-base-v2 | 2x smaller, fast enough |
| LLM | Groq (Llama 3.1 70B) | OpenAI GPT-4 | Free tier, fast inference |
| Chunking | Sentence-aware + overlap | Fixed-size | Never breaks mid-sentence |
| Mind map generation | JSON → Mermaid (server) | LLM generates Mermaid directly | Deterministic syntax, no errors |
| API key storage | Server-side .env | Browser localStorage | Security |
| Summarization | Map-reduce | Single-call stuffing | Handles long documents |
| PPTX parsing | python-pptx | Raw XML | Proper run-merging |

## 17.2 Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| PPTX text fragmentation (broken runs) | Use `python-pptx` for proper run-merging |
| LLM producing invalid Mermaid syntax | Extract structured JSON, convert server-side |
| Model reload per Spark row | `_MODEL_CACHE` + `mapInPandas` |
| Long docs exceed LLM context | Map-reduce summarization |
| Silent processing failures | Dead-letter topic (`documents.failed`) |
| API key exposure in browser | Server-side key, never sent to client |

---

# 18. 50 Rapid-Fire Interview Questions

## Architecture & Design

| # | Question | Key Points |
|---|----------|-----------|
| 1 | Walk me through the architecture | Upload → MinIO + Kafka → Spark → Qdrant → RAG |
| 2 | Why decoupled architecture? | Async processing, fault tolerance, scalability |
| 3 | What design patterns did you use? | Strategy (parsers), Singleton (services), Map-Reduce |
| 4 | How do services communicate? | Kafka (async), HTTP/REST (sync) |
| 5 | What happens if Spark is down? | Kafka retains messages; processed when Spark recovers |

## RAG & Retrieval

| # | Question | Key Points |
|---|----------|-----------|
| 6 | What is RAG? | Retrieve context + Augment prompt + Generate answer |
| 7 | RAG vs fine-tuning? | RAG: no retraining, citable. Fine-tuning: deeper adaptation |
| 8 | How do you prevent hallucination? | System prompt constraint, citations, fallback message |
| 9 | What is top-K retrieval? | Retrieve K most similar chunks by cosine similarity |
| 10 | How do you scope retrieval? | Qdrant metadata filtering: doc_id, student_id, course_id |

## Embeddings & Vectors

| # | Question | Key Points |
|---|----------|-----------|
| 11 | What are embeddings? | Dense vector representations of text in continuous space |
| 12 | Why cosine similarity? | Scale-invariant, works well with normalized vectors |
| 13 | Why normalize embeddings? | cos(θ) reduces to dot product, faster computation |
| 14 | Why 384 dimensions? | Sweet spot: 50% storage of 768-dim, ~2-3% quality drop |
| 15 | Same model for both sides? | Yes — different models = misaligned vector spaces |

## Kafka & Streaming

| # | Question | Key Points |
|---|----------|-----------|
| 16 | Why Kafka over RabbitMQ? | Durable log, replay on failure, native Spark connector |
| 17 | What is a dead-letter topic? | Failed messages routed to `documents.failed` for inspection |
| 18 | What does `acks=all` mean? | Wait for all replicas to acknowledge before confirming send |
| 19 | How many partitions? | 3 per topic → up to 3 parallel consumers |
| 20 | What is a consumer group? | Group of consumers sharing a topic; each partition → 1 consumer |

## Spark

| # | Question | Key Points |
|---|----------|-----------|
| 21 | Why Spark over Celery? | mapInPandas for model reuse, native Kafka connector |
| 22 | What is foreachBatch? | Process each micro-batch with custom logic |
| 23 | What is mapInPandas? | Process partitions with Python functions, load model once |
| 24 | What is checkpointing? | Save offset state for exactly-once recovery |
| 25 | Structured Streaming vs batch? | Streaming: continuous processing; batch: scheduled runs |

## Chunking & Parsing

| # | Question | Key Points |
|---|----------|-----------|
| 26 | Why sentence-aware chunking? | Never breaks mid-sentence, better retrieval quality |
| 27 | Why 15% overlap? | Context continuity across chunk boundaries |
| 28 | How do you handle short PPTX slides? | Merge slides < 50 tokens with the next slide |
| 29 | Why PyMuPDF over PyPDF2? | C-based, faster, better text extraction |
| 30 | What is the run-merging problem? | PPTX fragments text into runs; python-pptx merges them |

## LLM & Generation

| # | Question | Key Points |
|---|----------|-----------|
| 31 | How is your LLM provider-agnostic? | OpenAI-compatible API format; swap via config |
| 32 | What is JSON mode? | `response_format={"type":"json_object"}` forces valid JSON |
| 33 | How do you validate LLM output? | Server-side schema validation (quiz: 4 options, A-D) |
| 34 | Why centralize prompts? | Easy to iterate, A/B test, and review |
| 35 | How do you handle LLM failures? | HTTP 502 error, logged, graceful error message to user |

## Vector Database

| # | Question | Key Points |
|---|----------|-----------|
| 36 | Why Qdrant over FAISS? | Metadata filtering, persistence, full database features |
| 37 | What is HNSW? | Hierarchical graph for O(log n) approximate NN search |
| 38 | How do you handle multi-tenancy? | Metadata filter on student_id, course_id |
| 39 | What is batched upsert? | Write 100 points per API call to avoid timeouts |
| 40 | ANN vs exact NN? | ANN: O(log n), ~95% recall. Exact: O(n), 100% recall |

## Frontend & API

| # | Question | Key Points |
|---|----------|-----------|
| 41 | Why FastAPI over Flask? | Async, auto-docs, Pydantic validation |
| 42 | What are lifespan hooks? | Startup/shutdown logic (init MinIO, Kafka, Qdrant) |
| 43 | How do you handle CORS? | Middleware with `allow_origins=["*"]` (dev), restrict in prod |
| 44 | Why Vite over Webpack? | 10-100x faster HMR, ESM-native |
| 45 | How do mind maps work? | LLM → JSON tree → server: json_to_mermaid() → Mermaid.js |

## Testing & Production

| # | Question | Key Points |
|---|----------|-----------|
| 46 | How many tests? | 99 total: 83 unit + 16 integration |
| 47 | How do you mock LLM calls? | `unittest.mock.patch` on `llm_client.chat` |
| 48 | How would you scale to 10K users? | Horizontal FastAPI, Kafka partitions, Spark executors |
| 49 | What monitoring would you add? | Prometheus metrics, ELK logging, Qdrant dashboard |
| 50 | How would you deploy to production? | K8s, secrets manager for keys, PostgreSQL for docs, CDN for frontend |

---

> **Final Interview Tip:** When asked about your project, structure your answer as:
> 1. **What** — "It's a distributed RAG system for academic document intelligence"
> 2. **Why** — "To help students study their own uploaded materials with AI"
> 3. **How** — "Upload → Kafka → Spark → Qdrant → LLM with citations"
> 4. **Challenges** — Pick 1-2 specific technical challenges you solved
> 5. **Impact** — "99 tests, sub-5ms pipeline latency, 4 AI features"

---

*This handbook covers the complete AI Academic Learning Assistant project. Review each section's "Quick Revision Bullets" before your interview for rapid recall. Good luck! 🚀*
