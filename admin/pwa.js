// WebSearch PWA - Mobile App Logic
const API = '';
let currentTab = 'dashboard';
let chatThreadId = null;
let chatSending = false;
let threadsData = [];
let logsData = [];
let logsSearch = '';

// ===== API Helper =====
async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...opts,
  });
  if (!res.ok) {
    if (res.status === 401) {
      window.location.href = '/admin/login.html';
      return;
    }
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

// ===== Navigation =====
const pageTitles = {
  dashboard: ['Dashboard', "Vue d'ensemble"],
  chat: ['Chat', 'Assistant IA'],
  threads: ['Threads', 'Conversations'],
  logs: ['Logs', 'Historique serveur'],
  apikeys: ['Cles API', 'Configuration'],
  sources: ['Sources', 'Moteurs de recherche'],
  models: ['Modeles', 'Pool LLM'],
  clients: ['Clients', 'Apps connectees'],
  metrics: ['Metriques', 'Performance'],
  service: ['Service', 'Controle systemd'],
  settings: ['Reglages', 'Configuration'],
  more: ['Plus', 'Autres sections'],
};

function go(tab, el) {
  currentTab = tab;
  document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  if (!el) el = document.querySelector(`.tab-item[data-tab="${tab}"]`);
  if (el) el.classList.add('active');
  const page = document.getElementById(`page-${tab}`);
  if (page) page.classList.add('active');
  const t = pageTitles[tab] || [tab, ''];
  document.getElementById('page-title').textContent = t[0];
  document.getElementById('page-subtitle').textContent = t[1];

  if (tab === 'dashboard') loadDashboard();
  if (tab === 'threads') loadThreads();
  if (tab === 'chat') document.getElementById('chat-input').focus();
  if (tab === 'logs') loadLogs();
  if (tab === 'apikeys') loadApiKeys();
  if (tab === 'sources') loadSources();
  if (tab === 'models') loadModels();
  if (tab === 'clients') loadClients();
  if (tab === 'metrics') loadMetrics();
  if (tab === 'service') loadService();
  if (tab === 'settings') loadSettings();
}

function refreshPage() {
  go(currentTab);
}

// ===== Toast =====
function toast(msg, type = 'info') {
  const container = document.getElementById('toasts');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000);
}

// ===== Dashboard =====
async function loadDashboard() {
  try {
    const [health, threads] = await Promise.all([
      api('/health').catch(() => ({ status: 'offline' })),
      api('/threads').catch(() => [])
    ]);
    const isOnline = health.status === 'ok';
    document.getElementById('stats-grid').innerHTML = `
      <div class="stat-card">
        <div class="stat-value" style="color:${isOnline ? 'var(--success)' : 'var(--danger)'}">${isOnline ? '●' : '○'}</div>
        <div class="stat-label">${isOnline ? 'En ligne' : 'Hors ligne'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${threads.length}</div>
        <div class="stat-label">Conversations</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${health.db === 'ok' ? '●' : '○'}</div>
        <div class="stat-label">Base de donnees</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">4500</div>
        <div class="stat-label">Port API</div>
      </div>`;
    const activity = document.getElementById('recent-activity');
    if (threads.length === 0) {
      activity.innerHTML = '<div class="empty-state" style="padding:32px"><div class="empty-title">Aucune activite</div><div class="empty-desc">Commencez une conversation.</div></div>';
    } else {
      activity.innerHTML = threads.slice(0, 5).map(t => `
        <div class="list-item" onclick="openThread('${t.id}')">
          <div class="list-icon blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
          <div class="list-content">
            <div class="list-title">${escapeHtml(t.title)}</div>
            <div class="list-subtitle">${timeAgo(t.updated_at)}</div>
          </div>
        </div>`).join('');
    }
  } catch (e) {
    document.getElementById('stats-grid').innerHTML = '<div class="stat-card" style="grid-column:span 2"><div class="stat-value" style="color:var(--danger)">✗</div><div class="stat-label">Erreur de connexion</div></div>';
  }
}

// ===== Chat =====
const chatInput = document.getElementById('chat-input');
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
  document.getElementById('chat-send').disabled = !chatInput.value.trim();
});
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
});

async function sendMsg() {
  if (chatSending) return;
  const text = chatInput.value.trim();
  if (!text) return;
  chatSending = true;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  document.getElementById('chat-send').disabled = true;
  const empty = document.getElementById('chat-empty');
  if (empty) empty.remove();
  addBubble('user', text);
  showTyping();
  try {
    const body = { message: text };
    if (chatThreadId) body.thread_id = chatThreadId;
    const data = await api('/chat', { method: 'POST', body: JSON.stringify(body) });
    removeTyping();
    chatThreadId = data.thread_id;
    addBubble('assistant', data.response);
  } catch (e) {
    removeTyping();
    addBubble('assistant', 'Erreur de connexion.');
  }
  chatSending = false;
  chatInput.focus();
}

function addBubble(role, text) {
  const messages = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-bubble ${role}`;
  div.innerHTML = role === 'user' ? escapeHtml(text).replace(/\n/g, '<br>') : renderMd(text);
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function showTyping() {
  const messages = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-bubble assistant';
  div.id = 'typing';
  div.innerHTML = '<div style="display:flex;gap:4px;padding:4px 0"><span style="width:8px;height:8px;background:var(--text-muted);border-radius:50%;animation:bounce 1.4s infinite"></span><span style="width:8px;height:8px;background:var(--text-muted);border-radius:50%;animation:bounce 1.4s 0.2s infinite"></span><span style="width:8px;height:8px;background:var(--text-muted);border-radius:50%;animation:bounce 1.4s 0.4s infinite"></span></div>';
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  const style = document.createElement('style');
  style.textContent = '@keyframes bounce{0%,80%,100%{transform:scale(0)}40%{transform:scale(1)}}';
  document.head.appendChild(style);
}

function removeTyping() {
  const el = document.getElementById('typing');
  if (el) el.remove();
}

// ===== Threads =====
async function loadThreads() {
  try {
    const data = await api('/threads');
    threadsData = data;
    renderThreads(data);
  } catch (e) {
    document.getElementById('threads-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur</div></div>';
  }
}

function renderThreads(threads) {
  const list = document.getElementById('threads-list');
  const search = (document.getElementById('threads-search')?.value || '').toLowerCase();
  const filtered = threads.filter(t => !search || t.title.toLowerCase().includes(search));
  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state"><div class="empty-title">Aucune conversation</div></div>';
    return;
  }
  list.innerHTML = filtered.map(t => `
    <div class="list-item" onclick="openThread('${t.id}')">
      <div class="list-icon purple"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
      <div class="list-content">
        <div class="list-title">${escapeHtml(t.title)}</div>
        <div class="list-subtitle">#${t.id.substring(0,8)} · ${timeAgo(t.updated_at)}</div>
      </div>
    </div>`).join('');
}

function filterThreads() { renderThreads(threadsData); }

function openThread(id) {
  chatThreadId = id;
  go('chat');
  loadThreadMessages(id);
}

async function loadThreadMessages(id) {
  try {
    const data = await api(`/threads/${id}`);
    const messages = document.getElementById('chat-messages');
    messages.innerHTML = '';
    data.messages.forEach(m => addBubble(m.role, m.content));
  } catch (e) {
    toast('Erreur de chargement', 'error');
  }
}

// ===== Logs =====
async function loadLogs() {
  try {
    const data = await api('/admin/logs?lines=200');
    logsData = data.logs || [];
    renderLogs();
  } catch (e) {
    document.getElementById('logs-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur de connexion</div></div>';
  }
}

function renderLogs() {
  const list = document.getElementById('logs-list');
  const search = (document.getElementById('logs-search')?.value || '').toLowerCase();
  const filtered = logsData.filter(l => !search || l.message.toLowerCase().includes(search) || l.level.includes(search));
  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-title">Aucun log</div></div>';
    return;
  }
  list.innerHTML = filtered.slice(0, 50).map(l => {
    const color = l.level === 'error' ? 'var(--danger)' : l.level === 'warning' ? 'var(--warning)' : 'var(--text-secondary)';
    return `<div class="log-item">
      <span class="log-time">${l.timestamp.split(' ')[1]?.substring(0,8) || ''}</span>
      <span class="log-level" style="color:${color}">${l.level.toUpperCase()}</span>
      <span class="log-msg">${escapeHtml(l.message).substring(0, 120)}</span>
    </div>`;
  }).join('');
}

function filterLogs() { renderLogs(); }

// ===== API Keys =====
let apiKeysData = {};
async function loadApiKeys() {
  try {
    const data = await api('/admin/env');
    apiKeysData = data;
    renderApiKeys();
  } catch (e) {
    document.getElementById('apikeys-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur</div></div>';
  }
}

function renderApiKeys() {
  const list = document.getElementById('apikeys-list');
  const keys = Object.keys(apiKeysData);
  if (keys.length === 0) {
    list.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-title">Aucune cle</div></div>';
    return;
  }
  list.innerHTML = keys.map(k => {
    const v = apiKeysData[k];
    const masked = v && (v.includes('...') || v === '***');
    return `<div class="apikey-item">
      <label class="apikey-label">${escapeHtml(k)}</label>
      <input type="password" class="input" id="apikey-${k}" value="${escapeHtml(v || '')}" placeholder="Non configure" data-masked="${masked}">
    </div>`;
  }).join('');
}

async function saveApiKeys() {
  const keys = {};
  document.querySelectorAll('[id^="apikey-"]').forEach(el => {
    const k = el.id.replace('apikey-', '');
    const v = el.value.trim();
    if (v && el.dataset.masked !== 'true') keys[k] = v;
  });
  try {
    await api('/admin/env', { method: 'POST', body: JSON.stringify(keys) });
    toast('Cles sauvegardees', 'success');
    loadApiKeys();
  } catch (e) {
    toast('Erreur de sauvegarde', 'error');
  }
}

// ===== Sources =====
async function loadSources() {
  try {
    const data = await api('/admin/sources');
    const list = document.getElementById('sources-list');
    list.innerHTML = data.map(s => `
      <div class="list-item">
        <div class="list-icon ${s.enabled ? 'green' : 'orange'}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>
        </div>
        <div class="list-content">
          <div class="list-title">${escapeHtml(s.name)}</div>
          <div class="list-subtitle">${escapeHtml(s.description || '')} ${s.requires_key ? '(cle requise)' : ''}</div>
        </div>
        <div class="toggle ${s.enabled ? 'active' : ''}" onclick="toggleSource('${s.name}', ${!s.enabled}, this)"></div>
      </div>`).join('');
  } catch (e) {
    document.getElementById('sources-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur</div></div>';
  }
}

async function toggleSource(name, enabled, el) {
  try {
    await api(`/admin/sources/${name}`, { method: 'POST', body: JSON.stringify({ enabled }) });
    el.classList.toggle('active');
    toast(`${name} ${enabled ? 'active' : 'desactive'}`, 'success');
  } catch (e) {
    toast('Erreur', 'error');
  }
}

// ===== Models =====
async function loadModels() {
  try {
    const data = await api('/admin/models');
    const list = document.getElementById('models-list');
    list.innerHTML = `
      <div class="card-body">
        <div class="settings-list">
          <div class="settings-item"><span class="settings-label">Modeles disponibles</span><span class="settings-value">${data.pool?.length || 0}</span></div>
          <div class="settings-item"><span class="settings-label">Max par requete</span><span class="settings-value">${data.models_per_request || 3}</span></div>
          <div class="settings-item"><span class="settings-label">Cache TTL</span><span class="settings-value">${data.cache_ttl || 300}s</span></div>
        </div>
      </div>
      <div class="card-header"><div class="card-title" style="font-size:13px;color:var(--text-secondary);text-transform:uppercase">Pool</div></div>
      ${(data.pool || []).map(m => `<div class="list-item"><div class="list-content"><div class="list-title" style="font-size:13px;font-family:monospace">${escapeHtml(m)}</div></div></div>`).join('')}
    `;
  } catch (e) {
    document.getElementById('models-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur</div></div>';
  }
}

// ===== Clients =====
async function loadClients() {
  try {
    const data = await api('/admin/clients');
    const list = document.getElementById('clients-list');
    if (!data.clients || data.clients.length === 0) {
      list.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-title">Aucun client</div></div>';
      return;
    }
    list.innerHTML = data.clients.map(c => `
      <div class="list-item">
        <div class="list-icon ${c.active ? 'green' : 'orange'}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
        </div>
        <div class="list-content">
          <div class="list-title">${escapeHtml(c.name)}</div>
          <div class="list-subtitle">${c.request_count} req · ${c.scopes?.join(', ') || 'aucun scope'}</div>
        </div>
        <div class="toggle ${c.active ? 'active' : ''}" onclick="toggleClient('${c.id}', ${!c.active})"></div>
      </div>`).join('');
  } catch (e) {
    document.getElementById('clients-list').innerHTML = '<div class="empty-state"><div class="empty-title">Erreur</div></div>';
  }
}

async function toggleClient(id, active) {
  try {
    const endpoint = active ? 'activate' : 'deactivate';
    await api(`/admin/clients/${id}/${endpoint}`, { method: 'POST' });
    toast(`Client ${active ? 'active' : 'desactive'}`, 'success');
    loadClients();
  } catch (e) {
    toast('Erreur', 'error');
  }
}

async function createClient() {
  const name = prompt('Nom du client:');
  if (!name) return;
  try {
    const data = await api('/admin/clients', { method: 'POST', body: JSON.stringify({ name }) });
    toast('Client cree', 'success');
    loadClients();
  } catch (e) {
    toast('Erreur', 'error');
  }
}

// ===== Metrics =====
async function loadMetrics() {
  try {
    const data = await api('/metrics');
    document.getElementById('metrics-grid').innerHTML = `
      <div class="stat-card"><div class="stat-value">${data.cache?.hit_rate != null ? Math.round(data.cache.hit_rate * 100) + '%' : '-'}</div><div class="stat-label">Cache hit rate</div></div>
      <div class="stat-card"><div class="stat-value">${data.cache?.size || 0}/${data.cache?.max_size || 0}</div><div class="stat-label">Cache entries</div></div>`;
    const sources = data.sources || {};
    const srcList = document.getElementById('metrics-sources');
    const srcKeys = Object.keys(sources);
    if (srcKeys.length === 0) {
      srcList.innerHTML = '<div class="card-body" style="font-size:13px;color:var(--text-secondary)">Aucune source utilisee</div>';
    } else {
      srcList.innerHTML = srcKeys.map(k => {
        const s = sources[k];
        return `<div class="list-item"><div class="list-content"><div class="list-title">${escapeHtml(k)}</div><div class="list-subtitle">${s.hits || 0} hits · ${s.failures || 0} echecs</div></div></div>`;
      }).join('');
    }
    const cb = data.circuit_breaker || {};
    document.getElementById('metrics-cache').innerHTML = `
      <div class="card-body">
        <div class="settings-list">
          <div class="settings-item"><span class="settings-label">CB etat</span><span class="settings-value">${cb.state || 'unknown'}</span></div>
          <div class="settings-item"><span class="settings-label">CB echecs</span><span class="settings-value">${cb.failure_count || 0}</span></div>
        </div>
      </div>`;
  } catch (e) {
    document.getElementById('metrics-grid').innerHTML = '<div class="stat-card" style="grid-column:span 2"><div class="stat-value" style="color:var(--danger)">✗</div><div class="stat-label">Metriques indisponibles</div></div>';
  }
}

// ===== Service =====
async function loadService() {
  try {
    const data = await api('/admin/service/status');
    const el = document.getElementById('service-status');
    el.innerHTML = `<div class="service-indicator ${data.running ? 'running' : 'stopped'}">
      <div class="service-dot"></div>
      <span>${data.running ? 'En cours d\'execution' : 'Arrete'}</span>
    </div>`;
  } catch (e) {
    document.getElementById('service-status').innerHTML = '<div style="color:var(--text-secondary)">Etat inconnu</div>';
  }
}

async function restartService() {
  if (!confirm('Redemarrer le service ?')) return;
  try {
    await api('/admin/service/restart', { method: 'POST' });
    toast('Redemarrage en cours...', 'success');
    setTimeout(loadService, 3000);
  } catch (e) {
    toast('Erreur', 'error');
  }
}

async function stopService() {
  if (!confirm('Arreter le service ?')) return;
  try {
    await api('/admin/service/stop', { method: 'POST' });
    toast('Service arrete', 'success');
    setTimeout(loadService, 2000);
  } catch (e) {
    toast('Erreur', 'error');
  }
}

// ===== Settings =====
async function loadSettings() {
  try {
    const [settings, security] = await Promise.all([
      api('/admin/settings').catch(() => ({})),
      api('/admin/security').catch(() => ({}))
    ]);
    document.getElementById('set-name').textContent = settings.general?.displayname || settings.general?.fullname || '-';
    document.getElementById('set-ai').textContent = settings.ai?.name || 'WebSearch';
    document.getElementById('set-style').textContent = settings.ai?.response_style || 'Equilibre';
    document.getElementById('set-2fa').textContent = security.two_factor_enabled ? 'Active' : 'Desactive';
    document.getElementById('set-sessions').textContent = security.active_sessions || 0;
  } catch (e) {}
}

async function clearCache() {
  try {
    await api('/admin/cache/clear', { method: 'POST' });
    toast('Cache vide', 'success');
  } catch (e) {
    toast('Erreur', 'error');
  }
}

async function logout() {
  try {
    await api('/admin/api/logout', { method: 'POST' });
  } catch (e) {}
  window.location.href = '/admin/login.html';
}

// ===== Helpers =====
function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function timeAgo(ts) {
  const now = Date.now();
  const t = typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts;
  const diff = now - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return "a l'instant";
  if (m < 60) return `il y a ${m}min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `il y a ${h}h`;
  const d = Math.floor(h / 24);
  return `il y a ${d}j`;
}

function renderMd(text) {
  if (typeof marked === 'undefined') return escapeHtml(text).replace(/\n/g, '<br>');
  return marked.parse(text);
}

// ===== Auth Check =====
async function checkAuth() {
  try {
    const data = await api('/admin/api/auth/check');
    if (!data.authenticated) window.location.href = '/admin/login.html';
  } catch (e) {
    window.location.href = '/admin/login.html';
  }
}

// ===== Init =====
checkAuth();
loadDashboard();

// ===== PWA Install =====
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  const group = document.getElementById('install-group');
  if (group) group.style.display = '';
});

function installPWA() {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(() => {
    deferredPrompt = null;
    const group = document.getElementById('install-group');
    if (group) group.style.display = 'none';
  });
}
