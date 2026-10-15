import os
import sys
import json

# Windows consoles default to cp1252 — an emoji in a log line raises
# UnicodeEncodeError. Force UTF-8 output so this script never crashes.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from transformers import ViTForImageClassification, ViTImageProcessor
from PIL import Image
import torch

# Paths relative to this script — works on any machine.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "NutriCare_Food_Classifier_Final")
TEST_IMAGES_DIR = os.path.join(os.path.dirname(BASE_DIR), "test_images")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def pick_image():
    """CLI argument, else the first image found in ../test_images."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    if os.path.isdir(TEST_IMAGES_DIR):
        for name in sorted(os.listdir(TEST_IMAGES_DIR)):
            if name.lower().endswith(IMAGE_EXTENSIONS):
                return os.path.join(TEST_IMAGES_DIR, name)

    raise SystemExit(
        "No test image found. Pass one: python test_food_model.py <image>"
    )

# Load model and processor
print("Loading model...")

processor = ViTImageProcessor.from_pretrained(MODEL_PATH)

model = ViTForImageClassification.from_pretrained(MODEL_PATH)
model.eval()

# Load class names
with open(os.path.join(MODEL_PATH, "class_names.json"), "r", encoding="utf-8") as f:
    class_names = json.load(f)

print("✅ Model loaded")
print("Classes:", len(class_names))

# Image to classify (defaults to the first file in ../test_images)
IMAGE_PATH = pick_image()
print("Image   :", IMAGE_PATH)

image = Image.open(IMAGE_PATH).convert("RGB")

# Preprocess
inputs = processor(images=image, return_tensors="pt")

# Prediction
with torch.no_grad():
    outputs = model(**inputs)

# Get probabilities
probabilities = torch.softmax(outputs.logits, dim=-1)

# Best prediction
predicted_id = torch.argmax(probabilities, dim=-1).item()
confidence = probabilities[0][predicted_id].item()

predicted_food = class_names[predicted_id]

print("\n==============================")
print("FOOD PREDICTION")
print("==============================")
print("Food       :", predicted_food)
print("Confidence :", f"{confidence * 100:.2f}%")
print("Class ID   :", predicted_id)