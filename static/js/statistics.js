const statusLabels = {new: 'Новый', planned: 'Запланировано'};
const critLabels = {high: 'Высокая', medium: 'Средняя', low: 'Низкая'};
const critClasses = {high: 'criticality-high', medium: 'criticality-medium', low: 'criticality-low'};

const STORAGE_STATS_TEAMS = 'statsSelectedTeams';

function saveStatsTeams(ids) { localStorage.setItem(STORAGE_STATS_TEAMS, JSON.stringify(ids)); }
function getSavedStatsTeams() {
    try { return JSON.parse(localStorage.getItem(STORAGE_STATS_TEAMS)) || []; } catch { return []; }
}

function localDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

function getSelectedTeamIds() {
    const allCb = document.getElementById('teamAll');
    if (allCb && allCb.checked) return null;
    const checked = Array.from(document.querySelectorAll('.team-checkbox')).filter(cb => cb.checked);
    return checked.length ? checked.map(cb => cb.value) : null;
}

function buildTeamIdsParam(ids) {
    return ids && ids.length ? `&team_ids=${ids.join(',')}` : '';
}

function onTeamAllChange() {
    const allCb = document.getElementById('teamAll');
    if (allCb.checked) {
        document.querySelectorAll('.team-checkbox').forEach(cb => cb.checked = false);
    }
    updateDropdownLabel('teamDropdownMenu');
    saveStatsTeams(allCb.checked ? [] : getSelectedTeamIds() || []);
    loadAll();
}

function onTeamCheckboxChange() {
    const checked = Array.from(document.querySelectorAll('.team-checkbox')).filter(cb => cb.checked);
    const allCb = document.getElementById('teamAll');
    if (checked.length === 0) {
        allCb.checked = true;
    } else {
        allCb.checked = false;
    }
    updateDropdownLabel('teamDropdownMenu');
    saveStatsTeams(checked.map(cb => cb.value));
    loadAll();
}

document.addEventListener('DOMContentLoaded', function () {
    const saved = getSavedDateRange();
    if (saved.from && saved.to) {
        document.getElementById('statsDateFrom').value = saved.from;
        document.getElementById('statsDateTo').value = saved.to;
    } else {
        const today = new Date();
        const from = new Date(today);
        from.setDate(from.getDate() - 7);
        document.getElementById('statsDateFrom').value = localDateStr(from);
        document.getElementById('statsDateTo').value = localDateStr(today);
    }

    const savedTeams = getSavedStatsTeams();
    if (savedTeams.length > 0) {
        document.getElementById('teamAll').checked = false;
        const ids = savedTeams.map(String);
        document.querySelectorAll('.team-checkbox').forEach(cb => {
            cb.checked = ids.includes(cb.value);
        });
    }
    updateDropdownLabel('teamDropdownMenu');

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

    saveDateRange(document.getElementById('statsDateFrom').value, document.getElementById('statsDateTo').value);
    const from = document.getElementById('statsDateFrom').value;
    const to = document.getElementById('statsDateTo').value;
    if (!from || !to) return;

    const teamIds = getSelectedTeamIds();
    const teamParam = buildTeamIdsParam(teamIds);

    fetch(`/api/active-assignments/0?start_date=${from}&end_date=${to}${teamParam}`)
        .then(r => r.json())
        .then(data => {
            renderCounters(data, 'periodCounters');
            renderTable(data, 'periodTableBody', true);
        })
        .catch(e => console.error('Error loading period data:', e));
}

function loadTodayData() {
    const today = localDateStr(new Date());

    const teamIds = getSelectedTeamIds();
    const teamParam = buildTeamIdsParam(teamIds);

    fetch(`/api/active-assignments/0?start_date=${today}&end_date=${today}${teamParam}`)
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
    const wrapper = document.getElementById(tbodyId.replace('TableBody', 'TableWrapper'));
    const emptyEl = document.getElementById(tbodyId.replace('TableBody', 'Empty'));

    if (data.length === 0) {
        tbody.innerHTML = '';
        if (wrapper) wrapper.style.display = 'none';
        if (emptyEl) emptyEl.style.display = '';
        return;
    }

    if (wrapper) wrapper.style.display = '';
    if (emptyEl) emptyEl.style.display = 'none';

    let html = '';
    data.forEach(a => {
        const critClass = critClasses[a.criticality] || '';
        const critLabel = a.criticality === 'high' ? 'В' : a.criticality === 'medium' ? 'С' : 'Н';
        const statusLabel = statusLabels[a.status] || a.status;

        html += `<tr>
            <td>${a.task_name}</td>
            <td>${a.team_name || ''}</td>
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
