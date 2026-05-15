// Team Performance Dashboard Charts

// Color palette
const colors = {
    primary: '#0052cc',
    success: '#36b37e',
    warning: '#ffab00',
    danger: '#de350b',
    neutral: '#6b778c',
    palette: ['#0052cc', '#36b37e', '#ffab00', '#de350b', '#6554c0', '#00b8d9', '#ff5630', '#57d9a3']
};

// Status color mapping
const statusColors = {
    'To Do': '#6b778c',
    'Re-opened': '#de350b',
    'In Progress': '#0052cc',
    'Ready for Deployment': '#00b8d9',
    'Dev Checks': '#6554c0',
    'Ready for Testing': '#ffab00',
    'Ready for Production': '#36b37e',
    'Done': '#57d9a3'
};

let reopenChart = null;
let timeInStatusChart = null;

// Fetch dashboard data
async function fetchDashboardData() {
    try {
        const response = await fetch('/api/summary');
        if (!response.ok) throw new Error('Failed to fetch data');
        return await response.json();
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
        return null;
    }
}

// Update summary cards
function updateSummaryCards(data) {
    const velocity = data.velocity || {};

    document.getElementById('velocityThisWeek').textContent = velocity.this_week || 0;
    document.getElementById('velocityLastWeek').textContent = velocity.last_week || 0;

    const trendEl = document.getElementById('velocityTrend');
    const trend = velocity.trend || 0;
    trendEl.textContent = (trend >= 0 ? '+' : '') + trend + '%';
    trendEl.className = 'metric ' + (trend >= 0 ? 'positive' : 'negative');

    const staleTickets = data.stale_tickets || [];
    document.getElementById('staleCount').textContent = staleTickets.length;

    document.getElementById('lastUpdated').textContent =
        data.generated_at ? new Date(data.generated_at).toLocaleString() : 'Unknown';
}

// Render reopen rate chart
function renderReopenChart(reopenRates) {
    const ctx = document.getElementById('reopenChart').getContext('2d');

    const labels = Object.keys(reopenRates);
    const rates = labels.map(name => reopenRates[name].rate);
    const backgroundColors = rates.map(rate =>
        rate > 30 ? colors.danger : rate > 15 ? colors.warning : colors.success
    );

    if (reopenChart) {
        reopenChart.destroy();
    }

    reopenChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Reopen Rate (%)',
                data: rates,
                backgroundColor: backgroundColors,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            const name = context.label;
                            const stats = reopenRates[name];
                            return `${stats.reopened} of ${stats.total} tickets`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { callback: value => value + '%' }
                }
            }
        }
    });
}

// Render time in status chart
function renderTimeInStatusChart(timeInStatus) {
    const ctx = document.getElementById('timeInStatusChart').getContext('2d');

    // Get all unique statuses
    const allStatuses = new Set();
    Object.values(timeInStatus).forEach(statuses => {
        Object.keys(statuses).forEach(s => allStatuses.add(s));
    });
    const statusList = Array.from(allStatuses);

    // Build datasets
    const assignees = Object.keys(timeInStatus);
    const datasets = statusList.map((status, index) => ({
        label: status,
        data: assignees.map(a => timeInStatus[a][status] || 0),
        backgroundColor: statusColors[status] || colors.palette[index % colors.palette.length],
        borderRadius: 2
    }));

    if (timeInStatusChart) {
        timeInStatusChart.destroy();
    }

    timeInStatusChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: assignees,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 8, font: { size: 10 } }
                }
            },
            scales: {
                x: { stacked: true },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { callback: value => value + 'h' }
                }
            }
        }
    });
}

// Render stale tickets table
function renderStaleTable(staleTickets, jiraUrl) {
    const tbody = document.querySelector('#staleTable tbody');
    tbody.innerHTML = '';

    if (!staleTickets || staleTickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#6b778c;">No stale tickets</td></tr>';
        return;
    }

    staleTickets.slice(0, 10).forEach(ticket => {
        const tr = document.createElement('tr');
        const badgeClass = ticket.days_stale > 7 ? 'danger' : 'warning';

        tr.innerHTML = `
            <td><a href="${jiraUrl}/browse/${ticket.ticket_key}" target="_blank">${ticket.ticket_key}</a></td>
            <td>${(ticket.summary || '').substring(0, 50)}${ticket.summary && ticket.summary.length > 50 ? '...' : ''}</td>
            <td>${ticket.assignee || 'Unassigned'}</td>
            <td>${ticket.status}</td>
            <td><span class="badge ${badgeClass}">${ticket.days_stale} days</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Render reopen stats table
function renderReopenTable(reopenRates) {
    const tbody = document.querySelector('#reopenTable tbody');
    tbody.innerHTML = '';

    const sortedEntries = Object.entries(reopenRates)
        .sort((a, b) => b[1].rate - a[1].rate);

    sortedEntries.forEach(([name, stats]) => {
        const tr = document.createElement('tr');
        const badgeClass = stats.rate > 30 ? 'danger' : stats.rate > 15 ? 'warning' : 'success';

        tr.innerHTML = `
            <td>${name}</td>
            <td>${stats.total}</td>
            <td>${stats.reopened}</td>
            <td><span class="badge ${badgeClass}">${stats.rate}%</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Get Jira URL from page (set by Flask template)
function getJiraUrl() {
    const link = document.querySelector('footer a');
    return link ? link.href : '';
}

// Fetch and display AI insights
async function loadAiInsights() {
    const container = document.getElementById('aiInsights');
    const timestamp = document.getElementById('aiTimestamp');

    try {
        const response = await fetch('/api/ai-insights');
        const data = await response.json();

        if (data.insights) {
            container.innerHTML = data.insights;
            timestamp.textContent = data.generated_at
                ? new Date(data.generated_at).toLocaleString()
                : 'Unknown';
        } else {
            container.innerHTML = `<p class="no-insights">${data.message || 'No analysis available yet.'}</p>`;
            timestamp.textContent = '-';
        }
    } catch (error) {
        container.innerHTML = '<p class="no-insights">Failed to load AI insights.</p>';
        console.error('Error loading AI insights:', error);
    }
}

// Refresh AI insights (trigger new analysis)
async function refreshAiInsights() {
    const btn = document.getElementById('refreshAiBtn');
    const container = document.getElementById('aiInsights');

    btn.disabled = true;
    btn.textContent = 'Analyzing...';
    container.innerHTML = '<p class="loading">Claude is analyzing your team data...</p>';

    try {
        const response = await fetch('/api/ai-insights/generate', {
            method: 'POST'
        });
        const data = await response.json();

        if (data.insights) {
            container.innerHTML = data.insights;
            document.getElementById('aiTimestamp').textContent =
                new Date(data.generated_at).toLocaleString();
        } else {
            container.innerHTML = `<p class="no-insights">Error: ${data.error || 'Unknown error'}</p>`;
        }
    } catch (error) {
        container.innerHTML = '<p class="no-insights">Failed to generate analysis. Is Claude Code installed?</p>';
        console.error('Error generating AI insights:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Refresh Analysis';
    }
}

// Initialize dashboard
async function initDashboard() {
    const data = await fetchDashboardData();

    if (!data) {
        document.querySelector('main').innerHTML = `
            <div class="loading">
                <p>Failed to load dashboard data.</p>
                <p>Make sure you've run the data collector first.</p>
            </div>
        `;
        return;
    }

    const jiraUrl = getJiraUrl();

    updateSummaryCards(data);
    renderReopenChart(data.reopen_rates || {});
    renderTimeInStatusChart(data.time_in_status || {});
    renderStaleTable(data.stale_tickets || [], jiraUrl);
    renderReopenTable(data.reopen_rates || {});

    // Load AI insights
    loadAiInsights();
}

// Auto-refresh every 5 minutes
setInterval(initDashboard, 5 * 60 * 1000);

// Load on page ready
document.addEventListener('DOMContentLoaded', initDashboard);
