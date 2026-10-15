from services.ml_service import predict_nutrition

poha = {
    "Serving_Size_g": 100,
    "Protein_g": 7.44,
    "Total_Fat_g": 1.14,
    "Carbohydrate_g": 76.75,
    "Total_Free_Sugars_g": 0,
    "Lactose_g": None,
    "Sucrose_g": None,
    "Fructose_g": None,
    "Glucose_g": None,
    "Caffeine_mg": 0,
    "Total_Polyphenols_mg": None,
    "Sodium_mg": 10,
    "Potassium_mg": 33,
    "Dietary_Fibre_g": 3.46,
    "Saturated_Fat_g": 0.13,
    "Category": "Cereals and Millets",
    "Region": "National Average",
    "Cooking_Method": "Stir-fried / Sautéed"
}

print("\nTesting NutriCare AI ML Model...\n")

result = predict_nutrition(poha)

print("Prediction Result:")
print(result)
