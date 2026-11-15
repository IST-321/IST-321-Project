/* Viking Hub: weather for downtown Cleveland from Open-Meteo (https://open-meteo.com).
   The browser asks Open-Meteo directly, so the server needs no outside access.
   Shows the forecast on Home and adds a note to today's walk lines when rain, snow,
   storms or cold under 25°F are expected. If the forecast can't load, nothing shows. */
(function () {
  "use strict";
  const CFG = window.VH_WEATHER || {};
  if (CFG.off) return;  // previewing another day: the real forecast wouldn't match it

  const URL = "https://api.open-meteo.com/v1/forecast?latitude=41.5021&longitude=-81.6747"
    + "&hourly=temperature_2m,weather_code&temperature_unit=fahrenheit"
    + "&timezone=America%2FNew_York&forecast_days=1";
  const CACHE_KEY = "vh-weather";
  const CACHE_MS = 30 * 60 * 1000;
  const COLD_F = 25;

  const esc = (s) => VH.esc(s);
  const hourOf = (hhmm) => Number(String(hhmm).split(":")[0]);
  const hourLabel = (h) => `${h % 12 || 12} ${h < 12 ? "AM" : "PM"}`;

  // WMO weather codes, grouped into what a student needs to know
  function describe(code) {
    if (code === 0) return { icon: "sun", text: "Clear", wet: null };
    if (code <= 2) return { icon: "cloud-sun", text: "Partly cloudy", wet: null };
    if (code === 3) return { icon: "cloud", text: "Cloudy", wet: null };
    if (code === 45 || code === 48) return { icon: "fog", text: "Fog", wet: null };
    if (code >= 51 && code <= 57) return { icon: "rain", text: "Drizzle", wet: "Rain" };
    if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return { icon: "rain", text: code >= 80 ? "Rain showers" : "Rain", wet: "Rain" };
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return { icon: "snow", text: code >= 85 ? "Snow showers" : "Snow", wet: "Snow" };
    if (code >= 95) return { icon: "storm", text: "Thunderstorms", wet: "Storms" };
    return { icon: "cloud", text: "Cloudy", wet: null };
  }

  async function forecast() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
      if (saved && Date.now() - saved.at < CACHE_MS) return saved.hours;
    } catch (_) { /* storage can be unavailable; just fetch */ }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);
    try {
      const res = await fetch(URL, { signal: ctrl.signal });
      if (!res.ok) return null;
      const j = await res.json();
      const hours = j.hourly.time.map((t, i) => ({
        hour: Number(t.slice(11, 13)), temp: Math.round(j.hourly.temperature_2m[i]), code: j.hourly.weather_code[i],
      }));
      try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), hours })); } catch (_) { /* fine */ }
      return hours;
    } catch (_) {
      return null;
    } finally { clearTimeout(timer); }
  }

  /* ---------- Home: now and the next few hours ---------- */
  function renderHome(hours) {
    const box = document.querySelector("[data-weather]");
    if (!box) return;
    const h = Math.min(hourOf(CFG.now), 23);
    const now = hours.find((x) => x.hour === h);
    if (!now) return;
    const d = describe(now.code);
    const next = hours.filter((x) => x.hour > h).slice(0, 4);
    box.innerHTML = `<div class="ww-now">${VH.svg(d.icon)}<span><strong>${now.temp}°F</strong>
        <small>${esc(d.text)} · downtown Cleveland</small></span></div>
      ${next.length ? `<ol class="ww-hours" aria-label="Next few hours">${next.map((x) => {
        const n = describe(x.code);
        return `<li><small>${hourLabel(x.hour)}</small>${VH.svg(n.icon)}<span>${x.temp}°</span><span class="visually-hidden">${esc(n.text)}</span></li>`;
      }).join("")}</ol>` : ""}
      <a class="ww-credit" href="https://open-meteo.com/" target="_blank" rel="noopener">Weather data by Open-Meteo</a>`;
    box.hidden = false;
  }

  /* ---------- Walk lines: a note when the walk looks wet or cold ---------- */
  function annotate(root, hours) {
    root.querySelectorAll("[data-walk-at]:not([data-wx-done])").forEach((line) => {
      line.setAttribute("data-wx-done", "");
      if (line.dataset.walkDay !== CFG.today) return;
      const start = hourOf(line.dataset.walkAt);
      const [hh, mm] = line.dataset.walkAt.split(":").map(Number);
      const end = Math.floor((hh * 60 + mm + Number(line.dataset.walkMin || 0)) / 60);
      const during = hours.filter((x) => x.hour >= start && x.hour <= end);
      if (!during.length) return;
      const wetHour = during.find((x) => describe(x.code).wet);
      const coldest = Math.min(...during.map((x) => x.temp));
      if (!wetHour && coldest >= COLD_F) return;
      const wet = wetHour && describe(wetHour.code);
      const what = wet ? `${wet.wet} expected` : `Cold out, ${coldest}°F`;
      const note = document.createElement("span");
      note.className = "walk-weather";
      note.innerHTML = `${VH.svg(wet ? wet.icon : "cloud")}<span>${esc(what)}${line.hasAttribute("data-walk-indoor")
        ? `. <a href="/campus-map?innerlink=1">Take the Innerlink</a> to stay inside.` : " on this walk."}</span>`;
      line.after(note);
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const hours = await forecast();
    if (!hours) return;  // offline or the service is down: the page stays as it is
    renderHome(hours);
    annotate(document, hours);
    // The schedule draws its day view with JavaScript, so watch for new walk lines
    new MutationObserver(() => annotate(document, hours))
      .observe(document.querySelector("main") || document.body, { childList: true, subtree: true });
  });
})();
