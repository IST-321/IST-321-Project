/* Orientation: update recommended steps and sail the longship */
(() => {
  "use strict";
  const page = document.querySelector("[data-or-page]");
  if (!page) return;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  function showProgress(p) {
    $("[data-or-percent]", page).textContent = p.percent;
    $("[data-or-message]", page).textContent = p.message;
    $(".voyage-fill", page).style.width = p.percent + "%";
    $(".voyage-ship", page).style.left = p.percent + "%";
    $("[data-or-bar]", page).setAttribute("aria-valuenow", p.percent);
    ["complete", "in_progress", "not_started"].forEach((k) => { $(`[data-or-count="${k}"]`, page).textContent = p[k]; });
    page.classList.toggle("is-complete", p.percent === 100);
  }

  // The last step: bring the progress bar into view, then sail the final stretch and celebrate
  async function finishVoyage(p) {
    const bar = $(".or-progress", page);
    bar.scrollIntoView({ behavior: "smooth", block: "center" });
    await wait(700);
    showProgress(p);
    await wait(900);  // let the ship reach the flag
    VH.warCry && VH.warCry();
    const dlg = $("#celebrate-dialog");
    if (!dlg) return;
    // Onward (or closing the popup) heads home; Orientation is now retired from the menu
    dlg.addEventListener("close", () => { window.location.href = dlg.dataset.home; }, { once: true });
    dlg.showModal();
  }

  $$(".task", page).forEach((task) => {
    $$("[data-status]", task).forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (btn.classList.contains("is-on")) return;
        const status = btn.dataset.status;
        try {
          const data = await VH.api(`/api/orientation/${task.dataset.task}`, { method: "POST", body: { status } });
          $$("[data-status]", task).forEach((b) => {
            const on = b.dataset.status === status;
            b.classList.toggle("is-on", on);
            b.setAttribute("aria-checked", String(on));
          });
          task.className = "task status-" + status.toLowerCase().replace(" ", "-");
          if (data.progress.percent === 100 && !page.classList.contains("is-complete")) {
            await finishVoyage(data.progress);
          } else {
            showProgress(data.progress);
            if (status === "Complete") VH.toast("Orientation task completed");
          }
          if (status === "Complete") VH.alerts.refresh();
        } catch (err) { VH.toast(err.message, "error"); }
      });
    });
  });
})();
