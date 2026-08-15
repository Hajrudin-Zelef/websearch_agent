let chatThreadId = null;
let chatSending = false;
const chatInput = $('#chat-input');
const chatInner = $('#chat-inner');

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
});

function useSuggestion(chip) {
    const text = chip.querySelector('p').textContent;
    chatInput.value = text;
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
    sendChat();
}

function newChatThread() {
    chatThreadId = null;
    chatInner.innerHTML = `
        <div class="chat-welcome" id="welcome">
            <div class="chat-welcome-icon">
                <i data-lucide="sparkles"></i>
            </div>
            <h1>Comment puis-je vous aider ?</h1>
            <p>Posez une question, lancez une recherche ou analysez des informations avec votre agent IA.</p>
            <div class="chat-suggestions">
                <div class="suggestion-card" onclick="useSuggestion(this)">
                    <div class="suggestion-card-icon blue"><i data-lucide="globe"></i></div>
                    <div class="suggestion-card-text">
                        <h3>Recherche Web</h3>
                        <p>Explique le machine learning</p>
                    </div>
                </div>
                <div class="suggestion-card" onclick="useSuggestion(this)">
                    <div class="suggestion-card-icon purple"><i data-lucide="file-search"></i></div>
                    <div class="suggestion-card-text">
                        <h3>Analyse</h3>
                        <p>Recherche les dernieres actualites IA</p>
                    </div>
                </div>
                <div class="suggestion-card" onclick="useSuggestion(this)">
                    <div class="suggestion-card-icon green"><i data-lucide="git-compare"></i></div>
                    <div class="suggestion-card-text">
                        <h3>Comparaison</h3>
                        <p>Compare Claude et GPT</p>
                    </div>
                </div>
                <div class="suggestion-card" onclick="useSuggestion(this)">
                    <div class="suggestion-card-icon yellow"><i data-lucide="file-text"></i></div>
                    <div class="suggestion-card-text">
                        <h3>Resume</h3>
                        <p>Resume cet article pour moi</p>
                    </div>
                </div>
                <div class="suggestion-card" onclick="useSuggestion(this)">
                    <div class="suggestion-card-icon red"><i data-lucide="radar"></i></div>
                    <div class="suggestion-card-text">
                        <h3>Veille</h3>
                        <p>Veille technologique IA</p>
                    </div>
                </div>
            </div>
        </div>`;
    initIcons();
    chatInput.focus();
}

function appendChatMessage(role, text, metadata) {
    const isUser = role === 'user';
    const isRefused = metadata && metadata.refused;
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

    const div = document.createElement('div');
    div.className = `msg msg-${isUser ? 'user' : 'assistant'}`;

    const avatarIcon = isUser ? 'user' : 'sparkles';
    const name = isUser ? 'Vous' : 'WebSearch Agent';

    const contentHtml = isUser
        ? escapeHtml(text).replace(/\n/g, '<br>')
        : renderMd(text);

    div.innerHTML = `
        <div class="msg-avatar">
            <i data-lucide="${avatarIcon}"></i>
        </div>
        <div class="msg-body">
            <div class="msg-meta">
                <span class="msg-name">${name}</span>
                <span class="msg-time">${time}</span>
            </div>
            <div class="msg-content">${contentHtml}</div>
            ${isRefused ? '<div class="msg-refused"><i data-lucide="alert-triangle"></i> Reponse refusee</div>' : ''}
            <div class="msg-actions">
                <button class="msg-action-btn" onclick="copyChatMessage(this)" title="Copier">
                    <i data-lucide="copy"></i> Copier
                </button>
                ${!isUser ? '<button class="msg-action-btn" onclick="regenerateChatMessage()" title="Regenerer"><i data-lucide="refresh-cw"></i> Regenerer</button>' : ''}
            </div>
        </div>`;

    chatInner.appendChild(div);
    initIcons();
    chatScrollToBottom();
}

function showChatTyping() {
    const steps = [
        { text: 'Recherche en cours...', delay: 0 },
        { text: 'Analyse des resultats...', delay: 1500 },
        { text: 'Construction de la reponse...', delay: 3000 }
    ];

    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.id = 'typing-indicator';

    div.innerHTML = `
        <div class="typing-avatar">
            <i data-lucide="sparkles"></i>
        </div>
        <div class="typing-body">
            <div class="typing-content">
                <div class="typing-steps">
                    ${steps.map((s, i) => `
                        <div class="typing-step ${i === 0 ? 'active' : ''}" data-step="${i}">
                            <div class="typing-step-icon"></div>
                            <span>${s.text}</span>
                        </div>
                    `).join('')}
                </div>
                <div class="typing-progress">
                    <div class="typing-progress-bar"></div>
                </div>
            </div>
        </div>`;

    chatInner.appendChild(div);
    initIcons();
    chatScrollToBottom();

    steps.forEach((s, i) => {
        if (i === 0) return;
        setTimeout(() => {
            const el = div.querySelector(`[data-step="${i}"]`);
            if (el) {
                div.querySelectorAll('.typing-step').forEach(t => t.classList.remove('active'));
                el.classList.add('active');
                const prev = div.querySelector(`[data-step="${i - 1}"]`);
                if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
            }
        }, s.delay);
    });
}

function removeChatTyping() {
    const el = $('#typing-indicator');
    if (el) el.remove();
}

function chatScrollToBottom(smooth = true) {
    const chat = $('#chat-messages');
    if (!chat) return;
    requestAnimationFrame(() => {
        chat.scrollTo({ top: chat.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
    });
}

function copyChatMessage(btn) {
    const content = btn.closest('.msg-body').querySelector('.msg-content');
    navigator.clipboard.writeText(content.textContent).then(() => {
        toast('Copie dans le presse-papier', 'success');
    });
}

async function regenerateChatMessage() {
    const msgs = chatInner.querySelectorAll('.msg-user');
    if (msgs.length === 0) return;
    const lastUserMsg = msgs[msgs.length - 1].querySelector('.msg-content').textContent;
    chatInput.value = lastUserMsg;
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
    sendChat();
}

async function sendChat() {
    if (chatSending) return;
    const text = chatInput.value.trim();
    if (!text) return;

    chatSending = true;
    const btn = $('#btn-send');
    btn.disabled = true;
    chatInput.value = '';
    chatInput.style.height = 'auto';

    appendChatMessage('user', text);
    showChatTyping();

    try {
        const body = { message: text };
        if (chatThreadId) body.thread_id = chatThreadId;

        const data = await api('/chat', { method: 'POST', body: JSON.stringify(body) });
        removeChatTyping();

        if (data.error) {
            toast(data.error, 'error');
        } else {
            chatThreadId = data.thread_id;
            appendChatMessage('assistant', data.response, { refused: data.refused });
        }
    } catch (e) {
        removeChatTyping();
        toast('Erreur de connexion. Verifiez que le serveur est actif.', 'error');
    }

    chatSending = false;
    btn.disabled = false;
    chatInput.focus();
    chatScrollToBottom();
}
