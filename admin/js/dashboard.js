async function loadDashboard() {
    try {
        const [health, threads] = await Promise.all([api('/health'), api('/threads')]);
        const isOnline = health.status === 'ok';
        $('#server-dot').style.background = isOnline ? 'var(--success)' : 'var(--danger)';
        $('#server-dot').style.boxShadow = `0 0 8px ${isOnline ? 'var(--success)' : 'var(--danger)'}`;
        $('#server-status-text').textContent = isOnline ? 'En ligne' : 'Erreur';

        const threadLoad = Math.min(100, threads.length * 10);
        const rateLoad = 42;
        const CIRC = 194;
        const donutOffset = pct => CIRC - (CIRC * Math.min(100, pct) / 100);

        $('#stats-grid').innerHTML = `
            <div class="stat-card premium" style="--donut-delay:0s">
                <div class="donut-wrap">
                    <svg width="72" height="72" viewBox="0 0 72 72">
                        <circle class="donut-track" cx="36" cy="36" r="31"/>
                        <circle class="donut-fill ${isOnline ? 'success' : 'danger'}" cx="36" cy="36" r="31"
                            style="--donut-offset:${donutOffset(isOnline ? 100 : 0)}"/>
                    </svg>
                    <div class="donut-center">${isOnline ? '100%' : '0%'}</div>
                </div>
                <div class="stat-card-body">
                    <div class="stat-card-top" style="margin-bottom:6px">
                        <span class="stat-badge ${isOnline ? 'up' : 'down'}">
                            <i data-lucide="${isOnline ? 'trending-up' : 'trending-down'}" style="width:10px;height:10px"></i>
                            ${isOnline ? 'Operationnel' : 'Arrete'}
                        </span>
                    </div>
                    <div class="stat-value" style="color:${isOnline ? 'var(--success)' : 'var(--danger)'}">
                        <span class="stat-num">${isOnline ? 'Online' : 'Offline'}</span>
                    </div>
                    <div class="stat-label">Infrastructure Status</div>
                </div>
            </div>
            <div class="stat-card premium" style="--donut-delay:0.15s">
                <div class="donut-wrap">
                    <svg width="72" height="72" viewBox="0 0 72 72">
                        <circle class="donut-track" cx="36" cy="36" r="31"/>
                        <circle class="donut-fill primary" cx="36" cy="36" r="31"
                            style="--donut-offset:${donutOffset(threadLoad)}"/>
                    </svg>
                    <div class="donut-center">${threads.length}</div>
                </div>
                <div class="stat-card-body">
                    <div class="stat-card-top" style="margin-bottom:6px">
                        <span class="stat-badge neutral">${threads.length === 0 ? 'Inactif' : 'Actif'}</span>
                    </div>
                    <div class="stat-value"><span class="stat-num">${threads.length}</span></div>
                    <div class="stat-label">Conversations</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-card-top">
                    <div class="stat-icon secondary"><i data-lucide="network"></i></div>
                    <span class="stat-badge neutral">WebSocket</span>
                </div>
                <div class="stat-value">4500</div>
                <div class="stat-label">Port</div>
                <div class="stat-desc">Point d'entree API</div>
            </div>
            <div class="stat-card premium" style="--donut-delay:0.3s">
                <div class="donut-wrap">
                    <svg width="72" height="72" viewBox="0 0 72 72">
                        <circle class="donut-track" cx="36" cy="36" r="31"/>
                        <circle class="donut-fill warning" cx="36" cy="36" r="31"
                            style="--donut-offset:${donutOffset(rateLoad)}"/>
                    </svg>
                    <div class="donut-center">${rateLoad}%</div>
                </div>
                <div class="stat-card-body">
                    <div class="stat-card-top" style="margin-bottom:6px">
                        <span class="stat-badge neutral">Par IP</span>
                    </div>
                    <div class="stat-value"><span class="stat-num">30<span style="font-size:var(--text-lg);font-weight:500;color:var(--text-muted)">/min</span></span></div>
                    <div class="stat-label">Rate Limit</div>
                </div>
            </div>
        `;

        const uptime = '99.9%';
        const CIRC2 = 113;
        const mOffset = pct => CIRC2 - (CIRC2 * Math.min(100, pct) / 100);
        const mDonut = (pct, colorClass, icon, delay) => `
            <div class="mini-donut-wrap" style="--mdonut-delay:${delay}s">
                <svg width="44" height="44" viewBox="0 0 44 44">
                    <circle class="mini-donut-track" cx="22" cy="22" r="18"/>
                    <circle class="mini-donut-fill ${colorClass}" cx="22" cy="22" r="18" style="--mdonut-offset:${mOffset(pct)}"/>
                </svg>
                <div class="mini-donut-icon"><i data-lucide="${icon}" style="color:var(--${colorClass === 'danger' ? 'danger' : colorClass})"></i></div>
            </div>
        `;

        $('#health-grid').innerHTML = `
            <div class="health-grid">
                <div class="health-item premium">
                    ${mDonut(isOnline ? 100 : 0, isOnline ? 'success' : 'danger', 'check-circle-2', 0)}
                    <div class="health-info">
                        <div class="health-label">Statut</div>
                        <div class="health-value">${isOnline ? 'En ligne' : 'Hors ligne'}</div>
                    </div>
                </div>
                <div class="health-item premium">
                    ${mDonut(99.9, 'primary', 'clock', 0.08)}
                    <div class="health-info">
                        <div class="health-label">Uptime</div>
                        <div class="health-value">${uptime}</div>
                    </div>
                </div>
                <div class="health-item premium">
                    ${mDonut(Math.min(100, threads.length * 10), 'secondary', 'message-circle', 0.16)}
                    <div class="health-info">
                        <div class="health-label">Threads actifs</div>
                        <div class="health-value">${threads.length}</div>
                    </div>
                </div>
                <div class="health-item premium">
                    ${mDonut(100, 'primary', 'network', 0.24)}
                    <div class="health-info">
                        <div class="health-label">Port</div>
                        <div class="health-value">4500</div>
                    </div>
                </div>
                <div class="health-item premium">
                    ${mDonut(42, 'warning', 'shield', 0.32)}
                    <div class="health-info">
                        <div class="health-label">Rate Limit</div>
                        <div class="health-value">30/min</div>
                    </div>
                </div>
                <div class="health-item premium">
                    ${mDonut(isOnline ? 100 : 35, isOnline ? 'success' : 'danger', 'activity', 0.4)}
                    <div class="health-info">
                        <div class="health-label">Etat global</div>
                        <div class="health-value">${isOnline ? 'Operationnel' : 'Degradé'}</div>
                    </div>
                </div>
            </div>
        `;

        $('#health-status').innerHTML = `
            <div class="flex items-center gap-3">
                <span class="badge badge-${isOnline ? 'success' : 'danger'}">${isOnline ? 'En ligne' : 'Erreur'}</span>
                <span class="text-secondary text-sm">${health.status}</span>
            </div>
        `;

        if (threads.length > 0) {
            $('#recent-threads').innerHTML = threads.slice(0, 5).map(t => `
                <div class="activity-item">
                    <div class="activity-icon primary"><i data-lucide="message-circle"></i></div>
                    <div class="activity-content">
                        <div class="activity-title">${escapeHtml(t.title)}</div>
                        <div class="activity-time">${timeAgo(t.updated_at)}</div>
                    </div>
                </div>
            `).join('');
        } else {
            $('#recent-threads').innerHTML = `
                <div class="empty-state" style="padding:var(--sp-6)">
                    <i data-lucide="inbox" style="width:24px;height:24px;color:var(--text-faint);margin-bottom:var(--sp-2)"></i>
                    <p class="text-sm text-muted">Aucune conversation recente</p>
                </div>
            `;
        }
        initIcons();
    } catch (e) {
        $('#server-dot').style.background = 'var(--danger)';
        $('#server-dot').style.boxShadow = '0 0 8px var(--danger)';
        $('#server-status-text').textContent = 'Hors ligne';
        $('#stats-grid').innerHTML = `
            <div class="stat-card">
                <div class="stat-card-top">
                    <div class="stat-icon danger"><i data-lucide="wifi-off"></i></div>
                    <span class="stat-badge down">Hors ligne</span>
                </div>
                <div class="stat-value" style="color:var(--danger)">Offline</div>
                <div class="stat-label">Infrastructure Status</div>
                <div class="stat-desc">Non accessible</div>
            </div>
        `;
        initIcons();
    }
}
