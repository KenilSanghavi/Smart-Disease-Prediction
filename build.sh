#!/usr/bin/env bash
set -o errexit

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Training ML Model ==="
cd prediction/ml_models
python disease_prediction_model.py
cd ../..

echo "=== Running migrations ==="
python manage.py migrate

echo "=== Loading data ==="
python manage.py load_data

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Build complete! ==="