/**
 * Support Chat Widget — drop-in embeddable chat powered by Claude + RAG.
 *
 * Usage:
 *   <script>
 *     window.SupportChatConfig = {
 *       apiUrl:       "https://your-backend.example.com",  // required
 *       botName:      "Support Assistant",                  // optional
 *       primaryColor: "#6366f1",                            // optional
 *       greeting:     "Hi! How can I help you today?",     // optional
 *       position:     "right",                              // "right" | "left"
 *     };
 *   </script>
 *   <script src="chat-widget.js" defer></script>
 */

(function () {
  "use strict";

  // ── Config ────────────────────────────────────────────────────────────────────

  const cfg = Object.assign(
    {
      apiUrl: "",
      botName: "Support Assistant",
      primaryColor: "#6366f1",
      greeting: "Hi there! How can I help you today?",
      position: "right",
    },
    window.SupportChatConfig || {}
  );

  if (!cfg.apiUrl) {
    console.warn("[SupportChat] window.SupportChatConfig.apiUrl is required.");
    return;
  }

  // Strip trailing slash
  cfg.apiUrl = cfg.apiUrl.replace(/\/$/, "");

  // ── State ─────────────────────────────────────────────────────────────────────

  let isOpen = false;
  let isStreaming = false;
  let conversationHistory = [];

  // ── Styles ────────────────────────────────────────────────────────────────────

  const STYLES = `
    #sc-launcher {
      position: fixed;
      bottom: 24px;
      ${cfg.position}: 24px;
      z-index: 9999;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: ${cfg.primaryColor};
      border: none;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,0.22);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
      outline: none;
    }
    #sc-launcher:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 20px rgba(0,0,0,0.28);
    }
    #sc-launcher svg { pointer-events: none; }

    #sc-panel {
      position: fixed;
      bottom: 92px;
      ${cfg.position}: 24px;
      z-index: 9998;
      width: 360px;
      max-width: calc(100vw - 32px);
      height: 540px;
      max-height: calc(100vh - 120px);
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transform-origin: bottom ${cfg.position};
      transition: transform 0.2s ease, opacity 0.2s ease;
    }
    #sc-panel.sc-hidden {
      transform: scale(0.92) translateY(8px);
      opacity: 0;
      pointer-events: none;
    }

    /* Header */
    #sc-header {
      background: ${cfg.primaryColor};
      color: #fff;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }
    #sc-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: rgba(255,255,255,0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      flex-shrink: 0;
    }
    #sc-header-text { flex: 1; min-width: 0; }
    #sc-bot-name {
      font-weight: 600;
      font-size: 15px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    #sc-status { font-size: 12px; opacity: 0.85; }
    #sc-close-btn {
      background: none;
      border: none;
      color: #fff;
      cursor: pointer;
      padding: 4px;
      border-radius: 6px;
      opacity: 0.8;
      display: flex;
      align-items: center;
    }
    #sc-close-btn:hover { opacity: 1; background: rgba(255,255,255,0.15); }

    /* Messages */
    #sc-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }
    .sc-msg {
      display: flex;
      gap: 8px;
      max-width: 85%;
    }
    .sc-msg.user { align-self: flex-end; flex-direction: row-reverse; }
    .sc-msg.bot  { align-self: flex-start; }
    .sc-bubble {
      padding: 10px 13px;
      border-radius: 14px;
      font-size: 14px;
      line-height: 1.5;
      word-break: break-word;
      white-space: pre-wrap;
    }
    .sc-msg.user .sc-bubble {
      background: ${cfg.primaryColor};
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .sc-msg.bot .sc-bubble {
      background: #f3f4f6;
      color: #111827;
      border-bottom-left-radius: 4px;
    }
    .sc-msg.bot .sc-bubble.sc-error {
      background: #fee2e2;
      color: #b91c1c;
    }

    /* Typing indicator */
    .sc-typing { display: flex; align-items: center; gap: 4px; padding: 4px 2px; }
    .sc-typing span {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #9ca3af;
      animation: sc-bounce 1.2s infinite;
    }
    .sc-typing span:nth-child(2) { animation-delay: 0.2s; }
    .sc-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes sc-bounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-5px); }
    }

    /* Footer */
    #sc-footer {
      padding: 12px 14px;
      border-top: 1px solid #e5e7eb;
      display: flex;
      gap: 8px;
      align-items: flex-end;
      flex-shrink: 0;
    }
    #sc-input {
      flex: 1;
      resize: none;
      border: 1.5px solid #d1d5db;
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 14px;
      font-family: inherit;
      line-height: 1.4;
      max-height: 120px;
      overflow-y: auto;
      outline: none;
      transition: border-color 0.15s;
    }
    #sc-input:focus { border-color: ${cfg.primaryColor}; }
    #sc-input::placeholder { color: #9ca3af; }
    #sc-send-btn {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      border: none;
      background: ${cfg.primaryColor};
      color: #fff;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: opacity 0.15s;
    }
    #sc-send-btn:disabled { opacity: 0.45; cursor: not-allowed; }
    #sc-send-btn:not(:disabled):hover { opacity: 0.88; }

    /* Scrollbar */
    #sc-messages::-webkit-scrollbar { width: 4px; }
    #sc-messages::-webkit-scrollbar-track { background: transparent; }
    #sc-messages::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }
  `;

  // ── SVG icons ─────────────────────────────────────────────────────────────────

  const ICON_CHAT = `<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  const ICON_CLOSE = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  const ICON_SEND = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;

  // ── DOM Construction ──────────────────────────────────────────────────────────

  function injectStyles() {
    const style = document.createElement("style");
    style.textContent = STYLES;
    document.head.appendChild(style);
  }

  function buildWidget() {
    // Launcher button
    const launcher = document.createElement("button");
    launcher.id = "sc-launcher";
    launcher.setAttribute("aria-label", "Open support chat");
    launcher.innerHTML = ICON_CHAT;
    launcher.addEventListener("click", togglePanel);

    // Panel
    const panel = document.createElement("div");
    panel.id = "sc-panel";
    panel.classList.add("sc-hidden");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", cfg.botName);

    // Header
    const header = document.createElement("div");
    header.id = "sc-header";
    header.innerHTML = `
      <div id="sc-avatar">🤖</div>
      <div id="sc-header-text">
        <div id="sc-bot-name">${escHtml(cfg.botName)}</div>
        <div id="sc-status">Online</div>
      </div>
      <button id="sc-close-btn" aria-label="Close chat">${ICON_CLOSE}</button>
    `;
    header.querySelector("#sc-close-btn").addEventListener("click", closePanel);

    // Messages
    const messages = document.createElement("div");
    messages.id = "sc-messages";
    messages.setAttribute("role", "log");
    messages.setAttribute("aria-live", "polite");

    // Footer
    const footer = document.createElement("div");
    footer.id = "sc-footer";

    const input = document.createElement("textarea");
    input.id = "sc-input";
    input.placeholder = "Type a message…";
    input.rows = 1;
    input.setAttribute("aria-label", "Message input");

    const sendBtn = document.createElement("button");
    sendBtn.id = "sc-send-btn";
    sendBtn.innerHTML = ICON_SEND;
    sendBtn.setAttribute("aria-label", "Send message");
    sendBtn.addEventListener("click", sendMessage);

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
    });

    footer.appendChild(input);
    footer.appendChild(sendBtn);

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(footer);

    document.body.appendChild(launcher);
    document.body.appendChild(panel);

    // Show greeting
    appendBotMessage(cfg.greeting);
  }

  // ── UI Helpers ────────────────────────────────────────────────────────────────

  function escHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function togglePanel() {
    isOpen ? closePanel() : openPanel();
  }

  function openPanel() {
    isOpen = true;
    document.getElementById("sc-panel").classList.remove("sc-hidden");
    document.getElementById("sc-launcher").setAttribute("aria-label", "Close support chat");
    document.getElementById("sc-input").focus();
  }

  function closePanel() {
    isOpen = false;
    document.getElementById("sc-panel").classList.add("sc-hidden");
    document.getElementById("sc-launcher").setAttribute("aria-label", "Open support chat");
  }

  function scrollToBottom() {
    const msgs = document.getElementById("sc-messages");
    msgs.scrollTop = msgs.scrollHeight;
  }

  function appendUserMessage(text) {
    const msgs = document.getElementById("sc-messages");
    const row = document.createElement("div");
    row.className = "sc-msg user";
    row.innerHTML = `<div class="sc-bubble">${escHtml(text)}</div>`;
    msgs.appendChild(row);
    scrollToBottom();
  }

  function appendBotMessage(text, isError = false) {
    const msgs = document.getElementById("sc-messages");
    const row = document.createElement("div");
    row.className = "sc-msg bot";
    const bubble = document.createElement("div");
    bubble.className = "sc-bubble" + (isError ? " sc-error" : "");
    bubble.textContent = text;
    row.appendChild(bubble);
    msgs.appendChild(row);
    scrollToBottom();
    return bubble;
  }

  function appendTypingIndicator() {
    const msgs = document.getElementById("sc-messages");
    const row = document.createElement("div");
    row.className = "sc-msg bot";
    row.id = "sc-typing-row";
    row.innerHTML = `<div class="sc-bubble"><div class="sc-typing"><span></span><span></span><span></span></div></div>`;
    msgs.appendChild(row);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const el = document.getElementById("sc-typing-row");
    if (el) el.remove();
  }

  function setStreaming(active) {
    isStreaming = active;
    const btn = document.getElementById("sc-send-btn");
    const input = document.getElementById("sc-input");
    if (btn) btn.disabled = active;
    if (input) input.disabled = active;
  }

  // ── Chat Logic ────────────────────────────────────────────────────────────────

  async function sendMessage() {
    if (isStreaming) return;

    const input = document.getElementById("sc-input");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    appendUserMessage(text);

    // Snapshot history before adding this turn (API expects prior history only)
    const historySnapshot = [...conversationHistory];

    setStreaming(true);
    appendTypingIndicator();

    try {
      const response = await fetch(`${cfg.apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_history: historySnapshot,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server error ${response.status}`);
      }

      removeTypingIndicator();

      let botText = "";
      const bubble = appendBotMessage("");

      // Parse SSE stream manually (EventSource doesn't support POST)
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          if (event.type === "text") {
            botText += event.content;
            bubble.textContent = botText;
            scrollToBottom();
          } else if (event.type === "done") {
            break;
          } else if (event.type === "error") {
            bubble.classList.add("sc-error");
            bubble.textContent = "Sorry, something went wrong. Please try again.";
          }
        }
      }

      // Commit this turn to history
      if (botText) {
        conversationHistory.push({ role: "user", content: text });
        conversationHistory.push({ role: "assistant", content: botText });
        // Keep only the last 20 messages (10 turns) to avoid huge payloads
        if (conversationHistory.length > 20) {
          conversationHistory = conversationHistory.slice(-20);
        }
      }
    } catch (err) {
      removeTypingIndicator();
      appendBotMessage("Sorry, I couldn't reach the server. Please try again.", true);
      console.error("[SupportChat]", err);
    } finally {
      setStreaming(false);
      document.getElementById("sc-input")?.focus();
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────────

  function init() {
    injectStyles();
    buildWidget();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
