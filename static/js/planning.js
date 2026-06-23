let teamId = null;
let employees = [];
let freezeDays = [];
let teamBlocks = [];

let tasksData = [];
let assignmentsData = [];
let currentDateRange = {start: null, end: null};

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
        employees = initData.employees || [];
        freezeDays = initData.freeze_days || [];
        teamBlocks = initData.team_blocks || [];
    }

    initializeTable();
    setupDragScroll();

    // Загрузка данных
    loadData();

    // Обработчики для фильтров
    document.getElementById('dateFrom').addEventListener('change', loadData);
    document.getElementById('dateTo').addEventListener('change', loadData);
    document.getElementById('searchText').addEventListener('input', applyFilters);
    // document.getElementById('criticalityDropdown').addEventListener('change', applyFilters);
    // document.getElementById('statusDropdown').addEventListener('change', applyFilters);
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

function loadData() {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;

    if (!dateFrom || !dateTo) return;

    // Загружаем задачи
    fetch(`/api/tasks/${teamId}`)
        .then(response => response.json())
        .then(data => {
            tasksData = data;
            // Загружаем назначения
            return fetch(`/api/assignments/${teamId}?start_date=${dateFrom}&end_date=${dateTo}`);
        })
        .then(response => response.json())
        .then(data => {
            assignmentsData = data;
            renderTable();
            applyFilters();
        })
        .catch(error => console.error('Error loading data:', error));
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
    header.innerHTML = `
        <th></th>
        <th>Крит.</th>
        <th>Имя</th>
    `;

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
        body.innerHTML = `<tr><td colspan="${dates.length + 3}" class="empty-row">Нет запланированных работ</td></tr>`;
        return;
    }

    tasksData.forEach(task => {
        const row = document.createElement('tr');
        // Добавляем data-task-id для идентификации задачи
        row.dataset.taskId = task.id;

        // Колонка действий
        const actionCell = document.createElement('td');
        actionCell.className = 'action-col';
        actionCell.innerHTML = `
            <button class="btn-edit" onclick="openTaskModal(${task.id})" title="Редактировать работу">✏️</button>
            <button class="btn-delete" onclick="deleteTask(${task.id})" title="Удалить работу">🗑️</button>
        `;
        row.appendChild(actionCell);

        // Колонка критичности
        const critCell = document.createElement('td');
        critCell.className = 'criticality-col';
        const critClass = task.criticality === 'high' ? 'criticality-high' :
            task.criticality === 'medium' ? 'criticality-medium' : 'criticality-low';
        const critDisplay = task.criticality === 'high' ? 'В' :
            task.criticality === 'medium' ? 'С' : 'Н';
        critCell.innerHTML = `<span class="criticality-badge ${critClass}">${critDisplay}</span>`;
        row.appendChild(critCell);

        // Колонка описания
        const nameCell = document.createElement('td');
        const taskDescriptionBlock = task.description ? `<div class="description">${linkify(task.description)}</div>` : '';

        nameCell.innerHTML = `
                <div class="name-col">
                    <span class="name">${task.name}</span>
                    ${taskDescriptionBlock}
                </div>
            `;

        row.appendChild(nameCell);

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
    const searchText = document.getElementById('searchText').value.toLowerCase();

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

        const name = nameCell.textContent.toLowerCase();
        const critCell = row.querySelector('.criticality-col .criticality-badge');
        const critValue = critCell ?
            (critCell.classList.contains('criticality-high') ? 'high' :
                critCell.classList.contains('criticality-medium') ? 'medium' : 'low') : 'medium';

        let matches = !searchText || name.includes(searchText);

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
    document.getElementById('totalTasks').textContent = tasksData.length;
}

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

function openAssignmentModal(taskId, dateStr) {
    const modal = document.getElementById('assignmentModal');
    const title = document.getElementById('modalTitle');
    const taskIdField = document.getElementById('assignmentTaskId');
    const taskDateField = document.getElementById('taskDate');
    const assignmentIdField = document.getElementById('assignmentId');
    const taskCrit = document.getElementById('taskCriticality');
    const assignDate = document.getElementById('assignmentDate');
    const assignBlock = document.getElementById('assignmentBlock');
    const assignStatus = document.getElementById('assignmentStatus');
    const assignEmployee = document.getElementById('assignmentEmployee');
    const assignComment = document.getElementById('assignmentComment');

    const saveBtn = document.getElementById('saveAssignmentBtn');
    const updateBtn = document.getElementById('updateAssignmentBtn');
    const deleteBtn = document.getElementById('deleteAssignmentBtn');

    // Обновляем список блоков
    const currentBlocks = teamBlocks;
    if (currentBlocks.length > 0) {
        let blockOptions = '<option value="">Не выбран</option>';
        currentBlocks.forEach(block => {
            blockOptions += `<option value="${block.block_name}">${block.block_name}</option>`;
        });
        assignBlock.innerHTML = blockOptions;
    } else {
        assignBlock.innerHTML = '<option value="">Блоки не настроены для этой команды</option>';
    }

    const task = tasksData.find(t => t.id === taskId);
    if (!task) return;

    taskCrit.value = task.criticality;
    taskIdField.value = taskId;
    taskDateField.value = dateStr;

    const assignment = assignmentsData.find(a => a.task_id === taskId && a.date === dateStr);

    if (assignment) {
        title.textContent = `Редактирование: ${task.name}`;
        assignmentIdField.value = assignment.id;
        assignDate.value = assignment.date;
        assignBlock.value = assignment.block || '';
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
        assignBlock.value = '';
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

    const taskId = document.getElementById('assignmentTaskId').value;
    const assignmentId = document.getElementById('assignmentId').value;
    const date = document.getElementById('assignmentDate').value;
    const block = document.getElementById('assignmentBlock').value;
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

        // Получаем дату из заголовка колонки
        const colIndex = Array.from(row.children).indexOf(cell);
        const headerCells = document.querySelectorAll('#tableHeader th');
        if (colIndex < 3 || colIndex >= headerCells.length) return;

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
