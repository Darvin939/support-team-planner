let teamId = null;
let freezeDays = [];
let teamBlocks = [];

let tasksData = [];
let assignmentsData = [];
let currentDateRange = {start: null, end: null};

let currentPage = 1;
const PAGE_SIZE = 20;
let totalTasksCount = 0;
let searchDebounceTimer = null;
let showCompleted = false;

const TASK_STATUS_LABELS = {
    new: 'Новый',
    ready: 'К планированию',
    in_progress: 'В работе',
    done: 'Выполнено',
    cancelled: 'Отменено'
};

const VALID_TASK_TRANSITIONS = {
    new: ['ready', 'in_progress', 'cancelled'],
    ready: ['in_progress', 'cancelled'],
    in_progress: ['done', 'cancelled'],
};

// Состояние автоназначения по графику команды
let autoAssignDates = {};      // blockId -> dateStr
let autoAssignBaseDate = null;
let autoAssignSelected = null; // id блока, "взятого в руки" для перемещения

const statusMap = {
    'new': 'Новый',
    'planned': 'Запланировано',
    'rollback': 'Откат',
    'success': 'Успешно'
};

// Инициализация
document.addEventListener('DOMContentLoaded', function () {
    const dataEl = document.getElementById('planningData');
    if (dataEl) {
        const initData = JSON.parse(dataEl.textContent);
        teamId = initData.team_id;
        freezeDays = initData.freeze_days || [];
        teamBlocks = initData.team_blocks || [];
        saveTeamId(teamId);
    }

    const saved = getSavedDateRange();
    if (saved.from) document.getElementById('dateFrom').value = saved.from;
    if (saved.to) document.getElementById('dateTo').value = saved.to;

    initializeTable();
    setupDragScroll();
    setupAutoScheduleDragScroll();

    // Загрузка данных
    loadData();

    // Обработчики для фильтров
    document.getElementById('dateFrom').addEventListener('change', () => { currentPage = 1; loadData(); });
    document.getElementById('dateTo').addEventListener('change', () => { currentPage = 1; loadData(); });
    document.getElementById('searchText').addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => { currentPage = 1; loadData(); }, 300);
    });
    // document.getElementById('criticalityDropdown').addEventListener('change', applyFilters);
    // document.getElementById('statusDropdown').addEventListener('change', applyFilters);

    // При смене даты назначения пересчитываем автографик (если он включен)
    document.getElementById('assignmentDate').addEventListener('change', function () {
        if (document.getElementById('autoAssignToggle').checked) {
            autoAssignSelected = null;
            recomputeAutoAssignSchedule();
            renderAutoScheduleTable();
        }
    });
});

function dropdownOnChange(dropdownId) {
    updateDropdownLabel(dropdownId);
    applyFilters();
}

function initializeTable() {
    // Устанавливаем начальный период
    const dateFrom = new Date(document.getElementById('dateFrom').value);
    const dateTo = new Date(document.getElementById('dateTo').value);
    currentDateRange.start = dateFrom;
    currentDateRange.end = dateTo;

    updateDropdownLabel('criticalityDropdown');
    updateDropdownLabel('statusDropdown');
}

function scrollToToday() {
    const wrapper = document.getElementById('tableWrapper');
    const todayTh = document.querySelector('#tableHeader th.current');
    const taskTh = document.querySelector('#tableHeader th:nth-child(1)');
    if (!wrapper || !todayTh) return;
    wrapper.scrollLeft = todayTh.offsetLeft
        - wrapper.offsetWidth / 2
        + todayTh.offsetWidth / 2
        - taskTh.offsetWidth / 2;
}

function loadData() {
    clampDateRange('dateFrom', 'dateTo');

    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;

    if (!dateFrom || !dateTo) return;

    saveDateRange(dateFrom, dateTo);

    const search = document.getElementById('searchText').value.trim();
    const offset = (currentPage - 1) * PAGE_SIZE;

    // Загружаем задачи
    fetch(`/api/tasks/${teamId}?offset=${offset}&limit=${PAGE_SIZE}&search=${encodeURIComponent(search)}&show_completed=${showCompleted}`)
        .then(response => response.json())
        .then(data => {
            tasksData = data.tasks;
            totalTasksCount = data.total;
            // Загружаем назначения
            return fetch(`/api/assignments/${teamId}?start_date=${dateFrom}&end_date=${dateTo}`);
        })
        .then(response => response.json())
        .then(data => {
            assignmentsData = data;
            renderTable();
            renderPagination();
            applyFilters();
            scrollToToday();
        })
        .catch(error => console.error('Error loading data:', error));

    loadTodayCounters();
}

function loadTodayCounters() {
    const today = localDateStr(new Date());

    fetch(`/api/active-assignments/${teamId}?start_date=${today}&end_date=${today}`)
        .then(r => r.json())
        .then(data => {
            const statusLabels = {new: 'Новый', planned: 'Запланировано'};
            const critLabels = {high: 'Высокая', medium: 'Средняя', low: 'Низкая'};
            const statusCounts = {new: 0, planned: 0};
            const critCounts = {high: 0, medium: 0, low: 0};

            data.forEach(a => {
                if (statusCounts[a.status] !== undefined) statusCounts[a.status]++;
                if (critCounts[a.criticality] !== undefined) critCounts[a.criticality]++;
            });

            let html = `<span class="counter-item">На сегодня: <b>${data.length}</b></span>`;

            html += `<span class="counter-group-label">Статус:</span>`;
            for (const [key, label] of Object.entries(statusLabels)) {
                html += `<span class="counter-item counter-status-${key}">${label}: <b>${statusCounts[key]}</b></span>`;
            }

            html += `<span class="counter-group-label">Критичность:</span>`;
            for (const [key, label] of Object.entries(critLabels)) {
                html += `<span class="counter-item counter-crit-${key}">${label}: <b>${critCounts[key]}</b></span>`;
            }

            document.getElementById('planningCounters').innerHTML = html;
        })
        .catch(e => console.error('Error loading today counters:', e));
}

function localDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

function renderTable() {
    const dateFrom = new Date(document.getElementById('dateFrom').value);
    const dateTo = new Date(document.getElementById('dateTo').value);
    const dates = [];
    let currentDate = new Date(dateFrom);
    const todayDate = new Date().toDateString();

    while (currentDate <= dateTo) {
        dates.push(new Date(currentDate));
        currentDate.setDate(currentDate.getDate() + 1);
    }

    // Рендерим заголовки
    const header = document.getElementById('tableHeader');
    header.innerHTML = `<th class="task-info-col-header">Работа</th>`;

    dates.forEach(d => {
        const dateStr = d.toISOString().split('T')[0];
        const isWeekend = d.getDay() === 6 || d.getDay() === 0;
        const isFreeze = freezeDays.includes(dateStr);
        const dayLabel = d.getDate().toString().padStart(2, '0') + '.' + (d.getMonth() + 1).toString().padStart(2, '0');

        let className = 'date-col';
        if (isWeekend) className += ' weekend';
        if (d.toDateString() === todayDate) className += ' current';
        if (isFreeze) className += ' freeze';

        // Добавляем data-date атрибут для идентификации даты
        header.innerHTML += `<th class="${className}" data-date="${dateStr}">${dayLabel}</th>`;
    });

    // Рендерим тело таблицы
    const body = document.getElementById('tableBody');
    body.innerHTML = '';

    if (tasksData.length === 0) {
        body.innerHTML = `<tr><td colspan="${dates.length + 1}" class="empty-row">Нет запланированных работ</td></tr>`;
        return;
    }

    tasksData.forEach(task => {
        const row = document.createElement('tr');
        // Добавляем data-task-id для идентификации задачи
        row.dataset.taskId = task.id;
        const taskStatus = task.task_status || 'new';
        if (taskStatus !== 'new') row.classList.add(`task-row-status-${taskStatus}`);

        const critClass = task.criticality === 'high' ? 'criticality-high' :
            task.criticality === 'medium' ? 'criticality-medium' : 'criticality-low';
        const critDisplay = task.criticality === 'high' ? 'В' :
            task.criticality === 'medium' ? 'С' : 'Н';

        const taskAssignments = assignmentsData.filter(a => a.task_id === task.id);
        const allSuccess = taskAssignments.length > 0 && taskAssignments.every(a => a.status === 'success');
        if (allSuccess && taskStatus === 'in_progress') row.classList.add('task-all-success');

        const statusBadge = taskStatus === 'new' ? '' : `<span class="task-status-badge task-status-${taskStatus}">${TASK_STATUS_LABELS[taskStatus] || taskStatus}</span>`;
        const transitions = VALID_TASK_TRANSITIONS[taskStatus] || [];
        const transitionBtns = transitions.map(s => {
            const highlighted = s === 'done' && allSuccess;
            return `<button class="task-status-btn task-status-btn-${s}${highlighted ? ' task-status-btn-highlight' : ''}" onclick="setTaskStatus(${task.id},'${s}')">${TASK_STATUS_LABELS[s]}</button>`;
        }).join('');

        const descBlock = task.description
            ? `<div class="task-info-row-3"><div class="description">${linkify(task.description)}</div></div>`
            : '';

        const isTerminal = taskStatus === 'done' || taskStatus === 'cancelled';
        const editBtn = isTerminal ? '' : `<button class="btn-edit" onclick="openTaskModal(${task.id})" title="Редактировать">✏️</button>`;
        const deleteBtn = isTerminal ? '' : `<button class="btn-delete" onclick="deleteTask(${task.id})" title="Удалить">🗑️</button>`;

        const infoCell = document.createElement('td');
        infoCell.className = 'task-info-col';
        infoCell.innerHTML = `
            <div class="task-info-row-1">
                ${editBtn}
                <span class="criticality-badge ${critClass}">${critDisplay}</span>
                <span class="task-name">${task.name}</span>
            </div>
            <div class="task-info-row-2">
                ${deleteBtn}
                ${statusBadge}${transitionBtns}
            </div>
            ${descBlock}
        `;
        row.appendChild(infoCell);

        // Колонки с датами - убираем onclick, добавляем data атрибуты
        dates.forEach(d => {
            const dateStr = d.toISOString().split('T')[0];
            const isWeekend = d.getDay() === 6 || d.getDay() === 0;
            const isFreeze = freezeDays.includes(dateStr);

            const cell = document.createElement('td');
            cell.className = 'schedule-cell';
            if (isWeekend) cell.classList.add('weekend');
            if (isFreeze) cell.classList.add('freeze');
            if (d.toDateString() === todayDate) cell.classList.add('current');

            // Добавляем data атрибуты для идентификации
            cell.dataset.taskId = task.id;
            cell.dataset.date = dateStr;

            // Ищем назначение
            const assignment = assignmentsData.find(a =>
                a.task_id === task.id && a.date === dateStr
            );

            if (assignment) {
                const statusColor = getStatusColor(assignment.status);
                cell.innerHTML = `
                    <div class="schedule-info ${statusColor}">
                        <span class="schedule-location">${assignment.block || ''}</span>
                        <span class="schedule-status">${getStatusDisplay(assignment.status)}</span>
                        <span class="schedule-comment">${assignment.comment || ''}</span>
                        <span class="schedule-employee">${assignment.employee_name}</span>
                    </div>
                `;
            }

            row.appendChild(cell);
        });

        body.appendChild(row);
    });
}

function applyFilters() {
    const criticalityCheckboxes = document.querySelectorAll('#criticalityDropdown input[type="checkbox"]');
    const criticalityFilter = Array.from(criticalityCheckboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);

    const statusCheckboxes = document.querySelectorAll('#statusDropdown input[type="checkbox"]');
    const statusFilter = Array.from(statusCheckboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);

    const rows = document.querySelectorAll('#tableBody tr');
    let visibleCount = 0;

    rows.forEach(row => {
        if (row.classList.contains('empty-row')) return;

        const nameCell = row.querySelector('.name-col');
        if (!nameCell) return;

        const critCell = row.querySelector('.criticality-col .criticality-badge');
        const critValue = critCell ?
            (critCell.classList.contains('criticality-high') ? 'high' :
                critCell.classList.contains('criticality-medium') ? 'medium' : 'low') : 'medium';

        let matches = true;

        if (criticalityFilter.length > 0) {
            matches = matches && criticalityFilter.includes(critValue);
        }

        if (statusFilter.length > 0) {
            const cells = row.querySelectorAll('.schedule-cell');
            let hasStatusMatch = false;
            cells.forEach(cell => {
                const statusEl = cell.querySelector('.schedule-status');
                if (statusEl) {
                    const status = statusEl.textContent;
                    const statusCode = Object.keys(statusMap).find(key => statusMap[key] === status);
                    if (statusCode && statusFilter.includes(statusCode)) {
                        hasStatusMatch = true;
                    }
                }
            });
            matches = matches && hasStatusMatch;
        }

        row.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
    });

    document.getElementById('visibleTasks').textContent = visibleCount;
    document.getElementById('totalTasks').textContent = totalTasksCount;
}

function renderPagination() {
    const totalPages = Math.ceil(totalTasksCount / PAGE_SIZE);
    const bottom = document.getElementById('pagination');
    const top = document.getElementById('pagination-top');
    if (totalPages <= 1) {
        bottom.innerHTML = '';
        top.innerHTML = '';
        return;
    }

    const pagesToShow = new Set([1, totalPages]);
    for (let p = currentPage - 1; p <= currentPage + 1; p++) {
        if (p > 1 && p < totalPages) pagesToShow.add(p);
    }
    const sorted = [...pagesToShow].sort((a, b) => a - b);

    let html = `<button class="page-btn" onclick="goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>←</button>`;
    let prev = 0;
    sorted.forEach(p => {
        if (prev && p - prev > 1) html += `<span class="page-ellipsis">…</span>`;
        html += `<button class="page-btn${p === currentPage ? ' active' : ''}" onclick="goToPage(${p})">${p}</button>`;
        prev = p;
    });
    html += `<button class="page-btn" onclick="goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>→</button>`;

    bottom.innerHTML = html;
    top.innerHTML = html;
}

function onShowCompletedChange() {
    showCompleted = document.getElementById('showCompleted').checked;
    currentPage = 1;
    loadData();
}

function showToast(taskName, status) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        document.body.appendChild(container);
    }
    while (container.children.length >= 5) container.firstChild.remove();

    const label = TASK_STATUS_LABELS[status] || status;
    const toast = document.createElement('div');
    toast.className = `toast toast-${status}`;
    toast.textContent = `«${taskName}» — ${label}`;
    container.appendChild(toast);

    requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('toast-visible')));

    setTimeout(() => {
        toast.classList.add('toast-hiding');
        toast.addEventListener('transitionend', () => toast.remove(), {once: true});
    }, 4000);
}

function setTaskStatus(taskId, newStatus) {
    fetch(`/api/tasks/${taskId}/status`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({status: newStatus})
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) { alert('Ошибка: ' + data.error); return; }
            if (newStatus === 'done' || newStatus === 'cancelled') {
                const task = tasksData.find(t => t.id === taskId);
                showToast(task ? task.name : `#${taskId}`, newStatus);
                const row = document.querySelector(`tr[data-task-id="${taskId}"]`);
                if (row) {
                    row.classList.add('task-row-fadeout');
                    setTimeout(loadData, 1000);
                } else {
                    loadData();
                }
            } else {
                loadData();
            }
        })
        .catch(() => alert('Ошибка при смене статуса'));
}

function goToPage(page) {
    const totalPages = Math.ceil(totalTasksCount / PAGE_SIZE);
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadData();
}

document.addEventListener('keydown', function (e) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    const tag = document.activeElement.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    e.preventDefault();
    if (e.key === 'ArrowLeft') goToPage(currentPage - 1);
    else goToPage(currentPage + 1);
});

function getStatusColor(status) {
    const colors = {
        'new': 'status-new',
        'planned': 'status-planned',
        'rollback': 'status-rollback',
        'success': 'status-success'
    };
    return colors[status] || 'status-new';
}

function getStatusDisplay(status) {
    const map = {
        'new': 'Новый',
        'planned': 'Запланировано',
        'rollback': 'Откат',
        'success': 'Успешно'
    };
    return map[status] || status;
}

function renderBlockCheckboxes(selectedNames) {
    const container = document.getElementById('assignmentBlockList');
    container.innerHTML = '';

    if (!teamBlocks || teamBlocks.length === 0) {
        container.innerHTML = '<div class="checkbox-item-empty">Не выбрано (у команды нет блоков)</div>';
        return;
    }

    teamBlocks.forEach(block => {
        const checked = selectedNames.includes(block.name) ? 'checked' : '';
        const label = document.createElement('label');
        label.className = 'checkbox-item';
        label.innerHTML = `
            <input type="checkbox" value="${block.name.replace(/"/g, '&quot;')}" ${checked}>
            ${block.name} (сдвиг: ${block.shift_days})
        `;
        container.appendChild(label);
    });
}

function getSelectedBlocks() {
    const checkboxes = document.querySelectorAll('#assignmentBlockList input[type="checkbox"]');
    return Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
}

function addDaysStr(dateStr, days) {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + days);
    return d.toISOString().split('T')[0];
}

function computeAutoAssignDates(baseDateStr) {
    // Сортируем блоки по возрастанию сдвига. При попадании на день фриза
    // блок сдвигается на следующий не-фризовый день, а накопленный сдвиг
    // (offset) применяется и к последующим блокам, чтобы сохранить
    // относительный интервал между ними.
    const sorted = [...teamBlocks].sort((a, b) => a.shift_days - b.shift_days);
    let offset = 0;
    const result = {};

    sorted.forEach(block => {
        let dateStr = addDaysStr(baseDateStr, block.shift_days + offset);
        while (freezeDays.includes(dateStr)) {
            dateStr = addDaysStr(dateStr, 1);
            offset += 1;
        }
        result[block.id] = dateStr;
    });

    return result;
}

function recomputeAutoAssignSchedule() {
    const baseDateStr = document.getElementById('assignmentDate').value;
    if (!baseDateStr) return;
    autoAssignBaseDate = baseDateStr;
    autoAssignDates = computeAutoAssignDates(baseDateStr);
}

function getAutoScheduleDateRange() {
    let maxDate = new Date(autoAssignBaseDate);
    Object.values(autoAssignDates).forEach(dateStr => {
        const d = new Date(dateStr);
        if (d > maxDate) maxDate = d;
    });
    // Небольшой запас дат справа, чтобы можно было вручную подвинуть блок дальше графика
    maxDate.setDate(maxDate.getDate() + 5);

    const dates = [];
    let cur = new Date(autoAssignBaseDate);
    while (cur <= maxDate) {
        dates.push(cur.toISOString().split('T')[0]);
        cur.setDate(cur.getDate() + 1);
    }
    return dates;
}

function renderAutoScheduleTable() {
    const header = document.getElementById('autoScheduleHeader');
    const row = document.getElementById('autoScheduleRow');

    if (!teamBlocks || teamBlocks.length === 0) {
        header.innerHTML = '<th>Блок</th>';
        row.innerHTML = '<td class="checkbox-item-empty">У команды нет блоков раскатки</td>';
        return;
    }

    if (!autoAssignBaseDate) {
        header.innerHTML = '';
        row.innerHTML = '';
        return;
    }

    const dates = getAutoScheduleDateRange();
    const todayStr = new Date().toISOString().split('T')[0];
    const taskId = parseInt(document.getElementById('assignmentTaskId').value);
    const assignmentIdVal = document.getElementById('assignmentId').value;
    const currentAssignmentId = assignmentIdVal ? parseInt(assignmentIdVal) : null;

    let headerHtml = '<th>Блок</th>';
    let rowHtml = '<td class="auto-assign-row-label">Дата</td>';

    dates.forEach(dateStr => {
        const d = new Date(dateStr);
        const isWeekend = d.getDay() === 0 || d.getDay() === 6;
        const isFreeze = freezeDays.includes(dateStr);
        const isToday = dateStr === todayStr;

        let headerCls = 'date-col';
        if (isWeekend) headerCls += ' weekend';
        if (isFreeze) headerCls += ' freeze';
        if (isToday) headerCls += ' current';
        const label = d.getDate().toString().padStart(2, '0') + '.' + (d.getMonth() + 1).toString().padStart(2, '0');
        headerHtml += `<th class="${headerCls}">${label}</th>`;

        let cellCls = 'schedule-cell auto-block-cell';
        if (isWeekend) cellCls += ' weekend';
        if (isFreeze) cellCls += ' freeze';
        if (isToday) cellCls += ' current';

        const existing = assignmentsData.find(a => a.task_id === taskId && a.date === dateStr);
        const isOccupied = existing && existing.id !== currentAssignmentId;
        if (isOccupied) cellCls += ' occupied';

        const blocksHere = teamBlocks.filter(b => autoAssignDates[b.id] === dateStr);
        let badges = '';
        blocksHere.forEach(b => {
            const selectedCls = autoAssignSelected === b.id ? ' selected' : '';
            badges += `<span class="auto-block-badge${selectedCls}" onclick="event.stopPropagation(); pickAutoBlock(${b.id})">${b.name}</span>`;
        });

        rowHtml += `<td class="${cellCls}" onclick="placeAutoBlock('${dateStr}')">${badges}</td>`;
    });

    header.innerHTML = headerHtml;
    row.innerHTML = rowHtml;
}

function pickAutoBlock(blockId) {
    autoAssignSelected = (autoAssignSelected === blockId) ? null : blockId;
    renderAutoScheduleTable();
}

function placeAutoBlock(dateStr) {
    if (autoAssignSelected === null) return;
    autoAssignDates[autoAssignSelected] = dateStr;
    autoAssignSelected = null;
    renderAutoScheduleTable();
}

function setupAutoScheduleDragScroll() {
    const wrapper = document.getElementById('autoScheduleWrapper');
    if (!wrapper || wrapper._dragScrollSetup) return;
    wrapper._dragScrollSetup = true;

    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;
    let dragged = false;

    wrapper.style.cursor = 'grab';

    wrapper.addEventListener('mousedown', function (e) {
        isDown = true;
        dragged = false;
        startX = e.pageX - wrapper.offsetLeft;
        scrollLeft = wrapper.scrollLeft;
    });

    document.addEventListener('mousemove', function (e) {
        if (!isDown) return;
        const x = e.pageX - wrapper.offsetLeft;
        const walk = x - startX;
        if (Math.abs(walk) > 5) {
            dragged = true;
            wrapper.style.cursor = 'grabbing';
            wrapper.style.userSelect = 'none';
            wrapper.scrollLeft = scrollLeft - walk;
        }
    });

    document.addEventListener('mouseup', function () {
        if (!isDown) return;
        isDown = false;
        wrapper.style.cursor = 'grab';
        wrapper.style.userSelect = '';
        // Если был драг — не дать последующему клику закрыть модалку
        if (dragged) {
            window.__suppressModalClose = true;
            setTimeout(() => { window.__suppressModalClose = false; }, 0);
        }
    });

    // Если был драг — гасим последующий клик, чтобы он не выбрал/не переместил блок
    wrapper.addEventListener('click', function (e) {
        if (dragged) {
            e.stopPropagation();
            e.preventDefault();
            dragged = false;
        }
    }, true);
}

function toggleAutoAssign() {
    const enabled = document.getElementById('autoAssignToggle').checked;

    document.getElementById('manualBlockGroup').style.display = enabled ? 'none' : '';
    document.getElementById('autoBlockGroup').style.display = enabled ? '' : 'none';
    document.getElementById('assignmentEmployeeGroup').style.display = enabled ? 'none' : '';
    document.getElementById('assignmentCommentGroup').style.display = enabled ? 'none' : '';

    const statusSelect = document.getElementById('assignmentStatus');
    statusSelect.disabled = enabled;

    if (enabled) {
        statusSelect.value = 'new';
        autoAssignSelected = null;
        recomputeAutoAssignSchedule();
        renderAutoScheduleTable();
    }
}

function openAssignmentModal(taskId, dateStr) {
    const modal = document.getElementById('assignmentModal');
    const title = document.getElementById('modalTitle');
    const taskIdField = document.getElementById('assignmentTaskId');
    const taskDateField = document.getElementById('taskDate');
    const assignmentIdField = document.getElementById('assignmentId');
    const taskCrit = document.getElementById('taskCriticality');
    const assignDate = document.getElementById('assignmentDate');
    const assignStatus = document.getElementById('assignmentStatus');
    const assignEmployee = document.getElementById('assignmentEmployee');
    const assignComment = document.getElementById('assignmentComment');

    const saveBtn = document.getElementById('saveAssignmentBtn');
    const updateBtn = document.getElementById('updateAssignmentBtn');
    const deleteBtn = document.getElementById('deleteAssignmentBtn');

    const task = tasksData.find(t => t.id === taskId);
    if (!task) return;

    taskCrit.value = task.criticality;
    taskIdField.value = taskId;
    taskDateField.value = dateStr;

    // Сбрасываем переключатель автоназначения к выключенному состоянию
    document.getElementById('autoAssignToggle').checked = false;
    document.getElementById('manualBlockGroup').style.display = '';
    document.getElementById('autoBlockGroup').style.display = 'none';
    document.getElementById('assignmentEmployeeGroup').style.display = '';
    document.getElementById('assignmentCommentGroup').style.display = '';
    assignStatus.disabled = false;
    autoAssignSelected = null;
    autoAssignDates = {};
    autoAssignBaseDate = null;

    const assignment = assignmentsData.find(a => a.task_id === taskId && a.date === dateStr);

    // Текущие значения блока в назначении (из текстового поля, через запятую)
    const selectedBlockNames = assignment && assignment.block
        ? assignment.block.split(',').map(s => s.trim()).filter(Boolean)
        : [];
    renderBlockCheckboxes(selectedBlockNames);

    if (assignment) {
        title.textContent = `Редактирование: ${task.name}`;
        assignmentIdField.value = assignment.id;
        assignDate.value = assignment.date;
        assignStatus.value = assignment.status;
        assignEmployee.value = assignment.employee_id || '';
        assignComment.value = assignment.comment || '';
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';
        deleteBtn.style.display = 'inline-block';
    } else {
        title.textContent = `Новая запись: ${task.name}`;
        assignmentIdField.value = '';
        assignDate.value = dateStr;
        assignStatus.value = 'new';
        assignEmployee.value = '';
        assignComment.value = '';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
        deleteBtn.style.display = 'none';
    }

    modal.style.display = 'flex';
}

function saveAssignment(event) {
    event.preventDefault();

    const autoEnabled = document.getElementById('autoAssignToggle').checked;
    if (autoEnabled) {
        saveAutoAssignment();
        return;
    }

    const taskId = document.getElementById('assignmentTaskId').value;
    const assignmentId = document.getElementById('assignmentId').value;
    const date = document.getElementById('assignmentDate').value;
    const block = getSelectedBlocks().join(', ');
    const status = document.getElementById('assignmentStatus').value;
    const employeeId = document.getElementById('assignmentEmployee').value;
    const comment = document.getElementById('assignmentComment').value;

    fetch('/api/assignment', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            assignment_id: parseInt(assignmentId),
            task_id: parseInt(taskId),
            date: date,
            block: block,
            status: status,
            employee_id: employeeId ? parseInt(employeeId) : null,
            comment: comment
        })
    })
        .then(response => response.json())
        .then(() => {
            closeModal('assignmentModal');
            loadData();
        })
        .catch(error => {
            console.error('Error saving assignment:', error);
            alert('Ошибка при сохранении');
        });
}

function saveAutoAssignment() {
    const taskId = parseInt(document.getElementById('assignmentTaskId').value);
    const assignmentIdVal = document.getElementById('assignmentId').value;
    const currentAssignmentId = assignmentIdVal ? parseInt(assignmentIdVal) : null;

    if (!teamBlocks || teamBlocks.length === 0) {
        alert('У команды нет блоков раскатки для автоназначения');
        return;
    }

    // Группируем блоки по итоговым датам
    const groups = {};
    teamBlocks.forEach(block => {
        const d = autoAssignDates[block.id];
        if (!d) return;
        groups[d] = groups[d] || [];
        groups[d].push(block.name);
    });

    const dates = Object.keys(groups).sort();
    if (dates.length === 0) {
        alert('Нет блоков для автоназначения');
        return;
    }

    // Проверяем, не занята ли уже какая-то из дат другим назначением
    const conflictDates = dates.filter(d => {
        const existing = assignmentsData.find(a => a.task_id === taskId && a.date === d);
        return existing && existing.id !== currentAssignmentId;
    });

    if (conflictDates.length > 0) {
        const proceed = confirm(
            `На дату(ы) ${conflictDates.join(', ')} уже есть назначение(я).\nПерезаписать их?`
        );
        if (!proceed) return;
    }

    const requests = dates.map(d => {
        const existing = assignmentsData.find(a => a.task_id === taskId && a.date === d);
        return fetch('/api/assignment', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                assignment_id: existing ? existing.id : null,
                task_id: taskId,
                date: d,
                block: groups[d].join(', '),
                status: 'new',
                employee_id: null,
                comment: null
            })
        });
    });

    Promise.all(requests)
        .then(() => {
            closeModal('assignmentModal');
            loadData();
        })
        .catch(error => {
            console.error('Error saving auto assignment:', error);
            alert('Ошибка при автоназначении');
        });
}

function deleteAssignment() {
    const assignmentId = document.getElementById('assignmentId').value;
    if (!assignmentId) return;

    if (!confirm('Удалить эту запись?')) return;

    fetch(`/api/assignment/${assignmentId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(() => {
            closeModal('assignmentModal');
            loadData();
        })
        .catch(error => {
            console.error('Error deleting assignment:', error);
            alert('Ошибка при удалении');
        });
}

function openTaskModal(taskId) {
    const modal = document.getElementById('taskModal');
    const taskIdField = document.getElementById('taskId');
    const taskNameField = document.getElementById('newTaskName');
    const taskDescriptionField = document.getElementById('newTaskDescription');
    const taskCriticalityField = document.getElementById('newTaskCriticality');

    const saveBtn = document.getElementById('saveTaskBtn');
    const updateBtn = document.getElementById('updateTaskBtn');

    taskIdField.value = taskId;
    const task = tasksData.find(t => t.id === taskId);
    if (task) {
        taskNameField.value = task.name;
        taskDescriptionField.value = task.description;
        taskCriticalityField.value = task.criticality;
        saveBtn.style.display = 'none';
        updateBtn.style.display = 'inline-block';
    } else {
        taskNameField.value = '';
        taskDescriptionField.value = '';
        taskCriticalityField.value = 'medium';
        saveBtn.style.display = 'inline-block';
        updateBtn.style.display = 'none';
    }

    modal.style.display = 'flex'
}

function saveTask(event) {
    event.preventDefault();

    const taskId = document.getElementById('taskId').value;
    const name = document.getElementById('newTaskName').value;
    const description = document.getElementById('newTaskDescription').value;
    const criticality = document.getElementById('newTaskCriticality').value;

    if (!name) {
        alert('Введите имя работы');
        return;
    }

    fetch('/api/task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            task_id: taskId,
            team_id: teamId,
            name: name,
            description: description,
            criticality: criticality
        })
    })
        .then(response => response.json())
        .then(() => {
            closeModal('taskModal');
            loadData();
        })
        .catch(error => {
            console.error('Error adding task:', error);
            alert('Ошибка при добавлении');
        });
}

function deleteTask(taskId) {
    if (!confirm('Удалить всю работу со всеми назначениями?')) return;

    fetch(`/api/task/${taskId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(() => {
            loadData();
        })
        .catch(error => {
            console.error('Error deleting task:', error);
            alert('Ошибка при удалении');
        });
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function setupDragScroll() {
    const wrapper = document.getElementById('tableWrapper');
    if (!wrapper) return;

    let isDragging = false;
    let startX = 0;
    let scrollLeft = 0;
    let startTime = 0;
    let movedDistance = 0;
    let isMouseDown = false;
    let mouseDownTarget = null;

    wrapper.style.cursor = 'grab';

    // Обработчик для mousedown на wrapper
    wrapper.addEventListener('mousedown', function (e) {
        // Не активируем если клик на кнопке, инпуте или селекте
        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('select')) {
            return;
        }

        isDragging = false;
        movedDistance = 0;
        isMouseDown = true;
        mouseDownTarget = e.target;
        startX = e.pageX - wrapper.offsetLeft;
        scrollLeft = wrapper.scrollLeft;
        startTime = Date.now();

        // Запоминаем начальную позицию мыши
        wrapper._startMouseX = e.pageX;
        wrapper._startMouseY = e.pageY;
    });

    // Обработчик для mousemove на document
    document.addEventListener('mousemove', function (e) {
        if (!wrapper._startMouseX) return;

        const deltaX = Math.abs(e.pageX - wrapper._startMouseX);
        const deltaY = Math.abs(e.pageY - wrapper._startMouseY || 0);
        const totalDelta = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

        if (totalDelta > 5 && !isDragging) {
            isDragging = true;
            movedDistance = totalDelta;
            wrapper.style.cursor = 'grabbing';
            wrapper.style.userSelect = 'none';
        }

        if (isDragging) {
            const x = e.pageX - wrapper.offsetLeft;
            const walk = (x - startX) * 1.5;
            wrapper.scrollLeft = scrollLeft - walk;
        }
    });

    // Обработчик для mouseup на document
    document.addEventListener('mouseup', function (e) {
        if (wrapper._startMouseX !== undefined) {
            // Если было перетаскивание - сбрасываем флаги
            if (isDragging) {
                wrapper.style.cursor = 'grab';
                wrapper.style.userSelect = '';
                // Предотвращаем клик
                if (mouseDownTarget) {
                    mouseDownTarget._preventClick = true;
                }
            }

            wrapper._startMouseX = undefined;
            wrapper._startMouseY = undefined;

            setTimeout(() => {
                isDragging = false;
                isMouseDown = false;
                if (mouseDownTarget) {
                    mouseDownTarget._preventClick = false;
                }
                mouseDownTarget = null;
            }, 50);
        }
    });

    // Перехватываем клики на ячейках и проверяем, было ли перетаскивание
    wrapper.addEventListener('click', function (e) {
        const cell = e.target.closest('.schedule-cell');
        if (!cell) return;

        // Если было перетаскивание - игнорируем
        if (isDragging || movedDistance > 5) {
            e.stopPropagation();
            return;
        }

        // Проверяем, не было ли предотвращения клика
        if (cell._preventClick) {
            e.stopPropagation();
            return;
        }

        // Находим задачу и дату
        const row = cell.closest('tr');
        if (!row) return;

        // Получаем ID задачи из данных строки
        const taskId = row.dataset.taskId;
        if (!taskId) return;

        // Терминальные задачи — только чтение
        const task = tasksData.find(t => t.id === parseInt(taskId));
        if (task && (task.task_status === 'done' || task.task_status === 'cancelled')) return;

        // Получаем дату из заголовка колонки
        const colIndex = Array.from(row.children).indexOf(cell);
        const headerCells = document.querySelectorAll('#tableHeader th');
        if (colIndex < 1 || colIndex >= headerCells.length) return;

        // Проверяем, есть ли дата в заголовке
        const headerCell = headerCells[colIndex];
        const dateStr = headerCell.dataset.date;
        if (!dateStr) return;

        // Открываем модалку
        openAssignmentModal(parseInt(taskId), dateStr);
    });

    // Поддержка колесика мыши для горизонтальной прокрутки
    // wrapper.addEventListener('wheel', function(e) {
    //     if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
    //         e.preventDefault();
    //         this.scrollLeft += e.deltaX;
    //     } else if (Math.abs(e.deltaY) > 50) {
    //         e.preventDefault();
    //         this.scrollLeft += e.deltaY;
    //     }
    // }, { passive: false });
}
