let teamBlockRowSeq = 0;

const settingsDataEl = document.getElementById('settingsData');
const settingsInit = settingsDataEl ? JSON.parse(settingsDataEl.textContent) : {};
let teamsData = settingsInit.teams || [];

function addTeamBlockRow(name, shiftDays) {
    const list = document.getElementById('teamBlocksList');
    const rowId = 'blockRow_' + (teamBlockRowSeq++);
    const row = document.createElement('div');
    row.className = 'team-block-row';
    row.id = rowId;
    row.innerHTML = `
        <input type="text" class="block-name-input" placeholder="Название блока (например: ГФ, Б1)" value="${name ? name.replace(/"/g, '&quot;') : ''}">
        <input type="number" class="block-shift-input" placeholder="Сдвиг, дни" value="${shiftDays !== undefined && shiftDays !== null ? shiftDays : 0}">
        <button type="button" class="btn btn-danger btn-sm btn-remove-block" onclick="document.getElementById('${rowId}').remove()">🗑️</button>
    `;
    list.appendChild(row);
}

function collectTeamBlocks() {
    const rows = document.querySelectorAll('#teamBlocksList .team-block-row');
    const blocks = [];
    rows.forEach(row => {
        const name = row.querySelector('.block-name-input').value.trim();
        const shiftRaw = row.querySelector('.block-shift-input').value;
        if (!name) return;
        const shift_days = parseInt(shiftRaw, 10) || 0;
        blocks.push({name: name, shift_days: shift_days});
    });
    return blocks;
}

function openTeamModal(teamId) {
    const modal = document.getElementById('teamModal');
    const title = document.getElementById('teamModalTitle');
    const teamIdField = document.getElementById('teamId');
    const nameField = document.getElementById('teamNameInput');
    const saveBtn = document.getElementById('saveTeamBtn');
    const updateBtn = document.getElementById('updateTeamBtn');
    const blocksList = document.getElementById('teamBlocksList');

    blocksList.innerHTML = '';
    teamIdField.value = teamId || '';

    if (teamId) {
        const team = teamsData.find(t => t.id === teamId);
        title.textContent = 'Редактирование команды';
        nameField.value = team ? team.name : '';
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';

        const renderBlocks = (blocks) => {
            if (blocks && blocks.length) {
                blocks.forEach(b => addTeamBlockRow(b.name, b.shift_days));
            } else {
                addTeamBlockRow();
            }
        };

        if (team) {
            renderBlocks(team.blocks);
        } else {
            // На случай, если локальный кэш не успел загрузиться
            fetch(`/api/teams/${teamId}`)
                .then(response => response.json())
                .then(data => {
                    nameField.value = data.name || '';
                    renderBlocks(data.blocks);
                });
        }
    } else {
        title.textContent = 'Добавить команду';
        nameField.value = '';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
        addTeamBlockRow();
    }

    modal.style.display = 'flex';
}

function saveTeam(event) {
    event.preventDefault();

    const teamId = document.getElementById('teamId').value;
    const name = document.getElementById('teamNameInput').value.trim();
    const blocks = collectTeamBlocks();

    if (!name) {
        alert('Введите название команды');
        return;
    }

    const url = teamId ? `/api/teams/${teamId}` : '/api/teams';
    const method = teamId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, blocks: blocks})
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(error => {
            console.error('Error saving team:', error);
            alert('Ошибка при сохранении команды');
        });
}

function deleteTeam(teamId) {
    if (!confirm('Удалить команду? Все связанные данные будут удалены!')) return;

    fetch(`/api/teams/${teamId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении команды');
            }
        })
        .catch(error => {
            console.error('Error deleting team:', error);
            alert('Ошибка при удалении команды');
        });
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

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
        body: JSON.stringify({
            last_name: lastName,
            first_name: firstName,
            middle_name: middleName || null
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            }
        })
        .catch(error => {
            console.error('Error saving employee:', error);
            alert('Ошибка при сохранении сотрудника');
        });
}

function deleteEmployee(employeeId) {
    if (!confirm('Удалить сотрудника?')) return;

    fetch(`/api/employees/${employeeId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Ошибка при удалении сотрудника');
            }
        })
        .catch(error => {
            console.error('Error deleting employee:', error);
            alert('Ошибка при удалении сотрудника');
        });
}

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
