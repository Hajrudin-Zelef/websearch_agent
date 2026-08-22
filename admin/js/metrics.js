// ─── Real-time Metrics Dashboard ───
const METRICS_POLL_MS = 5000;
const METRICS_MAX_POINTS = 60;
let metricsInterval = null;
let metricsBuffer = [];
let metricsActive = false;

async function loadMetricsHistory() {
    try {
        const data = await api('/admin/metrics/history?since_seconds=3600');
        const history = data.history || [];
        metricsBuffer = history.slice(-METRICS_MAX_POINTS).map(row => ({
            ts: row.ts * 1000,
            sources: {},
            cache: { hits: row.cache_hits, misses: row.cache_misses },
            agent: { calls: row.agent_calls, success: row.agent_success, avg_time: row.agent_avg_time },
            circuit_breaker: {},
            _totalCalls: row.sources_calls,
            _totalSuccess: row.sources_success,
            _totalErrors: row.sources_errors,
            _chatCalls: row.chat_calls,
            _chatAvgTime: row.chat_avg_time,
            _searchCalls: row.search_calls,
            _searchAvgTime: row.search_avg_time,
        }));
    } catch (e) {
        console.error('Erreur chargement historique metriques:', e);
    }
}

function startMetricsPolling() {
    if (metricsActive) return;
    metricsActive = true;
    loadMetricsHistory().then(() => {
        if (metricsBuffer.length > 0) {
            renderCallsChart();
            renderLatencyChart();
        }
        fetchMetrics();
    });
    metricsInterval = setInterval(fetchMetrics, METRICS_POLL_MS);
    const badge = $('#metrics-live-badge');
    if (badge) badge.classList.add('connected');
}

function stopMetricsPolling() {
    metricsActive = false;
    if (metricsInterval) { clearInterval(metricsInterval); metricsInterval = null; }
    const badge = $('#metrics-live-badge');
    if (badge) badge.classList.remove('connected');
}

async function fetchMetrics() {
    try {
        const data = await api('/metrics');
        const point = {
            ts: Date.now(),
            sources: data.sources || {},
            cache: data.cache || {},
            agent: data.agent || {},
            circuit_breaker: data.circuit_breaker || {},
            by_origin: data.by_origin || {},
        };
        metricsBuffer.push(point);
        if (metricsBuffer.length > METRICS_MAX_POINTS) metricsBuffer.shift();
        renderMetricsDashboard(point);
    } catch (e) {}
}

function renderMetricsDashboard(point) {
    const sources = point.sources;
    const cache = point.cache;
    const agent = point.agent;
    const cb = point.circuit_breaker;

    // ─── Cards ───
    const totalCalls = Object.values(sources).reduce((s, v) => s + (v.calls || 0), 0);
    const totalSuccess = Object.values(sources).reduce((s, v) => s + (v.success || 0), 0);
    const totalErrors = Object.values(sources).reduce((s, v) => s + (v.errors || 0), 0);

    $('#metrics-sources-total').textContent = totalCalls;
    $('#metrics-sources-success').textContent = totalSuccess;
    $('#metrics-sources-errors').textContent = totalErrors;

    // ─── Cache ───
    $('#metrics-cache-hits').textContent = cache.hits || 0;
    $('#metrics-cache-misses').textContent = cache.misses || 0;
    $('#metrics-cache-rate').textContent = ((cache.hit_rate || 0) * 100).toFixed(1) + '%';
    $('#metrics-cache-size').textContent = `${cache.size || 0}/${cache.max_size || 200}`;

    // ─── Latency ───
    const allTimes = Object.values(sources).filter(s => s.avg_time > 0);
    if (allTimes.length > 0) {
        const avgLatency = allTimes.reduce((s, v) => s + v.avg_time, 0) / allTimes.length;
        const minLatency = Math.min(...allTimes.map(s => s.avg_time));
        const maxLatency = Math.max(...allTimes.map(s => s.max_time));
        $('#metrics-latency-avg').textContent = (avgLatency * 1000).toFixed(0) + 'ms';
        $('#metrics-latency-min').textContent = (minLatency * 1000).toFixed(0) + 'ms';
        $('#metrics-latency-max').textContent = (maxLatency * 1000).toFixed(0) + 'ms';
    }

    // ─── Agent stats ───
    const agentEl = $('#metrics-agent-calls');
    if (agentEl) agentEl.textContent = agent.calls || 0;
    const agentRateEl = $('#metrics-agent-rate');
    if (agentRateEl) {
        const rate = agent.calls > 0 ? ((agent.success / agent.calls) * 100).toFixed(1) : '0';
        agentRateEl.textContent = rate + '%';
    }

    // ─── SVG Charts ───
    renderCallsChart();
    renderLatencyChart();

    // ─── Circuit Breaker ───
    renderCircuitBreakers(cb);

    // ─── Source Table ───
    renderSourceTable(sources);

    // ─── Breakdown Chat vs Search ───
    renderOriginBreakdown(point.by_origin || {});
}

function renderOriginBreakdown(byOrigin) {
    const container = $('#metrics-origin-breakdown');
    if (!container) return;

    const chat = byOrigin.chat || { calls: 0, success: 0, errors: 0, avg_time: 0, error_rate: 0 };
    const search = byOrigin.search || { calls: 0, success: 0, errors: 0, avg_time: 0, error_rate: 0 };
    const total = chat.calls + search.calls;
    const chatPct = total > 0 ? Math.round((chat.calls / total) * 100) : 0;
    const searchPct = total > 0 ? Math.round((search.calls / total) * 100) : 0;

    container.innerHTML = `
        <div class="origin-breakdown-row">
            <div class="origin-breakdown-item">
                <div class="origin-breakdown-label"><i data-lucide="message-circle" style="width:14px;height:14px"></i> Chat</div>
                <div class="origin-breakdown-value">${chat.calls} appels</div>
                <div class="origin-breakdown-bar"><div class="origin-breakdown-fill" style="width:${chatPct}%;background:var(--primary)"></div></div>
                <div class="origin-breakdown-meta">${(chat.avg_time * 1000).toFixed(0)}ms moyen · ${(chat.error_rate * 100).toFixed(1)}% erreurs</div>
            </div>
            <div class="origin-breakdown-item">
                <div class="origin-breakdown-label"><i data-lucide="search" style="width:14px;height:14px"></i> Search</div>
                <div class="origin-breakdown-value">${search.calls} appels</div>
                <div class="origin-breakdown-bar"><div class="origin-breakdown-fill" style="width:${searchPct}%;background:var(--secondary)"></div></div>
                <div class="origin-breakdown-meta">${(search.avg_time * 1000).toFixed(0)}ms moyen · ${(search.error_rate * 100).toFixed(1)}% erreurs</div>
            </div>
        </div>`;
    initIcons();
}

function renderCallsChart() {
    const svg = $('#chart-calls');
    if (!svg || metricsBuffer.length < 2) return;

    const w = 500, h = 80, pad = 4;
    const points = metricsBuffer.map((p, i) => {
        const total = Object.values(p.sources).reduce((s, v) => s + (v.calls || 0), 0);
        return { x: (i / (METRICS_MAX_POINTS - 1)) * w, v: total };
    });
    const maxV = Math.max(1, ...points.map(p => p.v));

    const pathD = points.map((p, i) => {
        const y = h - pad - ((p.v / maxV) * (h - pad * 2));
        return `${i === 0 ? 'M' : 'L'}${p.x},${y}`;
    }).join(' ');

    const areaD = pathD + ` L${w},${h} L0,${h} Z`;

    svg.innerHTML = `
        <defs>
            <linearGradient id="callsGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--primary)" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="var(--primary)" stop-opacity="0"/>
            </linearGradient>
        </defs>
        <path d="${areaD}" fill="url(#callsGrad)"/>
        <path d="${pathD}" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${points[points.length-1].x}" cy="${h - pad - ((points[points.length-1].v / maxV) * (h - pad * 2))}" r="3" fill="var(--primary)"/>
    `;

    const label = $('#chart-calls-label');
    if (label) {
        const last = points[points.length - 1].v;
        const prev = points.length > 1 ? points[points.length - 2].v : last;
        const delta = last - prev;
        label.textContent = `${last} total`;
        if (delta > 0) label.innerHTML += ` <span style="color:var(--success)">+${delta}</span>`;
        else if (delta < 0) label.innerHTML += ` <span style="color:var(--danger)">${delta}</span>`;
    }
}

function renderLatencyChart() {
    const svg = $('#chart-latency');
    if (!svg || metricsBuffer.length < 2) return;

    const w = 500, h = 80, pad = 4;
    const points = metricsBuffer.map((p, i) => {
        const allT = Object.values(p.sources).filter(s => s.avg_time > 0);
        const avg = allT.length > 0 ? allT.reduce((s, v) => s + v.avg_time, 0) / allT.length : 0;
        return { x: (i / (METRICS_MAX_POINTS - 1)) * w, v: avg * 1000 };
    });
    const maxV = Math.max(100, ...points.map(p => p.v));

    const pathD = points.map((p, i) => {
        const y = h - pad - ((p.v / maxV) * (h - pad * 2));
        return `${i === 0 ? 'M' : 'L'}${p.x},${y}`;
    }).join(' ');

    const areaD = pathD + ` L${w},${h} L0,${h} Z`;

    svg.innerHTML = `
        <defs>
            <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--warning)" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="var(--warning)" stop-opacity="0"/>
            </linearGradient>
        </defs>
        <path d="${areaD}" fill="url(#latGrad)"/>
        <path d="${pathD}" fill="none" stroke="var(--warning)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${points[points.length-1].x}" cy="${h - pad - ((points[points.length-1].v / maxV) * (h - pad * 2))}" r="3" fill="var(--warning)"/>
    `;

    const label = $('#chart-latency-label');
    if (label) {
        const last = points[points.length - 1].v;
        label.textContent = `${last.toFixed(0)}ms moyen`;
    }
}

function renderCircuitBreakers(cb) {
    const container = $('#metrics-circuit-breakers');
    if (!container) return;

    const states = Object.entries(cb);
    if (states.length === 0) {
        container.innerHTML = '<p class="text-muted">Aucun circuit breaker</p>';
        return;
    }

    container.innerHTML = states.map(([name, info]) => {
        const state = info.state || 'unknown';
        const color = state === 'closed' ? 'success' : state === 'open' ? 'danger' : 'warning';
        const icon = state === 'closed' ? 'shield-check' : state === 'open' ? 'shield-x' : 'shield-alert';
        return `
            <div class="cb-badge">
                <i data-lucide="${icon}" style="width:14px;height:14px;color:var(--${color})"></i>
                <span class="cb-name">${escapeHtml(name.replace('_search', ''))}</span>
                <span class="badge badge-${color}" style="font-size:10px">${state}</span>
                ${info.failures > 0 ? `<span class="cb-failures">${info.failures} fail</span>` : ''}
            </div>`;
    }).join('');
    initIcons();
}

function renderSourceTable(sources) {
    const container = $('#metrics-sources-table');
    if (!container) return;

    const sourceNames = Object.keys(sources).sort();
    if (sourceNames.length === 0) {
        container.innerHTML = '<p class="text-muted">Aucune source utilisee pour le moment</p>';
        return;
    }

    let html = '<table class="metrics-table">';
    html += '<tr><th>Source</th><th>Appels</th><th>Succes</th><th>Erreurs</th><th>Taux</th><th>Moyen</th></tr>';
    for (const name of sourceNames) {
        const s = sources[name];
        const errorRate = s.calls > 0 ? ((s.errors / s.calls) * 100).toFixed(1) : '0';
        const avgMs = s.avg_time ? (s.avg_time * 1000).toFixed(0) : '0';
        html += `<tr>
            <td style="font-weight:500">${escapeHtml(name)}</td>
            <td>${s.calls}</td>
            <td style="color:var(--success)">${s.success}</td>
            <td style="color:${s.errors > 0 ? 'var(--danger)' : 'var(--text-muted)'}">${s.errors}</td>
            <td>${errorRate}%</td>
            <td>${avgMs}ms</td>
        </tr>`;
    }
    html += '</table>';
    container.innerHTML = html;
}

// ─── Metrics Detail Panel (reutilise le style logs-panel) ───
function showMetricsDetail(type) {
    document.querySelectorAll('.logs-panel, .logs-panel-overlay').forEach(el => el.remove());

    const point = metricsBuffer[metricsBuffer.length - 1] || { sources: {}, agent: {}, by_origin: {} };
    const titles = {
        sources: 'Sources — detail',
        success: 'Appels reussis',
        errors: 'Erreurs',
        agent: 'Agent — detail',
    };

    document.body.insertAdjacentHTML('beforeend', `
        <div class="logs-panel-overlay" onclick="closeLogsPanel()"></div>
        <div class="logs-panel" id="logs-panel">
            <div class="logs-panel-header">
                <div class="logs-panel-title">
                    <div class="logs-panel-icon"><i data-lucide="bar-chart-2"></i></div>
                    <div><h3>${titles[type] || 'Detail'}</h3></div>
                </div>
                <button class="btn btn-sm btn-ghost" onclick="closeLogsPanel()"><i data-lucide="x"></i></button>
            </div>
            <div class="logs-panel-section" style="flex:1;overflow-y:auto" id="metrics-detail-body">
                ${buildMetricsDetailContent(type, point)}
            </div>
        </div>`);

    refreshLogsPanelIcons();
    requestAnimationFrame(() => {
        const p = document.getElementById('logs-panel');
        if (p) p.classList.add('open');
    });
}

function buildMetricsDetailContent(type, point) {
    const sources = point.sources || {};
    const byOrigin = point.by_origin || {};
    const agent = point.agent || {};

    if (type === 'agent') {
        const rate = agent.calls > 0 ? ((agent.success / agent.calls) * 100).toFixed(1) : '0';
        return `
            <div class="logs-panel-stats" style="margin-bottom:var(--sp-4)">
                <div class="logs-stat-mini"><div class="logs-stat-mini-value">${agent.calls || 0}</div><div class="logs-stat-mini-label">Appels</div></div>
                <div class="logs-stat-mini"><div class="logs-stat-mini-value">${agent.success || 0}</div><div class="logs-stat-mini-label">Succes</div></div>
                <div class="logs-stat-mini"><div class="logs-stat-mini-value">${agent.errors || 0}</div><div class="logs-stat-mini-label">Erreurs</div></div>
                <div class="logs-stat-mini"><div class="logs-stat-mini-value">${rate}%</div><div class="logs-stat-mini-label">Taux</div></div>
            </div>
            <div class="logs-panel-section-title">Latence moyenne</div>
            <p style="font-size:var(--text-lg);font-weight:700">${((agent.avg_time || 0) * 1000).toFixed(0)}ms</p>
            <div class="logs-panel-section-title" style="margin-top:var(--sp-4)">Par origine</div>
            ${renderOriginList(byOrigin)}
        `;
    }

    if (type === 'errors') {
        const errored = Object.entries(sources).filter(([, s]) => s.errors > 0).sort((a, b) => b[1].errors - a[1].errors);
        if (errored.length === 0) {
            return '<div class="logs-empty-state"><i data-lucide="check" style="width:40px;height:40px;color:var(--text-faint)"></i><p>Aucune erreur</p></div>';
        }
        return '<table class="metrics-table"><tr><th>Source</th><th>Erreurs</th><th>Appels</th><th>Taux</th></tr>' +
            errored.map(([name, s]) => `<tr>
                <td style="font-weight:500">${escapeHtml(name)}</td>
                <td style="color:var(--danger)">${s.errors}</td>
                <td>${s.calls}</td>
                <td>${(s.error_rate * 100).toFixed(1)}%</td>
            </tr>`).join('') + '</table>';
    }

    if (type === 'success') {
        const withCalls = Object.entries(sources).filter(([, s]) => s.calls > 0).sort((a, b) => b[1].success - a[1].success);
        if (withCalls.length === 0) {
            return '<div class="logs-empty-state"><i data-lucide="inbox" style="width:40px;height:40px;color:var(--text-faint)"></i><p>Aucun appel</p></div>';
        }
        return '<table class="metrics-table"><tr><th>Source</th><th>Succes</th><th>Appels</th><th>Taux</th></tr>' +
            withCalls.map(([name, s]) => `<tr>
                <td style="font-weight:500">${escapeHtml(name)}</td>
                <td style="color:var(--success)">${s.success}</td>
                <td>${s.calls}</td>
                <td>${((s.success / s.calls) * 100).toFixed(1)}%</td>
            </tr>`).join('') + '</table>';
    }

    // sources (default)
    const sourceNames = Object.keys(sources).sort();
    if (sourceNames.length === 0) {
        return '<div class="logs-empty-state"><i data-lucide="inbox" style="width:40px;height:40px;color:var(--text-faint)"></i><p>Aucune source utilisee</p></div>';
    }
    return '<table class="metrics-table"><tr><th>Source</th><th>Appels</th><th>Succes</th><th>Erreurs</th><th>Moyen</th><th>Min</th><th>Max</th></tr>' +
        sourceNames.map(name => {
            const s = sources[name];
            return `<tr>
                <td style="font-weight:500">${escapeHtml(name)}</td>
                <td>${s.calls}</td>
                <td style="color:var(--success)">${s.success}</td>
                <td style="color:${s.errors > 0 ? 'var(--danger)' : 'var(--text-muted)'}">${s.errors}</td>
                <td>${(s.avg_time * 1000).toFixed(0)}ms</td>
                <td>${(s.min_time * 1000).toFixed(0)}ms</td>
                <td>${(s.max_time * 1000).toFixed(0)}ms</td>
            </tr>`;
        }).join('') + '</table>';
}

function renderOriginList(byOrigin) {
    const entries = Object.entries(byOrigin);
    if (entries.length === 0) return '<p class="text-muted">Aucune donnee</p>';
    return entries.map(([origin, s]) => `
        <div class="timeline-detail-row" style="margin-bottom:var(--sp-2)">
            <span class="timeline-detail-label" style="min-width:60px;text-transform:capitalize">${escapeHtml(origin)}</span>
            <span class="timeline-detail-value">${s.calls} appels · ${(s.avg_time * 1000).toFixed(0)}ms moyen · ${(s.error_rate * 100).toFixed(1)}% erreurs</span>
        </div>`).join('');
}
