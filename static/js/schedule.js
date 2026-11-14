/* Schedule planner: day and week views, classes, assignments, events and .ics import */
(() => {
  "use strict";
  const root = document.querySelector("[data-sch]");
  if (!root) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = VH.esc;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;

  let data = JSON.parse($("#sch-data").textContent);
  const TODAY = parseDate(data.today);
  let cursor = new Date(TODAY);
  let view = window.matchMedia("(max-width: 719px)").matches ? "day" : "week";

  const DAY_LETTERS = "MTWRFSU";            // Monday = M ... Sunday = U
  const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const START_HOUR = 7, END_HOUR = 22, PX_PER_MIN = 0.8;

  /* ---------- Date and time helpers ---------- */
  function parseDate(s) { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); }
  function iso(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
  function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
  function mondayOf(d) { return addDays(d, -((d.getDay() + 6) % 7)); }
  function weekdayIndex(d) { return (d.getDay() + 6) % 7; }
  function minutes(t) { const [h, m] = t.split(":").map(Number); return h * 60 + m; }
  function fmtTime(t) {
    if (!t) return "";
    let [h, m] = t.split(":").map(Number);
    const ap = h < 12 ? "AM" : "PM";
    h = h % 12 || 12;
    return `${h}:${String(m).padStart(2, "0")} ${ap}`;
  }
  function fmtDate(d, withDay = true) {
    return `${withDay ? DAY_NAMES[weekdayIndex(d)] + ", " : ""}${MONTHS[d.getMonth()]} ${d.getDate()}`;
  }
  function daysBetween(a, b) { return Math.round((b - a) / 86400000); }

  /* Common hour: Tuesdays and Thursdays during the term, when no classes meet */
  const CH = data.common_hour;
  const CLOSED = new Set(["2026-09-07", "2026-11-26", "2026-11-27"]);
  function hasCommonHour(day) {
    const key = iso(day);
    return CH && CH.days.includes(DAY_LETTERS[weekdayIndex(day)]) && key >= data.term.start && key <= data.term.end && !CLOSED.has(key);
  }
  const toMin = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };

  /* ---------- Build the items for one day ---------- */
  function itemsFor(day) {
    const key = iso(day);
    const letter = DAY_LETTERS[weekdayIndex(day)];
    const out = [];
    if (key >= data.term.start && key <= data.term.end) {
      data.classes.forEach((c) => {
        if (c.delivery !== "In person" || !c.days || !c.days.includes(letter)) return;
        const canceled = data.cancellations.some((x) => x.course_id === c.id && x.class_date === key);
        out.push({ type: "class", id: c.id, title: c.code, start: c.start_time, end: c.end_time,
                   sub: c.location, canceled, ref: c });
      });
    }
    data.events.filter((e) => e.event_date === key).forEach((e) => {
      out.push({ type: e.kind, id: e.id, title: e.title, start: e.start_time, end: e.end_time, sub: e.location, ref: e });
    });
    const due = data.assignments.filter((a) => a.due_date === key)
      .map((a) => ({ type: "assignment", id: a.id, title: `${a.course_code}: ${a.title}`, start: a.due_time, ref: a, done: !!a.completed }));
    [...out, ...due].forEach((i) => { i.day = key; });
    return { timed: out.filter((i) => i.start).sort((a, b) => a.start.localeCompare(b.start)),
             allDay: [...due, ...out.filter((i) => !i.start)] };
  }

  // Place overlapping items side by side
  function layout(items) {
    const cols = [];
    items.forEach((it) => {
      const s = minutes(it.start), e = it.end ? minutes(it.end) : s + 30;
      it._s = s; it._e = Math.max(e, s + 25);
      let c = cols.findIndex((end) => end <= s);
      if (c === -1) { c = cols.length; cols.push(0); }
      cols[c] = it._e;
      it._col = c;
    });
    items.forEach((it) => {
      it._cols = Math.max(1, ...items.filter((o) => o._s < it._e && o._e > it._s).map((o) => o._col + 1));
    });
    return items;
  }

  const TYPE_LABEL = { class: "Class", assignment: "Assignment due", personal: "Personal", campus: "Campus event", imported: "Blackboard" };

  function chip(it, compact = false) {
    const time = it.type === "assignment" ? `Due ${fmtTime(it.start)}` : it.start ? `${fmtTime(it.start)}${it.end ? " to " + fmtTime(it.end) : ""}` : "All day";
    return `<button type="button" class="sch-item k-${it.type}${it.canceled ? " is-canceled" : ""}${it.done ? " is-done" : ""}"
              data-open="${it.type}:${it.id}:${it.day}">
      <strong>${esc(it.title)}${it.canceled ? " · Canceled" : ""}</strong>
      ${compact ? "" : `<small>${esc(time)}${it.sub ? " · " + esc(it.sub) : ""}</small>`}
    </button>`;
  }

  /* ---------- Week view ---------- */
  function renderWeek() {
    const start = mondayOf(cursor);
    const days = [...Array(7)].map((_, i) => addDays(start, i));
    const end = days[6];
    $("[data-sch-range]").textContent = start.getMonth() === end.getMonth()
      ? `${MONTHS[start.getMonth()]} ${start.getDate()} to ${end.getDate()}, ${end.getFullYear()}`
      : `${MONTHS[start.getMonth()].slice(0, 3)} ${start.getDate()} to ${MONTHS[end.getMonth()].slice(0, 3)} ${end.getDate()}, ${end.getFullYear()}`;
    const height = (END_HOUR - START_HOUR) * 60 * PX_PER_MIN;
    let hours = "";
    for (let h = START_HOUR; h < END_HOUR; h++) {
      hours += `<div class="wk-hour" style="top:${(h - START_HOUR) * 60 * PX_PER_MIN}px">${fmtTime(`${String(h).padStart(2, "0")}:00`).replace(":00", "")}</div>`;
    }
    const cols = days.map((d) => {
      const { timed, allDay } = itemsFor(d);
      const isToday = iso(d) === iso(TODAY);
      const blocks = layout(timed).map((it) => {
        const top = Math.max(0, (it._s - START_HOUR * 60) * PX_PER_MIN);
        const h = Math.max(22, (it._e - it._s) * PX_PER_MIN - 2);
        const w = 100 / it._cols;
        return `<div class="wk-block" style="top:${top}px;height:${h}px;left:calc(${w * it._col}% + 2px);width:calc(${w}% - 4px)">${chip(it, h < 34)}</div>`;
      }).join("");
      return `<div class="wk-col${isToday ? " is-today" : ""}">
        <div class="wk-head"><span>${SHORT[weekdayIndex(d)]}</span><strong>${d.getDate()}</strong></div>
        <div class="wk-allday">${allDay.map((it) => chip(it, true)).join("")}</div>
        <div class="wk-grid" style="height:${height}px">${hasCommonHour(d)
          ? `<div class="wk-common" style="top:${(toMin(CH.start) - START_HOUR * 60) * PX_PER_MIN}px;height:${(toMin(CH.end) - toMin(CH.start)) * PX_PER_MIN}px" title="Common hour: no classes meet"><span>Common hour</span></div>` : ""}${blocks}</div>
      </div>`;
    }).join("");
    $("[data-sch-body]").innerHTML = `<div class="wk-scroll"><div class="wk">
      <div class="wk-gutter"><div class="wk-head"></div><div class="wk-allday wk-allday-label">Due</div>
        <div class="wk-grid" style="height:${height}px">${hours}</div></div>
      ${cols}</div></div>`;
    // Lines for each hour
    $$(".wk-col .wk-grid").forEach((g) => { g.style.backgroundSize = `100% ${60 * PX_PER_MIN}px`; });
  }

  /* ---------- Walking times (same estimate the server uses on Home) ---------- */
  const W = data.walk;
  function buildingFor(location) {
    const text = (location || "").toLowerCase();
    const hit = W.names.find(([name]) => text.includes(name));
    return hit ? hit[1] : null;
  }
  function walkMinutes(a, b) {
    const miles = Math.hypot(a[0] - b[0], a[1] - b[1]) / W.units_per_mile * W.path_factor;
    return Math.ceil(miles / W.mph * 60 + W.buffer);
  }
  // First class starts from home; each later class starts from the previous class's building
  // After a break longer than max_gap minutes, the next walk starts from home again
  function walkLines(timed) {
    let prev = null;  // { place, end } of the last building
    const out = new Map();
    timed.filter((it) => (it.type === "class" || it.type === "personal" || it.type === "campus" || it.type === "imported") && !it.canceled && it.start).forEach((it) => {
      const code = buildingFor(it.sub);
      if (!code || !W.points[code]) return;
      const from = prev && toMin(it.start) - prev.end <= W.max_gap ? prev.place : W.home;
      if (from.code === code) out.set(it, { same: true, from: from.label, fromHome: from === W.home });
      else {
        const minutes = walkMinutes(from.point, W.points[code]);
        const leave = minutes ? toMin(it.start) - minutes : 0;
        out.set(it, { from: from.label, minutes, leave: `${String(Math.floor(leave / 60)).padStart(2, "0")}:${String(leave % 60).padStart(2, "0")}`,
                      indoor: W.route.includes(from.code) && W.route.includes(code) });
      }
      prev = { place: { label: W.building_names[code], code, point: W.points[code] }, end: toMin(it.end || it.start) };
    });
    return out;
  }
  function walkHTML(w) {
    if (!w) return "";
    return `<span class="walk-line">${VH.svg("walk")}<span>${w.same ? (w.fromHome ? `At your home building, ${esc(w.from)}` : "Same building as your last stop")
      : `${w.minutes} min walk from ${esc(w.from)}, leave by ${fmtTime(w.leave)}`}</span>${w.indoor
      ? ` <a class="walk-indoor" href="/campus-map?innerlink=1">Indoor route: Innerlink</a>` : ""}</span>`;
  }

  /* ---------- Day view ---------- */
  function renderDay() {
    $("[data-sch-range]").textContent = `${fmtDate(cursor)}, ${cursor.getFullYear()}`;
    const { timed, allDay } = itemsFor(cursor);
    const online = data.classes.filter((c) => c.delivery === "Online");
    const isWeekday = weekdayIndex(cursor) < 5;
    const walks = walkLines(timed);
    const list = (items) => items.map((it) => `<li class="day-row">
        <span class="day-time">${it.type === "assignment" ? "Due " + fmtTime(it.start) : it.start ? fmtTime(it.start) : "All day"}
          ${it.end ? `<small>${fmtTime(it.end)}</small>` : ""}</span><div class="day-main">${chip(it)}${walkHTML(walks.get(it))}</div></li>`).join("");
    let html = "";
    if (allDay.length) html += `<h4 class="day-label">Due and all day</h4><ul class="day-list">${list(allDay)}</ul>`;
    html += `<h4 class="day-label">Schedule</h4>`;
    const commonBusy = timed.some((it) => it.type !== "class" && it.type !== "assignment" && it.start < CH.end && (it.end || it.start) > CH.start);
    if (hasCommonHour(cursor) && !commonBusy) {
      html += `<p class="day-common">${VH.svg("clock")}<span><strong>Common hour</strong>, ${fmtTime(CH.start)} to ${fmtTime(CH.end)}. No classes meet, so it's a good time for clubs and campus events.</span></p>`;
    }
    html += timed.length ? `<ul class="day-list">${list(timed)}</ul>` : `<p class="day-empty">Nothing scheduled. Enjoy the free time, Viking.</p>`;
    if (isWeekday && online.length) {
      html += `<p class="online-note">${VH.svg("calendar")}<span>${online.map((c) => `<strong>${esc(c.code)}</strong>`).join(", ")} ${online.length > 1 ? "are" : "is"} online, with coursework in Blackboard.</span></p>`;
    }
    $("[data-sch-body]").innerHTML = `<div class="day-view">${html}</div>`;
  }

  /* ---------- Deadlines and classes lists ---------- */
  let showPast = false;
  function deadlineRow(a) {
    const left = daysBetween(TODAY, parseDate(a.due_date));
    const when = left < 0 ? "Past due" : left === 0 ? "Due today" : left === 1 ? "Due tomorrow" : `Due in ${left} days`;
    const soon = !a.completed && left >= 0 && left <= 14;
    return `<li class="deadline${soon ? " is-soon" : ""}${a.completed ? " is-done" : ""}">
      <label class="check"><input type="checkbox" data-toggle-done="${a.id}" ${a.completed ? "checked" : ""}>
        <span class="check-box" aria-hidden="true">${VH.svg("check")}</span><span class="visually-hidden">Mark ${esc(a.title)} complete</span></label>
      <button type="button" class="deadline-main" data-open="assignment:${a.id}:${a.due_date}">
        <strong>${esc(a.course_code)}: ${esc(a.title)}</strong>
        <small>${fmtDate(parseDate(a.due_date))} at ${fmtTime(a.due_time)}</small>
      </button>
      <span class="deadline-when">${a.completed ? "Done" : when}</span>
    </li>`;
  }
  function renderDeadlines() {
    const sorted = [...data.assignments].sort((a, b) => (a.due_date + a.due_time).localeCompare(b.due_date + b.due_time));
    const todayKey = iso(TODAY);
    const upcoming = sorted.filter((a) => a.due_date >= todayKey || !a.completed);
    const past = sorted.filter((a) => a.due_date < todayKey && a.completed).reverse();
    let html = upcoming.length ? upcoming.map(deadlineRow).join("") : `<li class="day-empty">Nothing due. Nice work.</li>`;
    if (past.length) {
      html += `<li class="deadline-past-toggle"><button class="text-btn" type="button" data-toggle-past>${showPast ? "Hide past assignments" : `Show past assignments (${past.length})`}</button></li>`;
      if (showPast) html += past.map(deadlineRow).join("");
    }
    $("[data-deadlines]").innerHTML = html;
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-toggle-past]")) { showPast = !showPast; renderDeadlines(); }
  });

  function renderClasses() {
    const DAYS = { M: "Mon", T: "Tue", W: "Wed", R: "Thu", F: "Fri", S: "Sat", U: "Sun" };
    $("[data-classes]").innerHTML = data.classes.map((c) => `<li class="class-card">
      <div>
        <div class="task-title"><strong>${esc(c.code)}</strong><span class="tag ${c.delivery === "Online" ? "" : "tag-required"}">${c.delivery}</span></div>
        <small>${c.delivery === "Online" ? "No set meeting time · Blackboard" : `${[...c.days].map((d) => DAYS[d]).join(", ")} · ${fmtTime(c.start_time)} to ${fmtTime(c.end_time)}`}</small>
        <small>${c.location ? esc(c.location) + " · " : ""}${esc(c.professor)}</small>
      </div>
      <div class="class-card-actions">
        <button class="text-btn" type="button" data-edit-class="${c.id}">Edit</button>
        <button class="text-btn danger" type="button" data-delete-class="${c.id}">Delete</button>
      </div>
    </li>`).join("") || `<li class="day-empty">No classes yet.</li>`;
  }

  function render() {
    $$("[data-sch-view]").forEach((b) => b.classList.toggle("is-on", b.dataset.schView === view));
    view === "week" ? renderWeek() : renderDay();
    // In day view, any day from Nov 12 to the end of the term can become the app's today
    const key = iso(cursor);
    const makeDay = $("[data-sch-make-day]");
    makeDay.hidden = !(view === "day" && key !== data.today && key >= data.default_today && key <= data.term.end);
    renderDeadlines();
    renderClasses();
  }

  /* ---------- Toolbar ---------- */
  $("[data-sch-prev]").addEventListener("click", () => { cursor = addDays(cursor, view === "week" ? -7 : -1); render(); });
  $("[data-sch-next]").addEventListener("click", () => { cursor = addDays(cursor, view === "week" ? 7 : 1); render(); });
  $("[data-sch-today]").addEventListener("click", () => { cursor = new Date(TODAY); render(); });
  $$("[data-sch-view]").forEach((b) => b.addEventListener("click", () => { view = b.dataset.schView; render(); }));
  $("[data-sch-make-day]").addEventListener("click", () => VH.setAppDate(iso(cursor)));

  // A live moment (like a class canceled) can change the schedule while it's open
  document.addEventListener("vh:schedule-changed", async () => {
    try { data = (await VH.api("/api/schedule/data")).data; render(); } catch (_) { /* keep what's shown */ }
  });

  /* ---------- Export ---------- */
  const exportForm = $("[data-export]");
  exportForm.addEventListener("submit", (e) => {
    const any = $$('input[name="part"]:checked', exportForm).length > 0;
    $("[data-export-error]", exportForm).textContent = any ? "" : "Choose at least one thing to include.";
    if (!any) { e.preventDefault(); return; }
    VH.toast("Your calendar file is downloading");
  });

  const addMenu = $("[data-add-menu]");
  const addPanel = $(".add-menu", addMenu);
  const addToggle = $("[data-add-toggle]", addMenu);
  addToggle.addEventListener("click", (e) => { e.stopPropagation(); addPanel.hidden = !addPanel.hidden; addToggle.setAttribute("aria-expanded", String(!addPanel.hidden)); });
  document.addEventListener("click", (e) => { if (!addMenu.contains(e.target)) addPanel.hidden = true; });

  /* ---------- Dialog ---------- */
  const dlg = $("#sch-dialog");
  const body = $("[data-sch-dialog-body]", dlg);
  const open = (html) => { body.innerHTML = html; dlg.showModal(); };
  const close = () => dlg.close();
  dlg.addEventListener("click", (e) => { if (e.target === dlg) close(); });

  async function send(url, method, payload) {
    const res = await VH.api(url, { method, body: payload });
    data = res.data;
    render();
    VH.toast(res.message);
    return res;
  }

  function field(label, input, hint = "") {
    return `<label class="form-field"><span class="field-label">${label}</span>${input}${hint ? `<small class="muted">${hint}</small>` : ""}</label>`;
  }
  const input = (name, value = "", type = "text", extra = "") =>
    `<input class="text-input" name="${name}" type="${type}" value="${esc(value ?? "")}" ${extra}>`;

  /* Details */
  // Walking time to this class on the day it was opened from
  function walkFor(c, onDate) {
    if (!onDate || c.delivery !== "In person") return "";
    const { timed } = itemsFor(parseDate(onDate));
    const item = timed.find((i) => i.type === "class" && i.id === c.id && !i.canceled);
    const w = item && walkLines(timed).get(item);
    return w ? `<div><dt>Getting there</dt><dd>${walkHTML(w)}</dd></div>` : "";
  }

  function showDetails(type, id, onDate) {
    if (type === "class") {
      const c = data.classes.find((x) => x.id === id);
      const canceled = data.cancellations.some((x) => x.course_id === id && x.class_date === onDate);
      open(`<h2 id="sch-dialog-title">${esc(c.code)}</h2>
        <p class="detail-type k-class">Class · ${c.delivery}${canceled ? " · Canceled " + fmtDate(parseDate(onDate)) : ""}</p>
        <dl class="detail-list">
          ${c.days ? `<div><dt>Meets</dt><dd>${esc(c.days)} · ${fmtTime(c.start_time)} to ${fmtTime(c.end_time)}</dd></div>` : ""}
          ${c.location ? `<div><dt>Location</dt><dd>${esc(c.location)}</dd></div>` : ""}
          <div><dt>Professor</dt><dd>${esc(c.professor)}</dd></div>
          <div><dt>Status</dt><dd>${esc(c.status)}</dd></div>
          ${walkFor(c, onDate)}
        </dl>
        ${canceled ? `<p class="notice-inline">This class does not meet on ${fmtDate(parseDate(onDate))}. Watch Blackboard for updates.</p>` : ""}
        <div class="dialog-actions">
          <button class="btn btn-ghost" type="button" data-close>Close</button>
          <button class="btn btn-primary" type="button" data-edit-class="${c.id}">Edit class</button>
        </div>`);
    } else if (type === "assignment") {
      const a = data.assignments.find((x) => x.id === id);
      const left = daysBetween(TODAY, parseDate(a.due_date));
      open(`<h2 id="sch-dialog-title">${esc(a.title)}</h2>
        <p class="detail-type k-assignment">Assignment · ${esc(a.course_code)}</p>
        <dl class="detail-list">
          <div><dt>Due</dt><dd>${fmtDate(parseDate(a.due_date))}, ${parseDate(a.due_date).getFullYear()} at ${fmtTime(a.due_time)}</dd></div>
          <div><dt>Status</dt><dd>${a.completed ? "Complete" : left < 0 ? "Past due" : `Not complete · due in ${left} day${left === 1 ? "" : "s"}`}</dd></div>
        </dl>
        <div class="dialog-actions">
          <button class="btn btn-ghost danger-text" type="button" data-delete-assignment="${a.id}">Delete</button>
          <button class="btn btn-ghost" type="button" data-toggle-done="${a.id}">${a.completed ? "Mark not complete" : "Mark complete"}</button>
          <button class="btn btn-primary" type="button" data-edit-assignment="${a.id}">Edit</button>
        </div>`);
    } else {
      const e = data.events.find((x) => x.id === id);
      open(`<h2 id="sch-dialog-title">${esc(e.title)}</h2>
        <p class="detail-type k-${e.kind}">${TYPE_LABEL[e.kind]}</p>
        <dl class="detail-list">
          <div><dt>When</dt><dd>${fmtDate(parseDate(e.event_date))}${e.start_time ? `, ${fmtTime(e.start_time)}${e.end_time ? " to " + fmtTime(e.end_time) : ""}` : ", all day"}</dd></div>
          ${e.location ? `<div><dt>Location</dt><dd>${esc(e.location)}</dd></div>` : ""}
          ${e.notes ? `<div><dt>Notes</dt><dd>${esc(e.notes)}</dd></div>` : ""}
        </dl>
        <div class="dialog-actions">
          <button class="btn btn-ghost danger-text" type="button" data-delete-event="${e.id}">${e.booked ? "Cancel reservation" : e.kind === "personal" ? "Delete" : "Remove"}</button>
          ${e.booked ? `<a class="btn btn-primary" href="/book-a-space${/at the Rec$/.test(e.title) ? "?tab=rec" : ""}">Open Book a space</a>`
            : e.kind === "personal" ? `<button class="btn btn-primary" type="button" data-edit-event="${e.id}">Edit</button>` : `<button class="btn btn-primary" type="button" data-close>Close</button>`}
        </div>`);
    }
  }

  /* Forms */
  function classForm(c = null) {
    const days = c?.days || "";
    open(`<form data-form="class" data-id="${c?.id || ""}" novalidate>
      <h2 id="sch-dialog-title">${c ? "Edit class" : "Add class"}</h2>
      <div class="form-grid">
        ${field("Course code", input("code", c?.code, "text", 'placeholder="ENG 102" maxlength="12"'))}
        ${field("Professor", input("professor", c?.professor, "text", 'placeholder="Prof. Hayes"'))}
      </div>
      <fieldset class="choice-list two-col"><legend class="field-label">Delivery</legend>
        ${["In person", "Online"].map((d) => `<label class="choice"><input type="radio" name="delivery" value="${d}" ${(c?.delivery || "In person") === d ? "checked" : ""}><span>${d}</span></label>`).join("")}
      </fieldset>
      <div data-inperson>
        <fieldset class="day-pick"><legend class="field-label">Meets on</legend>
          ${[["M", "Mon"], ["T", "Tue"], ["W", "Wed"], ["R", "Thu"], ["F", "Fri"]].map(([k, l]) => `<label><input type="checkbox" name="days" value="${k}" ${days.includes(k) ? "checked" : ""}><span>${l}</span></label>`).join("")}
        </fieldset>
        <div class="form-grid">
          ${field("Starts", input("start_time", c?.start_time, "time"))}
          ${field("Ends", input("end_time", c?.end_time, "time"))}
        </div>
        ${field("Building and room", input("location", c?.location, "text", 'placeholder="Berkman Hall 436"'))}
      </div>
      <p class="field-error" data-form-error></p>
      <div class="dialog-actions">
        <button class="btn btn-ghost" type="button" data-close>Cancel</button>
        <button class="btn btn-primary" type="submit">${c ? "Save changes" : "Add class"}</button>
      </div></form>`);
    const form = $("form", body);
    const sync = () => { $("[data-inperson]", form).hidden = form.delivery.value === "Online"; };
    $$('input[name="delivery"]', form).forEach((r) => r.addEventListener("change", sync));
    sync();
  }

  function assignmentForm(a = null) {
    const courses = [...new Set(data.classes.map((c) => c.code))];
    if (a && !courses.includes(a.course_code)) courses.push(a.course_code);
    open(`<form data-form="assignment" data-id="${a?.id || ""}" novalidate>
      <h2 id="sch-dialog-title">${a ? "Edit assignment" : "Add assignment"}</h2>
      ${field("Course", `<select class="text-input" name="course_code">${courses.map((c) => `<option ${a?.course_code === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>`)}
      ${field("Assignment", input("title", a?.title, "text", 'placeholder="Chapter 8 reading"'))}
      <div class="form-grid">
        ${field("Due date", input("due_date", a?.due_date || iso(cursor), "date"))}
        ${field("Due time", input("due_time", a?.due_time || "23:59", "time"))}
      </div>
      <label class="check"><input type="checkbox" name="completed" ${a?.completed ? "checked" : ""}><span class="check-box" aria-hidden="true">${VH.svg("check")}</span> Completed</label>
      <p class="field-error" data-form-error></p>
      <div class="dialog-actions">
        <button class="btn btn-ghost" type="button" data-close>Cancel</button>
        <button class="btn btn-primary" type="submit">${a ? "Save changes" : "Add assignment"}</button>
      </div></form>`);
  }

  function eventForm(e = null) {
    open(`<form data-form="event" data-id="${e?.id || ""}" novalidate>
      <h2 id="sch-dialog-title">${e ? "Edit event" : "Add personal event"}</h2>
      ${field("Event", input("title", e?.title, "text", 'placeholder="Study group"'))}
      ${field("Date", input("event_date", e?.event_date || iso(cursor), "date"))}
      <div class="form-grid">
        ${field("Starts", input("start_time", e?.start_time, "time"), "Leave both times empty for all day")}
        ${field("Ends", input("end_time", e?.end_time, "time"))}
      </div>
      ${field("Location", input("location", e?.location, "text", 'placeholder="Optional"'))}
      ${field("Notes", `<textarea class="textarea" name="notes" maxlength="300" placeholder="Optional">${esc(e?.notes || "")}</textarea>`)}
      <p class="field-error" data-form-error></p>
      <div class="dialog-actions">
        <button class="btn btn-ghost" type="button" data-close>Cancel</button>
        <button class="btn btn-primary" type="submit">${e ? "Save changes" : "Add event"}</button>
      </div></form>`);
  }

  // Submit any form in the dialog
  dlg.addEventListener("submit", async (ev) => {
    const form = ev.target.closest("form[data-form]");
    if (!form) return;
    ev.preventDefault();
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    if (form.dataset.form === "class") payload.days = fd.getAll("days").join("");
    if (form.dataset.form === "assignment") payload.completed = fd.has("completed");
    const kind = { class: "classes", assignment: "assignments", event: "events" }[form.dataset.form];
    const id = form.dataset.id;
    try {
      await send(`/api/schedule/${kind}${id ? "/" + id : ""}`, id ? "PUT" : "POST", payload);
      close();
    } catch (err) {
      $("[data-form-error]", form).textContent = err.message;
    }
  });

  /* ---------- Clicks everywhere on the page and in the dialog ---------- */
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-open]");
    if (!t || !root.contains(t) && !dlg.contains(t)) return;
    const d = t.dataset;
    try {
      if (d.open) { const [type, id, day] = d.open.split(":"); showDetails(type === "personal" || type === "campus" || type === "imported" ? "event" : type, Number(id), day); }
      else if (d.close !== undefined) close();
      else if (d.add) {
        addPanel.hidden = true;
        ({ class: classForm, assignment: assignmentForm, event: eventForm })[d.add]();
      }
      else if (d.editClass) classForm(data.classes.find((c) => c.id === Number(d.editClass)));
      else if (d.editAssignment) assignmentForm(data.assignments.find((a) => a.id === Number(d.editAssignment)));
      else if (d.editEvent) eventForm(data.events.find((x) => x.id === Number(d.editEvent)));
      else if (d.deleteClass) {
        const c = data.classes.find((x) => x.id === Number(d.deleteClass));
        if (dlg.open) close();
        if (await VH.confirm({ title: `Delete ${c.code}?`, body: "It will be removed from your planner. This doesn't drop the class in CampusNet.", confirmLabel: "Delete class", danger: true })) {
          await send(`/api/schedule/classes/${c.id}`, "DELETE");
        }
      }
      else if (d.deleteAssignment) {
        close();
        if (await VH.confirm({ title: "Delete this assignment?", confirmLabel: "Delete", danger: true })) await send(`/api/schedule/assignments/${d.deleteAssignment}`, "DELETE");
      }
      else if (d.deleteEvent) {
        close();
        if (await VH.confirm({ title: "Remove this event from your schedule?", confirmLabel: "Remove", danger: true })) await send(`/api/schedule/events/${d.deleteEvent}`, "DELETE");
      }
    } catch (err) { VH.toast(err.message, "error"); }
  });

  // Complete / not complete (checkbox in the list, or button in details)
  document.addEventListener("change", async (e) => {
    const box = e.target.closest("input[data-toggle-done]");
    if (!box) return;
    try { await send(`/api/schedule/assignments/${box.dataset.toggleDone}`, "PATCH"); }
    catch (err) { box.checked = !box.checked; VH.toast(err.message, "error"); }
  });
  dlg.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-toggle-done]");
    if (!b) return;
    try { await send(`/api/schedule/assignments/${b.dataset.toggleDone}`, "PATCH"); close(); }
    catch (err) { VH.toast(err.message, "error"); }
  });

  /* ---------- Blackboard .ics import ---------- */
  const importForm = $("[data-import]");
  const fileInput = $("[data-import-file]");
  const importError = $("[data-import-error]");
  fileInput.addEventListener("change", () => {
    $("[data-import-name]").textContent = fileInput.files[0]?.name || "Choose .ics file";
    importError.textContent = "";
  });
  importForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fileInput.files.length) { importError.textContent = "Choose a calendar file to import."; return; }
    const fd = new FormData();
    fd.append("calendar", fileInput.files[0]);
    try {
      const res = await fetch("/api/schedule/import", { method: "POST", body: fd, headers: { "X-CSRF-Token": csrf }, credentials: "same-origin" });
      const out = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(out.error || "That file couldn't be imported.");
      data = out.data;
      render();
      VH.toast(out.message);
      importForm.reset();
      $("[data-import-name]").textContent = "Choose .ics file";
    } catch (err) { importError.textContent = err.message; }
  });

  render();
})();
