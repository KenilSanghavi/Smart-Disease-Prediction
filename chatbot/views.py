"""
chatbot/views.py - Fixed with multiple PDF support and clear PDF
"""
import requests
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from .models import ChatbotHistory

CHATBOT_URL = getattr(settings, 'CHATBOT_API_URL', 'http://127.0.0.1:8001')


@login_required
def chatbot_view(request):
    history      = ChatbotHistory.objects.filter(user=request.user).order_by('created_at')[:50]
    pdf_sessions = request.session.get('pdf_sessions', [])
    return render(request, 'chatbot/chatbot.html', {
        'user': request.user,
        'history': history,
        'pdf_sessions': pdf_sessions,
        'pdf_count': len(pdf_sessions),
    })


@login_required
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data    = json.loads(request.body)
        message = data.get('message', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    if not message:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)

    pdf_sessions = request.session.get('pdf_sessions', [])
    latest_pdf   = pdf_sessions[-1]['session_id'] if pdf_sessions else None
    english_msg  = message + " (Important: Please respond in English only)"

    try:
        resp = requests.post(f'{CHATBOT_URL}/chat', json={
            'session_id':  str(request.user.id),
            'message':     english_msg,
            'pdf_session': latest_pdf,
        }, timeout=30)
        resp.raise_for_status()
        result       = resp.json()
        bot_response = result.get('response', 'Sorry, could not process.')
        route        = result.get('route_taken', 'llm')
        confidence   = result.get('confidence', 0.0)
    except requests.exceptions.ConnectionError:
        bot_response = "Chatbot service not running. Start: cd chatbot && uvicorn main:app --port 8001"
        route = 'fallback'; confidence = 0.0
    except Exception as e:
        bot_response = f"Error: {str(e)}"
        route = 'fallback'; confidence = 0.0

    ChatbotHistory.objects.create(user=request.user, message=message,
        response=bot_response, route=route, confidence=confidence)

    return JsonResponse({'response': bot_response, 'route': route,
        'confidence': confidence, 'pdf_count': len(pdf_sessions)})


@login_required
def upload_pdf(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if 'pdf_file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)
    pdf_file = request.FILES['pdf_file']
    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files accepted'}, status=400)
    if pdf_file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File too large. Max 10MB.'}, status=400)
    try:
        resp = requests.post(f'{CHATBOT_URL}/upload-pdf',
            files={'file': (pdf_file.name, pdf_file.read(), 'application/pdf')},
            data={'session_id': str(request.user.id)}, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        pdf_sessions = request.session.get('pdf_sessions', [])
        pdf_sessions.append({
            'session_id': result['pdf_session_id'],
            'filename':   result['filename'],
            'pages':      result['pages'],
        })
        request.session['pdf_sessions'] = pdf_sessions
        request.session.modified = True
        return JsonResponse({'success': True, 'filename': result['filename'],
            'pages': result['pages'], 'pdf_count': len(pdf_sessions),
            'pdf_list': pdf_sessions})
    except requests.exceptions.ConnectionError:
        return JsonResponse({'error': 'Chatbot server not running'}, status=503)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def remove_pdf(request):
    """Remove a single PDF by index from session list."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data  = json.loads(request.body)
        index = int(data.get('index', -1))
    except Exception:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    pdf_sessions = request.session.get('pdf_sessions', [])
    if 0 <= index < len(pdf_sessions):
        removed = pdf_sessions.pop(index)
        request.session['pdf_sessions'] = pdf_sessions
        request.session.modified = True
        return JsonResponse({'success': True, 'removed': removed['filename'],
            'pdf_count': len(pdf_sessions), 'pdf_list': pdf_sessions})
    return JsonResponse({'error': 'Invalid index'}, status=400)


@login_required
def clear_pdf(request):
    """Clear ALL uploaded PDFs from session."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    request.session['pdf_sessions'] = []
    request.session.modified = True
    return JsonResponse({'success': True, 'pdf_count': 0})


@login_required
def clear_chat(request):
    """Clear all chat history."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    ChatbotHistory.objects.filter(user=request.user).delete()
    try:
        requests.delete(f'{CHATBOT_URL}/history/{request.user.id}', timeout=5)
    except Exception:
        pass
    return JsonResponse({'success': True})