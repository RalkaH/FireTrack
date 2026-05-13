// api.js - обёртка над backend API

const API_BASE_URL = '';

function getToken() {
    return localStorage.getItem('access_token');
}

async function authorizedFetch(path, options = {}) {
    const token = getToken();
    const headers = options.headers ? { ...options.headers } : {};

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const resp = await fetch(API_BASE_URL + path, {
        ...options,
        headers
    });

    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `HTTP ${resp.status}`);
    }
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
        return resp.json();
    }
    return resp;
}

const API = {
    /* -------- Общие -------- */

    logout() {
        localStorage.removeItem('access_token');
        window.location.href = '/static/login.html';
    },

    /* -------- Дашборд / отчёты -------- */

    getDashboard() {
        return authorizedFetch('/reports/dashboard', {
            method: 'GET'
        });
    },

    getUpcomingInspections(days) {
        return authorizedFetch(`/reports/upcoming?days=${encodeURIComponent(days)}`, {
            method: 'GET'
        });
    },

    getExpiredList() {
        return authorizedFetch('/reports/expired', {
            method: 'GET'
        });
    },

    downloadCSV() {
        return authorizedFetch('/reports/journal.csv', {
            method: 'GET'
        }).then(async (resp) => {
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'journal.csv';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        });
    },

    downloadJournalJSON() {
        return authorizedFetch('/reports/journal', {
            method: 'GET'
        }).then(async (resp) => {
            const data = new Blob([JSON.stringify(resp, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(data);
            const a = document.createElement('a');
            a.href = url;
            a.download = `journal_${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        });
    },

    recalculateStatuses() {
        return authorizedFetch('/statuses/recalculate', {
            method: 'POST'
        });
    },

    /* -------- Справочники -------- */

    getLocations() {
        return authorizedFetch('/locations', { method: 'GET' });
    },

    createLocation(data) {
        return authorizedFetch('/locations', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    getEmployees() {
        return authorizedFetch('/employees', { method: 'GET' });
    },

    createEmployee(data) {
        return authorizedFetch('/employees', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // статусы
    getStatuses() {
        return authorizedFetch('/statuses', { method: 'GET' });
    },

    /* -------- Огнетушители -------- */

    getExtinguishers() {
        return authorizedFetch('/extinguishers', { method: 'GET' });
    },

    createExtinguisher(data) {
        return authorizedFetch('/extinguishers', {
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
        return authorizedFetch(`/extinguishers/${id}`, {
            method: 'DELETE'
        });
    },

    getInspectionsByExtinguisher(id) {
        return authorizedFetch(`/inspections/by-extinguisher/${id}`, {
            method: 'GET'
        });
    },

    /* -------- Журнал проверок -------- */

    getJournal(params = {}) {
        const q = new URLSearchParams(params).toString();
        return authorizedFetch('/inspections' + (q ? `?${q}` : ''), { method: 'GET' });
    },

    createInspection(data) {
        return authorizedFetch('/inspections', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /* -------- Импорт CSV/текста -------- */

    importLocations(formData) {
        return authorizedFetch('/import/locations', {
            method: 'POST',
            body: formData
        });
    },

    importEmployees(formData) {
        return authorizedFetch('/import/employees', {
            method: 'POST',
            body: formData
        });
    },

    importExtinguishers(formData) {
        return authorizedFetch('/import/extinguishers', {
            method: 'POST',
            body: formData
        });
    },

    importInspections(formData) {
        return authorizedFetch('/import/inspections', {
            method: 'POST',
            body: formData
        });
    }
};
