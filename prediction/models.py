from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


# ── SYMPTOM MODEL ───────────────────────────────────────────
class Symptom(models.Model):
    CATEGORY_CHOICES = [
        ('respiratory', 'Respiratory'),
        ('pain', 'Pain'),
        ('gastro', 'Gastro'),
        ('general', 'General'),
    ]

    symptom_name = models.CharField(max_length=100, unique=True)
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    def __str__(self):
        return self.symptom_name


# ── DISEASE MODEL ───────────────────────────────────────────
class Disease(models.Model):
    disease_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.disease_name


# ── MEDICINE MODEL ──────────────────────────────────────────
class Medicine(models.Model):
    medicine_name = models.CharField(max_length=100)

    def __str__(self):
        return self.medicine_name


# ── DISEASE → MEDICINE MAPPING ─────────────────────────────
class DiseaseMedicine(models.Model):
    disease   = models.ForeignKey(Disease, on_delete=models.CASCADE)
    medicine  = models.CharField(max_length=200)
    dosage    = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.disease} → {self.medicine}"


# ── USER SYMPTOMS ──────────────────────────────────────────
class UserSymptom(models.Model):
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='user_symptoms')
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE)
    recorded_date = models.DateTimeField(auto_now_add=True)


# ── PREDICTION MODEL ───────────────────────────────────────
class Prediction(models.Model):
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='predictions')
    disease = models.ForeignKey(Disease, on_delete=models.SET_NULL, null=True)

    predicted_disease_1 = models.CharField(max_length=100)
    confidence_score_1  = models.FloatField()

    predicted_disease_2 = models.CharField(max_length=100, blank=True, null=True)
    confidence_score_2  = models.FloatField(blank=True, null=True)

    predicted_disease_3 = models.CharField(max_length=100, blank=True, null=True)
    confidence_score_3  = models.FloatField(blank=True, null=True)

    symptoms_selected = models.JSONField()
    vitals_data       = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.predicted_disease_1}"


# ── DIAGNOSIS REPORT ───────────────────────────────────────
class DiagnosisReport(models.Model):
    prediction = models.OneToOneField(Prediction, on_delete=models.CASCADE, related_name='report')
    report_name = models.CharField(max_length=200)
    notes       = models.TextField(blank=True, null=True)

    report_date = models.DateField(auto_now_add=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.report_name


# ── PRESCRIPTION MODEL ─────────────────────────────────────
class Prescription(models.Model):
    report = models.ForeignKey(DiagnosisReport, on_delete=models.CASCADE, related_name='prescriptions')
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='prescriptions')

    medicine_name = models.CharField(max_length=200)
    dosage        = models.CharField(max_length=100)
    frequency     = models.CharField(max_length=100)

    prescribed_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine_name} for {self.user}"