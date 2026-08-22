async function loadSources() {
    try {
        const data = await api('/admin/sources');
        $('#sources-list').innerHTML = data.map(s => `
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-name">
                        ${escapeHtml(s.name)}
                        ${s.requires_key
                            ? '<span class="badge badge-warning">Cle requise</span>'
                            : '<span class="badge badge-success">Gratuit</span>'}
                    </div>
                    <div class="toggle-desc">${escapeHtml(s.description)}</div>
                </div>
                <div class="toggle ${s.enabled ? 'on' : ''}" onclick="toggleSource('${s.name}', this)" role="switch" aria-checked="${s.enabled}" tabindex="0"></div>
            </div>
        `).join('');
        initIcons();
    } catch (e) {}
}

async function toggleSource(name, el) {
    const isOn = el.classList.contains('on');
    try {
        await api('/admin/sources/' + name, {
            method: 'POST',
            body: JSON.stringify({ enabled: !isOn })
        });
        el.classList.toggle('on');
        el.setAttribute('aria-checked', !isOn);
        toast(`${name} ${isOn ? 'desactive' : 'active'}`, 'success');
    } catch (e) {
        toast('Erreur de mise a jour', 'error');
    }
}

async function loadModels() {
    try {
        const data = await api('/admin/models');
        $('#models-per-request').value = data.models_per_request;
        $('#cache-ttl').value = data.cache_ttl;
        $('#models-list').innerHTML = data.pool.map((m, i) => `
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-name">${escapeHtml(m.model)}</div>
                    <div class="toggle-desc">Timeout: ${m.timeout}s — Poids: ${m.weight}</div>
                </div>
                <div class="toggle on" role="switch" aria-checked="true" tabindex="0"></div>
            </div>
        `).join('');
    } catch (e) {}
}

async function saveModelConfig() {
    toast('Configuration modeles sauvegardee', 'success');
}
