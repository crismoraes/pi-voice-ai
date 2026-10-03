const number = new Intl.NumberFormat("en-US");
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 6 });
const daysSelect = document.querySelector("#days");
const providerSelect = document.querySelector("#llm-provider");
const modelSelect = document.querySelector("#llm-model");
const applyButton = document.querySelector("#apply-llm");
let llmOptions = [];

function text(id, value) { document.querySelector(`#${id}`).textContent = value; }
function money(value) { return value == null ? "No cloud price" : usd.format(value); }
function providerLabel(provider) { return provider === "openai" ? "OpenAI" : "Local (llama.cpp)"; }

function populateModels(selectedModel) {
  const option = llmOptions.find((item) => item.provider === providerSelect.value);
  modelSelect.innerHTML = (option?.models || []).map((model) => `<option value="${model}">${model}</option>`).join("");
  if (selectedModel && option?.models.includes(selectedModel)) modelSelect.value = selectedModel;
  applyButton.disabled = !option?.available;
  text("llm-switch-status", option?.available ? "" : "Provider unavailable");
}

function renderTechnology(info) {
  text("app-version", `v${info.version}`);
  text("tech-llm", info.llm.model);
  text("tech-llm-mode", `LLM · ${info.llm.processing}`);
  const speed = info.llm.tokens_per_second == null ? "" : ` · ${info.llm.tokens_per_second.toFixed(1)} tokens/s`;
  text("tech-llm-detail", `${providerLabel(info.llm.provider)} · ${info.llm.processing} processing${speed}`);
  text("processing-note", info.llm.provider === "openai"
    ? "Audio, STT, and TTS stay on the Raspberry Pi. Only text is sent to OpenAI."
    : "The complete voice pipeline, including the LLM, is running locally on the Raspberry Pi.");
  text("tech-stt", info.stt.model);
  const normalization = info.stt.normalization ? `normalization to ${info.stt.target_peak} · max gain ${info.stt.max_gain}×` : "no normalization";
  text("tech-stt-detail", `${info.stt.engine} · ${info.stt.language} · ${info.stt.precision.toUpperCase()} · ${info.stt.threads} threads · ${normalization}`);
  text("tech-tts", info.tts.model);
  text("tech-tts-detail", `${info.tts.engine} · ${info.tts.threads} threads`);
  text("tech-audio", `${info.audio.mode.toUpperCase()} · ${info.audio.vad}`);
  text("tech-audio-detail", `threshold ${info.audio.vad_threshold} · ending silence ${info.audio.ending_silence_seconds.toFixed(1)} s · HTTPS ${info.audio.tls ? "on" : "off"}`);
  llmOptions = info.llm.options;
  providerSelect.innerHTML = llmOptions.map((option) => `<option value="${option.provider}">${providerLabel(option.provider)}${option.available ? "" : " (unavailable)"}</option>`).join("");
  providerSelect.value = info.llm.provider;
  populateModels(info.llm.model);
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
  if (!turns.length) { body.innerHTML = '<tr><td colspan="9">No data yet.</td></tr>'; return; }
  body.innerHTML = turns.map((turn) => `<tr>
    <td>${new Date(turn.created_at).toLocaleString("en-US")}</td><td>${turn.source}</td><td>${turn.model}</td>
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

providerSelect.addEventListener("change", () => populateModels());
daysSelect.addEventListener("change", loadDashboard);
applyButton.addEventListener("click", applyLlm);
loadDashboard();
