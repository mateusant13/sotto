/* zipc-panels.js -- the manifest FRAGMENT for the third zip.
 *
 * THE TEN PANEL DESIGNS of `cinematic-transcription-app-designs (1).zip`, pushed
 * into `SottoThemeManifest.themes` after `themes.js` and `panel-designs.js` have
 * had their say, so the three sets can never collide on a name.
 *
 * WHY A FRAGMENT AND NOT A THEME: `themes.js` carries the five designs of the first
 * zip and `panel-designs.js` the five of the second; this is the third set, with its
 * own stylesheet and its own names, loaded by `app/panel/panel.html` in two lines:
 *   <link rel="stylesheet" href="themes/zipc-panels.css" />   (in <head>)
 *   <script src="themes/zipc-panels.js"></script>              (after panel-designs.js)
 *
 * The swatch of each entry IS that design's own accent token in the stylesheet.
 */
(function (root) {
  'use strict';
  var fragment = [
    {
      name: 'GlassCards',
      label: 'Glass Cards · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#E9A85B',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Hairline',
      label: 'Hairline · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#9FC4D8',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Paper',
      label: 'Paper · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#C4562F',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Quotes',
      label: 'Quotes · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#E8C69B',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Ledger',
      label: 'Ledger · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#D8B060',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Feed',
      label: 'Feed · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#8B93F2',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Bubbles',
      label: 'Bubbles · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#D8A7E8',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Timeline',
      label: 'Timeline · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#BED6DC',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Chips',
      label: 'Chips · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#FFC496',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
    {
      name: 'Gutter',
      label: 'Gutter · painel',
      file: 'themes/zipc-panels.css',
      swatch: '#4A6B74',
      group: 'zipc-panels',
      groupLabel: 'Painéis (3.º zip)'
    },
  ];
  var manifest = root.SottoThemeManifest;
  if (!manifest || !Array.isArray(manifest.themes)) return;
  for (var i = 0; i < fragment.length; i += 1) manifest.themes.push(fragment[i]);
}(window));
