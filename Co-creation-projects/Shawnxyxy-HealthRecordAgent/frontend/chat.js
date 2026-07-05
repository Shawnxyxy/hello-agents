/** 健康助手对话 — SSE 客户端 */

let chatSessionId = null;
let chatPendingFile = null;
let chatStreaming = false;

const WELCOME_HTML = `
<div class="message-row message-assistant message-welcome">
    <div class="message-avatar">AI</div>
    <div class="message-body">
        <p>你好，我是<strong>健康助手</strong>。</p>
        <ul>
            <li>直接提问健康、饮食相关问题</li>
            <li>上传 PDF / 文本体检报告，我会帮你解读</li>
            <li>上传后可继续追问「我的指标怎么样？」</li>
        </ul>
    </div>
</div>`;

async function ensureChatSession(userId, options = {}) {
    const { forceNew = false, restoreHistory = false } = options;

    if (!forceNew && !chatSessionId) {
        const saved = getCurrentSessionId();
        if (saved) chatSessionId = saved;
    }

    if (!forceNew && chatSessionId) {
        try {
            const check = await fetch(
                `${API_BASE}/api/chat/sessions/${encodeURIComponent(chatSessionId)}?user_id=${encodeURIComponent(userId)}`
            );
            if (check.ok) {
                setCurrentSessionId(chatSessionId);
                if (restoreHistory) await loadChatSessionHistory(userId, chatSessionId);
                return chatSessionId;
            }
        } catch (_) { /* ignore */ }
        chatSessionId = null;
    }

    const res = await fetch(`${API_BASE}/api/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
    });
    if (!res.ok) throw new Error("创建会话失败");
    const data = await res.json();
    chatSessionId = data.session_id;
    setCurrentSessionId(chatSessionId);
    if (typeof loadSessionList === "function") loadSessionList();
    return chatSessionId;
}

function resetChatView() {
    chatSessionId = null;
    const box = document.getElementById("chatMessages");
    if (box) box.innerHTML = WELCOME_HTML;
    clearChatAttachment();
    setChatProgress("");
}

window.resetChatView = resetChatView;

async function loadChatForSession(sessionId) {
    chatSessionId = sessionId;
    const userId = getUserId();
    const box = document.getElementById("chatMessages");
    if (!box) return;
    box.innerHTML = "";
    await loadChatSessionHistory(userId, sessionId);
    if (!box.children.length) box.innerHTML = WELCOME_HTML;
}

window.loadChatForSession = loadChatForSession;

window.onChatSessionChanged = (sessionId) => {
    chatSessionId = sessionId;
};

async function loadChatSessionHistory(userId, sessionId) {
    const res = await fetch(
        `${API_BASE}/api/chat/sessions/${encodeURIComponent(sessionId)}/history?user_id=${encodeURIComponent(userId)}&limit=100`
    );
    if (!res.ok) return;
    const data = await res.json();
    (data.messages || []).forEach((m) => {
        appendMessage(m.role === "user" ? "user" : "assistant", m.content || "", m.attachment_name);
    });
}

function appendMessage(role, text, attachmentName) {
    const box = document.getElementById("chatMessages");
    if (!box) return null;

    const welcome = box.querySelector(".message-welcome");
    if (welcome) welcome.remove();

    const row = document.createElement("div");
    row.className = `message-row message-${role}`;
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? (getDisplayName().charAt(0).toUpperCase() || "U") : "AI";
    const body = document.createElement("div");
    body.className = "message-body";
    body.innerHTML = `<div class="chat-markdown">${formatChatText(text)}</div>`;
    if (attachmentName) {
        body.innerHTML += `<div class="chat-attachment-tag">📎 ${escapeHtml(attachmentName)}</div>`;
    }
    row.appendChild(avatar);
    row.appendChild(body);
    box.appendChild(row);
    scrollChatToBottom();
    return body;
}

function scrollChatToBottom() {
    const box = document.getElementById("chatMessages");
    if (box) box.scrollTop = box.scrollHeight;
}

function setChatProgress(text) {
    const el = document.getElementById("chatProgress");
    if (!el) return;
    if (!text) {
        el.classList.add("hidden");
        el.textContent = "";
        return;
    }
    el.classList.remove("hidden");
    el.textContent = text;
}

function updateSendButtonState() {
    const input = document.getElementById("chatInput");
    const btn = document.getElementById("chatSendBtn");
    if (!btn || !input) return;
    const hasContent = input.value.trim().length > 0 || !!chatPendingFile;
    btn.disabled = !hasContent || chatStreaming;
}

function onChatFileSelected(event) {
    const file = event.target.files && event.target.files[0];
    chatPendingFile = file || null;
    const preview = document.getElementById("chatAttachmentPreview");
    if (!preview) return;
    if (!file) {
        preview.classList.add("hidden");
        preview.textContent = "";
    } else {
        preview.classList.remove("hidden");
        preview.textContent = `📎 ${file.name}`;
    }
    updateSendButtonState();
}

function clearChatAttachment() {
    chatPendingFile = null;
    const input = document.getElementById("chatFile");
    if (input) input.value = "";
    const preview = document.getElementById("chatAttachmentPreview");
    if (preview) {
        preview.classList.add("hidden");
        preview.textContent = "";
    }
    updateSendButtonState();
}

function parseSseChunk(buffer) {
    const events = [];
    const parts = buffer.split("\n\n");
    const remainder = parts.pop() || "";
    for (const part of parts) {
        if (!part.trim()) continue;
        let event = "message";
        let data = "";
        for (const line of part.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (data) {
            try {
                events.push({ event, data: JSON.parse(data) });
            } catch (_) {
                events.push({ event, data: { raw: data } });
            }
        }
    }
    return { events, remainder };
}

async function sendChatMessage(event) {
    if (event) event.preventDefault();
    if (chatStreaming) return;

    const userId = getUserId();
    const input = document.getElementById("chatInput");
    const message = input ? input.value.trim() : "";
    if (!message && !chatPendingFile) return;

    appendMessage("user", message || "（上传附件）", chatPendingFile?.name);
    if (input) {
        input.value = "";
        input.style.height = "auto";
    }
    updateSendButtonState();

    chatStreaming = true;
    updateSendButtonState();

    const assistantBody = appendMessage("assistant", "", null);
    if (assistantBody) {
        assistantBody.innerHTML = '<p class="chat-typing">思考中…</p>';
    }
    let assistantText = "";
    let parseQualityHtml = "";

    try {
        await ensureChatSession(userId);

        const form = new FormData();
        form.append("user_id", userId);
        form.append("message", message);
        if (chatPendingFile) form.append("file", chatPendingFile);

        const res = await fetch(
            `${API_BASE}/api/chat/sessions/${encodeURIComponent(chatSessionId)}/messages`,
            { method: "POST", body: form }
        );

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(errText || `请求失败 ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parsed = parseSseChunk(buffer);
            buffer = parsed.remainder;

            for (const evt of parsed.events) {
                if (evt.event === "skill_start") {
                    setChatProgress(`▶ ${evt.data.label || evt.data.skill}`);
                } else if (evt.event === "skill_progress") {
                    const label = evt.data.label || evt.data.stage || evt.data.skill;
                    setChatProgress(`${label}…`);
                } else if (evt.event === "safety") {
                    setChatProgress("⚠️ 安全审查");
                } else if (evt.event === "parse_quality") {
                    parseQualityHtml = renderParseQualityBadge(evt.data);
                    if (assistantBody && assistantText) {
                        updateAssistantBody(assistantBody, assistantText, parseQualityHtml);
                    }
                } else if (evt.event === "token") {
                    assistantText += evt.data.text || "";
                    if (assistantBody) {
                        updateAssistantBody(assistantBody, assistantText, parseQualityHtml);
                    }
                    scrollChatToBottom();
                } else if (evt.event === "done") {
                    assistantText = evt.data.text || assistantText;
                    if (evt.data.parse_quality) {
                        parseQualityHtml = renderParseQualityBadge(evt.data.parse_quality);
                    }
                    if (assistantBody) {
                        updateAssistantBody(assistantBody, assistantText, parseQualityHtml);
                    }
                } else if (evt.event === "error") {
                    if (!evt.data.skill) {
                        throw new Error(evt.data.message || "服务端错误");
                    }
                    setChatProgress(`⚠️ ${evt.data.skill} 部分失败，继续生成回复…`);
                }
            }
        }
        if (typeof loadSessionList === "function") loadSessionList();
    } catch (err) {
        if (assistantBody) {
            assistantBody.innerHTML = `<p class="chat-error">出错了：${escapeHtml(String(err.message || err))}</p>`;
        }
    } finally {
        chatStreaming = false;
        setChatProgress("");
        clearChatAttachment();
        updateSendButtonState();
    }
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatChatText(text) {
    return escapeHtml(text).replace(/\n/g, "<br>");
}

function renderParseQualityBadge(quality) {
    if (!quality || quality.overall_score == null) return "";
    const pct = Math.round(Number(quality.overall_score) * 100);
    const count = quality.indicator_count ?? 0;
    const cls = quality.degraded ? "parse-quality-degraded" : "parse-quality-ok";
    let html = `<div class="parse-quality-badge ${cls}">📊 解析置信度 ${pct}% · 结构化 ${count} 项指标</div>`;
    const warnings = quality.warnings || [];
    if (warnings.length) {
        html += `<div class="parse-quality-warn">${escapeHtml(warnings.slice(0, 2).join("；"))}</div>`;
    }
    return html;
}

function updateAssistantBody(assistantBody, text, parseQualityHtml) {
    if (!assistantBody) return;
    const main = `<div class="chat-markdown">${formatChatText(text)}</div>`;
    assistantBody.innerHTML = main + (parseQualityHtml || "");
}

function autoResizeTextarea(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chatForm");
    const input = document.getElementById("chatInput");
    const fileInput = document.getElementById("chatFile");

    form?.addEventListener("submit", sendChatMessage);
    fileInput?.addEventListener("change", onChatFileSelected);

    if (input) {
        input.addEventListener("input", () => {
            autoResizeTextarea(input);
            updateSendButtonState();
        });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                form?.requestSubmit();
            }
        });
    }

    updateSendButtonState();

    const userId = getUserId();
    const saved = getCurrentSessionId();
    if (saved) {
        loadChatForSession(saved).catch(() => resetChatView());
    } else {
        ensureChatSession(userId).catch(console.warn);
    }
});
