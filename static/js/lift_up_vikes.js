/* Lift Up Vikes: choose a day and a 15-minute pantry turn, see and cancel planned visits */
(() => {
  "use strict";
  const page = document.querySelector("[data-lv-page]");
  if (!page) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = VH.esc;
  let state = JSON.parse($("#lv-data").textContent);
  let day = state.days[0] && state.days[0].date;
  let time = null;

  function render() {
    const lockEl = $("[data-lv-lock]");
    lockEl.hidden = !state.locked;
    lockEl.innerHTML = state.locked ? `${VH.svg("lock")}<span>${VH.esc(state.locked)}</span>` : "";
    if (!state.days.find((d) => d.date === day)) day = state.days[0] && state.days[0].date;
    $("[data-lv-days]").innerHTML = state.days.map((d) => {
      const open = d.slots.filter((s) => s.left > 0).length;
      return `<button type="button" role="tab" class="lv-day${d.date === day ? " is-on" : ""}" aria-selected="${d.date === day}" data-day="${d.date}">
        <span>${VH.fmtDate(d.date, { short: true }).split(",")[0]}</span><strong>${VH.parseDate(d.date).getDate()}</strong>
        <small>${open ? `${open} open` : "Full"}</small></button>`;
    }).join("");
    const current = state.days.find((d) => d.date === day);
    $("[data-lv-slots]").innerHTML = current ? current.slots.map((s) => `
      <button type="button" class="lv-slot${s.time === time ? " is-on" : ""}${s.mine ? " is-mine" : ""}" data-time="${s.time}" ${s.left && !s.mine ? "" : "disabled"}>
        <strong>${VH.fmtTime(s.time)}</strong><small>${s.mine ? "Your turn" : s.left ? `${s.left} of 8 spots` : "Full"}</small>
      </button>`).join("") : state.locked ? "" : `<p class="muted">No pantry hours in the next two weeks.</p>`;
    const confirm = $("[data-lv-confirm]");
    confirm.hidden = !time;
    if (time) $("[data-lv-choice]").innerHTML = `<strong>${VH.fmtDate(day)}</strong> at <strong>${VH.fmtTime(time)}</strong> in Berkman Hall 122`;
    $("[data-lv-mine]").innerHTML = state.appointments.length ? state.appointments.map((a) => `
      <li class="loan is-requested">
        <span class="row-icon">${VH.svg("basket")}</span>
        <div class="row-text"><strong>${VH.fmtDate(a.appt_date)} at ${VH.fmtTime(a.appt_time)}</strong><small>Berkman Hall 122 · bring reusable bags</small></div>
        <button class="link-btn small" type="button" data-lv-cancel="${a.id}">Cancel</button>
      </li>`).join("") : `<li class="report-empty">No visits planned.</li>`;
  }
  render();

  page.addEventListener("click", async (e) => {
    const d = e.target.closest("[data-day]");
    const s = e.target.closest("[data-time]");
    const c = e.target.closest("[data-lv-cancel]");
    if (d) { day = d.dataset.day; time = null; render(); }
    if (s && !s.disabled) { time = s.dataset.time; render(); }
    if (e.target.closest("[data-lv-book]")) {
      try {
        state = await VH.api("/api/lift-up-vikes/appointments", { method: "POST", body: { date: day, time } });
        VH.toast(`See you ${VH.fmtDate(day)} at ${VH.fmtTime(time)}`);
        time = null;
        render();
      } catch (err) { VH.toast(err.message, "error"); }
    }
    if (c) {
      const ok = await VH.confirm({ title: "Cancel this visit?", body: "The turn opens up for someone else.", confirmLabel: "Cancel visit", danger: true });
      if (!ok) return;
      try { state = await VH.api(`/api/lift-up-vikes/appointments/${c.dataset.lvCancel}/cancel`, { method: "POST" }); render(); VH.toast("Visit canceled"); }
      catch (err) { VH.toast(err.message, "error"); }
    }
  });
})();
