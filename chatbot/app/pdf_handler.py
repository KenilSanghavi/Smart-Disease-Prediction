"""
app/pdf_handler.py

BUGS FIXED:
  Bug 3+4 — Confidence was always wrong → route always went to web
    OLD: confidence = 1 - avg_distance
         Chroma L2 distances can be > 1.0, making confidence negative or 0
    NEW: confidence = 1 / (1 + avg_distance)
         This maps any positive distance to (0, 1] correctly.
         distance=0    → confidence=1.0  (perfect match)
         distance=0.5  → confidence=0.67
         distance=1.0  → confidence=0.50
         distance=2.0  → confidence=0.33
         Never negative, always in valid range.

  Extra bug — get_all_pdf_text() was called in graph.py but not defined here.
    FIX: Added get_all_pdf_text() function.
"""

import os
import uuid
import tempfile
import logging
from typing import Tuple, Optional

import pdfplumber
# from langchain.schema import Document
# from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import (
    GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
    EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP,
)

logger = logging.getLogger(__name__)

# Registry: {pdf_session_id: {"store": Chroma, "raw_text": str, "metadata": dict}}
_pdf_registry: dict = {}


def extract_pdf_text(pdf_path: str) -> Tuple[str, dict]:
    """Extract text and metadata from a PDF using pdfplumber."""
    full_text = ""
    metadata  = {"pages": 0, "filename": os.path.basename(pdf_path)}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            metadata["pages"] = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                full_text += f"\n[Page {i+1}]\n{text}"
                # Extract tables (common in medical reports)
                for table in page.extract_tables():
                    for row in table:
                        if row:
                            full_text += "\n" + " | ".join(str(c or "") for c in row)
        logger.info(f"Extracted {len(full_text)} chars from {metadata['pages']} pages")
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
    return full_text, metadata


def register_pdf(pdf_path: str) -> dict:
    """
    Process an uploaded PDF, build its vector store, and register it.
    Returns dict with pdf_session_id and metadata.
    """
    text, meta = extract_pdf_text(pdf_path)

    if not text.strip():
        return {
            "success": False,
            "message": "PDF is empty or image-based (scanned PDFs are not supported).",
        }

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    doc    = Document(page_content=text, metadata={"source": meta["filename"]})
    chunks = splitter.split_documents([doc])

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    tmp_dir = tempfile.mkdtemp()
    store   = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=tmp_dir,
        collection_name="user_pdf",
    )

    pdf_session_id = str(uuid.uuid4())
    _pdf_registry[pdf_session_id] = {
        "store"   : store,
        "raw_text": text,
        "metadata": meta,
    }

    logger.info(f"PDF registered: session={pdf_session_id}, chunks={len(chunks)}")
    return {
        "success"       : True,
        "pdf_session_id": pdf_session_id,
        "filename"      : meta["filename"],
        "pages"         : meta["pages"],
        "message"       : f"PDF loaded successfully ({len(chunks)} sections indexed).",
    }


def get_pdf_store(pdf_session_id: str) -> Optional[Chroma]:
    """Retrieve the vector store for a registered PDF session."""
    entry = _pdf_registry.get(pdf_session_id)
    return entry["store"] if entry else None


def get_all_pdf_text(pdf_session_id: str) -> str:
    """
    Return the full raw text of a registered PDF.
    Used by pdf_summary_node (Express Lane) to summarize the whole document.

    BUG FIX: This function was called in graph.py but was missing from this file.
    """
    entry = _pdf_registry.get(pdf_session_id)
    if not entry:
        logger.warning(f"PDF session not found: {pdf_session_id}")
        return ""
    return entry.get("raw_text", "")


def answer_from_pdf(
    question: str,
    pdf_session_id: str,
    k: int = 5,
) -> Tuple[str, float]:
    """
    Answer a question from the user's uploaded PDF.

    BUG 3+4 FIX: Confidence formula corrected.
    Chroma with L2 distance returns scores where lower = more similar.
    The correct way to convert L2 distance to confidence:

        confidence = 1 / (1 + distance)

    This always returns a value in (0, 1]:
        distance=0.0 → confidence=1.0  (perfect match)
        distance=1.0 → confidence=0.5
        distance=2.0 → confidence=0.33
        distance=5.0 → confidence=0.17

    The OLD formula (1 - distance) was WRONG because:
        distance=1.5 → 1 - 1.5 = -0.5 (invalid, treated as 0.0)
        This made ALL PDF queries return confidence≈0 → route always went to web

    Returns: (answer_text, confidence_score)
    """
    store = get_pdf_store(pdf_session_id)
    if not store:
        return "PDF not found. Please upload your document again.", 0.0

    try:
        results = store.similarity_search_with_score(question, k=k)
    except Exception as e:
        logger.error(f"PDF similarity search failed: {e}")
        return "Error searching the document.", 0.0

    if not results:
        return "Couldn't find relevant content in your document.", 0.0

    # BUG FIX: Correct distance-to-confidence conversion
    distances  = [score for _, score in results]
    avg_dist   = sum(distances) / len(distances)
    confidence = 1.0 / (1.0 + avg_dist)   # correct formula — always in (0, 1]
    confidence = round(min(1.0, max(0.0, confidence)), 3)

    logger.info(
        f"PDF search: avg_distance={avg_dist:.3f}, confidence={confidence:.3f}"
    )

    context = "\n\n".join(doc.page_content for doc, _ in results)

    llm    = ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    prompt = PromptTemplate.from_template(
        """You are reviewing a patient's medical document.
Answer the question using ONLY the document content below.
Be precise — reference specific values, dates, test results, or findings when relevant.
If the answer is not clearly present in the document, say: 
"This information is not available in your uploaded document."

Document content:
{context}

Question: {question}

Answer:"""
    )

    try:
        answer = (prompt | llm | StrOutputParser()).invoke({
            "context" : context,
            "question": question,
        })
    except Exception as e:
        logger.error(f"PDF answer generation failed: {e}")
        return "Error generating answer from document.", 0.0

    return answer, confidence