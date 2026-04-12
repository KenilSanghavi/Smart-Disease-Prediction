<<<<<<< HEAD
# MediSense AI — Smart Disease Prediction System v2

## What's New in v2
- ✅ New MediSense AI sidebar UI
- ✅ Auto-generated prescriptions from dataset
- ✅ PDF download with full prescription
- ✅ AI Chatbot integrated (FastAPI + LangGraph + RAG)
- ✅ 12 database tables (2 new: disease_medicine, chatbot_history)

---

## Project Structure
```
smart_disease_v2/
├── manage.py
├── requirements.txt
├── smart_disease/          ← Django config
│   ├── settings.py
│   └── urls.py
├── accounts/               ← Auth (Login, Signup, OTP, Profile)
├── prediction/             ← ML Prediction, Records, PDF
│   └── ml_models/
│       ├── disease_model.pkl     ← Train first!
│       ├── label_encoder.pkl
│       ├── scaler.pkl
│       ├── medicine_dataset.csv
│       └── disease_prediction_model.py
└── chatbot/                ← AI Chatbot (calls FastAPI)
    ├── app/                ← LangGraph chatbot code
    ├── config.py
    ├── main.py             ← FastAPI server
    └── requirements.txt
```

---

## Setup Instructions

### Step 1 — Create MySQL Database
```sql
CREATE DATABASE smart_disease;
```

### Step 2 — Update settings.py
```python
DATABASES = {
    'default': {
        'NAME': 'smart_disease',
        'USER': 'root',
        'PASSWORD': 'your_password',
    }
}
EMAIL_HOST_USER     = 'your-gmail@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-digit-app-password'
DEFAULT_FROM_EMAIL  = 'your-gmail@gmail.com'
```

### Step 3 — Install Django dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Train ML Model
```bash
cd prediction/ml_models
python disease_prediction_model.py
cd ../..
```

### Step 5 — Run Migrations
```bash
python manage.py makemigrations accounts
python manage.py makemigrations prediction
python manage.py makemigrations chatbot
python manage.py migrate
```

### Step 6 — Load Data
```bash
python manage.py load_data
```

### Step 7 — Create Admin
```bash
python manage.py createsuperuser
```

### Step 8 — Setup Chatbot API Keys
```bash
# Edit chatbot/.env (copy from chatbot/.env.example)
GROQ_API_KEY=your_groq_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```
Get free keys from: groq.com and tavily.com

### Step 9 — Start Chatbot Server (Terminal 1)
```bash
cd chatbot
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Step 10 — Start Django Server (Terminal 2)
```bash
python manage.py runserver
```

---

## URLs
| URL | Page |
|-----|------|
| /accounts/login/ | Login |
| /accounts/signup/ | Sign Up |
| /accounts/forgot-password/ | Forgot Password (OTP) |
| /prediction/dashboard/ | Dashboard |
| /prediction/predict/ | Disease Prediction |
| /prediction/records/ | Past Medical Records |
| /prediction/records/ID/pdf/ | Download PDF Report |
| /chatbot/ | AI Chatbot |
| /admin/ | Admin Panel |

---

## Database Tables (12 Total)
| Table | App |
|-------|-----|
| users | accounts |
| login_history | accounts |
| otp_verification | accounts |
| symptoms | prediction |
| diseases | prediction |
| disease_symptoms | prediction |
| disease_medicine ⭐ NEW | prediction |
| user_symptoms | prediction |
| predictions | prediction |
| diagnosis_reports | prediction |
| prescriptions | prediction |
| chatbot_history ⭐ NEW | chatbot |
=======
# Smart-Disease-Prediction
>>>>>>> cfee6c7ce9a0511811e95406e5bfc98f5ce95c2f
