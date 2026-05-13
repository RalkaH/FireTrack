// locations.js — страница "Места"

async function loadLocations() {
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="loading">
      <i class="bi bi-arrow-clockwise"></i>
      <p>Загрузка мест...</p>
    </div>
  `;

  try {
    const locations = await API.getLocations();

    content.innerHTML = `
      <!-- Page Header -->
      <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
        <h2><i class="bi bi-geo-alt"></i> Места размещения</h2>
        <button class="btn btn-primary" onclick="showAddLocationModalInList()">
          <i class="bi bi-plus-circle"></i> Добавить место
        </button>
      </div>

      <!-- Stats -->
      <div class="d-flex gap-3 mb-3">
        <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6;">
          <i class="bi bi-geo-alt me-1"></i> Всего: ${locations.length}
        </span>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul"></i> Список мест
        </div>
        <div class="card-body p-0">
          ${locations.length === 0 ? `
            <div class="empty-state">
              <i class="bi bi-geo-alt"></i>
              <p>Места пока не добавлены</p>
              <button class="btn btn-primary" onclick="showAddLocationModalInList()">
                <i class="bi bi-plus-circle"></i> Добавить первое место
              </button>
            </div>
          ` : `
            <div class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th style="width: 60px;">#</th>
                    <th>Название</th>
                    <th>Описание</th>
                  </tr>
                </thead>
                <tbody>
                  ${locations.map((loc, idx) => `
                    <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.04, 0.5)}s both;">
                      <td><span class="text-muted">${idx + 1}</span></td>
                      <td>
                        <strong>${loc.name}</strong>
                      </td>
                      <td class="text-muted">${loc.description || '<span class="text-muted" style="font-style: italic;">Нет описания</span>'}</td>
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
        Ошибка загрузки мест: ${error.message}
      </div>
    `;
  }
}

function showAddLocationModalInList() {
  showAddLocationModal();
  const form = document.getElementById('locationForm');
  if (form) {
    form.addEventListener('submit', () => {
      setTimeout(loadLocations, 500);
    }, { once: true });
  }
}
