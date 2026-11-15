/* Student jobs: hours meter, filters, save, and adding shifts to the schedule */
(function () {
  "use strict";
  const page = document.querySelector("[data-jobs-page]");
  if (!page) return;
  const $ = (s, r = page) => r.querySelector(s);
  const esc = (s) => VH.esc(s);
  const data = JSON.parse(document.getElementById("jobs-data").textContent);
  let state = data.state;
  let filter = "";
  const money = (n) => `$${n.toFixed(2)}`;
  const hrs = (n) => `${Number.isInteger(n) ? n : n.toFixed(1)} ${n === 1 ? "hour" : "hours"}`;

  function renderHours() {
    const total = state.hours_total, limit = state.limit;
    const left = Math.max(0, limit - total);
    const added = state.listings.filter((j) => j.added);
    const pct = Math.min(100, (total / limit) * 100);
    $("[data-jobs-hours]").innerHTML = `
      <div class="jh-top">
        <p><strong>${hrs(total)}</strong> a week of ${limit}</p>
        <small>${left ? `${hrs(left)} left under CSU's semester limit` : "You're at CSU's semester limit"}</small>
      </div>
      <div class="jh-bar${total >= limit ? " is-full" : ""}" role="img" aria-label="${total} of ${limit} hours a week"><span style="width:${pct}%"></span></div>
      <ul class="jh-jobs">
        <li>${VH.svg("briefcase")}<span><strong>${esc(state.current.title)}</strong><small>${esc(state.current.where)} · ${esc(state.current.shift_text.join(", "))} · ${hrs(state.current.hours)}</small></span><em>Current job</em></li>
        ${added.map((j) => `<li>${VH.svg("briefcase")}<span><strong>${esc(j.title)}</strong><small>${esc(j.dept)} · ${esc(j.shifts.join(", "))} · ${hrs(j.hours)}</small></span><em>On your schedule</em></li>`).join("")}
      </ul>
      <p class="muted small">Hours from every campus job count together. Finals week counts as part of the semester.</p>`;
  }

  function fitLine(j) {
    if (j.clashes.length) {
      const c = j.clashes[0];
      const more = j.clashes.length > 1 ? ` and ${j.clashes.length - 1} more` : "";
      return `<p class="job-fit is-clash">${VH.svg("warning")}<span>Overlaps <strong>${esc(c.course)}</strong> on ${esc(c.day)}, ${VH.fmtTime(c.start)} to ${VH.fmtTime(c.end)}${more}. CSU doesn't allow working during class time.</span></p>`;
    }
    return `<p class="job-fit">${VH.svg("check")}<span>Fits around your classes</span></p>`;
  }

  function renderList() {
    const list = state.listings.filter((j) =>
      !filter || (filter === "fits" && !j.clashes.length) || (filter === "fws" && j.fws) || (filter === "saved" && j.saved));
    const empty = { fits: "No openings fit around your classes right now.", fws: "No work-study openings right now.",
                    saved: "Save an opening to keep it here." }[filter] || "No openings right now.";
    $("[data-job-list]").innerHTML = list.length ? list.map((j) => `
      <li class="job-item" id="job-${j.id}">
        <div class="job-main">
          <div class="job-title">
            <strong>${esc(j.title)}</strong>
            ${j.fws ? `<span class="tag tag-required">Work-study</span>` : ""}
          </div>
          <p class="job-meta">${esc(j.dept)} · <a href="/campus-map?b=${esc(j.code)}">${esc(j.where)}</a></p>
          <p class="job-pay"><strong>${money(j.pay)}</strong> an hour · ${hrs(j.hours)} a week</p>
          <ul class="job-shifts">${j.shifts.map((s) => `<li>${VH.svg("clock")}${esc(s)}</li>`).join("")}</ul>
          ${fitLine(j)}
          <details class="job-more"><summary>About this job</summary><p>${esc(j.description)}</p>
            <p class="muted small">Posted ${VH.fmtDate(j.posted, { short: true })}</p></details>
        </div>
        <div class="job-actions">
          <a class="btn btn-primary btn-sm" href="${esc(data.handshake)}" target="_blank" rel="noopener">Apply on Handshake ${VH.svg("external")}<span class="visually-hidden">(opens in a new tab)</span></a>
          <button class="btn btn-ghost btn-sm" type="button" data-job-save="${j.id}" aria-pressed="${j.saved}">${VH.svg("bookmark")} ${j.saved ? "Saved" : "Save"}</button>
          ${j.added
            ? `<button class="btn btn-ghost btn-sm" type="button" data-job-unschedule="${j.id}">${VH.svg("x")} Remove shifts</button>`
            : j.clashes.length ? "" : `<button class="btn btn-ghost btn-sm" type="button" data-job-schedule="${j.id}">${VH.svg("calendar")} Add shifts to schedule</button>`}
        </div>
      </li>`).join("") : `<li class="job-empty">${esc(empty)}</li>`;
  }

  function render() { renderHours(); renderList(); }
  render();

  async function addShifts(id, confirm = false) {
    const job = state.listings.find((j) => j.id === id);
    try {
      const res = await VH.api(`/api/jobs/${id}/schedule`, { method: "POST", body: { confirm } });
      if (res.needs_confirm) {
        const first = res.conflicts[0];
        const ok = await VH.confirm({
          title: "Some shifts overlap your plans",
          body: `${res.count} ${res.count === 1 ? "shift overlaps" : "shifts overlap"} things already on your schedule, starting with ${first.title} on ${VH.fmtDate(first.date, { short: true })}. Add the shifts anyway?`,
          confirmLabel: "Add anyway" });
        if (ok) addShifts(id, true);
        return;
      }
      state = res.state; render(); VH.toast(res.message); VH.alerts.refresh();
    } catch (err) { VH.toast(err.message, "error"); }
    return job;
  }

  page.addEventListener("click", async (e) => {
    const chip = e.target.closest("[data-jobs-filter]");
    if (chip) {
      filter = chip.dataset.jobsFilter;
      page.querySelectorAll("[data-jobs-filter]").forEach((c) => c.classList.toggle("is-on", c === chip));
      renderList();
      return;
    }
    const save = e.target.closest("[data-job-save]");
    if (save) {
      const on = save.getAttribute("aria-pressed") === "true";
      try {
        const res = await VH.api(`/api/jobs/${save.dataset.jobSave}/save`, { method: on ? "DELETE" : "POST" });
        state = res.state; render(); VH.toast(res.message);
      } catch (err) { VH.toast(err.message, "error"); }
      return;
    }
    const add = e.target.closest("[data-job-schedule]");
    if (add) { addShifts(Number(add.dataset.jobSchedule)); return; }
    const rm = e.target.closest("[data-job-unschedule]");
    if (rm) {
      const job = state.listings.find((j) => j.id === Number(rm.dataset.jobUnschedule));
      const ok = await VH.confirm({ title: "Remove these shifts?", body: `Every ${job.title} shift comes off your schedule.`, confirmLabel: "Remove shifts" });
      if (!ok) return;
      try {
        const res = await VH.api(`/api/jobs/${job.id}/schedule`, { method: "DELETE" });
        state = res.state; render(); VH.toast(res.message);
      } catch (err) { VH.toast(err.message, "error"); }
    }
  });
})();
