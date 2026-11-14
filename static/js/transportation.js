/* Getting around pages: parking estimates, where-can-I-park, issue reports and the escort chat */
(() => {
  "use strict";
  const page = document.querySelector("[data-tr-page]");
  if (!page) return;
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const esc = VH.esc;
  const data = JSON.parse($("#tr-data").textContent);

  /* ---------- Parking right now ---------- */
  const garageList = $("[data-garages]");
  if (garageList) {
    let garages = data.garages;
    const LEVEL_CLASS = { "Open": "is-open", "Filling up": "is-filling", "Almost full": "is-low", "Full": "is-full" };
    const render = () => {
      garageList.innerHTML = garages.map((g) => `
        <li class="garage ${LEVEL_CLASS[g.level]}${data.focus === g.map ? " is-focus" : ""}" id="garage-${esc(g.code)}">
          <div class="garage-main">
            <div class="garage-title"><strong>${esc(g.name)}</strong><span class="garage-level">${esc(g.level)}</span></div>
            <small>${esc(g.address)} · ${esc(g.permits)}</small>
            <div class="garage-bar" role="img" aria-label="About ${g.available} of ${g.capacity} spaces open">
              <span style="width:${100 - g.percent}%"></span>
            </div>
          </div>
          <div class="garage-count"><strong>${g.available.toLocaleString()}</strong><small>of ${g.capacity.toLocaleString()} open</small></div>
          ${g.map ? `<a class="btn btn-ghost btn-sm garage-map" href="/campus-map?b=${esc(g.map)}">${VH.svg("map")}<span>Map</span></a>` : `<span class="garage-map"></span>`}
        </li>`).join("");
      const stamp = garages[0] && garages[0].updated_at;
      if (stamp) $("[data-park-updated]").textContent = `Estimated open spaces, updated ${VH.fmtTime(stamp.slice(11, 16))}`;
    };
    render();
    if (data.focus) {
      const el = $(".garage.is-focus");
      if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "center" }), 200);
    }
    $("[data-park-refresh]").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.classList.add("is-spinning");
      try {
        const res = await VH.api("/api/transportation/parking/refresh", { method: "POST" });
        garages = res.garages;
        render();
        res.frozen ? VH.toast(res.message, "error", 4500) : VH.toast("Parking updated");
      } catch (err) { VH.toast(err.message, "error"); }
      finally { btn.disabled = false; btn.classList.remove("is-spinning"); }
    });
  }

  /* ---------- Where can I park? ---------- */
  if ($("[data-where-results]")) {
    const fmtWindow = ([a, b]) => (a === "00:00" && b === "23:59") ? "24 hours" : `${VH.fmtTime(a)} to ${VH.fmtTime(b)}`;
    const rule = (row, permit) => {
      if (row.only_note) return { text: row.only_note };
      const win = row[permit];
      if (permit === "Visitor" && !win) return { text: row.visitor_note || "No visitor parking" };
      return win ? { win } : { text: "N/A" };
    };
    const cellText = (row, permit) => {
      const r = rule(row, permit);
      if (!r.win) return r.text;
      if (permit === "Visitor" && row.visitor_note) return row.visitor_note;
      const [wk, we] = r.win;
      if (wk[0] === we[0] && wk[1] === we[1]) return `Every day, ${fmtWindow(wk)}`;
      return `Weekdays ${fmtWindow(wk)}; weekends ${fmtWindow(we)}`;
    };
    const renderWhere = () => {
      const permit = $("[data-where-permit]").value;
      const weekend = $("[data-where-day]").value === "1";
      const time = $("[data-where-time]").value || "12:00";
      const yes = [], later = [];
      data.access.forEach((row) => {
        const r = rule(row, permit);
        if (!r.win) return;
        const [a, b] = r.win[weekend ? 1 : 0];
        (time >= a && time <= b ? yes : later).push({ row, when: fmtWindow([a, b]) });
      });
      const item = (x, ok) => `<li class="${ok ? "is-yes" : "is-later"}">${VH.svg(ok ? "check" : "clock")}
          <div><strong>${esc(x.row.name)}</strong><small>${ok ? "Valid now · " : "Not at this time · "}${esc(x.when)}${x.row.visitor_note && permit === "Visitor" ? " · " + esc(x.row.visitor_note) : ""}</small></div></li>`;
      $("[data-where-results]").innerHTML = yes.length || later.length
        ? `${yes.length ? `<ul class="where-list">${yes.map((x) => item(x, true)).join("")}</ul>` : `<p class="muted">Nowhere is open to this permit at that time.</p>`}
           ${later.length ? `<p class="where-sub">Valid at other times</p><ul class="where-list">${later.map((x) => item(x, false)).join("")}</ul>` : ""}`
        : `<p class="muted">This permit isn't valid in any of these locations.</p>`;
    };
    $$("[data-where-permit], [data-where-day], [data-where-time]").forEach((el) => el.addEventListener("input", renderWhere));
    renderWhere();
    $("[data-access-body]").innerHTML = data.access.map((row) => `<tr>
        <th scope="row">${esc(row.name)}</th><td>${esc(row.overnight || "N/A")}</td>
        ${data.permits.map((p) => { const t = cellText(row, p); return `<td class="${t === "N/A" ? "is-na" : ""}">${esc(t)}</td>`; }).join("")}
      </tr>`).join("");
  }

  /* ---------- Report an issue ---------- */
  const form = $("[data-report-form]");
  if (form) {
    let reports = data.reports;
    const pick = $("[data-loc-pick]");
    pick.addEventListener("change", () => { $("[data-loc-other]").hidden = pick.value !== "Somewhere else"; });
    const renderReports = (freshId) => {
      $("[data-report-list]").innerHTML = reports.length
        ? reports.map((r) => `<li class="${r.id === freshId ? "is-fresh" : ""}">
            <div class="report-top"><span class="report-cat">${esc(r.category)}</span><span class="status status-wait">${VH.svg("clock")}${esc(r.status)}</span></div>
            <strong>${esc(r.location)}</strong>
            <p>${esc(r.description)}</p>${r.details ? `<p class="muted small">${esc(r.details)}</p>` : ""}
            <small class="muted">Submitted ${VH.fmtStamp(r.created_at)}</small></li>`).join("")
        : `<li class="report-empty">No reports yet. Anything you submit shows up here with its status.</li>`;
    };
    renderReports();
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(form);
      const location = f.get("location_pick") === "Somewhere else" ? f.get("location_other") : f.get("location_pick");
      const err = $("[data-report-error]");
      err.textContent = "";
      try {
        reports = (await VH.api("/api/transportation/reports", { method: "POST", body: {
          category: f.get("category"), location, description: f.get("description"), details: f.get("details"),
        } })).reports;
        renderReports(reports[0] && reports[0].id);
        form.reset();
        $("[data-loc-other]").hidden = true;
        VH.toast("Report submitted. It's under review.");
      } catch (ex) { err.textContent = ex.message; }
    });
  }

  /* ---------- Escort chat ---------- */
  const chat = $("#escort-chat");
  if (chat) {
    const log = $("[data-chat-log]", chat);
    const quick = $("[data-chat-quick]", chat);
    const chatForm = $("[data-chat-form]", chat);
    const POINTS = data.points;
    const norm = (t) => t.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9 ]/g, " ").replace(/\b(the|hall|building|bldg)\b/g, " ").replace(/\s+/g, " ").trim();
    // Match a building by its code, full name, short names, or its pickup point
    function findPlace(text) {
      const raw = text.trim();
      const code = raw.toUpperCase();
      const byCode = POINTS.find((p) => p.code === code);
      if (byCode) return byCode;
      const t = norm(raw);
      if (!t) return null;
      return POINTS.find((p) => [p.name, ...p.aliases].some((n) => norm(n) === t))
        || POINTS.find((p) => [p.name, ...p.aliases].some((n) => norm(n).length > 3 && (t.includes(norm(n)) || norm(n).includes(t) && t.length > 3)))
        || POINTS.find((p) => norm(p.point) === t);
    }
    let step = 0, from = null, to = null, closing = null;

    function say(text, who = "them", delay = 0) {
      return new Promise((resolve) => {
        const show = () => {
          const li = document.createElement("li");
          li.className = `chat-msg from-${who}`;
          li.innerHTML = `<p>${esc(text)}</p>`;
          log.appendChild(li);
          log.scrollTop = log.scrollHeight;
          resolve();
        };
        if (!delay) { show(); return; }
        const typing = document.createElement("li");
        typing.className = "chat-msg from-them is-typing";
        typing.innerHTML = "<p><span></span><span></span><span></span></p>";
        log.appendChild(typing);
        log.scrollTop = log.scrollHeight;
        setTimeout(() => { typing.remove(); show(); }, delay);
      });
    }
    const offer = (options) => {
      quick.innerHTML = options.map((o) => `<button type="button" class="chip" data-quick="${esc(o)}">${esc(o)}</button>`).join("");
    };
    const SUGGEST = ["Student Center", "Berkman Hall", "Rhodes Tower", "Fenn Tower", "Recreation Center", "Washkewicz Hall"];
    async function notKnown(text) {
      await say(`Sorry, I don't recognize "${text}" as an escort location. Try a campus building such as Berkman Hall, Rhodes Tower or the Student Center, or its code, like BH.`, "them", 800);
      offer(SUGGEST);
    }
    async function reply(text) {
      quick.innerHTML = "";
      await say(text, "me");
      if (step === 3) return;
      if (/^arrived$/i.test(text.trim())) {
        if (step === 2) {
          step = 3;
          await say(`Glad you made it to ${to.name}, Magnus. This chat will close in 3 seconds.`, "them", 600);
          chatForm.msg.disabled = true;
          closing = setTimeout(() => chat.close(), 3000);
        } else {
          await say("Let's set up your walk first. Where should we meet you?", "them", 600);
          offer(SUGGEST);
        }
        return;
      }
      if (step === "confirm") {
        if (/^(y|yes|yeah|yep|correct|right|that'?s right|confirm)/i.test(text.trim())) {
          step = 1;
          await say(`Great, we'll meet you at ${from.name}. Where are you headed?`, "them", 800);
          offer(SUGGEST.filter((n) => !from.buildings.includes(n)).slice(0, 5));
          return;
        }
        if (/^(n|no|nope|somewhere else)/i.test(text.trim())) {
          step = 0; from = null;
          await say("No problem. Where should we meet you?", "them", 700);
          offer(SUGGEST);
          return;
        }
        const place = findPlace(text);
        if (!place) { await say("Sorry, I didn't catch that. Is that the right pickup point? Answer yes or no.", "them", 700); offer(["Yes, that's right", "No, somewhere else"]); return; }
        step = 0;
      }
      if (step === 0) {
        from = findPlace(text);
        if (!from) return notKnown(text);
        step = 1;
        await say(`Got it, we'll meet you at ${from.name}, at the ${from.point} pickup point. Where are you headed?`, "them", 900);
        offer(SUGGEST.filter((n) => n !== from.name).slice(0, 5));
      } else if (step === 1) {
        const place = findPlace(text);
        if (!place) return notKnown(text);
        if (place === from || (from.buildings && from.buildings.includes(place.name))) {
          await say(`You're already at ${from.name}. Where would you like to walk to?`, "them", 700);
          return;
        }
        to = place;
        step = 2;
        await say(`Thanks. A Viking Safety Ambassador will meet you at ${from.name} and walk with you to ${to.name}.`, "them", 1100);
        await say("Wait inside or in a well-lit spot near the entrance. The ambassador will be in a CSU safety uniform and will say your name.", "them", 1200);
        await say(`Your ambassador will end this chat once they confirm you've reached ${to.name}. You can also type ARRIVED when you get there.`, "them", 1000);
        await say("If you feel you're in danger at any point, call 216-687-2020 right away.", "them", 800);
      } else {
        await say("Your ambassador is on the way. Type ARRIVED when you reach your destination, or call 216-687-2020 if anything changes.", "them", 800);
      }
    }
    // The chat starts from a pickup point picked on the map, and only asks to confirm it
    async function startChat(stop) {
      clearTimeout(closing);
      log.innerHTML = "";
      to = null;
      chatForm.msg.disabled = false;
      chat.showModal();
      if (stop) {
        from = { name: stop.name, point: stop.name, buildings: stop.buildings };
        step = "confirm";
        await say(`Hi Magnus, this is Viking Safety Escorts. We'll meet you at ${stop.name}, by ${stop.buildings.join(" and ")}. Is that right?`, "them", 800);
        offer(["Yes, that's right", "No, somewhere else"]);
      } else {
        from = null; step = 0;
        await say("Hi Magnus, this is Viking Safety Escorts. Where should we meet you?", "them", 700);
        offer(SUGGEST);
      }
      chatForm.msg.focus();
    }
    const stopById = Object.fromEntries((data.stops || []).map((st) => [st.id, st]));
    // Once the chat opens, the selected point and key row go back to normal
    const fig = $(".escort-map");
    const clearHighlight = () => {
      const active = document.activeElement;
      if (active && active.closest && active.closest("[data-stop]")) active.blur();
      if (fig) fig.classList.add("is-chatting");
      const t = $("[data-esc-tip]");
      if (t) t.hidden = true;
    };
    const openFrom = (el) => { clearHighlight(); startChat(stopById[el.dataset.stop]); };
    page.addEventListener("click", (e) => {
      const el = e.target.closest("[data-stop]");
      if (el) openFrom(el);
    });
    page.addEventListener("keydown", (e) => {
      const el = e.target.closest(".esc-stop");
      if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openFrom(el); }
    });
    // The dialog hands focus back to the point when it closes; don't light it up again
    chat.addEventListener("close", () => requestAnimationFrame(clearHighlight));
    // Hover works again as soon as the pointer moves over the map
    if (fig) fig.addEventListener("pointermove", () => { if (!chat.open) fig.classList.remove("is-chatting"); });
    // Name and buildings when hovering a pickup point
    const tip = $("[data-esc-tip]");
    if (tip && fig) {
      fig.addEventListener("pointermove", (e) => {
        const el = e.target.closest(".esc-stop");
        if (!el || chat.open) { tip.hidden = true; return; }
        const st = stopById[el.dataset.stop];
        tip.innerHTML = `<strong>${esc(st.name)}</strong><span>${esc(st.buildings.join(", "))} · select to request an escort</span>`;
        tip.hidden = false;
        const r = fig.getBoundingClientRect();
        tip.style.transform = `translate(${Math.min(e.clientX - r.left + 14, r.width - tip.offsetWidth - 6)}px, ${Math.max(e.clientY - r.top - tip.offsetHeight - 12, 4)}px)`;
      });
      fig.addEventListener("pointerleave", () => { tip.hidden = true; });
    }
    $("[data-chat-close]", chat).addEventListener("click", () => chat.close());
    chat.addEventListener("close", () => clearTimeout(closing));
    quick.addEventListener("click", (e) => { const b = e.target.closest("[data-quick]"); if (b) reply(b.dataset.quick); });
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = chatForm.msg.value.trim();
      if (!text) return;
      chatForm.msg.value = "";
      reply(text);
    });
  }
})();
