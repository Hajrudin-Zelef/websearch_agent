// WebSearch PWA - Mobile App Logic
const API = '';
let currentTab = 'dashboard';
let chatThreadId = null;
let chatSending = false;
let threadsData = [];

// ===== API Helper =====
async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ===== Navigation =====
function go(tab, el) {
  currentTab = tab;
  document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
  document.getElementById(`page-${tab}`).classList.add('active');

  const titles = {
    dashboard: ['Dashboard', 'Vue d\'ensemble'],
    chat: ['Chat', 'Assistant IA'],
    threads: ['Threads', 'Conversations'],
    settings: ['Paramètres', 'Configuration']
  };
  document.getElementById('page-title').textContent = titles[tab][0];
  document.getElementById('page-subtitle').textContent = titles[tab][1];

  if (tab === 'dashboard') loadDashboard();
  if (tab === 'threads') loadThreads();
  if (tab === 'settings') loadSettings();
  if (tab === 'chat') document.getElementById('chat-input').focus();
}

function refreshPage() {
  if (currentTab === 'dashboard') loadDashboard();
  if (currentTab === 'threads') loadThreads();
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
        <div class="stat-label">Base de données</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">4500</div>
        <div class="stat-label">Port API</div>
      </div>
    `;

    const activity = document.getElementById('recent-activity');
    if (threads.length === 0) {
      activity.innerHTML = `
        <div class="empty-state" style="padding:32px">
          <div class="empty-title">Aucune activité</div>
          <div class="empty-desc">Commencez une conversation pour démarrer.</div>
        </div>`;
    } else {
      activity.innerHTML = threads.slice(0, 5).map(t => `
        <div class="list-item" onclick="openThread('${t.id}')">
          <div class="list-icon blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
          <div class="list-content">
            <div class="list-title">${escapeHtml(t.title)}</div>
            <div class="list-subtitle">${timeAgo(t.updated_at)}</div>
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    document.getElementById('stats-grid').innerHTML = `
      <div class="stat-card" style="grid-column:span 2">
        <div class="stat-value" style="color:var(--danger)">✗</div>
        <div class="stat-label">Erreur de connexion</div>
      </div>`;
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
    addBubble('assistant', 'Erreur de connexion. Vérifiez votre réseau.');
  }

  chatSending = false;
  chatInput.focus();
}

function addBubble(role, text) {
  const messages = document.getElementById('chat-messages');
  const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
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
    document.getElementById('threads-list').innerHTML = `
      <div class="empty-state">
        <div class="empty-title">Erreur de connexion</div>
        <div class="empty-desc">Impossible de charger les conversations.</div>
      </div>`;
  }
}

function renderThreads(threads) {
  const list = document.getElementById('threads-list');
  const search = (document.getElementById('threads-search')?.value || '').toLowerCase();
  const filtered = threads.filter(t => !search || t.title.toLowerCase().includes(search));

  if (filtered.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
        <div class="empty-title">${search ? 'Aucun résultat' : 'Aucune conversation'}</div>
        <div class="empty-desc">${search ? 'Essayez un autre terme.' : 'Les conversations apparaîtront ici.'}</div>
      </div>`;
    return;
  }

  list.innerHTML = filtered.map(t => `
    <div class="list-item" onclick="openThread('${t.id}')">
      <div class="list-icon purple"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div>
      <div class="list-content">
        <div class="list-title">${escapeHtml(t.title)}</div>
        <div class="list-subtitle">#${t.id.substring(0,8)} · ${timeAgo(t.updated_at)}</div>
      </div>
    </div>
  `).join('');
}

function filterThreads() {
  renderThreads(threadsData);
}

function openThread(id) {
  chatThreadId = id;
  go('chat', document.querySelector('[data-page="chat"]'));
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

// ===== Settings =====
async function loadSettings() {
  try {
    const data = await api('/admin/settings');
    document.getElementById('set-name').textContent = data.general?.displayname || '—';
    document.getElementById('set-ai').textContent = data.ai?.name || 'WebSearch';
    document.getElementById('set-style').textContent = data.ai?.response_style || 'Équilibré';
    document.getElementById('set-lang').textContent = 'Français';
  } catch (e) {}
}

async function clearCache() {
  try {
    await api('/admin/cache/clear', { method: 'POST' });
    toast('Cache vidé', 'success');
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
  if (m < 1) return "à l'instant";
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

window.addEventListener('appinstalled', () => {
  deferredPrompt = null;
  const group = document.getElementById('install-group');
  if (group) group.style.display = 'none';
  toast('Application installée', 'success');
});
