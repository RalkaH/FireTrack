// extinguishers.js — Управление огнетушителями (карточки, сроки перезарядки и службы)

let currentExtinguishers = [];
let locations = [];
let statuses = [];
// Фильтр по статусу, который нужно применить при следующем открытии страницы
// (например, переход «Показать все просроченные» с дашборда)
let pendingStatusFilter = null;

async function loadExtinguishers() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка огнетушителей...</p>
        </div>
    `;

    try {
        [currentExtinguishers, locations, statuses] = await Promise.all([
            API.getExtinguishers(),
            API.getLocations(),
            API.getStatuses()
        ]);

        renderExtinguishersPage();
        applyPendingStatusFilter();
    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки данных: ${esc(error.message)}
            </div>
        `;
    }
}

function renderExtinguishersPage() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <!-- Page Header -->
        <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
            <h2><i class="bi bi-droplet"></i> Огнетушители</h2>
            <button class="btn btn-primary requires-edit" onclick="showAddExtinguisherModal()">
                <i class="bi bi-plus-circle"></i> Добавить огнетушитель
            </button>
        </div>

        <!-- Filters -->
        <div class="filter-section">
            <div class="row g-3 align-items-end">
                <div class="col-md-4">
                    <label class="form-label">Поиск</label>
                    <div class="input-group">
                        <span class="input-group-text"><i class="bi bi-search"></i></span>
                        <input type="text" class="form-control" id="searchInput"
                               placeholder="По инвентарному номеру...">
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Место</label>
                    <select class="form-select" id="locationFilter">
                        <option value="">Все места</option>
                        ${locations.map(loc => `
                            <option value="${loc.id}">${esc(loc.name)}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Статус</label>
                    <select class="form-select" id="statusFilter">
                        <option value="">Все статусы</option>
                        ${statuses.map(st => `
                            <option value="${st.id}">${esc(st.name)}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-2">
                    <button class="btn btn-secondary w-100" onclick="resetFilters()">
                        <i class="bi bi-x-circle"></i> Сбросить
                    </button>
                </div>
            </div>
        </div>

        <!-- Stats bar -->
        <div class="d-flex gap-3 mb-3 flex-wrap">
            <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6;">
                <i class="bi bi-droplet me-1"></i> Всего: ${currentExtinguishers.length}
            </span>
            ${statuses.map(st => {
        const count = currentExtinguishers.filter(e => e.status_id === st.id).length;
        return count > 0 ? `<span class="badge ${getStatusClass(st.name)}">${esc(st.name)}: ${count}</span>` : '';
    }).join('')}
        </div>

        <!-- Table -->
        <div class="card">
            <div id="extinguishersTable">
                ${renderExtinguishersTable(currentExtinguishers)}
            </div>
        </div>
    `;

    // Event listeners
    document.getElementById('searchInput').addEventListener('input', filterExtinguishers);
    document.getElementById('locationFilter').addEventListener('change', filterExtinguishers);
    document.getElementById('statusFilter').addEventListener('change', filterExtinguishers);
}

function renderExtinguishersTable(extinguishers) {
    if (extinguishers.length === 0) {
        return `
            <div class="empty-state">
                <i class="bi bi-droplet"></i>
                <p>Огнетушители не найдены</p>
                <button class="btn btn-primary requires-edit" onclick="showAddExtinguisherModal()">
                    <i class="bi bi-plus-circle"></i> Добавить первый огнетушитель
                </button>
            </div>
        `;
    }

    return `
        <div class="table-responsive">
            <table class="table table-hover mb-0">
                <thead>
                    <tr>
                        <th>Инв. номер</th>
                        <th>Тип</th>
                        <th>Вместимость</th>
                        <th>Место</th>
                        <th>Статус</th>
                        <th>Дата изг.</th>
                        <th>Перезарядка</th>
                        <th style="width: 170px;">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${extinguishers.map((ext, idx) => {
        const location = locations.find(l => l.id === ext.location_id);
        const status = statuses.find(s => s.id === ext.status_id);

        return `
                            <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.03, 0.5)}s both;">
                                <td><strong>${esc(ext.inventory_number)}</strong></td>
                                <td>${esc(ext.type)}</td>
                                <td>${esc(ext.capacity)} л/кг</td>
                                <td>
                                    <span class="d-flex align-items-center gap-1">
                                        <i class="bi bi-geo-alt text-muted" style="font-size: 0.8rem;"></i>
                                        ${location ? esc(location.name) : '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge ${getStatusClass(status?.name)}">
                                        ${status ? esc(status.name) : '-'}
                                    </span>
                                </td>
                                <td>${formatDate(ext.manufacture_date) || '-'}</td>
                                <td>${renderDeadlineBadge(ext.next_recharge_date, ext.recharge_days_left, ext.recharge_state)}</td>
                                <td>
                                    <div class="table-actions">
                                        <button class="btn btn-sm btn-info"
                                                onclick="viewExtinguisherHistory(${ext.id})"
                                                title="История проверок">
                                            <i class="bi bi-clock-history"></i>
                                        </button>
                                        <button class="btn btn-sm btn-warning requires-edit"
                                                onclick="showRechargeModal(${ext.id})"
                                                title="Отметить перезарядку">
                                            <i class="bi bi-arrow-repeat"></i>
                                        </button>
                                        <button class="btn btn-sm btn-primary requires-edit"
                                                onclick="showEditExtinguisherModal(${ext.id})"
                                                title="Редактировать">
                                            <i class="bi bi-pencil"></i>
                                        </button>
                                        <button class="btn btn-sm btn-danger requires-admin"
                                                onclick="deleteExtinguisher(${ext.id})"
                                                title="Удалить">
                                            <i class="bi bi-trash"></i>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `;
    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

async function filterExtinguishers() {
    const searchValue = document.getElementById('searchInput').value.toLowerCase();
    const locationId = document.getElementById('locationFilter').value;
    const statusId = document.getElementById('statusFilter').value;

    let filtered = currentExtinguishers;

    if (searchValue) {
        filtered = filtered.filter(ext =>
            ext.inventory_number.toLowerCase().includes(searchValue)
        );
    }

    if (locationId) {
        filtered = filtered.filter(ext => ext.location_id == locationId);
    }

    if (statusId) {
        filtered = filtered.filter(ext => ext.status_id == statusId);
    }

    document.getElementById('extinguishersTable').innerHTML = renderExtinguishersTable(filtered);
}

function applyPendingStatusFilter() {
    if (!pendingStatusFilter) return;
    const status = statuses.find(s => s.name === pendingStatusFilter);
    pendingStatusFilter = null;
    if (!status) return;
    document.getElementById('statusFilter').value = String(status.id);
    filterExtinguishers();
}

// Собирает данные формы огнетушителя в объект для API.
// forUpdate=true: пустые необязательные поля отправляются как null (очищают значение)
function collectExtinguisherForm(form, forUpdate) {
    const data = Object.fromEntries(new FormData(form));

    data.inventory_number = data.inventory_number.trim();
    data.type = data.type.trim();
    data.capacity = parseFloat(data.capacity);
    data.location_id = parseInt(data.location_id);
    data.status_id = parseInt(data.status_id);

    ['manufacturer', 'manufacture_date', 'commissioning_date', 'last_recharge_date',
     'recharge_interval_months', 'service_life_years'].forEach(key => {
        const value = (data[key] || '').trim();
        if (value) {
            data[key] = key.endsWith('_months') || key.endsWith('_years') ? parseInt(value, 10) : value;
        } else if (forUpdate) {
            data[key] = null;
        } else {
            delete data[key];
        }
    });
    return data;
}

function resetFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('locationFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('extinguishersTable').innerHTML = renderExtinguishersTable(currentExtinguishers);
}

// onSuccess — что сделать после сохранения (по умолчанию обновить список огнетушителей)
function showAddExtinguisherModal(onSuccess = loadExtinguishers) {
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Добавить огнетушитель';
    document.getElementById('modalBody').innerHTML = renderExtinguisherForm();

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = collectExtinguisherForm(e.target, false);

        try {
            await API.createExtinguisher(data);
            showAlert('Огнетушитель успешно добавлен', 'success');
            modal.hide();
            onSuccess();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

async function showEditExtinguisherModal(id) {
    let extinguisher;
    try {
        extinguisher = await API.getExtinguisher(id);
    } catch (error) {
        showAlert('Не удалось загрузить огнетушитель: ' + error.message, 'danger');
        return;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Редактировать огнетушитель';
    document.getElementById('modalBody').innerHTML = renderExtinguisherForm(extinguisher);

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = collectExtinguisherForm(e.target, true);

        try {
            await API.updateExtinguisher(id, data);
            showAlert('Огнетушитель успешно обновлен', 'success');
            modal.hide();
            loadExtinguishers();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function renderExtinguisherForm(data = null) {
    const isEdit = data !== null;
    const today = todayISO();

    return `
        <form id="extinguisherForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Инвентарный номер *</label>
                    <input type="text" class="form-control" name="inventory_number"
                           value="${isEdit ? esc(data.inventory_number) : ''}" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Тип *</label>
                    <input type="text" class="form-control" name="type"
                           placeholder="ОУ-8, ОП-5 и т.д."
                           value="${isEdit ? esc(data.type) : ''}" required>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Вместимость (л/кг) *</label>
                    <input type="number" class="form-control" name="capacity"
                           value="${isEdit ? esc(data.capacity) : ''}"
                           step="0.1" min="0.1" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Производитель</label>
                    <input type="text" class="form-control" name="manufacturer"
                           value="${isEdit ? esc(data.manufacturer) : ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата изготовления</label>
                    <input type="date" class="form-control" name="manufacture_date" max="${today}"
                           value="${isEdit ? esc(data.manufacture_date) : ''}">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата ввода в эксплуатацию</label>
                    <input type="date" class="form-control" name="commissioning_date" max="${today}"
                           value="${isEdit ? esc(data.commissioning_date) : ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Место расположения *</label>
                    <select class="form-select" name="location_id" required>
                        <option value="">Выберите место</option>
                        ${locations.map(loc => `
                            <option value="${loc.id}" ${isEdit && loc.id === data.location_id ? 'selected' : ''}>
                                ${esc(loc.name)}
                            </option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Статус *</label>
                    <select class="form-select" name="status_id" required>
                        ${statuses.map(st => `
                            <option value="${st.id}" ${isEdit && st.id === data.status_id ? 'selected' : ''}>
                                ${esc(st.name)}
                            </option>
                        `).join('')}
                    </select>
                </div>
            </div>
            <div class="form-section-title"><i class="bi bi-arrow-repeat"></i> Перезарядка и срок службы</div>
            <div class="row">
                <div class="col-md-4 mb-3">
                    <label class="form-label">Последняя перезарядка</label>
                    <input type="date" class="form-control" name="last_recharge_date" max="${today}"
                           value="${isEdit ? esc(data.last_recharge_date) : ''}">
                    <small class="text-muted">Если пусто, отсчёт от даты изготовления</small>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Интервал перезарядки, мес.</label>
                    <input type="number" class="form-control" name="recharge_interval_months" min="1" max="240" step="1"
                           placeholder="${isEdit && data.effective_recharge_interval_months && !data.recharge_interval_months ? esc(data.effective_recharge_interval_months) + ' (по виду ОТВ)' : 'по виду ОТВ'}"
                           value="${isEdit && data.recharge_interval_months ? esc(data.recharge_interval_months) : ''}">
                    <small class="text-muted">Только если в паспорте указан другой срок</small>
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">Срок службы, лет</label>
                    <input type="number" class="form-control" name="service_life_years" min="1" max="50" step="1"
                           placeholder="${isEdit && data.effective_service_life_years && !data.service_life_years ? esc(data.effective_service_life_years) + ' (по умолчанию)' : 'по умолчанию'}"
                           value="${isEdit && data.service_life_years ? esc(data.service_life_years) : ''}">
                    <small class="text-muted">По паспорту огнетушителя</small>
                </div>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-save"></i> ${isEdit ? 'Сохранить изменения' : 'Сохранить'}
                </button>
            </div>
        </form>
    `;
}

async function deleteExtinguisher(id) {
    const ext = currentExtinguishers.find(e => e.id === id);
    const inventoryNumber = ext ? ext.inventory_number : `#${id}`;
    if (confirm(`Удалить огнетушитель ${inventoryNumber}?\n\nВсе связанные проверки также будут удалены.`)) {
        try {
            await API.deleteExtinguisher(id);
            showAlert('Огнетушитель успешно удален', 'success');
            loadExtinguishers();
        } catch (error) {
            showAlert('Ошибка удаления: ' + error.message, 'danger');
        }
    }
}

async function viewExtinguisherHistory(id) {
    let extinguisher, inspections;
    try {
        [extinguisher, inspections] = await Promise.all([
            API.getExtinguisher(id),
            API.getInspectionsByExtinguisher(id)
        ]);
    } catch (error) {
        showAlert('Не удалось загрузить историю: ' + error.message, 'danger');
        return;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = `История проверок: ${extinguisher.inventory_number}`;

    const location = locations.find(l => l.id === extinguisher.location_id);
    const status = statuses.find(s => s.id === extinguisher.status_id);

    document.getElementById('modalBody').innerHTML = `
        <div class="d-flex align-items-center gap-2 mb-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
            <span class="badge ${getStatusClass(status?.name)}">${status ? esc(status.name) : '-'}</span>
            <span class="text-muted">|</span>
            <span><strong>${esc(extinguisher.type)}</strong></span>
            <span class="text-muted">|</span>
            <span class="d-flex align-items-center gap-1">
                <i class="bi bi-geo-alt text-muted"></i> ${location ? esc(location.name) : '-'}
            </span>
        </div>

        <div class="row g-2 mb-3">
            <div class="col-md-6">
                <div class="deadline-box">
                    <div class="deadline-title"><i class="bi bi-arrow-repeat"></i> Перезарядка</div>
                    <div>${renderDeadlineBadge(extinguisher.next_recharge_date, extinguisher.recharge_days_left, extinguisher.recharge_state)}</div>
                    <small class="text-muted">
                        ${extinguisher.agent_label ? `ОТВ: ${esc(extinguisher.agent_label)}. ` : ''}
                        ${extinguisher.effective_recharge_interval_months ? `Интервал ${extinguisher.effective_recharge_interval_months} мес.` : 'Интервал не определён, укажите его в карточке.'}
                        ${extinguisher.last_recharge_date ? ` Последняя: ${formatDate(extinguisher.last_recharge_date)}.` : ''}
                    </small>
                </div>
            </div>
            <div class="col-md-6">
                <div class="deadline-box">
                    <div class="deadline-title"><i class="bi bi-hourglass-split"></i> Срок службы</div>
                    <div>${renderDeadlineBadge(extinguisher.service_end_date, null, extinguisher.service_state)}</div>
                    <small class="text-muted">
                        ${extinguisher.effective_service_life_years ? `${extinguisher.effective_service_life_years} лет от даты изготовления.` : ''}
                    </small>
                </div>
            </div>
        </div>

        ${inspections.length > 0 ? `
            <div class="table-responsive">
                <table class="table table-sm table-hover mb-0">
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>Давление</th>
                            <th>Вес</th>
                            <th>Осмотр</th>
                            <th>След. проверка</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${inspections.map(insp => `
                            <tr>
                                <td><strong>${formatDate(insp.inspection_date)}</strong></td>
                                <td>${insp.pressure ?? '-'}</td>
                                <td>${insp.weight ?? '-'}</td>
                                <td>
                                    <span class="badge badge-sm ${insp.visual_inspection === 'Исправен' ? 'status-actual' : insp.visual_inspection === 'Неисправен' ? 'status-expired' : 'status-maintenance'}">
                                        ${esc(insp.visual_inspection) || '-'}
                                    </span>
                                </td>
                                <td>${formatDate(insp.next_inspection_date)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        ` : `
            <div class="empty-state" style="padding: 40px;">
                <i class="bi bi-clipboard-x"></i>
                <p>Проверок еще не было</p>
            </div>
        `}
        <div class="text-end mt-3">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
        </div>
    `;

    modal.show();
}

// Бейдж срока: дата и сколько осталось, цвет по состоянию (ok, soon, overdue, unknown)
function renderDeadlineBadge(dateIso, daysLeft, state) {
    if (!dateIso || state === 'unknown') {
        return '<span class="badge badge-sm status-decommissioned" title="Не хватает даты изготовления или интервала">нет данных</span>';
    }
    const cls = { ok: 'status-actual', soon: 'status-maintenance', overdue: 'status-expired' }[state] || 'status-decommissioned';
    let suffix = '';
    if (daysLeft !== null && daysLeft !== undefined) {
        if (daysLeft < 0) suffix = ` · просрочено ${-daysLeft} ${plural(-daysLeft, 'день', 'дня', 'дней')}`;
        else if (state === 'soon') suffix = ` · через ${daysLeft} ${plural(daysLeft, 'день', 'дня', 'дней')}`;
    } else if (state === 'overdue') {
        suffix = ' · истёк';
    }
    return `<span class="badge badge-sm ${cls}">${formatDate(dateIso)}${suffix}</span>`;
}

// Отметка о перезарядке. onSuccess — что обновить после сохранения
async function showRechargeModal(id, onSuccess = loadExtinguishers) {
    let ext;
    try {
        ext = await API.getExtinguisher(id);
    } catch (error) {
        showAlert('Не удалось загрузить огнетушитель: ' + error.message, 'danger');
        return;
    }
    const today = todayISO();
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = `Перезарядка: ${ext.inventory_number}`;
    document.getElementById('modalBody').innerHTML = `
        <form id="rechargeForm">
            <p class="text-muted">
                ${esc(ext.type)}${ext.agent_label ? `, ${esc(ext.agent_label.toLowerCase())}` : ''}.
                Текущий срок перезарядки: ${renderDeadlineBadge(ext.next_recharge_date, ext.recharge_days_left, ext.recharge_state)}
            </p>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата перезарядки *</label>
                    <input type="date" class="form-control" name="recharge_date" value="${today}" max="${today}" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Интервал по паспорту, мес.</label>
                    <input type="number" class="form-control" name="recharge_interval_months" min="1" max="240"
                           placeholder="${ext.effective_recharge_interval_months ? esc(ext.effective_recharge_interval_months) + ' (без изменений)' : ''}">
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">Комментарий</label>
                <input type="text" class="form-control" name="comment" maxlength="200" placeholder="Организация, номер акта">
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-warning"><i class="bi bi-arrow-repeat"></i> Отметить перезарядку</button>
            </div>
        </form>
    `;
    document.getElementById('rechargeForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const form = Object.fromEntries(new FormData(e.target));
        const data = { recharge_date: form.recharge_date };
        if (form.recharge_interval_months) data.recharge_interval_months = parseInt(form.recharge_interval_months, 10);
        if (form.comment.trim()) data.comment = form.comment.trim();
        try {
            const updated = await API.markRecharged(id, data);
            showAlert(`Перезарядка отмечена. Следующая: ${formatDate(updated.next_recharge_date) || 'не определена'}`, 'success');
            modal.hide();
            onSuccess();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });
    modal.show();
}

function getStatusClass(statusName) {
    const classMap = {
        'Актуально': 'status-actual',
        'Просрочено': 'status-expired',
        'Требует обслуживания': 'status-maintenance',
        'На техническом обслуживании': 'status-service',
        'Списан': 'status-decommissioned'
    };
    return classMap[statusName] || 'status-decommissioned';
}
