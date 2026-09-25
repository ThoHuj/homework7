(function () {
  "use strict";

  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const stopBtn = document.getElementById("stop-btn");
  const newChatBtn = document.getElementById("new-chat-btn");
  const statusDot = document.querySelector(".status-dot");

  let streaming = false;
  let abortController = null;

  if (typeof marked !== "undefined") {
    marked.setOptions({ breaks: true, gfm: true });
  }

  function scrollToBottom() {
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function setStreaming(active) {
    streaming = active;
    sendBtn.disabled = active;
    messageInput.disabled = active;
    stopBtn.disabled = !active;
    statusDot.classList.toggle("streaming", active);
    statusDot.title = active ? "Streaming" : "Ready";
  }

  function clearWelcome() {
    const welcome = chatLog.querySelector(".welcome");
    if (welcome) welcome.remove();
  }

  function createMessageElement(role, text) {
    clearWelcome();

    const msg = document.createElement("div");
    msg.className = `message ${role}`;

    const header = document.createElement("div");
    header.className = "message-header";

    const roleLabel = document.createElement("span");
    roleLabel.className = `message-role ${role}`;
    roleLabel.textContent = role === "user" ? "you" : "bot";

    header.appendChild(roleLabel);

    if (role === "assistant") {
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn btn-copy";
      copyBtn.textContent = "copy";
      copyBtn.addEventListener("click", () => copyToClipboard(text, copyBtn));
      header.appendChild(copyBtn);
    }

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (role === "user") {
      bubble.textContent = text;
    } else if (role === "error") {
      bubble.textContent = text;
    } else {
      renderMarkdown(bubble, text);
    }

    msg.appendChild(header);
    msg.appendChild(bubble);
    chatLog.appendChild(msg);
    scrollToBottom();

    return { msg, bubble, copyBtn: header.querySelector(".btn-copy") };
  }

  function renderMarkdown(el, text) {
    if (typeof marked !== "undefined") {
      el.innerHTML = marked.parse(text);
    } else {
      el.textContent = text;
    }
  }

  async function copyToClipboard(text, btn) {
    try {
      await navigator.clipboard.writeText(text);
      const original = btn.textContent;
      btn.textContent = "copied!";
      setTimeout(() => { btn.textContent = original; }, 1500);
    } catch {
      btn.textContent = "failed";
      setTimeout(() => { btn.textContent = "copy"; }, 1500);
    }
  }

  function showError(message) {
    createMessageElement("error", message);
  }

  function addStreamingCursor(bubble) {
    const cursor = document.createElement("span");
    cursor.className = "streaming-cursor";
    cursor.setAttribute("aria-hidden", "true");
    bubble.appendChild(cursor);
    return cursor;
  }

  function removeStreamingCursor(bubble) {
    const cursor = bubble.querySelector(".streaming-cursor");
    if (cursor) cursor.remove();
  }

  function parseSSELine(line) {
    if (!line.startsWith("data: ")) return null;
    return line.slice(6);
  }

  async function consumeSSEStream(response, onToken) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        if (!line) continue;

        const data = parseSSELine(line);
        if (data === null) continue;

        if (data === "[DONE]") return;

        if (data.startsWith("[ERROR]")) {
          throw new Error(data.slice(7).trim() || "An error occurred.");
        }

        onToken(data);
      }
    }

    if (buffer.trim()) {
      const data = parseSSELine(buffer.trim());
      if (data && data !== "[DONE]" && !data.startsWith("[ERROR]")) {
        onToken(data);
      }
    }
  }

  async function sendMessage(text) {
    createMessageElement("user", text);

    const { bubble, copyBtn } = createMessageElement("assistant", "");
    let content = "";
    const cursor = addStreamingCursor(bubble);

    abortController = new AbortController();
    setStreaming(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: text }),
        signal: abortController.signal,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => "");
        throw new Error(errText || `Request failed (${response.status})`);
      }

      await consumeSSEStream(response, (token) => {
        content += token;
        removeStreamingCursor(bubble);
        renderMarkdown(bubble, content);
        addStreamingCursor(bubble);
        scrollToBottom();
      });
    } catch (err) {
      if (err.name === "AbortError") {
        if (content) {
          removeStreamingCursor(bubble);
          renderMarkdown(bubble, content + "\n\n*[stopped]*");
        } else {
          bubble.closest(".message").remove();
        }
        return;
      }

      bubble.closest(".message").remove();
      showError(err.message || "Something went wrong. Please try again.");
    } finally {
      removeStreamingCursor(bubble);
      if (copyBtn) {
        copyBtn.onclick = () => copyToClipboard(content, copyBtn);
      }
      abortController = null;
      setStreaming(false);
      messageInput.focus();
    }
  }

  async function stopStreaming() {
    if (!streaming) return;

    abortController?.abort();

    try {
      await fetch("/api/chat/stop", {
        method: "POST",
        credentials: "include",
      });
    } catch {
      /* server-side stop is best-effort */
    }
  }

  async function newChat() {
    if (streaming) await stopStreaming();

    try {
      await fetch("/api/chat/new", {
        method: "POST",
        credentials: "include",
      });
    } catch {
      showError("Could not start a new chat.");
      return;
    }

    chatLog.innerHTML =
      '<div class="welcome"><p><span class="prompt">&gt;</span> session initialized — ask anything.</p></div>';
    messageInput.focus();
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || streaming) return;
    messageInput.value = "";
    sendMessage(text);
  });

  stopBtn.addEventListener("click", stopStreaming);
  newChatBtn.addEventListener("click", newChat);

  messageInput.focus();
})();
