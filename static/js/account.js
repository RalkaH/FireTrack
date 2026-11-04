// account.js — смена собственного пароля
//
// Форма открывается в отдельном окне #passwordModal (а не в общем #formModal):
// при обязательной смене пароля окно нельзя закрыть, и оно не должно
// перебивать форму, которая была открыта в общем окне.

const PASSWORD_MIN_LENGTH = 8;

// Подсказка о надёжности пароля (сервер всё равно проверяет сам)
function passwordProblems(password, username) {
    const problems = [];
    if (password.length < PASSWORD_MIN_LENGTH) problems.push(`не короче ${PASSWORD_MIN_LENGTH} символов`);
    if (username && password.toLowerCase() === username.toLowerCase()) problems.push('не совпадает с логином');
    if (['admin123', 'password', '12345678', 'qwerty123'].includes(password.toLowerCase())) problems.push('не из списка простых');
    return problems;
}

// forced=true: пароль временный или admin123, без смены работать нельзя
function showChangePasswordModal(forced = false) {
    const el = document.getElementById('passwordModal');
    if (!el) return;
    if (el.classList.contains('show') && el.dataset.forced === '1') return;

    el.dataset.forced = forced ? '1' : '0';
    // Конфигурацию окна задаём при каждом открытии, поэтому старый экземпляр удаляем
    const existing = bootstrap.Modal.getInstance(el);
    if (existing) existing.dispose();
    const modal = new bootstrap.Modal(el, forced ? { backdrop: 'static', keyboard: false } : {});

    el.querySelector('.btn-close').classList.toggle('d-none', forced);
    el.querySelector('#passwordModalBody').innerHTML = `
        ${forced ? `
            <div class="alert alert-warning">
                <i class="bi bi-shield-lock"></i>
                Администратор выдал вам временный пароль, или используется пароль по умолчанию.
                Придумайте свой пароль, чтобы продолжить работу.
            </div>` : ''}
        <form id="changePasswordForm" autocomplete="off">
            <div class="mb-3">
                <label class="form-label">Текущий пароль *</label>
                <input type="password" class="form-control" name="old_password" required autocomplete="current-password">
            </div>
            <div class="mb-3">
                <label class="form-label">Новый пароль *</label>
                <input type="password" class="form-control" name="new_password" id="newPasswordInput"
                       required minlength="${PASSWORD_MIN_LENGTH}" autocomplete="new-password">
                <small class="text-muted" id="passwordHint">Не короче ${PASSWORD_MIN_LENGTH} символов, не совпадает с логином.</small>
            </div>
            <div class="mb-3">
                <label class="form-label">Повторите новый пароль *</label>
                <input type="password" class="form-control" name="repeat_password" required autocomplete="new-password">
            </div>
            <p class="text-muted small mb-3">
                <i class="bi bi-info-circle"></i>
                После смены пароля все остальные ваши сеансы (другие браузеры, устройства) будут завершены.
            </p>
            <div class="text-end">
                ${forced
                    ? '<button type="button" class="btn btn-secondary" onclick="API.logout()">Выйти</button>'
                    : '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>'}
                <button type="submit" class="btn btn-primary">
                    <i class="bi bi-key"></i> Сменить пароль
                </button>
            </div>
        </form>
    `;

    const input = document.getElementById('newPasswordInput');
    const hint = document.getElementById('passwordHint');
    input.addEventListener('input', () => {
        const problems = passwordProblems(input.value, currentUser && currentUser.username);
        hint.textContent = problems.length ? 'Пароль должен быть: ' + problems.join(', ') : 'Пароль подходит';
        hint.className = problems.length ? 'text-muted' : 'text-success';
    });

    document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target));
        if (data.new_password !== data.repeat_password) {
            showAlert('Новые пароли не совпадают', 'warning');
            return;
        }
        const problems = passwordProblems(data.new_password, currentUser && currentUser.username);
        if (problems.length) {
            showAlert('Пароль должен быть: ' + problems.join(', '), 'warning');
            return;
        }
        try {
            await API.changePassword(data.old_password, data.new_password);
            showAlert('Пароль изменён', 'success');
            modal.hide();
            if (forced) {
                currentUser = await API.getMe();
                navigateTo('dashboard');
            }
        } catch (error) {
            showAlert('Ошибка: ' + error.message, 'danger');
        }
    });

    modal.show();
}
