// Тёмная тема
(function () {
    const THEME_KEY = 'theme';
    const html = document.documentElement;
    const saved = localStorage.getItem(THEME_KEY) || '';
    html.setAttribute('data-theme', saved);

    document.addEventListener('DOMContentLoaded', function () {
        const btn = document.getElementById('themeToggle');
        if (!btn) return;
        btn.textContent = html.getAttribute('data-theme') === 'dark' ? '☾' : '☀';
        btn.addEventListener('click', function () {
            const isDark = html.getAttribute('data-theme') === 'dark';
            const next = isDark ? '' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem(THEME_KEY, next);
            btn.textContent = next === 'dark' ? '☾' : '☀';
        });
    });
})();

// Функции для выпадающих списков с чекбоксами
function toggleDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const toggle = dropdown.parentElement.querySelector('.dropdown-toggle');

    // Закрываем все другие выпадающие списки
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        if (menu.id !== dropdownId) {
            menu.classList.remove('show');
            const btn = menu.parentElement.querySelector('.dropdown-toggle');
            if (btn) btn.classList.remove('active');
        }
    });

    dropdown.classList.toggle('show');
    toggle.classList.toggle('active');
}

function updateDropdownLabel(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const toggle = dropdown.parentElement.querySelector('.dropdown-toggle');
    const label = toggle.querySelector('.dropdown-label');
    const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');

    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const total = checkboxes.length;

    if (checked.length === 0) {
        label.textContent = 'Ничего не выбрано';
    } else if (checked.length === total) {
        label.textContent = 'Все';
    } else {
        // Показываем первые 2 выбранных значения
        const values = checked.map(cb => {
            const parent = cb.closest('.checkbox-item');
            return parent ? parent.textContent.trim() : cb.value;
        });
        label.textContent = values.slice(0, 2).join(', ') + (values.length > 2 ? ', ...' : '');
    }
}

// Функция для преобразования текста: находит URL и заменяет их на ссылки
function linkify(text) {
    if (!text) {
        return '';
    }
    // Регулярное выражение для поиска URL (http, https, ftp)
    const urlPattern = /(https?:\/\/[^\s]+)/g;
    return text.replace(urlPattern, function (url) {
        return `<a href="${url}" target="_blank">${url}</a>`;
    });
}

// Сохранение фильтров в localStorage
const STORAGE_TEAM_ID = 'selectedTeamId';
const STORAGE_DATE_FROM = 'filterDateFrom';
const STORAGE_DATE_TO = 'filterDateTo';

function saveTeamId(teamId) { localStorage.setItem(STORAGE_TEAM_ID, teamId); }
function getSavedTeamId() { return localStorage.getItem(STORAGE_TEAM_ID); }
function saveDateRange(from, to) {
    if (from) localStorage.setItem(STORAGE_DATE_FROM, from);
    if (to) localStorage.setItem(STORAGE_DATE_TO, to);
}
function getSavedDateRange() {
    return { from: localStorage.getItem(STORAGE_DATE_FROM), to: localStorage.getItem(STORAGE_DATE_TO) };
}

// Ограничение периода дат
const MAX_PERIOD_DAYS = 60;

function clampDateRange(fromId, toId) {
    const fromInput = document.getElementById(fromId);
    const toInput = document.getElementById(toId);
    if (!fromInput || !toInput || !fromInput.value || !toInput.value) return;

    const from = new Date(fromInput.value);
    const to = new Date(toInput.value);
    const diffDays = Math.round((to - from) / 86400000);

    if (diffDays > MAX_PERIOD_DAYS) {
        const clamped = new Date(from);
        clamped.setDate(clamped.getDate() + MAX_PERIOD_DAYS);
        toInput.value = clamped.toISOString().split('T')[0];
    } else if (diffDays < 0) {
        toInput.value = fromInput.value;
    }
}

// === Пагинация со стрелками и сокращением номеров многоточием — используется
// и на странице планирования, и в журнале изменений ===
function renderSmartPagination(containerIds, currentPage, totalPages, onPageClickFn) {
    const containers = containerIds.map(id => document.getElementById(id)).filter(Boolean);
    if (containers.length === 0) return;
    if (totalPages <= 1) {
        containers.forEach(c => c.innerHTML = '');
        return;
    }

    const pagesToShow = new Set([1, totalPages]);
    for (let p = currentPage - 1; p <= currentPage + 1; p++) {
        if (p > 1 && p < totalPages) pagesToShow.add(p);
    }
    const sorted = [...pagesToShow].sort((a, b) => a - b);

    let html = `<button class="page-btn" onclick="${onPageClickFn}(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>←</button>`;
    let prev = 0;
    sorted.forEach(p => {
        if (prev && p - prev > 1) html += `<span class="page-ellipsis">…</span>`;
        html += `<button class="page-btn${p === currentPage ? ' active' : ''}" onclick="${onPageClickFn}(${p})">${p}</button>`;
        prev = p;
    });
    html += `<button class="page-btn" onclick="${onPageClickFn}(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>→</button>`;

    containers.forEach(c => c.innerHTML = html);
}

// Блокировка скролла фоновой страницы, пока открыто модальное окно
function lockBodyScroll() {
    document.body.style.overflow = 'hidden';
}

function unlockBodyScroll() {
    const anyOpen = Array.from(document.querySelectorAll('.modal')).some(m => m.style.display === 'flex');
    if (!anyOpen) {
        document.body.style.overflow = '';
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    unlockBodyScroll();
}

// === История изменений: общий рендеринг, используемый и на странице планирования
// (модалки задачи/назначения), и на странице журнала изменений ===

const HISTORY_FIELD_LABELS = {
    name: 'Название', description: 'Описание', criticality: 'Критичность', task_status: 'Статус',
    date: 'Дата', block: 'Блок', status: 'Статус', employee_id: 'Исполнитель',
    comment: 'Комментарий', is_psi: 'ПСИ', time_spent: 'Время выполнения', is_deleted: 'Удаление'
};

const CRITICALITY_LABELS = {high: 'Высокая', medium: 'Средняя', low: 'Низкая'};

const TASK_STATUS_LABELS = {
    new: 'Новый',
    ready: 'К планированию',
    in_progress: 'В работе',
    done: 'Выполнено',
    cancelled: 'Отменено'
};

const statusMap = {
    'new': 'Новый',
    'planned': 'Запланировано',
    'rollback': 'Откат',
    'success': 'Успешно'
};

// Кэш сотрудников для отображения имени по id там, где нет локального <select> с сотрудниками
// (например, на странице журнала изменений) — грузится один раз и переиспользуется.
let _employeesById = null;

function _formatEmployeeDisplayName(e) {
    if (!e.last_name) return '';
    if (!e.first_name) return e.last_name;
    const initials = `${e.first_name.charAt(0)}.${e.middle_name ? e.middle_name.charAt(0) + '.' : ''}`;
    return `${e.last_name} ${initials}`;
}

function ensureEmployeesLoaded() {
    if (_employeesById) return Promise.resolve(_employeesById);
    return fetch('/api/employees').then(r => r.json()).then(list => {
        _employeesById = new Map(list.map(e => [e.id, _formatEmployeeDisplayName(e)]));
        return _employeesById;
    });
}

function getEmployeeName(employeeId) {
    if (!employeeId) return '—';
    if (_employeesById && _employeesById.has(Number(employeeId))) return _employeesById.get(Number(employeeId));
    return `#${employeeId}`;
}

function formatChangedBy(entry) {
    return entry.changed_by_last_name
        ? `${entry.changed_by_last_name} ${(entry.changed_by_first_name || '').charAt(0)}.${entry.changed_by_middle_name ? entry.changed_by_middle_name.charAt(0) + '.' : ''}`
        : 'Система';
}

function formatHistoryValue(field, value) {
    if (field === 'is_deleted') return value === '1' || value === 1 || value === true ? 'Да' : 'Нет';
    if (value === null || value === undefined || value === '') return '—';
    if (field === 'criticality') return CRITICALITY_LABELS[value] || value;
    if (field === 'task_status') return TASK_STATUS_LABELS[value] || value;
    if (field === 'status') return statusMap[value] || value;
    if (field === 'employee_id') return getEmployeeName(value);
    if (field === 'is_psi') return (value === '1' || value === 1 || value === true) ? 'Да' : 'Нет';
    return value;
}

function renderHistoryEntries(entries, container, defaultEntity, showAssignmentContext) {
    if (!entries || entries.length === 0) {
        container.innerHTML = '<div class="history-empty">Изменений пока нет</div>';
        return;
    }

    container.innerHTML = entries.map(e => {
        const entity = e.entity || defaultEntity;
        const isAssignmentRow = entity === 'assignment';
        const who = formatChangedBy(e);
        const taskNamePrefix = e.task_name
            ? `«${e.task_name}»${e.task_is_deleted ? ' (задача удалена)' : ''} — `
            : '';

        let text;
        if (e.field_name === 'is_deleted' && e.new_value === '1') {
            text = isAssignmentRow ? `Назначение на ${e.date} удалено` : 'Задача удалена';
        } else if (e.action === 'create') {
            text = isAssignmentRow ? `Назначение на ${e.date} создано` : 'Задача создана';
        } else if (e.action === 'delete') {
            // legacy-записи (создавались до перехода на is_deleted), оставлены для полноты истории
            text = isAssignmentRow ? `Назначение на ${e.date} удалено` : 'Задача удалена';
        } else {
            const label = HISTORY_FIELD_LABELS[e.field_name] || e.field_name;
            const changeText = `${label}: ${formatHistoryValue(e.field_name, e.old_value)} <span class="history-arrow">➜</span> ${formatHistoryValue(e.field_name, e.new_value)}`;
            text = (showAssignmentContext && isAssignmentRow) ? `Назначение на ${e.date} — ${changeText}` : changeText;
        }

        const cls = showAssignmentContext && isAssignmentRow ? 'history-entry history-entry-assignment' : 'history-entry';
        return `<div class="${cls}"><div class="history-entry-time">${e.changed_at} — ${who}</div><div>${taskNamePrefix}${text}</div></div>`;
    }).join('');
}

const HISTORY_PAGE_SIZE = 10;
const historyPanels = {
    assignment: {open: false, offset: 0, total: 0},
    task: {open: false, offset: 0, total: 0},
    journal: {open: true, offset: 0, total: 0}
};

const HISTORY_PANEL_CONFIG = {
    assignment: {
        panel: 'assignmentHistoryPanel', modalContent: 'assignmentModalContent',
        toggleBtn: 'assignmentHistoryToggle', list: 'assignmentHistoryList',
        pagination: 'assignmentHistoryPagination', idField: 'assignmentId',
        endpoint: (id, offset, limit) => `/api/assignment/${id}/history?offset=${offset}&limit=${limit}`
    },
    task: {
        panel: 'taskHistoryPanel', modalContent: 'taskModalContent',
        toggleBtn: 'taskHistoryToggle', list: 'taskHistoryList',
        pagination: 'taskHistoryPagination', idField: 'taskId',
        endpoint: (id, offset, limit) => `/api/task/${id}/history?offset=${offset}&limit=${limit}`
    },
    journal: {
        panel: null, modalContent: null, toggleBtn: null,
        list: 'journalHistoryList', pagination: 'journalHistoryPagination', idField: 'journalTaskId',
        endpoint: (id, offset, limit) => `/api/task/${id}/history?offset=${offset}&limit=${limit}`
    }
};

function historyPanelEl(kind) {
    const cfg = HISTORY_PANEL_CONFIG[kind];
    return {
        panel: cfg.panel && document.getElementById(cfg.panel),
        modalContent: cfg.modalContent && document.getElementById(cfg.modalContent),
        toggleBtn: cfg.toggleBtn && document.getElementById(cfg.toggleBtn),
        list: document.getElementById(cfg.list),
        pagination: document.getElementById(cfg.pagination),
        id: document.getElementById(cfg.idField).value,
        endpoint: cfg.endpoint
    };
}

function resetHistoryPanel(kind) {
    const state = historyPanels[kind];
    state.open = false;
    state.offset = 0;
    state.total = 0;
    const el = historyPanelEl(kind);
    if (el.panel) el.panel.classList.remove('open');
    if (el.modalContent) {
        el.modalContent.classList.remove('history-open');
        el.modalContent.style.height = '';
    }
    if (el.toggleBtn) {
        el.toggleBtn.classList.remove('active');
        el.toggleBtn.textContent = '🕓 История';
    }
    el.list.innerHTML = '';
    el.pagination.innerHTML = '';
}

function toggleHistoryPanel(kind) {
    const state = historyPanels[kind];
    const el = historyPanelEl(kind);

    // Фиксируем естественную высоту модалки один раз, при первом раскрытии панели
    // за это открытие модалки, и держим её неизменной до следующего resetHistoryPanel
    // (открытия модалки заново). Так переключение истории туда-обратно меняет только
    // ширину и не "растягивает" модалку при закрытии до того, как доиграет анимация ширины.
    if (el.modalContent && !el.modalContent.style.height) {
        el.modalContent.style.height = el.modalContent.getBoundingClientRect().height + 'px';
    }

    state.open = !state.open;
    if (el.panel) el.panel.classList.toggle('open', state.open);
    if (el.modalContent) el.modalContent.classList.toggle('history-open', state.open);
    if (el.toggleBtn) {
        el.toggleBtn.classList.toggle('active', state.open);
        el.toggleBtn.textContent = state.open ? '✕ Скрыть историю' : '🕓 История';
    }

    if (state.open) {
        loadHistoryPage(kind, 0);
    }
}

function loadHistoryPage(kind, offset) {
    const state = historyPanels[kind];
    const el = historyPanelEl(kind);
    if (!el.id) return;
    state.offset = offset;
    el.list.innerHTML = '<span class="hint">Загрузка...</span>';
    el.pagination.innerHTML = '';

    Promise.all([
        fetch(el.endpoint(el.id, offset, HISTORY_PAGE_SIZE)).then(r => r.json()),
        ensureEmployeesLoaded(),
    ])
        .then(([data]) => {
            state.total = data.total;
            renderHistoryEntries(data.history, el.list, kind, kind !== 'assignment');
            renderHistoryPagination(kind);
        })
        .catch(() => { el.list.innerHTML = '<span class="hint">Ошибка загрузки истории</span>'; });
}

function renderHistoryPagination(kind) {
    const state = historyPanels[kind];
    const el = historyPanelEl(kind);
    const totalPages = Math.ceil(state.total / HISTORY_PAGE_SIZE);
    if (totalPages <= 1) {
        el.pagination.innerHTML = '';
        return;
    }
    const currentPage = Math.floor(state.offset / HISTORY_PAGE_SIZE) + 1;
    const from = state.total === 0 ? 0 : state.offset + 1;
    const to = Math.min(state.offset + HISTORY_PAGE_SIZE, state.total);
    el.pagination.innerHTML = `
        <button class="page-btn" onclick="loadHistoryPage('${kind}', ${Math.max(0, state.offset - HISTORY_PAGE_SIZE)})" ${currentPage === 1 ? 'disabled' : ''}>←</button>
        <span>${from}–${to} из ${state.total}</span>
        <button class="page-btn" onclick="loadHistoryPage('${kind}', ${state.offset + HISTORY_PAGE_SIZE})" ${currentPage === totalPages ? 'disabled' : ''}>→</button>
    `;
}

// Закрытие модального окна по Escape
function closeModalByEscapeBtn(e) {
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
        unlockBodyScroll();
    }
}

// Закрытие модального окна по клику вне его
function closeModalByClick(e) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    unlockBodyScroll();
}

// Закрытие выпадающих списков при клике вне их
function closeDropdownMenuByClick(e) {
    if (!e.target.closest('.dropdown-container')) {
        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
            const toggle = menu.parentElement.querySelector('.dropdown-toggle');
            if (toggle) toggle.classList.remove('active');
        });
    }
}

document.addEventListener('click', function (e) {
    // Если только что был drag-scroll — не закрываем модалку этим кликом
    if (window.__suppressModalClose) {
        return;
    }

    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) {
        return;
    }

    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') && active.selectionStart !== active.selectionEnd) {
        return;
    }

    closeModalByClick(e);
    closeDropdownMenuByClick(e);
});

// Закрытие модальных окон по Escape
document.addEventListener('keydown', function (e) {
    closeModalByEscapeBtn(e)
});

