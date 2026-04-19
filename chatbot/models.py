"""
================================================================
  chatbot/models.py — Chatbot History Model
  Table: CHATBOT_HISTORY (NEW)
================================================================
"""
from django.db import models
from accounts.models import CustomUser


class ChatbotHistory(models.Model):
    """
    NEW TABLE — Maps to: CHATBOT_HISTORY table
    Stores every chatbot conversation for each user.
    Allows users to view their chat history.
    """
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_history')
    message    = models.TextField(help_text="User's message to chatbot")
    response   = models.TextField(help_text="Chatbot's response")
    route      = models.CharField(max_length=20, blank=True, help_text="rag/llm/web/fallback")
    confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chatbot_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.name} — {self.message[:50]} ({self.created_at.date()})"
