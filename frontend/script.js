/* ═══════════════════════════════════════════════════════════════
   StockPad — Merged Script (translations + api + all page logic)
   Dashboard removed. All pages in SPA.
   ═══════════════════════════════════════════════════════════════ */

// ══════════════════════════════════════════════════════════════
// TRANSLATIONS
// ══════════════════════════════════════════════════════════════
const i18n = {
    _lang: localStorage.getItem('lang') || 'en',
    translations: {
        'sidebar.logo': { en: 'StockPad', ar: 'ستوك باد' },
        'sidebar.tagline': { en: 'smart inventory management', ar: 'إدارة المخزون الذكي' },
        'sidebar.inventory': { en: 'Inventory', ar: 'المخزون' },
        'sidebar.chatbot': { en: 'Chat Bot', ar: 'المساعد الذكي' },
        'sidebar.requests': { en: 'Requests', ar: 'الطلبات' },
        'sidebar.darkMode': { en: 'Dark Mode', ar: 'الوضع الداكن' },
        'sidebar.lightMode': { en: 'Light Mode', ar: 'الوضع الفاتح' },
        'sidebar.account': { en: 'Account / Profile', ar: 'الحساب / الملف الشخصي' },
        'sidebar.logout': { en: 'Logout', ar: 'تسجيل الخروج' },
        'sidebar.language': { en: '🌐 عربي', ar: '🌐 English' },
        'role.engineer': { en: 'Site Engineer', ar: 'مهندس موقع' },
        'role.warehouse': { en: 'Warehouse Manager', ar: 'مدير مخزن' },
        'role.admin': { en: 'Admin', ar: 'مدير النظام' },
        'role.manager': { en: 'Project Manager', ar: 'مدير مشروع' },
        'login.title': { en: 'Stock Pad', ar: 'ستوك باد' },
        'login.email': { en: 'Email', ar: 'البريد الإلكتروني' },
        'login.emailPlaceholder': { en: 'Enter your email', ar: 'أدخل بريدك الإلكتروني' },
        'login.password': { en: 'Password', ar: 'كلمة المرور' },
        'login.passwordPlaceholder': { en: 'Enter your password', ar: 'أدخل كلمة المرور' },
        'login.remember': { en: ' Remember Me', ar: ' تذكرني' },
        'login.forgot': { en: 'Forgot Password?', ar: 'نسيت كلمة المرور؟' },
        'login.btn': { en: 'Login', ar: 'تسجيل الدخول' },
        'login.noAccount': { en: "Don't have an account? ", ar: 'ليس لديك حساب؟ ' },
        'login.signup': { en: 'SignUp', ar: 'إنشاء حساب' },
        'forgot.title': { en: 'Reset Password', ar: 'إعادة تعيين كلمة المرور' },
        'forgot.subtitle': { en: 'Enter your email to receive a reset link', ar: 'أدخل بريدك الإلكتروني لاستلام رابط إعادة التعيين' },
        'forgot.emailPlaceholder': { en: 'Enter your email', ar: 'أدخل بريدك الإلكتروني' },
        'forgot.btn': { en: 'Send Reset Link', ar: 'إرسال رابط إعادة التعيين' },
        'forgot.back': { en: 'Back to Login', ar: 'العودة لتسجيل الدخول' },
        'signup.title': { en: 'Stock Pad - Sign Up', ar: 'ستوك باد - إنشاء حساب' },
        'signup.username': { en: 'Username', ar: 'اسم المستخدم' },
        'signup.usernamePlaceholder': { en: 'Pick a username', ar: 'اختر اسم مستخدم' },
        'signup.role': { en: 'Role', ar: 'الدور' },
        'signup.engineer': { en: 'Site Engineer', ar: 'مهندس موقع' },
        'signup.warehouse': { en: 'Warehouse Manager', ar: 'مدير مخزن' },
        'signup.admin': { en: 'Admin', ar: 'مدير النظام' },
        'signup.confirmPassword': { en: 'Confirm Password', ar: 'تأكيد كلمة المرور' },
        'signup.confirmPlaceholder': { en: 'Confirm your password', ar: 'أعد إدخال كلمة المرور' },
        'signup.btn': { en: 'Sign Up', ar: 'إنشاء حساب' },
        'signup.hasAccount': { en: 'Already have an account? ', ar: 'لديك حساب بالفعل؟ ' },
        'signup.login': { en: 'Login', ar: 'تسجيل الدخول' },
        'inv.title': { en: 'Raw Materials Inventory', ar: 'مخزون المواد الخام' },
        'inv.subtitle': { en: 'Browse and request available materials', ar: 'تصفح المواد المتاحة وقدم طلبك' },
        'inv.all': { en: 'All Items', ar: 'الكل' },
        'inv.building': { en: 'Building Materials', ar: 'مواد بناء' },
        'inv.steel': { en: 'Steel & Metal', ar: 'حديد ومعادن' },
        'inv.paint': { en: 'Paints', ar: 'دهانات' },
        'inv.finishing': { en: 'Finishing', ar: 'تشطيبات' },
        'inv.plumbing': { en: 'Plumbing', ar: 'سباكة' },
        'inv.electrical': { en: 'Electrical', ar: 'كهرباء' },
        'req.title': { en: 'Material Requests', ar: 'طلبات المواد' },
        'req.newRequest': { en: 'New Request', ar: 'طلب جديد' },
        'req.selectMaterial': { en: 'Select Material', ar: 'اختر المادة' },
        'req.notes': { en: 'Justification / Notes (Optional)', ar: 'السبب / ملاحظات (اختياري)' },
        'req.discard': { en: 'Discard', ar: 'تجاهل' },
        'req.submit': { en: 'Submit', ar: 'إرسال' },
        'req.approve': { en: 'Approve', ar: 'موافقة' },
        'req.reject': { en: 'Reject', ar: 'رفض' },
        'req.pending': { en: 'Pending', ar: 'قيد الانتظار' },
        'req.approved': { en: 'Approved', ar: 'تمت الموافقة' },
        'req.rejected': { en: 'Rejected', ar: 'مرفوض' },
        'req.requestedQty': { en: 'Requested Quantity', ar: 'الكمية المطلوبة' },
        'req.requestedBy': { en: 'Requested By', ar: 'مقدم الطلب' },
        'req.requestDate': { en: 'Request Date', ar: 'تاريخ الطلب' },
        'chat.title': { en: 'Inventory Assistant Chat Bot', ar: 'المساعد الذكي للمخزون' },
        'chat.welcome': { en: "Hello! I'm your **live inventory assistant**. I have real-time access to the StockPad database. Ask me anything about stock levels, materials, quantities, or status!", ar: "مرحباً! أنا **مساعدك الشخصي لجرد المخزون**. لدي وصول مباشر لقاعدة بيانات ستوك باد. اسألني عن أي شيء يتعلق بمستويات المخزون، المواد، الكميات أو الحالة!" },
        'chat.placeholder': { en: 'Ask about materials, stock levels, or inventory...', ar: 'اسأل عن المواد، مستويات المخزون...' },
        'chat.outOfStock': { en: "What's out of stock?", ar: 'ما هو غير المتوفر؟' },
        'chat.lowStock': { en: 'Low stock items', ar: 'المواد منخفضة المخزون' },
        'chat.totalValue': { en: 'Total inventory value', ar: 'إجمالي قيمة المخزون' },
        'chat.history': { en: 'History', ar: 'السجل' },
        'chat.historyTitle': { en: 'Chat History', ar: 'سجل المحادثات' },
        'chat.noHistory': { en: 'No previous chats found.', ar: 'لا يوجد سجل محادثات سابق.' },
        'chat.newChat': { en: 'New Chat', ar: 'محادثة جديدة' },
        'chat.messages': { en: 'messages', ar: 'رسائل' },
        'chat.confirmDelete': { en: 'Are you sure you want to delete this conversation?', ar: 'هل أنت متأكد من حذف هذه المحادثة؟' },
        'profile.title': { en: 'Account Profile', ar: 'الملف الشخصي' },
        'profile.personal': { en: 'Personal Information', ar: 'المعلومات الشخصية' },
        'profile.fullName': { en: 'Full Name', ar: 'الاسم الكامل' },
        'profile.email': { en: 'Email Address', ar: 'البريد الإلكتروني' },
        'profile.editBtn': { en: 'Edit Information', ar: 'تعديل المعلومات' },
        'profile.saveBtn': { en: 'Save Changes', ar: 'حفظ التغييرات' },
        'profile.settings': { en: 'Account Settings', ar: 'إعدادات الحساب' },
        'profile.emailNotif': { en: 'Email Notifications', ar: 'إشعارات البريد' },
        'profile.emailNotifSub': { en: 'Receive updates on stock levels', ar: 'تلقي تحديثات عن مستويات المخزون' },
        'profile.twoFactor': { en: 'Two-Factor Authentication', ar: 'المصادقة الثنائية' },
        'profile.twoFactorSub': { en: 'Secure your account', ar: 'تأمين حسابك' },
        'profile.changePass': { en: 'Change Password', ar: 'تغيير كلمة المرور' },
        'profile.activity': { en: 'Recent Activity', ar: 'النشاط الأخير' },
        'profile.noActivity': { en: 'No recent activity', ar: 'لا يوجد نشاط أخير' },
        'profile.noActivitySub': { en: 'Start by making a material request', ar: 'ابدأ بتقديم طلبات المواد' },
        'profile.wmConnection': { en: 'WM Connection Status', ar: 'حالة الاتصال بالمخزن' },
        'profile.wmConnectionSub': { en: 'Live link to your Warehouse Manager', ar: 'اتصال مباشر بمدير المخزن' },
        'profile.wmConnected': { en: 'Connected', ar: 'متصل' },
        'profile.wmNotConnected': { en: 'Not Connected', ar: 'غير متصل' },
        'profile.wmChecking': { en: 'Checking...', ar: 'جاري التحقق...' },
    },
    t(key) { const e = this.translations[key]; if (!e) return key; return e[this._lang] || e.en || key; },
    getLang() { return this._lang; },
    setLang(lang) { this._lang = lang; localStorage.setItem('lang', lang); this.applyToPage(); },
    toggle() { this.setLang(this._lang === 'en' ? 'ar' : 'en'); },
    applyToPage() {
        const lang = this._lang;
        document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
        document.documentElement.lang = lang;
        document.querySelectorAll('[data-i18n]').forEach(el => { el.innerHTML = this.t(el.getAttribute('data-i18n')); });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = this.t(el.getAttribute('data-i18n-placeholder')); });
        const themeSpan = document.querySelector('#themeToggle span');
        if (themeSpan) { const isDark = document.documentElement.classList.contains('dark-mode'); themeSpan.textContent = this.t(isDark ? 'sidebar.lightMode' : 'sidebar.darkMode'); }
        document.querySelectorAll('[data-i18n="sidebar.language"]').forEach(el => { el.textContent = this.t('sidebar.language'); });
        document.querySelectorAll('.logo').forEach(el => { el.textContent = this.t('sidebar.logo'); });
    },
    init() { this.applyToPage(); }
};

// ══════════════════════════════════════════════════════════════
// API
// ══════════════════════════════════════════════════════════════
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:')
    ? 'http://127.0.0.1:8000'
    : window.location.origin;
const API_URL = `${API_BASE}/api`;

// ── WM (Warehouse Manager) Site Integration ───────────────────
// Base URL for the remote WM website API. Change this to match
// the deployed WM server address (same value as WM_WEBSITE_BASE_URL in settings.py).
const WM_BASE_URL = 'https://stockpad-backend-production.up.railway.app';
const api = {
    getToken: () => localStorage.getItem('access_token'),
    setToken: (access, refresh) => { localStorage.setItem('access_token', access); if (refresh) localStorage.setItem('refresh_token', refresh); },
    clearToken: () => { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); localStorage.removeItem('user_role'); localStorage.removeItem('username'); },
    request: async (endpoint, method = 'GET', data = null, useAuth = true) => {
        const headers = {};
        let body = data;
        if (!(data instanceof FormData)) { headers['Content-Type'] = 'application/json'; if (data) body = JSON.stringify(data); }
        if (useAuth) { const token = api.getToken(); if (token) headers['Authorization'] = `Bearer ${token}`; }
        const config = { method, headers };
        if (body) config.body = body;
        try {
            const response = await fetch(`${API_URL}${endpoint}`, config);
            if (response.status === 401 && useAuth) { api.clearToken(); navigateTo('login'); return null; }
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                let errorMessage = errorData.detail || errorData.error;
                if (!errorMessage && typeof errorData === 'object') { const firstKey = Object.keys(errorData)[0]; if (firstKey) { const val = errorData[firstKey]; errorMessage = Array.isArray(val) ? val[0] : val; if (firstKey !== 'non_field_errors') errorMessage = `${firstKey.charAt(0).toUpperCase() + firstKey.slice(1)}: ${errorMessage}`; } }
                throw new Error(errorMessage || 'API Error');
            }
            if (response.status === 204 || response.status === 205) return true;
            return await response.json();
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            if (error.name === 'TypeError' || error.message.includes('fetch')) { const msg = "Could not connect to the backend server. Please make sure the Django server is running."; api.showModal('Connection Failed', msg, true); throw new Error(msg); }
            throw error;
        }
    },
    login: async (email, password, rememberMe = false) => {
        const data = await api.request('/auth/login/', 'POST', { username: email, password }, false);
        if (data) {
            api.setToken(data.access, data.refresh);
            if (rememberMe) localStorage.setItem('remember_me', 'true'); else localStorage.removeItem('remember_me');
            const user = await api.getMe();
            localStorage.setItem('user_role', user.role);
            localStorage.setItem('username', user.username);
            localStorage.setItem('user_id', user.id);
            // Persist email for WM integration calls (requester_email, catalog fetch, status check)
            localStorage.setItem('user_email', user.email || email);
            return user;
        }
    },
    register: async (username, email, password, role) => api.request('/auth/register/', 'POST', { username, email, password, role }, false),
    googleLogin: async (credential) => {
        const data = await api.request('/auth/google/', 'POST', { credential }, false);
        if (data) { 
            api.setToken(data.access, data.refresh); 
            localStorage.setItem('user_role', data.user.role || 'engineer'); 
            localStorage.setItem('username', data.user.username); 
            localStorage.setItem('user_id', data.user.id);
            // Persist email for WM integration calls
            localStorage.setItem('user_email', data.user.email || '');
            return data.user; 
        }
    },
    logout: async () => { const refresh = localStorage.getItem('refresh_token'); if (refresh) await api.request('/auth/logout/', 'POST', { refresh }).catch(() => {}); api.clearToken(); localStorage.removeItem('remember_me'); localStorage.removeItem('user_email'); navigateTo('login'); },
    getMe: async () => { const user = await api.request('/auth/me/'); if (user && user.avatar && !user.avatar.startsWith('http')) user.avatar = `${API_BASE}${user.avatar}`; return user; },
    updateProfile: async (payload) => api.request('/auth/me/', 'PATCH', payload),
    uploadAvatar: async (file) => { const fd = new FormData(); fd.append('avatar', file); return api.request('/auth/me/', 'PATCH', fd); },
    getMaterials: async (params = {}) => { let qs = ''; const keys = Object.keys(params).filter(k => params[k] !== 'all' && params[k] !== ''); if (keys.length > 0) qs = '?' + keys.map(k => `${k}=${encodeURIComponent(params[k])}`).join('&'); return api.request(`/materials/${qs}`); },

    /**
     * Fetch the materials catalogue from the WM site asynchronously.
     * Passes the engineer's email so the WM server returns only the
     * materials belonging to the Warehouse Manager who whitelisted them.
     * Falls back to local PE materials on network/auth errors.
     *
     * @param {string} engineerEmail — logged-in engineer's email address
     * @returns {Promise<Array>} array of material objects
     */
    fetchWMCatalog: async (engineerEmail) => {
        try {
            const response = await fetch(
                `${WM_BASE_URL}/api/inventory/materials/catalog/`,
                {
                    method: 'GET',
                    headers: {
                        'X-Engineer-Email': engineerEmail,
                        'X-Site-B-API-Key': 'stockpad-site-b-key', // must match WM server config
                    },
                    signal: AbortSignal.timeout(10000), // 10-second hard timeout
                }
            );
            if (!response.ok) {
                console.warn(`[WM Catalog] HTTP ${response.status} — falling back to local materials.`);
                return null;
            }
            const data = await response.json();
            return Array.isArray(data) ? data : (data.results || data.materials || []);
        } catch (err) {
            if (err.name === 'TimeoutError') {
                console.warn('[WM Catalog] Request timed out — falling back to local materials.');
            } else {
                console.warn('[WM Catalog] Fetch error:', err.message, '— falling back to local materials.');
            }
            return null;
        }
    },

    /**
     * Check whether this engineer is whitelisted / active on the WM site.
     * Returns { connected: boolean, manager: string|null }.
     *
     * @param {string} engineerEmail — logged-in engineer's email address
     */
    checkWMConnectionStatus: async (engineerEmail) => {
        try {
            const response = await fetch(
                `${WM_BASE_URL}/api/inventory/engineer-status/?email=${encodeURIComponent(engineerEmail)}`,
                {
                    method: 'GET',
                    headers: {
                        'X-Engineer-Email': engineerEmail,
                        'X-Site-B-API-Key': 'stockpad-site-b-key',
                    },
                    signal: AbortSignal.timeout(8000),
                }
            );
            if (response.ok) {
                const data = await response.json();
                // WM API returns { active: true/false, manager_name: '...' }
                return { connected: data.active === true, manager: data.manager_name || null };
            }
            // 403/404 → engineer is not whitelisted
            return { connected: false, manager: null };
        } catch (err) {
            console.warn('[WM Status] Could not reach WM server:', err.message);
            return { connected: false, manager: null, unreachable: true };
        }
    },

    /**
     * Submit a material request, explicitly embedding the requester's email
     * for WM-side identity verification (Task 2).
     */
    createRequest: async (materialId, quantity, notes) => {
        const requesterEmail = localStorage.getItem('user_email') || '';
        return api.request('/requests/', 'POST', {
            material: materialId,
            quantity_needed: quantity,
            justification: notes,
            requester_email: requesterEmail,
        });
    },
    getMyRequests: async (status = null) => { let ep = '/requests/mine/'; if (status) ep += `?status=${status}`; return api.request(ep); },
    getAllRequests: async (status = null) => { let ep = '/requests/all/'; if (status) ep += `?status=${status}`; return api.request(ep); },
    approveRequest: async (id) => api.request(`/requests/${id}/approve/`, 'PATCH'),
    rejectRequest: async (id, reason) => api.request(`/requests/${id}/reject/`, 'PATCH', { reason }),
    updateRequest: async (id, quantity, justification) => api.request(`/requests/${id}/`, 'PATCH', { quantity_needed: quantity, justification }),
    deleteRequest: async (id) => api.request(`/requests/${id}/`, 'DELETE'),
    getConversations: async () => api.request('/chatbot/conversations/'),
    getConversationDetails: async (id) => api.request(`/chatbot/conversations/${id}/`),
    deleteConversation: async (id) => api.request(`/chatbot/conversations/${id}/`, 'DELETE'),
    requireAuth: () => { if (!api.getToken()) { navigateTo('login'); return false; } return true; },
    chat: async (message, files = [], conversationId = null) => {
        const currentLang = localStorage.getItem('lang') || 'en'; let payload;
        if (files && files.length > 0) { payload = new FormData(); payload.append('message', message); payload.append('lang', currentLang); if (conversationId) payload.append('conversation_id', conversationId); files.forEach(f => payload.append('files', f)); }
        else { payload = { message, lang: currentLang }; if (conversationId) payload.conversation_id = conversationId; }
        return api.request('/chatbot/', 'POST', payload);
    },
    forgotPassword: async (email) => { let url = window.location.href.split('#')[0].split('?')[0]; return api.request('/auth/password-reset/', 'POST', { email, frontend_url: url }, false); },
    resetPassword: async (uid, token, password) => api.request('/auth/password-reset-confirm/', 'POST', { uid, token, password }, false),
    getNotifications: async () => api.request('/notifications/'),
    showModal: (title, message, isError = false, callback = null) => {
        const isDark = document.documentElement.classList.contains('dark-mode');
        const overlay = document.createElement('div');
        overlay.style = `position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);display:flex;justify-content:center;align-items:center;z-index:99999;animation:modalFadeIn 0.3s ease;`;
        const content = document.createElement('div');
        content.style = `background:${isDark?'#1f2937':'white'};color:${isDark?'#f3f4f6':'#111827'};padding:2.5rem;border-radius:20px;max-width:420px;width:90%;text-align:center;box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);border:1px solid ${isDark?'#374151':'#e5e7eb'};`;
        const iconColor = isError ? '#ef4444' : '#f97316';
        content.innerHTML = `<div style="width:60px;height:60px;background:${iconColor}20;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 1.5rem;"><i class="fas ${isError?'fa-exclamation-triangle':(callback?'fa-question-circle':'fa-check-circle')}" style="font-size:1.5rem;color:${iconColor};"></i></div><h3 style="margin-top:0;font-size:1.5rem;font-weight:700;margin-bottom:0.5rem;">${title}</h3><p style="color:${isDark?'#9ca3af':'#6b7280'};margin-bottom:2rem;line-height:1.5;">${message}</p><div style="display:flex;gap:12px;justify-content:center;">${callback?`<button id="modalCancel" style="background:${isDark?'#374151':'#f3f4f6'};color:${isDark?'#f3f4f6':'#111827'};border:none;padding:0.8rem 1.5rem;border-radius:12px;cursor:pointer;font-weight:600;flex:1;">Cancel</button>`:''}<button id="modalConfirm" style="background:${iconColor};color:white;border:none;padding:0.8rem 1.5rem;border-radius:12px;cursor:pointer;font-weight:700;flex:1;">${callback?'Yes, Proceed':'Got it'}</button></div>`;
        overlay.appendChild(content);
        document.body.appendChild(overlay);
        const close = (result) => { document.body.removeChild(overlay); if (callback) callback(result); };
        content.querySelector('#modalConfirm').onclick = () => close(true);
        if (callback) content.querySelector('#modalCancel').onclick = () => close(false);
    },
};

// ══════════════════════════════════════════════════════════════
// NAVIGATION / SPA ROUTER
// ══════════════════════════════════════════════════════════════
const AUTH_VIEWS = ['login', 'signup', 'forgot', 'reset'];
const APP_VIEWS = ['inventory', 'chatbot', 'requests', 'profile'];
let currentView = null;
let viewInitialized = {};

function navigateTo(view) {
    // Hide all
    AUTH_VIEWS.forEach(v => { const el = document.getElementById(`view-${v}`); if (el) el.classList.remove('active'); });
    APP_VIEWS.forEach(v => { const el = document.getElementById(`view-${v}`); if (el) el.style.display = 'none'; });
    const appWrapper = document.getElementById('app-wrapper');

    if (AUTH_VIEWS.includes(view)) {
        appWrapper.classList.remove('active');
        document.getElementById(`view-${view}`).classList.add('active');
    } else if (APP_VIEWS.includes(view)) {
        if (!api.getToken()) { navigateTo('login'); return; }
        appWrapper.classList.add('active');
        document.getElementById(`view-${view}`).style.display = 'block';
        // Update sidebar active state
        document.querySelectorAll('.nav-item[data-view]').forEach(el => { el.classList.toggle('active', el.dataset.view === view); });
    }
    currentView = view;
    window.location.hash = view;
    // Initialize view if first time
    if (!viewInitialized[view]) { viewInitialized[view] = true; initView(view); }
    else if (view === 'inventory') loadMaterials();
    else if (view === 'requests') loadRequests();
    else if (view === 'profile') { loadProfile(); loadRecentActivity(); }
    i18n.applyToPage();
}

// ══════════════════════════════════════════════════════════════
// THEME TOGGLE
// ══════════════════════════════════════════════════════════════
function setupTheme() {
    const themeToggle = document.getElementById('themeToggle');
    if (!themeToggle) return;
    const updateThemeUI = () => {
        const isDark = document.documentElement.classList.contains('dark-mode');
        const icon = themeToggle.querySelector('i');
        const text = themeToggle.querySelector('span');
        if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        if (text) text.textContent = i18n.t(isDark ? 'sidebar.lightMode' : 'sidebar.darkMode');
    };
    updateThemeUI();
    themeToggle.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark-mode');
        localStorage.setItem('theme', document.documentElement.classList.contains('dark-mode') ? 'dark' : 'light');
        updateThemeUI();
        i18n.applyToPage();
    });
}

// ══════════════════════════════════════════════════════════════
// NOTIFICATIONS (shared)
// ══════════════════════════════════════════════════════════════
function timeAgo(iso) {
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff/60) + 'm ago';
    if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
    return Math.floor(diff/86400) + 'd ago';
}

async function loadNotificationsFor(prefix) {
    try {
        const data = await api.getNotifications();
        const notifs = data.notifications || [];
        const badge = document.getElementById(`${prefix}-notifBadge`);
        const list = document.getElementById(`${prefix}-notifList`);
        if (!badge || !list) return;
        if (notifs.length > 0) {
            badge.textContent = notifs.length > 9 ? '9+' : notifs.length;
            badge.style.display = 'flex';
            list.innerHTML = notifs.map(n => `<div style="padding:0.8rem 1.2rem;display:flex;align-items:flex-start;gap:0.65rem;border-bottom:1px solid var(--border-color);"><i class="fas fa-${n.icon}" style="color:${n.color};margin-top:2px;"></i><div><div style="font-size:0.83rem;color:var(--text-primary);line-height:1.4;">${n.text}</div><div style="font-size:0.74rem;color:var(--text-muted);margin-top:2px;">${timeAgo(n.time)}</div></div></div>`).join('');
        } else {
            badge.style.display = 'none';
            list.innerHTML = '<div style="padding:1.5rem;text-align:center;color:var(--text-muted);font-size:0.85rem;">You\'re all caught up! ✓</div>';
        }
    } catch(e) { /* silently fail */ }
}

function setupNotifBell(prefix) {
    const bell = document.getElementById(`${prefix}-notifBell`);
    const panel = document.getElementById(`${prefix}-notifPanel`);
    if (!bell || !panel) return;
    bell.addEventListener('click', e => { e.stopPropagation(); panel.style.display = panel.style.display === 'block' ? 'none' : 'block'; });
    document.addEventListener('click', () => { panel.style.display = 'none'; });
    loadNotificationsFor(prefix);
    setInterval(() => loadNotificationsFor(prefix), 30000);
}

// ══════════════════════════════════════════════════════════════
// VIEW INITIALIZERS
// ══════════════════════════════════════════════════════════════
function initView(view) {
    switch(view) {
        case 'login': initLogin(); break;
        case 'signup': initSignup(); break;
        case 'forgot': initForgot(); break;
        case 'reset': initReset(); break;
        case 'inventory': initInventory(); break;
        case 'chatbot': initChatbot(); break;
        case 'requests': initRequests(); break;
        case 'profile': initProfile(); break;
    }
}

// ── LOGIN ────────────────────────────────────────────────────
function initLogin() {
    document.getElementById('loginBtn').addEventListener('click', async () => {
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const rememberMe = document.getElementById('rememberMe').checked;
        if (!email || !password) { api.showModal('Error', 'Please fill in all fields.', true); return; }
        try {
            const user = await api.login(email, password, rememberMe);
            if (user) navigateTo('inventory');
        } catch (error) { api.showModal('Login Failed', error.message, true); }
    });
    document.getElementById('login-password').addEventListener('keyup', e => { if (e.key === 'Enter') document.getElementById('loginBtn').click(); });
}

// ── SIGNUP ───────────────────────────────────────────────────
function initSignup() {
    document.getElementById('signupBtn').addEventListener('click', async () => {
        const username = document.getElementById('signup-username').value.trim();
        const email = document.getElementById('signup-email').value.trim();
        const password = document.getElementById('signup-password').value;
        const confirm = document.getElementById('signup-confirm').value;
        const role = document.getElementById('signup-role').value;
        if (!username || !email || !password || !confirm) { api.showModal('Error', 'Please fill in all fields.', true); return; }
        if (!email.includes('@')) { api.showModal('Error', 'Please enter a valid email address.', true); return; }
        if (password !== confirm) { api.showModal('Error', 'Passwords do not match.', true); return; }
        try {
            await api.register(username, email, password, role);
            api.showModal('Success', 'Account created successfully! Redirecting to login...');
            setTimeout(() => navigateTo('login'), 2000);
        } catch (error) { api.showModal('Registration Failed', error.message, true); }
    });
}

// ── FORGOT PASSWORD ──────────────────────────────────────────
function initForgot() {
    document.getElementById('forgotBtn').addEventListener('click', async () => {
        const email = document.getElementById('forgot-email').value;
        if (!email || !email.includes('@')) { api.showModal('Error', 'Please enter a valid email address.', true); return; }
        try {
            const btn = document.getElementById('forgotBtn');
            const originalText = btn.innerText; btn.innerText = 'Sending...'; btn.disabled = true;
            const result = await api.forgotPassword(email);
            api.showModal('Reset Link Sent', result.message || 'If an account exists with this email, you will receive a reset link shortly.');
            btn.innerText = originalText; btn.disabled = false;
        } catch (err) { api.showModal('Error', err.message, true); const btn = document.getElementById('forgotBtn'); btn.innerText = 'Send Reset Link'; btn.disabled = false; }
    });
}

// ── RESET PASSWORD ───────────────────────────────────────────
function initReset() {
    const urlParams = new URLSearchParams(window.location.search);
    const uid = urlParams.get('uid'), token = urlParams.get('token');
    if (!uid || !token) { api.showModal('Invalid Link', 'This password reset link is invalid or has expired.', true, () => navigateTo('forgot')); }
    document.getElementById('resetBtn').addEventListener('click', async () => {
        const password = document.getElementById('reset-newPassword').value;
        const confirm = document.getElementById('reset-confirmPassword').value;
        if (password.length < 8) { api.showModal('Error', 'Password must be at least 8 characters long.', true); return; }
        if (password !== confirm) { api.showModal('Error', 'Passwords do not match.', true); return; }
        try {
            const btn = document.getElementById('resetBtn'); btn.innerText = 'Resetting...'; btn.disabled = true;
            await api.resetPassword(uid, token, password);
            api.showModal('Success', 'Your password has been reset successfully.', false, () => navigateTo('login'));
        } catch (err) { api.showModal('Reset Failed', err.message, true); const btn = document.getElementById('resetBtn'); btn.innerText = 'Reset Password'; btn.disabled = false; }
    });
}

// ── GOOGLE AUTHENTICATION ────────────────────────────────────
const GOOGLE_CLIENT_ID = '300690246891-chol78ebq3ila9lpjs82qh7581djpin9.apps.googleusercontent.com'; // Replace with your actual Google Client ID

function handleGoogleResponse(response) {
    if (!response || !response.credential) {
        api.showModal('Error', 'Google authentication failed. No credential received.', true);
        return;
    }
    
    // Disable buttons layout during request
    const btnContainer1 = document.getElementById('googleLoginBtnContainer');
    const btnContainer2 = document.getElementById('googleSignupBtnContainer');
    if (btnContainer1) btnContainer1.style.opacity = '0.5';
    if (btnContainer2) btnContainer2.style.opacity = '0.5';
    
    api.googleLogin(response.credential)
        .then((user) => {
            if (user) {
                navigateTo('inventory');
            }
        })
        .catch(err => {
            api.showModal('Google Login Failed', err.message, true);
        })
        .finally(() => {
            if (btnContainer1) btnContainer1.style.opacity = '1';
            if (btnContainer2) btnContainer2.style.opacity = '1';
        });
}

function initGoogleAuth() {
    if (typeof google === 'undefined' || !google.accounts) {
        setTimeout(initGoogleAuth, 100);
        return;
    }
    
    google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse
    });
    
    const loginContainer = document.getElementById('googleLoginBtnContainer');
    if (loginContainer) {
        google.accounts.id.renderButton(
            loginContainer,
            { theme: 'outline', size: 'large', shape: 'rectangular', text: 'signin_with' }
        );
    }
    
    const signupContainer = document.getElementById('googleSignupBtnContainer');
    if (signupContainer) {
        google.accounts.id.renderButton(
            signupContainer,
            { theme: 'outline', size: 'large', shape: 'rectangular', text: 'signup_with' }
        );
    }
}

// ══════════════════════════════════════════════════════════════
// INVENTORY
// ══════════════════════════════════════════════════════════════
let allMaterials = [];
let selectedCategory = 'all';

function initInventory() {
    setupNotifBell('inv');
    loadMaterials();
    // Category chips
    document.querySelectorAll('.category-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            selectedCategory = chip.dataset.category;
            renderMaterials();
        });
    });
    // Search
    const searchInput = document.getElementById('inventorySearch');
    const clearBtn = document.getElementById('clearSearchBtn');
    searchInput.addEventListener('input', () => { clearBtn.style.display = searchInput.value ? 'flex' : 'none'; renderMaterials(); });
    clearBtn.addEventListener('click', () => { searchInput.value = ''; clearBtn.style.display = 'none'; renderMaterials(); });
    // Modal submit
    document.getElementById('modalSubmitBtn').addEventListener('click', submitInventoryRequest);
}

// ── WM catalog source indicator (set to true when live WM data is shown) ──
let _wmCatalogActive = false;

async function loadMaterials() {
    const engineerEmail = localStorage.getItem('user_email') || '';
    let wmData = null;

    // ── Task 1: Attempt async WM catalog fetch with the engineer's email ──
    if (engineerEmail) {
        wmData = await api.fetchWMCatalog(engineerEmail);
    }

    if (wmData && wmData.length > 0) {
        // WM catalog loaded — use it exclusively so both sites mirror the same data.
        allMaterials = wmData;
        _wmCatalogActive = true;
        _showCatalogSourceBanner(true);
        console.info(`[WM Catalog] Loaded ${wmData.length} materials for ${engineerEmail} from WM site.`);
    } else {
        // Fall back to the local PE inventory (WM unreachable or engineer not whitelisted).
        _wmCatalogActive = false;
        _showCatalogSourceBanner(false);
        try {
            const data = await api.getMaterials();
            allMaterials = Array.isArray(data) ? data : (data.results || []);
        } catch(e) {
            console.error('[Inventory] Failed to load local materials:', e);
        }
    }

    renderMaterials();
}

/**
 * Shows a subtle banner at the top of the inventory grid indicating whether
 * the catalogue is sourced from the WM site or the local PE database.
 */
function _showCatalogSourceBanner(isWM) {
    const grid = document.getElementById('productsGrid');
    if (!grid) return;
    const existing = document.getElementById('catalogSourceBanner');
    if (existing) existing.remove();
    const banner = document.createElement('div');
    banner.id = 'catalogSourceBanner';
    banner.style.cssText = [
        'grid-column:1/-1', 'display:flex', 'align-items:center', 'gap:0.5rem',
        `padding:0.55rem 1rem`, 'border-radius:10px', 'font-size:0.82rem', 'font-weight:600',
        'margin-bottom:0.25rem', 'animation:fadeInDown 0.4s ease',
        isWM
            ? 'background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);color:#15803d;'
            : 'background:rgba(251,146,60,0.1);border:1px solid rgba(251,146,60,0.3);color:#92400e;'
    ].join(';');
    banner.innerHTML = isWM
        ? `<i class="fas fa-link"></i> Showing live catalogue from your Warehouse Manager`
        : `<i class="fas fa-database"></i> Showing local inventory (WM site not reachable)`;
    grid.prepend(banner);
}

function renderMaterials() {
    const grid = document.getElementById('productsGrid');
    const searchVal = (document.getElementById('inventorySearch')?.value || '').toLowerCase();
    let filtered = allMaterials;
    if (selectedCategory !== 'all') filtered = filtered.filter(m => (m.category_name || m.category || '').toLowerCase().includes(selectedCategory));
    if (searchVal) filtered = filtered.filter(m => m.name.toLowerCase().includes(searchVal));
    grid.innerHTML = filtered.map((m, i) => {
        const statusClass = m.stock_status === 'out_of_stock' ? 'Out of Stock' : (m.stock_status === 'low_stock' ? 'Low Stock' : 'In Stock');
        const lastUpdated = m.last_updated ? new Date(m.last_updated).toLocaleDateString() : '-';
        return `<div class="product-card animate-in" style="animation-delay:${i*0.03}s">
            <div class="card-header"><h3 class="product-name">${m.name}</h3><span class="stock-badge">${statusClass}</span></div>
            <div class="card-body"><p class="product-category">${m.category_name || m.category || ''}</p>
            <div class="stock-text-container"><span class="stock-qty">${m.quantity} ${m.unit || ''}</span><span class="stock-date">Updated: ${lastUpdated}</span></div></div>
            <div class="card-footer"><button class="request-btn" onclick="openRequestModal(${m.id}, '${m.name.replace(/'/g, "\\'")}', '${m.unit || 'Units'}')">${i18n.t('inv.request') || 'Request'}</button></div>
        </div>`;
    }).join('');
    if (filtered.length === 0) grid.innerHTML = '<p style="text-align:center;color:var(--text-muted);grid-column:1/-1;padding:3rem;">No materials found.</p>';
}

let currentModalMaterial = null;
function openRequestModal(id, name, unit) {
    currentModalMaterial = id;
    document.getElementById('modalMaterialName').textContent = name;
    document.getElementById('modalUnitText').textContent = unit;
    document.getElementById('modalQtyInput').value = '';
    document.getElementById('modalNotesInput').value = '';
    document.getElementById('requestModal').style.display = 'flex';
}
function closeRequestModal() { document.getElementById('requestModal').style.display = 'none'; }
async function submitInventoryRequest() {
    const qty = parseInt(document.getElementById('modalQtyInput').value);
    const notes = document.getElementById('modalNotesInput').value;
    if (!qty || qty < 1) { api.showModal('Error', 'Please enter a valid quantity.', true); return; }
    try {
        await api.createRequest(currentModalMaterial, qty, notes);
        api.showModal('Success', 'Request submitted successfully!');
        closeRequestModal();
    } catch(e) { api.showModal('Error', e.message, true); }
}

// ══════════════════════════════════════════════════════════════
// CHATBOT
// ══════════════════════════════════════════════════════════════
let chatConversationId = null;
let chatFiles = [];

function initChatbot() {
    setupNotifBell('chat');
    addBotMessage(i18n.t('chat.welcome'));
    // Send
    document.getElementById('sendBtn').addEventListener('click', sendChatMessage);
    document.getElementById('chatInput').addEventListener('keyup', e => { if (e.key === 'Enter') sendChatMessage(); });
    // File attach
    document.getElementById('attachBtn').addEventListener('click', () => document.getElementById('fileInput').click());
    document.getElementById('fileInput').addEventListener('change', e => {
        chatFiles = [...chatFiles, ...Array.from(e.target.files)];
        renderFilePreview(); e.target.value = '';
    });
    // History
    document.getElementById('showHistoryBtn').addEventListener('click', openHistory);
    document.getElementById('closeHistory').addEventListener('click', closeHistory);
    document.getElementById('historyOverlay').addEventListener('click', closeHistory);
    document.getElementById('newChatBtn').addEventListener('click', () => {
        chatConversationId = null; chatFiles = [];
        document.getElementById('chatMessages').innerHTML = '';
        addBotMessage(i18n.t('chat.welcome'));
    });
}

function addBotMessage(text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'message bot-message';
    // Simple markdown: bold, lists
    let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
    if (html.includes('<li>')) html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    html = html.replace(/\n/g, '<br>');
    div.innerHTML = `<div class="message-avatar"><i class="fas fa-robot"></i></div><div class="message-bubble"><p>${html}</p><span class="message-time">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span></div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addUserMessage(text, files = []) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'message user-message';
    let attachHTML = '';
    if (files.length > 0) attachHTML = `<div class="message-attachments">${files.map(f => `<div class="attachment-item"><i class="fas fa-file"></i><span>${f.name}</span></div>`).join('')}</div>`;
    div.innerHTML = `<div class="message-avatar"><i class="fas fa-user"></i></div><div class="message-bubble"><p>${text}</p>${attachHTML}<span class="message-time">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span></div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg && chatFiles.length === 0) return;
    addUserMessage(msg, chatFiles);
    input.value = '';
    const filesToSend = [...chatFiles]; chatFiles = [];
    document.getElementById('filePreview').style.display = 'none';
    // Show typing
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = '<div class="message-avatar"><i class="fas fa-robot"></i></div><div class="message-bubble"><p><i class="fas fa-spinner fa-spin"></i> Thinking...</p></div>';
    document.getElementById('chatMessages').appendChild(typingDiv);
    try {
        const result = await api.chat(msg, filesToSend, chatConversationId);
        if (result.conversation_id) chatConversationId = result.conversation_id;
        document.getElementById('typing-indicator')?.remove();
        addBotMessage(result.response || result.message || 'No response');
    } catch(e) {
        document.getElementById('typing-indicator')?.remove();
        addBotMessage('Sorry, I encountered an error. Please try again.');
    }
}

function askQuestion(q) { document.getElementById('chatInput').value = q; sendChatMessage(); }

function renderFilePreview() {
    const container = document.getElementById('filePreview');
    if (chatFiles.length === 0) { container.style.display = 'none'; return; }
    container.style.display = 'flex';
    container.innerHTML = chatFiles.map((f, i) => `<div class="preview-item"><i class="fas fa-file"></i><span>${f.name}</span><i class="fas fa-times remove-file" onclick="removeFile(${i})"></i></div>`).join('');
}
function removeFile(i) { chatFiles.splice(i, 1); renderFilePreview(); }

async function openHistory() {
    document.getElementById('historyPanel').classList.add('active');
    document.getElementById('historyOverlay').classList.add('active');
    try {
        const data = await api.getConversations();
        const convs = Array.isArray(data) ? data : (data.results || []);
        const list = document.getElementById('historyList');
        if (convs.length === 0) { list.innerHTML = `<p style="text-align:center;color:var(--text-muted);padding:2rem;">${i18n.t('chat.noHistory')}</p>`; return; }
        list.innerHTML = convs.map(c => {
            const date = new Date(c.updated_at || c.created_at).toLocaleDateString();
            return `<div class="history-item" onclick="loadConversation(${c.id})"><div class="history-item-header"><span class="history-date">${date}</span><i class="fas fa-trash delete-conv" onclick="event.stopPropagation();deleteConv(${c.id})"></i></div><h4 class="history-title">${c.title || 'Conversation'}</h4><span class="history-meta">${c.message_count || '?'} ${i18n.t('chat.messages')}</span></div>`;
        }).join('');
    } catch(e) { console.error(e); }
}
function closeHistory() { document.getElementById('historyPanel').classList.remove('active'); document.getElementById('historyOverlay').classList.remove('active'); }
async function loadConversation(id) {
    closeHistory();
    chatConversationId = id;
    const container = document.getElementById('chatMessages');
    container.innerHTML = '';
    try {
        const data = await api.getConversationDetails(id);
        const msgs = data.messages || [];
        msgs.forEach(m => { if (m.role === 'user') addUserMessage(m.content); else addBotMessage(m.content); });
    } catch(e) { addBotMessage('Failed to load conversation.'); }
}
async function deleteConv(id) {
    api.showModal(i18n.t('chat.confirmDelete'), '', false, async (ok) => { if (ok) { await api.deleteConversation(id); openHistory(); } });
}

// ══════════════════════════════════════════════════════════════
// REQUESTS
// ══════════════════════════════════════════════════════════════
let currentRejectId = null;
let currentEditId = null;

function initRequests() {
    setupNotifBell('req');
    loadRequests();
    loadMaterialsForSelect();
}

async function loadMaterialsForSelect() {
    try {
        const data = await api.getMaterials();
        const materials = Array.isArray(data) ? data : (data.results || []);
        const select = document.getElementById('reqMaterial');
        select.innerHTML = '<option value="">-- Select --</option>' + materials.map(m => `<option value="${m.id}" data-unit="${m.unit || 'Units'}">${m.name}</option>`).join('');
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $(select).select2({ dropdownParent: document.getElementById('newRequestModal'), placeholder: i18n.t('req.selectMaterial'), allowClear: true });
            $(select).on('change', function() {
                const opt = this.options[this.selectedIndex];
                document.getElementById('unitDisplay').textContent = opt?.dataset?.unit || '-';
            });
        }
    } catch(e) { console.error(e); }
}

async function loadRequests() {
    try {
        const role = localStorage.getItem('user_role');
        const isManager = role === 'warehouse' || role === 'admin';
        let requests;
        if (isManager) { const data = await api.getAllRequests(); requests = Array.isArray(data) ? data : (data.results || []); }
        else { const data = await api.getMyRequests(); requests = Array.isArray(data) ? data : (data.results || []); }
        renderRequests(requests, isManager);
    } catch(e) { console.error(e); }
}

function renderRequests(requests, isManager) {
    const list = document.getElementById('requestsList');
    const currentUserId = parseInt(localStorage.getItem('user_id'));
    if (requests.length === 0) { list.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:3rem;">No requests yet.</p>'; return; }
    requests.sort((a, b) => new Date(b.created_at || b.request_date) - new Date(a.created_at || a.request_date));
    list.innerHTML = requests.map(r => {
        const statusLabel = i18n.t(`req.${r.status}`);
        const date = new Date(r.created_at || r.request_date).toLocaleDateString();
        const isOwn = r.requested_by_id === currentUserId || r.user === currentUserId;
        const canManage = false; // Deprecated local approvals, managed on Website 1
        const canEdit = isOwn && r.status === 'pending';
        let actionsHTML = '';
        if (canManage) actionsHTML = `<div class="request-actions"><button class="btn-approve" onclick="approveReq(${r.id})"><i class="fas fa-check"></i> ${i18n.t('req.approve')}</button><button class="btn-reject" onclick="openRejectionModal(${r.id},'${(r.material_name||'').replace(/'/g,"\\'")}')"><i class="fas fa-times"></i> ${i18n.t('req.reject')}</button></div>`;
        if (r.status === 'approved') actionsHTML = `<div class="approval-info"><i class="fas fa-check-circle"></i> ${i18n.t('req.approved')}</div>`;
        if (r.status === 'rejected') actionsHTML = `<div class="rejection-info"><i class="fas fa-times-circle"></i> ${i18n.t('req.rejected')}${r.rejection_reason ? ': ' + r.rejection_reason : ''}</div>`;
        let userActionsHTML = '';
        if (canEdit) userActionsHTML = `<div class="user-actions"><button class="action-icon edit" onclick="openEditModal(${r.id},'${(r.material_name||'').replace(/'/g,"\\'")}',${r.quantity_needed || r.quantity},'${(r.justification||'').replace(/'/g,"\\'")}')" title="Edit"><i class="fas fa-pen"></i></button><button class="action-icon delete" onclick="deleteReq(${r.id})" title="Delete"><i class="fas fa-trash"></i></button></div>`;
        return `<div class="request-card ${r.status}">
            <div class="request-header"><div class="request-info"><h3>${r.material_name || 'Material'}</h3><span class="request-id">#REQ-${String(r.id).padStart(4,'0')}</span></div>${userActionsHTML}<span class="status-badge ${r.status}">${statusLabel}</span></div>
            <div class="request-body">
                <div class="request-detail"><i class="fas fa-boxes"></i><div><span class="detail-label">${i18n.t('req.requestedQty')}</span><span class="detail-value">${r.quantity_needed || r.quantity} ${r.unit || ''}</span></div></div>
                <div class="request-detail"><i class="fas fa-user"></i><div><span class="detail-label">${i18n.t('req.requestedBy')}</span><span class="detail-value">${r.requested_by || r.user_name || 'Unknown'} ${isOwn ? i18n.t('req.you') : ''}</span></div></div>
                <div class="request-detail"><i class="fas fa-calendar"></i><div><span class="detail-label">${i18n.t('req.requestDate')}</span><span class="detail-value">${date}</span></div></div>
            </div>
            ${r.justification ? `<div class="request-notes">${r.justification}</div>` : ''}
            ${actionsHTML}
        </div>`;
    }).join('');
}

function openNewRequestModal() { document.getElementById('newRequestModal').style.display = 'flex'; }
function closeNewRequestModal() { document.getElementById('newRequestModal').style.display = 'none'; }
async function submitRequest() {
    const matId = document.getElementById('reqMaterial').value;
    const qty = parseInt(document.getElementById('reqQuantity').value);
    const notes = document.getElementById('reqNotes').value;
    if (!matId) { api.showModal('Error', 'Please select a material.', true); return; }
    if (!qty || qty < 1) { api.showModal('Error', 'Please enter a valid quantity.', true); return; }
    // Task 2: api.createRequest now always includes requester_email from localStorage.
    try {
        await api.createRequest(parseInt(matId), qty, notes);
        api.showModal('Success', 'Request submitted!');
        closeNewRequestModal();
        loadRequests();
    } catch(e) { api.showModal('Error', e.message, true); }
}
async function approveReq(id) { try { await api.approveRequest(id); loadRequests(); } catch(e) { api.showModal('Error', e.message, true); } }
function openRejectionModal(id, name) { currentRejectId = id; document.getElementById('rejectionTarget').textContent = name; document.getElementById('rejectReason').value = ''; document.getElementById('rejectionModal').style.display = 'flex'; }
function closeRejectionModal() { document.getElementById('rejectionModal').style.display = 'none'; }
async function submitRejection() { const reason = document.getElementById('rejectReason').value; if (!reason) { api.showModal('Error', 'Please provide a rejection reason.', true); return; } try { await api.rejectRequest(currentRejectId, reason); closeRejectionModal(); loadRequests(); } catch(e) { api.showModal('Error', e.message, true); } }
function openEditModal(id, name, qty, notes) { currentEditId = id; document.getElementById('editMaterialName').textContent = name; document.getElementById('editQuantity').value = qty; document.getElementById('editNotes').value = notes; document.getElementById('editModal').style.display = 'flex'; }
function closeEditModal() { document.getElementById('editModal').style.display = 'none'; }
async function updateRequest() { const qty = parseInt(document.getElementById('editQuantity').value); const notes = document.getElementById('editNotes').value; try { await api.updateRequest(currentEditId, qty, notes); api.showModal('Success', 'Request updated!'); closeEditModal(); loadRequests(); } catch(e) { api.showModal('Error', e.message, true); } }
async function deleteReq(id) { api.showModal('Delete Request', 'Are you sure you want to delete this request?', true, async (ok) => { if (ok) { try { await api.deleteRequest(id); loadRequests(); } catch(e) { api.showModal('Error', e.message, true); } } }); }

// Export functions
function exportRequestsPDF() {
    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        doc.setFontSize(18); doc.text('Material Requests Report', 14, 22);
        doc.setFontSize(10); doc.text('Generated: ' + new Date().toLocaleString(), 14, 30);
        const rows = []; document.querySelectorAll('.request-card').forEach(card => {
            const name = card.querySelector('.request-info h3')?.textContent || '';
            const id = card.querySelector('.request-id')?.textContent || '';
            const status = card.querySelector('.status-badge')?.textContent || '';
            rows.push([id, name, status]);
        });
        doc.autoTable({ head: [['ID', 'Material', 'Status']], body: rows, startY: 35 });
        doc.save('requests-report.pdf');
    } catch(e) { api.showModal('Error', 'Failed to export PDF.', true); }
}
function exportRequestsExcel() {
    try {
        const rows = [['ID', 'Material', 'Status']];
        document.querySelectorAll('.request-card').forEach(card => {
            rows.push([card.querySelector('.request-id')?.textContent || '', card.querySelector('.request-info h3')?.textContent || '', card.querySelector('.status-badge')?.textContent || '']);
        });
        const ws = XLSX.utils.aoa_to_sheet(rows);
        const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Requests');
        XLSX.writeFile(wb, 'requests-report.xlsx');
    } catch(e) { api.showModal('Error', 'Failed to export Excel.', true); }
}

// ══════════════════════════════════════════════════════════════
// ACCOUNT PROFILE
// ══════════════════════════════════════════════════════════════
let currentUserData = null;

function initProfile() {
    loadProfile();
    loadRecentActivity();
    // Task 3: render the WM connection status badge asynchronously after profile loads.
    loadWMConnectionStatus();
}

async function loadProfile() {
    try {
        currentUserData = await api.getMe();
        const nameDisplay = `${currentUserData.first_name} ${currentUserData.last_name}`.trim() || currentUserData.username;
        document.getElementById('displayName').textContent = nameDisplay;
        document.getElementById('displayFullName').textContent = nameDisplay;
        document.getElementById('displayRole').textContent = i18n.t(`role.${currentUserData.role.toLowerCase()}`);
        document.getElementById('displayEmail').textContent = currentUserData.email;
        const img = document.getElementById('avatarImage');
        const icon = document.getElementById('avatarIcon');
        const avatar = currentUserData.avatar_url || currentUserData.avatar;
        if (avatar) { let url = avatar; if (url.startsWith('/')) url = API_BASE + url; img.src = url; img.style.display = 'block'; icon.style.display = 'none'; }
        document.getElementById('editName').value = currentUserData.username;
        document.getElementById('editFullName').value = nameDisplay;
        document.getElementById('editEmail').value = currentUserData.email;
        const roleMapping = { 'engineer': 'Engineer', 'warehouse': 'Warehouse', 'admin': 'Admin' };
        document.getElementById('editRole').value = roleMapping[currentUserData.role.toLowerCase()] || 'Engineer';
        // Ensure email is always persisted for WM integration (covers page-refresh scenarios)
        localStorage.setItem('user_email', currentUserData.email);
    } catch(e) { console.error('Failed to load profile:', e); }
}

/**
 * Task 3 — Async WM Connection Status Badge
 * Hits the WM API with the engineer's email and renders a live
 * green (Connected) or red (Not Connected) badge in the settings card.
 */
async function loadWMConnectionStatus() {
    const badge = document.getElementById('wmConnectionBadge');
    const badgeText = document.getElementById('wmConnectionBadgeText');
    const badgeManager = document.getElementById('wmConnectionManager');
    if (!badge || !badgeText) return; // badge element not yet in DOM

    // Show "Checking..." pulse while waiting
    badge.className = 'wm-badge wm-badge--checking';
    badgeText.textContent = i18n.t('profile.wmChecking');
    if (badgeManager) badgeManager.textContent = '';

    const engineerEmail = localStorage.getItem('user_email') ||
        (currentUserData ? currentUserData.email : '');

    if (!engineerEmail) {
        badge.className = 'wm-badge wm-badge--disconnected';
        badgeText.textContent = i18n.t('profile.wmNotConnected');
        return;
    }

    const result = await api.checkWMConnectionStatus(engineerEmail);

    if (result.connected) {
        badge.className = 'wm-badge wm-badge--connected';
        badgeText.textContent = i18n.t('profile.wmConnected');
        if (badgeManager && result.manager) {
            badgeManager.textContent = `Manager: ${result.manager}`;
        }
    } else {
        badge.className = 'wm-badge wm-badge--disconnected';
        badgeText.textContent = i18n.t('profile.wmNotConnected');
        if (badgeManager && result.unreachable) {
            badgeManager.textContent = 'WM server unreachable';
        }
    }
}

async function handleAvatarUpload(event) {
    const file = event.target.files[0]; if (!file) return;
    try { await api.uploadAvatar(file); api.showModal('Success', 'Profile photo updated!'); loadProfile(); } catch(e) { api.showModal('Upload Failed', e.message, true); }
}

async function toggleEditMode() {
    const editBtnText = document.getElementById('editBtnText');
    const isEditing = editBtnText.getAttribute('data-i18n') === 'profile.saveBtn';
    const fields = [{ display: 'displayFullName', edit: 'editFullName' }, { display: 'displayEmail', edit: 'editEmail' }, { display: 'displayName', edit: 'editName' }, { display: 'displayRole', edit: 'editRole' }];
    if (isEditing) {
        const fullName = document.getElementById('editFullName').value.trim();
        const email = document.getElementById('editEmail').value.trim();
        const role = document.getElementById('editRole').value;
        const [firstName, ...lastNameParts] = fullName.split(' ');
        try {
            await api.updateProfile({ first_name: firstName, last_name: lastNameParts.join(' '), email, role: role });
            api.showModal('Success', 'Profile updated successfully!');
            editBtnText.setAttribute('data-i18n', 'profile.editBtn'); editBtnText.textContent = i18n.t('profile.editBtn');
            fields.forEach(f => { document.getElementById(f.display).style.display = 'block'; document.getElementById(f.edit).style.display = 'none'; });
            loadProfile();
        } catch(e) { api.showModal('Update Failed', e.message, true); }
    } else {
        editBtnText.setAttribute('data-i18n', 'profile.saveBtn'); editBtnText.textContent = i18n.t('profile.saveBtn');
        fields.forEach(f => { document.getElementById(f.display).style.display = 'none'; document.getElementById(f.edit).style.display = 'block'; });
    }
}

async function loadRecentActivity() {
    try {
        const response = await api.getMyRequests();
        const requests = Array.isArray(response) ? response : (response.results || []);
        const activityList = document.getElementById('activityList');
        if (requests.length > 0) {
            activityList.innerHTML = '';
            requests.sort((a, b) => new Date(b.request_date) - new Date(a.request_date));
            requests.slice(0, 5).forEach(req => {
                const item = document.createElement('div'); item.className = 'activity-item';
                const iconClass = req.status === 'approved' ? 'fa-check-circle success' : (req.status === 'rejected' ? 'fa-times-circle danger' : 'fa-clock warning');
                const date = new Date(req.created_at || req.request_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                item.innerHTML = `<i class="fas ${iconClass}"></i><div><p>${req.material_name} — ${i18n.t('req.' + req.status)}</p><small>${date} • ${req.quantity || req.quantity_needed} units</small></div>`;
                activityList.appendChild(item);
            });
        } else {
            activityList.innerHTML = `<div class="activity-item"><i class="fas fa-info-circle"></i><div><p>${i18n.t('profile.noActivity')}</p><small>${i18n.t('profile.noActivitySub')}</small></div></div>`;
        }
    } catch(e) { console.error('Activity load error:', e); }
}

function openPasswordModal() { document.getElementById('passwordModal').style.display = 'flex'; }
function closePasswordModal() { document.getElementById('passwordModal').style.display = 'none'; }
async function savePassword() { api.showModal('Coming Soon', 'Password change functionality is being prioritized for the next release.'); closePasswordModal(); }

// ══════════════════════════════════════════════════════════════
// BOOTSTRAP — runs on page load
// ══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    i18n.init();
    setupTheme();
    initGoogleAuth();
    // Logout button
    document.getElementById('logoutBtn')?.addEventListener('click', e => { e.preventDefault(); api.logout(); });
    // Determine initial view
    const hash = window.location.hash.replace('#', '');
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('uid') && urlParams.get('token')) { navigateTo('reset'); }
    else if (hash && [...AUTH_VIEWS, ...APP_VIEWS].includes(hash)) { navigateTo(hash); }
    else if (api.getToken()) { navigateTo('inventory'); }
    else { navigateTo('login'); }
});
