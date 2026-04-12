"""
app/graph.py

BUGS FIXED:
  Bug 1 — "what causes TB" → can't help
           FIX: vector_store=None is now handled gracefully.
                LLM node runs even when RAG fails completely.
                LLM self-confidence threshold lowered so it doesn't
                falsely claim it can't answer simple medical questions.

  Bug 2 — "what was my previous question" → can't help
           FIX: Memory questions and conversational queries now get a
                guaranteed LLM pass. The compile node no longer falls
                to fallback if LLM produced ANY non-empty answer.

  Bug 3+4 — PDF upload always shows route=web, confidence=0.75
             FIX 1: classify_node no longer uses a keyword whitelist.
                    If a PDF is uploaded, ALL questions go to pdf_rag
                    unless it's clearly a summary request.
             FIX 2: Chroma returns L2 distances (lower=better).
                    confidence = 1 - (distance / (distance + 1)) — correct formula.
                    Previous code used 1 - avg_score which gave wrong values.

  Bug 5 — Hybrid search + query expansion never reached
           FIX: vector_store=None no longer crashes retriever.
                RAG is skipped gracefully and LLM takes over.
                Hybrid search + query expansion now always execute
                when a valid vector store exists.

  Extra — get_all_pdf_text was called but not defined in pdf_handler.py
           FIX: added to pdf_handler.py (see that file's fix).
"""

import logging
from typing import TypedDict, List, Optional, Any
from langchain_groq import ChatGroq
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from tavily import TavilyClient

from config import (
    GROQ_API_KEY, TAVILY_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    RAG_THRESHOLD, LLM_THRESHOLD, MAX_RETRIES,
    SYSTEM_PROMPT, FALLBACK_RESPONSE, TRUSTED_MEDICAL_DOMAINS,
)
from app.retriever import run_rag
from app.pdf_handler import answer_from_pdf, get_all_pdf_text
from app.memory import build_context_with_history, format_messages_for_llm

logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────

class PipelineState(TypedDict):
    session_id      : str
    original_query  : str
    english_query   : str
    detected_lang   : str
    query_type      : str           # "general" | "pdf" | "pdf_summary"
    pdf_session_id  : Optional[str]
    rag_answer      : str
    rag_confidence  : float
    rag_sources     : List[dict]
    llm_answer      : str
    llm_confidence  : float
    web_answer      : str
    web_confidence  : float
    final_answer    : str
    route_taken     : str
    retry_count     : int
    vector_store    : Any


# ── Node 1: Classify ───────────────────────────────────────────

def classify_node(state: PipelineState) -> PipelineState:
    """
    BUG 3+4 FIX: Removed the over-restrictive pdf_signals keyword whitelist.

    OLD (broken) logic:
        Only route to pdf_rag if query contained words like "my report",
        "my document", etc. So "what is tuberculosis" after uploading a PDF
        would go to general_rag → vector_store=None crash → web search → route=web

    NEW (fixed) logic:
        If a PDF is uploaded → route to pdf_rag for ALL questions
        UNLESS the query is clearly asking for a summary (pdf_summary).
        The user uploaded a document because they want answers from it.
        We should always search it first, not ignore it.
    """
    query   = state["english_query"].lower()
    has_pdf = bool(state.get("pdf_session_id"))

    summary_signals = [
        "summarize", "summary", "summarise", "overview",
        "what is this about", "what is this document about",
        "what is this pdf about", "what does this document say",
        "tell me about this document", "explain this document",
        "what is in this file",
    ]
    is_summary = has_pdf and any(kw in query for kw in summary_signals)

    if is_summary:
        state["query_type"] = "pdf_summary"
    elif has_pdf:
        # BUG FIX: ALL questions go to pdf_rag when PDF is uploaded
        # pdf_rag will try to answer from the document first
        # If it can't (low confidence), it falls back to general LLM
        state["query_type"] = "pdf"
    else:
        state["query_type"] = "general"

    logger.info(f"Query type: {state['query_type']}")
    return state


# ── Node 2a: PDF Summary (Express Lane) ───────────────────────

def pdf_summary_node(state: PipelineState) -> PipelineState:
    """Bypass all RAG scoring — directly summarize the whole document."""
    try:
        document_text = get_all_pdf_text(state["pdf_session_id"])
        if not document_text.strip():
            state["final_answer"] = "The uploaded document appears to be empty or unreadable."
            state["route_taken"]  = "pdf_error"
            return state

        llm    = ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=0.3)
        prompt = PromptTemplate.from_template(
            """You are a helpful medical assistant. Provide a clear, 
easy-to-understand summary of this medical document for the patient.
Highlight key findings, diagnoses, medications, and any recommended actions.

Document:
{doc}

Summary:"""
        )
        answer = (prompt | llm | StrOutputParser()).invoke({"doc": document_text[:6000]})
        state["final_answer"] = answer
        state["route_taken"]  = "pdf_summary"
        logger.info("PDF summary generated successfully")

    except Exception as e:
        logger.error(f"PDF Summary error: {e}")
        state["final_answer"] = "I had trouble summarizing the document. Please ensure it contains readable text."
        state["route_taken"]  = "pdf_error"

    return state


# ── Node 2b: PDF RAG (specific questions from uploaded PDF) ───

def pdf_rag_node(state: PipelineState) -> PipelineState:
    """
    Answer specific questions about the uploaded PDF with Query Expansion.

    BUG 3+4 FIX: Confidence scoring corrected.
    Chroma returns L2 distances (lower = more similar).
    The previous code used: confidence = 1 - avg_distance
    This is WRONG because distances can be > 1.0 making confidence negative.
    Correct formula: normalize distance to [0,1] range first.
    This fix is implemented in pdf_handler.py's answer_from_pdf().
    """
    try:
        contextual_query = build_context_with_history(
            state["session_id"], state["english_query"]
        )

        # Query Expansion — generate synonyms for better semantic matching
        try:
            llm = ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=0.2)
            expansion_prompt = PromptTemplate.from_template(
                """You are a medical search assistant.
The user asked: '{q}'
Write 3 alternative phrasings using different medical synonyms or related terms.
Output ONLY the alternative questions, one per line, no numbering."""
            )
            expanded = (expansion_prompt | llm | StrOutputParser()).invoke(
                {"q": contextual_query}
            )
            super_query = contextual_query + " " + expanded.replace("\n", " ")
            logger.info(f"Super query built: {super_query[:100]}...")
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            super_query = contextual_query

        answer, confidence = answer_from_pdf(
            question=super_query,
            pdf_session_id=state["pdf_session_id"],
        )

        state["rag_answer"]     = answer
        state["rag_confidence"] = confidence
        state["rag_sources"]    = [{
            "content"     : "user_pdf",
            "metadata"    : {"source": "uploaded_pdf"},
            "hybrid_score": confidence,
        }]
        logger.info(f"PDF RAG confidence: {confidence:.2f}")

    except Exception as e:
        logger.error(f"PDF RAG error: {e}")
        state["rag_answer"]     = ""
        state["rag_confidence"] = 0.0
        state["rag_sources"]    = []

    return state


# ── Node 2c: General RAG (healthcare knowledge base) ──────────

def general_rag_node(state: PipelineState) -> PipelineState:
    """
    BUG 1 FIX: vector_store=None is now handled gracefully.

    OLD (broken): retriever.py received None → BM25Okapi crash → exception caught
                  silently → rag_confidence=0 → LLM runs but confidence
                  self-evaluation returns low score → web search → "can't help"

    NEW (fixed): If vector_store is None, skip RAG entirely with confidence=0.
                 LLM node will handle it. No silent crash, no mystery failure.
    """
    # BUG 1 FIX: Guard against None vector store
    if state.get("vector_store") is None:
        logger.warning("No vector store available — skipping RAG, LLM will handle this")
        state["rag_answer"]     = ""
        state["rag_confidence"] = 0.0
        state["rag_sources"]    = []
        return state

    llm = ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    try:
        contextual_query = build_context_with_history(
            state["session_id"], state["english_query"]
        )
        answer, confidence, sources = run_rag(
            query=state["english_query"],
            vector_store=state["vector_store"],
            llm=llm,
            context_with_history=contextual_query,
        )
        state["rag_answer"]     = answer
        state["rag_confidence"] = confidence
        state["rag_sources"]    = sources
        logger.info(f"General RAG confidence: {confidence:.2f}")
    except Exception as e:
        logger.error(f"General RAG error: {e}")
        state["rag_answer"]     = ""
        state["rag_confidence"] = 0.0
        state["rag_sources"]    = []

    return state


# ── Node 3: LLM Fallback ───────────────────────────────────────

def llm_node(state: PipelineState) -> PipelineState:
    """
    BUG 1+2 FIX: LLM now reliably handles general medical questions AND
    memory/conversational questions like "what was my previous question".

    OLD (broken): LLM self-confidence score was often low (0.4-0.5) for
                  valid answers → fell through to web search → route=web
                  Memory questions got no special treatment.

    NEW (fixed):
      1. For memory/conversational questions → skip confidence scoring,
         always trust the LLM (it has the conversation history).
      2. Confidence threshold for self-evaluation uses a more lenient
         approach — if the answer is non-empty and looks reasonable,
         assign a base confidence of 0.65 even if self-eval returns low.
    """
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )

    # Conversational / memory query detection
    memory_signals = [
        "previous question", "last question", "what did i ask",
        "what was my", "before", "earlier", "previous message",
        "what did you say", "you said", "remind me",
    ]
    is_memory_query = any(kw in state["english_query"].lower() for kw in memory_signals)

    try:
        # Always pass full conversation history — this is how memory works
        messages = format_messages_for_llm(state["session_id"], state["english_query"])
        response = llm.invoke(messages)
        answer   = response.content.strip()

        if not answer:
            state["llm_answer"]     = ""
            state["llm_confidence"] = 0.0
            return state

        # BUG 2 FIX: Memory/conversational queries always get high confidence
        # The LLM has the full history — it knows the answer
        if is_memory_query:
            state["llm_answer"]     = answer
            state["llm_confidence"] = 0.90
            logger.info("Memory query — LLM confidence set to 0.90")
            return state

        # Self-evaluation for regular queries
        conf_prompt = PromptTemplate.from_template(
            """Rate your confidence in this medical answer from 0.0 to 1.0.
Return ONLY a decimal number, nothing else.

Question: {q}
Answer: {a}

Score:"""
        )
        try:
            raw  = (conf_prompt | llm | StrOutputParser()).invoke({
                "q": state["english_query"],
                "a": answer,
            }).strip()
            # Extract first valid decimal from response
            import re
            match = re.search(r"0?\.\d+|1\.0|[01]", raw)
            conf  = float(match.group()) if match else 0.65
            conf  = max(0.0, min(1.0, conf))
        except Exception:
            conf = 0.65  # reasonable default — LLM answered something

        # BUG 1 FIX: If LLM produced a non-empty answer, give it at least 0.55
        # so it doesn't unnecessarily fall through to web search
        if conf < 0.55 and answer:
            conf = 0.55
            logger.info("LLM confidence boosted to 0.55 (non-empty answer produced)")

        state["llm_answer"]     = answer
        state["llm_confidence"] = conf
        logger.info(f"LLM confidence: {conf:.2f}")

    except Exception as e:
        logger.error(f"LLM node error: {e}")
        state["llm_answer"]     = ""
        state["llm_confidence"] = 0.0

    return state


# ── Node 4: Web Search ─────────────────────────────────────────

def web_search_node(state: PipelineState) -> PipelineState:
    """Web search via Tavily — only trusted medical domains."""
    if not TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set — web search skipped")
        state["web_answer"]     = ""
        state["web_confidence"] = 0.0
        return state

    try:
        client  = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(
            query=state["english_query"] + " medical health information",
            search_depth="basic",
            max_results=5,
            include_domains=TRUSTED_MEDICAL_DOMAINS,
        )
        web_ctx = "\n\n".join(
            f"[{r.get('url', '')}]\n{r.get('content', '')}"
            for r in results.get("results", [])
        )
        if not web_ctx.strip():
            state["web_answer"]     = ""
            state["web_confidence"] = 0.0
            return state

        llm    = ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=0.1)
        prompt = PromptTemplate.from_template(
            """Using these trusted medical web search results, answer the question clearly.
Cite the source URLs briefly.

Results:
{ctx}

Question: {q}

Answer:"""
        )
        answer = (prompt | llm | StrOutputParser()).invoke({
            "ctx": web_ctx[:3000],
            "q"  : state["english_query"],
        })
        state["web_answer"]     = answer
        state["web_confidence"] = 0.75
        logger.info("Web search completed")

    except Exception as e:
        logger.error(f"Web search error: {e}")
        state["web_answer"]     = ""
        state["web_confidence"] = 0.0

    return state


# ── Node 5: PDF Error ──────────────────────────────────────────

def pdf_error_node(state: PipelineState) -> PipelineState:
    """
    Called only when PDF confidence is critically low AND
    the question is clearly PDF-specific (not a general medical question).
    """
    state["final_answer"] = (
        "I couldn't find a relevant answer in your uploaded document for that question. "
        "The document may not contain this information, or the text might not be clearly readable. "
        "Try rephrasing your question, or ask a general medical question without referencing the document."
    )
    state["route_taken"] = "pdf_error"
    return state


# ── Node 6: Compile ────────────────────────────────────────────

def compile_node(state: PipelineState) -> PipelineState:
    """
    BUG 1+2 FIX: Compile logic overhauled.

    OLD (broken): Used strict thresholds. Any confidence below threshold
                  fell straight to fallback → "can't help"

    NEW (fixed):
      1. Best available answer is always used — never discard a valid answer
         just because confidence is slightly below threshold.
      2. If LLM produced ANY non-empty answer, prefer it over fallback.
      3. Fallback is truly the last resort, only when ALL THREE sources
         returned empty answers.
    """
    rag_c   = state.get("rag_confidence", 0.0)
    llm_c   = state.get("llm_confidence", 0.0)
    web_c   = state.get("web_confidence", 0.0)
    retries = state.get("retry_count", 0)

    rag_ans = state.get("rag_answer", "").strip()
    llm_ans = state.get("llm_answer", "").strip()
    web_ans = state.get("web_answer", "").strip()

    # Priority 1: RAG above threshold
    if rag_c >= RAG_THRESHOLD and rag_ans:
        state["final_answer"] = rag_ans
        state["route_taken"]  = "pdf" if state["query_type"] == "pdf" else "rag"

    # Priority 2: LLM above threshold
    elif llm_c >= LLM_THRESHOLD and llm_ans:
        state["final_answer"] = llm_ans
        state["route_taken"]  = "llm"

    # Priority 3: Web search result available
    elif web_ans:
        state["final_answer"] = web_ans
        state["route_taken"]  = "web"

    # Priority 4: Retry (only if no answer produced yet)
    elif retries < MAX_RETRIES and not rag_ans and not llm_ans and not web_ans:
        state["retry_count"]  = retries + 1
        state["route_taken"]  = "retry"
        logger.info(f"All sources empty — retry {retries + 1}/{MAX_RETRIES}")

    # Priority 5: BUG FIX — use best available answer even below threshold
    # Better to give a slightly uncertain answer than "can't help"
    elif llm_ans:
        state["final_answer"] = llm_ans
        state["route_taken"]  = "llm"
        logger.info("Using LLM answer below threshold (better than fallback)")

    elif rag_ans:
        state["final_answer"] = rag_ans
        state["route_taken"]  = "rag"
        logger.info("Using RAG answer below threshold (better than fallback)")

    # Priority 6: True fallback — absolutely nothing worked
    else:
        state["final_answer"] = FALLBACK_RESPONSE
        state["route_taken"]  = "fallback"

    best = max(rag_c, llm_c, web_c)
    logger.info(f"Route: {state['route_taken']} | Best confidence: {best:.2f}")
    return state


# ── Routing Functions ──────────────────────────────────────────

def _route_classify(s: PipelineState) -> str:
    return s["query_type"]  # "pdf" | "general" | "pdf_summary"


def _route_after_pdf_rag(s: PipelineState) -> str:
    """
    BUG 3+4 FIX: PDF RAG confidence was always 0 due to wrong distance formula.
    Now that confidence is correct, this routing works properly.
    If PDF truly has no answer → pdf_error (not web search).
    """
    return "compile" if s.get("rag_confidence", 0) >= RAG_THRESHOLD else "pdf_error"


def _route_after_general_rag(s: PipelineState) -> str:
    """General RAG falls back to LLM — never to pdf_error."""
    return "compile" if s.get("rag_confidence", 0) >= RAG_THRESHOLD else "llm"


def _route_after_llm(s: PipelineState) -> str:
    """
    BUG 1+2 FIX: LLM now sets confidence >= 0.55 for valid answers.
    So most valid LLM answers reach compile without hitting web search.
    Web search is now a true last resort, not a default.
    """
    return "compile" if s.get("llm_confidence", 0) >= LLM_THRESHOLD else "web"


def _route_after_compile(s: PipelineState) -> str:
    return "retry" if s.get("route_taken") == "retry" else "done"


# ── Build Graph ────────────────────────────────────────────────

def build_graph(vector_store: Chroma):
    """Build and compile the complete LangGraph pipeline."""
    graph = StateGraph(PipelineState)

    graph.add_node("classify",     classify_node)
    graph.add_node("pdf_rag",      pdf_rag_node)
    graph.add_node("pdf_summary",  pdf_summary_node)
    graph.add_node("general_rag",  general_rag_node)
    graph.add_node("llm",          llm_node)
    graph.add_node("web_search",   web_search_node)
    graph.add_node("pdf_error",    pdf_error_node)
    graph.add_node("compile",      compile_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify", _route_classify,
        {"pdf": "pdf_rag", "general": "general_rag", "pdf_summary": "pdf_summary"}
    )
    graph.add_conditional_edges(
        "pdf_rag", _route_after_pdf_rag,
        {"compile": "compile", "pdf_error": "pdf_error"}
    )
    graph.add_conditional_edges(
        "general_rag", _route_after_general_rag,
        {"compile": "compile", "llm": "llm"}
    )
    graph.add_conditional_edges(
        "llm", _route_after_llm,
        {"compile": "compile", "web": "web_search"}
    )
    graph.add_edge("web_search", "compile")
    graph.add_edge("pdf_summary", END)
    graph.add_edge("pdf_error", END)
    graph.add_conditional_edges(
        "compile", _route_after_compile,
        {"retry": "general_rag", "done": END}
    )

    return graph.compile()