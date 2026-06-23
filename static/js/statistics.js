    document.addEventListener('DOMContentLoaded', function() {
        loadStatistics();
    });

    function loadStatistics() {
        const teamId = document.getElementById('statsTeamSelect').value;

        fetch(`/api/statistics/${teamId}`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('totalActive').textContent = data.total_active;
                document.getElementById('critHigh').textContent = data.criticality.high || 0;
                document.getElementById('critMedium').textContent = data.criticality.medium || 0;
                document.getElementById('critLow').textContent = data.criticality.low || 0;
                document.getElementById('statusNew').textContent = data.status_today.new || 0;
                document.getElementById('statusPlanned').textContent = data.status_today.planned || 0;
                document.getElementById('statusRollback').textContent = data.status_today.rollback || 0;
                document.getElementById('statusSuccess').textContent = data.status_today.success || 0;
            })
            .catch(error => {
                console.error('Error loading statistics:', error);
            });
    }
