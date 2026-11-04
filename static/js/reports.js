// reports.js — раздел «Отчёты»: выбор отчёта, периода и формата

const REPORTS = [
    {
        id: 'journal',
        title: 'Журнал проверок',
        icon: 'bi-clipboard-check',
        color: 'blue',
        description: 'Все проверки за период: показания, состояние узлов, замечания, проверяющий. '
            + 'Строки с дефектами подсвечены.',
        period: true,
        formats: [
            { kind: 'print', label: 'Печать / PDF', icon: 'bi-printer' },
            { kind: 'xlsx', label: 'Excel', icon: 'bi-file-earmark-excel', path: '/reports/journal.xlsx', file: 'journal.xlsx' },
            { kind: 'csv', label: 'CSV для импорта', icon: 'bi-filetype-csv', path: '/reports/journal.csv', file: 'journal.csv' }
        ]
    },
    {
        id: 'maintenance',
        title: 'Журнал ТО огнетушителей (форма Г.2)',
        icon: 'bi-journal-check',
        color: 'amber',
        description: 'Рекомендуемая форма журнала технического обслуживания из приложения Г СП 9.13130.2009: '
            + 'проверки узлов, ОТВ, индикатора давления, перезарядки. Графы «Принятые меры» и подпись заполняются от руки.',
        period: true,
        formats: [
            { kind: 'print', label: 'Печать / PDF', icon: 'bi-printer' },
            { kind: 'xlsx', label: 'Excel', icon: 'bi-file-earmark-excel', path: '/reports/maintenance.xlsx', file: 'maintenance.xlsx' }
        ]
    },
    {
        id: 'fleet',
        title: 'Состояние парка',
        icon: 'bi-clipboard-data',
        color: 'green',
        description: 'Сводка по статусам и местам, просроченные и требующие обслуживания, '
            + 'ближайшие проверки, перезарядки и окончание срока службы.',
        period: false,
        formats: [
            { kind: 'print', label: 'Печать / PDF', icon: 'bi-printer' },
            { kind: 'xlsx', label: 'Excel', icon: 'bi-file-earmark-excel', path: '/reports/fleet.xlsx', file: 'fleet.xlsx' }
        ]
    }
];

// Быстрый выбор периода
function periodPreset(preset) {
    const today = todayISO();
    const [y, m] = today.split('-').map(Number);
    const pad = n => String(n).padStart(2, '0');
    switch (preset) {
        case 'month': return { date_from: `${y}-${pad(m)}-01`, date_to: today };
        case 'quarter': {
            const qStart = Math.floor((m - 1) / 3) * 3 + 1;
            return { date_from: `${y}-${pad(qStart)}-01`, date_to: today };
        }
        case 'year': return { date_from: `${y}-01-01`, date_to: today };
        case 'prev_year': return { date_from: `${y - 1}-01-01`, date_to: `${y - 1}-12-31` };
        default: return { date_from: '', date_to: '' };
    }
}

function loadReportsPage() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="page-header">
            <h2><i class="bi bi-printer"></i> Отчёты</h2>
            <p class="text-muted mb-0">Выберите отчёт, период и формат. Для PDF нажмите «Печать / PDF»
               и в окне печати выберите «Сохранить как PDF».</p>
        </div>

        <div class="row g-4">
            ${REPORTS.map((r, idx) => `
                <div class="col-xl-4 col-lg-6">
                    <div class="section-card report-card h-100 animate-fadeInUp stagger-${idx + 1}">
                        <div class="card-header">
                            <i class="bi ${r.icon}"></i> ${esc(r.title)}
                        </div>
                        <div class="card-body d-flex flex-column">
                            <p class="text-muted small">${esc(r.description)}</p>
                            ${r.period ? `
                                <div class="row g-2 mb-2">
                                    <div class="col-6">
                                        <label class="form-label">С даты</label>
                                        <input type="date" class="form-control" id="${r.id}_from" max="${todayISO()}">
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label">По дату</label>
                                        <input type="date" class="form-control" id="${r.id}_to" max="${todayISO()}">
                                    </div>
                                </div>
                                <div class="d-flex flex-wrap gap-1 mb-3">
                                    ${[['month', 'Этот месяц'], ['quarter', 'Квартал'], ['year', 'Этот год'],
                                       ['prev_year', 'Прошлый год'], ['all', 'Всё время']].map(([key, label]) => `
                                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="applyPreset('${r.id}', '${key}')">${label}</button>
                                    `).join('')}
                                </div>
                            ` : `
                                <div class="mb-3">
                                    <label class="form-label">Ближайшие проверки на, дней</label>
                                    <input type="number" class="form-control" id="${r.id}_days" value="30" min="1" max="365">
                                </div>
                            `}
                            <div class="d-flex flex-wrap gap-2 mt-auto">
                                ${r.formats.map(f => `
                                    <button class="btn ${f.kind === 'print' ? 'btn-primary' : 'btn-secondary'}"
                                            onclick="runReport('${r.id}', '${f.kind}')">
                                        <i class="bi ${f.icon}"></i> ${esc(f.label)}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>

        <div class="section-card mt-4">
            <div class="card-header"><i class="bi bi-info-circle"></i> Шапка и подпись</div>
            <div class="card-body text-muted small">
                Название организации и ответственный за пожарную безопасность берутся из настроек.
                <span class="requires-admin">Изменить их можно в разделе
                    <a href="#" data-page="settings">«Настройки»</a>.</span>
                Все выгрузки отчётов записываются в журнал действий.
            </div>
        </div>
    `;
    applyPreset('journal', 'year');
    applyPreset('maintenance', 'year');
}

function applyPreset(reportId, preset) {
    const { date_from, date_to } = periodPreset(preset);
    document.getElementById(`${reportId}_from`).value = date_from;
    document.getElementById(`${reportId}_to`).value = date_to;
}

function reportParams(report) {
    if (report.period) {
        const params = {
            date_from: document.getElementById(`${report.id}_from`).value,
            date_to: document.getElementById(`${report.id}_to`).value
        };
        if (params.date_from && params.date_to && params.date_from > params.date_to) {
            throw new Error('Дата начала позже даты окончания');
        }
        return params;
    }
    return { days: document.getElementById(`${report.id}_days`).value || 30 };
}

async function runReport(reportId, kind) {
    const report = REPORTS.find(r => r.id === reportId);
    const format = report.formats.find(f => f.kind === kind);
    try {
        const params = reportParams(report);
        if (kind === 'print') {
            window.open('/static/print.html' + queryString({ report: reportId, ...params }), '_blank');
            return;
        }
        await API.downloadFile(format.path, params, format.file);
        showAlert('Файл отчёта сформирован', 'success');
    } catch (error) {
        showAlert('Ошибка: ' + error.message, 'danger');
    }
}
