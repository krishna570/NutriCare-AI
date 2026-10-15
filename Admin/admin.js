/**
 * NutriCare AI - Admin Dashboard JavaScript
 * Connects to MongoDB Backend API (http://127.0.0.1:8000)
 * Fallback to LocalStorage when offline
 */

document.addEventListener("DOMContentLoaded", () => {

    // API BASE — same origin when served by the Node.js backend
    // (port 8000), direct call when opened as a file.
    const API_BASE =
        ((location.protocol.startsWith("http") && location.port === "8000")
            ? ""
            : "http://127.0.0.1:8000") + "/api";

    // DOM Elements
    const dbStatusBadge = document.getElementById("dbStatusBadge");
    const dbStatusText = document.getElementById("dbStatusText");
    const kpiTotalUsers = document.getElementById("kpiTotalUsers");
    const kpiAvgBmi = document.getElementById("kpiAvgBmi");
    const kpiNormalRate = document.getElementById("kpiNormalRate");
    const kpiNormalCount = document.getElementById("kpiNormalCount");
    const kpiStorageMode = document.getElementById("kpiStorageMode");
    const kpiStorageHost = document.getElementById("kpiStorageHost");
    const userCountLabel = document.getElementById("userCountLabel");
    const usersTableBody = document.getElementById("usersTableBody");
    const emptyState = document.getElementById("emptyState");
    const searchInput = document.getElementById("searchInput");
    const bmiFilter = document.getElementById("bmiFilter");
    const genderFilter = document.getElementById("genderFilter");
    const refreshBtn = document.getElementById("refreshBtn");
    const exportCsvBtn = document.getElementById("exportCsvBtn");
    const exportJsonBtn = document.getElementById("exportJsonBtn");

    // Admin Authentication Elements
    const adminLoginOverlay = document.getElementById("adminLoginOverlay");
    const adminLoginForm = document.getElementById("adminLoginForm");
    const adminEmailInput = document.getElementById("adminEmail");
    const adminPasswordInput = document.getElementById("adminPassword");
    const adminLoginError = document.getElementById("adminLoginError");
    const adminLoginSubmitBtn = document.getElementById("adminLoginSubmitBtn");
    const adminMainContent = document.getElementById("adminMainContent");
    const adminUserMenu = document.getElementById("adminUserMenu");
    const adminUserEmail = document.getElementById("adminUserEmail");
    const adminLogoutBtn = document.getElementById("adminLogoutBtn");

    // Modal elements
    const userDetailModal = document.getElementById("userDetailModal");
    const closeDetailModal = document.getElementById("closeDetailModal");
    const modalDetailContent = document.getElementById("modalDetailContent");

    // Database Architecture Modal
    const dbArchitectureModal = document.getElementById("dbArchitectureModal");
    const showDbArchitectureBtn = document.getElementById("showDbArchitectureBtn");
    const closeDbModal = document.getElementById("closeDbModal");
    const dbArchitectureContent = document.getElementById("dbArchitectureContent");

    let allUsers = [];
    let isMongoConnected = false;

    // =========================================================
    // 0. ADMIN AUTHENTICATION GATEWAY
    // =========================================================
    function checkAdminAuth() {
        const token = sessionStorage.getItem("nutricare_admin_token");
        const email = sessionStorage.getItem("nutricare_admin_email") || "admin@nutricare.ai";

        if (token) {
            if (adminLoginOverlay) {
                adminLoginOverlay.classList.remove("active");
                adminLoginOverlay.style.display = "none";
            }
            if (adminMainContent) adminMainContent.style.display = "block";
            if (adminUserMenu) {
                adminUserMenu.style.display = "flex";
                if (adminUserEmail) adminUserEmail.textContent = email;
            }
            checkHealthAndLoadData();
        } else {
            if (adminLoginOverlay) {
                adminLoginOverlay.classList.add("active");
                adminLoginOverlay.style.display = "flex";
            }
            if (adminMainContent) adminMainContent.style.display = "none";
            if (adminUserMenu) adminUserMenu.style.display = "none";
        }
    }

    if (adminLoginForm) {
        adminLoginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = adminEmailInput ? adminEmailInput.value.trim().toLowerCase() : "";
            const password = adminPasswordInput ? adminPasswordInput.value : "";

            if (adminLoginError) adminLoginError.style.display = "none";
            if (adminLoginSubmitBtn) {
                adminLoginSubmitBtn.disabled = true;
                adminLoginSubmitBtn.textContent = "Verifying...";
            }

            try {
                let loggedIn = false;

                // 1. Try backend admin login API
                try {
                    const res = await fetch(`${API_BASE}/admin/login`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email, password })
                    });

                    if (res.ok) {
                        const data = await res.json();
                        sessionStorage.setItem("nutricare_admin_token", data.token || "admin_session");
                        sessionStorage.setItem("nutricare_admin_email", email);
                        loggedIn = true;
                    } else {
                        const err = await res.json().catch(() => ({}));
                        throw new Error(err.detail || "Invalid admin credentials");
                    }
                } catch (apiErr) {
                    // Fallback to default admin if backend offline
                    if (email === "admin@nutricare.ai" && password === "admin123") {
                        sessionStorage.setItem("nutricare_admin_token", "admin_local_token");
                        sessionStorage.setItem("nutricare_admin_email", email);
                        loggedIn = true;
                    } else {
                        throw apiErr;
                    }
                }

                if (loggedIn) {
                    checkAdminAuth();
                }
            } catch (err) {
                if (adminLoginError) {
                    adminLoginError.textContent = err.message || "Invalid admin credentials. Please try again.";
                    adminLoginError.style.display = "block";
                }
            } finally {
                if (adminLoginSubmitBtn) {
                    adminLoginSubmitBtn.disabled = false;
                    adminLoginSubmitBtn.textContent = "Unlock Dashboard ➔";
                }
            }
        });
    }

    if (adminLogoutBtn) {
        adminLogoutBtn.addEventListener("click", () => {
            sessionStorage.removeItem("nutricare_admin_token");
            sessionStorage.removeItem("nutricare_admin_email");
            checkAdminAuth();
        });
    }

    // =========================================================            // 1. CHECK BACKEND CONNECTION & FETCH DATA
    // =========================================================
    async function checkHealthAndLoadData() {
        dbStatusBadge.className = "db-status-pill checking";
        dbStatusText.textContent = "Checking backend...";

        try {
            const healthRes = await fetch(`${API_BASE}/health`, { method: "GET" });

            if (healthRes.ok) {
                const healthData = await healthRes.json();
                isMongoConnected = healthData.mongodb_connected;

                if (isMongoConnected) {
                    dbStatusBadge.className = "db-status-pill online";
                    dbStatusText.textContent = "🟢 MongoDB Connected";
                    kpiStorageMode.textContent = "MongoDB Active";
                    kpiStorageHost.textContent = healthData.database || "nutricare_db.users";
                } else {
                    // Node.js backend — users live in a local JSON file
                    dbStatusBadge.className = "db-status-pill local";
                    dbStatusText.textContent = "🟢 Backend Connected (Local JSON)";
                    kpiStorageMode.textContent = "Local JSON Active";
                    kpiStorageHost.textContent =
                        healthData.database_file || healthData.database || "backend/data/users.json";
                }

                // Load users from Backend API
                await fetchUsersFromBackend();
                return;
            }
        } catch (err) {
            console.warn("Backend API is offline. Falling back to Local Storage cache:", err.message);
        }

        // Offline Fallback to LocalStorage
        isMongoConnected = false;
        dbStatusBadge.className = "db-status-pill local";
        dbStatusText.textContent = "🟡 Local Storage Cache";
        kpiStorageMode.textContent = "Local Storage";
        kpiStorageHost.textContent = "Start backend to sync with MongoDB";

        loadUsersFromLocalStorage();
    }

    // Fetch from FastAPI / Express MongoDB API
    async function fetchUsersFromBackend() {
        try {
            const res = await fetch(`${API_BASE}/admin/users`);
            if (!res.ok) throw new Error("Failed to fetch users from backend");

            const data = await res.json();
            allUsers = data.users || [];
            console.log(`Loaded ${allUsers.length} users from MongoDB`);

            // Also keep localStorage updated
            if (allUsers.length > 0) {
                localStorage.setItem("nutricare_users", JSON.stringify(allUsers));
            }

            renderDashboard();
        } catch (err) {
            console.error("Error loading from backend, falling back to local:", err);
            loadUsersFromLocalStorage();
        }
    }

    // Load from LocalStorage
    function loadUsersFromLocalStorage() {
        try {
            const stored = localStorage.getItem("nutricare_users");
            allUsers = stored ? JSON.parse(stored) : [];
        } catch (e) {
            allUsers = [];
        }
        renderDashboard();
    }

    // =========================================================
    // 2. RENDER DASHBOARD (KPIs & TABLE)
    // =========================================================
    function renderDashboard() {
        updateKPICards();
        applyFiltersAndRenderTable();
    }

    function computeBmiCategory(bmi) {
        if (!bmi) return "Not Computed";
        if (bmi < 18.5) return "Underweight";
        if (bmi < 25.0) return "Normal weight";
        if (bmi < 30.0) return "Overweight";
        return "Obese";
    }

    function getBmiBadgeClass(cat) {
        const c = (cat || "").toLowerCase();
        if (c.includes("normal")) return "normal";
        if (c.includes("underweight")) return "underweight";
        if (c.includes("overweight")) return "overweight";
        return "obese";
    }

    // Update KPI Metric Cards
    function updateKPICards() {
        kpiTotalUsers.textContent = allUsers.length;

        if (allUsers.length === 0) {
            kpiAvgBmi.textContent = "--";
            kpiNormalRate.textContent = "0%";
            kpiNormalCount.textContent = "0 users in healthy range";
            return;
        }

        const bmis = allUsers.map(u => parseFloat(u.bmi)).filter(b => !isNaN(b) && b > 0);

        if (bmis.length > 0) {
            const avg = (bmis.reduce((a, b) => a + b, 0) / bmis.length).toFixed(1);
            kpiAvgBmi.textContent = avg;

            const normalCount = bmis.filter(b => b >= 18.5 && b < 25.0).length;
            const normalPercentage = Math.round((normalCount / bmis.length) * 100);
            kpiNormalRate.textContent = `${normalPercentage}%`;
            kpiNormalCount.textContent = `${normalCount} of ${bmis.length} in normal range`;
        } else {
            kpiAvgBmi.textContent = "--";
            kpiNormalRate.textContent = "0%";
        }
    }

    // Filter & Render Table Rows
    function applyFiltersAndRenderTable() {
        const searchTerm = (searchInput.value || "").toLowerCase().trim();
        const selectedBmi = bmiFilter.value;
        const selectedGender = genderFilter.value;

        const filtered = allUsers.filter(user => {
            const matchesSearch =
                !searchTerm ||
                (user.fullName && user.fullName.toLowerCase().includes(searchTerm)) ||
                (user.email && user.email.toLowerCase().includes(searchTerm));

            const category = user.bmiCategory || computeBmiCategory(user.bmi);
            const matchesBmi =
                selectedBmi === "all" ||
                category.toLowerCase() === selectedBmi.toLowerCase();

            const matchesGender =
                selectedGender === "all" ||
                (user.gender && user.gender.toLowerCase() === selectedGender.toLowerCase());

            return matchesSearch && matchesBmi && matchesGender;
        });

        userCountLabel.textContent = filtered.length;

        if (filtered.length === 0) {
            usersTableBody.innerHTML = "";
            emptyState.style.display = "block";
            return;
        }

        emptyState.style.display = "none";
        usersTableBody.innerHTML = filtered.map((user) => {
            const initial = user.fullName ? user.fullName.charAt(0).toUpperCase() : "U";
            const bmi = user.bmi ? parseFloat(user.bmi).toFixed(1) : "--";
            const category = user.bmiCategory || computeBmiCategory(user.bmi);
            const badgeClass = getBmiBadgeClass(category);
            const regDate = user.registeredAt
                ? (user.registeredAt.includes("T") ? user.registeredAt.split("T")[0] : user.registeredAt.split(" ")[0])
                : "Recent";

            const userId = user.id || user._id || user.email;

            return `
                <tr data-id="${userId}">
                    <td>
                        <div class="user-cell">
                            <div class="user-avatar">${initial}</div>
                            <span class="user-name">${escapeHtml(user.fullName || 'Anonymous')}</span>
                        </div>
                    </td>
                    <td><span style="color: #475569; font-family: monospace;">${escapeHtml(user.email)}</span></td>
                    <td>
                        <span style="text-transform: capitalize;">
                            ${user.age ? `${user.age} yrs` : '--'} · ${user.gender || '--'}
                        </span>
                    </td>
                    <td>${user.height ? `${user.height} cm` : '--'}</td>
                    <td>${user.weight ? `${user.weight} kg` : '--'}</td>
                    <td>
                        <span class="bmi-badge ${badgeClass}">
                            <strong>${bmi}</strong> ${category}
                        </span>
                    </td>
                    <td><small style="color: #88978e;">${regDate}</small></td>
                    <td style="text-align: right;">
                        <div class="row-actions">
                            <button class="btn-icon view" title="View Full Health Profile" onclick="viewUserDetails('${escapeHtml(userId)}')">
                                👁
                            </button>
                            <button class="btn-icon delete" title="Delete User Record" onclick="deleteUserRecord('${escapeHtml(userId)}')">
                                🗑
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // =========================================================
    // 3. USER ACTIONS (VIEW DETAILS & DELETE)
    // =========================================================
    window.viewUserDetails = function(userId) {
        const user = allUsers.find(u => (u.id === userId || u._id === userId || u.email === userId));
        if (!user) return;

        const initial = user.fullName ? user.fullName.charAt(0).toUpperCase() : "U";
        const bmi = user.bmi ? parseFloat(user.bmi).toFixed(1) : "Not computed";
        const category = user.bmiCategory || computeBmiCategory(user.bmi);

        let advice = "NutriCare AI recommends maintaining balanced whole foods, steady hydration, and routine physical activity.";
        if (category.toLowerCase().includes("underweight")) {
            advice = "NutriCare AI Recommendation: Focus on nutrient-dense, healthy-calorie foods (avocados, nuts, complex carbohydrates) and resistance training.";
        } else if (category.toLowerCase().includes("overweight") || category.toLowerCase().includes("obese")) {
            advice = "NutriCare AI Recommendation: Prioritize higher dietary fiber, lean protein, portion balance, and consistent daily aerobic movement.";
        }

        modalDetailContent.innerHTML = `
            <div class="detail-profile">
                <div class="detail-avatar">${initial}</div>
                <div class="detail-meta">
                    <h4>${escapeHtml(user.fullName || 'Anonymous')}</h4>
                    <p>${escapeHtml(user.email)}</p>
                </div>
            </div>

            <div class="detail-grid">
                <div class="detail-item">
                    <span>Age & Gender</span>
                    <strong>${user.age || '--'} yrs · ${user.gender || '--'}</strong>
                </div>
                <div class="detail-item">
                    <span>Height & Weight</span>
                    <strong>${user.height ? `${user.height} cm` : '--'} · ${user.weight ? `${user.weight} kg` : '--'}</strong>
                </div>
                <div class="detail-item">
                    <span>Body Mass Index</span>
                    <strong style="color: var(--green-dark);">${bmi} BMI</strong>
                </div>
                <div class="detail-item">
                    <span>Classification</span>
                    <strong>${category}</strong>
                </div>
            </div>

            <div class="recommendation-box">
                <strong>🤖 Baymax AI Health Insight:</strong>
                ${advice}
            </div>

            <div style="margin-top: 16px; font-size: 11px; color: #94a39b; text-align: center;">
                Record ID: <code>${user.id || user._id || 'local'}</code> · Registered: ${user.registeredAt || 'Recent'}
            </div>
        `;

        userDetailModal.classList.add("active");
    };

    window.deleteUserRecord = async function(userId) {
        const user = allUsers.find(u => (u.id === userId || u._id === userId || u.email === userId));
        const name = user ? user.fullName : "this user";

        if (!confirm(`Are you sure you want to delete ${name} from the database? This action cannot be undone.`)) {
            return;
        }

        // Try delete via backend if online
        try {
            const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}`, {
                method: "DELETE"
            });
            if (res.ok) {
                console.log(`Deleted user ${userId} from MongoDB`);
            }
        } catch (e) {
            console.warn("Backend unavailable during delete, updating local storage.");
        }

        // Remove from local memory
        allUsers = allUsers.filter(u => (u.id !== userId && u._id !== userId && u.email !== userId));
        localStorage.setItem("nutricare_users", JSON.stringify(allUsers));

        renderDashboard();
    };

    // Close detail modal
    if (closeDetailModal) {
        closeDetailModal.addEventListener("click", () => userDetailModal.classList.remove("active"));
    }
    if (userDetailModal) {
        userDetailModal.addEventListener("click", (e) => {
            if (e.target === userDetailModal) userDetailModal.classList.remove("active");
        });
    }

    // =========================================================
    // 4. SEARCH, FILTER & EXPORT
    // =========================================================
    if (searchInput) searchInput.addEventListener("input", applyFiltersAndRenderTable);
    if (bmiFilter) bmiFilter.addEventListener("change", applyFiltersAndRenderTable);
    if (genderFilter) genderFilter.addEventListener("change", applyFiltersAndRenderTable);

    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            checkHealthAndLoadData();
        });
    }

    if (dbStatusBadge) {
        dbStatusBadge.addEventListener("click", () => {
            checkHealthAndLoadData();
        });
    }

    // Export CSV
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener("click", () => {
            if (allUsers.length === 0) {
                alert("No users available to export.");
                return;
            }

            const headers = ["Full Name", "Email", "Age", "Gender", "Height (cm)", "Weight (kg)", "BMI", "Category", "Registered At"];
            const rows = allUsers.map(u => [
                `"${(u.fullName || '').replace(/"/g, '""')}"`,
                `"${(u.email || '').replace(/"/g, '""')}"`,
                u.age || '',
                u.gender || '',
                u.height || '',
                u.weight || '',
                u.bmi || '',
                `"${(u.bmiCategory || computeBmiCategory(u.bmi)).replace(/"/g, '""')}"`,
                `"${(u.registeredAt || '').replace(/"/g, '""')}"`
            ]);

            const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `nutricare_users_${new Date().toISOString().slice(0, 10)}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // Export JSON
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener("click", () => {
            if (allUsers.length === 0) {
                alert("No users available to export.");
                return;
            }
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(allUsers, null, 2));
            const downloadAnchor = document.createElement("a");
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `nutricare_users_${new Date().toISOString().slice(0, 10)}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            document.body.removeChild(downloadAnchor);
        });
    }

    // =========================================================
    // 5. MONGODB ARCHITECTURE MODAL INSPECTOR
    // =========================================================
    async function openDbArchitectureModal() {
        if (!dbArchitectureModal || !dbArchitectureContent) return;
        dbArchitectureModal.classList.add("active");
        dbArchitectureContent.innerHTML = `
            <div class="table-loader">
                <div class="spinner"></div>
                <span>Fetching database architecture metadata...</span>
            </div>
        `;

        try {
            const res = await fetch(`${API_BASE}/admin/db-info`);
            if (res.ok) {
                const info = await res.json();
                renderDbInfo(info);
                return;
            }
        } catch (e) {
            console.warn("Could not fetch db-info from API, using cached schema:", e);
        }

        // Schema fallback
        renderDbInfo({
            databaseName: "nutricare_db",
            connectionUri: "mongodb://localhost:27017",
            collections: [
                {
                    name: "users",
                    description: "Stores user profiles, login credentials, and live BMI analytics",
                    documentCount: allUsers.length,
                    fields: [
                        { field: "_id", type: "ObjectId", description: "Primary Key" },
                        { field: "fullName", type: "String", description: "User full name" },
                        { field: "email", type: "String (Unique)", description: "Login email address" },
                        { field: "password", type: "String", description: "User authentication password" },
                        { field: "age", type: "Integer", description: "Age in years" },
                        { field: "gender", type: "String", description: "Gender identity" },
                        { field: "height", type: "Float", description: "Height in centimeters" },
                        { field: "weight", type: "Float", description: "Weight in kilograms" },
                        { field: "bmi", type: "Float", description: "Body Mass Index" },
                        { field: "bmiCategory", type: "String", description: "Classification" },
                        { field: "registeredAt", type: "Date / ISO String", description: "Timestamp of registration" }
                    ]
                },
                {
                    name: "admins",
                    description: "Stores authorized administrator credentials",
                    documentCount: 1,
                    fields: [
                        { field: "_id", type: "ObjectId", description: "Primary Key" },
                        { field: "email", type: "String (Unique)", description: "admin@nutricare.ai" },
                        { field: "password", type: "String", description: "admin123" },
                        { field: "role", type: "String", description: "superadmin" }
                    ]
                }
            ]
        });
    }

    function renderDbInfo(info) {
        if (!dbArchitectureContent) return;
        dbArchitectureContent.innerHTML = `
            <div style="background:#effaf4; padding:14px; border-radius:12px; border:1px solid #bcead1; margin-bottom:18px;">
                <div style="font-size:13px; color:#176b3c; font-weight:700;">Active Database:</div>
                <div style="font-family:monospace; font-size:12px; color:#224734; margin-top:4px;">
                    ${String(info.connectionUri).startsWith("file:")
                        ? escapeHtml(info.connectionUri)
                        : `${escapeHtml(info.connectionUri)}/${escapeHtml(info.databaseName)}`}
                </div>
            </div>
            ${info.collections.map(col => `
                <div class="collection-card">
                    <div class="collection-header">
                        <div>
                            <span class="collection-title">📁 Collection: <code>${escapeHtml(col.name)}</code></span>
                            <p style="font-size:12px; color:#64756c; margin-top:2px;">${escapeHtml(col.description)}</p>
                        </div>
                        <span class="doc-count-pill">${col.documentCount} records</span>
                    </div>
                    <table class="fields-table">
                        <thead>
                            <tr>
                                <th>Field Name</th>
                                <th>Data Type</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${col.fields.map(f => `
                                <tr>
                                    <td><code>${escapeHtml(f.field)}</code></td>
                                    <td style="color:#047857; font-weight:600;">${escapeHtml(f.type)}</td>
                                    <td style="color:#55695f;">${escapeHtml(f.description)}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `).join("")}
        `;
    }

    if (showDbArchitectureBtn) {
        showDbArchitectureBtn.addEventListener("click", openDbArchitectureModal);
    }
    if (closeDbModal && dbArchitectureModal) {
        closeDbModal.addEventListener("click", () => dbArchitectureModal.classList.remove("active"));
    }
    if (dbArchitectureModal) {
        dbArchitectureModal.addEventListener("click", (e) => {
            if (e.target === dbArchitectureModal) dbArchitectureModal.classList.remove("active");
        });
    }

    // Escape HTML helper
    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initialize Admin Gateway Check
    checkAdminAuth();
});
