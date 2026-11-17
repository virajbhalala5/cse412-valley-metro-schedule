// Home page map: a real street map (Leaflet + OpenStreetMap). If the street tiles can't load
// (no internet), it switches to the plain line diagram in map_svg.js.
window.showStation = function (id) {
  const panel = document.getElementById("panel");
  panel.innerHTML = "<p class='note'>Loading...</p>";
  fetch("/api/station/" + encodeURIComponent(id) + "/next").then(r => r.json()).then(d => {
    const pills = d.lines.map(l => `<span class="pill" style="background:#${l.color}">${l.name}</span>`).join(" ");
    const rows = d.deps.map(x => `<div class="dep"><b>${x.time}</b><span class="pill" style="background:#${x.color}">${x.line}</span><span>${x.toward || ""}</span></div>`).join("") || "<p class='note'>No trains found.</p>";
    panel.innerHTML = `<h3 style="margin:0 0 6px">${d.name}</h3><div>${pills}</div><p class="note" style="margin:10px 0 2px">Next trains (${d.note})</p>${rows}
      <p style="margin:12px 0 0" class="row"><a class="btn small" href="/stations/${encodeURIComponent(d.id)}">Station page</a><a class="btn ghost small" href="/planner?from=${encodeURIComponent(d.id)}">Plan a trip</a></p>`;
  });
};

(function () {
  const data = JSON.parse(document.getElementById("mapdata").textContent);
  const box = document.getElementById("lmap"), svg = document.getElementById("map");
  const tools = document.querySelector(".maptools");

  function fallback() {
    if (window.__svgStarted) return; window.__svgStarted = true;
    box.style.display = "none"; svg.style.display = "block"; tools.style.display = "flex";
    document.querySelector(".hint").textContent = "Offline view. Scroll to zoom, drag to move, click a station.";
    window.initSvgMap();
  }
  if (!window.L) { fallback(); return; }
  tools.style.display = "none";

  const st = {}; data.stations.forEach(s => st[s.id] = s);
  const map = L.map(box, { zoomControl: true, scrollWheelZoom: true, preferCanvas: false });
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
  let loaded = 0, failed = 0;
  tiles.on("tileload", () => loaded++); tiles.on("tileerror", () => failed++);
  setTimeout(() => { if (!loaded && failed) { map.remove(); fallback(); } }, 5000);

  const groups = {};                     // line name -> layer group (legend toggles it)
  const g = n => groups[n] || (groups[n] = L.layerGroup().addTo(map));
  data.lines.forEach(Ln => {
    L.polyline(Ln.pts, { color: "#" + Ln.color, weight: 6, opacity: .9, lineCap: "round" }).addTo(g(Ln.name));
  });
  let selected = null;
  data.stations.forEach(s => {
    if (!s.lines.length) return;
    const c = L.circleMarker([s.lat, s.lon], { radius: 5, color: "#0F1C2E", weight: 2, fillColor: "#fff", fillOpacity: 1 });
    c.bindTooltip(s.name + " · " + s.lines.join(", "), { direction: "top", offset: [0, -6] });
    c.on("click", () => {
      if (selected) selected.setStyle({ radius: 5, fillColor: "#fff" });
      selected = c; c.setStyle({ radius: 8, fillColor: "#ffd54a" }); c.bringToFront(); window.showStation(s.id);
    });
    c.addTo(g(s.lines[0]));      // sits in the group of its first line so the legend can hide it with that line
  });
  const all = data.stations.filter(s => s.lines.length).map(s => [s.lat, s.lon]);
  const fit = () => map.fitBounds(all, { padding: [30, 30] });
  fit();
  const reset = L.control({ position: "topleft" });
  reset.onAdd = () => { const b = L.DomUtil.create("a", "leaflet-bar leaflet-control"); b.href = "#"; b.title = "Show whole network";
    b.style.cssText = "width:30px;height:30px;line-height:30px;text-align:center;background:#fff;font-size:16px;text-decoration:none;color:#222;display:block";
    b.innerHTML = "&#8635;"; b.onclick = e => { e.preventDefault(); fit(); }; return b; };
  reset.addTo(map);
  document.querySelectorAll(".legend button").forEach(b => b.addEventListener("click", () => {
    const off = b.classList.toggle("off"), grp = groups[b.dataset.line];
    if (grp) off ? map.removeLayer(grp) : map.addLayer(grp);
  }));
  window.addEventListener("resize", () => map.invalidateSize());
})();
