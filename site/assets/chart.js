// A small dependency-free SVG line chart: min/max downsampling, nice ticks,
// pointer and keyboard crosshair. Dates are ISO strings ("2026-11-13" or "2026-11").

const NS = "http://www.w3.org/2000/svg";
const DAY = 86400000;

export function toTime(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, (m || 1) - 1, d || 1);
}

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function niceStep(span, count) {
  const raw = span / Math.max(1, count);
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  const nice = unit < 1.5 ? 1 : unit < 3 ? 2 : unit < 7 ? 5 : 10;
  return nice * power;
}

function yTicks(min, max, count) {
  if (min === max) {
    const pad = Math.abs(min) * 0.05 || 1;
    min -= pad;
    max += pad;
  }
  const step = niceStep(max - min, count);
  const start = Math.floor(min / step) * step;
  const ticks = [];
  for (let v = start; ; v += step) {
    ticks.push(Number(v.toFixed(10)));
    if (v >= max - step * 1e-9) break;
  }
  return { ticks, min: ticks[0], max: ticks[ticks.length - 1], step };
}

function xTicks(t0, t1, width, fmt) {
  const span = t1 - t0;
  const target = Math.max(2, Math.floor(width / 110));
  const years = span / (365.25 * DAY);
  const out = [];
  const start = new Date(t0);
  if (years > 2.5) {
    const stepY = Math.max(1, Math.ceil(years / target));
    let y = start.getUTCFullYear() + 1;
    y = Math.ceil(y / stepY) * stepY;
    for (; Date.UTC(y, 0, 1) <= t1; y += stepY) out.push({ t: Date.UTC(y, 0, 1), label: String(y) });
  } else {
    const months = Math.max(1, Math.round(span / (30.44 * DAY)));
    const stepM = [1, 2, 3, 6, 12].find((s) => months / s <= target) || 12;
    let y = start.getUTCFullYear();
    let m = start.getUTCMonth() + 1;
    for (;;) {
      if (m > 11) { y += Math.floor(m / 12); m %= 12; }
      const t = Date.UTC(y, m, 1);
      if (t > t1) break;
      if (m % stepM === 0) out.push({ t, label: fmt.month(t) });
      m += 1;
    }
  }
  return out;
}

// Keep the first, min, max and last point of each pixel column.
function downsample(times, values, x0, x1, width) {
  if (times.length <= width * 2) return { times, values };
  const outT = [];
  const outV = [];
  const span = x1 - x0 || 1;
  let bucket = -1;
  let first = 0, last = 0, lo = 0, hi = 0;
  const flush = () => {
    const idx = [first, lo, hi, last].filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b);
    for (const i of idx) { outT.push(times[i]); outV.push(values[i]); }
  };
  for (let i = 0; i < times.length; i++) {
    const b = Math.floor(((times[i] - x0) / span) * width);
    if (b !== bucket) {
      if (bucket >= 0) flush();
      bucket = b; first = last = lo = hi = i;
    } else {
      last = i;
      if (values[i] < values[lo]) lo = i;
      if (values[i] > values[hi]) hi = i;
    }
  }
  flush();
  return { times: outT, values: outV };
}

export function lowerBound(arr, x) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] < x) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/**
 * Draw (or redraw) a chart into `host`.
 * opts: { times, values, dates, step, format: {value(v), date(iso), month(t)}, label(i), onFocus(i) }
 */
export function drawChart(host, opts) {
  host.innerHTML = "";
  const { times, values, dates, format } = opts;
  if (!times.length) {
    host.textContent = opts.empty || "";
    return null;
  }
  const rect = host.getBoundingClientRect();
  const width = Math.max(280, rect.width);
  const height = Math.max(200, rect.height);
  const pad = { l: 8, r: 64, t: 14, b: 26 };
  const now = opts.until || times[times.length - 1];
  const t0 = times[0];
  const t1 = opts.step ? Math.max(now, times[times.length - 1]) : times[times.length - 1];
  let vmin = Infinity, vmax = -Infinity;
  for (const v of values) { if (v < vmin) vmin = v; if (v > vmax) vmax = v; }
  const yt = yTicks(vmin, vmax, height < 300 ? 4 : 5);
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const sx = (t) => pad.l + ((t - t0) / (t1 - t0 || 1)) * iw;
  const sy = (v) => pad.t + (1 - (v - yt.min) / (yt.max - yt.min || 1)) * ih;

  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "none", "aria-hidden": "true" }, host);
  const defs = el("defs", {}, svg);
  const grad = el("linearGradient", { id: "area-fill", x1: "0", x2: "0", y1: "0", y2: "1" }, defs);
  el("stop", { offset: "0", "stop-color": "#cfff45", "stop-opacity": "0.22" }, grad);
  el("stop", { offset: "1", "stop-color": "#cfff45", "stop-opacity": "0" }, grad);

  const grid = el("g", { class: "grid" }, svg);
  const axis = el("g", { class: "axis" }, svg);
  for (const v of yt.ticks) {
    const y = sy(v);
    el("line", { x1: pad.l, x2: pad.l + iw, y1: y, y2: y }, grid);
    const label = el("text", { x: width - pad.r + 8, y: y + 4 }, axis);
    label.textContent = format.tick(v, yt.step);
  }
  for (const tick of xTicks(t0, t1, iw, format)) {
    const x = sx(tick.t);
    if (x < pad.l + 12 || x > pad.l + iw - 12) continue;
    el("line", { x1: x, x2: x, y1: pad.t, y2: pad.t + ih }, grid);
    const label = el("text", { x, y: height - 6, "text-anchor": "middle" }, axis);
    label.textContent = tick.label;
  }

  const ds = downsample(times, values, t0, t1, iw);
  let d = "";
  for (let i = 0; i < ds.times.length; i++) {
    const x = sx(ds.times[i]).toFixed(1);
    const y = sy(ds.values[i]).toFixed(1);
    if (i === 0) d += `M${x},${y}`;
    else if (opts.step) d += `H${x}V${y}`;
    else d += `L${x},${y}`;
  }
  if (opts.step) d += `H${sx(t1).toFixed(1)}`;
  const base = (pad.t + ih).toFixed(1);
  const area = `${d}V${base}H${sx(ds.times[0]).toFixed(1)}Z`;
  el("path", { class: "area", d: area }, svg);
  el("path", { class: "line", d }, svg);

  const cross = el("g", { class: "cross", visibility: "hidden" }, svg);
  const vline = el("line", { y1: pad.t, y2: pad.t + ih }, cross);
  const dot = el("circle", { r: 4 }, cross);
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  host.appendChild(tip);

  let current = -1;
  const show = (i) => {
    if (i < 0 || i >= times.length) return;
    current = i;
    const x = sx(times[i]);
    const y = sy(values[i]);
    vline.setAttribute("x1", x); vline.setAttribute("x2", x);
    dot.setAttribute("cx", x); dot.setAttribute("cy", y);
    cross.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.innerHTML = `<b>${format.value(values[i])}</b><span>${format.date(dates[i])}</span>`;
    const left = Math.min(Math.max(x, 70), width - 70);
    tip.style.left = `${(left / width) * 100}%`;
    tip.style.top = `${Math.max(y, 54)}px`;
    if (opts.onFocus) opts.onFocus(i);
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); tip.hidden = true; };
  const nearest = (clientX) => {
    const r = svg.getBoundingClientRect();
    const t = t0 + ((clientX - r.left - (pad.l * r.width) / width) / ((iw * r.width) / width)) * (t1 - t0);
    let i = lowerBound(times, t);
    if (i > 0 && (i === times.length || t - times[i - 1] < times[i] - t)) i -= 1;
    return Math.min(i, times.length - 1);
  };
  host.onpointermove = (e) => show(nearest(e.clientX));
  host.onpointerdown = (e) => show(nearest(e.clientX));
  host.onpointerleave = (e) => { if (e.pointerType === "mouse") hide(); };
  host.onblur = hide;
  host.onkeydown = (e) => {
    const page = Math.max(1, Math.round(times.length / 20));
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageUp: -page, PageDown: page };
    if (e.key in moves) { show(Math.min(times.length - 1, Math.max(0, (current < 0 ? times.length - 1 : current) + moves[e.key]))); e.preventDefault(); }
    else if (e.key === "Home") { show(0); e.preventDefault(); }
    else if (e.key === "End") { show(times.length - 1); e.preventDefault(); }
    else if (e.key === "Escape") hide();
  };
  return { show, hide };
}

/** A tiny sparkline as an SVG string. */
export function sparkline(values, { width = 240, height = 40, step = false } = {}) {
  if (values.length < 2) return "";
  let lo = Infinity, hi = -Infinity;
  for (const v of values) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const span = hi - lo || 1;
  const sx = (i) => (i / (values.length - 1)) * (width - 4) + 2;
  const sy = (v) => height - 3 - ((v - lo) / span) * (height - 6);
  let d = "";
  values.forEach((v, i) => {
    const x = sx(i).toFixed(1), y = sy(v).toFixed(1);
    d += i === 0 ? `M${x},${y}` : step ? `H${x}V${y}` : `L${x},${y}`;
  });
  const lastX = sx(values.length - 1).toFixed(1), lastY = sy(values[values.length - 1]).toFixed(1);
  return `<svg class="spark" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" fill="none" stroke="#cfff45" stroke-width="1.5" vector-effect="non-scaling-stroke"/><circle cx="${lastX}" cy="${lastY}" r="2.5" fill="#cfff45"/></svg>`;
}
