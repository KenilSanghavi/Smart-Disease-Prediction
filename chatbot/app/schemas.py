"""
app/schemas.py
Pydantic models for all FastAPI request and response bodies.
Your Django backend friend uses these as the API contract.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RouteEnum(str, Enum):
    rag      = "rag"
    llm      = "llm"
    web      = "web"
    pdf      = "pdf"
    fallback = "fallback"


# ── Request models ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Request body for POST /chat
    Django sends this when user submits a message.
    """
    session_id : str  = Field(..., description="Unique session ID per user (e.g. user's Django user ID)")
    message    : str  = Field(..., description="User's message in any language")
    pdf_session: Optional[str] = Field(None, description="PDF session ID if user uploaded a PDF")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id" : "user_123",
                "message"    : "What are the symptoms of dengue?",
                "pdf_session": None,
            }
        }


class UploadPDFRequest(BaseModel):
    """Used internally after file upload."""
    session_id: str


# ── Response models ────────────────────────────────────────────

class SourceDocument(BaseModel):
    content  : str
    source   : str
    score    : float


class ChatResponse(BaseModel):
    """
    Response body for POST /chat
    Django receives this and displays it to the user.
    """
    session_id       : str
    message          : str            # original user message
    response         : str            # AI answer in user's language
    detected_language: str            # ISO 639-1 code (e.g. 'en', 'hi')
    route_taken      : RouteEnum      # which source answered: rag/llm/web/fallback
    confidence       : float          # 0.0 to 1.0
    sources          : List[SourceDocument] = []

    class Config:
        json_schema_extra = {
            "example": {
                "session_id"       : "user_123",
                "message"          : "What are the symptoms of dengue?",
                "response"         : "Dengue fever symptoms include high fever, severe headache...",
                "detected_language": "en",
                "route_taken"      : "rag",
                "confidence"       : 0.87,
                "sources"          : [],
            }
        }


class UploadPDFResponse(BaseModel):
    """Response after PDF upload."""
    pdf_session_id: str
    filename      : str
    pages         : int
    message       : str


class MessageItem(BaseModel):
    role   : str   # "user" or "assistant"
    content: str


class HistoryResponse(BaseModel):
    """Response for GET /history/{session_id}"""
    session_id: str
    messages  : List[MessageItem]
    count     : int


class HealthResponse(BaseModel):
    status         : str
    vector_store_ok: bool
    llm_model      : str
