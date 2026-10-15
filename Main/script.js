
/* =========================================================
   API BASE
   When this page is served by the Node.js backend (port 8000)
   every fetch stays on the same origin. Opened as a file, or
   from another static server, it calls the backend directly.
   ========================================================= */
const API_BASE =
    (location.protocol.startsWith("http") && location.port === "8000")
        ? ""
        : "http://127.0.0.1:8000";

    /* ================= USER SESSION & GREETING ================= */
    (function setupUserSession() {
        let currentUser = null;
        try {
            const stored = localStorage.getItem("nutricare_current_user") || localStorage.getItem("nutricare_session_user");
            if (stored) currentUser = JSON.parse(stored);
        } catch (e) {
            currentUser = null;
        }

        if (currentUser) {
            const name = currentUser.fullName || currentUser.name || (currentUser.email ? currentUser.email.split("@")[0] : "User");
            const welcomeHeading = document.querySelector(".welcome h2");
            if (welcomeHeading) {
                welcomeHeading.innerHTML = `Welcome, <span>${name}</span>! 👋`;
            }

            const profileEl = document.querySelector(".profile");
            if (profileEl) {
                profileEl.title = `${name} (${currentUser.email || ''})`;
                const initial = name.charAt(0).toUpperCase();
                const avatarEl = profileEl.querySelector(".avatar");
                const initialHTML = `<span style="font-weight:700; color:var(--cyan);">${initial}</span>`;
                if (avatarEl) avatarEl.innerHTML = initialHTML;
                else profileEl.innerHTML = initialHTML;

                const clickTarget = avatarEl || profileEl;
                clickTarget.addEventListener("click", () => {
                    const doLogout = confirm(`Signed in as: ${name}\nEmail: ${currentUser.email || ''}\n\nWould you like to log out?`);
                    if (doLogout) {
                        localStorage.removeItem("nutricare_current_user");
                        localStorage.removeItem("nutricare_session_user");
                        sessionStorage.removeItem("nutricare_current_user");
                        window.location.href = "../Login/Login.html";
                    }
                });
            }
        }
    })();

    /* ================= DATE ================= */
    const dateElement = document.getElementById("currentDate");
    const today = new Date();

    if (dateElement) {
        dateElement.textContent = today.toLocaleDateString("en-IN", {
            weekday: "short",
            day: "2-digit",
            month: "short",
            year: "numeric"
        });
    }

    /* ================= FILE UPLOAD (non-food reports) ================= */
    function handleFile(input, outputId) {
        const output = document.getElementById(outputId);

        if (!input.files || input.files.length === 0) {
            output.textContent = "No file selected";
            return;
        }

        const file = input.files[0];
        output.textContent = "✓ " + file.name;
        addReport(file);
        updateReportCount();
    }

    /* ================= FOOD IMAGE ANALYSIS ================= */
    async function analyzeFoodImage(input) {
        if (!input.files || input.files.length === 0) return;

        const file = input.files[0];

        // Update upload label text
        const fileLabel = document.getElementById("foodFile");
        if (fileLabel) fileLabel.textContent = "✓ " + file.name;

        // Show result panel in LOADING state
        const panel       = document.getElementById("foodResultPanel");
        const loadingDiv  = document.getElementById("foodResultLoading");
        const contentDiv  = document.getElementById("foodResultContent");
        const errorDiv    = document.getElementById("foodResultError");
        const subtitle    = document.getElementById("foodResultSubtitle");

        panel.style.display      = "block";
        loadingDiv.style.display = "block";
        contentDiv.style.display = "none";
        errorDiv.style.display   = "none";
        if (subtitle) subtitle.textContent = "Analyzing your food image...";

        // Smooth scroll to result panel
        panel.scrollIntoView({ behavior: "smooth", block: "start" });

        // Show image preview immediately
        const previewImg = document.getElementById("foodPreviewImg");
        const previewUrl = URL.createObjectURL(file);
        if (previewImg) previewImg.src = previewUrl;

        // Convert image to base64
        let base64 = "";
        try {
            base64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload  = e => resolve(e.target.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        } catch (err) {
            showFoodError("Could not read the image file. Please try again.");
            return;
        }

        // Call Node.js → Python API
        try {
            const response = await fetch(`${API_BASE}/api/food/predict`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ image_base64: base64 })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                const errMsg = data.detail || (data.error && data.error.detail) || "Prediction failed.";
                showFoodError(errMsg);
                return;
            }

            renderFoodResult(data.prediction);

        } catch (err) {
            showFoodError(
                "Could not reach the NutriCare AI server. " +
                "Make sure Node.js (port 8000) and Python (port 5000) are both running."
            );
        }
    }

    /* Render the food prediction result into the panel */
    function renderFoodResult(pred) {
        const loadingDiv = document.getElementById("foodResultLoading");
        const contentDiv = document.getElementById("foodResultContent");
        const subtitle   = document.getElementById("foodResultSubtitle");

        // Hide loading, show content
        loadingDiv.style.display = "none";
        contentDiv.style.display = "block";
        if (subtitle) subtitle.textContent = "Result ready";

        // ── Food name ───────────────────────────────────────────
        const nameEl = document.getElementById("foodNameDisplay");
        if (nameEl) nameEl.textContent = pred.display_name || pred.food_name || "Unknown";

        // ── Confidence bar ───────────────────────────────────────
        const bar  = document.getElementById("confidenceBar");
        const pct  = document.getElementById("confidenceText");
        const conf = pred.confidence || 0;

        if (bar) {
            // Trigger animation by setting width after a tiny delay
            bar.style.width = "0%";
            setTimeout(() => { bar.style.width = conf + "%"; }, 60);
        }
        if (pct) pct.textContent = conf.toFixed(1) + "%";

        // ── Nutrition stats ──────────────────────────────────────
        const n = pred.nutrition || {};
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val !== undefined ? val : "—";
        };
        set("statKcal",    n.kcal);
        set("statProtein", n.protein_g);
        set("statCarbs",   n.carbs_g);
        set("statFat",     n.fat_g);
        set("statSugar",   n.sugar_g);
        set("statFibre",   n.fibre_g);

        // Update dashboard "Today's Calories" card
        const calCard = document.querySelector(".card:nth-child(1) .card-value");
        if (calCard && n.kcal) {
            calCard.innerHTML = `${n.kcal} <span>kcal</span>`;
        }
        const protCard = document.querySelector(".card:nth-child(2) .card-value");
        if (protCard && n.protein_g) {
            protCard.innerHTML = `${n.protein_g} <span>g</span>`;
        }
        const sugarCard = document.querySelector(".card:nth-child(3) .card-value");
        if (sugarCard && n.sugar_g) {
            sugarCard.innerHTML = `${n.sugar_g} <span>g</span>`;
        }

        // ── Risk badges ──────────────────────────────────────────
        const badges  = document.getElementById("riskBadges");
        const flags   = pred.risk_flags || {};
        badges.innerHTML = "";

        if (flags.high_sugar)   badges.innerHTML += `<span class="risk-badge sugar">🍬 High Sugar</span>`;
        if (flags.high_sodium)  badges.innerHTML += `<span class="risk-badge sodium">🧂 High Sodium</span>`;
        if (flags.high_calories)badges.innerHTML += `<span class="risk-badge calories">🔥 High Calorie</span>`;
        if (!flags.high_sugar && !flags.high_sodium && !flags.high_calories) {
            badges.innerHTML = `<span class="risk-badge safe">✅ Balanced Choice</span>`;
        }

        // ── Top-5 list ───────────────────────────────────────────
        const top5El = document.getElementById("top5List");
        top5El.innerHTML = "";

        const top5 = pred.top5 || [];
        top5.forEach(item => {
            const isFirst = item.rank === 1;
            const row = document.createElement("div");
            row.className = "top5-row";
            if (isFirst) row.style.border = "1px solid rgba(0,245,212,0.3)";

            row.innerHTML = `
                <span class="top5-rank">${isFirst ? "🥇" : item.rank}</span>
                <span class="top5-name">${item.food.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
                <div class="top5-bar-wrap">
                    <div class="top5-bar" style="width:${item.confidence}%"></div>
                </div>
                <span class="top5-pct">${item.confidence.toFixed(1)}%</span>
            `;
            top5El.appendChild(row);
        });
    }

    /* Show error state in the food result panel */
    function showFoodError(message) {
        const loadingDiv = document.getElementById("foodResultLoading");
        const contentDiv = document.getElementById("foodResultContent");
        const errorDiv   = document.getElementById("foodResultError");
        const errorMsg   = document.getElementById("foodErrorMsg");
        const subtitle   = document.getElementById("foodResultSubtitle");

        loadingDiv.style.display = "none";
        contentDiv.style.display = "none";
        errorDiv.style.display   = "block";
        if (errorMsg) errorMsg.textContent = message;
        if (subtitle) subtitle.textContent  = "Error";
    }

    /* ================= REPORT LIST ================= */
    function addReport(file) {
        const list = document.getElementById("reportsList");

        if (list.innerText.includes("No reports yet")) {
            list.innerHTML = "";
        }

        const item = document.createElement("div");
        item.className = "report";

        item.innerHTML = `
            <div class="report-icon">📄</div>
            <div class="report-info">
                <strong>${escapeHTML(file.name)}</strong>
                <span>${formatFileSize(file.size)}</span>
            </div>
            <div class="report-status">Uploaded</div>
        `;

        list.prepend(item);
    }

    function updateReportCount() {
        const reports = document.querySelectorAll("#reportsList .report");
        const count = document.querySelectorAll("#reportsList .report-info strong").length;
        const value = document.querySelector(".card:nth-child(4) .card-value");
        if (value) {
            value.innerHTML = `${count} <span>uploaded</span>`;
        }
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    function escapeHTML(value) {
        return value
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    /* ============================================================
       LIVE PHONE STEP TRACKER
       ============================================================ */

    const STEP_GOAL = 8000;
    const STEP_STORAGE = "nutricare_steps_today";
    const STEP_DATE_STORAGE = "nutricare_steps_date";

    let stepCount = 0;
    let tracking = false;
    let lastMagnitude = null;
    let lastStepTime = 0;
    let recentStepTimes = [];
    let motionListenerAttached = false;
    let motionSamples = [];
    let lastMotionUiUpdate = 0;

    // Thresholds are intentionally conservative to reduce false steps.
    const STEP_THRESHOLD = 2.0;
    const MIN_STEP_INTERVAL = 280;
    const MAX_STEP_INTERVAL = 1600;

    function getTodayKey() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
    }

    function loadSteps() {
        const savedDate = localStorage.getItem(STEP_DATE_STORAGE);
        const todayKey = getTodayKey();

        if (savedDate !== todayKey) {
            stepCount = 0;
            localStorage.setItem(STEP_STORAGE, "0");
            localStorage.setItem(STEP_DATE_STORAGE, todayKey);
        } else {
            stepCount = parseInt(localStorage.getItem(STEP_STORAGE) || "0", 10);
            if (!Number.isFinite(stepCount)) stepCount = 0;
        }

        updateStepUI();
    }

    function saveSteps() {
        localStorage.setItem(STEP_STORAGE, String(stepCount));
        localStorage.setItem(STEP_DATE_STORAGE, getTodayKey());
    }

    function updateStepUI() {
        const countEl = document.getElementById("stepCount");
        const dashboardEl = document.getElementById("dashboardSteps");
        const ring = document.getElementById("stepRing");
        const distanceEl = document.getElementById("stepDistance");
        const caloriesEl = document.getElementById("stepCalories");
        const speedEl = document.getElementById("stepSpeed");

        if (!countEl) return;

        countEl.textContent = stepCount.toLocaleString("en-IN");

        if (dashboardEl) dashboardEl.textContent = stepCount.toLocaleString("en-IN");

        const progress = Math.min(stepCount / STEP_GOAL, 1);
        if (ring) {
            ring.style.background =
                `conic-gradient(var(--cyan) ${progress * 360}deg, rgba(255,255,255,.06) ${progress * 360}deg)`;
        }

        // Approximate values for the prototype.
        const distanceKm = stepCount * 0.00075;
        const calories = Math.round(stepCount * 0.04);

        if (distanceEl) distanceEl.textContent = distanceKm.toFixed(2);
        if (caloriesEl) caloriesEl.textContent = calories.toLocaleString("en-IN");

        // Calculate approximate current walking cadence.
        const now = Date.now();
        recentStepTimes = recentStepTimes.filter(t => now - t <= 60000);
        if (speedEl) speedEl.textContent = recentStepTimes.length;

        const status = document.getElementById("dashboardStepStatus");
        if (status) {
            status.textContent = tracking ? "Live sensor tracking" : "Step tracker ready";
        }
    }

    function setStepStatus(message, type = "") {
        const status = document.getElementById("stepStatus");
        const badge = document.getElementById("stepLiveBadge");

        if (status) {
            status.className = "step-status" + (type ? " " + type : "");
            status.innerHTML = message;
        }

        if (badge) {
            if (type === "live") {
                badge.textContent = "● LIVE";
                badge.style.color = "var(--cyan)";
            } else if (type === "error") {
                badge.textContent = "ERROR";
                badge.style.color = "var(--danger)";
            } else {
                badge.textContent = "NOT STARTED";
                badge.style.color = "var(--warning)";
            }
        }
    }

    async function startStepTracking() {
        if (tracking) {
            stopStepTracking();
            return;
        }

        // iPhone/iPad Safari requires explicit permission after a user gesture.
        if (typeof DeviceMotionEvent === "undefined") {
            setStepStatus(
                "❌ This device/browser does not expose a motion sensor. Try the latest Chrome on Android or Safari on iPhone.",
                "error"
            );
            return;
        }

        try {
            if (typeof DeviceMotionEvent.requestPermission === "function") {
                const permission = await DeviceMotionEvent.requestPermission();

                if (permission !== "granted") {
                    setStepStatus(
                        "⚠️ Motion permission was not granted. Please allow motion access and try again.",
                        "error"
                    );
                    return;
                }
            }

            attachMotionListener();
        } catch (error) {
            console.error(error);
            setStepStatus(
                "❌ Motion permission could not be enabled. Make sure the page is running over HTTPS and try again.",
                "error"
            );
        }
    }

    function attachMotionListener() {
        if (motionListenerAttached) return;

        window.addEventListener("devicemotion", handleMotion, { passive: true });
        motionListenerAttached = true;
        tracking = true;

        const button = document.getElementById("startStepBtn");
        if (button) {
            button.textContent = "⏸ Stop Tracking";
        }

        setStepStatus(
            "🟢 <b>LIVE:</b> Phone motion access is active. Keep the phone with you and start walking. Steps will appear here automatically.",
            "live"
        );

        if (document.getElementById("dashboardStepStatus")) {
            document.getElementById("dashboardStepStatus").textContent = "Live sensor tracking";
        }
    }

    function stopStepTracking() {
        if (motionListenerAttached) {
            window.removeEventListener("devicemotion", handleMotion);
            motionListenerAttached = false;
        }

        tracking = false;

        const button = document.getElementById("startStepBtn");
        if (button) {
            button.textContent = "📱 Allow & Start";
        }

        setStepStatus(
            "⏸ Step tracking paused. Tap <b>Allow & Start</b> whenever you want to continue.",
            ""
        );

        updateStepUI();
    }

    function handleMotion(event) {
        if (!tracking) return;

        const acc = event.accelerationIncludingGravity || event.acceleration;

        if (!acc) return;

        const x = Number(acc.x) || 0;
        const y = Number(acc.y) || 0;
        const z = Number(acc.z) || 0;

        // Magnitude removes most dependence on phone orientation.
        const magnitude = Math.sqrt(x*x + y*y + z*z);

        if (lastMagnitude === null) {
            lastMagnitude = magnitude;
            return;
        }

        const delta = Math.abs(magnitude - lastMagnitude);
        lastMagnitude = magnitude;

        // Visual live signal.
        updateMotionBars(delta);

        const now = Date.now();

        // Adaptive signal history helps avoid counting every sensor vibration.
        motionSamples.push({ time: now, delta });
        motionSamples = motionSamples.filter(s => now - s.time < 1000);

        if (delta >= STEP_THRESHOLD && now - lastStepTime >= MIN_STEP_INTERVAL) {
            // Require a second part of the motion signal before accepting a step.
            const hasRecentMovement = motionSamples.some(
                s => s.time < now - 80 && s.delta >= STEP_THRESHOLD * 0.55
            );

            if (hasRecentMovement || delta >= STEP_THRESHOLD * 1.55) {
                registerStep(now);
            }
        }
    }

    function registerStep(now) {
        if (now - lastStepTime < MIN_STEP_INTERVAL) return;

        // Prevent unrealistically fast repeated steps.
        if (lastStepTime && now - lastStepTime < 180) return;

        lastStepTime = now;
        stepCount += 1;
        recentStepTimes.push(now);
        recentStepTimes = recentStepTimes.filter(t => now - t <= 60000);

        saveSteps();
        updateStepUI();

        const badge = document.getElementById("stepLiveBadge");
        if (badge) {
            badge.textContent = "● STEP DETECTED";
            badge.style.color = "var(--cyan)";

            clearTimeout(window.stepBadgeTimer);
            window.stepBadgeTimer = setTimeout(() => {
                if (tracking) badge.textContent = "● LIVE";
            }, 650);
        }
    }

    function updateMotionBars(delta) {
        const now = Date.now();
        if (now - lastMotionUiUpdate < 70) return;
        lastMotionUiUpdate = now;

        const bars = document.querySelectorAll(".motion-bar");
        const level = Math.min(8, Math.max(0, Math.round(delta * 1.5)));

        bars.forEach((bar, index) => {
            bar.classList.toggle("active", index < level);
            if (index < level) {
                bar.style.height = `${8 + index * 2}px`;
            } else {
                bar.style.height = "8px";
            }
        });
    }

    function resetSteps() {
        const confirmed = confirm("Reset today's NutriCare step count to 0?");
        if (!confirmed) return;

        stepCount = 0;
        recentStepTimes = [];
        lastMagnitude = null;
        lastStepTime = 0;

        saveSteps();
        updateStepUI();

        setStepStatus(
            tracking
                ? "🟢 <b>LIVE:</b> Step count reset. Start walking to detect new steps."
                : "📱 Step count reset. Tap <b>Allow & Start</b> to begin tracking.",
            tracking ? "live" : ""
        );
    }

    function scrollToSteps() {
        const panel = document.getElementById("stepTrackerPanel");
        if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // Load saved count immediately when the page opens.
    loadSteps();

    // Keep the daily count/date correct if the page stays open across midnight.
    setInterval(() => {
        const storedDate = localStorage.getItem(STEP_DATE_STORAGE);
        if (storedDate !== getTodayKey()) loadSteps();
        updateStepUI();
    }, 30000);

    /* ================= CHAT ================= */
    async function sendMessage() {
        const input    = document.getElementById("chatInput");
        const messages = document.getElementById("messages");
        const text     = input.value.trim();

        if (!text) return;

        // ── Render user bubble ───────────────────────────────────
        const userBubble = document.createElement("div");
        userBubble.className   = "message user";
        userBubble.textContent = text;
        messages.appendChild(userBubble);

        input.value = "";
        messages.scrollTop = messages.scrollHeight;

        // ── Render loading bubble ────────────────────────────────
        const loadingBubble = document.createElement("div");
        loadingBubble.className = "message bot";
        loadingBubble.innerHTML =
            "<span style='opacity:.55;'>🤖 NutriCare AI is thinking…</span>";
        messages.appendChild(loadingBubble);
        messages.scrollTop = messages.scrollHeight;

        // Local LLM answers can take a while — tell the user we're alive.
        const slowHint = setTimeout(() => {
            loadingBubble.innerHTML =
                "<span style='opacity:.55;'>🤖 NutriCare AI is still thinking…<br>" +
                "<small>The local AI model can take up to a minute.</small></span>";
            messages.scrollTop = messages.scrollHeight;
        }, 8000);

        // ── Call Node.js → RAG / Fallback API ───────────────────
        try {
            const response = await fetch(`${API_BASE}/api/chat`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ question: text, profile: buildProfilePayload() })
            });

            const data = await response.json();
            clearTimeout(slowHint);

            if (!response.ok || !data.success) {
                loadingBubble.innerHTML =
                    "⚠️ " + escapeHTML(data.detail || "The AI could not answer right now. Please try again.");
                messages.scrollTop = messages.scrollHeight;
                return;
            }

            // Render answer — preserve line breaks as <br>
            loadingBubble.innerHTML = escapeHTML(data.answer)
                .replace(/\n/g, "<br>");

        } catch (err) {
            clearTimeout(slowHint);
            loadingBubble.innerHTML =
                "❌ Could not reach the NutriCare AI server.<br>" +
                "Make sure Node.js is running on port 8000.<br>" +
                "<small style='opacity:.6'>(" + err.message + ")</small>";
        }

        messages.scrollTop = messages.scrollHeight;
    }


    /* ================= FOCUS CHAT ================= */
    function focusChat() {
        document.getElementById("chatPanel").scrollIntoView({
            behavior: "smooth"
        });

        setTimeout(() => {
            document.getElementById("chatInput").focus();
        }, 500);
    }


    /* =========================================================
       PERSONALISED FOOD PLAN
       Report/profile → foods you can eat + 15-day food chart
       ========================================================= */

    let lastFoodPlan = null;

    function readStoredUser() {
        try {
            const stored = localStorage.getItem("nutricare_current_user") ||
                           localStorage.getItem("nutricare_session_user");
            if (stored) return JSON.parse(stored);

            // Fallback: most recently saved registration in the local cache
            const cached = localStorage.getItem("nutricare_users");
            if (cached) {
                const users = JSON.parse(cached);
                if (Array.isArray(users) && users.length) return users[users.length - 1];
            }
        } catch (e) {}
        return null;
    }

    function getSelectedConditions() {
        const boxes = Array.from(document.querySelectorAll(".planCondition"));
        const selected = boxes.filter(b => b.checked).map(b => b.value);
        try {
            localStorage.setItem("nutricare_conditions", JSON.stringify(selected));
        } catch (e) {}
        return selected;
    }

    function buildProfilePayload() {
        const user = readStoredUser();
        return {
            age:          user ? user.age : null,
            gender:       user ? user.gender : null,
            height:       user ? user.height : null,
            weight:       user ? user.weight : null,
            bmi:          user ? user.bmi : null,
            bmi_category: user ? (user.bmiCategory || user.bmi_category) : null,
            conditions:   getSelectedConditions()
        };
    }

    function initConditionBoxes() {
        let saved = [];
        try { saved = JSON.parse(localStorage.getItem("nutricare_conditions") || "[]"); }
        catch (e) { saved = []; }

        document.querySelectorAll(".planCondition").forEach(box => {
            box.checked = saved.includes(box.value);
            box.addEventListener("change", () => getSelectedConditions());
        });
    }
    initConditionBoxes();

    /* ---------- Header BMI badge ---------- */
    function updateHeaderBMI() {
        const el = document.getElementById("headerBMI");
        if (!el) return;
        const p = buildProfilePayload();
        if (!p.bmi) {
            el.textContent = "BMI —";
            el.classList.remove("has-bmi");
            return;
        }
        const cat = p.bmi_category ? " · " + p.bmi_category : "";
        el.textContent = "BMI " + Number(p.bmi).toFixed(1) + cat;
        el.classList.add("has-bmi");
    }
    updateHeaderBMI();

    /* ---------- Mobile drawer nav ---------- */
    (function () {
        const btn = document.getElementById("navMenuBtn");
        const backdrop = document.getElementById("navBackdrop");
        if (!btn) return;
        const close = () => document.body.classList.remove("nav-open");
        btn.addEventListener("click", () => document.body.classList.toggle("nav-open"));
        if (backdrop) backdrop.addEventListener("click", close);
        document.querySelectorAll(".sidebar .menu button").forEach(b =>
            b.addEventListener("click", close));
        window.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
    })();

    function setPlanStatus(message) {
        const el = document.getElementById("planStatus");
        if (!el) return;
        if (!message) {
            el.style.display = "none";
            el.textContent = "";
            return;
        }
        el.style.display = "block";
        el.textContent = message;
    }

    /* ---------- Foods I can eat (report-based) ---------- */
    async function loadFoodRecommendations() {
        const panel = document.getElementById("recommendPanel");
        if (panel) panel.style.display = "none";
        setPlanStatus("📄 Reading your report against the nutrition dataset...");

        try {
            const response = await fetch(`${API_BASE}/api/recommend`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ profile: buildProfilePayload() })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.detail ||
                    (data.error && data.error.detail) ||
                    "Could not build food recommendations."
                );
            }

            renderRecommendations(data);
            setPlanStatus("");

        } catch (err) {
            setPlanStatus("⚠️ " + err.message + " — make sure Node (8000) and Python (5000) are running.");
        }
    }

    function renderRecommendations(data) {
        const panel = document.getElementById("recommendPanel");
        const summary = document.getElementById("recommendSummary");
        const groupsEl = document.getElementById("recommendGroups");
        if (!panel || !groupsEl) return;

        if (summary) summary.textContent = data.summary || "";

        const counts = data.counts || {};
        const groups = [
            { key: "eat_more", title: "✅ Eat freely",        items: data.eat_more || [], color: "#34d399" },
            { key: "moderate", title: "⚠️ Eat in moderation", items: data.moderate || [], color: "#fbbf24" },
            { key: "limit",    title: "⛔ Limit / avoid",     items: data.limit    || [], color: "#f87171" }
        ];

        groupsEl.innerHTML = groups.map(group => `
            <div style="margin-bottom:14px;">
                <div style="font-size:12px; font-weight:800; color:${group.color}; margin-bottom:6px;">
                    ${group.title} <span style="opacity:.6; font-weight:600;">(${counts[group.key] != null ? counts[group.key] : group.items.length})</span>
                </div>
                ${group.items.map(item => `
                    <div style="display:flex; justify-content:space-between; gap:10px; padding:7px 9px; border-radius:8px; background:rgba(255,255,255,.03); margin-bottom:5px; font-size:12px;">
                        <div style="min-width:0;">
                            <b>${escapeHTML(item.food)}</b>
                            <div style="opacity:.6; font-size:11px;">
                                ${escapeHTML(item.category || "")}${item.kcal != null ? " · " + Math.round(item.kcal) + " kcal" : ""}
                            </div>
                        </div>
                        <div style="text-align:right; max-width:48%; opacity:.85; font-size:11px;">
                            ${escapeHTML(item.why || "")}
                        </div>
                    </div>`).join("") || "<div style='opacity:.55; font-size:11px;'>None found.</div>"}
            </div>`).join("");

        panel.style.display = "block";
        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    /* ---------- 15-day food chart ---------- */
    async function createFoodChart() {
        const panel = document.getElementById("chartPanel");
        if (panel) panel.style.display = "none";
        setPlanStatus("📅 Building your 15-day food chart...");

        try {
            const response = await fetch(`${API_BASE}/api/plan`, {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ profile: buildProfilePayload() })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.detail ||
                    (data.error && data.error.detail) ||
                    "Could not create the food chart."
                );
            }

            renderFoodChart(data);
            setPlanStatus("");

        } catch (err) {
            setPlanStatus("⚠️ " + err.message + " — make sure Node (8000) and Python (5000) are running.");
        }
    }

    function renderFoodChart(data) {
        const panel   = document.getElementById("chartPanel");
        const summary = document.getElementById("chartSummary");
        const table   = document.getElementById("chartTable");
        if (!panel || !table) return;

        lastFoodPlan = data;
        if (summary) summary.textContent = data.summary || "";

        const rows = (data.days || []).map(day => `
            <tr style="border-bottom:1px solid rgba(255,255,255,.06);">
                <td style="padding:8px 6px; vertical-align:top; white-space:nowrap;">
                    <b>Day ${day.day}</b><br>
                    <small style="opacity:.6;">${day.weekday ? day.weekday.slice(0, 3) : ""} ${day.date}</small>
                </td>
                <td style="padding:8px 6px;">
                    ${(day.meals || []).map(m => `
                        <div style="margin-bottom:3px;">
                            <small style="opacity:.55;">${escapeHTML(m.slot)}:</small>
                            ${escapeHTML(m.food)}
                            <small style="opacity:.6;">(${m.kcal} kcal${m.portion && m.portion !== "1 serving" ? ", " + escapeHTML(m.portion) : ""})</small>
                        </div>`).join("")}
                </td>
                <td style="padding:8px 6px; vertical-align:top; white-space:nowrap; text-align:right;">
                    <b>${day.total_kcal}</b> kcal<br>
                    <small style="opacity:.6;">${day.sodium_mg} mg Na</small>
                </td>
            </tr>`).join("");

        table.innerHTML = `
            <table style="width:100%; border-collapse:collapse; font-size:11.5px;">
                <thead>
                    <tr style="text-align:left; color:#9fe7c5;">
                        <th style="padding:8px 6px;">Day</th>
                        <th style="padding:8px 6px;">Meals (target ${data.daily_kcal_target} kcal/day)</th>
                        <th style="padding:8px 6px; text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;

        panel.style.display = "block";
        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function downloadFoodChartCSV() {
        if (!lastFoodPlan) {
            alert("Create the 15-day chart first.");
            return;
        }

        const header = ["Day", "Date", "Weekday", "Slot", "Food", "Category",
                        "Kcal", "Portion", "Day total kcal", "Day sodium mg"];
        const esc = value => `"${String(value == null ? "" : value).replace(/"/g, '""')}"`;
        const lines = [header.map(esc).join(",")];

        (lastFoodPlan.days || []).forEach(day => {
            (day.meals || []).forEach(meal => {
                lines.push([
                    day.day, day.date, day.weekday, meal.slot, meal.food, meal.category,
                    meal.kcal, meal.portion, day.total_kcal, day.sodium_mg
                ].map(esc).join(","));
            });
        });

        const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
        const url  = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "nutricare-15-day-food-chart.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    function printFoodChart() {
        if (!lastFoodPlan) {
            alert("Create the 15-day chart first.");
            return;
        }

        const win = window.open("", "_blank", "width=900,height=700");
        if (!win) {
            alert("Please allow pop-ups for this site to print the chart.");
            return;
        }

        const rows = (lastFoodPlan.days || []).map(day => `
            <tr>
                <td><b>Day ${day.day}</b><br><small>${day.weekday} ${day.date}</small></td>
                <td>${(day.meals || []).map(m =>
                    `<div><b>${m.slot}:</b> ${escapeHTML(m.food)} <small>(${m.kcal} kcal${m.portion && m.portion !== "1 serving" ? ", " + escapeHTML(m.portion) : ""})</small></div>`
                ).join("")}</td>
                <td align="right"><b>${day.total_kcal}</b> kcal<br><small>${day.sodium_mg} mg Na</small></td>
            </tr>`).join("");

        win.document.write(`<!doctype html>
<html><head><title>NutriCare AI — 15-Day Food Chart</title>
<style>
    body { font-family: Arial, sans-serif; color: #111; margin: 24px; }
    h1 { font-size: 20px; color: #176b3c; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { text-align: left; border-bottom: 2px solid #176b3c; padding: 8px 6px; }
    td { border-bottom: 1px solid #ddd; padding: 8px 6px; vertical-align: top; }
    .note { font-size: 12px; color: #444; margin-top: 12px; }
</style></head>
<body>
    <h1>NutriCare AI — 15-Day Daily Food Chart</h1>
    <p>${escapeHTML(lastFoodPlan.summary || "")}</p>
    <table>
        <thead><tr><th>Day</th><th>Meals</th><th align="right">Daily total</th></tr></thead>
        <tbody>${rows}</tbody>
    </table>
    <p class="note">⚠️ Generated by NutriCare AI for educational purposes — not a substitute for medical advice.</p>
</body></html>`);
        win.document.close();
        setTimeout(() => {
            try { win.print(); } catch (e) { /* user can print manually */ }
        }, 600);
    }
   
