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
      "[호출 에이전트: 질문 분석 에이전트]\n질문 의도를 파악하고, 조회·집계·요약 중 어떤 분석이 필요한지 판단하고 있습니다.",
      "[호출 에이전트: 데이터 추출 에이전트]\nSQL을 생성하고 그룹고객 데이터를 조회하고 있습니다.",
      "[호출 에이전트: 데이터 요약 에이전트]\n조회된 데이터를 분석하여 핵심 내용을 요약하고 있습니다.",
      "[호출 에이전트: 응답 조립]\n분석 결과를 모아 최종 답변을 완성하고 있습니다.",
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

    function renderCharts(container, charts) {
      if (!charts || !charts.length || typeof Chart === "undefined") return;
      charts.forEach((spec) => {
        const block = document.createElement("div");
        block.className = "chart-block";
        const title = document.createElement("p");
        title.className = "chart-title";
        title.textContent = spec.title || "막대그래프";
        block.appendChild(title);
        const wrap = document.createElement("div");
        wrap.className = "chart-canvas-wrap";
        const canvas = document.createElement("canvas");
        const canvasId = "culture-chart-" + ++chartUid;
        canvas.id = canvasId;
        wrap.appendChild(canvas);
        block.appendChild(wrap);
        container.appendChild(block);
        new Chart(canvas, {
          type: spec.type || "bar",
          data: {
            labels: spec.labels || [],
            datasets: spec.datasets || [],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: (spec.datasets || []).length > 1 },
            },
            scales: {
              y: { beginAtZero: true },
            },
          },
        });
      });
      scrollChatToBottom();
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
      INST1_DATA_TABLE_ORDER.push("TSHDEOA01", "TSHDEOA02", "TSHDEOA04");
      INST1_TABLE_LABELS.TSHDEOA01 = "그룹고객기본정보";
      INST1_TABLE_LABELS.TSHDEOA02 = "그룹고객거래기본";
      INST1_TABLE_LABELS.TSHDEOA04 = "그룹고객소득대출정보";
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
      if (!cols.includes("고객수")) return cols;
      return cols.filter((c) => c !== "고객수").concat(["고객수"]);
    }

    function renderInst1Tables(container, inst1Data, inst1Queries, inst1ColumnOrders, inst1ResultLabels) {
      const data = inst1Data && typeof inst1Data === "object" ? inst1Data : {};
      const queries = inst1Queries && typeof inst1Queries === "object" ? inst1Queries : {};
      const tableNames = [...new Set([...Object.keys(queries), ...Object.keys(data)])];
      if (!tableNames.length) return;
      tableNames.forEach((tableName) => {
        const displayName = inst1ResultLabel(tableName, inst1ResultLabels);
        const rows = data[tableName] || [];
        const sql = queries[tableName] || "";
        if (sql) {
          renderInst1Sql(container, tableName, sql, displayName);
        }
        if (!rows.length) return;
        const block = document.createElement("div");
        block.className = "inst1-table-block";
        const title = document.createElement("p");
        title.className = "chart-title";
        title.textContent = displayName + " — 조회 결과 (" + rows.length + "건)";
        block.appendChild(title);
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
        rows.forEach((row) => {
          const tr = document.createElement("tr");
          cols.forEach((c) => {
            const td = document.createElement("td");
            const v = row[c];
            td.textContent = displayCellValue(c, v);
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
      const chartAvailable = !!options.chartAvailable;
      const hasExcel = hasExcelExportData(excelExport);
      const hasReport = hasReportExportData(reportExport);
      if (!hasExcel && !hasReport && !chartAvailable) return;

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

      if (chartAvailable) {
        const chartBtn = document.createElement("button");
        chartBtn.type = "button";
        chartBtn.className = "btn-chart-generate";
        chartBtn.textContent = "차트 생성";
        chartBtn.addEventListener("click", () =>
          generateChart(container, chartBtn, bar)
        );
        bar.appendChild(chartBtn);
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

    async function generateChart(container, btn, bar) {
      const prev = btn.textContent;
      btn.disabled = true;
      btn.textContent = "생성 중…";
      try {
        const res = await fetch("/api/generate/chart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: "{}",
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "차트 생성 실패 (" + res.status + ")");
        }
        if (data.charts && data.charts.length) {
          renderCharts(container, data.charts);
        }
        btn.remove();
      } catch (err) {
        btn.textContent = prev;
        alert(err.message || String(err));
      } finally {
        btn.disabled = false;
      }
    }

    function renderExcelExport(container, excelExport) {
      /* unified action bar handles excel button */
    }

    function renderExcelButton(container, excelExport) {
      renderActionBar(container, {
        excelExport,
        reportExport: null,
        chartAvailable: false,
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
      return !!(
        reportExport &&
        reportExport.agent === "inst1_data_summary" &&
        (reportExport.content || reportExport.summary)
      );
    }

    function renderReportExport(container, reportExport, chartAvailable, excelExport) {
      renderActionBar(container, {
        excelExport: excelExport || null,
        reportExport,
        chartAvailable: !!chartAvailable,
      });
    }

    function renderReportButton(container, reportExport) {
      renderActionBar(container, {
        excelExport: null,
        reportExport,
        chartAvailable: false,
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
          body: JSON.stringify({ report: reportData }),
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
          throw new Error("생성된 PDF 파일이 비어 있습니다.");
        }
        let filename = reportData.filename || "culture_report.pdf";
        filename = filename.replace(/[^A-Za-z0-9._-]/g, "_");
        if (!filename.toLowerCase().endsWith(".pdf")) filename += ".pdf";
        const savedPath = res.headers.get("X-Saved-Path") || "";
        const pdfBlob = new Blob([blob], { type: "application/pdf" });
        const url = URL.createObjectURL(pdfBlob);
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
      chartAvailable,
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
      textEl.textContent = followUp.displayContent;
      el.appendChild(textEl);
      if (role === "assistant" && schemaPipelineNotice) {
        renderSchemaPipelineNotice(el, schemaPipelineNotice);
      }
      if (role === "assistant" && charts && charts.length) {
        renderCharts(el, charts);
      }
      if (role === "assistant" && pdfUrl) {
        renderPdfLink(el, pdfUrl);
      }
      if (role === "assistant" && (inst1Data || inst1Queries)) {
        renderInst1Tables(
          el,
          inst1Data || {},
          inst1Queries || null,
          inst1ColumnOrders || null,
          inst1ResultLabels || null
        );
      }
      if (role === "assistant") {
        renderActionBar(el, {
          excelExport,
          reportExport,
          chartAvailable: !!chartAvailable,
        });
      }
      if (role === "assistant" && followUp.questions.length) {
        renderFollowUpQuestions(el, followUp.questions);
      }
      if (role === "assistant" && aggregateColumnOptions && aggregateColumnOptions.length) {
        renderAggregateColumnOptions(
          el,
          aggregateColumnOptions,
          aggregateColumnLabel,
          aggregateColumnPickMode
        );
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
          item.chart_available || false,
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
          if (payload.text) state.full = payload.text;
          state.textEl.textContent = state.full;
          if (payload.charts && payload.charts.length) {
            renderCharts(state.el, payload.charts);
          }
          if (payload.pdf_url) {
            renderPdfLink(state.el, payload.pdf_url);
          }
          if (payload.inst1_data || payload.inst1_queries) {
            renderInst1Tables(
              state.el,
              payload.inst1_data || {},
              payload.inst1_queries || null,
              payload.inst1_column_orders || null,
              payload.inst1_result_labels || null
            );
          }
          renderActionBar(state.el, {
            excelExport: payload.excel_export,
            reportExport: payload.report_export,
            chartAvailable: !!payload.chart_available,
          });
          const followUp = resolveFollowUpQuestions(
            state.full,
            payload.follow_up_questions
          );
          if (followUp.displayContent !== state.full) {
            state.textEl.textContent = followUp.displayContent;
          }
          if (followUp.questions.length) {
            renderFollowUpQuestions(state.el, followUp.questions);
          }
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
          if (payload.notice) {
            chatNotice.textContent = payload.notice;
            chatNotice.style.display = "block";
          }
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

    async function sendViaJson(text, msgParts, state) {
      let fallbackIdx = 0;
      showGeneratingStatus(state, FALLBACK_STATUS_MESSAGES[0]);
      const fallbackTimer = setInterval(() => {
        fallbackIdx = (fallbackIdx + 1) % FALLBACK_STATUS_MESSAGES.length;
        showGeneratingStatus(state, FALLBACK_STATUS_MESSAGES[fallbackIdx]);
      }, 7000);
      try {
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
        finishGenerating(state);
        state.full = data.reply || "";
        state.textEl.textContent = state.full;
        if (data.charts && data.charts.length) {
          renderCharts(state.el, data.charts);
        }
        if (data.pdf_url) {
          renderPdfLink(state.el, data.pdf_url);
        }
        if (data.inst1_data || data.inst1_queries) {
          renderInst1Tables(
            state.el,
            data.inst1_data || {},
            data.inst1_queries || null,
            data.inst1_column_orders || null,
            data.inst1_result_labels || null
          );
        }
        renderActionBar(state.el, {
          excelExport: data.excel_export,
          reportExport: data.report_export,
          chartAvailable: !!data.chart_available,
        });
        const followUp = resolveFollowUpQuestions(state.full, data.follow_up_questions);
        if (followUp.displayContent !== state.full) {
          state.textEl.textContent = followUp.displayContent;
        }
        if (followUp.questions.length) {
          renderFollowUpQuestions(state.el, followUp.questions);
        }
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
        if (data.notice) {
          chatNotice.textContent = data.notice;
          chatNotice.style.display = "block";
        }
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
      const msgParts = appendMsg("assistant", "", true);
      const state = {
        full: "",
        el: msgParts.el,
        textEl: msgParts.textEl,
        typing: createTypingController(msgParts.textEl),
      };
      showGeneratingStatus(
        state,
        "[호출 에이전트: 질문 분석 에이전트]\n질문을 접수했습니다. 분석을 시작합니다."
      );

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
      }
    }

    window.cultureSend = sendMessage;
    renderHistory(opts.history || []);

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
