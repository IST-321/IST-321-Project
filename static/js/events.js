/* Events and VikesConnect: event list with schedule conflicts, clubs and club applications */
(() => {
  "use strict";
  const page = document.querySelector("[data-ev-page]");
  if (!page) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = VH.esc;
  const data = JSON.parse($("#ev-data").textContent);
  let events = data.events;
  let filter = "";
  const open = new Set();

  /* ---------- Events ---------- */
  const CAT = { "Campus event": "cat-campus", "Club meeting": "cat-club", "Athletics": "cat-athletics" };
  function conflictHTML(e) {
    const active = e.conflicts.filter((c) => !c.canceled);
    const canceled = e.conflicts.filter((c) => c.canceled);
    let html = "";
    if (active.length) {
      html += `<p class="ev-conflict">${VH.svg("warning")}<span>Overlaps ${active.map((c) =>
        `<strong>${esc(c.title)}</strong> (${VH.fmtTime(c.start)} to ${VH.fmtTime(c.end)})`).join(" and ")}</span></p>`;
    }
    if (canceled.length) {
      html += `<p class="ev-ok">${VH.svg("check")}<span>${canceled.map((c) => `<strong>${esc(c.title)}</strong>`).join(", ")} is canceled that day, so there's no conflict.</span></p>`;
    }
    if (!e.conflicts.length) html += `<p class="ev-ok">${VH.svg("check")}<span>Fits your schedule</span></p>`;
    return html;
  }
  function renderEvents() {
    const list = events.filter((e) => !filter || (filter === "mine" ? e.added : e.category === filter));
    $("[data-ev-list]").innerHTML = list.length ? list.map((e) => {
      const d = VH.parseDate(e.event_date);
      const hasConflict = e.conflicts.some((c) => !c.canceled);
      return `<li class="ev ${CAT[e.category]}${e.added ? " is-added" : ""}${hasConflict ? " has-conflict" : ""}" data-ev="${e.id}">
        <div class="ev-date"><span>${VH.fmtDate(e.event_date, { short: true }).split(",")[0]}</span><strong>${d.getDate()}</strong><span>${VH.fmtDate(e.event_date, { weekday: false, short: true }).split(" ")[0]}</span></div>
        <div class="ev-main">
          <div class="ev-title"><strong>${esc(e.title)}</strong>
            <span class="ev-cat">${esc(e.category)}</span>${e.common_hour ? `<span class="ev-cat ev-ch">Common hour</span>` : ""}</div>
          <small>${VH.fmtTime(e.start_time)} to ${VH.fmtTime(e.end_time)} · ${esc(e.location)} · ${esc(e.host)}</small>
          ${conflictHTML(e)}
          <div class="ev-more" ${open.has(e.id) ? "" : "hidden"}><p>${esc(e.description)}</p></div>
        </div>
        <div class="ev-actions">
          ${e.added
            ? `<button class="btn btn-ghost btn-sm" type="button" data-ev-remove="${e.id}">${VH.svg("check")}<span>On your schedule</span></button>`
            : `<button class="btn btn-primary btn-sm" type="button" data-ev-add="${e.id}">${VH.svg("plus")}<span>Add to schedule</span></button>`}
          <button class="link-btn small" type="button" data-ev-details="${e.id}" aria-expanded="${open.has(e.id)}">${open.has(e.id) ? "Hide details" : "Details"}</button>
        </div>
      </li>`;
    }).join("") : `<li class="ev-empty">${filter === "mine" ? "You haven't added any campus events yet." : "Nothing here right now."}</li>`;
  }
  renderEvents();

  $$("[data-ev-filter]").forEach((b) => b.addEventListener("click", () => {
    $$("[data-ev-filter]").forEach((x) => x.classList.toggle("is-on", x === b));
    filter = b.dataset.evFilter;
    renderEvents();
  }));

  $("[data-ev-list]").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const d = b.dataset;
    if (d.evDetails) {
      const id = Number(d.evDetails);
      open.has(id) ? open.delete(id) : open.add(id);
      renderEvents();
      return;
    }
    const id = Number(d.evAdd || d.evRemove);
    if (!id) return;
    const ev = events.find((x) => x.id === id);
    if (d.evAdd && ev.conflicts.some((c) => !c.canceled)) {
      const ok = await VH.confirm({
        title: "Add it anyway?",
        body: `${ev.title} overlaps ${ev.conflicts.filter((c) => !c.canceled).map((c) => c.title).join(" and ")}. You can still add it and decide later.`,
        confirmLabel: "Add to schedule",
      });
      if (!ok) return;
    }
    b.disabled = true;
    try {
      events = (await VH.api(`/api/events/${id}/schedule`, { method: d.evAdd ? "POST" : "DELETE" })).events;
      renderEvents();
      VH.toast(d.evAdd ? `${ev.title} added to your schedule` : `${ev.title} removed from your schedule`);
    } catch (err) { VH.toast(err.message, "error"); b.disabled = false; }
  });

  /* ---------- Clubs ---------- */
  $$(".club-toggle").forEach((t) => t.addEventListener("click", () => {
    const li = t.closest(".club");
    const more = $(".club-more", li);
    const show = more.hidden;
    more.hidden = !show;
    t.setAttribute("aria-expanded", String(show));
    li.classList.toggle("is-open", show);
  }));

  const dlg = $("#apply-dialog");
  const form = $("[data-apply-form]", dlg);
  let current = null;
  $$("[data-apply]").forEach((b) => b.addEventListener("click", () => {
    current = data.clubs.find((c) => c.slug === b.dataset.apply);
    if (!current || data.applied[current.slug]) return;
    form.reset();
    $("[data-apply-name]", dlg).textContent = current.name;
    $("[data-apply-question]", dlg).textContent = current.question;
    $("[data-apply-error]", dlg).textContent = "";
    dlg.showModal();
    form.major.focus();
  }));
  $("[data-apply-cancel]", dlg).addEventListener("click", () => dlg.close());
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    const err = $("[data-apply-error]", dlg);
    err.textContent = "";
    const submit = $('button[type="submit"]', form);
    submit.disabled = true;
    try {
      const res = await VH.api(`/api/clubs/${current.slug}/apply`, { method: "POST", body: {
        major: f.get("major"), standing: f.get("standing"), graduation: f.get("graduation"), phone: f.get("phone"),
        why: f.get("why"), club_answer: f.get("club_answer"), heard: f.get("heard"),
        availability: f.getAll("availability"), agree: f.get("agree") === "on",
      } });
      data.applied = res.applied;
      const li = $(`.club[data-club="${current.slug}"]`);
      li.classList.add("is-applied", "just-applied");
      $("[data-club-state]", li).textContent = "Applied";
      const btn = $("[data-apply]", li);
      btn.disabled = true;
      btn.textContent = "Application submitted";
      dlg.close();
      VH.toast(`Application to ${current.name} submitted`);
      VH.alerts.refresh();
    } catch (ex) { err.textContent = ex.message; }
    finally { submit.disabled = false; }
  });

  /* ---------- Links from search: #event-12 or #club-cab ---------- */
  function openFromHash() {
    const h = location.hash.slice(1);
    let target = null;
    if (h.startsWith("event-")) target = $(`[data-ev="${CSS.escape(h.slice(6))}"]`);
    if (h.startsWith("club-")) {
      target = $(`.club[data-club="${CSS.escape(h.slice(5))}"]`);
      const t = target && $(".club-toggle", target);
      if (t && !target.classList.contains("is-open")) t.click();
    }
    if (target) {
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      target.classList.add("is-flash");
      setTimeout(() => target.classList.remove("is-flash"), 2200);
    }
  }
  openFromHash();
  window.addEventListener("hashchange", openFromHash);
})();
