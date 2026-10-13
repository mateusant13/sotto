/* Sotto -- THE STRIP DRAG, as a SEPARATE FILE ON PURPOSE.
 *
 * IT WAS AN INLINE <script> UNTIL 2026-10-13, AND IT NEVER RAN. MEASURED: panel.html
 * declares `script-src 'self'` with NO `'unsafe-inline'` (:22-25), and a CSP without
 * 'unsafe-inline' BLOCKS every inline <script> block. The handler below was the ONLY
 * inline script in the document -- 1 inline against 12 with src -- so the one piece of
 * panel code that made the strip MOVABLE was dead in every launch.
 *
 * That is why the strip could not be dragged, and it is a measure of how quietly this
 * failed: the page threw nothing, the console stayed clean, and the shell log had no
 * error, because a BLOCKED SCRIPT IS NOT AN ERROR -- it simply does not execute. My own
 * probe failed to trigger it for rounds and I blamed the probe (and once the bridge),
 * when the handler had never been attached at all. The lane that built the page probe
 * reported the same thing from the other side: an inline probe 'never fired, blocked by
 * the panel's own CSP'.
 *
 * Moving the bytes here is the whole fix. A file under script-src 'self' is allowed.
 */
      (function () {
        "use strict";
        var KEY = "sotto:strip-offset";
        var THRESHOLD = 4;
        var bar = document.getElementById("strip-controls");
        var panel = document.getElementById("panel");
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
          var bridge = window.sotto;
          if (bridge && typeof bridge.setStripOffset === "function") {
            try { bridge.setStripOffset(Math.round(off.x), Math.round(off.y), phase); } catch (err) {}
          }
        }

        /* Restore what the owner left, BEFORE the first paint: the bar opens where
           he put it, not where the shell docked it. */
        var offset = read();
        paint(offset);

        var start = null;
        var live = null;

        bar.addEventListener("pointerdown", function (event) {
          if (event.button !== 0) return;
          /* A press on a CONTROL is that control's. The handle and the bar's own
             gaps are the drag's. */
          if (event.target && event.target.closest && event.target.closest("button, a, input, select, textarea")) return;
          start = { px: event.clientX, py: event.clientY, ox: offset.x, oy: offset.y };
          /* `live` stays NULL until the pointer actually moves: it is the flag that
             separates a DRAG from a CLICK, and `end()` writes nothing when it is null. */
          live = null;
          document.body.classList.add("is-strip-dragging");
        });

        window.addEventListener("pointermove", function (event) {
          if (!start) return;
          var dx = event.clientX - start.px;
          var dy = event.clientY - start.py;
          if (Math.abs(dx) < THRESHOLD && Math.abs(dy) < THRESHOLD) return;
          event.preventDefault();
          live = { x: start.ox + dx, y: start.oy + dy };
          paint(live);
          write(live);
          tell(live, "move");
        }, { passive: false });

        function end() {
          if (!start) return;
          var moved = live !== null;
          offset = live || offset;
          start = null;
          live = null;
          document.body.classList.remove("is-strip-dragging");
          /* A press that never moved is NOT a drag: it must not rewrite the stored
             position (nor tell the shell anything). Measured: without this guard a
             plain CLICK on the bar wrote {x:0,y:0} over a position the owner had
             already chosen. */
          if (!moved) return;
          write(offset);
          tell(offset, "end");
        }
        window.addEventListener("pointerup", end);
        window.addEventListener("pointercancel", end);
        window.addEventListener("blur", end);
      })();
    