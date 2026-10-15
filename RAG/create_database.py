import os
import pandas as pd

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


# ============================================================
# NUTRICARE AI - RAG DATABASE CREATION
# ============================================================

# Folder that holds this script (…/RAG) — works on any machine.
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

MASTER_CSV = os.path.join(
    BASE_PATH,
    "data",
    "NutriCare_AI_Master_ML_Ready_v18 (1).csv"
)

QA_CSV = os.path.join(
    BASE_PATH,
    "data",
    "NutriCare_RAG_QA_Dataset.csv"
)

CHROMA_PATH = os.path.join(
    BASE_PATH,
    "chroma_db"
)


print("\n========================================")
print("       NUTRICARE AI - RAG")
print("========================================")


# ============================================================
# 1. LOAD MASTER NUTRITION DATASET
# ============================================================

print("\n[1/5] Loading master nutrition dataset...")

master_df = pd.read_csv(MASTER_CSV)

print("Master dataset loaded!")
print("Rows:", len(master_df))
print("Columns:", len(master_df.columns))


# Remove unwanted column if present
if "Unnamed: 33" in master_df.columns:
    master_df = master_df.drop(columns=["Unnamed: 33"])


# ============================================================
# 2. LOAD Q&A DATASET
# ============================================================

print("\n[2/5] Loading Q&A dataset...")

qa_df = pd.read_csv(QA_CSV)

print("Q&A dataset loaded!")
print("Rows:", len(qa_df))
print("Columns:", len(qa_df.columns))


# ============================================================
# 3. CREATE DOCUMENTS
# ============================================================

print("\n[3/5] Creating RAG documents...")

documents = []


# ------------------------------------------------------------
# MASTER NUTRITION RECORDS
# ------------------------------------------------------------

for _, row in master_df.iterrows():

    text = f"""
Food Information

Food ID: {row.get('Food_ID', '')}
Food Name: {row.get('Food_Name', '')}
Food Code: {row.get('Food_Code', '')}

Region: {row.get('Region', '')}
Category: {row.get('Category', '')}

Serving Size: {row.get('Serving_Size_g', '')} g

Energy: {row.get('Energy_kcal', '')} kcal
Energy: {row.get('Energy_kJ', '')} kJ

Protein: {row.get('Protein_g', '')} g
Total Fat: {row.get('Total_Fat_g', '')} g
Carbohydrate: {row.get('Carbohydrate_g', '')} g

Total Free Sugars: {row.get('Total_Free_Sugars_g', '')} g

Lactose: {row.get('Lactose_g', '')} g
Sucrose: {row.get('Sucrose_g', '')} g
Fructose: {row.get('Fructose_g', '')} g
Glucose: {row.get('Glucose_g', '')} g

Caffeine: {row.get('Caffeine_mg', '')} mg
Total Polyphenols: {row.get('Total_Polyphenols_mg', '')} mg

Sodium: {row.get('Sodium_mg', '')} mg
Potassium: {row.get('Potassium_mg', '')} mg

Dietary Fibre: {row.get('Dietary_Fibre_g', '')} g
Saturated Fat: {row.get('Saturated_Fat_g', '')} g

Diabetes Classification:
{row.get('Diabetes_Classification', '')}

Hypertension Classification:
{row.get('Hypertension_Classification', '')}

Obesity Classification:
{row.get('Obesity_Classification', '')}

Household Portion:
{row.get('Household_Portion', '')}

Cooking Method:
{row.get('Cooking_Method', '')}

Age Group Suitability:
{row.get('Age_Group_Suitability', '')}

Age Group Guidance:
{row.get('Age_Group_Guidance', '')}

18-29 Years:
{row.get('Suitable_18_29_Years', '')}

30-44 Years:
{row.get('Suitable_30_44_Years', '')}

45-59 Years:
{row.get('Suitable_45_59_Years', '')}

60-74 Years:
{row.get('Suitable_60_74_Years', '')}

75+ Years:
{row.get('Suitable_75_Plus_Years', '')}

Source:
{row.get('Source', '')}

Verification Status:
{row.get('Verification_Status', '')}

Notes:
{row.get('Notes', '')}
"""

    documents.append(
        Document(
            page_content=text,
            metadata={
                "type": "nutrition",
                "Food_ID": str(row.get("Food_ID", "")),
                "Food_Name": str(row.get("Food_Name", "")),
                "Category": str(row.get("Category", "")),
                "Region": str(row.get("Region", ""))
            }
        )
    )


# ------------------------------------------------------------
# Q&A RECORDS
# ------------------------------------------------------------

for _, row in qa_df.iterrows():

    question = str(row.get("Question", ""))
    answer = str(row.get("Answer", ""))

    text = f"""
Question:
{question}

Answer:
{answer}

Food ID:
{row.get('Food_ID', '')}

Food Name:
{row.get('Food_Name', '')}

Question Type:
{row.get('Question_Type', '')}

Source:
{row.get('Source', '')}
"""

    documents.append(
        Document(
            page_content=text,
            metadata={
                "type": "qa",
                "Food_ID": str(row.get("Food_ID", "")),
                "Food_Name": str(row.get("Food_Name", "")),
                "Question_Type": str(row.get("Question_Type", ""))
            }
        )
    )


print("Nutrition documents:", len(master_df))
print("Q&A documents:", len(qa_df))
print("Total RAG documents:", len(documents))


# ============================================================
# 4. LOAD EMBEDDING MODEL
# ============================================================

print("\n[4/5] Loading embedding model...")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

print("Embedding model loaded successfully!")


# ============================================================
# 5. CREATE CHROMADB
# ============================================================

print("\n[5/5] Creating ChromaDB...")
print("This may take a few minutes because we have many documents.")


vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embeddings,
    persist_directory=CHROMA_PATH
)


print("\n========================================")
print("       RAG DATABASE CREATED!")
print("========================================")

print("Nutrition records:", len(master_df))
print("Q&A records:", len(qa_df))
print("Total documents:", len(documents))

print("\nChromaDB location:")
print(CHROMA_PATH)

print("\n========================================")
print("              SUCCESS!")
print("========================================")