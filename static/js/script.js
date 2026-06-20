// Закрытие модального окна по клику вне его
document.addEventListener('click', function(e) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
});

// Закрытие модальных окон по Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
});

function restoreFilterState() {
    const dateFrom = document.getElementById('dateFrom');
    const dateTo = document.getElementById('dateTo');
    if (dateFrom && dateTo) {
        const savedFrom = localStorage.getItem('filterDateFrom');
        const savedTo = localStorage.getItem('filterDateTo');
        if (savedFrom) dateFrom.value = savedFrom;
        if (savedTo) dateTo.value = savedTo;
    }
}

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

// Закрытие выпадающих списков при клике вне их
document.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown-container')) {
        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
            const toggle = menu.parentElement.querySelector('.dropdown-toggle');
            if (toggle) toggle.classList.remove('active');
        });
    }
});

// Загрузка состояния фильтров при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    restoreFilterState();
});


