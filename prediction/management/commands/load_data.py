"""
================================================================
  load_data.py — Management Command to Seed Database
  Usage: python manage.py load_data
  Loads: Symptoms, Diseases, DiseaseMedicine from md.csv dataset
================================================================
"""
import os
import pandas as pd
from django.core.management.base import BaseCommand
from prediction.models import Symptom, Disease, DiseaseMedicine


class Command(BaseCommand):
    """
    Seeds the database with all symptoms, diseases, and
    medicine prescriptions from the updated md.csv dataset.
    Run this ONCE after migrations.
    """
    help = 'Load symptoms, diseases and medicines from dataset into DB'

    def handle(self, *args, **kwargs):
        """Main entry point."""
        self.stdout.write('\n🔄 Loading data into database...\n')
        self._load_symptoms()
        self._load_diseases()
        self._load_disease_medicines()
        self.stdout.write(self.style.SUCCESS('\n✅ All data loaded successfully!\n'))

    def _load_symptoms(self):
        """
        Loads all 14 symptom columns from ML model
        into the SYMPTOMS table with categories.
        """
        self.stdout.write('  📋 Loading symptoms...')
        symptoms = [
            ('fever',            'Fever',             'respiratory'),
            ('cough',            'Cough',             'respiratory'),
            ('cold',             'Cold',              'respiratory'),
            ('breathlessness',   'Breathlessness',    'respiratory'),
            ('sore_throat',      'Sore Throat',       'respiratory'),
            ('headache',         'Headache',          'pain'),
            ('body_pain',        'Body Pain',         'pain'),
            ('chest_pain',       'Chest Pain',        'pain'),
            ('dizziness',        'Dizziness',         'pain'),
            ('nausea',           'Nausea',            'gastro'),
            ('vomiting',         'Vomiting',          'gastro'),
            ('diarrhea',         'Diarrhea',          'gastro'),
            ('loss_of_appetite', 'Loss of Appetite',  'gastro'),
            ('fatigue',          'Fatigue',           'general'),
        ]
        count = 0
        for name, display, category in symptoms:
            _, created = Symptom.objects.get_or_create(
                symptom_name=name,
                defaults={'display_name': display, 'category': category}
            )
            if created:
                count += 1
        self.stdout.write(f'     ✓ {count} symptoms added.')

    def _load_diseases(self):
        """Loads all 17 diseases from dataset into DISEASES table."""
        self.stdout.write('  🦠 Loading diseases...')
        diseases = [
            ('common_cold',    'Common Cold',    'Rest and fluids'),
            ('viral_fever',    'Viral Fever',    'Rest and antipyretics'),
            ('migraine',       'Migraine',       'Avoid triggers, pain relief'),
            ('gastritis',      'Gastritis',      'Antacids, avoid spicy food'),
            ('typhoid',        'Typhoid',        'Antibiotics, rest, fluids'),
            ('food_poisoning', 'Food Poisoning', 'Hydration, rest'),
            ('bronchitis',     'Bronchitis',     'Rest, fluids, cough medicine'),
            ('asthma',         'Asthma',         'Inhalers, avoid triggers'),
            ('tuberculosis',   'Tuberculosis',   'Long-term antibiotics'),
            ('diabetes',       'Diabetes',       'Diet control, insulin'),
            ('hypertension',   'Hypertension',   'Low-salt diet, exercise'),
            ('dengue',         'Dengue',         'Rest, fluids, pain relief'),
            ('malaria',        'Malaria',        'Antimalarial drugs'),
            ('influenza',      'Influenza',      'Rest, antivirals'),
            ('pneumonia',      'Pneumonia',      'Antibiotics, rest'),
            ('sinusitis',      'Sinusitis',      'Decongestants, steam'),
            ('covid19',        'COVID-19',       'Isolation, rest, monitoring'),
        ]
        count = 0
        for name, display, precaution in diseases:
            _, created = Disease.objects.get_or_create(
                disease_name=name,
                defaults={'description': display, 'precautions': precaution}
            )
            if created:
                count += 1
        self.stdout.write(f'     ✓ {count} diseases added.')

    def _load_disease_medicines(self):
        """
        Loads medicine prescriptions from md.csv dataset
        into the DISEASE_MEDICINE table.
        Uses the most common prescription per disease.
        """
        self.stdout.write('  💊 Loading disease medicines from dataset...')

        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'ml_models', 'medicine_dataset.csv'
        )

        if not os.path.exists(csv_path):
            self.stdout.write(f'     ⚠️ Dataset not found at: {csv_path}')
            return

        try:
            df    = pd.read_csv(csv_path)
            count = 0

            # Get most common prescription per disease
            for disease_name in df['disease'].unique():
                disease_df = df[df['disease'] == disease_name]
                # Use first row as representative prescription
                row = disease_df.iloc[0]

                try:
                    disease = Disease.objects.get(disease_name=disease_name)
                    _, created = DiseaseMedicine.objects.get_or_create(
                        disease=disease,
                        defaults={
                            'medicine':  str(row['medicine']),
                            'dosage':    str(row['dosage']),
                            'frequency': str(row['frequency']),
                        }
                    )
                    if created:
                        count += 1
                except Disease.DoesNotExist:
                    self.stdout.write(f'     ⚠️ Disease not found: {disease_name}')

            self.stdout.write(f'     ✓ {count} disease medicines added.')

        except Exception as e:
            self.stdout.write(f'     ❌ Error loading medicines: {e}')
