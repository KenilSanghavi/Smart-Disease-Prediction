"""
config.py
Central configuration for the entire chatbot system.
All tunable parameters live here — change once, applies everywhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ── LLM ───────────────────────────────────────────────────────
# Free Groq models: llama-3.1-8b-instant | llama-3.1-70b-versatile | mixtral-8x7b-32768
LLM_MODEL       = "llama-3.1-8b-instant"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS  = 1024

# ── Embeddings (free, runs locally) ───────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")
DOCS_DIR      = os.path.join(BASE_DIR, "docs")
UPLOADS_DIR   = os.path.join(BASE_DIR, "uploads")

# ── ChromaDB Collection ────────────────────────────────────────
CHROMA_COLLECTION = "healthcare_kb"

# ── Chunking ───────────────────────────────────────────────────
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 100

# ── RAG Retrieval ──────────────────────────────────────────────
TOP_K_RETRIEVAL = 6    # docs fetched from vector store
TOP_K_RERANK    = 3    # docs kept after reranking
BM25_WEIGHT     = 0.3  # keyword search weight
SEMANTIC_WEIGHT = 0.7  # semantic search weight
NUM_EXPANSIONS  = 2    # extra query variants to generate

# ── Confidence Thresholds ──────────────────────────────────────
RAG_THRESHOLD = 0.55   # below this → try LLM
LLM_THRESHOLD = 0.50   # below this → try web search
MAX_RETRIES   = 2      # max pipeline retries before fallback

# ── Memory ─────────────────────────────────────────────────────
MAX_HISTORY_TURNS = 10   # how many user+assistant turns to keep per session

# ── FastAPI ────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are a knowledgeable, empathetic healthcare AI assistant.

IMPORTANT: Always respond in ENGLISH only, regardless of the language the user writes in.

Your responsibilities:
- Provide accurate, evidence-based medical information
- Be empathetic and supportive with patients
- Always recommend consulting a qualified doctor for personal diagnosis
- For emergency symptoms (chest pain, difficulty breathing, stroke signs),
  always advise calling emergency services immediately
- Never prescribe specific dosages without clinical context
- Clearly acknowledge when information is uncertain or incomplete

You assist with health information — you do not replace professional medical care.
Always respond in ENGLISH."""

FALLBACK_RESPONSE = (
    "I'm sorry, I wasn't able to find a confident answer to your question. "
    "For accurate medical advice, please consult a qualified healthcare professional. "
    "You can also refer to trusted sources like WHO (who.int) or NIH (nih.gov)."
)

# ── Trusted web domains for search ────────────────────────────
TRUSTED_MEDICAL_DOMAINS = [
    "who.int", "nih.gov", "cdc.gov", "nhs.uk",
    "mayoclinic.org", "webmd.com", "healthline.com",
    "medlineplus.gov", "pubmed.ncbi.nlm.nih.gov",
]
