const CONDITION_LABELS = {
  standard: "Standard Interface",
  explanation: "Explanation-Based Interface",
  verification_guided: "Verification-Guided Interface",
};

const CONDITION_INTROS = {
  standard:
    "<strong>Standard Interface:</strong> Inspect the problem statement and C++ code directly with no extra verification aids.",
  explanation:
    "<strong>Explanation-Based Interface:</strong> Read the short line-anchored notes on the right explaining code purpose, logic, and assumptions.",
  verification_guided:
    "<strong>Verification-Guided Interface:</strong> Use the highlighted lines, edge cases, checklist, and optional expandable hints to guide your inspection.",
};

const state = {
  participantId: null,
  blocks: [],
  blockIndex: 0,
  taskIndex: 0,
  taskStartMs: 0,
  timerInterval: null,
  selectedLine: null,
  expandedHintsCount: 0,
  llmPreviewData: null,
  llmPreviewCond: "standard",
  pgData: null,
  pgCond: "verification_guided",
};

// --- Navigation ---
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.dataset.view;
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    document.getElementById(target).classList.remove("hidden");
    if (target === "researcher-view") {
      loadAnalytics();
    }
  });
});

function setStudyStep(stepNum) {
  document.querySelectorAll("#study-stepper .step-item").forEach((el) => {
    const n = Number(el.dataset.step);
    el.classList.remove("active", "done");
    if (n < stepNum) el.classList.add("done");
    if (n === stepNum) el.classList.add("active");
  });
}

// --- C/C++ Syntax Highlighter (Zero-dependency safe tokenizer) ---
const CPP_KEYWORDS = new Set([
  "if", "else", "for", "while", "do", "switch", "case", "break", "continue",
  "return", "const", "constexpr", "static_cast", "dynamic_cast", "reinterpret_cast",
  "struct", "class", "public", "private", "protected", "namespace", "using",
  "true", "false", "nullptr", "auto", "sizeof", "new", "delete", "try", "catch",
]);

const CPP_TYPES = new Set([
  "int", "long", "short", "char", "bool", "float", "double", "void",
  "size_t", "uint32_t", "uint64_t", "int64_t", "std", "vector", "string",
  "map", "unordered_map", "set", "pair",
]);

function highlightCppLine(rawLine) {
  const tokenRegex = /(\/\/.*$|\/\*.*?\*\/|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|#\w+|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*\b)/g;
  let result = "";
  let lastIdx = 0;
  let match;

  while ((match = tokenRegex.exec(rawLine)) !== null) {
    if (match.index > lastIdx) {
      result += escapeHtml(rawLine.slice(lastIdx, match.index));
    }
    const tok = match[0];
    if (tok.startsWith("//") || tok.startsWith("/*")) {
      result += `<span class="tok-cmt">${escapeHtml(tok)}</span>`;
    } else if (tok.startsWith('"') || tok.startsWith("'")) {
      result += `<span class="tok-str">${escapeHtml(tok)}</span>`;
    } else if (tok.startsWith("#")) {
      result += `<span class="tok-prep">${escapeHtml(tok)}</span>`;
    } else if (/^\d/.test(tok)) {
      result += `<span class="tok-num">${escapeHtml(tok)}</span>`;
    } else if (CPP_KEYWORDS.has(tok)) {
      result += `<span class="tok-kw">${escapeHtml(tok)}</span>`;
    } else if (CPP_TYPES.has(tok)) {
      result += `<span class="tok-type">${escapeHtml(tok)}</span>`;
    } else {
      const nextChar = rawLine[tokenRegex.lastIndex];
      if (nextChar === "(") {
        result += `<span class="tok-fn">${escapeHtml(tok)}</span>`;
      } else {
        result += escapeHtml(tok);
      }
    }
    lastIdx = tokenRegex.lastIndex;
  }

  if (lastIdx < rawLine.length) {
    result += escapeHtml(rawLine.slice(lastIdx));
  }
  return result || " ";
}

function renderCodeViewer(containerEl, code, options = {}) {
  const { attentionLines = [], selectedLine = null, onLineClick = null } = options;
  containerEl.innerHTML = "";
  const lines = code.split("\n");

  lines.forEach((text, i) => {
    const lineNum = i + 1;
    const row = document.createElement("div");
    row.className = "code-line";
    if (attentionLines.includes(lineNum)) row.classList.add("attention");
    if (selectedLine === lineNum) row.classList.add("selected-error");

    const numSpan = document.createElement("span");
    numSpan.className = "line-num";
    numSpan.textContent = lineNum;
    if (onLineClick) {
      numSpan.title = `Click to mark line ${lineNum}`;
      numSpan.addEventListener("click", () => onLineClick(lineNum));
    }

    const codeSpan = document.createElement("span");
    codeSpan.className = "line-code";
    codeSpan.innerHTML = highlightCppLine(text);

    row.appendChild(numSpan);
    row.appendChild(codeSpan);
    containerEl.appendChild(row);
  });
}

// --- Health & LLM Status ---
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const pill = document.getElementById("llm-status-pill");
    const llm = data.llm;
    pill.textContent = llm.live_llm_enabled
      ? `LLM: ${llm.provider} (${llm.model})`
      : "LLM: Mock Mode (Set API key in .env)";
    document.getElementById("kpi-llm").textContent = `${llm.provider} (${llm.model})`;
  } catch (e) {
    console.error("Health check failed", e);
  }
}

// --- Onboarding & Consent ---
const cppSlider = document.getElementById("cpp-fam");
cppSlider.addEventListener("input", () => {
  document.getElementById("cpp-fam-val").textContent = cppSlider.value;
});

document.getElementById("onboarding-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    consent_given: document.getElementById("consent-check").checked,
    programming_experience: document.getElementById("prog-exp").value,
    cpp_familiarity: Number(cppSlider.value),
    ai_tool_frequency: document.getElementById("ai-freq").value,
  };

  const res = await fetch("/api/participants", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    alert("Could not start session. Please check all fields.");
    return;
  }

  const data = await res.json();
  state.participantId = data.participant_id;

  const planRes = await fetch(`/api/study/${state.participantId}/plan`);
  const plan = await planRes.json();
  state.blocks = plan.blocks;
  state.blockIndex = 0;
  state.taskIndex = 0;

  setStudyStep(2);
  document.getElementById("step-onboarding").classList.add("hidden");
  document.getElementById("step-task").classList.remove("hidden");
  renderCurrentTask();
});

// --- Render Active Study Task ---
function renderCurrentTask() {
  const block = state.blocks[state.blockIndex];
  const task = block.tasks[state.taskIndex];
  const cond = block.condition;

  state.selectedLine = null;
  state.expandedHintsCount = 0;
  document.getElementById("selected-line-indicator").classList.add("hidden");
  document.getElementById("verdict-form").reset();
  document.getElementById("confidence-val").textContent = "3";
  document.getElementById("error-details-box").classList.add("hidden");

  document.getElementById("active-condition-badge").textContent = CONDITION_LABELS[cond];
  document.getElementById("progress-text").textContent =
    `Block ${state.blockIndex + 1} of ${state.blocks.length} · Task ${state.taskIndex + 1} of ${block.tasks.length}`;
  document.getElementById("condition-intro-banner").innerHTML = CONDITION_INTROS[cond];

  document.getElementById("task-title").textContent = task.title;
  document.getElementById("task-difficulty").textContent = task.difficulty;
  document.getElementById("task-problem").textContent = task.problem_statement;

  const attentionLines =
    cond === "verification_guided" && task.verification_guided
      ? task.verification_guided.attention_lines || []
      : [];

  const codeContainer = document.getElementById("study-code-viewer");
  const handleLineClick = (lineNum) => {
    state.selectedLine = state.selectedLine === lineNum ? null : lineNum;
    const tag = document.getElementById("selected-line-indicator");
    if (state.selectedLine) {
      document.getElementById("error-line-input").value = state.selectedLine;
      tag.textContent = `Marked Line: ${state.selectedLine}`;
      tag.classList.remove("hidden");
    } else {
      document.getElementById("error-line-input").value = "";
      tag.classList.add("hidden");
    }
    renderCodeViewer(codeContainer, task.code, {
      attentionLines,
      selectedLine: state.selectedLine,
      onLineClick: handleLineClick,
    });
  };

  renderCodeViewer(codeContainer, task.code, {
    attentionLines,
    selectedLine: state.selectedLine,
    onLineClick: handleLineClick,
  });

  const expPanel = document.getElementById("panel-explanation");
  const vgPanel = document.getElementById("panel-verification");
  expPanel.classList.add("hidden");
  vgPanel.classList.add("hidden");

  if (cond === "explanation" && task.explanation_notes) {
    expPanel.classList.remove("hidden");
    const list = document.getElementById("explanation-notes-list");
    list.innerHTML = "";
    task.explanation_notes.forEach((n) => {
      const div = document.createElement("div");
      div.className = "note-item";
      div.innerHTML = `<strong>Line ${n.line}: ${escapeHtml(n.title)}</strong><span>${escapeHtml(n.text)}</span>`;
      list.appendChild(div);
    });
  } else if (cond === "verification_guided" && task.verification_guided) {
    vgPanel.classList.remove("hidden");
    const vg = task.verification_guided;

    document.getElementById("vg-assumptions").innerHTML = vg.assumptions
      .map((a) => `<li>${escapeHtml(a)}</li>`)
      .join("");

    document.getElementById("vg-edge-cases").innerHTML = vg.suggested_edge_cases
      .map((ec) => `<div class="edge-pill">${escapeHtml(ec)}</div>`)
      .join("");

    const checkEl = document.getElementById("vg-checklist");
    checkEl.innerHTML = "";
    vg.checklist.forEach((item, idx) => {
      const lbl = document.createElement("label");
      lbl.className = "checkbox-label";
      lbl.innerHTML = `<input type="checkbox" class="vg-check-item" data-idx="${idx}" /><span>${escapeHtml(item)}</span>`;
      checkEl.appendChild(lbl);
    });

    const hintsEl = document.getElementById("vg-hints");
    hintsEl.innerHTML = "";
    (vg.expandable_hints || []).forEach((h) => {
      const det = document.createElement("details");
      det.innerHTML = `<summary>Line ${h.line}: ${escapeHtml(h.label)}</summary><p>${escapeHtml(h.detail)}</p>`;
      det.addEventListener("toggle", () => {
        if (det.open) state.expandedHintsCount += 1;
      });
      hintsEl.appendChild(det);
    });
  }

  startTimer();
}

function startTimer() {
  if (state.timerInterval) clearInterval(state.timerInterval);
  state.taskStartMs = performance.now();
  const timerEl = document.getElementById("task-timer");
  timerEl.textContent = "00:00";

  state.timerInterval = setInterval(() => {
    const secs = Math.floor((performance.now() - state.taskStartMs) / 1000);
    const mm = String(Math.floor(secs / 60)).padStart(2, "0");
    const ss = String(secs % 60).padStart(2, "0");
    timerEl.textContent = `${mm}:${ss}`;
  }, 500);
}

document.querySelectorAll('input[name="verdict"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const box = document.getElementById("error-details-box");
    if (radio.value === "incorrect" && radio.checked) {
      box.classList.remove("hidden");
    } else {
      box.classList.add("hidden");
    }
  });
});

const confSlider = document.getElementById("confidence-slider");
confSlider.addEventListener("input", () => {
  document.getElementById("confidence-val").textContent = confSlider.value;
});

document.getElementById("verdict-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  clearInterval(state.timerInterval);
  const elapsedMs = Math.round(performance.now() - state.taskStartMs);

  const block = state.blocks[state.blockIndex];
  const task = block.tasks[state.taskIndex];
  const verdict = document.querySelector('input[name="verdict"]:checked').value;
  const lineVal = document.getElementById("error-line-input").value;
  const checkedItems = Array.from(document.querySelectorAll(".vg-check-item:checked")).map(
    (el) => Number(el.dataset.idx)
  );

  await fetch("/api/responses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_id: state.participantId,
      task_id: task.id,
      condition: block.condition,
      order_index: state.blockIndex * 2 + state.taskIndex,
      user_verdict: verdict,
      suspected_error_line: lineVal ? Number(lineVal) : null,
      suspected_error_description: document.getElementById("error-desc-input").value || null,
      confidence: Number(confSlider.value),
      time_taken_ms: elapsedMs,
      checklist_checked: checkedItems,
      expanded_hints_count: state.expandedHintsCount,
    }),
  });

  if (state.taskIndex + 1 < block.tasks.length) {
    state.taskIndex += 1;
    renderCurrentTask();
  } else {
    document.getElementById("step-task").classList.add("hidden");
    document.getElementById("rating-condition-name").textContent = CONDITION_LABELS[block.condition];
    document.getElementById("rating-form").reset();
    document.getElementById("step-rating").classList.remove("hidden");
  }
});

[
  ["rate-mental", "val-mental"],
  ["rate-effort", "val-effort"],
  ["rate-frustration", "val-frustration"],
  ["rate-helpful", "val-helpful"],
  ["rate-distract", "val-distract"],
  ["rate-usability", "val-usability"],
].forEach(([inputId, valId]) => {
  const el = document.getElementById(inputId);
  el.addEventListener("input", () => {
    document.getElementById(valId).textContent = el.value;
  });
});

document.getElementById("rating-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const block = state.blocks[state.blockIndex];

  await fetch("/api/ratings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_id: state.participantId,
      condition: block.condition,
      mental_demand: Number(document.getElementById("rate-mental").value),
      effort: Number(document.getElementById("rate-effort").value),
      frustration: Number(document.getElementById("rate-frustration").value),
      helpfulness: Number(document.getElementById("rate-helpful").value),
      distraction: Number(document.getElementById("rate-distract").value),
      overall_usability: Number(document.getElementById("rate-usability").value),
      useful_features: document.getElementById("qual-useful").value,
      confusing_features: document.getElementById("qual-confusing").value,
      comments: "",
    }),
  });

  document.getElementById("step-rating").classList.add("hidden");

  if (state.blockIndex + 1 < state.blocks.length) {
    state.blockIndex += 1;
    state.taskIndex = 0;
    document.getElementById("step-task").classList.remove("hidden");
    renderCurrentTask();
  } else {
    setStudyStep(3);
    document.getElementById("complete-pid").textContent = state.participantId;
    document.getElementById("step-complete").classList.remove("hidden");
  }
});

document.getElementById("btn-restart-study").addEventListener("click", () => {
  setStudyStep(1);
  document.getElementById("step-complete").classList.add("hidden");
  document.getElementById("onboarding-form").reset();
  document.getElementById("step-onboarding").classList.remove("hidden");
});

document.getElementById("btn-go-playground").addEventListener("click", () => {
  document.querySelector('[data-view="playground-view"]').click();
});

document.getElementById("btn-go-dashboard").addEventListener("click", () => {
  document.querySelector('[data-view="researcher-view"]').click();
});

// --- 2. AI Code Playground (General Use) ---
document.getElementById("playground-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("btn-pg-solve");
  btn.disabled = true;
  btn.textContent = "Generating Solution...";

  const preferred = document.querySelector('input[name="pg-iface"]:checked').value;
  try {
    const res = await fetch("/api/llm/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_statement: document.getElementById("pg-problem").value,
        language: "C++",
        preferred_interface: preferred,
      }),
    });
    state.pgData = await res.json();
    state.pgCond = preferred;
    syncPreviewTabs("pg-switch-tabs", preferred);
    renderPlaygroundResult();
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask AI for Solution";
  }
});

document.querySelectorAll("#pg-switch-tabs .preview-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.pgCond = tab.dataset.cond;
    syncPreviewTabs("pg-switch-tabs", state.pgCond);
    renderPlaygroundResult();
  });
});

function renderPlaygroundResult() {
  const d = state.pgData;
  if (!d) return;

  document.getElementById("pg-result-card").classList.remove("hidden");
  document.getElementById("pg-result-title").textContent = d.title || "AI Solution";
  document.getElementById("pg-result-meta").textContent =
    `Generated via ${d.llm_provider_used} · Viewing ${CONDITION_LABELS[state.pgCond]}`;

  renderConditionSplit(document.getElementById("pg-result-body"), d, state.pgCond, "pg-code-viewer");
}

// --- 3. Researcher Dashboard & LLM Tools ---
async function loadAnalytics() {
  const res = await fetch("/api/analytics/summary");
  const data = await res.json();

  document.getElementById("kpi-participants").textContent = data.total_participants;
  document.getElementById("kpi-responses").textContent = data.total_responses;

  const tbody = document.getElementById("stats-table-body");
  tbody.innerHTML = "";
  Object.entries(data.conditions).forEach(([cond, stats]) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${CONDITION_LABELS[cond] || cond}</strong></td>
      <td>${stats.n_responses}</td>
      <td>${stats.accuracy_pct}%</td>
      <td>${stats.error_detection_pct}%</td>
      <td>${stats.false_rejection_pct}%</td>
      <td>${stats.avg_time_sec}s</td>
      <td>${stats.avg_confidence}</td>
      <td>${stats.avg_workload}</td>
      <td>${stats.avg_usability}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById("btn-refresh-stats").addEventListener("click", loadAnalytics);

document.getElementById("btn-llm-analyze").addEventListener("click", async () => {
  const btn = document.getElementById("btn-llm-analyze");
  btn.disabled = true;
  btn.textContent = "Calling LLM...";
  try {
    const res = await fetch("/api/llm/analyze-code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "Custom C++ Analysis",
        problem_statement: document.getElementById("llm-problem").value,
        code: document.getElementById("llm-code").value,
      }),
    });
    state.llmPreviewData = await res.json();
    renderLLMPreview();
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Verification Aids (LLM)";
  }
});

document.getElementById("btn-llm-generate").addEventListener("click", async () => {
  const btn = document.getElementById("btn-llm-generate");
  btn.disabled = true;
  btn.textContent = "Generating via LLM...";
  try {
    const res = await fetch("/api/llm/generate-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: document.getElementById("gen-topic").value,
        difficulty: document.getElementById("gen-diff").value,
        should_contain_bug: document.getElementById("gen-bug").checked,
      }),
    });
    state.llmPreviewData = await res.json();
    renderLLMPreview();
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Task via LLM";
  }
});

document.querySelectorAll("#researcher-preview-tabs .preview-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    state.llmPreviewCond = tab.dataset.cond;
    syncPreviewTabs("researcher-preview-tabs", state.llmPreviewCond);
    renderLLMPreview();
  });
});

function renderLLMPreview() {
  const d = state.llmPreviewData;
  if (!d) return;

  document.getElementById("llm-preview-box").classList.remove("hidden");
  document.getElementById("preview-title").textContent =
    `${d.title || "Preview"} (via ${d.llm_provider_used})`;

  renderConditionSplit(
    document.getElementById("llm-preview-content"),
    d,
    state.llmPreviewCond,
    "preview-code-viewer"
  );
}

// Shared split renderer for Playground & Researcher Preview
function renderConditionSplit(container, d, cond, viewerId) {
  const attention =
    cond === "verification_guided" ? d.verification_guided?.attention_lines || [] : [];

  let sideHtml = "";
  if (cond === "explanation") {
    sideHtml = `<div class="card"><h4>Explanation-Based Notes</h4><div class="notes-list">${(
      d.explanation_notes || []
    )
      .map(
        (n) =>
          `<div class="note-item"><strong>Line ${n.line}: ${escapeHtml(n.title)}</strong><span>${escapeHtml(n.text)}</span></div>`
      )
      .join("")}</div></div>`;
  } else if (cond === "verification_guided" && d.verification_guided) {
    const vg = d.verification_guided;
    const hintsHtml = (vg.expandable_hints || [])
      .map(
        (h) =>
          `<details><summary>Line ${h.line}: ${escapeHtml(h.label)}</summary><p>${escapeHtml(h.detail)}</p></details>`
      )
      .join("");
    sideHtml = `
      <div class="card">
        <h4>Verification-Guided Support</h4>
        <div class="vg-section"><h5>Assumptions</h5><ul class="compact-list">${vg.assumptions
          .map((a) => `<li>${escapeHtml(a)}</li>`)
          .join("")}</ul></div>
        <div class="vg-section"><h5>Suggested Edge Cases</h5><div class="pill-list">${vg.suggested_edge_cases
          .map((e) => `<div class="edge-pill">${escapeHtml(e)}</div>`)
          .join("")}</div></div>
        <div class="vg-section"><h5>Checklist</h5><ul class="compact-list">${vg.checklist
          .map((c) => `<li>${escapeHtml(c)}</li>`)
          .join("")}</ul></div>
        ${hintsHtml ? `<div class="vg-section"><h5>Expandable Hints</h5><div class="hints-list">${hintsHtml}</div></div>` : ""}
      </div>`;
  }

  let gtBanner = "";
  if (typeof d.ground_truth_correct === "boolean") {
    gtBanner = `<div class="info-banner"><strong>Researcher Ground Truth:</strong> ${
      d.ground_truth_correct
        ? "Correct Solution"
        : `Buggy (Line ${d.ground_truth_error_line}: ${escapeHtml(d.ground_truth_error_description || "")})`
    }</div>`;
  }

  container.innerHTML = `
    ${gtBanner}
    <p><strong>Problem:</strong> ${escapeHtml(d.problem_statement)}</p>
    <div class="workspace-grid">
      <div class="code-viewer" id="${viewerId}"></div>
      <div>${sideHtml || '<div class="card muted">Standard mode: code only, no verification aids shown.</div>'}</div>
    </div>
  `;

  renderCodeViewer(document.getElementById(viewerId), d.code, {
    attentionLines: attention,
  });
}

function syncPreviewTabs(containerId, activeCond) {
  document.querySelectorAll(`#${containerId} .preview-tab`).forEach((t) => {
    t.classList.toggle("active", t.dataset.cond === activeCond);
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

checkHealth();
