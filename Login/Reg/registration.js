/* =========================================================
   NutriCare AI - Registration JavaScript
   2-Step Wizard, Validation, BMI Calculator & Baymax Assistant
   ========================================================= */

/* API BASE — same origin when served by the Node.js backend
   (port 8000), direct call when opened as a file. */
const API_BASE =
    (location.protocol.startsWith("http") && location.port === "8000")
        ? ""
        : "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {

    /* =========================================================
       DOM ELEMENTS
       ========================================================= */
    // Step panels
    const step1 = document.getElementById("step1");
    const step2 = document.getElementById("step2");

    // Header & Progress
    const stepLabel = document.getElementById("stepLabel");
    const formTitle = document.getElementById("formTitle");
    const formSubtitle = document.getElementById("formSubtitle");
    const progressFill = document.getElementById("progressFill");
    const pStep1 = document.getElementById("pStep1");
    const pStep2 = document.getElementById("pStep2");

    // Buttons
    const nextStep1 = document.getElementById("nextStep1");
    const backStep2 = document.getElementById("backStep2");
    const registrationForm = document.getElementById("registrationForm");
    const createAccountButton = document.getElementById("createAccountButton");

    // Inputs: Step 1
    const fullNameInput = document.getElementById("fullName");
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const confirmPasswordInput = document.getElementById("confirmPassword");
    const passwordToggle = document.getElementById("passwordToggle");
    const strengthFill = document.getElementById("strengthFill");
    const strengthText = document.getElementById("strengthText");

    // Inputs: Step 2
    const ageInput = document.getElementById("age");
    const genderInput = document.getElementById("gender");
    const heightInput = document.getElementById("height");
    const weightInput = document.getElementById("weight");
    const bmiCard = document.getElementById("bmiCard");
    const bmiValue = document.getElementById("bmiValue");
    const bmiStatus = document.getElementById("bmiStatus");
    const termsCheckbox = document.getElementById("termsCheckbox");

    // Error message elements
    const nameError = document.getElementById("nameError");
    const emailError = document.getElementById("emailError");
    const passwordError = document.getElementById("passwordError");
    const confirmPasswordError = document.getElementById("confirmPasswordError");
    const ageError = document.getElementById("ageError");
    const genderError = document.getElementById("genderError");
    const heightError = document.getElementById("heightError");
    const weightError = document.getElementById("weightError");
    const termsError = document.getElementById("termsError");

    // Success Modal
    const successModal = document.getElementById("successModal");
    const countdownEl = document.getElementById("countdown");

    // Baymax Voice & Assistant
    const baymaxBox = document.getElementById("baymaxBox");
    const baymaxVoice = document.getElementById("baymaxVoice");
    const aiMessage = document.getElementById("aiMessage");
    const messageText = document.getElementById("messageText");

    let currentStep = 1;
    let computedBmi = null;

    /* =========================================================
       BAYMAX AUDIO & VOICE
       ========================================================= */
    if (baymaxVoice) {
        baymaxVoice.volume = 1.0;
        baymaxVoice.preload = "auto";
        baymaxVoice.load();

        baymaxVoice.addEventListener("ended", () => {
            baymaxVoice.currentTime = 0;
            if (aiMessage) aiMessage.classList.remove("speaking");
            if (baymaxBox) baymaxBox.classList.remove("speaking");
            updateBaymaxMessageForCurrentStep();
        });
    }

    function playBaymaxVoice() {
        if (!baymaxVoice) return;

        baymaxVoice.currentTime = 0;
        const playPromise = baymaxVoice.play();

        if (playPromise !== undefined) {
            playPromise
                .then(() => {
                    if (aiMessage) aiMessage.classList.add("speaking");
                    if (baymaxBox) baymaxBox.classList.add("speaking");
                    if (messageText) {
                        messageText.textContent = "Hello! I am NutriCare AI, your personal healthcare companion! 🤖";
                    }
                })
                .catch((err) => {
                    console.warn("Audio autoplay blocked by browser:", err);
                    if (messageText) {
                        messageText.textContent = "Click Baymax to activate voice assistant! 🔊";
                    }
                });
        }
    }

    function stopBaymaxVoice() {
        if (!baymaxVoice) return;
        baymaxVoice.pause();
        baymaxVoice.currentTime = 0;
        if (aiMessage) aiMessage.classList.remove("speaking");
        if (baymaxBox) baymaxBox.classList.remove("speaking");
        updateBaymaxMessageForCurrentStep();
    }

    function updateBaymaxMessageForCurrentStep() {
        if (!messageText) return;
        if (currentStep === 1) {
            messageText.textContent = "Hi! I'm Baymax. Let's create your profile 🤖";
        } else if (currentStep === 2) {
            messageText.textContent = "Enter your height & weight to calculate your BMI 🧬";
        }
    }

    if (baymaxBox) {
        baymaxBox.addEventListener("mouseenter", () => playBaymaxVoice());
        baymaxBox.addEventListener("mouseleave", () => stopBaymaxVoice());
        baymaxBox.addEventListener("click", () => playBaymaxVoice());
        baymaxBox.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                playBaymaxVoice();
            }
        });
    }

    /* =========================================================
       PASSWORD VISIBILITY TOGGLE
       ========================================================= */
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener("click", () => {
            const isPassword = passwordInput.getAttribute("type") === "password";
            passwordInput.setAttribute("type", isPassword ? "text" : "password");
            passwordToggle.textContent = isPassword ? "🙈" : "👁";
        });
    }

    /* =========================================================
       PASSWORD STRENGTH CALCULATION
       ========================================================= */
    if (passwordInput && strengthFill && strengthText) {
        passwordInput.addEventListener("input", () => {
            const val = passwordInput.value;
            passwordError.textContent = "";
            passwordInput.classList.remove("has-error");

            if (!val) {
                strengthFill.className = "";
                strengthFill.style.width = "0%";
                strengthText.textContent = "Enter at least 8 characters";
                return;
            }

            let score = 0;
            if (val.length >= 8) score++;
            if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score++;
            if (/[0-9]/.test(val)) score++;
            if (/[^a-zA-Z0-9]/.test(val)) score++;

            if (score <= 1) {
                strengthFill.className = "weak";
                strengthText.textContent = "Weak password (add numbers or uppercase)";
            } else if (score === 2 || score === 3) {
                strengthFill.className = "medium";
                strengthText.textContent = "Good password (add symbols for extra strength)";
            } else {
                strengthFill.className = "strong";
                strengthText.textContent = "Strong password! 🛡️";
            }
        });
    }

    /* =========================================================
       CONFIRM PASSWORD VALIDATION
       ========================================================= */
    if (confirmPasswordInput && passwordInput) {
        confirmPasswordInput.addEventListener("input", () => {
            if (confirmPasswordInput.value && confirmPasswordInput.value !== passwordInput.value) {
                confirmPasswordError.textContent = "Passwords do not match.";
                confirmPasswordInput.classList.add("has-error");
            } else {
                confirmPasswordError.textContent = "";
                confirmPasswordInput.classList.remove("has-error");
            }
        });
    }

    /* =========================================================
       LIVE BMI CALCULATOR (STEP 2)
       ========================================================= */
    function calculateBMI() {
        const heightCm = parseFloat(heightInput.value);
        const weightKg = parseFloat(weightInput.value);

        if (!heightCm || !weightKg || heightCm < 50 || weightKg < 10) {
            bmiValue.textContent = "-- BMI";
            bmiStatus.textContent = "Enter height and weight above to calculate your BMI";
            bmiCard.className = "bmi-card";
            computedBmi = null;
            return;
        }

        const heightM = heightCm / 100;
        const bmi = (weightKg / (heightM * heightM)).toFixed(1);
        computedBmi = parseFloat(bmi);
        bmiValue.textContent = `${bmi} BMI`;

        bmiCard.classList.remove("normal", "underweight", "overweight", "obese");

        if (bmi < 18.5) {
            bmiStatus.textContent = "Category: Underweight (Higher calorie intake recommended)";
            bmiCard.classList.add("underweight");
        } else if (bmi < 24.9) {
            bmiStatus.textContent = "Category: Normal weight (Healthy balance! Maintain good habits)";
            bmiCard.classList.add("normal");
        } else if (bmi < 29.9) {
            bmiStatus.textContent = "Category: Overweight (NutriCare AI will suggest optimal portions)";
            bmiCard.classList.add("overweight");
        } else {
            bmiStatus.textContent = "Category: Obese (NutriCare AI will design a gentle wellness plan)";
            bmiCard.classList.add("obese");
        }
    }

    if (heightInput) heightInput.addEventListener("input", calculateBMI);
    if (weightInput) weightInput.addEventListener("input", calculateBMI);

    /* =========================================================
       STEP 1 VALIDATION
       ========================================================= */
    function validateStep1() {
        let isValid = true;

        // Name
        const name = fullNameInput.value.trim();
        if (!name || name.length < 2) {
            nameError.textContent = "Please enter your full name (minimum 2 letters).";
            fullNameInput.classList.add("has-error");
            isValid = false;
        } else {
            nameError.textContent = "";
            fullNameInput.classList.remove("has-error");
        }

        // Email
        const email = emailInput.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email || !emailRegex.test(email)) {
            emailError.textContent = "Please enter a valid email address.";
            emailInput.classList.add("has-error");
            isValid = false;
        } else {
            // Check if email already registered in localStorage
            const existingUsers = getRegisteredUsers();
            const exists = existingUsers.some((u) => u.email.toLowerCase() === email.toLowerCase());
            if (exists) {
                emailError.textContent = "An account with this email already exists. Please sign in.";
                emailInput.classList.add("has-error");
                isValid = false;
            } else {
                emailError.textContent = "";
                emailInput.classList.remove("has-error");
            }
        }

        // Password
        const password = passwordInput.value;
        if (!password || password.length < 8) {
            passwordError.textContent = "Password must be at least 8 characters long.";
            passwordInput.classList.add("has-error");
            isValid = false;
        } else {
            passwordError.textContent = "";
            passwordInput.classList.remove("has-error");
        }

        // Confirm Password
        const confirmPassword = confirmPasswordInput.value;
        if (password !== confirmPassword) {
            confirmPasswordError.textContent = "Passwords do not match.";
            confirmPasswordInput.classList.add("has-error");
            isValid = false;
        } else {
            confirmPasswordError.textContent = "";
            confirmPasswordInput.classList.remove("has-error");
        }

        return isValid;
    }

    /* =========================================================
       STEP 2 VALIDATION
       ========================================================= */
    function validateStep2() {
        let isValid = true;

        const age = parseInt(ageInput.value, 10);
        if (!age || age < 10 || age > 120) {
            ageError.textContent = "Please enter a valid age between 10 and 120.";
            ageInput.classList.add("has-error");
            isValid = false;
        } else {
            ageError.textContent = "";
            ageInput.classList.remove("has-error");
        }

        const gender = genderInput.value;
        if (!gender) {
            genderError.textContent = "Please select your gender.";
            genderInput.classList.add("has-error");
            isValid = false;
        } else {
            genderError.textContent = "";
            genderInput.classList.remove("has-error");
        }

        const height = parseFloat(heightInput.value);
        if (!height || height < 60 || height > 250) {
            heightError.textContent = "Please enter height between 60cm and 250cm.";
            heightInput.classList.add("has-error");
            isValid = false;
        } else {
            heightError.textContent = "";
            heightInput.classList.remove("has-error");
        }

        const weight = parseFloat(weightInput.value);
        if (!weight || weight < 20 || weight > 350) {
            weightError.textContent = "Please enter weight between 20kg and 350kg.";
            weightInput.classList.add("has-error");
            isValid = false;
        } else {
            weightError.textContent = "";
            weightInput.classList.remove("has-error");
        }

        if (!termsCheckbox.checked) {
            termsError.textContent = "You must agree to the Terms and Privacy Policy to create an account.";
            isValid = false;
        } else {
            termsError.textContent = "";
        }

        return isValid;
    }

    /* =========================================================
       STEP NAVIGATION (2 STEPS)
       ========================================================= */
    function goToStep(stepNumber) {
        currentStep = stepNumber;

        // Toggle active form step
        step1.classList.toggle("active", stepNumber === 1);
        step2.classList.toggle("active", stepNumber === 2);

        // Update Header & Labels
        if (stepNumber === 1) {
            stepLabel.textContent = "STEP 01 OF 02";
            formTitle.textContent = "Create your account";
            formSubtitle.textContent = "Let's start with your basic information.";
            progressFill.style.width = "50%";
            pStep1.className = "progress-step active";
            pStep2.className = "progress-step";
        } else if (stepNumber === 2) {
            stepLabel.textContent = "STEP 02 OF 02";
            formTitle.textContent = "Health & BMI Profile";
            formSubtitle.textContent = "NutriCare AI calculates your BMI to personalize recommendations.";
            progressFill.style.width = "100%";
            pStep1.className = "progress-step completed";
            pStep2.className = "progress-step active";
            calculateBMI();
        }

        updateBaymaxMessageForCurrentStep();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    // Step 1 -> Step 2
    if (nextStep1) {
        nextStep1.addEventListener("click", () => {
            if (validateStep1()) {
                goToStep(2);
            }
        });
    }

    // Step 2 -> Step 1
    if (backStep2) {
        backStep2.addEventListener("click", () => {
            goToStep(1);
        });
    }

    /* =========================================================
       LOCAL STORAGE STORAGE HELPERS
       ========================================================= */
    function getRegisteredUsers() {
        try {
            const users = localStorage.getItem("nutricare_users");
            return users ? JSON.parse(users) : [];
        } catch (e) {
            console.error("Error reading nutricare_users:", e);
            return [];
        }
    }

    function saveUser(userObj) {
        try {
            const users = getRegisteredUsers();
            users.push(userObj);
            localStorage.setItem("nutricare_users", JSON.stringify(users));
            // Also store as current email for instant pre-fill on login
            localStorage.setItem("nutricare_email", userObj.email);
            localStorage.setItem("nutricare_just_registered", "true");
            localStorage.setItem("nutricare_registered_name", userObj.fullName);
            return true;
        } catch (e) {
            console.error("Error saving user:", e);
            return false;
        }
    }

    /* =========================================================
       SUBMIT REGISTRATION (STEP 2)
       ========================================================= */
    if (registrationForm) {
        registrationForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            // Validate Step 2 fields and terms
            if (!validateStep2()) {
                return;
            }

            if (createAccountButton) {
                createAccountButton.disabled = true;
                createAccountButton.innerHTML = "Creating Account... ✦";
            }

            const userProfile = {
                id: "user_" + Date.now(),
                fullName: fullNameInput.value.trim(),
                email: emailInput.value.trim().toLowerCase(),
                password: passwordInput.value,
                age: parseInt(ageInput.value, 10),
                gender: genderInput.value,
                height: parseFloat(heightInput.value),
                weight: parseFloat(weightInput.value),
                bmi: computedBmi,
                registeredAt: new Date().toISOString()
            };

            // 1. Send to MongoDB Backend API (http://127.0.0.1:8000/api/register)
            try {
                const response = await fetch(                `${API_BASE}/api/register`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(userProfile)
                });

                if (response.ok) {
                    const data = await response.json();
                    console.log("✅ User registered in MongoDB database successfully:", data);
                    if (data.user && data.user.id) {
                        userProfile.id = data.user.id;
                    }
                } else {
                    const errData = await response.json().catch(() => ({}));
                    console.warn("MongoDB API returned warning:", errData.detail || response.statusText);
                }
            } catch (networkError) {
                console.warn(
                    "Backend MongoDB server offline, saving to Local Storage cache:",
                    networkError.message
                );
            }

            // 2. Also save to LocalStorage cache for immediate persistence
            console.log("Saving user profile to NutriCare local cache:", userProfile);
            saveUser(userProfile);

            // Play voice celebratory feedback if possible
            if (baymaxVoice) {
                baymaxVoice.currentTime = 0;
                baymaxVoice.play().catch(() => {});
            }

            // Show success modal
            if (successModal) {
                successModal.classList.add("active");

                let secondsLeft = 3;
                countdownEl.textContent = secondsLeft;

                const timer = setInterval(() => {
                    secondsLeft--;
                    if (countdownEl) countdownEl.textContent = secondsLeft;

                    if (secondsLeft <= 0) {
                        clearInterval(timer);
                        window.location.href = "../Login.html?registered=true";
                    }
                }, 1000);
            } else {
                alert("Account created successfully! Taking you to login.");
                window.location.href = "../Login.html?registered=true";
            }
        });
    }

    console.log("NutriCare AI 2-Step Registration Script Initialized");
});
