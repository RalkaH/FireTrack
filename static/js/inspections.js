// inspections.js - Управление проверками

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
        // Загрузить данные
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
                Ошибка загрузки данных: ${error.message}
            </div>
        `;
    }
}

function renderInspectionsPage() {
    const content = document.getElementById('content');
    
    content.innerHTML = `
        <div class="row mb-4">
            <div class="col-12">
                <h2><i class="bi bi-clipboard-check"></i> Журнал проверок</h2>
            </div>
        </div>

        <!-- Действия -->
        <div class="filter-section">
            <div class="row g-3">
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
                        <i class="bi bi-filter"></i> Применить
                    </button>
                </div>
                <div class="col-md-3">
                    <label class="form-label">&nbsp;</label>
                    <button class="btn btn-success w-100" onclick="showAddInspectionModal()">
                        <i class="bi bi-plus-circle"></i> Новая проверка
                    </button>
                </div>
            </div>
        </div>

        <!-- Таблица проверок -->
        <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
                <span>Всего проверок: ${allInspections.length}</span>
                <button class="btn btn-sm btn-outline-primary" onclick="API.downloadCSV()">
                    <i class="bi bi-download"></i> Экспорт CSV
                </button>
            </div>
            <div class="card-body">
                <div id="inspectionsTable">
                    ${renderInspectionsTable(allInspections)}
                </div>
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
                <button class="btn btn-primary" onclick="showAddInspectionModal()">
                    <i class="bi bi-plus-circle"></i> Провести первую проверку
                </button>
            </div>
        `;
    }

    return `
        <div class="table-responsive">
            <table class="table table-hover table-sm">
                <thead>
                    <tr>
                        <th>Дата проверки</th>
                        <th>Огнетушитель</th>
                        <th>Место</th>
                        <th>Проверяющий</th>
                        <th>Давление</th>
                        <th>Вес</th>
                        <th>Осмотр</th>
                        <th>Пломба</th>
                        <th>Чека</th>
                        <th>Шланг</th>
                        <th>След. проверка</th>
                        <th>Комментарии</th>
                    </tr>
                </thead>
                <tbody>
                    ${inspections.map(insp => {
                        const extinguisher = allExtinguishers.find(e => e.id === insp.fire_extinguisher_id);
                        const employee = allEmployees.find(e => e.id === insp.employee_id);
                        const location = extinguisher ? locations.find(l => l.id === extinguisher.location_id) : null;
                        
                        return `
                            <tr>
                                <td><strong>${formatDate(insp.inspection_date)}</strong></td>
                                <td>
                                    ${extinguisher ? `
                                        <div>${extinguisher.inventory_number}</div>
                                        <small class="text-muted">${extinguisher.type}</small>
                                    ` : '-'}
                                </td>
                                <td>${location ? location.name : '-'}</td>
                                <td>
                                    ${employee ? `
                                        <div>${employee.full_name}</div>
                                        <small class="text-muted">${employee.position}</small>
                                    ` : '-'}
                                </td>
                                <td>${insp.pressure || '-'}</td>
                                <td>${insp.weight || '-'}</td>
                                <td>${insp.visual_inspection || '-'}</td>
                                <td>${insp.seal_condition || '-'}</td>
                                <td>${insp.safety_pin_condition || '-'}</td>
                                <td>${insp.hose_condition || '-'}</td>
                                <td>
                                    <span class="badge bg-info">
                                        ${formatDate(insp.next_inspection_date)}
                                    </span>
                                </td>
                                <td>
                                    ${insp.comments ? `
                                        <small>${insp.comments}</small>
                                    ` : '-'}
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
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

function showAddInspectionModal() {
    if (allExtinguishers.length === 0) {
        showAlert('Сначала добавьте огнетушители', 'warning');
        return;
    }

    if (allEmployees.length === 0) {
        showAlert('Сначала добавьте сотрудников', 'warning');
        return;
    }

    const modal = new bootstrap.Modal(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Провести проверку';
    
    // Установить сегодняшнюю дату
    const today = new Date().toISOString().split('T')[0];
    // Дата следующей проверки через 6 месяцев
    const nextInspection = new Date();
    nextInspection.setMonth(nextInspection.getMonth() + 6);
    const nextInspectionDate = nextInspection.toISOString().split('T')[0];

    document.getElementById('modalBody').innerHTML = `
        <form id="inspectionForm">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Огнетушитель *</label>
                    <select class="form-select" name="fire_extinguisher_id" required>
                        <option value="">Выберите огнетушитель</option>
                        ${allExtinguishers.map(ext => {
                            const loc = locations.find(l => l.id === ext.location_id);
                            return `
                                <option value="${ext.id}">
                                    ${ext.inventory_number} - ${ext.type} (${loc ? loc.name : '-'})
                                </option>
                            `;
                        }).join('')}
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Дата проверки *</label>
                    <input type="date" class="form-control" name="inspection_date" 
                           value="${today}" required max="${today}">
                </div>
            </div>

            <div class="row">
                <div class="col-md-12 mb-3">
                    <label class="form-label">Проверяющий *</label>
                    <select class="form-select" name="employee_id" required>
                        <option value="">Выберите сотрудника</option>
                        ${allEmployees.map(emp => `
                            <option value="${emp.id}">
                                ${emp.full_name} - ${emp.position}
                            </option>
                        `).join('')}
                    </select>
                </div>
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
                        <option value="Исправен">Исправен</option>
                        <option value="Требует внимания">Требует внимания</option>
                        <option value="Неисправен">Неисправен</option>
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние пломбы</label>
                    <select class="form-select" name="seal_condition">
                        <option value="Цела">Цела</option>
                        <option value="Повреждена">Повреждена</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние чеки</label>
                    <select class="form-select" name="safety_pin_condition">
                        <option value="Исправна">Исправна</option>
                        <option value="Повреждена">Повреждена</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Состояние шланга</label>
                    <select class="form-select" name="hose_condition">
                        <option value="Исправен">Исправен</option>
                        <option value="Поврежден">Поврежден</option>
                        <option value="Отсутствует">Отсутствует</option>
                    </select>
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label">Дата следующей проверки *</label>
                <input type="date" class="form-control" name="next_inspection_date" 
                       value="${nextInspectionDate}" required>
                <small class="text-muted">По умолчанию через 6 месяцев (ГОСТ)</small>
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

    document.getElementById('inspectionForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);
        
        // Преобразовать типы
        data.fire_extinguisher_id = parseInt(data.fire_extinguisher_id);
        data.employee_id = parseInt(data.employee_id);
        
        if (data.pressure) data.pressure = parseFloat(data.pressure);
        if (data.weight) data.weight = parseFloat(data.weight);
        
        // Удалить пустые поля
        Object.keys(data).forEach(key => {
            if (data[key] === '' || data[key] === null) {
                delete data[key];
            }
        });

        try {
            await API.createInspection(data);
            showAlert('Проверка успешно зарегистрирована', 'success');
            modal.hide();
            loadInspections();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function showAlert(message) {
    alert(message);
}