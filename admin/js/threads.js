let threadsRawData = [];

function computeThreadStats(threads) {
    const now = Date.now();
    const dayMs = 86400000;
    const today = new Date();
    today.setHours(0,0,0,0);
    const todayStart = today.getTime();
    const weekStart = todayStart - (today.getDay() * dayMs);

    let countToday = 0, countWeek = 0;
    threads.forEach(t => {
        const ts = typeof t.updated_at === 'number' && t.updated_at < 1e12 ? t.updated_at * 1000 : t.updated_at;
        if (ts >= todayStart) countToday++;
        if (ts >= weekStart) countWeek++;
    });

    const mostRecent = threads.length > 0 ? timeAgo(threads[0].updated_at) : '—';

    $('#threads-stat-total').textContent = threads.length;
    $('#threads-stat-today').textContent = countToday;
    $('#threads-stat-week').textContent = countWeek;
    $('#threads-stat-recent').textContent = mostRecent;
    $('#threads-total-count').textContent = threads.length;
    $('#thread-count').textContent = threads.length;
}

function renderThreads(threads) {
    const list = $('#threads-list');
    const searchTerm = ($('#threads-search')?.value || '').toLowerCase();

    const filtered = threads.filter(t => {
        if (searchTerm && !t.title.toLowerCase().includes(searchTerm)) return false;
        return true;
    });

    if (filtered.length === 0) {
        const isSearch = searchTerm.length > 0;
        list.innerHTML = `
            <div class="threads-empty">
                <div class="threads-empty-icon"><i data-lucide="${isSearch ? 'search' : 'message-circle'}" style="width:28px;height:28px"></i></div>
                <div class="threads-empty-title">${isSearch ? 'Aucun resultat' : 'Aucune conversation'}</div>
                <div class="threads-empty-desc">${isSearch ? 'Essayez un autre terme de recherche.' : 'Les nouvelles conversations apparaitront ici automatiquement.'}</div>
                ${!isSearch ? `<button onclick="loadThreads()" class="btn btn-sm btn-primary" style="margin-top:var(--sp-4)"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> Actualiser</button>` : ''}
            </div>`;
        initIcons();
        return;
    }

    list.innerHTML = `<div class="threads-grid">${filtered.map(t => {
        const id = t.id.substring(0, 8);
        return `
            <div class="thread-card" data-id="${t.id}">
                <div class="thread-card-left">
                    <div class="thread-card-icon"><i data-lucide="message-circle"></i></div>
                    <div class="thread-card-body">
                        <div class="thread-card-title">${escapeHtml(t.title)}</div>
                        <div class="thread-card-meta">
                            <span class="thread-card-id">#${id}</span>
                            <span class="thread-card-dot">·</span>
                            <span class="thread-card-time">${timeAgo(t.updated_at)}</span>
                        </div>
                    </div>
                </div>
                <div class="thread-card-actions">
                    <button onclick="deleteThread('${t.id}')" class="btn btn-sm btn-ghost thread-card-delete" title="Supprimer">
                        <i data-lucide="trash-2" style="width:13px;height:13px"></i>
                    </button>
                </div>
            </div>`;
    }).join('')}</div>`;
    initIcons();
}

async function loadThreads() {
    const list = $('#threads-list');
    list.innerHTML = `
        <div class="threads-skeleton-group">
            <div class="threads-skeleton-card"><div class="skeleton" style="height:80px;border-radius:var(--radius-2xl)"></div></div>
            <div class="threads-skeleton-card"><div class="skeleton" style="height:80px;border-radius:var(--radius-2xl)"></div></div>
            <div class="threads-skeleton-card"><div class="skeleton" style="height:80px;border-radius:var(--radius-2xl)"></div></div>
        </div>`;

    try {
        const data = await api('/threads');
        threadsRawData = data;
        computeThreadStats(data);
        renderThreads(data);

        const badge = $('#threads-sync-badge');
        if (badge) badge.classList.add('synced');
    } catch (e) {
        list.innerHTML = `
            <div class="threads-empty">
                <div class="threads-empty-icon"><i data-lucide="wifi-off" style="width:28px;height:28px"></i></div>
                <div class="threads-empty-title">Erreur de connexion</div>
                <div class="threads-empty-desc">Impossible de charger les conversations.</div>
                <button onclick="loadThreads()" class="btn btn-sm btn-primary" style="margin-top:var(--sp-4)"><i data-lucide="refresh-cw" style="width:12px;height:12px"></i> Reessayer</button>
            </div>`;
        initIcons();
    }
}

async function deleteThread(id) {
    if (!confirm('Supprimer cette conversation ?')) return;
    try {
        await api('/threads/' + id, { method: 'DELETE' });
        threadsRawData = threadsRawData.filter(t => t.id !== id);
        computeThreadStats(threadsRawData);
        renderThreads(threadsRawData);
        toast('Conversation supprimee', 'success');
    } catch (e) {
        toast('Erreur de suppression', 'error');
    }
}

if ($('#threads-search')) {
    $('#threads-search').addEventListener('input', () => { if (threadsRawData.length) renderThreads(threadsRawData); });
}
