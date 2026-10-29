// inspections.js — Управление проверками

let allInspections = [];
let allExtinguishers = [];
let allEmployees = [];

async function loadInspections() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка журнала проверок...</p>
        </div>
    `;

    try {
        [allInspections, allExtinguishers, allEmployees, locations, statuses] = await Promise.all([
            API.getJournal(),
            API.getExtinguishers(),
            API.getEmployees(),
            API.getLocations(),
            API.getStatuses()
        ]);

        renderInspectionsPage();
    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки данных: ${esc(error.message)}
            </div>
        `;
    }
}

function renderInspectionsPage() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <!-- Page Header -->
        <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
            <h2><i class="bi bi-clipboard-check"></i> Журнал проверок</h2>
            <button class="btn btn-success requires-edit" onclick="showAddInspectionModal()">
                <i class="bi bi-plus-circle"></i> Новая проверка
            </button>
        </div>

        <!-- Filters -->
        <div class="filter-section">
            <div class="row g-3 align-items-end">
                <div class="col-md-3">
                    <label class="form-label">Дата от</label>
                    <input type="date" class="form-control" id="dateFrom">
                </div>
                <div class="col-md-3">
                    <label class="form-label">Дата до</label>
                    <input type="date" class="form-control" id="dateTo">
                </div>
                <div class="col-md-3">
                    <label class="form-label">&nbsp;</label>
                    <button class="btn btn-info w-100" onclick="filterInspections()">
                        <i class="bi bi-funnel"></i> Применить фильтр
                    </button>
                </div>
                <div class="col-md-3">
                    <label class="form-label">&nbsp;</label>
                    <button class="btn btn-secondary w-100" onclick="resetInspectionFilters()">
                        <i class="bi bi-x-circle"></i> Сбросить
                    </button>
                </div>
            </div>
        </div>

        <!-- Stats -->
        <div class="d-flex gap-3 mb-3 flex-wrap">
            <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6;">
                <i class="bi bi-clipboard-check me-1"></i> Всего: ${allInspections.length}
            </span>
            <span class="badge" style="background: rgba(16,185,129,0.1); color: #10B981;">
                <i class="bi bi-check-circle me-1"></i> Исправен: ${allInspections.filter(i => i.visual_inspection === 'Исправен').length}
            </span>
            <span class="badge" style="background: rgba(245,158,11,0.1); color: #D97706;">
                <i class="bi bi-exclamation-circle me-1"></i> Требует внимания: ${allInspections.filter(i => i.visual_inspection === 'Требует внимания').length}
            </span>
            <span class="badge" style="background: rgba(239,68,68,0.1); color: #EF4444;">
                <i class="bi bi-x-circle me-1"></i> Неисправен: ${allInspections.filter(i => i.visual_inspection === 'Неисправен').length}
            </span>
        </div>

        <!-- Table -->
        <div class="card">
            <div id="inspectionsTable">
                ${renderInspectionsTable(allInspections)}
            </div>
        </div>
    `;
}

function renderInspectionsTable(inspections) {
    if (inspections.length === 0) {
        return `
            <div class="empty-state">
                <i class="bi bi-clipboard-x"></i>
                <p>Проверки не найдены</p>
                <button class="btn btn-success requires-edit" onclick="showAddInspectionModal()">
                    <i class="bi bi-plus-circle"></i> Провести первую проверку
                </button>
            </div>
        `;
    }

    return `
        <div class="table-responsive">
            <table class="table table-hover table-sm mb-0">
                <thead>
                    <tr>
                        <th>Дата</th>
                        <th>Огнетушитель</th>
                        <th>Место</th>
                        <th>Проверяющий</th>
                        <th>Давл.</th>
                        <th>Вес</th>
                        <th>Осмотр</th>
                        <th>Пломба</th>
                        <th>Чека</th>
                        <th>Шланг</th>
                        <th>След. проверка</th>
                        <th>Комментарий</th>
                    </tr>
                </thead>
                <tbody>
                    ${inspections.map((insp, idx) => {
        const extinguisher = allExtinguishers.find(e => e.id === insp.fire_extinguisher_id);
        const employee = allEmployees.find(e => e.id === insp.employee_id);
        const location = extinguisher ? locations.find(l => l.id === extinguisher.location_id) : null;

        return `
                            <tr style="animation: fadeInUp 0.2s ease-out ${Math.min(idx * 0.02, 0.5)}s both;">
                                <td><strong>${formatDate(insp.inspection_date)}</strong></td>
                                <td>
                                    ${extinguisher ? `
                                        <div><strong>${esc(extinguisher.inventory_number)}</strong></div>
                                        <small class="text-muted">${esc(extinguisher.type)}</small>
                                    ` : '-'}
                                </td>
                                <td>
                                    <span class="d-flex align-items-center gap-1">
                                        <i class="bi bi-geo-alt text-muted" style="font-size: 0.75rem;"></i>
                                        ${location ? esc(location.name) : '-'}
                                    </span>
                                </td>
                                <td>
                                    ${employee ? `
                                        <div class="d-flex align-items-center gap-2">
                                            <div style="width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(135deg, #10B981, #059669); display: flex; align-items: center; justify-content: center; color: white; font-size: 0.65rem; font-weight: 600;">
                                                ${esc(getInitials(employee.full_name))}
                                            </div>
                                            <div>
                                                <div style="font-size: 0.85rem;">${esc(employee.full_name)}</div>
                                                <small class="text-muted">${esc(employee.position)}</small>
                                            </div>
                                        </div>
                                    ` : '-'}
                                </td>
                                <td>${insp.pressure ?? '-'}</td>
                                <td>${insp.weight ?? '-'}</td>
                                <td>
                                    <span class="badge badge-sm ${getInspectionBadgeClass(insp.visual_inspection)}">
                                        ${esc(insp.visual_inspection) || '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge badge-sm ${getConditionBadgeClass(insp.seal_condition)}">
                                        ${esc(insp.seal_condition) || '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge badge-sm ${getConditionBadgeClass(insp.safety_pin_condition)}">
                                        ${esc(insp.safety_pin_condition) || '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge badge-sm ${getConditionBadgeClass(insp.hose_condition)}">
                                        ${esc(insp.hose_condition) || '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge badge-sm ${isOverdue(insp.next_inspection_date) ? 'status-expired' : 'status-service'}">
                                        ${formatDate(insp.next_inspection_date)}
                                    </span>
                                </td>
                                <td>
                                    ${insp.comments ? `
                                        <small class="text-muted" title="${esc(insp.comments)}">${esc(insp.comments.length > 30 ? insp.comments.substring(0, 30) + '...' : insp.comments)}</small>
                                    ` : '<span class="text-muted">-</span>'}
                                </td>
                            </tr>
                        `;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function getInspectionBadgeClass(value) {
    switch (value) {
        case 'Исправен': return 'status-actual';
        case 'Требует внимания': return 'status-maintenance';
        case 'Неисправен': return 'status-expired';
        default: return 'status-decommissioned';
    }
}

function getConditionBadgeClass(value) {
    switch (value) {
        case 'Цела':
        case 'Исправен':
        case 'Исправна': return 'status-actual';
        case 'Повреждена':
        case 'Поврежден': return 'status-maintenance';
        case 'Отсутствует': return 'status-expired';
        default: return 'status-decommissioned';
    }
}

// Просрочена ли дата (сравнение строк ГГГГ-ММ-ДД, без сдвига часового пояса)
function isOverdue(dateString) {
    if (!dateString) return false;
    return dateString < todayISO();
}

// Инициалы для аватарки сотрудника
function getInitials(fullName) {
    return (fullName || '')
        .split(/\s+/)
        .filter(Boolean)
        .map(part => part[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
}

async function filterInspections() {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;

    const filters = {};
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;

    try {
        allInspections = await API.getJournal(filters);
        document.getElementById('inspectionsTable').innerHTML = renderInspectionsTable(allInspections);
    } catch (error) {
        showAlert('Ошибка фильтрации: ' + error.message, 'danger');
    }
}

async function resetInspectionFilters() {
    document.getElementById('dateFrom').value = '';
    document.getElementById('dateTo').value = '';
    try {
        allInspections = await API.getJournal();
        document.getElementById('inspectionsTable').innerHTML = renderInspectionsTable(allInspections);
    } catch (error) {
        showAlert('Ошибка загрузки журнала: ' + error.message, 'danger');
    }
}

// onSuccess — что сделать после сохранения (по умолчанию обновить журнал)
function showAddInspectionModal(onSuccess = loadInspections) {
    if (allExtinguishers.length === 0) {
        showAlert('Сначала добавьте огнетушители', 'warning');
        return;
    }

    if (allEmployees.length === 0) {
        showAlert('Сначала добавьте сотрудников', 'warning');
        return;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Провести проверку';

    // Списанные огнетушители в списке не показываем
    const decommissioned = statuses.find(st => st.name === 'Списан');
    const activeExtinguishers = allExtinguishers.filter(ext => !decommissioned || ext.status_id !== decommissioned.id);

    const today = todayISO();
    const nextInspectionDate = addMonthsISO(today, 6);

    document.getElementById('modalBody').innerHTML = `
        <form id="inspectionForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Огнетушитель *</label>
                    <select class="form-select" name="fire_extinguisher_id" required>
                        <option value="">Выберите огнетушитель</option>
                        ${activeExtinguishers.map(ext => {
        const loc = locations.find(l => l.id === ext.location_id);
        return `
                                <option value="${ext.id}">
                                    ${esc(ext.inventory_number)} — ${esc(ext.type)} (${loc ? esc(loc.name) : '-'})
                                </option>
                            `;
    }).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата проверки *</label>
                    <input type="date" class="form-control" name="inspection_date" id="inspectionDateInput"
                           value="${today}" required max="${today}">
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label">Проверяющий *</label>
                <select class="form-select" name="employee_id" required>
                    <option value="">Выберите сотрудника</option>
                    ${allEmployees.map(emp => `
                        <option value="${emp.id}">
                            ${esc(emp.full_name)} — ${esc(emp.position)}
                        </option>
                    `).join('')}
                </select>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Давление (МПа)</label>
                    <input type="number" class="form-control" name="pressure"
                           step="0.1" min="0" placeholder="1.5">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Вес (кг)</label>
                    <input type="number" class="form-control" name="weight"
                           step="0.1" min="0" placeholder="7.8">
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Визуальный осмотр</label>
                    <select class="form-select" name="visual_inspection">
                        <option value="Исправен" selected>Исправен</option>
                        <option value="Требует внимания">Требует внимания</option>
                        <option value="Неисправен">Неисправен</option>
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние пломбы</label>
                    <select class="form-select" name="seal_condition">
                        <option value="Цела" selected>Цела</option>
                        <option value="Повреждена">Повреждена</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние чеки</label>
                    <select class="form-select" name="safety_pin_condition">
                        <option value="Исправна" selected>Исправна</option>
                        <option value="Повреждена">Повреждена</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние шланга</label>
                    <select class="form-select" name="hose_condition">
                        <option value="Исправен" selected>Исправен</option>
                        <option value="Поврежден">Поврежден</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label">Дата следующей проверки</label>
                <input type="date" class="form-control" name="next_inspection_date" id="nextInspectionInput"
                       value="${nextInspectionDate}" min="${today}">
                <small class="text-muted">По умолчанию через 6 месяцев после проверки. Если оставить пустым, сервер рассчитает сам.</small>
            </div>

            <div class="mb-3">
                <label class="form-label">Комментарии</label>
                <textarea class="form-control" name="comments" rows="3"
                          placeholder="Дополнительные замечания..."></textarea>
            </div>

            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-success">
                    <i class="bi bi-check-circle"></i> Провести проверку
                </button>
            </div>
        </form>
    `;

    // При смене даты проверки сдвигаем дату следующей, если её не меняли вручную
    const inspectionInput = document.getElementById('inspectionDateInput');
    const nextInput = document.getElementById('nextInspectionInput');
    let nextEditedManually = false;
    nextInput.addEventListener('input', () => { nextEditedManually = true; });
    inspectionInput.addEventListener('change', () => {
        if (!inspectionInput.value) return;
        nextInput.min = inspectionInput.value;
        if (!nextEditedManually) nextInput.value = addMonthsISO(inspectionInput.value, 6);
    });

    document.getElementById('inspectionForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        data.fire_extinguisher_id = parseInt(data.fire_extinguisher_id);
        data.employee_id = parseInt(data.employee_id);

        if (data.pressure) data.pressure = parseFloat(data.pressure);
        if (data.weight) data.weight = parseFloat(data.weight);

        Object.keys(data).forEach(key => {
            if (data[key] === '' || data[key] === null) delete data[key];
        });

        try {
            await API.createInspection(data);
            showAlert('Проверка успешно зарегистрирована', 'success');
            modal.hide();
            onSuccess();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}
