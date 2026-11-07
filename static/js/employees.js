// employees.js — страница "Сотрудники"

let employeeRows = [];

async function loadEmployees() {
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="loading">
      <i class="bi bi-arrow-clockwise"></i>
      <p>Загрузка сотрудников...</p>
    </div>
  `;

  try {
    employeeRows = await API.getEmployees();

    content.innerHTML = `
      <!-- Page Header -->
      <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
        <h2><i class="bi bi-people"></i> Сотрудники</h2>
        <button class="btn btn-primary requires-edit" onclick="showAddEmployeeModalInList()">
          <i class="bi bi-person-plus"></i> Добавить сотрудника
        </button>
      </div>

      <!-- Stats -->
      <div class="d-flex gap-3 mb-3">
        <span class="badge" style="background: rgba(16,185,129,0.1); color: #10B981;">
          <i class="bi bi-people me-1"></i> Всего: ${employeeRows.length}
        </span>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul"></i> Список сотрудников
        </div>
        <div class="card-body p-0">
          ${employeeRows.length === 0 ? `
            <div class="empty-state">
              <i class="bi bi-people"></i>
              <p>Сотрудники пока не добавлены</p>
              <button class="btn btn-primary requires-edit" onclick="showAddEmployeeModalInList()">
                <i class="bi bi-person-plus"></i> Добавить первого сотрудника
              </button>
            </div>
          ` : `
            <div class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th style="width: 60px;">#</th>
                    <th>ФИО</th>
                    <th>Должность</th>
                    <th class="requires-edit" style="width: 110px;">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  ${employeeRows.map((emp, idx) => `
                    <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.04, 0.5)}s both;">
                      <td><span class="text-muted">${idx + 1}</span></td>
                      <td>
                        <div class="d-flex align-items-center gap-2">
                          <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6, #1D4ED8); display: flex; align-items: center; justify-content: center; color: white; font-size: 0.8rem; font-weight: 600;">
                            ${esc(getInitials(emp.full_name))}
                          </div>
                          <strong>${esc(emp.full_name)}</strong>
                        </div>
                      </td>
                      <td class="text-muted">${esc(emp.position)}</td>
                      <td class="requires-edit">
                        <div class="table-actions">
                          <button class="btn btn-sm btn-primary" title="Изменить" onclick="showEditEmployeeModal(${emp.id})">
                            <i class="bi bi-pencil"></i>
                          </button>
                          <button class="btn btn-sm btn-danger requires-admin" title="Удалить" onclick="deleteEmployee(${emp.id})">
                            <i class="bi bi-trash"></i>
                          </button>
                        </div>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </div>
      </div>
    `;
  } catch (error) {
    content.innerHTML = `
      <div class="alert alert-danger">
        <i class="bi bi-exclamation-triangle"></i>
        Ошибка загрузки сотрудников: ${esc(error.message)}
      </div>
    `;
  }
}

function showAddEmployeeModalInList() {
  // Список обновляется только после успешного сохранения
  showAddEmployeeModal(loadEmployees);
}

function showEditEmployeeModal(id) {
  const emp = employeeRows.find(e => e.id === id);
  if (!emp) return;
  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
  document.getElementById('modalTitle').textContent = 'Изменить сотрудника';
  document.getElementById('modalBody').innerHTML = `
    <form id="editEmployeeForm">
      <div class="mb-3">
        <label class="form-label">ФИО *</label>
        <input type="text" class="form-control" name="full_name" value="${esc(emp.full_name)}" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Должность *</label>
        <input type="text" class="form-control" name="position" value="${esc(emp.position)}" required>
      </div>
      <div class="text-end">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
        <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить</button>
      </div>
    </form>
  `;
  document.getElementById('editEmployeeForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      await API.updateEmployee(id, data);
      showAlert('Сотрудник сохранён', 'success');
      modal.hide();
      loadEmployees();
    } catch (error) {
      showAlert('Ошибка: ' + error.message, 'danger');
    }
  });
  modal.show();
}

async function deleteEmployee(id) {
  const emp = employeeRows.find(e => e.id === id);
  if (!emp || !confirm(`Удалить сотрудника «${emp.full_name}»?`)) return;
  try {
    await API.deleteEmployee(id);
    showAlert('Сотрудник удалён', 'success');
    loadEmployees();
  } catch (error) {
    showAlert(error.message, 'danger');
  }
}
