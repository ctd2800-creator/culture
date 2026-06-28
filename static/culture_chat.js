/* Culture chat UI — sync API + optional SSE stream + summary bar charts */
window.CultureChat = {
  init(opts) {
    const STREAM_URL = "/api/chat/stream";
    const CHAT_URL = "/api/chat";
    const history = opts.history || [];
    let chartUid = 0;

    const chatBox = document.getElementById("chatBox");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const statusLine = document.getElementById("statusLine");
    const chatNotice = document.getElementById("chatNotice");
    let pendingChartReady = !!opts.hasPendingChart;
    // 현재 집계 결과에 대해 사용자가 생성한 차트 유형(순서·중복 제거).
    // 분석 에이전트 요청 시 서버로 전달해 세션 유실과 무관하게 모든 차트를 재생성.
    let generatedChartTypes = [];
    let liveChatHistory = (opts.history || []).map((item) => ({
      role: item.role,
      content: item.content || "",
      charts: [...(item.charts || [])],
      inst1_data: item.inst1_data || {},
      inst1_column_orders: item.inst1_column_orders || {},
      inst1_result_labels: item.inst1_result_labels || {},
      inst1_queries: item.inst1_queries || {},
      report_export: item.report_export || null,
    }));

    function snapshotAssistantMessage(payload, textFallback) {
      return {
        role: "assistant",
        content: payload.reply || payload.text || textFallback || "",
        charts: [...(payload.charts || [])],
        inst1_data: payload.inst1_data || {},
        inst1_column_orders: payload.inst1_column_orders || {},
        inst1_result_labels: payload.inst1_result_labels || {},
        inst1_queries: payload.inst1_queries || {},
        report_export: payload.report_export || null,
      };
    }

    function appendChartsToLastAssistant(charts) {
      if (!charts || !charts.length) return;
      for (let i = liveChatHistory.length - 1; i >= 0; i--) {
        if (liveChatHistory[i].role === "assistant") {
          liveChatHistory[i].charts = [
            ...(liveChatHistory[i].charts || []),
            ...charts,
          ];
          break;
        }
      }
    }

    const ANALYSIS_REQUEST_HINTS = [
      "외부요인",
      "외부 요인",
      "외부정보",
      "외부 정보",
      "시장 동향",
      "시장동향",
      "경제 동향",
      "정책 동향",
      "결합해 분석",
      "결합하여 분석",
      "결합 분석",
      "인사이트",
      "외부요인과 결합",
    ];
    const CHART_REQUEST_HINTS = ["차트", "그래프", "막대", "시각화", "그려", "chart"];
    const ANALYSIS_FOLLOW_UP = "결과를 외부요인과 결합해 분석해줘";
    const CHART_FOLLOW_UP = "조회한 집계 데이터로 차트를 그려드릴까요?";

    function isAnalysisRequest(text) {
      const m = (text || "").trim();
      if (!m) return false;
      if (m === ANALYSIS_FOLLOW_UP) return true;
      if (ANALYSIS_REQUEST_HINTS.some((h) => m.includes(h))) return true;
      if (/결합.{0,12}분석/.test(m)) return true;
      if (/외부.{0,8}(요인|정보).{0,12}분석/.test(m)) return true;
      return false;
    }

    function isChartRequest(text) {
      const m = (text || "").trim();
      if (!m) return false;
      if (m === CHART_FOLLOW_UP) return true;
      const lower = m.toLowerCase();
      return CHART_REQUEST_HINTS.some((h) => lower.includes(h.toLowerCase()));
    }

    function initialGeneratingStatus(text) {
      if (pendingChartReady && isAnalysisRequest(text)) {
        return (
          "[호출 에이전트: 분석 에이전트]\n" +
          "직전 집계 결과를 바탕으로 외부요인과 결합해 분석하고 있습니다."
        );
      }
      if (pendingChartReady && isChartRequest(text)) {
        return (
          "[호출 에이전트: 차트 에이전트]\n" +
          "집계 결과 차트를 준비하고 있습니다."
        );
      }
      return "답변을 준비하고 있습니다…";
    }

    function syncPendingChartReady(data) {
      if (typeof data?.pending_chart_ready === "boolean") {
        pendingChartReady = data.pending_chart_ready;
        return;
      }
      const inst1 = data?.inst1_data;
      if (!inst1 || typeof inst1 !== "object") return;
      for (const key of Object.keys(inst1)) {
        const block = inst1[key];
        if (block && Array.isArray(block.rows) && block.rows.length) {
          pendingChartReady = true;
          return;
        }
      }
    }

    if (!chatBox || !messageInput || !sendBtn) {
      console.error("CultureChat: DOM elements missing");
      return;
    }

    function fillMessageInput(text) {
      messageInput.value = (text || "").trim();
      messageInput.dispatchEvent(new Event("input"));
      messageInput.focus();
    }

    function appendToMessageInput(part) {
      const token = (part || "").trim();
      if (!token) return;
      const current = messageInput.value.trim();
      if (!current) {
        messageInput.value = token;
      } else {
        const parts = current
          .split(/[,，、]/)
          .map((s) => s.trim())
          .filter(Boolean);
        if (parts.includes(token)) {
          messageInput.focus();
          return;
        }
        messageInput.value = parts.join(", ") + ", " + token;
      }
      messageInput.dispatchEvent(new Event("input"));
      messageInput.focus();
    }

    function renderClickableList(container, label, items, onPick) {
      if (!items || !items.length) return;
      const block = document.createElement("div");
      block.className = "msg-follow-up";
      const labelEl = document.createElement("p");
      labelEl.className = "follow-up-label";
      labelEl.textContent = label;
      block.appendChild(labelEl);
      items.forEach((item) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "follow-up-chip";
        btn.textContent = item;
        btn.addEventListener("click", () => onPick(item));
        block.appendChild(btn);
      });
      container.appendChild(block);
      scrollChatToBottom();
    }

    function renderFollowUpQuestions(container, questions) {
      renderClickableList(container, "추천 질문", questions, fillMessageInput);
    }

    function appendMeasureToMessageInput(part) {
      const token = (part || "").trim();
      if (!token) return;
      if (token === "고객수") {
        fillMessageInput("고객수");
        return;
      }
      const current = messageInput.value.trim();
      const parts = current
        ? current
            .split(/[,，、]/)
            .map((s) => s.trim())
            .filter(Boolean)
            .filter((s) => s !== "고객수")
        : [];
      if (parts.includes(token)) {
        messageInput.focus();
        return;
      }
      parts.push(token);
      messageInput.value = parts.join(", ");
      messageInput.dispatchEvent(new Event("input"));
      messageInput.focus();
    }

    function renderSchemaPipelineNotice(container, text) {
      if (!text || !String(text).trim()) return;
      if (container.querySelector(".schema-pipeline-notice")) return;
      const el = document.createElement("div");
      el.className = "schema-pipeline-notice";
      el.textContent = String(text).trim();
      const textEl = container.querySelector(".msg-text");
      if (textEl) {
        container.insertBefore(el, textEl);
      } else {
        container.appendChild(el);
      }
    }

    function renderAggregateColumnOptions(container, columns, label, pickMode) {
      let onPick = appendToMessageInput;
      if (pickMode === "replace") {
        onPick = fillMessageInput;
      } else if (pickMode === "measure") {
        onPick = appendMeasureToMessageInput;
      }
      renderClickableList(
        container,
        label || "집계 가능 컬럼 예:",
        columns,
        onPick
      );
    }

    function extractFollowUpQuestions(content) {
      if (!content) return [];
      const marker = "추천 질문";
      const idx = content.indexOf(marker);
      if (idx < 0) return [];
      return content
        .slice(idx + marker.length)
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.startsWith("- "))
        .map((line) => line.slice(2).trim())
        .filter(Boolean);
    }

    function stripFollowUpSection(content) {
      const markers = ["\n추천 질문\n", "\n\n추천 질문\n"];
      for (const marker of markers) {
        const idx = content.indexOf(marker);
        if (idx >= 0) return content.slice(0, idx).trimEnd();
      }
      return content;
    }

    function resolveFollowUpQuestions(content, followUpQuestions) {
      const questions = (followUpQuestions || []).filter(Boolean);
      if (questions.length) {
        return { displayContent: content, questions };
      }
      const legacy = extractFollowUpQuestions(content);
      if (!legacy.length) {
        return { displayContent: content, questions: [] };
      }
      return {
        displayContent: stripFollowUpSection(content),
        questions: legacy,
      };
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

    const FALLBACK_STATUS_MESSAGES = [
      "답변을 준비하고 있습니다…",
      "데이터를 조회·분석하고 있습니다…",
      "결과를 정리하고 있습니다…",
    ];

    function createTypingController(textEl) {
      let intervalId = null;

      function stop() {
        if (intervalId !== null) {
          clearInterval(intervalId);
          intervalId = null;
        }
      }

      function typeText(text) {
        stop();
        const target = text || "";
        let pos = 0;
        textEl.textContent = "";
        scrollChatToBottom();
        if (!target) return;

        intervalId = setInterval(() => {
          pos += 1;
          textEl.textContent = target.slice(0, pos);
          scrollChatToBottom();
          if (pos >= target.length) stop();
        }, 30);
      }

      return { typeText, stop };
    }

    function formatStatusMessage(payload) {
      if (payload && payload.text) return payload.text;
      const agent = (payload && payload.agent) || "";
      const desc = (payload && payload.description) || "";
      if (agent && desc) return `[호출 에이전트: ${agent}]\n${desc}`;
      return "답변을 생성하고 있습니다…";
    }

    function showGeneratingStatus(state, payloadOrText) {
      if (!state || !state.typing) return;
      const text =
        typeof payloadOrText === "string"
          ? payloadOrText
          : formatStatusMessage(payloadOrText);
      state.el.classList.add("generating");
      state.typing.typeText(text);
    }

    function finishGenerating(state) {
      if (!state || !state.typing) return;
      state.typing.stop();
      state.el.classList.remove("generating");
    }

    function messageTailAnchor(container) {
      return (
        container.querySelector("[data-chart-type-picker]") ||
        container.querySelector(".msg-follow-up:not(.msg-chart-type-picker)")
      );
    }

    function appendBeforeMessageTail(container, node) {
      const anchor = messageTailAnchor(container);
      if (anchor) container.insertBefore(node, anchor);
      else container.appendChild(node);
    }

    function sanitizeChartFilename(title) {
      const raw = String(title || "culture_chart").trim();
      const safe = raw.replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").slice(0, 80);
      const base = safe || "culture_chart";
      return base.toLowerCase().endsWith(".png") ? base : base + ".png";
    }

    function downloadChartImage(chartInstance, canvas, title) {
      let dataUrl = "";
      try {
        if (chartInstance && typeof chartInstance.toBase64Image === "function") {
          dataUrl = chartInstance.toBase64Image("image/png", 1);
        }
      } catch (_) {
        /* fallback below */
      }
      if (!dataUrl && canvas) {
        dataUrl = canvas.toDataURL("image/png");
      }
      if (!dataUrl) {
        throw new Error("차트 이미지를 생성할 수 없습니다.");
      }
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = sanitizeChartFilename(title);
      document.body.appendChild(a);
      a.click();
      a.remove();
    }

    function renderCharts(container, charts, options) {
      if (!charts || !charts.length || typeof Chart === "undefined") return;
      const opts = options || {};
      charts.forEach((spec) => {
        const chartType = spec.type || "bar";
        const isRadial = chartType === "pie" || chartType === "doughnut";
        const titleText = spec.title || "차트";
        const block = document.createElement("div");
        block.className = "chart-block";
        if (!opts.hideTitle) {
          const title = document.createElement("p");
          title.className = "chart-title";
          title.textContent = titleText;
          block.appendChild(title);
        }
        const wrap = document.createElement("div");
        wrap.className = "chart-canvas-wrap";
        const canvas = document.createElement("canvas");
        const canvasId = "culture-chart-" + ++chartUid;
        canvas.id = canvasId;
        wrap.appendChild(canvas);
        block.appendChild(wrap);
        let saveBtn = null;
        if (!opts.hideSave) {
          const actions = document.createElement("div");
          actions.className = "chart-block-actions";
          saveBtn = document.createElement("button");
          saveBtn.type = "button";
          saveBtn.className = "btn-chart-image-save";
          saveBtn.textContent = "이미지 저장";
          actions.appendChild(saveBtn);
          block.appendChild(actions);
        }
        appendBeforeMessageTail(container, block);
        const datasets = spec.datasets || [];
        const measureName = isRadial && datasets.length ? datasets[0].label : "";
        const chartInstance = new Chart(canvas, {
          type: chartType,
          data: {
            labels: spec.labels || [],
            datasets: datasets,
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: isRadial || datasets.length > 1 },
              title: isRadial && measureName
                ? { display: true, text: measureName, font: { size: 14 } }
                : { display: false },
            },
            ...(isRadial ? {} : { scales: { y: { beginAtZero: true } } }),
          },
        });
        if (saveBtn) {
          saveBtn.addEventListener("click", () => {
            const prev = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = "저장 중…";
            try {
              downloadChartImage(chartInstance, canvas, titleText);
            } catch (err) {
              alert(err.message || String(err));
            } finally {
              saveBtn.disabled = false;
              saveBtn.textContent = prev;
            }
          });
        }
      });
      scrollChatToBottom();
    }

    function renderChartTypePicker(container, options) {
      if (!options || !options.length || container.querySelector("[data-chart-type-picker]")) {
        return;
      }
      // 새 집계 결과의 차트 유형 선택지가 나타나면 생성 이력 초기화.
      generatedChartTypes = [];
      const block = document.createElement("div");
      block.className = "msg-follow-up msg-chart-type-picker";
      block.dataset.chartTypePicker = "1";
      const labelEl = document.createElement("p");
      labelEl.className = "follow-up-label";
      labelEl.textContent = "차트 유형 선택";
      block.appendChild(labelEl);
      options.forEach((opt) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "follow-up-chip chart-type-chip";
        btn.textContent = opt.label || opt.id || "차트";
        btn.addEventListener("click", () => selectChartType(container, opt.id, btn, block));
        block.appendChild(btn);
      });
      container.appendChild(block);
      scrollChatToBottom();
    }

    async function selectChartType(container, chartType, btn, block) {
      const buttons = block?.querySelectorAll("button") || [];
      buttons.forEach((b) => {
        b.disabled = true;
      });
      const prev = btn?.textContent;
      if (btn) btn.textContent = "생성 중…";
      try {
        const res = await fetch("/api/generate/chart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ chart_type: chartType }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "차트 생성 실패 (" + res.status + ")");
        }
        if (data.charts && data.charts.length) {
          renderCharts(container, data.charts);
          appendChartsToLastAssistant(data.charts);
        }
        if (generatedChartTypes.indexOf(chartType) === -1) {
          generatedChartTypes.push(chartType);
        }
        buttons.forEach((b) => {
          b.disabled = false;
        });
        if (btn) btn.textContent = prev;
      } catch (err) {
        if (btn) btn.textContent = prev;
        buttons.forEach((b) => {
          b.disabled = false;
        });
        alert(err.message || String(err));
      }
    }

    const inst1Tables = Array.isArray(opts.inst1Tables) ? opts.inst1Tables : [];
    const INST1_TABLE_LABELS = {
      TSHDE0ZCD: "그룹고객분석인스턴스목록",
    };
    const INST1_DATA_TABLE_ORDER = [];
    inst1Tables.forEach((item) => {
      if (!item || !item.table) return;
      if (item.korean) INST1_TABLE_LABELS[item.table] = item.korean;
      if (item.table !== "TSHDE0ZCD") INST1_DATA_TABLE_ORDER.push(item.table);
    });
    if (!INST1_DATA_TABLE_ORDER.length) {
      INST1_DATA_TABLE_ORDER.push("TSHDEOA01", "TSHDEOA02", "TSHDEOA03", "TSHDEOA04", "TSHDEOA05", "TSHDEOA06");
      INST1_TABLE_LABELS.TSHDEOA01 = "그룹고객기본정보";
      INST1_TABLE_LABELS.TSHDEOA02 = "그룹고객거래기본";
      INST1_TABLE_LABELS.TSHDEOA03 = "그룹고객연락처정보";
      INST1_TABLE_LABELS.TSHDEOA04 = "그룹고객소득대출정보";
      INST1_TABLE_LABELS.TSHDEOA05 = "그룹계열사마케팅정보";
      INST1_TABLE_LABELS.TSHDEOA06 = "그룹신용등급정보";
    }

    function inst1ResultLabel(key, labels) {
      if (labels && labels[key]) return labels[key];
      if (INST1_TABLE_LABELS[key]) return INST1_TABLE_LABELS[key] + "(" + key + ")";
      if (key.startsWith("JOIN_")) {
        const tables = INST1_DATA_TABLE_ORDER.filter((t) => key.includes(t));
        if (tables.length) {
          const ko = tables.map((t) => INST1_TABLE_LABELS[t] || t).join("·");
          return ko + "(" + tables.join("·") + ")";
        }
      }
      for (const t of INST1_DATA_TABLE_ORDER) {
        if (key.startsWith(t + "_")) return (INST1_TABLE_LABELS[t] || t) + "(" + t + ")";
      }
      return key;
    }

    function renderInst1Sql(container, tableName, sql, displayName) {
      if (!sql) return;
      const block = document.createElement("div");
      block.className = "inst1-sql-block";
      const label = document.createElement("p");
      label.className = "inst1-sql-label";
      label.textContent = displayName + " — 생성된 SQL";
      block.appendChild(label);
      const pre = document.createElement("pre");
      pre.className = "inst1-sql";
      pre.textContent = sql;
      block.appendChild(pre);
      container.appendChild(block);
    }

    const CUSTOMER_ID_COLUMN = "그룹고객식별자";

    function maskCustomerId(value) {
      if (value === null || value === undefined) return "";
      const s = String(value).trim();
      if (!s) return "";
      if (s.length <= 2) return "*".repeat(s.length);
      if (s.length <= 4) return s[0] + "*".repeat(s.length - 2) + s[s.length - 1];
      return s.slice(0, 2) + "*".repeat(s.length - 3) + s[s.length - 1];
    }

    function isCustomerIdColumn(column) {
      const col = String(column || "").trim();
      return col === CUSTOMER_ID_COLUMN || col.endsWith("고객식별자");
    }

    function isCodeLikeColumn(column) {
      const col = String(column || "").trim();
      if (!col || isCustomerIdColumn(col)) return true;
      if (col === "기준년월" || col === "그룹회사코드") return true;
      if (col.includes("년월일")) return true;
      if (col.endsWith("코드") || col.endsWith("구분") || col.endsWith("여부") || col.endsWith("등급")) {
        return true;
      }
      return false;
    }

    function isNumericCellValue(value) {
      if (value === null || value === undefined || value === "") return false;
      if (typeof value === "number") return Number.isFinite(value);
      const s = String(value).trim();
      return /^-?\d+(\.\d+)?$/.test(s);
    }

    function formatNumericDisplay(value) {
      const n = typeof value === "number" ? value : Number(String(value).trim());
      if (!Number.isFinite(n)) return null;
      if (Number.isInteger(n)) {
        return n.toLocaleString("ko-KR");
      }
      return n.toLocaleString("ko-KR", { maximumFractionDigits: 4 });
    }

    function displayCellValue(column, value) {
      if (isCustomerIdColumn(column)) return maskCustomerId(value);
      if (column === "전월대비증감") {
        if (value === null || value === undefined || value === "") return "-";
        if (isNumericCellValue(value)) {
          const num = Number(value);
          const formatted = formatNumericDisplay(Math.abs(num));
          const body = formatted !== null ? formatted : String(Math.abs(num));
          if (num > 0) return "▲ " + body;
          if (num < 0) return "▼ " + body;
          return "0";
        }
      }
      if (!isCodeLikeColumn(column) && isNumericCellValue(value)) {
        const formatted = formatNumericDisplay(value);
        if (formatted !== null) return formatted;
      }
      return value === null || value === undefined ? "" : String(value);
    }

    function orderInst1Columns(rows, preferred) {
      const cols =
        preferred && preferred.length
          ? preferred.filter((c) => rows.length && c in rows[0])
          : rows.length
            ? Object.keys(rows[0])
            : [];
      const trailing = ["고객수", "전월대비증감"].filter((c) => cols.includes(c));
      if (!trailing.length) return cols;
      return cols.filter((c) => !trailing.includes(c)).concat(trailing);
    }

    // 연속된 동일 값 셀을 세로 병합(rowspan). 왼쪽 컬럼부터 계층적으로 적용해
    // 상위 그룹이 같을 때만 병합되도록 한다(예: 기준년월이 같은 구간만 합침).
    function computeRowSpans(rows, cols) {
      const n = rows.length;
      const spans = rows.map(() => cols.map(() => 1));
      // 집계값/측정값 컬럼은 병합하지 않는다.
      const noMerge = new Set(["고객수", "전월대비증감"]);
      cols.forEach((col, cIdx) => {
        if (noMerge.has(col) || cIdx === cols.length - 1) return;
        let start = 0;
        while (start < n) {
          let end = start + 1;
          while (
            end < n &&
            sameCell(rows[end][col], rows[start][col]) &&
            parentGroupsMatch(rows, cols, cIdx, end, start)
          ) {
            end += 1;
          }
          const groupLen = end - start;
          if (groupLen > 1) {
            spans[start][cIdx] = groupLen;
            for (let r = start + 1; r < end; r += 1) spans[r][cIdx] = 0;
          }
          start = end;
        }
      });
      return spans;

      function sameCell(a, b) {
        return String(a == null ? "" : a) === String(b == null ? "" : b);
      }
      function parentGroupsMatch(rowsArr, colArr, cIdx, r1, r2) {
        for (let p = 0; p < cIdx; p += 1) {
          if (!sameCell(rowsArr[r1][colArr[p]], rowsArr[r2][colArr[p]])) {
            return false;
          }
        }
        return true;
      }
    }

    // 보고서 전용 '보고서 제목: ...' 라인은 채팅 화면에서 숨긴다.
    function stripReportTitleLine(content) {
      if (!content) return content;
      const lines = content.split("\n");
      const kept = lines.filter(
        (line) => !/^\s*보고서\s*제목\s*[:：]/.test(line)
      );
      return kept.join("\n").replace(/^\n+/, "");
    }

    // 분석 에이전트 본문을 '외부 환경 연결' 기준으로 head/tail 분리.
    function splitAnalysisContent(content) {
      const text = content || "";
      const lines = text.split("\n");
      for (let i = 0; i < lines.length; i += 1) {
        const norm = lines[i].replace(/[#*\-0-9.()[\]\s]/g, "");
        if (norm.indexOf("외부환경연결") === 0 && norm.length <= "외부환경연결".length + 2) {
          return {
            head: lines.slice(0, i).join("\n").trimEnd(),
            tail: lines.slice(i).join("\n").trim(),
          };
        }
      }
      return { head: text, tail: "" };
    }

    function hasInst1Rows(inst1Data) {
      if (!inst1Data || typeof inst1Data !== "object") return false;
      return Object.keys(inst1Data).some((k) => {
        const v = inst1Data[k];
        return Array.isArray(v) ? v.length : v && Array.isArray(v.rows) && v.rows.length;
      });
    }

    // 분석 에이전트 메시지: 요약 → 표·차트 → 외부 환경 연결~ 순으로 렌더.
    // 반환값 true면 호출부에서 별도 표/차트 렌더를 생략한다.
    function renderAnalysisLayout(el, textEl, displayContent, media) {
      const inst1Data = media.inst1Data || {};
      const isAnalysis =
        displayContent &&
        displayContent.indexOf("외부 환경 연결") !== -1 &&
        hasInst1Rows(inst1Data);
      if (!isAnalysis) return false;
      const parts = splitAnalysisContent(displayContent);
      if (textEl) textEl.textContent = parts.head;
      renderInst1Tables(
        el,
        inst1Data,
        null,
        media.inst1ColumnOrders || null,
        media.inst1ResultLabels || null,
        { hideSql: true, hideTitle: true }
      );
      if (media.charts && media.charts.length) {
        renderCharts(el, media.charts, { hideTitle: true, hideSave: true });
      }
      if (parts.tail) {
        const tailEl = document.createElement("div");
        tailEl.className = "msg-text msg-analysis-tail";
        tailEl.textContent = parts.tail;
        el.appendChild(tailEl);
      }
      return true;
    }

    function renderInst1Tables(container, inst1Data, inst1Queries, inst1ColumnOrders, inst1ResultLabels, options) {
      const opts = options || {};
      const data = inst1Data && typeof inst1Data === "object" ? inst1Data : {};
      const queries = inst1Queries && typeof inst1Queries === "object" ? inst1Queries : {};
      const tableNames = [...new Set([...Object.keys(queries), ...Object.keys(data)])];
      if (!tableNames.length) return;
      tableNames.forEach((tableName) => {
        const displayName = inst1ResultLabel(tableName, inst1ResultLabels);
        const rows = data[tableName] || [];
        const sql = queries[tableName] || "";
        if (sql && !opts.hideSql) {
          renderInst1Sql(container, tableName, sql, displayName);
        }
        if (!rows.length) return;
        const block = document.createElement("div");
        block.className = "inst1-table-block";
        if (!opts.hideTitle) {
          const title = document.createElement("p");
          title.className = "chart-title";
          title.textContent = displayName + " — 조회 결과 (" + rows.length + "건)";
          block.appendChild(title);
        }
        const wrap = document.createElement("div");
        wrap.className = "inst1-table-wrap";
        const tbl = document.createElement("table");
        tbl.className = "inst1-table";
        const cols = orderInst1Columns(rows, (inst1ColumnOrders || {})[tableName]);
        const thead = document.createElement("thead");
        const hr = document.createElement("tr");
        cols.forEach((c) => {
          const th = document.createElement("th");
          th.textContent = c;
          hr.appendChild(th);
        });
        thead.appendChild(hr);
        tbl.appendChild(thead);
        const tbody = document.createElement("tbody");
        const spans = computeRowSpans(rows, cols);
        rows.forEach((row, rIdx) => {
          const tr = document.createElement("tr");
          cols.forEach((c, cIdx) => {
            const span = spans[rIdx][cIdx];
            if (span === 0) return;
            const td = document.createElement("td");
            td.textContent = displayCellValue(c, row[c]);
            if (span > 1) {
              td.rowSpan = span;
              td.classList.add("inst1-cell-merged");
            }
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        });
        tbl.appendChild(tbody);
        wrap.appendChild(tbl);
        block.appendChild(wrap);
        container.appendChild(block);
      });
      scrollChatToBottom();
    }

    function hasExcelExportData(excelExport) {
      if (!excelExport || excelExport.agent !== "inst1_extract") return false;
      if (excelExport.rows && excelExport.rows.length) return true;
      const sheets = excelExport.sheets || [];
      return sheets.some((s) => s.rows && s.rows.length);
    }

    function renderActionBar(container, options) {
      if (container.querySelector("[data-action-bar]")) return;
      const excelExport = options.excelExport;
      const reportExport = options.reportExport;
      const hasExcel = hasExcelExportData(excelExport);
      const hasReport = hasReportExportData(reportExport);
      if (!hasExcel && !hasReport) return;

      const bar = document.createElement("div");
      bar.className = "msg-action-bar";
      bar.dataset.actionBar = "1";

      if (hasExcel) {
        const excelWrap = document.createElement("div");
        excelWrap.className = "excel-export-wrap";
        const excelBtn = document.createElement("button");
        excelBtn.type = "button";
        excelBtn.className = "btn-excel-export";
        excelBtn.textContent = "엑셀 저장";
        excelBtn.addEventListener("click", () => downloadExcel(excelExport, excelBtn));
        excelWrap.appendChild(excelBtn);
        bar.appendChild(excelWrap);
      }

      if (hasReport) {
        const reportWrap = document.createElement("div");
        reportWrap.className = "report-export-wrap";
        const reportBtn = document.createElement("button");
        reportBtn.type = "button";
        reportBtn.className = "btn-report-export";
        reportBtn.textContent = "보고서";
        reportBtn.addEventListener("click", () =>
          downloadReport(reportExport, reportBtn)
        );
        reportWrap.appendChild(reportBtn);
        bar.dataset.reportExport = JSON.stringify(reportExport);
        bar.appendChild(reportWrap);
      }

      container.appendChild(bar);
      scrollChatToBottom();
    }

    function updateActionBarReport(container, reportExport) {
      const bar = container.querySelector("[data-action-bar]");
      if (!bar || !hasReportExportData(reportExport)) return;
      bar.dataset.reportExport = JSON.stringify(reportExport);
      const reportBtn = bar.querySelector(".btn-report-export");
      if (!reportBtn) {
        const reportWrap = document.createElement("div");
        reportWrap.className = "report-export-wrap";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-report-export";
        btn.textContent = "보고서";
        btn.addEventListener("click", () => downloadReport(reportExport, btn));
        reportWrap.appendChild(btn);
        bar.appendChild(reportWrap);
        return;
      }
      const newBtn = reportBtn.cloneNode(true);
      reportBtn.replaceWith(newBtn);
      newBtn.addEventListener("click", () => downloadReport(reportExport, newBtn));
    }

    function renderExcelButton(container, excelExport) {
      renderActionBar(container, {
        excelExport,
        reportExport: null,
      });
    }

    async function downloadExcel(exportData, btn) {
      const wrap = btn.closest(".excel-export-wrap");
      const prev = btn.textContent;
      btn.disabled = true;
      btn.textContent = "저장 중…";
      wrap?.querySelector(".excel-save-path")?.remove();
      try {
        const res = await fetch("/api/export/excel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ export: exportData }),
        });
        const contentType = res.headers.get("Content-Type") || "";
        if (!res.ok || contentType.includes("application/json")) {
          let errMsg = "엑셀 저장 실패 (" + res.status + ")";
          try {
            const errJson = await res.json();
            if (errJson.error) errMsg = errJson.error;
          } catch (_) {
            /* ignore */
          }
          throw new Error(errMsg);
        }
        const blob = await res.blob();
        if (!blob || blob.size < 100) {
          throw new Error("생성된 엑셀 파일이 비어 있습니다.");
        }
        let filename = exportData.filename || "culture_export.xlsx";
        filename = filename.replace(/[^A-Za-z0-9._-]/g, "_");
        if (!filename.toLowerCase().endsWith(".xlsx")) filename += ".xlsx";
        const savedPath = res.headers.get("X-Saved-Path") || "";
        const xlsxBlob = new Blob([blob], {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });
        const url = URL.createObjectURL(xlsxBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          URL.revokeObjectURL(url);
          a.remove();
        }, 1000);
        btn.textContent = "저장 완료";
        if (wrap && savedPath) {
          const info = document.createElement("p");
          info.className = "excel-save-path";
          info.textContent = "저장 위치: " + savedPath;
          wrap.appendChild(info);
        }
      } catch (err) {
        btn.textContent = prev;
        alert(err.message || String(err));
      } finally {
        btn.disabled = false;
      }
    }

    function hasReportExportData(reportExport) {
      const agent = reportExport && reportExport.agent;
      return !!(
        reportExport &&
        (agent === "inst1_data_summary" || agent === "inst1_external_insight") &&
        (reportExport.content || reportExport.summary)
      );
    }

    function renderReportExport(container, reportExport, excelExport) {
      renderActionBar(container, {
        excelExport: excelExport || null,
        reportExport,
      });
    }

    function renderReportButton(container, reportExport) {
      renderActionBar(container, {
        excelExport: null,
        reportExport,
      });
    }

    async function downloadReport(reportData, btn) {
      const wrap = btn.closest(".report-export-wrap");
      const prev = btn.textContent;
      btn.disabled = true;
      btn.textContent = "생성 중…";
      wrap?.querySelector(".report-save-path")?.remove();
      try {
        const res = await fetch("/api/export/report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            use_session: true,
            messages: liveChatHistory,
            report: reportData || undefined,
            filename: (reportData && reportData.filename) || undefined,
          }),
        });
        const contentType = res.headers.get("Content-Type") || "";
        if (!res.ok || contentType.includes("application/json")) {
          let errMsg = "보고서 저장 실패 (" + res.status + ")";
          try {
            const errJson = await res.json();
            if (errJson.error) errMsg = errJson.error;
          } catch (_) {
            /* ignore */
          }
          throw new Error(errMsg);
        }
        const blob = await res.blob();
        if (!blob || blob.size < 100) {
          throw new Error("생성된 보고서 파일이 비어 있습니다.");
        }
        let filename = (reportData && reportData.filename) || "culture_report.docx";
        filename = filename.replace(/[^A-Za-z0-9._-]/g, "_");
        if (filename.toLowerCase().endsWith(".pptx")) {
          filename = filename.slice(0, -5) + ".docx";
        }
        if (!filename.toLowerCase().endsWith(".docx")) filename += ".docx";
        const savedPath = res.headers.get("X-Saved-Path") || "";
        const docBlob = new Blob([blob], {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });
        const url = URL.createObjectURL(docBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          URL.revokeObjectURL(url);
          a.remove();
        }, 1000);
        btn.textContent = "저장 완료";
        if (wrap && savedPath) {
          const info = document.createElement("p");
          info.className = "report-save-path";
          info.textContent = "저장 위치: " + savedPath;
          wrap.appendChild(info);
        }
      } catch (err) {
        btn.textContent = prev;
        alert(err.message || String(err));
      } finally {
        btn.disabled = false;
      }
    }

    function renderPdfLink(container, pdfUrl) {
      if (!pdfUrl) return;
      const wrap = document.createElement("div");
      wrap.className = "pdf-link-wrap";
      const link = document.createElement("a");
      link.className = "pdf-link";
      link.href = pdfUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "PDF 다운로드 (S3)";
      wrap.appendChild(link);
      container.appendChild(wrap);
      scrollChatToBottom();
    }

    function appendMsg(
      role,
      content,
      streaming,
      charts,
      pdfUrl,
      inst1Data,
      inst1Queries,
      inst1ColumnOrders,
      inst1ResultLabels,
      followUpQuestions,
      excelExport,
      reportExport,
      chartTypeOptions,
      aggregateColumnOptions,
      aggregateColumnLabel,
      aggregateColumnPickMode,
      schemaPipelineNotice
    ) {
      clearHint();
      const el = document.createElement("div");
      el.className = "msg " + role + (streaming ? " streaming" : "");
      const textEl = document.createElement("div");
      textEl.className = "msg-text";
      const followUp = resolveFollowUpQuestions(content, followUpQuestions);
      const displayText = stripReportTitleLine(followUp.displayContent);
      textEl.textContent = displayText;
      el.appendChild(textEl);
      if (role === "assistant" && schemaPipelineNotice) {
        renderSchemaPipelineNotice(el, schemaPipelineNotice);
      }
      const analysisHandled =
        role === "assistant" &&
        renderAnalysisLayout(el, textEl, displayText, {
          charts,
          inst1Data,
          inst1ColumnOrders,
          inst1ResultLabels,
        });
      if (role === "assistant" && !analysisHandled) {
        if (inst1Data || inst1Queries) {
          renderInst1Tables(
            el,
            inst1Data || {},
            inst1Queries || null,
            inst1ColumnOrders || null,
            inst1ResultLabels || null
          );
        }
        if (charts && charts.length) {
          renderCharts(el, charts);
        }
      }
      if (role === "assistant" && pdfUrl) {
        renderPdfLink(el, pdfUrl);
      }
      if (role === "assistant") {
        renderActionBar(el, {
          excelExport,
          reportExport,
        });
      }
      if (role === "assistant" && aggregateColumnOptions && aggregateColumnOptions.length) {
        renderAggregateColumnOptions(
          el,
          aggregateColumnOptions,
          aggregateColumnLabel,
          aggregateColumnPickMode
        );
      }
      if (role === "assistant" && chartTypeOptions && chartTypeOptions.length) {
        renderChartTypePicker(el, chartTypeOptions);
      }
      if (role === "assistant" && followUp.questions.length) {
        renderFollowUpQuestions(el, followUp.questions);
      }
      chatBox.appendChild(el);
      scrollChatToBottom();
      return { el, textEl };
    }

    function renderHistory(items) {
      chatBox.innerHTML = "";
      if (!items.length) {
        const hint = document.createElement("p");
        hint.className = "chat-hint";
        hint.dataset.chatHint = "1";
        hint.textContent =
          "메시지를 입력하거나, 위 추천질문처럼 그룹고객기본정보 집계를 요청하세요.";
        chatBox.appendChild(hint);
        return;
      }
      items.forEach((item) =>
        appendMsg(
          item.role,
          item.content || "",
          false,
          item.charts || [],
          item.pdf_url || "",
          item.inst1_data || null,
          item.inst1_queries || null,
          item.inst1_column_orders || null,
          item.inst1_result_labels || null,
          item.follow_up_questions || [],
          item.excel_export || null,
          item.report_export || null,
          item.chart_type_options || [],
          item.aggregate_column_options || [],
          item.aggregate_column_label || "",
          item.aggregate_column_pick_mode || "append",
          item.schema_pipeline_notice || ""
        )
      );
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
          showGeneratingStatus(state, payload);
          if (payload.schema_pipeline || (payload.text || "").indexOf("[데이터 사전]") >= 0) {
            renderSchemaPipelineNotice(state.el, payload.text);
          }
        } else if (payload.type === "chunk") {
          finishGenerating(state);
          state.full += payload.text || "";
          state.textEl.textContent = state.full;
          scrollChatToBottom();
        } else if (payload.type === "error") {
          finishGenerating(state);
          throw new Error(payload.text || "오류");
        } else if (payload.type === "done") {
          finishGenerating(state);
          syncPendingChartReady(payload);
          if (payload.text) state.full = payload.text;
          state.textEl.textContent = state.full;
          const followUp = resolveFollowUpQuestions(
            state.full,
            payload.follow_up_questions
          );
          if (followUp.displayContent !== state.full) {
            state.textEl.textContent = followUp.displayContent;
          }
          const payloadAnalysisHandled = renderAnalysisLayout(
            state.el,
            state.textEl,
            followUp.displayContent,
            {
              charts: payload.charts,
              inst1Data: payload.inst1_data,
              inst1ColumnOrders: payload.inst1_column_orders,
              inst1ResultLabels: payload.inst1_result_labels,
            }
          );
          if (!payloadAnalysisHandled) {
            if (payload.inst1_data || payload.inst1_queries) {
              renderInst1Tables(
                state.el,
                payload.inst1_data || {},
                payload.inst1_queries || null,
                payload.inst1_column_orders || null,
                payload.inst1_result_labels || null
              );
            }
            if (payload.charts && payload.charts.length) {
              renderCharts(state.el, payload.charts);
            }
          }
          if (payload.pdf_url) {
            renderPdfLink(state.el, payload.pdf_url);
          }
          renderActionBar(state.el, {
            excelExport: payload.excel_export,
            reportExport: payload.report_export,
          });
          if (payload.aggregate_column_options && payload.aggregate_column_options.length) {
            renderAggregateColumnOptions(
              state.el,
              payload.aggregate_column_options,
              payload.aggregate_column_label,
              payload.aggregate_column_pick_mode
            );
          }
          if (payload.schema_pipeline_notice) {
            renderSchemaPipelineNotice(state.el, payload.schema_pipeline_notice);
          }
          if (payload.chart_type_options && payload.chart_type_options.length) {
            renderChartTypePicker(state.el, payload.chart_type_options);
          }
          if (followUp.questions.length) {
            renderFollowUpQuestions(state.el, followUp.questions);
          }
          if (payload.notice) {
            chatNotice.textContent = payload.notice;
            chatNotice.style.display = "block";
          }
          liveChatHistory.push({
            role: "assistant",
            content: payload.text || payload.reply || state.full || followUp.displayContent || "",
            charts: [...(payload.charts || [])],
            inst1_data: payload.inst1_data || {},
            inst1_column_orders: payload.inst1_column_orders || {},
            inst1_result_labels: payload.inst1_result_labels || {},
            inst1_queries: payload.inst1_queries || {},
            report_export: payload.report_export || null,
          });
        }
      }
    }

    async function sendViaStream(text, msgParts, state) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 15000);
      const res = await fetch(STREAM_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message: text, chart_types: generatedChartTypes }),
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

    async function sendViaJson(text, msgParts, state) {
      let fallbackIdx = 0;
      showGeneratingStatus(state, initialGeneratingStatus(text));
      const fallbackTimer = setInterval(() => {
        fallbackIdx = (fallbackIdx + 1) % FALLBACK_STATUS_MESSAGES.length;
        showGeneratingStatus(state, FALLBACK_STATUS_MESSAGES[fallbackIdx]);
      }, 7000);
      try {
        const res = await fetch(CHAT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ message: text, chart_types: generatedChartTypes }),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "요청 실패 (" + res.status + ")");
        }
        syncPendingChartReady(data);
        finishGenerating(state);
        state.full = data.reply || "";
        state.textEl.textContent = state.full;
        const followUp = resolveFollowUpQuestions(state.full, data.follow_up_questions);
        if (followUp.displayContent !== state.full) {
          state.textEl.textContent = followUp.displayContent;
        }
        const dataAnalysisHandled = renderAnalysisLayout(
          state.el,
          state.textEl,
          followUp.displayContent,
          {
            charts: data.charts,
            inst1Data: data.inst1_data,
            inst1ColumnOrders: data.inst1_column_orders,
            inst1ResultLabels: data.inst1_result_labels,
          }
        );
        if (!dataAnalysisHandled) {
          if (data.inst1_data || data.inst1_queries) {
            renderInst1Tables(
              state.el,
              data.inst1_data || {},
              data.inst1_queries || null,
              data.inst1_column_orders || null,
              data.inst1_result_labels || null
            );
          }
          if (data.charts && data.charts.length) {
            renderCharts(state.el, data.charts);
          }
        }
        if (data.pdf_url) {
          renderPdfLink(state.el, data.pdf_url);
        }
        renderActionBar(state.el, {
          excelExport: data.excel_export,
          reportExport: data.report_export,
        });
        if (data.aggregate_column_options && data.aggregate_column_options.length) {
          renderAggregateColumnOptions(
            state.el,
            data.aggregate_column_options,
            data.aggregate_column_label,
            data.aggregate_column_pick_mode
          );
        }
        if (data.schema_pipeline_notice) {
          renderSchemaPipelineNotice(state.el, data.schema_pipeline_notice);
        }
        if (data.chart_type_options && data.chart_type_options.length) {
          renderChartTypePicker(state.el, data.chart_type_options);
        }
        if (followUp.questions.length) {
          renderFollowUpQuestions(state.el, followUp.questions);
        }
        if (data.notice) {
          chatNotice.textContent = data.notice;
          chatNotice.style.display = "block";
        }
        liveChatHistory.push({
          role: "assistant",
          content: data.reply || state.full || followUp.displayContent || "",
          charts: [...(data.charts || [])],
          inst1_data: data.inst1_data || {},
          inst1_column_orders: data.inst1_column_orders || {},
          inst1_result_labels: data.inst1_result_labels || {},
          inst1_queries: data.inst1_queries || {},
          report_export: data.report_export || null,
        });
      } finally {
        clearInterval(fallbackTimer);
      }
    }

    async function sendMessage() {
      const text = messageInput.value.trim();
      if (!text || sendBtn.disabled) return;

      messageInput.value = "";
      sendBtn.disabled = true;
      statusLine.textContent = "";
      chatNotice.style.display = "none";

      appendMsg("user", text, false);
      liveChatHistory.push({ role: "user", content: text });
      const msgParts = appendMsg("assistant", "", true);
      const state = {
        full: "",
        el: msgParts.el,
        textEl: msgParts.textEl,
        typing: createTypingController(msgParts.textEl),
      };
      showGeneratingStatus(state, initialGeneratingStatus(text));

      try {
        const useStream = opts.preferStream !== false;
        if (useStream) {
          try {
            await sendViaStream(text, msgParts, state);
          } catch (streamErr) {
            console.warn("stream fallback:", streamErr);
            state.full = "";
            state.textEl.textContent = "";
            await sendViaJson(text, msgParts, state);
          }
        } else {
          await sendViaJson(text, msgParts, state);
        }

        if (!state.full.trim()) {
          state.textEl.textContent = "(응답 본문이 비어 있습니다.)";
        }
        finishGenerating(state);
        state.el.classList.remove("streaming");
        statusLine.textContent = "";
      } catch (err) {
        finishGenerating(state);
        state.el.classList.remove("streaming");
        state.textEl.textContent = "(처리 실패: " + err.message + ")";
        statusLine.textContent = "";
        console.error(err);
      } finally {
        sendBtn.disabled = false;
        messageInput.focus();
        if (window.cultureReloadQuestions) {
          window.cultureReloadQuestions();
        }
      }
    }

    window.cultureSend = sendMessage;
    renderHistory(opts.history || []);

    const questionHistoryEl = document.getElementById("questionHistory");

    function renderQuestionHistory(questions) {
      if (!questionHistoryEl) return;
      questionHistoryEl.innerHTML = "";
      if (!questions || !questions.length) {
        const empty = document.createElement("p");
        empty.className = "question-history-empty";
        empty.textContent = "아직 질문 내역이 없습니다.";
        questionHistoryEl.appendChild(empty);
        return;
      }
      questions.forEach((q) => {
        const text = (q && q.question) || "";
        if (!text) return;
        const chip = document.createElement("p");
        chip.className = "question-chip";
        chip.textContent = text;
        chip.title = text;
        chip.setAttribute("tabindex", "0");
        chip.setAttribute("role", "button");
        chip.addEventListener("click", () => fillMessageInput(text));
        chip.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fillMessageInput(text);
          }
        });
        questionHistoryEl.appendChild(chip);
      });
    }

    async function loadQuestionHistory() {
      if (!questionHistoryEl) return;
      try {
        const res = await fetch("/api/questions", {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data && data.ok) {
          renderQuestionHistory(data.questions || []);
        }
      } catch (err) {
        console.warn("질문 내역 로드 실패:", err);
      }
    }

    window.cultureReloadQuestions = loadQuestionHistory;
    loadQuestionHistory();

    function bindSidebarFillChips(selector) {
      document.querySelectorAll(selector).forEach((chip) => {
        chip.addEventListener("click", () => {
          const fillText = chip.dataset.fillText || chip.textContent;
          fillMessageInput(fillText);
        });
        chip.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            chip.click();
          }
        });
        chip.setAttribute("tabindex", "0");
        chip.setAttribute("role", "button");
      });
    }

    bindSidebarFillChips(".prompt-chip, .table-chip");

    window.addEventListener("pageshow", (event) => {
      if (event.persisted) {
        renderHistory(opts.history || []);
        chatNotice.style.display = "none";
        statusLine.textContent = "";
      }
    });
    sendBtn.addEventListener("click", sendMessage);
    messageInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    messageInput.addEventListener("input", () => {
      messageInput.style.height = "auto";
      messageInput.style.height = Math.min(messageInput.scrollHeight, 88) + "px";
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
