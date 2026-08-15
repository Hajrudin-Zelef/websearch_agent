async function loadServiceStatus() {
    try {
        const data = await api('/admin/service/status');
        const isRunning = data.running;
        $('#service-status').innerHTML = `
            <span class="badge badge-${isRunning ? 'success' : 'danger'}">
                <i data-lucide="${isRunning ? 'check-circle-2' : 'x-circle'}" style="width:10px;height:10px"></i>
                ${isRunning ? 'En marche' : 'Arrete'}
            </span>
        `;
        initIcons();
    } catch (e) {}
}

async function serviceAction(action) {
    const msg = action === 'stop' ? 'Arreter le serveur ?' : 'Redemarrer le serveur ?';
    if (!confirm(msg)) return;
    try {
        await api('/admin/service/' + action, { method: 'POST' });
        toast(`Service ${action === 'stop' ? 'arrete' : 'redemarré'}`, 'success');
        setTimeout(loadServiceStatus, 2000);
    } catch (e) {
        toast('Erreur de controle du service', 'error');
    }
}

async function clearCache() {
    try {
        await api('/admin/cache/clear', { method: 'POST' });
        toast('Cache vide', 'success');
    } catch (e) {
        toast('Erreur de vidage du cache', 'error');
    }
}
