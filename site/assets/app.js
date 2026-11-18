import { drawChart, lowerBound, sparkline, toTime } from "./chart.js";

const API = "v1";
const CARD_IDS = ["fix", "udis", "tiie-28", "tiie-91", "tiie-182", "tiie-fondeo", "inpc", "inflacion-anual", "salario-minimo-general", "uma-diaria"];
const EXTRA = { "inflacion-anual": ["inflacion-mensual"], "salario-minimo-general": ["salario-minimo-zlfn"], "uma-diaria": ["uma-mensual", "uma-anual"] };

const T = {
  es: {
    skip: "Saltar al contenido", nav: "Secciones", nav_values: "Valores", nav_charts: "Gráficas", nav_converter: "Convertidor", nav_api: "API", nav_sources: "Fuentes",
    kicker: "Datos abiertos · API estática · actualizado por GitHub Actions", today_title: "Último valor publicado",
    title: "Los indicadores oficiales de México, <em>trazables al DOF</em>.",
    lead: "Tipo de cambio FIX, UDIS, TIIE, INPC e inflación, salario mínimo y UMA. Cada valor trae la nota del Diario Oficial de la Federación que lo publicó, y se sirve como JSON y CSV sin cuenta, sin token y con CORS abierto.",
    cta_api: "Usar la API", cta_repo: "Código y datos en GitHub",
    values_title: "Últimos valores", values_sub: "Cada tarjeta enlaza a la nota del DOF. La marca ✓ indica que el valor se comparó con el texto de la nota.",
    loading: "Cargando datos…", charts_title: "Gráficas", charts_sub: "Elige una serie y un periodo. Con el teclado: enfoca la gráfica y usa las flechas, Inicio y Fin.",
    series: "Serie", range: "Periodo", all: "Todo", show_table: "Ver los últimos valores en una tabla",
    conv_title: "Convertidor", conv_sub: "Cálculos en tu navegador con los valores publicados. Informativo: no constituye asesoría legal ni fiscal.",
    udi_title: "Pesos y UDIS en una fecha", date: "Fecha", amount: "Monto", direction: "Dirección", pesos_to_udis: "Pesos a UDIS", udis_to_pesos: "UDIS a pesos",
    inf_title: "Inflación entre dos meses", from_month: "Mes inicial", to_month: "Mes final", amount_optional: "Monto a actualizar (opcional)",
    api_title: "API estática", api_sub: "Archivos JSON y CSV servidos por GitHub Pages, versionados en <code>/v1</code>, con <code>Access-Control-Allow-Origin: *</code>. Sin cuenta, sin token, sin límite publicado más allá del de GitHub Pages.",
    path: "Ruta", what: "Qué contiene",
    ep_index: "Catálogo: series, unidades, qué significa cada fecha, cobertura, último valor y fuentes.",
    ep_latest: "El valor más reciente y el anterior.", ep_year: "Todos los valores de un año.",
    ep_day: "Un día (series diarias). Si ese día no hubo publicación, la respuesta es 404: consulta el año.",
    ep_month: "Un mes (INPC e inflación).", ep_all: "La serie completa, con fuente de cada valor.",
    ep_compact: "Fechas y valores en dos arreglos, para gráficas.", ep_schema: "JSON Schema de cada archivo.",
    examples: "Ejemplos", copy: "Copiar", copied: "Copiado", live_title: "Respuesta real de <code>v1/fix/latest.json</code>",
    src_title: "Fuentes y estatus",
    src_sub: "VERDE: verificado contra el DOF. AMARILLO: fuente oficial con verificación parcial o limitaciones documentadas. ROJO: no verificado. El detalle de cada serie, los errores encontrados en las fuentes y cómo se corrigieron están en <a href=\"https://github.com/BEG-lag/indicadores-mx/blob/main/docs/fuentes.md\">docs/fuentes.md</a>.",
    disclaimer: "Espejo no oficial. Solo el Diario Oficial de la Federación y las instituciones que emiten cada indicador tienen validez oficial. No constituye opinión legal ni asesoría fiscal.",
    author: "Hecho por <strong>Benjamín Esponda García</strong>, abogado mexicano que construye con IA. <a href=\"https://pivotek.mx\">pivotek.mx</a> · <a href=\"https://github.com/BEG-lag/portafolio-ia\">portafolio</a> · <a href=\"https://github.com/BEG-lag/indicadores-mx\">código</a>",
    licenses: "Código bajo licencia MIT. Datos en el dominio público (CC0 1.0). Sin analítica ni cookies. Fuentes tipográficas autoalojadas (SIL OFL 1.1).",
    fresh: (d, n, s) => `Datos al <b>${d}</b> · <b>${n}</b> valores en <b>${s}</b> series`,
    dof: "Nota del DOF", source: "Fuente", checked: "Comparado con el texto de la nota del DOF", not_checked: "Valor del SIDOF, sin comparar con la nota",
    vs_prev: "vs. anterior", monthly: "mensual", annual: "anual", zlfn: "Frontera Norte", in_force: "vigente desde",
    status: "Estatus", coverage: "Cobertura", count: "Valores", with_note: "Con nota DOF", verified: "Verificados",
    ids: "Series:", lang_btn: "EN", lang_label: "Switch to English",
    caption: (name, n, a, b) => `${name}: ${n} valores del ${a} al ${b}.`,
    chart_label: (name, last, date) => `Gráfica de ${name}. Último valor ${last} (${date}).`,
    table_date: "Fecha", table_value: "Valor", load_error: "No se pudieron cargar los datos. Intenta de nuevo más tarde.",
    udi_used: (v, d) => `Valor de la UDI del ${d}: ${v} pesos`, udi_none: (a, b) => `No hay valor de la UDI para esa fecha. Disponible del ${a} al ${b}.`,
    inf_res: (p, f) => `Variación del INPC: ${p} (factor ${f})`, inf_used: (a, va, b, vb) => `INPC ${a}: ${va} · INPC ${b}: ${vb}`,
    inf_none: (a, b) => `Elige meses entre ${a} y ${b}.`, updated_amount: "Monto actualizado", bad_amount: "Escribe un monto válido.",
    see_note: "ver nota del DOF", published_until: "publicada hasta el", unit: "Unidad",
  },
  en: {
    skip: "Skip to content", nav: "Sections", nav_values: "Values", nav_charts: "Charts", nav_converter: "Converter", nav_api: "API", nav_sources: "Sources",
    kicker: "Open data · static API · updated by GitHub Actions", today_title: "Latest published value",
    title: "Mexico's official indicators, <em>traceable to the DOF</em>.",
    lead: "FIX exchange rate, UDIS, TIIE, INPC and inflation, minimum wage and UMA. Every value carries the Diario Oficial de la Federación note that published it, served as JSON and CSV with no account, no token and open CORS.",
    cta_api: "Use the API", cta_repo: "Code and data on GitHub",
    values_title: "Latest values", values_sub: "Each card links to its DOF note. The ✓ mark means the value was compared with the note's text.",
    loading: "Loading data…", charts_title: "Charts", charts_sub: "Pick a series and a period. With the keyboard: focus the chart and use the arrows, Home and End.",
    series: "Series", range: "Period", all: "All", show_table: "Show the latest values in a table",
    conv_title: "Converter", conv_sub: "Computed in your browser with the published values. Informational only: not legal or tax advice.",
    udi_title: "Pesos and UDIS on a date", date: "Date", amount: "Amount", direction: "Direction", pesos_to_udis: "Pesos to UDIS", udis_to_pesos: "UDIS to pesos",
    inf_title: "Inflation between two months", from_month: "From month", to_month: "To month", amount_optional: "Amount to update (optional)",
    api_title: "Static API", api_sub: "JSON and CSV files served by GitHub Pages, versioned under <code>/v1</code>, with <code>Access-Control-Allow-Origin: *</code>. No account, no token, no limit beyond GitHub Pages' own.",
    path: "Path", what: "Contents",
    ep_index: "Catalog: series, units, what each date means, coverage, latest value and sources.",
    ep_latest: "The most recent value and the previous one.", ep_year: "Every value of one year.",
    ep_day: "One day (daily series). If nothing was published that day the answer is 404: query the year.",
    ep_month: "One month (INPC and inflation).", ep_all: "The whole series, with the source of each value.",
    ep_compact: "Dates and values as two arrays, for charts.", ep_schema: "JSON Schema of every file.",
    examples: "Examples", copy: "Copy", copied: "Copied", live_title: "Live response of <code>v1/fix/latest.json</code>",
    src_title: "Sources and status",
    src_sub: "VERDE (green): verified against the DOF. AMARILLO (amber): official source with partial verification or documented limits. ROJO (red): not verified. Details per series, the errors found in the sources and how they were fixed are in <a href=\"https://github.com/BEG-lag/indicadores-mx/blob/main/docs/fuentes.md\">docs/fuentes.md</a> (Spanish).",
    disclaimer: "Unofficial mirror. Only the DOF and the issuing institutions are authoritative. Not legal or tax advice.",
    author: "Built by <strong>Benjamín Esponda García</strong>, a Mexican lawyer who builds with AI. <a href=\"https://pivotek.mx\">pivotek.mx</a> · <a href=\"https://github.com/BEG-lag/portafolio-ia\">portfolio</a> · <a href=\"https://github.com/BEG-lag/indicadores-mx\">code</a>",
    licenses: "Code under the MIT License. Data in the public domain (CC0 1.0). No analytics, no cookies. Self-hosted fonts (SIL OFL 1.1).",
    fresh: (d, n, s) => `Data as of <b>${d}</b> · <b>${n}</b> values in <b>${s}</b> series`,
    dof: "DOF note", source: "Source", checked: "Compared with the text of the DOF note", not_checked: "SIDOF value, not compared with the note",
    vs_prev: "vs. previous", monthly: "monthly", annual: "annual", zlfn: "Northern Border", in_force: "in force since",
    status: "Status", coverage: "Coverage", count: "Values", with_note: "With DOF note", verified: "Verified",
    ids: "Series:", lang_btn: "ES", lang_label: "Cambiar a español",
    caption: (name, n, a, b) => `${name}: ${n} values from ${a} to ${b}.`,
    chart_label: (name, last, date) => `Chart of ${name}. Latest value ${last} (${date}).`,
    table_date: "Date", table_value: "Value", load_error: "The data could not be loaded. Please try again later.",
    udi_used: (v, d) => `UDI value on ${d}: ${v} pesos`, udi_none: (a, b) => `No UDI value for that date. Available from ${a} to ${b}.`,
    inf_res: (p, f) => `INPC change: ${p} (factor ${f})`, inf_used: (a, va, b, vb) => `INPC ${a}: ${va} · INPC ${b}: ${vb}`,
    inf_none: (a, b) => `Pick months between ${a} and ${b}.`, updated_amount: "Updated amount", bad_amount: "Enter a valid amount.",
    see_note: "see the DOF note", published_until: "published through", unit: "Unit",
  },
};

const state = { lang: "es", index: null, series: {}, compact: {}, chartId: "fix", range: "1y" };

function pickLang() {
  const url = new URL(location.href).searchParams.get("lang");
  if (url === "en" || url === "es") return url;
  try { const saved = localStorage.getItem("lang"); if (saved === "en" || saved === "es") return saved; } catch { /* private mode */ }
  return "es";
}

const t = (key) => T[state.lang][key];
const locale = () => (state.lang === "es" ? "es-MX" : "en-US");

function fmtNumber(v, decimals) {
  return new Intl.NumberFormat(locale(), { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(v);
}

function fmtValue(entry, v) {
  const n = fmtNumber(v, entry.decimals);
  if (entry.unit === "percent") return `${n}%`;
  if (entry.unit.startsWith("MXN")) return `$${n}`;
  return n;
}

function fmtDate(iso) {
  const time = toTime(iso);
  const opts = iso.length === 7 ? { month: "short", year: "numeric", timeZone: "UTC" } : { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" };
  return new Intl.DateTimeFormat(locale(), opts).format(time);
}

function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

async function getJson(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function compact(id) {
  if (!state.compact[id]) {
    state.compact[id] = getJson(`${API}/${id}/compact.json`).then((c) => ({
      dates: c.dates,
      values: c.values,
      times: c.dates.map(toTime),
    }));
  }
  return state.compact[id];
}

// ------------------------------------------------------------------ i18n

function applyLang() {
  document.documentElement.lang = state.lang;
  for (const node of document.querySelectorAll("[data-i18n]")) {
    const value = t(node.dataset.i18n);
    if (typeof value === "string") node.textContent = value;
  }
  for (const node of document.querySelectorAll("[data-i18n-html]")) {
    const value = t(node.dataset.i18nHtml);
    if (typeof value === "string") node.innerHTML = value;
  }
  for (const node of document.querySelectorAll("[data-i18n-attr]")) {
    const [attr, key] = node.dataset.i18nAttr.split(":");
    node.setAttribute(attr, t(key));
  }
  const btn = document.getElementById("lang");
  btn.textContent = t("lang_btn");
  btn.setAttribute("aria-label", t("lang_label"));
  btn.setAttribute("lang", state.lang === "es" ? "en" : "es");
  document.title = state.lang === "es"
    ? "indicadores-mx · Indicadores económicos oficiales de México, trazables al DOF"
    : "indicadores-mx · Mexico's official economic indicators, traceable to the DOF";
}

function render() {
  applyLang();
  if (!state.index) return;
  renderFresh();
  renderCards();
  renderSelect();
  renderChart();
  renderStatus();
  renderIds();
  runUdi();
  runInflation();
}

// ------------------------------------------------------------------ cards

function renderFresh() {
  const idx = state.index;
  const total = idx.series.reduce((n, s) => n + s.coverage.count, 0);
  document.getElementById("fresh").innerHTML = t("fresh")(fmtDate(idx.data_updated), fmtNumber(total, 0), idx.series.length);
}

function delta(entry, latest, previous) {
  if (!previous || entry.kind === "step") return "";
  const diff = latest - previous;
  const cls = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
  const arrow = diff > 0 ? "▲" : diff < 0 ? "▼" : "=";
  const amount = entry.unit === "percent" ? `${fmtNumber(Math.abs(diff), entry.decimals)} pp` : fmtNumber(Math.abs(diff), entry.decimals);
  return `<span class="delta ${cls}" title="${esc(t("vs_prev"))}">${arrow} ${amount}</span>`;
}

function cardHtml(entry, latest) {
  const src = latest.source || {};
  const ok = src.checked ? `<span class="ok" title="${esc(t("checked"))}" aria-label="${esc(t("checked"))}">✓</span>` : "";
  const link = src.url ? `<a class="src" href="${esc(src.url)}">${esc(src.dof_note ? t("dof") : t("source"))} ↗</a>` : "";
  const prevValue = latest.previous ? latest.previous.value : null;
  const extra = (EXTRA[entry.id] || [])
    .map((id) => {
      const e = state.series[id];
      if (!e) return "";
      const label = id === "inflacion-mensual" ? t("monthly") : id === "salario-minimo-zlfn" ? t("zlfn") : id === "uma-mensual" ? t("monthly") : t("annual");
      return `<span>${esc(label)} <b>${esc(fmtValue(e, e.latest.value))}</b></span>`;
    })
    .filter(Boolean)
    .join(" · ");
  let when = entry.kind === "step" ? `${t("in_force")} ${fmtDate(latest.date)}` : fmtDate(latest.date);
  if (entry.id === "udis" && latest.date < entry.coverage.last) when += ` · ${t("published_until")} ${fmtDate(entry.coverage.last)}`;
  return `
    <article class="card" aria-labelledby="card-${entry.id}">
      <div class="label"><span id="card-${entry.id}">${esc(entry.short[state.lang])}</span>${ok}</div>
      <div class="value">${esc(fmtValue(entry, latest.value))}</div>
      ${extra ? `<div class="extra">${extra}</div>` : ""}
      <div class="meta"><span>${esc(when)}</span>${delta(entry, latest.value, prevValue)}${link}</div>
      <div class="spark-slot" data-spark="${entry.id}"></div>
    </article>`;
}

async function renderCards() {
  const host = document.getElementById("cards");
  // UDIS are published up to two weeks ahead: the card shows today's value.
  const today = state.index.data_updated;
  const path = (id) => {
    const entry = state.series[id];
    if (id === "udis" && entry.coverage.first <= today && today < entry.coverage.last) return `${API}/udis/${today}.json`;
    return `${API}/${id}/latest.json`;
  };
  const latest = await Promise.all(
    CARD_IDS.filter((id) => state.series[id]).map((id) => getJson(path(id)).then((l) => [id, l]).catch(() => null)),
  );
  host.innerHTML = latest.filter(Boolean).map(([id, l]) => cardHtml(state.series[id], l)).join("");
  renderToday(Object.fromEntries(latest.filter(Boolean)));
  for (const slot of host.querySelectorAll("[data-spark]")) {
    const id = slot.dataset.spark;
    const entry = state.series[id];
    compact(id).then((c) => {
      const n = entry.kind === "daily" ? 120 : entry.kind === "monthly" ? 36 : c.values.length;
      slot.innerHTML = sparkline(c.values.slice(-n), { step: entry.kind === "step" });
    });
  }
}

function renderToday(byId) {
  const rows = ["fix", "udis", "tiie-28", "inflacion-anual"]
    .filter((id) => byId[id])
    .map((id) => {
      const entry = state.series[id];
      const obs = byId[id];
      const src = obs.source && obs.source.url ? `<a href="${esc(obs.source.url)}">${esc(obs.source.dof_note ? "DOF" : t("source"))} ↗</a>` : "";
      return `<div class="row-t"><dt>${esc(entry.short[state.lang])}</dt><dd>${esc(fmtValue(entry, obs.value))}</dd><span class="when">${esc(fmtDate(obs.date))}${src}</span></div>`;
    });
  document.getElementById("today").innerHTML = rows.join("");
}

// ------------------------------------------------------------------ chart

function renderSelect() {
  const select = document.getElementById("chart-series");
  select.innerHTML = state.index.series
    .map((s) => `<option value="${s.id}"${s.id === state.chartId ? " selected" : ""}>${esc(s.name[state.lang])}</option>`)
    .join("");
}

const RANGES = { "1m": 31, "6m": 183, "1y": 366, "5y": 1827, "10y": 3653, all: Infinity };

async function renderChart() {
  const entry = state.series[state.chartId];
  const host = document.getElementById("chart");
  const c = await compact(entry.id);
  let start = 0;
  if (RANGES[state.range] !== Infinity) {
    const from = c.times[c.times.length - 1] - RANGES[state.range] * 86400000;
    start = Math.max(0, lowerBound(c.times, from) - (entry.kind === "daily" ? 0 : 1));
  }
  if (c.times.length - start < 2) start = Math.max(0, c.times.length - 2);
  const times = c.times.slice(start), values = c.values.slice(start), dates = c.dates.slice(start);
  const decimals = entry.decimals;
  const format = {
    value: (v) => fmtValue(entry, v),
    date: (iso) => fmtDate(iso),
    month: (time) => new Intl.DateTimeFormat(locale(), { month: "short", year: "2-digit", timeZone: "UTC" }).format(time),
    tick: (v, step) => fmtNumber(v, step >= 1 ? 0 : Math.min(decimals, Math.max(1, -Math.floor(Math.log10(step))))),
  };
  // Step series run until today, or until the day a closed series ended.
  const until = entry.kind === "step" ? (entry.ended ? toTime(entry.ended) : toTime(state.index.data_updated)) : undefined;
  drawChart(host, { times, values, dates, format, step: entry.kind === "step", until });
  const name = entry.name[state.lang];
  host.setAttribute("aria-label", t("chart_label")(name, fmtValue(entry, values[values.length - 1]), fmtDate(dates[dates.length - 1])));
  document.getElementById("chart-caption").textContent = `${t("caption")(name, fmtNumber(values.length, 0), fmtDate(dates[0]), fmtDate(dates[dates.length - 1]))} ${t("unit")}: ${entry.unit_label[state.lang]}.`;
  const rows = dates.slice(-15).reverse().map((d, i) => `<tr><td>${esc(fmtDate(d))}</td><td class="num">${esc(fmtValue(entry, values[values.length - 1 - i]))}</td></tr>`);
  document.getElementById("chart-table").innerHTML = `<caption class="sr-only">${esc(name)}</caption><thead><tr><th scope="col">${t("table_date")}</th><th scope="col" class="num">${t("table_value")}</th></tr></thead><tbody>${rows.join("")}</tbody>`;
}

// ------------------------------------------------------------------ converter

function parseAmount(text) {
  const clean = String(text).trim().replace(/\s/g, "").replace(/,(?=\d{3}(\D|$))/g, "");
  if (!/^\d+(\.\d+)?$/.test(clean)) return null;
  return Number(clean);
}

async function runUdi() {
  const out = document.getElementById("udi-result");
  const date = document.getElementById("udi-date").value;
  const amount = parseAmount(document.getElementById("udi-amount").value);
  const dir = document.querySelector('input[name="udi-dir"]:checked').value;
  const c = await compact("udis");
  if (amount === null) { out.innerHTML = `<span class="warn">${esc(t("bad_amount"))}</span>`; return; }
  const i = c.dates.indexOf(date);
  if (!date || i < 0) {
    out.innerHTML = `<span class="warn">${esc(t("udi_none")(fmtDate(c.dates[0]), fmtDate(c.dates[c.dates.length - 1])))}</span>`;
    return;
  }
  const udi = c.values[i];
  const result = dir === "mxn" ? amount / udi : amount * udi;
  const shown = dir === "mxn" ? `${fmtNumber(result, 6)} UDIS` : `$${fmtNumber(result, 2)}`;
  out.innerHTML = `<span class="big">${esc(shown)}</span>${esc(t("udi_used")(fmtNumber(udi, 6), fmtDate(date)))} · <span id="udi-src"></span>`;
  getJson(`${API}/udis/${date}.json`).then((o) => {
    const slot = document.getElementById("udi-src");
    if (slot && o.source && o.source.url) slot.innerHTML = `<a href="${esc(o.source.url)}">${esc(t("see_note"))} ↗</a>`;
  }).catch(() => {});
}

async function runInflation() {
  const out = document.getElementById("inf-result");
  const from = document.getElementById("inf-from").value;
  const to = document.getElementById("inf-to").value;
  const raw = document.getElementById("inf-amount").value.trim();
  const amount = raw ? parseAmount(raw) : null;
  const c = await compact("inpc");
  const a = c.dates.indexOf(from), b = c.dates.indexOf(to);
  if (a < 0 || b < 0) {
    out.innerHTML = `<span class="warn">${esc(t("inf_none")(fmtDate(c.dates[0]), fmtDate(c.dates[c.dates.length - 1])))}</span>`;
    return;
  }
  const factor = c.values[b] / c.values[a];
  const pctText = `${fmtNumber((factor - 1) * 100, 2)}%`;
  let html = `<span class="big">${esc(pctText)}</span>${esc(t("inf_res")(pctText, fmtNumber(factor, 6)))}<br>`;
  html += esc(t("inf_used")(fmtDate(from), fmtNumber(c.values[a], 3), fmtDate(to), fmtNumber(c.values[b], 3)));
  if (raw && amount === null) html += `<br><span class="warn">${esc(t("bad_amount"))}</span>`;
  else if (amount !== null) html += `<br>${esc(t("updated_amount"))}: <b>$${esc(fmtNumber(amount * factor, 2))}</b>`;
  html += ` · <a href="${API}/inpc/${esc(to)}.json">${esc(to)}.json</a>`;
  out.innerHTML = html;
}

// ------------------------------------------------------------------ API and status

function renderIds() {
  document.getElementById("series-ids").innerHTML = `${esc(t("ids"))} ${state.index.series.map((s) => `<code>${s.id}</code>`).join(" ")}`;
}

function renderStatus() {
  const rows = state.index.series.map((s) => `
    <tr>
      <td>${esc(s.name[state.lang])}<br><code>${s.id}</code></td>
      <td><span class="chip ${s.status}">${s.status}</span></td>
      <td>${esc(fmtDate(s.coverage.first))} – ${esc(fmtDate(s.coverage.last))}</td>
      <td class="num">${fmtNumber(s.coverage.count, 0)}</td>
      <td class="num">${fmtNumber(s.coverage.with_dof_note, 0)}</td>
      <td class="num">${fmtNumber(s.coverage.checked_against_note, 0)}</td>
    </tr>`);
  document.getElementById("status-table").innerHTML = `<thead><tr><th scope="col">${t("series")}</th><th scope="col">${t("status")}</th><th scope="col">${t("coverage")}</th><th scope="col" class="num">${t("count")}</th><th scope="col" class="num">${t("with_note")}</th><th scope="col" class="num">${t("verified")}</th></tr></thead><tbody>${rows.join("")}</tbody>`;
}

function setupTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const select = (tab) => {
    for (const other of tabs) {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      document.getElementById(other.getAttribute("aria-controls")).hidden = !on;
    }
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (e) => {
      const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!step) return;
      const next = tabs[(i + step + tabs.length) % tabs.length];
      select(next);
      next.focus();
    });
  });
  for (const btn of document.querySelectorAll("[data-copy]")) {
    btn.addEventListener("click", async () => {
      const text = document.getElementById(btn.dataset.copy).textContent;
      try { await navigator.clipboard.writeText(text); btn.textContent = t("copied"); } catch { btn.textContent = "✗"; }
      setTimeout(() => { btn.textContent = t("copy"); }, 1600);
    });
  }
}

// ------------------------------------------------------------------ boot

function setupControls() {
  document.getElementById("lang").addEventListener("click", () => {
    state.lang = state.lang === "es" ? "en" : "es";
    try { localStorage.setItem("lang", state.lang); } catch { /* ignore */ }
    const url = new URL(location.href);
    url.searchParams.set("lang", state.lang);
    history.replaceState(null, "", url);
    render();
  });
  document.getElementById("chart-series").addEventListener("change", (e) => { state.chartId = e.target.value; renderChart(); });
  for (const btn of document.querySelectorAll("#chart-ranges button")) {
    btn.addEventListener("click", () => {
      state.range = btn.dataset.range;
      for (const b of document.querySelectorAll("#chart-ranges button")) b.setAttribute("aria-pressed", String(b === btn));
      renderChart();
    });
  }
  for (const id of ["udi-date", "udi-amount"]) document.getElementById(id).addEventListener("input", runUdi);
  for (const r of document.querySelectorAll('input[name="udi-dir"]')) r.addEventListener("change", runUdi);
  for (const id of ["inf-from", "inf-to", "inf-amount"]) document.getElementById(id).addEventListener("input", runInflation);
  for (const form of document.querySelectorAll("form")) form.addEventListener("submit", (e) => e.preventDefault());
  let timer;
  new ResizeObserver(() => { clearTimeout(timer); timer = setTimeout(renderChart, 120); }).observe(document.getElementById("chart"));
}

async function boot() {
  state.lang = pickLang();
  applyLang();
  setupTabs();
  try {
    state.index = await getJson(`${API}/index.json`);
  } catch {
    document.getElementById("cards").innerHTML = `<p class="note">${esc(t("load_error"))}</p>`;
    return;
  }
  for (const s of state.index.series) state.series[s.id] = s;
  const udis = state.series.udis;
  const inpc = state.series.inpc;
  const today = state.index.data_updated;
  document.getElementById("udi-date").value = udis && today <= udis.coverage.last ? today : udis.coverage.last;
  document.getElementById("udi-date").min = udis.coverage.first;
  document.getElementById("udi-date").max = udis.coverage.last;
  const last = inpc.coverage.last;
  const [y, m] = last.split("-").map(Number);
  document.getElementById("inf-to").value = last;
  document.getElementById("inf-from").value = `${y - 1}-${String(m).padStart(2, "0")}`;
  for (const id of ["inf-from", "inf-to"]) { document.getElementById(id).min = inpc.coverage.first; document.getElementById(id).max = last; }
  setupControls();
  render();
  getJson(`${API}/fix/latest.json`).then((j) => { document.getElementById("live-response").textContent = JSON.stringify(j, null, 2); }).catch(() => {});
}

boot();
