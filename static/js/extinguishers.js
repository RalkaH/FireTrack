// extinguishers.js — Управление огнетушителями

let currentExtinguishers = [];
let locations = [];
let statuses = [];

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
    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки данных: ${error.message}
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
            <button class="btn btn-primary" onclick="showAddExtinguisherModal()">
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
                            <option value="${loc.id}">${loc.name}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Статус</label>
                    <select class="form-select" id="statusFilter">
                        <option value="">Все статусы</option>
                        ${statuses.map(st => `
                            <option value="${st.id}">${st.name}</option>
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
        return count > 0 ? `<span class="badge ${getStatusClass(st.name)}">${st.name}: ${count}</span>` : '';
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
                <button class="btn btn-primary" onclick="showAddExtinguisherModal()">
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
                        <th>Производитель</th>
                        <th>Дата изг.</th>
                        <th style="width: 130px;">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${extinguishers.map((ext, idx) => {
        const location = locations.find(l => l.id === ext.location_id);
        const status = statuses.find(s => s.id === ext.status_id);

        return `
                            <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.03, 0.5)}s both;">
                                <td><strong>${ext.inventory_number}</strong></td>
                                <td>${ext.type}</td>
                                <td>${ext.capacity} л/кг</td>
                                <td>
                                    <span class="d-flex align-items-center gap-1">
                                        <i class="bi bi-geo-alt text-muted" style="font-size: 0.8rem;"></i>
                                        ${location ? location.name : '-'}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge ${getStatusClass(status?.name)}">
                                        ${status ? status.name : '-'}
                                    </span>
                                </td>
                                <td>${ext.manufacturer || '-'}</td>
                                <td>${formatDate(ext.manufacture_date)}</td>
                                <td>
                                    <div class="table-actions">
                                        <button class="btn btn-sm btn-info"
                                                onclick="viewExtinguisherHistory(${ext.id})"
                                                title="История проверок">
                                            <i class="bi bi-clock-history"></i>
                                        </button>
                                        <button class="btn btn-sm btn-primary"
                                                onclick="showEditExtinguisherModal(${ext.id})"
                                                title="Редактировать">
                                            <i class="bi bi-pencil"></i>
                                        </button>
                                        <button class="btn btn-sm btn-danger"
                                                onclick="deleteExtinguisher(${ext.id}, '${ext.inventory_number}')"
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

function resetFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('locationFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('extinguishersTable').innerHTML = renderExtinguishersTable(currentExtinguishers);
}

function showAddExtinguisherModal() {
    const modal = new bootstrap.Modal(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Добавить огнетушитель';
    document.getElementById('modalBody').innerHTML = renderExtinguisherForm();

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        data.capacity = parseFloat(data.capacity);
        data.location_id = parseInt(data.location_id);
        data.status_id = parseInt(data.status_id);

        Object.keys(data).forEach(key => {
            if (data[key] === '' || data[key] === null) delete data[key];
        });

        try {
            await API.createExtinguisher(data);
            showAlert('Огнетушитель успешно добавлен', 'success');
            modal.hide();
            loadExtinguishers();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

async function showEditExtinguisherModal(id) {
    const extinguisher = await API.getExtinguisher(id);

    const modal = new bootstrap.Modal(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Редактировать огнетушитель';
    document.getElementById('modalBody').innerHTML = renderExtinguisherForm(extinguisher);

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        data.capacity = parseFloat(data.capacity);
        data.location_id = parseInt(data.location_id);
        data.status_id = parseInt(data.status_id);

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

    return `
        <form id="extinguisherForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Инвентарный номер *</label>
                    <input type="text" class="form-control" name="inventory_number"
                           value="${isEdit ? data.inventory_number : ''}" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Тип *</label>
                    <input type="text" class="form-control" name="type"
                           placeholder="ОУ-8, ОП-5 и т.д."
                           value="${isEdit ? data.type : ''}" required>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Вместимость (л/кг) *</label>
                    <input type="number" class="form-control" name="capacity"
                           value="${isEdit ? data.capacity : ''}"
                           step="0.1" min="0.1" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Производитель</label>
                    <input type="text" class="form-control" name="manufacturer"
                           value="${isEdit ? data.manufacturer || '' : ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата изготовления</label>
                    <input type="date" class="form-control" name="manufacture_date"
                           value="${isEdit ? data.manufacture_date || '' : ''}">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата ввода в эксплуатацию</label>
                    <input type="date" class="form-control" name="commissioning_date"
                           value="${isEdit ? data.commissioning_date || '' : ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Место расположения *</label>
                    <select class="form-select" name="location_id" required>
                        <option value="">Выберите место</option>
                        ${locations.map(loc => `
                            <option value="${loc.id}" ${isEdit && loc.id === data.location_id ? 'selected' : ''}>
                                ${loc.name}
                            </option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Статус *</label>
                    <select class="form-select" name="status_id" required>
                        ${statuses.map(st => `
                            <option value="${st.id}" ${isEdit && st.id === data.status_id ? 'selected' : ''}>
                                ${st.name}
                            </option>
                        `).join('')}
                    </select>
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

async function deleteExtinguisher(id, inventoryNumber) {
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
    const extinguisher = await API.getExtinguisher(id);
    const inspections = await API.getInspectionsByExtinguisher(id);

    const modal = new bootstrap.Modal(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = `История проверок: ${extinguisher.inventory_number}`;

    const location = locations.find(l => l.id === extinguisher.location_id);
    const status = statuses.find(s => s.id === extinguisher.status_id);

    document.getElementById('modalBody').innerHTML = `
        <div class="d-flex align-items-center gap-2 mb-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
            <span class="badge ${getStatusClass(status?.name)}">${status ? status.name : '-'}</span>
            <span class="text-muted">|</span>
            <span><strong>${extinguisher.type}</strong></span>
            <span class="text-muted">|</span>
            <span class="d-flex align-items-center gap-1">
                <i class="bi bi-geo-alt text-muted"></i> ${location ? location.name : '-'}
            </span>
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
                                <td>${insp.pressure || '-'}</td>
                                <td>${insp.weight || '-'}</td>
                                <td>
                                    <span class="badge badge-sm ${insp.visual_inspection === 'Исправен' ? 'status-actual' : insp.visual_inspection === 'Неисправен' ? 'status-expired' : 'status-maintenance'}">
                                        ${insp.visual_inspection || '-'}
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

function formatDate(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('ru-RU');
}
