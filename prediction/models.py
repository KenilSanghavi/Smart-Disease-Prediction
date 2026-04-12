"""
================================================================
  prediction/models.py — Disease Prediction Models
  Tables: SYMPTOMS, DISEASES, DISEASE_SYMPTOMS, USER_SYMPTOMS,
          PREDICTIONS, DIAGNOSIS_REPORTS, MEDICINES,
          PRESCRIPTIONS, DISEASE_MEDICINE (NEW)
================================================================
"""
from django.db import models
from accounts.models import CustomUser


class Symptom(models.Model):
    """Maps to: SYMPTOMS table — all symptoms shown as checkboxes."""
    CATEGORY_CHOICES = [
        ('respiratory', 'Respiratory'),
        ('pain',        'Pain'),
        ('gastro',      'Gastro'),
        ('general',     'General'),
    ]
    symptom_name = models.CharField(max_length=100, unique=True)
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    display_name = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'symptoms'
        ordering = ['category', 'symptom_name']

    def __str__(self):
        return self.display_name or self.symptom_name


class Disease(models.Model):
    """Maps to: DISEASES table — all 17 diseases ML can predict."""
    disease_name = models.CharField(max_length=100, unique=True)
    description  = models.TextField(blank=True)
    precautions  = models.TextField(blank=True)

    class Meta:
        db_table = 'diseases'

    def __str__(self):
        return self.disease_name


class DiseaseSymptom(models.Model):
    """Maps to: DISEASE_SYMPTOMS table — disease to symptom mapping."""
    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name='disease_symptoms')
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE)

    class Meta:
        db_table        = 'disease_symptoms'
        unique_together = ('disease', 'symptom')

    def __str__(self):
        return f"{self.disease} — {self.symptom}"


class DiseaseMedicine(models.Model):
    """
    NEW TABLE — Maps to: DISEASE_MEDICINE table
    Stores prescription data from the updated dataset (md.csv).
    Each disease has medicine, dosage and frequency from the dataset.
    Auto-used when ML predicts a disease to fill prescription.
    """
    disease   = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name='medicines')
    medicine  = models.TextField(help_text="Medicine names from dataset")
    dosage    = models.TextField(help_text="Dosage instructions from dataset")
    frequency = models.TextField(help_text="Frequency/timing instructions from dataset")

    class Meta:
        db_table = 'disease_medicine'

    def __str__(self):
        return f"{self.disease.disease_name} — {self.medicine[:50]}"


class UserSymptom(models.Model):
    """Maps to: USER_SYMPTOMS table — records user selected symptoms."""
    user          = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_symptoms')
    symptom       = models.ForeignKey(Symptom, on_delete=models.CASCADE)
    recorded_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_symptoms'

    def __str__(self):
        return f"{self.user.name} — {self.symptom.symptom_name}"


class Prediction(models.Model):
    """
    Maps to: PREDICTIONS table
    Stores top 3 ML predictions with confidence scores.
    """
    user                = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='predictions')
    disease             = models.ForeignKey(Disease, on_delete=models.SET_NULL, null=True)
    predicted_disease_1 = models.CharField(max_length=100, blank=True)
    confidence_score_1  = models.FloatField(default=0.0)
    predicted_disease_2 = models.CharField(max_length=100, blank=True)
    confidence_score_2  = models.FloatField(default=0.0)
    predicted_disease_3 = models.CharField(max_length=100, blank=True)
    confidence_score_3  = models.FloatField(default=0.0)
    symptoms_selected   = models.JSONField(default=dict)
    vitals_data         = models.JSONField(default=dict)
    prediction_date     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'predictions'
        ordering = ['-prediction_date']

    def __str__(self):
        return f"{self.user.name} — {self.predicted_disease_1} ({self.prediction_date.date()})"


class DiagnosisReport(models.Model):
    """
    Maps to: DIAGNOSIS_REPORTS table
    Auto-created after every prediction.
    Includes full prescription from DiseaseMedicine table.
    """
    prediction  = models.OneToOneField(Prediction, on_delete=models.CASCADE, related_name='report')
    report_name = models.CharField(max_length=200, blank=True)
    doctor_name = models.CharField(max_length=100, blank=True, default='AI Diagnosis')
    notes       = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    report_date = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'diagnosis_reports'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Report — {self.prediction.user.name} — {self.report_date}"


class Medicine(models.Model):
    """Maps to: MEDICINES table — medicine master list."""
    medicine_name = models.CharField(max_length=200, unique=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'medicines'

    def __str__(self):
        return self.medicine_name


class Prescription(models.Model):
    """
    Maps to: PRESCRIPTIONS table
    Auto-filled from DiseaseMedicine after prediction.
    Downloaded in PDF report.
    """
    report          = models.ForeignKey(DiagnosisReport, on_delete=models.CASCADE, related_name='prescriptions')
    user            = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='prescriptions')
    medicine_name   = models.TextField()
    dosage          = models.TextField()
    frequency       = models.TextField()
    prescribed_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'prescriptions'

    def __str__(self):
        return f"{self.user.name} — {self.medicine_name[:50]}"
