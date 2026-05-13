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
      <div class="row mb-3">
        <div class="col-12 d-flex justify-content-between align-items-center">
          <h2><i class="bi bi-geo-alt me-2"></i>Места размещения</h2>
          <button class="btn btn-primary" onclick="showAddLocationModalInList()">
            <i class="bi bi-plus-circle"></i> Добавить место
          </button>
        </div>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul me-1"></i> Список мест
        </div>
        <div class="card-body">
          ${locations.length === 0 ? `
            <p class="text-muted mb-0">Места пока не добавлены.</p>
          ` : `
            <div class="table-responsive">
              <table class="table table-hover mb-0">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Название</th>
                    <th>Описание</th>
                  </tr>
                </thead>
                <tbody>
                  ${locations.map((loc, idx) => `
                    <tr>
                      <td>${idx + 1}</td>
                      <td>${loc.name}</td>
                      <td>${loc.description || ''}</td>
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

// отдельная обёртка, чтобы после сохранения обновлять список
function showAddLocationModalInList() {
  const oldHandler = showAddLocationModal;
  showAddLocationModal();        // откроет твой уже существующий модал

  // перехватим submit: после успешного добавления перезагрузим список
  const form = document.getElementById('locationForm');
  if (form) {
    form.addEventListener('submit', () => {
      setTimeout(loadLocations, 500);
    }, { once: true });
  }
}
