// dashboard.js - Главная страница с дашбордом
console.log('DASHBOARD JS LOADED v2');

async function loadDashboard() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка данных...</p>
        </div>
    `;

    try {
        const stats = await API.getDashboard();
        const upcoming = await API.getUpcomingInspections(30);
        const expired = await API.getExpiredList();

        content.innerHTML = `
            <div class="row mb-3">
                <div class="col-12">
                    <h2><i class="bi bi-speedometer2 me-2"></i>Панель управления</h2>
                </div>
            </div>

            <!-- Статистика -->
            <div class="row row-dashboard g-3 mb-3">
                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card blue d-flex flex-column align-items-center text-center">
                        <div class="icon mb-2"><i class="bi bi-droplet-fill"></i></div>
                        <div class="label">ВСЕГО ОГНЕТУШИТЕЛЕЙ</div>
                        <div class="value mt-1">${stats.total_extinguishers}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card green d-flex flex-column align-items-center text-center">
                        <div class="icon mb-2"><i class="bi bi-check-circle-fill"></i></div>
                        <div class="label">АКТУАЛЬНЫЕ</div>
                        <div class="value mt-1">${stats.status_breakdown['Актуально'] || 0}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card red d-flex flex-column align-items-center text-center">
                        <div class="icon mb-2"><i class="bi bi-exclamation-triangle-fill"></i></div>
                        <div class="label">ПРОСРОЧЕНО</div>
                        <div class="value mt-1">${stats.expired_count}</div>
                    </div>
                </div>

                <div class="col-12 col-sm-6 col-xl-3">
                    <div class="dashboard-card amber d-flex flex-column align-items-center text-center">
                        <div class="icon mb-2"><i class="bi bi-clock-fill"></i></div>
                        <div class="label">ПРОВЕРОК В БЛИЖАЙШИЕ 30 ДНЕЙ</div>
                        <div class="value mt-1">${stats.upcoming_inspections_30_days}</div>
                    </div>
                </div>
            </div>

            <!-- Предстоящие / просроченные -->
            <div class="row g-3 mb-3">
                <div class="col-12 col-xl-6">
                    <div class="card section-card">
                        <div class="card-header">
                            <i class="bi bi-calendar-check me-1"></i> Предстоящие проверки (30 дней)
                        </div>
                        <div class="card-body">
                            ${renderUpcoming(upcoming)}
                        </div>
                    </div>
                </div>

                <div class="col-12 col-xl-6">
                    <div class="card section-card">
                        <div class="card-header">
                            <i class="bi bi-exclamation-triangle me-1"></i> Просроченные огнетушители
                        </div>
                        <div class="card-body">
                            ${renderExpired(expired)}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Быстрые действия -->
            <div class="row mb-3">
                <div class="col-12">
                    <div class="card section-card quick-actions">
                        <div class="card-header">
                            <i class="bi bi-lightning-fill me-1"></i> Быстрые действия
                        </div>
                        <div class="card-body d-flex flex-wrap gap-2">
                            <button class="btn btn-primary" onclick="showAddExtinguisherModal()">
                                <i class="bi bi-plus-circle"></i> Добавить огнетушитель
                            </button>
                            <button class="btn btn-secondary" onclick="showAddLocationModal()">
                                <i class="bi bi-geo-alt"></i> Добавить место
                            </button>
                            <button class="btn btn-secondary" onclick="showAddEmployeeModal()">
                                <i class="bi bi-person-plus"></i> Добавить сотрудника
                            </button>
                            <button class="btn btn-success" onclick="openInspectionFromDashboard()">
                                <i class="bi bi-clipboard-check"></i> Провести проверку
                            </button>
                            <button class="btn btn-info" onclick="API.downloadCSV()">
                                <i class="bi bi-download"></i> Скачать журнал (CSV)
                            </button>
                                <button class="btn btn-sm btn-outline-secondary" onclick="API.downloadJournalJSON()">
                                <i class="bi bi-file-code"></i> Экспорт JSON
                            </button>
                            <button class="btn btn-warning" onclick="recalculateAllStatuses()">
                                <i class="bi bi-arrow-clockwise"></i> Пересчитать статусы
                            </button>

                        </div>
                    </div>
                </div>
            </div>
        `;

        // Обработчики для ссылок data-page
        content.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                document
                    .querySelector(`[data-page="${this.getAttribute('data-page')}"]`)
                    .classList.add('active');
                loadPage(this.getAttribute('data-page'));
            });
        });

    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки данных: ${error.message}
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
                        <th>Осталось дней</th>
                    </tr>
                </thead>
                <tbody>
                    ${upcoming.slice(0, 5).map(item => `
                        <tr>
                            <td><strong>${item.inventory_number}</strong></td>
                            <td>${item.location}</td>
                            <td>${formatDate(item.next_inspection)}</td>
                            <td>
                                <span class="badge ${item.days_until_inspection <= 7 ? 'bg-danger' : 'bg-warning'}">
                                    ${item.days_until_inspection} дн.
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${upcoming.length > 5 ? `
            <div class="text-center mt-2">
                <a href="#" class="btn btn-sm btn-outline-primary" data-page="reports">
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
                    </tr>
                </thead>
                <tbody>
                    ${expired.slice(0, 5).map(item => `
                        <tr class="table-danger">
                            <td><strong>${item.inventory_number}</strong></td>
                            <td>${item.type}</td>
                            <td>${item.location}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${expired.length > 5 ? `
            <div class="text-center mt-2">
                <a href="#" class="btn btn-sm btn-outline-danger" data-page="reports">
                    Показать все (${expired.length})
                </a>
            </div>
        ` : ''}
    `;
}

async function recalculateAllStatuses() {
    if (isRecalculating) return;          // защита от повторного клика
    isRecalculating = true;

    try {
        await API.recalculateStatuses();  // POST /statuses/recalculate
        alert('Статусы пересчитаны');
        await loadDashboard();            // обновить дашборд
    } catch (err) {
        console.error('Ошибка пересчёта статусов', err);
        alert('Ошибка пересчёта статусов');
    } finally {
        isRecalculating = false;
    }
}



function showAddLocationModal() {
    const modal = new bootstrap.Modal(document.getElementById('formModal'));
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
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function showAddEmployeeModal() {
    const modal = new bootstrap.Modal(document.getElementById('formModal'));
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
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function formatDate(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('ru-RU');
}

async function openInspectionFromDashboard() {
    try {
        // если проверки ещё не загружались – подгрузим всё нужное
        if (allExtinguishers.length === 0 || allEmployees.length === 0) {
            [allExtinguishers, allEmployees, locations] = await Promise.all([
                API.getExtinguishers(),
                API.getEmployees(),
                API.getLocations()
            ]);
        }
        showAddInspectionModal();
    } catch (error) {
        showAlert('Не удалось подготовить данные для проверки: ' + error.message, 'danger');
    }
}
