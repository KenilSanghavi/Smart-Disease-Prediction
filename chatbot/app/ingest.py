"""
app/ingest.py
Run this ONCE to build the ChromaDB vector store from your healthcare PDFs.
Place your PDF files in the docs/ folder, then run:
    python app/ingest.py
"""

import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from config import (
    DOCS_DIR, CHROMA_DB_DIR, EMBEDDING_MODEL,
    CHUNK_SIZE, CHUNK_OVERLAP, CHROMA_COLLECTION
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_pdfs(docs_path: str) -> list:
    path = Path(docs_path)
    path.mkdir(parents=True, exist_ok=True)

    pdf_files = list(path.glob("**/*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {docs_path}")
        logger.warning("Add healthcare PDF documents to the docs/ folder and run again.")
        return []

    logger.info(f"Found {len(pdf_files)} PDFs: {[f.name for f in pdf_files]}")
    loader = DirectoryLoader(docs_path, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True)
    docs   = loader.load()
    logger.info(f"Loaded {len(docs)} pages")
    return docs


def split_docs(documents: list) -> list:
    if not documents:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, c in enumerate(chunks):
        c.metadata["chunk_id"] = i
    logger.info(f"Created {len(chunks)} chunks")
    return chunks


def build_store(chunks: list) -> Chroma:
    if not chunks:
        return None

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    logger.info("Building ChromaDB vector store...")
    store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR,
        collection_name=CHROMA_COLLECTION,
    )
    logger.info(f"Stored {store._collection.count()} vectors in {CHROMA_DB_DIR}")
    return store


def main():
    print("\n" + "=" * 55)
    print("  HEALTHCARE CHATBOT — VECTOR STORE BUILDER")
    print("=" * 55)
    docs   = load_pdfs(DOCS_DIR)
    if not docs:
        return
    chunks = split_docs(docs)
    store  = build_store(chunks)
    if store:
        print(f"\n  Done! Vector store ready at: {CHROMA_DB_DIR}")
        print(f"  Total chunks: {len(chunks)}")
        print("\n  Now run: uvicorn main:app --reload")
    print("=" * 55)


if __name__ == "__main__":
    main()
