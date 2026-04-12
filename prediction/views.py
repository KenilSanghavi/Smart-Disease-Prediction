"""
================================================================
  prediction/views.py — Disease Prediction + Prescription + PDF
  Features:
    - ML prediction with top 3 diseases
    - Auto-fills prescription from DiseaseMedicine table
    - PDF download with full prescription
    - Past records, report detail
================================================================
"""
import os
import pickle
import numpy as np
from datetime import date as date_obj
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from .models import (
    Symptom, Disease, Prediction, DiagnosisReport,
    Medicine, Prescription, UserSymptom, DiseaseMedicine
)


# ── LOAD ML MODELS ON SERVER START ───────────────────────────
BASE_ML = os.path.join(os.path.dirname(__file__), 'ml_models')
ML_LOADED = False

try:
    with open(os.path.join(BASE_ML, 'disease_model.pkl'), 'rb') as f:
        _data     = pickle.load(f)
        ML_MODEL  = _data['model']
    with open(os.path.join(BASE_ML, 'scaler.pkl'), 'rb') as f:
        ML_SCALER = pickle.load(f)
    with open(os.path.join(BASE_ML, 'label_encoder.pkl'), 'rb') as f:
        ML_LE     = pickle.load(f)
    ML_LOADED = True
    print("[ML] Disease prediction model loaded successfully!")
except Exception as e:
    print(f"[ML] Model not loaded: {e}. Run disease_prediction_model.py first.")


def _run_ml_prediction(feature_values, dob, gender):
    """
    Calls ML model predict_top3() function.
    Returns top 3 disease predictions with confidence %.
    """
    from .ml_models.disease_prediction_model import predict_top3
    result = predict_top3(
        model=ML_MODEL, scaler=ML_SCALER, le=ML_LE,
        feature_values=feature_values, dob=dob, gender=gender
    )
    return result['top3_predictions']


def _get_prescription_for_disease(disease_name):
    """
    Fetches medicine prescription from DiseaseMedicine table
    for a given disease name. Returns dict with medicine, dosage, frequency.
    """
    try:
        disease = Disease.objects.get(disease_name=disease_name)
        rx      = DiseaseMedicine.objects.filter(disease=disease).first()
        if rx:
            return {
                'medicine':  rx.medicine,
                'dosage':    rx.dosage,
                'frequency': rx.frequency,
            }
    except Disease.DoesNotExist:
        pass
    return None


# ── DASHBOARD VIEW ────────────────────────────────────────────
@login_required
def dashboard_view(request):
    """
    Main dashboard with stats cards and 3 action cards.
    Shows: total predictions, records, accuracy, alerts.
    """
    user              = request.user
    total_predictions = Prediction.objects.filter(user=user).count()
    total_records     = DiagnosisReport.objects.filter(prediction__user=user).count()
    recent_prediction = Prediction.objects.filter(user=user).first()

    context = {
        'user':              user,
        'total_predictions': total_predictions,
        'total_records':     total_records,
        'accuracy':          98,
        'alerts':            0,
        'recent_prediction': recent_prediction,
    }
    return render(request, 'prediction/dashboard.html', context)


# ── PREDICT VIEW ──────────────────────────────────────────────
@login_required
def predict_view(request):
    """
    Disease Prediction with symptom checkboxes + vitals.
    POST: Runs ML, saves prediction + prescription, shows results.
    """
    symptoms_by_category = {
        'Respiratory': Symptom.objects.filter(category='respiratory'),
        'Pain':        Symptom.objects.filter(category='pain'),
        'Gastro':      Symptom.objects.filter(category='gastro'),
        'General':     Symptom.objects.filter(category='general'),
    }

    if request.method == 'POST':
        if not ML_LOADED:
            messages.error(request, '⚠️ ML model not found! Run disease_prediction_model.py first.')
            return redirect('predict')

        # ── Get vitals from form ──────────────────────────────
        try:
            bmi              = float(request.POST.get('bmi', 22.0))
            body_temperature = float(request.POST.get('body_temperature', 37.0))
            heart_rate       = int(request.POST.get('heart_rate', 80))
            symptom_duration = int(request.POST.get('symptom_duration_days', 1))
            pain_severity    = int(request.POST.get('pain_severity', 1))
            chronic_disease  = 1 if request.POST.get('chronic_disease') else 0
            allergy_history  = 1 if request.POST.get('allergy_history') else 0
            recent_travel    = 1 if request.POST.get('recent_travel') else 0
            smoking          = 1 if request.POST.get('smoking') else 0
            alcohol          = 1 if request.POST.get('alcohol') else 0
        except (ValueError, TypeError):
            messages.error(request, 'Please fill in all vitals correctly.')
            return render(request, 'prediction/predict.html', {'symptoms_by_category': symptoms_by_category})

        # ── Build feature dict from checkboxes ────────────────
        selected_symptoms = request.POST.getlist('symptoms')
        all_sym_cols = [
            'fever','cough','cold','headache','fatigue','body_pain',
            'sore_throat','nausea','vomiting','diarrhea','breathlessness',
            'chest_pain','dizziness','loss_of_appetite'
        ]
        feature_values = {col: 0 for col in all_sym_cols}
        for sym in selected_symptoms:
            if sym in feature_values:
                feature_values[sym] = 1

        feature_values.update({
            'bmi': bmi, 'body_temperature': body_temperature,
            'heart_rate': heart_rate, 'symptom_duration_days': symptom_duration,
            'pain_severity': pain_severity, 'chronic_disease': chronic_disease,
            'allergy_history': allergy_history, 'recent_travel': recent_travel,
            'smoking': smoking, 'alcohol': alcohol,
        })

        # ── Get user DOB + gender ─────────────────────────────
        user   = request.user
        gender = 1 if user.gender == 'male' else 0
        dob    = user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else '1990-01-01'

        # ── Run ML prediction ─────────────────────────────────
        try:
            top3 = _run_ml_prediction(feature_values, dob, gender)
        except Exception as e:
            messages.error(request, f'Prediction error: {str(e)}')
            return render(request, 'prediction/predict.html', {'symptoms_by_category': symptoms_by_category})

        # ── Save user symptoms ────────────────────────────────
        for sym_name in selected_symptoms:
            sym_obj = Symptom.objects.filter(symptom_name=sym_name).first()
            if sym_obj:
                UserSymptom.objects.create(user=user, symptom=sym_obj)

        # ── Get/create disease object ─────────────────────────
        primary_disease, _ = Disease.objects.get_or_create(disease_name=top3[0]['disease'])

        # ── Save Prediction ───────────────────────────────────
        pred_obj = Prediction.objects.create(
            user                = user,
            disease             = primary_disease,
            predicted_disease_1 = top3[0]['disease'],
            confidence_score_1  = top3[0]['probability_pct'],
            predicted_disease_2 = top3[1]['disease'] if len(top3) > 1 else '',
            confidence_score_2  = top3[1]['probability_pct'] if len(top3) > 1 else 0,
            predicted_disease_3 = top3[2]['disease'] if len(top3) > 2 else '',
            confidence_score_3  = top3[2]['probability_pct'] if len(top3) > 2 else 0,
            symptoms_selected   = {'symptoms': selected_symptoms},
            vitals_data         = {'bmi': bmi, 'body_temperature': body_temperature, 'heart_rate': heart_rate},
        )

        # ── Auto-create Diagnosis Report ──────────────────────
        disease_display = top3[0]['disease'].replace('_', ' ').title()
        report_obj = DiagnosisReport.objects.create(
            prediction  = pred_obj,
            report_name = f"Diagnosis Report — {disease_display}",
            notes       = f"AI predicted {disease_display} with {top3[0]['probability_pct']}% confidence.",
        )

        # ── Auto-fill Prescription from DiseaseMedicine ───────
        rx_data = _get_prescription_for_disease(top3[0]['disease'])
        if rx_data:
            Prescription.objects.create(
                report        = report_obj,
                user          = user,
                medicine_name = rx_data['medicine'],
                dosage        = rx_data['dosage'],
                frequency     = rx_data['frequency'],
            )

        # ── Render result page ────────────────────────────────
        prescription = Prescription.objects.filter(report=report_obj).first()
        return render(request, 'prediction/result.html', {
            'top3':             top3,
            'prediction':       pred_obj,
            'report':           report_obj,
            'prescription':     prescription,
            'selected_symptoms': selected_symptoms,
        })

    return render(request, 'prediction/predict.html', {
        'symptoms_by_category': symptoms_by_category,
        'user': request.user,
    })


# ── PAST RECORDS VIEW ─────────────────────────────────────────
@login_required
def records_view(request):
    """Shows all past diagnosis reports for the user."""
    reports = DiagnosisReport.objects.filter(
        prediction__user=request.user
    ).select_related('prediction').order_by('-recorded_at')
    return render(request, 'prediction/records.html', {'reports': reports})


# ── REPORT DETAIL VIEW ────────────────────────────────────────
@login_required
def report_detail_view(request, report_id):
    """Shows full report with prescription details."""
    report = get_object_or_404(DiagnosisReport, id=report_id, prediction__user=request.user)
    prescriptions = Prescription.objects.filter(report=report)
    return render(request, 'prediction/report_detail.html', {
        'report':        report,
        'prediction':    report.prediction,
        'prescriptions': prescriptions,
    })


# ── HISTORY VIEW ──────────────────────────────────────────────
@login_required
def history_view(request):
    """Shows all predictions in a table."""
    predictions = Prediction.objects.filter(user=request.user)
    return render(request, 'prediction/history.html', {'predictions': predictions})


# ── PDF DOWNLOAD VIEW ─────────────────────────────────────────
@login_required
def download_report_pdf(request, report_id):
    """
    Generates and downloads a professional PDF report.
    Fixed: Text wraps properly inside table cells using Paragraph.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    report        = get_object_or_404(DiagnosisReport, id=report_id, prediction__user=request.user)
    pred          = report.prediction
    prescriptions = Prescription.objects.filter(report=report)
    user          = request.user

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="MediSense_Report_{report_id}.pdf"'

    doc    = SimpleDocTemplate(response, pagesize=letter, topMargin=40, bottomMargin=40,
                               leftMargin=40, rightMargin=40)
    styles = getSampleStyleSheet()

    # ── Custom styles ─────────────────────────────────────────
    title_style = ParagraphStyle('Title', parent=styles['Title'],
        fontSize=20, textColor=colors.HexColor('#2563eb'), spaceAfter=4)

    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
        fontSize=13, textColor=colors.HexColor('#1e293b'), spaceBefore=14, spaceAfter=8)

    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#475569'), leading=15)

    cell_style = ParagraphStyle('Cell', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#1e293b'), leading=14,
        wordWrap='CJK')

    label_style = ParagraphStyle('Label', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#1e293b'),
        fontName='Helvetica-Bold', leading=14)

    small_style = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=9, textColor=colors.grey)

    elements = []

    # ── Header ────────────────────────────────────────────────
    elements.append(Paragraph("🧠 MediSense AI — Smart Disease Prediction", title_style))
    elements.append(Paragraph("Diagnosis &amp; Prescription Report", styles['Heading3']))
    elements.append(HRFlowable(width="100%", thickness=2,
        color=colors.HexColor('#2563eb'), spaceAfter=14))
    elements.append(Spacer(1, 6))

    # ── Patient Information ───────────────────────────────────
    elements.append(Paragraph("Patient Information", h2_style))
    patient_data = [
        [Paragraph('<b>Patient Name</b>', label_style), Paragraph(user.name or 'N/A', cell_style)],
        [Paragraph('<b>Email</b>',        label_style), Paragraph(user.email, cell_style)],
        [Paragraph('<b>Age</b>',          label_style), Paragraph(str(user.age or 'N/A'), cell_style)],
        [Paragraph('<b>Gender</b>',       label_style), Paragraph(user.gender.title() if user.gender else 'N/A', cell_style)],
        [Paragraph('<b>Contact</b>',      label_style), Paragraph(user.contact_no or 'N/A', cell_style)],
        [Paragraph('<b>Report Date</b>',  label_style), Paragraph(str(report.report_date), cell_style)],
        [Paragraph('<b>Report ID</b>',    label_style), Paragraph(f'RPT-{report.id:04d}', cell_style)],
    ]
    pt = Table(patient_data, colWidths=[140, 380])
    pt.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (0, -1), colors.HexColor('#eff6ff')),
        ('FONTSIZE',       (0, 0), (-1, -1), 10),
        ('GRID',           (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING',        (0, 0), (-1, -1), 8),
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8faff')]),
    ]))
    elements.append(pt)
    elements.append(Spacer(1, 16))

    # ── AI Prediction Results ─────────────────────────────────
    elements.append(Paragraph("AI Prediction Results", h2_style))
    pred_data = [[
        Paragraph('<b>Rank</b>', label_style),
        Paragraph('<b>Predicted Disease</b>', label_style),
        Paragraph('<b>Confidence Score</b>', label_style),
    ]]
    for rank, (disease, conf) in enumerate([
        (pred.predicted_disease_1, pred.confidence_score_1),
        (pred.predicted_disease_2, pred.confidence_score_2),
        (pred.predicted_disease_3, pred.confidence_score_3),
    ], 1):
        if disease:
            pred_data.append([
                Paragraph(f'#{rank}', cell_style),
                Paragraph(disease.replace('_', ' ').title(), cell_style),
                Paragraph(f'{conf}%', cell_style),
            ])

    prt = Table(pred_data, colWidths=[50, 310, 160])
    prt.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR',      (0, 0), (-1, 0), colors.white),
        ('FONTSIZE',       (0, 0), (-1, -1), 10),
        ('GRID',           (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING',        (0, 0), (-1, -1), 10),
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',          (2, 0), (2, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8faff')]),
    ]))
    elements.append(prt)
    elements.append(Spacer(1, 16))

    # ── Reported Symptoms ─────────────────────────────────────
    elements.append(Paragraph("Reported Symptoms", h2_style))
    symptoms = pred.symptoms_selected.get('symptoms', [])
    sym_text = ', '.join([s.replace('_', ' ').title() for s in symptoms]) or 'None reported'
    elements.append(Paragraph(sym_text, body_style))
    elements.append(Spacer(1, 16))

    # ── Prescription ──────────────────────────────────────────
    if prescriptions.exists():
        elements.append(Paragraph("💊 Prescription", h2_style))
        for rx in prescriptions:
            elements.append(Paragraph(
                f"<b>Primary Diagnosis:</b> {pred.predicted_disease_1.replace('_',' ').title()}",
                body_style
            ))
            elements.append(Spacer(1, 8))

            rx_data = [
                [Paragraph('<b>Medicine(s)</b>', label_style),
                 Paragraph(rx.medicine_name, cell_style)],

                [Paragraph('<b>Dosage</b>', label_style),
                 Paragraph(rx.dosage, cell_style)],

                [Paragraph('<b>Frequency</b>', label_style),
                 Paragraph(rx.frequency, cell_style)],

                [Paragraph('<b>Prescribed</b>', label_style),
                 Paragraph(str(rx.prescribed_date.date()), cell_style)],
            ]

            # Wider second column so text wraps properly
            rxt = Table(rx_data, colWidths=[100, 420])
            rxt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fef9c3')),
                ('TEXTCOLOR',  (0, 0), (0, -1), colors.HexColor('#92400e')),
                ('FONTSIZE',   (0, 0), (-1, -1), 10),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING',    (0, 0), (-1, -1), 10),
                ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(rxt)
        elements.append(Spacer(1, 16))

    # ── Doctor Notes ──────────────────────────────────────────
    if report.notes:
        elements.append(Paragraph("Doctor Notes", h2_style))
        elements.append(Paragraph(report.notes, body_style))
        elements.append(Spacer(1, 16))

    # ── Disclaimer ────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1,
        color=colors.HexColor('#e2e8f0'), spaceBefore=10))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "⚠️ DISCLAIMER: This report is AI-generated by MediSense AI and is for informational "
        "purposes only. It does not constitute medical advice. Please consult a qualified "
        "healthcare professional for diagnosis and treatment.",
        small_style
    ))

    doc.build(elements)
    return response