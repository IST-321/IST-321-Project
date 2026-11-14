/* Interactive campus map: building details, pins, find, zoom, pan and full screen */
(() => {
  "use strict";
  const page = document.querySelector("[data-map-page]");
  if (!page) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = VH.esc;

  const svg = $("[data-cmap]", page);
  const stage = $("[data-map-stage]", page);
  const tip = $("[data-map-tip]", page);
  const pop = $("[data-map-pop]", page);
  const pinLayer = $("[data-pins]", svg);
  const data = JSON.parse($("#map-data").textContent);
  const list = data.buildings;
  let pins = data.pins;
  const byCode = Object.fromEntries(list.map((b) => [b.code, b]));
  const FULL = { x: 0, y: 0, w: 680, h: 395 };
  let box = { ...FULL };
  let popAt = null;          // map point the open popup is attached to
  let dropMode = false;

  list.filter((b) => b.category === "Parking").forEach((b) => {
    $$(`.m-tag[data-code="${b.code}"], .m-bldg[data-code="${b.code}"]`, svg).forEach((el) => el.classList.add("is-park"));
  });
  $$(".m-bldg", svg).forEach((g) => { const b = byCode[g.dataset.code]; if (b) g.setAttribute("aria-label", `${b.name} (${b.code})`); });

  // Garages are outlined in the color of how full they are, and follow the counts as they change
  const LEVEL = { "Open": "is-open", "Filling up": "is-filling", "Almost full": "is-low", "Full": "is-full" };
  function paintGarages() {
    list.filter((b) => b.parking).forEach((b) => {
      $$(`.m-bldg[data-code="${b.code}"]`, svg).forEach((g) => {
        g.classList.remove("is-open", "is-filling", "is-low", "is-full");
        g.classList.add(LEVEL[b.parking.level]);
      });
    });
  }
  // Draw each garage's roof last so its lighter color shows on top of the walls
  list.filter((b) => b.parking).forEach((b) => {
    $$(`.m-bldg[data-code="${b.code}"]`, svg).forEach((g) => $$(".top", g).forEach((t) => g.appendChild(t)));
  });
  paintGarages();
  async function refreshGarages() {
    try {
      const { garages } = await VH.api("/api/transportation/parking/refresh", { method: "POST" });
      garages.forEach((g) => {
        const b = byCode[g.code];
        if (b && b.parking) Object.assign(b.parking, { available: g.available, percent: g.percent, level: g.level, updated_at: g.updated_at });
      });
      paintGarages();
    } catch { /* keep the last counts */ }
  }
  // Counts only move on the real day; previewing another day keeps them as they are
  if (!window.VH_PREVIEW) setInterval(() => { if (!document.hidden) refreshGarages(); }, 45000);

  /* ---------- Helpers ---------- */
  const DAYS = { M: "Mon", T: "Tue", W: "Wed", R: "Thu", F: "Fri", S: "Sat", U: "Sun" };
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtTime(t) {
    if (!t) return "";
    let [h, m] = t.split(":").map(Number);
    const ap = h < 12 ? "AM" : "PM";
    return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${ap}`;
  }
  function fmtDay(iso) { const [y, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${d}`; }
  const at = (b, location) => b.names.some((n) => (location || "").toLowerCase().includes(n.toLowerCase()));

  function toScreen(x, y) {
    const pt = svg.createSVGPoint();
    pt.x = x; pt.y = y;
    const p = pt.matrixTransform(svg.getScreenCTM());
    const r = stage.getBoundingClientRect();
    return { x: p.x - r.left, y: p.y - r.top };
  }
  function toMap(evt) {
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [p.x, p.y];
  }

  /* ---------- Popup ---------- */
  function placePopup() {
    if (pop.hidden || !popAt) return;
    if (window.matchMedia("(max-width: 639px)").matches && !document.fullscreenElement) {
      pop.classList.add("is-sheet");
      pop.style.transform = "";
      return;
    }
    pop.classList.remove("is-sheet");
    const p = toScreen(popAt[0], popAt[1]);
    const w = pop.offsetWidth, h = pop.offsetHeight;
    const sw = stage.clientWidth, sh = stage.clientHeight;
    let x = Math.min(Math.max(p.x - w / 2, 10), sw - w - 10);
    let y = p.y - h - 22;
    let below = false;
    if (y < 10) { y = Math.min(p.y + 18, sh - h - 10); below = true; }
    pop.style.transform = `translate(${x}px, ${Math.max(10, y)}px)`;
    pop.classList.toggle("is-below", below);
    pop.style.setProperty("--arrow-x", `${Math.min(Math.max(p.x - x, 18), w - 18)}px`);
  }
  function openPopup(html, mapPoint) {
    pop.innerHTML = `<button class="icon-btn pop-close" type="button" data-pop-close aria-label="Close">${VH.svg("x")}</button>${html}`;
    popAt = mapPoint;
    pop.hidden = false;
    placePopup();
  }
  function closePopup() {
    pop.hidden = true;
    popAt = null;
    $$(".m-bldg.is-selected", svg).forEach((x) => x.classList.remove("is-selected"));
    $$(".bldg-row.is-on", page).forEach((r) => r.classList.remove("is-on"));
    history.replaceState(null, "", location.pathname);
  }

  function parkingHTML(b) {
    const p = b.parking;
    const level = LEVEL[p.level];
    return `<div class="pop-park ${level}">
        <p class="pop-label">Estimated open spaces</p>
        <div class="pop-park-count"><strong>${p.available.toLocaleString()}</strong><span class="muted">of ${p.capacity.toLocaleString()}</span>
          <span class="garage-level">${esc(p.level)}</span></div>
        <div class="garage-bar"><span style="width:${100 - p.percent}%"></span></div>
        <p class="muted small">Updated ${VH.fmtTime(p.updated_at.slice(11, 16))}. Viking Hub estimate; CSU doesn't publish live counts.</p>
        <p class="pop-label">Who can park here</p>
        <p class="small">${esc(p.permits)}</p>
      </div>
      <div class="pop-actions">
        <a class="btn btn-primary btn-sm" href="${esc(p.url)}">${VH.svg("bus")} Parking details</a>
      </div>`;
  }

  function buildingHTML(b, tab = "info") {
    const tabs = b.parking ? `<div class="pop-tabs" role="tablist">
        <button type="button" role="tab" class="${tab === "info" ? "is-on" : ""}" aria-selected="${tab === "info"}" data-pop-tab="info:${b.code}">Building</button>
        <button type="button" role="tab" class="${tab === "parking" ? "is-on" : ""}" aria-selected="${tab === "parking"}" data-pop-tab="parking:${b.code}">Parking</button>
      </div>` : "";
    if (tab === "parking" && b.parking) {
      return `<div class="pop-head">
          <span class="code-tag lg-tag is-park">${esc(b.code)}</span>
          <div><h3>${esc(b.name)}</h3><span class="muted small">${esc(b.category)} · ${esc(b.address)}</span></div>
        </div>${tabs}${parkingHTML(b)}`;
    }
    return buildingInfoHTML(b, tabs);
  }

  function buildingInfoHTML(b, tabs) {
    const pinned = pins.find((p) => p.code === b.code);
    const classes = data.places.classes.filter((c) => at(b, c.location));
    const events = data.places.events.filter((e) => at(b, e.location)).slice(0, 2);
    const directions = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(/^\d/.test(b.address) ? b.address + ", Cleveland, OH 44115" : b.name + ", Cleveland State University")}`;
    return `<div class="pop-head">
        <span class="code-tag lg-tag ${b.category === "Parking" ? "is-park" : ""}">${esc(b.code)}</span>
        <div><h3>${esc(b.name)}</h3><span class="muted small">${esc(b.category)} · ${esc(b.address)}</span></div>
      </div>${tabs}
      ${b.parking ? `<p class="small pop-park-line">${VH.svg("bus")} About <strong>${b.parking.available.toLocaleString()}</strong> spaces open · <button class="link-btn" type="button" data-pop-tab="parking:${b.code}">Check parking</button></p>` : ""}
      ${b.inside.length ? `<p class="pop-label">Inside</p><ul class="pop-list">${b.inside.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}
      ${classes.length || events.length ? `<p class="pop-label">On your schedule here</p><ul class="pop-list pop-mine">
          ${classes.map((c) => `<li><strong>${esc(c.code)}</strong> · ${[...(c.days || "")].map((d) => DAYS[d]).join(", ")} at ${fmtTime(c.start_time)} · ${esc(c.location)}</li>`).join("")}
          ${events.map((e) => `<li><strong>${esc(e.title)}</strong> · ${fmtDay(e.event_date)}${e.start_time ? " at " + fmtTime(e.start_time) : ""}</li>`).join("")}
        </ul>` : ""}
      ${b.links.length ? `<p class="pop-label">Resources</p><ul class="pop-links">${b.links.map((l) =>
        `<li><a href="${esc(l.url)}" ${l.external ? 'target="_blank" rel="noopener"' : ""}>${esc(l.label)}${l.external ? " " + VH.svg("external") : ""}</a></li>`).join("")}</ul>` : ""}
      <div class="pop-actions">
        ${pinned ? `<button class="btn btn-ghost btn-sm" type="button" data-unpin="${pinned.id}">${VH.svg("pin")} Unpin</button>${homeBtn(pinned)}`
                 : `<button class="btn btn-primary btn-sm" type="button" data-pin-building="${b.code}">${VH.svg("pin")} Pin to my map</button>`}
        <a class="btn btn-ghost btn-sm" href="${directions}" target="_blank" rel="noopener">Directions</a>
      </div>`;
  }

  /* The Innerlink: the enclosed walkways between buildings */
  const IL = data.innerlink;
  function innerlinkHTML() {
    return `<div class="pop-head"><span class="row-icon">${VH.svg("building")}</span>
        <div><h3>Innerlink</h3><span class="muted small">Indoor walkway across campus</span></div></div>
      <p class="small">Enclosed bridges and hallways connect the core of campus, from the West Garage to the East Garage, so you can cross campus without going outside.</p>
      <p class="pop-label">Buildings on the route</p>
      <div class="pop-route">${IL.route.map((c) => `<span title="${esc(byCode[c] ? byCode[c].name : c)}">${esc(c)}</span>`).join("")}</div>
      <p class="pop-label">Hours</p><p class="small">${esc(IL.hours)}</p>
      <p class="pop-label">After hours, enter with your Viking Card at</p>
      <ul class="pop-list">${IL.entries.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <ul class="pop-links"><li><a href="${esc(IL.url)}" target="_blank" rel="noopener">Innerlink hours announcement ${VH.svg("external")}</a></li></ul>`;
  }
  function routeHighlight(on) {
    $$(".m-links", svg).forEach((g) => g.classList.toggle("is-hover", on));
    IL.route.forEach((c) => $$(`.m-bldg[data-code="${c}"]`, svg).forEach((g) => g.classList.toggle("is-route", on)));
  }
  function openInnerlink(at) {
    $$(".m-bldg.is-selected", svg).forEach((x) => x.classList.remove("is-selected"));
    openPopup(innerlinkHTML(), at || [330, 196]);
  }

  function openBuilding(code, { center = false, tab = "info" } = {}) {
    const b = byCode[code];
    if (!b) return;
    $$(".m-bldg.is-selected", svg).forEach((x) => x.classList.remove("is-selected"));
    $$(`.m-bldg[data-code="${b.shape}"]`, svg).forEach((x) => x.classList.add("is-selected"));
    $$(".bldg-row", page).forEach((r) => r.classList.toggle("is-on", r.dataset.pick === code));
    if (center && b.pin) centerOn(b.pin);
    openPopup(buildingHTML(b, tab), b.pin || [340, 200]);
    history.replaceState(null, "", `?b=${code}`);
  }

  // Home is where Leave by walking times start for the first class of the day
  function homeBtn(p) {
    return p.is_home ? `<span class="home-tag">${VH.svg("home")} Home</span>`
                     : `<button class="btn btn-ghost btn-sm" type="button" data-set-home="${p.id}">${VH.svg("home")} Set as home</button>`;
  }
  function openPin(p) {
    if (p.code) { openBuilding(p.code); return; }
    openPopup(`<div class="pop-head"><span class="pin-dot"></span><div><h3>${esc(p.label)}</h3><span class="muted small">Pin you dropped</span></div></div>
      <div class="pop-actions"><button class="btn btn-ghost btn-sm" type="button" data-unpin="${p.id}">${VH.svg("pin")} Remove pin</button>${homeBtn(p)}</div>`, [p.x, p.y]);
  }

  /* ---------- Pins ---------- */
  function renderPins() {
    pinLayer.innerHTML = pins.map((p) => `<g class="m-pin${p.code ? "" : " is-custom"}${p.is_home ? " is-home" : ""}" data-pin="${p.id}" transform="translate(${p.x} ${p.y - 3})" tabindex="0" role="button" aria-label="Pin: ${esc(p.label)}">
        <ellipse class="m-pin-shadow" rx="4" ry="1.4"/>
        <g class="m-pin-drop"><path d="M0 0c-5.5-7-8-10.8-8-14.2a8 8 0 0 1 16 0c0 3.4-2.5 7.2-8 14.2z"/><circle cy="-14" r="3.2"/></g>
        ${p.code ? "" : `<text class="m-pin-label" y="7">${esc(p.label)}</text>`}
      </g>`).join("");
    $("[data-pin-list]", page).innerHTML = pins.length ? pins.map((p) => {
      const b = p.code && byCode[p.code];
      return `<li class="pin-row">
        <span class="pin-dot"></span>
        <button type="button" class="pin-main" data-show-pin="${p.id}"><strong>${esc(p.label)}</strong><small>${b && b.name !== p.label ? esc(b.name) : b ? esc(b.category) : "Dropped pin"}</small></button>
        ${p.is_home ? `<span class="home-tag">${VH.svg("home")} Home</span>` : `<button class="text-btn" type="button" data-set-home="${p.id}">Set as home</button>`}
        <button class="text-btn danger" type="button" data-unpin="${p.id}">Remove</button>
      </li>`;
    }).join("") : `<li class="day-empty">No pins yet.</li>`;
  }

  async function savePin(body) {
    const res = await VH.api("/api/map/pins", { method: "POST", body });
    pins = res.pins;
    renderPins();
    VH.toast(res.message);
    return res;
  }
  async function removePin(id) {
    const res = await VH.api(`/api/map/pins/${id}`, { method: "DELETE" });
    pins = res.pins;
    renderPins();
    VH.toast(res.message);
  }

  /* ---------- Drop-a-pin mode ---------- */
  const dropBtn = $("[data-drop-pin]", page);
  function setDropMode(on) {
    dropMode = on;
    page.classList.toggle("is-dropping", on);
    dropBtn.setAttribute("aria-pressed", String(on));
    dropBtn.classList.toggle("btn-primary", on);
    dropBtn.classList.toggle("btn-ghost", !on);
    $("[data-drop-banner]", page).hidden = !on;
    if (on) closePopup();
  }
  dropBtn.addEventListener("click", () => setDropMode(!dropMode));
  $("[data-drop-cancel]", page).addEventListener("click", () => setDropMode(false));

  function askPinName(x, y) {
    openPopup(`<form class="pin-form" data-pin-form>
        <div class="pop-head"><span class="pin-dot"></span><div><h3>New pin</h3><span class="muted small">Name this spot</span></div></div>
        <input class="text-input" name="label" maxlength="40" value="My pin" aria-label="Pin name">
        <p class="field-error" data-pin-error></p>
        <div class="pop-actions"><button class="btn btn-primary btn-sm" type="submit">Save pin</button><button class="btn btn-ghost btn-sm" type="button" data-pop-close>Cancel</button></div>
      </form>`, [x, y]);
    const form = $("[data-pin-form]", pop);
    form.dataset.x = x; form.dataset.y = y;
    const input = form.label; input.focus(); input.select();
  }

  /* ---------- Map clicks and hover ---------- */
  let downAt = null;
  svg.addEventListener("click", (e) => {
    if (downAt && Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 6) return;  // it was a drag
    if (dropMode) {
      const [x, y] = toMap(e);
      setDropMode(false);
      askPinName(Math.round(x * 10) / 10, Math.round(y * 10) / 10);
      return;
    }
    // Look up what is under the pointer; after a drag the click event can land on the map itself
    const hit = e.target !== svg ? e.target : (document.elementFromPoint(e.clientX, e.clientY) || e.target);
    const pinEl = hit.closest("[data-pin]");
    if (pinEl) { openPin(pins.find((p) => p.id === Number(pinEl.dataset.pin))); return; }
    if (hit.closest(".m-links")) { openInnerlink(toMap(e)); return; }
    const el = hit.closest(".m-bldg, .m-tag");
    if (el && el.dataset.code) openBuilding(el.dataset.code);
    else closePopup();
  });
  svg.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    if (e.target.closest(".m-links")) { e.preventDefault(); openInnerlink(); return; }
    const el = e.target.closest(".m-bldg, [data-pin]");
    if (!el) return;
    e.preventDefault();
    el.dataset.pin ? openPin(pins.find((p) => p.id === Number(el.dataset.pin))) : openBuilding(el.dataset.code);
  });

  function hover(code, on) {
    const shape = byCode[code]?.shape || code;
    $$(`.m-bldg[data-code="${shape}"], .m-tag[data-code="${code}"]`, svg).forEach((el) => el.classList.toggle("is-hover", on));
  }
  svg.addEventListener("pointermove", (e) => {
    if (dragging || e.pointerType === "touch") return;
    const link = e.target.closest(".m-links");
    const el = link || e.target.closest(".m-bldg, .m-tag");
    $$(".is-hover, .is-route", svg).forEach((x) => x.classList.remove("is-hover", "is-route"));
    if (!el || dropMode) { tip.hidden = true; return; }
    if (link) {
      routeHighlight(true);
      tip.innerHTML = `<strong>Innerlink</strong><span>Indoor walkway from the West Garage to the East Garage · select for details</span>`;
    } else {
      const b = byCode[el.dataset.code];
      if (!b) return;
      hover(el.dataset.code, true);
      tip.innerHTML = `<strong>${esc(b.name)}</strong><span>${esc(b.code)} · ${b.parking ? `about ${b.parking.available.toLocaleString()} spaces open · ` : ""}select for details</span>`;
    }
    tip.hidden = false;
    const r = stage.getBoundingClientRect();
    const x = Math.min(e.clientX - r.left + 14, r.width - tip.offsetWidth - 8);
    const y = Math.max(e.clientY - r.top - tip.offsetHeight - 12, 8);
    tip.style.transform = `translate(${x}px, ${y}px)`;
  });
  svg.addEventListener("pointerleave", () => { tip.hidden = true; $$(".is-hover, .is-route", svg).forEach((x) => x.classList.remove("is-hover", "is-route")); });

  /* ---------- Clicks in the popup and lists ---------- */
  page.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-show-pin]");
    if (!t) return;
    const d = t.dataset;
    try {
      if (d.popClose !== undefined) closePopup();
      else if (d.popTab) { const [tab, code] = d.popTab.split(":"); openBuilding(code, { tab }); }
      else if (d.pinBuilding) { await savePin({ code: d.pinBuilding }); openBuilding(d.pinBuilding); }
      else if (d.unpin) {
        const p = pins.find((x) => x.id === Number(d.unpin));
        await removePin(Number(d.unpin));
        if (p && p.code && !pop.hidden) openBuilding(p.code); else closePopup();
      }
      else if (d.setHome) {
        const res = await VH.api(`/api/map/pins/${d.setHome}/home`, { method: "POST" });
        pins = res.pins;
        renderPins();
        VH.toast(res.message);
        const p = pins.find((x) => x.id === Number(d.setHome));
        if (!pop.hidden && p) openPin(p);
      }
      else if (d.showPin) {
        const p = pins.find((x) => x.id === Number(d.showPin));
        centerOn([p.x, p.y]);
        stage.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => openPin(p), 250);
      }
      else if (d.pick) {
        stage.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => openBuilding(d.pick, { center: true }), 250);
      }
    } catch (err) { VH.toast(err.message, "error"); }
  });
  pop.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-pin-form]");
    if (!form) return;
    e.preventDefault();
    try {
      const res = await savePin({ x: Number(form.dataset.x), y: Number(form.dataset.y), label: form.label.value });
      openPin(res.pins[res.pins.length - 1]);
    } catch (err) { $("[data-pin-error]", form).textContent = err.message; }
  });
  $$("[data-bldg-list] .bldg-row", page).forEach((r) => {
    r.addEventListener("mouseenter", () => hover(r.dataset.pick, true));
    r.addEventListener("mouseleave", () => hover(r.dataset.pick, false));
  });
  $$(".chip", page).forEach((c) => c.addEventListener("click", () => {
    $$(".chip", page).forEach((x) => x.classList.toggle("is-on", x === c));
    $$(".bldg-row", page).forEach((r) => { r.parentElement.hidden = c.dataset.cat && r.dataset.cat !== c.dataset.cat; });
  }));

  /* ---------- Find ---------- */
  const find = $("[data-map-find]", page);
  const results = $("[data-find-results]", page);
  function search(q) {
    q = q.trim().toLowerCase();
    if (!q) return [];
    return list.filter((b) => [b.code, ...b.names, ...b.inside].join(" ").toLowerCase().includes(q)).slice(0, 7);
  }
  find.addEventListener("input", () => {
    const found = search(find.value);
    results.hidden = !find.value.trim();
    results.innerHTML = found.length ? found.map((b) => `<li><button type="button" data-find="${b.code}">
        <span class="code-tag ${b.category === "Parking" ? "is-park" : ""}">${b.code}</span><span>${esc(b.name)}</span></button></li>`).join("")
      : `<li class="find-empty">No buildings match.</li>`;
  });
  find.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const first = search(find.value)[0]; if (first) { choose(first.code); } }
    if (e.key === "Escape") { results.hidden = true; }
  });
  results.addEventListener("click", (e) => { const b = e.target.closest("[data-find]"); if (b) choose(b.dataset.find); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".map-find")) results.hidden = true; });
  function choose(code) { results.hidden = true; find.value = byCode[code].name; openBuilding(code, { center: true }); }

  /* ---------- Zoom, pan and full screen ---------- */
  function apply() {
    svg.setAttribute("viewBox", `${box.x} ${box.y} ${box.w} ${box.h}`);
    page.classList.toggle("is-zoomed", box.w < FULL.w - 1);
    placePopup();
  }
  function clamp() {
    box.w = Math.min(FULL.w, Math.max(110, box.w));
    box.h = box.w * FULL.h / FULL.w;
    box.x = Math.min(FULL.w - box.w, Math.max(0, box.x));
    box.y = Math.min(FULL.h - box.h, Math.max(0, box.y));
  }
  function zoom(factor, cx = box.x + box.w / 2, cy = box.y + box.h / 2) {
    const nw = box.w * factor;
    box.x = cx - (cx - box.x) * (nw / box.w);
    box.y = cy - (cy - box.y) * (nw / box.w);
    box.w = nw;
    clamp(); apply();
  }
  function centerOn([x, y]) {
    if (box.w >= FULL.w - 1) box.w = FULL.w / 2;
    box.x = x - box.w / 2;
    box.y = y - (box.w * FULL.h / FULL.w) / 2;
    clamp(); apply();
  }
  $$("[data-zoom]", page).forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.zoom === "in") zoom(0.7);
    else if (b.dataset.zoom === "out") zoom(1 / 0.7);
    else { box = { ...FULL }; apply(); }
  }));
  svg.addEventListener("wheel", (e) => {
    if (!e.ctrlKey && !e.metaKey && !document.fullscreenElement) return;  // normal scrolling keeps scrolling the page
    e.preventDefault();
    const [cx, cy] = toMap(e);
    zoom(e.deltaY > 0 ? 1.15 : 0.87, cx, cy);
  }, { passive: false });

  // A press only becomes a drag once the pointer moves, so a plain click still reaches the building
  let dragging = false, last = null, pressed = null;
  svg.addEventListener("pointerdown", (e) => {
    downAt = { x: e.clientX, y: e.clientY };
    pressed = (box.w >= FULL.w - 1 || dropMode || e.button !== 0) ? null : e.pointerId;
  });
  svg.addEventListener("pointermove", (e) => {
    if (!dragging && pressed === e.pointerId && downAt && Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 6) {
      dragging = true; last = { x: e.clientX, y: e.clientY };
      svg.setPointerCapture(e.pointerId);
      page.classList.add("is-dragging");
      tip.hidden = true;
    }
    if (!dragging) return;
    const r = svg.getBoundingClientRect();
    box.x -= (e.clientX - last.x) / r.width * box.w;
    box.y -= (e.clientY - last.y) / r.height * box.h;
    last = { x: e.clientX, y: e.clientY };
    clamp(); apply();
  });
  const endDrag = () => { dragging = false; pressed = null; page.classList.remove("is-dragging"); };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);

  const fsBtn = $("[data-fullscreen]", page);
  const mapPanel = $(".map-panel", page);
  fsBtn.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (mapPanel.requestFullscreen) mapPanel.requestFullscreen();
  });
  document.addEventListener("fullscreenchange", () => {
    $("span", fsBtn).textContent = document.fullscreenElement ? "Exit full screen" : "Full screen";
    setTimeout(placePopup, 60);
  });
  window.addEventListener("resize", placePopup);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !pop.hidden && !document.fullscreenElement) closePopup(); });

  renderPins();
  if (page.dataset.selected) openBuilding(page.dataset.selected, { center: true });
  else if (page.dataset.innerlink !== undefined) {
    stage.scrollIntoView({ block: "center" });
    routeHighlight(true);
    openInnerlink();
  }
})();
