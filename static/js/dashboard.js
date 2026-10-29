// dashboard.js — Главная страница с дашбордом

async function loadDashboard() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка данных...</p>
        </div>
    `;

    try {
        const [stats, upcoming, expired] = await Promise.all([
            API.getDashboard(),
            API.getUpcomingInspections(30),
            API.getExpiredList()
        ]);

        content.innerHTML = `
            <!-- Page Header -->
            <div class="page-header">
                <h2><i class="bi bi-speedometer2"></i> Панель управления</h2>
            </div>

            <!-- Statistics Cards -->
            <div class="row row-dashboard g-3 mb-4">
                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card blue animate-fadeInUp stagger-1">
                        <div class="d-flex align-items-center justify-content-between">
                            <div class="icon-wrap"><i class="bi bi-droplet-fill"></i></div>
                            <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6; font-size: 0.75rem;">Всего</span>
                        </div>
                        <div class="label">Огнетушителей</div>
                        <div class="value">${stats.total_extinguishers}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card green animate-fadeInUp stagger-2">
                        <div class="d-flex align-items-center justify-content-between">
                            <div class="icon-wrap"><i class="bi bi-check-circle-fill"></i></div>
                            <span class="badge" style="background: rgba(16,185,129,0.1); color: #10B981; font-size: 0.75rem;">Актуально</span>
                        </div>
                        <div class="label">В исправности</div>
                        <div class="value">${stats.status_breakdown['Актуально'] || 0}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card red animate-fadeInUp stagger-3">
                        <div class="d-flex align-items-center justify-content-between">
                            <div class="icon-wrap"><i class="bi bi-exclamation-triangle-fill"></i></div>
                            <span class="badge" style="background: rgba(239,68,68,0.1); color: #EF4444; font-size: 0.75rem;">Требует внимания</span>
                        </div>
                        <div class="label">Просрочено</div>
                        <div class="value">${stats.expired_count}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card amber animate-fadeInUp stagger-4">
                        <div class="d-flex align-items-center justify-content-between">
                            <div class="icon-wrap"><i class="bi bi-clock-fill"></i></div>
                            <span class="badge" style="background: rgba(245,158,11,0.1); color: #D97706; font-size: 0.75rem;">30 дней</span>
                        </div>
                        <div class="label">Предстоящих проверок</div>
                        <div class="value">${stats.upcoming_inspections_30_days}</div>
                    </div>
                </div>
            </div>

            <!-- Upcoming & Expired -->
            <div class="row g-4 mb-4">
                <div class="col-12 col-xl-6">
                    <div class="section-card animate-fadeInUp stagger-3">
                        <div class="card-header">
                            <i class="bi bi-calendar-check"></i>
                            Предстоящие проверки (30 дней)
                        </div>
                        <div class="card-body">
                            ${renderUpcoming(upcoming)}
                        </div>
                    </div>
                </div>

                <div class="col-12 col-xl-6">
                    <div class="section-card animate-fadeInUp stagger-4">
                        <div class="card-header">
                            <i class="bi bi-exclamation-triangle"></i>
                            Просроченные огнетушители
                        </div>
                        <div class="card-body">
                            ${renderExpired(expired)}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Actions -->
            <div class="section-card quick-actions animate-fadeInUp stagger-5">
                <div class="card-header">
                    <i class="bi bi-lightning-fill"></i>
                    Быстрые действия
                </div>
                <div class="card-body d-flex flex-wrap gap-2">
                    <button class="btn btn-primary requires-edit" onclick="openAddExtinguisherFromDashboard()">
                        <i class="bi bi-plus-circle"></i> Добавить огнетушитель
                    </button>
                    <button class="btn btn-secondary requires-edit" onclick="showAddLocationModal()">
                        <i class="bi bi-geo-alt"></i> Добавить место
                    </button>
                    <button class="btn btn-secondary requires-edit" onclick="showAddEmployeeModal()">
                        <i class="bi bi-person-plus"></i> Добавить сотрудника
                    </button>
                    <button class="btn btn-success requires-edit" onclick="openInspectionFromDashboard()">
                        <i class="bi bi-clipboard-check"></i> Провести проверку
                    </button>
                    <button class="btn btn-info" onclick="API.downloadCSV()">
                        <i class="bi bi-download"></i> Скачать журнал (CSV)
                    </button>
                    <button class="btn btn-outline-primary" onclick="API.downloadJournalJSON()">
                        <i class="bi bi-file-code"></i> Экспорт JSON
                    </button>
                    <button class="btn btn-warning requires-edit" onclick="recalculateAllStatuses()">
                        <i class="bi bi-arrow-clockwise"></i> Пересчитать статусы
                    </button>
                </div>
            </div>
        `;

    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger animate-fadeIn">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки данных: ${esc(error.message)}
            </div>
        `;
    }
}

function renderUpcoming(upcoming) {
    if (upcoming.length === 0) {
        return `
            <div class="empty-state">
                <i class="bi bi-check-circle"></i>
                <p>Нет предстоящих проверок в ближайшие 30 дней</p>
            </div>
        `;
    }

    return `
        <div class="table-responsive">
            <table class="table table-hover mb-0">
                <thead>
                    <tr>
                        <th>Инв. номер</th>
                        <th>Место</th>
                        <th>Дата проверки</th>
                        <th>Осталось</th>
                    </tr>
                </thead>
                <tbody>
                    ${upcoming.slice(0, 5).map((item, idx) => `
                        <tr style="animation: fadeInUp 0.3s ease-out ${idx * 0.05}s both;">
                            <td><strong>${esc(item.inventory_number)}</strong></td>
                            <td>${esc(item.location)}</td>
                            <td>${formatDate(item.next_inspection)}</td>
                            <td>
                                <span class="badge badge-sm ${item.days_until_inspection <= 7 ? 'status-expired' : 'status-maintenance'}">
                                    ${item.days_until_inspection} дн.
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${upcoming.length > 5 ? `
            <div class="text-center mt-3">
                <a href="#" class="btn btn-sm btn-outline-primary" data-page="inspections">
                    Показать все (${upcoming.length})
                </a>
            </div>
        ` : ''}
    `;
}

function renderExpired(expired) {
    if (expired.length === 0) {
        return `
            <div class="empty-state">
                <i class="bi bi-check-circle"></i>
                <p>Нет просроченных огнетушителей</p>
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
                        <th>Место</th>
                        <th>Просрочено</th>
                    </tr>
                </thead>
                <tbody>
                    ${expired.slice(0, 5).map((item, idx) => `
                        <tr style="animation: fadeInUp 0.3s ease-out ${idx * 0.05}s both;">
                            <td><strong style="color: #DC2626;">${esc(item.inventory_number)}</strong></td>
                            <td>${esc(item.type)}</td>
                            <td>${esc(item.location)}</td>
                            <td>
                                <span class="badge badge-sm status-expired">
                                    ${item.days_overdue === null || item.days_overdue === undefined ? 'нет проверок' : item.days_overdue + ' дн.'}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${expired.length > 5 ? `
            <div class="text-center mt-3">
                <a href="#" class="btn btn-sm btn-outline-danger" data-page="extinguishers" data-status-filter="Просрочено">
                    Показать все (${expired.length})
                </a>
            </div>
        ` : ''}
    `;
}

async function recalculateAllStatuses() {
    if (isRecalculating) return;
    isRecalculating = true;

    try {
        const result = await API.recalculateStatuses();
        showAlert(`Статусы пересчитаны, изменено: ${result.changed}`, 'success');
        await loadDashboard();
    } catch (err) {
        console.error('Ошибка пересчёта статусов', err);
        showAlert('Ошибка пересчёта статусов: ' + err.message, 'danger');
    } finally {
        isRecalculating = false;
    }
}

// onSuccess вызывается после успешного сохранения (например, чтобы обновить список)
function showAddLocationModal(onSuccess) {
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Добавить место расположения';
    document.getElementById('modalBody').innerHTML = `
        <form id="locationForm">
            <div class="mb-3">
                <label class="form-label">Название места *</label>
                <input type="text" class="form-control" name="name"
                       placeholder="Кабинет 101" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Описание</label>
                <textarea class="form-control" name="description" rows="3"
                          placeholder="Первый этаж, слева от входа"></textarea>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-save"></i> Сохранить
                </button>
            </div>
        </form>
    `;

    document.getElementById('locationForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        try {
            await API.createLocation(data);
            showAlert('Место успешно добавлено', 'success');
            modal.hide();
            if (typeof onSuccess === 'function') onSuccess();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function showAddEmployeeModal(onSuccess) {
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = 'Добавить сотрудника';
    document.getElementById('modalBody').innerHTML = `
        <form id="employeeForm">
            <div class="mb-3">
                <label class="form-label">ФИО *</label>
                <input type="text" class="form-control" name="full_name"
                       placeholder="Иванов Иван Иванович" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Должность *</label>
                <input type="text" class="form-control" name="position"
                       placeholder="Инженер по технике безопасности" required>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-save"></i> Сохранить
                </button>
            </div>
        </form>
    `;

    document.getElementById('employeeForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        try {
            await API.createEmployee(data);
            showAlert('Сотрудник успешно добавлен', 'success');
            modal.hide();
            if (typeof onSuccess === 'function') onSuccess();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

// Загружает справочники, нужные формам (огнетушители, сотрудники, места, статусы).
// Переменные объявлены через let в extinguishers.js и inspections.js и общие для всех скриптов.
async function loadReferenceData() {
    [allExtinguishers, allEmployees, locations, statuses] = await Promise.all([
        API.getExtinguishers(),
        API.getEmployees(),
        API.getLocations(),
        API.getStatuses()
    ]);
}

async function openInspectionFromDashboard() {
    try {
        await loadReferenceData();
        showAddInspectionModal(loadDashboard);
    } catch (error) {
        showAlert('Не удалось подготовить данные для проверки: ' + error.message, 'danger');
    }
}

async function openAddExtinguisherFromDashboard() {
    try {
        await loadReferenceData();
        if (locations.length === 0) {
            showAlert('Сначала добавьте хотя бы одно место размещения', 'warning');
            return;
        }
        showAddExtinguisherModal(loadDashboard);
    } catch (error) {
        showAlert('Не удалось подготовить форму: ' + error.message, 'danger');
    }
}
