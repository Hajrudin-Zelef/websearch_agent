async function loadClients() {
    try {
        const data = await api('/admin/clients');
        const { clients, stats } = data;

        $('#clients-stat-total').textContent = stats.total_clients;
        $('#clients-stat-requests').textContent = stats.total_requests;
        $('#clients-stat-active').textContent = stats.active_clients;
        $('#clients-stat-inactive').textContent = stats.total_clients - stats.active_clients;
        $('#clients-count').textContent = stats.active_clients;

        $('#clients-stat-today').textContent = '—';

        if (stats.top_clients && stats.top_clients.length > 0) {
            $('#clients-stat-top').textContent = stats.top_clients[0].name;
        } else {
            $('#clients-stat-top').textContent = '—';
        }

        const list = $('#clients-list');
        if (clients.length === 0) {
            list.innerHTML = `
                <div class="clients-empty">
                    <i data-lucide="key" style="width:48px;height:48px;color:var(--text-faint);margin-bottom:var(--sp-4)"></i>
                    <h3 style="font-size:var(--text-lg);font-weight:600;margin-bottom:var(--sp-2)">Aucune app configuree</h3>
                    <p style="color:var(--text-muted);margin-bottom:var(--sp-4)">Creez votre premiere app pour commencer a tracker les appels API.</p>
                    <button onclick="showCreateClientModal()" class="btn btn-primary">
                        <i data-lucide="plus" style="width:14px;height:14px"></i> Creer une app
                    </button>
                </div>`;
            initIcons();
            return;
        }

        list.innerHTML = clients.map(c => `
            <div class="client-card ${c.active ? '' : 'inactive'}">
                <div class="client-card-header">
                    <div class="client-card-icon ${c.active ? 'active' : 'inactive'}">
                        <i data-lucide="${c.active ? 'smartphone' : 'pause'}"></i>
                    </div>
                    <div class="client-card-info">
                        <div class="client-card-name">${escapeHtml(c.name)}</div>
                        <div class="client-card-meta">
                            ${c.description ? escapeHtml(c.description) + ' · ' : ''}
                            Creee le ${new Date(c.created_at * 1000).toLocaleDateString('fr-FR')}
                            ${c.last_used_at ? ' · Derniere utilisation: ' + new Date(c.last_used_at * 1000).toLocaleDateString('fr-FR') : ''}
                        </div>
                    </div>
                    <div class="client-card-stats">
                        <span class="client-card-requests">${c.request_count} requetes</span>
                        <span class="client-card-status ${c.active ? 'active' : 'inactive'}">${c.active ? 'Active' : 'Desactivee'}</span>
                    </div>
                </div>
                <div class="client-card-actions">
                    <button onclick="showClientLogs('${c.id}', '${escapeHtml(c.name)}')" class="btn btn-sm btn-primary" title="Voir les logs">
                        <i data-lucide="activity" style="width:14px;height:14px"></i> Logs
                    </button>
                    <button onclick="copyClientKey('${c.id}')" class="btn btn-sm btn-ghost" title="Voir la cle">
                        <i data-lucide="eye" style="width:14px;height:14px"></i>
                    </button>
                    <button onclick="regenerateClientKey('${c.id}')" class="btn btn-sm btn-ghost" title="Regenerer la cle">
                        <i data-lucide="refresh-cw" style="width:14px;height:14px"></i>
                    </button>
                    ${c.active ?
                        `<button onclick="deactivateClient('${c.id}')" class="btn btn-sm btn-ghost" title="Desactiver">
                            <i data-lucide="pause" style="width:14px;height:14px"></i>
                        </button>` :
                        `<button onclick="activateClient('${c.id}')" class="btn btn-sm btn-ghost" title="Activer">
                            <i data-lucide="play" style="width:14px;height:14px"></i>
                        </button>`
                    }
                    <button onclick="deleteClient('${c.id}')" class="btn btn-sm btn-ghost text-danger" title="Supprimer">
                        <i data-lucide="trash-2" style="width:14px;height:14px"></i>
                    </button>
                </div>
            </div>
        `).join('');
        initIcons();
    } catch (e) {
        console.error('Erreur chargement clients:', e);
    }
}

function showCreateClientModal() {
    const name = prompt('Nom de l\'application:');
    if (!name) return;

    const description = prompt('Description (optionnel):') || '';

    createClient(name, description);
}

async function createClient(name, description) {
    try {
        const client = await api('/admin/clients', {
            method: 'POST',
            body: JSON.stringify({ name, description })
        });

        showCredentialsCard(name, client.api_key, client.client_secret);
        toast('App creee avec succes', 'success');
        loadClients();
    } catch (e) {
        toast('Erreur lors de la creation', 'error');
    }
}

async function showClientLogs(clientId, clientName) {
    try {
        const data = await api(`/admin/clients/${clientId}/logs?limit=50`);
        const logs = data.logs;

        const totalRequests = logs.length;
        const avgResponseTime = logs.length > 0
            ? Math.round(logs.reduce((a, l) => a + (l.response_time_ms || 0), 0) / logs.length)
            : 0;
        const cacheHits = logs.filter(l => l.cached).length;
        const cacheRate = totalRequests > 0 ? Math.round((cacheHits / totalRequests) * 100) : 0;
        const providers = {};
        logs.forEach(l => {
            if (l.tools_used) {
                l.tools_used.split(',').filter(t => t).forEach(t => {
                    providers[t] = (providers[t] || 0) + 1;
                });
            }
        });
        const topProviders = Object.entries(providers).sort((a, b) => b[1] - a[1]).slice(0, 5);
        const paths = { fast: 0, full: 0 };
        logs.forEach(l => { if (l.path) paths[l.path] = (paths[l.path] || 0) + 1; });

        let panelHtml = `
            <div class="logs-panel-overlay" onclick="closeLogsPanel()"></div>
            <div class="logs-panel" id="logs-panel">
                <div class="logs-panel-header">
                    <div class="logs-panel-title">
                        <div class="logs-panel-icon"><i data-lucide="activity"></i></div>
                        <div>
                            <h3>${escapeHtml(clientName)}</h3>
                            <span class="logs-panel-subtitle">${totalRequests} requetes enregistrees</span>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-ghost" onclick="closeLogsPanel()">
                        <i data-lucide="x"></i>
                    </button>
                </div>

                <div class="logs-panel-stats">
                    <div class="logs-stat-mini">
                        <div class="logs-stat-mini-value">${totalRequests}</div>
                        <div class="logs-stat-mini-label">Requetes</div>
                    </div>
                    <div class="logs-stat-mini">
                        <div class="logs-stat-mini-value">${avgResponseTime}ms</div>
                        <div class="logs-stat-mini-label">Temps moyen</div>
                    </div>
                    <div class="logs-stat-mini">
                        <div class="logs-stat-mini-value">${cacheRate}%</div>
                        <div class="logs-stat-mini-label">Cache hit</div>
                    </div>
                    <div class="logs-stat-mini">
                        <div class="logs-stat-mini-value">${paths.fast || 0}/${paths.full || 0}</div>
                        <div class="logs-stat-mini-label">Fast/Full</div>
                    </div>
                </div>

                ${topProviders.length > 0 ? `
                <div class="logs-panel-section">
                    <div class="logs-panel-section-title">Top Providers</div>
                    <div class="logs-providers-bar">
                        ${topProviders.map(([name, count]) => {
                            const pct = Math.round((count / totalRequests) * 100);
                            return `
                                <div class="logs-provider-item">
                                    <div class="logs-provider-name">${escapeHtml(name)}</div>
                                    <div class="logs-provider-bar">
                                        <div class="logs-provider-fill" style="width:${pct}%"></div>
                                    </div>
                                    <div class="logs-provider-count">${count}x</div>
                                </div>`;
                        }).join('')}
                    </div>
                </div>
                ` : ''}

                <div class="logs-panel-section">
                    <div class="logs-panel-section-title">Historique</div>
                    <div class="logs-timeline">`;

        if (logs.length === 0) {
            panelHtml += `
                <div class="logs-empty-state">
                    <i data-lucide="inbox" style="width:40px;height:40px;color:var(--text-faint)"></i>
                    <p>Aucune requete</p>
                </div>`;
        } else {
            logs.forEach((log, idx) => {
                const date = new Date(log.timestamp * 1000);
                const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                const dateStr = date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
                const tools = log.tools_used ? log.tools_used.split(',').filter(t => t) : [];
                const models = log.models_used ? log.models_used.split(',').filter(m => m) : [];
                const isSuccess = log.status_code < 400;
                const responseTime = log.response_time_ms || 0;

                let speedClass = 'slow';
                if (responseTime < 1000) speedClass = 'fast';
                else if (responseTime < 3000) speedClass = 'medium';

                panelHtml += `
                    <div class="timeline-entry" onclick="this.classList.toggle('expanded')">
                        <div class="timeline-dot ${isSuccess ? 'success' : 'error'}"></div>
                        <div class="timeline-line"></div>
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <span class="timeline-time">${timeStr}</span>
                                <span class="timeline-date">${dateStr}</span>
                                <span class="timeline-status ${isSuccess ? 'ok' : 'err'}">${log.status_code || '—'}</span>
                                <span class="timeline-speed ${speedClass}">${responseTime}ms</span>
                                ${log.cached ? '<span class="timeline-badge">CACHE</span>' : ''}
                                <i data-lucide="chevron-down" class="timeline-chevron"></i>
                            </div>
                            ${log.query ? `<div class="timeline-query">"${escapeHtml(log.query.slice(0, 120))}${log.query.length > 120 ? '...' : ''}"</div>` : ''}
                            <div class="timeline-details">
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="route"></i></span>
                                    <span class="timeline-detail-label">Path</span>
                                    <span class="timeline-detail-value">${log.path || '—'}</span>
                                </div>
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="globe"></i></span>
                                    <span class="timeline-detail-label">Endpoint</span>
                                    <span class="timeline-detail-value mono">${log.endpoint || '—'}</span>
                                </div>
                                ${tools.length > 0 ? `
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="layers"></i></span>
                                    <span class="timeline-detail-label">Providers</span>
                                    <div class="timeline-tags">
                                        ${tools.map(t => `<span class="timeline-tag provider">${escapeHtml(t)}</span>`).join('')}
                                    </div>
                                </div>
                                ` : ''}
                                ${models.length > 0 ? `
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="cpu"></i></span>
                                    <span class="timeline-detail-label">Modeles</span>
                                    <div class="timeline-tags">
                                        ${models.map(m => `<span class="timeline-tag model">${escapeHtml(m.split('/').pop())}</span>`).join('')}
                                    </div>
                                </div>
                                ` : ''}
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="map-pin"></i></span>
                                    <span class="timeline-detail-label">IP</span>
                                    <span class="timeline-detail-value mono">${escapeHtml(log.ip_address || '—')}</span>
                                </div>
                                <div class="timeline-detail-row">
                                    <span class="timeline-detail-icon"><i data-lucide="user"></i></span>
                                    <span class="timeline-detail-label">User-Agent</span>
                                    <span class="timeline-detail-value truncate">${escapeHtml(log.user_agent || '—')}</span>
                                </div>
                            </div>
                        </div>
                    </div>`;
            });
        }

        panelHtml += `
                    </div>
                </div>
            </div>`;

        document.body.insertAdjacentHTML('beforeend', panelHtml);
        initIcons();

        requestAnimationFrame(() => {
            document.getElementById('logs-panel').classList.add('open');
        });
    } catch (e) {
        toast('Erreur chargement logs', 'error');
    }
}

function closeLogsPanel() {
    const panel = document.getElementById('logs-panel');
    const overlay = document.querySelector('.logs-panel-overlay');
    if (panel) panel.classList.remove('open');
    if (overlay) {
        overlay.style.opacity = '0';
        setTimeout(() => overlay.remove(), 300);
    }
    setTimeout(() => panel?.remove(), 300);
}

async function copyClientKey(clientId) {
    try {
        const client = await api(`/admin/clients/${clientId}`);
        prompt(`Cle API pour "${client.name}":`, 'La cle n\'est plus visible. Utilisez "Regenerer" pour en avoir une nouvelle.');
    } catch (e) {
        toast('Erreur', 'error');
    }
}

async function regenerateClientKey(clientId) {
    if (!confirm('Regenerer la cle ? L\'ancienne cle sera desactivee.')) return;

    try {
        const result = await api(`/admin/clients/${clientId}/regenerate`, { method: 'POST' });

        showCredentialsCard(result.name, result.api_key, result.client_secret);
        toast('Cle regeneree', 'success');
        loadClients();
    } catch (e) {
        toast('Erreur lors de la regeneration', 'error');
    }
}

async function deactivateClient(clientId) {
    if (!confirm('Desactiver cette app ?')) return;

    try {
        await api(`/admin/clients/${clientId}/deactivate`, { method: 'POST' });
        toast('App desactivee', 'success');
        loadClients();
    } catch (e) {
        toast('Erreur', 'error');
    }
}

async function activateClient(clientId) {
    try {
        await api(`/admin/clients/${clientId}/activate`, { method: 'POST' });
        toast('App reactiver', 'success');
        loadClients();
    } catch (e) {
        toast('Erreur', 'error');
    }
}

async function deleteClient(clientId) {
    if (!confirm('Supprimer cette app definitivement ?')) return;

    try {
        await api(`/admin/clients/${clientId}`, { method: 'DELETE' });
        toast('App supprimee', 'success');
        loadClients();
    } catch (e) {
        toast('Erreur', 'error');
    }
}

function showCredentialsCard(name, apiKey, clientSecret) {
    const existing = document.getElementById('credentials-card');
    if (existing) existing.remove();

    const card = document.createElement('div');
    card.id = 'credentials-card';
    card.className = 'client-card';
    card.style.cssText = 'border:2px solid var(--success);background:var(--bg-success-subtle);margin-bottom:var(--sp-4);padding:var(--sp-4);border-radius:var(--radius-lg)';

    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3)">
            <div>
                <div style="font-weight:600;color:var(--success);font-size:var(--text-lg)">Credentials generes pour "${escapeHtml(name)}"</div>
                <div style="color:var(--text-muted);font-size:var(--text-sm);margin-top:var(--sp-1)">Copiez-les maintenant, ils ne seront plus visibles !</div>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="this.parentElement.parentElement.remove()">
                <i data-lucide="x" style="width:16px;height:16px"></i>
            </button>
        </div>

        <div style="margin-bottom:var(--sp-3)">
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);text-transform:uppercase;letter-spacing:0.05em">API Key</div>
            <div style="display:flex;gap:var(--sp-2);align-items:center">
                <input type="text" value="${apiKey}" readonly
                    style="flex:1;font-family:var(--font-mono);font-size:var(--text-sm);background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius);padding:var(--sp-2) var(--sp-3);color:var(--text)">
                <button class="btn btn-sm btn-primary" onclick="navigator.clipboard.writeText('${apiKey}');toast('API Key copiee !','success')">
                    <i data-lucide="copy" style="width:14px;height:14px"></i> Copier
                </button>
            </div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-1)">
                Header: <code>X-API-Key</code> ou <code>Authorization: Bearer ws_...</code>
            </div>
        </div>

        <div style="margin-bottom:var(--sp-3)">
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);text-transform:uppercase;letter-spacing:0.05em">Client Secret (OAuth2)</div>
            <div style="display:flex;gap:var(--sp-2);align-items:center">
                <input type="text" value="${clientSecret}" readonly
                    style="flex:1;font-family:var(--font-mono);font-size:var(--text-sm);background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius);padding:var(--sp-2) var(--sp-3);color:var(--text)">
                <button class="btn btn-sm btn-primary" onclick="navigator.clipboard.writeText('${clientSecret}');toast('Client Secret copie !','success')">
                    <i data-lucide="copy" style="width:14px;height:14px"></i> Copier
                </button>
            </div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-1)">
                Utilisez avec <code>POST /oauth/token</code> : <code>{"client_id": "...", "client_secret": "..."}</code>
            </div>
        </div>

        <div style="background:var(--bg-subtle);border-radius:var(--radius);padding:var(--sp-3);font-size:var(--text-xs);color:var(--text-muted)">
            <strong>Exemple OAuth2 :</strong>
            <code style="display:block;margin-top:var(--sp-1);white-space:pre-wrap">curl -X POST http://localhost:4500/oauth/token \\
  -H "Content-Type: application/json" \\
  -d '{"client_id": "${apiKey.split('_')[0] + '_' + '...'}", "client_secret": "..."}'

# Reponse: {"access_token": "eyJ...", "token_type": "Bearer", "expires_in": 3600}

curl -H "Authorization: Bearer eyJ..." http://localhost:4500/chat \\
  -d '{"message": "Bonjour"}'</code>
        </div>
    `;

    const list = document.getElementById('clients-list');
    if (list) {
        list.parentNode.insertBefore(card, list);
    } else {
        document.querySelector('.page[id="page-clients"]')?.prepend(card);
    }
    initIcons();
}
