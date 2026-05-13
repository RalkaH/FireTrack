// extinguishers.js - Управление огнетушителями

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
        // Загрузить данные
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
        <div class="row mb-4">
            <div class="col-12">
                <h2><i class="bi bi-droplet"></i> Огнетушители</h2>
            </div>
        </div>

        <!-- Фильтры и поиск -->
        <div class="filter-section">
            <div class="row g-3">
                <div class="col-md-4">
                    <input type="text" class="form-control" id="searchInput" 
                           placeholder="Поиск по инвентарному номеру...">
                </div>
                <div class="col-md-3">
                    <select class="form-select" id="locationFilter">
                        <option value="">Все места</option>
                        ${locations.map(loc => `
                            <option value="${loc.id}">${loc.name}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-3">
                    <select class="form-select" id="statusFilter">
                        <option value="">Все статусы</option>
                        ${statuses.map(st => `
                            <option value="${st.id}">${st.name}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-2">
                    <button class="btn btn-primary w-100" onclick="showAddExtinguisherModal()">
                        <i class="bi bi-plus-circle"></i> Добавить
                    </button>
                </div>
            </div>
        </div>

        <!-- Таблица огнетушителей -->
        <div class="card">
            <div class="card-body">
                <div id="extinguishersTable">
                    ${renderExtinguishersTable(currentExtinguishers)}
                </div>
            </div>
        </div>
    `;

    // Добавить обработчики
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
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Инв. номер</th>
                        <th>Тип</th>
                        <th>Вместимость</th>
                        <th>Место</th>
                        <th>Статус</th>
                        <th>Производитель</th>
                        <th>Дата изготовления</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    ${extinguishers.map(ext => {
                        const location = locations.find(l => l.id === ext.location_id);
                        const status = statuses.find(s => s.id === ext.status_id);
                        
                        return `
                            <tr>
                                <td><strong>${ext.inventory_number}</strong></td>
                                <td>${ext.type}</td>
                                <td>${ext.capacity} л/кг</td>
                                <td>${location ? location.name : '-'}</td>
                                <td>
                                    <span class="badge ${getStatusClass(status?.name)}">
                                        ${status ? status.name : '-'}
                                    </span>
                                </td>
                                <td>${ext.manufacturer || '-'}</td>
                                <td>${formatDate(ext.manufacture_date)}</td>
                                <td class="table-actions">
                                    <button class="btn btn-sm btn-info" 
                                            onclick="viewExtinguisherHistory(${ext.id})">
                                        <i class="bi bi-clock-history"></i>
                                    </button>
                                    <button class="btn btn-sm btn-primary" 
                                            onclick="showEditExtinguisherModal(${ext.id})">
                                        <i class="bi bi-pencil"></i>
                                    </button>
                                    <button class="btn btn-sm btn-danger" 
                                            onclick="deleteExtinguisher(${ext.id}, '${ext.inventory_number}')">
                                        <i class="bi bi-trash"></i>
                                    </button>
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

    // Фильтр по поиску
    if (searchValue) {
        filtered = filtered.filter(ext => 
            ext.inventory_number.toLowerCase().includes(searchValue)
        );
    }

    // Фильтр по месту
    if (locationId) {
        filtered = filtered.filter(ext => ext.location_id == locationId);
    }

    // Фильтр по статусу
    if (statusId) {
        filtered = filtered.filter(ext => ext.status_id == statusId);
    }

    document.getElementById('extinguishersTable').innerHTML = renderExtinguishersTable(filtered);
}

function showAddExtinguisherModal() {
    const modal = new bootstrap.Modal(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Добавить огнетушитель';
    document.getElementById('modalBody').innerHTML = `
        <form id="extinguisherForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Инвентарный номер *</label>
                    <input type="text" class="form-control" name="inventory_number" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Тип *</label>
                    <input type="text" class="form-control" name="type" 
                           placeholder="ОУ-8, ОП-5 и т.д." required>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Вместимость (л/кг) *</label>
                    <input type="number" class="form-control" name="capacity" 
                           step="0.1" min="0.1" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Производитель</label>
                    <input type="text" class="form-control" name="manufacturer">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата изготовления</label>
                    <input type="date" class="form-control" name="manufacture_date">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата ввода в эксплуатацию</label>
                    <input type="date" class="form-control" name="commissioning_date">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Место расположения *</label>
                    <select class="form-select" name="location_id" required>
                        <option value="">Выберите место</option>
                        ${locations.map(loc => `
                            <option value="${loc.id}">${loc.name}</option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Статус *</label>
                    <select class="form-select" name="status_id" required>
                        ${statuses.map(st => `
                            <option value="${st.id}">${st.name}</option>
                        `).join('')}
                    </select>
                </div>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-save"></i> Сохранить
                </button>
            </div>
        </form>
    `;

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);
        
        // Преобразовать типы
        data.capacity = parseFloat(data.capacity);
        data.location_id = parseInt(data.location_id);
        data.status_id = parseInt(data.status_id);
        
        // Удалить пустые поля
        Object.keys(data).forEach(key => {
            if (data[key] === '' || data[key] === null) {
                delete data[key];
            }
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
    document.getElementById('modalBody').innerHTML = `
        <form id="extinguisherForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Инвентарный номер *</label>
                    <input type="text" class="form-control" name="inventory_number" 
                           value="${extinguisher.inventory_number}" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Тип *</label>
                    <input type="text" class="form-control" name="type" 
                           value="${extinguisher.type}" required>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Вместимость (л/кг) *</label>
                    <input type="number" class="form-control" name="capacity" 
                           value="${extinguisher.capacity}" step="0.1" min="0.1" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Производитель</label>
                    <input type="text" class="form-control" name="manufacturer" 
                           value="${extinguisher.manufacturer || ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата изготовления</label>
                    <input type="date" class="form-control" name="manufacture_date" 
                           value="${extinguisher.manufacture_date || ''}">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата ввода в эксплуатацию</label>
                    <input type="date" class="form-control" name="commissioning_date" 
                           value="${extinguisher.commissioning_date || ''}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Место расположения *</label>
                    <select class="form-select" name="location_id" required>
                        ${locations.map(loc => `
                            <option value="${loc.id}" ${loc.id === extinguisher.location_id ? 'selected' : ''}>
                                ${loc.name}
                            </option>
                        `).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Статус *</label>
                    <select class="form-select" name="status_id" required>
                        ${statuses.map(st => `
                            <option value="${st.id}" ${st.id === extinguisher.status_id ? 'selected' : ''}>
                                ${st.name}
                            </option>
                        `).join('')}
                    </select>
                </div>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-save"></i> Сохранить изменения
                </button>
            </div>
        </form>
    `;

    document.getElementById('extinguisherForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);
        
        // Преобразовать типы
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
    document.getElementById('modalBody').innerHTML = `
        <div class="mb-3">
            <strong>Тип:</strong> ${extinguisher.type} | 
            <strong>Место:</strong> ${locations.find(l => l.id === extinguisher.location_id)?.name}
        </div>
        ${inspections.length > 0 ? `
            <div class="table-responsive">
                <table class="table table-sm">
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
                                <td>${formatDate(insp.inspection_date)}</td>
                                <td>${insp.pressure || '-'}</td>
                                <td>${insp.weight || '-'}</td>
                                <td>${insp.visual_inspection || '-'}</td>
                                <td>${formatDate(insp.next_inspection_date)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        ` : `
            <div class="alert alert-info">
                Проверок еще не было
            </div>
        `}
        <div class="text-end">
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
