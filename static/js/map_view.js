/* Phone map helpers shared by the campus map and the escort map.
   - Pinch with two fingers to zoom, drag with one finger to move around once zoomed.
   - "Full screen" on a phone opens the map over the whole app and asks the phone to
     turn sideways (where the browser allows it). Turning the phone by hand works too.
   Desktop keeps its own behavior: these only kick in for touch and phone-sized screens. */
(() => {
  "use strict";
  // Phone-sized screens, plus phones turned sideways (touch screens up to tablet width)
  const phone = () => window.matchMedia("(max-width: 639px), (pointer: coarse) and (max-width: 950px)").matches;

  /**
   * Pinch zoom on an SVG map.
   * getBox/setBox read and write the visible part of the map ({x, y, w, h} in map units).
   * zoomAt(factor, x, y) zooms around a map point; onPinch() is told a pinch happened, so the
   * caller can ignore the click that may follow.
   */
  function pinchZoom(svg, { zoomAt, panBy, onPinch }) {
    const touches = new Map();
    let last = null;
    const toMap = (cx, cy) => {
      const pt = svg.createSVGPoint();
      pt.x = cx; pt.y = cy;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      return [p.x, p.y];
    };
    const state = () => {
      const [a, b] = [...touches.values()];
      return { d: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
    };
    svg.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "touch") return;
      touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (touches.size === 2) { last = state(); onPinch(true); }
    });
    svg.addEventListener("pointermove", (e) => {
      if (!touches.has(e.pointerId)) return;
      touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (touches.size !== 2 || !last) return;
      const now = state();
      const [mx, my] = toMap(now.mx, now.my);
      if (now.d > 0 && last.d > 0) zoomAt(last.d / now.d, mx, my);
      panBy(now.mx - last.mx, now.my - last.my);
      last = now;
      e.preventDefault();
    }, { passive: false });
    const end = (e) => {
      touches.delete(e.pointerId);
      if (touches.size < 2 && last) { last = null; setTimeout(() => onPinch(false), 250); }
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    return { active: () => touches.size >= 2 };
  }

  /** Open a panel over the whole app on phones, sideways when the browser allows it. */
  function expander(panel, button, { onChange } = {}) {
    let open = false;
    const label = button.querySelector("span");
    const normal = label ? label.textContent : "";
    async function set(on) {
      open = on;
      panel.classList.toggle("is-expanded", on);
      document.documentElement.classList.toggle("map-expanded", on);
      if (label) label.textContent = on ? "Close" : normal;
      if (on) {
        try { if (panel.requestFullscreen) await panel.requestFullscreen({ navigationUI: "hide" }); } catch (_) { /* fine without it */ }
        try { if (screen.orientation && screen.orientation.lock) await screen.orientation.lock("landscape"); } catch (_) { /* not every browser allows it */ }
      } else {
        try { if (screen.orientation && screen.orientation.unlock) screen.orientation.unlock(); } catch (_) { /* nothing to undo */ }
        if (document.fullscreenElement) { try { await document.exitFullscreen(); } catch (_) { /* already closed */ } }
      }
      if (onChange) onChange(on);
    }
    button.addEventListener("click", (e) => {
      if (!open && !phone()) return;  // desktop keeps its own full screen
      e.stopImmediatePropagation();
      set(!open);                     // Close always works, whichever way the phone is turned
    }, true);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && open) set(false); });
    document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && open) set(false); });
    return { isOpen: () => open, close: () => set(false) };
  }

  window.VHMap = { phone, pinchZoom, expander };
})();
