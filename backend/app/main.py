"""
FastAPI application entry point.

Sets up:
  - CORS middleware
  - Structured logging
  - Lifespan hooks (MinIO bucket, Kafka producer + topics)
  - Route registration
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.services.minio_service import minio_service
from backend.app.services.kafka_service import kafka_service
from backend.app.services.qdrant_service import qdrant_retrieval_service
from backend.app.routers import upload, documents, ask, quiz, summarize, mindmap

# ─── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup hooks, yield, then run shutdown hooks."""
    # ── Startup ────────────────────────────────────────────────
    logger.info("Starting AI Academic Learning Assistant API …")

    # Ensure MinIO bucket exists
    try:
        minio_service.ensure_bucket()
    except Exception as exc:
        logger.warning("MinIO not reachable on startup: %s", exc)

    # Connect Kafka producer, create topics, and start background status consumer
    kafka_service.connect()
    kafka_service.create_topics()
    kafka_service.start_consumer()

    # Ensure Qdrant collection exists
    try:
        qdrant_retrieval_service.ensure_collection()
    except Exception as exc:
        logger.warning("Qdrant not reachable on startup: %s", exc)

    logger.info("Startup complete.")
    yield

    # ── Shutdown ───────────────────────────────────────────────
    logger.info("Shutting down …")
    kafka_service.close()
    logger.info("Shutdown complete.")


# ─── Application ──────────────────────────────────────────────
app = FastAPI(
    title="AI Academic Learning Assistant",
    description=(
        "Upload academic documents (PDF, PPTX, notes) and get AI-powered "
        "quizzes, summaries, mind maps, and Q&A — backed by Spark, Kafka, "
        "and a vector database."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ───────────────────────────────────────────────────
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(quiz.router)
app.include_router(summarize.router)
app.include_router(mindmap.router)


@app.get("/", tags=["Health"])
async def root():
    """Health-check / landing endpoint."""
    return {
        "service": "AI Academic Learning Assistant",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Readiness probe for container orchestration."""
    return {"status": "ok"}
