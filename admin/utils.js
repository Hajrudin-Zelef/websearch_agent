const API_BASE = '';
async function api(path, opts = {}) {
const res = await fetch(API_BASE + path, {
headers: { 'Content-Type': 'application/json' },
credentials: 'include',
...opts,
});
if (!res.ok) {
  // Si l'utilisateur n'est pas authentifié, rediriger vers la page de connexion
  if (res.status === 401) {
    window.location.href = '/admin/login.html';
    return;
  }
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  throw new Error(err.detail || err.error || 'Erreur serveur');
}
return res.json();
}
function $(sel, ctx = document) { return ctx.querySelector(sel); }
function $$(sel, ctx = document) { return [...ctx.querySelectorAll(sel)]; }
function el(tag, attrs = {}, children = []) {
const e = document.createElement(tag);
for (const [k, v] of Object.entries(attrs)) {
if (k === 'class') e.className = v;
else if (k === 'style' && typeof v === 'object') Object.assign(e.style, v);
else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
else if (k === 'html') e.innerHTML = v;
else if (k === 'text') e.textContent = v;
else e.setAttribute(k, v);
}
for (const c of children) {
if (typeof c === 'string') e.appendChild(document.createTextNode(c));
else if (c) e.appendChild(c);
}
return e;
}
function escapeHtml(s) {
const div = document.createElement('div');
div.textContent = s;
return div.innerHTML;
}
function timeAgo(timestamp) {
const now = Date.now();
const ts = typeof timestamp === 'number' && timestamp < 1e12 ? timestamp * 1000 : timestamp;
const diff = now - ts;
const seconds = Math.floor(diff / 1000);
const minutes = Math.floor(seconds / 60);
const hours = Math.floor(minutes / 60);
const days = Math.floor(hours / 24);
if (seconds < 60) return "à l'instant";
if (minutes < 60) return `il y a ${minutes}min`;
if (hours < 24) return `il y a ${hours}h`;
if (days < 7) return `il y a ${days}j`;
return new Date(ts).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}
function formatDate(timestamp) {
const ts = typeof timestamp === 'number' && timestamp < 1e12 ? timestamp * 1000 : timestamp;
return new Date(ts).toLocaleDateString('fr-FR', {
day: 'numeric', month: 'short', year: 'numeric',
hour: '2-digit', minute: '2-digit'
});
}
let toastContainer = null;
function ensureToastContainer() {
if (!toastContainer) {
toastContainer = el('div', { class: 'toast-container', id: 'toast-container' });
document.body.appendChild(toastContainer);
}
return toastContainer;
}
function toast(msg, type = 'info', duration = 3500) {
const container = ensureToastContainer();
const icons = {
success: '<i data-lucide="check-circle-2"></i>',
error: '<i data-lucide="x-circle"></i>',
warning: '<i data-lucide="alert-triangle"></i>',
info: '<i data-lucide="info"></i>',
};
const t = el('div', { class: `toast ${type}`, html: `
<span class="toast-icon">${icons[type] || icons.info}</span>
<span>${escapeHtml(msg)}</span>
`});
container.appendChild(t);
if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [t] });
setTimeout(() => {
t.classList.add('leaving');
setTimeout(() => t.remove(), 200);
}, duration);
}
function renderMd(text) {
if (typeof marked === 'undefined') return fallbackMd(text);
marked.setOptions({
gfm: true,
breaks: true,
headerIds: false,
mangle: false,
});
const renderer = new marked.Renderer();
renderer.code = function(code, lang) {
const escaped = escapeHtml(typeof code === 'object' ? code.text : code);
const language = typeof code === 'object' ? code.lang : lang;
const langLabel = language ? `<div class="code-lang">${language}</div>` : '';
return `<pre class="code-block">${langLabel}<code class="language-${language || 'text'}">${escaped}</code></pre>`;
};
renderer.table = function(header, body) {
return `<div class="table-wrap"><table class="table"><thead>${header}</thead><tbody>${body}</tbody></table></div>`;
};
return marked.parse(text, { renderer });
}
function fallbackMd(s) {
s = escapeHtml(s);
s = s.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>');
s = s.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
s = s.replace(/^## (.+)$/gm, '<h2>$1</h2>');
s = s.replace(/^# (.+)$/gm, '<h1>$1</h1>');
s = s.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
s = s.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
s = s.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
s = s.replace(/^---$/gm, '<hr>');
s = s.split(/\n\n+/).map(p => {
p = p.trim();
if (!p) return '';
if (p.startsWith('<h') || p.startsWith('<pre') || p.startsWith('<blockquote') || p.startsWith('<hr') || p.startsWith('<li') || p.startsWith('<div')) return p;
return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
}).join('\n');
s = s.replace(/(<li>[\s\S]*?<\/li>)/g, m => {
if (m.startsWith('<ul>') || m.startsWith('<ol>')) return m;
return '<ul>' + m + '</ul>';
});
return s;
}
function createTyping() {
const div = el('div', { class: 'msg assistant', id: 'typing-indicator' });
div.innerHTML = `
<div class="msg-avatar"><i data-lucide="bot"></i></div>
<div class="msg-content">
<div class="msg-role">Agent</div>
<div class="typing-dots"><span></span><span></span><span></span></div>
</div>`;
return div;
}
function removeTyping() {
const el = $('#typing-indicator');
if (el) el.remove();
}
function scrollToBottom(smooth = true) {
const chat = $('#chat-messages') || $('#chat');
if (!chat) return;
requestAnimationFrame(() => {
chat.scrollTo({ top: chat.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
});
}
function initKeyboardShortcuts(handlers) {
document.addEventListener('keydown', (e) => {
const isMeta = e.metaKey || e.ctrlKey;
if (isMeta && e.key === 'k') {
e.preventDefault();
handlers.search?.();
}
if (isMeta && e.key === 'n') {
e.preventDefault();
handlers.newThread?.();
}
});
}
function initIcons() {
if (typeof lucide !== 'undefined') {
lucide.createIcons();
}
}
function observeIcons(container) {
if (typeof lucide === 'undefined') return;
let pending = false;
const observer = new MutationObserver((mutations) => {
const hasNewIconPlaceholder = mutations.some(m =>
[...m.addedNodes].some(n => n.nodeType === 1 && (n.hasAttribute?.('data-lucide') || n.querySelector?.('[data-lucide]')))
);
if (!hasNewIconPlaceholder || pending) return;
pending = true;
requestAnimationFrame(() => {
lucide.createIcons({ nodes: container ? [container] : undefined });
pending = false;
});
});
observer.observe(document.body, { childList: true, subtree: true });
}
if (document.readyState === 'loading') {
document.addEventListener('DOMContentLoaded', () => { initIcons(); observeIcons(); });
} else {
initIcons();
observeIcons();
}