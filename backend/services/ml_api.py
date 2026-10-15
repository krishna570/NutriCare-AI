import base64
import io
import json
import os
import sys

# Windows consoles default to cp1252 — an emoji in a log line raises
# UnicodeEncodeError and would break model loading. Force UTF-8 output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import torch
import joblib
import pandas as pd

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor

# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOOD_MODEL_PATH = os.path.join(
    BASE_DIR, "models", "NutriCare_Food_Classifier_Final"
)

COMBINED_MODEL_PATH = os.path.join(
    BASE_DIR, "models", "NutriCare_AI_Combined_ML_Model.joblib"
)

# ============================================================
# NUTRITION LOOKUP TABLE  (per 100g / standard serving)
# Maps each of the 43 Indian food class names to estimated
# nutrition values so the frontend can display real numbers
# right after food detection without any extra network call.
# ============================================================

NUTRITION_DB = {
    "aloo_gobi":         {"kcal": 95,  "protein_g": 3.0, "carbs_g": 14.0, "fat_g": 3.5, "sugar_g": 2.5, "fibre_g": 3.0},
    "aloo_masala":       {"kcal": 130, "protein_g": 3.0, "carbs_g": 20.0, "fat_g": 4.5, "sugar_g": 2.0, "fibre_g": 2.5},
    "bhindi_masala":     {"kcal": 90,  "protein_g": 2.5, "carbs_g": 9.0,  "fat_g": 5.0, "sugar_g": 2.0, "fibre_g": 3.5},
    "biryani":           {"kcal": 320, "protein_g": 14.0,"carbs_g": 45.0, "fat_g": 9.0, "sugar_g": 2.0, "fibre_g": 1.5},
    "burger":            {"kcal": 295, "protein_g": 13.0,"carbs_g": 30.0, "fat_g": 13.0,"sugar_g": 6.0, "fibre_g": 1.5},
    "butter_naan":       {"kcal": 310, "protein_g": 8.0, "carbs_g": 52.0, "fat_g": 8.0, "sugar_g": 3.0, "fibre_g": 2.0},
    "chai":              {"kcal": 60,  "protein_g": 2.0, "carbs_g": 8.0,  "fat_g": 2.0, "sugar_g": 7.0, "fibre_g": 0.0},
    "chapati":           {"kcal": 104, "protein_g": 3.0, "carbs_g": 18.0, "fat_g": 2.5, "sugar_g": 0.5, "fibre_g": 2.5},
    "chicken_curry":     {"kcal": 250, "protein_g": 22.0,"carbs_g": 8.0,  "fat_g": 14.0,"sugar_g": 3.0, "fibre_g": 1.5},
    "chole":             {"kcal": 180, "protein_g": 9.0, "carbs_g": 27.0, "fat_g": 5.0, "sugar_g": 4.0, "fibre_g": 7.5},
    "chole_bhature":     {"kcal": 450, "protein_g": 13.0,"carbs_g": 65.0, "fat_g": 16.0,"sugar_g": 4.0, "fibre_g": 7.0},
    "coconut_chutney":   {"kcal": 100, "protein_g": 1.5, "carbs_g": 5.0,  "fat_g": 9.0, "sugar_g": 2.0, "fibre_g": 2.5},
    "dal_makhani":       {"kcal": 200, "protein_g": 9.0, "carbs_g": 22.0, "fat_g": 9.0, "sugar_g": 3.0, "fibre_g": 6.0},
    "dhokla":            {"kcal": 155, "protein_g": 6.5, "carbs_g": 25.0, "fat_g": 3.5, "sugar_g": 4.0, "fibre_g": 2.0},
    "dum_aloo":          {"kcal": 195, "protein_g": 4.0, "carbs_g": 28.0, "fat_g": 8.0, "sugar_g": 3.0, "fibre_g": 3.5},
    "fish_curry":        {"kcal": 220, "protein_g": 20.0,"carbs_g": 8.0,  "fat_g": 12.0,"sugar_g": 2.5, "fibre_g": 1.0},
    "fried_rice":        {"kcal": 250, "protein_g": 6.0, "carbs_g": 42.0, "fat_g": 6.5, "sugar_g": 2.0, "fibre_g": 1.5},
    "ghevar":            {"kcal": 380, "protein_g": 6.0, "carbs_g": 55.0, "fat_g": 16.0,"sugar_g": 30.0,"fibre_g": 1.0},
    "green_chutney":     {"kcal": 50,  "protein_g": 2.0, "carbs_g": 5.0,  "fat_g": 2.5, "sugar_g": 2.0, "fibre_g": 2.5},
    "gulab_jamun":       {"kcal": 380, "protein_g": 5.0, "carbs_g": 55.0, "fat_g": 16.0,"sugar_g": 40.0,"fibre_g": 0.5},
    "idli":              {"kcal": 39,  "protein_g": 2.0, "carbs_g": 8.0,  "fat_g": 0.2, "sugar_g": 0.5, "fibre_g": 0.5},
    "jalebi":            {"kcal": 370, "protein_g": 3.5, "carbs_g": 58.0, "fat_g": 14.0,"sugar_g": 45.0,"fibre_g": 0.5},
    "kaathi_rolls":      {"kcal": 280, "protein_g": 12.0,"carbs_g": 36.0, "fat_g": 9.0, "sugar_g": 4.0, "fibre_g": 2.5},
    "kadai_paneer":      {"kcal": 260, "protein_g": 12.0,"carbs_g": 10.0, "fat_g": 19.0,"sugar_g": 4.0, "fibre_g": 2.0},
    "kebab":             {"kcal": 240, "protein_g": 18.0,"carbs_g": 12.0, "fat_g": 14.0,"sugar_g": 2.0, "fibre_g": 1.0},
    "kheer":             {"kcal": 185, "protein_g": 5.0, "carbs_g": 30.0, "fat_g": 6.0, "sugar_g": 22.0,"fibre_g": 0.5},
    "kulfi":             {"kcal": 250, "protein_g": 6.0, "carbs_g": 32.0, "fat_g": 12.0,"sugar_g": 28.0,"fibre_g": 0.0},
    "lassi":             {"kcal": 130, "protein_g": 5.0, "carbs_g": 18.0, "fat_g": 4.5, "sugar_g": 16.0,"fibre_g": 0.0},
    "masala_dosa":       {"kcal": 300, "protein_g": 7.0, "carbs_g": 48.0, "fat_g": 9.0, "sugar_g": 3.0, "fibre_g": 3.5},
    "modak":             {"kcal": 280, "protein_g": 4.5, "carbs_g": 42.0, "fat_g": 11.0,"sugar_g": 20.0,"fibre_g": 2.0},
    "momos":             {"kcal": 180, "protein_g": 10.0,"carbs_g": 25.0, "fat_g": 4.5, "sugar_g": 2.0, "fibre_g": 2.0},
    "mutton_curry":      {"kcal": 290, "protein_g": 24.0,"carbs_g": 8.0,  "fat_g": 18.0,"sugar_g": 3.0, "fibre_g": 1.0},
    "paani_puri":        {"kcal": 180, "protein_g": 4.0, "carbs_g": 30.0, "fat_g": 5.0, "sugar_g": 5.0, "fibre_g": 2.5},
    "pakode":            {"kcal": 310, "protein_g": 7.0, "carbs_g": 35.0, "fat_g": 16.0,"sugar_g": 2.0, "fibre_g": 3.0},
    "palak_paneer":      {"kcal": 240, "protein_g": 10.0,"carbs_g": 10.0, "fat_g": 18.0,"sugar_g": 3.0, "fibre_g": 3.0},
    "pav_bhaji":         {"kcal": 350, "protein_g": 9.0, "carbs_g": 52.0, "fat_g": 12.0,"sugar_g": 8.0, "fibre_g": 5.0},
    "pizza":             {"kcal": 285, "protein_g": 12.0,"carbs_g": 34.0, "fat_g": 11.0,"sugar_g": 4.0, "fibre_g": 2.0},
    "poha":              {"kcal": 180, "protein_g": 4.0, "carbs_g": 32.0, "fat_g": 4.5, "sugar_g": 2.0, "fibre_g": 2.5},
    "rajma_curry":       {"kcal": 185, "protein_g": 9.0, "carbs_g": 29.0, "fat_g": 4.0, "sugar_g": 3.0, "fibre_g": 7.0},
    "ras_malai":         {"kcal": 220, "protein_g": 7.0, "carbs_g": 26.0, "fat_g": 10.0,"sugar_g": 22.0,"fibre_g": 0.0},
    "samosa":            {"kcal": 260, "protein_g": 5.0, "carbs_g": 32.0, "fat_g": 13.0,"sugar_g": 2.0, "fibre_g": 2.5},
    "shahi_paneer":      {"kcal": 290, "protein_g": 11.0,"carbs_g": 12.0, "fat_g": 22.0,"sugar_g": 5.0, "fibre_g": 1.5},
    "white_rice":        {"kcal": 210, "protein_g": 4.0, "carbs_g": 45.0, "fat_g": 0.5, "sugar_g": 0.0, "fibre_g": 0.5},
}

# Foods that may raise diabetes / hypertension / obesity risk — for badge display
HIGH_SUGAR_FOODS   = {"gulab_jamun","jalebi","ghevar","kheer","kulfi","ras_malai","modak","lassi","chai"}
HIGH_SODIUM_FOODS  = {"paani_puri","pakode","burger","pizza","pav_bhaji","momos","kebab","chole_bhature"}
HIGH_CALORIE_FOODS = {"biryani","butter_naan","chole_bhature","palak_paneer","kadai_paneer","shahi_paneer",
                      "gulab_jamun","jalebi","ghevar","mutton_curry","pizza","burger","pav_bhaji"}

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="NutriCare AI ML Service", version="2.0.0")

# ============================================================
# LAZY MODEL LOADERS  (load only when first request arrives)
# ============================================================

_food_processor = None
_food_model = None
_food_class_names = None
_combined_models = None


def load_food_classifier():
    global _food_processor, _food_model, _food_class_names
    if _food_model is None:
        print("🔄 Loading NutriCare ViT Food Classifier...")
        _food_processor = ViTImageProcessor.from_pretrained(FOOD_MODEL_PATH)
        _food_model = ViTForImageClassification.from_pretrained(FOOD_MODEL_PATH)
        _food_model.eval()
        with open(os.path.join(FOOD_MODEL_PATH, "class_names.json"), "r") as f:
            _food_class_names = json.load(f)
        print(f"✅ Food Classifier loaded — {len(_food_class_names)} classes")


def load_combined_model():
    global _combined_models
    if _combined_models is None:
        print("🔄 Loading NutriCare Combined ML Model...")
        _combined_models = joblib.load(COMBINED_MODEL_PATH)
        print("✅ Combined ML Model loaded")


# ============================================================
# SCHEMAS
# ============================================================

class FoodImageRequest(BaseModel):
    image_base64: str   # pure base64, no data-URI prefix needed


class NutritionData(BaseModel):
    Serving_Size_g: float
    Protein_g: float
    Total_Fat_g: float
    Carbohydrate_g: float
    Total_Free_Sugars_g: float
    Lactose_g: float = 0.0
    Sucrose_g: float = 0.0
    Fructose_g: float = 0.0
    Glucose_g: float = 0.0
    Caffeine_mg: float = 0.0
    Total_Polyphenols_mg: float = 0.0
    Sodium_mg: float = 0.0
    Potassium_mg: float = 0.0
    Dietary_Fibre_g: float = 0.0
    Saturated_Fat_g: float = 0.0
    Category: str
    Region: str
    Cooking_Method: str


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "NutriCare AI ML Service",
        "endpoints": ["/predict-food", "/predict"]
    }


@app.post("/predict-food")
def predict_food(req: FoodImageRequest):
    """
    Accepts a base64-encoded food image.
    Returns: food name, confidence %, top-5 predictions, nutrition estimates.
    """
    # ── 1. Load model (lazy) ──────────────────────────────────
    try:
        load_food_classifier()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load food classifier: {str(e)}")

    # ── 2. Decode image ───────────────────────────────────────
    try:
        # Strip data-URI prefix if present  e.g. "data:image/jpeg;base64,..."
        b64_data = req.image_base64
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]

        image_bytes = base64.b64decode(b64_data)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")

    # ── 3. Run ViT inference ──────────────────────────────────
    try:
        inputs = _food_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = _food_model(**inputs)

        probabilities = torch.softmax(outputs.logits, dim=-1)[0]
        top5 = torch.topk(probabilities, k=5)

        predicted_idx = top5.indices[0].item()
        confidence    = top5.values[0].item()
        food_name     = _food_class_names[predicted_idx]

        top5_list = [
            {
                "rank": i + 1,
                "food":       _food_class_names[top5.indices[i].item()],
                "confidence": round(top5.values[i].item() * 100, 2)
            }
            for i in range(5)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model inference failed: {str(e)}")

    # ── 4. Nutrition lookup ───────────────────────────────────
    nutrition = NUTRITION_DB.get(food_name, {
        "kcal": 0, "protein_g": 0, "carbs_g": 0,
        "fat_g": 0, "sugar_g": 0, "fibre_g": 0
    })

    # ── 5. Risk flags ─────────────────────────────────────────
    risk_flags = {
        "high_sugar":    food_name in HIGH_SUGAR_FOODS,
        "high_sodium":   food_name in HIGH_SODIUM_FOODS,
        "high_calories": food_name in HIGH_CALORIE_FOODS,
    }

    return {
        "food_name":    food_name,
        "display_name": food_name.replace("_", " ").title(),
        "confidence":   round(confidence * 100, 2),
        "top5":         top5_list,
        "nutrition":    nutrition,
        "risk_flags":   risk_flags,
        "model":        "NutriCare ViT Food Classifier (43 Indian Foods)"
    }


@app.post("/predict")
def predict_nutrition(data: NutritionData):
    """
    Accepts manual nutritional input.
    Returns energy (kcal) + diabetes / hypertension / obesity classification.
    """
    try:
        load_combined_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load combined model: {str(e)}")

    features  = _combined_models["features"]
    input_row = pd.DataFrame([data.model_dump()], columns=features)

    energy_pred      = _combined_models["energy_model"].predict(input_row)[0]
    diabetes_pred    = _combined_models["diabetes_model"].predict(input_row)[0]
    hypertension_pred= _combined_models["hypertension_model"].predict(input_row)[0]
    obesity_pred     = _combined_models["obesity_model"].predict(input_row)[0]

    return {
        "energy_kcal":               round(float(energy_pred), 2),
        "diabetes_classification":   str(diabetes_pred),
        "hypertension_classification": str(hypertension_pred),
        "obesity_classification":    str(obesity_pred),
    }