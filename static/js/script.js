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

// Закрытие модального окна по Escape
function closeModalByEscapeBtn(e) {
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
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

