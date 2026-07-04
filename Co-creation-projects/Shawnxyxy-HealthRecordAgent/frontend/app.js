/** 应用壳层：用户身份、侧边栏、会话列表 */

const API_BASE = "http://127.0.0.1:8000";
const USER_ID_STORAGE_KEY = "healthRecordAgent_userId";
const DISPLAY_NAME_STORAGE_KEY = "healthRecordAgent_displayName";
const CHAT_SESSION_KEY = "healthRecordAgent_chatSessionId";

function ensureUserId() {
    try {
        let id = localStorage.getItem(USER_ID_STORAGE_KEY);
        if (!id) {
            id = "user-" + (crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Date.now().toString(36));
            localStorage.setItem(USER_ID_STORAGE_KEY, id);
        }
        return id;
    } catch (_) {
        return "user-anonymous";
    }
}

function getUserId() {
    return ensureUserId();
}

function getDisplayName() {
    try {
        return localStorage.getItem(DISPLAY_NAME_STORAGE_KEY) || "用户";
    } catch (_) {
        return "用户";
    }
}

function setDisplayName(name) {
    const v = (name || "").trim() || "用户";
    try {
        localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, v);
    } catch (_) { /* ignore */ }
    refreshUserChip();
}

function refreshUserChip() {
    const name = getDisplayName();
    const nameEl = document.getElementById("userDisplayName");
    const avatarEl = document.getElementById("userAvatar");
    const idEl = document.getElementById("userIdDisplay");
    if (nameEl) nameEl.textContent = name;
    if (avatarEl) avatarEl.textContent = name.charAt(0).toUpperCase();
    if (idEl) idEl.textContent = ensureUserId();
}

function openSidebar() {
    document.body.classList.add("sidebar-open");
    const bd = document.getElementById("sidebarBackdrop");
    if (bd) bd.hidden = false;
}

function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    const bd = document.getElementById("sidebarBackdrop");
    if (bd) bd.hidden = true;
}

function toggleUserPanel() {
    const panel = document.getElementById("userPanel");
    const chip = document.getElementById("userChip");
    if (!panel) return;
    const open = panel.classList.toggle("hidden");
    if (chip) chip.setAttribute("aria-expanded", open ? "false" : "true");
}

async function loadSessionList() {
    const listEl = document.getElementById("sessionList");
    if (!listEl) return;

    const userId = ensureUserId();
    listEl.innerHTML = '<p class="session-list-loading">加载中…</p>';

    try {
        const res = await fetch(
            `${API_BASE}/api/chat/users/${encodeURIComponent(userId)}/sessions?limit=30`
        );
        const data = await res.json();
        const items = data.items || [];
        if (!items.length) {
            listEl.innerHTML = '<p class="session-list-empty">暂无历史对话</p>';
            return;
        }
        listEl.innerHTML = "";
        items.forEach((row) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "session-item";
            if (row.session_id === getCurrentSessionId()) {
                btn.classList.add("session-item-active");
            }
            btn.dataset.sessionId = row.session_id;
            const preview = (row.preview || "新对话").replace(/^\[上传附件:.*\]$/, "📎 上传报告");
            btn.textContent = preview.length > 28 ? preview.slice(0, 28) + "…" : preview;
            btn.title = preview;
            btn.addEventListener("click", () => switchToSession(row.session_id));
            listEl.appendChild(btn);
        });
    } catch (e) {
        listEl.innerHTML = '<p class="session-list-empty">加载失败</p>';
        console.warn("loadSessionList:", e);
    }
}

function getCurrentSessionId() {
    try {
        return localStorage.getItem(CHAT_SESSION_KEY);
    } catch (_) {
        return null;
    }
}

function setCurrentSessionId(sessionId) {
    try {
        if (sessionId) localStorage.setItem(CHAT_SESSION_KEY, sessionId);
        else localStorage.removeItem(CHAT_SESSION_KEY);
    } catch (_) { /* ignore */ }
    if (typeof window.onChatSessionChanged === "function") {
        window.onChatSessionChanged(sessionId);
    }
}

async function switchToSession(sessionId) {
    setCurrentSessionId(sessionId);
    closeSidebar();
    if (typeof window.loadChatForSession === "function") {
        await window.loadChatForSession(sessionId);
    }
    await loadSessionList();
}

async function startNewChat() {
    setCurrentSessionId(null);
    if (typeof window.resetChatView === "function") {
        window.resetChatView();
    }
    closeSidebar();
    await loadSessionList();
    const input = document.getElementById("chatInput");
    input?.focus();
}

function resetUserIdentity() {
    if (!confirm("将清除本地用户标识与当前会话，历史数据仍保留在服务器上。继续？")) return;
    try {
        localStorage.removeItem(USER_ID_STORAGE_KEY);
        localStorage.removeItem(DISPLAY_NAME_STORAGE_KEY);
        localStorage.removeItem(CHAT_SESSION_KEY);
    } catch (_) { /* ignore */ }
    setDisplayName("用户");
    refreshUserChip();
    startNewChat();
    loadSessionList();
}

document.addEventListener("DOMContentLoaded", () => {
    refreshUserChip();

    const displayInput = document.getElementById("displayNameInput");
    if (displayInput) {
        displayInput.value = getDisplayName();
        displayInput.addEventListener("change", () => setDisplayName(displayInput.value));
        displayInput.addEventListener("blur", () => setDisplayName(displayInput.value));
    }

    document.getElementById("sidebarOpenBtn")?.addEventListener("click", openSidebar);
    document.getElementById("sidebarCloseBtn")?.addEventListener("click", closeSidebar);
    document.getElementById("sidebarBackdrop")?.addEventListener("click", closeSidebar);
    document.getElementById("newChatBtn")?.addEventListener("click", startNewChat);
    document.getElementById("userChip")?.addEventListener("click", toggleUserPanel);
    document.getElementById("resetUserBtn")?.addEventListener("click", resetUserIdentity);

    loadSessionList();
});
