let logInterval = null;
let logsPaused = false;
let logsData = [];
let logsFiltered = [];
let logsCurrentLevel = 'all';
let logsCurrentCategory = 'all';

function setLogLevel(level, btn) {
    logsCurrentLevel = level;
    document.querySelectorAll('.logs-filter-group:first-child .logs-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    filterLogs();
}

function setLogCategory(category, btn) {
    logsCurrentCategory = category;
    document.querySelectorAll('.logs-filter-group:nth-child(2) .logs-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    filterLogs();
}

function filterLogs() {
    const searchTerm = ($('#logs-search')?.value || '').toLowerCase();

    logsFiltered = logsData.filter(log => {
        if (logsCurrentLevel !== 'all' && log.level !== logsCurrentLevel) return false;
        if (logsCurrentCategory !== 'all' && log.category !== logsCurrentCategory) return false;
        if (searchTerm && !log.message.toLowerCase().includes(searchTerm)) return false;
        return true;
    });

    renderLogsTimeline();
}

function startLogs() {
    logsPaused = false;
    $('#btn-logs-start').classList.add('hidden');
    $('#btn-logs-stop').classList.remove('hidden');
    $('#logs-live-badge').classList.add('connected');
    const emptyEl = $('#logs-empty-state');
    if (emptyEl) emptyEl.remove();

    fetchLogs();
    logInterval = setInterval(fetchLogs, 3000);
}

async function fetchLogs() {
    if (logsPaused) return;
    try {
        const data = await api('/admin/logs?lines=200');
        logsData = data.logs || [];

        const stats = data.stats || {};
        $('#logs-count-total').textContent = stats.total || 0;
        $('#logs-count-error').textContent = stats.error || 0;
        $('#logs-count-warn').textContent = stats.warning || 0;
        $('#logs-count-info').textContent = stats.info || 0;

        const now = new Date();
        $('#logs-last-update').textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        filterLogs();
        initIcons();
    } catch (e) {}
}

function stopLogs() {
    logsPaused = true;
    if (logInterval) { clearInterval(logInterval); logInterval = null; }
    $('#btn-logs-start').classList.remove('hidden');
    $('#btn-logs-stop').classList.add('hidden');
    $('#logs-live-badge').classList.remove('connected');
}

function clearLogs() {
    logsData = [];
    logsFiltered = [];
    if (logInterval) { clearInterval(logInterval); logInterval = null; }
    logsPaused = true;
    $('#btn-logs-start').classList.remove('hidden');
    $('#btn-logs-stop').classList.add('hidden');
    $('#logs-live-badge').classList.remove('connected');
    $('#logs-count-error').textContent = '0';
    $('#logs-count-warn').textContent = '0';
    $('#logs-count-info').textContent = '0';
    $('#logs-count-total').textContent = '0';
    $('#logs-last-update').textContent = '—';
    $('#log-output').innerHTML = `
        <div class="logs-empty" id="logs-empty-state">
            <div class="logs-empty-icon"><i data-lucide="activity" style="width:32px;height:32px"></i></div>
            <div class="logs-empty-title">Aucun evenement detecte</div>
            <div class="logs-empty-desc">Les journaux systeme apparaitront ici en temps reel.</div>
            <button onclick="startLogs()" class="btn btn-sm btn-primary" style="margin-top:var(--sp-4)">
                <i data-lucide="play" style="width:12px;height:12px"></i> Actualiser
            </button>
        </div>`;
    initIcons();
}

function downloadLogs() {
    if (!logsData.length) return;
    const blob = new Blob([logsData.map(l => l.raw).join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Logs telecharges', 'success');
}

function renderLogsTimeline() {
    const box = $('#log-output');

    if (logsFiltered.length === 0) {
        box.innerHTML = `
            <div class="logs-empty">
                <div class="logs-empty-icon"><i data-lucide="search" style="width:24px;height:24px"></i></div>
                <div class="logs-empty-title">${logsData.length === 0 ? 'Aucun evenement' : 'Aucun resultat'}</div>
                <div class="logs-empty-desc">${logsData.length === 0 ? 'Demarrez le stream pour voir les logs.' : 'Modifiez vos filtres.'}</div>
            </div>`;
        initIcons();
        return;
    }

    const categoryIcons = {
        routing: 'route', search: 'globe', llm: 'cpu', cache: 'database',
        auth: 'shield', error: 'alert-circle', security: 'lock', thread: 'message-circle', system: 'server'
    };

    const categoryColors = {
        routing: 'primary', search: 'success', llm: 'secondary', cache: 'warning',
        auth: 'info', error: 'danger', security: 'danger', thread: 'primary', system: 'neutral'
    };

    box.innerHTML = `<div class="logs-timeline-list">` + logsFiltered.map((log, i) => {
        const icon = categoryIcons[log.category] || 'info';
        const color = categoryColors[log.category] || 'neutral';
        const time = log.timestamp ? log.timestamp.split(' ')[1] || log.timestamp : '';
        const detailsHtml = Object.keys(log.details).length > 0
            ? `<div class="log-entry-details">
                ${Object.entries(log.details).map(([k, v]) => {
                    const val = Array.isArray(v) ? v.join(', ') : v;
                    return `<div class="log-entry-detail">
                        <span class="log-entry-label">${k}:</span>
                        <span class="log-entry-value">${escapeHtml(String(val))}</span>
                    </div>`;
                }).join('')}
               </div>`
            : '';

        return `<div class="log-entry timeline" onclick="this.classList.toggle('expanded')">
            <div class="log-entry-left">
                <div class="log-entry-icon ${color}"><i data-lucide="${icon}"></i></div>
                <div class="log-entry-line"></div>
            </div>
            <div class="log-entry-body">
                <div class="log-entry-header">
                    <span class="log-entry-time">${time}</span>
                    <span class="log-entry-level badge badge-${log.level === 'error' ? 'danger' : log.level === 'warning' ? 'warning' : 'primary'}">${log.level}</span>
                    <span class="log-entry-category">${log.category}</span>
                    <i data-lucide="chevron-down" class="log-entry-chevron"></i>
                </div>
                <div class="log-entry-message">${escapeHtml(log.message)}</div>
                ${detailsHtml}
            </div>
        </div>`;
    }).join('') + `</div>`;

    initIcons();
}
