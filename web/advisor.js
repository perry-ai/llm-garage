const $ = (id) => document.getElementById(id);

async function api(path) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  const contentType = response.headers.get("Content-Type") || "";
  let payload = {};
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    await response.text();
  }
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("后台版本过旧或检测路由尚未加载，请重新运行 start.bat。");
    }
    throw new Error((payload.messages || [`请求失败（HTTP ${response.status}）`]).join("\n"));
  }
  return payload;
}

function createElement(tag, className = "", textContent = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (textContent !== "") element.textContent = textContent;
  return element;
}

function formatGiB(value) {
  if (value === null || value === undefined || value === "") return "未知";
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)} GiB` : "未知";
}

function createMetric(label, value, detail = "") {
  const card = createElement("article", "hardware-card");
  card.appendChild(createElement("span", "metric-label", label));
  card.appendChild(createElement("strong", "metric-value", value || "未知"));
  if (detail) card.appendChild(createElement("small", "metric-detail", detail));
  return card;
}

function appendExternalLink(parent, label, url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:") return;
    const link = createElement("a", "source-link", label);
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noreferrer";
    parent.appendChild(link);
  } catch {
    // Ignore malformed source metadata instead of creating an unsafe link.
  }
}

function renderHardware(hardware) {
  const container = $("hardwareSummary");
  container.replaceChildren();

  const operatingSystem = hardware.operatingSystem || {};
  const cpu = hardware.cpu || {};
  const memory = hardware.memory || {};
  container.appendChild(
    createMetric(
      "操作系统",
      operatingSystem.displayName
        || `${operatingSystem.name || "未知"} ${operatingSystem.release || ""}`.trim(),
      `${operatingSystem.architecture || "未知架构"} · ${operatingSystem.version || "版本未知"}`,
    ),
  );
  container.appendChild(
    createMetric(
      "CPU",
      cpu.name || "未知 CPU",
      `${cpu.physicalCores ?? "?"} 物理核心 · ${cpu.logicalThreads ?? "?"} 逻辑线程`,
    ),
  );
  container.appendChild(
    createMetric(
      "系统内存",
      `${formatGiB(memory.ramAvailableGiB)} 可用`,
      `${formatGiB(memory.ramTotalGiB)} 总计 · 推荐按当前可用量计算`,
    ),
  );

  const gpus = hardware.gpus || [];
  if (gpus.length === 0) {
    container.appendChild(
      createMetric("GPU", "未确认可用独立 GPU", "进入保守 CPU 推荐路线"),
    );
  } else {
    for (const gpu of gpus) {
      const isNvidia = String(gpu.vendor || "").toLowerCase() === "nvidia";
      const memoryLine = gpu.vramTotalGiB
        ? `${formatGiB(gpu.vramFreeGiB)} 可用 · ${formatGiB(gpu.vramTotalGiB)} 总计`
        : "显存数据不可可靠确认";
      const details = [
        memoryLine,
        gpu.driverVersion ? `驱动 ${gpu.driverVersion}` : "",
        isNvidia ? `来源 ${gpu.source || "nvidia-smi"} · ${gpu.confidence || "high"}` : "非 NVIDIA：保守 CPU 路线",
      ]
        .filter(Boolean)
        .join(" · ");
      container.appendChild(createMetric(`GPU ${gpu.index ?? ""}`.trim(), gpu.name, details));
    }
  }

  const warnings = hardware.warnings || [];
  if (warnings.length) {
    const warningPanel = createElement("div", "hardware-warning");
    warningPanel.appendChild(createElement("strong", "", "检测提示"));
    const list = createElement("ul");
    for (const warning of warnings) list.appendChild(createElement("li", "", warning));
    warningPanel.appendChild(list);
    container.appendChild(warningPanel);
  }

  const nvidiaRoute = hardware.recommendationPath === "nvidia";
  $("hardwareRoute").textContent = nvidiaRoute ? "NVIDIA 加速路线" : "保守 CPU 路线";
  $("hardwareRoute").className = `route-badge ${nvidiaRoute ? "route-gpu" : "route-cpu"}`;
}

function fitLabel(fit) {
  return (
    fit.label
    ||
    {
      comfortable: "舒适",
      safe: "安全",
      try: "吃力可跑",
      "not-recommended": "不推荐",
    }[fit.status] || fit.status
  );
}

function offloadHeadline(model) {
  const offload = model.offload || {};
  if (offload.mode === "cpu") {
    return "CPU 路线 · --gpu-layers 0 · 纯 CPU 可加 --device none";
  }
  if (offload.mode === "full") {
    return `新版 auto · 明确全卸载 all · 旧版兼容值 ${offload.numericCompatibilityValue}`;
  }
  return `新版 auto · 手动起点 ${offload.layerCount}/${offload.blockCount} 个重复层`;
}

function renderModel(model) {
  const card = createElement(
    "article",
    `model-card fit-${model.fit.status}${model.position === "safe-default" ? " featured" : ""}`,
  );
  const header = createElement("div", "model-card-header");
  const titleGroup = createElement("div");
  if (model.position === "safe-default") {
    titleGroup.appendChild(createElement("span", "model-ribbon", "安全首推"));
  } else if (model.position === "lowest-risk") {
    titleGroup.appendChild(createElement("span", "model-ribbon uncertain", "最低风险 · 资源未知"));
  } else if (model.fit.status === "try") {
    titleGroup.appendChild(createElement("span", "model-ribbon stretch", "吃力档 · 需要耐心"));
  }
  titleGroup.appendChild(createElement("h3", "", model.name));
  const parameterLabel = model.activeParametersBillions
    ? `${model.parametersBillions}B 总参数 / ${model.activeParametersBillions}B 激活`
    : `${model.parametersBillions}B`;
  titleGroup.appendChild(
    createElement(
      "p",
      "model-id",
      `${parameterLabel} · ${model.quantization} · 官方文件约 ${model.officialFileSizeGB} GB`,
    ),
  );
  header.appendChild(titleGroup);
  header.appendChild(createElement("span", "fit-badge", fitLabel(model.fit)));
  card.appendChild(header);

  card.appendChild(createElement("p", "fit-reason", model.fit.reason));
  const facts = createElement("div", "model-facts");
  facts.appendChild(
    createElement(
      "span",
      "",
      `${model.memory.kvCacheContextSize} ctx KV ≈ ${formatGiB(model.memory.estimatedKvCacheGiB)}`,
    ),
  );
  facts.appendChild(createElement("span", "", `Context 首跑 ${model.suggested.ctxSize}`));
  facts.appendChild(createElement("span", "", `Threads 起点 ${model.suggested.threads}`));
  facts.appendChild(createElement("span", "", `原生窗口 ${model.architecture.nativeContext}`));
  if (model.artifact.sharded) {
    facts.appendChild(createElement("span", "artifact-warning", "两分片 GGUF"));
  }
  card.appendChild(facts);

  const offload = createElement("div", "offload-panel");
  offload.appendChild(createElement("span", "metric-label", "CPU / GPU 卸载建议"));
  offload.appendChild(createElement("strong", "", offloadHeadline(model)));
  offload.appendChild(createElement("p", "", model.offload.explanation));
  card.appendChild(offload);

  const details = createElement("details", "model-details");
  details.appendChild(createElement("summary", "", "为什么这样推荐？展开预算"));
  const reasonList = createElement("ul");
  for (const reason of model.reasons || []) {
    reasonList.appendChild(createElement("li", "", reason));
  }
  details.appendChild(reasonList);
  details.appendChild(createElement("p", "artifact-note", model.artifact.note));

  const calculation = model.offload.calculation || {};
  const budget = createElement("dl", "budget-grid");
  const budgetRows = [
    ["当前可用 RAM", formatGiB(model.fit.ramAvailableGiB)],
    [
      "主机与应用余量",
      formatGiB(model.fit.hostRamReserveGiB + model.fit.applicationRamReserveGiB),
    ],
    ["可用于模型的 RAM", formatGiB(model.fit.modelRamBudgetGiB)],
    ["当前空闲 VRAM", formatGiB(calculation.vramFreeGiB)],
    ["系统显存余量", formatGiB(calculation.systemReserveGiB)],
    ["计算显存余量", formatGiB(calculation.computeReserveGiB)],
    ["4K KV 估算", formatGiB(calculation.estimatedKvCacheGiB)],
    ["权重层预算", formatGiB(calculation.usableVramGiB)],
    ["主机侧权重估算", formatGiB(calculation.estimatedHostWeightGiB)],
    ["保守单层估算", formatGiB(calculation.estimatedLayerGiB)],
  ];
  for (const [label, value] of budgetRows) {
    budget.appendChild(createElement("dt", "", label));
    budget.appendChild(createElement("dd", "", value));
  }
  details.appendChild(budget);
  details.appendChild(createElement("p", "model-risk", `风险：${model.risk}`));
  card.appendChild(details);

  const footer = createElement("div", "model-card-footer");
  footer.appendChild(createElement("span", "", `License: ${model.license}`));
  const sourceLinks = createElement("div", "model-source-links");
  appendExternalLink(sourceLinks, "魔搭社区 ↗", model.modelScopeUrl);
  appendExternalLink(sourceLinks, "Hugging Face ↗", model.officialUrl);
  footer.appendChild(sourceLinks);
  card.appendChild(footer);
  return card;
}

function renderRecommendations(payload) {
  renderHardware(payload.hardware);
  $("recommendationPosture").textContent = payload.posture;
  $("rulesVersion").textContent = payload.assumptions.rulesVersion;

  const modelContainer = $("recommendationModels");
  modelContainer.replaceChildren();
  for (const model of payload.models || []) {
    modelContainer.appendChild(renderModel(model));
  }

  const rulesContainer = $("recommendationRules");
  rulesContainer.replaceChildren();
  for (const rule of payload.rules || []) {
    const card = createElement("article", "rule-card");
    card.appendChild(createElement("strong", "", rule.condition));
    card.appendChild(createElement("p", "", rule.result));
    rulesContainer.appendChild(card);
  }

  const assumptions = $("recommendationAssumptions");
  assumptions.replaceChildren();
  const assumptionLabels = {
    systemVramReserve: "系统显存余量",
    computeVramReserve: "计算显存余量",
    contextSize: "首跑 Context",
    kvCacheTypes: "KV cache 精度",
    hostRamReserve: "主机内存余量",
    rulesVersion: "规则版本",
  };
  for (const [key, value] of Object.entries(payload.assumptions || {})) {
    const row = createElement("div");
    row.appendChild(createElement("span", "", assumptionLabels[key] || key));
    row.appendChild(createElement("strong", "", String(value)));
    assumptions.appendChild(row);
  }

  const learningContainer = $("learningTopics");
  learningContainer.replaceChildren();
  for (const topic of payload.learning || []) {
    const details = createElement("details", "learning-card");
    const summary = createElement("summary");
    const summaryGroup = createElement("div");
    summaryGroup.appendChild(createElement("strong", "", topic.title));
    summaryGroup.appendChild(createElement("span", "", topic.summary));
    summary.appendChild(summaryGroup);
    summary.appendChild(createElement("span", "expand-mark", "+"));
    details.appendChild(summary);
    details.appendChild(createElement("p", "learning-details", topic.details));
    const steps = createElement("ol");
    for (const step of topic.steps || []) steps.appendChild(createElement("li", "", step));
    details.appendChild(steps);
    details.appendChild(createElement("p", "learning-caution", `注意：${topic.caution}`));
    const sources = createElement("div", "learning-sources");
    for (const source of topic.sources || []) {
      appendExternalLink(sources, `${source.label} ↗`, source.url);
    }
    details.appendChild(sources);
    details.addEventListener("toggle", () => {
      const mark = details.querySelector(".expand-mark");
      if (mark) mark.textContent = details.open ? "−" : "+";
    });
    learningContainer.appendChild(details);
  }
}

function showDetectionError(error) {
  const message = error.message || String(error);
  $("recommendationStatus").textContent = `检测失败 · ${message}`;
  $("hardwareRoute").textContent = "检测失败";
  $("hardwareRoute").className = "route-badge route-error";
  $("advisorErrorMessage").textContent = message;
  $("advisorError").hidden = false;
}

async function loadRecommendations() {
  const button = $("refreshRecommendationsBtn");
  button.disabled = true;
  $("advisorError").hidden = true;
  $("recommendationStatus").textContent = "正在检测 CPU、RAM、GPU 与显存…";
  try {
    const metadata = await api("/api/app");
    const capabilities = metadata.capabilities || [];
    if (!capabilities.includes("hardware-recommendations")) {
      throw new Error("当前后台不支持硬件推荐，请重新运行 start.bat。");
    }
    const payload = await api(`/api/recommendations?refresh=${Date.now()}`);
    renderRecommendations(payload);
    const detectedAt = payload.hardware.detectedAt
      ? new Date(payload.hardware.detectedAt).toLocaleString()
      : "刚刚";
    $("recommendationStatus").textContent = `检测完成 · ${detectedAt} · 当前空闲资源会继续变化`;
  } catch (error) {
    showDetectionError(error);
  } finally {
    button.disabled = false;
  }
}

$("refreshRecommendationsBtn").addEventListener("click", loadRecommendations);
loadRecommendations();
