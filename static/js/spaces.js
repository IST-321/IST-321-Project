/* Book a space: library room reservations and Rec Center group fitness */
(() => {
  "use strict";
  const page = document.querySelector("[data-sp-page]");
  if (!page) return;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = VH.esc;
  const data = JSON.parse($("#sp-data").textContent);

  const dayButton = (iso, on, small) => `<button type="button" role="tab" class="lv-day${on ? " is-on" : ""}" aria-selected="${on}" data-day="${iso}">
      <span>${VH.fmtDate(iso, { short: true }).split(",")[0]}</span><strong>${VH.parseDate(iso).getDate()}</strong><small>${small}</small></button>`;
  const clashText = (list) => list.map((c) => `${c.title} (${VH.fmtTime(c.start)} to ${VH.fmtTime(c.end || c.start)})`).join(", ");
  function showLock(msg) {
    $$("[data-sp-lock]", page).forEach((el) => {
      el.hidden = !msg;
      el.innerHTML = msg ? `${VH.svg("lock")}<span>${esc(msg)}</span>` : "";
    });
  }

  /* =========================================================
     Library rooms
     ========================================================= */
  if ($("[data-room-pick]", page)) {
    let state = data.room_state;
    let room = data.rooms[0].id, day = null, time = null, hours = 1;
    const roomOf = () => data.rooms.find((r) => r.id === room);

    function slotsFor(r, d) {
      const days = state.slots[r] || [];
      return days.find((x) => x.date === d);
    }
    // A start time works only when every hour of the booking is free
    function fits(dayInfo, t) {
      const start = Number(t.slice(0, 2));
      for (let i = 0; i < hours; i++) {
        const s = dayInfo.slots.find((x) => Number(x.time.slice(0, 2)) === start + i);
        if (!s || s.free <= 0) return false;
      }
      return true;
    }

    function render() {
      showLock(state.locked);
      const r = roomOf();
      $$("[data-room]", page).forEach((b) => { b.classList.toggle("is-on", b.dataset.room === room); b.setAttribute("aria-checked", String(b.dataset.room === room)); });
      $("[data-room-length]", page).hidden = r.lengths.length < 2 || !!state.locked;
      if (r.lengths.length < 2) hours = 1;
      $$("[data-hours]", page).forEach((b) => b.classList.toggle("is-on", Number(b.dataset.hours) === hours));
      $("[data-room-course]", page).hidden = !r.needs_course || !time;

      const days = state.slots[room] || [];
      if (!days.find((d) => d.date === day)) day = (days.find((d) => !d.closed) || {}).date || null;
      $("[data-room-days]", page).innerHTML = days.map((d) => {
        const open = d.closed ? 0 : d.slots.filter((s) => fits(d, s.time)).length;
        return dayButton(d.date, d.date === day, d.closed ? "Closed" : open ? `${open} open` : "Full");
      }).join("");
      const info = day && slotsFor(room, day);
      $("[data-room-slots]", page).innerHTML = state.locked ? "" : !info ? `<p class="muted">No open days this week.</p>`
        : info.closed ? `<p class="muted">The library is closed that day.</p>`
        : info.slots.length ? info.slots.map((s) => {
            const ok = fits(info, s.time);
            const endH = Number(s.time.slice(0, 2)) + hours;
            return `<button type="button" class="lv-slot${s.time === time ? " is-on" : ""}" data-time="${s.time}" ${ok ? "" : "disabled"}>
              <strong>${VH.fmtTime(s.time)}</strong><small>${ok ? `to ${VH.fmtTime(`${String(endH).padStart(2, "0")}:00`)}` : "Taken"}</small></button>`;
          }).join("") : `<p class="muted">No times left today.</p>`;

      const confirm = $("[data-room-confirm]", page);
      confirm.hidden = !time;
      if (time) {
        const endH = Number(time.slice(0, 2)) + hours;
        $("[data-room-choice]", page).innerHTML = `<strong>${esc(r.name)}</strong>, ${VH.fmtDate(day)} from <strong>${VH.fmtTime(time)}</strong> to <strong>${VH.fmtTime(`${String(endH).padStart(2, "0")}:00`)}</strong>`;
      }
      $("[data-room-mine]", page).innerHTML = state.mine.length ? state.mine.map((b) => `
        <li class="loan is-requested">
          <span class="row-icon">${VH.svg("door")}</span>
          <div class="row-text"><strong>${esc(b.room_name)}${b.unit > 1 || b.room === "video" ? ` ${b.unit}` : ""}</strong>
            <small>${VH.fmtDate(b.book_date)}, ${VH.fmtTime(b.start_time)} to ${VH.fmtTime(b.end_time)} · ${esc(b.where)}${b.details ? ` · ${esc(b.details)}` : ""}</small></div>
          <button class="link-btn small" type="button" data-room-cancel="${b.id}">Cancel</button>
        </li>`).join("") : `<li class="report-empty">No rooms reserved.</li>`;
    }
    render();

    page.addEventListener("click", async (e) => {
      const rb = e.target.closest("[data-room]");
      const db = e.target.closest("[data-room-days] [data-day]");
      const hb = e.target.closest("[data-hours]");
      const sb = e.target.closest("[data-room-slots] [data-time]");
      const cancel = e.target.closest("[data-room-cancel]");
      if (rb) { room = rb.dataset.room; time = null; render(); }
      if (db) { day = db.dataset.day; time = null; render(); }
      if (hb) { hours = Number(hb.dataset.hours); time = null; render(); }
      if (sb && !sb.disabled) { time = sb.dataset.time; $("[data-room-error]", page).textContent = ""; render(); }
      if (cancel) {
        const ok = await VH.confirm({ title: "Cancel this reservation?", body: "It comes off your schedule too.", confirmLabel: "Cancel reservation", danger: true });
        if (!ok) return;
        try {
          const res = await VH.api(`/api/spaces/rooms/${cancel.dataset.roomCancel}/cancel`, { method: "POST" });
          state = res.state; render(); VH.toast(res.message);
        } catch (err) { VH.toast(err.message, "error"); }
      }
    });

    async function book(confirm = false) {
      const err = $("[data-room-error]", page);
      const body = { room, date: day, time, hours, confirm,
                     course: $("#rc-course").value.trim(), instructor: $("#rc-instructor").value.trim() };
      if (roomOf().needs_course && (!body.course || !body.instructor)) { err.textContent = "Add the course and instructor for the presentation."; return; }
      if (!confirm) {
        const ok = await VH.confirm({ title: "Reserve this room?", confirmLabel: "Reserve",
          body: "If your plans change, cancel at least 2 hours before your start time. Repeated no-shows without canceling 2 hours ahead mean losing online room booking for one semester." });
        if (!ok) return;
      }
      try {
        const res = await VH.api("/api/spaces/rooms", { method: "POST", body });
        if (res.needs_confirm) {
          const ok = await VH.confirm({ title: "This overlaps your schedule", body: `It overlaps ${clashText(res.conflicts)}. Reserve it anyway?`, confirmLabel: "Reserve anyway" });
          if (ok) book(true);
          return;
        }
        state = res.state; time = null; render();
        VH.toast(res.message);
        VH.alerts.refresh();
      } catch (ex) { err.textContent = ex.message; }
    }
    $("[data-room-book]", page).addEventListener("click", () => book());
  }

  /* =========================================================
     Rec Center
     ========================================================= */
  if ($("[data-fit-list]", page)) {
    let state = data.rec;
    let day = state.days[0];

    function chart() {
      const bars = state.crowd[day] || [];
      if (!bars.length) return "";
      const W = 100 / bars.length;
      const nowHour = state.now.date === day ? state.now.hour : null;
      const LV = { Quiet: "is-quiet", Moderate: "is-mid", Busy: "is-busy" };
      return `<svg class="crowd-svg" viewBox="0 0 100 46" preserveAspectRatio="none" role="img"
          aria-label="Usual crowd by hour on ${esc(VH.fmtDate(day))}">
        ${bars.map((b, i) => `<rect class="${LV[b.level]}${b.hour === nowHour ? " is-now" : ""}" x="${(i * W + W * 0.12).toFixed(2)}" y="${(40 - b.value * 0.38).toFixed(2)}"
            width="${(W * 0.76).toFixed(2)}" height="${(b.value * 0.38).toFixed(2)}" rx="0.6"><title>${VH.fmtTime(`${String(b.hour).padStart(2, "0")}:00`)}: ${b.level.toLowerCase()}</title></rect>`).join("")}
      </svg>
      <div class="crowd-axis">${bars.map((b, i) => (i % 3 === 0 ? `<span style="left:${(i * W + W / 2).toFixed(2)}%">${VH.fmtTime(`${String(b.hour).padStart(2, "0")}:00`).replace(":00", "")}</span>` : "")).join("")}</div>
      <p class="crowd-key"><span class="ck is-quiet"></span>Quiet <span class="ck is-mid"></span>Moderate <span class="ck is-busy"></span>Busy
        ${nowHour !== null && bars.some((b) => b.hour === nowHour) ? `· Now: <strong>${bars.find((b) => b.hour === nowHour).level.toLowerCase()}</strong>` : ""}</p>`;
    }

    function render() {
      showLock(state.locked);
      $("[data-rec-days]", page).innerHTML = state.days.map((d) => {
        const n = state.sessions.filter((s) => s.date === d).length;
        return dayButton(d, d === day, n ? `${n} class${n === 1 ? "" : "es"}` : "No classes");
      }).join("");
      $("[data-crowd]", page).innerHTML = chart();
      const list = state.sessions.filter((s) => s.date === day);
      $("[data-fit-list]", page).innerHTML = list.length ? list.map((s) => `
        <li class="fit${s.signup ? " is-added" : ""}${s.conflicts.length ? " has-conflict" : ""}">
          <div class="fit-time"><strong>${VH.fmtTime(s.start)}</strong><small>${s.minutes} min</small></div>
          <div class="fit-main">
            <strong>${esc(s.name)}</strong><small>${esc(s.room)}</small>
            <p>${esc(s.description)}</p>
            ${s.conflicts.length ? `<p class="ev-conflict">${VH.svg("warning")}<span>Overlaps ${esc(clashText(s.conflicts))}</span></p>` : ""}
          </div>
          ${state.locked ? "" : s.signup
            ? `<button class="btn btn-ghost btn-sm" type="button" data-fit-remove="${s.signup}">${VH.svg("check")} Added</button>`
            : `<button class="btn btn-primary btn-sm" type="button" data-fit-add="${s.class_id}">${VH.svg("plus")} Add</button>`}
        </li>`).join("") : `<li class="report-empty">No group fitness classes this day. The gym and pool are still open.</li>`;
    }
    render();

    async function add(classId, confirm = false) {
      try {
        const res = await VH.api("/api/spaces/rec", { method: "POST", body: { class_id: classId, date: day, confirm } });
        if (res.needs_confirm) {
          const ok = await VH.confirm({ title: "This overlaps your schedule", body: `It overlaps ${clashText(res.conflicts)}. Add it anyway?`, confirmLabel: "Add anyway" });
          if (ok) add(classId, true);
          return;
        }
        state = res.state; render(); VH.toast(res.message);
      } catch (err) { VH.toast(err.message, "error"); }
    }

    page.addEventListener("click", async (e) => {
      const db = e.target.closest("[data-rec-days] [data-day]");
      const ab = e.target.closest("[data-fit-add]");
      const rb = e.target.closest("[data-fit-remove]");
      if (db) { day = db.dataset.day; render(); }
      if (ab) add(Number(ab.dataset.fitAdd));
      if (rb) {
        try {
          const res = await VH.api(`/api/spaces/rec/${rb.dataset.fitRemove}`, { method: "DELETE" });
          state = res.state; render(); VH.toast(res.message);
        } catch (err) { VH.toast(err.message, "error"); }
      }
    });
  }
})();
