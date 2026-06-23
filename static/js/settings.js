function addTeam() {
    openTeamSettingsModal(null, '', []);
}

function editTeam(teamId) {
    // Загружаем текущие данные команды
    fetch(`/api/teams/${teamId}`)
        .then(response => response.json())
        .then(teamData => {
            fetch(`/api/teams/${teamId}/blocks`)
                .then(response => response.json())
                .then(blocksData => {
                    openTeamSettingsModal(teamId, teamData.name, blocksData);
                })
                .catch(error => {
                    console.error('Error loading blocks:', error);
                    alert('Ошибка при загрузке блоков');
                });
        })
        .catch(error => {
            console.error('Error loading team:', error);
            alert('Ошибка при загрузке команды');
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

// === Модальное окно настроек команды ===
function openTeamSettingsModal(teamId, teamName, blocks) {
    // Создаем модальное окно, если его нет
    if (!document.getElementById('teamSettingsModal')) {
        createTeamSettingsModal();
    }

    const modal = document.getElementById('teamSettingsModal');
    document.getElementById('teamSettingsTeamId').value = teamId;
    document.getElementById('teamSettingsName').value = teamName;

    const blocksList = document.getElementById('teamBlocksList');
    blocksList.innerHTML = '';

    if (blocks && blocks.length > 0) {
        blocks.forEach((block, index) => {
            addBlockToList(block.block_name.toUpperCase(), block.schedule_offset);
        });
    }

    // Сброс поля ввода нового блока
    document.getElementById('newBlockInput').value = '';
    document.getElementById('newBlockOffset').value = '0';

    modal.style.display = 'flex';
}

function createTeamSettingsModal() {
    const modal = document.createElement('div');
    modal.id = 'teamSettingsModal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Настройки команды</h2>
                <span class="modal-close" onclick="closeTeamSettingsModal()">&times;</span>
            </div>
            <div class="form-group" style="padding: 20px;">
                <input type="hidden" id="teamSettingsTeamId" value="">
                
                <label for="teamSettingsName">Название команды</label>
                <input type="text" id="teamSettingsName" required>
            </div>

            <div class="form-group" style="padding: 0 20px;">
                <label>Блоки</label>
                <div class="add-block-form">
                    <input type="text" id="newBlockInput" placeholder="Название блока (например: GF, Б1)">
                    <input type="number" id="newBlockOffset" placeholder="Сдвиг (дни)" value="0" min="0">
                    <button type="button" class="btn btn-success" onclick="addNewBlock()">Добавить</button>
                </div>
                <div id="teamBlocksList" class="blocks-list"></div>
            </div>

            <div class="form-actions" style="padding: 20px; border-top: 1px solid #eee;">
                <button type="button" class="btn btn-success" onclick="saveTeamSettings()">Сохранить</button>
                <button type="button" class="btn btn-secondary" onclick="closeTeamSettingsModal()">Закрыть</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function closeTeamSettingsModal() {
    const modal = document.getElementById('teamSettingsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function validateBlocks() {
    const offsets = new Set();
    const blockItems = document.querySelectorAll('.block-item');

    for (const item of blockItems) {
        const offset = parseInt(item.querySelector('.block-offset-input').value) || 0;
        if (offsets.has(offset)) {
            alert('Сдвиг ' + offset + ' уже используется другим блоком');
            return false;
        }
        offsets.add(offset);
    }
    return true;
}

function addBlockToList(blockName, offset = 0) {
    // Приводим к UPPER CASE
    blockName = blockName.toUpperCase();

    const blocksList = document.getElementById('teamBlocksList');
    const div = document.createElement('div');
    div.className = 'block-item';
    div.innerHTML = `
        <input type="text" class="block-name-input" value="${blockName}" placeholder="Название блока">
        <input type="number" class="block-offset-input" value="${offset}" min="0" placeholder="Сдвиг">
        <button type="button" class="btn btn-danger btn-sm" onclick="removeBlock(this)">🗑️</button>
    `;
    blocksList.appendChild(div);
}

function addNewBlock() {
    const blockInput = document.getElementById('newBlockInput');
    const offsetInput = document.getElementById('newBlockOffset');
    const blockName = blockInput.value.trim().toUpperCase();
    const offset = parseInt(offsetInput.value) || 0;

    if (!blockName) {
        alert('Введите название блока');
        return;
    }

    addBlockToList(blockName, offset);

    blockInput.value = '';
    offsetInput.value = '0';
}

function removeBlock(btn) {
    const blockItem = btn.closest('.block-item');
    if (blockItem) {
        blockItem.remove();
    }
}

function saveTeamSettings() {
    const teamId = document.getElementById('teamSettingsTeamId').value;
    const teamName = document.getElementById('teamSettingsName').value.trim();

    if (!teamName) {
        alert('Введите название команды');
        return;
    }

    // Предварительная проверка уникальности сдвигов
    if (!validateBlocks()) {
        return;
    }

    // Если teamId пустой - создаем новую команду
    if (!teamId) {
        fetch('/api/teams', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: teamName})
        })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Ошибка при создании команды');
                }
                const newTeamId = data.id;

                // Сохраняем блоки
                return saveTeamBlocks(newTeamId);
            })
            .then(() => {
                closeTeamSettingsModal();
                location.reload();
            })
            .catch(error => {
                console.error('Error saving team settings:', error);
                alert('Ошибка: ' + error.message);
            });
    } else {
        // Редактируем существующую команду
        // Сохраняем название команды
        fetch(`/api/teams/${teamId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: teamName})
        })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    throw new Error(data.error || 'Ошибка при обновлении команды');
                }

                // Сохраняем блоки
                return saveTeamBlocks(teamId);
            })
            .then(() => {
                closeTeamSettingsModal();
                location.reload();
            })
            .catch(error => {
                console.error('Error saving team settings:', error);
                alert('Ошибка: ' + error.message);
            });
    }
}

function saveTeamBlocks(teamId) {
    const blocks = [];
    const offsets = new Set();

    document.querySelectorAll('.block-item').forEach(item => {
        const blockName = item.querySelector('.block-name-input').value.trim();
        const offset = parseInt(item.querySelector('.block-offset-input').value) || 0;

        if (!blockName) return;

        // Приводим к UPPER CASE
        const upperBlockName = blockName.toUpperCase();

        // Проверка дубликатов сдвигов
        if (offsets.has(offset)) {
            throw new Error('Сдвиг ' + offset + ' уже используется другим блоком');
        }
        offsets.add(offset);

        blocks.push({block_name: upperBlockName, schedule_offset: offset});
    });

    return fetch(`/api/teams/${teamId}/blocks`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({blocks: blocks})
    }).then(response => response.json());
}

// Обработчик клика вне модального окна для закрытия
window.onclick = function (event) {
    const modal = document.getElementById('teamSettingsModal');
    if (event.target === modal) {
        closeTeamSettingsModal();
    }
}
