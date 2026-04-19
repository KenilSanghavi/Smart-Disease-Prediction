from django.contrib import admin
from .models import Symptom, Disease, DiseaseSymptom, DiseaseMedicine, UserSymptom, Prediction, DiagnosisReport, Medicine, Prescription

@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = ('symptom_name', 'category')
    list_filter  = ('category',)

@admin.register(Disease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display  = ('disease_name',)
    search_fields = ('disease_name',)

@admin.register(DiseaseMedicine)
class DiseaseMedicineAdmin(admin.ModelAdmin):
    list_display  = ('disease', 'medicine')
    list_filter   = ('disease',)

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'predicted_disease_1', 'confidence_score_1', 'created_at')
    list_filter   = ('created_at',)

@admin.register(DiagnosisReport)
class DiagnosisReportAdmin(admin.ModelAdmin):
    list_display = ('prediction', 'report_name', 'report_date')

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'medicine_name', 'prescribed_date')

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('medicine_name', 'created_at')
