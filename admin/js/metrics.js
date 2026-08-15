async function loadMetrics() {
    try {
        const data = await api('/metrics');

        const sources = data.sources || {};
        const totalCalls = Object.values(sources).reduce((s, v) => s + (v.calls || 0), 0);
        const totalSuccess = Object.values(sources).reduce((s, v) => s + (v.success || 0), 0);
        const totalErrors = Object.values(sources).reduce((s, v) => s + (v.errors || 0), 0);

        $('#metrics-sources-total').textContent = totalCalls;
        $('#metrics-sources-success').textContent = totalSuccess;
        $('#metrics-sources-errors').textContent = totalErrors;

        const cache = data.cache || {};
        $('#metrics-cache-hits').textContent = cache.hits || 0;
        $('#metrics-cache-misses').textContent = cache.misses || 0;
        $('#metrics-cache-rate').textContent = ((cache.hit_rate || 0) * 100).toFixed(1) + '%';
        $('#metrics-cache-size').textContent = `${cache.size || 0}/${cache.max_size || 200}`;

        const allTimes = Object.values(sources).filter(s => s.avg_time > 0);
        if (allTimes.length > 0) {
            const avgLatency = allTimes.reduce((s, v) => s + v.avg_time, 0) / allTimes.length;
            const minLatency = Math.min(...allTimes.map(s => s.avg_time));
            const maxLatency = Math.max(...allTimes.map(s => s.max_time));
            $('#metrics-latency-avg').textContent = (avgLatency * 1000).toFixed(0) + 'ms';
            $('#metrics-latency-min').textContent = (minLatency * 1000).toFixed(0) + 'ms';
            $('#metrics-latency-max').textContent = (maxLatency * 1000).toFixed(0) + 'ms';
        }

        const sourceNames = Object.keys(sources).sort();
        if (sourceNames.length > 0) {
            let html = '<table style="width:100%;border-collapse:collapse;font-size:13px">';
            html += '<tr style="border-bottom:1px solid var(--border);text-align:left"><th style="padding:8px">Source</th><th>Appels</th><th>Succes</th><th>Erreurs</th><th>Taux</th><th>Moyen</th></tr>';
            for (const name of sourceNames) {
                const s = sources[name];
                const errorRate = s.calls > 0 ? ((s.errors / s.calls) * 100).toFixed(1) : '0';
                const avgMs = s.avg_time ? (s.avg_time * 1000).toFixed(0) : '0';
                html += `<tr style="border-bottom:1px solid var(--border)">
                    <td style="padding:8px;font-weight:500">${escapeHtml(name)}</td>
                    <td>${s.calls}</td>
                    <td style="color:var(--success)">${s.success}</td>
                    <td style="color:${s.errors > 0 ? 'var(--danger)' : 'var(--text-muted)'}">${s.errors}</td>
                    <td>${errorRate}%</td>
                    <td>${avgMs}ms</td>
                </tr>`;
            }
            html += '</table>';
            $('#metrics-sources-table').innerHTML = html;
        } else {
            $('#metrics-sources-table').innerHTML = '<p class="text-muted">Aucune source utilisee pour le moment</p>';
        }
    } catch (e) {
        console.error('Metrics error:', e);
    }
}
