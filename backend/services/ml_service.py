import os
import sys

# Windows consoles default to cp1252 — an emoji in a log line raises
# UnicodeEncodeError. Force UTF-8 output so loading never crashes.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import joblib
import pandas as pd


# ============================================================
# MODEL PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "NutriCare_AI_Combined_ML_Model.joblib"
)


# ============================================================
# LOAD NUTRICARE ML MODEL
# ============================================================

print("Loading NutriCare AI ML model...")

models = joblib.load(MODEL_PATH)

energy_model = models["energy_model"]
diabetes_model = models["diabetes_model"]
hypertension_model = models["hypertension_model"]
obesity_model = models["obesity_model"]

FEATURES = models["features"]

print("✅ NutriCare AI ML model loaded successfully!")


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_nutrition(food_data: dict):

    # Create DataFrame using the same feature names
    input_data = pd.DataFrame(
        [food_data],
        columns=FEATURES
    )

    # -----------------------------------------
    # Energy prediction
    # -----------------------------------------

    energy_prediction = energy_model.predict(
        input_data
    )[0]

    # -----------------------------------------
    # Diabetes classification
    # -----------------------------------------

    diabetes_prediction = diabetes_model.predict(
        input_data
    )[0]

    # -----------------------------------------
    # Hypertension classification
    # -----------------------------------------

    hypertension_prediction = hypertension_model.predict(
        input_data
    )[0]

    # -----------------------------------------
    # Obesity classification
    # -----------------------------------------

    obesity_prediction = obesity_model.predict(
        input_data
    )[0]

    return {
        "energy_kcal": round(float(energy_prediction), 2),

        "diabetes_classification":
            str(diabetes_prediction),

        "hypertension_classification":
            str(hypertension_prediction),

        "obesity_classification":
            str(obesity_prediction)
    }