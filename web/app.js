const fields = [
  "serverPath",
  "modelPath",
  "host",
  "port",
  "ctxSize",
  "gpuLayers",
  "threads",
  "batchSize",
  "ubatchSize",
  "parallel",
  "temperature",
  "topP",
  "embedding",
  "reranking",
  "advancedArgs",
];

const autoFields = new Set(["gpuLayers", "threads", "batchSize", "ubatchSize", "parallel", "temperature", "topP"]);

const defaults = {
  id: "default",
  name: "Default LLMGarage server",
  serverPath: "",
  modelPath: "",
  host: "127.0.0.1",
  port: 8080,
  ctxSize: 4096,
  gpuLayers: "",
  threads: "",
  batchSize: "",
  ubatchSize: "",
  parallel: "",
  temperature: "",
  topP: "",
  embedding: false,
  reranking: false,
  advancedArgs: "",
};

const text = {
  discardChanges: "\u5f53\u524d\u9884\u8bbe\u6709\u672a\u4fdd\u5b58\u4fee\u6539\uff0c\u786e\u8ba4\u5207\u6362\u5417\uff1f",
  saved: "\u9884\u8bbe\u5df2\u4fdd\u5b58",
  started: "\u5df2\u542f\u52a8",
  stopped: "\u5df2\u505c\u6b62",
  killAllConfirm: "\u8fd9\u4f1a\u5f3a\u5236\u505c\u6b62\u6240\u6709\u540d\u4e3a llama-server.exe \u7684\u8fdb\u7a0b\uff0c\u5305\u542b\u4e0d\u662f\u7531 LLMGarage \u542f\u52a8\u7684\u5b9e\u4f8b\u3002\u786e\u8ba4\u7ee7\u7eed\uff1f",
  executed: "\u5df2\u6267\u884c",
  keepOne: "\u81f3\u5c11\u4fdd\u7559\u4e00\u4e2a\u9884\u8bbe",
  deleteConfirm: "\u786e\u8ba4\u5220\u9664\u5f53\u524d\u9884\u8bbe\uff1f",
};

let presets = [];
let selectedId = localStorage.getItem("llmgarage.selectedPreset") || "default";
let dirty = false;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error((payload.messages || ["Request failed"]).join("\n"));
  }
  return payload;
}

function activePreset() {
  return presets.find((preset) => preset.id === selectedId) || presets[0];
}

function isAutoValue(value) {
  return value === "" || value === null || value === undefined || value === "auto";
}

function setAutoMode(field, mode) {
  const element = $(field);
  const modeSelect = document.querySelector(`.auto-mode[data-target="${field}"]`);
  if (!element || !modeSelect) return;
  modeSelect.value = mode;
  element.disabled = mode === "auto";
  if (mode === "auto") {
    element.value = "";
    element.placeholder = "auto";
  } else {
    element.placeholder = "";
  }
}

function syncAutoControls(preset) {
  for (const field of autoFields) {
    const value = preset[field];
    setAutoMode(field, isAutoValue(value) ? "auto" : "manual");
  }
}
function readForm() {
  const preset = { ...activePreset(), name: $("presetName").value.trim() || "Untitled preset" };
  for (const field of fields) {
    const element = $(field);
    if (!element) continue;
    if (element.type === "checkbox") {
      preset[field] = element.checked;
    } else if (element.type === "number") {
      const modeSelect = document.querySelector(`.auto-mode[data-target="${field}"]`);
      if (autoFields.has(field) && modeSelect && modeSelect.value === "auto") {
        preset[field] = "";
      } else {
        preset[field] = element.value === "" ? "" : Number(element.value);
      }
    } else {
      preset[field] = element.value;
    }
  }
  return preset;
}

function writeForm(preset) {
  $("presetName").value = preset.name || "";
  for (const field of fields) {
    const element = $(field);
    if (!element) continue;
    if (element.type === "checkbox") {
      element.checked = Boolean(preset[field]);
    } else {
      element.value = preset[field] ?? "";
    }
  }
  syncAutoControls(preset);
  setDirty(false);
  updateCommandPreview();
}

function setDirty(value) {
  dirty = value;
  $("dirtyBadge").hidden = !dirty;
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.hidden = false;
  window.setTimeout(() => {
    toast.hidden = true;
  }, 3500);
}

function renderPresets() {
  const select = $("presetSelect");
  select.innerHTML = "";
  for (const preset of presets) {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.name;
    option.selected = preset.id === selectedId;
    select.appendChild(option);
  }

  const list = $("presetList");
  list.innerHTML = "";
  for (const preset of presets) {
    const item = document.createElement("button");
    item.className = `preset-item${preset.id === selectedId ? " active" : ""}`;
    item.type = "button";
    item.textContent = preset.name;
    item.addEventListener("click", () => selectPreset(preset.id));
    list.appendChild(item);
  }
}

function maybeDiscardChanges() {
  return !dirty || confirm(text.discardChanges);
}

function selectPreset(id) {
  if (!maybeDiscardChanges()) return;
  selectedId = id;
  localStorage.setItem("llmgarage.selectedPreset", selectedId);
  renderPresets();
  writeForm(activePreset());
}

async function loadPresets() {
  const payload = await api("/api/presets");
  presets = payload.presets && payload.presets.length ? payload.presets : [{ ...defaults }];
  if (!presets.some((preset) => preset.id === selectedId)) {
    selectedId = presets[0].id;
  }
  renderPresets();
  writeForm(activePreset());
}

async function savePresets() {
  const current = readForm();
  presets = presets.map((preset) => (preset.id === selectedId ? current : preset));
  await api("/api/presets", { method: "POST", body: JSON.stringify({ presets }) });
  setDirty(false);
  renderPresets();
  showToast(text.saved);
}

async function updateCommandPreview() {
  const preset = readForm();
  try {
    const payload = await api("/api/command", { method: "POST", body: JSON.stringify({ preset }) });
    $("commandPreview").textContent = payload.command;
  } catch (error) {
    $("commandPreview").textContent = error.message;
  }
}

async function validatePreset() {
  const payload = await api("/api/validate", {
    method: "POST",
    body: JSON.stringify({ preset: readForm() }),
  });
  const box = $("validationBox");
  box.textContent = payload.messages.join("\n");
  box.className = `messages ${payload.ok ? "ok" : "bad"}`;
  return payload.ok;
}

async function startServer() {
  const payload = await api("/api/start", {
    method: "POST",
    body: JSON.stringify({ preset: readForm() }),
  });
  showToast((payload.messages || [text.started]).join("\n"));
  await refreshState();
  await refreshLogs();
}

async function stopServer() {
  const payload = await api("/api/stop", { method: "POST", body: "{}" });
  showToast((payload.messages || [text.stopped]).join("\n"));
  await refreshState();
  await refreshLogs();
}

async function killAllServers() {
  if (!confirm(text.killAllConfirm)) return;
  const payload = await api("/api/kill-all", { method: "POST", body: "{}" });
  showToast((payload.messages || [text.executed]).join("\n"));
  await refreshState();
  await refreshLogs();
}

async function refreshState() {
  const state = await api("/api/state");
  $("appUrl").textContent = state.appUrl;
  $("runState").textContent = state.running ? "Running" : "Stopped";
  $("runState").className = `status ${state.running ? "running" : "idle"}`;
  $("pidText").textContent = state.pid ? `PID ${state.pid}` : "PID -";
  $("uptimeText").textContent = formatSeconds(state.uptimeSeconds || 0);
}

async function refreshLogs() {
  const payload = await api("/api/logs");
  $("logs").textContent = (payload.lines || []).join("\n");
  $("logs").scrollTop = $("logs").scrollHeight;
}

function formatSeconds(total) {
  const hours = String(Math.floor(total / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function newPreset() {
  if (!maybeDiscardChanges()) return;
  const id = `preset-${Date.now()}`;
  const preset = { ...defaults, id, name: "New preset" };
  presets.push(preset);
  selectedId = id;
  renderPresets();
  writeForm(preset);
  setDirty(true);
}

function duplicatePreset() {
  const source = readForm();
  const id = `preset-${Date.now()}`;
  const copy = { ...source, id, name: `${source.name} copy` };
  presets.push(copy);
  selectedId = id;
  renderPresets();
  writeForm(copy);
  setDirty(true);
}

function deletePreset() {
  if (presets.length <= 1) {
    showToast(text.keepOne);
    return;
  }
  if (!confirm(text.deleteConfirm)) return;
  presets = presets.filter((preset) => preset.id !== selectedId);
  selectedId = presets[0].id;
  renderPresets();
  writeForm(activePreset());
  setDirty(true);
}

async function healthCheck() {
  const preset = readForm();
  const payload = await api("/api/health", {
    method: "POST",
    body: JSON.stringify({ host: preset.host, port: preset.port }),
  });
  $("testResult").textContent = JSON.stringify(payload, null, 2);
}

async function testPrompt() {
  const preset = readForm();
  const payload = await api("/api/test", {
    method: "POST",
    body: JSON.stringify({ host: preset.host, port: preset.port, prompt: $("testPrompt").value }),
  });
  $("testResult").textContent = JSON.stringify(payload, null, 2);
}

function bindTipPanels() {
  document.querySelectorAll(".tip").forEach((button) => {
    const field = button.closest(".auto-field");
    const panel = field ? field.querySelector(".tip-panel") : null;
    if (!panel) return;
    panel.textContent = button.dataset.tip || "";
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      panel.hidden = expanded;
    });
  });
}
function bindEvents() {
  $("presetSelect").addEventListener("change", (event) => selectPreset(event.target.value));
  $("savePresetBtn").addEventListener("click", () => savePresets().catch(showError));
  $("newPresetBtn").addEventListener("click", newPreset);
  $("duplicatePresetBtn").addEventListener("click", duplicatePreset);
  $("deletePresetBtn").addEventListener("click", deletePreset);
  $("validateBtn").addEventListener("click", () => validatePreset().catch(showError));
  $("startBtn").addEventListener("click", () => startServer().catch(showError));
  $("stopBtn").addEventListener("click", () => stopServer().catch(showError));
  $("killAllBtn").addEventListener("click", () => killAllServers().catch(showError));
  $("refreshLogsBtn").addEventListener("click", (event) => {
    event.preventDefault();
    refreshLogs().catch(showError);
  });
  $("healthBtn").addEventListener("click", () => healthCheck().catch(showError));
  $("testPromptBtn").addEventListener("click", () => testPrompt().catch(showError));
  bindTipPanels();

  $("presetName").addEventListener("input", () => setDirty(true));

  document.querySelectorAll(".auto-mode").forEach((modeSelect) => {
    modeSelect.addEventListener("change", () => {
      setAutoMode(modeSelect.dataset.target, modeSelect.value);
      setDirty(true);
      updateCommandPreview();
    });
  });

  for (const field of fields) {
    const element = $(field);
    if (!element) continue;
    element.addEventListener("input", () => {
      setDirty(true);
      updateCommandPreview();
    });
    element.addEventListener("change", () => {
      setDirty(true);
      updateCommandPreview();
    });
  }
}

function showError(error) {
  showToast(error.message || String(error));
}

async function init() {
  bindEvents();
  await loadPresets();
  await refreshState();
  await refreshLogs();
  window.setInterval(() => refreshState().catch(() => {}), 1000);
  window.setInterval(() => refreshLogs().catch(() => {}), 1000);
}

init().catch(showError);









