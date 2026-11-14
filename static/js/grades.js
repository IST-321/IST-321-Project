/* Grade tracker: running course grades, editable scores, and "what do I need?" */
(() => {
  "use strict";
  const page = document.querySelector("[data-grades]");
  if (!page) return;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = VH.esc;
  const data = JSON.parse($("#grades-data").textContent);
  const courses = Object.fromEntries(data.courses.map((c) => [c.code, c]));
  const targets = {};          // chosen target per course
  const openCats = new Set();  // categories the student expanded
  const list = $("[data-grade-list]", page);

  const num = (n) => (Number.isInteger(n) ? String(n) : String(+n.toFixed(2)));
  const pct = (n) => (n === null ? "No scores yet" : `${num(n)}%`);

  function needText(n, target) {
    if (!n) return "";
    if (n.state === "needed") return `You need about <strong>${n.need}%</strong> on the rest of your work.`;
    if (n.state === "secured") return `Already locked in, even with no points on the rest.`;
    if (n.state === "out_of_reach") return `Out of reach now. Full marks on the rest would finish at about ${num(n.best)}%.`;
    return n.reached ? `Everything is graded, and you reached a ${esc(target)}.` : `Everything is graded, and you finished below a ${esc(target)}.`;
  }

  function itemRow(i) {
    const due = i.due_date ? VH.fmtDate(i.due_date, { weekday: false, short: true }) : "";
    return `<li class="g-item${i.earned === null ? " is-open" : ""}" data-item="${i.id}">
      <div class="g-item-main"><strong>${esc(i.title)}</strong><small>${i.earned === null ? `Not graded yet${due ? " · due " + due : ""}` : `${num(i.percent)}%${due ? " · " + due : ""}`}</small></div>
      <label class="g-score"><span class="visually-hidden">Score for ${esc(i.title)}</span>
        <input class="text-input" type="text" inputmode="decimal" value="${i.earned === null ? "" : num(i.earned)}" placeholder="–" data-earned></label>
      <span class="g-of">of ${num(i.possible)}</span>
      <button class="icon-btn g-remove" type="button" data-remove="${i.id}" aria-label="Remove ${esc(i.title)}">${VH.svg("x")}</button>
    </li>`;
  }

  function card(c) {
    const target = targets[c.code] || "B";
    const meter = c.current === null ? 0 : Math.min(100, c.current);
    return `<section class="panel g-card" data-course="${esc(c.code)}">
      <header class="g-head">
        <div><h3>${esc(c.code)}</h3><span class="muted small">${esc(c.professor)}</span></div>
        <div class="g-now"><strong>${pct(c.current)}</strong>${c.letter ? `<span class="g-letter">${esc(c.letter)}</span>` : ""}</div>
      </header>
      <div class="g-meter" role="img" aria-label="Current grade ${pct(c.current)}"><span style="width:${meter}%"></span></div>
      <div class="g-need">
        <label for="t-${esc(c.code)}">To finish with</label>
        <select class="text-input" id="t-${esc(c.code)}" data-target>${data.targets.map((t) => `<option${t === target ? " selected" : ""}>${t}</option>`).join("")}</select>
        <p data-need-text aria-live="polite"></p>
      </div>
      <ul class="g-cats">${c.categories.map((cat) => {
        const key = `${c.code}:${cat.id}`;
        const open = openCats.has(key);
        return `<li class="g-cat${open ? " is-open" : ""}">
          <button type="button" class="g-cat-head" data-cat="${key}" aria-expanded="${open}">
            <span class="g-cat-name">${esc(cat.name)}</span><span class="muted small">${cat.weight}% of grade</span>
            <span class="g-cat-score${cat.score === null ? " is-empty" : ""}">${cat.score === null ? "Not graded" : pct(cat.score)}</span>${VH.svg("chevron-right")}
          </button>
          <div class="g-cat-body"${open ? "" : " hidden"}>
            <ul class="g-items">${cat.items.map(itemRow).join("")}</ul>
            <form class="g-add" data-add="${cat.id}" novalidate>
              <input class="text-input" name="title" placeholder="New score, like Quiz 5" aria-label="Name">
              <input class="text-input" name="earned" inputmode="decimal" placeholder="Score" aria-label="Score">
              <input class="text-input" name="possible" inputmode="decimal" placeholder="Out of" aria-label="Points possible">
              <button class="btn btn-ghost btn-sm" type="submit">${VH.svg("plus")} Add</button>
            </form>
          </div>
        </li>`;
      }).join("")}</ul>
      <div class="g-foot">
        <p class="muted small">${c.remaining.length ? `Still to come: ${c.remaining.map(esc).join(", ")}.` : "Every item is graded."} Official grades are in CampusNet.</p>
        <div class="g-setup">
          <span class="g-badge${c.customized ? " is-custom" : ""}">${c.customized ? `${VH.svg("check-circle")} Set up by you` : "Standard sections"}</span>
          <button class="btn btn-ghost btn-sm" type="button" data-edit-setup>${VH.svg("edit")} Edit sections</button>
        </div>
      </div>
    </section>`;
  }

  async function refreshNeed(code) {
    const box = $(`[data-course="${CSS.escape(code)}"]`, list);
    const target = targets[code] || "B";
    try {
      const n = await VH.api(`/api/grades/need?course=${encodeURIComponent(code)}&target=${encodeURIComponent(target)}`);
      $("[data-need-text]", box).innerHTML = needText(n, target);
    } catch (err) { $("[data-need-text]", box).textContent = err.message; }
  }

  function render(code) {
    if (code) {
      const old = $(`[data-course="${CSS.escape(code)}"]`, list);
      old.outerHTML = card(courses[code]);
      refreshNeed(code);
    } else {
      list.innerHTML = data.courses.map((c) => card(courses[c.code])).join("");
      data.courses.forEach((c) => refreshNeed(c.code));
    }
  }
  render();

  const codeOf = (el) => el.closest("[data-course]").dataset.course;
  function apply(course, message) {
    courses[course.code] = { ...courses[course.code], ...course };
    render(course.code);
    if (message) VH.toast(message);
  }

  list.addEventListener("click", async (e) => {
    const head = e.target.closest("[data-cat]");
    if (head) {
      const key = head.dataset.cat;
      openCats.has(key) ? openCats.delete(key) : openCats.add(key);
      const li = head.closest(".g-cat");
      li.classList.toggle("is-open");
      head.setAttribute("aria-expanded", String(li.classList.contains("is-open")));
      $(".g-cat-body", li).hidden = !li.classList.contains("is-open");
      return;
    }
    const edit = e.target.closest("[data-edit-setup]");
    if (edit) { openSetup(codeOf(edit)); return; }
    const rm = e.target.closest("[data-remove]");
    if (rm) {
      const ok = await VH.confirm({ title: "Remove this score?", body: "It comes out of this course's running grade.", confirmLabel: "Remove", danger: true });
      if (!ok) return;
      try {
        const res = await VH.api(`/api/grades/items/${rm.dataset.remove}`, { method: "DELETE" });
        apply(res.course, res.message);
      } catch (err) { VH.toast(err.message, "error"); }
    }
  });

  /* ---------- Sections and scale editor ---------- */
  const dlg = $("#g-dialog");
  const secList = $("[data-sec-list]", dlg);
  let editing = null;
  function secRow(sec) {
    return `<li class="g-sec" data-sec-id="${sec.id || ""}">
      <input class="text-input" data-sec-name value="${esc(sec.name)}" aria-label="Section name" maxlength="40" placeholder="Section name">
      <span class="g-weight"><input class="text-input" data-sec-weight inputmode="numeric" value="${sec.weight}" aria-label="Weight for ${esc(sec.name || "new section")}"><span>%</span></span>
      <button class="icon-btn" type="button" data-sec-remove aria-label="Remove ${esc(sec.name || "section")}">${VH.svg("x")}</button>
    </li>`;
  }
  function updateTotal() {
    const total = $$("[data-sec-weight]", secList).reduce((n, i) => n + (Number(i.value) || 0), 0);
    const el = $("[data-sec-total]", dlg);
    el.textContent = `Total ${total}%`;
    el.classList.toggle("is-off", total !== 100);
  }
  function openSetup(code) {
    editing = code;
    const c = courses[code];
    $("#g-dialog-title").textContent = `${code} sections and scale`;
    secList.innerHTML = c.categories.map((cat) => secRow(cat)).join("");
    $("[data-scale]", dlg).innerHTML = c.scale.map(([l, cut]) => `<label class="g-cut"><span>${esc(l)}</span>
      <input class="text-input" inputmode="decimal" data-cut="${esc(l)}" value="${num(cut)}" aria-label="Lowest percentage for ${esc(l)}"></label>`).join("");
    $("[data-setup-error]", dlg).textContent = "";
    $("[data-setup-reset]", dlg).hidden = !c.customized;
    updateTotal();
    dlg.showModal();
  }
  secList.addEventListener("input", updateTotal);
  secList.addEventListener("click", (e) => {
    const rm = e.target.closest("[data-sec-remove]");
    if (rm) { rm.closest(".g-sec").remove(); updateTotal(); }
  });
  $("[data-sec-add]", dlg).addEventListener("click", () => {
    secList.insertAdjacentHTML("beforeend", secRow({ name: "", weight: 0 }));
    $(".g-sec:last-child [data-sec-name]", secList).focus();
    updateTotal();
  });
  $("[data-setup-save]", dlg).addEventListener("click", async () => {
    const sections = $$(".g-sec", secList).map((li) => ({
      id: li.dataset.secId ? Number(li.dataset.secId) : null,
      name: $("[data-sec-name]", li).value.trim(),
      weight: $("[data-sec-weight]", li).value.trim(),
    }));
    const removed = courses[editing].categories.filter((cat) => !sections.some((x) => x.id === cat.id) && cat.items.some((i) => i.earned !== null));
    if (removed.length) {
      const ok = await VH.confirm({ title: "Remove sections with scores?", body: `${removed.map((r) => r.name).join(", ")} ${removed.length > 1 ? "have" : "has"} scores that will be removed too.`, confirmLabel: "Remove and save", danger: true });
      if (!ok) return;
    }
    const scale = $$("[data-cut]", dlg).map((i) => [i.dataset.cut, i.value.trim()]);
    try {
      const res = await VH.api(`/api/grades/${encodeURIComponent(editing)}/setup`, { method: "POST", body: { sections, scale } });
      dlg.close();
      apply(res.course, res.message);
    } catch (err) { $("[data-setup-error]", dlg).textContent = err.message; }
  });
  $("[data-setup-reset]", dlg).addEventListener("click", async () => {
    const std = data.standard.sections.map(([n, w]) => `${n} ${w}%`).join(", ");
    const ok = await VH.confirm({ title: `Use standard sections for ${editing}?`, body: `${editing} goes back to ${std}, with the standard letter scale. Its scores are removed.`, confirmLabel: "Use standard sections", danger: true });
    if (!ok) return;
    try {
      const res = await VH.api(`/api/grades/${encodeURIComponent(editing)}/reset`, { method: "POST" });
      dlg.close();
      apply(res.course, res.message);
    } catch (err) { $("[data-setup-error]", dlg).textContent = err.message; }
  });

  list.addEventListener("change", async (e) => {
    if (e.target.matches("[data-target]")) {
      const code = codeOf(e.target);
      targets[code] = e.target.value;
      refreshNeed(code);
      return;
    }
    if (e.target.matches("[data-earned]")) {
      const row = e.target.closest("[data-item]");
      const raw = e.target.value.trim();
      if (raw && !/^\d+(\.\d{1,2})?$/.test(raw)) { VH.toast("Enter a number, like 18 or 18.5.", "error"); return; }
      try {
        const res = await VH.api(`/api/grades/items/${row.dataset.item}`, { method: "PATCH", body: { earned: raw } });
        apply(res.course, raw ? "Score saved" : "Score cleared");
      } catch (err) { VH.toast(err.message, "error"); }
    }
  });
  // Enter in a score box saves it
  list.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-earned]")) e.target.blur(); });

  list.addEventListener("submit", async (e) => {
    const form = e.target.closest("[data-add]");
    if (!form) return;
    e.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    if (!f.title.trim()) { VH.toast("Give the score a name, like Quiz 5.", "error"); return; }
    if (!/^\d+(\.\d{1,2})?$/.test(f.possible.trim())) { VH.toast("Enter the points possible, like 10.", "error"); return; }
    try {
      const res = await VH.api("/api/grades/items", { method: "POST", body: { category_id: Number(form.dataset.add), ...f } });
      apply(res.course, res.message);
    } catch (err) { VH.toast(err.message, "error"); }
  });
})();
