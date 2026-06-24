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

    function addFreezeDay() {
        const date = document.getElementById('freezeDateInput').value;
        if (!date) {
            alert('Выберите дату');
            return;
        }

        fetch('/api/freeze-days', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({date: date})
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Ошибка при добавлении дня фриза');
                }
            })
            .catch(error => {
                console.error('Error adding freeze day:', error);
                alert('Ошибка при добавлении дня фриза');
            });
    }

    function addFreezeRange() {
        const start = document.getElementById('freezeDateFrom').value;
        const end = document.getElementById('freezeDateTo').value;
        if (!start || !end) {
            alert('Выберите диапазон дат');
            return;
        }

        if (start > end) {
            alert('Начальная дата должна быть раньше конечной');
            return;
        }

        fetch('/api/freeze-days', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({start_date: start, end_date: end})
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Ошибка при добавлении диапазона');
                }
            })
            .catch(error => {
                console.error('Error adding freeze range:', error);
                alert('Ошибка при добавлении диапазона');
            });
    }

    function deleteFreezeDay(date) {
        if (!confirm(`Удалить день фриза ${date}?`)) return;

        fetch(`/api/freeze-days/${encodeURIComponent(date)}`, {
            method: 'DELETE'
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Ошибка при удалении дня фриза');
                }
            })
            .catch(error => {
                console.error('Error deleting freeze day:', error);
                alert('Ошибка при удалении дня фриза');
            });
    }
