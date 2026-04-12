from django.urls import path
from . import views

urlpatterns = [
    path('',            views.chatbot_view,  name='chatbot'),
    path('send/',       views.send_message,  name='chatbot_send'),
    path('upload-pdf/', views.upload_pdf,    name='chatbot_upload_pdf'),
    path('remove-pdf/', views.remove_pdf,    name='chatbot_remove_pdf'),
    path('clear-pdf/',  views.clear_pdf,     name='chatbot_clear_pdf'),
    path('clear/',      views.clear_chat,    name='chatbot_clear'),
]