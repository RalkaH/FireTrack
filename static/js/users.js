// users.js — страница «Пользователи» (только для администратора)

let allUsers = [];

const ROLE_HINTS = {
    admin: 'Всё, включая пользователей, журнал действий и настройки',
    engineer: 'Добавляет и редактирует огнетушители, проводит проверки, импорт',
    viewer: 'Только просмотр и отчёты'
};

async function loadUsers() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Загрузка пользователей...</p>
        </div>
    `;
    try {
        allUsers = await API.getUsers();
        renderUsersPage();
    } catch (error) {
        content.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i>
                Ошибка загрузки пользователей: ${esc(error.message)}
            </div>
        `;
    }
}

function roleBadge(role) {
    const cls = { admin: 'status-expired', engineer: 'status-service', viewer: 'status-decommissioned' }[role] || 'status-decommissioned';
    return `<span class="badge badge-sm ${cls}">${esc(ROLE_NAMES[role] || role)}</span>`;
}

function renderUsersPage() {
    const content = document.getElementById('content');
    const active = allUsers.filter(u => u.is_active).length;

    content.innerHTML = `
        <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
            <h2><i class="bi bi-person-gear"></i> Пользователи</h2>
            <button class="btn btn-primary" onclick="showUserModal()">
                <i class="bi bi-person-plus"></i> Добавить пользователя
            </button>
        </div>

        <div class="d-flex gap-3 mb-3 flex-wrap">
            <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6;">
                <i class="bi bi-people me-1"></i> Всего: ${allUsers.length}
            </span>
            <span class="badge" style="background: rgba(16,185,129,0.1); color: #10B981;">
                <i class="bi bi-check-circle me-1"></i> Активных: ${active}
            </span>
            ${allUsers.length - active > 0 ? `
            <span class="badge" style="background: rgba(107,114,128,0.12); color: #6B7280;">
                <i class="bi bi-lock me-1"></i> Заблокировано: ${allUsers.length - active}
            </span>` : ''}
        </div>

        <div class="card">
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead>
                        <tr>
                            <th>Логин</th>
                            <th>ФИО</th>
                            <th>Email</th>
                            <th>Роль</th>
                            <th>Состояние</th>
                            <th>Последний вход</th>
                            <th style="width: 150px;">Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${allUsers.map(u => {
                            const isMe = currentUser && u.id === currentUser.id;
                            return `
                            <tr class="${u.is_active ? '' : 'row-muted'}">
                                <td><strong>${esc(u.username)}</strong>${isMe ? ' <small class="text-muted">(вы)</small>' : ''}</td>
                                <td>${esc(u.full_name)}</td>
                                <td class="text-muted">${esc(u.email)}</td>
                                <td>${roleBadge(u.role)}</td>
                                <td>
                                    ${u.is_active
                                        ? '<span class="badge badge-sm status-actual">Активен</span>'
                                        : '<span class="badge badge-sm status-decommissioned"><i class="bi bi-lock"></i> Заблокирован</span>'}
                                    ${u.must_change_password ? '<br><small class="text-warning"><i class="bi bi-key"></i> сменит пароль при входе</small>' : ''}
                                </td>
                                <td class="text-muted">${u.last_login_at ? formatDateTime(u.last_login_at + (u.last_login_at.endsWith('Z') ? '' : 'Z')) : 'не входил'}</td>
                                <td>
                                    <div class="table-actions">
                                        <button class="btn btn-sm btn-primary" title="Изменить" onclick="showUserModal(${u.id})">
                                            <i class="bi bi-pencil"></i>
                                        </button>
                                        <button class="btn btn-sm btn-warning" title="Сбросить пароль" onclick="showResetPasswordModal(${u.id})">
                                            <i class="bi bi-key"></i>
                                        </button>
                                        ${isMe ? '' : u.is_active
                                            ? `<button class="btn btn-sm btn-danger" title="Заблокировать" onclick="toggleUserActive(${u.id}, false)"><i class="bi bi-lock"></i></button>`
                                            : `<button class="btn btn-sm btn-success" title="Разблокировать" onclick="toggleUserActive(${u.id}, true)"><i class="bi bi-unlock"></i></button>`}
                                    </div>
                                </td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="section-card mt-4">
            <div class="card-header"><i class="bi bi-info-circle"></i> Роли</div>
            <div class="card-body">
                ${Object.keys(ROLE_HINTS).map(r => `
                    <div class="mb-2">${roleBadge(r)} <span class="text-muted ms-2">${esc(ROLE_HINTS[r])}</span></div>
                `).join('')}
                <p class="text-muted small mb-0 mt-3">
                    Блокировка, смена роли и сброс пароля завершают все сеансы пользователя сразу.
                    Удалять пользователей нельзя намеренно: заблокированная учётная запись остаётся в журнале действий.
                </p>
            </div>
        </div>
    `;
}

// Случайный временный пароль без похожих символов (0/O, 1/l)
function generateTempPassword(length = 12) {
    const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';
    const bytes = new Uint32Array(length);
    crypto.getRandomValues(bytes);
    let result = '';
    for (const b of bytes) result += alphabet[b % alphabet.length];
    return result.slice(0, 4) + '-' + result.slice(4, 8) + '-' + result.slice(8);
}

function roleOptions(selected, disabled) {
    return `
        <select class="form-select" name="role" required ${disabled ? 'disabled' : ''}>
            ${['viewer', 'engineer', 'admin'].map(r => `
                <option value="${r}" ${r === selected ? 'selected' : ''}>${esc(ROLE_NAMES[r])}</option>
            `).join('')}
        </select>
        <small class="text-muted" id="roleHint">${esc(ROLE_HINTS[selected] || '')}</small>
    `;
}

// Без id — создание, с id — редактирование
function showUserModal(id = null) {
    const user = id ? allUsers.find(u => u.id === id) : null;
    const isEdit = Boolean(user);
    const isMe = isEdit && currentUser && user.id === currentUser.id;
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = isEdit ? `Пользователь ${user.username}` : 'Новый пользователь';

    const tempPassword = generateTempPassword();
    document.getElementById('modalBody').innerHTML = `
        <form id="userForm" autocomplete="off">
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">Логин *</label>
                    <input type="text" class="form-control" name="username" required
                           pattern="[A-Za-z0-9_.\\-]{3,32}" title="3-32 символа: латиница, цифры, _ . -"
                           value="${isEdit ? esc(user.username) : ''}" ${isEdit ? 'disabled' : ''}>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">Роль *</label>
                    ${roleOptions(isEdit ? user.role : 'engineer', isMe)}
                    ${isMe ? '<small class="d-block text-muted">Свою роль изменить нельзя</small>' : ''}
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">ФИО *</label>
                <input type="text" class="form-control" name="full_name" required value="${isEdit ? esc(user.full_name) : ''}">
            </div>
            <div class="mb-3">
                <label class="form-label">Email *</label>
                <input type="email" class="form-control" name="email" required value="${isEdit ? esc(user.email) : ''}">
            </div>
            ${isEdit ? '' : `
            <div class="mb-3">
                <label class="form-label">Временный пароль *</label>
                <div class="input-group">
                    <input type="text" class="form-control font-monospace" name="password" required minlength="8" value="${tempPassword}">
                    <button type="button" class="btn btn-secondary" onclick="this.previousElementSibling.value = generateTempPassword()" title="Сгенерировать">
                        <i class="bi bi-shuffle"></i>
                    </button>
                </div>
                <div class="form-check mt-2">
                    <input class="form-check-input" type="checkbox" name="must_change_password" id="mustChange" checked>
                    <label class="form-check-label" for="mustChange">Потребовать смену пароля при первом входе</label>
                </div>
                <small class="text-muted">Передайте пароль пользователю лично. После сохранения его больше нигде не будет видно.</small>
            </div>`}
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить</button>
            </div>
        </form>
    `;

    const roleSelect = document.querySelector('#userForm [name="role"]');
    roleSelect.addEventListener('change', () => {
        document.getElementById('roleHint').textContent = ROLE_HINTS[roleSelect.value] || '';
    });

    document.getElementById('userForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const form = e.target;
        const data = Object.fromEntries(new FormData(form));
        try {
            if (isEdit) {
                const update = { full_name: data.full_name.trim(), email: data.email.trim() };
                if (!isMe) update.role = data.role;
                await API.updateUser(id, update);
                showAlert('Пользователь сохранён', 'success');
            } else {
                await API.createUser({
                    username: data.username.trim(),
                    full_name: data.full_name.trim(),
                    email: data.email.trim(),
                    role: data.role,
                    password: data.password,
                    must_change_password: form.querySelector('#mustChange').checked
                });
                showAlert(`Пользователь ${data.username} создан`, 'success');
            }
            modal.hide();
            loadUsers();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}

function showResetPasswordModal(id) {
    const user = allUsers.find(u => u.id === id);
    if (!user) return;
    const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
    document.getElementById('modalTitle').textContent = `Сброс пароля: ${user.username}`;
    document.getElementById('modalBody').innerHTML = `
        <form id="resetPasswordForm" autocomplete="off">
            <p>Пользователь получит временный пароль и при следующем входе должен будет придумать свой.
               Все его текущие сеансы будут завершены.</p>
            <label class="form-label">Временный пароль *</label>
            <div class="input-group mb-3">
                <input type="text" class="form-control font-monospace" name="new_password" required minlength="8" value="${generateTempPassword()}">
                <button type="button" class="btn btn-secondary" onclick="this.previousElementSibling.value = generateTempPassword()" title="Сгенерировать">
                    <i class="bi bi-shuffle"></i>
                </button>
            </div>
            <div class="text-end">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                <button type="submit" class="btn btn-warning"><i class="bi bi-key"></i> Сбросить пароль</button>
            </div>
        </form>
    `;
    document.getElementById('resetPasswordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = new FormData(e.target).get('new_password');
        try {
            await API.resetUserPassword(id, password);
            modal.hide();
            showAlert(`Пароль ${user.username} сброшен. Не забудьте передать временный пароль.`, 'success');
            loadUsers();
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });
    modal.show();
}

async function toggleUserActive(id, isActive) {
    const user = allUsers.find(u => u.id === id);
    if (!user) return;
    const question = isActive
        ? `Разблокировать пользователя ${user.username}?`
        : `Заблокировать пользователя ${user.username}?\n\nОн не сможет войти, текущие сеансы завершатся сразу.`;
    if (!confirm(question)) return;
    try {
        await API.setUserActive(id, isActive);
        showAlert(isActive ? 'Пользователь разблокирован' : 'Пользователь заблокирован', 'success');
        loadUsers();
    } catch (error) {
        showAlert('Ошибка: ' + error.message, 'danger');
    }
}
