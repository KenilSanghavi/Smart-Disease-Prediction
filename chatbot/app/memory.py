"""
app/memory.py
Conversation memory — stores chat history per session.
Uses an in-memory store (dict) that works perfectly for development.
For production at scale, swap the store with Redis (just change _store).

Each session stores the last MAX_HISTORY_TURNS turns of conversation.
This history is injected into every LLM call so the model remembers
what was said earlier in the conversation.
"""

from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from config import MAX_HISTORY_TURNS, SYSTEM_PROMPT
import logging

logger = logging.getLogger(__name__)

# In-memory store: {session_id: [list of LangChain message objects]}
_store: Dict[str, List[BaseMessage]] = {}


def get_history(session_id: str) -> List[BaseMessage]:
    """
    Get conversation history for a session as LangChain message objects.
    Returns empty list for new sessions.
    """
    return _store.get(session_id, [])


def add_turn(session_id: str, user_message: str, ai_response: str) -> None:
    """
    Add one user + assistant turn to the conversation history.
    Automatically trims to MAX_HISTORY_TURNS to prevent context overflow.
    """
    if session_id not in _store:
        _store[session_id] = []

    _store[session_id].append(HumanMessage(content=user_message))
    _store[session_id].append(AIMessage(content=ai_response))

    # Keep only the most recent N turns (each turn = 2 messages)
    max_messages = MAX_HISTORY_TURNS * 2
    if len(_store[session_id]) > max_messages:
        _store[session_id] = _store[session_id][-max_messages:]

    logger.info(f"Session {session_id}: {len(_store[session_id])//2} turns stored")


def clear_history(session_id: str) -> None:
    """Delete all conversation history for a session."""
    if session_id in _store:
        del _store[session_id]
        logger.info(f"Cleared history for session {session_id}")


def get_history_as_dicts(session_id: str) -> List[dict]:
    """
    Return conversation history as list of dicts for the API response.
    Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    history = get_history(session_id)
    result  = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            result.append({"role": "user",      "content": msg.content})
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})
    return result


def build_context_with_history(session_id: str, current_query: str) -> str:
    """
    Build a context string that includes conversation history.
    This is injected into the RAG and LLM prompts so the model
    is aware of the full conversation, not just the current message.
    """
    history = get_history(session_id)
    if not history:
        return current_query

    history_text = ""
    for msg in history[-6:]:  # last 3 turns for context
        if isinstance(msg, HumanMessage):
            history_text += f"User: {msg.content}\n"
        elif isinstance(msg, AIMessage):
            history_text += f"Assistant: {msg.content}\n"

    return (
        f"Previous conversation:\n{history_text}\n"
        f"Current question: {current_query}"
    )


def format_messages_for_llm(
    session_id: str,
    current_query: str
) -> List[BaseMessage]:
    """
    Build the full message list for LLM including system prompt + history + current query.
    Pass this directly to ChatGroq for memory-aware responses.
    """
    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(get_history(session_id))
    messages.append(HumanMessage(content=current_query))
    return messages
