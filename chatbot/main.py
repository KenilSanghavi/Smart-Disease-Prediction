# """
# main.py
# FastAPI application entry point.

# HOW TO RUN:
#     uvicorn main:app --reload --host 0.0.0.0 --port 8000

# SWAGGER DOCS (auto-generated):
#     http://localhost:8000/docs

# Your Django friend calls:
#     POST   http://localhost:8000/chat
#     POST   http://localhost:8000/upload-pdf
#     GET    http://localhost:8000/history/{session_id}
#     DELETE http://localhost:8000/history/{session_id}
#     GET    http://localhost:8000/health
# """

# import os
# import logging
# from contextlib import asynccontextmanager
# from pathlib import Path

# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse

# from config import (
#     CHROMA_DB_DIR, EMBEDDING_MODEL, CHROMA_COLLECTION,
#     API_HOST, API_PORT, GROQ_API_KEY, TAVILY_API_KEY,
#     UPLOADS_DIR,
# )

# logging.basicConfig(
#     level=logging.WARNING,
#     format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
# )
# logger = logging.getLogger(__name__)


# # ── Startup / Shutdown ─────────────────────────────────────────

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Runs on startup — loads vector store and builds the LangGraph pipeline.
#     Everything is attached to app.state so all routes can access them.
#     """
#     print("\n" + "=" * 60)
#     print("  HEALTHCARE AI CHATBOT — Starting up")
#     print("=" * 60)

#     # Validate API keys
#     if not GROQ_API_KEY:
#         print("  ERROR: GROQ_API_KEY not set in .env file")
#         raise RuntimeError("GROQ_API_KEY is required")
#     if not TAVILY_API_KEY:
#         print("  WARNING: TAVILY_API_KEY not set — web search disabled")

#     # Create directories
#     Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

#     # Load ChromaDB vector store
#     vector_store = None
#     if Path(CHROMA_DB_DIR).exists():
#         try:
#             from langchain_community.embeddings import HuggingFaceEmbeddings
#             from langchain_community.vectorstores import Chroma

#             print("  Loading embedding model...")
#             embeddings = HuggingFaceEmbeddings(
#                 model_name=EMBEDDING_MODEL,
#                 model_kwargs={"device": "cpu"},
#                 encode_kwargs={"normalize_embeddings": True},
#             )
#             vector_store = Chroma(
#                 persist_directory=CHROMA_DB_DIR,
#                 embedding_function=embeddings,
#                 collection_name=CHROMA_COLLECTION,
#             )
#             count = vector_store._collection.count()
#             print(f"  Vector store loaded: {count} chunks")
#         except Exception as e:
#             print(f"  WARNING: Vector store load failed: {e}")
#             print("  RAG will be disabled. Run: python app/ingest.py")
#     else:
#         print("  WARNING: No vector store found at", CHROMA_DB_DIR)
#         print("  Add PDFs to docs/ folder and run: python app/ingest.py")

#     # Build LangGraph chatbot pipeline
#     from app.graph import build_graph
#     chatbot = build_graph(vector_store)

#     # Attach to app state
#     app.state.vector_store = vector_store
#     app.state.chatbot      = chatbot

#     print("  Chatbot pipeline ready!")
#     print(f"  API docs: http://{API_HOST}:{API_PORT}/docs")
#     print("=" * 60 + "\n")

#     yield  # app runs here

#     print("\n  Healthcare chatbot shutting down.")


# # ── Create FastAPI app ─────────────────────────────────────────

# app = FastAPI(
#     title       = "Healthcare AI Chatbot API",
#     description = """
# ## Healthcare AI Chatbot

# A production-ready healthcare chatbot powered by LangGraph + RAG + Groq LLM.

# ### Features
# - **Multilingual** — detects and responds in user's language (100+ languages)
# - **RAG** — answers from curated healthcare knowledge base
# - **LLM fallback** — Groq LLaMA for general medical knowledge
# - **Web search fallback** — Tavily search on trusted medical sites
# - **PDF Q&A** — users can upload their medical report and ask questions
# - **Memory** — remembers conversation history per session

# ### For Django integration
# Pass the user's Django session/user ID as `session_id` in every request.
# """,
#     version     = "1.0.0",
#     lifespan    = lifespan,
# )

# # ── CORS ───────────────────────────────────────────────────────
# # Allow your Django server to call this API
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins     = ["*"],  # Change to your Django domain in production
#     allow_credentials = True,
#     allow_methods     = ["*"],
#     allow_headers     = ["*"],
# )


# # ── Register routes ────────────────────────────────────────────

# from app.api import router as chat_router

# # Override the broken duplicate route in api.py with clean implementation
# from fastapi import Request as FastAPIRequest
# from app.schemas import ChatRequest, ChatResponse, SourceDocument, RouteEnum
# from app.translator import preprocess, from_english
# from app.memory import add_turn
# from app.graph import PipelineState
# import logging as _log

# _logger = _log.getLogger("routes")

# @app.post("/chat", response_model=ChatResponse, tags=["Chat"])
# async def chat(body: ChatRequest, request: FastAPIRequest):
#     """Send a message. Returns AI response in user's language with confidence score."""
#     chatbot      = request.app.state.chatbot
#     vector_store = request.app.state.vector_store

#     if not body.message.strip():
#         return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

#     lang_data = preprocess(body.message)

#     state: PipelineState = {
#         "session_id"     : body.session_id,
#         "original_query" : body.message,
#         "english_query"  : lang_data["english_text"],
#         "detected_lang"  : lang_data["detected_lang"],
#         "query_type"     : "general",
#         "pdf_session_id" : body.pdf_session,
#         "rag_answer"     : "",
#         "rag_confidence" : 0.0,
#         "rag_sources"    : [],
#         "llm_answer"     : "",
#         "llm_confidence" : 0.0,
#         "web_answer"     : "",
#         "web_confidence" : 0.0,
#         "final_answer"   : "",
#         "route_taken"    : "",
#         "retry_count"    : 0,
#         "vector_store"   : vector_store,
#     }

#     try:
#         final_state = chatbot.invoke(state)
#     except Exception as e:
#         _logger.error(f"Pipeline error: {e}")
#         return JSONResponse(status_code=500, content={"detail": "Pipeline error. Please try again."})

#     english_answer = final_state.get("final_answer", "")
#     route          = final_state.get("route_taken", "fallback")
#     confidence     = max(
#         final_state.get("rag_confidence", 0.0),
#         final_state.get("llm_confidence", 0.0),
#         final_state.get("web_confidence", 0.0),
#     )

#     translated = from_english(english_answer, lang_data["detected_lang"])
#     add_turn(body.session_id, body.message, translated)

#     sources = [
#         SourceDocument(
#             content=d.get("content", "")[:200],
#             source=d.get("metadata", {}).get("source", "knowledge_base"),
#             score=round(d.get("hybrid_score", 0.0), 3),
#         )
#         for d in final_state.get("rag_sources", [])[:3]
#     ]

#     route_enum = RouteEnum(route) if route in [e.value for e in RouteEnum] else RouteEnum.fallback

#     return ChatResponse(
#         session_id        = body.session_id,
#         message           = body.message,
#         response          = translated,
#         detected_language = lang_data["detected_lang"],
#         route_taken       = route_enum,
#         confidence        = round(confidence, 3),
#         sources           = sources,
#     )


# # Register remaining routes from api.py (upload-pdf, history, health)
# from fastapi import UploadFile, File, Form
# from app.schemas import UploadPDFResponse, HistoryResponse, MessageItem, HealthResponse
# from app.pdf_handler import register_pdf
# from app.memory import get_history_as_dicts, clear_history
# from pathlib import Path as _Path
# import shutil
# from fastapi.responses import JSONResponse as _JSON

# @app.post("/upload-pdf", response_model=UploadPDFResponse, tags=["PDF"])
# async def upload_pdf(file: UploadFile = File(...), session_id: str = Form(...)):
#     """Upload a medical report PDF. Returns pdf_session_id for use in /chat."""
#     if not file.filename.lower().endswith(".pdf"):
#         return JSONResponse(status_code=400, content={"detail": "Only PDF files accepted."})
#     _Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
#     save_path = os.path.join(UPLOADS_DIR, f"{session_id}_{file.filename}")
#     with open(save_path, "wb") as f:
#         shutil.copyfileobj(file.file, f)
#     result = register_pdf(save_path)
#     if not result["success"]:
#         return JSONResponse(status_code=422, content={"detail": result["message"]})
#     return UploadPDFResponse(
#         pdf_session_id=result["pdf_session_id"],
#         filename=result["filename"],
#         pages=result["pages"],
#         message=result["message"],
#     )

# @app.get("/history/{session_id}", response_model=HistoryResponse, tags=["Memory"])
# async def get_history(session_id: str):
#     """Get conversation history for a session."""
#     history = get_history_as_dicts(session_id)
#     return HistoryResponse(
#         session_id=session_id,
#         messages=[MessageItem(role=m["role"], content=m["content"]) for m in history],
#         count=len(history),
#     )

# @app.delete("/history/{session_id}", tags=["Memory"])
# async def delete_history(session_id: str):
#     """Clear conversation history for a session (e.g. on logout)."""
#     clear_history(session_id)
#     return {"message": f"History cleared for session {session_id}"}

# @app.get("/health", response_model=HealthResponse, tags=["System"])
# async def health_check(request: FastAPIRequest):
#     """Health check — call this to verify the service is running."""
#     vs_ok = False
#     try:
#         vs_ok = request.app.state.vector_store._collection.count() > 0
#     except Exception:
#         vs_ok = False
#     return HealthResponse(status="ok", vector_store_ok=vs_ok, llm_model=LLM_MODEL)


# # ── Run directly ───────────────────────────────────────────────

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)








"""
main.py
FastAPI application entry point.

HOW TO RUN:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

# import os
# import logging
# import shutil
# from contextlib import asynccontextmanager
# from pathlib import Path

# from fastapi import FastAPI, Request as FastAPIRequest, UploadFile, File, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse

# from config import (
#     CHROMA_DB_DIR, EMBEDDING_MODEL, CHROMA_COLLECTION,
#     API_HOST, API_PORT, GROQ_API_KEY, TAVILY_API_KEY,
#     UPLOADS_DIR, LLM_MODEL
# )
# from app.schemas import (
#     ChatRequest, ChatResponse, SourceDocument, RouteEnum, 
#     UploadPDFResponse, HistoryResponse, MessageItem, HealthResponse
# )
# from app.translator import preprocess, from_english
# from app.memory import add_turn, get_history_as_dicts, clear_history
# from app.pdf_handler import register_pdf
# from app.graph import PipelineState, build_graph

# logging.basicConfig(
#     level=logging.WARNING,
#     format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
# )
# logger = logging.getLogger(__name__)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     if not GROQ_API_KEY:
#         raise RuntimeError("GROQ_API_KEY is required in .env")
        
#     Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

#     vector_store = None
#     if Path(CHROMA_DB_DIR).exists():
#         try:
#             from langchain_community.embeddings import HuggingFaceEmbeddings
#             from langchain_community.vectorstores import Chroma

#             embeddings = HuggingFaceEmbeddings(
#                 model_name=EMBEDDING_MODEL,
#                 model_kwargs={"device": "cpu"},
#                 encode_kwargs={"normalize_embeddings": True},
#             )
#             vector_store = Chroma(
#                 persist_directory=CHROMA_DB_DIR,
#                 embedding_function=embeddings,
#                 collection_name=CHROMA_COLLECTION,
#             )
#         except Exception as e:
#             logger.error(f"Vector store load failed: {e}")

#     chatbot = build_graph(vector_store)

#     app.state.vector_store = vector_store
#     app.state.chatbot      = chatbot

#     yield

# app = FastAPI(
#     title="Healthcare AI Chatbot API",
#     version="1.0.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.post("/chat", response_model=ChatResponse, tags=["Chat"])
# async def chat(body: ChatRequest, request: FastAPIRequest):
#     chatbot = request.app.state.chatbot
#     vector_store = request.app.state.vector_store

#     if not body.message.strip():
#         return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

#     lang_data = preprocess(body.message)

#     state: PipelineState = {
#         "session_id"     : body.session_id,
#         "original_query" : body.message,
#         "english_query"  : lang_data["english_text"],
#         "detected_lang"  : lang_data["detected_lang"],
#         "query_type"     : "general",
#         "pdf_session_id" : body.pdf_session,
#         "rag_answer"     : "",
#         "rag_confidence" : 0.0,
#         "rag_sources"    : [],
#         "llm_answer"     : "",
#         "llm_confidence" : 0.0,
#         "web_answer"     : "",
#         "web_confidence" : 0.0,
#         "final_answer"   : "",
#         "route_taken"    : "",
#         "retry_count"    : 0,
#         "vector_store"   : vector_store,
#     }

#     try:
#         final_state = chatbot.invoke(state)
#     except Exception as e:
#         logger.error(f"Pipeline error: {e}")
#         return JSONResponse(status_code=500, content={"detail": "Pipeline error."})

#     english_answer = final_state.get("final_answer", "")
#     route          = final_state.get("route_taken", "fallback")
#     confidence     = max(
#         final_state.get("rag_confidence", 0.0),
#         final_state.get("llm_confidence", 0.0),
#         final_state.get("web_confidence", 0.0),
#     )

#     translated = from_english(english_answer, lang_data["detected_lang"])
#     add_turn(body.session_id, body.message, translated)

#     sources = [
#         SourceDocument(
#             content=d.get("content", "")[:200],
#             source=d.get("metadata", {}).get("source", "knowledge_base"),
#             score=round(d.get("hybrid_score", 0.0), 3),
#         )
#         for d in final_state.get("rag_sources", [])[:3]
#     ]

#     route_enum = RouteEnum(route) if route in [e.value for e in RouteEnum] else RouteEnum.fallback

#     return ChatResponse(
#         session_id=body.session_id,
#         message=body.message,
#         response=translated,
#         detected_language=lang_data["detected_lang"],
#         route_taken=route_enum,
#         confidence=round(confidence, 3),
#         sources=sources,
#     )

# @app.post("/upload-pdf", response_model=UploadPDFResponse, tags=["PDF"])
# async def upload_pdf(file: UploadFile = File(...), session_id: str = Form(...)):
#     if not file.filename.lower().endswith(".pdf"):
#         return JSONResponse(status_code=400, content={"detail": "Only PDF files accepted."})
#     Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
#     save_path = os.path.join(UPLOADS_DIR, f"{session_id}_{file.filename}")
#     with open(save_path, "wb") as f:
#         shutil.copyfileobj(file.file, f)
#     result = register_pdf(save_path)
#     if not result["success"]:
#         return JSONResponse(status_code=422, content={"detail": result["message"]})
#     return UploadPDFResponse(
#         pdf_session_id=result["pdf_session_id"],
#         filename=result["filename"],
#         pages=result["pages"],
#         message=result["message"],
#     )

# @app.get("/history/{session_id}", response_model=HistoryResponse, tags=["Memory"])
# async def get_history(session_id: str):
#     history = get_history_as_dicts(session_id)
#     return HistoryResponse(
#         session_id=session_id,
#         messages=[MessageItem(role=m["role"], content=m["content"]) for m in history],
#         count=len(history),
#     )

# @app.delete("/history/{session_id}", tags=["Memory"])
# async def delete_history(session_id: str):
#     clear_history(session_id)
#     return {"message": f"History cleared for session {session_id}"}

# @app.get("/health", response_model=HealthResponse, tags=["System"])
# async def health_check(request: FastAPIRequest):
#     vs_ok = False
#     try:
#         vs_ok = request.app.state.vector_store._collection.count() > 0
#     except Exception:
#         pass
#     return HealthResponse(status="ok", vector_store_ok=vs_ok, llm_model=LLM_MODEL)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)









"""
main.py
FastAPI application entry point.
"""

import os
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request as FastAPIRequest, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import (
    CHROMA_DB_DIR, EMBEDDING_MODEL, CHROMA_COLLECTION,
    API_HOST, API_PORT, GROQ_API_KEY, TAVILY_API_KEY,
    UPLOADS_DIR, LLM_MODEL
)
from app.schemas import (
    ChatRequest, ChatResponse, SourceDocument, RouteEnum, 
    UploadPDFResponse, HistoryResponse, MessageItem, HealthResponse
)
from app.translator import preprocess, from_english
from app.memory import add_turn, get_history_as_dicts, clear_history
from app.pdf_handler import register_pdf
from app.graph import PipelineState, build_graph

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required in .env")
        
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

    vector_store = None
    if Path(CHROMA_DB_DIR).exists():
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma

            embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            vector_store = Chroma(
                persist_directory=CHROMA_DB_DIR,
                embedding_function=embeddings,
                collection_name=CHROMA_COLLECTION,
            )
        except Exception as e:
            logger.error(f"Vector store load failed: {e}")

    chatbot = build_graph(vector_store)

    app.state.vector_store = vector_store
    app.state.chatbot      = chatbot

    yield

app = FastAPI(
    title="Healthcare AI Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(body: ChatRequest, request: FastAPIRequest):
    chatbot = request.app.state.chatbot
    vector_store = request.app.state.vector_store

    if not body.message.strip():
        return JSONResponse(status_code=400, content={"detail": "Message cannot be empty."})

    lang_data = preprocess(body.message)

    state: PipelineState = {
        "session_id"     : body.session_id,
        "original_query" : body.message,
        "english_query"  : lang_data["english_text"],
        "detected_lang"  : lang_data["detected_lang"],
        "query_type"     : "general",
        "pdf_session_id" : body.pdf_session,
        "rag_answer"     : "",
        "rag_confidence" : 0.0,
        "rag_sources"    : [],
        "llm_answer"     : "",
        "llm_confidence" : 0.0,
        "web_answer"     : "",
        "web_confidence" : 0.0,
        "final_answer"   : "",
        "route_taken"    : "",
        "retry_count"    : 0,
        "vector_store"   : vector_store,
    }

    try:
        final_state = chatbot.invoke(state)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Pipeline error."})

    english_answer = final_state.get("final_answer", "")
    route          = final_state.get("route_taken", "fallback")
    confidence     = max(
        final_state.get("rag_confidence", 0.0),
        final_state.get("llm_confidence", 0.0),
        final_state.get("web_confidence", 0.0),
    )

    translated = from_english(english_answer, lang_data["detected_lang"])
    add_turn(body.session_id, body.message, translated)

    sources = [
        SourceDocument(
            content=d.get("content", "")[:200],
            source=d.get("metadata", {}).get("source", "knowledge_base"),
            score=round(d.get("hybrid_score", 0.0), 3),
        )
        for d in final_state.get("rag_sources", [])[:3]
    ]

    route_enum = RouteEnum(route) if route in [e.value for e in RouteEnum] else RouteEnum.fallback

    return ChatResponse(
        session_id=body.session_id,
        message=body.message,
        response=translated,
        detected_language=lang_data["detected_lang"],
        route_taken=route_enum,
        confidence=round(confidence, 3),
        sources=sources,
    )

@app.post("/upload-pdf", response_model=UploadPDFResponse, tags=["PDF"])
async def upload_pdf(file: UploadFile = File(...), session_id: str = Form(...)):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(status_code=400, content={"detail": "Only PDF files accepted."})
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
    save_path = os.path.join(UPLOADS_DIR, f"{session_id}_{file.filename}")
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = register_pdf(save_path)
    if not result["success"]:
        return JSONResponse(status_code=422, content={"detail": result["message"]})
    return UploadPDFResponse(
        pdf_session_id=result["pdf_session_id"],
        filename=result["filename"],
        pages=result["pages"],
        message=result["message"],
    )

@app.get("/history/{session_id}", response_model=HistoryResponse, tags=["Memory"])
async def get_history(session_id: str):
    history = get_history_as_dicts(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[MessageItem(role=m["role"], content=m["content"]) for m in history],
        count=len(history),
    )

@app.delete("/history/{session_id}", tags=["Memory"])
async def delete_history(session_id: str):
    clear_history(session_id)
    return {"message": f"History cleared for session {session_id}"}

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: FastAPIRequest):
    vs_ok = False
    try:
        vs_ok = request.app.state.vector_store._collection.count() > 0
    except Exception:
        pass
    return HealthResponse(status="ok", vector_store_ok=vs_ok, llm_model=LLM_MODEL)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)