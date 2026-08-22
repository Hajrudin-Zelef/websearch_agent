const API_KEY_GROUPS = [
    { id: 'llm', label: 'LLM Provider', icon: 'brain', color: 'primary', openByDefault: true },
    { id: 'web', label: 'Recherche Web', icon: 'search', color: 'secondary' },
    { id: 'crawl', label: 'Crawlers & Extraction', icon: 'download', color: 'warning' },
    { id: 'code', label: 'Code, Git & SearXNG', icon: 'git-branch', color: 'danger' },
    { id: 'agent-reach', label: 'Agent Reach', icon: 'globe', color: 'muted' },
];

const API_KEY_FIELDS = [
    { id: 'OPENROUTER_API_KEY', group: 'llm', label: 'OpenRouter', icon: 'sparkles', color: 'primary', sub: 'Provider principal', placeholder: 'sk-or-v1-...' },
    { id: 'PERPLEXITY_API_KEY', group: 'llm', label: 'Perplexity', icon: 'globe', color: 'secondary', sub: 'Recherche IA temps reel', placeholder: 'pplx-...' },
    { id: 'TAVILY_API_KEY', group: 'web', label: 'Tavily', icon: 'zap', color: 'warning', sub: 'Recherche avancee IA', placeholder: 'tvly-...' },
    { id: 'BRAVE_API_KEY', group: 'web', label: 'Brave Search', icon: 'shield', color: 'primary', sub: 'Moteur recherche prive', placeholder: 'BSA...' },
    { id: 'FIRECRAWL_API_KEY', group: 'crawl', label: 'Firecrawl', icon: 'file-code', color: 'warning', sub: 'Extraction contenu web', placeholder: 'fc-...' },
    { id: 'SGAI_API_KEY', group: 'crawl', label: 'ScrapeGraph AI', icon: 'bot', color: 'secondary', sub: 'Scraping intelligent IA', placeholder: 'ScrapeGraph AI' },
    { id: 'GITHUB_TOKEN', group: 'code', label: 'GitHub', icon: 'github', color: 'neutral', sub: 'Token repositories', placeholder: 'ghp_...' },
    { id: 'SEARXNG_URL', group: 'code', label: 'SearXNG', icon: 'search', color: 'success', sub: 'Recherche self-hosted', placeholder: 'https://search.inetol.net', type: 'text' },
    { id: 'SEARXNG_API_KEY', group: 'code', label: 'SearXNG Key', icon: 'key', color: 'success', sub: 'Instance privee', placeholder: 'Instance privee' },
    { id: 'JINA_API_KEY', group: 'agent-reach', label: 'Jina', icon: 'search', color: 'success', sub: 'Recherche web via Jina Reader', placeholder: 'jina_xxx' },
    { id: 'EXA_API_KEY', group: 'agent-reach', label: 'Exa', icon: 'search', color: 'success', sub: 'Recherche web via Exa', placeholder: 'exa_xxx' },
    { id: 'YT_DLP_COOKIES_FILE', group: 'agent-reach', label: 'YouTube', icon: 'video', color: 'success', sub: 'Cookies navigateur pour yt-dlp', placeholder: '/home/sam/.agent-reach/youtube_cookies.txt' },
    { id: 'TWITTER_COOKIES_FILE', group: 'agent-reach', label: 'Twitter/X', icon: 'twitter', color: 'success', sub: 'Cookies navigateur pour xreach', placeholder: '/home/sam/.agent-reach/twitter_cookies.txt' },
    { id: 'XIAOHONGSHU_COOKIES_FILE', group: 'agent-reach', label: 'XiaoHongShu', icon: 'share-2', color: 'success', sub: 'Cookies navigateur', placeholder: '/home/sam/.agent-reach/xiaohongshu_cookies.txt' },
    { id: 'LINKEDIN_EMAIL', group: 'agent-reach', label: 'LinkedIn', icon: 'linkedin', color: 'success', sub: 'Login et mot de passe', placeholder: 'email@linkedin.com' },
    { id: 'LINKEDIN_PASSWORD', group: 'agent-reach', label: 'LinkedIn Password', icon: 'lock', color: 'success', sub: 'Mot de passe LinkedIn', placeholder: 'mot de passe' },
    { id: 'BOSSZHIPIN_COOKIES_FILE', group: 'agent-reach', label: 'Bosszhipin', icon: 'briefcase', color: 'success', sub: 'Cookies navigateur', placeholder: '/home/sam/.agent-reach/bosszhipin_cookies.txt' },
];

function buildProviderFields(field) {
    const isPassword = field.type !== 'text';
    const eyeBtn = isPassword
        ? '<button type="button" class="apikeys-toggle-vis" onclick="toggleKeyReveal(\'key-' + field.id + '\', this)"><i data-lucide="eye"></i></button>'
        : '';
    const inputType = isPassword ? 'password' : 'text';
    const iconName = isPassword ? 'lock' : 'link';
    const copyBtn = '<button type="button" class="btn btn-sm btn-ghost apikeys-copy-btn" onclick="copyApiKey(\'key-' + field.id + '\')" title="Copier"><i data-lucide="copy" style="width:13px;height:13px"></i></button>';
    return '<div class="apikeys-field">' +
        '<label class="apikeys-label">' + field.id + '</label>' +
        '<div class="apikeys-input-row-inline">' +
            '<div class="apikeys-input-wrap">' +
                '<i data-lucide="' + iconName + '"></i>' +
                '<input type="' + inputType + '" class="input" id="key-' + field.id + '" placeholder="' + (field.placeholder || '') + '" autocomplete="off" data-full="">' +
                eyeBtn +
            '</div>' +
            copyBtn +
        '</div>' +
    '</div>';
}

function buildProviderItem(field) {
    const fields = buildProviderFields(field);
    return '<details class="apikeys-provider">' +
        '<summary>' +
            '<div class="apikeys-field-icon ' + (field.color || 'success') + '"><i data-lucide="' + (field.icon || 'key') + '"></i></div>' +
            '<div class="apikeys-field-meta">' +
                '<div class="apikeys-field-name">' + field.label + '</div>' +
                '<div class="apikeys-field-sub">' + (field.sub || '') + '</div>' +
            '</div>' +
            '<div class="toggle on" id="toggle-' + field.id + '" onclick="event.stopPropagation(); toggleApiKeyEnabled(\'' + field.id + '\', this)" role="switch" aria-checked="true" tabindex="0"></div>' +
        '</summary>' +
        '<div class="apikeys-provider-body">' +
            fields +
        '</div>' +
    '</details>';
}

function buildAccordionGroup(group, fields) {
    const openAttr = group.openByDefault ? ' open' : '';
    const providers = fields.map(function(f) { return buildProviderItem(f); }).join('');
    var colorVar = group.color === 'muted' ? 'text-muted' : group.color;

    return '<details class="apikeys-group"' + openAttr + '>' +
        '<summary>' +
            '<i data-lucide="' + group.icon + '" style="width:16px;height:16px;color:var(--' + colorVar + ')"></i>' +
            '<span>' + group.label + '</span>' +
            '<span class="apikeys-group-count">' + fields.length + '</span>' +
        '</summary>' +
        '<div class="apikeys-group-body">' +
            providers +
        '</div>' +
    '</details>';
}

function renderAPIKeysForm() {
    var form = document.getElementById('apikeys-form');
    if (!form) return;

    var grouped = {};
    var g, f;
    for (g = 0; g < API_KEY_GROUPS.length; g++) {
        grouped[API_KEY_GROUPS[g].id] = [];
    }
    for (f = 0; f < API_KEY_FIELDS.length; f++) {
        var field = API_KEY_FIELDS[f];
        if (grouped[field.group]) {
            grouped[field.group].push(field);
        }
    }

    var groupsHtml = '';
    for (g = 0; g < API_KEY_GROUPS.length; g++) {
        var group = API_KEY_GROUPS[g];
        if (grouped[group.id] && grouped[group.id].length > 0) {
            groupsHtml += buildAccordionGroup(group, grouped[group.id]);
        }
    }

    var addKeyHtml = '<details class="apikeys-group">' +
        '<summary>' +
            '<i data-lucide="plus-circle" style="width:16px;height:16px;color:var(--text-muted)"></i>' +
            '<span>Ajouter une cle</span>' +
        '</summary>' +
        '<div class="apikeys-group-body">' +
            '<div class="apikeys-add-key-card">' +
                '<div class="apikeys-add-key-row">' +
                    '<div class="apikeys-field" style="flex:0 0 200px">' +
                        '<label class="apikeys-label">Nom de la variable</label>' +
                        '<input type="text" class="input" id="new-key-name" placeholder="MA_CLE_API" autocomplete="off">' +
                    '</div>' +
                    '<div class="apikeys-field" style="flex:1">' +
                        '<label class="apikeys-label">Valeur</label>' +
                        '<div class="apikeys-input-wrap">' +
                            '<i data-lucide="lock"></i>' +
                            '<input type="password" class="input" id="new-key-value" placeholder="votre-cle-api" autocomplete="off">' +
                            '<button type="button" class="apikeys-toggle-vis" onclick="toggleKeyReveal(\'new-key-value\', this)"><i data-lucide="eye"></i></button>' +
                        '</div>' +
                    '</div>' +
                    '<button type="button" class="btn btn-primary" onclick="addNewKey()" style="align-self:flex-end;height:40px;margin-top:auto">' +
                        '<i data-lucide="plus" style="width:14px;height:14px"></i> Ajouter' +
                    '</button>' +
                '</div>' +
            '</div>' +
        '</div>' +
    '</details>';

    var securityHtml = '<div class="apikeys-security-notice">' +
        '<i data-lucide="shield-check" style="width:16px;height:16px;color:var(--success)"></i>' +
        '<span>Cles stockees localement. Jamais partagees. Chiffrement actif.</span>' +
    '</div>';

    var saveHtml = '<div class="apikeys-save-bar">' +
        '<button type="submit" class="btn btn-primary btn-lg" id="apikeys-save-btn">' +
            '<i data-lucide="save"></i>' +
            '<span id="apikeys-save-text">Sauvegarder la configuration</span>' +
        '</button>' +
    '</div>';

    form.innerHTML = groupsHtml + addKeyHtml + securityHtml + saveHtml;
    if (typeof initIcons === 'function') initIcons();
}

function isMaskedApiValue(value) {
    if (!value) return false;
    var v = String(value).trim();
    if (v === '***') return true;
    if (v.indexOf('...') !== -1) return true;
    return false;
}

function setStatusBadgeText(statusBadge, text) {
    var el = statusBadge ? statusBadge.querySelector('span:last-child') : null;
    if (el) el.textContent = text;
}

function isKeyConfigured(value) {
    if (!value) return false;
    var v = String(value).trim();
    if (!v) return false;
    if (v === '***') return true;
    if (v.indexOf('...') !== -1) return true;
    return v.length > 0;
}

function updateServiceStatus(key, value) {
    var toggle = document.getElementById('toggle-' + key);
    if (!toggle) return;
    var configured = isKeyConfigured(value);
    var enabled = toggle.classList.contains('on');
    toggle.setAttribute('aria-checked', enabled);
}

function updateApiKeysStats() {
    var total = API_KEY_FIELDS.length;
    var configured = 0;
    var llm = 0, web = 0;

    for (var i = 0; i < API_KEY_FIELDS.length; i++) {
        var f = API_KEY_FIELDS[i];
        var el = document.getElementById('key-' + f.id);
        var val = el ? el.value : '';
        if (isKeyConfigured(val)) {
            configured++;
            if (f.group === 'llm') llm++;
            if (f.group === 'web') web++;
        }
    }

    var statConnected = document.getElementById('apikeys-stat-connected');
    var statLlm = document.getElementById('apikeys-stat-llm');
    var statWeb = document.getElementById('apikeys-stat-web');
    var statConfigured = document.getElementById('apikeys-configured');
    if (statConnected) statConnected.textContent = configured;
    if (statLlm) statLlm.textContent = llm;
    if (statWeb) statWeb.textContent = web;
    if (statConfigured) statConfigured.textContent = configured + ' / ' + total;

    var statusBadge = document.getElementById('apikeys-status-badge');
    var statusText = document.getElementById('apikeys-stat-status');
    if (statusBadge) {
        if (configured === total) {
            statusBadge.className = 'apikeys-status-badge configured';
            setStatusBadgeText(statusBadge, 'Tout configure');
            if (statusText) statusText.textContent = 'Complet';
        } else if (configured > 0) {
            statusBadge.className = 'apikeys-status-badge partial';
            setStatusBadgeText(statusBadge, 'Partielle');
            if (statusText) statusText.textContent = 'Partiel';
        } else {
            statusBadge.className = 'apikeys-status-badge missing';
            setStatusBadgeText(statusBadge, 'Aucune cle');
            if (statusText) statusText.textContent = 'Vide';
        }
    }
}

async function loadAPIKeys() {
    try {
        if (typeof renderAPIKeysForm === 'function' && !document.getElementById('key-' + API_KEY_FIELDS[0].id)) {
            renderAPIKeysForm();
        }

        var data = await api('/admin/env');
        var keys = Object.keys(data || {});
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            var value = data[key];
            var el = document.getElementById('key-' + key);
            if (el) {
                el.value = value || '';
                el.setAttribute('data-full', value || '');
            }

            var toggle = document.getElementById('toggle-' + key);
            if (toggle) {
                var enabledKey = key + '_ENABLED';
                var isEnabled = data[enabledKey] !== 'false';
                toggle.className = 'toggle ' + (isEnabled ? 'on' : '');
                toggle.setAttribute('aria-checked', isEnabled);
            }
        }
        updateApiKeysStats();
    } catch (e) {
        console.error('Erreur chargement cles API:', e);
        if (typeof toast === 'function') toast('Impossible de charger les cles API', 'error');
    }
}

async function fetchRealKey(key) {
    try {
        var res = await api('/admin/env/' + key + '/reveal');
        return res.value || '';
    } catch (e) {
        console.warn('Reveal impossible pour ' + key, e);
        return '';
    }
}

async function toggleKeyReveal(inputId, btn) {
    var input = document.getElementById(inputId);
    if (!input) return;
    var isPassword = input.type === 'password';

    if (isPassword) {
        if (inputId.indexOf('key-') === 0) {
            var key = inputId.replace('key-', '');
            var val = await fetchRealKey(key);
            if (val) {
                input.value = val;
                input.setAttribute('data-full', val);
            }
        }
        input.type = 'text';
        if (btn) btn.innerHTML = '<i data-lucide="eye-off"></i>';
    } else {
        input.type = 'password';
        input.value = input.getAttribute('data-full') || input.value;
        if (btn) btn.innerHTML = '<i data-lucide="eye"></i>';
    }

    input.focus();
    if (typeof initIcons === 'function') initIcons();
}

async function copyApiKey(inputId) {
    var input = document.getElementById(inputId);
    if (!input) return;
    var key = inputId.replace('key-', '');
    var val = await fetchRealKey(key);
    if (!val) {
        toast('Aucune valeur a copier', 'warning');
        return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(val).then(
            function() { toast('Cle copiee', 'success'); },
            function() { fallbackCopy(val); }
        );
    } else {
        fallbackCopy(val);
    }
}

function fallbackCopy(text) {
    var ta = document.createElement('textarea');
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
    var isOn = el.classList.contains('on');
    el.classList.toggle('on');
    el.setAttribute('aria-checked', !isOn);
    toast(key + ' ' + (isOn ? 'desactive' : 'active') + '. Sauvegarde requise.', 'success');
}

function addNewKey() {
    var nameEl = document.getElementById('new-key-name');
    var valueEl = document.getElementById('new-key-value');
    var name = nameEl.value.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_');
    var value = valueEl.value.trim();

    if (!name) { toast('Nom de variable requis', 'warning'); return; }
    if (!value) { toast('Valeur requise', 'warning'); return; }

    var existing = document.getElementById('key-' + name);
    if (existing) {
        existing.value = value;
        existing.setAttribute('data-full', value);
        toast(name + ' mise a jour', 'success');
    } else {
        var container = document.createElement('div');
        container.className = 'apikeys-field';
        var lbl = document.createElement('label');
        lbl.className = 'apikeys-label';
        lbl.textContent = name;
        var row = document.createElement('div');
        row.className = 'apikeys-input-row-inline';
        var wrap = document.createElement('div');
        wrap.className = 'apikeys-input-wrap';
        var icon = document.createElement('i');
        icon.setAttribute('data-lucide', 'lock');
        var inp = document.createElement('input');
        inp.type = 'password';
        inp.className = 'input';
        inp.id = 'key-' + name;
        inp.placeholder = 'votre-cle-api';
        inp.autocomplete = 'off';
        inp.value = value;
        inp.setAttribute('data-full', value);
        var eyeBtn = document.createElement('button');
        eyeBtn.type = 'button';
        eyeBtn.className = 'apikeys-toggle-vis';
        eyeBtn.onclick = function() { toggleKeyReveal('key-' + name, this); };
        var eyeIcon = document.createElement('i');
        eyeIcon.setAttribute('data-lucide', 'eye');
        eyeBtn.appendChild(eyeIcon);
        wrap.appendChild(icon);
        wrap.appendChild(inp);
        wrap.appendChild(eyeBtn);
        var cpBtn = document.createElement('button');
        cpBtn.type = 'button';
        cpBtn.className = 'btn btn-sm btn-ghost apikeys-copy-btn';
        cpBtn.title = 'Copier';
        cpBtn.onclick = function() { copyApiKey('key-' + name); };
        var cpIcon = document.createElement('i');
        cpIcon.setAttribute('data-lucide', 'copy');
        cpIcon.style.cssText = 'width:13px;height:13px';
        cpBtn.appendChild(cpIcon);
        row.appendChild(wrap);
        row.appendChild(cpBtn);
        container.appendChild(lbl);
        container.appendChild(row);
        var addCard = document.querySelector('.apikeys-add-key-card');
        if (addCard) addCard.parentNode.insertBefore(container, addCard);
        if (typeof initIcons === 'function') initIcons();
        toast(name + ' ajoutee', 'success');
    }

    nameEl.value = '';
    valueEl.value = '';
    valueEl.type = 'password';
    updateApiKeysStats();
}

var apiKeysForm = document.getElementById('apikeys-form');
if (apiKeysForm) {
    apiKeysForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        var saveBtn = document.getElementById('apikeys-save-btn');
        var saveText = document.getElementById('apikeys-save-text');
        if (saveBtn) saveBtn.disabled = true;
        if (saveText) saveText.textContent = 'Enregistrement...';

        var keys = {};
        var inputs = document.querySelectorAll('#apikeys-form input[type="text"], #apikeys-form input[type="password"], #apikeys-form select');
        for (var i = 0; i < inputs.length; i++) {
            var el = inputs[i];
            var key = el.id.replace('key-', '');
            var val = el.value;
            if (val && key !== 'new-key-name' && key !== 'new-key-value') {
                // Ignore masked values to prevent overwriting real secrets
                if (typeof isMaskedApiValue === 'function' && isMaskedApiValue(val)) {
                    continue;
                }
                keys[key] = val;
            }
        }

        for (var j = 0; j < API_KEY_FIELDS.length; j++) {
            var f = API_KEY_FIELDS[j];
            var toggle = document.getElementById('toggle-' + f.id);
            if (toggle) {
                keys[f.id + '_ENABLED'] = toggle.classList.contains('on') ? 'true' : 'false';
            }
        }

        try {
            await api('/admin/env', { method: 'POST', body: JSON.stringify(keys) });
            if (saveText) saveText.textContent = 'Configuration enregistree';
            toast('Configuration sauvegardee', 'success');

            var now = new Date();
            var lastSave = document.getElementById('apikeys-last-save');
            if (lastSave) lastSave.textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

            setTimeout(function() {
                if (saveText) saveText.textContent = 'Sauvegarder la configuration';
                if (saveBtn) saveBtn.disabled = false;
            }, 2000);
        } catch (err) {
            if (saveText) saveText.textContent = 'Erreur de sauvegarde';
            toast('Erreur de sauvegarde', 'error');

            setTimeout(function() {
                if (saveText) saveText.textContent = 'Sauvegarder la configuration';
                if (saveBtn) saveBtn.disabled = false;
            }, 2000);
        }
    });
}

