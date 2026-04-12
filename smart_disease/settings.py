"""
================================================================
  settings.py — Django Project Configuration
  Project: Smart Disease Prediction System v2
  New: Chatbot app, Medicine Prescription, PDF Download
================================================================
"""
import os
from pathlib import Path
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-smart-disease-v2-change-in-production-xyz123'

DEBUG = True

ALLOWED_HOSTS = [
    'web-production-78f04.up.railway.app',
    '*'
]
CSRF_TRUSTED_ORIGINS = [
    'https://web-production-78f04.up.railway.app',
]
# ── INSTALLED APPS ──────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',     # Login, Signup, OTP, Profile
    'prediction',   # ML Prediction, Records, Prescriptions, PDF
    'chatbot',      # AI Chatbot integration
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smart_disease.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_disease.wsgi.application'

# ── DATABASE — MySQL ─────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.mysql',
        'NAME':     os.environ.get('MYSQL_DATABASE', 'smart_disease'),
        'USER':     os.environ.get('MYSQL_USER', 'root'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD', 'Bright!1261'),
        'HOST':     os.environ.get('MYSQL_HOST', 'localhost'),
        'PORT':     os.environ.get('MYSQL_PORT', '3306'),
    }
}

# ── CUSTOM USER MODEL ────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.CustomUser'

# ── AUTH REDIRECTS ───────────────────────────────────────────
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/prediction/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ── PASSWORD VALIDATION ──────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

# ── STATIC FILES ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── MEDIA FILES ──────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = False
USE_TZ = True

# ── EMAIL CONFIG ─────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'kenilsanghavi2017@gamil.com'           # ← Your Gmail
EMAIL_HOST_PASSWORD = 'ifcj yiim qeni mfmx'       # ← Your App Password
DEFAULT_FROM_EMAIL = 'Smart Disease Prediction <your-email@gmail.com>'        # ← Your Gmail

# ── OTP SETTINGS ─────────────────────────────────────────────
OTP_EXPIRY_MINUTES = 5

# ── CHATBOT API — FastAPI runs on port 8001 ──────────────────
CHATBOT_API_URL = 'http://127.0.0.1:8001'

# ── MESSAGE TAGS ─────────────────────────────────────────────
MESSAGE_TAGS = {
    messages.DEBUG:   'debug',
    messages.INFO:    'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR:   'error',
}
