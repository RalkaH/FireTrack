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
      <div class="row mb-3">
        <div class="col-12 d-flex justify-content-between align-items-center">
          <h2><i class="bi bi-people me-2"></i>Сотрудники</h2>
          <button class="btn btn-primary" onclick="showAddEmployeeModalInList()">
            <i class="bi bi-person-plus"></i> Добавить сотрудника
          </button>
        </div>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul me-1"></i> Список сотрудников
        </div>
        <div class="card-body">
          ${employees.length === 0 ? `
            <p class="text-muted mb-0">Сотрудники пока не добавлены.</p>
          ` : `
            <div class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>ФИО</th>
                    <th>Должность</th>
                  </tr>
                </thead>
                <tbody>
                  ${employees.map((emp, idx) => `
                    <tr>
                      <td>${idx + 1}</td>
                      <td>${emp.full_name}</td>
                      <td>${emp.position}</td>
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
