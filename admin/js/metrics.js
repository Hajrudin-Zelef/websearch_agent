// ─── Real-time Metrics Dashboard ───
const METRICS_POLL_MS = 5000;
const METRICS_MAX_POINTS = 60;
let metricsInterval = null;
let metricsBuffer = [];
let metricsActive = false;

function startMetricsPolling() {
    if (metricsActive) return;
    metricsActive = true;
    fetchMetrics();
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
