const settingsDataEl = document.getElementById('settingsData');
const settingsInit = settingsDataEl ? JSON.parse(settingsDataEl.textContent) : {};
let teamsData = settingsInit.teams || [];
let blocksData = settingsInit.blocks || [];
let templatesData = settingsInit.block_templates || [];

// === КОМАНДЫ ===

function renderTeamTemplatesCheckboxes(selectedIds) {
    const container = document.getElementById('teamTemplatesList');
    if (!templatesData.length) {
        container.innerHTML = '<span style="color:#6c757d;font-size:0.9em;">Нет шаблонов. Создайте шаблон в разделе «Шаблоны блоков».</span>';
        return;
    }
    container.innerHTML = templatesData.map(t => `
        <label class="checkbox-item">
            <input type="checkbox" class="team-template-checkbox" value="${t.id}"${selectedIds.includes(t.id) ? ' checked' : ''}>
            ${t.name}
        </label>
    `).join('');
}

function collectTeamTemplates() {
    return Array.from(document.querySelectorAll('#teamTemplatesList .team-template-checkbox'))
        .filter(cb => cb.checked)
        .map(cb => parseInt(cb.value));
}

function openTeamModal(teamId) {
    const modal = document.getElementById('teamModal');
    const title = document.getElementById('teamModalTitle');
    const teamIdField = document.getElementById('teamId');
    const nameField = document.getElementById('teamNameInput');
    const saveBtn = document.getElementById('saveTeamBtn');
    const updateBtn = document.getElementById('updateTeamBtn');

    teamIdField.value = teamId || '';

    if (teamId) {
        const team = teamsData.find(t => t.id === teamId);
        title.textContent = 'Редактирование команды';
        nameField.value = team ? team.name : '';
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';

        const selectedIds = team ? (team.templates || []).map(t => t.id) : [];
        renderTeamTemplatesCheckboxes(selectedIds);

        if (!team) {
            fetch(`/api/teams/${teamId}`)
                .then(r => r.json())
                .then(data => {
                    nameField.value = data.name || '';
                    renderTeamTemplatesCheckboxes(data.template_ids || []);
                });
        }
    } else {
        title.textContent = 'Добавить команду';
        nameField.value = '';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
        renderTeamTemplatesCheckboxes([]);
    }

    modal.style.display = 'flex';
}

function saveTeam(event) {
    event.preventDefault();

    const teamId = document.getElementById('teamId').value;
    const name = document.getElementById('teamNameInput').value.trim();
    const template_ids = collectTeamTemplates();

    if (!name) {
        alert('Введите название команды');
        return;
    }

    const url = teamId ? `/api/teams/${teamId}` : '/api/teams';
    const method = teamId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, template_ids: template_ids})
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(() => alert('Ошибка при сохранении команды'));
}

function deleteTeam(teamId) {
    if (!confirm('Удалить команду? Все связанные данные будут удалены!')) return;

    fetch(`/api/teams/${teamId}`, {method: 'DELETE'})
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении команды');
            }
        })
        .catch(() => alert('Ошибка при удалении команды'));
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// === СОТРУДНИКИ ===

let employeesData = settingsInit.employees || [];

function openEmployeeModal(employeeId) {
    const modal = document.getElementById('employeeModal');
    const title = document.getElementById('employeeModalTitle');
    const idField = document.getElementById('employeeId');
    const lastNameField = document.getElementById('employeeLastName');
    const firstNameField = document.getElementById('employeeFirstName');
    const middleNameField = document.getElementById('employeeMiddleName');
    const saveBtn = document.getElementById('saveEmployeeBtn');
    const updateBtn = document.getElementById('updateEmployeeBtn');

    idField.value = employeeId || '';

    if (employeeId) {
        const emp = employeesData.find(e => e.id === employeeId);
        title.textContent = 'Редактирование сотрудника';
        lastNameField.value = emp ? emp.last_name : '';
        firstNameField.value = emp ? emp.first_name : '';
        middleNameField.value = emp ? (emp.middle_name || '') : '';
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';
    } else {
        title.textContent = 'Добавить сотрудника';
        lastNameField.value = '';
        firstNameField.value = '';
        middleNameField.value = '';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
    }

    modal.style.display = 'flex';
}

function saveEmployee(event) {
    event.preventDefault();

    const employeeId = document.getElementById('employeeId').value;
    const lastName = document.getElementById('employeeLastName').value.trim();
    const firstName = document.getElementById('employeeFirstName').value.trim();
    const middleName = document.getElementById('employeeMiddleName').value.trim();

    if (!lastName || !firstName) {
        alert('Введите фамилию и имя сотрудника');
        return;
    }

    const url = employeeId ? `/api/employees/${employeeId}` : '/api/employees';
    const method = employeeId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({last_name: lastName, first_name: firstName, middle_name: middleName || null})
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(() => alert('Ошибка при сохранении сотрудника'));
}

function deleteEmployee(employeeId) {
    if (!confirm('Удалить сотрудника?')) return;

    fetch(`/api/employees/${employeeId}`, {method: 'DELETE'})
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении сотрудника');
            }
        })
        .catch(() => alert('Ошибка при удалении сотрудника'));
}

// === БЛОКИ ===

function createBlock() {
    const input = document.getElementById('newBlockName');
    const name = input.value.trim();
    if (!name) {
        alert('Введите название блока');
        return;
    }

    fetch('/api/blocks', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name})
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(() => alert('Ошибка при создании блока'));
}

function deleteBlock(blockId) {
    if (!confirm('Удалить блок? Он будет удалён из всех шаблонов.')) return;

    fetch(`/api/blocks/${blockId}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении блока');
            }
        })
        .catch(() => alert('Ошибка при удалении блока'));
}

// === ШАБЛОНЫ БЛОКОВ ===

let templateBlockRowSeq = 0;

function addTemplateBlockRow(blockId, shiftDays) {
    const list = document.getElementById('templateBlocksList');
    const rowId = 'tmplBlockRow_' + (templateBlockRowSeq++);
    const row = document.createElement('div');
    row.className = 'team-block-row';
    row.id = rowId;

    const options = blocksData.map(b =>
        `<option value="${b.id}"${b.id === blockId ? ' selected' : ''}>${b.name}</option>`
    ).join('');

    row.innerHTML = `
        <select class="tmpl-block-select">${options}</select>
        <input type="number" class="block-shift-input" placeholder="Сдвиг, дни" value="${shiftDays !== undefined && shiftDays !== null ? shiftDays : 0}">
        <button type="button" class="btn btn-danger btn-sm btn-remove-block" onclick="document.getElementById('${rowId}').remove()">🗑️</button>
    `;
    list.appendChild(row);
}

function collectTemplateEntries() {
    const rows = document.querySelectorAll('#templateBlocksList .team-block-row');
    const entries = [];
    rows.forEach(row => {
        const select = row.querySelector('.tmpl-block-select');
        const shiftInput = row.querySelector('.block-shift-input');
        if (!select || !select.value) return;
        entries.push({
            block_id: parseInt(select.value),
            shift_days: parseInt(shiftInput.value, 10) || 0
        });
    });
    return entries;
}

function openTemplateModal(templateId) {
    const modal = document.getElementById('templateModal');
    const title = document.getElementById('templateModalTitle');
    const idField = document.getElementById('templateId');
    const nameField = document.getElementById('templateNameInput');
    const saveBtn = document.getElementById('saveTemplateBtn');
    const updateBtn = document.getElementById('updateTemplateBtn');
    const list = document.getElementById('templateBlocksList');

    list.innerHTML = '';
    templateBlockRowSeq = 0;
    idField.value = templateId || '';

    if (templateId) {
        const tmpl = templatesData.find(t => t.id === templateId);
        title.textContent = 'Редактирование шаблона';
        nameField.value = tmpl ? tmpl.name : '';
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';

        const renderEntries = (blocks) => {
            if (blocks && blocks.length) {
                blocks.forEach(b => addTemplateBlockRow(b.id, b.shift_days));
            } else {
                addTemplateBlockRow();
            }
        };

        if (tmpl) {
            renderEntries(tmpl.blocks);
        } else {
            fetch(`/api/block-templates/${templateId}`)
                .then(r => r.json())
                .then(data => {
                    nameField.value = data.name || '';
                    renderEntries(data.blocks);
                });
        }
    } else {
        title.textContent = 'Добавить шаблон';
        nameField.value = '';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
        addTemplateBlockRow();
    }

    modal.style.display = 'flex';
}

function saveTemplate(event) {
    event.preventDefault();

    const templateId = document.getElementById('templateId').value;
    const name = document.getElementById('templateNameInput').value.trim();
    const entries = collectTemplateEntries();

    if (!name) {
        alert('Введите название шаблона');
        return;
    }

    const url = templateId ? `/api/block-templates/${templateId}` : '/api/block-templates';
    const method = templateId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, entries: entries})
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(() => alert('Ошибка при сохранении шаблона'));
}

function deleteTemplate(templateId) {
    if (!confirm('Удалить шаблон?')) return;

    fetch(`/api/block-templates/${templateId}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении шаблона');
            }
        })
        .catch(() => alert('Ошибка при удалении шаблона'));
}

// === ДНИ ФРИЗА ===

const MONTH_NAMES = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                     'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const CURRENT_YEAR = new Date().getFullYear();
let allFreezeDays = settingsInit.freeze_days || [];
let modalMonth = null;
let modalSelectedDays = new Set();

function buildCalendarTable(year, month, markedDays, interactive) {
    const daysInMonth = new Date(year, month, 0).getDate();
    let firstDow = new Date(year, month - 1, 1).getDay();
    firstDow = firstDow === 0 ? 6 : firstDow - 1;

    const cls = 'freeze-calendar' + (interactive ? ' interactive' : '');
    let html = `<table class="${cls}"><thead><tr>`;
    ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].forEach(d => html += `<th>${d}</th>`);
    html += '</tr></thead><tbody><tr>';

    for (let i = 0; i < firstDow; i++) html += '<td></td>';

    const today = new Date();

    for (let d = 1; d <= daysInMonth; d++) {
        const col = (firstDow + d - 1) % 7;
        if (col === 0 && d > 1) html += '</tr><tr>';

        const isMarked = markedDays.has(d);
        const isWeekend = col === 5 || col === 6;
        const isToday = year === today.getFullYear() && month === (today.getMonth() + 1) && d === today.getDate();
        const tdClasses = [isWeekend ? 'cal-weekend' : '', isToday ? 'cal-today' : ''].filter(Boolean).join(' ');

        if (interactive) {
            const selClass = isMarked ? ' selected' : '';
            html += `<td data-day="${d}" class="${tdClasses}" onclick="toggleModalDay(${d})">` +
                    `<span class="cal-day-inner${selClass}">${d}</span></td>`;
        } else {
            const markClass = isMarked ? ' freeze-day-marked' : '';
            html += `<td class="${tdClasses}"><span class="cal-day-inner${markClass}">${d}</span></td>`;
        }
    }

    const lastCol = (firstDow + daysInMonth - 1) % 7;
    for (let i = lastCol + 1; i < 7; i++) html += '<td></td>';
    html += '</tr></tbody></table>';
    return html;
}

function getFreezeDaysByMonth() {
    const byMonth = {};
    const prefix = String(CURRENT_YEAR);
    allFreezeDays.forEach(dateStr => {
        if (!dateStr.startsWith(prefix)) return;
        const month = parseInt(dateStr.substring(5, 7), 10);
        const day = parseInt(dateStr.substring(8, 10), 10);
        if (!byMonth[month]) byMonth[month] = new Set();
        byMonth[month].add(day);
    });
    return byMonth;
}

function renderFreezeMonthsGrid() {
    const grid = document.getElementById('freezeMonthsGrid');
    if (!grid) return;
    const byMonth = getFreezeDaysByMonth();
    const months = Object.keys(byMonth).map(Number).sort((a, b) => a - b);

    if (months.length === 0) {
        grid.innerHTML = '<p style="color:#6c757d;">Нет дней фриза</p>';
        return;
    }

    let html = '';
    months.forEach(m => {
        const days = byMonth[m];
        html += '<div class="freeze-month-card">';
        html += '<div class="freeze-month-header">';
        html += `<span>${MONTH_NAMES[m - 1]}</span>`;
        html += '<div>';
        html += `<button class="btn btn-primary btn-sm" onclick="openFreezeMonthModal(${m})">✏️</button> `;
        html += `<button class="btn btn-danger btn-sm" onclick="deleteFreezeMonth(${m})">🗑️</button>`;
        html += '</div></div>';
        html += buildCalendarTable(CURRENT_YEAR, m, days, false);
        html += '</div>';
    });
    grid.innerHTML = html;
}

function openFreezeMonthModal(month) {
    const selectorEl = document.getElementById('freezeMonthSelector');
    const titleEl = document.getElementById('freezeMonthModalTitle');
    const byMonth = getFreezeDaysByMonth();

    if (month === null) {
        titleEl.textContent = 'Добавить дни фриза';
        const usedMonths = new Set(Object.keys(byMonth).map(Number));
        let defaultMonth = null;
        for (let m = 1; m <= 12; m++) {
            if (!usedMonths.has(m)) { defaultMonth = m; break; }
        }
        if (defaultMonth === null) defaultMonth = 1;

        let selectHtml = '<label>Месяц</label><select id="freezeMonthSelect" onchange="onFreezeMonthSelectChange()">';
        for (let m = 1; m <= 12; m++) {
            const sel = m === defaultMonth ? ' selected' : '';
            selectHtml += `<option value="${m}"${sel}>${MONTH_NAMES[m - 1]}</option>`;
        }
        selectHtml += '</select>';
        selectorEl.innerHTML = selectHtml;
        selectorEl.style.display = '';

        modalMonth = defaultMonth;
        modalSelectedDays = new Set();
    } else {
        titleEl.textContent = 'Редактирование: ' + MONTH_NAMES[month - 1];
        selectorEl.style.display = 'none';
        selectorEl.innerHTML = '';
        modalMonth = month;
        modalSelectedDays = new Set(byMonth[month] || []);
    }

    renderModalCalendar();
    document.getElementById('freezeMonthModal').style.display = 'flex';
}

function onFreezeMonthSelectChange() {
    const sel = document.getElementById('freezeMonthSelect');
    modalMonth = parseInt(sel.value, 10);
    const byMonth = getFreezeDaysByMonth();
    modalSelectedDays = new Set(byMonth[modalMonth] || []);
    renderModalCalendar();
}

function renderModalCalendar() {
    document.getElementById('freezeModalCalendar').innerHTML =
        buildCalendarTable(CURRENT_YEAR, modalMonth, modalSelectedDays, true);
}

function toggleModalDay(day) {
    if (modalSelectedDays.has(day)) {
        modalSelectedDays.delete(day);
    } else {
        modalSelectedDays.add(day);
    }
    const cell = document.querySelector(`#freezeModalCalendar td[data-day="${day}"]`);
    if (cell) {
        const span = cell.querySelector('.cal-day-inner');
        if (span) span.classList.toggle('selected');
    }
}

function saveFreezeMonth() {
    const days = Array.from(modalSelectedDays).sort((a, b) => a - b);
    fetch('/api/freeze-days/month', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({year: CURRENT_YEAR, month: modalMonth, days: days})
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) location.reload();
            else alert('Ошибка при сохранении');
        })
        .catch(() => alert('Ошибка при сохранении'));
}

function deleteFreezeMonth(month) {
    if (!confirm(`Удалить все дни фриза за ${MONTH_NAMES[month - 1]}?`)) return;
    fetch(`/api/freeze-days/month/${CURRENT_YEAR}/${month}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
            if (data.success) location.reload();
            else alert('Ошибка при удалении');
        })
        .catch(() => alert('Ошибка при удалении'));
}

renderFreezeMonthsGrid();
