// small helpers used on several pages
document.addEventListener("DOMContentLoaded", () => {
  // fade flash messages away
  document.querySelectorAll(".flash.ok").forEach(f => setTimeout(() => { f.style.transition = "opacity .6s"; f.style.opacity = 0; }, 4500));

  // "Now" buttons: fill date and time boxes with the current local date and time
  document.querySelectorAll("[data-now]").forEach(b => b.addEventListener("click", () => {
    const f = b.closest("form"), d = new Date(), p = n => String(n).padStart(2, "0");
    f.querySelector("[name=date]").value = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    f.querySelector("[name=time]").value = `${p(d.getHours())}:${p(d.getMinutes())}`;
    f.requestSubmit();
  }));

  // swap button in the trip planner
  const sw = document.getElementById("swap");
  if (sw) sw.addEventListener("click", () => {
    const a = document.querySelector("[name=from]"), b = document.querySelector("[name=to]");
    [a.value, b.value] = [b.value, a.value];
    if (a.value && b.value) a.form.requestSubmit();
  });

  // live filter for tables (stations page)
  const lf = document.getElementById("livefilter");
  if (lf) lf.addEventListener("input", () => {
    const q = lf.value.toLowerCase(); let n = 0;
    document.querySelectorAll("#livetable tbody tr").forEach(tr => {
      const show = tr.textContent.toLowerCase().includes(q); tr.style.display = show ? "" : "none"; if (show) n++;
    });
    const c = document.getElementById("livecount"); if (c) c.textContent = n + " stations";
  });

  // add / remove stop rows in the add-trip form
  const rows = document.getElementById("stoprows");
  if (rows) {
    const renum = () => rows.querySelectorAll(".stoprow").forEach((r, i) => r.querySelector(".num").textContent = i + 1);
    document.getElementById("addstop").addEventListener("click", () => {
      const last = rows.lastElementChild, c = last.cloneNode(true);
      c.querySelector("select").value = ""; c.querySelectorAll("input").forEach(i => i.value = "");
      rows.appendChild(c); renum();
    });
    rows.addEventListener("click", e => {
      if (e.target.classList.contains("rm") && rows.children.length > 2) { e.target.closest(".stoprow").remove(); renum(); }
    });
  }
});
