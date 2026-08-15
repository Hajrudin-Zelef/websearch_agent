// ─── Navigation ───
function initNavigation() {
    $$('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            $$('.nav-item').forEach(n => n.classList.remove('active'));
            $$('.page').forEach(p => p.classList.remove('active'));
            item.classList.add('active');
            const page = item.dataset.page;
            $(`#page-${page}`).classList.add('active');
            if (page === 'threads') loadThreads();
            if (page === 'logs') startLogs();
            if (page === 'settings') loadSettings();
            if (page === 'clients') loadClients();
            if (page === 'metrics') loadMetrics();
            if (page !== 'logs') stopLogs();
            if (window.innerWidth <= 768) closeSidebar();
        });
    });
}

// ─── Mobile Sidebar ───
function toggleSidebar() {
    const sidebar = $('#sidebar');
    const backdrop = $('#sidebar-backdrop');
    sidebar.classList.toggle('open');
    backdrop.classList.toggle('active');
    document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
}

function closeSidebar() {
    const sidebar = $('#sidebar');
    const backdrop = $('#sidebar-backdrop');
    sidebar.classList.remove('open');
    backdrop.classList.remove('active');
    document.body.style.overflow = '';
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSidebar();
});

window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeSidebar();
});

// ─── Auth Check ───
(async () => {
    try {
        const res = await fetch('/admin/api/auth/check');
        const data = await res.json();
        if (!data.authenticated) {
            window.location.href = '/admin/login.html';
        }
    } catch (e) {
        window.location.href = '/admin/login.html';
    }
})();

// ─── Logout ───
async function logout() {
    try {
        await api('/admin/api/logout', { method: 'POST' });
        window.location.href = '/admin/login.html';
    } catch (e) {
        window.location.href = '/admin/login.html';
    }
}

// ─── Init ───
initNavigation();
initIcons();
loadDashboard();
loadAPIKeys();
loadSources();
loadModels();
loadServiceStatus();
loadClients();
