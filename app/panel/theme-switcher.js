/* Sotto — theme switcher.
 *
 * ONE DEPENDENCY-FREE MODULE. It reads the manifest (`themes/themes.js`, loaded
 * BEFORE this file), owns the choice, and switches a theme by writing ONE
 * attribute:
 *
 *     document.documentElement.dataset.theme = 'theme-3'
 *
 * That is the whole mechanism. All five stylesheets are linked at once, every
 * rule in each of them is scoped to `:root[data-theme='theme-N']`, so a switch
 * is one attribute write: no reload, no parse, no network, no flicker, and no
 * per-theme JavaScript. CSS owns an optional <=180 ms colour transition and
 * honours `prefers-reduced-motion`; this module never animates anything.
 *
 * ── IT DOES NOT TOUCH THE CAPTION, STATUS OR HISTORY LOGIC ───────────────────
 * It reads no caption, writes no caption, adds no listener to the live box, and
 * changes no element that carries text. The only element it CREATES is its OWN
 * picker button, and only in the header's control cluster (`.panel__controls`),
 * never inside `.captions`, `.history` or `.status`. If a host page already
 * provides a `#theme-button`, this module BINDS to it instead of creating one.
 *
 * ── TWO MOUNT POINTS, ONE CHOICE (2026-10-08) ────────────────────────────────
 * `.panel__header` is `display:none` on the STRIP surface, so a theme control
 * that exists only inside it is UNREACHABLE the moment the shell opens the
 * strip — the owner would have no way to change the theme there. The strip's
 * control row therefore carries its own `[data-theme-button]` in the markup, and
 * this module wires and paints EVERY element carrying that attribute (plus
 * `#theme-button`). The header button is still the one it creates when the host
 * page has none; the strip button is the host page's. One `paintAll()` keeps
 * them showing the same theme, so they cannot drift.
 *
 * ── PERSISTENCE IS DEFENSIVE ON PURPOSE ─────────────────────────────────────
 * `localStorage` is not guaranteed over `file://` in WebView2: touching it can
 * throw (`SecurityError` / `QuotaExceededError`) or silently be per-document
 * opaque storage. So every access goes through `readStore`/`writeStore`, which
 * swallow a throw and fall back to an in-memory default. The choice works for
 * the session either way; persistence is a bonus, never a precondition.
 */
(function (root) {
  'use strict';

  var STORE_KEY = 'sotto.theme';

  /* The manifest is a sibling script. The inline copy is the fallback for the
   * case where it is missing (a host that only linked this file): it keeps the
   * switcher functional rather than leaving the panel with no theme at all. The
   * labels and swatches are the five design directions' own — the same table as
   * `themes/themes.js`, which is what `<html data-theme>` and the five
   * `themes/theme-N.css` files are keyed to. */
  var MANIFEST = (root && root.SottoThemeManifest) || null;
  var THEMES = (MANIFEST && MANIFEST.themes) || [
    { name: 'theme-1', label: 'Teleprompter', file: 'themes/theme-1.css', swatch: '#f2e9d8' },
    { name: 'theme-2', label: 'Broadcast', file: 'themes/theme-2.css', swatch: '#ff6a55' },
    { name: 'theme-3', label: 'Manuscrito', file: 'themes/theme-3.css', swatch: '#a9c1d9' },
    { name: 'theme-4', label: 'Cinema Card', file: 'themes/theme-4.css', swatch: '#e4b363' },
    { name: 'theme-5', label: 'Instrumento', file: 'themes/theme-5.css', swatch: '#5fd3a7' }
  ];
  var FALLBACK = (MANIFEST && MANIFEST.fallback) || THEMES[0].name;

  var memoryStore = null;

  function readStore() {
    try {
      var v = root.localStorage.getItem(STORE_KEY);
      return typeof v === 'string' ? v : null;
    } catch (err) {
      /* file:// in WebView2, a privacy mode, or a host policy: not an error,
       * just no storage. The in-memory value below is the fallback. */
      return memoryStore;
    }
  }

  function writeStore(name) {
    memoryStore = name;
    try {
      root.localStorage.setItem(STORE_KEY, name);
    } catch (err) {
      /* Deliberately silent: the choice still took effect in this document. */
    }
  }

  function known(name) {
    if (!name) return null;
    for (var i = 0; i < THEMES.length; i += 1) {
      if (THEMES[i].name === name) return THEMES[i];
    }
    return null;
  }

  function themeElement() {
    if (root.document && root.document.documentElement) return root.document.documentElement;
    return null;
  }

  function currentTheme() {
    var el = themeElement();
    return (el && el.dataset && el.dataset.theme) || FALLBACK;
  }

  function labelOf(name) {
    var t = known(name);
    return t ? t.label : String(name);
  }

  /* ── the picker ─────────────────────────────────────────────────────────────
   * A button that CYCLES, and a picker dialog that JUMPS. Cycling is the whole
   * interaction the owner asked for ("no painel, vai ter botao de mudar o
   * tema"): one click, next design, instantly. The picker exists because five
   * clicks to reach the one you want is not a control, it is a puzzle — and it
   * is the only reason this module creates a second element.
   */
  var picker = null;

  function ensurePicker(doc) {
    if (picker) return picker;
    picker = doc.createElement('div');
    picker.className = 'theme-picker';
    picker.hidden = true;
    picker.setAttribute('role', 'dialog');
    picker.setAttribute('aria-label', 'Choose a theme');

    var list = doc.createElement('div');
    list.className = 'theme-picker__list';
    list.setAttribute('role', 'group');

    /* THE LIST IS GROUPED AND BADGED (owner, 2026-10-08). He asked for the
     * near-duplicate designs to be shippable as alternatives for A/B/C testing —
     * *"pros que sao bem parecidos, faça outra alternativa, a b c testing"* — and
     * a flat list of thirty names makes two variants of ONE design look like two
     * unrelated themes. So the manifest's `group` becomes a heading and its
     * `variant` becomes the badge, which is what lets him find the pair he wants
     * to compare. Nothing here decides anything: it renders what the manifest
     * says, so a variant that is mislabelled is a manifest bug and not a UI one. */
    var lastGroup = null;
    THEMES.forEach(function (theme) {
      var group = theme.group || null;
      if (group && group !== lastGroup) {
        var head = doc.createElement('div');
        head.className = 'theme-picker__group';
        head.textContent = theme.groupLabel || group;
        list.append(head);
      }
      lastGroup = group;

      var b = doc.createElement('button');
      b.type = 'button';
      b.className = 'theme-picker__option';
      b.dataset.themeChoice = theme.name;
      b.style.setProperty('--theme-swatch', theme.swatch);

      var chip = doc.createElement('span');
      chip.className = 'theme-picker__swatch';
      chip.setAttribute('aria-hidden', 'true');
      b.append(chip);

      var label = doc.createElement('span');
      label.className = 'theme-picker__label';
      label.textContent = theme.label;
      b.append(label);

      if (theme.variant) {
        var badge = doc.createElement('span');
        badge.className = 'theme-picker__variant';
        badge.textContent = theme.variant;
        badge.title = 'Variante ' + theme.variant + ' deste design';
        b.append(badge);
      }

      b.addEventListener('click', function () {
        api.set(theme.name);
        closePicker();
      });
      list.append(b);
    });

    picker.append(list);
    doc.body.append(picker);
    return picker;
  }

  function closePicker() {
    if (picker) picker.hidden = true;
    buttons(root.document).forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  }

  function openPicker() {
    var doc = root.document;
    ensurePicker(doc);
    picker.hidden = false;
    buttons(doc).forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    var first = picker.querySelector('.theme-picker__option[aria-current="true"]')
      || picker.querySelector('.theme-picker__option');
    if (first) {
      first.focus();
      /* With the full set in the list, the current theme can be well below the
       * fold, and a picker that opens on somebody else's theme reads as "my
       * choice was lost". `scrollIntoView` with `block:'nearest'` scrolls only
       * when it has to, so the common case does not move at all. */
      if (typeof first.scrollIntoView === 'function') {
        first.scrollIntoView({ block: 'nearest' });
      }
    }
  }

  function syncPicker() {
    if (!picker) return;
    var name = currentTheme();
    var opts = picker.querySelectorAll('.theme-picker__option');
    for (var i = 0; i < opts.length; i += 1) {
      var on = opts[i].dataset.themeChoice === name;
      if (on) opts[i].setAttribute('aria-current', 'true');
      else opts[i].removeAttribute('aria-current');
    }
  }

  function paintButton(btn) {
    if (!btn) return;
    var name = currentTheme();
    var theme = known(name);
    btn.dataset.themeCurrent = name;
    btn.title = 'Theme: ' + labelOf(name) + ' — click for the next one, right-click for all five';
    btn.setAttribute('aria-label', btn.title);
    if (theme) btn.style.setProperty('--theme-swatch', theme.swatch);
    var label = btn.querySelector('.theme-button__label');
    if (label) label.textContent = labelOf(name);
  }

  /* ── EVERY MOUNT POINT, ONE PAINT ───────────────────────────────────────────
   * The theme control exists in TWO places on purpose: the header's cluster
   * (`.panel__controls`, where the module creates `#theme-button` if the host
   * page has none) and the STRIP's control row (`#strip-theme-button`, markup,
   * because `.panel__header` is `display:none` on that surface and a button
   * inside it is unreachable). Both carry `data-theme-button`; this is the one
   * list, so a third mount point is a markup line and nothing else, and the two
   * can never show different themes. */
  function buttons(doc) {
    if (!doc || !doc.querySelectorAll) return [];
    var out = [];
    var seen = [];
    var push = function (el) { if (el && seen.indexOf(el) < 0) { seen.push(el); out.push(el); } };
    var nodes = doc.querySelectorAll('[data-theme-button]');
    for (var i = 0; i < nodes.length; i += 1) push(nodes[i]);
    push(doc.getElementById('theme-button'));
    return out;
  }

  function paintAll(doc) {
    buttons(doc).forEach(paintButton);
  }

  function wireButton(btn) {
    if (!btn) return;
    /* THE TWO CLICKS ARE THE OWNER'S, verbatim (2026-10-08): *"clique esquerdo
     * avança, direito retrocede nos temas"*. So the right button now walks
     * BACKWARDS, which is a change of contract: it used to OPEN THE PICKER. The
     * picker did not lose its home — it moved to the keyboard (ArrowDown /
     * ArrowUp / Enter), where it already was — and the reason that is the right
     * trade is the owner's OTHER request: walking the flat manifest order means
     * the A/B/C variants of one design sit next to each other, so one click each
     * way flips between them, which is the comparison he asked to be able to do. */
    btn.addEventListener('click', function () {
      api.next();
    });
    btn.addEventListener('contextmenu', function (ev) {
      ev.preventDefault();
      api.previous();
    });
    btn.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp' || ev.key === 'Enter') {
        ev.preventDefault();
        if (picker && !picker.hidden) closePicker();
        else openPicker();
        return;
      }
      if (ev.key === 'ArrowRight') {
        ev.preventDefault();
        api.next();
      } else if (ev.key === 'ArrowLeft') {
        ev.preventDefault();
        api.previous();
      }
    });
    paintButton(btn);
  }

  /* The button the MODULE owns, used only when the host page has none. It is
   * inserted into the header's control cluster — `.panel__controls` — which is
   * where the panel's other controls live, so the tab order stays where the eye
   * already is. Nothing else in the document is moved, wrapped or renamed. */
  function ensureButton(doc) {
    var existing = doc.getElementById('theme-button');
    if (existing) return existing;

    var host = doc.querySelector('.panel__controls') || doc.querySelector('.panel__header');
    if (!host) return null;

    var btn = doc.createElement('button');
    btn.type = 'button';
    btn.className = 'icon-button theme-button';
    btn.id = 'theme-button';
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');

    var label = doc.createElement('span');
    label.className = 'theme-button__label';
    btn.append(label);

    host.prepend(btn);
    return btn;
  }

  /* list() — the five themes, in order, as the manifest declares them. */
  var api = {
    list: function () {
      return THEMES.map(function (t) {
        return {
          name: t.name, label: t.label, swatch: t.swatch,
          group: t.group || null, variant: t.variant || null
        };
      });
    },

    /* current() — what the document is wearing RIGHT NOW, read from the DOM and
     * not from a cached variable, so a hand-set attribute is never contradicted. */
    current: function () {
      return currentTheme();
    },

    /* set(name) — the switch itself: ONE attribute write. An unknown name is
     * refused and the current theme is returned instead of a half-applied one. */
    set: function (name, opts) {
      var el = themeElement();
      if (!el) return FALLBACK;
      var theme = known(name);
      if (!theme) return currentTheme();

      el.dataset.theme = theme.name;
      if (!opts || opts.persist !== false) writeStore(theme.name);

      syncPicker();
      paintAll(root.document);
      return theme.name;
    },

    /* next() — cycle, in manifest order, wrapping. */
    next: function () {
      var name = currentTheme();
      for (var i = 0; i < THEMES.length; i += 1) {
        if (THEMES[i].name === name) return api.set(THEMES[(i + 1) % THEMES.length].name);
      }
      return api.set(FALLBACK);
    },

    /* previous() — the SAME walk, one step back, on the owner's right button
     * (2026-10-08). Wrapping is deliberate: the ends of the list are not a wall,
     * they are the ends of a ring, so a wrong click costs one more click instead
     * of a trip to the picker. */
    previous: function () {
      var name = currentTheme();
      for (var i = 0; i < THEMES.length; i += 1) {
        if (THEMES[i].name === name) {
          return api.set(THEMES[(i - 1 + THEMES.length) % THEMES.length].name);
        }
      }
      return api.set(FALLBACK);
    },

    /* group(name) — the A/B/C family a theme belongs to, or null. Exposed because
     * "which designs are variants of one another" is a claim the picker renders
     * and an oracle should be able to check without reading the buttons. */
    group: function (name) {
      var t = known(name || currentTheme());
      return t && t.group ? t.group : null;
    },

    /** variant(name) — 'A' | 'B' | 'C' | null. */
    variant: function (name) {
      var t = known(name || currentTheme());
      return t && t.variant ? t.variant : null;
    },

    /* mount() — idempotent. Wires the header button (the host's or our own) and
     * the picker, then re-applies the stored choice. Called once at load and
     * again if the harness injects a button later; a second call must not
     * duplicate a listener or a picker, which is what `wired` guards. */
    mount: function () {
      var doc = root.document;
      if (!doc || !doc.body) return false;
      var btn = ensureButton(doc);
      var all = buttons(doc);
      all.forEach(function (b) {
        if (b.dataset.wired) return;
        b.dataset.wired = 'true';
        wireButton(b);
      });
      syncPicker();
      return Boolean(btn) || all.length > 0;
    },

    /* last() — the stored choice, or null. Exposed because "which theme comes
     * back after a restart" is a claim that has to be checkable. */
    last: function () {
      return readStore();
    }
  };

  if (root) {
    root.SottoTheme = api;

    if (root.document) {
      var apply = function () {
        /* The stored choice is applied BEFORE first paint (`script-src 'self'`
         * scripts in <head> run before the body exists), so the panel never
         * paints one theme and then flips to another. */
        var stored = readStore();
        api.set(known(stored) ? stored : FALLBACK, { persist: false });

        var boot = function () {
          api.mount();
          /* Dismissing the picker: a click outside it, Escape, or focus leaving
           * the header. No caption element is ever a target of these listeners. */
          root.document.addEventListener('click', function (ev) {
            if (!picker || picker.hidden) return;
            if (picker.contains(ev.target)) return;
            var b = root.document.getElementById('theme-button');
            if (b && b.contains(ev.target)) return;
            closePicker();
          });
          root.document.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') closePicker();
          });
        };

        if (root.document.readyState === 'loading') {
          root.document.addEventListener('DOMContentLoaded', boot);
        } else {
          boot();
        }
      };
      apply();
    }
  }

  /* Usable from Node for `node --check` and for a unit oracle. */
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : null));
