// locations.js — страница "Места"

let locationRows = [];

async function loadLocations() {
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="loading">
      <i class="bi bi-arrow-clockwise"></i>
      <p>Загрузка мест...</p>
    </div>
  `;

  try {
    locationRows = await API.getLocations();

    content.innerHTML = `
      <!-- Page Header -->
      <div class="page-header d-flex justify-content-between align-items-center flex-wrap gap-3">
        <h2><i class="bi bi-geo-alt"></i> Места размещения</h2>
        <button class="btn btn-primary requires-edit" onclick="showAddLocationModalInList()">
          <i class="bi bi-plus-circle"></i> Добавить место
        </button>
      </div>

      <!-- Stats -->
      <div class="d-flex gap-3 mb-3">
        <span class="badge" style="background: rgba(59,130,246,0.1); color: #3B82F6;">
          <i class="bi bi-geo-alt me-1"></i> Всего: ${locationRows.length}
        </span>
      </div>

      <div class="card section-card">
        <div class="card-header">
          <i class="bi bi-list-ul"></i> Список мест
        </div>
        <div class="card-body p-0">
          ${locationRows.length === 0 ? `
            <div class="empty-state">
              <i class="bi bi-geo-alt"></i>
              <p>Места пока не добавлены</p>
              <button class="btn btn-primary requires-edit" onclick="showAddLocationModalInList()">
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
                    <th class="requires-edit" style="width: 110px;">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  ${locationRows.map((loc, idx) => `
                    <tr style="animation: fadeInUp 0.25s ease-out ${Math.min(idx * 0.04, 0.5)}s both;">
                      <td><span class="text-muted">${idx + 1}</span></td>
                      <td>
                        <strong>${esc(loc.name)}</strong>
                      </td>
                      <td class="text-muted">${esc(loc.description) || '<span class="text-muted" style="font-style: italic;">Нет описания</span>'}</td>
                      <td class="requires-edit">
                        <div class="table-actions">
                          <button class="btn btn-sm btn-primary" title="Изменить" onclick="showEditLocationModal(${loc.id})">
                            <i class="bi bi-pencil"></i>
                          </button>
                          <button class="btn btn-sm btn-danger requires-admin" title="Удалить" onclick="deleteLocation(${loc.id})">
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
        Ошибка загрузки мест: ${esc(error.message)}
      </div>
    `;
  }
}

function showAddLocationModalInList() {
  // Список обновляется только после успешного сохранения
  showAddLocationModal(loadLocations);
}

function showEditLocationModal(id) {
  const loc = locationRows.find(l => l.id === id);
  if (!loc) return;
  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('formModal'));
  document.getElementById('modalTitle').textContent = 'Изменить место';
  document.getElementById('modalBody').innerHTML = `
    <form id="editLocationForm">
      <div class="mb-3">
        <label class="form-label">Название места *</label>
        <input type="text" class="form-control" name="name" value="${esc(loc.name)}" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Описание</label>
        <textarea class="form-control" name="description" rows="3">${esc(loc.description)}</textarea>
      </div>
      <div class="text-end">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
        <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Сохранить</button>
      </div>
    </form>
  `;
  document.getElementById('editLocationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      await API.updateLocation(id, data);
      showAlert('Место сохранено', 'success');
      modal.hide();
      loadLocations();
    } catch (error) {
      showAlert('Ошибка: ' + error.message, 'danger');
    }
  });
  modal.show();
}

async function deleteLocation(id) {
  const loc = locationRows.find(l => l.id === id);
  if (!loc || !confirm(`Удалить место «${loc.name}»?`)) return;
  try {
    await API.deleteLocation(id);
    showAlert('Место удалено', 'success');
    loadLocations();
  } catch (error) {
    showAlert(error.message, 'danger');
  }
}
