const number = new Intl.NumberFormat("en-US");
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 6 });
const daysSelect = document.querySelector("#days");
const providerSelect = document.querySelector("#llm-provider");
const modelSelect = document.querySelector("#llm-model");
const applyButton = document.querySelector("#apply-llm");
const assistantToggle = document.querySelector("#assistant-enabled");
let llmOptions = [];
const voiceControls = Object.fromEntries(["stt", "tts"].map((component) => [component, {
  provider: document.querySelector(`#${component}-provider`),
  model: document.querySelector(`#${component}-model`),
  apply: document.querySelector(`#apply-${component}`),
  options: [],
}]));

function text(id, value) { document.querySelector(`#${id}`).textContent = value; }
function money(value) { return value == null ? "No cloud price" : usd.format(value); }
function providerLabel(provider) {
  if (provider === "openai") return "OpenAI";
  if (provider === "llama.cpp") return "Local (llama.cpp)";
  if (provider === "sherpa-onnx") return "Local (sherpa-onnx)";
  return provider;
}

function componentLabel(provider, model) {
  if (!model) return "—";
  const models = {
    "whisper-small-int8": "Whisper Small INT8",
    "whisper-tiny-int8": "Whisper Tiny INT8",
    "pt_BR-jeff-medium": "Piper Jeff Medium",
  };
  const providerName = provider ? `${providerLabel(provider)} · ` : "";
  return `${providerName}${models[model] || model}`;
}

function pipelineLabel(pipeline) {
  if (pipeline === "chained") return "Chained";
  if (pipeline === "openai-realtime") return "OpenAI Realtime";
  return pipeline || "—";
}

function renderAssistantState(enabled) {
  assistantToggle.checked = enabled;
  text("assistant-toggle-label", enabled ? "On" : "Off");
  text("assistant-status", enabled
    ? "Listening for a voice request"
    : "Paused — microphone capture and AI processing are off");
  document.querySelector(".assistant-control").classList.toggle("paused", !enabled);
}

function populateModels(selectedModel) {
  const option = llmOptions.find((item) => item.provider === providerSelect.value);
  modelSelect.innerHTML = (option?.models || []).map((model) => `<option value="${model}">${model}</option>`).join("");
  if (selectedModel && option?.models.includes(selectedModel)) modelSelect.value = selectedModel;
  applyButton.disabled = !option?.available;
  text("llm-switch-status", option?.available ? "" : "Provider unavailable");
}

function populateVoiceModels(component, selectedModel) {
  const controls = voiceControls[component];
  const option = controls.options.find((item) => item.provider === controls.provider.value);
  controls.model.innerHTML = (option?.models || []).map((model) =>
    `<option value="${model.id}"${model.available ? "" : " disabled"}>${model.label}${model.available ? "" : " (not installed)"}</option>`
  ).join("");
  if (selectedModel && option?.models.some((model) => model.id === selectedModel && model.available)) {
    controls.model.value = selectedModel;
  }
  const selected = option?.models.find((model) => model.id === controls.model.value);
  controls.apply.disabled = !selected?.available;
  text(`${component}-switch-status`, selected?.available ? "" : "Model unavailable");
}

function configureVoiceSelector(component, info) {
  const controls = voiceControls[component];
  controls.options = info.options;
  controls.provider.innerHTML = controls.options.map((option) => {
    const available = option.models.some((model) => model.available);
    return `<option value="${option.provider}">${providerLabel(option.provider)}${available ? "" : " (unavailable)"}</option>`;
  }).join("");
  controls.provider.value = info.provider;
  populateVoiceModels(component, info.model);
}

function renderTechnology(info) {
  renderAssistantState(info.assistant.enabled);
  text("app-version", `v${info.version}`);
  text("tech-llm", info.llm.model);
  text("tech-llm-mode", `LLM · ${info.llm.processing}`);
  const speed = info.llm.tokens_per_second == null ? "" : ` · ${info.llm.tokens_per_second.toFixed(1)} tokens/s`;
  text("tech-llm-detail", `${providerLabel(info.llm.provider)} · ${info.llm.processing} processing${speed}`);
  text("processing-note", info.llm.provider === "openai"
    ? "Audio, STT, and TTS stay on the Raspberry Pi. Only text is sent to OpenAI."
    : "The complete voice pipeline, including the LLM, is running locally on the Raspberry Pi.");
  text("tech-stt", info.stt.model_label);
  text("tech-stt-mode", `STT · ${info.stt.processing}`);
  const normalization = info.stt.normalization ? `normalization to ${info.stt.target_peak} · max gain ${info.stt.max_gain}×` : "no normalization";
  text("tech-stt-detail", `${providerLabel(info.stt.provider)} · ${info.stt.language} · ${info.stt.threads} threads · ${normalization}`);
  text("tech-tts", info.tts.model_label);
  text("tech-tts-mode", `TTS · ${info.tts.processing}`);
  text("tech-tts-detail", `${providerLabel(info.tts.provider)} · ${info.tts.threads} threads`);
  text("tech-audio", `${info.audio.mode.toUpperCase()} · ${info.audio.vad}`);
  text("tech-audio-detail", `threshold ${info.audio.vad_threshold} · ending silence ${info.audio.ending_silence_seconds.toFixed(1)} s · HTTPS ${info.audio.tls ? "on" : "off"}`);
  llmOptions = info.llm.options;
  providerSelect.innerHTML = llmOptions.map((option) => `<option value="${option.provider}">${providerLabel(option.provider)}${option.available ? "" : " (unavailable)"}</option>`).join("");
  providerSelect.value = info.llm.provider;
  populateModels(info.llm.model);
  configureVoiceSelector("stt", info.stt);
  configureVoiceSelector("tts", info.tts);
}

function renderChart(daily) {
  const chart = document.querySelector("#chart");
  if (!daily.length) { chart.innerHTML = '<p class="empty">No data yet.</p>'; return; }
  const maximum = Math.max(...daily.map((item) => item.total_tokens), 1);
  chart.innerHTML = daily.map((item) => `<div class="chart-row">
    <time>${new Date(`${item.date}T12:00:00`).toLocaleDateString("en-US", { day: "2-digit", month: "short" })}</time>
    <div class="bar-track"><div class="bar" style="width:${(item.total_tokens / maximum) * 100}%"></div></div>
    <strong>${number.format(item.total_tokens)}</strong><span>${money(item.estimated_cost_usd)}</span>
  </div>`).join("");
}

function renderTurns(turns) {
  const body = document.querySelector("#turn-list");
  if (!turns.length) { body.innerHTML = '<tr><td colspan="12">No data yet.</td></tr>'; return; }
  body.innerHTML = turns.map((turn) => `<tr>
    <td>${new Date(turn.created_at).toLocaleString("en-US")}</td><td>${turn.source}</td><td>${pipelineLabel(turn.pipeline)}</td>
    <td>${componentLabel(turn.stt_provider, turn.stt_model)}</td><td>${componentLabel(turn.llm_provider, turn.model)}</td>
    <td>${componentLabel(turn.tts_provider, turn.tts_model)}</td>
    <td>${number.format(turn.input_tokens)}</td><td>${number.format(turn.cached_input_tokens)}</td>
    <td>${number.format(turn.output_tokens)}</td><td>${number.format(turn.total_tokens)}</td>
    <td>${money(turn.estimated_cost_usd)}</td><td>${turn.total_seconds == null ? "—" : `${turn.total_seconds.toFixed(2)} s`}</td>
  </tr>`).join("");
}

async function loadDashboard() {
  text("dashboard-error", "");
  try {
    const days = daysSelect.value;
    const [summaryResponse, turnsResponse, systemResponse] = await Promise.all([
      fetch(`/api/usage/summary?days=${days}`), fetch(`/api/usage/turns?days=${days}&limit=100`), fetch("/api/system/info"),
    ]);
    if (!summaryResponse.ok || !turnsResponse.ok || !systemResponse.ok) throw new Error("The dashboard could not be loaded.");
    const summary = await summaryResponse.json();
    const recent = await turnsResponse.json();
    const system = await systemResponse.json();
    const totals = summary.totals;
    text("turns", number.format(totals.turns)); text("tokens", number.format(totals.total_tokens));
    text("input-tokens", number.format(totals.input_tokens)); text("output-tokens", number.format(totals.output_tokens));
    text("cached-tokens", number.format(totals.cached_input_tokens)); text("cost", money(totals.estimated_cost_usd));
    text("pricing-note", `USD estimate for ${summary.pricing.model} · pricing dated ${new Date(`${summary.pricing.effective_date}T12:00:00`).toLocaleDateString("en-US")}`);
    renderTechnology(system); renderChart(summary.daily); renderTurns(recent.turns);
  } catch (error) { text("dashboard-error", error.message); }
}

async function applyLlm() {
  applyButton.disabled = true;
  text("llm-switch-status", "Applying…");
  try {
    const response = await fetch("/api/system/llm", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: providerSelect.value, model: modelSelect.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The LLM could not be changed.");
    text("llm-switch-status", `Active: ${providerLabel(result.provider)} / ${result.model}`);
    await loadDashboard();
  } catch (error) { text("llm-switch-status", error.message); applyButton.disabled = false; }
}

async function applyVoiceModel(component) {
  const controls = voiceControls[component];
  controls.apply.disabled = true;
  text(`${component}-switch-status`, "Loading model…");
  try {
    const response = await fetch(`/api/system/${component}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: controls.provider.value, model: controls.model.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `The ${component.toUpperCase()} model could not be changed.`);
    text(`${component}-switch-status`, `Active: ${providerLabel(result.provider)} / ${result.model_label}`);
    await loadDashboard();
  } catch (error) {
    text(`${component}-switch-status`, error.message);
    controls.apply.disabled = false;
  }
}

async function setAssistantState() {
  const requested = assistantToggle.checked;
  assistantToggle.disabled = true;
  text("assistant-status", requested ? "Starting…" : "Stopping…");
  try {
    const response = await fetch("/api/system/assistant", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: requested }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The assistant state could not be changed.");
    renderAssistantState(result.enabled);
  } catch (error) {
    assistantToggle.checked = !requested;
    text("assistant-status", error.message);
  } finally {
    assistantToggle.disabled = false;
  }
}

providerSelect.addEventListener("change", () => populateModels());
voiceControls.stt.provider.addEventListener("change", () => populateVoiceModels("stt"));
voiceControls.tts.provider.addEventListener("change", () => populateVoiceModels("tts"));
daysSelect.addEventListener("change", loadDashboard);
applyButton.addEventListener("click", applyLlm);
voiceControls.stt.apply.addEventListener("click", () => applyVoiceModel("stt"));
voiceControls.tts.apply.addEventListener("click", () => applyVoiceModel("tts"));
assistantToggle.addEventListener("change", setAssistantState);
loadDashboard();
