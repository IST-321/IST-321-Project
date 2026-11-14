/* Mobile Campus: equipment list, loan requests and current loans */
(() => {
  "use strict";
  const page = document.querySelector("[data-mc-page]");
  if (!page) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = VH.esc;
  let state = JSON.parse($("#mc-data").textContent);

  const pools = (e) => ({ "Semester": e.available - e.seven_day, "7 day": e.seven_day });
  const ICON = { Laptop: "laptop", Calculator: "grid" };

  function render() {
    const lockEl = $("[data-mc-lock]");
    lockEl.hidden = !state.locked;
    lockEl.innerHTML = state.locked ? `${VH.svg("lock")}<span>${esc(state.locked)}</span>` : "";
    const active = state.requests.filter((r) => r.status === "Requested" || r.status === "Checked out");
    $("[data-eq-list]").innerHTML = state.equipment.map((e) => {
      const p = pools(e);
      const mine = active.find((r) => r.kind === e.kind);
      const status = e.available === 0 ? ["is-out", "All checked out"] : e.available <= 5 ? ["is-low", `${e.available} available`] : ["is-ok", `${e.available} available`];
      return `<li class="eq">
        <span class="row-icon">${VH.svg(ICON[e.kind] || "laptop")}</span>
        <div class="eq-main">
          <div class="eq-title"><strong>${esc(e.name)}</strong><span class="eq-status ${status[0]}">${status[1]}</span></div>
          <p>${esc(e.description)}</p>
          <small class="muted">Semester loans: ${p.Semester} free · 7 day loans: ${p["7 day"]} free · ${e.total} in the program</small>
        </div>
        ${mine ? `<span class="eq-note">You have a ${esc(e.kind.toLowerCase())}</span>`
               : `<button class="btn ${e.available ? "btn-primary" : "btn-ghost"} btn-sm" type="button" data-request="${e.id}" ${e.available ? "" : "disabled"}${state.locked ? ' aria-disabled="true"' : ""}>${e.available ? "Request" : "Unavailable"}</button>`}
      </li>`;
    }).join("");
    $("[data-loan-list]").innerHTML = active.length ? active.map((r) => `
      <li class="loan ${r.status === "Checked out" ? "is-out" : "is-requested"}">
        <span class="row-icon">${VH.svg(ICON[r.kind] || "laptop")}</span>
        <div class="row-text">
          <strong>${esc(r.name)}</strong>
          <small>${r.status === "Checked out"
            ? `Checked out ${VH.fmtDate(r.pickup_date, { short: true })} · due back ${VH.fmtDate(r.due_date, { short: true })}`
            : `${esc(r.loan_type)} loan · pick up ${VH.fmtDate(r.pickup_date)} in Student Center 128A`}</small>
        </div>
        <span class="status ${r.status === "Checked out" ? "status-ok" : "status-wait"}">${esc(r.status)}</span>
        ${r.status === "Requested" ? `<button class="link-btn small" type="button" data-cancel="${r.id}">Cancel</button>` : ""}
      </li>`).join("") : `<li class="report-empty">No loans or requests right now.</li>`;
  }
  render();

  const dlg = $("#eq-dialog");
  const form = $("[data-eq-form]", dlg);
  let item = null;
  page.addEventListener("click", async (e) => {
    const req = e.target.closest("[data-request]");
    const cancel = e.target.closest("[data-cancel]");
    if (req && state.locked) { VH.toast(state.locked, "error", 5200); return; }
    if (req) {
      item = state.equipment.find((x) => x.id === Number(req.dataset.request));
      form.reset();
      const p = pools(item);
      $("[data-eq-name]", dlg).textContent = item.name;
      $("[data-eq-desc]", dlg).textContent = item.description;
      $('[data-eq-pool="Semester"]', dlg).textContent = `(${p.Semester} free)`;
      $('[data-eq-pool="7 day"]', dlg).textContent = `(${p["7 day"]} free)`;
      if (!p.Semester && p["7 day"]) form.loan_type.value = "7 day";
      $("[data-eq-error]", dlg).textContent = "";
      dlg.showModal();
    }
    if (cancel) {
      const ok = await VH.confirm({ title: "Cancel this request?", body: "The device goes back to the pool for other students.", confirmLabel: "Cancel request", danger: true });
      if (!ok) return;
      try {
        state = await VH.api(`/api/mobile-campus/requests/${cancel.dataset.cancel}/cancel`, { method: "POST" });
        render();
        VH.toast("Request canceled");
      } catch (err) { VH.toast(err.message, "error"); }
    }
  });
  $("[data-eq-cancel]", dlg).addEventListener("click", () => dlg.close());
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    try {
      state = await VH.api("/api/mobile-campus/requests", { method: "POST", body: {
        equipment_id: item.id, loan_type: f.get("loan_type"), pickup_date: f.get("pickup_date"),
        note: f.get("note"), agreement: f.get("agreement") === "on",
      } });
      render();
      dlg.close();
      VH.toast(`${item.name} requested. Bring your Viking Card to pick it up.`);
      VH.alerts.refresh();
    } catch (err) { $("[data-eq-error]", dlg).textContent = err.message; }
  });
})();
