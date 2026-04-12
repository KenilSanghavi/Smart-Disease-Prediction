"""
app/translator.py
Multilingual support — detects language and translates.
Supports 100+ languages via Google Translate (no API key needed).
"""

import logging
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language of text. Returns ISO 639-1 code. Falls back to 'en'."""
    try:
        if not text or len(text.strip()) < 3:
            return "en"
        return detect(text)
    except LangDetectException:
        return "en"


def to_english(text: str, source_lang: str) -> str:
    """Translate text to English. Returns original if already English."""
    if source_lang == "en":
        return text
    try:
        return GoogleTranslator(source=source_lang, target="en").translate(text)
    except Exception as e:
        logger.warning(f"Translation to English failed: {e}")
        return text


def from_english(text: str, target_lang: str) -> str:
    """Translate English text to target language. Returns as-is if English."""
    if target_lang == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception as e:
        logger.warning(f"Translation from English failed: {e}")
        return text


def preprocess(user_text: str) -> dict:
    """
    Full multilingual preprocessing.
    Returns: {original_text, detected_lang, english_text}
    """
    lang         = detect_language(user_text)
    english_text = to_english(user_text, lang)
    return {
        "original_text": user_text,
        "detected_lang": lang,
        "english_text" : english_text,
    }
