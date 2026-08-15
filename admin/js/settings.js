let refusalTags = [];

document.addEventListener('DOMContentLoaded', () => {
    $$('.settings-sidebar-item').forEach(item => {
        item.addEventListener('click', () => {
            $$('.settings-sidebar-item').forEach(i => i.classList.remove('active'));
            $$('.settings-section').forEach(s => s.classList.remove('active'));
            item.classList.add('active');
            const section = item.dataset.settings;
            const target = $(`#settings-${section}`);
            if (target) target.classList.add('active');
        });
    });

    $$('.radio-card').forEach(card => {
        card.addEventListener('click', () => {
            const group = card.closest('.radio-cards');
            group.querySelectorAll('.radio-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
        });
    });

    const tagInput = $('#tag-input-refusal');
    if (tagInput) {
        tagInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addRefusalTag(tagInput.value.replace(',', ''));
                tagInput.value = '';
            }
            if (e.key === 'Backspace' && !tagInput.value && refusalTags.length > 0) {
                refusalTags.pop();
                renderRefusalTags();
            }
        });
    }

    const prompt = $('#set-system-prompt');
    if (prompt) {
        prompt.addEventListener('input', () => {});
    }
});

async function loadSettings() {
    try {
        const data = await api('/admin/settings');

        $('#set-fullname').value = data.general?.fullname || '';
        $('#set-displayname').value = data.general?.displayname || '';
        $('#set-language').value = data.general?.language || 'fr';
        $('#set-timezone').value = data.general?.timezone || 'Europe/Paris';

        $('#set-system-prompt').value = data.agent?.system_prompt || '';
        $('#set-ai-name').value = data.ai?.name || 'WebSearch Agent';

        const markers = data.agent?.refusal_markers || '';
        refusalTags = markers.split(',').map(s => s.trim()).filter(Boolean);
        renderRefusalTags();

        const appearance = data.appearance || {};
        applyAppearance(appearance);
        $$(`#theme-selector .radio-card`).forEach(c => {
            c.classList.toggle('selected', c.dataset.theme === (appearance.theme || 'dark'));
            c.querySelector('input').checked = c.dataset.theme === (appearance.theme || 'dark');
        });

        const responseStyle = data.ai?.response_style || 'balanced';
        $$(`#response-style-selector .radio-card`).forEach(c => {
            c.classList.toggle('selected', c.dataset.style === responseStyle);
            c.querySelector('input').checked = c.dataset.style === responseStyle;
        });

        const searchSpeed = data.ai?.search_speed || 'normal';
        $$(`#search-speed-selector .radio-card`).forEach(c => {
            c.classList.toggle('selected', c.dataset.speed === searchSpeed);
            c.querySelector('input').checked = c.dataset.speed === searchSpeed;
        });

        initIcons();
    } catch (e) {
        toast('Erreur de chargement des parametres', 'error');
    }

    loadAccount();
    loadSessions();
    loadSecurity();
    loadPlugins();
    loadDeveloper();
    loadApiClientsList();
}

async function loadAccount() {
    try {
        const data = await api('/admin/account');
        $('#set-email').value = data.email || '';
    } catch (e) {}
}

async function loadSecurity() {
    try {
        const data = await api('/admin/security');
        const toggle2fa = $('#set-2fa');
        if (toggle2fa) toggle2fa.checked = data.two_factor_enabled;
        const badge = document.querySelector('#settings-security .status-badge.warning');
        if (badge) {
            badge.textContent = data.two_factor_enabled ? 'Activee' : 'Non activee';
            badge.className = `status-badge ${data.two_factor_enabled ? 'success' : 'warning'}`;
        }
    } catch (e) {}
}

async function loadPlugins() {
    try {
        const data = await api('/admin/plugins');
        const list = document.getElementById('plugins-list');
        if (!list) return;
        list.innerHTML = data.plugins.map(p => `
            <div class="plugin-card">
                <div class="plugin-icon"><i data-lucide="puzzle"></i></div>
                <div class="plugin-info">
                    <div class="plugin-name">${escapeHtml(p.name)} <span class="plugin-version">${p.enabled ? 'actif' : 'inactif'}</span></div>
                    <div class="plugin-desc">${escapeHtml(p.description)}</div>
                </div>
                <label class="toggle">
                    <input type="checkbox" ${p.enabled ? 'checked' : ''} onchange="togglePlugin('${p.name}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
            </div>
        `).join('');
        if (data.modules) {
            data.modules.forEach(mod => {
                const card = document.querySelector(`[data-module="${mod.name}"]`);
                if (card) {
                    const toggle = card.querySelector('input[type="checkbox"]');
                    if (toggle) {
                        toggle.checked = mod.enabled;
                        toggle.onchange = function() { togglePlugin(mod.name, this.checked); };
                    }
                }
            });
        }
        initIcons();
    } catch (e) {}
}

async function togglePlugin(name, enabled) {
    try {
        await api(`/admin/plugins/${name}/toggle`, {
            method: 'POST',
            body: JSON.stringify({ enabled }),
        });
        toast(`${name} ${enabled ? 'activé' : 'désactivé'}`, 'success');
    } catch (e) {
        toast('Erreur', 'error');
    }
}

async function loadDeveloper() {
    try {
        const data = await api('/admin/developer');
        if ($('#set-webhooks')) $('#set-webhooks').checked = data.webhooks_enabled;
        if ($('#set-streaming')) $('#set-streaming').checked = data.streaming;
        if ($('#set-rag')) $('#set-rag').checked = data.rag;
        if ($('#set-log-level')) $('#set-log-level').value = data.log_level || 'INFO';
        if ($('#set-webhook-url')) $('#set-webhook-url').value = data.webhook_url || '';
    } catch (e) {}
}

function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === 'light') {
        root.style.setProperty('--bg', '#ffffff');
        root.style.setProperty('--bg-surface', '#f4f4f5');
        root.style.setProperty('--bg-elevated', '#e4e4e7');
        root.style.setProperty('--bg-hover', '#d4d4d8');
        root.style.setProperty('--bg-active', '#a1a1aa');
        root.style.setProperty('--bg-input', '#f4f4f5');
        root.style.setProperty('--bg-sidebar', '#fafafa');
        root.style.setProperty('--border', 'rgba(0,0,0,0.08)');
        root.style.setProperty('--border-hover', 'rgba(0,0,0,0.14)');
        root.style.setProperty('--text', '#18181b');
        root.style.setProperty('--text-secondary', '#52525b');
        root.style.setProperty('--text-muted', '#71717a');
        root.style.setProperty('--text-faint', '#a1a1aa');
        root.style.setProperty('--shadow-xs', '0 1px 2px rgba(0,0,0,0.06)');
        root.style.setProperty('--shadow-sm', '0 2px 4px rgba(0,0,0,0.08)');
        root.style.setProperty('--shadow-md', '0 4px 12px rgba(0,0,0,0.1)');
        root.style.setProperty('--shadow-lg', '0 8px 24px rgba(0,0,0,0.12)');
    } else {
        root.style.removeProperty('--bg');
        root.style.removeProperty('--bg-surface');
        root.style.removeProperty('--bg-elevated');
        root.style.removeProperty('--bg-hover');
        root.style.removeProperty('--bg-active');
        root.style.removeProperty('--bg-input');
        root.style.removeProperty('--bg-sidebar');
        root.style.removeProperty('--border');
        root.style.removeProperty('--border-hover');
        root.style.removeProperty('--text');
        root.style.removeProperty('--text-secondary');
        root.style.removeProperty('--text-muted');
        root.style.removeProperty('--text-faint');
        root.style.removeProperty('--shadow-xs');
        root.style.removeProperty('--shadow-sm');
        root.style.removeProperty('--shadow-md');
        root.style.removeProperty('--shadow-lg');
    }
}

function applyAppearance(appearance) {
    applyTheme(appearance?.theme || 'dark');
    const fontSize = appearance?.font_size || 'medium';
    const sizes = { small: '14px', medium: '16px', large: '18px' };
    document.documentElement.style.fontSize = sizes[fontSize] || '16px';
    const wide = appearance?.wide_messages ?? false;
    document.documentElement.classList.toggle('wide-messages', wide);
}

function renderRefusalTags() {
    const container = $('#tags-refusal');
    const input = $('#tag-input-refusal');
    if (!container || !input) return;

    container.querySelectorAll('.tag').forEach(t => t.remove());

    refusalTags.forEach((tag, i) => {
        const el = document.createElement('span');
        el.className = 'tag';
        el.innerHTML = `${escapeHtml(tag)}<button class="tag-remove" onclick="removeRefusalTag(${i})"><i data-lucide="x"></i></button>`;
        container.insertBefore(el, input);
    });

    initIcons();
}

function addRefusalTag(text) {
    const val = text.trim().toLowerCase();
    if (!val || refusalTags.includes(val)) return;
    refusalTags.push(val);
    renderRefusalTags();
}

function removeRefusalTag(index) {
    refusalTags.splice(index, 1);
    renderRefusalTags();
}

async function saveSettings() {
    const btn = $('#btn-save-settings');
    const btnText = $('#btn-save-text');

    btn.classList.add('saving');
    btn.disabled = true;
    btnText.textContent = 'Sauvegarde...';

    const getSelected = (selector) => {
        const el = document.querySelector(`${selector} .radio-card.selected input`);
        return el ? el.value : null;
    };

    const settings = {
        general: {
            fullname: $('#set-fullname')?.value || '',
            displayname: $('#set-displayname')?.value || '',
            language: $('#set-language')?.value || 'fr',
            timezone: $('#set-timezone')?.value || 'Europe/Paris',
        },
        appearance: {
            theme: getSelected('#theme-selector') || 'dark',
            font_size: $('#set-font-size')?.value || 'medium',
            animations: $('#set-animations')?.checked ?? true,
            wide_messages: $('#set-wide-messages')?.checked ?? false,
        },
        ai: {
            name: $('#set-ai-name')?.value || 'WebSearch Agent',
            system_prompt: $('#set-system-prompt')?.value || '',
            refusal_markers: refusalTags.join(','),
            response_style: getSelected('#response-style-selector') || 'balanced',
            search_speed: getSelected('#search-speed-selector') || 'normal',
        },
        agent: {
            system_prompt: $('#set-system-prompt')?.value || '',
            refusal_markers: refusalTags.join(','),
            max_context_length: 6000,
        },
    };

    try {
        await api('/admin/settings', {
            method: 'POST',
            body: JSON.stringify(settings),
        });

        btn.classList.remove('saving');
        btn.classList.add('saved');
        btnText.textContent = 'Sauvegarde !';

        toast('Parametres sauvegardes', 'success');

        setTimeout(() => {
            btn.classList.remove('saved');
            btn.disabled = false;
            btnText.textContent = 'Sauvegarder';
        }, 2000);
    } catch (e) {
        btn.classList.remove('saving');
        btn.disabled = false;
        btnText.textContent = 'Sauvegarder';
        toast('Erreur de sauvegarde', 'error');
    }
}

async function saveAccountEmail() {
    try {
        await api('/admin/account/email', {
            method: 'POST',
            body: JSON.stringify({ email: $('#set-email')?.value || '' }),
        });
        toast('Email sauvegarde', 'success');
    } catch (e) {
        toast('Erreur', 'error');
    }
}

async function changePassword() {
    const current = $('#pw-current')?.value;
    const newPw = $('#pw-new')?.value;
    const confirm = $('#pw-confirm')?.value;
    if (!current || !newPw) { toast('Remplissez tous les champs', 'error'); return; }
    if (newPw !== confirm) { toast('Les mots de passe ne correspondent pas', 'error'); return; }
    if (newPw.length < 6) { toast('Minimum 6 caracteres', 'error'); return; }
    try {
        await api('/admin/account/password', {
            method: 'POST',
            body: JSON.stringify({ current, new: newPw }),
        });
        toast('Mot de passe mis a jour. Redmarrez le service.', 'success');
        $('#pw-current').value = '';
        $('#pw-new').value = '';
        $('#pw-confirm').value = '';
    } catch (e) {
        toast(e.message || 'Erreur', 'error');
    }
}

async function loadSessions() {
    try {
        const data = await api('/admin/account/sessions');
        const list = $('#sessions-list');
        if (!list) return;
        list.innerHTML = data.sessions.map(s => `
            <div class="session-item">
                <div class="session-icon"><i data-lucide="${s.is_current ? 'monitor' : 'smartphone'}"></i></div>
                <div class="session-info">
                    <div class="session-device">Session ${s.token_prefix}...</div>
                    <div class="session-meta">Expire dans ${s.expires_in_hours}h</div>
                </div>
                ${s.is_current ? '<span class="session-current">Actuel</span>' :
                    `<button class="btn-danger" style="font-size:11px;padding:4px 10px" onclick="disconnectSession('${s.token_prefix}')">Deconnecter</button>`}
            </div>
        `).join('');
        initIcons();
    } catch (e) {}
}

async function disconnectSession(prefix) {
    try {
        await api(`/admin/account/sessions/${prefix}`, { method: 'DELETE' });
        toast('Session deconnectee', 'success');
        loadSessions();
    } catch (e) { toast('Erreur', 'error'); }
}

async function toggle2FA(enabled) {
    try {
        const data = await api('/admin/security/2fa', {
            method: 'POST',
            body: JSON.stringify({ enabled }),
        });
        const badge = $('#badge-2fa');
        if (badge) {
            badge.textContent = enabled ? 'Activee' : 'Non activee';
            badge.className = `status-badge ${enabled ? 'success' : 'warning'}`;
        }
        if (enabled && data.secret) {
            toast(`2FA activee. Secret: ${data.secret}`, 'success');
        } else {
            toast(enabled ? '2FA activee' : '2FA desactivee', 'success');
        }
    } catch (e) { toast('Erreur', 'error'); }
}

async function saveDeveloper() {
    try {
        await api('/admin/developer', {
            method: 'POST',
            body: JSON.stringify({
                log_level: $('#set-log-level')?.value || 'INFO',
                streaming: $('#set-streaming')?.checked ?? false,
                rag: $('#set-rag')?.checked ?? false,
                webhooks_enabled: $('#set-webhooks')?.checked ?? false,
                webhook_url: $('#set-webhook-url')?.value || '',
            }),
        });
        toast('Parametres developpeur sauvegardes', 'success');
    } catch (e) { toast('Erreur', 'error'); }
}

async function loadApiClientsList() {
    try {
        const data = await api('/admin/clients');
        const list = document.getElementById('api-clients-list');
        if (!list) return;
        if (!data.clients || data.clients.length === 0) {
            list.innerHTML = '<div style="color:var(--text-muted);padding:var(--sp-4);text-align:center">Aucun client API configure</div>';
            return;
        }
        list.innerHTML = data.clients.map(c => `
            <div class="plugin-card">
                <div class="plugin-icon"><i data-lucide="key"></i></div>
                <div class="plugin-info">
                    <div class="plugin-name">${escapeHtml(c.name)}</div>
                    <div class="plugin-desc" style="font-family:var(--font-mono);font-size:var(--text-xs)">${c.api_key ? c.api_key.substring(0,8) + '...' + c.api_key.substring(c.api_key.length-4) : '••••••••'}</div>
                </div>
                <label class="toggle">
                    <input type="checkbox" ${c.active ? 'checked' : ''} onchange="toggleClient('${c.id}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
            </div>
        `).join('');
        initIcons();
    } catch (e) {}
}

async function toggleClient(clientId, active) {
    try {
        if (active) {
            await api(`/admin/clients/${clientId}/activate`, { method: 'POST' });
        } else {
            await api(`/admin/clients/${clientId}/deactivate`, { method: 'POST' });
        }
        toast(`Client ${active ? 'active' : 'desactive'}`, 'success');
        loadApiClientsList();
    } catch (e) { toast('Erreur', 'error'); }
}

async function createApp() {
    const name = $('#new-app-name')?.value?.trim();
    const desc = $('#new-app-desc')?.value?.trim() || '';
    if (!name) { toast('Entrez un nom', 'error'); return; }
    try {
        const client = await api('/admin/clients', {
            method: 'POST',
            body: JSON.stringify({ name, description: desc }),
        });
        toast('Application creee', 'success');
        $('#new-app-name').value = '';
        $('#new-app-desc').value = '';
        showApiKeyCard(client.name, client.api_key, client.client_secret);
        loadApiClientsList();
    } catch (e) { toast('Erreur', 'error'); }
}

function showApiKeyCard(name, key, secret) {
    const existing = document.getElementById('new-apikey-card');
    if (existing) existing.remove();
    const card = document.createElement('div');
    card.id = 'new-apikey-card';
    card.className = 'settings-card';
    card.style.borderColor = 'var(--success)';
    card.innerHTML = `
        <div class="settings-card-header">
            <div>
                <div class="settings-card-title" style="color:var(--success)">Credentials crees pour "${escapeHtml(name)}"</div>
                <div class="settings-card-desc">Copiez-les maintenant, ils ne seront plus visibles !</div>
            </div>
        </div>
        <div style="margin-bottom:var(--sp-3)">
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);text-transform:uppercase;letter-spacing:0.05em">API Key</div>
            <div style="display:flex;gap:var(--sp-2);align-items:center">
                <input type="text" class="settings-form-input" value="${key}" readonly style="font-family:var(--font-mono);font-size:var(--text-sm);flex:1" id="apikey-display">
                <button class="btn-save-settings" onclick="copyToClipboard('apikey-display')" style="white-space:nowrap">
                    <i data-lucide="copy"></i> Copier
                </button>
            </div>
            <div class="settings-form-hint">Header: <code>X-API-Key</code> ou <code>Authorization: Bearer ws_...</code></div>
        </div>
        ${secret ? `
        <div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-1);text-transform:uppercase;letter-spacing:0.05em">Client Secret (OAuth2)</div>
            <div style="display:flex;gap:var(--sp-2);align-items:center">
                <input type="text" class="settings-form-input" value="${secret}" readonly style="font-family:var(--font-mono);font-size:var(--text-sm);flex:1" id="clientsecret-display">
                <button class="btn-save-settings" onclick="copyToClipboard('clientsecret-display')" style="white-space:nowrap">
                    <i data-lucide="copy"></i> Copier
                </button>
            </div>
            <div class="settings-form-hint">Utilisez avec <code>POST /oauth/token</code> pour obtenir un JWT</div>
        </div>
        ` : ''}
    `;
    const list = document.getElementById('api-clients-list');
    list.parentNode.insertBefore(card, list);
    initIcons();
}

function copyToClipboard(elementId) {
    const input = document.getElementById(elementId);
    if (input) {
        navigator.clipboard.writeText(input.value);
        toast('Copie !', 'success');
    }
}

async function exportData() {
    try {
        const data = await api('/admin/data/export');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `websearch-export-${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast('Export telecharge', 'success');
    } catch (e) { toast('Erreur', 'error'); }
}

async function deleteHistory() {
    if (!confirm('Supprimer tout l\'historique? Cette action est irreversible.')) return;
    try {
        await api('/admin/data/history', { method: 'DELETE' });
        toast('Historique supprime', 'success');
    } catch (e) { toast('Erreur', 'error'); }
}

async function disconnectAll() {
    if (!confirm('Deconnecter toutes les sessions?')) return;
    try {
        const data = await api('/admin/danger/disconnect-all', { method: 'POST' });
        toast(`${data.disconnected} session(s) deconnectee(s)`, 'success');
    } catch (e) { toast('Erreur', 'error'); }
}

async function resetSettings() {
    if (!confirm('Reinitialiser tous les parametres?')) return;
    try {
        await api('/admin/danger/reset', { method: 'POST' });
        toast('Parametres reinitialises', 'success');
        loadSettings();
    } catch (e) { toast('Erreur', 'error'); }
}
