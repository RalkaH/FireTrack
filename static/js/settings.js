// settings.js — страница «Настройки» (только для администратора)

let backupNames = [];

const SETTINGS_GROUPS = [
    {
        title: 'Шапка и подпись отчётов',
        icon: 'bi-file-earmark-text',
        keys: ['organization_name', 'responsible_position', 'responsible_name']
    },
    {
        title: 'Сроки перезарядки по умолчанию',
        icon: 'bi-arrow-repeat',
        note: 'Таблица 1 ГОСТ Р 59641-2021 («не реже»): вода и пена 1 раз в год, порошок, углекислота и хладон 1 раз в 5 лет. '
            + 'Если в паспорте огнетушителя указан другой срок, задайте его в карточке огнетушителя.',
        keys: ['recharge_months_water', 'recharge_months_foam', 'recharge_months_powder',
               'recharge_months_co2', 'recharge_months_halon']
    },
    {
        title: 'Проверки, испытания и срок службы',
        icon: 'bi-hourglass-split',
        note: 'ГОСТ Р 59641-2021: ежегодная проверка (п. 5.1.1), испытания один раз в пять лет (п. 5.1.9 и 5.1.11.2). '
            + 'Срок службы перезаряжаемого огнетушителя с металлическим корпусом не менее 10 лет (п. 5.53 ГОСТ Р 51057-2001), точный срок указан в паспорте.',
        keys: ['inspection_interval_months', 'test_interval_months', 'service_life_years',
               'recharge_warning_days', 'recharge_overdue_needs_service']
    },
    {
        title: 'Резервные копии',
        icon: 'bi-database-check',
        note: 'Раз в сутки при работающем сервере база копируется в папку backups. Старые автокопии удаляются, ручные и сделанные перед обновлением остаются.',
        keys: ['backup_keep_count']
    }
];

async function loadSettingsPage() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка настроек...</p>
        </div>
    `;
    let data;
    try {
        data = await API.getSettings();
    } catch (error) {
        content.innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${esc(error.message)}</div>`;
        return;
    }

    const field = (key) => {
        const value = data.values[key];
        const def = data.defaults[key];
        const label = esc(data.labels[key] || key);
        if (typeof def === 'boolean') {
            return `
                <div class="form-check form-switch mb-3">
                    <input class="form-check-input" type="checkbox" role="switch" id="set_${key}" name="${key}" ${value ? 'checked' : ''}>
                    <label class="form-check-label" for="set_${key}">${label}</label>
                </div>`;
        }
        if (typeof def === 'number') {
            const lim = data.limits[key] || {};
            return `
                <div class="col-md-6 col-xl-4 mb-3">
                    <label class="form-label" for="set_${key}">${label}</label>
                    <input type="number" class="form-control" id="set_${key}" name="${key}" value="${esc(value)}"
                           min="${lim.min ?? ''}" max="${lim.max ?? ''}" step="1" required>
                    <small class="text-muted">По умолчанию: ${esc(def)}</small>
                </div>`;
        }
        return `
            <div class="col-md-6 col-xl-4 mb-3">
                <label class="form-label" for="set_${key}">${label}</label>
                <input type="text" class="form-control" id="set_${key}" name="${key}" value="${esc(value)}" maxlength="200">
            </div>`;
    };

    content.innerHTML = `
        <div class="page-header">
            <h2><i class="bi bi-sliders"></i> Настройки</h2>
        </div>
        <form id="settingsForm">
            ${SETTINGS_GROUPS.map(g => `
                <div class="section-card mb-4">
                    <div class="card-header"><i class="bi ${g.icon}"></i> ${esc(g.title)}</div>
                    <div class="card-body">
                        ${g.note ? `<p class="text-muted small"><i class="bi bi-book"></i> ${esc(g.note)}</p>` : ''}
                        <div class="row">${g.keys.map(field).join('')}</div>
                    </div>
                </div>
            `).join('')}
            <div class="text-end">
                <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить настройки</button>
            </div>
        </form>

        <div class="section-card mt-4">
            <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
                <span><i class="bi bi-archive"></i> Копии базы</span>
                <button type="button" class="btn btn-sm btn-primary" onclick="createBackupNow()">
                    <i class="bi bi-plus-circle"></i> Создать копию сейчас
                </button>
            </div>
            <div class="card-body" id="backupsList"><p class="text-muted mb-0">Загрузка...</p></div>
        </div>
    `;

    document.getElementById('settingsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const values = {};
        for (const key of Object.keys(data.defaults)) {
            const input = e.target.elements[key];
            if (!input) continue;
            if (input.type === 'checkbox') values[key] = input.checked;
            else if (input.type === 'number') values[key] = parseInt(input.value, 10);
            else values[key] = input.value.trim();
        }
        try {
            const result = await API.saveSettings(values);
            const extra = result.changed_statuses ? `, пересчитано статусов: ${result.changed_statuses}` : '';
            showAlert('Настройки сохранены' + extra, 'success');
            loadSettingsPage();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });
    loadBackups();
}

/* ---------- Резервные копии ---------- */

const BACKUP_KIND_NAMES = { auto: 'Автоматическая', manual: 'Ручная', migration: 'Перед обновлением' };

function formatSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

async function loadBackups() {
    const box = document.getElementById('backupsList');
    if (!box) return;
    try {
        const items = await API.getBackups();
        backupNames = items.map(b => b.name);
        box.innerHTML = items.length === 0
            ? '<p class="text-muted mb-0">Копий пока нет.</p>'
            : `<div class="table-responsive"><table class="table table-sm table-hover mb-0">
                <thead><tr><th>Создана</th><th>Тип</th><th>Размер</th><th>Файл</th><th style="width: 60px;"></th></tr></thead>
                <tbody>${items.slice(0, 30).map((b, idx) => `
                    <tr>
                        <td class="text-nowrap">${formatDateTime(b.created_at)}</td>
                        <td>${esc(BACKUP_KIND_NAMES[b.kind] || b.kind)}</td>
                        <td class="text-nowrap">${esc(formatSize(b.size))}</td>
                        <td class="text-muted small">${esc(b.name)}</td>
                        <td><button type="button" class="btn btn-sm btn-info" title="Скачать" onclick="downloadBackup(${idx})"><i class="bi bi-download"></i></button></td>
                    </tr>`).join('')}
                </tbody></table></div>`;
    } catch (error) {
        box.innerHTML = `<div class="alert alert-danger mb-0">${esc(error.message)}</div>`;
    }
}

async function createBackupNow() {
    try {
        const result = await API.createBackup();
        showAlert(`Копия создана: ${result.name}`, 'success');
        loadBackups();
    } catch (error) {
        showAlert('Ошибка: ' + error.message, 'danger');
    }
}

async function downloadBackup(index) {
    try {
        await API.downloadFile(`/backups/${encodeURIComponent(backupNames[index])}`, {}, backupNames[index]);
    } catch (error) {
        showAlert('Не удалось скачать копию: ' + error.message, 'danger');
    }
}
