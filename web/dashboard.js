const number = new Intl.NumberFormat("en-US");
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 6 });
const daysSelect = document.querySelector("#days");
const providerSelect = document.querySelector("#llm-provider");
const modelSelect = document.querySelector("#llm-model");
const applyButton = document.querySelector("#apply-llm");
const assistantToggle = document.querySelector("#assistant-enabled");
const interruptButton = document.querySelector("#interrupt-assistant");
const pipelineSelect = document.querySelector("#voice-pipeline");
const realtimeModelSelect = document.querySelector("#realtime-model");
const realtimeVoiceSelect = document.querySelector("#realtime-voice");
const applyPipelineButton = document.querySelector("#apply-pipeline");
const promptInput = document.querySelector("#assistant-prompt");
const savePromptButton = document.querySelector("#save-prompt");
const resetPromptButton = document.querySelector("#reset-prompt");
let llmOptions = [];
let assistantInterruptAvailable = false;
let promptState = null;
let promptDirty = false;
const voiceControls = Object.fromEntries(["stt", "tts"].map((component) => [component, {
  provider: document.querySelector(`#${component}-provider`),
  model: document.querySelector(`#${component}-model`),
  apply: document.querySelector(`#apply-${component}`),
  options: [],
}]));

function text(id, value) { document.querySelector(`#${id}`).textContent = value; }
function money(value) { return value == null ? "No cloud price" : usd.format(value); }
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}
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

function renderAssistantState(enabled, interruptAvailable = assistantInterruptAvailable) {
  assistantInterruptAvailable = interruptAvailable;
  assistantToggle.checked = enabled;
  text("assistant-toggle-label", enabled ? "On" : "Off");
  text("assistant-status", enabled
    ? "Listening for a voice request"
    : "Paused — microphone capture and AI processing are off");
  document.querySelector(".assistant-control").classList.toggle("paused", !enabled);
  interruptButton.disabled = !enabled || !interruptAvailable;
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
  renderAssistantState(info.assistant.enabled, info.assistant.interrupt_available);
  text("app-version", `v${info.version}`);
  text("tech-llm", info.llm.model);
  text("tech-llm-mode", `LLM · ${info.llm.processing}`);
  const speed = info.llm.tokens_per_second == null ? "" : ` · ${info.llm.tokens_per_second.toFixed(1)} tokens/s`;
  text("tech-llm-detail", `${providerLabel(info.llm.provider)} · ${info.llm.processing} processing${speed}`);
  const realtime = info.pipeline.id === "openai-realtime";
  text("processing-note", realtime
    ? `Audio is processed by OpenAI Realtime using ${info.pipeline.realtime_model} and the ${info.pipeline.realtime_voice} voice.`
    : info.llm.provider === "openai"
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
  text("tech-audio-detail", `threshold ${info.audio.vad_threshold} · ending silence ${info.audio.ending_silence_seconds.toFixed(1)} s · voice interruption ${info.audio.barge_in ? "on" : "off"} · HTTPS ${info.audio.tls ? "on" : "off"}`);
  llmOptions = info.llm.options;
  providerSelect.innerHTML = llmOptions.map((option) => `<option value="${option.provider}">${providerLabel(option.provider)}${option.available ? "" : " (unavailable)"}</option>`).join("");
  providerSelect.value = info.llm.provider;
  populateModels(info.llm.model);
  configureVoiceSelector("stt", info.stt);
  configureVoiceSelector("tts", info.tts);
  pipelineSelect.innerHTML = info.pipeline.options.map((option) =>
    `<option value="${option.id}"${option.available ? "" : " disabled"}>${option.label}${option.available ? "" : " (unavailable)"}</option>`
  ).join("");
  pipelineSelect.value = info.pipeline.id;
  realtimeModelSelect.innerHTML = info.pipeline.realtime_models.map((model) => `<option value="${model}">${model}</option>`).join("");
  realtimeModelSelect.value = info.pipeline.realtime_model;
  realtimeVoiceSelect.innerHTML = info.pipeline.realtime_voices.map((voice) => `<option value="${voice}">${voice}</option>`).join("");
  realtimeVoiceSelect.value = info.pipeline.realtime_voice;
  document.querySelectorAll(".chained-control select, .chained-control button").forEach((control) => { control.disabled = realtime; });
  realtimeModelSelect.disabled = !realtime;
  realtimeVoiceSelect.disabled = !realtime;
}

function renderPrompt(prompt, { force = false } = {}) {
  promptState = prompt;
  promptInput.maxLength = prompt.max_characters;
  if (force || !promptDirty) {
    promptInput.value = prompt.instructions;
    promptDirty = false;
  }
  text("prompt-revision", `Revision ${prompt.revision}${prompt.is_default ? " · default" : ""}`);
  updatePromptControls();
}

function updatePromptControls() {
  const length = promptInput.value.length;
  const maximum = promptState?.max_characters || Number(promptInput.maxLength) || 0;
  text("prompt-count", `${number.format(length)} / ${number.format(maximum)} characters`);
  savePromptButton.disabled = !promptState || !promptInput.value.trim() || !promptDirty || length > maximum;
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
  const list = document.querySelector("#turn-list");
  if (!turns.length) { list.innerHTML = '<p class="empty">No data yet.</p>'; return; }
  list.innerHTML = turns.map((turn) => {
    const technologies = [
      ["STT", componentLabel(turn.stt_provider, turn.stt_model)],
      ["LLM", componentLabel(turn.llm_provider, turn.model)],
      ["TTS / voice", componentLabel(turn.tts_provider, turn.tts_model)],
    ];
    const metrics = [
      ["Input", number.format(turn.input_tokens)],
      ["Cached", number.format(turn.cached_input_tokens)],
      ["Output", number.format(turn.output_tokens)],
      ["Audio input", number.format(turn.audio_input_tokens)],
      ["Audio output", number.format(turn.audio_output_tokens)],
      ["Total tokens", number.format(turn.total_tokens)],
      ["Model time", turn.total_seconds == null ? "—" : `${turn.total_seconds.toFixed(2)} s`],
    ];
    return `<article class="turn-card">
      <header class="turn-card-header">
        <div>
          <time datetime="${escapeHtml(turn.created_at)}">${escapeHtml(new Date(turn.created_at).toLocaleString("en-US"))}</time>
          <div class="turn-badges"><span>${escapeHtml(turn.source)}</span><span>${escapeHtml(pipelineLabel(turn.pipeline))}</span></div>
        </div>
        <div class="turn-cost"><span>Estimated cost</span><strong>${escapeHtml(money(turn.estimated_cost_usd))}</strong></div>
      </header>
      <div class="turn-technologies">${technologies.map(([label, value]) =>
        `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`
      ).join("")}</div>
      <dl class="turn-metrics">${metrics.map(([label, value]) =>
        `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`
      ).join("")}</dl>
    </article>`;
  }).join("");
}

async function loadDashboard() {
  text("dashboard-error", "");
  try {
    const days = daysSelect.value;
    const [summaryResponse, turnsResponse, systemResponse, promptResponse] = await Promise.all([
      fetch(`/api/usage/summary?days=${days}`), fetch(`/api/usage/turns?days=${days}&limit=100`), fetch("/api/system/info"), fetch("/api/system/prompt"),
    ]);
    if (!summaryResponse.ok || !turnsResponse.ok || !systemResponse.ok || !promptResponse.ok) throw new Error("The dashboard could not be loaded.");
    const summary = await summaryResponse.json();
    const recent = await turnsResponse.json();
    const system = await systemResponse.json();
    const prompt = await promptResponse.json();
    const totals = summary.totals;
    text("turns", number.format(totals.turns)); text("tokens", number.format(totals.total_tokens));
    text("input-tokens", number.format(totals.input_tokens)); text("output-tokens", number.format(totals.output_tokens));
    text("cached-tokens", number.format(totals.cached_input_tokens)); text("cost", money(totals.estimated_cost_usd));
    text("audio-input-tokens", number.format(totals.audio_input_tokens)); text("audio-output-tokens", number.format(totals.audio_output_tokens));
    text("pricing-note", "USD estimates use the dated price snapshot stored with each turn.");
    renderTechnology(system); renderPrompt(prompt); renderChart(summary.daily); renderTurns(recent.turns);
  } catch (error) { text("dashboard-error", error.message); }
}

async function savePrompt() {
  savePromptButton.disabled = true;
  resetPromptButton.disabled = true;
  text("prompt-status", "Saving…");
  try {
    const response = await fetch("/api/system/prompt", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instructions: promptInput.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The assistant behavior could not be saved.");
    promptDirty = false;
    renderPrompt(result, { force: true });
    text("prompt-status", "Saved. Active sessions update automatically for the next turn.");
  } catch (error) {
    text("prompt-status", error.message);
  } finally {
    resetPromptButton.disabled = false;
    updatePromptControls();
  }
}

async function resetPrompt() {
  savePromptButton.disabled = true;
  resetPromptButton.disabled = true;
  text("prompt-status", "Restoring default…");
  try {
    const response = await fetch("/api/system/prompt/reset", { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The default behavior could not be restored.");
    promptDirty = false;
    renderPrompt(result, { force: true });
    text("prompt-status", "Default behavior restored.");
  } catch (error) {
    text("prompt-status", error.message);
  } finally {
    resetPromptButton.disabled = false;
    updatePromptControls();
  }
}

async function applyPipeline() {
  applyPipelineButton.disabled = true;
  text("pipeline-switch-status", "Applying…");
  try {
    const response = await fetch("/api/system/pipeline", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipeline: pipelineSelect.value, model: realtimeModelSelect.value, voice: realtimeVoiceSelect.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The voice pipeline could not be changed.");
    text("pipeline-switch-status", `Active: ${pipelineLabel(result.pipeline)}`);
    await loadDashboard();
  } catch (error) {
    text("pipeline-switch-status", error.message);
  } finally {
    applyPipelineButton.disabled = false;
  }
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

async function interruptAssistant() {
  interruptButton.disabled = true;
  text("interrupt-status", "Stopping…");
  try {
    const response = await fetch("/api/system/assistant/interrupt", { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "The response could not be stopped.");
    text("interrupt-status", result.interrupted ? "Response stopped. Listening again." : "No active response.");
  } catch (error) {
    text("interrupt-status", error.message);
  } finally {
    interruptButton.disabled = !assistantToggle.checked || !assistantInterruptAvailable;
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
interruptButton.addEventListener("click", interruptAssistant);
pipelineSelect.addEventListener("change", () => {
  const realtime = pipelineSelect.value === "openai-realtime";
  realtimeModelSelect.disabled = !realtime;
  realtimeVoiceSelect.disabled = !realtime;
});
applyPipelineButton.addEventListener("click", applyPipeline);
promptInput.addEventListener("input", () => { promptDirty = true; text("prompt-status", "Unsaved changes"); updatePromptControls(); });
savePromptButton.addEventListener("click", savePrompt);
resetPromptButton.addEventListener("click", resetPrompt);
loadDashboard();
