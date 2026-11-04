// audit.js — страница «Журнал действий» (только для администратора)

let auditMeta = null;
let auditState = { page: 1, page_size: 50 };
let auditItems = [];

const AUDIT_ACTION_CLASS = {
    create: 'status-actual',
    update: 'status-service',
    delete: 'status-expired',
    import: 'status-service',
    login_success: 'status-actual',
    login_failed: 'status-expired',
    password_change: 'status-maintenance',
    password_reset: 'status-maintenance',
    block: 'status-expired',
    unblock: 'status-actual',
    recalculate: 'status-decommissioned',
    export: 'status-decommissioned'
};

// Подписи полей для блока «было и стало»
const AUDIT_FIELD_LABELS = {
    inventory_number: 'Инв. номер', type: 'Тип', capacity: 'Вместимость', manufacturer: 'Производитель',
    manufacture_date: 'Дата изготовления', commissioning_date: 'Ввод в эксплуатацию',
    location_id: 'Место (ID)', status_id: 'Статус (ID)', last_recharge_date: 'Последняя перезарядка',
    recharge_interval_months: 'Интервал перезарядки, мес.', service_life_years: 'Срок службы, лет',
    username: 'Логин', full_name: 'ФИО', email: 'Email', role: 'Роль', is_active: 'Активен',
    must_change_password: 'Сменить пароль', name: 'Название', description: 'Описание', position: 'Должность',
    fire_extinguisher_id: 'Огнетушитель (ID)', inspection_date: 'Дата проверки', employee_id: 'Сотрудник (ID)',
    pressure: 'Давление', weight: 'Масса', visual_inspection: 'Осмотр', seal_condition: 'Пломба',
    safety_pin_condition: 'Чека', hose_condition: 'Шланг', comments: 'Комментарии',
    next_inspection_date: 'Следующая проверка', created: 'Создано', errors: 'Ошибок', first_errors: 'Первые ошибки'
};

async function loadAuditPage() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка журнала действий...</p>
        </div>
    `;
    try {
        auditMeta = await API.getAuditMeta();
    } catch (error) {
        content.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${esc(error.message)}</div>`;
        return;
    }
    auditState = { page: 1, page_size: 50 };

    const options = (items, empty) => `<option value="">${empty}</option>` +
        items.map(i => `<option value="${esc(i.key)}">${esc(i.label)}</option>`).join('');

    content.innerHTML = `
        <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
            <h2><i class="bi bi-journal-text"></i> Журнал действий</h2>
            <button class="btn btn-info" onclick="exportAuditCsv()">
                <i class="bi bi-filetype-csv"></i> Выгрузить CSV
            </button>
        </div>

        <form class="filter-section" id="auditFilters">
            <div class="row g-3 align-items-end">
                <div class="col-md-2">
                    <label class="form-label">С даты</label>
                    <input type="date" class="form-control" name="date_from">
                </div>
                <div class="col-md-2">
                    <label class="form-label">По дату</label>
                    <input type="date" class="form-control" name="date_to">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Пользователь</label>
                    <select class="form-select" name="username">
                        <option value="">Все</option>
                        ${auditMeta.usernames.map(u => `<option value="${esc(u)}">${esc(u)}</option>`).join('')}
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Действие</label>
                    <select class="form-select" name="action">${options(auditMeta.actions, 'Все')}</select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Объект</label>
                    <select class="form-select" name="entity_type">${options(auditMeta.entity_types, 'Все')}</select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Поиск</label>
                    <input type="search" class="form-control" name="q" placeholder="Текст или IP">
                </div>
            </div>
            <div class="d-flex gap-2 mt-3">
                <button type="submit" class="btn btn-info"><i class="bi bi-funnel"></i> Применить</button>
                <button type="button" class="btn btn-secondary" onclick="resetAuditFilters()"><i class="bi bi-x-circle"></i> Сбросить</button>
                <button type="button" class="btn btn-outline-danger ms-auto" onclick="quickAuditFilter('login_failed')">
                    <i class="bi bi-shield-exclamation"></i> Неудачные входы
                </button>
            </div>
            <small class="text-muted d-block mt-2">Даты фильтра в UTC, время в таблице показано по вашему часовому поясу.</small>
        </form>

        <div class="card">
            <div id="auditTable"></div>
        </div>
        <div id="auditPager" class="d-flex justify-content-between align-items-center mt-3 flex-wrap gap-2"></div>
    `;

    document.getElementById('auditFilters').addEventListener('submit', (e) => {
        e.preventDefault();
        auditState.page = 1;
        fetchAudit();
    });
    fetchAudit();
}

function auditFilters() {
    const form = document.getElementById('auditFilters');
    return form ? Object.fromEntries(new FormData(form)) : {};
}

function resetAuditFilters() {
    document.getElementById('auditFilters').reset();
    auditState.page = 1;
    fetchAudit();
}

function quickAuditFilter(action) {
    const form = document.getElementById('auditFilters');
    form.reset();
    form.elements.action.value = action;
    auditState.page = 1;
    fetchAudit();
}

async function fetchAudit() {
    const table = document.getElementById('auditTable');
    table.innerHTML = '<div class="loading" style="padding: 30px;"><i class="bi bi-arrow-clockwise"></i></div>';
    try {
        const data = await API.getAudit({ ...auditFilters(), page: auditState.page, page_size: auditState.page_size });
        auditItems = data.items;
        table.innerHTML = renderAuditTable(data.items);
        renderAuditPager(data);
    } catch (error) {
        table.innerHTML = `<div class="alert alert-danger m-3">${esc(error.message)}</div>`;
    }
}

function actionLabel(key) {
    const item = auditMeta && auditMeta.actions.find(a => a.key === key);
    return item ? item.label : key;
}

function entityLabel(key) {
    const item = auditMeta && auditMeta.entity_types.find(a => a.key === key);
    return item ? item.label : (key || '');
}

function formatAuditValue(value) {
    if (value === null || value === undefined || value === '') return '<span class="text-muted">пусто</span>';
    if (typeof value === 'boolean') return value ? 'да' : 'нет';
    if (Array.isArray(value)) return value.map(v => esc(v)).join('<br>');
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
    return esc(value);
}

function renderAuditChanges(changes) {
    if (!changes) return '';
    const rows = Object.entries(changes).map(([field, diff]) => {
        const isDiff = diff && typeof diff === 'object' && !Array.isArray(diff) && ('old' in diff || 'new' in diff);
        const label = esc(AUDIT_FIELD_LABELS[field] || field);
        if (!isDiff) return `<tr><td>${label}</td><td colspan="2">${formatAuditValue(diff)}</td></tr>`;
        return `<tr><td>${label}</td><td class="audit-old">${formatAuditValue(diff.old)}</td><td class="audit-new">${formatAuditValue(diff.new)}</td></tr>`;
    }).join('');
    return `
        <table class="table table-sm audit-diff mb-0">
            <thead><tr><th>Поле</th><th>Было</th><th>Стало</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function renderAuditTable(items) {
    if (items.length === 0) {
        return `<div class="empty-state"><i class="bi bi-journal-x"></i><p>Записей не найдено</p></div>`;
    }
    return `
        <div class="table-responsive">
            <table class="table table-hover table-sm mb-0 audit-table">
                <thead>
                    <tr>
                        <th style="width: 160px;">Время</th>
                        <th>Пользователь</th>
                        <th>Действие</th>
                        <th>Объект</th>
                        <th>Описание</th>
                        <th>IP</th>
                        <th style="width: 40px;"></th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map(e => `
                        <tr>
                            <td class="text-nowrap">${formatDateTime(e.created_at)}</td>
                            <td>${e.username ? `<strong>${esc(e.username)}</strong>` : '<span class="text-muted">-</span>'}</td>
                            <td><span class="badge badge-sm ${AUDIT_ACTION_CLASS[e.action] || 'status-decommissioned'}">${esc(actionLabel(e.action))}</span></td>
                            <td class="text-muted text-nowrap">${esc(entityLabel(e.entity_type))}${e.entity_id ? ` #${e.entity_id}` : ''}</td>
                            <td>${esc(e.summary)}</td>
                            <td class="text-muted text-nowrap" title="${esc(e.user_agent)}">${esc(e.ip)}</td>
                            <td>
                                ${e.changes ? `
                                    <button class="btn btn-sm btn-outline-primary" title="Подробности" onclick="toggleAuditDetails(${e.id}, this)">
                                        <i class="bi bi-chevron-down"></i>
                                    </button>` : ''}
                            </td>
                        </tr>
                        <tr class="audit-details d-none" id="audit-details-${e.id}">
                            <td colspan="7">
                                ${renderAuditChanges(e.changes)}
                                ${e.user_agent ? `<small class="text-muted d-block mt-2">User-Agent: ${esc(e.user_agent)}</small>` : ''}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>`;
}

function toggleAuditDetails(id, button) {
    const row = document.getElementById(`audit-details-${id}`);
    if (!row) return;
    const hidden = row.classList.toggle('d-none');
    button.innerHTML = `<i class="bi bi-chevron-${hidden ? 'down' : 'up'}"></i>`;
}

function renderAuditPager(data) {
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    document.getElementById('auditPager').innerHTML = `
        <span class="text-light small">Найдено записей: ${data.total}. Страница ${data.page} из ${pages}</span>
        <div class="d-flex gap-2">
            <button class="btn btn-sm btn-secondary" ${data.page <= 1 ? 'disabled' : ''} onclick="auditGoTo(${data.page - 1})">
                <i class="bi bi-chevron-left"></i> Назад
            </button>
            <button class="btn btn-sm btn-secondary" ${data.page >= pages ? 'disabled' : ''} onclick="auditGoTo(${data.page + 1})">
                Вперёд <i class="bi bi-chevron-right"></i>
            </button>
        </div>`;
}

function auditGoTo(page) {
    auditState.page = page;
    fetchAudit();
}

async function exportAuditCsv() {
    try {
        await API.downloadFile('/audit/export.csv', auditFilters(), 'audit.csv');
    } catch (error) {
        showAlert('Не удалось выгрузить журнал: ' + error.message, 'danger');
    }
}
