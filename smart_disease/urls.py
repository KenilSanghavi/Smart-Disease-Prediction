"""
================================================================
  urls.py — Main URL Configuration
================================================================
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('prediction/', include('prediction.urls')),
    path('chatbot/', include('chatbot.urls')),
    path('', lambda request: redirect('login')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
