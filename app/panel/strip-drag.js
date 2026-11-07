/* Sotto -- WINDOW DRAG (panel header + bottom strip).
 *
 * OWNER, 2026-10-17, verbatim: "mover os paineis e extremamente ruim e nao
 * otimizado, parece q foi implementado completamente errado."
 *
 * WHAT IT WAS: the strip moved the WINDOW from a JS `pointermove` handler --
 * up to ~150 bridge messages and ~150 `SetWindowPos` calls per second, each
 * one also writing a log line. A move that is driven from JavaScript is always
 * chasing the compositor: every sample is at least one frame late, and the
 * shell's own "move the window" answer is another hop. That is why it felt
 * heavy and rubbery no matter how many writes were removed.
 *
 * WHAT IT IS NOW: the OS moves the window. `pointerdown` on the header or on
 * the strip asks the shell for ONE native drag (`ReleaseCapture()` +
 * `WM_NCLBUTTONDOWN` with `HTCAPTION`), which enters Windows' own modal move
 * loop. The pointer is then tracked by the window manager, not by this page:
 * no per-move messages, no per-move writes, no lag, and no feedback loop
 * between `clientX` and the window position.
 *
 * The shell persists the final rect (clamped into the work area) when the
 * native loop returns. The old JS path is kept ONLY as a fallback for a host
 * that does not ship `beginWindowDrag` (a browser harness, an older shell).
 */
(function () {
  "use strict";

  var bridge = window.sotto;
  var bar = document.getElementById("strip-controls");
  var panel = document.getElementById("panel");
  var header = document.querySelector(".panel__header");
  var native = !!(bridge && typeof bridge.beginWindowDrag === "function");

  /* THE WHOLE BAR IS THE HANDLE, AND A CONTROL IS NOT PART OF IT.
   *
   * MEASURED on the shipped file before this change (`_main/_render-1710/
   * drag-test.html`, real `strip-drag.js`, stub bridge counting
   * `beginWindowDrag`): pressing the bar, the grip, the panel header and the
   * header's empty gap each asked for one drag; pressing a `<button>` asked for
   * none; but pressing a `role="button"` element and a bare `<label>` inside the
   * bar asked for one EACH -- VERDICT FAIL. Both are clickable things, and a
   * gesture that belongs to them was being taken by the window.
   *
   * `closest()` walks ancestors, so the `<button>` cases were already right --
   * this list is the SET OF THINGS THAT ACT LIKE A CONTROL, not a list of tags
   * that happen to be used today. `label` and `summary` are in it because they
   * carry a click of their own; `data-no-drag` is the escape hatch for anything
   * a future theme turns into a control. */
  function isControl(target) {
    return !!(target && target.closest
      && target.closest(
        "button, a, input, select, textarea, summary, label, "
        + "[role='button'], [role='link'], [role='checkbox'], [role='switch'], "
        + "[role='tab'], [role='menuitem'], [contenteditable='true'], [data-no-drag], "
        /* A LINE OF THE TRANSCRIPT IS NOT A HANDLE. It is a selectable row with
         * its own click and its own folder button, and it lives inside a
         * scroller -- dragging the window out of a press that was meant to
         * select a line is the classic reading-app defect. The list and the
         * scroller around it are excluded with it, by class, because a press in
         * the empty space under the last line belongs to the scroller too. */
        + ".hist, .history__list, .history__body, .history__search, .history__bar, "
        + ".captions, .captions__body, .captions__list, .dialog, "
        + ".theme-dropdown, .panel-menu, .menu"));
  }

  function endVisual() {
    document.body.classList.remove("is-strip-dragging");
  }

  if (native) {
    function start(surface, event) {
      if (event.button !== 0 || isControl(event.target)) return;
      /* ONE PRESS, ONE DRAG. The handle is now the panel AND the header inside
       * it, so a press on the header reaches this function twice as the event
       * bubbles -- and each call asks the shell for another native move loop.
       * MEASURED with `_main/panel-drag-targets-oracle.js`: header, wordmark and
       * the control row each asked for TWO drags before this flag. Two
       * `WM_NCLBUTTONDOWN`s for one press is the class of defect that reads as
       * "the drag is broken": the second move loop owns the pointer the moment
       * the first releases it. The marker rides the EVENT object, so every
       * handler in the same dispatch sees it, and it dies with the event. */
      if (event.__sottoDragged) return;
      event.__sottoDragged = true;
      /* A drag must not also select text or start a native image drag. */
      event.preventDefault();
      document.body.classList.add("is-strip-dragging");
      try {
        bridge.beginWindowDrag(surface);
      } catch (err) {
        /* A refused drag is not a reason to break the page. */
        endVisual();
      }
    }

    if (bar) {
      bar.addEventListener("pointerdown", function (event) { start("strip", event); });
    }
    if (header) {
      /* The header AROUND the controls is the panel's drag handle. Presses
       * that land on a control stay the control's -- `isControl` is that
       * boundary, and it is the same one the strip has always used. */
      header.addEventListener("pointerdown", function (event) { start("panel", event); });
    }
    /* THE WHOLE PANEL IS THE HANDLE NOW, AND THAT IS THE FIX (owner, 2026-11-06,
     * verbatim): *"usa bem as skills, pra implementar o fato de ser possivel
     * mover qualquer painel pela tela. já que agora ta extremamente bugado. a
     * tentativa ta muito falha."*
     *
     * MEASURED BEFORE THIS: the native drag was armed on `.panel__header` and
     * `.stripbar` ONLY. On the panel surface that is a 56 px bar at the top of a
     * 900 px window, and every design that gives that bar less height -- or a
     * different composition -- shrinks the grab area with it, which reads as "the
     * panel sometimes does not move at all". The window has no other handle: the
     * body of the panel was inert.
     *
     * WHAT IS NOT A HANDLE is `isControl`'s list, plus the transcript rows and the
     * caption box: a press that selects a line, opens a menu or scrolls the feed
     * must not move the window. That boundary is the whole design, and the loop
     * oracle counts it in both directions (a press on the background asks for ONE
     * drag; a press on a row asks for none). */
    if (panel) {
      panel.addEventListener("pointerdown", function (event) { start("panel", event); });
    }
    window.addEventListener("pointerup", endVisual);
    window.addEventListener("pointercancel", endVisual);
    window.addEventListener("blur", endVisual);
    return;
  }

  /* ── FALLBACK: the old JS drag, for a host without the native call ────────
   * It is byte-for-byte the behaviour that shipped before 2026-10-17. Do not
   * extend it: a real shell takes the branch above and never runs this. */
  var KEY = "sotto:strip-offset";
  var THRESHOLD = 4;
  if (!bar || !panel) return;

  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      if (!raw) return { x: 0, y: 0 };
      var v = JSON.parse(raw);
      return { x: Number(v && v.x) || 0, y: Number(v && v.y) || 0 };
    } catch (err) { return { x: 0, y: 0 }; }
  }

  function write(off) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify({ x: Math.round(off.x), y: Math.round(off.y), v: 1 }));
    } catch (err) { /* a position that cannot be remembered is not worth a broken drag */ }
  }

  function paint(off) {
    document.documentElement.style.setProperty("--strip-move-x", Math.round(off.x) + "px");
    document.documentElement.style.setProperty("--strip-move-y", Math.round(off.y) + "px");
  }

  function tell(off, phase) {
    if (bridge && typeof bridge.setStripOffset === "function") {
      try {
        bridge.setStripOffset(Math.round(off.x), Math.round(off.y), phase);
      } catch (err) {
        /* A host that refuses the offset is a host that is going away, and a
         * drag must not break the page because of it. But SAY SO: this was the
         * only catch in this file with neither a body nor a reason, and a strip
         * that quietly stops following the drag is the kind of thing that gets
         * "fixed" by guessing. The token follows the panel's own convention
         * (`sotto: <WHAT> <detail>`, as in history-store.js). */
        if (window.console && window.console.error) {
          window.console.error('sotto: STRIP_OFFSET_FAILED phase=' + phase +
                               ' error=' + (err && err.message));
        }
      }
    }
  }

  var offset = read();
  paint(offset);
  var start = null;
  var live = null;

  bar.addEventListener("pointerdown", function (event) {
    if (event.button !== 0 || isControl(event.target)) return;
    start = { px: event.screenX, py: event.screenY, ox: offset.x, oy: offset.y };
    live = null;
    document.body.classList.add("is-strip-dragging");
  });

  window.addEventListener("pointermove", function (event) {
    if (!start) return;
    var dx = event.screenX - start.px;
    var dy = event.screenY - start.py;
    if (Math.abs(dx) < THRESHOLD && Math.abs(dy) < THRESHOLD) return;
    event.preventDefault();
    live = { x: start.ox + dx, y: start.oy + dy };
    paint(live);
    tell(live, "move");
  }, { passive: false });

  function finish() {
    if (!start) return;
    var moved = live !== null;
    offset = live || offset;
    start = null;
    live = null;
    endVisual();
    if (!moved) return;
    write(offset);
    tell(offset, "end");
  }

  window.addEventListener("pointerup", finish);
  window.addEventListener("pointercancel", finish);
  window.addEventListener("blur", finish);
})();
