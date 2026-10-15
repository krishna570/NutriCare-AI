/**
 * ============================================================
 * NutriCare AI - Main Node.js Backend
 * ============================================================
 *
 * Features:
 * - User Registration
 * - User Login
 * - BMI Calculation
 * - Local JSON Database
 * - Admin Users
 * - Admin Statistics
 * - Delete Users
 * - OTP Send / Verify
 * - Python ML Service Connection
 * - ML Prediction
 * - Frontend Static Files
 *
 * MongoDB is NOT required.
 * User data is stored in:
 *
 * backend/data/users.json
 *
 * Python ML Service:
 * http://127.0.0.1:5000
 *
 * Node.js Backend:
 * http://127.0.0.1:8000
 * ============================================================
 */

require("dotenv").config();

const express = require("express");
const cors = require("cors");
const axios = require("axios");

const fs = require("fs");
const path = require("path");

const app = express();


// ============================================================
// CONFIGURATION
// ============================================================

const PORT = Number(process.env.PORT) > 0
    ? Number(process.env.PORT)
    : 8000;

const ML_SERVICE_URL =
    process.env.ML_SERVICE_URL || "http://127.0.0.1:5000";

// How long we wait for the Python RAG service.
// Knowledge-base answers come back instantly, but an LLM call on CPU
// can take a minute or more — 15 s used to abort every real RAG answer.
const RAG_TIMEOUT_MS = Number(process.env.RAG_TIMEOUT_MS || 120000);


// ============================================================
// PATHS
// ============================================================

// backend folder
const BACKEND_DIR = __dirname;

// Main project folder
const PROJECT_DIR = path.join(BACKEND_DIR, "..");

// Local database folder
const DATA_DIR = path.join(BACKEND_DIR, "data");

// Users JSON file
const USERS_FILE = path.join(DATA_DIR, "users.json");


// ============================================================
// CREATE DATA FOLDER / FILE
// ============================================================

if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
}

if (!fs.existsSync(USERS_FILE)) {
    fs.writeFileSync(
        USERS_FILE,
        JSON.stringify([], null, 2),
        "utf8"
    );
}


// ============================================================
// MIDDLEWARE
// ============================================================

app.use(cors());

app.use(express.json({
    limit: "20mb"
}));

app.use(express.urlencoded({
    extended: true,
    limit: "20mb"
}));


// ============================================================
// SERVE FRONTEND
// ============================================================

// The whole frontend (Main/, Login/, Admin/) is served from this
// server, so the browser always talks to the same origin as the API.
// Never expose the backend source / node_modules as static files.
app.use((req, res, next) => {
    if (
        req.path === "/backend" ||
        req.path.startsWith("/backend/")
    ) {
        return res.status(404).send("Not found");
    }
    next();
});

app.use(express.static(PROJECT_DIR));


// ============================================================
// LOCAL DATABASE FUNCTIONS
// ============================================================

function readUsers() {

    try {

        const data = fs.readFileSync(
            USERS_FILE,
            "utf8"
        );

        if (!data.trim()) {
            return [];
        }

        return JSON.parse(data);

    } catch (error) {

        console.error(
            "❌ Error reading users.json:",
            error.message
        );

        return [];
    }
}


function saveUsers(users) {

    try {

        fs.writeFileSync(
            USERS_FILE,
            JSON.stringify(users, null, 2),
            "utf8"
        );

        return true;

    } catch (error) {

        console.error(
            "❌ Error saving users.json:",
            error.message
        );

        return false;
    }
}


// ============================================================
// OTP MEMORY STORAGE
// ============================================================

const otpStore = {};


// ============================================================
// ADMIN ACCOUNT
// ============================================================

const ADMIN_EMAIL =
    process.env.ADMIN_EMAIL || "admin@nutricare.ai";

const ADMIN_PASSWORD =
    process.env.ADMIN_PASSWORD || "admin123";


// ============================================================
// HELPER FUNCTIONS
// ============================================================

function generateId() {

    return (
        Date.now().toString(36) +
        Math.random().toString(36).substring(2, 8)
    );
}


function computeBmi(height, weight) {

    height = Number(height);
    weight = Number(weight);

    if (
        !height ||
        !weight ||
        height <= 0 ||
        weight <= 0
    ) {
        return null;
    }

    const heightMeters = height / 100;

    return Number(
        (
            weight /
            (heightMeters * heightMeters)
        ).toFixed(1)
    );
}


function computeBmiCategory(bmi) {

    if (bmi === null || bmi === undefined) {
        return "Not Computed";
    }

    if (bmi < 18.5) {
        return "Underweight";
    }

    if (bmi < 25) {
        return "Normal weight";
    }

    if (bmi < 30) {
        return "Overweight";
    }

    return "Obese";
}


function formatUser(user) {

    if (!user) {
        return null;
    }

    return {

        id: user.id,

        fullName: user.fullName,

        email: user.email,

        age: user.age,

        gender: user.gender,

        height: user.height,

        weight: user.weight,

        bmi: user.bmi,

        bmiCategory: user.bmiCategory,

        registeredAt: user.registeredAt

    };
}


function generateOTP() {

    return Math.floor(
        100000 +
        Math.random() * 900000
    ).toString();
}


// ============================================================
// ROOT ROUTE → Redirect to Login UI
// (redirect so relative paths ./Style.css ./script.js work)
// ============================================================

app.get("/", (req, res) => {
    res.redirect("/Login/Login.html");
});


// ============================================================
// HEALTH CHECK
// ============================================================

app.get("/api/health", (req, res) => {

    res.json({

        status: "online",

        service:
            "NutriCare AI Node.js Backend",

        database:
            "Local JSON Database",

        // Node backend stores users in a JSON file — no MongoDB involved.
        // (The Admin panel uses this flag to pick its status wording.)
        mongodb_connected: false,

        storage:
            "Local JSON file",

        database_file:
            USERS_FILE,

        ml_service:
            ML_SERVICE_URL,

        timestamp:
            new Date().toISOString()

    });

});


// ============================================================
// ML SERVICE HEALTH
// ============================================================

app.get(
    "/api/ml/health",
    async (req, res) => {

        try {

            const response =
                await axios.get(
                    `${ML_SERVICE_URL}/`,
                    {
                        timeout: 5000
                    }
                );

            res.json({

                status: "online",

                node_backend:
                    "connected",

                python_ml_service:
                    response.data

            });

        } catch (error) {

            console.error(
                "❌ ML health error:",
                error.message
            );

            res.status(503).json({

                status: "offline",

                node_backend:
                    "online",

                python_ml_service:
                    "unavailable",

                error:
                    error.message

            });

        }

    }
);


// ============================================================
// ML PREDICTION
// ============================================================

app.post(
    "/api/ml/predict",
    async (req, res) => {

        try {

            console.log(
                "🧠 Sending food data to Python ML service..."
            );

            const response =
                await axios.post(

                    `${ML_SERVICE_URL}/predict`,

                    req.body,

                    {

                        timeout: 30000,

                        headers: {

                            "Content-Type":
                                "application/json"

                        }

                    }

                );


            console.log(
                "✅ ML prediction received:",
                response.data
            );


            res.json({

                success: true,

                prediction:
                    response.data

            });


        } catch (error) {

            console.error(
                "❌ ML prediction error:",
                error.message
            );


            if (error.response) {

                return res.status(
                    error.response.status || 500
                ).json({

                    success: false,

                    detail:
                        "Python ML service returned an error.",

                    error:
                        error.response.data

                });

            }


            res.status(503).json({

                success: false,

                detail:
                    "Unable to connect to NutriCare AI ML service.",

                error:
                    error.message

            });

        }

    }
);


// ============================================================
// FOOD IMAGE PREDICTION  (ViT Classifier → Python)
// ============================================================

app.post(
    "/api/food/predict",
    async (req, res) => {

        try {

            const { image_base64 } = req.body;

            if (!image_base64) {
                return res.status(400).json({
                    success: false,
                    detail: "image_base64 field is required."
                });
            }

            console.log("🍽️  Sending food image to Python ViT classifier...");

            const response = await axios.post(
                `${ML_SERVICE_URL}/predict-food`,
                { image_base64 },
                {
                    timeout: 60000,
                    headers: { "Content-Type": "application/json" }
                }
            );

            console.log(
                "✅ Food prediction received:",
                response.data.display_name,
                `(${response.data.confidence}%)`
            );

            res.json({
                success: true,
                prediction: response.data
            });

        } catch (error) {

            console.error("❌ Food prediction error:", error.message);

            if (error.response) {
                return res.status(error.response.status || 500).json({
                    success: false,
                    detail: "Python food classifier returned an error.",
                    error: error.response.data
                });
            }

            res.status(503).json({
                success: false,
                detail: "Unable to connect to NutriCare AI food classifier. Make sure the Python service is running on port 5000.",
                error: error.message
            });
        }

    }
);


// ============================================================
// FOOD RECOMMENDATIONS  (report → what the user can eat)
// ============================================================

app.post(
    "/api/recommend",
    async (req, res) => {

        try {

            console.log("🥗 Food recommendations requested...");

            const response = await axios.post(
                `${ML_SERVICE_URL}/food-recommend`,
                { profile: req.body.profile || {} },
                {
                    timeout: 30000,
                    headers: { "Content-Type": "application/json" }
                }
            );

            res.json(response.data);

        } catch (error) {

            console.error("❌ Recommendation error:", error.message);

            if (error.response) {
                return res.status(error.response.status || 500).json({
                    success: false,
                    detail: "Recommendation service returned an error.",
                    error: error.response.data
                });
            }

            res.status(503).json({
                success: false,
                detail: "Unable to reach NutriCare AI Python service. Make sure it is running on port 5000.",
                error: error.message
            });

        }

    }
);


// ============================================================
// 15-DAY DAILY FOOD CHART
// ============================================================

app.post(
    "/api/plan",
    async (req, res) => {

        try {

            console.log("📅 15-day food chart requested...");

            const response = await axios.post(
                `${ML_SERVICE_URL}/plan/15-day`,
                {
                    profile: req.body.profile || {},
                    start_date: req.body.start_date || null
                },
                {
                    timeout: 30000,
                    headers: { "Content-Type": "application/json" }
                }
            );

            console.log("✅ Food chart ready:", response.data.days?.length, "days");

            res.json(response.data);

        } catch (error) {

            console.error("❌ Food chart error:", error.message);

            if (error.response) {
                return res.status(error.response.status || 500).json({
                    success: false,
                    detail: "Food chart service returned an error.",
                    error: error.response.data
                });
            }

            res.status(503).json({
                success: false,
                detail: "Unable to reach NutriCare AI Python service. Make sure it is running on port 5000.",
                error: error.message
            });

        }

    }
);


// ============================================================
// BUILT-IN NUTRITION KNOWLEDGE  (fallback when Python is offline)
// ============================================================

function nutriFallback(question) {
    const q = question.toLowerCase();

    // ── Blood / haematology ──────────────────────────────────
    if (/\bhb\b|hemoglobin|haemoglobin/.test(q))
        return "HB stands for Hemoglobin. It is the iron-containing protein in red blood cells responsible for carrying oxygen from the lungs to the rest of the body.\n\n📊 Normal HB levels:\n• Men: 13.5 – 17.5 g/dL\n• Women: 12.0 – 15.5 g/dL\n• Children: 11.0 – 16.0 g/dL\n\nLow HB indicates anaemia. Causes include iron deficiency, vitamin B12 deficiency, or chronic disease. High HB can indicate dehydration or polycythaemia.";

    if (/\bwbc\b|white blood cell|leukocyte/.test(q))
        return "WBC (White Blood Cells) are your immune system's fighters. Normal range: 4,500 – 11,000 cells/µL.\n\n• High WBC → infection, inflammation, or leukaemia\n• Low WBC → bone marrow issues or immunosuppression";

    if (/\brbc\b|red blood cell|erythrocyte/.test(q))
        return "RBC (Red Blood Cells) carry oxygen using haemoglobin. Normal count:\n• Men: 4.7 – 6.1 million/µL\n• Women: 4.2 – 5.4 million/µL\n\nLow RBC = anaemia. High RBC = polycythaemia.";

    if (/platelet|plt/.test(q))
        return "Platelets help blood clot after injury. Normal range: 150,000 – 400,000/µL.\n\n• Low (< 150,000) = thrombocytopenia → bleeding risk\n• High (> 400,000) = thrombocytosis → clotting risk";

    if (/\bhba1c\b|glycated|a1c/.test(q))
        return "HbA1c (Glycated Haemoglobin) shows average blood sugar over 2–3 months.\n\n📊 Ranges:\n• Normal: < 5.7%\n• Pre-diabetes: 5.7 – 6.4%\n• Diabetes: ≥ 6.5%\n\nUsed to monitor and diagnose Type 2 diabetes.";

    // ── Blood sugar ──────────────────────────────────────────
    if (/blood sugar|glucose|fasting sugar|diabetes/.test(q))
        return "Blood Glucose (Sugar) measures how much glucose is in your blood.\n\n📊 Normal ranges:\n• Fasting: 70 – 100 mg/dL\n• After meals (2h): < 140 mg/dL\n• Pre-diabetes (fasting): 100 – 125 mg/dL\n• Diabetes (fasting): ≥ 126 mg/dL\n\nManage blood sugar with balanced meals, regular exercise, and limited refined carbs.";

    // ── BMI ──────────────────────────────────────────────────
    if (/\bbmi\b|body mass index/.test(q))
        return "BMI (Body Mass Index) estimates body fat from height and weight.\n\n📐 Formula: weight (kg) ÷ height² (m²)\n\n📊 Categories:\n• < 18.5 → Underweight\n• 18.5 – 24.9 → Normal weight ✅\n• 25 – 29.9 → Overweight\n• ≥ 30 → Obese\n\nBMI is a screening tool — it does not measure body fat directly.";

    // ── Macronutrients ───────────────────────────────────────
    if (/\bprotein\b/.test(q))
        return "Protein is a macronutrient essential for muscle repair, enzyme production, and immune function.\n\n📊 Daily need: 0.8 g per kg body weight (sedentary adults). Athletes: 1.2 – 2.0 g/kg.\n\n🥩 Good sources: eggs, chicken, fish, lentils, tofu, dairy, beans.";

    if (/\bcarb|carbohydrate/.test(q))
        return "Carbohydrates are the body's primary energy source.\n\n📊 Should provide 45–65% of daily calories.\n\n✅ Prefer complex carbs: oats, brown rice, whole wheat, vegetables.\n❌ Limit simple carbs: white bread, sugary drinks, sweets.";

    if (/\bfat\b|lipid/.test(q))
        return "Dietary fats provide energy, support cell growth, and absorb fat-soluble vitamins (A, D, E, K).\n\n📊 Recommended: 20–35% of total daily calories.\n\n✅ Healthy fats: avocado, olive oil, nuts, fish (omega-3)\n❌ Limit: trans fats, excessive saturated fats.";

    if (/calori|kcal/.test(q))
        return "Calories (kcal) measure the energy content of food.\n\n📊 Average daily needs:\n• Women: 1,600 – 2,400 kcal\n• Men: 2,000 – 3,000 kcal\n(varies by age, weight, activity level)\n\nTrack calories with NutriCare's food image detection feature!";

    if (/\bfibre|fiber/.test(q))
        return "Dietary fibre supports digestion, controls blood sugar, and reduces cholesterol.\n\n📊 RDA:\n• Women: 25 g/day\n• Men: 38 g/day\n\n🌾 Sources: oats, fruits, vegetables, legumes, whole grains.";

    // ── Vitamins ─────────────────────────────────────────────
    if (/vitamin\s*a/.test(q))
        return "Vitamin A supports vision, immunity, and skin health.\n\n📊 RDA: 700–900 µg/day\n🥕 Sources: carrots, sweet potato, spinach, eggs, liver.";

    if (/vitamin\s*b12|b-12/.test(q))
        return "Vitamin B12 is essential for nerve function, DNA synthesis, and red blood cell formation.\n\n📊 RDA: 2.4 µg/day\n🥩 Sources: meat, fish, dairy, eggs. Vegans should supplement.\n\nDeficiency causes anaemia and neurological damage.";

    if (/vitamin\s*c/.test(q))
        return "Vitamin C is an antioxidant that boosts immunity and helps absorb iron.\n\n📊 RDA: 65 – 90 mg/day\n🍊 Sources: oranges, guava, bell pepper, strawberries, broccoli.";

    if (/vitamin\s*d/.test(q))
        return "Vitamin D regulates calcium absorption and supports bone health and immunity.\n\n📊 RDA: 600 – 800 IU/day (adults)\n☀️ Sources: sunlight, fatty fish, fortified milk, egg yolks.\n\nDeficiency is very common in India — consider a blood test.";

    if (/vitamin\s*e/.test(q))
        return "Vitamin E is a fat-soluble antioxidant protecting cells from oxidative stress.\n\n📊 RDA: 15 mg/day\n🌰 Sources: sunflower seeds, almonds, spinach, vegetable oils.";

    if (/vitamin\s*k/.test(q))
        return "Vitamin K is essential for blood clotting and bone metabolism.\n\n📊 RDA: 90–120 µg/day\n🥬 Sources: kale, spinach, broccoli, Brussels sprouts.";

    // ── Minerals ─────────────────────────────────────────────
    if (/\biron\b/.test(q))
        return "Iron is needed to make haemoglobin and carry oxygen in blood.\n\n📊 RDA: 8 mg/day (men) | 18 mg/day (women)\n\n🥩 Sources: red meat, spinach, lentils, tofu, fortified cereals.\n💡 Tip: Take with Vitamin C to boost absorption. Avoid tea/coffee around meals.";

    if (/calcium/.test(q))
        return "Calcium is critical for bones, teeth, nerve signals, and muscle function.\n\n📊 RDA: 1,000 mg/day (adults) | 1,200 mg (women 51+)\n🥛 Sources: dairy, fortified plant milks, tofu, leafy greens.";

    if (/\bzinc\b/.test(q))
        return "Zinc supports immune function, wound healing, and DNA synthesis.\n\n📊 RDA: 8–11 mg/day\n🥜 Sources: meat, shellfish, legumes, seeds, nuts.";

    if (/magnesium/.test(q))
        return "Magnesium supports 300+ enzyme reactions, muscle function, and sleep.\n\n📊 RDA: 310–420 mg/day\n🌰 Sources: nuts, seeds, dark chocolate, leafy greens, whole grains.";

    if (/potassium/.test(q))
        return "Potassium regulates fluid balance, nerve signals, and muscle contractions.\n\n📊 RDA: 2,600–3,400 mg/day\n🍌 Sources: bananas, potatoes, avocado, spinach, beans.";

    if (/sodium|salt/.test(q))
        return "Sodium regulates fluid balance and blood pressure.\n\n📊 WHO limit: < 2,000 mg/day (about 5 g salt)\n\n⚠️ Excess sodium raises blood pressure and risk of heart disease. Limit processed and packaged foods.";

    // ── Sugar / sweeteners ───────────────────────────────────
    if (/\bsugar\b/.test(q))
        return "Sugar provides quick energy but excess causes weight gain, diabetes, and tooth decay.\n\n📊 WHO recommends < 25 g free sugar/day (about 6 teaspoons).\n\n❌ Avoid: sugary drinks, sweets, white bread\n✅ Prefer: fruits, whole grains.";

    // ── Cholesterol / lipids ─────────────────────────────────
    if (/cholesterol|ldl|hdl|triglyceride/.test(q))
        return "Blood Lipid Panel (Cholesterol):\n\n📊 Desirable ranges:\n• Total cholesterol: < 200 mg/dL\n• LDL ('bad'): < 100 mg/dL\n• HDL ('good'): > 60 mg/dL\n• Triglycerides: < 150 mg/dL\n\n✅ Lower LDL with: oats, fruits, veggies, healthy fats, exercise.";

    // ── Blood pressure ───────────────────────────────────────
    if (/blood pressure|bp|hypertension/.test(q))
        return "Blood Pressure is the force of blood against artery walls.\n\n📊 Categories:\n• Normal: < 120/80 mmHg\n• Elevated: 120–129 / < 80\n• High (Stage 1): 130–139 / 80–89\n• High (Stage 2): ≥ 140 / ≥ 90\n\n🥗 Manage with DASH diet: low sodium, high potassium, fruits & vegetables.";

    // ── Water / hydration ────────────────────────────────────
    if (/water|hydration|dehydration/.test(q))
        return "Water is essential for every body function — digestion, temperature regulation, and joint lubrication.\n\n📊 Daily recommendation:\n• Women: ~2.7 L (11.5 cups)\n• Men: ~3.7 L (15.5 cups)\n\nIncrease intake during exercise, heat, or illness.";

    // ── Food / diet questions ────────────────────────────────
    if (/weight loss|lose weight|diet/.test(q))
        return "Healthy Weight Loss Tips:\n\n1️⃣ Calorie deficit: eat 300–500 kcal less than you burn\n2️⃣ High protein to preserve muscle\n3️⃣ Increase fibre for satiety\n4️⃣ Limit refined carbs and added sugar\n5️⃣ Exercise: 150+ min/week moderate aerobic activity\n6️⃣ Stay hydrated — drink water before meals\n7️⃣ Sleep 7–9 hours/night (poor sleep increases hunger hormones)";

    if (/anaemia|anemia/.test(q))
        return "Anaemia is a condition where the blood lacks enough healthy red blood cells or haemoglobin.\n\n📊 Common types:\n• Iron-deficiency anaemia (most common)\n• Vitamin B12 / folate deficiency anaemia\n• Haemolytic anaemia\n\n🔴 Symptoms: fatigue, pale skin, shortness of breath, dizziness.\n\n🥩 Treatment: iron-rich foods, Vitamin C, B12 supplements (as advised by a doctor).";

    if (/thyroid|tsh|t3|t4/.test(q))
        return "Thyroid Function:\n\n📊 TSH (Thyroid Stimulating Hormone) normal range: 0.4 – 4.0 mIU/L\n• High TSH → Hypothyroidism (underactive thyroid)\n• Low TSH → Hyperthyroidism (overactive thyroid)\n\n🧂 Iodine is critical for thyroid hormone production. Sources: iodised salt, seafood.";

    // ── Generic greeting / help ──────────────────────────────
    if (/hello|hi|hey|good morning|good afternoon|namaste/.test(q))
        return "Hello! 👋 I'm NutriCare AI. I can help you with:\n\n🩸 Blood report values (HB, WBC, RBC, HbA1c, etc.)\n🥗 Nutrition questions (protein, vitamins, minerals)\n📊 BMI, blood sugar, cholesterol\n🍽️ Diet and weight management tips\n\nWhat would you like to know?";

    if (/what can you do|help|features/.test(q))
        return "I'm NutriCare AI! Here's what I can help with:\n\n✅ Explain blood test results (HB, WBC, HbA1c, etc.)\n✅ Nutrition info (vitamins, minerals, macros)\n✅ BMI calculation and interpretation\n✅ Blood sugar and diabetes info\n✅ Diet and healthy eating tips\n✅ Food image detection (use the upload feature)\n\nJust type your question!";

    // ── Default ──────────────────────────────────────────────
    return `I'm NutriCare AI 🤖. I can answer questions about blood reports (HB, WBC, HbA1c), nutrition (protein, vitamins, minerals), BMI, blood sugar, cholesterol, and healthy diet tips.\n\nYou asked: "${question}"\n\nCould you rephrase or be more specific? For example: "What is HB?", "What foods are high in iron?", or "What is a normal blood sugar level?"`;
}


// ============================================================
// RAG CHAT  (tries Python RAG first → falls back to built-in)
// ============================================================

app.post(
    "/api/chat",
    async (req, res) => {            const { question, profile } = req.body;

        if (!question || !String(question).trim()) {
            return res.status(400).json({
                success: false,
                detail: "question field is required."
            });
        }

        const q = String(question).trim();
        console.log("💬 RAG question received:", q);

        // ── 1. Try Python RAG service ────────────────────────
        try {
            const response = await axios.post(
                `${ML_SERVICE_URL}/rag-chat`,
                { question: q, profile: profile || null },
                {
                    timeout: RAG_TIMEOUT_MS,
                    headers: { "Content-Type": "application/json" }
                }
            );

            const answer = response.data.answer || response.data.result || "";
            console.log("✅ RAG answer (Python):", answer.substring(0, 120));

            return res.json({
                success: true,
                answer:  answer,
                sources: response.data.sources || [],
                via:     response.data.via || "python_rag"
            });

        } catch (ragErr) {
            // Python service is down or slow — use built-in fallback
            console.warn("⚠️  Python RAG unavailable, using built-in fallback. Error:", ragErr.message);
        }

        // ── 2. Built-in keyword fallback (always works) ──────
        const answer = nutriFallback(q);
        console.log("✅ RAG answer (built-in fallback):", answer.substring(0, 80));

        return res.json({
            success: true,
            answer:  answer,
            sources: [],
            via:     "builtin_fallback"
        });
    }
);



app.post(
    "/api/send-otp",
    async (req, res) => {

        try {

            const email =
                String(req.body.email || "")
                    .trim()
                    .toLowerCase();


            if (!email) {

                return res.status(400).json({

                    success: false,

                    detail:
                        "Email address is required."

                });

            }


            const otp =
                generateOTP();


            otpStore[email] = {

                otp: otp,

                createdAt:
                    Date.now(),

                expiresAt:
                    Date.now() +
                    5 * 60 * 1000

            };


            console.log("");
            console.log(
                "================================"
            );

            console.log(
                "📧 OTP GENERATED"
            );

            console.log(
                "Email:",
                email
            );

            console.log(
                "OTP:",
                otp
            );

            console.log(
                "Valid for 5 minutes"
            );

            console.log(
                "================================"
            );


            res.json({

                success: true,

                message:
                    "OTP generated successfully.",

                email: email,

                // Development only
                otp: otp

            });

        } catch (error) {

            console.error(
                "OTP error:",
                error
            );

            res.status(500).json({

                success: false,

                detail:
                    "Unable to generate OTP."

            });

        }

    }
);


// ============================================================
// VERIFY OTP
// ============================================================

app.post(
    "/api/verify-otp",
    async (req, res) => {

        try {

            const email =
                String(req.body.email || "")
                    .trim()
                    .toLowerCase();

            const otp =
                String(req.body.otp || "")
                    .trim();


            if (!email || !otp) {

                return res.status(400).json({

                    success: false,

                    detail:
                        "Email and OTP are required."

                });

            }


            const stored =
                otpStore[email];


            if (!stored) {

                return res.status(400).json({

                    success: false,

                    detail:
                        "OTP not found. Please request a new OTP."

                });

            }


            if (
                Date.now() >
                stored.expiresAt
            ) {

                delete otpStore[email];

                return res.status(400).json({

                    success: false,

                    detail:
                        "OTP has expired. Please request a new OTP."

                });

            }


            if (
                stored.otp !== otp
            ) {

                return res.status(400).json({

                    success: false,

                    detail:
                        "Invalid OTP."

                });

            }


            delete otpStore[email];


            res.json({

                success: true,

                message:
                    "OTP verified successfully.",

                verified:
                    true

            });

        } catch (error) {

            console.error(
                "OTP verification error:",
                error
            );

            res.status(500).json({

                success: false,

                detail:
                    "OTP verification failed."

            });

        }

    }
);


// ============================================================
// REGISTER USER
// ============================================================

app.post(
    "/api/register",
    async (req, res) => {

        try {

            const {

                fullName,

                email,

                password,

                age,

                gender,

                height,

                weight,

                bmi

            } = req.body;


            // ---------------------------------------------
            // VALIDATION
            // ---------------------------------------------

            if (
                !fullName ||
                !email ||
                !password
            ) {

                return res.status(400).json({

                    detail:
                        "Name, email and password are required."

                });

            }


            if (
                age === undefined ||
                gender === undefined ||
                height === undefined ||
                weight === undefined
            ) {

                return res.status(400).json({

                    detail:
                        "Age, gender, height and weight are required."

                });

            }


            const cleanEmail =
                String(email)
                    .trim()
                    .toLowerCase();


            // ---------------------------------------------
            // CHECK EXISTING USER
            // ---------------------------------------------

            const users =
                readUsers();


            const existingUser =
                users.find(
                    user =>
                        user.email === cleanEmail
                );


            if (existingUser) {

                return res.status(400).json({

                    detail:
                        "An account with this email address already exists."

                });

            }


            // ---------------------------------------------
            // BMI
            // ---------------------------------------------

            let calculatedBmi =
                bmi !== undefined &&
                bmi !== null &&
                bmi !== ""
                    ? Number(bmi)
                    : computeBmi(
                        height,
                        weight
                    );


            const bmiCategory =
                computeBmiCategory(
                    calculatedBmi
                );


            // ---------------------------------------------
            // CREATE USER
            // ---------------------------------------------

            const newUser = {

                id:
                    generateId(),

                fullName:
                    String(fullName).trim(),

                email:
                    cleanEmail,

                password:
                    String(password),

                age:
                    Number(age),

                gender:
                    String(gender),

                height:
                    Number(height),

                weight:
                    Number(weight),

                bmi:
                    calculatedBmi,

                bmiCategory:
                    bmiCategory,

                registeredAt:
                    new Date()
                        .toISOString()
                        .replace("T", " ")
                        .substring(0, 19)

            };


            users.push(newUser);


            const saved =
                saveUsers(users);


            if (!saved) {

                return res.status(500).json({

                    detail:
                        "Unable to save user."

                });

            }


            console.log("");
            console.log(
                "👤 NEW USER REGISTERED"
            );

            console.log(
                "Name:",
                newUser.fullName
            );

            console.log(
                "Email:",
                newUser.email
            );

            console.log(
                "BMI:",
                newUser.bmi
            );

            console.log(
                "BMI Category:",
                newUser.bmiCategory
            );


            res.status(201).json({

                message:
                    "User profile registered successfully.",

                user:
                    formatUser(newUser)

            });


        } catch (error) {

            console.error(
                "❌ Registration error:",
                error
            );

            res.status(500).json({

                detail:
                    "Server error during registration."

            });

        }

    }
);


// ============================================================
// LOGIN
// ============================================================

app.post(
    "/api/login",
    async (req, res) => {

        try {

            const {

                email,

                password

            } = req.body;


            if (
                !email ||
                !password
            ) {

                return res.status(400).json({

                    detail:
                        "Email and password are required."

                });

            }


            const cleanEmail =
                String(email)
                    .trim()
                    .toLowerCase();


            const users =
                readUsers();


            const user =
                users.find(
                    item =>
                        item.email === cleanEmail
                );


            if (!user) {

                return res.status(401).json({

                    detail:
                        "No account found with this email."

                });

            }


            if (
                user.password !==
                String(password)
            ) {

                return res.status(401).json({

                    detail:
                        "Incorrect password."

                });

            }


            console.log(
                "🔐 User login:",
                user.email
            );


            res.json({

                message:
                    "Login successful",

                user:
                    formatUser(user)

            });


        } catch (error) {

            console.error(
                "❌ Login error:",
                error
            );

            res.status(500).json({

                detail:
                    "Server error during login."

            });

        }

    }
);


// ============================================================
// GET CURRENT USER
// ============================================================

app.get(
    "/api/user/:email",
    (req, res) => {

        try {

            const email =
                String(req.params.email)
                    .trim()
                    .toLowerCase();


            const users =
                readUsers();


            const user =
                users.find(
                    item =>
                        item.email === email
                );


            if (!user) {

                return res.status(404).json({

                    detail:
                        "User not found."

                });

            }


            res.json({

                success: true,

                user:
                    formatUser(user)

            });

        } catch (error) {

            res.status(500).json({

                detail:
                    error.message

            });

        }

    }
);


// ============================================================
// ADMIN LOGIN
// ============================================================

app.post(
    "/api/admin/login",
    (req, res) => {

        const {

            email,

            password

        } = req.body;


        if (
            email === ADMIN_EMAIL &&
            password === ADMIN_PASSWORD
        ) {

            console.log(
                "⚙️ Admin login successful"
            );


            return res.json({

                success: true,

                message:
                    "Admin login successful.",

                admin: {

                    email:
                        ADMIN_EMAIL,

                    role:
                        "admin"

                }

            });

        }


        return res.status(401).json({

            success: false,

            detail:
                "Invalid admin email or password."

        });

    }
);


// ============================================================
// ADMIN - GET ALL USERS
// ============================================================

app.get(
    "/api/admin/users",
    (req, res) => {

        try {

            const users =
                readUsers();


            res.json({

                count:
                    users.length,

                users:
                    users.map(
                        formatUser
                    )

            });

        } catch (error) {

            res.status(500).json({

                detail:
                    error.message

            });

        }

    }
);


// ============================================================
// ADMIN - STATISTICS
// ============================================================

app.get(
    "/api/admin/stats",
    (req, res) => {

        try {

            const users =
                readUsers();


            const totalUsers =
                users.length;


            // ---------------------------------------------
            // BMI
            // ---------------------------------------------

            const bmis =
                users

                    .map(
                        user =>
                            Number(user.bmi)
                    )

                    .filter(
                        bmi =>
                            !isNaN(bmi)
                    );


            const avgBmi =
                bmis.length > 0

                    ? Number(
                        (
                            bmis.reduce(
                                (
                                    total,
                                    bmi
                                ) =>
                                    total + bmi,
                                0
                            ) /
                            bmis.length
                        ).toFixed(1)
                    )

                    : 0;


            // ---------------------------------------------
            // BMI DISTRIBUTION
            // ---------------------------------------------

            const bmiDistribution = {

                underweight: 0,

                normal: 0,

                overweight: 0,

                obese: 0

            };


            bmis.forEach(
                bmi => {

                    if (bmi < 18.5) {

                        bmiDistribution
                            .underweight++;

                    }

                    else if (
                        bmi < 25
                    ) {

                        bmiDistribution
                            .normal++;

                    }

                    else if (
                        bmi < 30
                    ) {

                        bmiDistribution
                            .overweight++;

                    }

                    else {

                        bmiDistribution
                            .obese++;

                    }

                }
            );


            // ---------------------------------------------
            // GENDER DISTRIBUTION
            // ---------------------------------------------

            const genderDistribution = {

                male: 0,

                female: 0,

                other: 0

            };


            users.forEach(
                user => {

                    const gender =
                        String(
                            user.gender ||
                            "other"
                        ).toLowerCase();


                    if (
                        gender === "male"
                    ) {

                        genderDistribution
                            .male++;

                    }

                    else if (
                        gender === "female"
                    ) {

                        genderDistribution
                            .female++;

                    }

                    else {

                        genderDistribution
                            .other++;

                    }

                }
            );


            res.json({

                totalUsers,

                avgBmi,

                bmiDistribution,

                genderDistribution

            });


        } catch (error) {

            res.status(500).json({

                detail:
                    error.message

            });

        }

    }
);


// ============================================================
// ADMIN - DELETE USER
// ============================================================

app.delete(
    "/api/admin/users/:id",
    (req, res) => {

        try {

            const id =
                String(
                    req.params.id
                );


            let users =
                readUsers();


            const oldLength =
                users.length;


            users =
                users.filter(
                    user => {

                        return (
                            user.id !== id &&
                            user.email !== id
                        );

                    }
                );


            if (
                users.length ===
                oldLength
            ) {

                return res.status(404).json({

                    detail:
                        "User not found."

                });

            }


            saveUsers(users);


            console.log(
                "🗑️ User deleted:",
                id
            );


            res.json({

                message:
                    "User deleted successfully.",

                deletedId:
                    id

            });


        } catch (error) {

            res.status(500).json({

                detail:
                    error.message

            });

        }

    }
);


// ============================================================
// ADMIN - GET USER COUNT
// ============================================================

app.get(
    "/api/admin/user-count",
    (req, res) => {

        const users =
            readUsers();


        res.json({

            count:
                users.length

        });

    }
);


// ============================================================
// ADMIN - DATABASE SCHEMA INSPECTOR
// ============================================================

app.get(
    "/api/admin/db-info",
    (req, res) => {

        const users = readUsers();


        res.json({

            connectionUri:
                "file://" + USERS_FILE.replace(/\\/g, "/"),

            databaseName:
                "nutricare_json_db",

            storage:
                "Local JSON file — MongoDB not required",

            collections: [
                {
                    name: "users",
                    description:
                        "Registered NutriCare users with live BMI analytics",
                    documentCount: users.length,
                    fields: [
                        { field: "id",           type: "String",        description: "Primary key" },
                        { field: "fullName",     type: "String",        description: "User full name" },
                        { field: "email",        type: "String (Unique)", description: "User login email" },
                        { field: "password",     type: "String",        description: "User authentication password" },
                        { field: "age",          type: "Integer",       description: "Age in years" },
                        { field: "gender",       type: "String",        description: "Gender identity" },
                        { field: "height",       type: "Float",         description: "Height in centimetres" },
                        { field: "weight",       type: "Float",         description: "Weight in kilograms" },
                        { field: "bmi",          type: "Float",         description: "Body Mass Index" },
                        { field: "bmiCategory",  type: "String",        description: "Classification" },
                        { field: "registeredAt", type: "Date / ISO String", description: "Timestamp of registration" }
                    ]
                }
            ]

        });

    }
);


// ============================================================
// DATABASE DEBUG
// ============================================================

app.get(
    "/api/debug/users",
    (req, res) => {

        const users =
            readUsers();


        // Do NOT return passwords
        const safeUsers =
            users.map(
                user => ({

                    id:
                        user.id,

                    fullName:
                        user.fullName,

                    email:
                        user.email,

                    age:
                        user.age,

                    gender:
                        user.gender,

                    height:
                        user.height,

                    weight:
                        user.weight,

                    bmi:
                        user.bmi,

                    bmiCategory:
                        user.bmiCategory,

                    registeredAt:
                        user.registeredAt

                })
            );


        res.json({

            count:
                safeUsers.length,

            users:
                safeUsers

        });

    }
);


// ============================================================
// LOGOUT
// ============================================================

app.post(
    "/api/logout",
    (req, res) => {

        res.json({

            success: true,

            message:
                "Logout successful."

        });

    }
);


// ============================================================
// 404 API HANDLER
// ============================================================

app.use(
    "/api",
    (req, res) => {

        res.status(404).json({

            detail:
                "API endpoint not found.",

            path:
                req.originalUrl

        });

    }
);


// ============================================================
// FRONTEND FALLBACK
// ============================================================

app.get(
    "*",
    (req, res, next) => {

        // Don't interfere with API routes
        if (
            req.path.startsWith("/api/")
        ) {

            return next();

        }


        const requestedPath =
            path.join(
                PROJECT_DIR,
                req.path
            );


        if (
            fs.existsSync(
                requestedPath
            ) &&
            fs.statSync(
                requestedPath
            ).isFile()
        ) {

            return res.sendFile(
                requestedPath
            );

        }


        // Main page fallback
        const mainIndex =
            path.join(
                PROJECT_DIR,
                "Main",
                "index.html"
            );


        if (
            fs.existsSync(
                mainIndex
            )
        ) {

            return res.sendFile(
                mainIndex
            );

        }


        res.status(404).send(
            "NutriCare AI page not found."
        );

    }
);


// ============================================================
// START SERVER
// ============================================================

app.listen(
    PORT,
    () => {

        console.log("");

        console.log(
            "========================================"
        );

        console.log(
            "🚀 NutriCare AI Node.js Backend"
        );

        console.log(
            `🌐 http://127.0.0.1:${PORT}`
        );

        console.log(
            `🧠 Python ML: ${ML_SERVICE_URL}`
        );

        console.log(
            "💾 Database: Local JSON"
        );

        console.log(
            `📁 Users: ${USERS_FILE}`
        );

        console.log(
            "========================================"
        );

        console.log("");

    }
);