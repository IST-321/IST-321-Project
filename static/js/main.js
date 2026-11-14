/* CSU Viking Hub: shared interactions (app bar, alerts, dialogs, sign in) */
(() => {
  "use strict";

  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  /* Small inline icons used by scripts (same style as the template icon set) */
  const ICON = {
    check: '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm4.6 6.2-6 6-2.9-2.9-1.6 1.6 4.5 4.5 7.6-7.6z"/>',
    alert: '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm-1.2 4.5v7.5h2.4V6.5zm0 9v2.5h2.4v-2.5z"/>',
    x: '<path d="M5.9 4.2 12 10.3l6.1-6.1 1.7 1.7-6.1 6.1 6.1 6.1-1.7 1.7-6.1-6.1-6.1 6.1-1.7-1.7 6.1-6.1-6.1-6.1z"/>',
    card: '<path fill-rule="evenodd" d="M4.5 4h15A2.5 2.5 0 0 1 22 6.5V8H2V6.5A2.5 2.5 0 0 1 4.5 4zM2 10.5h20v7a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 17.5zm3.5 4v2H11v-2z"/>',
    calendar: '<path fill-rule="evenodd" d="M7 2h2v2.5h6V2h2v2.5h1.5A2.5 2.5 0 0 1 21 7v11.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5V7a2.5 2.5 0 0 1 2.5-2.5H7zM5 10v8.5c0 .3.2.5.5.5h13c.3 0 .5-.2.5-.5V10zm2 2h3.5v3.5H7z"/>',
    clock: '<path fill-rule="evenodd" d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm-1.2 4.5v6.2l4.9 2.9 1.2-2-3.7-2.2V6.5z"/>',
    megaphone: '<path d="M3 9h4.5L17 4v16l-9.5-5H7l1 5H5.5L4.2 15H3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1zM19 9h1.5a1.5 1.5 0 0 1 1.5 1.5v3a1.5 1.5 0 0 1-1.5 1.5H19z"/>',
    flag: '<path d="M4.5 2h2v20h-2zM8 3h12l-3 4.75L20 12.5H8z"/>',
    bus: '<path fill-rule="evenodd" d="M7 2h10a3.5 3.5 0 0 1 3.5 3.5V17a2 2 0 0 1-1.5 1.9V21.5h-3V19H8v2.5H5v-2.6A2 2 0 0 1 3.5 17V5.5A3.5 3.5 0 0 1 7 2zM6 6v5.5h12V6zm1.5 8a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm9 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>',
    external: '<path d="M14 3h7v7h-2.2V6.8l-7.1 7.1-1.6-1.6 7.1-7.1H14zM3.5 6.5A1.5 1.5 0 0 1 5 5h6v2.2H5.7v11.1h11.1V13H19v6a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19z"/>',
    pin: '<path fill-rule="evenodd" d="M12 1.5a7.5 7.5 0 0 1 7.5 7.5c0 5.3-7.5 13.5-7.5 13.5S4.5 14.3 4.5 9A7.5 7.5 0 0 1 12 1.5zm0 4.8a2.7 2.7 0 1 0 0 5.4 2.7 2.7 0 0 0 0-5.4z"/>',
    lock: '<path fill-rule="evenodd" d="M6.5 10V7.5a5.5 5.5 0 0 1 11 0V10h.5a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V12a2 2 0 0 1 2-2zm2.4 0h6.2V7.5a3.1 3.1 0 0 0-6.2 0zm2 4v4h2.2v-4z"/>',
    unlock: '<path fill-rule="evenodd" d="M6.5 10V7.5a5.5 5.5 0 0 1 10.7-1.8l-2.3.8a3.1 3.1 0 0 0-6 1V10H18a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V12a2 2 0 0 1 2-2zm4.4 4v4h2.2v-4z"/>',
  };
  // The full icon set from templates/partials/icons.html, so scripts and templates match
  try { Object.assign(ICON, JSON.parse(document.getElementById("icon-data").textContent)); } catch (_) { /* keep the built-in set */ }
  const svg = (name, cls = "") =>
    `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${ICON[name] || ICON.alert}</svg>`;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- Public helpers ---------- */
  const VH = {
    svg, esc,

    toast(message, type = "success", ms = 3200) {
      const region = $(".toast-region");
      if (!region) return;
      const el = document.createElement("div");
      el.className = `toast toast-${type}`;
      el.setAttribute("role", type === "error" ? "alert" : "status");
      el.innerHTML = svg(type === "error" ? "alert" : "check") + "<span></span>";
      el.querySelector("span").textContent = message;
      region.appendChild(el);
      setTimeout(() => {
        el.classList.add("is-leaving");
        el.addEventListener("animationend", () => el.remove(), { once: true });
      }, ms);
    },

    async api(url, { method = "GET", body } = {}) {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: body ? JSON.stringify(body) : undefined,
        credentials: "same-origin",
      });
      if (res.status === 401) { location.href = "/login"; throw new Error("Please sign in again."); }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Something went wrong. Try again.");
      return data;
    },

    /** Promise-based confirm using the shared dialog. Resolves true or false. */
    confirm({ title, body, confirmLabel = "Confirm", danger = false }) {
      const dlg = $("#confirm-dialog");
      if (!dlg) return Promise.resolve(window.confirm(title));
      $("[data-confirm-title]", dlg).textContent = title;
      $("[data-confirm-body]", dlg).textContent = body || "";
      const ok = $("[data-confirm-ok]", dlg);
      ok.textContent = confirmLabel;
      ok.className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
      dlg.returnValue = "";
      dlg.showModal();
      ok.focus();
      return new Promise((resolve) => {
        dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
      });
    },
  };
  window.VH = VH;

  /* ---------- Back button: use history when we came from inside the site ---------- */
  $$("[data-back]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      try {
        if (document.referrer && new URL(document.referrer).origin === location.origin) {
          e.preventDefault();
          history.back();
        }
      } catch (_) { /* fall through to the link */ }
    });
  });

  /* ---------- Popovers (account menu and alerts) ---------- */
  function popover(root, toggle, panel, onOpen, onClose) {
    const close = () => {
      if (panel.hidden) return;
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      onClose && onClose();
    };
    const open = () => { panel.hidden = false; toggle.setAttribute("aria-expanded", "true"); onOpen && onOpen(); };
    toggle.addEventListener("click", (e) => { e.stopPropagation(); panel.hidden ? open() : close(); });
    document.addEventListener("click", (e) => { if (!root.contains(e.target)) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { close(); toggle.focus(); } });
    return { open, close };
  }
  $$("[data-menu]").forEach((m) => popover(m, $("[data-menu-toggle]", m), $(".menu-panel", m)));

  /* ---------- Sidebar: collapses on desktop, slides in as a drawer on phones ---------- */
  const sidebar = $("#sidebar");
  const sideBackdrop = $(".sidebar-backdrop");
  const desktop = window.matchMedia("(min-width: 960px)");
  const setDrawer = (open) => {
    sidebar.classList.toggle("is-open", open);
    sideBackdrop.hidden = !open;
    document.body.style.overflow = open ? "hidden" : "";
    $$("[data-nav-toggle]").forEach((b) => b.setAttribute("aria-expanded", String(open)));
  };
  if (sidebar) {
    $$("[data-nav-toggle]").forEach((btn) => btn.addEventListener("click", () => {
      if (desktop.matches) {
        const collapsed = document.documentElement.classList.toggle("nav-collapsed");
        try { localStorage.setItem("vh-nav", collapsed ? "collapsed" : "open"); } catch (_) {}
        btn.setAttribute("aria-expanded", String(!collapsed));
      } else {
        setDrawer(!sidebar.classList.contains("is-open"));
      }
    }));
    sideBackdrop.addEventListener("click", () => setDrawer(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sidebar.classList.contains("is-open")) setDrawer(false); });
    desktop.addEventListener("change", () => setDrawer(false));
  }

  /* ---------- Home tiles: clicking a tile opens its page ---------- */
  document.addEventListener("click", (e) => {
    const tile = e.target.closest("[data-panel-link]");
    if (!tile || e.target.closest("a, button, input, [data-vcard], .alert-item")) return;
    location.href = tile.dataset.panelLink;
  });

  /* =========================================================
     Tap to pay: a copy of the card floats to the middle of the screen.
     Clicking outside it (or pressing Escape) puts it back.
     ========================================================= */
  const tapLayer = $("[data-tap-layer]");
  let lifted = null;

  function liftCard(cardEl) {
    if (cardEl.classList.contains("is-locked")) {
      VH.toast("Your card is locked. Unlock it to use tap to pay.", "error");
      return;
    }
    const rect = cardEl.getBoundingClientRect();
    const wrap = document.createElement("div");
    wrap.className = "tap-card";
    Object.assign(wrap.style, { left: rect.left + "px", top: rect.top + "px", width: rect.width + "px" });
    const copy = cardEl.cloneNode(true);
    copy.removeAttribute("data-vcard");
    copy.removeAttribute("tabindex");
    copy.setAttribute("role", "img");
    copy.setAttribute("aria-label", "Viking Card ready for tap to pay");
    wrap.appendChild(copy);
    tapLayer.appendChild(wrap);
    tapLayer.hidden = false;
    lockScroll(true);
    cardEl.style.visibility = "hidden";

    const vw = window.innerWidth, vh = window.innerHeight;
    const scale = Math.min(480, vw * 0.9) / rect.width;
    const sheetH = 150;  // room under the card for the purchase form
    const cardH = rect.height * scale;
    const cx = vw / 2, cy = Math.max(cardH / 2 + 16, (vh - sheetH) / 2 - 10);
    const dx = cx - (rect.left + rect.width / 2);
    const dy = cy - (rect.top + rect.height / 2);
    const caption = $(".tap-caption", tapLayer);
    caption.style.top = cy + cardH / 2 + 18 + "px";
    resetSheet();
    requestAnimationFrame(() => { wrap.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`; });
    wrap.addEventListener("click", dropCard);
    lifted = { cardEl, wrap };
  }

  // Keep the page behind the lifted card from scrolling (wheel, touch and keyboard)
  const blockScroll = (e) => { if (lifted) e.preventDefault(); };
  const blockKeys = (e) => { if (lifted && ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(e.key)) e.preventDefault(); };
  function lockScroll(on) {
    const gap = window.innerWidth - document.documentElement.clientWidth;
    document.documentElement.classList.toggle("scroll-locked", on);
    document.body.style.paddingRight = on && gap > 0 ? gap + "px" : "";
  }
  if (tapLayer) {
    tapLayer.addEventListener("wheel", blockScroll, { passive: false });
    tapLayer.addEventListener("touchmove", blockScroll, { passive: false });
    document.addEventListener("keydown", blockKeys);
  }

  function dropCard() {
    if (!lifted) return;
    const { cardEl, wrap } = lifted;
    lifted = null;
    wrap.style.transform = "";
    $(".tap-backdrop", tapLayer).style.opacity = "0";
    $(".tap-caption", tapLayer).style.opacity = "0";
    setTimeout(() => {
      wrap.remove();
      tapLayer.hidden = true;
      lockScroll(false);
      $(".tap-backdrop", tapLayer).style.opacity = "";
      $(".tap-caption", tapLayer).style.opacity = "";
      cardEl.style.visibility = "";
      cardEl.focus({ preventScroll: true });
    }, 330);
  }
  VH.dropCard = dropCard;

  /* Tap to pay purchases: pick a register and an amount. Only the Viking Hub balance changes. */
  const sheet = tapLayer && $("[data-tap-sheet]", tapLayer);
  function resetSheet() {
    if (!sheet) return;
    $("[data-tap-amount]", sheet).value = "";
    $("[data-tap-error]", sheet).textContent = window.VH_PREVIEW
      ? `Tap to pay works on the real day, November 12. You're previewing ${window.VH_PREVIEW}.` : "";
    $("[data-tap-pay]", sheet).disabled = Boolean(window.VH_PREVIEW);
    syncSheet();
  }
  function syncSheet() {
    const swipe = $("[data-tap-register]", sheet).selectedOptions[0].hasAttribute("data-swipe");
    $("[data-tap-amount-wrap]", sheet).hidden = swipe;
    $("[data-tap-pay]", sheet).textContent = swipe ? "Use 1 swipe" : "Pay";
  }
  if (sheet) {
    $("[data-tap-register]", sheet).addEventListener("change", () => { syncSheet(); $("[data-tap-error]", sheet).textContent = ""; });
    sheet.addEventListener("submit", async (e) => {
      e.preventDefault();
      const option = $("[data-tap-register]", sheet).selectedOptions[0];
      const swipe = option.hasAttribute("data-swipe");
      const errorEl = $("[data-tap-error]", sheet);
      const raw = $("[data-tap-amount]", sheet).value.trim().replace(/^\$/, "");
      if (!swipe && !/^\d+(\.\d{1,2})?$/.test(raw)) { errorEl.textContent = "Enter an amount like 6.45."; return; }
      if (!swipe && (Number(raw) <= 0 || Number(raw) > 100)) { errorEl.textContent = "Enter an amount up to $100.00."; return; }
      const place = option.textContent.replace(" (meal swipe)", "");
      const amount = swipe ? "" : "$" + Number(raw).toFixed(2);
      const ok = await VH.confirm(swipe
        ? { title: "Use 1 meal swipe?", body: `A meal swipe will be used at ${place}.`, confirmLabel: "Use 1 swipe" }
        : { title: `Pay ${amount} at ${place}?`, body: "This comes out of your Viking Card balance.", confirmLabel: `Pay ${amount}` });
      if (!ok) return;
      try {
        const data = await VH.api("/api/viking-card/tap", { method: "POST", body: { register: option.value, amount: raw } });
        dropCard();
        $$("[data-balance]").forEach((el) => { el.textContent = data.balance_label; });
        if (data.swipes !== null) $$("[data-swipes]").forEach((el) => { el.textContent = data.swipes; });
        document.dispatchEvent(new CustomEvent("vh:card", { detail: data }));
        VH.toast(data.message);
        VH.alerts.refresh();
      } catch (err) { errorEl.textContent = err.message; }
    });
    // Clicks inside the form shouldn't put the card back
    sheet.addEventListener("click", (e) => e.stopPropagation());
  }

  /* Move the day the app treats as today (Home, schedule, alerts and the rest follow it) */
  VH.setAppDate = async (iso) => {
    try {
      const res = await VH.api("/api/app-date", { method: "POST", body: { date: iso || null } });
      sessionStorage.setItem("vh-toast", res.message);
      location.reload();
    } catch (err) { VH.toast(err.message, "error"); }
  };
  $$("[data-app-date]").forEach((box) => {
    const input = $("[data-app-date-input]", box);
    $("[data-app-date-open]", box).addEventListener("click", () => {
      try { input.showPicker(); } catch { input.focus(); }
    });
    input.addEventListener("change", () => { if (input.value) VH.setAppDate(input.value); });
  });
  $$("[data-app-date-reset]").forEach((b) => b.addEventListener("click", () => VH.setAppDate(null)));
  const pendingToast = sessionStorage.getItem("vh-toast");
  if (pendingToast) { sessionStorage.removeItem("vh-toast"); setTimeout(() => VH.toast(pendingToast), 150); }

  /* =========================================================
     Search everything: press / or Ctrl+K anywhere. The index loads once,
     then matching happens as you type.
     ========================================================= */
  const searchDlg = $("#search-dialog");
  if (searchDlg) {
    const input = $("[data-search-input]", searchDlg);
    const box = $("[data-search-results]", searchDlg);
    const GROUPS = ["Pages", "Buildings", "Offices and resources", "Your classes and assignments", "Clubs", "Campus events", "Alerts"];
    const GROUP_ICON = { "Pages": "grid", "Buildings": "building", "Offices and resources": "info", "Your classes and assignments": "calendar",
                         "Clubs": "ticket", "Campus events": "ticket", "Alerts": "alert" };
    let index = null, hits = [], active = 0;
    const norm = (t) => (t || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();

    async function loadIndex() {
      if (index) return;
      const raw = await VH.api("/api/search-index");
      index = raw.map((it) => ({ ...it, _t: norm(it.title), _h: norm(`${it.title} ${it.sub} ${it.keys}`), _k: norm(it.keys).split(" ") }));
    }
    function score(it, q, words) {
      if (!words.every((w) => it._h.includes(w))) return 0;
      let n = 1;
      if (words.length === 1 && it._k.includes(q)) n += 120;          // a building code or short form, like BH or rec
      if (it._t === q) n += 100;
      if (it._t.startsWith(q)) n += 60;
      if (words.every((w) => it._t.split(" ").some((t) => t.startsWith(w)))) n += 40;
      if (it._t.includes(q)) n += 20;
      return n;
    }
    function render() {
      const q = norm(input.value);
      const words = q.split(" ").filter(Boolean);
      if (!index) { box.innerHTML = `<p class="search-empty">Loading…</p>`; return; }
      if (!words.length) {
        hits = index.filter((it) => it.group === "Pages").slice(0, 8);
      } else {
        const scored = index.map((it) => [score(it, q, words), it]).filter(([n]) => n > 0).sort((a, b) => b[0] - a[0]);
        hits = [];
        GROUPS.forEach((g) => hits.push(...scored.filter(([, it]) => it.group === g).slice(0, 5).map(([, it]) => it)));
        // Put the group holding the best match first
        if (scored.length) {
          const top = scored[0][1].group;
          hits = [...hits.filter((h) => h.group === top), ...hits.filter((h) => h.group !== top)];
        }
      }
      active = 0;
      if (!hits.length) { box.innerHTML = `<p class="search-empty">Nothing matches "${esc(input.value.trim())}". Try a building, office, club or class.</p>`; return; }
      let html = "", last = "";
      hits.forEach((it, i) => {
        if (it.group !== last) { html += `<p class="search-group">${esc(words.length ? it.group : "Go to")}</p>`; last = it.group; }
        html += `<a class="search-hit${i === 0 ? " is-active" : ""}" role="option" id="sr-${i}" aria-selected="${i === 0}" href="${esc(it.url)}" data-i="${i}">
          <span class="row-icon">${svg(GROUP_ICON[it.group] || "info")}</span>
          <span class="row-text"><strong>${esc(it.title)}</strong>${it.sub ? `<small>${esc(it.sub)}</small>` : ""}</span></a>`;
      });
      box.innerHTML = html;
      input.setAttribute("aria-activedescendant", "sr-0");
    }
    function move(d) {
      const items = $$(".search-hit", box);
      if (!items.length) return;
      items[active].classList.remove("is-active");
      items[active].setAttribute("aria-selected", "false");
      active = (active + d + items.length) % items.length;
      items[active].classList.add("is-active");
      items[active].setAttribute("aria-selected", "true");
      items[active].scrollIntoView({ block: "nearest" });
      input.setAttribute("aria-activedescendant", items[active].id);
    }
    async function openSearch() {
      if (searchDlg.open) return;
      input.value = "";
      searchDlg.showModal();
      input.focus();
      render();
      try { await loadIndex(); render(); } catch (err) { box.innerHTML = `<p class="search-empty">${esc(err.message)}</p>`; }
    }
    $$("[data-search-open]").forEach((b) => b.addEventListener("click", openSearch));
    $("[data-search-close]", searchDlg).addEventListener("click", () => searchDlg.close());
    searchDlg.addEventListener("click", (e) => { if (e.target === searchDlg) searchDlg.close(); });
    input.addEventListener("input", render);
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") {
        const it = hits[active];
        if (it) { e.preventDefault(); searchDlg.close(); location.href = it.url; }
      }
    });
    box.addEventListener("click", () => searchDlg.close());
    document.addEventListener("keydown", (e) => {
      const typing = e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey)) {
        if (document.querySelector("dialog[open]:not(#search-dialog)")) return;
        e.preventDefault();
        openSearch();
      }
    });
  }

  /* Lock the card from anywhere (used by the low balance alert) */
  VH.lockCard = async () => {
    const ok = await VH.confirm({ title: "Lock your Viking Card?", body: "While it's locked you can't add funds or use tap to pay. You can unlock it on the Viking Card page at any time.", confirmLabel: "Lock card", danger: true });
    if (!ok) return false;
    try {
      await VH.api("/api/viking-card/lock", { method: "POST", body: { locked: true } });
      $$(".vcard").forEach((c) => c.classList.add("is-locked"));
      document.dispatchEvent(new CustomEvent("vh:card-locked"));
      VH.toast("Your Viking Card is locked");
      VH.alerts.refresh();
      return true;
    } catch (err) { VH.toast(err.message, "error"); return false; }
  };

  /* Shared date and time formatting for page scripts: "1:30 PM", "Tuesday, November 17" */
  const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  VH.fmtTime = (t) => {
    if (!t) return "";
    const [h, m] = t.split(":").map(Number);
    return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
  };
  VH.parseDate = (iso) => { const [y, m, d] = iso.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
  VH.fmtDate = (iso, { weekday = true, short = false } = {}) => {
    const d = VH.parseDate(iso);
    const month = short ? MONTH_NAMES[d.getMonth()].slice(0, 3) : MONTH_NAMES[d.getMonth()];
    const day = short ? DAY_NAMES[d.getDay()].slice(0, 3) : DAY_NAMES[d.getDay()];
    return `${weekday ? day + ", " : ""}${month} ${d.getDate()}`;
  };
  VH.fmtStamp = (iso) => `${VH.fmtDate(iso, { short: true })} at ${VH.fmtTime(iso.slice(11, 16))}`;

  if (tapLayer) {
    $("[data-tap-close]", tapLayer).addEventListener("click", dropCard);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") dropCard(); });
    $$("[data-vcard]").forEach((card) => {
      card.addEventListener("click", (e) => { e.stopPropagation(); liftCard(card); });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); liftCard(card); }
      });
    });
  }

  /* =========================================================
     Sounds. Viking Hub plays sound files from static/audio:
     horn.mp3 (or .wav, .ogg, .m4a) for the alerts horn and war-cry.mp3 for finishing orientation.
     With no file there, the horn still shakes silently.
     ========================================================= */
  const SOUNDS = (() => { try { return JSON.parse(document.getElementById("sound-data").textContent); } catch (_) { return {}; } })();
  const HORN_SECONDS = 0.8;  // same length as the horn-shake animation in style.css

  function playSound(url, { volume = 0.5, seconds = 0 } = {}) {
    if (!url) return;
    try {
      const a = new Audio(url);
      a.volume = volume;
      a.play().catch(() => {});
      if (!seconds) return;
      // Fade over the last quarter second so the sound ends with the animation
      setTimeout(() => {
        const fade = setInterval(() => {
          a.volume = Math.max(0, a.volume - volume / 8);
          if (a.volume <= 0.001) { clearInterval(fade); a.pause(); }
        }, 30);
      }, Math.max(0, seconds * 1000 - 240));
    } catch (_) { /* audio not available */ }
  }

  // Heard every time the horn shakes, so it plays quietly and stops with the shake
  // Each sound can be turned off in Settings
  const prefs = () => window.VH_PREFS || {};
  function blowHorn() { if (prefs().sound_horn !== false) playSound(SOUNDS.horn, { volume: 0.28, seconds: HORN_SECONDS }); }
  function warCry() { if (prefs().sound_war_cry !== false) playSound(SOUNDS.war_cry, { volume: 0.7 }); }

  VH.blowHorn = blowHorn;
  VH.warCry = warCry;

  /* =========================================================
     Alerts: one store, rendered in the horn panel and on Home
     ========================================================= */
  const alertsData = $("#alerts-data");
  let alerts = alertsData ? JSON.parse(alertsData.textContent) : [];
  const lists = $$("[data-alert-list]");
  const expanded = new WeakSet();

  // Buttons some alerts carry, such as the low balance alert
  const ALERT_ACTIONS = {
    add_funds: `<a class="btn btn-primary btn-sm" href="/viking-card#add-funds">${svg("plus")} Add funds</a>`,
    lock_card: `<button class="btn btn-ghost btn-sm" type="button" data-alert-lock>${svg("lock")} Lock card</button>`,
  };
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-alert-lock]");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    VH.lockCard();
  });

  // New alerts stay highlighted until the student closes the list they saw them in
  function alertHTML(a, arriving) {
    return `<li class="alert-item alert-cat-${esc(a.category)}${a.new ? " is-new" : ""}${arriving ? " is-arriving" : ""}" data-alert-id="${a.id}">
      <a class="alert-link" href="${esc(a.url)}">
        <span class="row-icon">${svg(a.icon)}</span>
        <span class="alert-body"><span class="alert-meta">${a.new ? `<span class="alert-new-tag">New</span>` : ""}<span>${esc(a.label)}</span></span>
          <strong>${esc(a.title)}</strong><p>${esc(a.body)}</p><small>${esc(a.when)}</small></span>
      </a>
      ${a.actions && a.actions.length ? `<div class="alert-actions">${a.actions.map((k) => ALERT_ACTIONS[k] ? ALERT_ACTIONS[k] : "").join("")}</div>` : ""}
      <button class="alert-clear" type="button" data-alert-clear="${a.id}" aria-label="Clear alert: ${esc(a.title)}">${svg("x")}</button>
    </li>`;
  }

  function filterFor(list) {
    const box = list.closest(".popover, .panel, section") || list.parentElement;
    const pick = $("[data-alert-filter]", box);
    return pick ? pick.value : "";
  }
  function render() {
    lists.forEach((list) => {
      const limit = expanded.has(list) ? Infinity : Number(list.dataset.limit || 5);
      const f = filterFor(list);
      const matching = alerts.filter((a) => !f || (f === "new" ? a.new : a.category === f));
      const shown = matching.slice(0, limit);
      const existing = new Set($$("[data-alert-id]", list).map((li) => Number(li.dataset.alertId)));
      list.innerHTML = shown.map((a) => alertHTML(a, existing.size > 0 && !existing.has(a.id))).join("");
      const box = list.parentElement;
      const empty = $("[data-alert-empty]", box);
      if (empty) empty.hidden = alerts.length > 0;
      const none = $("[data-alert-none]", box);
      if (none) none.hidden = !(alerts.length > 0 && matching.length === 0);
      const note = $("[data-alert-new-note]", box);
      if (note) note.hidden = !alerts.some((a) => a.new);
      const toggle = $("[data-alerts-toggle]", box);
      if (toggle) {
        const extra = matching.length - Number(list.dataset.limit || 5);
        toggle.hidden = extra <= 0;
        toggle.textContent = expanded.has(list) ? "Show fewer" : `Show all (${matching.length})`;
      }
      const clearAll = $("[data-alerts-clear-all]", box);
      if (clearAll) clearAll.hidden = alerts.length === 0;
    });
    // The horn badge counts new alerts
    const fresh = alerts.filter((a) => a.new).length;
    $$("[data-alert-count]").forEach((b) => { b.textContent = fresh; b.hidden = fresh === 0; });
    $$("[data-alert-count-inline]").forEach((b) => { b.textContent = alerts.length ? `(${alerts.length})` : ""; });
  }

  // Collapse an alert's height, then re-render so the rest move up into its place.
  function animateOut(id) {
    const items = $$(`[data-alert-id="${id}"]`);
    items.forEach((li) => {
      li.style.height = li.offsetHeight + "px";
      requestAnimationFrame(() => { li.classList.add("is-leaving"); li.style.height = "0px"; });
    });
    return new Promise((r) => setTimeout(r, items.length ? 280 : 0));
  }

  document.addEventListener("click", async (e) => {
    const clearBtn = e.target.closest("[data-alert-clear]");
    if (clearBtn) {
      e.preventDefault();
      const id = Number(clearBtn.dataset.alertClear);
      clearBtn.disabled = true;
      try {
        await Promise.all([VH.api(`/api/alerts/${id}/clear`, { method: "POST" }), animateOut(id)]);
        alerts = alerts.filter((a) => a.id !== id);
        render();
      } catch (err) { clearBtn.disabled = false; VH.toast(err.message, "error"); }
      return;
    }
    if (e.target.closest("[data-alerts-clear-all]")) {
      if (!alerts.length) return;
      try {
        await VH.api("/api/alerts/clear-all", { method: "POST" });
        await Promise.all(alerts.map((a) => animateOut(a.id)));
        alerts = [];
        render();
        VH.toast("All alerts cleared");
      } catch (err) { VH.toast(err.message, "error"); }
      return;
    }
    const toggle = e.target.closest("[data-alerts-toggle]");
    if (toggle) {
      const list = $("[data-alert-list]", toggle.parentElement);
      expanded.has(list) ? expanded.delete(list) : expanded.add(list);
      render();
    }
  });

  $$("[data-alert-filter]").forEach((s) => s.addEventListener("change", render));

  async function markSeen() {
    if (!alerts.some((a) => a.new)) return;
    alerts = alerts.map((a) => ({ ...a, new: false }));
    try { await VH.api("/api/alerts/seen", { method: "POST" }); } catch (_) { /* tried again next time */ }
    render();
  }
  // On the full alerts page, the highlight lasts until the student leaves the page
  if ($("[data-mark-seen='leave']")) {
    window.addEventListener("pagehide", () => {
      if (!alerts.some((a) => a.new)) return;
      fetch("/api/alerts/seen", { method: "POST", keepalive: true, credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": $('meta[name="csrf-token"]').content } });
    });
  }

  VH.alerts = {
    async refresh() {
      try { alerts = (await VH.api("/api/alerts")).alerts; render(); } catch (_) {}
    },
  };

  const hornRoot = $("[data-alerts-root]");
  if (hornRoot) {
    const horn = $("[data-horn]", hornRoot);
    popover(hornRoot, horn, $("#alerts-panel"), () => VH.alerts.refresh(), markSeen);
    horn.addEventListener("click", shakeHorn);
  }
  render();

  /* Shake the horn, show sound lines and give a short, quiet blast */
  function shakeHorn() {
    const horn = $("[data-horn]");
    if (!horn) return;
    horn.classList.remove("is-blowing");
    void horn.offsetWidth;  // restart the animation
    horn.classList.add("is-blowing");
    blowHorn();
    clearTimeout(shakeHorn.t);
    shakeHorn.t = setTimeout(() => horn.classList.remove("is-blowing"), 850);
  }

  /* =========================================================
     Live moments: some pages get a new alert a few seconds after they open
     (once per launch of the app). The horn shakes, a card slides in, and the
     page updates if the alert changed something on it.
     ========================================================= */
  function liveCard(a) {
    const region = $(".live-region") || document.body.appendChild(Object.assign(document.createElement("div"), { className: "live-region" }));
    const el = document.createElement("div");
    el.className = "live-card";
    el.setAttribute("role", "status");
    el.innerHTML = `<span class="row-icon">${svg(a.icon)}</span>
      <div class="live-body"><span class="live-label">New alert · ${esc(a.label)}</span><strong>${esc(a.title)}</strong><p>${esc(a.body)}</p>
        <a class="live-link" href="${esc(a.url)}">View</a></div>
      <button class="icon-btn live-close" type="button" aria-label="Dismiss">${svg("x")}</button>`;
    region.appendChild(el);
    const close = () => { el.classList.add("is-leaving"); setTimeout(() => el.remove(), 300); };
    $(".live-close", el).addEventListener("click", close);
    setTimeout(close, 8000);
  }
  if (window.VH_MOMENT && window.VH_MOMENT.id) {
    const m = window.VH_MOMENT;
    setTimeout(async () => {
      if (document.hidden) return;  // the student switched tabs; it waits for the next visit
      try {
        const data = await VH.api(`/api/moments/${m.id}`, { method: "POST" });
        if (data.card) {
          $$("[data-balance]").forEach((el) => { el.textContent = data.card.balance_label; });
          document.dispatchEvent(new CustomEvent("vh:card", { detail: data.card }));
        }
        if (data.schedule_changed) document.dispatchEvent(new CustomEvent("vh:schedule-changed"));
        if (!data.alert) return;
        alerts = [data.alert, ...alerts.filter((a) => a.id !== data.alert.id)];
        render();
        shakeHorn();
        liveCard(data.alert);
      } catch (_) { /* nothing new this time */ }
    }, m.delay * 1000);
  }

  /* =========================================================
     Sign in page
     ========================================================= */
  $$("[data-toggle-password]").forEach((btn) => {
    const input = btn.parentElement.querySelector("input");
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", String(show));
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
      input.focus();
    });
  });

  // Keep the browser from filling saved sign-in details unless Remember me was used.
  // The fields stay read-only until the student actually selects them.
  $$("[data-no-autofill]").forEach((input) => {
    const unlock = () => input.removeAttribute("readonly");
    input.addEventListener("focus", unlock, { once: true });
    input.addEventListener("pointerdown", unlock, { once: true });
  });

  const loginForm = $("[data-login-form]");
  if (loginForm) {
    // Let the student know when Caps Lock is on while typing the password
    const caps = $("[data-caps]", loginForm);
    const pw = $("#password", loginForm);
    const checkCaps = (e) => { if (e.getModifierState) caps.hidden = !e.getModifierState("CapsLock"); };
    pw.addEventListener("keydown", checkCaps);
    pw.addEventListener("keyup", checkCaps);
    pw.addEventListener("blur", () => { caps.hidden = true; });

    const idInput = $("#student_id", loginForm);
    const pwInput = $("#password", loginForm);
    const submit = $("[data-submit]", loginForm);
    const setError = (input, message) => {
      const field = input.closest(".field");
      field.classList.toggle("has-error", Boolean(message));
      $(".field-error", field).textContent = message || "";
      input.setAttribute("aria-invalid", message ? "true" : "false");
    };
    const checkId = () => {
      const v = idInput.value.trim();
      if (!v) return "Enter your ID.";
      if (!/^2\d{6}$/.test(v)) return "Your ID is the 7-digit number on your Viking Card.";
      return "";
    };
    const checkPw = () => (pwInput.value ? "" : "Enter your password.");

    idInput.addEventListener("input", () => {
      const digits = idInput.value.replace(/\D/g, "").slice(0, 7);
      if (digits !== idInput.value) idInput.value = digits;
      if (idInput.closest(".field").classList.contains("has-error")) setError(idInput, checkId());
    });
    idInput.addEventListener("blur", () => { if (idInput.value) setError(idInput, checkId()); });
    pwInput.addEventListener("input", () => {
      if (pwInput.closest(".field").classList.contains("has-error")) setError(pwInput, checkPw());
    });

    // Enter in either field submits the form; validate first.
    loginForm.addEventListener("submit", (e) => {
      const idErr = checkId();
      const pwErr = checkPw();
      setError(idInput, idErr);
      setError(pwInput, pwErr);
      if (idErr || pwErr) { e.preventDefault(); (idErr ? idInput : pwInput).focus(); return; }
      submit.classList.add("is-loading");
      submit.innerHTML = '<span class="spinner" aria-hidden="true"></span><span>Signing in</span>';
    });
    window.addEventListener("pageshow", () => {
      submit.classList.remove("is-loading");
      submit.innerHTML = "<span>Sign in</span>";
    });
  }
})();
