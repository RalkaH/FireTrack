// employees.js — страница "Сотрудники"

async function loadEmployees() {
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="loading">
      <i class="bi bi-arrow-clockwise"></i>
      <p>Загрузка сотрудников...</p>
    </div>
  `;

  try {
    const employees = await API.getEmployees();

    content.innerHTML = `
      <!-- Page Header -->
      <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
        <h2><i class="bi bi-people"></i> Сотрудники</h2>
        <button class="btn btn-primary" onclick="showAddEmployeeModalInList()">
          <i class="bi bi-person-plus"></i> Добавить сотрудника
        </button>
      </div>

      <!-- Stats -->
      <div class="d-flex gap-3 mb-3">
        <span class="badge" style="background: rgba(16,185,129,0.1); color: #10B981;">
          <i class="bi bi-people me-1"></i> Всего: ${employees.length}
        </span>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul"></i> Список сотрудников
        </div>
        <div class="card-body p-0">
          ${employees.length === 0 ? `
            <div class="empty-state">
              <i class="bi bi-people"></i>
              <p>Сотрудники пока не добавлены</p>
              <button class="btn btn-primary" onclick="showAddEmployeeModalInList()">
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
                  </tr>
                </thead>
                <tbody>
                  ${employees.map((emp, idx) => `
                    <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.04, 0.5)}s both;">
                      <td><span class="text-muted">${idx + 1}</span></td>
                      <td>
                        <div class="d-flex align-items-center gap-2">
                          <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #3B82F6, #1D4ED8); display: flex; align-items: center; justify-content: center; color: white; font-size: 0.8rem; font-weight: 600;">
                            ${emp.full_name.split(' ').map(n => n[0]).join('').substring(0, 2)}
                          </div>
                          <strong>${emp.full_name}</strong>
                        </div>
                      </td>
                      <td class="text-muted">${emp.position}</td>
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
        Ошибка загрузки сотрудников: ${error.message}
      </div>
    `;
  }
}

function showAddEmployeeModalInList() {
  showAddEmployeeModal();
  const form = document.getElementById('employeeForm');
  if (form) {
    form.addEventListener('submit', () => {
      setTimeout(loadEmployees, 500);
    }, { once: true });
  }
}
