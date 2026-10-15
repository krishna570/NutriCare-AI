import os
import re
import pandas as pd

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


# ============================================
# PATHS
# ============================================

# Folder that holds this script (…/RAG) — works on any machine.
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

CSV_PATH = os.path.join(
    BASE_PATH,
    "data",
    "NutriCare_AI_Master_ML_Ready_v18 (1).csv"
)

CHROMA_PATH = os.path.join(BASE_PATH, "chroma_db")


# ============================================
# HEADER
# ============================================

print("\n========================================")
print("       NUTRICARE AI - RAG TEST")
print("========================================")


# ============================================
# LOAD MASTER CSV
# ============================================

print("\nLoading nutrition dataset...")

df = pd.read_csv(CSV_PATH)

print("Dataset loaded!")
print("Rows:", len(df))

if "Unnamed: 33" in df.columns:
    df = df.drop(columns=["Unnamed: 33"])

df["Food_Name"] = df["Food_Name"].fillna("").astype(str)


# ============================================
# TEXT NORMALIZATION
# ============================================

def normalize(text):

    text = str(text).lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


df["Clean_Food_Name"] = df["Food_Name"].apply(normalize)


# ============================================
# FIND FOOD
# ============================================

def find_food(question):

    question_clean = normalize(question)

    matches = []

    for _, row in df.iterrows():

        food_name = row["Clean_Food_Name"]

        if not food_name:
            continue

        # Full food name match
        if re.search(
            r"\b" + re.escape(food_name) + r"\b",
            question_clean
        ):
            matches.append(row)
            continue

        # Match first/main food word
        food_words = food_name.split()

        if food_words:

            main_food = food_words[0]

            if len(main_food) >= 3:

                if re.search(
                    r"\b" + re.escape(main_food) + r"\b",
                    question_clean
                ):
                    matches.append(row)

    return matches


# ============================================
# SELECT BEST RECORD
# ============================================

def select_best_record(matches):

    if not matches:
        return None

    result = pd.DataFrame(matches)

    # Prefer National record
    national = result[
        result["Region"]
        .fillna("")
        .astype(str)
        .str.lower()
        .str.contains("national")
    ]

    if not national.empty:

        return national.iloc[0]

    return result.iloc[0]


# ============================================
# DISPLAY FOOD
# ============================================

def display_food(row):

    print("\n========================================")
    print("          FOOD INFORMATION")
    print("========================================")

    print("Food ID:", row.get("Food_ID", "N/A"))
    print("Food Name:", row.get("Food_Name", "N/A"))
    print("Food Code:", row.get("Food_Code", "N/A"))

    print("Category:", row.get("Category", "N/A"))
    print("Region:", row.get("Region", "N/A"))

    print("\n---------- NUTRITION ----------")

    print(
        "Serving Size:",
        row.get("Serving_Size_g", "N/A"),
        "g"
    )

    print(
        "Energy:",
        row.get("Energy_kcal", "N/A"),
        "kcal"
    )

    print(
        "Protein:",
        row.get("Protein_g", "N/A"),
        "g"
    )

    print(
        "Total Fat:",
        row.get("Total_Fat_g", "N/A"),
        "g"
    )

    print(
        "Carbohydrate:",
        row.get("Carbohydrate_g", "N/A"),
        "g"
    )

    print(
        "Free Sugars:",
        row.get("Total_Free_Sugars_g", "N/A"),
        "g"
    )

    print(
        "Dietary Fibre:",
        row.get("Dietary_Fibre_g", "N/A"),
        "g"
    )

    print(
        "Saturated Fat:",
        row.get("Saturated_Fat_g", "N/A"),
        "g"
    )

    print(
        "Sodium:",
        row.get("Sodium_mg", "N/A"),
        "mg"
    )

    print(
        "Potassium:",
        row.get("Potassium_mg", "N/A"),
        "mg"
    )

    print(
        "Caffeine:",
        row.get("Caffeine_mg", "N/A"),
        "mg"
    )

    print("\n---------- SUGAR DETAILS ----------")

    print(
        "Lactose:",
        row.get("Lactose_g", "N/A"),
        "g"
    )

    print(
        "Sucrose:",
        row.get("Sucrose_g", "N/A"),
        "g"
    )

    print(
        "Fructose:",
        row.get("Fructose_g", "N/A"),
        "g"
    )

    print(
        "Glucose:",
        row.get("Glucose_g", "N/A"),
        "g"
    )

    print("\n---------- CLASSIFICATION ----------")

    print(
        "Diabetes:",
        row.get("Diabetes_Classification", "N/A")
    )

    print(
        "Hypertension:",
        row.get("Hypertension_Classification", "N/A")
    )

    print(
        "Obesity:",
        row.get("Obesity_Classification", "N/A")
    )

    print("\n---------- OTHER ----------")

    print(
        "Household Portion:",
        row.get("Household_Portion", "N/A")
    )

    print(
        "Cooking Method:",
        row.get("Cooking_Method", "N/A")
    )

    print(
        "Age Guidance:",
        row.get("Age_Group_Guidance", "N/A")
    )

    print(
        "Verification:",
        row.get("Verification_Status", "N/A")
    )

    print(
        "Source:",
        row.get("Source", "N/A")
    )


# ============================================
# LOAD CHROMA
# ============================================

print("\nLoading ChromaDB...")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(
    persist_directory=CHROMA_PATH,
    embedding_function=embeddings
)

print("ChromaDB loaded successfully!")


# ============================================
# SEMANTIC SEARCH
# ============================================

def semantic_search(question):

    print("\nNo exact food found.")
    print("Using semantic search...")

    results = vectorstore.similarity_search(
        question,
        k=5
    )

    if not results:

        print("\nNo relevant information found.")

        return

    print("\n========================================")
    print("       SEMANTIC SEARCH RESULTS")
    print("========================================")

    for i, doc in enumerate(results, 1):

        food_id = doc.metadata.get(
            "Food_ID",
            ""
        )

        food_name = doc.metadata.get(
            "Food_Name",
            ""
        )

        print(
            f"\n========== RESULT {i} =========="
        )

        print("Food ID:", food_id)
        print("Food Name:", food_name)

        # Find complete record in CSV
        if food_id:

            record = df[
                df["Food_ID"].astype(str)
                == str(food_id)
            ]

            if not record.empty:

                row = record.iloc[0]

                print(
                    "Category:",
                    row.get("Category", "N/A")
                )

                print(
                    "Region:",
                    row.get("Region", "N/A")
                )

                print(
                    "Energy:",
                    row.get("Energy_kcal", "N/A"),
                    "kcal"
                )

                print(
                    "Protein:",
                    row.get("Protein_g", "N/A"),
                    "g"
                )


# ============================================
# START RAG
# ============================================

print("\n========================================")
print("       NUTRICARE AI READY")
print("========================================")

print("\nAsk questions such as:")

print("  What is the nutrition information of poha?")
print("  How many calories are in poha?")
print("  How much protein does poha contain?")
print("  Tell me about idli")
print("  What is the nutrition of ragi?")

print("\nType 'exit' to stop.")


# ============================================
# CHAT LOOP
# ============================================

while True:

    try:
        question = input("\nAsk NutriCare: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        break

    if question.lower() in ["exit", "quit"]:

        print("\nNutriCare RAG stopped.")

        break

    if not question:

        print("\nPlease enter a question.")

        continue

    print("\nSearching nutrition database...")

    matches = find_food(question)

    # ========================================
    # EXACT MATCH
    # ========================================

    if matches:

        print(
            "\nExact food match found:",
            len(matches),
            "record(s)"
        )

        best_record = select_best_record(matches)

        if best_record is not None:

            display_food(best_record)

        continue

    # ========================================
    # SEMANTIC SEARCH
    # ========================================

    semantic_search(question)