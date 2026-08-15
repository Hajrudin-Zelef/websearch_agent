const API_KEY_FIELDS = [
    { id: 'OPENROUTER_API_KEY', cat: 'llm', label: 'OpenRouter' },
    { id: 'PERPLEXITY_API_KEY', cat: 'web', label: 'Perplexity' },
    { id: 'TAVILY_API_KEY', cat: 'web', label: 'Tavily' },
    { id: 'BRAVE_API_KEY', cat: 'web', label: 'Brave' },
    { id: 'FIRECRAWL_API_KEY', cat: 'crawl', label: 'Firecrawl' },
    { id: 'SGAI_API_KEY', cat: 'crawl', label: 'ScrapeGraph' },
    { id: 'GITHUB_TOKEN', cat: 'code', label: 'GitHub' },
    { id: 'SEARXNG_URL', cat: 'searxng', label: 'SearXNG URL' },
    { id: 'SEARXNG_API_KEY', cat: 'searxng', label: 'SearXNG Key' },
];

function isKeyConfigured(value) {
    if (!value) return false;
    if (value === '***' || value === '') return false;
    if (value.includes('...')) return true;
    return value.length > 0;
}

function updateServiceStatus(key, value) {
    const toggle = $(`#toggle-${key}`);
    if (!toggle) return;
    const configured = isKeyConfigured(value);
    const enabled = toggle.classList.contains('on');
    toggle.setAttribute('aria-checked', enabled);
}

function updateApiKeysStats() {
    let total = API_KEY_FIELDS.length;
    let configured = 0;
    let llm = 0, web = 0;

    API_KEY_FIELDS.forEach(f => {
        const el = $(`#key-${f.id}`);
        const val = el ? el.value : '';
        if (isKeyConfigured(val)) {
            configured++;
            if (f.cat === 'llm') llm++;
            if (f.cat === 'web') web++;
        }
    });

    $('#apikeys-stat-connected').textContent = configured;
    $('#apikeys-stat-llm').textContent = llm;
    $('#apikeys-stat-web').textContent = web;
    $('#apikeys-configured').textContent = `${configured} / ${total}`;

    const statusBadge = $('#apikeys-status-badge');
    const statusText = $('#apikeys-stat-status');
    if (configured === total) {
        statusBadge.className = 'apikeys-status-badge configured';
        statusBadge.querySelector('span:last-child').textContent = 'Tout configure';
        statusText.textContent = 'Complet';
    } else if (configured > 0) {
        statusBadge.className = 'apikeys-status-badge partial';
        statusBadge.querySelector('span:last-child').textContent = 'Partielle';
        statusText.textContent = 'Partiel';
    } else {
        statusBadge.className = 'apikeys-status-badge missing';
        statusBadge.querySelector('span:last-child').textContent = 'Aucune clee';
        statusText.textContent = 'Vide';
    }
}

async function loadAPIKeys() {
    try {
        const data = await api('/admin/env');
        for (const [key, value] of Object.entries(data)) {
            const el = $(`#key-${key}`);
            if (el) {
                el.value = value;
                el.setAttribute('data-full', value);
            }
            const toggle = $(`#toggle-${key}`);
            if (toggle) {
                const enabledKey = key + '_ENABLED';
                const isEnabled = data[enabledKey] !== 'false';
                toggle.className = `toggle ${isEnabled ? 'on' : ''}`;
                toggle.setAttribute('aria-checked', isEnabled);
            }
        }
        updateApiKeysStats();
    } catch (e) {}
}

async function fetchRealKey(key) {
    try {
        const res = await api(`/admin/env/${key}/reveal`);
        return res.value || '';
    } catch (e) {
        return '';
    }
}

async function toggleKeyReveal(inputId, btn) {
    const input = $(`#${inputId}`);
    if (!input) return;
    const isPassword = input.type === 'password';

    if (isPassword) {
        const key = inputId.replace('key-', '');
        const val = await fetchRealKey(key);
        input.type = 'text';
        input.value = val;
        input.setAttribute('data-full', val);
        btn.innerHTML = '<i data-lucide="eye-off"></i>';
    } else {
        input.type = 'password';
        input.value = input.getAttribute('data-full') || input.value;
        btn.innerHTML = '<i data-lucide="eye"></i>';
    }
    input.focus();
    initIcons();
}

async function copyApiKey(inputId) {
    const input = $(`#${inputId}`);
    if (!input) return;
    const key = inputId.replace('key-', '');
    const val = await fetchRealKey(key);
    if (!val) {
        toast('Aucune valeur a copier', 'warning');
        return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(val).then(
            () => toast('Cle copiee', 'success'),
            () => fallbackCopy(val)
        );
    } else {
        fallbackCopy(val);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        toast('Cle copiee', 'success');
    } catch (e) {
        toast('Erreur de copie', 'error');
    }
    ta.remove();
}

function toggleApiKeyEnabled(key, el) {
    const isOn = el.classList.contains('on');
    el.classList.toggle('on');
    el.setAttribute('aria-checked', !isOn);
    toast(`${key} ${isOn ? 'desactive' : 'active'}`, 'success');
}

function addNewKey() {
    const nameEl = $('#new-key-name');
    const valueEl = $('#new-key-value');
    const name = nameEl.value.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    const value = valueEl.value.trim();

    if (!name) { toast('Nom de variable requis', 'warning'); return; }
    if (!value) { toast('Valeur requise', 'warning'); return; }

    let existing = $(`#key-${name}`);
    if (existing) {
        existing.value = value;
        existing.setAttribute('data-full', value);
        toast(`${name} mise a jour`, 'success');
    } else {
        const container = document.createElement('div');
        container.className = 'apikeys-field';
        const lbl = document.createElement('label');
        lbl.className = 'apikeys-label';
        lbl.textContent = name;
        const row = document.createElement('div');
        row.className = 'apikeys-input-row-inline';
        const wrap = document.createElement('div');
        wrap.className = 'apikeys-input-wrap';
        const icon = document.createElement('i');
        icon.setAttribute('data-lucide', 'lock');
        const inp = document.createElement('input');
        inp.type = 'password';
        inp.className = 'input';
        inp.id = `key-${name}`;
        inp.placeholder = 'votre-cle-api';
        inp.autocomplete = 'off';
        inp.value = value;
        inp.setAttribute('data-full', value);
        const eyeBtn = document.createElement('button');
        eyeBtn.type = 'button';
        eyeBtn.className = 'apikeys-toggle-vis';
        eyeBtn.onclick = function() { toggleKeyReveal(`key-${name}`, this); };
        const eyeIcon = document.createElement('i');
        eyeIcon.setAttribute('data-lucide', 'eye');
        eyeBtn.appendChild(eyeIcon);
        wrap.appendChild(icon);
        wrap.appendChild(inp);
        wrap.appendChild(eyeBtn);
        const cpBtn = document.createElement('button');
        cpBtn.type = 'button';
        cpBtn.className = 'btn btn-sm btn-ghost apikeys-copy-btn';
        cpBtn.title = 'Copier';
        cpBtn.onclick = function() { copyApiKey(`key-${name}`); };
        const cpIcon = document.createElement('i');
        cpIcon.setAttribute('data-lucide', 'copy');
        cpIcon.style.cssText = 'width:13px;height:13px';
        cpBtn.appendChild(cpIcon);
        row.appendChild(wrap);
        row.appendChild(cpBtn);
        container.appendChild(lbl);
        container.appendChild(row);
        const addCard = $('.apikeys-add-key-card');
        if (addCard) addCard.parentNode.insertBefore(container, addCard);
        initIcons();
        toast(`${name} ajoutee`, 'success');
    }

    nameEl.value = '';
    valueEl.value = '';
    valueEl.type = 'password';
    updateApiKeysStats();
}

document.getElementById('apikeys-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = $('#apikeys-save-btn');
    const saveText = $('#apikeys-save-text');
    saveBtn.disabled = true;
    saveText.textContent = 'Enregistrement...';

    const keys = {};
    $$('#apikeys-form input[type="text"], #apikeys-form input[type="password"], #apikeys-form select').forEach(el => {
        const key = el.id.replace('key-', '');
        const val = el.value;
        if (val && key !== 'new-key-name' && key !== 'new-key-value') {
            keys[key] = val;
        }
    });

    API_KEY_FIELDS.forEach(f => {
        const toggle = $(`#toggle-${f.id}`);
        if (toggle) {
            keys[f.id + '_ENABLED'] = toggle.classList.contains('on') ? 'true' : 'false';
        }
    });

    try {
        await api('/admin/env', { method: 'POST', body: JSON.stringify(keys) });
        saveText.textContent = 'Configuration enregistree';
        toast('Configuration sauvegardee', 'success');
        const now = new Date();
        $('#apikeys-last-save').textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        setTimeout(() => {
            saveText.textContent = 'Sauvegarder la configuration';
            saveBtn.disabled = false;
        }, 2000);
    } catch (e) {
        saveText.textContent = 'Erreur de sauvegarde';
        toast('Erreur de sauvegarde', 'error');
        setTimeout(() => {
            saveText.textContent = 'Sauvegarder la configuration';
            saveBtn.disabled = false;
        }, 2000);
    }
});
