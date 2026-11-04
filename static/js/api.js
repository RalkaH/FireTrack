// api.js - обёртка над backend API и общие утилиты интерфейса

const API_BASE_URL = '';
const TOKEN_KEY = 'access_token';
const LOGIN_PAGE = '/static/login.html';

/* ================= Утилиты ================= */

// Экранирует текст перед вставкой в HTML (защита от XSS и поломки разметки)
function esc(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Форматирует дату из API (ГГГГ-ММ-ДД или ISO) в ДД.ММ.ГГГГ без сдвига часового пояса
function formatDate(isoString) {
    if (!isoString) return '';
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoString);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return esc(isoString);
    return d.toLocaleDateString('ru-RU');
}

// Дата и время из API (UTC с суффиксом Z) в местное «ДД.ММ.ГГГГ ЧЧ:ММ:СС»
function formatDateTime(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return esc(isoString);
    return d.toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

// Склонение: plural(5, 'день', 'дня', 'дней') -> 'дней'
function plural(n, one, few, many) {
    const abs = Math.abs(n) % 100;
    const last = abs % 10;
    if (abs > 10 && abs < 20) return many;
    if (last === 1) return one;
    if (last >= 2 && last <= 4) return few;
    return many;
}

// Сегодняшняя дата в формате ГГГГ-ММ-ДД по местному времени
function todayISO() {
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Добавляет к дате ГГГГ-ММ-ДД указанное число месяцев
function addMonthsISO(isoDate, months) {
    const [y, m, d] = isoDate.split('-').map(Number);
    const date = new Date(y, m - 1 + months, d);
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/* ================= Сессия ================= */

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

// Достаёт payload из JWT без проверки подписи (подпись проверяет сервер)
function decodeTokenPayload(token) {
    try {
        const part = token.split('.')[1];
        const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
        const padded = base64 + '='.repeat((4 - base64.length % 4) % 4);
        return JSON.parse(atob(padded));
    } catch (e) {
        return null;
    }
}

// Сколько секунд токен ещё действует (0, если токена нет или он истёк)
function tokenSecondsLeft(token = getToken()) {
    if (!token) return 0;
    const payload = decodeTokenPayload(token);
    if (!payload || !payload.exp) return 0;
    return Math.max(0, Math.floor(payload.exp - Date.now() / 1000));
}

function isTokenValid(token = getToken()) {
    return tokenSecondsLeft(token) > 0;
}

let sessionRedirecting = false;

// Завершает сессию и отправляет на страницу входа.
// reason: 'expired' — сессия истекла, 'logout' — пользователь вышел сам
function redirectToLogin(reason = 'expired') {
    if (sessionRedirecting) return;
    sessionRedirecting = true;
    localStorage.removeItem(TOKEN_KEY);
    const params = reason === 'logout' ? '' : `?reason=${encodeURIComponent(reason)}`;
    window.location.replace(LOGIN_PAGE + params);
}

// Периодически проверяет срок токена, чтобы выкинуть на вход сразу после истечения
function startSessionWatcher() {
    if (!getToken()) {
        // Ещё не входили — просто открываем форму входа без сообщения об истечении
        redirectToLogin('logout');
        return false;
    }
    if (!isTokenValid()) {
        redirectToLogin('expired');
        return false;
    }
    setInterval(() => {
        if (!isTokenValid()) redirectToLogin('expired');
    }, 30 * 1000);
    // Проверка при возврате на вкладку (например, после сна ноутбука)
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && !isTokenValid()) {
            redirectToLogin('expired');
        }
    });
    return true;
}

/* ================= HTTP ================= */

// Превращает тело ошибки FastAPI в понятный текст
async function extractErrorMessage(resp) {
    let text = '';
    try {
        text = await resp.text();
        const data = JSON.parse(text);
        if (typeof data.detail === 'string') return data.detail;
        if (Array.isArray(data.detail)) {
            return data.detail
                .map(item => {
                    const field = Array.isArray(item.loc) ? item.loc.filter(p => p !== 'body').join('.') : '';
                    const msg = (item.msg || '').replace(/^Value error, /, '');
                    return field ? `${field}: ${msg}` : msg;
                })
                .join('; ');
        }
    } catch (e) {
        // не JSON — вернём как есть
    }
    return text || `Ошибка сервера (HTTP ${resp.status})`;
}

async function authorizedFetch(path, options = {}) {
    const token = getToken();
    if (!isTokenValid(token)) {
        redirectToLogin('expired');
        throw new Error('Сессия истекла');
    }

    const headers = options.headers ? { ...options.headers } : {};
    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    headers['Authorization'] = `Bearer ${token}`;

    let resp;
    try {
        resp = await fetch(API_BASE_URL + path, { ...options, headers });
    } catch (e) {
        throw new Error('Сервер недоступен. Проверьте, что приложение запущено.');
    }

    if (resp.status === 401) {
        redirectToLogin('expired');
        throw new Error('Сессия истекла');
    }
    // Сервер требует сменить пароль (временный пароль или admin123)
    if (resp.status === 403 && resp.headers.get('X-Password-Change-Required') === '1') {
        if (typeof showChangePasswordModal === 'function') showChangePasswordModal(true);
        throw new Error('Сначала смените пароль');
    }
    if (!resp.ok) {
        throw new Error(await extractErrorMessage(resp));
    }
    if (resp.status === 204) return null;

    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
        return resp.json();
    }
    return resp;
}

// Собирает ?a=1&b=2 из объекта, пропуская пустые значения
function queryString(params = {}) {
    const clean = Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined);
    if (clean.length === 0) return '';
    return '?' + new URLSearchParams(clean).toString();
}

// Скачивает ответ сервера как файл
async function downloadBlob(resp, fallbackName) {
    const blob = await resp.blob();
    const disposition = resp.headers.get('content-disposition') || '';
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = match ? match[1] : fallbackName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
}

const API = {
    /* -------- Общие -------- */

    logout() {
        redirectToLogin('logout');
    },

    getMe() {
        return authorizedFetch('/auth/me', { method: 'GET' });
    },

    /* -------- Дашборд / отчёты -------- */

    getDashboard() {
        return authorizedFetch('/reports/dashboard', { method: 'GET' });
    },

    getUpcomingInspections(days) {
        return authorizedFetch(`/reports/upcoming?days=${encodeURIComponent(days)}`, { method: 'GET' });
    },

    getExpiredList() {
        return authorizedFetch('/reports/expired', { method: 'GET' });
    },

    getRechargeList() {
        return authorizedFetch('/reports/recharge', { method: 'GET' });
    },

    // Данные отчёта для страницы печати: kind = journal | maintenance | fleet
    getPrintData(kind, params = {}) {
        return authorizedFetch(`/reports/print/${encodeURIComponent(kind)}${queryString(params)}`, { method: 'GET' });
    },

    // Скачивает файл отчёта (XLSX, CSV) с учётом фильтров
    async downloadFile(path, params = {}, fallbackName = 'report') {
        const resp = await authorizedFetch(path + queryString(params), { method: 'GET' });
        await downloadBlob(resp, fallbackName);
    },

    async downloadCSV() {
        try {
            const resp = await authorizedFetch('/reports/journal.csv', { method: 'GET' });
            await downloadBlob(resp, 'journal.csv');
        } catch (error) {
            showAlert('Не удалось скачать журнал: ' + error.message, 'danger');
        }
    },

    async downloadJournalJSON() {
        try {
            const data = await authorizedFetch('/reports/journal', { method: 'GET' });
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `journal_${todayISO()}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            showAlert('Не удалось выгрузить журнал: ' + error.message, 'danger');
        }
    },

    recalculateStatuses() {
        return authorizedFetch('/statuses/recalculate', { method: 'POST' });
    },

    /* -------- Справочники -------- */

    getLocations() {
        return authorizedFetch('/locations/', { method: 'GET' });
    },

    createLocation(data) {
        return authorizedFetch('/locations/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    getEmployees() {
        return authorizedFetch('/employees/', { method: 'GET' });
    },

    createEmployee(data) {
        return authorizedFetch('/employees/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    getStatuses() {
        return authorizedFetch('/statuses/', { method: 'GET' });
    },

    /* -------- Огнетушители -------- */

    getExtinguishers() {
        return authorizedFetch('/extinguishers/', { method: 'GET' });
    },

    createExtinguisher(data) {
        return authorizedFetch('/extinguishers/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    getExtinguisher(id) {
        return authorizedFetch(`/extinguishers/${id}`, { method: 'GET' });
    },

    updateExtinguisher(id, data) {
        return authorizedFetch(`/extinguishers/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    deleteExtinguisher(id) {
        return authorizedFetch(`/extinguishers/${id}`, { method: 'DELETE' });
    },

    getInspectionsByExtinguisher(id) {
        return authorizedFetch(`/inspections/by-extinguisher/${id}`, { method: 'GET' });
    },

    /* -------- Журнал проверок -------- */

    getJournal(params = {}) {
        const q = new URLSearchParams(params).toString();
        return authorizedFetch('/inspections/' + (q ? `?${q}` : ''), { method: 'GET' });
    },

    createInspection(data) {
        return authorizedFetch('/inspections/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /* -------- Импорт CSV/текста -------- */

    importLocations(formData) {
        return authorizedFetch('/import/locations', { method: 'POST', body: formData });
    },

    importEmployees(formData) {
        return authorizedFetch('/import/employees', { method: 'POST', body: formData });
    },

    importExtinguishers(formData) {
        return authorizedFetch('/import/extinguishers', { method: 'POST', body: formData });
    },

    importInspections(formData) {
        return authorizedFetch('/import/inspections', { method: 'POST', body: formData });
    },

    /* -------- Перезарядка -------- */

    markRecharged(id, data) {
        return authorizedFetch(`/extinguishers/${id}/recharge`, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /* -------- Пароль -------- */

    // Меняет пароль и сохраняет новый токен (старые токены сервер отзывает)
    async changePassword(oldPassword, newPassword) {
        const result = await authorizedFetch('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
        localStorage.setItem(TOKEN_KEY, result.access_token);
        return result;
    },

    /* -------- Пользователи (admin) -------- */

    getUsers() {
        return authorizedFetch('/users/', { method: 'GET' });
    },

    createUser(data) {
        return authorizedFetch('/users/', { method: 'POST', body: JSON.stringify(data) });
    },

    updateUser(id, data) {
        return authorizedFetch(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
    },

    setUserActive(id, isActive) {
        return authorizedFetch(`/users/${id}/status`, {
            method: 'POST',
            body: JSON.stringify({ is_active: isActive })
        });
    },

    resetUserPassword(id, newPassword) {
        return authorizedFetch(`/users/${id}/reset-password`, {
            method: 'POST',
            body: JSON.stringify({ new_password: newPassword })
        });
    },

    /* -------- Журнал действий (admin) -------- */

    getAudit(params = {}) {
        return authorizedFetch('/audit/' + queryString(params), { method: 'GET' });
    },

    getAuditMeta() {
        return authorizedFetch('/audit/meta', { method: 'GET' });
    },

    /* -------- Настройки -------- */

    getSettings() {
        return authorizedFetch('/settings/', { method: 'GET' });
    },

    saveSettings(values) {
        return authorizedFetch('/settings/', { method: 'PUT', body: JSON.stringify(values) });
    }
};
