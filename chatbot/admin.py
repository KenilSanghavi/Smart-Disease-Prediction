from django.contrib import admin
from .models import ChatbotHistory
@admin.register(ChatbotHistory)
class ChatbotHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'route', 'confidence', 'created_at')
    list_filter  = ('route', 'created_at')
    search_fields = ('user__email', 'message')
