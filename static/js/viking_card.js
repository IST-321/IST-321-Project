/* Viking Card page: funds, lock, activity and replacement. Tap to pay lives in main.js. */
(() => {
  "use strict";
  const page = document.querySelector("[data-vc-page]");
  if (!page) return;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const isLocked = () => page.dataset.locked === "1";
  let insights = JSON.parse($("#card-insights").textContent);
  const esc = VH.esc;

  /* ---------- Forecast: how long the balance and swipes last ---------- */
  function renderForecast() {
    const m = insights.money, sw = insights.swipes;
    const lines = [];
    if (m.pace > 0 && m.short) {
      lines.push(`<p class="fc-line is-short">${VH.svg("alert")}<span>
        <strong>Your balance is running low.</strong> At about ${esc(m.pace_label)} a day it lasts until <strong>${esc(m.runs_out)}</strong>.
        Adding about <strong>${esc(m.need_label)}</strong> carries you to the end of the semester.</span></p>`);
    } else if (m.pace > 0) {
      lines.push(`<p class="fc-line">${VH.svg("card")}<span>
        At your pace of about <strong>${esc(m.pace_label)} a day</strong>, ${m.runs_out ? `your balance lasts until <strong>${esc(m.runs_out)}</strong>.` : "your balance lasts well past the semester."}
        ${m.before_end ? `Adding about ${esc(m.need_label)} would carry you to ${esc(m.term_end)}.` : `That covers you through the end of the semester, ${esc(m.term_end)}.`}</span></p>`);
    } else {
      lines.push(`<p class="fc-line">${VH.svg("card")}<span>No purchases in the last two weeks, so your balance is holding steady.</span></p>`);
    }
    if (sw) {
      lines.push(`<p class="fc-line${sw.short ? " is-short" : ""}">${VH.svg(sw.short ? "alert" : "meal")}<span>
        That's about <strong>${sw.allowance} swipes a week</strong> until ${esc(m.term_end)}. You've been using about ${sw.per_week} a week,
        ${sw.short ? "so your swipes would run out before the semester ends." : `so about ${sw.projected_left} would be left over.`}</span></p>`);
    }
    $("[data-forecast]", page).innerHTML = lines.join("");
  }

  /* ---------- Spending by place: last 30 days, drawn as plain SVG bars ---------- */
  let placeFilter = null;
  function renderChart() {
    const box = $("[data-place-chart]", page);
    const data = insights.by_place;
    $("[data-spend-total]", page).textContent = data.length ? `Last 30 days · ${insights.total_30_label}` : "Last 30 days";
    if (!data.length) { box.innerHTML = `<p class="muted small">No purchases in the last 30 days.</p>`; return; }
    const max = Math.max(...data.map((d) => d.spent));
    box.innerHTML = `<ul class="place-bars" role="list">${data.map((d) => `
      <li><button type="button" class="place-bar${placeFilter === d.place ? " is-on" : ""}" data-place-pick="${esc(d.place)}"
          aria-pressed="${placeFilter === d.place}" aria-label="${esc(d.place)}, ${esc(d.label)} over ${d.count} purchase${d.count === 1 ? "" : "s"}">
        <span class="pb-name">${esc(d.place)}</span>
        <svg class="pb-track" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
          <rect class="pb-bg" x="0" y="0" width="100" height="10" rx="2"/>
          <rect class="pb-fill" x="0" y="0" width="${Math.max(2, d.spent / max * 100).toFixed(1)}" height="10" rx="2"/>
        </svg>
        <span class="pb-amount">${esc(d.label)}</span>
      </button></li>`).join("")}</ul>`;
  }
  $("[data-place-chart]", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-place-pick]");
    if (!b) return;
    const place = b.dataset.placePick;
    placeFilter = placeFilter === place ? null : place;
    renderChart();
    if (placeFilter) {
      setExpanded(true, false);
      applyFilter("Purchase");
      $("#activity-title", page).scrollIntoView({ block: "start", behavior: "smooth" });
    } else applyFilter("all");
  });

  function update(next) {
    insights = next;
    renderForecast();
    renderChart();
  }
  renderForecast();
  renderChart();

  /* ---------- Low balance alert setting ---------- */
  $("[data-low-alert]", page).addEventListener("change", async (e) => {
    try {
      const data = await VH.api("/api/viking-card/low-alert", { method: "POST", body: { cents: Number(e.target.value) } });
      update(data.insights);
      VH.toast(data.message);
    } catch (err) { VH.toast(err.message, "error"); }
  });

  /* ---------- Tap to pay purchases (made from the lifted card) and locking from an alert ---------- */
  document.addEventListener("vh:card", (e) => {
    prependTxn(e.detail.transaction);
    update(e.detail.insights);
  });
  document.addEventListener("vh:card-locked", () => setLocked(true));

  /* ---------- Lock and unlock ---------- */
  function setLocked(locked) {
    page.dataset.locked = locked ? "1" : "0";
    $$(".vcard").forEach((c) => c.classList.toggle("is-locked", locked));
    if (locked) VH.dropCard();
  }
  $$("[data-lock]", page).forEach((btn) => {
    btn.addEventListener("click", async () => {
      const locking = btn.dataset.lock === "1";
      const ok = await VH.confirm(locking
        ? { title: "Lock your Viking Card?", body: "While it's locked you can't add funds or use tap to pay. You can unlock it here at any time.", confirmLabel: "Lock card", danger: true }
        : { title: "Unlock your Viking Card?", body: "Your card will be active again.", confirmLabel: "Unlock card" });
      if (!ok) return;
      try {
        await VH.api("/api/viking-card/lock", { method: "POST", body: { locked: locking } });
        setLocked(locking);
        VH.toast(locking ? "Your Viking Card is locked" : "Your Viking Card is unlocked");
        VH.alerts.refresh();
      } catch (err) { VH.toast(err.message, "error"); }
    });
  });

  /* ---------- Add funds ---------- */
  const form = $("[data-add-funds]", page);
  const input = $("#fund-amount", form);
  const errorEl = $("#fund-error", form);
  const fmt = (n) => "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const showError = (msg) => {
    errorEl.textContent = msg || "";
    input.closest(".input-wrap").classList.toggle("has-error", Boolean(msg));
  };
  const validate = () => {
    const raw = input.value.trim().replace(/^\$/, "");
    if (!raw) return [null, "Enter an amount."];
    if (!/^\d+(\.\d{1,2})?$/.test(raw)) return [null, "Enter an amount like 25 or 25.50."];
    const amount = Number(raw);
    if (amount < 5 || amount > 500) return [null, "Add between $5.00 and $500.00 at a time."];
    return [amount, ""];
  };

  $$("[data-amount]", form).forEach((b) => b.addEventListener("click", () => {
    $$("[data-amount]", form).forEach((x) => x.classList.toggle("is-on", x === b));
    input.value = Number(b.dataset.amount).toFixed(2);
    showError("");
  }));
  input.addEventListener("input", () => {
    $$("[data-amount]", form).forEach((x) => x.classList.remove("is-on"));
    if (errorEl.textContent) showError(validate()[1]);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const [amount, err] = validate();
    showError(err);
    if (err) { input.focus(); return; }
    const ok = await VH.confirm({
      title: `Add ${fmt(amount)} to your Viking Card?`,
      body: "The amount will be added to your Viking Card balance.",
      confirmLabel: `Add ${fmt(amount)}`,
    });
    if (!ok) return;
    try {
      const data = await VH.api("/api/viking-card/funds", { method: "POST", body: { amount: amount.toFixed(2) } });
      $$("[data-balance]").forEach((el) => { el.textContent = data.balance_label; });
      prependTxn(data.transaction);
      update(data.insights);
      input.value = "";
      $$("[data-amount]", form).forEach((x) => x.classList.remove("is-on"));
      VH.toast("Viking Card balance updated");
      VH.alerts.refresh();
    } catch (error) { showError(error.message); }
  });

  /* ---------- Activity ---------- */
  const list = $("[data-txn-list]", page);
  const toggle = $("[data-txn-toggle]", page);
  const filterBar = $("[data-txn-filter]", page);
  const countLabel = () => `See all (${$$(".txn", list).length})`;

  const TXN_ICON = { "Deposit": "plus", "Purchase": "receipt", "Meal swipe": "meal" };
  function prependTxn(t) {
    const li = document.createElement("li");
    li.className = "txn is-new";
    li.dataset.type = t.type;
    li.dataset.place = t.place;
    li.innerHTML = `<span class="txn-icon txn-${t.type.toLowerCase().replace(" ", "-")}">${VH.svg(TXN_ICON[t.type])}</span>
      <div class="txn-main"><strong>${VH.esc(t.location)}</strong><small>${VH.esc(t.type)} · ${VH.esc(t.when)}</small></div>
      <span class="txn-amount${t.amount > 0 ? " is-credit" : ""}">${VH.esc(t.amount_label)}</span>`;
    list.prepend(li);
    if (!list.classList.contains("is-expanded")) toggle.textContent = countLabel();
  }

  const closeTop = $("[data-txn-close]", page);
  function setExpanded(open, scroll = true) {
    list.classList.toggle("is-expanded", open);
    filterBar.hidden = !open;
    closeTop.hidden = !open;
    toggle.textContent = open ? "Show fewer" : countLabel();
    if (!open) {
      placeFilter = null;
      renderChart();
      applyFilter("all");
      // Bring the activity heading back into view after collapsing a long list
      if (scroll) $("#activity-title", page).scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }
  toggle.addEventListener("click", () => setExpanded(!list.classList.contains("is-expanded")));
  closeTop.addEventListener("click", () => setExpanded(false));

  const placeChip = $("[data-place-clear]", page);
  // "Other" groups the smaller places together
  function inPlace(place) {
    if (placeFilter !== "Other") return place === placeFilter;
    const other = insights.by_place.find((d) => d.place === "Other");
    return other ? other.includes.includes(place) : false;
  }
  function applyFilter(type) {
    if (type !== "Purchase") placeFilter = null;
    $$("[data-filter]", filterBar).forEach((b) => b.classList.toggle("is-on", b.dataset.filter === type));
    $$(".txn", list).forEach((li) => li.classList.toggle("is-filtered",
      (type !== "all" && li.dataset.type !== type) || (placeFilter && !inPlace(li.dataset.place))));
    placeChip.hidden = !placeFilter;
    if (placeFilter) placeChip.innerHTML = `${esc(placeFilter)} ${VH.svg("x")}`;
    placeChip.setAttribute("aria-label", placeFilter ? `Show all places, not just ${placeFilter}` : "");
  }
  $$("[data-filter]", filterBar).forEach((b) => b.addEventListener("click", () => { applyFilter(b.dataset.filter); renderChart(); }));
  placeChip.addEventListener("click", () => { placeFilter = null; renderChart(); applyFilter("all"); });

  /* ---------- Replacement request ---------- */
  const dlg = $("#replace-dialog");
  const steps = { form: $('[data-replace-step="form"]', dlg), done: $('[data-replace-step="done"]', dlg) };
  const details = $("#replace-details", dlg);
  const replaceError = $("#replace-error", dlg);
  const setReplaceError = (msg) => { replaceError.textContent = msg || ""; details.classList.toggle("has-error", Boolean(msg)); };

  $("[data-replace-open]", page).addEventListener("click", () => {
    steps.form.hidden = false;
    steps.done.hidden = true;
    details.value = "";
    setReplaceError("");
    dlg.showModal();
  });
  details.addEventListener("input", () => { if (replaceError.textContent) setReplaceError(""); });

  $("[data-replace-submit]", dlg).addEventListener("click", async () => {
    const reason = $('input[name="reason"]:checked', dlg)?.value;
    const text = details.value.trim();
    if (text.length < 5) { setReplaceError("Add a short explanation of what happened."); details.focus(); return; }
    try {
      const data = await VH.api("/api/viking-card/replacement", { method: "POST", body: { reason, details: text } });
      steps.form.hidden = true;
      steps.done.hidden = false;
      const box = $("[data-request-list]", page);
      box.hidden = false;
      const p = document.createElement("p");
      p.className = "request-item";
      p.innerHTML = `<span><strong>${VH.esc(data.reason)}</strong> · saved ${VH.esc(data.when)}<br><small>${VH.esc(data.details)}</small></span>`;
      box.querySelector(".eyebrow").after(p);
    } catch (err) { setReplaceError(err.message); }
  });
})();
