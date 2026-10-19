#!/usr/bin/env python3
"""O QUE O PAINEL PINTA DE VERDADE, depois de todo o JS ter corrido.

PORQUÊ ESTE INSTRUMENTO EXISTE. Uma captura mostra um ponto ao lado da
engrenagem e um ao lado do nome do tema. Nenhum dos dois esta em `panel.html`:
sao criados em RUNTIME por `theme-switcher.js` / `theme-tune.js` / `panel.js`.
Uma imagem responde "parece estranho"; so o DOM depois do boot responde
"que elemento e, com que classe, e quem o criou".

A QUE NAO RESPONDE -- E O QUE ESTA MEDICAO JA CUSTOU.

  * Nao responde ONDE esta o cluster de controlos no ecra do dono. O headless
    Edge prende o LAYOUT viewport a 492 px, em `--screenshot` E em `--dump-dom`
    (medido 2026-10-18: `--headless=new` e `--headless=old` devolvem PNGs
    byte-identicos de 62 570 B com a mesma entrada). O docstring do `shot.py`
    dizia que o clamp nao se aplicava ao `--screenshot` e esta retractado.

  * `--force-width` (esta opcao) e uma SOLUCAO PARCIAL e esta anotada como tal:
    ela põe `html`/`body` a N px e faz de `body` o containing block, e o painel
    e o header ENCOLHEM de facto (medido: body 492 -> 380, header 464 -> 352).
    Mas o cluster manteve a geometria de 492 — `.panel__controls` mediu
    `width: 250px` com a borda direita em 478 com o painel a 380, que e 492 - 14.
    Uma primeira leva de corridas afirmou as duas coisas ao mesmo tempo: "header
    clientWidth 352, scrollWidth 352, sem overflow" E "tres controlos 34 a 98 px
    fora da borda". Isso nao pode ser verdade ao mesmo tempo, e o `--dump-dom`
    contra a janela WebView2 REAL mediu depois `past_by=0` para os seis.

    REGRA. Este instrumento responde "o que o painel CONSTROI depois de todos os
    modulos correrem, e que elemento e cada coisa" — identidade, classe, caixa,
    visibilidade. Nao responde "onde esta o botao no ecra do dono", e um numero
    de geometria impresso sob `--force-width` descreve um hibrido que ninguem ve.
    Para a posicao, `sotto_webview.py --dump-dom` — e nao precisa de remedia.

O QUE ELE FAZ. Reusa `_main/_design-lane/shot.py::build` -- a MESMA copia do
painel real com a MESMA instrumentacao de legenda, porque uma foto de outra
copia nao provaria nada. Depois acrescenta UM script que, 600 ms depois do
DOMContentLoaded (tempo suficiente para theme-switcher/theme-tune/panel.js
terem montado), serializa a arvore de `.panel__header` e escreve o JSON num
`<pre id="RUNTIME">`. `--dump-dom` imprime isso.

O QUE ELE NAO E. Nao abre janela nenhuma (headless Edge desenha nada) e nao
laca a app. Custo: um arranque de Chromium, ~3 s.

    py -3 _main\\panel-runtime-dom.py [--theme theme-1] [--surface panel]
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, 'H:/sotto/_main/_design-lane')
import shot  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

PROBE_JS = r'''/* AN EXTERNAL FILE, NOT AN INLINE BLOCK, AND THAT IS THE WHOLE FIRST BUG.

       `panel.html:22-25` declares
         default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'
       with NO 'unsafe-inline' on `script-src`, so an inline <script> is BLOCKED.
       The first three runs injected one and read `NO-RUNTIME-PAYLOAD` every
       time, with a byte-identical 87 898-byte DOM: the probe never ran, and a
       blocked script prints nothing on screen and nothing in the dump. The
       file itself already carries the lesson (`panel.html:1190-1194`): an inline
       strip-drag "NEVER RAN" for the same reason.

       This is now written to `_rtprobe.js` beside the panel and loaded with a
       src, which is what `shot.py` does with `_shot.js`. */

var RTOUT = { ok: false, stage: 'entered', error: null };
(function () {
  'use strict';
  var M1 = '@@RUNT' + 'IME@@';
  var M2 = '@@E' + 'ND@@';
  function emit(text) {
    var pre = document.createElement('pre');
    pre.id = 'RUNTIME';
    pre.textContent = M1 + text + M2;
    document.body.appendChild(pre);
  }
  function b64(s) {
    var bytes = new TextEncoder().encode(s);
    var bin = '';
    for (var k = 0; k < bytes.length; k += 1) bin += String.fromCharCode(bytes[k]);
    return btoa(bin);
  }

  /* THE 492 px CLAMP, AND WHY THIS FILE HAS TO FORCE THE WIDTH.
   `shot.py`'s own docstring (:42-46) records it: headless Edge clamps the
   LAYOUT viewport to 492 px, measured with --dump-dom, and --screenshot is
   exempt (that is how the 380x900 PNGs are real). The first geometry run
   through this instrument therefore measured a 492 px panel and printed
   `past_by=0` on every control -- true, and true for a panel the owner does
   not have. Reading it as "the controls fit" would have been a fact about the
   instrument.

   So the width is FORCED, with the same number the shell uses
   (`PANEL_WIDTH = 380`, shot.py:115 / sotto_webview.py). The app's own layout
   is a width-driven one -- the generated themes size the live line in vw --
   so a clamped viewport is not a slightly different measurement, it is a
   different panel. */
  var FW = __FORCE_WIDTH__;
  if (FW > 0) {
    var st = document.createElement('style');
    /* `body` MUST BECOME THE CONTAINING BLOCK. `panel.css:150-152` is
       `.panel { position: absolute; inset: 0 }` with no positioned ancestor,
       so its containing block is the INITIAL CONTAINING BLOCK -- the viewport
       the clamp holds at 492. Setting `html{width:380px}` alone changed
       nothing at all (measured: panel still [0,0,492,808]) because the panel
       never asked the document for its width. `body{position:relative}` is
       what actually moves the slab to 380. Widths INSIDE the panel are then
       the app's own 380-wide layout, which is the number being asked for. */
    st.textContent =
      'html{width:' + FW + 'px !important;}' +
      'body{width:' + FW + 'px !important; position:relative !important;' +
      ' min-width:0 !important;}';
    document.head.appendChild(st);
  }

  function clsOf(e) {
    if (!e) return null;
    if (e.className && e.className.baseVal !== undefined) return e.className.baseVal;
    return typeof e.className === 'string' ? (e.className.trim() || null) : null;
  }

  function go() {
    try {
      var out = {};
      var hdr = document.querySelector('.panel__header');
      if (hdr) {
        /* EVERY descendant with a non-zero box: the dots the owner is asking
           about are grandchildren, and a `.panel__controls > *` selector would
           miss them entirely. */
        var deep = [];
        var all = hdr.querySelectorAll('*');
        for (var i = 0; i < all.length; i += 1) {
          var e = all[i];
          var r = e.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) continue;
          var c = clsOf(e) || '';
          var cs = getComputedStyle(e);
          deep.push({
            path: e.tagName.toLowerCase() +
                  (e.id ? '#' + e.id : '') +
                  (c ? '.' + c.split(/\s+/).join('.') : ''),
            text: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30),
            box: [Math.round(r.left * 10) / 10, Math.round(r.top * 10) / 10,
                  Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10],
            /* WHY IT IS VISIBLE AT ALL. An element with a box and opacity 0 or
               visibility hidden still occupies space and still shows up in a
               screenshot as nothing -- so "it has a box" is not "the owner can
               see it". These three say which. */
            vis: cs.visibility + '/' + cs.opacity + '/' + cs.display,
            bg: cs.backgroundColor,
            radius: cs.borderTopLeftRadius
          });
        }
        out.headerAll = deep;
      } else {
        out.headerAll = 'NO-.panel__header';
      }

      /* THE OVERFLOW QUESTION, WITH THE PANEL'S OWN NUMBERS. The element boxes
         above are in viewport pixels, so the only thing that decides whether a
         control is reachable is the panel's own client width next to them.
         "It has a box" is not "the owner can click it". */
      var panel = document.querySelector('main.panel');
      var hdrBox = hdr ? hdr.getBoundingClientRect() : null;
      var ctl = document.querySelector('.panel__controls');
      out.geom = {
        viewport: [document.documentElement.clientWidth,
                   document.documentElement.clientHeight],
        /* THE THREE NUMBERS THAT DISAGREE MUST ALL BE VISIBLE. A first run said
           `header.clientWidth 352 / scrollWidth 352` (no overflow) while the
           controls' right edge sat at 478 -- 98px past a 380 panel, and exactly
           492 - 14, i.e. the geometry of the 492px layout. Either the header
           really is 352 wide and its flex children are positioned off a 464
           track, or nothing moved. `offsetWidth` and the COMPUTED width say
           which, and so does running the same probe with no forced width. */
        bodyW: [document.body.clientWidth, document.body.offsetWidth,
                getComputedStyle(document.body).width],
        panelLayout: (function () {
          var p = document.querySelector('main.panel');
          var cs = getComputedStyle(p);
          var grid = cs.gridTemplateColumns;
          var tracks = [];
          for (var t = 0; t < p.children.length; t += 1) {
            tracks.push({
              tag: p.children[t].tagName.toLowerCase(),
              id: p.children[t].id || null,
              cls: clsOf(p.children[t]),
              offW: p.children[t].offsetWidth,
              clientW: p.children[t].clientWidth,
              scrollW: p.children[t].scrollWidth,
              left: Math.round(p.children[t].getBoundingClientRect().left),
              right: Math.round(p.children[t].getBoundingClientRect().right),
              computed: getComputedStyle(p.children[t]).width
            });
          }
          return {
            position: cs.position,
            computedWidth: cs.width,
            gridTemplateColumns: grid,
            tracks: tracks
          };
        })(),
        headerInner: (function () {
          if (!hdr) return null;
          var cs = getComputedStyle(hdr);
          return {
            offsetW: hdr.offsetWidth,
            clientW: hdr.clientWidth,
            scrollW: hdr.scrollWidth,
            computed: cs.width,
            justify: cs.justifyContent,
            display: cs.display,
            /* THE RESOLVED TRACKS. `gen_themes.py:1901-1904` replaces the flex
               header with `display:grid; grid-template-columns: 1fr auto`, and
               `:1947-1952` drops the cluster into column 2 with
               `justify-self:end`. In that template a `1fr` track has an AUTOMATIC
               minimum, so the row cannot get narrower than its content unless
               something is allowed to shrink -- which is the whole question, and
               the browser's own resolved track widths answer it in one line
               where the arithmetic from the source did not. */
            gridTemplateColumns: cs.gridTemplateColumns,
            gridColumnGap: cs.columnGap,
            /* And what each of the row's children resolved to. */
            row: (function () {
              var r = [];
              var kids = hdr.children;
              for (var i = 0; i < kids.length; i += 1) {
                var k = kids[i];
                var kb = k.getBoundingClientRect();
                var kcs = getComputedStyle(k);
                r.push({
                  tag: k.tagName.toLowerCase(),
                  id: k.id || null,
                  cls: clsOf(k),
                  gridColumn: kcs.gridColumnStart + '/' + kcs.gridColumnEnd,
                  justifySelf: kcs.justifySelf,
                  flex: kcs.flex,
                  minWidth: kcs.minWidth,
                  width: kcs.width,
                  box: [Math.round(kb.left), Math.round(kb.width)],
                  right: Math.round(kb.right)
                });
              }
              return r;
            })()
          };
        })(),
        panel: panel ? {
          rect: [Math.round(panel.getBoundingClientRect().left),
                 Math.round(panel.getBoundingClientRect().top),
                 Math.round(panel.getBoundingClientRect().width),
                 Math.round(panel.getBoundingClientRect().height)],
          clientW: panel.clientWidth,
          scrollW: panel.scrollWidth,
          overflowX: panel.scrollWidth > panel.clientWidth
        } : 'NO-main.panel',
        header: hdrBox ? {
          rect: [Math.round(hdrBox.left), Math.round(hdrBox.top),
                 Math.round(hdrBox.width), Math.round(hdrBox.height)],
          clientW: hdr.clientWidth,
          scrollW: hdr.scrollWidth,
          overflowX: hdr.scrollWidth > hdr.clientWidth
        } : null,
        controls: ctl ? {
          rect: [Math.round(ctl.getBoundingClientRect().left),
                 Math.round(ctl.getBoundingClientRect().top),
                 Math.round(ctl.getBoundingClientRect().width),
                 Math.round(ctl.getBoundingClientRect().height)],
          scrollW: ctl.scrollWidth,
          clientW: ctl.clientWidth
        } : null,
        /* EVERY control's right edge against the panel's own right edge: the
           honest form of "is this button reachable", one number per button. */
        controlsPastEdge: (function () {
          var outp = [];
          var right = panel ? panel.getBoundingClientRect().right : 0;
          var btns = document.querySelectorAll(
            '.panel__controls button, .panel__controls a');
          for (var m = 0; m < btns.length; m += 1) {
            var b = btns[m].getBoundingClientRect();
            outp.push({
              id: btns[m].id || btns[m].className,
              right: Math.round(b.right),
              past_by: Math.round(Math.max(0, b.right - right)),
              onscreen: b.right <= right + 0.5 && b.left >= -0.5
            });
          }
          return outp;
        })()
      };
      var pops = [];
      var kids = document.body.children;
      for (var j = 0; j < kids.length; j += 1) {
        var b = kids[j];
        pops.push({
          tag: b.tagName.toLowerCase(),
          id: b.id || null,
          cls: clsOf(b),
          text: (b.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)
        });
      }
      out.bodyChildren = pops;
      emit(b64(JSON.stringify(out)));
    } catch (err) {
      emit(b64(JSON.stringify({ ok: false, stage: 'threw',
                                 error: String(err) })));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(go, 600); });
  } else {
    setTimeout(go, 600);
  }
})();
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--theme', default='theme-1')
    ap.add_argument('--surface', default='panel')
    ap.add_argument('--width', type=int, default=380,
                    help='force the layout width; --dump-dom clamps it to 492')
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix='rtedom-')
    html_path = shot.build(args.theme, args.surface, work)

    # THE PROBE IS A FILE. `script-src 'self'` refuses an inline block, so this
    # is a sibling of _shot.js, loaded the same way -- and it is written AFTER
    # build() has copied the panel in, because build() overwrites anything it
    # puts in the workdir.
    probe = PROBE_JS.replace('__FORCE_WIDTH__', str(int(args.width)))
    with open(os.path.join(work, '_rtprobe.js'), 'w', encoding='utf-8',
              newline='\n') as fh:
        fh.write(probe)

    with open(html_path, encoding='utf-8') as fh:
        html = fh.read()
    html = html.replace('</body>',
                        '    <script src="_rtprobe.js"></script>\n</body>', 1)
    with open(html_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)

    # SAY WHAT WAS WRITTEN, BEFORE SPENDING A CHROMIUM ON IT. "the payload was
    # missing" is one sentence; "the payload was missing because the template
    # never reached the file" is the sentence that saves the next ten minutes.
    with open(html_path, encoding='utf-8') as fh:
        check = fh.read()
    print('INJECTION bytes=%d probe_src=%s probe_file=%s'
          % (len(check), '_rtprobe.js' in check,
             os.path.isfile(os.path.join(work, '_rtprobe.js'))))

    url = 'file:///' + html_path.replace(os.sep, '/') + '#' + args.surface
    # --virtual-time-budget IS the clock, and --dump-dom reads whatever the DOM
    # is WHEN the budget expires. The first two runs used 4000 and produced no
    # payload at all: the dump is written at load, before the probe's 600 ms
    # timer has fired. 20000 is the same number the app's own panel probe uses,
    # and the page is a file:// document, so virtual time costs no real seconds.
    budget = int(os.environ.get('SOTTO_RT_BUDGET', '20000'))
    # A PROFILE OF ITS OWN, EVERY RUN. Without it the two first runs returned
    # 87898 DOM bytes EACH AND IDENTICAL, and raising the budget changed
    # nothing: a browser was already running under the default profile, the new
    # command was handed to it, and --headless/--dump-dom on the command line
    # were never this process's arguments. Two runs that agree byte for byte
    # across a changed input is the shape of an answer that is not about the
    # question. A fresh --user-data-dir makes this process the browser, so the
    # flags in `cmd` are the flags that ran.
    profile = os.path.join(work, '_edgeprofile')
    cmd = [shot.EDGE, '--headless=new', '--disable-gpu', '--no-first-run',
           '--no-default-browser-check', '--user-data-dir=%s' % profile,
           '--virtual-time-budget=%d' % budget,
           '--window-size=380,900', '--dump-dom', url]
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    dom = (proc.stdout or b'').decode('utf-8', 'replace')

    # TAKE THE LAST ONE. The probe emits a stage line at parse time AND a final
    # line when it finishes, so there are legitimately several payloads in one
    # dump; the reader keeps the last, which is the one that ran to completion.
    marks = re.findall(r'@@RUNTIME@@(.*?)@@END@@', dom, re.S)
    if not marks:
        print('NO-RUNTIME-PAYLOAD rc=%s bytes=%d' % (proc.returncode, len(dom)))
        print((proc.stderr or b'').decode('utf-8', 'replace')[:400])
        return 2

    payload = base64.b64decode(marks[-1]).decode('utf-8')
    data = json.loads(payload)

    print('THEME %s SURFACE %s' % (args.theme, args.surface))
    if 'header' in data:
        print('HEADER  %s' % json.dumps(data['header'], ensure_ascii=False))
    print('--- every element with a non-zero box inside .panel__header ---')
    for e in data.get('headerAll', []):
        print('  %-46s box=%-28s text=%s'
              % (e['path'], e['box'], json.dumps(e['text'], ensure_ascii=False)))
    print('--- direct children of <body> (the popups modules create) ---')
    for b in data.get('bodyChildren', []):
        print('  %-34s cls=%-28s text=%s'
              % (b['tag'] + (('#' + b['id']) if b['id'] else ''),
                 json.dumps(b['cls'], ensure_ascii=False),
                 json.dumps(b['text'], ensure_ascii=False)))

    g = data.get('geom') or {}
    print('--- GEOMETRY (viewport px; the panel is %s wide) ---' % g.get('viewport'))
    print('  bodyW        %s' % json.dumps(g.get('bodyW')))
    print('  headerInner  %s' % json.dumps(g.get('headerInner'), ensure_ascii=False))
    pl = g.get('panelLayout') or {}
    print('  panel        position=%s computed=%s grid=%s'
          % (pl.get('position'), pl.get('computedWidth'),
             pl.get('gridTemplateColumns')))
    for t in pl.get('tracks', []):
        print('    %-30s offW=%-6s clientW=%-6s scrollW=%-6s computed=%-8s [%s..%s]'
              % ('%s%s cls=%s' % (t['tag'],
                                  ('#' + t['id']) if t['id'] else '',
                                  json.dumps(t['cls'], ensure_ascii=False)),
                 t['offW'], t['clientW'], t['scrollW'], t['computed'],
                 t['left'], t['right']))
    for key in ('panel', 'header', 'controls'):
        print('  %-9s %s' % (key, json.dumps(g.get(key), ensure_ascii=False)))
    print('--- every control in .panel__controls, against the panel right edge ---')
    for c in g.get('controlsPastEdge', []):
        print('  %-28s right=%-6s past_by=%-5s onscreen=%s'
              % (c['id'], c['right'], c['past_by'], c['onscreen']))
    return 0


if __name__ == '__main__':
    sys.exit(main())