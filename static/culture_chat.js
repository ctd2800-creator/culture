/* Culture chat UI — sync API + optional SSE stream */
window.CultureChat = {
  init(opts) {
    const STREAM_URL = "/api/chat/stream";
    const CHAT_URL = "/api/chat";
    const history = opts.history || [];

    const chatBox = document.getElementById("chatBox");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const statusLine = document.getElementById("statusLine");
    const chatNotice = document.getElementById("chatNotice");

    if (!chatBox || !messageInput || !sendBtn) {
      console.error("CultureChat: DOM elements missing");
      return;
    }

    function clearHint() {
      const hint = chatBox.querySelector("[data-chat-hint]");
      if (hint) hint.remove();
    }

    function scrollChatToBottom() {
      requestAnimationFrame(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
      });
    }

    function appendMsg(role, content, streaming) {
      clearHint();
      const el = document.createElement("div");
      el.className = "msg " + role + (streaming ? " streaming" : "");
      el.textContent = content;
      chatBox.appendChild(el);
      scrollChatToBottom();
      return el;
    }

    function renderHistory(items) {
      chatBox.innerHTML = "";
      if (!items.length) {
        const hint = document.createElement("p");
        hint.className = "chat-hint";
        hint.dataset.chatHint = "1";
        hint.textContent =
          "메시지를 입력하거나, 위 예시처럼 월별 데이터 요약을 요청하세요.";
        chatBox.appendChild(hint);
        return;
      }
      items.forEach((item) => appendMsg(item.role, item.content || "", false));
    }

    function processSsePart(part, state) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let payload;
        try {
          payload = JSON.parse(line.slice(6));
        } catch (_) {
          continue;
        }
        if (payload.type === "status") {
          statusLine.textContent = payload.text || "";
        } else if (payload.type === "chunk") {
          state.full += payload.text || "";
          state.assistantEl.textContent = state.full;
          scrollChatToBottom();
        } else if (payload.type === "error") {
          throw new Error(payload.text || "오류");
        } else if (payload.type === "done") {
          if (payload.text) state.full = payload.text;
          state.assistantEl.textContent = state.full;
          if (payload.notice) {
            chatNotice.textContent = payload.notice;
            chatNotice.style.display = "block";
          }
        }
      }
    }

    async function sendViaStream(text, assistantEl, state) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 15000);
      const res = await fetch(STREAM_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) {
        const errText = await res.text();
        throw new Error("스트리밍 실패 (" + res.status + "): " + errText.slice(0, 120));
      }
      if (!res.body || !res.body.getReader) {
        throw new Error("스트리밍 미지원");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          if (part.trim()) processSsePart(part, state);
        }
      }
      if (buffer.trim()) processSsePart(buffer, state);
    }

    async function sendViaJson(text, assistantEl, state) {
      statusLine.textContent = "응답 생성 중… (Bedrock 호출, 10~60초)";
      const res = await fetch(CHAT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || "요청 실패 (" + res.status + ")");
      }
      state.full = data.reply || "";
      assistantEl.textContent = state.full;
      if (data.notice) {
        chatNotice.textContent = data.notice;
        chatNotice.style.display = "block";
      }
    }

    async function sendMessage() {
      const text = messageInput.value.trim();
      if (!text || sendBtn.disabled) return;

      messageInput.value = "";
      sendBtn.disabled = true;
      statusLine.textContent = "요청 전송 중…";
      chatNotice.style.display = "none";

      appendMsg("user", text, false);
      const assistantEl = appendMsg("assistant", "…", true);
      const state = { full: "", assistantEl };

      try {
        const useStream = opts.preferStream !== false;
        if (useStream) {
          try {
            statusLine.textContent = "스트리밍 연결 중…";
            await sendViaStream(text, assistantEl, state);
          } catch (streamErr) {
            console.warn("stream fallback:", streamErr);
            assistantEl.textContent = "…";
            await sendViaJson(text, assistantEl, state);
          }
        } else {
          await sendViaJson(text, assistantEl, state);
        }

        if (!state.full.trim()) {
          assistantEl.textContent = "(응답 본문이 비어 있습니다.)";
        }
        assistantEl.classList.remove("streaming");
        statusLine.textContent = "";
      } catch (err) {
        assistantEl.classList.remove("streaming");
        assistantEl.textContent = "(처리 실패: " + err.message + ")";
        statusLine.textContent = "";
        console.error(err);
      } finally {
        sendBtn.disabled = false;
        messageInput.focus();
      }
    }

    window.cultureSend = sendMessage;
    renderHistory(history);
    sendBtn.addEventListener("click", sendMessage);
    messageInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    messageInput.addEventListener("input", () => {
      messageInput.style.height = "auto";
      messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + "px";
    });

    if (window.visualViewport) {
      const onViewport = () => {
        const vv = window.visualViewport;
        const gap = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
        document.querySelector(".composer")?.style.setProperty(
          "padding-bottom",
          `max(${gap}px, env(safe-area-inset-bottom, 0px))`
        );
        if (document.activeElement === messageInput) {
          scrollChatToBottom();
        }
      };
      window.visualViewport.addEventListener("resize", onViewport);
      window.visualViewport.addEventListener("scroll", onViewport);
    }
  },
};
