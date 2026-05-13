// import.js — Импорт данных

async function loadImportPage() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <!-- Page Header -->
        <div class="page-header">
            <h2><i class="bi bi-upload"></i> Импорт данных</h2>
            <p class="text-muted mb-0">Вставьте текст CSV (включая строку с заголовками) и нажмите «Импортировать»</p>
        </div>

        <div class="row g-4">
            <!-- Locations -->
            <div class="col-lg-6">
                <div class="card section-card import-card-locations h-100">
                    <div class="card-header text-white">
                        <i class="bi bi-geo-alt"></i> Места расположения
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center gap-2 mb-3 p-2" style="background: rgba(59,130,246,0.05); border-radius: 8px;">
                            <i class="bi bi-info-circle text-muted"></i>
                            <code style="font-size: 0.8rem; color: var(--text-secondary);">name;description</code>
                        </div>
                        <textarea id="locationsText" class="form-control" rows="6"
                                  placeholder="name;description&#10;Кабинет 101;Первый этаж..."></textarea>
                        <button class="btn btn-primary mt-3" onclick="importLocationsText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="locationsResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Employees -->
            <div class="col-lg-6">
                <div class="card section-card import-card-employees h-100">
                    <div class="card-header text-white">
                        <i class="bi bi-people"></i> Сотрудники
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center gap-2 mb-3 p-2" style="background: rgba(16,185,129,0.05); border-radius: 8px;">
                            <i class="bi bi-info-circle text-muted"></i>
                            <code style="font-size: 0.8rem; color: var(--text-secondary);">full_name;position</code>
                        </div>
                        <textarea id="employeesText" class="form-control" rows="6"
                                  placeholder="full_name;position&#10;Иванов Иван Иванович;Инженер..."></textarea>
                        <button class="btn btn-success mt-3" onclick="importEmployeesText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="employeesResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Extinguishers -->
            <div class="col-lg-6">
                <div class="card section-card import-card-extinguishers h-100">
                    <div class="card-header text-white">
                        <i class="bi bi-droplet"></i> Огнетушители
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center gap-2 mb-3 p-2" style="background: rgba(249,115,22,0.05); border-radius: 8px;">
                            <i class="bi bi-info-circle text-muted"></i>
                            <code style="font-size: 0.75rem; color: var(--text-secondary);">inventory_number;type;capacity;manufacturer;manufacture_date;commissioning_date;location_name;status_name</code>
                        </div>
                        <div class="alert alert-warning alert-sm mb-3">
                            <i class="bi bi-exclamation-triangle"></i>
                            <small>Перед импортом огнетушителей добавьте места и статусы.</small>
                        </div>
                        <textarea id="extinguishersText" class="form-control" rows="6"
                                  placeholder="inventory_number;type;...;status_name&#10;ОУ-001;ОУ-5;5.0;..."></textarea>
                        <button class="btn btn-primary mt-3" onclick="importExtinguishersText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="extinguishersResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Inspections -->
            <div class="col-lg-6">
                <div class="card section-card import-card-inspections h-100">
                    <div class="card-header text-white">
                        <i class="bi bi-clipboard-check"></i> Журнал проверок
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center gap-2 mb-3 p-2" style="background: rgba(245,158,11,0.05); border-radius: 8px;">
                            <i class="bi bi-info-circle text-muted"></i>
                            <small class="text-muted" style="font-size: 0.75rem;">Дата;Инв. номер;Тип;Место;Статус;ФИО;Должность;Давление;Вес;Осмотр;Пломба;Чека;Шланг;Комментарий;След. проверка</small>
                        </div>
                        <div class="alert alert-warning alert-sm mb-3">
                            <i class="bi bi-exclamation-triangle"></i>
                            <small>Перед импортом проверок добавьте огнетушители и сотрудников.</small>
                        </div>
                        <textarea id="inspectionsText" class="form-control" rows="6"
                                  placeholder="Дата проверки;Инв. номер;...&#10;01.01.2024;ОУ-001;..."></textarea>
                        <button class="btn btn-warning mt-3" onclick="importInspectionsText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="inspectionsResult" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Import Order Guide -->
        <div class="section-card mt-4">
            <div class="card-header">
                <i class="bi bi-list-ol"></i> Рекомендуемый порядок импорта
            </div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4">
                        <div class="d-flex align-items-start gap-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #6B7280, #4B5563); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;">1</div>
                            <div>
                                <strong style="font-size: 0.9rem;">Статусы</strong>
                                <p class="text-muted mb-0" style="font-size: 0.8rem;">Инициализируйте через Swagger (POST /statuses/init-defaults)</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="d-flex align-items-start gap-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6, #1D4ED8); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;">2</div>
                            <div>
                                <strong style="font-size: 0.9rem;">Места расположения</strong>
                                <p class="text-muted mb-0" style="font-size: 0.8rem;">Импортируйте список мест</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="d-flex align-items-start gap-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #10B981, #059669); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;">3</div>
                            <div>
                                <strong style="font-size: 0.9rem;">Сотрудники</strong>
                                <p class="text-muted mb-0" style="font-size: 0.8rem;">Импортируйте список проверяющих</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="d-flex align-items-start gap-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #F97316, #EF4444); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;">4</div>
                            <div>
                                <strong style="font-size: 0.9rem;">Огнетушители</strong>
                                <p class="text-muted mb-0" style="font-size: 0.8rem;">Требуются уже добавленные места и статусы</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="d-flex align-items-start gap-3 p-3" style="background: #F8FAFC; border-radius: 12px;">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #F59E0B, #D97706); display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;">5</div>
                            <div>
                                <strong style="font-size: 0.9rem;">Журнал проверок</strong>
                                <p class="text-muted mb-0" style="font-size: 0.8rem;">Требуются огнетушители и сотрудники</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function makeTextFileFromTextarea(text) {
    const blob = new Blob([text], { type: 'text/csv;charset=utf-8;' });
    return new File([blob], 'import.csv', { type: 'text/csv' });
}

async function importLocationsText() {
    const textarea = document.getElementById('locationsText');
    const resultDiv = document.getElementById('locationsResult');
    const text = textarea.value.trim();

    if (!text) {
        resultDiv.innerHTML = '<div class="alert alert-warning">Вставьте текст CSV</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="loading" style="padding: 20px;"><i class="bi bi-arrow-clockwise" style="font-size: 1.5rem;"></i><p>Импорт...</p></div>';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importLocations(form);
        renderImportResult(resultDiv, result);
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Ошибка: ${error.message}</div>`;
    }
}

async function importEmployeesText() {
    const textarea = document.getElementById('employeesText');
    const resultDiv = document.getElementById('employeesResult');
    const text = textarea.value.trim();

    if (!text) {
        resultDiv.innerHTML = '<div class="alert alert-warning">Вставьте текст CSV</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="loading" style="padding: 20px;"><i class="bi bi-arrow-clockwise" style="font-size: 1.5rem;"></i><p>Импорт...</p></div>';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importEmployees(form);
        renderImportResult(resultDiv, result);
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Ошибка: ${error.message}</div>`;
    }
}

async function importExtinguishersText() {
    const textarea = document.getElementById('extinguishersText');
    const resultDiv = document.getElementById('extinguishersResult');
    const text = textarea.value.trim();

    if (!text) {
        resultDiv.innerHTML = '<div class="alert alert-warning">Вставьте текст CSV</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="loading" style="padding: 20px;"><i class="bi bi-arrow-clockwise" style="font-size: 1.5rem;"></i><p>Импорт...</p></div>';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importExtinguishers(form);
        renderImportResult(resultDiv, result);
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Ошибка: ${error.message}</div>`;
    }
}

async function importInspectionsText() {
    const textarea = document.getElementById('inspectionsText');
    const resultDiv = document.getElementById('inspectionsResult');
    const text = textarea.value.trim();

    if (!text) {
        resultDiv.innerHTML = '<div class="alert alert-warning">Вставьте текст CSV</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="loading" style="padding: 20px;"><i class="bi bi-arrow-clockwise" style="font-size: 1.5rem;"></i><p>Импорт...</p></div>';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importInspections(form);
        renderImportResult(resultDiv, result);
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Ошибка: ${error.message}</div>`;
    }
}

function renderImportResult(container, result) {
    let html = '';

    if (result.success > 0) {
        html += `
            <div class="alert alert-success animate-fadeIn">
                <i class="bi bi-check-circle"></i>
                <strong>Успешно импортировано: ${result.success}</strong>
            </div>
        `;
    }

    if (result.errors && result.errors.length > 0) {
        html += `
            <div class="alert alert-danger animate-fadeIn" style="max-height: 200px; overflow-y: auto;">
                <i class="bi bi-exclamation-triangle"></i>
                <strong>Ошибки (${result.errors.length}):</strong>
                <ul class="mb-0 mt-2">
                    ${result.errors.map(err => `<li>${err}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    container.innerHTML = html || '<div class="alert alert-info">Импорт завершён.</div>';
}
