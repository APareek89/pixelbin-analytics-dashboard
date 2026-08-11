const WINDOW_DAYS = Number(document.body.dataset.window || 7);
const PERIOD_LINKS = [
  { days: 7, label: "Past 7 days", href: "./" },
  { days: 30, label: "Past 30 days", href: "30-days.html" },
  { days: 90, label: "Past 90 days", href: "90-days.html" },
];
const SERIES_COLORS = ["#60a5fa", "#a78bfa", "#34d399", "#ff7340"];
const charts = [];

const fmt = (value) => {
  const number = Number(value || 0);
  if (number >= 1e6) return `${(number / 1e6).toFixed(2)}M`;
  if (number >= 1e3) return `${(number / 1e3).toFixed(1)}k`;
  return Math.round(number).toLocaleString();
};
const pct = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const sum = (values) => values.reduce((total, value) => total + Number(value || 0), 0);
const average = (values) => (values.length ? sum(values) / values.length : 0);
const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

function dateRange(endDate, days) {
  const end = new Date(`${endDate}T00:00:00Z`);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days + 1);
  const labels = [];
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    labels.push(cursor.toISOString().slice(0, 10));
  }
  return labels;
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(date);
}

function formatBuiltAt(value) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

function seriesFromDaily(daily, labels) {
  return labels.map((date) => Number(daily?.[date] || 0));
}

function propertyRows(daily, labels) {
  const indexed = Object.fromEntries(daily.map((row) => [row.date, row]));
  return labels.map((date) => indexed[date] || {
    date, sessions: 0, activeUsers: 0, pageViews: 0, organicSessions: 0, bounceRate: 0, engagementRate: 0,
  });
}

function chartOptions(labels, percentAxis = false) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: WINDOW_DAYS <= 30 ? { duration: 420 } : false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        display: true,
        position: "bottom",
        labels: { color: "#34324A", boxWidth: 9, boxHeight: 9, padding: 10, font: { size: 9, family: "Inter" } },
      },
      tooltip: {
        backgroundColor: "#fff", borderColor: "#ECE7F8", borderWidth: 1, titleColor: "#34324A", bodyColor: "#34324A",
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: "#6E6D74", maxTicksLimit: WINDOW_DAYS <= 7 ? 7 : 12, font: { size: 9 }, callback(index) { return shortDate(labels[index]); } },
      },
      y: {
        beginAtZero: true,
        grid: { color: "#ECE7F8" },
        ticks: { color: "#6E6D74", font: { size: 9 }, callback: (value) => percentAxis ? `${value}%` : fmt(value) },
      },
    },
  };
}

function baseDataset(label, data, color, index) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: `${color}${index === 0 ? "18" : "0D"}`,
    fill: index === 0,
    tension: 0.32,
    pointRadius: WINDOW_DAYS <= 7 ? 2.8 : WINDOW_DAYS <= 30 ? 1.5 : 0,
    pointHoverRadius: 4,
    borderWidth: index === 0 ? 2.3 : 1.7,
  };
}

function pageShell(data, labels) {
  const start = labels[0];
  const end = labels.at(-1);
  const propertyTabs = [
    { id: "overview", label: "GA4 Overview" },
    { id: "ai-tools", label: "AI Tools · Top 10" },
    { id: "pixelbin", label: "Pixelbin Product" },
    { id: "wm", label: "WatermarkRemover.io" },
    { id: "um", label: "Upscale.media" },
  ];
  return `
    <main class="shell">
      <header class="brand-bar">
        <div class="brand-left"><a class="brand-wordmark" href="https://www.pixelbin.io" target="_blank" rel="noreferrer"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span>pixelbin</span><small>.io</small></a></div>
        <div class="brand-center"><h1>Growth <span class="gradient-text">Dashboard</span></h1><p>GA4 product and acquisition trends across Pixelbin, Watermark Remover, and Upscale Media</p></div>
        <div class="brand-right"><span class="chip">Refreshed ${esc(formatBuiltAt(data.generatedAt))}</span></div>
      </header>
      <nav class="period-nav" aria-label="Dashboard period">${PERIOD_LINKS.map((item) => `<a class="period-link${item.days === WINDOW_DAYS ? " active" : ""}" href="${item.href}">${item.label}</a>`).join("")}</nav>
      <nav class="tab-nav" aria-label="Dashboard sections">${propertyTabs.map((tab, index) => `<button class="tab-button${index === 0 ? " active" : ""}" data-tab="${tab.id}">${tab.label}</button>`).join("")}</nav>
      <section class="tab-panel active" id="panel-overview"></section>
      <section class="tab-panel" id="panel-ai-tools"></section>
      <section class="tab-panel" id="panel-pixelbin"></section>
      <section class="tab-panel" id="panel-wm"></section>
      <section class="tab-panel" id="panel-um"></section>
      <footer>GA4 Data API · ${esc(start)} to ${esc(end)} · ${data.range.todayPartial ? "Today is partial" : "Complete days"} · Property timezone</footer>
    </main>
    <div class="modal-backdrop" id="mapping-modal"><div class="modal" id="mapping-content"></div></div>`;
}

function introHtml(title, text, labels, chips = "") {
  return `<div class="card intro"><div><p class="eyebrow">${WINDOW_DAYS}-day view</p><h2>${esc(title)}</h2><p>${text}</p></div><div class="range-box">${chips}<span>Reporting range</span><strong>${esc(shortDate(labels[0]))} – ${esc(shortDate(labels.at(-1)))} 2026</strong><span>Today is partial</span></div></div>`;
}

function renderOverview(data, labels) {
  const panel = document.getElementById("panel-overview");
  panel.innerHTML = introHtml(
    "Audience and acquisition overview",
    "Daily sessions, active users and Organic Search sessions for all three GA4 properties. KPI totals and chart density follow the selected window.",
    labels,
  ) + `<div class="property-grid">${Object.entries(data.properties).map(([key, property]) => {
    const rows = propertyRows(property.daily, labels);
    const sessions = rows.map((row) => row.sessions);
    const active = rows.map((row) => row.activeUsers);
    const pageViews = rows.map((row) => row.pageViews);
    const organic = rows.map((row) => row.organicSessions);
    const bounce = rows.filter((row) => row.sessions > 0).map((row) => row.bounceRate);
    return `<article class="card property-card" style="--property-color:${esc(property.color)}">
      <div class="property-head"><div><h3>${esc(property.label)}</h3><div class="property-id">Property ${esc(property.id)}</div></div><span class="chip gray">Daily</span></div>
      <div class="kpi-grid">
        <div class="kpi"><div class="kpi-label">Sessions</div><div class="kpi-value">${fmt(sum(sessions))}</div></div>
        <div class="kpi"><div class="kpi-label">Avg DAU</div><div class="kpi-value">${fmt(average(active))}</div></div>
        <div class="kpi"><div class="kpi-label">Pageviews</div><div class="kpi-value">${fmt(sum(pageViews))}</div></div>
        <div class="kpi"><div class="kpi-label">Organic</div><div class="kpi-value">${fmt(sum(organic))}</div></div>
        <div class="kpi"><div class="kpi-label">Bounce</div><div class="kpi-value">${pct(average(bounce))}</div></div>
      </div>
      <div class="property-chart"><canvas id="property-${key}"></canvas></div>
    </article>`;
  }).join("")}</div>`;

  Object.entries(data.properties).forEach(([key, property]) => {
    const rows = propertyRows(property.daily, labels);
    const datasets = [
      baseDataset("Sessions", rows.map((row) => row.sessions), property.color, 0),
      baseDataset("Active users", rows.map((row) => row.activeUsers), "#9770FF", 1),
      baseDataset("Organic sessions", rows.map((row) => row.organicSessions), "#FF7340", 2),
    ];
    charts.push(new Chart(document.getElementById(`property-${key}`), { type: "line", data: { labels, datasets }, options: chartOptions(labels) }));
  });
}

function eventTotal(event, labels) {
  return sum(seriesFromDaily(event.daily, labels));
}

function aiToolSummary(tools, labels) {
  return `<div class="card summary-wrap"><table class="summary-table"><thead><tr><th>90d rank / AI tool</th><th>Pageviews</th><th>Input</th><th>Action</th><th>Output</th><th>Event mapping</th></tr></thead><tbody>${tools.map((tool) => {
    const events = tool.events;
    return `<tr><td><div class="tool-name"><span class="rank">${tool.rank}</span><div><strong>${esc(tool.name)}</strong><div class="slug">/ai-tools/${esc(tool.slug)}</div></div></div></td><td>${fmt(sum(seriesFromDaily(tool.pageViews, labels)))}</td>${[0, 1, 2].map((index) => `<td>${events[index] ? fmt(eventTotal(events[index], labels)) : "—"}</td>`).join("")}<td><span class="chip gray">${events.length ? esc(events[0].source.replace("_", " ")) : "pageview only"}</span></td></tr>`;
  }).join("")}</tbody></table></div>`;
}

function toolCardHtml(tool, labels, index) {
  const series = [{ name: "page_view", daily: tool.pageViews, source: "page_path" }, ...tool.events].slice(0, 4);
  return `<article class="card chart-card">
    <div class="chart-head"><div class="chart-head-left"><p class="eyebrow">#${tool.rank} by 90-day traffic</p><h3>${esc(tool.name)}</h3><div class="meta">/ai-tools/${esc(tool.slug)}</div></div><div class="chart-head-actions"><span class="chip green">${fmt(sum(seriesFromDaily(tool.pageViews, labels)))} views</span><button class="info-button" data-tool-index="${index}" aria-label="Show event mapping">i</button></div></div>
    <div class="mini-kpis">${series.map((item, seriesIndex) => `<div class="mini-kpi" style="--series-color:${SERIES_COLORS[seriesIndex]}"><span title="${esc(item.name)}">${esc(item.name)}</span><strong>${fmt(sum(seriesFromDaily(item.daily, labels)))}</strong></div>`).join("")}</div>
    <div class="canvas-wrap"><canvas id="ai-tool-${index}"></canvas></div>
    <div class="source-note">Associated events are observed on this tool's page, content group, or exact <code>app_name</code>. They are directional product signals, not a strict same-session funnel.</div>
  </article>`;
}

function renderAiTools(data, labels) {
  const panel = document.getElementById("panel-ai-tools");
  const tools = data.aiTools.tools;
  panel.innerHTML = introHtml(
    "Top 10 AI tools by traffic",
    `${esc(data.aiTools.selectionRule)} Product events were discovered from page_path, app_name and content_group evidence rather than assigned from a generic event list.`,
    labels,
    `<span class="chip orange">Stable 90-day ranking</span>`,
  ) + aiToolSummary(tools, labels) + `<div class="section-title"><div><h2>Tool-level traffic and product actions</h2><p>Each chart combines page views with up to three tool-specific input, action and output events.</p></div><span class="chip">10 tools · ${WINDOW_DAYS} days</span></div><div class="chart-grid">${tools.map((tool, index) => toolCardHtml(tool, labels, index)).join("")}</div>`;

  tools.forEach((tool, index) => {
    const series = [{ name: "page_view", daily: tool.pageViews }, ...tool.events].slice(0, 4);
    const datasets = series.map((item, seriesIndex) => baseDataset(item.name, seriesFromDaily(item.daily, labels), SERIES_COLORS[seriesIndex], seriesIndex));
    charts.push(new Chart(document.getElementById(`ai-tool-${index}`), { type: "line", data: { labels, datasets }, options: chartOptions(labels) }));
  });
  panel.querySelectorAll(".info-button").forEach((button) => {
    button.addEventListener("click", () => openMapping(tools[Number(button.dataset.toolIndex)]));
  });
}

function flowCardHtml(flow, propertyKey, labels, index) {
  return `<article class="card chart-card"><div class="chart-head"><div class="chart-head-left"><p class="eyebrow">${esc(flow.scope)}</p><h3>${esc(flow.name)}</h3><div class="meta">${esc(flow.slug)}</div></div>${flow.queryError ? '<span class="chip orange">Query unavailable</span>' : '<span class="chip gray">GA4 events</span>'}</div><div class="mini-kpis">${flow.events.map((event, eventIndex) => `<div class="mini-kpi" style="--series-color:${SERIES_COLORS[eventIndex]}"><span title="${esc(event.name)}">${esc(event.name)}</span><strong>${fmt(eventTotal(event, labels))}</strong></div>`).join("")}</div><div class="canvas-wrap"><canvas id="flow-${propertyKey}-${index}"></canvas></div></article>`;
}

function renderFlows(data, labels, propertyKey) {
  const panel = document.getElementById(`panel-${propertyKey}`);
  const property = data.properties[propertyKey];
  const flows = data.flows[propertyKey] || [];
  panel.innerHTML = introHtml(
    `${property.label} product events`,
    "Established product-event flows retained from the growth dashboard and re-queried for the selected reporting window.",
    labels,
    `<span class="chip">Property ${esc(property.id)}</span>`,
  ) + `<div class="chart-grid">${flows.length ? flows.map((flow, index) => flowCardHtml(flow, propertyKey, labels, index)).join("") : '<div class="card empty-note">No configured product flows.</div>'}</div>`;
  flows.forEach((flow, index) => {
    const datasets = flow.events.map((event, eventIndex) => baseDataset(event.name, seriesFromDaily(event.daily, labels), SERIES_COLORS[eventIndex], eventIndex));
    charts.push(new Chart(document.getElementById(`flow-${propertyKey}-${index}`), { type: "line", data: { labels, datasets }, options: chartOptions(labels) }));
  });
}

function openMapping(tool) {
  const modal = document.getElementById("mapping-modal");
  const paths = tool.topPaths.map((item) => `${item.path} · ${fmt(item.pageViews)} pageviews`).join("\n");
  document.getElementById("mapping-content").innerHTML = `<div class="modal-head"><div><p class="eyebrow">Event attribution</p><h3>${esc(tool.name)}</h3><div class="meta">/ai-tools/${esc(tool.slug)}</div></div><button class="close-button" id="close-modal">Close</button></div><ul class="mapping-list"><li><span class="chip gray">Traffic</span><code>page_view</code><strong>${fmt(tool.pageViewTotal90d)}</strong></li>${tool.events.map((event) => `<li><span class="chip ${event.stage === "output" ? "green" : event.stage === "action" ? "orange" : ""}">${esc(event.stage)}</span><code>${esc(event.name)}</code><span>${esc(event.source.replace("_", " "))}</span></li>`).join("")}</ul><div class="path-box">Top observed paths\n${esc(paths)}</div><p class="source-note">${esc(tool.trackingNote)} Selection favors a complete three-stage event family from one exact attribution scope.</p>`;
  modal.classList.add("open");
  document.getElementById("close-modal").onclick = () => modal.classList.remove("open");
}

function setupTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${button.dataset.tab}`));
      setTimeout(() => charts.forEach((chart) => chart.resize()), 40);
    });
  });
  const modal = document.getElementById("mapping-modal");
  modal.addEventListener("click", (event) => { if (event.target === modal) modal.classList.remove("open"); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") modal.classList.remove("open"); });
}

async function init() {
  try {
    const response = await fetch("data/dashboard.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Dashboard data returned ${response.status}`);
    const data = await response.json();
    const labels = dateRange(data.range.end, WINDOW_DAYS);
    document.getElementById("app").innerHTML = pageShell(data, labels);
    renderOverview(data, labels);
    renderAiTools(data, labels);
    renderFlows(data, labels, "pixelbin");
    renderFlows(data, labels, "wm");
    renderFlows(data, labels, "um");
    setupTabs();
  } catch (error) {
    document.getElementById("app").innerHTML = `<div class="loading"><strong>Dashboard could not load.</strong><br />${esc(error.message)}</div>`;
  }
}

init();
