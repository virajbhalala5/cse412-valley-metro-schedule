// Interactive line map drawn as SVG from the station and serves tables. No outside libraries.
window.initSvgMap = function () {
  const data = JSON.parse(document.getElementById("mapdata").textContent);
  const svg = document.getElementById("map"), tip = document.getElementById("tip");
  const NS = "http://www.w3.org/2000/svg";
  const st = {};
  const lat0 = data.stations.reduce((s, x) => s + x.lat, 0) / data.stations.length;
  const k = Math.cos(lat0 * Math.PI / 180);
  data.stations.forEach(s => { s.x = s.lon * k; s.y = -s.lat; st[s.id] = s; });
  const xs = data.stations.map(s => s.x), ys = data.stations.map(s => s.y);
  const pad = 0.02, bx = Math.min(...xs) - pad, by = Math.min(...ys) - pad;
  const bw = Math.max(...xs) - Math.min(...xs) + 2 * pad, bh = Math.max(...ys) - Math.min(...ys) + 2 * pad;
  const full = { x: bx, y: by, w: bw, h: bh };
  let vb = { ...full }, selected = null;
  const el = (n, a) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const gLines = el("g", {}), gDots = el("g", {}); svg.append(gLines, gDots);
  const lineEls = {}, dotEls = [], labelEls = [];  // lineEls[name] is a list of polylines

  data.lines.forEach(L => {
    const pts = L.pts.map(p => (p[1] * k) + "," + (-p[0])).join(" ");
    const pl = el("polyline", { points: pts, fill: "none", stroke: "#" + L.color, "stroke-linecap": "round", "stroke-linejoin": "round", class: "ln" });
    gLines.append(pl); (lineEls[L.name] = lineEls[L.name] || []).push(pl);
  });
  // labels on the ends of each line and on the downtown hub
  const gLbl = el("g", {}); svg.append(gLbl);
  const want = new Set();
  data.lines.forEach(L => { want.add(L.stops[0]); want.add(L.stops[L.stops.length - 1]); });
  data.stations.forEach(s => { if (/Downtown Phx Hub\/Jefferson/.test(s.name)) want.add(s.id); });
  want.forEach(id => { const s = st[id]; if (!s) return;
    const t = el("text", { class: "lbl", "pointer-events": "none" }); t.textContent = s.name.replace("Downtown Phx Hub/Jefferson St", "Downtown Hub");
    gLbl.append(t); labelEls.push({ t, s }); });
  data.stations.forEach(s => {
    if (!s.lines.length) return;
    const c = el("circle", { cx: s.x, cy: s.y, fill: "#fff", stroke: "#0F1C2E", class: "dot", style: "cursor:pointer" });
    c.addEventListener("mouseenter", () => { tip.textContent = s.name + "  ·  " + s.lines.join(", "); tip.style.opacity = 1; c.setAttribute("fill", "#ffd54a"); });
    c.addEventListener("mousemove", e => { const r = svg.parentNode.getBoundingClientRect(); tip.style.left = (e.clientX - r.left + 14) + "px"; tip.style.top = (e.clientY - r.top + 14) + "px"; });
    c.addEventListener("mouseleave", () => { tip.style.opacity = 0; c.setAttribute("fill", c === selected ? "#ffd54a" : "#fff"); });
    c.addEventListener("click", () => { if (!moved) select(s.id, c); });
    gDots.append(c); dotEls.push({ c, s });
  });

  function select(id, c) {
    selected = c; dotEls.forEach(({ c: d }) => d.setAttribute("fill", d === c ? "#ffd54a" : "#fff"));
    draw();
    window.showStation(id);
  }
  function draw() {
    // keep the map's shape: letterbox into the element's aspect ratio
    const r = svg.getBoundingClientRect(), ar = r.width / r.height;
    let w = vb.w, h = vb.h;
    if (w / h < ar) w = h * ar; else h = w / ar;
    svg.setAttribute("viewBox", `${vb.x - (w - vb.w) / 2} ${vb.y - (h - vb.h) / 2} ${w} ${h}`);
    const unit = w / r.width;                       // user units per screen pixel
    Object.values(lineEls).flat().forEach(p => p.setAttribute("stroke-width", 6.5 * unit));
    dotEls.forEach(({ c }) => { const sel = c === selected; c.setAttribute("r", (sel ? 7 : 3.8) * unit); c.setAttribute("stroke-width", (sel ? 3 : 1.8) * unit); });
    labelEls.forEach(({ t, s }) => { const right = s.x > bx + bw * 0.8, top = s.y < by + bh * 0.12;
      t.setAttribute("text-anchor", right ? "end" : "start");
      t.setAttribute("x", s.x + (right ? -8 : 8) * unit); t.setAttribute("y", s.y + (top ? 16 : -7) * unit); t.style.fontSize = (12 * unit) + "px"; t.setAttribute("stroke-width", 3 * unit); });
  }
  function zoom(f, cx, cy) {
    const nx = cx ?? vb.x + vb.w / 2, ny = cy ?? vb.y + vb.h / 2;
    vb = { x: nx - (nx - vb.x) * f, y: ny - (ny - vb.y) * f, w: vb.w * f, h: vb.h * f }; draw();
  }
  function toUser(e) {
    const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  svg.addEventListener("wheel", e => { e.preventDefault(); const u = toUser(e); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, u.x, u.y); }, { passive: false });
  let drag = null, moved = false;
  svg.addEventListener("pointerdown", e => { drag = { x: e.clientX, y: e.clientY, vb: { ...vb } }; moved = false; });
  window.addEventListener("pointermove", e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) { moved = true; svg.classList.add("drag"); }
    const r = svg.getBoundingClientRect(), unit = (svg.viewBox.baseVal.width) / r.width;
    vb = { ...drag.vb, x: drag.vb.x - dx * unit, y: drag.vb.y - dy * unit }; draw();
  });
  window.addEventListener("pointerup", () => { drag = null; svg.classList.remove("drag"); setTimeout(() => moved = false, 0); });
  document.getElementById("zin").onclick = () => zoom(1 / 1.4);
  document.getElementById("zout").onclick = () => zoom(1.4);
  document.getElementById("zreset").onclick = () => { vb = { ...full }; draw(); };
  document.querySelectorAll(".legend button").forEach(b => b.addEventListener("click", () => {
    const off = b.classList.toggle("off"); lineEls[b.dataset.line].forEach(p => p.style.display = off ? "none" : "");
  }));
  window.addEventListener("resize", draw); draw();
};
