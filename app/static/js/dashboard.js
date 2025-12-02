document.addEventListener('DOMContentLoaded', () => {
    const tableRoot = document.querySelector('#incident-table tbody');
    if (!tableRoot) {
        return;
    }

    const charts = {
        status: null,
        severity: null,
        timeline: null,
    };
    let chartSignature = null;

    async function fetchJson(url, options = {}) {
        const response = await fetch(url, {
            headers: { 'Accept': 'application/json', ...(options.headers || {}) },
            credentials: 'same-origin',
            ...options,
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || response.statusText);
        }
        return response.json();
    }

    function formatDate(value) {
        if (!value) {
            return '-';
        }
        const date = new Date(value);
        return date.toLocaleString();
    }

    function renderMetricCards(metrics) {
        const { status_breakdown, total_incidents, avg_ack_minutes, avg_resolution_minutes } = metrics;
        document.querySelector('#total-incidents').textContent = total_incidents;
        document.querySelector('#open-incidents').textContent = status_breakdown.open ?? 0;
        document.querySelector('#ack-incidents').textContent = status_breakdown.acknowledged ?? 0;
        document.querySelector('#resolved-incidents').textContent = status_breakdown.resolved ?? 0;
        const badge = document.querySelector('#avg-response');
        const ack = avg_ack_minutes ? `Ack: ${avg_ack_minutes}m` : 'Ack: n/a';
        const resolve = avg_resolution_minutes ? `Resolve: ${avg_resolution_minutes}m` : 'Resolve: n/a';
        badge.textContent = `${ack} • ${resolve}`;
    }

    function renderIncidentTable(incidents) {
        tableRoot.innerHTML = '';
        incidents.forEach((incident) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${incident.id}</td>
                <td>
                    <div class="fw-semibold">${incident.title}</div>
                    <div class="small text-muted">${incident.category}</div>
                </td>
                <td><span class="badge bg-${badgeClass(incident.severity)} text-uppercase">${incident.severity}</span></td>
                <td>${incident.status}</td>
                <td>${formatDate(incident.detected_at)}</td>
                <td class="text-nowrap">
                    ${renderActionButtons(incident)}
                </td>
            `;
            tableRoot.appendChild(row);
        });
    }

    function badgeClass(severity) {
        switch (severity) {
            case 'critical':
                return 'danger';
            case 'high':
                return 'warning';
            case 'medium':
                return 'info';
            default:
                return 'secondary';
        }
    }

    function renderActionButtons(incident) {
        if (incident.status === 'resolved') {
            return '<span class="badge bg-success">Closed</span>';
        }
        const ackBtn = incident.status === 'open'
            ? `<button class="btn btn-sm btn-outline-primary me-1" data-action="ack" data-id="${incident.id}">Ack</button>`
            : '';
        const resolveBtn = `<button class="btn btn-sm btn-outline-success" data-action="resolve" data-id="${incident.id}">Resolve</button>`;
        return `${ackBtn}${resolveBtn}`;
    }

    function metricsSignature(metrics) {
        return JSON.stringify({
            status: metrics.status_breakdown,
            severity: metrics.severity_breakdown,
            timeline: metrics.incidents_timeline,
        });
    }

    function renderCharts(metrics) {
        const statusCtx = document.getElementById('status-chart');
        const severityCtx = document.getElementById('severity-chart');
        const timelineCtx = document.getElementById('timeline-chart');

        const statusLabels = Object.keys(metrics.status_breakdown);
        const statusValues = Object.values(metrics.status_breakdown);
        const severityLabels = Object.keys(metrics.severity_breakdown);
        const severityValues = Object.values(metrics.severity_breakdown);
        const timelineLabels = metrics.incidents_timeline.map((item) => item[0]);
        const timelineValues = metrics.incidents_timeline.map((item) => item[1]);

        if (charts.status) charts.status.destroy();
        if (charts.severity) charts.severity.destroy();
        if (charts.timeline) charts.timeline.destroy();

        charts.status = new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: statusLabels,
                datasets: [{
                    data: statusValues,
                    backgroundColor: ['#dc3545', '#ffc107', '#198754'],
                }],
            },
            options: { plugins: { legend: { position: 'bottom' } } },
        });

        charts.severity = new Chart(severityCtx, {
            type: 'bar',
            data: {
                labels: severityLabels,
                datasets: [{
                    label: 'Incidents',
                    data: severityValues,
                    backgroundColor: '#0d6efd',
                }],
            },
            options: {
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
            },
        });

        charts.timeline = new Chart(timelineCtx, {
            type: 'line',
            data: {
                labels: timelineLabels,
                datasets: [{
                    label: 'Incidents',
                    data: timelineValues,
                    tension: 0.3,
                    borderColor: '#6610f2',
                    backgroundColor: 'rgba(102, 16, 242, 0.2)',
                    fill: true,
                }],
            },
            options: {
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 } },
                },
            },
        });
    }

    function renderSensors(sensors) {
        const list = document.getElementById('sensor-list');
        const rationalePane = document.getElementById('ai-rationale');
        list.innerHTML = '';
        sensors.forEach((sensor) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = `list-group-item list-group-item-action d-flex justify-content-between align-items-center status-${sensor.status}`;
            item.textContent = `${sensor.id} (${sensor.type})`;
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary rounded-pill';
            const prediction = sensor.prediction || {};
            badge.textContent = `Risk ${prediction.score ?? '0.0'}`;
            item.appendChild(badge);
            item.addEventListener('click', () => {
                list.querySelectorAll('.list-group-item').forEach((node) => node.classList.remove('active'));
                item.classList.add('active');
                const rationale = prediction.rationale?.length ? prediction.rationale.join('; ') : 'No AI rationale available.';
                rationalePane.textContent = `${sensor.id}: ${rationale}`;
            });
            list.appendChild(item);
        });
        if (sensors.length) {
            list.querySelector('.list-group-item').click();
        }
    }

    async function patchIncident(id, status) {
        await fetchJson(`/api/incidents/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status }),
        });
    }

    async function refreshDashboard() {
        const data = await fetchJson('/api/dashboard');
        renderMetricCards(data.metrics);
        renderIncidentTable(data.incidents);
        const nextSignature = metricsSignature(data.metrics);
        if (nextSignature !== chartSignature) {
            renderCharts(data.metrics);
            chartSignature = nextSignature;
        }
        renderSensors(data.sensors);
    }

    async function refreshSensors() {
        const data = await fetchJson('/api/sensors');
        renderSensors(data.sensors);
    }

    async function simulateIncident() {
        const notice = document.getElementById('ai-rationale');
        notice.textContent = 'Running simulation...';
        const data = await fetchJson('/api/simulate', { method: 'POST' });
        if (data.created_incident) {
            notice.textContent = `Simulation created incident ${data.created_incident.id}.`;
        } else {
            notice.textContent = 'Simulation completed without creating an incident.';
        }
        await refreshDashboard();
    }

    document.addEventListener('click', async (event) => {
        const button = event.target;
        if (!(button instanceof HTMLButtonElement)) {
            return;
        }
        const action = button.dataset.action;
        if (!action) {
            return;
        }
        const id = Number.parseInt(button.dataset.id, 10);
        try {
            if (action === 'ack') {
                await patchIncident(id, 'acknowledged');
            }
            if (action === 'resolve') {
                await patchIncident(id, 'resolved');
            }
            await refreshDashboard();
        } catch (error) {
            console.error('Failed to update incident', error);
        }
    });

    const simulateBtn = document.getElementById('simulate-btn');
    if (simulateBtn) {
        simulateBtn.addEventListener('click', () => {
            simulateIncident().catch((error) => {
                console.error('Simulation failed', error);
                const notice = document.getElementById('ai-rationale');
                notice.textContent = `Simulation failed: ${error.message}`;
            });
        });
    }

    refreshDashboard().catch((error) => console.error('Failed to load dashboard', error));
    setInterval(() => {
        refreshDashboard().catch((error) => console.error('Refresh failed', error));
        refreshSensors().catch((error) => console.error('Sensor refresh failed', error));
    }, 15000);

});
