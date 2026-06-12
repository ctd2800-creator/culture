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

    function clearHint() {
      const hint = chatBox.querySelector("[data-chat-hint]");
      if (hint) hint.remove();
    }

    function scrollChatToBottom() {
      requestAnimationFrame(() => {
        chatBox.scrollTop = chatBox.scrollHeight;
      });
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

    const INST1_TABLE_LABELS = {
      TSHDEOA01: "그룹고객기본정보",
      TSHDEOA02: "그룹고객거래기본",
      TSHDE0ZCD: "그룹고객분석인스턴스목록",
    };

    function inst1ResultLabel(key, labels) {
      if (labels && labels[key]) return labels[key];
      if (INST1_TABLE_LABELS[key]) return INST1_TABLE_LABELS[key] + "(" + key + ")";
      if (key.startsWith("JOIN_")) {
        const tables = ["TSHDEOA01", "TSHDEOA02"].filter((t) => key.includes(t));
        if (tables.length) {
          const ko = tables.map((t) => INST1_TABLE_LABELS[t]).join("·");
          return ko + "(" + tables.join("·") + ")";
        }
      }
      for (const t of ["TSHDEOA01", "TSHDEOA02"]) {
        if (key.startsWith(t + "_")) return INST1_TABLE_LABELS[t] + "(" + t + ")";
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
            td.textContent = v === null || v === undefined ? "" : String(v);
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

    function renderFollowUpQuestions(container, questions) {
      if (!questions || !questions.length) return;
      const block = document.createElement("div");
      block.className = "msg-follow-up";
      const label = document.createElement("p");
      label.className = "follow-up-label";
      label.textContent = "추천 질문";
      block.appendChild(label);
      questions.forEach((q) => {
        const item = document.createElement("p");
        item.className = "follow-up-item";
        item.textContent = "- " + q;
        block.appendChild(item);
      });
      container.appendChild(block);
      scrollChatToBottom();
    }

    function hasExcelExportData(excelExport) {
      if (!excelExport || excelExport.agent !== "inst1_extract") return false;
      if (excelExport.rows && excelExport.rows.length) return true;
      const sheets = excelExport.sheets || [];
      return sheets.some((s) => s.rows && s.rows.length);
    }

    function renderExcelExport(container, excelExport) {
      if (!hasExcelExportData(excelExport)) return;
      renderExcelButton(container, excelExport);
    }

    function renderExcelButton(container, excelExport) {
      if (!hasExcelExportData(excelExport)) return;
      const wrap = document.createElement("div");
      wrap.className = "excel-export-wrap";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-excel-export";
      btn.textContent = "엑셀 저장";
      btn.addEventListener("click", () => downloadExcel(excelExport, btn));
      wrap.appendChild(btn);
      container.appendChild(wrap);
      scrollChatToBottom();
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
      return !!(reportExport && (reportExport.content || reportExport.summary));
    }

    function renderReportExport(container, reportExport) {
      if (!hasReportExportData(reportExport)) return;
      renderReportButton(container, reportExport);
    }

    function renderReportButton(container, reportExport) {
      if (!hasReportExportData(reportExport)) return;
      const wrap = document.createElement("div");
      wrap.className = "report-export-wrap";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-report-export";
      btn.textContent = "보고서";
      btn.addEventListener("click", () => downloadReport(reportExport, btn));
      wrap.appendChild(btn);
      container.appendChild(wrap);
      scrollChatToBottom();
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
      reportExport
    ) {
      clearHint();
      const el = document.createElement("div");
      el.className = "msg " + role + (streaming ? " streaming" : "");
      const textEl = document.createElement("div");
      textEl.className = "msg-text";
      textEl.textContent = content;
      el.appendChild(textEl);
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
        renderExcelExport(el, excelExport);
        renderReportExport(el, reportExport);
      }
      if (role === "assistant" && followUpQuestions && followUpQuestions.length) {
        renderFollowUpQuestions(el, followUpQuestions);
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
          item.report_export || null
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
          statusLine.textContent = payload.text || "";
        } else if (payload.type === "chunk") {
          state.full += payload.text || "";
          state.textEl.textContent = state.full;
          scrollChatToBottom();
        } else if (payload.type === "error") {
          throw new Error(payload.text || "오류");
        } else if (payload.type === "done") {
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
          renderExcelExport(state.el, payload.excel_export);
          renderReportExport(state.el, payload.report_export);
          if (payload.follow_up_questions && payload.follow_up_questions.length) {
            renderFollowUpQuestions(state.el, payload.follow_up_questions);
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
      renderExcelExport(state.el, data.excel_export);
      renderReportExport(state.el, data.report_export);
      if (data.follow_up_questions && data.follow_up_questions.length) {
        renderFollowUpQuestions(state.el, data.follow_up_questions);
      }
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
      const msgParts = appendMsg("assistant", "…", true);
      const state = { full: "", el: msgParts.el, textEl: msgParts.textEl };

      try {
        const useStream = opts.preferStream !== false;
        if (useStream) {
          try {
            statusLine.textContent = "스트리밍 연결 중…";
            await sendViaStream(text, msgParts, state);
          } catch (streamErr) {
            console.warn("stream fallback:", streamErr);
            state.textEl.textContent = "…";
            await sendViaJson(text, msgParts, state);
          }
        } else {
          await sendViaJson(text, msgParts, state);
        }

        if (!state.full.trim()) {
          state.textEl.textContent = "(응답 본문이 비어 있습니다.)";
        }
        state.el.classList.remove("streaming");
        statusLine.textContent = "";
      } catch (err) {
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
    renderHistory([]);

    window.addEventListener("pageshow", (event) => {
      if (event.persisted) {
        renderHistory([]);
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
