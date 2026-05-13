// static/js/import.js

async function loadImportPage() {
    const content = document.getElementById('content');

    content.innerHTML = `
        <div class="row mb-4">
            <div class="col-12">
                <h2><i class="bi bi-upload"></i> Импорт данных из CSV (текст)</h2>
                <p class="text-muted">
                    Вставьте текст CSV (включая строку с заголовками) и нажмите «Импортировать».
                </p>
            </div>
        </div>

        <div class="row">
            <!-- Места -->
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <i class="bi bi-geo-alt"></i> Места расположения
                    </div>
                    <div class="card-body">
                        <p class="text-muted">Заголовок: name;description</code></p>
                        <textarea id="locationsText" class="form-control" rows="6"
                                  placeholder="name;description&#10;Кабинет 101;Первый этаж..."></textarea>
                        <button class="btn btn-primary mt-3" onclick="importLocationsText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="locationsResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Сотрудники -->
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header bg-success text-white">
                        <i class="bi bi-people"></i> Сотрудники
                    </div>
                    <div class="card-body">
                        <p class="text-muted">Заголовок: full_name;position</code></p>
                        <textarea id="employeesText" class="form-control" rows="6"
                                  placeholder="full_name;position&#10;Иванов Иван Иванович;Инженер..."></textarea>
                        <button class="btn btn-success mt-3" onclick="importEmployeesText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="employeesResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Огнетушители -->
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header bg-danger text-white">
                        <i class="bi bi-droplet"></i> Огнетушители
                    </div>
                    <div class="card-body">
                        <p class="text-muted">
                            Заголовок: inventory_number;type;capacity;manufacturer;manufacture_date;commissioning_date;location_name;status_name</code>
                        </p>
                        <div class="alert alert-warning alert-sm">
                            <small>
                                <i class="bi bi-exclamation-triangle"></i>
                                Перед импортом огнетушителей добавьте места и статусы.
                            </small>
                        </div>
                        <textarea id="extinguishersText" class="form-control" rows="6"
                                  placeholder="inventory_number;type;...;status_name&#10;ОУ-001;ОУ-5;5.0;..."></textarea>
                        <button class="btn btn-danger mt-3" onclick="importExtinguishersText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="extinguishersResult" class="mt-3"></div>
                    </div>
                </div>
            </div>

            <!-- Проверки -->
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header bg-warning text-dark">
                        <i class="bi bi-clipboard-check"></i> Журнал проверок
                    </div>
                    <div class="card-body">
                        <p class="text-muted">
                            Заголовок: Дата проверки;Инвентарный номер;Тип;Место расположения;Статус;ФИО проверяющего;Должность;Давление;Вес;Визуальный осмотр;Состояние пломбы;Состояние чеки;Состояние шланга;Комментарии;Дата следующей проверки
                        </p>
                        <div class="alert alert-warning alert-sm">
                            <small>
                                <i class="bi bi-exclamation-triangle"></i>
                                Перед импортом проверок добавьте огнетушители и сотрудников.
                            </small>
                        </div>
                        <textarea id="inspectionsText" class="form-control" rows="6"
                                  placeholder="Дата проверки;Инвентарный номер;..."></textarea>
                        <button class="btn btn-warning mt-3" onclick="importInspectionsText()">
                            <i class="bi bi-upload"></i> Импортировать
                        </button>
                        <div id="inspectionsResult" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Порядок импорта -->
        <div class="card">
            <div class="card-header">
                <i class="bi bi-list-ol"></i> Рекомендуемый порядок импорта
            </div>
            <div class="card-body">
                <ol>
                    <li><strong>Статусы</strong> — инициализируйте стандартные статусы через Swagger (POST /statuses/init-defaults)</li>
                    <li><strong>Места расположения</strong> — импортируйте список мест</li>
                    <li><strong>Сотрудники</strong> — импортируйте список проверяющих</li>
                    <li><strong>Огнетушители</strong> — импортируйте огнетушители (требуются места и статусы)</li>
                    <li><strong>Журнал проверок</strong> — импортируйте историю проверок (требуются огнетушители и сотрудники)</li>
                </ol>
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

    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Загрузка...';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importLocations(form);

        let html = '';
        if (result.success > 0) {
            html += `
                <div class="alert alert-success">
                    <strong>Успешно импортировано: ${result.success}</strong>
                </div>
            `;
        }
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="alert alert-danger">
                    <strong>Ошибки (${result.errors.length}):</strong>
                    <ul class="mb-0 mt-2">
                        ${result.errors.map(err => `<li>${err}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        resultDiv.innerHTML = html || '<div class="alert alert-info">Импорт завершён.</div>';
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
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

    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Загрузка...';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importEmployees(form);

        let html = '';
        if (result.success > 0) {
            html += `
                <div class="alert alert-success">
                    <strong>Успешно импортировано: ${result.success}</strong>
                </div>
            `;
        }
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="alert alert-danger">
                    <strong>Ошибки (${result.errors.length}):</strong>
                    <ul class="mb-0 mt-2">
                        ${result.errors.map(err => `<li>${err}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        resultDiv.innerHTML = html || '<div class="alert alert-info">Импорт завершён.</div>';
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
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

    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Загрузка...';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importExtinguishers(form);

        let html = '';
        if (result.success > 0) {
            html += `
                <div class="alert alert-success">
                    <strong>Успешно импортировано: ${result.success}</strong>
                </div>
            `;
        }
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="alert alert-danger">
                    <strong>Ошибки (${result.errors.length}):</strong>
                    <ul class="mb-0 mt-2">
                        ${result.errors.map(err => `<li>${err}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        resultDiv.innerHTML = html || '<div class="alert alert-info">Импорт завершён.</div>';
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
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

    resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm"></div> Загрузка...';

    try {
        const file = makeTextFileFromTextarea(text);
        const form = new FormData();
        form.append('file', file);
        const result = await API.importInspections(form);

        let html = '';
        if (result.success > 0) {
            html += `
                <div class="alert alert-success">
                    <strong>Успешно импортировано: ${result.success}</strong>
                </div>
            `;
        }
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="alert alert-danger">
                    <strong>Ошибки (${result.errors.length}):</strong>
                    <ul class="mb-0 mt-2" style="max-height: 200px; overflow-y: auto;">
                        ${result.errors.map(err => `<li>${err}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        resultDiv.innerHTML = html || '<div class="alert alert-info">Импорт завершён.</div>';
    } catch (error) {
        resultDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
    }
}