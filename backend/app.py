"""
NutriCare AI - FastAPI Backend with MongoDB Connection
Features:
- MongoDB Persistence (nutricare_db: users, otps, admins)
- Admin Authentication (Email & Password)
- Email OTP Verification during Signup (API Key / SMTP / Console)
- User Registration & Login Authentication
- Admin Dashboard Analytics & Database Schema Inspector
"""

import os
import sys
import json
import random
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Windows consoles default to cp1252 — an emoji in a log line raises
# UnicodeEncodeError. Force UTF-8 output so the API never crashes on logging.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load environment variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nutricare_db")
PORT = int(os.getenv("PORT", 8000))

# Admin Credentials (Default: admin@nutricare.ai / admin123)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@nutricare.ai").lower().strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Email Provider Configuration (Resend API or SMTP)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()

app = FastAPI(
    title="NutriCare AI API",
    description="Backend API connected to MongoDB for User Registration, OTP Verification, and Admin Panel",
    version="2.0.0"
)

# Enable CORS for frontend web pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage fallback for OTPs if MongoDB is offline
local_otps: Dict[str, dict] = {}

# =========================================================
# MONGODB CONNECTION & INITIALIZATION
# =========================================================
mongo_client = None
db = None
users_col = None
otps_col = None
admins_col = None

def get_database():
    global mongo_client, db, users_col, otps_col, admins_col
    try:
        if mongo_client is None:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            mongo_client = client
            db = mongo_client[DB_NAME]

            # 1. Users collection
            users_col = db["users"]
            users_col.create_index("email", unique=True)

            # 2. OTPs collection (with TTL index for automatic expiry)
            otps_col = db["otps"]
            try:
                otps_col.create_index("email")
                otps_col.create_index("createdAt", expireAfterSeconds=300)  # Auto-delete after 5 min
            except Exception:
                pass

            # 3. Admins collection
            admins_col = db["admins"]
            admins_col.create_index("email", unique=True)

            # Seed default admin if not existing
            if admins_col.count_documents({"email": ADMIN_EMAIL}) == 0:
                admins_col.insert_one({
                    "email": ADMIN_EMAIL,
                    "password": ADMIN_PASSWORD,
                    "role": "superadmin",
                    "createdAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                })

            print(f"✅ Connected to MongoDB successfully at {MONGODB_URI} (DB: {DB_NAME})")
        return db
    except Exception as e:
        mongo_client = None
        db = None
        users_col = None
        otps_col = None
        admins_col = None
        print(f"⚠️ MongoDB not reachable at {MONGODB_URI} ({type(e).__name__}). Running in fallback mode.")
        return None


@app.on_event("startup")
def startup_event():
    get_database()


# =========================================================
# EMAIL OTP DISPATCHER
# =========================================================
def send_otp_email(to_email: str, otp: str) -> bool:
    """
    Sends 6-digit OTP code to the user's email address.
    Supports Resend API, standard SMTP, and always logs in the terminal.
    """
    subject = f"NutriCare AI - Your Verification Code is {otp}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 25px; border: 1px solid #d8e8df; border-radius: 16px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #13a957; margin: 0;">🥗 NutriCare AI</h2>
            <p style="color: #64756c; font-size: 13px; margin-top: 4px;">Smart Nutrition & Wellness Companion</p>
        </div>
        <p style="color: #24352c; font-size: 14px;">Hello,</p>
        <p style="color: #24352c; font-size: 14px; line-height: 1.5;">
            Thank you for creating an account with NutriCare AI. Please use the following 6-digit verification code to complete your registration:
        </p>
        <div style="text-align: center; margin: 25px 0;">
            <span style="display: inline-block; font-size: 32px; font-weight: 800; letter-spacing: 6px; padding: 12px 24px; background: #effaf4; color: #176b3c; border-radius: 12px; border: 1px solid #a7f3d0;">
                {otp}
            </span>
        </div>
        <p style="color: #64756c; font-size: 12px; line-height: 1.4;">
            ⏱️ This code is valid for <strong>5 minutes</strong>. If you did not request this code, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #e7eee9; margin: 20px 0;">
        <p style="color: #9aa59f; font-size: 11px; text-align: center;">
            🔒 Protected by NutriCare AI Security. Keep your code private.
        </p>
    </div>
    """

    # Always print clearly in the backend console for immediate developer testing
    print("\n" + "=" * 60)
    print(f"🔑 [NUTRICARE AI OTP CODE] --> {to_email}")
    print(f"👉 CODE: {otp}  (Valid for 5 minutes)")
    print("=" * 60 + "\n")

    # 1. Try Resend API if API Key is configured
    if RESEND_API_KEY:
        try:
            url = "https://api.resend.com/emails"
            payload = json.dumps({
                "from": "NutriCare AI <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in (200, 201):
                    print(f"✉️ OTP successfully delivered via Resend API to {to_email}")
                    return True
        except Exception as e:
            print(f"⚠️ Resend API email error: {e}")

    # 2. Try SMTP if configured
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"NutriCare AI <{SMTP_USER}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to_email, msg.as_string())
            print(f"✉️ OTP successfully delivered via SMTP to {to_email}")
            return True
        except Exception as e:
            print(f"⚠️ SMTP email error: {e}")

    return False


# =========================================================
# PYDANTIC SCHEMAS
# =========================================================
class SendOtpSchema(BaseModel):
    email: EmailStr


class VerifyOtpSchema(BaseModel):
    email: EmailStr
    otp: str


class UserRegisterSchema(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    age: int
    gender: str
    height: float
    weight: float
    bmi: Optional[float] = None


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str
    remember: Optional[bool] = False


class AdminLoginSchema(BaseModel):
    email: EmailStr
    password: str


# Helper to format MongoDB document for JSON response
def format_user_doc(doc):
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")),
        "fullName": doc.get("fullName", ""),
        "email": doc.get("email", ""),
        "age": doc.get("age"),
        "gender": doc.get("gender", ""),
        "height": doc.get("height"),
        "weight": doc.get("weight"),
        "bmi": doc.get("bmi"),
        "bmiCategory": doc.get("bmiCategory", ""),
        "isVerified": doc.get("isVerified", True),
        "registeredAt": doc.get("registeredAt", "")
    }


def compute_bmi_category(bmi: float) -> str:
    if bmi is None:
        return "Not Computed"
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25.0:
        return "Normal weight"
    elif bmi < 30.0:
        return "Overweight"
    else:
        return "Obese"


# =========================================================
# GENERAL & HEALTH CHECK
# =========================================================

@app.get("/api/health")
def health_check():
    """Returns backend and MongoDB health connection status."""
    database = get_database()
    mongo_connected = False
    user_count = 0

    if database is not None and mongo_client is not None:
        try:
            mongo_client.admin.command('ping')
            mongo_connected = True
            user_count = users_col.count_documents({})
        except Exception:
            mongo_connected = False

    return {
        "status": "online",
        "service": "NutriCare AI Backend",
        "mongodb_connected": mongo_connected,
        "database": DB_NAME,
        "user_count": user_count,
        "email_service": "Resend API" if RESEND_API_KEY else ("SMTP" if SMTP_USER else "Terminal Console (Ready)"),
        "timestamp": datetime.utcnow().isoformat()
    }


# =========================================================
# EMAIL OTP ROUTES
# =========================================================

@app.post("/api/send-otp")
def send_otp(data: SendOtpSchema):
    """
    Generates a 6-digit OTP, stores it in MongoDB (or local cache),
    and sends it to the user's email (with terminal console fallback).
    """
    email = data.email.lower().strip()
    database = get_database()

    # Check if user is already registered
    if users_col is not None:
        if users_col.find_one({"email": email}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please login instead."
            )

    # Generate 6-digit code
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Store in MongoDB
    if otps_col is not None:
        otps_col.delete_many({"email": email})  # Delete previous codes
        otps_col.insert_one({
            "email": email,
            "otp": otp_code,
            "createdAt": datetime.utcnow(),
            "expiresAt": expires_at,
            "verified": False
        })
    else:
        # In-memory fallback
        local_otps[email] = {
            "otp": otp_code,
            "expiresAt": expires_at,
            "verified": False
        }

    # Dispatch email (or print to console)
    sent_via_email = send_otp_email(email, otp_code)

    return {
        "success": True,
        "message": f"Verification code sent to {email}. Check your email or backend terminal.",
        "email": email,
        "delivered_via_network": sent_via_email
    }


@app.post("/api/verify-otp")
def verify_otp(data: VerifyOtpSchema):
    """Verifies the 6-digit OTP against MongoDB records."""
    email = data.email.lower().strip()
    submitted_otp = data.otp.strip()
    database = get_database()

    found_otp = None
    is_expired = False

    if otps_col is not None:
        record = otps_col.find_one({"email": email, "verified": False})
        if record:
            found_otp = record.get("otp")
            expires_at = record.get("expiresAt")
            if expires_at and datetime.utcnow() > expires_at:
                is_expired = True
    else:
        record = local_otps.get(email)
        if record and not record.get("verified"):
            found_otp = record.get("otp")
            if datetime.utcnow() > record.get("expiresAt"):
                is_expired = True

    if not found_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found for this email. Please click 'Send OTP'."
        )

    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    if found_otp != submitted_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect verification code. Please check and try again."
        )

    # Mark as verified
    if otps_col is not None:
        otps_col.update_one({"email": email}, {"$set": {"verified": True}})
    elif email in local_otps:
        local_otps[email]["verified"] = True

    print(f"✅ Email verified successfully: {email}")

    return {
        "success": True,
        "message": "Email verified successfully! You may now proceed.",
        "email": email
    }


# =========================================================
# USER REGISTRATION & LOGIN
# =========================================================

@app.post("/api/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegisterSchema):
    """Registers new user in MongoDB database."""
    database = get_database()
    email = user.email.lower().strip()

    if users_col is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB service unavailable. Please ensure MongoDB is started."
        )

    # Check duplicate email
    if users_col.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Compute BMI if missing
    calculated_bmi = user.bmi
    if calculated_bmi is None and user.height > 0 and user.weight > 0:
        height_m = user.height / 100.0
        calculated_bmi = round(user.weight / (height_m * height_m), 1)

    bmi_cat = compute_bmi_category(calculated_bmi)

    user_doc = {
        "fullName": user.fullName.strip(),
        "email": email,
        "password": user.password,
        "age": user.age,
        "gender": user.gender,
        "height": user.height,
        "weight": user.weight,
        "bmi": calculated_bmi,
        "bmiCategory": bmi_cat,
        "isVerified": True,
        "registeredAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

    result = users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    print(f"👤 Saved user in MongoDB: {email} (ID: {result.inserted_id})")

    return {
        "message": "User registered successfully in MongoDB",
        "user": format_user_doc(user_doc)
    }


@app.post("/api/login")
def login_user(credentials: UserLoginSchema):
    """Authenticates user email and password against MongoDB."""
    database = get_database()
    if users_col is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB database is offline."
        )

    email = credentials.email.lower().strip()
    user_doc = users_col.find_one({"email": email})

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with this email. Please sign up."
        )

    if user_doc.get("password") != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again."
        )

    print(f"🔐 User logged in via MongoDB: {email}")

    return {
        "message": "Login successful",
        "user": format_user_doc(user_doc)
    }


# =========================================================
# ADMIN AUTHENTICATION & MANAGEMENT
# =========================================================

@app.post("/api/admin/login")
def admin_login(credentials: AdminLoginSchema):
    """
    Authenticates Admin Panel using Email and Password.
    Checks against ADMIN_EMAIL/ADMIN_PASSWORD and MongoDB 'admins' collection.
    """
    email = credentials.email.lower().strip()
    pwd = credentials.password
    database = get_database()

    admin_match = False

    # 1. Check environment variables
    if email == ADMIN_EMAIL and pwd == ADMIN_PASSWORD:
        admin_match = True

    # 2. Check MongoDB admins collection
    if not admin_match and admins_col is not None:
        db_admin = admins_col.find_one({"email": email})
        if db_admin and db_admin.get("password") == pwd:
            admin_match = True

    if not admin_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin email or password."
        )

    print(f"🛡️ Admin authenticated successfully: {email}")

    return {
        "success": True,
        "message": "Admin authenticated successfully",
        "token": f"admin_token_{int(datetime.utcnow().timestamp())}",
        "admin": {
            "email": email,
            "role": "Super Administrator"
        }
    }


@app.get("/api/admin/users")
def get_all_users():
    """Admin API: Retrieves all registered users from MongoDB."""
    database = get_database()
    if users_col is None:
        raise HTTPException(status_code=503, detail="MongoDB is offline.")

    cursor = users_col.find().sort("registeredAt", -1)
    users = [format_user_doc(doc) for doc in cursor]

    return {
        "count": len(users),
        "users": users
    }


@app.get("/api/admin/stats")
def get_admin_stats():
    """Admin API: Returns summarized KPI statistics calculated from MongoDB."""
    database = get_database()
    if users_col is None:
        raise HTTPException(status_code=503, detail="MongoDB is offline.")

    users = list(users_col.find())
    total_users = len(users)

    if total_users == 0:
        return {
            "totalUsers": 0,
            "avgBmi": 0,
            "bmiDistribution": {"underweight": 0, "normal": 0, "overweight": 0, "obese": 0},
            "genderDistribution": {"male": 0, "female": 0, "other": 0}
        }

    bmis = [u.get("bmi") for u in users if u.get("bmi") is not None]
    avg_bmi = round(sum(bmis) / len(bmis), 1) if bmis else 0

    bmi_dist = {"underweight": 0, "normal": 0, "overweight": 0, "obese": 0}
    for b in bmis:
        if b < 18.5:
            bmi_dist["underweight"] += 1
        elif b < 25.0:
            bmi_dist["normal"] += 1
        elif b < 30.0:
            bmi_dist["overweight"] += 1
        else:
            bmi_dist["obese"] += 1

    gender_dist = {"male": 0, "female": 0, "other": 0}
    for u in users:
        g = (u.get("gender") or "other").lower()
        if g in gender_dist:
            gender_dist[g] += 1
        else:
            gender_dist["other"] += 1

    return {
        "totalUsers": total_users,
        "avgBmi": avg_bmi,
        "bmiDistribution": bmi_dist,
        "genderDistribution": gender_dist
    }


@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: str):
    """Admin API: Deletes a user from MongoDB by ID or email."""
    database = get_database()
    if users_col is None:
        raise HTTPException(status_code=503, detail="MongoDB is offline.")

    query = {}
    if ObjectId.is_valid(user_id):
        query = {"_id": ObjectId(user_id)}
    else:
        query = {"email": user_id.lower()}

    result = users_col.delete_one(query)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found in MongoDB.")

    print(f"🗑️ Deleted user from MongoDB: {user_id}")
    return {"message": "User deleted successfully", "deletedId": user_id}


@app.get("/api/admin/db-info")
def get_db_architecture():
    """
    Returns complete architectural details about where and how MongoDB
    stores all users, login credentials, and OTP verification records.
    """
    database = get_database()
    users_count = users_col.count_documents({}) if users_col is not None else 0
    otps_count = otps_col.count_documents({}) if otps_col is not None else 0
    admins_count = admins_col.count_documents({}) if admins_col is not None else 0

    return {
        "databaseName": DB_NAME,
        "connectionUri": MONGODB_URI.split("@")[-1] if "@" in MONGODB_URI else MONGODB_URI,
        "collections": [
            {
                "name": "users",
                "description": "Stores user registration and authentication details",
                "documentCount": users_count,
                "fields": [
                    {"field": "_id", "type": "ObjectId", "description": "Primary unique key"},
                    {"field": "fullName", "type": "String", "description": "Full name of the user"},
                    {"field": "email", "type": "String (Indexed, Unique)", "description": "Login email address"},
                    {"field": "password", "type": "String", "description": "User password for authentication"},
                    {"field": "age", "type": "Integer", "description": "Age in years"},
                    {"field": "gender", "type": "String", "description": "male / female / other"},
                    {"field": "height", "type": "Float", "description": "Height in centimeters"},
                    {"field": "weight", "type": "Float", "description": "Weight in kilograms"},
                    {"field": "bmi", "type": "Float", "description": "Calculated Body Mass Index"},
                    {"field": "bmiCategory", "type": "String", "description": "Normal weight / Underweight / Overweight / Obese"},
                    {"field": "isVerified", "type": "Boolean", "description": "True if email was verified with OTP"},
                    {"field": "registeredAt", "type": "String / Date", "description": "Timestamp of account creation"}
                ]
            },
            {
                "name": "otps",
                "description": "Stores temporary 6-digit verification codes for sign-up",
                "documentCount": otps_count,
                "fields": [
                    {"field": "_id", "type": "ObjectId", "description": "Primary key"},
                    {"field": "email", "type": "String", "description": "User email address"},
                    {"field": "otp", "type": "String (6 digits)", "description": "Active verification code"},
                    {"field": "expiresAt", "type": "Date (TTL 5 mins)", "description": "Expiration time"},
                    {"field": "verified", "type": "Boolean", "description": "True when code is validated"}
                ]
            },
            {
                "name": "admins",
                "description": "Stores authorized administrator credentials",
                "documentCount": admins_count,
                "fields": [
                    {"field": "_id", "type": "ObjectId", "description": "Primary key"},
                    {"field": "email", "type": "String (Unique)", "description": "Admin email address"},
                    {"field": "password", "type": "String", "description": "Admin dashboard access password"},
                    {"field": "role", "type": "String", "description": "superadmin"}
                ]
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting NutriCare AI Backend on http://127.0.0.1:{PORT}")
    uvicorn.run("app:app", host="127.0.0.1", port=PORT, reload=True)
