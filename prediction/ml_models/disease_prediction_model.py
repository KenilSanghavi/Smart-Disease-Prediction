"""
================================================================
  Smart Disease Prediction System — ML Model (Production)
  ----------------------------------------------------------------
  PURPOSE   : Predict top-3 diseases with % probabilities
  AUTHOR    : ML developer
  GIVES TO  : Django backend developer

  WHAT THIS FILE DOES:
    1. Trains the ensemble ML model on the dataset
    2. Saves 3 pkl files (model, scaler, label encoder)
    3. Exposes predict_top3() for Django to import and call

  WHAT THIS FILE DOES NOT DO (handled by Django/MySQL):
    - No PDF generation
    - No medicine/dosage storage
    - No database saving
    - No user login/auth
    - No form handling

  HOW YOUR DJANGO FRIEND USES THIS:
    from disease_prediction_model import predict_top3
    result = predict_top3(model, scaler, le, data, dob, gender)

  FILES TO HAND OVER TO DJANGO DEVELOPER:
    - disease_prediction_model.py   (this file)
    - disease_model.pkl
    - label_encoder.pkl
    - scaler.pkl
================================================================
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import date

from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    VotingClassifier,
)
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score
from sklearn.utils import resample

warnings.filterwarnings("ignore")


# SECTION 1 — CONFIGURATION

BASE_DIR = os.getcwd()

DATASET_PATH       = os.path.join(BASE_DIR, "medicine_dataset.csv")
MODEL_SAVE_PATH    = os.path.join(BASE_DIR, "disease_model.pkl")
LABEL_ENCODER_PATH = os.path.join(BASE_DIR, "label_encoder.pkl")
SCALER_PATH        = os.path.join(BASE_DIR, "scaler.pkl")

RANDOM_STATE             = 42
TEST_SIZE                = 0.20
TARGET_SAMPLES_PER_CLASS = 150

FEATURE_COLS = [
    "age", "gender", "bmi", "body_temperature", "heart_rate",
    "fever", "cough", "cold", "headache", "fatigue",
    "body_pain", "sore_throat", "nausea", "vomiting", "diarrhea",
    "breathlessness", "chest_pain", "dizziness", "loss_of_appetite",
    "symptom_duration_days", "pain_severity",
    "chronic_disease", "allergy_history", "recent_travel",
    "smoking", "alcohol",
]
TARGET_COL = "disease"


# SECTION 2 — DATA LOADING & PREPROCESSING

def load_and_preprocess(path):
    print("\n[1/5] Loading dataset...")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n  ERROR: Dataset not found at: {path}\n"
            "  Make sure the CSV is in the same folder as this script.\n"
        )
    df = pd.read_csv(path)
    print(f"      Shape     : {df.shape}")
    print(f"      Diseases  : {df[TARGET_COL].nunique()}")
    print(f"      Missing   : {df.isnull().sum().sum()} values")
    df = _engineer_features(df)
    return df


def _engineer_features(df):
    """Add derived features that improve model accuracy."""
    df["age_group"] = pd.cut(
        df["age"],
        bins=[0, 12, 17, 35, 60, 120],
        labels=[0, 1, 2, 3, 4]
    ).astype(int)

    df["bmi_category"] = pd.cut(
        df["bmi"],
        bins=[0, 18.5, 24.9, 29.9, 100],
        labels=[0, 1, 2, 3]
    ).astype(int)

    df["temp_flag"] = (df["body_temperature"] >= 38.0).astype(int)
    df["high_hr"]   = (df["heart_rate"] >= 100).astype(int)

    df["respiratory_score"] = df[["fever","cough","cold","breathlessness","sore_throat"]].sum(axis=1)
    df["gi_score"]          = df[["nausea","vomiting","diarrhea","loss_of_appetite"]].sum(axis=1)
    df["pain_score"]        = df[["headache","body_pain","chest_pain","dizziness"]].sum(axis=1)
    df["total_symptoms"]    = df[[
        "fever","cough","cold","headache","fatigue","body_pain","sore_throat",
        "nausea","vomiting","diarrhea","breathlessness","chest_pain",
        "dizziness","loss_of_appetite"
    ]].sum(axis=1)

    return df


def _balance_classes(df, target_col, target_n):
    print("[2/5] Balancing classes...")
    balanced = []
    for cls in df[target_col].unique():
        subset = df[df[target_col] == cls]
        if len(subset) < target_n:
            subset = resample(
                subset, replace=True,
                n_samples=target_n,
                random_state=RANDOM_STATE
            )
        balanced.append(subset)
    result = (pd.concat(balanced)
              .sample(frac=1, random_state=RANDOM_STATE)
              .reset_index(drop=True))
    print(f"      Balanced size: {result.shape}")
    return result


def _encode_and_split(df):
    print("[3/5] Encoding and splitting...")

    le = LabelEncoder()
    df["label"] = le.fit_transform(df[TARGET_COL])

    extended_features = FEATURE_COLS + [
        "age_group", "bmi_category", "temp_flag", "high_hr",
        "respiratory_score", "gi_score", "pain_score", "total_symptoms",
    ]

    X = df[extended_features].values
    y = df["label"].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y
    )

    print(f"      Train : {X_train.shape}")
    print(f"      Test  : {X_test.shape}")
    return X_train, X_test, y_train, y_test, le, scaler, extended_features



# SECTION 3 — MODEL BUILDING

def _build_ensemble():
    """Build lightweight model for cloud deployment."""
    print("[4/5] Building lightweight Random Forest model...")

    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        max_features="sqrt",
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return rf

def _train_and_evaluate(ensemble, X_train, X_test, y_train, y_test, le):
    print("[5/5] Training + calibrating probabilities...")
    print("      (this takes 1-2 minutes — please wait)")

    ensemble.fit(X_train, y_train)

    # Platt scaling — makes probability outputs more reliable
    calibrated = CalibratedClassifierCV(ensemble, method="sigmoid", cv=5)
    calibrated.fit(X_train, y_train)

    # Evaluation
    y_pred = calibrated.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)

    print(f"\n      Test Accuracy : {acc * 100:.2f}%")
    print("\n      Per-class breakdown:")
    print(classification_report(
        y_test, y_pred,
        target_names=le.classes_,
        digits=3
    ))

    # Quick cross-val check on RF alone
    cv = cross_val_score(
        RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1),
        X_train, y_train, cv=5, scoring="accuracy"
    )
    print(f"      5-Fold CV (RF baseline): {cv.mean()*100:.2f}% +/- {cv.std()*100:.2f}%")

    return calibrated



# SECTION 4 — PREDICTION FUNCTION

def predict_top3(model, scaler, le,
                 feature_values: dict,
                 dob: str,
                 gender: int,
                 disabled: bool = False) -> dict:
    

    # Calculate age from date of birth
    birth  = date.fromisoformat(dob)
    today  = date.today()
    age    = today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )

    # Build feature vector from input dict
    fv         = {col: feature_values.get(col, 0) for col in FEATURE_COLS}
    fv["age"]    = age
    fv["gender"] = gender

    # Compute engineered features (same as training)
    bmi  = fv.get("bmi", 22.0)
    temp = fv.get("body_temperature", 37.0)
    hr   = fv.get("heart_rate", 80)

    age_group = (
        0 if age <= 12 else
        1 if age <= 17 else
        2 if age <= 35 else
        3 if age <= 60 else 4
    )
    bmi_cat = (
        0 if bmi < 18.5 else
        1 if bmi < 25.0 else
        2 if bmi < 30.0 else 3
    )
    resp  = sum(fv.get(c, 0) for c in ["fever","cough","cold","breathlessness","sore_throat"])
    gi    = sum(fv.get(c, 0) for c in ["nausea","vomiting","diarrhea","loss_of_appetite"])
    pain  = sum(fv.get(c, 0) for c in ["headache","body_pain","chest_pain","dizziness"])
    total = sum(fv.get(c, 0) for c in [
        "fever","cough","cold","headache","fatigue","body_pain","sore_throat",
        "nausea","vomiting","diarrhea","breathlessness","chest_pain",
        "dizziness","loss_of_appetite"
    ])

    extra = [
        age_group, bmi_cat,
        int(temp >= 38.0), int(hr >= 100),
        resp, gi, pain, total
    ]

    # build final row and scale it
    row        = np.array([fv[c] for c in FEATURE_COLS] + extra).reshape(1, -1)
    row_scaled = scaler.transform(row)

    # get probabilities from calibrated ensemble
    proba   = model.predict_proba(row_scaled)[0]
    classes = le.classes_

    # get top-3
    top_idx = np.argsort(proba)[::-1][:3]

    return {
        "patient_info": {
            "age"     : age,
            "gender"  : "Male" if gender == 1 else "Female",
            "disabled": disabled,
        },
        "top3_predictions": [
            {
                "rank"            : i + 1,
                "disease"         : classes[idx],        
                "probability_pct" : round(proba[idx] * 100, 2),
            }
            for i, idx in enumerate(top_idx)
        ],
    }



# SECTION 5 — TRAINING SCRIPT

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("   DISEASE PREDICTION MODEL — TRAINING")
    print("=" * 60)
    print(f"   Dataset : {DATASET_PATH}")
    print(f"   Saving  : {BASE_DIR}")
    print("=" * 60)

    # Step 1-3: Load, balance, encode, split
    df = load_and_preprocess(DATASET_PATH)
    df = _balance_classes(df, TARGET_COL, TARGET_SAMPLES_PER_CLASS)
    X_train, X_test, y_train, y_test, le, scaler, feat_cols = _encode_and_split(df)

    # Step 4-5: Build and train
    ensemble = _build_ensemble()
    calibrated_model = _train_and_evaluate(ensemble, X_train, X_test, y_train, y_test, le)

    # Save the 3 pkl files Django will need
    with open(MODEL_SAVE_PATH, "wb") as f:
        pickle.dump({"model": calibrated_model, "feature_cols": feat_cols}, f)

    with open(LABEL_ENCODER_PATH, "wb") as f:
        pickle.dump(le, f)

    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    # Quick demo to verify everything works
    print("\n  VERIFICATION — sample prediction:")
    print("-" * 60)

    sample = {
        "bmi": 22.5, "body_temperature": 39.8, "heart_rate": 105,
        "fever": 1, "cough": 0, "cold": 0, "headache": 1,
        "fatigue": 1, "body_pain": 1, "sore_throat": 0,
        "nausea": 1, "vomiting": 0, "diarrhea": 0,
        "breathlessness": 0, "chest_pain": 0, "dizziness": 1,
        "loss_of_appetite": 1, "symptom_duration_days": 4,
        "pain_severity": 4, "chronic_disease": 0,
        "allergy_history": 0, "recent_travel": 1,
        "smoking": 0, "alcohol": 0,
    }

    result = predict_top3(
        model         = calibrated_model,
        scaler        = scaler,
        le            = le,
        feature_values= sample,
        dob           = "1995-06-15",
        gender        = 1,
        disabled      = False,
    )

    pi = result["patient_info"]
    print(f"  Patient : Age {pi['age']} | {pi['gender']}")
    print()
    for p in result["top3_predictions"]:
        print(f"  #{p['rank']} {p['disease']:<20} {p['probability_pct']:>6.2f}% ")

    