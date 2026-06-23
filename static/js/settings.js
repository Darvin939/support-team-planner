    function addTeam() {
        const name = document.getElementById('teamNameInput').value.trim();
        if (!name) {
            alert('Введите название команды');
            return;
        }

        fetch('/api/teams', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name})
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
                console.error('Error adding team:', error);
                alert('Ошибка при добавлении команды');
            });
    }

    function editTeam(teamId) {
        const team = document.querySelector(`.team-card[data-id="${teamId}"] h3`);
        if (!team) return;

        const currentName = team.textContent;
        const newName = prompt('Новое название команды:', currentName);
        if (newName && newName.trim()) {
            fetch(`/api/teams/${teamId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: newName.trim()})
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
                    console.error('Error updating team:', error);
                    alert('Ошибка при обновлении команды');
                });
        }
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

    function addEmployee() {
        const lastName = document.getElementById('employeeLastName').value.trim();
        const firstName = document.getElementById('employeeFirstName').value.trim();
        const middleName = document.getElementById('employeeMiddleName').value.trim();

        if (!lastName || !firstName) {
            alert('Введите фамилию и имя сотрудника');
            return;
        }

        fetch('/api/employees', {
            method: 'POST',
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
                console.error('Error adding employee:', error);
                alert('Ошибка при добавлении сотрудника');
            });
    }

    function editEmployee(employeeId) {
        const item = document.querySelector(`.executor-item[data-id="${employeeId}"]`);
        if (!item) return;

        const nameParts = item.querySelector('.executor-name').textContent.trim().split(' ');
        const lastName = nameParts[0] || '';
        const firstName = nameParts[1] || '';
        const middleName = nameParts.slice(2).join(' ') || '';

        const newLastName = prompt('Фамилия:', lastName);
        if (newLastName === null) return;
        const newFirstName = prompt('Имя:', firstName);
        if (newFirstName === null) return;
        const newMiddleName = prompt('Отчество (оставьте пустым если нет):', middleName);
        if (newMiddleName === null) return;

        if (!newLastName.trim() || !newFirstName.trim()) {
            alert('Фамилия и имя обязательны');
            return;
        }

        fetch(`/api/employees/${employeeId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                last_name: newLastName.trim(),
                first_name: newFirstName.trim(),
                middle_name: newMiddleName.trim() || null
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
                console.error('Error updating employee:', error);
                alert('Ошибка при обновлении сотрудника');
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
