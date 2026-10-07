/* Sotto — the theme MANIFEST.
 *
 * WHY THIS IS A SCRIPT AND NOT A JSON FILE, AND WHY IT IS NOT `fetch`ed:
 * the panel runs over `file://`, and `fetch()` of a `file://` URL is refused by
 * Chromium. It is ALSO refused without a network round trip under the panel's
 * own CSP (`default-src 'none'`). A `<script src="themes/themes.js">` is allowed
 * by `script-src 'self'`, loads synchronously in document order, and gives
 * `theme-switcher.js` the list before any theme has to exist. So the manifest is
 * ONE plain object literal, readable by a human and by a script, and the
 * switcher has no I/O at all.
 *
 * THE FIVE NAMES ARE THE OWNER'S FIVE DESIGN DIRECTIONS, in his own order, and
 * each entry is the direction's own accent from
 * `H:\aireplay\docs\design\sotto-app-design-directions\src\data\designs.ts`:
 *
 *   1 Teleprompter  tele   #f2e9d8  Barlow Condensed
 *   2 Broadcast     bcast  #ff6a55  IBM Plex Mono
 *   3 Manuscrito    mano   #a9c1d9  Newsreader
 *   4 Cinema Card   cine   #e4b363  Fraunces
 *   5 Instrumento   inst   #5fd3a7  Space Grotesk
 *
 * `name` is the id in `document.documentElement.dataset.theme`, i.e. the
 * `theme-N` of `themes/theme-N.css` and the value every rule in those files is
 * scoped to. `label` is what the in-panel button and the picker show, and it is
 * the DIRECTION's name — a theme is a design here, not a colour scheme, and the
 * owner has to be able to read which direction he is looking at. `swatch` must
 * equal that theme's `--accent`, or the dot on the button lies about the theme
 * it is offering; the five accents above are what `gen_themes.py` writes into
 * those files, and `_main/_theme-probe-arm.py` checks the two agree — per theme,
 * against the direction's own accent in `designs.ts` (the manifest is read out of
 * the live document and compared with `EXPECTED`, so a swatch that drifts from
 * its theme goes RED). (This comment used to name `_main/_theme-styles-oracle.js`,
 * which does not exist — the check lives in the probe.)
 */
(function (root) {
  'use strict';

  var THEMES = [
    {
      name: 'theme-1',
      label: 'Teleprompter',
      file: 'themes/theme-1.css',
      swatch: '#f2e9d8'
    },
    {
      name: 'theme-2',
      label: 'Broadcast',
      file: 'themes/theme-2.css',
      swatch: '#ff6a55'
    },
    {
      name: 'theme-3',
      label: 'Manuscrito',
      file: 'themes/theme-3.css',
      swatch: '#a9c1d9'
    },
    {
      name: 'theme-4',
      label: 'Cinema Card',
      file: 'themes/theme-4.css',
      swatch: '#e4b363'
    },
    {
      name: 'theme-5',
      label: 'Instrumento',
      file: 'themes/theme-5.css',
      swatch: '#5fd3a7'
    }
  ];

  var api = {
    themes: THEMES,
    /* The theme a document wears before anybody has chosen one. It is spelled
     * out here so `theme-switcher.js` and the harness cannot disagree about it. */
    fallback: 'theme-1',
    byName: function (name) {
      for (var i = 0; i < THEMES.length; i += 1) {
        if (THEMES[i].name === name) return THEMES[i];
      }
      return null;
    }
  };

  if (root) root.SottoThemeManifest = api;
  /* Also usable from Node (`node --check`, a manifest oracle), where there is no
   * `window` to hang it on. */
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : null));
