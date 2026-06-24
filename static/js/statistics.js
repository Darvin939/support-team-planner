const statusLabels = {new: 'Новый', planned: 'Запланировано'};
const critLabels = {high: 'Высокая', medium: 'Средняя', low: 'Низкая'};
const critClasses = {high: 'criticality-high', medium: 'criticality-medium', low: 'criticality-low'};

function localDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

document.addEventListener('DOMContentLoaded', function () {
    const today = new Date();
    const from = new Date(today);
    from.setDate(from.getDate() - 7);

    document.getElementById('statsDateFrom').value = localDateStr(from);
    document.getElementById('statsDateTo').value = localDateStr(today);

    document.getElementById('statsDateFrom').addEventListener('change', loadPeriodData);
    document.getElementById('statsDateTo').addEventListener('change', loadPeriodData);

    loadAll();
});

function loadAll() {
    loadPeriodData();
    loadTodayData();
}

function loadPeriodData() {
    clampDateRange('statsDateFrom', 'statsDateTo');

    const teamId = document.getElementById('statsTeamSelect').value;
    const from = document.getElementById('statsDateFrom').value;
    const to = document.getElementById('statsDateTo').value;
    if (!from || !to) return;

    fetch(`/api/active-assignments/${teamId}?start_date=${from}&end_date=${to}`)
        .then(r => r.json())
        .then(data => {
            renderCounters(data, 'periodCounters');
            renderTable(data, 'periodTableBody', true);
        })
        .catch(e => console.error('Error loading period data:', e));
}

function loadTodayData() {
    const teamId = document.getElementById('statsTeamSelect').value;
    const today = localDateStr(new Date());

    fetch(`/api/active-assignments/${teamId}?start_date=${today}&end_date=${today}`)
        .then(r => r.json())
        .then(data => {
            renderCounters(data, 'todayCounters');
            renderTable(data, 'todayTableBody', false);
        })
        .catch(e => console.error('Error loading today data:', e));
}

function renderCounters(data, containerId) {
    const statusCounts = {new: 0, planned: 0};
    const critCounts = {high: 0, medium: 0, low: 0};

    data.forEach(a => {
        if (statusCounts[a.status] !== undefined) statusCounts[a.status]++;
        if (critCounts[a.criticality] !== undefined) critCounts[a.criticality]++;
    });

    const container = document.getElementById(containerId);
    let html = `<span class="counter-item">Всего: <b>${data.length}</b></span>`;

    html += `<span class="counter-group-label">Статус:</span>`;
    for (const [key, label] of Object.entries(statusLabels)) {
        html += `<span class="counter-item counter-status-${key}">${label}: <b>${statusCounts[key]}</b></span>`;
    }

    html += `<span class="counter-group-label">Критичность:</span>`;
    for (const [key, label] of Object.entries(critLabels)) {
        html += `<span class="counter-item counter-crit-${key}">${label}: <b>${critCounts[key]}</b></span>`;
    }

    container.innerHTML = html;
}

function renderTable(data, tbodyId, showDate) {
    const tbody = document.getElementById(tbodyId);
    const colCount = showDate ? 7 : 6;

    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colCount}" class="empty-row">Нет активных работ</td></tr>`;
        return;
    }

    let html = '';
    data.forEach(a => {
        const critClass = critClasses[a.criticality] || '';
        const critLabel = a.criticality === 'high' ? 'В' : a.criticality === 'medium' ? 'С' : 'Н';
        const statusLabel = statusLabels[a.status] || a.status;

        html += `<tr>
            <td>${a.task_name}</td>
            <td><span class="criticality-badge ${critClass}">${critLabel}</span></td>`;
        if (showDate) html += `<td>${a.date}</td>`;
        html += `<td>${a.block || ''}</td>
            <td>${statusLabel}</td>
            <td>${a.employee_name || ''}</td>
            <td>${a.comment || ''}</td>
        </tr>`;
    });

    tbody.innerHTML = html;
}
