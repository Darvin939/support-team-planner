const JOURNAL_PAGE_SIZE = 20;
let journalTeamId = null;
let journalOffset = 0;
let journalTotal = 0;

document.addEventListener('DOMContentLoaded', () => {
    const dataEl = document.getElementById('journalData');
    if (!dataEl) return; // команда не выбрана — страница ничего не грузит
    journalTeamId = JSON.parse(dataEl.textContent).team_id;
    loadJournalPage(0);
});

function loadJournalPage(offset) {
    journalOffset = offset;
    const list = document.getElementById('journalList');
    list.innerHTML = '<span class="hint">Загрузка...</span>';

    Promise.all([
        fetch(`/api/journal/${journalTeamId}?offset=${offset}&limit=${JOURNAL_PAGE_SIZE}`).then(r => r.json()),
        ensureEmployeesLoaded(),
    ])
        .then(([data]) => {
            journalTotal = data.total;
            renderJournalList(data.items, list);
            renderJournalPagination();
        })
        .catch(() => { list.innerHTML = '<span class="hint">Ошибка загрузки</span>'; });
}

function renderJournalList(items, container) {
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="history-empty">Изменений пока нет</div>';
        return;
    }
    container.innerHTML = items.map(item => {
        const entity = item.entity;
        const isAssignmentRow = entity === 'assignment';
        const who = formatChangedBy(item);
        const taskNameLabel = `«${item.task_name}»${item.task_is_deleted ? ' <span class="journal-deleted-tag">удалена</span>' : ''}`;

        let text;
        if (item.field_name === 'is_deleted' && item.new_value === '1') {
            text = isAssignmentRow ? `Назначение на ${item.date} удалено` : 'Задача удалена';
        } else if (item.action === 'create') {
            text = isAssignmentRow ? `Назначение на ${item.date} создано` : 'Задача создана';
        } else if (item.action === 'delete') {
            text = isAssignmentRow ? `Назначение на ${item.date} удалено` : 'Задача удалена';
        } else {
            const label = HISTORY_FIELD_LABELS[item.field_name] || item.field_name;
            const changeText = `${label}: ${formatHistoryValue(item.field_name, item.old_value)} <span class="history-arrow">➜</span> ${formatHistoryValue(item.field_name, item.new_value)}`;
            text = isAssignmentRow ? `Назначение на ${item.date} — ${changeText}` : changeText;
        }

        return `
            <div class="journal-item" onclick="openJournalTaskModal(${item.task_id})">
                <div class="history-entry-time">${item.changed_at} — ${who}</div>
                <div>${taskNameLabel} — ${text}</div>
            </div>`;
    }).join('');
}

function renderJournalPagination() {
    const totalPages = Math.ceil(journalTotal / JOURNAL_PAGE_SIZE);
    const currentPage = Math.floor(journalOffset / JOURNAL_PAGE_SIZE) + 1;
    renderSmartPagination(['journalPaginationTop', 'journalPagination'], currentPage, totalPages, 'goToJournalPage');
}

function goToJournalPage(page) {
    const totalPages = Math.ceil(journalTotal / JOURNAL_PAGE_SIZE);
    if (page < 1 || page > totalPages) return;
    loadJournalPage((page - 1) * JOURNAL_PAGE_SIZE);
}

function openJournalTaskModal(taskId) {
    document.getElementById('journalTaskId').value = taskId;
    historyPanels.journal = {open: true, offset: 0, total: 0};
    loadHistoryPage('journal', 0);
    document.getElementById('journalTaskModal').style.display = 'flex';
    lockBodyScroll();
}
