const state = {
  tier: "quick",
  running: false,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", async () => {
  bindControls();
  await loadStatus();
  await loadBars();
});

function bindControls() {
  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".segment").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.tier = button.dataset.tier;
      if (state.tier === "quick") {
        $("providerSelect").value = "claude";
      } else if ($("providerSelect").value === "claude") {
        $("providerSelect").value = "both";
      }
    });
  });

  $("runButton").addEventListener("click", runAgent);
  $("resetButton").addEventListener("click", resetState);
}

async function loadStatus() {
  const payload = await fetchJson("/api/status");
  $("agentLine").textContent = `${payload.agent} · ${payload.symbol} · ${payload.market} · ${payload.mode}`;
  setKeyStatus("claudeStatus", "Claude", payload.keys.claude);
  setKeyStatus("miromindStatus", "Miromind", payload.keys.miromind);
}

async function loadBars() {
  const payload = await fetchJson("/api/bars");
  drawChart(payload.bars || []);
}

async function runAgent() {
  setRunning(true, "Running");
  clearReports();
  try {
    const payload = await fetchJson("/api/run", {
      method: "POST",
      body: JSON.stringify({
        with_research: $("researchToggle").checked,
        allow_reprocess: $("reprocessToggle").checked,
        report_tier: state.tier,
        provider: $("providerSelect").value,
      }),
      headers: { "Content-Type": "application/json" },
    });
    renderResult(payload.result);
  } catch (error) {
    $("runState").textContent = "Error";
    $("claudeReport").textContent = String(error);
  } finally {
    setRunning(false);
  }
}

async function resetState() {
  if (!window.confirm("重置纸交易状态？")) return;
  setRunning(true, "Resetting");
  try {
    await fetchJson("/api/reset", { method: "POST" });
    $("metricAction").textContent = "-";
    $("metricReason").textContent = "state_reset";
    $("metricEquity").textContent = "-";
    $("metricCash").textContent = "-";
    $("guidanceBox").innerHTML = "<h3>投资建议区分</h3><p>状态已重置，可以重新运行 agent。</p>";
    clearReports();
  } finally {
    setRunning(false);
  }
}

function renderResult(result) {
  $("metricAction").textContent = result.action || "-";
  $("metricReason").textContent = result.reason || "-";
  $("metricEquity").textContent = money(result.equity_usd);
  $("metricCash").textContent = money(result.cash_usd);
  $("runState").textContent = "Done";

  const research = result.research || {};
  renderGuidance(research.investment_guidance);
  $("claudeTier").textContent = research.tier || "-";
  $("miroTier").textContent = research.tier || "-";
  $("claudeReport").textContent = research.claude_review || "没有 Claude 报告。";
  $("miroReport").textContent = research.miromind_research || "没有 Miromind 报告。";

  const errors = research.errors || {};
  const errorLines = Object.entries(errors).map(([key, value]) => `${key}: ${value}`);
  if (errorLines.length) {
    $("miroReport").textContent += `\n\nErrors\n${errorLines.join("\n")}`;
  }
}

function renderGuidance(guidance) {
  if (!guidance) {
    $("guidanceBox").innerHTML = "<h3>投资建议区分</h3><p>没有生成建议区分。</p>";
    return;
  }

  $("guidanceBox").innerHTML = `
    <h3>投资建议区分</h3>
    <ul>
      <li><strong>规则动作:</strong> ${escapeHtml(guidance.rule_action || "-")}</li>
      <li><strong>规则观点:</strong> ${escapeHtml(guidance.rule_view || "-")}</li>
      <li><strong>执行姿态:</strong> ${escapeHtml(guidance.execution_posture || "-")}</li>
      <li><strong>报告深度:</strong> ${escapeHtml(guidance.research_depth || "-")}</li>
      <li>${escapeHtml(guidance.real_money_note || "")}</li>
    </ul>
  `;
}

function clearReports() {
  $("claudeReport").textContent = "运行中...";
  $("miroReport").textContent = "运行中...";
}

function setKeyStatus(id, label, ok) {
  const el = $(id);
  el.textContent = `${label}: ${ok ? "已配置" : "未配置"}`;
  el.classList.toggle("good", ok);
  el.classList.toggle("bad", !ok);
}

function setRunning(isRunning, label = "Ready") {
  state.running = isRunning;
  $("runButton").disabled = isRunning;
  $("resetButton").disabled = isRunning;
  $("runState").textContent = isRunning ? label : "Ready";
}

function drawChart(bars) {
  const canvas = $("priceChart");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  if (!bars.length) return;

  const closes = bars.map((bar) => bar.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const pad = 26;
  const span = max - min || 1;

  ctx.strokeStyle = "#d8dde6";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = pad + ((height - pad * 2) * i) / 3;
    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "#0f766e";
  ctx.lineWidth = 3;
  ctx.beginPath();
  closes.forEach((close, index) => {
    const x = pad + ((width - pad * 2) * index) / Math.max(1, closes.length - 1);
    const y = height - pad - ((close - min) / span) * (height - pad * 2);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#667085";
  ctx.font = "16px system-ui";
  ctx.fillText(`High ${max.toFixed(2)}`, pad, 20);
  ctx.fillText(`Low ${min.toFixed(2)}`, pad, height - 8);
  $("chartLabel").textContent = `${bars.length} bars`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function money(value) {
  if (typeof value !== "number") return "-";
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
