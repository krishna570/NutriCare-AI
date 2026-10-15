/* =========================================================
   NutriCare AI - Main JavaScript
   Baymax Hover + Voice + Login
   ========================================================= */

/* API BASE — same origin when served by the Node.js backend
   (port 8000), direct call when opened as a file. */
const API_BASE =
    (location.protocol.startsWith("http") && location.port === "8000")
        ? ""
        : "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {

    /* =========================================================
       ELEMENTS
       ========================================================= */

    const baymaxBox = document.querySelector(".baymax-box");
    const baymaxImage = document.querySelector(".baymax-box img");
    const baymaxVoice = document.getElementById("baymaxVoice");
    const aiStatus = document.querySelector(".ai-status");
    const loginForm = document.getElementById("loginForm");


    /* =========================================================
       BAYMAX VOICE SETTINGS
       ========================================================= */

    let voiceReady = false;
    let voiceUnlocked = false;

    if (baymaxVoice) {

        baymaxVoice.preload = "auto";
        baymaxVoice.volume = 1.0;

        // Force browser to load the MP3
        baymaxVoice.load();

        baymaxVoice.addEventListener("canplaythrough", () => {
            voiceReady = true;
            console.log("✅ Baymax voice loaded successfully.");
        });

        baymaxVoice.addEventListener("loadeddata", () => {
            voiceReady = true;
            console.log("🔊 Baymax MP3 is ready.");
        });

        baymaxVoice.addEventListener("error", () => {
            voiceReady = false;

            console.error(
                "❌ Baymax voice could not be loaded.",
                baymaxVoice.error
            );
        });

        baymaxVoice.addEventListener("ended", () => {
            baymaxVoice.currentTime = 0;
        });
    }


    /* =========================================================
       PLAY BAYMAX VOICE
       ========================================================= */

    function playBaymaxVoice() {

        if (!baymaxVoice) {
            console.warn("⚠️ #baymaxVoice was not found.");
            return;
        }

        // Start the voice from beginning
        baymaxVoice.currentTime = 0;

        const playPromise = baymaxVoice.play();

        if (playPromise !== undefined) {

            playPromise
                .then(() => {

                    voiceUnlocked = true;

                    console.log("🔊 Baymax voice playing.");

                    if (aiStatus) {

                        aiStatus.innerHTML =
                            '<span class="status-dot"></span> Baymax is speaking...';

                    }

                })
                .catch((error) => {

                    console.warn(
                        "⚠️ Browser blocked Baymax voice:",
                        error
                    );

                    if (aiStatus) {

                        aiStatus.innerHTML =
                            '<span class="status-dot"></span> Click Baymax once to enable voice';

                    }

                });
        }
    }


    /* =========================================================
       STOP BAYMAX VOICE
       ========================================================= */

    function stopBaymaxVoice() {

        if (!baymaxVoice) return;

        baymaxVoice.pause();

        baymaxVoice.currentTime = 0;

        if (aiStatus) {

            aiStatus.innerHTML =
                '<span class="status-dot"></span> Hover to activate your AI companion';

        }
    }


    /* =========================================================
       BAYMAX HOVER
       ========================================================= */

    if (baymaxBox) {

        /*
         * When mouse enters Baymax:
         * 1. CSS shows Baymax
         * 2. JavaScript starts voice
         */

        baymaxBox.addEventListener("mouseenter", () => {

            playBaymaxVoice();

        });


        /*
         * When mouse leaves:
         * Stop Baymax voice
         */

        baymaxBox.addEventListener("mouseleave", () => {

            stopBaymaxVoice();

        });


        /* =====================================================
           CLICK = USER ACTIVATION

           Chrome/Edge may block audio that starts only from
           hover. A click counts as user interaction.
           ===================================================== */

        baymaxBox.addEventListener("click", () => {

            playBaymaxVoice();

        });


        /* =====================================================
           TOUCH SUPPORT
           ===================================================== */

        baymaxBox.addEventListener(
            "touchstart",
            () => {

                playBaymaxVoice();

            },
            {
                passive: true
            }
        );
    }


    /* =========================================================
       KEYBOARD SUPPORT
       ========================================================= */

    if (baymaxBox) {

        baymaxBox.setAttribute("tabindex", "0");

        baymaxBox.setAttribute(
            "role",
            "button"
        );

        baymaxBox.setAttribute(
            "aria-label",
            "Activate NutriCare AI Baymax assistant"
        );


        baymaxBox.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {

                    event.preventDefault();

                    playBaymaxVoice();

                }
            }
        );
    }


    /* =========================================================
       LOGIN FORM
       ========================================================= */

    if (loginForm) {

        loginForm.addEventListener(
            "submit",
            async (event) => {

                event.preventDefault();


                /* -------------------------------------------------
                   GET INPUTS
                   ------------------------------------------------- */

                const emailInput =
                    document.getElementById("email");

                const passwordInput =
                    document.getElementById("password");

                const rememberInput =
                    document.getElementById("remember");

                const loginButton =
                    loginForm.querySelector(".login-btn");


                /* -------------------------------------------------
                   VALUES
                   ------------------------------------------------- */

                const email =
                    emailInput
                        ? emailInput.value.trim()
                        : "";

                const password =
                    passwordInput
                        ? passwordInput.value
                        : "";

                const remember =
                    rememberInput
                        ? rememberInput.checked
                        : false;


                /* -------------------------------------------------
                   VALIDATION
                   ------------------------------------------------- */

                if (!email || !password) {

                    alert(
                        "Please enter your email and password."
                    );

                    return;
                }


                /* -------------------------------------------------
                   DISABLE LOGIN BUTTON
                   ------------------------------------------------- */

                if (loginButton) {

                    loginButton.disabled = true;

                    loginButton.dataset.originalText =
                        loginButton.textContent;

                    loginButton.textContent =
                        "Logging in...";
                }


                /* =================================================
                   SEND LOGIN REQUEST TO BACKEND
                   ================================================= */

                try {

                    let authenticated = false;
                    let userData = null;

                    // 1. First attempt login via Backend API (if server is running)
                    try {

                        const response =
                            await fetch(
                                `${API_BASE}/api/login`,
                                {
                                    method: "POST",
                                    headers: {
                                        "Content-Type": "application/json"
                                    },
                                    body: JSON.stringify({
                                        email: email,
                                        password: password,
                                        remember: remember
                                    })
                                }
                            );

                        let data = {};
                        try {
                            data = await response.json();
                        } catch {
                            data = {};
                        }

                        if (!response.ok) {
                            throw new Error(
                                data.detail ||
                                data.message ||
                                "Invalid email or password."
                            );
                        }

                        console.log("✅ Backend login successful:", data);
                        authenticated = true;
                        userData = data.user || data;

                    } catch (apiError) {

                        console.warn(
                            "Backend API offline or returned error. Checking registered accounts in storage...",
                            apiError.message
                        );

                        // 2. Fallback: Authenticate against localStorage registered users
                        let registeredUsers = [];
                        try {
                            const stored = localStorage.getItem("nutricare_users");
                            registeredUsers = stored ? JSON.parse(stored) : [];
                        } catch (e) {
                            registeredUsers = [];
                        }

                        const matchedUser = registeredUsers.find(
                            (u) => u.email.toLowerCase() === email.toLowerCase()
                        );

                        if (matchedUser) {
                            if (matchedUser.password === password) {
                                authenticated = true;
                                userData = matchedUser;
                            } else {
                                throw new Error(
                                    "Incorrect password. Please verify and try again."
                                );
                            }
                        } else {
                            throw new Error(
                                apiError.message && !apiError.message.includes("fetch") && !apiError.message.includes("Failed")
                                    ? apiError.message
                                    : "No account found with this email. Please click 'Create Account' to sign up."
                            );
                        }
                    }

                    if (!authenticated || !userData) {
                        throw new Error("Authentication failed.");
                    }

                    /* -------------------------------------------------
                       REMEMBER EMAIL
                       ------------------------------------------------- */

                    if (remember) {
                        localStorage.setItem("nutricare_email", email);
                    } else {
                        localStorage.removeItem("nutricare_email");
                    }

                    /* -------------------------------------------------
                       STORE USER SESSION
                       ------------------------------------------------- */

                    localStorage.setItem("nutricare_current_user", JSON.stringify(userData));
                    localStorage.setItem("nutricare_session_user", JSON.stringify(userData));
                    sessionStorage.setItem("nutricare_current_user", JSON.stringify(userData));

                    /* -------------------------------------------------
                       LOGIN SUCCESS FEEDBACK & REDIRECT TO MAIN
                       ------------------------------------------------- */

                    const userName = userData.fullName || userData.name || email.split("@")[0];

                    if (aiStatus) {
                        aiStatus.innerHTML =
                            `<span class="status-dot"></span> Welcome back, ${userName}! 👋`;
                    }

                    if (loginAlert) {
                        loginAlert.className = "login-alert success";
                        loginAlert.innerHTML =
                            `<span>✅</span> <div><strong>Login Successful!</strong><br>Welcome back, ${userName}! Redirecting to dashboard...</div>`;
                        loginAlert.style.display = "flex";
                    }

                    // Play Baymax voice if available
                    if (baymaxVoice) {
                        baymaxVoice.currentTime = 0;
                        baymaxVoice.play().catch(() => {});
                    }

                    // Redirect to Main/index.html
                    setTimeout(() => {
                        window.location.href = "../Main/index.html";
                    }, 600);

                }


                /* =================================================
                   LOGIN ERROR
                   ================================================= */

                catch (error) {

                    console.error(
                        "❌ Login error:",
                        error
                    );

                    if (loginAlert) {
                        loginAlert.className = "login-alert error";
                        loginAlert.innerHTML =
                            `<span>⚠️</span> <div><strong>Login Failed</strong><br>${error.message || "Invalid email or password."}</div>`;
                        loginAlert.style.display = "flex";
                    } else {
                        alert(
                            error.message ||
                            "Login failed. Please check your details."
                        );
                    }
                }


                /* =================================================
                   ENABLE LOGIN BUTTON AGAIN
                   ================================================= */

                finally {

                    if (loginButton) {

                        loginButton.disabled = false;

                        loginButton.textContent =
                            loginButton.dataset.originalText ||
                            "Login";
                    }
                }

            }
        );
    }


    /* =========================================================
       CHECK REGISTRATION REDIRECT & LOAD REMEMBERED EMAIL
       ========================================================= */

    const urlParams = new URLSearchParams(window.location.search);
    const justRegistered =
        urlParams.get("registered") === "true" ||
        localStorage.getItem("nutricare_just_registered") === "true";

    const savedEmail =
        localStorage.getItem(
            "nutricare_email"
        );

    const emailInput =
        document.getElementById("email");

    const passwordInput =
        document.getElementById("password");

    const rememberInput =
        document.getElementById("remember");

    const loginAlert =
        document.getElementById("loginAlert");


    if (
        savedEmail &&
        emailInput
    ) {

        emailInput.value =
            savedEmail;

        if (rememberInput) {

            rememberInput.checked =
                true;
        }
    }

    if (justRegistered && loginAlert) {

        const registeredName =
            localStorage.getItem("nutricare_registered_name");

        loginAlert.className = "login-alert success";
        loginAlert.innerHTML =
            `<span>✅</span> <div><strong>Account Created Successfully!</strong><br>${registeredName ? `Welcome, ${registeredName}! ` : ''}Please enter your password to sign in.</div>`;
        loginAlert.style.display = "flex";

        localStorage.removeItem("nutricare_just_registered");

        if (passwordInput) {
            setTimeout(() => {
                passwordInput.focus();
            }, 300);
        }
    }


    /* =========================================================
       FORGOT PASSWORD
       ========================================================= */

    const forgotPassword =
        document.querySelector(".forgot");


    if (forgotPassword) {

        forgotPassword.addEventListener(
            "click",
            (event) => {

                event.preventDefault();


                const emailInput =
                    document.getElementById("email");

                const email =
                    emailInput
                        ? emailInput.value.trim()
                        : "";


                if (!email) {

                    alert(
                        "Please enter your email address first."
                    );

                    if (emailInput) {

                        emailInput.focus();

                    }

                    return;
                }


                alert(
                    "Password reset for " +
                    email +
                    " will be connected to the backend soon."
                );

            }
        );
    }


    /* =========================================================
       CREATE ACCOUNT LINK NAVIGATION
       ========================================================= */

    const createAccount =
        document.querySelector(".signup a");


    if (createAccount) {

        createAccount.addEventListener(
            "click",
            (event) => {

                // Smoothly navigate to Registration page
                window.location.href = "./Reg/Registration.html";

            }
        );
    }


    /* =========================================================
       DEBUG INFORMATION
       ========================================================= */

    console.log(
        "=========================================="
    );

    console.log(
        "🥗 NutriCare AI JavaScript loaded"
    );

    console.log(
        "🤖 Baymax element:",
        baymaxBox
            ? "FOUND"
            : "NOT FOUND"
    );

    console.log(
        "🎞️ Baymax image:",
        baymaxImage
            ? "FOUND"
            : "NOT FOUND"
    );

    console.log(
        "🔊 Baymax audio:",
        baymaxVoice
            ? "FOUND"
            : "NOT FOUND"
    );

    console.log(
        "🔐 Login form:",
        loginForm
            ? "FOUND"
            : "NOT FOUND"
    );

    console.log(
        "=========================================="
    );

});