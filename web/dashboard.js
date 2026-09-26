const number = new Intl.NumberFormat("pt-BR");
const usd = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 6 });
const daysSelect = document.querySelector("#days");

function text(id, value) { document.querySelector(`#${id}`).textContent = value; }
function money(value) { return value == null ? "Sem tarifa" : usd.format(value); }

function renderChart(daily) {
  const chart = document.querySelector("#chart");
  if (!daily.length) { chart.innerHTML = '<p class="empty">Ainda não há dados.</p>'; return; }
  const maximum = Math.max(...daily.map((item) => item.total_tokens), 1);
  chart.innerHTML = daily.map((item) => `
    <div class="chart-row">
      <time>${new Date(`${item.date}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })}</time>
      <div class="bar-track"><div class="bar" style="width:${(item.total_tokens / maximum) * 100}%"></div></div>
      <strong>${number.format(item.total_tokens)}</strong><span>${money(item.estimated_cost_usd)}</span>
    </div>`).join("");
}

function renderTurns(turns) {
  const body = document.querySelector("#turn-list");
  if (!turns.length) { body.innerHTML = '<tr><td colspan="9">Ainda não há dados.</td></tr>'; return; }
  body.innerHTML = turns.map((turn) => `<tr>
    <td>${new Date(turn.created_at).toLocaleString("pt-BR")}</td><td>${turn.source}</td><td>${turn.model}</td>
    <td>${number.format(turn.input_tokens)}</td><td>${number.format(turn.cached_input_tokens)}</td>
    <td>${number.format(turn.output_tokens)}</td><td>${number.format(turn.total_tokens)}</td>
    <td>${money(turn.estimated_cost_usd)}</td><td>${turn.total_seconds == null ? "—" : `${turn.total_seconds.toFixed(2)} s`}</td>
  </tr>`).join("");
}

async function loadDashboard() {
  text("dashboard-error", "");
  try {
    const days = daysSelect.value;
    const [summaryResponse, turnsResponse] = await Promise.all([
      fetch(`/api/usage/summary?days=${days}`), fetch(`/api/usage/turns?days=${days}&limit=100`),
    ]);
    if (!summaryResponse.ok || !turnsResponse.ok) throw new Error("Não foi possível carregar o histórico.");
    const summary = await summaryResponse.json();
    const recent = await turnsResponse.json();
    const totals = summary.totals;
    text("turns", number.format(totals.turns)); text("tokens", number.format(totals.total_tokens));
    text("input-tokens", number.format(totals.input_tokens)); text("output-tokens", number.format(totals.output_tokens));
    text("cached-tokens", number.format(totals.cached_input_tokens)); text("cost", money(totals.estimated_cost_usd));
    text("pricing-note", `Estimativa em USD para ${summary.pricing.model} · preços de ${new Date(`${summary.pricing.effective_date}T12:00:00`).toLocaleDateString("pt-BR")}`);
    renderChart(summary.daily); renderTurns(recent.turns);
  } catch (error) { text("dashboard-error", error.message); }
}

daysSelect.addEventListener("change", loadDashboard);
loadDashboard();
