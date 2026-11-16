'use strict';

/* O MARCO DO ARRANQUE, publicado pela PAGINA (2026-11-10). O medidor da shell
 * (`BOOT_PROFILE_JS`) expoe `window.__sottoBootMark`; declarado com `typeof`, um
 * harness sem medidor nao ganha um erro por causa de um marco.
 * PORQUE: no log do dono os 32 `PANEL_BOOT_PROFILE` trazem `longtasks: []` e
 * `slowest: []` AO MESMO TEMPO -- os dois campos nao entregam nada neste
 * contexto --, e `marks` foi de 29 ms (`early`) a 472 ms (`dom`) sem nomear o
 * bloco do meio. Um marco por etapa nomeia-o entre dois numeros. */
const bootMark = (typeof window.__sottoBootMark === 'function')
  ? window.__sottoBootMark
  : function () {};
bootMark('panel-js');

/**
 * Sotto — the panel renderer (v3: the live box is the product).
 *
 * TOP      header      the wordmark and the two controls (pause, hide), hide
 *                      LAST so it sits rightmost — the owner's 2026-10-08 ruling,
 *                      satisfied by document order in `panel.html` because this
 *                      module never re-parents them (lookups only: `:69` by id,
 *                      `:93`/`:1505`/`:1652` by `[data-pause-trigger]`).
 * THEN     `#history`  the canonical transcript: a feed read back from disk.
 *                      SECONDARY. With no canonical (batch) producer it stays
 *                      COLLAPSED to one bar (label, folder path, one honest
 *                      note, a chevron) and gives the height back to the live
 *                      box; it opens by itself the day `history.root()` reports
 *                      a producer. Its search is disabled while nothing can
 *                      write it — see `applyTranscriptMode`.
 * THEN     `#captions` the LIVE caption box: the streaming caption growing line
 *                      by line. THE PRODUCT, and the only flexible row in the
 *                      grid — it takes the panel's free height. It is BELOW the
 *                      transcript because the owner ruled so, verbatim
 *                      (2026-10-08): *"a legenda ao vivo, no painel, tem que
 *                      ficar embaixo do painel. o historico a cima"*. The DOM
 *                      order and `panel.css`'s `grid-template-rows` are ONE
 *                      decision: the `1fr` is assigned in document order.
 * BOTTOM   `.status`   the status line, up to two lines so the cause is not the
 *                      part that gets cut.
 *
 * The renderer owns the DOM and nothing else. Two things come from outside:
 *   * captions, through `window.sotto.onCaption` (the preload/WebView2 bridge);
 *   * the transcript store, through `window.sotto.history` (append/tail/search/
 *     reveal/root) — implemented by whichever shell is hosting the page.
 *
 * The history API is probed, never assumed: an older shell without it degrades
 * to a working live box and an explicit "transcript unavailable" note, instead
 * of a renderer that throws on load. Every element this file reaches for is
 * null-checked, for the same reason: `_main/_audit-render/panel-harness.html`
 * loads THIS file against an older copy of the markup.
 */

/**
 * Cap on rendered LIVE lines, matching MAX_CAPTIONS in the shell.
 *
 * MEDIDO a 2026-11-05 (recibo `_main/receipt-20261105-right-panel-history.md`):
 * com 200 o painel retinha **7 min 37 s** -- o dono enche a janela em ~7
 * minutos e cada linha nova passa a apagar a mais antiga da tela. A janela sobe
 * para 1200 porque o custo e' um `<li>` de ~100 B (1200 linhas = ~120 KB de
 * DOM, lixo para um WebView2) e o beneficio e' a transcricao dele durar mais de
 * meia hora em vez de evapora-la enquanto ele le'.
 */
const MAX_CAPTIONS = 1200;
/** Cap on history entries held in the feed (newest kept). */
const MAX_HISTORY = 500;
/** How many entries a fresh `tail()` loads. */
const HISTORY_LOAD = 400;
/**
 * HOW FAR BACK THE FEED GOES.
 *
 * A JANELA E' A DO BACKEND (2026-11-09). Era 48 h pela ordem de 2026-11-06
 * (*"ate 48hrs. nao faça isso ser travado ou pesado."*); o recall de MESES veio
 * depois, `sotto_webview.HISTORY_RETENTION_H` passou a 4320 h (180 dias) e o
 * filtro daqui ficou em 48 -- escondendo 178 dias que o disco tem. Um numero so'.
 * Continua a ser FILTRO sobre a cauda ja' devolvida, sem segunda leitura.
 */
const HISTORY_RETENTION_H = 4320;
/**
 * THE TRANSCRIPT FONT DIAL — its bounds and its storage key (owner, 2026-10-09).
 * The scale is a multiplier around the CSS DESIGN size (`--caption-size`, 15px),
 * never an absolute size, because the owner asked for a dial rather than a fixed
 * size. STEP is one click; the range is wide enough to be useful on a 4K panel and
 * narrow enough that the strip's ~100 px row still holds its caption at the top
 * end. The value is a STRING in localStorage so a half-written number can never
 * be read as a scale.
 */
const FONT_SCALE_MIN = 0.8;
const FONT_SCALE_MAX = 2.0;
const FONT_SCALE_STEP = 0.1;
const FONT_SCALE_DEFAULT = 1;
const FONT_SCALE_KEY = 'sotto:caption-scale';
/**
 * THE STRIP'S HEIGHT — AND WHY THERE IS ONLY ONE, 2026-10-17.
 *
 * Until this morning there were TWO constants here, `STRIP_HEIGHT = '40px'` and
 * `FLOAT_HEIGHT = '220px'`, and `applyFloat` picked between them. The second one
 * is GONE, and it is gone because of what the log measured when the owner
 * clicked the caption button (`_main/webview-run.log`, 2026-10-17):
 *
 *   21:40:12.621 STRIP_HEIGHT from=40 to=220 source=css css_value=220 reason=surface-strip-float-on
 *   21:40:12.638 PANEL_SURFACE surface=strip reason=strip-float-on window=380x220@(770,768)
 *
 * One click grew the owner's panel from 380x40 to 380x220 — +180 px of empty box.
 * His words, verbatim: *"ao clicar no botao de legenda, nao deve abrir qualquer
 * coisa. e pra ativar a legenda, na minha tela, sem background, sem estar
 * conectada a qualquer painel. ela e livre na minha tela, um overlay"*. The
 * 220 px window WAS the thing that opened, so the constant that produced it is
 * deleted instead of being re-tuned: there is no height to grow to.
 *
 * `--strip-height` still EXISTS and is still the shell's source of truth — it is
 * read out of the stylesheet (`sotto_webview.py:7970`, `reason=surface-*`,
 * `source=css`) — it is just no longer written from here. The owner's reference
 * is a short, simple bar: that is the `float-off` state the log already shows as
 * `window=380x40@(770,948)`.
 */
const STRIP_HEIGHT = '40px';
const dom = {
  panel: document.getElementById('panel'),
  // live caption box
  captions: document.getElementById('captions-body'),
  placeholder: document.getElementById('placeholder'),
  list: document.getElementById('caption-list'),
  captionsHint: document.getElementById('captions-hint'),
  statsChip: document.getElementById('stats-chip'),
  // transcript feed
  transcript: document.getElementById('history'),
  /* THE DRAWER HANDLE IS GONE (owner, 2026-10-14: *"tira o botao de transcript…
     remove o CONTROLO"*): `#history-toggle` was deleted from the markup, so this
     lookup went with it. The drawer is always open; the FOLDER button
     (`#history-root`, below) still opens the place the data lives. */
  transcriptNote: document.getElementById('transcript-note'),
  transcriptCount: document.getElementById('history-count'),
  historyList: document.getElementById('history-list'),
  historyRoot: document.getElementById('history-root'),
  historyStatus: document.getElementById('history-status'),
  revealButton: document.getElementById('reveal-button'),
  // THE SEARCH BOX IS GONE (owner, 2026-10-21 21:24: *"tira a caixa de procurar
  // texto"*), so these four lookups went with it. Every use of them below was
  // already null-guarded, which is why deleting the nodes left the panel working --
  // and why the guards stay: they are what made the removal safe.
  // footer
  status: document.getElementById('status'),
  statusText: document.getElementById('status-text'),
  statusDot: document.getElementById('status-dot'),
  hideButton: document.getElementById('hide-button'),
  // `quitButton` and `clearButton` were here and are gone with their controls (the
  // owner removed both from `panel.html`). The KEYS went too, not just the markup:
  // `dom.clearButton.addEventListener` was unguarded, so a markup-only removal threw
  // at wire time — and a `null` entry kept here would reproduce that throw for the
  // next reader. What the removals cost is recorded at both sites in `panel.html`
  // and in `_main/receipt-panel-stale-oracles.md` §11.
  // the strip surface's control row (`panel.html` `.stripbar`) — `null` on a
  // shell or an older harness that does not ship it, because every handler below
  // null-checks: `_main/_audit-render/panel-harness.html` loads THIS file against
  // markup that may be older than it.
  stripControls: document.getElementById('strip-controls'),
  stripLiveButton: document.getElementById('strip-live-button'),
  /* THE LIVE-CAPTION LAMP (owner, 2026-10-19). TWO COPIES, ONE FACT: the panel
     surface's (inside `.panel__controls`, the far end from the pause button) and the
     strip's (beside the LIVE switch). `paintLiveLamps` paints BOTH from the
     shell's own account of the live caption. */
  liveLamp: document.getElementById('live-lamp'),
  stripLiveLamp: document.getElementById('strip-live-lamp'),
  stripLiveLabel: document.getElementById('strip-live-label'),
  stripPauseButtons: document.querySelectorAll('[data-pause-trigger]'),
  stripState: document.getElementById('strip-state'),
  stripWord: document.getElementById('strip-word'),
  stripOpenButton: document.getElementById('strip-open-button'),
  stripHideButton: document.getElementById('strip-hide-button'),
  // REMOVED 2026-10-12: `stripTransparencyButton`. The transparency button is GONE from
  // panel.html (it was the reported bug — see the comment there and in panel.css), so
  // the key is gone with it, on the file's own rule that a `null` entry would
  // reintroduce a throw at wire time. `applyTransparency` is kept (below), now
  // unreachable from the UI and harmless if a stale caller still invokes it.
  // REMOVED 2026-10-13: `stripFloatButton`. The separate "Linhar" button is gone
  // from panel.html — the owner's prompts of the handoff conversation put the
  // caption on the LIVE toggle (*"o botao de mostrar a legenda ao vivo deve ser o
  // 'live'"*, *"nele eu ativo o segundo overlay, q e a legenda independente"*), so
  // the key goes with the markup, on this file's own rule that a `null` entry is a
  // throw waiting for the next reader. `applyFloat` still owns the overlay and
  // `applyLiveEnabled` is now its only caller.
  // the transcript font dial (owner, 2026-10-09; ONE button each since
  // 2026-10-18, *"1 botao de tamanho em vez de 2"*). TWO buttons, ONE number:
  // one on the panel (`#font-scale-button`) and one on the strip
  // (`#strip-font-scale-button`), both cycling the same `--caption-scale`, so the two
  // surfaces cannot disagree. `null` on an older harness, and every handler
  // below null-checks — the same contract the strip keys above carry.
  fontScaleButton: document.getElementById('font-scale-button'),
  stripFontScaleButton: document.getElementById('strip-font-scale-button'),
  // the pause confirmation (`panel.html`, outside `.panel` so the slab's own
  // `overflow: hidden` cannot clip its backdrop)
  pauseDialog: document.getElementById('pause-dialog'),
  pauseConfirmButton: document.getElementById('pause-confirm-button'),
  pauseCancelButton: document.getElementById('pause-cancel-button'),
  pauseShellNote: document.getElementById('pause-dialog-shell'),
  pauseButtons: document.querySelectorAll('[data-pause-trigger]'),
  panelPauseButton: document.getElementById('panel-pause-button'),
  // THE 3-DOT MENU (owner, 2026-10-21): the trigger, the popover, the translation
  // selector and the slot that carries the worker's cause.
  menuButton: document.getElementById('menu-button'),
  panelMenu: document.getElementById('panel-menu'),
  translationSelect: document.getElementById('translation-select'),
  captionPlateSelect: document.getElementById('caption-plate-select'),
  captionOpacityRange: document.getElementById('caption-opacity-range'),
  captionOpacityValue: document.getElementById('caption-opacity-value'),
  captionCaptureSelect: document.getElementById('caption-capture-exclude-select'),
  historyExport: document.getElementById('history-export-txt'),
  menuCause: document.getElementById('panel-menu-cause'),
};

const bridge = window.sotto;
/** The history store, or null when the hosting shell does not implement it. */
const historyApi = bridge && bridge.history ? bridge.history : null;

/**
 * When the pipeline started, so readiness can state the MEASURED warm-up
 * instead of implying the owner is looking at a sequence of failures.
 */
const pipelineStartedAt = Date.now();

// ---------------------------------------------------------------------------
// MODULE STATE THAT THE INIT BLOCK BELOW REACHES — DECLARED FIRST, ON PURPOSE
// ---------------------------------------------------------------------------
// MEASURED 2026-10-07, on the owner's screen with a video playing: the worker
// transcribed for 20+ seconds at peak 0.44, the shell logged thousands of
// `BRIDGE_CAPTION_SENT delivered=true`, and the panel stayed frozen on
// "Starting the worker" with `#caption-list` at `display:none`. The cause was
// ONE `let` in the wrong place:
//
//     panel.js:87   wireHistory()          <- runs at module init
//     panel.js:304  markRevealState()
//     panel.js:428  reads `selectedEntry`  <- `let` declared at :263, BELOW
//
// `let`/`const` are hoisted but NOT initialised, so reading one above its
// declaration is a ReferenceError (the temporal dead zone). The throw aborted
// the init block at its first statement — so `wireCaptions()`, `wireStatus()`,
// `wireStats()` and `wireControls()` NEVER RAN, on every launch, and the panel
// looked merely quiet instead of broken. Nothing in the shell's log could see
// it (Python only sees its own `evaluate_js` call, which succeeded); it took
// the `window.addEventListener('error')` hook added to the injected bridge the
// same day. The lesson is the ordering rule this block now enforces: any state
// an init call can touch is DECLARED ABOVE the init block.
//
// Every entry held in the feed, oldest first.
let historyEntries = [];
/**
 * THE TRANSCRIPT'S REFUSALS, COUNTED (2026-11-05). The choke point used to
 * `return` in silence, and that silence cost a day: 3830 captions were painted
 * and ZERO lines reached `history/`, with nothing in the log to say why. Every
 * refusal now names itself through `bridge.historyRefused` (the shell writes
 * `HISTORY_REFUSED`), counted PER SIGNATURE so a steady stream of the same
 * refusal logs on the first one and every 50th — an instrument, not a flood.
 * Declared here, above the init block, for the temporal-dead-zone rule.
 */
let historyRefusals = 0;
let historyRefusalSeen = new Map();
/** The entry currently selected (its file is what "Show in folder" opens). */
let selectedEntry = null;
/**
 * STICKY FOLLOW for the live box: true while the owner is watching the newest
 * line. Declared HERE (above the init block) because `followNewestLine` reads it
 * from the caption path — see the temporal-dead-zone note above.
 *
 * MEASURED 2026-10-07, the owner's words: *"a transcrição não tá dando auto
 * scroll no painel"*. The old rule was "scroll only if the box is ALREADY within
 * 48 px of the bottom" (`scrollHeight - scrollTop - clientHeight < 48`), which is
 * a rule that can never START: with `scrollTop = 0` and a list already taller
 * than the 288 px box, that expression is hundreds of pixels, so the panel showed
 * the OLDEST lines forever while the newest accumulated below the fold — the
 * captions looked like they had stopped arriving. The rule that works is the
 * chat-style one: follow by default, stop the moment the owner scrolls away from
 * the bottom, resume the moment he comes back.
 */
let stickToNewest = true, pinnedHeight = 0;
/** Non-empty while the feed is showing SEARCH RESULTS instead of the feed. */
let searchQuery = '';
/** The result set backing the current search view. */
let searchHits = [];
/**
 * THE SOURCE FILTER (owner, 2026-11-09). Every history line carries `via=pc`
 * (transcribed from the PC's own audio) or `via=youtube` (read off the YouTube
 * player's caption track); a line written before the contract existed has no
 * `via` and is read as `pc`. The two buttons in `.history__filters` toggle these
 * booleans. BOTH may be on; both may NOT be off, because an empty feed has no
 * explanation on screen any more -- turning the last source off turns the other
 * on (`toggleViaFilter`), which is the one rule the UI enforces by itself.
 */
const viaFilter = { pc: true, youtube: true };
const VIA_KEYS = ['pc', 'youtube'];
/**
 * D1 — THE CANONICAL PRODUCER the shell reports from `history.root()`, or null.
 *
 * This is the ONE field that decides whether the transcript section is a live
 * feed or an honest closed drawer: `null` means nothing writes the canonical
 * transcript, so the section collapses, its search is disabled, and the note in
 * the bar says why. It is never invented here — absent/unknown is null, which is
 * the fail-closed reading.
 */
let canonicalProducer = null;
/**
 * THE TWO SURFACES (owner, 2026-10-08) — and every piece of state behind them,
 * declared HERE for the reason the note above gives: the init block below calls
 * `wireSurfaces()`, so a `let` written further down would be a temporal-dead-zone
 * ReferenceError that aborts the whole module and leaves the panel mute.
 *
 *   liveEnabled      the Live on/off toggle. `true` is what the app ships with:
 *                    the streaming engine runs while the panel is open, and the
 *                    toggle is how the owner turns it off without quitting. It is
 *                    the LOCAL belief until the shell confirms (`setLiveEnabled`),
 *                    and the button reports which of the two it is showing.
 *   paused           after a CONFIRMED pause. Nothing is transcribed until the
 *                    shell resumes, so the strip says so rather than looking idle.
 *   statusSnapshot   the last status the shell sent ({ text, kind }). The strip's
 *                    one-word status is read from it, so the word and the sentence
 *                    below can never disagree with each other.
 *   surfaceListeners set of callbacks told when the surface changes.
 *   pendingFocusReturn  the element focus came from before the dialog opened, so
 *                    Cancel gives it back. NEVER an autofocus: the panel does not
 *                    steal focus from the window underneath it.
 */
/* THE APP SHIPS WITH THE CAPTION **OFF THE SCREEN** (owner, read from his own
 * prompts of the handoff conversation, 2026-10-12, verbatim):
 *   *"primeiro, o painel de baixo. NELE EU ATIVO o segundo overlay, q é a legenda
 *    independente."*   — the caption is ACTIVATED from the bottom panel;
 *   *"um botao de linhar a legenda, que LIGA ela NA TELA"* — the button TURNS IT ON.
 * It was `true` until 2026-10-13, which meant Alt+C opened the 220px floated
 * caption immediately and the thin band the owner keeps asking for was never the
 * first thing he saw. `false` is the owner's model of his three overlays:
 *   1 the bottom panel (buttons only, ~40px),
 *   2 the caption, loose on the screen — switched on BY the `live` button in it,
 *   3 the right panel.
 * So the `live` button's OFF state is the SHIPPING state, and its title says what
 * the click does; the WORD on it is still painted from `aria-pressed`, so it
 * cannot lie about which state it is in. */
let liveEnabled = false;
let paused = false;
/**
 * TRANSPARENCY (strip only): true while the owner has asked the strip to drop
 * its chrome and keep only the captions. Declared HERE, above the init block,
 * for the temporal-dead-zone rule the 2026-10-07 bug bought:
 * `wireStripControls()` reads it at load.
 *
 * KEPT, NOT DELETED — but it has NO button any more (owner order 2026-10-12, and
 * the button WAS the bug: the two hide-rules that used to be in panel.css turned
 * the window into the shell's opaque #0B0F14 with nothing clickable). The rules
 * are deleted, so a stale call here only sets an attribute nothing paints and
 * posts a message the shell may or may not apply. Nothing vanishes, which is the
 * whole point: the function is inert, not armed.
 */
let transparencyOn = false;
/**
 * THE TRANSCRIPT FONT DIAL (owner, 2026-10-09): the live `--caption-scale` value,
 * clamped to FONT_SCALE_MIN..FONT_SCALE_MAX and persisted in localStorage so the
 * size the owner chose survives a restart. FOUR buttons (two on the panel, two on
 * the strip) all move this ONE number, and `panel.css` derives every caption and
 * history size from it — so the two surfaces cannot disagree and no theme can
 * override the size.
 *
 * Declared HERE, above the init block, for the temporal-dead-zone rule the
 * 2026-10-07 bug bought: `wireFontDial()` reads it at load and re-applies the
 * persisted value before the first caption paints.
 */
let captionScale = FONT_SCALE_DEFAULT;
let pauseSupported = false;

/**
 * THE TRANSLATION SELECTOR'S TABLE -- DECLARED **ABOVE** THE PANEL'S INIT
 * (2026-10-21).
 *
 * `wireStripControls()` calls `wireMenu()`, and `wireMenu()` fills the
 * selector from this table. The table was declared BELOW that call, and a
 * `const` read before its declaration is a **TDZ error**: the panel threw
 * "Cannot access 'TRANSLATION_LANGS' before initialization" at load, and
 * every probe that boots the real panel reported SETUP ERROR. The
 * AGENTS.md rule says it: *"tudo o que o bloco de init de `panel.js` pode
 * tocar e declarado ACIMA dele"*.
 */

/** The languages the translation selector offers. `en`/`pt`/`es` are first --
 *  the owner asked that they be selectable even though the default policy never
 *  translates among them. */
const TRANSLATION_LANGS = [
  /* `''` is not "no choice": the shell reads it as "the language I chose for
   * Sotto", and that default is Português (BR) — hence the label. */
  ['', 'Auto (Português BR)'],
  ['en', 'English'],
  ['pt', 'Português (BR)'],
  ['es', 'Español'],
  ['fr', 'Français'],
  ['de', 'Deutsch'],
  ['it', 'Italiano'],
  ['nl', 'Nederlands'],
  ['pl', 'Polski'],
  ['ru', 'Русский'],
  ['uk', 'Українська'],
  ['tr', 'Türkçe'],
  ['ar', 'العربية'],
  ['hi', 'हिन्दी'],
  ['id', 'Bahasa Indonesia'],
  ['vi', 'Tiếng Việt'],
  ['th', 'ไทย'],
  ['ko', '한국어'],
  ['ja', '日本語'],
  ['zh', '中文'],
  ['he', 'עברית'],
  ['el', 'Ελληνικά'],
  ['cs', 'Čeština'],
  ['sv', 'Svenska'],
  ['da', 'Dansk'],
  ['fi', 'Suomi'],
  ['no', 'Norsk'],
  ['ro', 'Română'],
  ['hu', 'Magyar'],
];
const TRANSLATION_KEY = 'sotto.translationTarget';

// ── O ASPECTO DA LEGENDA NATIVA (dono, 2026-11-09) ───────────────────────────
// Dois valores, um dono por valor: o shell prende e GRAVA em
// `_main/caption-settings.json` (o ficheiro e' a verdade entre arranques), e o
// localStorage aqui serve so' para a caixa abrir mostrando o que esta' no ar
// antes de o shell responder. `0` = o default que embarca (`tight`).
const CAPTION_PLATE_KEY = 'sotto.captionPlate';
const CAPTION_OPACITY_KEY = 'sotto.captionOpacity';
/** O "modo stealth" (dono, 2026-11-16): DESLIGADO de fabrica. O ficheiro
 *  `_main/caption-settings.json` e' a verdade; o localStorage aqui so' evita a
 *  caixa abrir a mentir antes de o shell responder. */
const CAPTION_CAPTURE_KEY = 'sotto.captionCaptureExclude';
const CAPTION_PLATES = ['tight', 'normal'];
/** A transparencia e' o INVERSO do alfa: 0% = placa opaca (alfa 1.0), 70% =
 *  a placa a 30% de alfa -- o piso que `caption_settings.visual()` prende. */
const CAPTION_TRANSPARENCY_MAX = 70;

function storedCaptionLook() {
  let plate = 'tight';
  let transparency = 0;
  try {
    const p = String(window.localStorage.getItem(CAPTION_PLATE_KEY) || '');
    if (CAPTION_PLATES.indexOf(p) >= 0) plate = p;
    const t = parseInt(window.localStorage.getItem(CAPTION_OPACITY_KEY) || '0', 10);
    if (!isNaN(t)) transparency = Math.min(CAPTION_TRANSPARENCY_MAX, Math.max(0, t));
  } catch (_) {
    // A storage-less harness must not take the look controls down with it.
  }
  return { plate: plate, transparency: transparency };
}

function sendCaptionLook(plate, transparency) {
  const opacity = 1 - (transparency / 100);
  if (bridge && typeof bridge.setCaptionVisual === 'function') {
    bridge.setCaptionVisual({ plate: plate, opacity: opacity });
  }
}

/** O "modo stealth": `on` e' o valor que o shell grava e aplica a' janela viva.
 *  Um shell antigo (sem `setCaptureExclude`) deixa o controlo sem efeito e sem
 *  rebentar -- a mesma regra de todos os `typeof` acima. */
function sendCaptionCaptureExclude(on) {
  if (bridge && typeof bridge.setCaptureExclude === 'function') {
    bridge.setCaptureExclude(!!on);
  }
}

let liveSupported = false;
let statusSnapshot = { text: '', kind: null };

// ── THE STATUS IS A REPAIR CONTROL, AND THESE TWO LIVE ABOVE THE INIT BLOCK ──
// Owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei
// que, ao clicar, deve fazer a pipeline inteira ser revivida, se nao tiver
// funcionando"*. `wireRevive` below is that click. The hint is a CONSTANT and
// it is declared here, above the init block, because `updateStripState` reads
// it on every status — and anything the init block can reach is declared above
// it (the rule the 2026-10-07 TDZ bug bought, see AGENTS.md).
const REVIVE_HINT = 'click to restart the pipeline (reloads the live engine)';
const REVIVE_TITLE = 'Restart the pipeline · reloads the live engine';
//: True between asking the shell for a revive and giving up on an answer. The
//: SHELL also refuses a second respawn (`REVIVE_REFUSED`); this flag is what
//: lets the panel say so without a round trip it does not have.
let reviveInFlight = false;
let pendingFocusReturn = null;
/** The history root the shell reported, or null. */
let historyRootPath = null;
/**
 * LINE IDENTITY (owner, 2026-10-08, verbatim: *"essa repeticao de linhas tem que
 * acabar ... nao tem que repetir linha e com append na proxima"*) — NOW
 * `(source, start)` (STEP 4, 2026-10-11).
 *
 * ONE live-box line per worker SEGMENT, and the segment's identity was its
 * `start`. The worker narrates one line as a run of partials that all carry the
 * SAME `start` with `end` growing, and closes it with ONE `final:true` event —
 * and that final event is a REVISION, not necessarily a superset (the owner's own
 * `_main/webview-run.log` carries a segment whose final text differs from the
 * last partial: `...and on the right` -> `problems and use this skill...`).
 *
 * So a commit whose identity is ALREADY the identity of a committed line REPLACES
 * that line's text IN PLACE; only a commit with a NEW identity appends a row. The
 * map is what makes that decidable: without it, the second commit of one segment
 * looked like a second line, which is the duplication the owner is looking at.
 *
 * WHY `start` ALONE WAS NOT ENOUGH. The worker now stamps every caption event
 * with a `source` (`proc:<pid>` / `device:<name>` / `file:<name>`), and the
 * owner requires audio from different apps to be PROCESSED SEPARATELY. Two apps
 * both have an audio second `start=5`, so a map keyed by `start` alone makes the
 * second app's line REPLACE the first's — the exact collision this step removes.
 * See `rowIdentity` for the key and why it cannot collide with a number.
 *
 * FAIL-SAFE DIRECTION: a commit with no usable identity (`start` absent — an
 * older worker, or a non-audio one) appends, exactly as before. Replacing the
 * wrong row would lose a line; appending at worst shows the old behaviour.
 *
 * Declared in this block on purpose — `addCaption` is reachable from the engines
 * the init block below creates, and a `let` read above its declaration is a
 * temporal-dead-zone ReferenceError that takes the whole module down (see the
 * note at the top of this file).
 */
let committedByStart = new Map();

/**
 * O TEXTO QUE ESTA' NAQUELA LINHA -- o que o olho le, para comparar duas linhas.
 * Le do `.caption__text` (a folha que `addCaption` escreve) e cai para o
 * `data-text`, que a mesma funcao mantem; uma linha sem folha devolve `''`.
 */
function rowText(row) {
  if (!row || !row.querySelector) return '';
  const body = row.querySelector('.caption__text');
  const text = body ? body.textContent : '';
  if (typeof text === 'string' && text) return text.trim();
  const stored = row.getAttribute ? row.getAttribute('data-text') : null;
  return typeof stored === 'string' ? stored.trim() : '';
}

/**
 * A ULTIMA LINHA DESTE SOURCE (nao de outra app, nao de outra voz: STEP 4).
 * `data-source` ausente so' casa com um commit sem source -- a mesma tupla que
 * `rowIdentity` trata como chave, para as duas leituras concordarem.
 */
/** Quantas linhas do mesmo source a busca de prefixo examina. */
const DEDUPE_WINDOW = 8;

/**
 * As ultimas `n` linhas do mesmo `source`, da mais NOVA para a mais velha.
 *
 * Nasceu do defeito medido a 2026-11-05 (recibo
 * `_main/receipt-20261105-right-panel-history.md`): `lastRowForSource` devolve
 * UMA linha, e quando o `final` de uma frase chega depois de a frase seguinte
 * abrir, a unica linha comparada e' a errada e a lista ganha uma duplicata
 * exacta -- 51 de 200 linhas na tela dele.
 */
function recentRowsForSource(source, n) {
  const out = [];
  if (!dom.list || !(n > 0)) return out;
  const want = source === null || source === undefined ? null : String(source);
  for (let i = dom.list.childElementCount - 1; i >= 0 && out.length < n; i -= 1) {
    const row = dom.list.children[i];
    if (!row || !row.dataset) continue;
    const have = row.dataset.source === undefined || row.dataset.source === ''
      ? null : String(row.dataset.source);
    if (have === want) out.push(row);
  }
  return out;
}

function lastRowForSource(source) {
  if (!dom.list) return null;
  const want = source === null || source === undefined ? null : String(source);
  for (let i = dom.list.childElementCount - 1; i >= 0; i -= 1) {
    const row = dom.list.children[i];
    if (!row || !row.dataset) continue;
    const have = row.dataset.source === undefined || row.dataset.source === ''
      ? null : String(row.dataset.source);
    if (have === want) return row;
  }
  return null;
}

/**
 * `B` CONTINUA `A`: um e' o outro a crescer. Usado com a identidade AUSENTE, e
 * so' com ela -- duas linhas que o worker identificou por `start` NUNCA se
 * fundem aqui, porque `addCaption` ja' as resolve antes de chegar a isto.
 */
function isPrefixExtension(previous, text) {
  const a = String(previous || '').trim();
  const b = String(text || '').trim();
  if (!a || !b) return false;
  const ta = a.split(/\s+/);
  const tb = b.split(/\s+/);
  if (!ta.length || !tb.length) return false;
  const shorter = ta.length <= tb.length ? ta : tb;
  const longer = ta.length <= tb.length ? tb : ta;
  for (let i = 0; i < shorter.length; i += 1) {
    if (shorter[i] === longer[i]) continue;
    // A ULTIMA palavra e' o unico lugar onde a pontuacao decide: um fecho
    // posto pelo worker (`but.`) e o mesmo `but` a continuar (`but running`)
    // sao a MESMA palavra -- e e' esta a linha que o dono leu (06:07:33
    // `... three, but.` seguida de `... three, but running max.`).
    if (i === shorter.length - 1) {
      const clean = shorter[i].replace(/[.,!?;:'"\u2026]+$/, '');
      if (clean && longer[i].startsWith(clean)) return true;
    }
    return false;
  }
  return true;
}

/**
 * THE KEY OF A COMMITTED ROW: `(source, start)` (STEP 4).
 *
 * With a source the key is `source + "\u0000" + start`. The NUL cannot appear in
 * a device name, a pid or a file name, and a STRING key can never equal the
 * NUMBER `start` — so a sourced row and a sourceless row cannot collide either.
 *
 * With NO source the key is the NUMBER `start`, exactly as it always was, key for
 * key: a run with no source behaves as before this change.
 *
 * `null` means "no usable identity" (no `start`): the caller may not append a
 * line that merely CONTINUES the previous one -- see `isPrefixExtension` and the
 * wall of growing prefixes he measured on 2026-11-05. Anything else appends,
 * exactly as the fail-safe direction always did.
 */
function rowIdentity(source, start) {
  if (start === null || start === undefined) return null;
  return source === null || source === undefined ? start : String(source) + "\u0000" + start;
}

/**
 * THE VOICE A LINE BELONGS TO, read back out of its `source` -- DISPLAY ONLY.
 *
 * `source` is an OPAQUE key. The panel never parses it, and neither does the
 * shell: the whole trick of per-voice `source` is that the existing per-source
 * machinery gives one forming row per person with no structural change. This
 * is the FIRST thing in the panel that looks inside the string, so it is
 * written to be provably incapable of changing behaviour:
 *
 *   - it RETURNS A DISPLAY VALUE. Nothing here is ever fed back into
 *     `rowIdentity`, `committedByStart`, `retireProvisional` or any lookup. If
 *     the hue were the key, renaming a voice would move a line -- the exact
 *     failure the key was chosen to prevent.
 *   - it returns `null` for anything that is not exactly `<base>/voice:speaker-<n>`
 *     (or a bare `voice:speaker-<n>`), so a row with no voice -- which is every
 *     row the owner sees today -- is untouched, byte for byte.
 *
 * WHY A DOT AND NO TEXT: the owner removed a visible ordinal once, verbatim
 * ("nao e' pra ter mais ele", 2026-10-08), twice, for the same element on every
 * row. A coloured dot carries the whole message -- "these rows are the same
 * person" / "these are not" -- and adds no string to the caption. The identity
 * is still on the row as `data-voice`, for probes and for whatever the owner
 * decides the display should become.
 *
 * The hue is the golden angle off the slot number, so two voices never land on
 * the same colour and the colour does not change between windows -- which is
 * what makes it legible at all.
 */
const SOTTO_VOICE_RE = /(?:^|\/)voice:(speaker-\d+)\s*$/;
const SOTTO_GOLDEN_ANGLE = 137.508;

function voiceFromSource(source) {
  if (typeof source !== 'string' || !source) return null;
  const m = SOTTO_VOICE_RE.exec(source);
  if (!m) return null;
  const n = Number(String(m[1]).replace(/^speaker-/, ''));
  if (!Number.isFinite(n)) return null;
  return { label: m[1], n: n, hue: (n * SOTTO_GOLDEN_ANGLE) % 360 };
}

/** Paint (or repaint) the voice dot. Idempotent; a no-op when there is none. */
function applyVoice(line, source) {
  const v = voiceFromSource(source);
  if (!line || !line.dataset) return;
  if (!v) return;                      // no voice -> nothing added, nothing removed
  line.dataset.voice = v.label;
  let dot = line.querySelector('.caption__voice');
  if (!dot) {
    dot = document.createElement('span');
    dot.className = 'caption__voice';
    dot.setAttribute('aria-hidden', 'true');
    line.insertBefore(dot, line.firstChild);
  }
  dot.style.setProperty('--voice-hue', String(Math.round(v.hue)));
  line.setAttribute('aria-label', 'voz ' + v.n);
}

/**
 * HOW MANY LINES THIS DOCUMENT HAS CLOSED — a DIAGNOSTIC counter, kept on the row
 * as `data-index` and NO LONGER PAINTED.
 *
 * The `bcast` direction prints this ordinal beside each line
 * (`pad3(h.id)` in
 * `H:\aireplay\docs\design\sotto-app-design-directions\src\components\Panel.tsx`),
 * and it was on screen as `033 11:21:03`. THE OWNER HAD IT REMOVED, verbatim
 * (2026-10-08): *"tira esse numero de 033 11:21:03. no caso tira esse 033"* — the
 * time stays, the ordinal goes. He left the door open for the other half
 * ("if the 033 is useful for diagnosis, keep it in the internal state but never on
 * screen"), so the counter and the `data-index` attribute SURVIVE and only the
 * `<span class="caption__index">` that carried it into the paint is gone. A probe
 * can still read `li[data-index]`; a human sees `11:21:03`.
 *
 * A MONOTONIC COUNTER, NOT A DOM POSITION, and that is still the whole point: a
 * CSS counter (or "index among siblings") RENUMBERS as `MAX_CAPTIONS` trims the
 * oldest rows off the top, so line 137 would silently become line 1. A REVISION of
 * a row keeps the ordinal it was born with (`committedByStart` identifies the row).
 *
 * Declared in this block on purpose: `addCaption` is reachable from the engine
 * the init block below creates, and a `let` read above its declaration is a
 * temporal-dead-zone ReferenceError that takes the whole module down (see the
 * note at the top of this file).
 */
let lineOrdinal = 0;
/**
 * THE WORDS CURRENTLY PAINTED in the forming line of EACH SOURCE, so a repaint
 * can be INCREMENTAL. The live box is rewritten on every partial, and the
 * per-word contrast ramp (`mano`) and the forming fog (`cine`) both need one
 * span per word — but recreating those spans on every partial would restart every
 * transition and throw away the very thing that makes the ramp gradual. So the
 * spans are REUSED by index and only the words that actually changed are written;
 * the ramp is repainted only when the TOTAL moves.
 *
 * KEYED BY SOURCE (STEP 4, 2026-10-11), because there is now ONE OPEN ROW PER
 * SOURCE: two apps must be able to form two sentences at the same time without
 * one's partial repainting the other's spans. The key is the source string, or
 * `null` for a run with no source — the same key `provisionalRows` uses.
 */
const paintedWordsBySource = new Map();

/**
 * THE ONE OPEN (`--provisional`) ROW PER SOURCE, as the `<li>` itself.
 *
 * A Map rather than an attribute selector ON PURPOSE: a device name is
 * `device:CABLE Output (VB-Audio Virtual Cable)` — it contains `:`, quotes and
 * backslashes — so `querySelector('[data-source="…"]')` would need escaping that
 * a caption must never depend on. The map is the lookup; `data-source` is
 * written only so a probe can READ the identity off the row.
 */
const provisionalRows = new Map();

/**
 * ONE FORMULATION ENGINE PER SOURCE (STEP 4, 2026-10-11).
 *
 * The engine holds single-stream buffer state (`committed`/`provisional`, the
 * LocalAgreement-2 history, the emitted watermark), so TWO SOURCES IN ONE ENGINE
 * interleave into ONE garbled sentence. `engineFor(source)` builds and caches one
 * engine per source key, and the panel never feeds a fragment to another source's
 * engine. The key is the source string, or `null` for no source.
 *
 * Declared HERE, above the init block, on purpose: the init block calls
 * `wireCaptions()`, and anything it can reach is declared above it — a
 * `let`/`const` read above its declaration is a temporal-dead-zone ReferenceError
 * that takes the whole module down (see the note at the top of this file).
 */
const engines = new Map();

/**
 * THE MISSING INSTRUMENT: WHEN THE EYE IS SERVED, not only when the line is
 * committed (owner order, 2026-11-04).
 *
 * `CAPTION_APPLIED` — the shell's row — measures the COMMIT. But the provisional
 * text is painted at `renderProvisional`, and NOTHING logged that instant: the
 * whole 1509 ms leg the audit measured sat between a paint the owner was already
 * reading and a commit that changed no pixel. Optimising that leg is only honest
 * if the paint is measured beside it, so this emits ONE row per paint, with the
 * SAME correlation the commit path uses — the panel's own row identity
 * (`rowIdentity(source, start)`, what `addCaption` keys the row by) — plus the
 * visible text, which is the field `CAPTION_APPLIED` carries.
 *
 * THE SINK IS INJECTED, NEVER ASSUMED. The page has no log channel of its own
 * (`window.sotto` exposes `captionApplied`/`statusApplied` and no generic
 * `log`), so this cannot invent a shell kind: it appends to a bounded in-memory
 * ring (`window.SottoPaintLog`, read by DOM probes) and forwards the same row to
 * `window.SottoPaintSink(row)` when one is installed. The oracle installs one
 * and measures both legs (`_main/panel-commit-stable-oracle.py`); a shell that
 * adds a `paint-row` kind can install one too, and the row's shape is already
 * the log's (`CAPTION_PROVISIONAL_PAINT n=… at=… id=… src=… conf=… prov=…
 * text=…`).
 */
const PAINT_ROWS_MAX = 64;
const paintRows = [];
let paintSequence = 0;

function noteProvisionalPaint(source, start, confirmed, provisional, text) {
  paintSequence += 1;
  const at = Date.now();
  const row = {
    tag: 'CAPTION_PROVISIONAL_PAINT',
    n: paintSequence,
    at,
    // THE SAME CORRELATION THE COMMIT ROW USES: `addCaption` finds its row by
    // this identity, and `recordHistory` writes the same `start` to the file.
    id: rowIdentity(source, start),
    src: source,
    start: start === undefined ? null : start,
    conf: confirmed,
    prov: provisional,
    text,
  };
  paintRows.push(row);
  if (paintRows.length > PAINT_ROWS_MAX) paintRows.shift();
  if (typeof window.SottoPaintSink === 'function') {
    try { window.SottoPaintSink(row); } catch (err) { /* a probe must not break the paint */ }
  }
  return row;
}

/** The ring, newest last. Read by probes; never by the renderer. */
window.SottoPaintLog = function () { return paintRows.slice(); };
/** The rows' LOG LINE, exactly as a shell would write it. */
window.SottoPaintLine = function (row) {
  const r = row || paintRows[paintRows.length - 1];
  if (!r) return '';
  return 'CAPTION_PROVISIONAL_PAINT n=' + r.n
    + ' at=' + r.at
    + ' id=' + JSON.stringify(r.id)
    + ' src=' + (r.src === null ? '-' : String(r.src))
    + ' conf=' + r.conf
    + ' prov=' + r.prov
    + ' text=' + JSON.stringify(r.text);
};

/**
 * `pad3` — the mockup's own width for the line ordinal.
 *
 * KEPT even though nothing paints the ordinal any more: it is the FORMAT the
 * mockup defines, and the number is still written to `data-index` for the DOM
 * probes. It is used below by `stampOrdinal`, which is the single place the
 * ordinal is written, so this cannot become a function nobody calls.
 */
function pad3(n) {
  const s = String(Math.max(0, Math.trunc(n)));
  return s.length >= 3 ? s : '000'.slice(s.length) + s;
}

/** THE ONE PLACE THE ORDINAL IS STAMPED — on the ROW, never in the paint. */
function stampOrdinal(line, ordinal) {
  if (!line || typeof line.dataset !== 'object' || !line.dataset) return;
  line.dataset.index = String(ordinal);
  line.dataset.indexPadded = pad3(ordinal);
}

/** The ramp's own numbers, once, so the JS and the CSS cannot disagree. */
const WORD_RAMP = { min: 0.45, span: 0.55 };

/**
 * The contrast a word carries by POSITION in the forming line: the newest word
 * is at full contrast and every older one settles back.
 *
 * The direction's words (`designs.ts`, `mano`): *"cada palavra recém-chegada
 * ganha contraste aos poucos"* — and the mockup's own formula is
 * `0.45 + 0.55 · (i+1)/len`. It is computed HERE, once per word per total
 * change, and handed to CSS as `--w-op`; the theme decides whether to use it.
 */
function wordRamp(i, n) {
  if (!n) return '1';
  const v = WORD_RAMP.min + WORD_RAMP.span * ((i + 1) / n);
  return String(Math.round(v * 1000) / 1000);
}

/**
 * Paint a word list into a span, REUSING the spans that are already there.
 *
 * `offset`/`total` place these words in the FORMING LINE as a whole (the
 * confirmed part and the still-rewriteable tail are two hosts, one line), so the
 * ramp is continuous across the seam instead of restarting in the tail.
 *
 * The DOM shape is the one `panel.js` has always produced — words separated by
 * single spaces, so `textContent` reads exactly as the old `join(' ')` did, and
 * `.caption__confirmed` / `.caption__provisional` keep their meaning.
 */
function paintWords(host, words, offset, total, totalChanged, typingIndex, flat) {
  if (!host) return;
  const typing = typeof typingIndex === 'number' ? typingIndex : -1;
  // A LINHA DO PLAYER NAO TEM RAMPA (2026-11-02). MEDIDO no banco de ensaio:
  // `--w-op` era recalculado a cada acrescento ('Lean' 1 -> 0.725 -> 0.633), ou
  // seja a frase ja' no ecra era re-animada -- o dono: *"tu ta simplesmente
  // reaplicando a animacao atual"*. O YouTube deixa a palavra que apareceu em
  // contraste cheio. `flat` vem de `renderProvisional` pela regra `external:`.
  const restyle = !!totalChanged && !flat;
  const ramp = flat ? '1' : null;
  for (let i = 0; i < words.length; i += 1) {
    let span = host.children[i];
    let fresh = false;
    if (!span) {
      span = document.createElement('span');
      span.className = 'caption__word';
      host.append(span, document.createTextNode(' '));
      fresh = true;
    }
    // THE WORD'S IDENTITY IS IN `dataset.w`, NOT IN ITS `textContent`, and that
    // changed with the typing reveal: a typing word's textContent is now the
    // concatenation of its character spans, so writing `textContent` to it would
    // DESTROY the spans it is made of. The two facts that decide the paint are
    // "is this the same word" and "should this word be typing", and both are
    // cheap reads.
    const isTyping = i === typing;
    const wasTyping = span.dataset.typing === '1';
    if (span.dataset.w !== words[i] || wasTyping !== isTyping) {
      span.dataset.w = words[i];
      paintChars(span, words[i], isTyping);
    }
    if (fresh || restyle) {
      span.style.setProperty('--w-i', String(offset + i));
      span.style.setProperty('--w-n', String(total));
      span.style.setProperty('--w-op', ramp === null ? wordRamp(offset + i, total) : ramp);
    }
  }
  while (host.children.length > words.length) {
    const last = host.lastElementChild;
    const space = last.nextSibling;
    host.removeChild(last);
    if (space) host.removeChild(space);
  }
}

/**
 * The newest word of the forming line, painted WHOLE.
 *
 * WHAT IT USED TO BE (2026-10-20): ONE `<span class="caption__ch">` PER
 * CHARACTER, with `--c-i` (its index in the word) stamped through CSSOM, and
 * the CSS revealing them one at a time. That is a TYPEWRITER, and the owner
 * read it as tokens: *"fica aparecendo como se fosse 'tokens' e nao palavras
 * inteiras. pode somente palavras inteiras."*
 *
 * WHAT IT IS NOW: the word is ONE text node and appears whole. The `data-typing`
 * marker stays, so the word-level rule in `panel.css`
 * (`.caption--provisional .caption__word[data-typing]`) can still mark the
 * newest word, and the CSS that animated the characters has nothing to animate.
 *
 * NEVER A `style=` ATTRIBUTE: `panel.html`'s CSP is `style-src 'self'` and a
 * markup style attribute is refused by it (measured; see the cost receipt §10).
 *
 * EVERY WORD IS A PLAIN TEXT NODE NOW, so `textContent` reads exactly as it
 * did when the line was one string, and the extra elements are gone: the
 * forming line's DOM no longer grows with the length of the longest word.
 *
 * THE THREE CASES THAT MATTER, and the reason this is not a one-line
 * `textContent =`:
 *   * GROWTH (`"casa"` → `"casas"`): the word gets LONGER as the model firms it
 *     up. The text node is REPLACED, so the word is whole at every step. The
 *     growing word is not painted at all while it grows (the engine holds the
 *     forming tail's last word back until it is committed), so this case is
 *     rare and, when it happens, the word simply changes.
 *   * REWRITE (`"casa"` → `"caso"`): the text node is replaced with the new
 *     word. The word stays whole; only its letters change.
 *   * NO LONGER THE NEWEST WORD (or a committed line): the `data-typing`
 *     marker is taken off, and the word is written exactly as it was.
 */
function paintChars(span, word, typing) {
  if (!typing) {
    delete span.dataset.typing;
    // THE TEXT IS ALWAYS WRITTEN — and that is not defensive, it is the bug this
    // function had for one revision: the first version only collapsed spans that
    // were ALREADY built, so a brand-new word (no `dataset.typing`, no children)
    // was left EMPTY and the whole line rendered blank. The cheap identity check
    // below keeps the write off the common path without ever skipping it.
    const kids = span.childNodes;
    if (kids.length === 1 && kids[0].nodeType === 3 && kids[0].data === word) return;
    span.replaceChildren(document.createTextNode(word));
    return;
  }
  span.dataset.typing = '1';
  // THE WORD IS WRITTEN WHOLE (2026-10-20, the owner's "so palavras inteiras").
  //
  // The owner, verbatim, about the live caption: *"o jeito que as letras ou
  // palavras aparecem na tela ta bem ruim. fica aparecendo como se fosse
  // 'tokens' e nao palavras inteiras. pode somente palavras inteiras."*
  //
  // This function used to give the newest word one `<span class="caption__ch">`
  // per CHARACTER and let the CSS reveal them one at a time (`--type-step`).
  // That is a TYPEWRITER: the owner saw a half-word on the screen and read it
  // as tokens. A word is now written as ONE text node and appears whole.
  //
  // The per-character spans are gone, so the CSS that animated them
  // (`panel.css`, and the per-theme overrides) has nothing to animate: the
  // word-level rule that replaced it is on `.caption__word[data-typing]`.
  //
  // The write is the SAME one the non-typing branch does, and it is the one
  // that keeps the old bug away: `replaceChildren` clears EVERYTHING, so a
  // stale text node from another word can never fuse onto this one (the
  // "anove" bug of ARM S of `_main/_panel2-dom-probe.js`).
  const kids = span.childNodes;
  if (kids.length === 1 && kids[0].nodeType === 3 && kids[0].data === word) return;
  span.replaceChildren(document.createTextNode(word));
}

/* THE CAPTION WINDOW'S ATTRIBUTE NAME, DECLARED HERE FOR THE SAME REASON THE AUDIO
 * LEVEL IS (see the note at the bottom of this block): the init block below
 * REACHES it, and a `const` reached from above its own declaration throws at load.
 *
 * MEASURED 2026-10-17 16:00:40, real WebView2, the shell's own log:
 *   WARN PAGE_ERROR text="Uncaught ReferenceError: Cannot access
 *   'CAPTION_WINDOW_ATTR' before initialization" at=panel.js:2221:48
 *   stack="... at captionOverlayIsUp (panel.js:2221:48) at
 *   watchCaptionWindowState (panel.js:2254:20) at panel.js:629:3"
 * Line 629 called `watchCaptionWindowState()`; the constant it reads was declared
 * at 2217. The throw happened INSIDE the init block, so every statement after it
 * in that block -- wirePause, wireRevive, announceReady, wireLevel and
 * wireThemeScrollGuard -- never ran at all, which is why the owner's caption
 * button did nothing and nothing said why.
 *
 * ONLY THE NAME AND ITS ONE READER MOVED. `watchCaptionWindowState`,
 * `requestCaptionOverlay` and `applyLiveEnabled` are function declarations, so they
 * hoist and stay beside the long explanation they belong to. This is the SECOND
 * time this file has paid for a binding below the code that reaches it (the audio
 * level was the first), which is why the gate exists:
 *   node _main/tdz-reach-oracle.js app/panel/panel.js 612 635
 */
const CAPTION_WINDOW_ATTR = 'data-caption-window';

/** What the shell last said it did with its caption window. NOT what the page wants. */
function captionOverlayIsUp() {
  return document.documentElement.getAttribute(CAPTION_WINDOW_ATTR) === 'on';
}

// ---------------------------------------------------------------------------
// this reads `LEVEL`. It sat BELOW the burst until 2026-10-17, which was the
// second TDZ in this file; it was masked because the first one threw first.
// THE AUDIO LEVEL — REAL DATA OR NOTHING. Declared ABOVE the init block, which
// reaches it: `wireLevel()` ends in a SYNCHRONOUS `pull()` -> `pushLevel()` ->
// ---------------------------------------------------------------------------
// THE WAVE THE DESIGN DREW WAS FAKE, AND IT IS DELETED. `.chrome__meter` ran a
// pure CSS keyframe loop that animated identically with speech, with silence and
// with a DEAD WORKER — measured in `docs/research/12-audio-level-contract.md`.
// A wave that lies is worse than no wave, which is what the owner forbade.
//
// WHAT THE REAL DATA IS, and what is still missing (that document's finding, not
// a guess): the worker's `peak` is the MAXIMUM OF THE RUN so far — it only rises,
// so three ticks in a row print the same number while the `rms` drifts — and it
// is published at about ONE POINT PER 10 s, where a wave needs ~10/s. Both are
// being fixed in the worker and in the shell by other lanes; the contract this
// code is built against is `stats.peak` = the level OF ONE WINDOW, plus
// `stats.blocks`.
//
// SO THE WAVE IS MOUNTED AND OFF. It consumes `onStats`/`getStats` when a shell
// has them, keeps an N=128 history (≈12.8 s at 10 Hz), smooths it with an
// INSTANT ATTACK and a ~200 ms release, and paints five compositor-only bars.
// With no data the bars sit at the floor, `body[data-level="none"]` says so, and
// the probe asserts that they do not move.
const LEVEL = {
  /** Ring buffer of window levels, newest at `(head - 1 + N) % N`. */
  hist: new Float32Array(128),
  head: 0,
  n: 0,
  /** The smoothed value the bars show. */
  level: 0,
  /** False until a REAL measurement arrives — never inferred from anything. */
  have: false,
  /** Local clock of the last measurement, so a stale feed can be detected. */
  at: null,
};
/** Instant attack, ~200 ms release: without the release the bars shake. */
const LEVEL_RELEASE_MS = 200;
const LEVEL_FLOOR = 0.14;
let lastLevelPaint = 0;

/** No bridge means no captions can ever arrive; say so instead of looking idle. */
if (!bridge) {
  if (dom.status) dom.status.classList.add('status--error');
  document.body.dataset.state = 'error';
  if (dom.statusText) dom.statusText.textContent = 'Preload bridge missing · captions are impossible';
  if (dom.placeholder) {
    const noBridgeTitle = dom.placeholder.querySelector('.captions__placeholder-title');
    const noBridgeBody = dom.placeholder.querySelector('.captions__placeholder-body');
    if (noBridgeTitle) noBridgeTitle.textContent = 'Panel not wired';
    // The cause, not a sentence (owner, 2026-11-09: *"ZERO frases explicativas"*):
    // the body used to read "window.sotto is undefined. The preload script did not
    // run, so no caption can reach this panel."
    if (noBridgeBody) noBridgeBody.textContent = 'window.sotto undefined · preload did not run';
  }
  setHistoryNote('Transcript unavailable: no bridge');
  /* O OUTRO DESFECHO DO ARRANQUE, nomeado: sem ponte a pagina NAO liga nada,
   * e sem este marco um arranque que nao fiou nada mede o tempo todo em
   * `panel-js` e parece o mesmo que um arranque lento. */
  bootMark('no-bridge');
} else {
  wireHistory();
  wireCaptions();
  wireExternalCaptions();
  wireStatus();
  // Silent no-op unless the hosting shell exposes `onStats` (see `wireStats`).
  wireStats();
  wireControls();
  // THE TWO SURFACES, in this order: the surface decides which layout the rest
  // of the wiring paints into, and `wireControls` above has already bound the
  // controls that exist on BOTH of them.
  wireSurfaces();
  wireStripControls();
  /* The caption button paints what the SHELL's caption window is doing, from the shell's
   * own account of it (`data-caption-window`). Armed here, next to the wiring it serves,
   * so a caption window the owner raised before this document existed still paints the
   * button on load with no click. */
  watchCaptionWindowState();
  wirePause();
  wireHistorySearch();
  // The status is a repair control: one click revives the whole pipeline.
  wireRevive();
  bootMark('wired');
  announceReady();
  // O PRIMEIRO QUADRO DEPOIS DA FIACAO: o que o dono ve existir e' este, nao o
  // `announceReady` (que so' diz que a ponte respondeu).
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(function () { bootMark('paint1'); });
    setTimeout(function () { bootMark('paint2'); }, 0);
  }
  wireLevel();
}


// THE TRANSCRIPT'S SCROLL GUARD IS ARMED WHETHER OR NOT A BRIDGE EXISTS (lane:
// caption): the feed and the live box are in the document either way, and the owner's
// rule is about the layout, not about captions arriving.
wireThemeScrollGuard();
// THE WHEEL OWNS THE TRANSCRIPT (owner, 2026-11-08: *"eu nao consigo usar meu
// scroll pra scrollar as legendas no historico."*), with or without a bridge.
wireHistoryWheel();
// THE KEYBOARD TOO (owner contract 2026-11-09: "no visible scrollbars (keep wheel
// AND keyboard scrolling)"). Hiding the bar removed the only affordance that showed
// the box can move, so the keys that used to scroll the focused box must work
// without the box being focusable at all.
wireHistoryKeys();


// ---------------------------------------------------------------------------
// Caption formulation. The TEXT decisions live in `caption-formulation.js`,
// which is DOM-free precisely so an oracle can run the real functions outside
// Electron; this block owns only the wiring and the rendering of what the
// engines decide.
// ---------------------------------------------------------------------------

/**
 * The engine for one source — built on first use, cached forever.
 *
 * `source` is the worker's own key (`proc:<pid>` / `device:<name>` /
 * `file:<name>`) or `null` when the worker stamped none. ONE ENGINE PER SOURCE
 * is the whole point (STEP 4): the engine's buffer state is single-stream, so two
 * apps sharing an engine produce one garbled sentence, and a partial for one app
 * must never touch the other's open row. The map key IS the source, so `null`
 * and the string `"null"` are different engines, as they must be.
 */
function engineFor(source) {
  const key = source === null || source === undefined ? null : String(source);
  const cached = engines.get(key);
  if (cached) return cached;
  const engine = window.SottoFormulation.createEngine({
    source: key,
    // `reason` and `meta` are the provenance the engine computes at the moment of
    // the write — WHICH rule closed the line and WHERE in the audio it began.
    // Both used to be dropped here (M7/M8).
    onCommit: (text, reason, meta) => {
      // THE PROVISIONAL ROW HAS TO GO WHEN THE LINE IT SHOWED IS WRITTEN, and the
      // panel is the only place that can do it: the engine is DOM-free.
      //
      // MEASURED 2026-10-08 by `_main/_panel2-dom-probe.js`: feeding a worker-shaped
      // stream (a `final:true` line, then the next line's growing partial) left ONE
      // `<li>` holding both the committed text and the provisional tail. The flow
      // was `renderProvisional` (creates the open row) → `commit` → `addCaption`
      // (retires it, appends the committed row) → and then, because the ENGINE's
      // tail is empty at that instant, no `onProvisional` followed — so the row
      // `addCaption` had just retired was never replaced, `addCaption`'s own append
      // was the only row left, and the next fragment rewrote that same row in place.
      // The box therefore NEVER painted a closed line as a closed line: it always
      // showed one open row whose confirmed span had grown. That is not what the
      // owner reads (`panel.js` has always claimed "the box replaces, one row per
      // closed line").
      //
      // Retiring HERE and letting the next `renderProvisional` create a fresh open
      // row is the same rule `addCaption` already applied, moved to the moment the
      // line actually became final. If the engine still holds a tail, `onProvisional`
      // fires immediately after this (the engine's OWN order) and re-creates it.
      //
      // PER SOURCE: this retires only THIS engine's open row. Retiring another
      // source's row here would blank a sentence the other app is still forming.
      retireProvisional(key);
      addCaption(text, reason, meta);
    },
    onProvisional: (committed, provisional, start) => renderProvisional(committed, provisional, key, start),
  });
  engines.set(key, StableWords.wrap(engine));
  return engine;
}

/**
 * THE FALLBACK DEADLINE — armed ONLY while an engine is still holding a tail the
 * worker never proved (owner order, 2026-11-04).
 *
 * UNTIL 2026-11-04 this was armed on every caption, unconditionally, and it was
 * the PRIMARY path: measured on the owner's own log (session 12:22:26-12:51:39,
 * 216 `CAPTION_IN`), a line committed p50 1509 ms after its fragment arrived and
 * 51.5 % of them inside [1490,1520] — the constant itself, because fragments in
 * that session are p50 4150 ms apart. Every one of those fragments carried
 * `stable:true`, i.e. the worker had already proved every word: the panel was
 * waiting for a second opinion that could never differ.
 *
 * `engine.ingest` now commits such a fragment on arrival, so its engine holds
 * NOTHING and arming the timer for it would buy nothing but a wake-up 1500 ms
 * later. `armHoldIfHeld` is the whole rule: arm the deadline only when there is
 * something to give up on. The population that still lands here is named in the
 * `COMMIT_MAX_HOLD_MS` doc in `caption-formulation.js`: `final:true stable:false`
 * fragments (610 of them in the same log), the player channel
 * (`external:player`), the batch pass, and any worker build predating the
 * `stable` stamp.
 *
 * RE-ARMED while ANY engine still holds a PROVISIONAL line: the deadline no
 * longer writes anything to the transcript (M6 — see `expireHold`), so a timer
 * that fired on a live provisional line must go back to waiting rather than let
 * the line be abandoned. With one engine per source (STEP 4) the question is
 * asked of EVERY engine, because one app's stalled tail is still a reason for
 * the deadline to stay armed.
 *
 * F6 — THE GUARD THAT COULD NOT BE TRUE. This read
 * `engine.state().provisionalRoute`, a field `state()` never returned (its
 * three keys are `committed`, `provisional`, `lastAudioEnd`), so the test was
 * always `undefined` → false and the timer was NEVER re-armed: the first hold
 * deadline disarmed the deadline for the rest of the run, and a line that
 * stalled after it was held until the next fragment or the next status change.
 * The real field is the provisional TAIL itself — a non-empty array is exactly
 * "the engine is still holding something".
 */
let holdTimer = null;
function armHoldTimer() {
  clearTimeout(holdTimer);
  holdTimer = setTimeout(() => {
    holdTimer = null;
    // EVERY engine, not just one: the deadline is a property of the stream, and
    // each source's engine holds its OWN tail (STEP 4). The timer is re-armed
    // while ANY engine still holds a provisional line.
    let held = false;
    for (const engine of engines.values()) {
      engine.expireHold();
      if (engine.state().provisional.length) held = true;
    }
    if (held) armHoldTimer();
  }, window.SottoFormulation.COMMIT_MAX_HOLD_MS);
}

/** Is ANY engine still holding a tail the worker has not proved? */
function anyTailHeld() {
  for (const engine of engines.values()) {
    if (engine.state().provisional.length) return true;
  }
  return false;
}

/**
 * Arm the deadline IF, and only if, a fragment left a tail behind.
 *
 * Called AFTER `ingest`, which is the point where the answer exists: a
 * `stable:true` fragment commits inside `ingest` and leaves nothing, a fragment
 * without the promise leaves a tail that the deadline is for. A previous timer is
 * cleared either way — the deadline always measures from the newest fragment.
 */
function armHoldIfHeld() {
  clearTimeout(holdTimer);
  holdTimer = null;
  if (!anyTailHeld()) return;
  armHoldTimer();
}

/**
 * THE LIVE BOX AND THE PLACEHOLDER ARE ONE SLOT IN TWO STATES.
 *
 * THE LIST IS BORN HIDDEN: `panel.html` ships `<ol class="captions__list"
 * id="caption-list" hidden>` and `panel.css` makes that attribute bite
 * (`.captions__list[hidden] { display: none; }`), because an empty box must not
 * take the placeholder's place. The attribute was taken off in ONE place only
 * -- `addCaption`, the path a COMMITTED line takes. A line that is still
 * PROVISIONAL -- the player's own captions, the ASR hypothesis still growing --
 * never goes through `addCaption`, so it was painted into a box that stayed
 * `display: none`.
 *
 * MEASURED 2026-10-20, 02:22:35, on the owner's own panel with the YouTube
 * track open (`_main/panel-state.json`): `live.count = 1`, `live.hidden = true`,
 * the placeholder visible, and the line's own text right there in the DOM. The
 * caption HAD arrived and the owner could not see it.
 *
 * So ONE function owns both directions: the box is unhidden wherever a line is
 * painted, and the placeholder comes back wherever the box has nothing left to
 * show. No path can paint a line into an invisible box again.
 */
function syncCaptionBox() {
  if (!dom.list) return;
  if (dom.list.childElementCount > 0) {
    dom.list.hidden = false;
    if (dom.placeholder) dom.placeholder.hidden = true;
  } else {
    dom.list.hidden = true;
    if (dom.placeholder) dom.placeholder.hidden = false;
  }
}

/**
 * The provisional line: one `<li>` whose text is REWRITTEN IN PLACE as the
 * hypothesis changes. It is never acknowledged as applied until it commits,
 * because a caption the model later contradicts is not a caption.
 * The line contains two spans inside .caption__text: .caption__confirmed and
 * .caption__provisional, so we can update the provisional part without
 * touching the confirmed part (which avoids flicker).
 *
 * ── WHAT CHANGED 2026-10-08, AND WHY IT IS STILL "REWRITTEN IN PLACE" ────────
 * Each WORD is now its own `<span class="caption__word">`, carrying `--w-i`,
 * `--w-n` and `--w-op` (see `paintWords`). Two directions need per-word handles
 * and neither could be built without them:
 *
 *   * `mano` — "cada palavra recém-chegada ganha contraste aos poucos". The ramp
 *     is `--w-op`, and the theme transitions `opacity` to it: an OPACITY
 *     transition, which the compositor owns, on a span that is REUSED (not
 *     recreated) so the transition is never restarted by the next partial.
 *   * `cine` — "a frase fechada é sólida; a em curso vive na névoa". The fog is
 *     a `filter: blur()` the theme applies to the tail span.
 *
 * AND THE THIRD HANDLE IS THE CHARACTER, added for the owner's first line in the
 * brief: *"TYPING letter-by-letter on the live line"*. The NEWEST WORD of the
 * forming line is split into one span per character by `paintChars`, and
 * `panel.css` reveals them one at a time with an `opacity` animation. That is
 * the only word in the document built this way, so the cost is bounded by the
 * longest word rather than by the transcript, and no committed text is affected.
 *
 * The contract is unchanged: ONE row per segment (identity = `start`), the
 * confirmed span is written only when its words changed, the tail span is the
 * one that moves, and nothing here animates a property that forces a relayout
 * (see `_main/receipt-panel-per-theme-chrome.md` §cost).
 *
 * ── AND ONE OPEN ROW PER SOURCE (STEP 4, 2026-10-11) ─────────────────────────
 * `source` is the worker's key or `null`. The row and its paint cache are found
 * through `provisionalRows`/`paintedWordsBySource` — NEVER through an attribute
 * selector, because a device name contains `:`, quotes and backslashes. A partial
 * for source A therefore cannot find, repaint or retire source B's open row, which
 * is the observable the per-source ENGINES exist for.
 */
function renderProvisional(committed, provisional, source, start) {
  if (!dom.list) return;
  const key = source === null || source === undefined ? null : String(source);
  const confWords = Array.isArray(committed) ? committed.map(t => t.w) : [];
  const provWords = Array.isArray(provisional) ? provisional.map(t => t.w) : [];
  // THE GROWING WORD IS HELD BACK (2026-10-20, the owner's "so palavras
  // inteiras"). The tail's LAST word is the one the model is still deciding
  // ("cre" -> "create"), and a half-word on the screen is exactly what the
  // owner called "tokens": *"fica aparecendo como se fosse 'tokens' e nao
  // palavras inteiras. pode somente palavras inteiras."*
  //
  // LocalAgreement-2 already knows the answer: a word is whole when two
  // consecutive hypotheses agree on it, and that is what the CONFIRMED span
  // holds. So the tail's last word waits for the commit.
  //
  // THE PLAYER'S WORDS ARE WHOLE BY CONSTRUCTION: the cue comes from YouTube's
  // own track and the shell serves it verbatim (`youtube_captions.align_painted`
  // hands back the cue's FULL text), so its last word IS a whole word and is
  // NOT held back -- the owner compares that caption against the screen, word
  // by word, in real time.
  //
  // THE WORD IS NOT LOST: it is in the engine's buffer and `commit` hands the
  // whole line to the transcript. Only the PAINTING waits.
  // A CLOSED LINE'S WORDS ARE WHOLE (2026-10-20). The worker closes a line
  // with `meta.final === true` -- its SECOND pass over the whole segment
  // (`redux`) -- and that text is final: its last word will never change.
  // Holding it back showed the owner a sentence missing its last word.
  // MEASURED, `_main/caption-independent-oracle.js` ARM A18 (shipped
  // bytes): real="quixotescamente uma" want="quixotescamente uma linha".
  //
  // THE ENGINE IS THE ONE THAT KNOWS: it saw the fragment's `meta.final`.
  // `state()` is its public, DOM-free window, so the renderer READS the
  // answer there instead of guessing from the source name.
  const engine = engines.get(key);
  const tailClosed = !!(engine && typeof engine.state === 'function'
    && engine.state().tailClosed);
  // THE PLAYER'S WORDS ARE WHOLE BY CONSTRUCTION: the cue comes from
  // YouTube's own track and the shell serves it verbatim
  // (`youtube_captions.align_painted` hands back the cue's FULL text), so
  // its last word IS a whole word and is NOT held back -- the owner
  // compares that caption against the screen, word by word, in real time.
  // `wordsAreWhole`: are these words PROVEN whole? The worker says so when it
  // held the unproven word back (owner, 2026-10-30); `stable-words.js` owns it.
  const wordsAreWhole = StableWords.wordsAreWhole(tailClosed, key);
  const shownProv = wordsAreWhole ? provWords : provWords.slice(0, -1);
  const total = confWords.length + shownProv.length;

  // Find or create the line that holds THIS source's provisional hypothesis. An
  // entry whose node left the document (MAX_CAPTIONS trimmed it) is dropped,
  // exactly as the old `querySelector` found nothing for it.
  let line = provisionalRows.get(key) || null;
  if (line && !line.isConnected) {
    provisionalRows.delete(key);
    line = null;
  }
  if (!line) {
    line = document.createElement('li');
    line.className = 'caption caption--provisional';
    // The source on the row, for probes — UNSET when there is no source, so the
    // no-source DOM stays byte-identical to before this change.
    if (key !== null && line.dataset) line.dataset.source = key;
    provisionalRows.set(key, line);
    // The ordinal this line will be born with when it commits. STAMPED ON THE
    // ROW ONLY (`data-index` / `data-index-padded`) — the `<span>` that used to
    // paint it is gone, by the owner's own instruction (2026-10-08): *"to falando
    // desse numero a esquerda. o vermelho. nao é pra ter mais ele"*. A probe can
    // still read the ordinal; nobody sees it.
    stampOrdinal(line, lineOrdinal + 1);

    // The direction's own indicator (`inst`): a REAL element, because a
    // border-left cannot be animated on the compositor and the direction's one
    // dynamic element is exactly this LED. `display: none` for the other four
    // directions — see `panel.css`.
    const led = document.createElement('span');
    led.className = 'caption__led';
    led.setAttribute('aria-hidden', 'true');

    const time = document.createElement('span');
    time.className = 'caption__time';
    time.textContent = clockTime();

    const body = document.createElement('span');
    body.className = 'caption__text';

    // Inside the body we have two spans: one for confirmed, one for provisional.
    const confirmedSpan = document.createElement('span');
    confirmedSpan.className = 'caption__confirmed';
    const provisionalSpan = document.createElement('span');
    provisionalSpan.className = 'caption__provisional';
    // The tail marker ('·'), its own element so a theme can style it and so the
    // word spans above stay countable by `paintWords`.
    const mark = document.createElement('span');
    mark.className = 'caption__mark';

    body.append(confirmedSpan, provisionalSpan, mark);
    line.append(led, time, body);
    dom.list.append(line);
    // THE BOX IS VISIBLE FROM THE FIRST LINE, not from the first COMMIT. This
    // row is a PROVISIONAL one, and `addCaption` was the only path that ever
    // took the `hidden` off the list -- so a forming line was painted into a
    // `display: none` box (see `syncCaptionBox`).
    syncCaptionBox();
    paintedWordsBySource.set(key, { confirmed: [], provisional: [], total: 0 });
    followNewestLine();
  }

  // THE VOICE DOT, on the FORMING line -- this is the row the owner is actually
  // looking at, so it is the one that had to be handled here and not only in the
  // commit path. MEASURED: with the dot on the commit path alone, the DOM after
  // a forming caption carried `data-source` and NO `data-voice`, and a probe
  // showed `caption caption--provisional`, zero `.caption__voice`. Idempotent,
  // so calling it on a reused row costs nothing and cannot double the dot.
  applyVoice(line, key);

  // Update the two inner spans IN PLACE — reusing every span that already holds
  // the right word (see `paintWords`). The cache is THIS source's, so the other
  // app's row keeps its spans and its ramp.
  const paintedWords = paintedWordsBySource.get(key) || { confirmed: [], provisional: [], total: 0 };
  const totalChanged = total !== paintedWords.total;
  // O PLAYER NAO TEM RAMPA: a palavra que o YouTube ja' desenhou fica como esta'.
  const playerLine = key !== null && key.indexOf('external:') === 0;
  paintWords(line.querySelector('.caption__confirmed'), confWords, 0, total, totalChanged,
    undefined, playerLine);
  // AND THE WORD REVEAL, on the newest word of the forming line — see
  // `paintChars`. `shownProv.length - 1` is `-1` for an empty tail, which is
  // exactly "nothing types": a line whose words have all settled is text the
  // model has stopped reconsidering, and retyping it would be a lie about what
  // just arrived.
  paintWords(line.querySelector('.caption__provisional'), shownProv,
    confWords.length, total, totalChanged, shownProv.length - 1, playerLine);
  const mark = line.querySelector('.caption__mark');
  // THE MARK FOLLOWS THE UNTRIMMED TAIL: the line IS still forming even while
  // its growing word is held back, and the marker is how the owner knows that.
  if (mark) mark.textContent = provWords.length ? '▍' : '';
  paintedWordsBySource.set(key, { confirmed: confWords, provisional: shownProv, total });
  // The forming line, whole. The floated caption shows the same sentence the panel
  // is forming — provisional words included, because that is what the owner is
  // watching. `meta` is null here: a provisional has no producer yet, and the
  // overlay keeps the last credits it was given rather than erasing them.
  if (window.SottoCaptionFloat) {
    window.SottoCaptionFloat.push((confWords.join(' ') + ' ' + shownProv.join(' ')).trim(), null);
  }
  // AND FOLLOW, because this is a GROWTH, not an append: the line gets taller
  // while the sentence is still being formed — the exact moment the owner is
  // watching. Following only on creation (above) left the newest words below the
  // fold for the whole interesting part of the line (measured 2026-10-07).
  followNewestLine();
  // ── THE PIXEL IS SERVED HERE, AND THIS IS THE ROW THAT SAYS SO ────────────
  // Emitted AFTER the words, the mark and the scroll: this is the instant the
  // text exists on screen and is what the owner's eye has. One row per paint,
  // carrying the
  // same identity the commit path keys the row by (`rowIdentity(source, start)`),
  // so `push -> paint` and `paint -> commit` are two numbers that can be read
  // apart instead of one number that can only be guessed. See
  // `noteProvisionalPaint` and `_main/panel-commit-stable-oracle.py`.
  noteProvisionalPaint(key, start,
    confWords.length, shownProv.length,
    (confWords.join(' ') + ' ' + shownProv.join(' ')).trim());
  // ── AND THE FROZEN SKIN, IF THIS THEME HAS ONE (owner, 2026-10-08) ────────
  // The same two word arrays, painted into the MOCKUP'S OWN caption plate instead
  // of ours (`skin-host.js`). `panel.js` stays the single source of the text: the
  // skin is told what to show, it never reads the bridge itself, so a broken skin
  // cannot corrupt the caption and every existing DOM oracle keeps its own DOM.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.live({ committed: confWords, provisional: provWords });
  }
}

/**
 * Drop ONE source's provisional line: its words are now committed text.
 *
 * `source` is the worker's key or `null` — the SAME key `renderProvisional` used,
 * so a commit for app A retires app A's open row and leaves app B's sentence on
 * screen (STEP 4). The lookup is the Map, never an attribute selector (a device
 * name contains `:`, quotes and backslashes).
 */
function retireProvisional(source) {
  if (!dom.list) return;
  const key = source === null || source === undefined ? null : String(source);
  const line = provisionalRows.get(key) || null;
  if (line && line.isConnected) dom.list.removeChild(line);
  provisionalRows.delete(key);
  paintedWordsBySource.delete(key);
  // THE BOX EMPTIED ITSELF: the placeholder comes back, so the owner is told
  // there is nothing to read instead of staring at an empty strip.
  syncCaptionBox();
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.live({ committed: [], provisional: [] });
  }
}

function wireCaptions() {
  // The follow is armed BEFORE the first caption can arrive: the scroll listener
  // is what keeps `stickToNewest` honest, and a panel that has never seen a
  // scroll event must still follow the newest line (that is the whole bug the
  // flag exists for).
  wireFollow();
  // `meta` carries the audio seconds. They are what let the engine tell a NEW
  // word from a RE-READ one, so they are not optional decoration.
  bridge.onCaption(({ text, meta }) => {
    // WHICH APP THIS IS (STEP 4). The worker stamps `source` on every caption
    // event (`proc:<pid>` / `device:<name>` / `file:<name>`) and OMITS it when
    // there is none. A non-empty string is the engine key; anything else is the
    // no-source engine — the same fail-closed reading `addCaption` uses for the row.
    const source = meta && typeof meta.source === 'string' && meta.source ? meta.source : null;
    engineFor(source).ingest(String(text || '').trim(), meta || {});
    // THE DEADLINE IS A FALLBACK, SO IT IS ARMED AFTER THE DECISION, NOT BEFORE
    // IT (2026-11-04). It used to be armed here unconditionally — "any fragment
    // at all means the stream is alive" — which made it the clock for lines the
    // worker had already proven (measured p50 1509 ms). `ingest` commits a
    // `stable:true` fragment, so there is nothing left to expire; this arms only
    // when a tail really is held.
    armHoldIfHeld();
  });
}

/**
 * THE PLAYER'S OWN CAPTIONS (YouTube/Stremio), on their own channel.
 *
 * The shell reads the line the player is painting and sends it here. Unlike
 * the ASR stream, these lines are ALREADY complete: each one REPLACES the live
 * box. `reset()` empties the per-source buffer, `ingest` shows exactly this
 * line, and `final` commits it once. Without the reset the engine appended the
 * new line to the previous partial and the history read
 * "previous. previous. current." (measured 2026-10-17).
 */
function wireExternalCaptions() {
  if (!bridge || typeof bridge.onExternalCaption !== 'function') return;
  bridge.onExternalCaption((payload) => {
    const text = String((payload && payload.text) || '').trim();
    if (!text) return;
    const meta = (payload && payload.meta) || {};
    const source = typeof meta.source === 'string' && meta.source
      ? meta.source : 'external:player';
    const engine = engineFor(source);
    engine.reset();
    engine.ingest(text, meta);
    // THE HOLD DEADLINE IS A PROPERTY OF THE LINE, NOT OF THE CHANNEL. The
    // timer was armed by the WORKER's channel only, so a line that came from
    // the PLAYER while the worker was quiet never got a deadline of its own --
    // and since the worker's status change no longer closes the player's line
    // (see `wireStatus`), the deadline is what keeps that line from being
    // stranded as a forming row. It is still armed AFTER `ingest` and only while
    // a tail is held (2026-11-04): the player is the fallback population — its
    // cues carry no `stable` stamp — so this is exactly the case the deadline
    // exists for, and `flush` below leaves nothing to expire.
    if (meta.final === true) engine.flush('external-final');
    armHoldIfHeld();
  });
}

/**
 * A committed caption line: final text, acknowledged, and recorded in history.
 *
 * `reason` is the rule that closed the line and `meta` is the route + the audio
 * position the engine stamped on it (M7/M8). Both travel to the store, which
 * writes them on the line — the transcript used to be written with no way at all
 * to tell a closed sentence from a fragment.
 */
function addCaption(text, reason, meta) {
  if (!text) return false;
  if (!dom.list) return false;

  // WHICH LINE THIS IS — `(source, start)`, not `start` alone (STEP 4).
  //
  // `start` is the worker's own segment identity: every partial of one segment
  // carries the same `start`. With TWO apps the same audio second exists in BOTH
  // streams, so `start` alone collides and one app's line REPLACES the other's.
  // The source is the other half of the identity (see `rowIdentity`).
  const source = meta && typeof meta.source === 'string' && meta.source ? meta.source : null;

  // Retire the open row of THIS source only — a commit for app A must not blank
  // app B's sentence while it is still forming (STEP 4).
  retireProvisional(source);

  const start = meta && typeof meta.start === 'number' ? meta.start : null;
  const identity = rowIdentity(source, start);
  let existing = identity === null ? null : committedByStart.get(identity) || null;
  // UMA LINHA QUE SO' CRESCE NAO ABRE UMA LINHA NOVA (2026-11-05). MEDIDO na
  // tela do dono (06:07:33-06:07:42): nove `<li>` para a MESMA frase, cada uma
  // com mais palavras que a anterior -- `Run to like max two max, three, but.`
  // / `... but running max.` / `... running max two max one.` O que ele le e'
  // *"historico completamente patetico"*, e a causa e' `meta.start` ausente:
  // `rowIdentity` devolve `null` sem `start`, `committedByStart` nunca mapeia e
  // CADA commit apendava. A regra abaixo e' a mesma do replace-in-place, so'
  // sem a chave: quando o texto novo CONTINUA o texto da ultima linha deste
  // source, e' a mesma frase a crescer -- e crescer nao e' dizer de novo.
  // Fecha nos dois sentidos (`A` prefixo de `B` e `B` prefixo de `A`), porque a
  // revisao tambem corta, e quando um commit chega SEM identidade nada aqui
  // toca numa linha que ja' pertence a um `start` conhecido.
  //
  // E UMA SO' LINHA PARA COMPARAR NAO CHEGA (medido a 2026-11-05: 51 de 200
  // linhas eram `A,B,A` EXACTAS). A linha S comeca com `start=None`, o primeiro
  // commit da linha SEGUINTE fica com o slot de "ultima linha", e o `final` de S
  // chega DEPOIS -- o prefixo e' comparado contra a linha errada e o texto que a
  // lista ja' tinha e' apendado de novo. Como 2371 de 3321 commits de hoje
  // chegaram sem `start` (71 %), a janela de comparacao passa a ser as ultimas
  // `DEDUPE_WINDOW` linhas DESTE source, e nao a ultima so'.
  if (!existing && identity === null) {
    for (const row of recentRowsForSource(source, DEDUPE_WINDOW)) {
      if (isPrefixExtension(rowText(row), text) || isPrefixExtension(text, rowText(row))) {
        existing = row;
        break;
      }
    }
  }
  if (existing && !existing.isConnected) committedByStart.delete(identity);
  const line = existing && existing.isConnected ? existing : document.createElement('li');

  if (typeof line.dataset === 'object' && line.dataset) {    line.dataset.start = start === null ? '' : String(start);
    // Read by `_main/_panel2-repeat-probe.js` and by the DOM probes: the identity
    // is an attribute of the row, so what a probe asserts is what a human sees.
    line.dataset.revision = existing ? 'true' : 'false';
    // The SOURCE half of the identity, for probes — UNSET when there is none, so
    // the no-source DOM stays byte-identical to before this change.
    if (source !== null) line.dataset.source = source;
    applyVoice(line, source);
  }

  if (existing) {
    // REPLACE IN PLACE — the owner's rule. The row keeps its position and its
    // timestamp (it is the same moment of audio), and only its text moves; the
    // corrected words are never shown next to the ones they correct. It also
    // keeps its ORDINAL: a revision is the same line said better, not a new one.
    const body = existing.querySelector('.caption__text');
    // S4's per-letter swap, applied EXACTLY as `_main/receipt-20261012-S4.md`
    // specifies it. The module keeps its own memory per element, so the animation
    // fires on a producer swap and on a real text change; the `else` branch keeps
    // the panel correct if the module has not loaded (it is deferred), and a line
    // with no producer stays plain text.
    if (window.SottoLetterSwap) {
      window.SottoLetterSwap.apply(body, null, text, {
        prevText: existing ? existing.getAttribute('data-text') : null,
        prevProducer: existing ? existing.getAttribute('data-producer') : null,
        producer: meta && meta.producer ? String(meta.producer) : null
      });
    } else if (body) {
      body.textContent = text;
    }
    if (existing && existing.getAttribute && existing.getAttribute('data-text') !== null) {
      existing.setAttribute('data-text', text);
    }
  } else {
    line.className = 'caption';
    // THE ORDINAL: a monotonic counter, so trimming `MAX_CAPTIONS` cannot
    // renumber what was said (see `lineOrdinal`). It is stamped on the ROW and
    // NOT PAINTED — the `bcast` direction's own index column was removed from the
    // screen at the owner's request (2026-10-08), twice, and it was the SAME
    // element on every row: *"nao é pra ter mais ele"*.
    lineOrdinal += 1;
    stampOrdinal(line, lineOrdinal);
    const time = document.createElement('span');
    time.className = 'caption__time';
    time.textContent = clockTime();
    const body = document.createElement('span');
    body.className = 'caption__text';
    body.textContent = text;
    line.append(time, body);
    dom.list.append(line);
    if (identity !== null) committedByStart.set(identity, line);
  }

  // Mark the newest line, drop the highlight from the previous one. A REVISED row
  // is the newest thing that happened, so the highlight follows the revision.
  const previous = dom.list.querySelector('.caption--latest');
  if (previous) previous.classList.remove('caption--latest');
  line.classList.add('caption--latest');

  while (dom.list.childElementCount > MAX_CAPTIONS) {
    const first = dom.list.firstElementChild;
    // The trimmed row leaves the index with it, or the map would hand a later
    // commit a node that is no longer in the box. The key is the TRIMMED ROW'S
    // OWN `(source, start)`, read back off the row — never the key of the line
    // being appended, which may belong to a different source (STEP 4).
    const trimmedSource = first && first.dataset && first.dataset.source ? first.dataset.source : null;
    const trimmedStart = first && first.dataset && first.dataset.start !== '' && first.dataset.start !== undefined
      ? Number(first.dataset.start)
      : null;
    const trimmedKey = rowIdentity(trimmedSource, trimmedStart);
    if (trimmedKey !== null) committedByStart.delete(trimmedKey);
    dom.list.removeChild(first);
  }

  // THE ROW IS IN THE LIST NOW, so the box can show it. This is the COMMITTED
  // path; the PROVISIONAL one calls the same function where it creates its row.
  syncCaptionBox();

  followNewestLine();
  updateLiveHint();
  recordHistory(text, reason, meta);
  bridge.captionApplied(text);
  // ── AND THE FLOATED CAPTION, IF IT IS ON (owner, 2026-10-12) ──────────────
  // The SAME closed line the panel just painted, with the meta THIS function was
  // given — which is what carries the producer credits into the overlay
  // (`caption-float.js` writes `#caption-float-credits` only when a meta arrives).
  // It belongs here, in the COMMIT path, and not in `renderProvisional`: there the
  // text is the two word arrays joined and `meta` is null. A copy of this line did
  // stand in `renderProvisional` and referenced a `text` binding that does not exist
  // in that scope — a ReferenceError on EVERY forming line, measured by
  // `_main/_s2-bar-dom-oracle.js` on 2026-10-12. `caption-float.js` ignores a repeat
  // of the sentence already on screen, so the two push sites cannot fight.
  if (window.SottoCaptionFloat) window.SottoCaptionFloat.push(text, meta || null);
  setStatus('Receiving captions', 'live');
  // The frozen skin's own history list gets the same closed line (see `skin-host.js`).
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.line({ text, time: clockTime(), via: viaOf({ via: meta && meta.via }) });
  }
  return true;
}

/** One follow per frame, never in the push: `scrollHeight` costs a layout. */
let followFrame = 0;
function followNewestLine() {
  if (!stickToNewest || !dom.captions || followFrame) return;
  if (typeof requestAnimationFrame !== 'function') return;
  followFrame = requestAnimationFrame(() => {
    followFrame = 0;
    pinLiveTranscriptToBottom();
  });
}

/**
 * The owner's scroll is the ONLY thing allowed to stop the follow, and coming
 * back to the bottom is the only thing allowed to restart it. `passive: true`
 * because this listener never cancels the scroll and must not delay it.
 */
function wireFollow() {
  if (!dom.captions) return;
  dom.captions.addEventListener('scroll', () => {
    const { scrollTop, scrollHeight, clientHeight } = dom.captions;
    // A box that grew after the pin is OUR lag, not his scroll (theme-4, measured):
    if (scrollHeight > pinnedHeight) return;
    stickToNewest = (scrollHeight - scrollTop - clientHeight) < 48;
  }, { passive: true });
}

// ---------------------------------------------------------------------------
// THE TRANSCRIPT NEVER SCROLLS TO THE TOP ON A THEME CHANGE (lane: caption)
// ---------------------------------------------------------------------------
// OWNER, 2026-10-12, verbatim: *"e nao e pra mudanca de design/tema/template ficar
// scrollando pra cima. e sempre mostrando o bottom do historico de transcript."*
//
// WHAT MOVES THE SCROLL WHEN A THEME CHANGES, measured in THIS document (the lane's
// own instrument is _main/caption-independent-oracle.js; the anchors below are the
// 2026-10-12 21:0x revision of each file):
//   * A theme write is `data-theme` on <html>, and the document carries THREE
//     observers on that one attribute — theme-tune.js:986, lazy-assets.js:266 and
//     skin-host.js:555 — the last two INJECT stylesheets into the live document. A
//     sheet that lands after the attribute write reflows the list: the scroll
//     position is kept, the CONTENT height is not, so the newest line leaves the view.
//   * A template/skin switch also HIDES the container outright:
//     `body[data-skin][data-surface="panel"] .history { display: none !important }`
//     (skin-layout.css:66-68), and `data-skin` is written on <body>
//     (skin-host.js:304). A scroll container that is not rendered has no position to
//     come back to, so the feed returns at its FIRST line.
//   * The panel's own re-render did it too: `renderFeed` ended with
//     `dom.historyList.scrollTop = 0` (this file, was :1642), and the strip surface
//     hides `.history` as well (panel.css:1456).
//
// THE RULE, in one place: after ANY theme/template/skin change the transcript
// container is at its BOTTOM, never at its top. The pin runs on the attribute write,
// on the next frame, twice on a short timer (a stylesheet that lands late reflows
// again) and on every stylesheet `load` — the event a template's own sheet fires.
// `load` does not bubble, hence the capture-phase listener.

/**
 * THE BOX THAT ACTUALLY SCROLLS THE TRANSCRIPT. MEASURED 2026-11-08
 * (`_main/panel-history-wheel-probe.mjs`): `#history-list` has `overflow-y:auto`
 * and `overscroll-behavior:contain`, but is painted `display:block`, so its box is
 * as tall as its content and never scrolls -- `contain` then swallows the wheel
 * before it reaches `.history__body`, which is the box that does scroll. So the
 * document is asked, never assumed: nearest ancestor (list included) whose
 * `overflow-y` scrolls; the one whose content overflows wins.
 */
function historyScroller() {
  const list = dom.historyList;
  if (!list) return null;
  let nearest = null;
  for (let node = list; node && node !== document.body && node !== document.documentElement;
    node = node.parentElement) {
    const y = getComputedStyle(node).overflowY;
    if (y !== 'auto' && y !== 'scroll' && y !== 'overlay') continue;
    if (!nearest) nearest = node;
    if (node.scrollHeight > node.clientHeight + 1) return node;
  }
  return nearest;
}

/**
 * THE WHEEL SCROLLS THE TRANSCRIPT (owner, 2026-11-08: *"eu nao consigo usar meu
 * scroll pra scrollar as legendas no historico."*). The listener is on the
 * SECTION, so a row, the space under the last one and the tools row all scroll
 * it. `preventDefault` only when the box moves, so an end of travel is not eaten;
 * `deltaMode` is honoured (a line-mode wheel reports lines, not pixels).
 *
 * ACCELERATION (owner, 2026-11-09, verbatim: *"eu quero APERTAR meu scroll e descer
 * rapidamente pra cima ou pra baixo no historico"*). One isolated notch is left
 * EXACTLY as before -- 1:1, the box moves what the wheel says -- because a wheel
 * that always jumps is unusable for reading. What changes is the BURST: notches
 * that arrive inside `WHEEL_BURST_MS` of each other grow the step (1x, 1.75x,
 * 2.5x ... capped at `WHEEL_GAIN_MAX`), so five quick notches cross a screen
 * instead of five lines. The step is capped at a fraction of the visible box so a
 * single event can never skip past what the eye can follow.
 *
 * `historyWheelStep` is PURE and takes `state` by value, so the oracle drives the
 * real arithmetic instead of re-deriving it from the constant names. */
const WHEEL_BURST_MS = 220;
const WHEEL_BURST_GAIN = 0.75;
const WHEEL_GAIN_MAX = 6;
const WHEEL_MAX_FRACTION = 0.75;

function historyWheelStep(deltaY, deltaMode, viewportH, state) {
  const direction = deltaY > 0 ? 1 : -1;
  const unit = deltaMode === 1 ? 16 : deltaMode === 2 ? viewportH : 1;
  const now = state.now || 0;
  const last = state.last || 0;
  const gap = last ? now - last : Infinity;
  const burst = gap <= WHEEL_BURST_MS ? (state.burst || 0) + 1 : 1;
  const gain = Math.min(WHEEL_GAIN_MAX, 1 + (burst - 1) * WHEEL_BURST_GAIN);
  const cap = Math.max(1, viewportH * WHEEL_MAX_FRACTION);
  let step = deltaY * unit * gain;
  if (Math.abs(step) > cap) step = direction * cap;
  return { step, burst, now, gain };
}

let _wheelState = { now: 0, burst: 0 };

function wireHistoryWheel() {
  const section = dom.transcript;
  if (!section) return;
  section.addEventListener('wheel', (event) => {
    if (!event.deltaY) return;
    const scroller = historyScroller();
    if (!scroller) return;
    const max = scroller.scrollHeight - scroller.clientHeight;
    if (max <= 0) return;
    const next0 = historyWheelStep(event.deltaY, event.deltaMode, scroller.clientHeight, {
      now: event.timeStamp || performance.now(),
      last: _wheelState.now,
      burst: _wheelState.burst,
    });
    _wheelState = { now: next0.now, burst: next0.burst };
    const next = Math.max(0, Math.min(max, scroller.scrollTop + next0.step));
    if (next === scroller.scrollTop) return;
    event.preventDefault();
    scroller.scrollTop = next;
  }, { passive: false });
  wireHistoryMiddleDrag(section);
}

/* "APERTAR O SCROLL" IS THE OTHER HALF OF THE ORDER: a middle-button press over the
 * transcript turns the panel into a grab surface -- 1 px of pointer is
 * `MIDDLE_DRAG_GAIN` px of transcript -- and the press is consumed so WebView2
 * never opens its autoscroll widget or pastes the clipboard into the field. Only a
 * press that STARTS on the transcript counts, and the drag stops on `mouseup`
 * anywhere (`window`), so a release outside the box cannot leave it stuck. */
const MIDDLE_DRAG_GAIN = 2.5;

function wireHistoryMiddleDrag(section) {
  let drag = null;
  section.addEventListener('mousedown', (event) => {
    if (event.button !== 1) return;
    const scroller = historyScroller();
    if (!scroller || scroller.scrollHeight - scroller.clientHeight <= 0) return;
    event.preventDefault();
    drag = { scroller, y: event.clientY, top: scroller.scrollTop };
  });
  section.addEventListener('auxclick', (event) => {
    if (event.button === 1) event.preventDefault();
  });
  window.addEventListener('mousemove', (event) => {
    if (!drag) return;
    const max = drag.scroller.scrollHeight - drag.scroller.clientHeight;
    drag.scroller.scrollTop = Math.max(0,
      Math.min(max, drag.top - (event.clientY - drag.y) * MIDDLE_DRAG_GAIN));
  });
  window.addEventListener('mouseup', (event) => {
    if (event.button === 1) drag = null;
  });
  window.addEventListener('blur', () => { drag = null; });
}

/**
 * THE KEYS SCROLL THE TRANSCRIPT. `PageUp`/`PageDown` move a page, `Home`/`End` the
 * ends, the arrows a line -- the same box the wheel owns, resolved by the same
 * document-driven `historyScroller()`. A key is left alone when it is typing
 * (`input`/`textarea`/`select`/contenteditable), when a modifier is held (the app's
 * own hotkeys), or when the box cannot move, so nothing is swallowed at an end of
 * travel. `preventDefault` only after the box actually moved.
 */
const HISTORY_KEY_STEP = 48;

function historyKeyDelta(event, scroller) {
  const page = Math.max(1, scroller.clientHeight - HISTORY_KEY_STEP);
  switch (event.key) {
    case 'PageDown': return page;
    case 'PageUp': return -page;
    case 'ArrowDown': return HISTORY_KEY_STEP;
    case 'ArrowUp': return -HISTORY_KEY_STEP;
    case 'End': return scroller.scrollHeight;
    case 'Home': return -scroller.scrollHeight;
    default: return 0;
  }
}

function wireHistoryKeys() {
  const section = dom.transcript;
  if (!section) return;
  section.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    const target = event.target;
    if (target && (target.isContentEditable
      || /^(input|textarea|select)$/i.test(target.tagName || ''))) return;
    const scroller = historyScroller();
    if (!scroller) return;
    const max = scroller.scrollHeight - scroller.clientHeight;
    if (max <= 0) return;
    const delta = historyKeyDelta(event, scroller);
    if (!delta) return;
    const next = Math.max(0, Math.min(max, scroller.scrollTop + delta));
    if (next === scroller.scrollTop) return;
    event.preventDefault();
    scroller.scrollTop = next;
  });
}

/**
 * The feed at its newest line. `force` for a fresh render or a layout change; an
 * ARRIVING line follows only while the reader is within `HISTORY_FOLLOW_SLACK` of
 * the bottom — pinning the real scroller (which this did not reach before
 * 2026-11-08) would otherwise yank the owner out of the old lines on every
 * committed caption.
 */
const HISTORY_FOLLOW_SLACK = 48;

function pinHistoryToBottom(force) {
  const scroller = historyScroller();
  if (!scroller) return false;
  const max = scroller.scrollHeight - scroller.clientHeight;
  if (max <= 0) return false;
  if (!force && max - scroller.scrollTop > HISTORY_FOLLOW_SLACK) return false;
  scroller.scrollTop = max;
  return true;
}

/**
 * The LIVE box at its newest line — but only while the owner is watching it.
 * `stickToNewest` is the older, deliberate rule (his own scroll is the only thing
 * allowed to stop the follow, see `wireFollow`); a theme change must not override it.
 */
function pinLiveTranscriptToBottom() {
  const box = dom.captions;
  if (!box || !stickToNewest) return false;
  box.scrollTop = box.scrollHeight, pinnedHeight = box.scrollHeight;
  return true;
}

/** Both transcript containers, one call. A layout change FORCES the feed: a theme
 *  switch rebuilds the scroller and its `scrollTop` returns as 0. */
function pinTranscriptsToBottom() {
  const feed = pinHistoryToBottom(true);
  const live = pinLiveTranscriptToBottom();
  return feed || live;
}

/**
 * Re-pin after a layout change: NOW, and once the layout has settled. The immediate
 * call is what the oracle measures; the deferred ones are what catch a stylesheet
 * that lands after the attribute write.
 */
function repinTranscriptsAfterLayoutChange() {
  pinTranscriptsToBottom();
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => pinTranscriptsToBottom());
  }
  setTimeout(() => pinTranscriptsToBottom(), 60);
  setTimeout(() => pinTranscriptsToBottom(), 300);
}

/** Arm the observers. A document without MutationObserver gets no pin and no throw. */
function wireThemeScrollGuard() {
  if (typeof MutationObserver !== 'function') return false;
  const root = document.documentElement;
  if (!root) return false;
  new MutationObserver(() => repinTranscriptsAfterLayoutChange())
    .observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  if (document.body) {
    new MutationObserver(() => repinTranscriptsAfterLayoutChange())
      .observe(document.body, {
        attributes: true,
        attributeFilter: ['data-skin', 'data-skin-theme', 'data-surface', 'data-float'],
      });
  }
  document.addEventListener('load', (event) => {
    const node = event.target;
    if (!node || node.tagName !== 'LINK') return;
    if (String(node.getAttribute('rel') || '').toLowerCase() !== 'stylesheet') return;
    repinTranscriptsAfterLayoutChange();
  }, true);
  return true;
}

/**
 * THE LIVE BOX'S ROW COUNT IS NOT PAINTED EITHER. It read `6 lines` / `400 lines`
 * in the bar above the captions — the second of the two counts the owner pointed
 * at (*"…400 lines… 400 lines…"*). The count is still computed here and still
 * available to a probe through the DOM (`#caption-list` children), it is simply
 * not written to the screen: the bar keeps the label and the "behind" chip, which
 * says something the owner can ACT on, and drops the tally.
 */
function updateLiveHint() {
  if (!dom.list) return;
  void dom.list.childElementCount;
  if (dom.captionsHint) dom.captionsHint.textContent = '';
}

// ---------------------------------------------------------------------------
// History — the top feed, its disk store, the search and the "show in folder".
// ---------------------------------------------------------------------------
// NOTE: this section's state (`historyEntries`, `selectedEntry`, `searchQuery`,
// `searchHits`, `canonicalProducer`) is declared ABOVE, before the init block
// that calls `wireHistory()` — see the temporal-dead-zone note there. Do not
// re-add declarations here: a second `let` of the same name in one scope is a
// SyntaxError that takes the whole panel down.

function wireHistory() {
  /* THE DRAWER HANDLE IS GONE (owner, 2026-10-14), and with it the `transcriptExpanded`
     flag and the function that read it: the drawer is always open now. Nothing here
     reads `#history-toggle`; it does not exist in the document. */

  if (dom.revealButton) {
    dom.revealButton.addEventListener('click', () => {
      // Disabled until a line is selected, so this is a belt-and-braces guard and
      // not the only thing standing between the owner and a stray explorer window.
      if (!selectedEntry) return;
      revealPath(selectedEntry.path);
    });
  }
  if (dom.historyRoot) dom.historyRoot.addEventListener('click', () => revealPath(null));
  markRevealState();
  wireViaFilters();

  if (!historyApi) {
    setHistoryNote(
      'Transcript unavailable: this shell has no store (nothing is written)',
    );
    if (dom.revealButton) dom.revealButton.disabled = true;
    loadHistoryFromMemory();
    return;
  }

  historyApi
    .root()
    .then((r) => {
      const root = (r && r.root) || (typeof r === 'string' ? r : '');
      if (root) {
        // THE FOLDER PATH IS NOT PAINTED. The owner quoted it as one of the
        // strings to take off the screen (*"'h sotto history 400 lines…'"*), and
        // it was the widest thing in the bar. The button KEEPS its capability —
        // it still opens the folder, and the path is still in its `title`, so a
        // hover names the place and a click goes there — but the bar itself shows
        // a folder affordance instead of a path. The path is also still in the
        // internal state (`historyRootPath`), which is what the probe reads.
        historyRootPath = root;
        if (dom.historyRoot) {
          dom.historyRoot.textContent = '';
          dom.historyRoot.title = `Open ${root}`;
        }
      }
      // D1 — WHO writes this feed, as the shell reports it. `null` (today) means
      // the section must collapse and say so. Read AFTER the tail so the note
      // carries both the writer and the row count; `applyTranscriptMode` runs
      // again from `renderFeed` for that reason.
      canonicalProducer = canonicalProducerOf(r);
      applyTranscriptMode();
    })
    .catch(() => {});

  loadHistory();
}

/** `{canonicalProducer}`, or a bare string, or nothing at all — never invented. */
function canonicalProducerOf(result) {
  if (typeof result === 'string') return result.trim() || null;
  const value = result && result.canonicalProducer;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/**
 * D1 — the transcript section's ONE state function.
 *
 * THE DRAWER IS ALWAYS OPEN (owner, 2026-11-06: *"é pra sempre aparecer no
 * painel"*), so there is no collapsed state and no flag to read: this function
 * paints the row count slot (hidden) and the note. THE CHEVRON THAT OPENED IT
 * BY HAND IS GONE (owner, 2026-10-14), and the search is a glyph now.
 */
function applyTranscriptMode() {
  const rows = historyEntries.length;

  if (dom.transcriptCount) {
    // THE THIRD COUNT SITE — the owner's own words suggested there was more than
    // one (*"400 lines… 400 lines…"*) and there were three: this one, the live
    // bar's tally and the note's prefix. All three stop painting. The element
    // stays in the DOM, hidden and empty, and `rows` is still the live state
    // (`historyEntries.length`), so nothing about the feed became unreadable to a
    // probe — only to the eye.
    dom.transcriptCount.textContent = '';
    dom.transcriptCount.hidden = true;
    void rows;
  }
  if (dom.transcriptNote) {
    const note = transcriptNoteText(rows);
    dom.transcriptNote.textContent = note;
    dom.transcriptNote.title = transcriptNoteTitle();
    // An empty note is HIDDEN, not left as a gap: the paragraph used to hold the
    // bar open for a sentence that is no longer painted.
    dom.transcriptNote.hidden = note === '';
  }
}

/**
 * THE COLLAPSED BAR CARRIES NO SENTENCE ANY MORE — the owner ruled, verbatim
 * (2026-10-08): *"tambem tira essas coisas como 'h sotto history 400 lines no
 * canonial writer 400 lines the transcript'"*. That is this line, the folder path
 * beside it and the row count above it: DIAGNOSTIC PROSE, painted where a product
 * sentence belongs. He had already had `Receiving captions` removed for the same
 * reason — the panel was telling him how it was built instead of what it heard.
 *
 * So the function is kept, still called, and still the ONE decision point, but it
 * now returns the empty string: the information is NOT lost, it moved to the
 * bar's `title` (a hover, i.e. something the owner asks for) and to the internal
 * state (`canonicalProducer`, `historyEntries.length`), which is exactly the
 * trade he offered: *"if it is useful for diagnosis, keep it in the internal
 * state but never on screen."* Nothing here invents a writer it does not have —
 * `transcriptNoteTitle` still refuses to claim one.
 */
function transcriptNoteText(rows) {
  void rows;
  return '';
}

/** The same sentence, unabbreviated, for the bar's tooltip. */
function transcriptNoteTitle() {
  return canonicalProducer
    ? `The canonical transcript is written by ${canonicalProducer}.`
    : 'Nothing writes the canonical transcript yet: the batch pass (Parakeet Redux) '
      + 'does not exist on this box, so the live engine\'s lines are refused here by design.';
}

/**
 * D5 — the "Show in folder" button is honest about what it can do: it opens the
 * SELECTED line, so with no selection it is disabled and says what to do first.
 * The folder path button next to it needs no selection and is always live.
 */
function markRevealState() {
  if (!dom.revealButton) return;
  const has = Boolean(selectedEntry);
  dom.revealButton.disabled = !has || !historyApi;
  dom.revealButton.title = has && selectedEntry.path
    ? `Show ${selectedEntry.path} in the OS file manager`
    : has
      ? 'Show the transcript folder in the OS file manager'
      : 'Select a transcript line first · this button opens the selected line';
}

/**
 * A LINHA E' UMA, E TEM UM NOME (2026-11-14).
 *
 * O ficheiro e o relogio da linha sao a identidade que as DUAS metades ja'
 * carregam: o `history_tail` devolve `{date, hour, time, path}` e o
 * `history_append` devolve o MESMO par para a linha que acabou de gravar. Era
 * a unica coisa que os dois caminhos tinham em comum e ninguem usava: o
 * `loadHistory` substituia a lista inteira (`historyEntries = entries`) e o
 * `pushEntry` so' olhava para o `action` do store. Resultado medido no arquivo
 * do dono: a mesma linha entrava DUAS vezes quando o `tail` resolvia depois de
 * a linha ao vivo ter chegado (as duas copias existiam no ficheiro E na lista),
 * e uma linha que chegava durante a leitura era APAGADA pela substituicao.
 */
function feedKey(entry) {
  if (!entry || typeof entry !== 'object') return null;
  const time = String(entry.time || '').trim();
  const date = String(entry.date || '').trim();
  // SEM DIA NAO HA' IDENTIDADE. So' o store carimba `date`/`path`; a linha de
  // recurso (shell sem store) traz so' a hora, e duas falas no mesmo segundo
  // sao duas linhas -- fundi-las apagava uma delas.
  if (!time || !date) return null;
  return `${entry.path || ''}\u0000${date}\u0000${time}`;
}

/** A MESMA LINHA NUNCA ENCOLHE (mesma regra que o store ja' aplica ao ficheiro). */
function longerOf(a, b) {
  const la = String((a && a.text) || '').length;
  const lb = String((b && b.text) || '').length;
  return lb > la ? b : a;
}

/**
 * A CAUDA NAO APAGA O QUE CHEGOU DEPOIS DELA.
 *
 * `history_entries` le o disco no instante do pedido; tudo o que o painel
 * gravou DEPOIS desse instante nao esta' nessa leitura. Substituir a lista pela
 * resposta era por isso uma perda garantida sempre que uma legenda fechava
 * durante os ~centenas de ms da leitura -- e uma duplicata garantida para a
 * linha que ja' estava no ficheiro E na lista. A fusao e' por `feedKey`, e em
 * caso de colisao fica o texto MAIOR.
 */
function mergeHistoryTail(stored, live) {
  const out = Array.isArray(stored) ? stored.slice() : [];
  const at = new Map();
  out.forEach((entry, i) => {
    const key = feedKey(entry);
    if (key) at.set(key, i);
  });
  for (const entry of (Array.isArray(live) ? live : [])) {
    const key = feedKey(entry);
    if (key && at.has(key)) {
      const i = at.get(key);
      out[i] = longerOf(out[i], entry);
      continue;
    }
    if (key) at.set(key, out.length);
    out.push(entry);
  }
  return out;
}

/**
 * A CAUDA ENTRA NA LISTA, NAO A SUBSTITUI.
 *
 * Funcao propria porque a cauda e' ASSINCRONA: entram linhas ao vivo enquanto a
 * leitura decorre, e o que chega DEPOIS tem de sobreviver. Separada, o braco
 * `_main/panel-row-identity-oracle.js` (CHK-G/CHK-H) corre exactamente este
 * caminho e o mutante M5 (`historyEntries = entries`) fica vermelho; enterrada
 * no `.then()`, o braco so' conseguia chamar `mergeHistoryTail` e nao a
 * atribuicao que era o defeito.
 */
function applyHistoryTail(entries) {
  // A FUSAO, NAO A SUBSTITUICAO (ver `mergeHistoryTail`).
  historyEntries = mergeHistoryTail(entries, historyEntries);
  while (historyEntries.length > MAX_HISTORY) historyEntries.shift();
  renderFeed();
}

function loadHistory() {
  if (!historyApi || !historyApi.tail) return;
  historyApi
    .tail(HISTORY_LOAD)
    .then((r) => {
      applyHistoryTail(normaliseEntries(r));
    })
    .catch((err) => setHistoryNote('Transcript read failed: ' + errorText(err)));
}

/** A shell that has no history store still shows the captions it saw this run. */
function loadHistoryFromMemory() {
  renderFeed();
}

/**
 * THE VIEWING CONTEXT OF A LINE (owner, 2026-11-09). Each transcription keeps a
 * COMPACT record of what the audio was and what was in front of him: the app
 * that produced the sound, the audio source, and the foreground app/title/URL.
 *
 * The names are the contract with the history owner
 * (`.agent-work/history-ui-contract.md`): `sourceApp`, `audioSource`,
 * `viewingApp`, `viewingTitle`, `viewingUrl`. This function is the ONE place
 * that bounds them, because the values come from a bridge payload and a title
 * can be a whole sentence. Empty means ABSENT -- a field is never invented, and
 * a context with no field at all is `null`, not `{}`.
 */
const CONTEXT_FIELDS = [
  ['sourceApp', 60],
  ['audioSource', 120],
  ['viewingApp', 60],
  ['viewingTitle', 200],
  ['viewingUrl', 512],
];

function normaliseContext(meta) {
  const raw = meta && meta.context;
  if (!raw || typeof raw !== 'object') return null;
  const out = {};
  for (const [key, limit] of CONTEXT_FIELDS) {
    const value = raw[key];
    if (typeof value !== 'string') continue;
    const text = value.replace(/\s+/g, ' ').trim().slice(0, limit);
    if (text) out[key] = text;
  }
  return Object.keys(out).length ? out : null;
}

/** One short sentence for the row's tooltip and for search context. */
function contextSummary(entry) {
  const ctx = entry && entry.context;
  if (!ctx || typeof ctx !== 'object') return '';
  const parts = [];
  if (ctx.audioSource) parts.push(ctx.audioSource);
  else if (ctx.sourceApp) parts.push(ctx.sourceApp);
  if (ctx.viewingTitle) {
    parts.push(ctx.viewingApp ? `${ctx.viewingApp}: ${ctx.viewingTitle}` : ctx.viewingTitle);
  } else if (ctx.viewingApp) {
    parts.push(ctx.viewingApp);
  }
  if (ctx.viewingUrl) parts.push(ctx.viewingUrl);
  return parts.join(' · ');
}

/**
 * Record a committed caption. The shell is the source of truth for the file
 * path (it names the folder), so the entry it returns is what the feed stores;
 * if the store is absent or fails, the caption still appears in the feed with
 * no path, and the failure is stated rather than hidden.
 */
function recordHistory(text, reason, meta) {
  // M8 — the line's provenance, as the store writes it on disk:
  //   route   which road closed this line: `final` (the worker's second pass
  //           over the whole segment, M3) or `provisional-draft` (a terminal
  //           flush of a line the worker never closed).
  //   start   the worker's LINE identity in audio seconds — the worker's own
  //           `start` field (`sotto_worker.py:_event`), not a panel invention.
  //   reason  the rule that fired at the moment of the write, which the panel
  //           already received and dropped.
  //
  // OWNER 2026-10-06, verbatim: "o historico simplesmente mostra a legenda ao
  // vivo, inves de mostrar a versao processada pelo redux."
  //
  // The transcript carries ONLY a line the WORKER closed (`route=final`: the
  // second pass over the whole segment, M3). A `provisional-draft` IS the live
  // caption — the box may show it, the history may not — and it used to reach
  // the file through `flush('status-change')` (see `wireStatus` below), which
  // fires on every worker status while this worker restarts constantly.
  // MEASURED in the owner's own `history/2026-10-06/10.md`: 9 of the 13 lines
  // written after the 2026-10-06 cure are
  // `route=provisional-draft reason=status-change`, word for word the live box
  // ("Em", "Antes dos", "Simplesmente", ...). See docs/audit/historico-vs-redux.md.
  // FAIL-CLOSED (owner 2026-10-06). The engine stamps every commit with the
  // route it derived from the worker's `final` flag (caption-formulation.js
  // `commit`): 'final' = the line the WORKER closed (its second pass — the
  // "redux" line the transcript carries), 'provisional-draft' = the LIVE
  // caption, which the box paints and the transcript may NEVER take.
  //
  // An ABSENT route is NOT a final line. The old `(meta && meta.route) ||
  // 'final'` default made this guard VACUOUS — MEASURED 2026-10-06: every
  // commit arrived with `route=null` and every one was written, so the WHOLE
  // live caption reached the transcript (the defect the owner reported).
  // THE ROUTE IS DERIVED, NOT DEMANDED (2026-11-01). This used to be
  //   const route = meta && meta.route;
  //   if (route !== 'final') return;          // <- refused FIRST
  // and the BATCH engine emits no route at all (`worker/redux_batch.py:185`),
  // so a parakeet line died one statement before the guard that accepts it. The
  // decision now lives in the DOM-free predicate, so the oracle executes THIS
  // rule: `provisional-draft` refused always, a canonical (batch) line recorded
  // as `batch`, a CLOSED line recorded as `final`. The producer is no longer an
  // admission gate — it is provenance, written as `producer=` (2026-11-05).
  const sourceApi = window.SottoHistorySource;
  const route = sourceApi && sourceApi.transcriptRoute
    ? sourceApi.transcriptRoute(meta)
    : null;
  // A REFUSAL THAT CANNOT SAY ITS NAME IS NOT AN ANSWER (2026-11-05). This used
  // to be `if (!route) return;` and, behind it, a SECOND gate
  // (`isCanonicalLine`) that only a `producer:'redux'` line could pass — and the
  // batch pass is off by default, so on this box the transcript had ZERO writers.
  // MEASURED on the owner's own run: 3830 `CAPTION_APPLIED`, 0 `HISTORY_APPEND`,
  // `history/2026-11-05/` absent, and not one refusal line in the log.
  // The decision (which routes may enter) lives in `history-source.js`; this
  // choke point only reports it. Owner 2026-10-07's separation is now PROVENANCE,
  // not admission: the store writes `producer=` on every line, so a Parakeet line
  // and a streaming line stay tellable apart — see `_history_provenance`.
  if (!route) {
    reportHistoryRefusal(sourceApi, meta);
    return;
  }
  // WHICH branch produced that `route` — the FALLBACK must ANNOUNCE itself
  // (P1 `4fb5b25380cbc8269977e22e`). `'worker-stamped'` = a worker vote decided
  // it (the worker's `final` flag); `'fallback'` = NO worker stamp was seen and
  // `caption-formulation.js routeFor`'s else-half MANUFACTURED this `final`.
  // The store writes it on the line as `src=`, so a transcript of `src=fallback`
  // is the de-landing, readable without running the panel. Absent meta keeps it
  // null: the field is never invented here.
  const routeSource = meta && typeof meta.routeSource === 'string' ? meta.routeSource : null;
  // WHO produced this line. It is NOT a gate any more (see the decision above);
  // it is the field the store writes as `producer=`, so the 2026-10-07 separation
  // survives as a FACT ON THE LINE instead of as a reason to drop it. Absent when
  // the worker declared nothing — the field is never invented.
  const producer = sourceApi && sourceApi.producerOf
    ? sourceApi.producerOf(meta)
    : null;
  const options = {
    source: producer || 'live',
    producer,
    // DE ONDE VEIO O SOM (2026-11-09): `via=` na linha, e a unica coisa que os
    // dois filtros do historico leem. Derivado do MESMO meta que decide a rota,
    // logo um item de audio nunca chega ao store sem origem.
    via: sourceApi && sourceApi.viaOf ? sourceApi.viaOf(meta) : null,
    route,
    routeSource,
    start: meta && typeof meta.start === 'number' ? meta.start : null,
    reason: reason || '',
    context: normaliseContext(meta),
  };
  // M8 — what the FILE gets. Usually the same string the box shows; for a line
  // the worker never closed the engine hands a `fileText` without the terminal
  // mark it would otherwise have INVENTED, so the transcript cannot dress a
  // fragment as a closed sentence.
  const body = meta && typeof meta.fileText === 'string' && meta.fileText
    ? meta.fileText
    : text;
  if (!historyApi || !historyApi.append) {
    /* THE FALLBACK KEEPS THE CONTEXT (2026-11-09). A row that lost it in the
     * no-store path would be the only row on screen with no `data-context` and no
     * tooltip, and the owner would read that as the context never being captured. */
    pushEntry({ time: clockTime(), text: body, path: null, context: options.context });
    return;
  }
  historyApi
    .append(body, options)
    .then((r) => {
      const entry = (r && r.entry) || null;
      // O STORE MANDA (2026-11-04). `null` = a linha foi RECUSADA
      // (`provisional-draft`, `route` nao canonica) e o painel NAO inventa uma
      // linha de recurso -- era metade das repeticoes que o dono fotografou
      // (`pushEntry(entry || {time, text, path: null})`), com o ficheiro certo
      // e a lista dobrada. `action='skip'` (a mesma linha outra vez) tambem sai
      // por aqui, e quem o aplica e' `pushEntry`.
      if (!entry) return;
      pushEntry(entry);
    })
    .catch((err) => {
      setHistoryNote('History write failed: ' + errorText(err));
      pushEntry({ time: clockTime(), text, path: null, context: options.context });
    });
}

/**
 * EVERY REFUSAL LEAVES A LINE (2026-11-05).
 *
 * The choke point above used to `return` and nothing else. That is how the
 * transcript stayed empty for a day with 3830 captions painted and not one
 * `HISTORY_*` line to explain it: a gate that cannot say no is not a gate.
 * The shell writes `HISTORY_REFUSED reason=… route=… producer=… src=… n=…`
 * (`SottoHost._history_refused`), counted per signature so the same refusal logs
 * on its first occurrence and every 50th after that.
 */
function reportHistoryRefusal(sourceApi, meta) {
  historyRefusals += 1;
  const info = (sourceApi && sourceApi.historyRefusal ? sourceApi.historyRefusal(meta) : null)
    || { reason: 'no-source-module', route: null, producer: null, src: null };
  const key = [info.reason, info.route, info.producer, info.src].join('\u0000');
  const n = (historyRefusalSeen.get(key) || 0) + 1;
  historyRefusalSeen.set(key, n);
  if (n !== 1 && n % 50 !== 0) return;
  if (!bridge || typeof bridge.historyRefused !== 'function') return;
  bridge.historyRefused({
    where: 'panel/recordHistory',
    reason: info.reason,
    route: info.route,
    // THE WORKER'S OWN VOTE, when the meta carries one: `route` is what the
    // panel DERIVED, `final` is what the worker SAID, and a reader who has only
    // the log must be able to tell the two apart without re-deriving the chain.
    final: meta && typeof meta.final === 'boolean' ? meta.final : null,
    producer: info.producer,
    src: info.src,
    n,
    total: historyRefusals,
  });
}

function pushEntry(entry) {
  const action = entry && typeof entry.action === 'string' ? entry.action : 'append';
  // A LISTA NAO E' UM LOG DE EVENTOS (dono, 2026-11-04). A decisao vem do
  // store (`sotto_webview.history_merge`): `skip` = a mesma linha outra vez,
  // `replace` = a mesma linha ainda a crescer (reescreve a ultima), `append` =
  // linha nova. Sem isto o painel duplicava a frase que ele fotografou seis
  // vezes, e o ficheiro ja' tinha a regra certa.
  if (action === 'skip') return;
  // ── A MESMA LINHA NAO ENTRA DUAS VEZES (2026-11-14) ──────────────────────
  // O store pode dizer `append` para uma linha que o painel JA' tem: a cauda
  // lida (`history_tail`) pode conter esta mesma linha, ou uma re-entrega da
  // ponte pode repetir o commit. `feedKey` e' o nome da linha nos DOIS
  // caminhos, logo e' ele que decide, antes do `action`.
  //
  // `replace_at` (a fusao dos dois motores, `history_append`) devolve a entrada
  // escrita com `action='replace_at'` e NAO diz o indice a que pertence; o
  // `replaceFeedRow` antigo reescrevia a ULTIMA linha, o que numa fusao de lote
  // reescrevia a linha errada. Com a chave, o painel reescreve a linha que o
  // store realmente reescreveu; sem a chave na lista, e' uma linha nova.
  const key = feedKey(entry);
  const at = key === null ? -1 : historyEntries.findIndex((row) => feedKey(row) === key);
  // `replace` = the store rewrote its LAST line (a line still growing), so the
  // panel rewrites its last row. `replace_at` = the store rewrote a line in the
  // MIDDLE (the batch pass said it better); that one is named by `feedKey`, and
  // an old row the panel never loaded is appended because there is no row to
  // rewrite -- never the last row, which belongs to a different sentence.
  const merging = action === 'replace' && !searchQuery && historyEntries.length > 0;
  if (at >= 0) {
    // A LINHA JA' EXISTE: reescreve-se onde esta', nunca se acrescenta.
    historyEntries[at] = merging || action === 'replace_at'
      ? longerOf(historyEntries[at], entry)
      : entry;
  } else if (merging) {
    historyEntries[historyEntries.length - 1] = longerOf(historyEntries[historyEntries.length - 1], entry);
  } else {
    historyEntries.push(entry);
  }
  while (historyEntries.length > MAX_HISTORY) historyEntries.shift();

  if (searchQuery) {
    /* THE CONTEXT MATCHES TOO, or an open search view silently drops a line that
     * the store's own search would return: the same query, two answers, depending
     * on whether the line arrived before or after the search was opened. */
    if (viaVisible(entry)
      && (matches(entry.text, searchQuery) || matches(contextSummary(entry), searchQuery))) {
      searchHits = [entry].concat(searchHits);
      renderSearchResults(searchQuery, searchHits);
    }
    return;
  }
  /* A FILTERED FEED IS REBUILT, NOT PATCHED. The incremental path below can
   * only grow the tail; with a source hidden, the row that belongs at the tail
   * may be a different entry, so the one writer that knows the whole predicate
   * (`renderFeed`) paints it. With both sources on, the cheap path stands. */
  if (!viaVisible(entry) || viaFilter.pc === false || viaFilter.youtube === false) {
    renderFeed();
    return;
  }
  // A NEW LINE IS PAINTED AS IT ARRIVES (owner, 2026-11-06): *"é pra sempre
  // aparecer no painel"*. The gallery bucket that used to gate this is gone, so
  // there is no "outside the open bucket" case left: a line either grows the row
  // it belongs to (`merge`) or appends a new one.
  if (at >= 0) replaceFeedRow(entry);
  else if (merging && action === 'replace') replaceFeedRow(entry);
  else appendFeedRow(entry);
}

/**
 * THE WINDOW IS ONE PREDICATE, FOR THE FEED AND FOR THE SEARCH ALIKE.
 *
 * Measured 2026-11-09: the feed filtered by `HISTORY_RETENTION_H` and the search
 * results did NOT, so a query the shell still answered with a line older than
 * the window painted a row the feed would never show. The store prunes lazily
 * (`_history_prune` runs on append), so "the disk has no such line" is not a
 * fact the panel may assume. One predicate, used by both readers.
 */
function withinHistoryWindow(entry) {
  const at = entryAt(entry);
  return !Number.isFinite(at) || at >= Date.now() - HISTORY_RETENTION_H * 3600 * 1000;
}

/** `pc` | `youtube` for one entry; a line from before the contract is `pc`.
 *
 * THE FILE MAY SAY THREE THINGS (2026-11-09): `pc`, `youtube`, `external`. The
 * third is a player that is NOT the YouTube tab (Stremio, VLC) -- the same
 * external channel, a different origin -- and the two BUTTONS are
 * "what came from the machine" and "what came from a video", so `external`
 * belongs to the video button. It stays a separate word ON THE LINE so a later
 * reader can tell the two apart without re-running the tick that produced it.
 */
function viaOf(entry) {
  const value = String((entry && entry.via) || '').trim().toLowerCase();
  if (value === 'youtube' || value === 'external') return 'youtube';
  return 'pc';
}

/** Is this entry admitted by the two source buttons? Missing = `pc`. */
function viaVisible(entry) {
  return viaFilter[viaOf(entry)] !== false;
}

/** Repaint the two source buttons from `viaFilter`, never from the DOM. */
function paintViaFilters() {
  for (const via of VIA_KEYS) {
    const button = document.getElementById(`history-filter-${via}`);
    if (!button) continue;
    const on = viaFilter[via] !== false;
    button.setAttribute('aria-pressed', on ? 'true' : 'false');
    button.classList.toggle('is-off', !on);
  }
  // ONE POLICY, TWO LISTS: the design's own frozen list obeys the same buttons.
  if (window.SottoSkin && typeof SottoSkin.filterVia === 'function') {
    SottoSkin.filterVia({ pc: viaFilter.pc !== false, youtube: viaFilter.youtube !== false });
  }
}

/** Repaint the one list writer. Search view and feed view are the same slot. */
function repaintFeedForFilter() {
  if (searchQuery) renderSearchResults(searchQuery, searchHits);
  else renderFeed();
}

/** One button: flip its own source; NEVER let both sources end up off. */
function toggleViaFilter(via) {
  if (!VIA_KEYS.includes(via)) return;
  const next = viaFilter[via] === false;
  viaFilter[via] = next;
  if (!next) {
    const other = via === 'pc' ? 'youtube' : 'pc';
    if (viaFilter[other] === false) viaFilter[other] = true;
  }
  paintViaFilters();
  repaintFeedForFilter();
}

/** Bind the two buttons once, at wire time (`wireHistory`). */
function wireViaFilters() {
  for (const via of VIA_KEYS) {
    const button = document.getElementById(`history-filter-${via}`);
    if (!button) continue;
    button.addEventListener('click', () => toggleViaFilter(via));
  }
  paintViaFilters();
}

/**
 * THE FEED PAINTS ITSELF (owner, 2026-11-06), and it is the ONLY writer of
 * `#history-list`.
 *
 * Verbatim: *"o historico tem que persistir, aparecendo no painel da direita, por
 * padrao, ate 48hrs ... e nao é pra começar a ativar o historico so quando eu
 * mostro o painel. é pra sempre aparecer no painel."* and *"tambem tira a data de
 * mostrar o historico do painel na direita."*
 *
 * WHAT STOOD HERE was the day/hour gallery: `24h`/`1h` ranges plus a chip per day
 * and per hour, and the list stayed EMPTY until one was pressed. It is deleted —
 * the markup, the counters, the pick state and the module that bucketed the
 * entries — because the owner stopped asking to navigate the store and started
 * asking to see it. The list shows the SAME window the shell keeps on disk
 * (`HISTORY_RETENTION_H`, 180 days since 2026-11-09) and follows the newest line
 * from then on (`appendFeedRow` / `replaceFeedRow`).
 *
 * WHY A WINDOW AND WHY IT IS CHEAP: the shell already tails the store
 * (`HISTORY_LOAD` lines) and prunes day files past the same window
 * (`HISTORY_RETENTION_H`), so this is a filter over what was already read, not a
 * second pass over the disk.
 *
 * NO EMPTY STATE IS WRITTEN ANY MORE (owner, 2026-11-09: *"NO EXPLANATORY PROSE
 * IN ANY PANEL"*). This function used to append a `<li class="history__empty">`
 * saying "No transcript yet." / "No transcript store in this shell."; the owner
 * reads an empty feed as an empty feed and does not want a sentence about it.
 * The element is gone, so there is no second writer a render path can leave
 * behind while rows exist.
 */
function renderFeed() {
  if (!dom.historyList) return;
  clearList();
  const rows = historyEntries.filter(withinHistoryWindow).filter(viaVisible);
  for (const entry of rows) dom.historyList.append(makeRow(entry));
  // NEVER THE TOP (owner, 2026-10-12): *"e sempre mostrando o bottom do historico
  // de transcript."* One function, used by the render path and the theme guard.
  pinHistoryToBottom(true);
  applyTranscriptMode();
}

function appendFeedRow(entry) {
  if (!dom.historyList || !viaVisible(entry)) return;
  const emptyNote = dom.historyList.querySelector('.history__empty');
  if (emptyNote) emptyNote.remove();
  dom.historyList.append(makeRow(entry));
  pinHistoryToBottom();
  applyTranscriptMode();
}

/**
 * REESCREVE a ultima linha da lista em vez de acrescentar outra (dono,
 * 2026-11-04, verbatim: *"o historico da legenda e completamente IMBECIL na
 * logica. fica duplicando frase. fica dando append ou sei la"*).
 *
 * Quem DECIDE e' o store (`sotto_webview.history_merge`), que devolve
 * `action='replace'` para a mesma linha a crescer; aqui so' se aplica. Sem
 * isto o ficheiro ficava com uma linha e o painel com seis, que foi o que ele
 * fotografou (10:01:44 -> 10:01:57, a mesma frase seis vezes).
 */
function replaceFeedRow(entry) {
  if (!dom.historyList) return;
  const rows = dom.historyList.querySelectorAll('[data-history-row]');
  // A LINHA NOMEADA, NAO A ULTIMA (2026-11-14). O store devolve
  // `action='replace_at'` quando a fusao dos dois motores reescreveu uma linha do
  // MEIO do ficheiro; reescrever a ultima `<li>` punha o texto do lote em cima de
  // outra frase e deixava a linha corrigida por corrigir -- duas frases trocadas
  // no ecra com o ficheiro certo. A chave e' a mesma dos dois caminhos
  // (`feedKey`), e o fallback para a ultima linha fica so' para quando a entrada
  // nao tem nome (a linha ao vivo, que ainda nao foi gravada).
  const key = feedKey(entry);
  let target = null;
  if (key !== null) {
    for (const row of rows) {
      if (row.dataset && row.dataset.historyKey === key) { target = row; break; }
    }
  }
  const last = target || (rows.length ? rows[rows.length - 1] : null);
  if (!last) {
    appendFeedRow(entry);
    return;
  }
  const fresh = makeRow(entry);
  fresh.setAttribute('data-history-row', '1');
  last.replaceWith(fresh);
  pinHistoryToBottom();
  applyTranscriptMode();
}


function clearList() {
  if (!dom.historyList) return;
  dom.historyList.replaceChildren();
}

/** One row of the feed: timestamp, text, and a per-entry "show in folder". */
function makeRow(entry, hitQuery) {
  const li = document.createElement('li');
  li.className = 'hist';
  li.tabIndex = 0;
  //: A MARCA DA LINHA, para `replaceFeedRow` saber QUAL reescrever quando o
  //: store diz que a mesma linha cresceu (ver `replaceFeedRow`).
  li.dataset.historyRow = '1';
  //: WHERE THE LINE CAME FROM (owner, 2026-11-09): `pc` or `youtube`, from the
  //: same contract the two filter buttons read. On the row so a gate can count
  //: what was filtered without re-parsing the store.
  li.dataset.via = viaOf(entry);
  //: O NOME DA LINHA NA LISTA (2026-11-14): o mesmo `feedKey` que a cauda lida e
  //: a linha ao vivo partilham, para `replaceFeedRow` reescrever a linha NOMEADA
  //: em vez da ultima. So' quando a entrada tem dia+hora (as linhas do store).
  const rowKey = feedKey(entry);
  if (rowKey !== null) li.dataset.historyKey = rowKey;
  if (entry.path) li.dataset.path = entry.path;
  if (selectedEntry && sameEntry(selectedEntry, entry)) li.classList.add('hist--selected');

  const time = document.createElement('span');
  time.className = 'hist__time';
  time.textContent = stampFor(entry);
  //: O DIA NAO ENTRA NA FAIXA -- E AGORA ELE E' RECUPERAVEL (2026-11-09). A ordem
  //: de 2026-11-06 tirou a data do chip porque a janela era 48 h e o dia era
  //: contexto que ele ja' tinha. Com 180 dias essa premissa caiu: uma linha de
  //: 150 dias atras mostra so' `HH:MM:SS` e fica indistinguivel da de hoje. O
  //: chip continua exactamente o que ele mandou (nada de novo no ecra) e o dia
  //: viaja no `title`, que so' aparece quando ele para o rato na linha.
  const fullStamp = fullStampFor(entry);
  if (fullStamp) time.title = fullStamp;

  const text = document.createElement('span');
  text.className = 'hist__text';
  if (hitQuery) {
    for (const part of highlight(String(entry.text || ''), hitQuery)) {
      if (typeof part === 'string') text.append(document.createTextNode(part));
      else {
        const mark = document.createElement('mark');
        mark.textContent = part.mark;
        text.append(mark);
      }
    }
  } else {
    text.textContent = entry.text || '';
  }

  const folder = document.createElement('button');
  folder.type = 'button';
  folder.className = 'hist__folder';
  folder.title = entry.path ? `Show ${entry.path} in folder` : 'Show in folder';
  folder.setAttribute('aria-label', 'Show in folder');
  // D6 — the SAME 16x16 stroke folder as `#reveal-button` in the tools row. This
  // used to be `\u{1F4C1}`, an emoji: its glyph, weight and vertical metrics were
  // whatever Windows' emoji font decided, next to a panel built out of hairline
  // SVGs.
  folder.append(icon('M1.5 4.2a1 1 0 0 1 1-1h3.1l1.3 1.4h5.6a1 1 0 0 1 1 1v6.2a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1z', 1.3));
  folder.addEventListener('click', (event) => {
    event.stopPropagation();
    select(entry);
    revealPath(entry.path);
  });

  // THE VIEWING CONTEXT RIDES ON THE ROW (owner, 2026-11-09). It is one compact
  // sentence, never a new column: the tooltip carries it, `data-context` lets a
  // gate read it, and when the SEARCH matched the context rather than the words
  // the context is painted under the line with the match marked -- otherwise a
  // hit would look like a line that does not contain the query.
  const ctxSummary = contextSummary(entry);
  if (ctxSummary) {
    li.dataset.context = ctxSummary;
    li.title = ctxSummary;
    text.title = ctxSummary;
    if (hitQuery && !matches(entry.text, hitQuery) && matches(ctxSummary, hitQuery)) {
      const note = document.createElement('span');
      note.className = 'hist__ctx';
      for (const part of highlight(ctxSummary, hitQuery)) {
        if (typeof part === 'string') {
          note.append(document.createTextNode(part));
        } else {
          const mark = document.createElement('mark');
          mark.textContent = part.mark;
          note.append(mark);
        }
      }
      text.append(note);
    }
  }

  li.append(time, text, folder);
  li.addEventListener('click', () => select(entry));
  li.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      select(entry);
    }
  });
  return li;
}

/**
 * An inline SVG icon from the panel's one icon set: 16x16, `currentColor`,
 * hairline stroke, no fill. `d` is the path, `width` the stroke width.
 */
function icon(d, width) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', String(width));
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  svg.append(path);
  return svg;
}

function select(entry) {
  selectedEntry = entry;
  if (!dom.historyList) { markRevealState(); return; }
  for (const row of dom.historyList.querySelectorAll('.hist')) {
    const same = row.dataset.path && entry.path && row.dataset.path === entry.path
      && row.querySelector('.hist__text')
      && row.querySelector('.hist__text').textContent === (entry.text || '');
    row.classList.toggle('hist--selected', Boolean(same));
  }
  markRevealState();
}

// ---------------------------------------------------------------------------
// THE TWO SURFACES
// ---------------------------------------------------------------------------
// Owner, 2026-10-08: the global hotkey opens the LIVE CAPTIONS ONLY — a short strip — and the
// full column becomes something the owner opens on purpose. One document, two
// layouts, and the shell switches between them by setting ONE attribute:
//
//     document.body.dataset.surface = 'strip' | 'panel'
//
// `app/panel/surface.js` defines it; `panel.css` draws the difference; this
// file only BEHAVES differently. Two rules keep that honest:
//
//   * every surface-dependent decision asks `currentSurface()` — never a second
//     copy of the attribute name, so a grep for `data-surface` finds one place in
//     each file and the three can be diffed against each other;
//   * every control is bound ONCE and hidden by CSS on the surface it does not
//     belong to (`display: none` also takes it out of the tab order and the
//     accessibility tree, which `visibility`/`opacity` would not).
//
// `window.SottoSurfaces` is the shell-facing half of the contract; the exact
// wire names, sizes and expected log lines are in
// `_main/receipt-panel-two-surfaces.md`.

/** `'strip'` or `'panel'` — the document's own answer, never a guess. */
function currentSurface() {
  return window.SottoSurfaces ? window.SottoSurfaces.current() : 'panel';
}

/**
 * Switch the layout IN THIS DOCUMENT. The shell is expected to call
 * `bridge.setPanelSurface(name)` instead (it must resize the window in the same
 * breath — see `openFullPanel`), but this is what a shell without that call, a
 * browser, and the audit harness use.
 */
function setSurface(name) {
  /* THE GUARD THAT BREAKS A FEEDBACK LOOP, AND IT IS THE FIX FOR THE OWNER'S FREEZE.
   *
   * MEASURED 2026-10-13 (audit lane, and it CONFIRMED the log flood and the freeze are the
   * SAME bug): one iteration of the loop was
   *
   *   :2753 bridge.onGeometry -> :2774 setSurface(geometry.surface) -> HERE
   *     -> applySurface() -> applyLiveEnabled -> :2159 applyFloat
   *     -> :2300 bridge.setPanelSurface('strip', 'strip-float-off')
   *     -> shell :6963 set_panel_surface -> :7011 _apply_window_geometry
   *     -> :7154 send_geometry -> :5027 emit('geometry') -- with NO DEDUP -- back to :2753.
   *
   * The shell echoes the geometry back on every surface call, and this function re-ran the
   * whole surface pipeline on every echo, INCLUDING when the name had not changed. So the
   * two sides drove each other for ever at the speed of a JS<->Python round trip: p50 102/s,
   * p90 185/s, p99 264/s, max 294/s over 14 536 seconds.
   *
   * WHY THAT IS THE FREEZE: `write_atomic` measures 8.42 ms per write on H:, a ceiling of
   * 118.8 writes a second, and the loop called it every iteration. p99 alone asked for more
   * than twice the volume's bandwidth.
   *
   * THE GUARD IS ON A REAL CHANGE, not on a suppression: a genuine switch still runs
   * applySurface() exactly as before (both through SottoSurfaces.onChange, wired at :1921,
   * and explicitly here), the startup call at :1922 is untouched, the no-SottoSurfaces path
   * still calls it, and the return value is unchanged. What stops is only the RE-RUN for a
   * name that did not move. */
  const before = currentSurface();
  if (window.SottoSurfaces) window.SottoSurfaces.set(name);
  const after = currentSurface();
  if (!window.SottoSurfaces || after !== before) applySurface();
  return after;
}

/** Wire the surface hooks the shell drives, and paint the surface we start in. */
function wireSurfaces() {
  if (window.SottoSurfaces) window.SottoSurfaces.onChange(applySurface);
  applySurface();
}

/**
 * Everything that differs BEHAVIOURALLY between the two surfaces, in one
 * function, so the difference is readable in one place.
 *
 * The transcript drawer keeps its state across a switch (it is the same DOM node
 * and `applyTranscriptMode` is not undone), so opening the panel from the strip
 * cannot reset a drawer the owner had opened or a search he had run.
 */
function applySurface() {
  const surface = currentSurface();
  // The placeholder's prose is GONE (owner, 2026-11-09: *"ZERO frases explicativas
  // em qualquer parte"*), so there is no longer a sentence to carry into a
  // tooltip for the strip — this used to copy the body's four lines into
  // `title` so the strip kept the information. The state word in the TITLE is all
  // that is left, and it fits both surfaces.
  const body = dom.placeholder && dom.placeholder.querySelector('.captions__placeholder-body');
  if (body) body.title = '';
  applyPauseAvailability();
  // THE LIVE STATE *IS* THE CAPTION-ON-SCREEN STATE now (owner, 2026-10-13):
  // `applyLiveEnabled` drives `body[data-float]` through `applyFloat`, so this one
  // call repaints the button AND the overlay after every surface switch. The caption
  // survives a switch to the panel (the panel already shows the caption) and is
  // restored on the way back, so the button never lies about what is on screen.
  applyLiveEnabled(liveEnabled, { silent: true });
  return surface;
}

/** The strip's three controls. Live toggle, Pause, Open panel — and no more. */

function wireStripControls() {
  if (dom.stripLiveButton) {
    /* THE OWNER'S BUTTON (2026-10-17): it is a switch for the caption window that
     * lives OUTSIDE this panel, so a click ASKS the shell and paints nothing. The
     * paint arrives with the shell's own `data-caption-window` write -- see
     * `requestCaptionOverlay` / `watchCaptionWindowState`. */
    dom.stripLiveButton.addEventListener('click', () => {
      requestCaptionOverlay(!liveEnabled);
    });
  }
  if (dom.stripOpenButton) {
    dom.stripOpenButton.addEventListener('click', () => openFullPanel('strip-open'));
  }
  // HIDE: the strip's own dismiss. It calls the SAME `bridge.hide()` the panel's
  // `#hide-button` calls — there is no second mechanism. The shell re-shows the
  // strip on Alt+C. A shell without the method is left alone rather than throwing.
  if (dom.stripHideButton) {
    dom.stripHideButton.addEventListener('click', () => {
      if (bridge && typeof bridge.hide === 'function') bridge.hide();
    });
  }
  // LINHAR IS THE LIVE BUTTON NOW (owner, 2026-10-13): the separate float button
  // was removed from panel.html and the click handler above (`applyLiveEnabled`)
  // is what moves the overlay, through `applyFloat`. One control, one attribute,
  // one window height — see `applyFloat` for the whole contract.
  // ONE handler per pause control, bound from a class so the strip's button and
  // the panel's own button cannot drift apart; `wirePause` owns the dialog.
  for (const button of dom.pauseButtons) {
    // THE STRIP IS 40 px TALL: a confirmation dialog cannot fit there (the
    // 2026-10-17 screenshot showed it always painted over the bar). Its pause
    // button IS the confirmation: one click unloads. The side panel keeps the
    // dialog.
    if (button.id === 'strip-pause-button') {
      button.addEventListener('click', () => (paused ? resumePipeline() : confirmPause()));
    } else {
      button.addEventListener('click', () => (paused ? resumePipeline() : openPauseConfirm(button)));
    }
  }
  // The font dial is wired from the STRIP side too, so the strip's pair and the
  // panel's pair reach the same apply function. See `wireFontDial`.
  wireFontDial();
  // THE 3-DOT MENU (font dial + Pause inside it, the translation selector and the
  // worker cause). See `wireMenu`.
  wireMenu();
}

/**
 * THE 3-DOT MENU (owner, 2026-10-21).
 *
 * The owner moved the caption-size dial and Pause OFF the top row and into this
 * menu, and asked for a TRANSLATION selector and for the worker's cause to live
 * here too -- so the panel itself never shows an error or a stop. Verbatim:
 * *"quero na direita o botao de fechar/hide, e na esquerda dele um botao de 3
 * pontos pra abrir mais opcoes/botoes"*, and, on what goes inside,
 * *"fonte + pausa + traducao + causa"*.
 *
 * The two moved controls keep their ids, so `wireFontDial` and `wirePause` above
 * find them exactly as before; this function owns ONLY the popover, the
 * translation selector and the cause slot.
 */



function currentTranslationTarget() {
  try {
    return window.localStorage.getItem(TRANSLATION_KEY) || '';
  } catch (_) {
    return '';
  }
}

function wireMenu() {
  const button = dom.menuButton;
  const menu = dom.panelMenu;
  if (!button || !menu) return;
  const close = () => {
    menu.hidden = true;
    button.setAttribute('aria-expanded', 'false');
  };
  const open = () => {
    menu.hidden = false;
    button.setAttribute('aria-expanded', 'true');
  };
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    if (menu.hidden) open(); else close();
  });
  // A click anywhere else, or Escape, closes it -- a popover that outlives its
  // trigger is the "button that changes and nothing else" the owner named.
  document.addEventListener('click', (event) => {
    if (menu.hidden) return;
    if (menu.contains(event.target) || button.contains(event.target)) return;
    close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !menu.hidden) close();
  });

  // THE TRANSLATION SELECTOR. Persisted in localStorage and handed to the shell
  // through `bridge.setTranslationTarget` when that method exists; the shell owns
  // which track is fetched, so an explicit choice overrides the default policy
  // (English for every video, Spanish stays Spanish) for EVERY video.
  const select = dom.translationSelect;
  if (select) {
    for (const [code, label] of TRANSLATION_LANGS) {
      const option = document.createElement('option');
      option.value = code;
      option.textContent = label;
      select.appendChild(option);
    }
    select.value = currentTranslationTarget();
    select.addEventListener('change', () => {
      const value = select.value || '';
      try {
        window.localStorage.setItem(TRANSLATION_KEY, value);
      } catch (_) {
        // A storage-less harness must not take the selector down with it.
      }
      if (bridge && typeof bridge.setTranslationTarget === 'function') {
        bridge.setTranslationTarget(value);
      }
    });
    if (bridge && typeof bridge.setTranslationTarget === 'function') {
      bridge.setTranslationTarget(select.value || '');
    }
  }

  // O FUNDO DA LEGENDA E A TRANSPARENCIA (dono, 2026-11-09). Os dois falam com
  // a JANELA NATIVA, nao com este documento: `setCaptionVisual` no shell prende,
  // grava em `_main/caption-settings.json` e repinta o overlay vivo. A caixa so'
  // mostra o estado; o numero que vale e' o que o ficheiro guarda.
  const plateSelect = dom.captionPlateSelect;
  const opacityRange = dom.captionOpacityRange;
  const opacityValue = dom.captionOpacityValue;
  if (plateSelect || opacityRange) {
    const look = storedCaptionLook();
    if (plateSelect) plateSelect.value = look.plate;
    if (opacityRange) opacityRange.value = String(look.transparency);
    if (opacityValue) opacityValue.textContent = look.transparency + '%';
    const submit = () => {
      const plate = plateSelect ? plateSelect.value : look.plate;
      const transparency = opacityRange
        ? (parseInt(opacityRange.value, 10) || 0) : look.transparency;
      if (opacityValue) opacityValue.textContent = transparency + '%';
      try {
        window.localStorage.setItem(CAPTION_PLATE_KEY, plate);
        window.localStorage.setItem(CAPTION_OPACITY_KEY, String(transparency));
      } catch (_) {
        // Sem storage a escolha vale para esta sessao -- nunca derruba a caixa.
      }
      sendCaptionLook(plate, transparency);
    };
    if (plateSelect) plateSelect.addEventListener('change', submit);
    if (opacityRange) {
      // O rotulo segue o dedo enquanto arrasta; o envio e' no `change`, para o
      // shell nao gravar o ficheiro cinquenta vezes num gesto so'.
      opacityRange.addEventListener('input', () => {
        if (opacityValue) {
          opacityValue.textContent = (parseInt(opacityRange.value, 10) || 0) + '%';
        }
      });
      opacityRange.addEventListener('change', submit);
    }
    // O ARRANQUE NAO MANDA UM PUSH SEM ESCOLHA: so' envia quando ha um valor
    // guardado, para uma sessao nova nao escrever por cima do ficheiro que o
    // shell ja' leu quando criou o overlay.
    let stored = false;
    try {
      stored = window.localStorage.getItem(CAPTION_PLATE_KEY) !== null
        || window.localStorage.getItem(CAPTION_OPACITY_KEY) !== null;
    } catch (_) { stored = false; }
    if (stored) sendCaptionLook(look.plate, look.transparency);
  }

  // O "MODO STEALTH" (dono, 2026-11-16): DESLIGADO de fabrica, so' o dono o
  // liga. `setCaptureExclude` no shell grava `capture_exclude` no ficheiro e
  // aplica na hora a' janela que ele ja' esta' a ver.
  const captureSelect = dom.captionCaptureSelect;
  if (captureSelect) {
    let captureStored = null;
    try {
      captureStored = window.localStorage.getItem(CAPTION_CAPTURE_KEY);
    } catch (_) {
      // Sem storage a caixa abre no default (off), que e' o que o ficheiro diz.
    }
    const captureOn = captureStored === '1';
    captureSelect.value = captureOn ? '1' : '0';
    captureSelect.addEventListener('change', () => {
      const on = captureSelect.value === '1';
      try {
        window.localStorage.setItem(CAPTION_CAPTURE_KEY, on ? '1' : '0');
      } catch (_) {
        // A escolha vale para esta sessao; perder a preferencia nao e' fatal.
      }
      sendCaptionCaptureExclude(on);
    });
    // No arranque, so' um valor JA' guardado e' reenviado -- uma sessao nova
    // nao escreve por cima do ficheiro que o shell leu ao criar o overlay.
    if (captureStored !== null) sendCaptionCaptureExclude(captureSelect.value === '1');
  }

  // The export button lives in the popover, so the header contract (settings
  // immediately left of close) is untouched on all 59 designs.
  if (dom.historyExport) {
    dom.historyExport.addEventListener('click', () => { exportTranscript(); });
  }
}

/**
 * THE TRANSCRIPT FONT DIAL (owner, 2026-10-09, verbatim: *"bota um botao de
 * aumentar ou diminuir a fonte das transcricoes, tanto no overlay abaixo, que
 * vamos criar, tanto no painel da direita"*).
 *
 * TWO BUTTONS, ONE NUMBER. One lives in `.panel__controls` (`#font-scale-button`)
 * and one in the strip (`#strip-font-scale-button`). Both call the same
 * `applyCaptionScale`, which sets `--caption-scale` on the document element — the ONE
 * value `panel.css` derives every caption, history and strip-caption size from. So
 * the two surfaces can never disagree, and because the derivation lives in BASE rules
 * (`body[data-surface="strip"] .caption__text` included), no theme can override it.
 *
 * ONE BUTTON PER SURFACE, CYCLING (owner, 2026-10-18, *"1 botao de tamanho em vez
 * de 2"*). It was a smaller/larger PAIR on each surface — four buttons for one
 * number. The dial still has thirteen stops (0.8 → 2.0 by 0.1), so a two-state toggle
 * was not an option: it would have thrown away eleven sizes. Instead the single
 * button steps UP one stop and WRAPS to the minimum after the maximum. That also
 * removes the `disabled` ends of travel the old pair needed, which is a real gain —
 * the control can now never sit greyed out doing nothing.
 *
 * WHAT IS DELIBERATELY NOT HERE: a second source of truth. The value is written to
 * localStorage only so it survives a restart, and it is READ BACK HERE at load and
 * applied before the first caption paints; nothing else stores a size, and no size
 * is hard-coded in JS.
 *
 * FAILURE MODES, all silent by design: an older harness without the buttons leaves
 * every handler unbound (no throw); a localStorage that throws (private mode) is
 * caught, because losing a preference must never cost the panel its captions; a
 * value outside the clamp is clamped rather than trusted.
 */
function wireFontDial() {
  // Restore the persisted scale BEFORE wiring, so the first caption already paints
  // at the size the owner chose.
  const stored = readStoredFontScale();
  if (stored !== null) applyCaptionScale(stored, { persist: false });

  const bind = (button) => {
    if (!button) return;
    button.addEventListener('click', cycleCaptionScale);
    /* THE WHEEL MOVES THE SAME DIAL (owner, 2026-11-06, verbatim): *"e o negocio de
     * scrollar botao pra aumentar ou diminuir ... tambem faça essa funcao no botao de
     * aumentar o tamanho da legenda."*
     *
     * ONE STEP PER NOTCH, in the direction of the wheel, through the SAME
     * `applyCaptionScale` the click uses -- so the clamp, the rounding and the
     * persistence are not re-implemented here. The 120 ms latch is the click's own
     * rate; a trackpad flick that fired twenty events would jump the dial from 1.0
     * to 2.0 in one gesture and there is no undo on this control. */
    let wheelAt = 0;
    button.addEventListener('wheel', (event) => {
      if (!event.deltaY) return;
      event.preventDefault();
      const now = Date.now();
      if (now - wheelAt < 120) return;
      wheelAt = now;
      stepCaptionScale(event.deltaY > 0 ? -1 : 1);
    }, { passive: false });
  };
  bind(dom.fontScaleButton);
  bind(dom.stripFontScaleButton);
}

/**
 * One step UP or DOWN the dial, clamped at both ends.
 *
 * A CLICK AND A WHEEL ARE NOT THE SAME GESTURE, and that is why this exists beside
 * `cycleCaptionScale`: a click WRAPS (the owner's 2026-10-18 ruling, because the pair
 * it replaced could sit disabled at an end of travel), while a wheel that wrapped
 * would take the dial from the smallest size straight to the largest mid-flick. The
 * wheel stops at the stop and the click keeps wrapping.
 */
function stepCaptionScale(direction) {
  const next = captionScale + FONT_SCALE_STEP * (direction > 0 ? 1 : -1);
  applyCaptionScale(Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, next)));
}

/**
 * ONE CLICK = ONE STEP UP, THEN WRAP.
 *
 * The arithmetic is done through `applyCaptionScale` so there is exactly one place
 * that clamps, rounds and persists. The wrap is decided HERE and not in
 * `applyCaptionScale` on purpose: `applyCaptionScale` clamps, and clamping is what
 * the pair's `disabled` state used to make visible. If the wrap lived there, a
 * stored value or a programmatic call would silently teleport from 2.0 to 0.8 —
 * correct for a button, wrong for a function that is also the restore path
 * (`wireFontDial` calls it with `persist: false` before the first caption paints).
 *
 * The epsilon guard matters: `FONT_SCALE_MAX - 1e-9` rather than `===`, because the
 * value is rounded to a step and stored as a float. At the top stop the old pair's
 * `larger` button disabled; without the guard a click there would compute
 * 2.0 + 0.1, clamp back to 2.0 and read as a button that did nothing.
 */
function cycleCaptionScale() {
  const atTop = captionScale >= FONT_SCALE_MAX - 1e-9;
  const next = atTop ? FONT_SCALE_MIN : captionScale + FONT_SCALE_STEP;
  applyCaptionScale(next);
}

/** Read the persisted scale, or null when absent/unreadable/out of range. */
function readStoredFontScale() {
  let raw = null;
  try {
    raw = window.localStorage.getItem(FONT_SCALE_KEY);
  } catch (_err) {
    return null; // private mode / storage disabled: the default size stands.
  }
  if (raw === null) return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return null;
  if (value < FONT_SCALE_MIN || value > FONT_SCALE_MAX) return null;
  return value;
}

/**
 * Apply a scale: clamp it, round to the step so the dial has real stops, set the
 * custom property, remember it, and report which end of the range is reached on
 * the buttons themselves (a disabled button at a limit is the honest UI; a button
 * that does nothing is not).
 */
function applyCaptionScale(next, options) {
  const opts = options || {};
  const clamped = Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, next));
  // Round to the step so repeated clicks cannot drift into ugly values like 1.05.
  const stepped = Math.round(clamped / FONT_SCALE_STEP) * FONT_SCALE_STEP;
  captionScale = Number(stepped.toFixed(4));

  document.documentElement.style.setProperty('--caption-scale', String(captionScale));

  if (opts.persist !== false) {
    try {
      window.localStorage.setItem(FONT_SCALE_KEY, String(captionScale));
    } catch (_err) {
      /* a preference that cannot be remembered is not an error worth showing. */
    }
  }
  reportFontScaleState();
}

/**
 * The scale dial is TWO buttons now, and it NEVER disables either of them.
 *
 * The old pair reported its ends with `disabled`, which is honest for a button that
 * runs off a rail — but this button WRAPS. The last stop goes back to the first, so
 * there is no end of travel to report, and a control that sits greyed out at a
 * boundary is a control the owner has to think about. What replaces the state is the
 * NUMBER, written where each surface can actually show it: `aria-label`/`title` on
 * the panel's icon button, and a printed percentage in the strip's label line.
 */
function reportFontScaleState() {
  const percent = Math.round(captionScale * 100);
  const label = `Caption size: ${percent}%`;
  const set = (button) => {
    if (!button) return;
    button.title = label;
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-disabled', 'false');
    button.disabled = false;
    // The value goes on the button as DATA too, so a probe can read the current
    // stop without reaching into panel.js's module scope.
    button.setAttribute('data-font-scale', String(captionScale));
    const readout = button.querySelector('[data-font-scale-readout]');
    if (readout) readout.textContent = `${percent}%`;
  };
  set(dom.fontScaleButton);
  set(dom.stripFontScaleButton);
}

/**
 * TRANSPARENCY (strip only). NO BUTTON CALLS IT ANY MORE — the button was deleted
 * from panel.html on 2026-10-12 because it was the reported bug (the two CSS
 * hide-rules made the window an unclickable solid colour). It is kept as the
 * panel's half of the shell contract so a shell that still answers
 * `sotto:transparency` keeps a working counterpart, and so a stale caller cannot
 * crash; the `dom.stripTransparencyButton` guards below are all it can reach.
 *
 * THE MESSAGE. The bridge method `bridge.setTransparency(on)` posts the
 * documented `sotto:transparency` message with `{ on: bool }` — the SAME
 * bridge-method pattern every other panel->shell call in this file uses
 * (`bridge.hide()`, `bridge.quit()`, `bridge.setPointerInteractive()`). The
 * shell side may not exist yet: an absent method is NOT an error, and the local
 * `body[data-transparency]` state stands on its own (fail silently, never throw).
 */
function applyTransparency(on) {
  transparencyOn = Boolean(on);
  document.body.dataset.transparency = transparencyOn ? 'on' : 'off';
  if (dom.stripTransparencyButton) {
    dom.stripTransparencyButton.setAttribute('aria-pressed', transparencyOn ? 'true' : 'false');
    dom.stripTransparencyButton.title = transparencyOn
      ? 'Chrome hidden · captions only. Press again (or use the shell) to bring the controls back.'
      : 'Transparency: hide the strip chrome and keep only the captions';
  }
  if (bridge && typeof bridge.setTransparency === 'function') {
    try {
      bridge.setTransparency(transparencyOn);
    } catch (err) {
      // A throwing bridge must not take the local state down with it.
    }
  }
}

/**
 * THE CAPTION BUTTON IS A SWITCH FOR THE REAL OVERLAY, AND IT PAINTS WHAT IS
 * ACTUALLY ON SCREEN (owner, 2026-10-17, verbatim: *"quando eu clico em legenda, ele
 * simplesmente muda o botao. nao era pra ele fazer isso. tira todo o codigo que faz
 * isso."*).
 *
 * WHAT WAS WRONG, in this file's own words. The click handler was
 * `applyLiveEnabled(!liveEnabled)`, and that function FLIPPED A MODULE-LEVEL BOOLEAN and
 * repainted `aria-pressed`, `data-state`, the label and the title from it -- before it
 * asked anybody. So the button always moved, even on a shell where nothing came up, which
 * is precisely what the owner saw: a button that changes and nothing else. The shell's own
 * answer was then thrown away: the bridge resolves `{liveEnabled: <the value the page
 * asked for>}` (`sotto_webview.py:3607-3611`), so the page painted its REQUEST back as if
 * it were a RESULT. That echo is deleted here.
 *
 * WHAT IS NOW: ONE direction of travel, and the page never invents a state.
 *   click   -> `requestCaptionOverlay()` asks the shell and paints NOTHING;
 *   shell   -> `show_caption_window()` shows/hides its own window and writes what it
 *              actually did onto the document as `data-caption-window`
 *              (`sotto_webview.py:7177-7179`);
 *   page    -> `watchCaptionWindowState()` observes THAT attribute and repaints from it.
 * So a refused or failed overlay leaves the button exactly where it was, and a caption
 * window that is already on screen (the owner pressed live before switching surface, or
 * the shell raised it on its own) paints the button ON without any click at all.
 *
 * `applyLiveEnabled` keeps its name and its signature because the surface switch still
 * calls it (`:2006`) to REPAINT; it is a painter now, not a switch. `{silent: true}` is
 * accepted and ignored on purpose, so no caller has to change to get the new behaviour.
 *
 * `CAPTION_WINDOW_ATTR` and `captionOverlayIsUp` used to live HERE, and the init block
 * reached them from above -- a ReferenceError at load, measured and logged on
 * 2026-10-17 16:00:40. Both are now declared just above that init block, which is the
 * only reason this whole mechanism works on the first paint. Do not move them back.
 */

/**
 * ASK THE SHELL. Deliberately paints nothing: the paint belongs to the shell's answer,
 * which arrives as `data-caption-window`. A shell without `setLiveEnabled` has no answer
 * to wait for, so the page keeps its own boolean there and says so in the title.
 */
function requestCaptionOverlay(on) {
  const wired = typeof bridge === 'object' && bridge !== null
    && typeof bridge.setLiveEnabled === 'function';
  if (!wired) {
    applyLiveEnabled(Boolean(on));
    return false;
  }
  try {
    const result = bridge.setLiveEnabled(Boolean(on));
    if (result && typeof result.then === 'function') {
      result.catch((err) => {
        setStatus('Caption overlay refused: ' + errorText(err), '');
        // Repaint from the FACT, not from the request: the shell did not do it.
        applyLiveEnabled(captionOverlayIsUp());
      });
    }
  } catch (err) {
    setStatus('Caption overlay refused: ' + errorText(err), '');
    applyLiveEnabled(captionOverlayIsUp());
  }
  return true;
}

/** Repaint the button whenever the shell's own account of the overlay changes. */
function watchCaptionWindowState() {
  applyLiveEnabled(captionOverlayIsUp());
  if (typeof MutationObserver !== 'function') return false;
  new MutationObserver(() => {
    const up = captionOverlayIsUp();
    // THE LAMP IS PAINTED HERE, FIRST, AND ON EVERY WRITE. The thing that changes
    // in this callback is the SHELL'S OWN ACCOUNT (`data-caption-window`), so the
    // readout of that account is painted FROM the account -- not from the button's
    // state, and not only when the button's state happens to change. A readout
    // painted by one of its two callers goes stale the day the other caller is the
    // one that runs, and this one is the caller that runs when the owner presses
    // Alt+C on the other surface.
    paintLiveLamps(up);
    if (up !== liveEnabled) applyLiveEnabled(up);
  }).observe(document.documentElement, {
    attributes: true,
    attributeFilter: [CAPTION_WINDOW_ATTR],
  });
  return true;
}

/**
 * THE LIVE-CAPTION LAMP (owner, 2026-10-19, verbatim: *"com um alt c so, com audio ou
 * nao, tem que ter indicativo se a legenda ao vivo ativou ou nao. pode fazer isso com
 * uma bolinha que acende vermelho ou verde."*).
 *
 * ONE FACT, AND IT IS THE SHELL'S. `on` is never a local wish: it is
 * `captionOverlayIsUp()` -- the shell's `data-caption-window` attribute, which
 * `sotto_webview.py::show_caption_window()` writes on every LIVE switch
 * (`_set_live_enabled`, `sotto_webview.py:9525-9566`) and which this panel's own
 * MutationObserver watches. RED = the live caption is OFF, GREEN = it is ON.
 *
 * IT IS A READOUT, NOT A CONTROL: no click, no focus, no pointer events (the CSS
 * carries `pointer-events: none`). The owner asked for an INDICATOR, and an
 * indicator that takes clicks is a second switch that can disagree with the first.
 *
 * WHY THERE IS NO `title` ON IT. A tooltip is painted by the browser for the
 * element the pointer actually HIT, and `pointer-events: none` means the pointer
 * never hits the lamp -- it hits the header behind it. A `title` here would be a
 * promise the browser never keeps. The state is in `data-live` (the CSS reads it)
 * and in `aria-label` (a screen reader reads it); both are updated here.
 */
function paintLiveLamps(on) {
  const state = on ? 'on' : 'off';
  const label = on
    ? 'Live caption: ON · the live engine is on.'
    : 'Live caption: OFF · press Alt+C to turn it on.';
  for (const lamp of [dom.liveLamp, dom.stripLiveLamp]) {
    if (!lamp) continue;
    lamp.dataset.live = state;
    lamp.setAttribute('aria-label', label);
  }
}

/**
 * THE PAINTER. Called with a FACT: the overlay's real state (from the shell's
 * `data-caption-window`) or, on a shell with no caption window at all, the page's own
 * fallback. It never talks to the shell -- `requestCaptionOverlay` is the only door.
 */
function applyLiveEnabled(enabled, options) {
  liveEnabled = Boolean(enabled);
  const wired = typeof bridge === 'object' && bridge !== null
    && typeof bridge.setLiveEnabled === 'function';
  liveSupported = wired;

  if (dom.stripLiveButton) {
    dom.stripLiveButton.setAttribute('aria-pressed', liveEnabled ? 'true' : 'false');
    dom.stripLiveButton.setAttribute('aria-disabled', wired ? 'false' : 'true');
    dom.stripLiveButton.dataset.wired = wired ? 'true' : 'false';
    dom.stripLiveButton.title = liveEnabled
      ? (wired
        ? 'live · the captions are ON SCREEN and the live engine is on. Click to take them off the screen.'
        : 'live · the captions are ON SCREEN. This shell does not implement setLiveEnabled() yet, so this switch cannot reach the engine.')
      : (wired
        ? 'live is off · the captions are off the screen and the live engine is stopped. Click to bring them back.'
        : 'live is off · the captions are off the screen. Click to put them ON SCREEN, loose like the .zip demos.');
  }
  if (dom.stripLiveLabel) {
    // The word is the control's NAME, not its state: it stays "LIVE" (painted
    // red by base CSS) in both states, and the state is carried by aria-pressed
    // plus the title. `updateStripState` is what says "Live off" in the readout.
    dom.stripLiveLabel.textContent = 'LIVE';
  }
  if (dom.stripLiveButton && !liveEnabled) dom.stripLiveButton.dataset.state = 'off';
  else if (dom.stripLiveButton) delete dom.stripLiveButton.dataset.state;

  // THE LAMP FOLLOWS THE SAME FACT AS THE BUTTON (see `paintLiveLamps`). This is
  // the SECOND of its two painters: the observer in `watchCaptionWindowState`
  // paints it from the shell's own write, and this one paints it whenever the
  // page repaints the button -- so a shell that never writes the attribute (no
  // caption window at all) still has a lamp that says something true.
  paintLiveLamps(liveEnabled);

  // THE CAPTION ON SCREEN FOLLOWS THE REAL OVERLAY STATE. ONE FACT, NOT TWO: when the
  // shell's caption window is up, the caption is loose on the screen, and `applyFloat`
  // owns the attribute, the window height and the page's own caption. Called on EVERY
  // paint -- including the repaint a surface switch or the shell's attribute triggers --
  // so the button and the screen cannot drift apart.
  applyFloat(liveEnabled);

  /* DELETED 2026-10-17, and this is the code the owner named: the old tail of this
   * function called `bridge.setLiveEnabled()` and then treated the Promise's answer as a
   * confirmation --
   *
   *     result.then((payload) => { ...applyLiveEnabled(confirmed) })
   *
   * -- while the shell resolves `{liveEnabled: <the page's own request>}`
   * (`sotto_webview.py:3607-3611`). That is the button painting its own wish back at
   * itself, which is why clicking it "simplesmente muda o botao": the page confirmed
   * itself. The one door to the shell is now `requestCaptionOverlay()`, called by the
   * click handler only, and it paints nothing. */
  updateStripState();
}

/** The strip's status: a dot and ONE word. See `updateStripState`. */
function updateStripState() {
  if (!dom.stripState) return;
  const kind = statusSnapshot.kind;
  let word;
  let state;
  if (paused) {
    word = 'Paused';
    state = '';
  } else if (!liveEnabled) {
    // THE READOUT SAYS WHAT IS OFF, AND IT IS THE CAPTION. It said 'Live off'
    // until 2026-10-13, which read as "the transcription stopped" while the worker
    // was streaming perfectly — the button's own red/grey pill is where LIVE vs
    // NOT-LIVE is stated, and this word only says the caption is not on screen.
    word = 'OFF';
    state = '';
  } else if (kind === 'error') {
    word = 'Error';
    state = 'error';
  } else if (kind === 'no-audio') {
    // NOT red and not 'Working': the worker is alive, the endpoint is quiet.
    word = 'No audio';
    state = '';
  } else if (kind === 'live') {
    word = 'Live';
    state = 'live';
  } else {
    word = statusSnapshot.text ? 'Working' : 'Starting';
    state = '';
  }
  if (dom.stripWord) dom.stripWord.textContent = word;
  dom.stripState.classList.toggle('is-live', state === 'live');
  dom.stripState.classList.toggle('is-error', state === 'error');
  // The full sentence is one hover away — and the strip never loses it while
  // `#status-text` stays in the DOM for the read-back probes. The revive hint
  // is APPENDED rather than written instead, because this line runs on every
  // status and would otherwise erase the one place the strip says that it is
  // clickable.
  dom.stripState.title = (paused
    ? 'Paused · the engines are unloaded until you resume'
    : statusSnapshot.text || 'Sotto is starting') + ' · ' + REVIVE_HINT;
}

/** Open the FULL panel. `bridge.setPanelSurface('panel')` resizes in the shell. */
function openFullPanel(reason) {
  if (bridge && typeof bridge.setPanelSurface === 'function') {
    bridge.setPanelSurface('panel', reason);
    return;
  }
  // No shell call: switch the layout here (a browser, the harness, or a shell
  // that has not ported it yet). The strip is NOT short until the window is.
  setSurface('panel');
}
/**
 * FLOAT THE CAPTION ON THE SCREEN — the ZIP's own behaviour (owner, 2026-10-12:
 * *"um botao de linhar a legenda, que liga ela NA TELA, igual um overlay,
 * EXATAMENTE IGUAL os .zip fazem"*; and his own prompts of the handoff
 * conversation: *"primeiro, o painel de baixo. NELE EU ATIVO o segundo overlay,
 * q e a legenda independente."*).
 *
 * ONE CONTROL, ONE ATTRIBUTE, ONE WINDOW HEIGHT — and since 2026-10-13 that
 * control is `#strip-live-button`, not a button of its own: `applyLiveEnabled`
 * is the only caller, so "live" and "the caption is on the screen" are ONE fact.
 * `body[data-float]` is the attribute; `caption-float.js` owns the overlay's
 * content; the shell owns the window, and the only runtime resize it has is a
 * re-read of `--float-height`/`--strip-height` on `setPanelSurface('strip')` —
 * so the height is raised and lowered THROUGH that call, never by the page
 * touching the window.
 *
 * THE STRIP SURFACE IS THE ONLY ONE THAT FLOATS. The panel already shows the
 * caption, so floating it there would hide the panel to show the same words; and
 * the overlay's own CSS is scoped to `body[data-surface="strip"]`, so the
 * attribute alone can never paint it over the panel. The shell call is guarded by
 * the surface for the same reason — see `applyFloat`.
 *
 * FAILURE MODES, all silent by design: a shell without `setPanelSurface` (a
 * browser, the audit harness) still gets the attribute and the layout, just not
 * the resize; a document with no live button still gets the overlay.
 */
function setStripHeight(value) {
  document.documentElement.style.setProperty('--strip-height', value);
}

/* REMOVED 2026-10-13: `paintFloatState()`. It existed to keep the separate
 * "Linhar" button honest about the overlay it toggled, and that button is gone.
 * The live button is painted by `applyLiveEnabled` from the SAME boolean that
 * drives the overlay, so there is no second state left to paint. */

/**
 * Apply the floated state: the attribute, the button, and the window height.
 * Idempotent — a second call with the same state changes nothing.
 */
/**
 * THE PANEL'S ONE WRITE INTO THE INDEPENDENT OVERLAY (lane: caption, 2026-10-12).
 * The overlay owns its own state and can be on screen with no panel mounted at all
 * (caption-float.js show()/hide()/setFloat()); this call is how the panel's own button
 * moves it. It is a CALL, never a dependency: a document without the module (an older
 * harness, a browser probe) keeps the attribute and the layout and nothing throws.
 * Returns true when the module took the state.
 */
function syncCaptionFloat(state) {
  const api = window.SottoCaptionFloat;
  if (!api || typeof api.setFloat !== 'function') return false;
  api.setFloat(state === 'on');
  return true;
}

/**
 * THE OWNER'S RULE, 2026-10-17, verbatim — this function used to break it:
 *
 *   "ao clicar no botao de legenda, nao deve abrir qualquer coisa. e pra ativar a
 *    legenda, na minha tela, sem background, sem estar conectada a qualquer
 *    painel. ela e livre na minha tela, um overlay"
 *
 * MEASURED, in `_main/webview-run.log`, what ONE click of that button did:
 *
 *   21:40:12.621  STRIP_HEIGHT from=40 to=220 source=css css_value=220 reason=surface-strip-float-on
 *   21:40:12.638  PANEL_SURFACE surface=strip reason=strip-float-on window=380x220@(770,768)
 *   21:40:12.643  PANEL_SURFACE surface=strip reason=float-on      window=380x220@(770,768)
 *
 * The panel's own window GREW BY 180 PX — that is the "abrir qualquer coisa", and
 * it is not the short simple bar in the owner's reference image. Worse, the page
 * went TRANSPARENT at the same moment (`caption-float.css:69`), and the panel's
 * window is NOT layered — `WS_EX_LAYERED` is opt-in and off by default
 * (`sotto_webview.py:4969-4994`, log: `style=WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|
 * WS_EX_TRANSPARENT` with no `|WS_EX_LAYERED`) — so a transparent page inside an
 * opaque WinForms window is the WHITE SLAB and the white corners, measured.
 *
 * THERE WERE THREE WRITES, NOT ONE, and every one of them is gone below:
 *   1. `setStripHeight(FLOAT_HEIGHT)` put `--strip-height: 220px` on <html>.
 *   2. `bridge.setPanelSurface('strip', 'strip-float-on')` asked the shell to
 *      re-surface the strip; `refresh_strip_height` read that variable back
 *      (`sotto_webview.py:7970`) and docked the window to it.
 *   3. `syncCaptionFloat()` -> `caption-float.js:243` asked for the SAME
 *      `setPanelSurface('strip', 'float-on')`, so a call that skipped (2) still
 *      grew the window. That is why the two `PANEL_SURFACE` lines are one
 *      millisecond apart in the log above.
 *
 * SO A SHELL THAT OWNS A CAPTION WINDOW GETS NOTHING FROM THIS FUNCTION. The
 * caption is `NativeCaptionOverlay` — a topmost, per-pixel-alpha, click-through
 * Win32 window on its own thread (`caption_overlay.py:257-269`, measured live as
 * `CAPTION_OVERLAY_PUSH count=1 visible=true hwnd=1775132`). It is on the
 * DESKTOP, not inside this window. `requestCaptionOverlay()` is the only door to
 * it and `watchCaptionWindowState()` paints the button from the shell's own
 * `data-caption-window` write. Clicking LIVE changes no geometry here, and the
 * panel keeps its own dark base (`panel.css:105-127`, THE RENDER PROTECTION) so
 * the window cannot come out white.
 *
 * THE FALLBACK IS WHY THIS IS A BRANCH AND NOT A DELETION. A shell with NO
 * `setLiveEnabled` — a browser probe, `_main/_audit-verify` — has no caption
 * window of its own, so there the page's own overlay IS the caption and the old
 * path is the only way a word reaches the screen. That harness is what
 * `_main/panel-caption-button-probe.mjs` drives, and it must keep working.
 */
function shellOwnsCaptionWindow() {
  return typeof bridge === 'object' && bridge !== null
    && typeof bridge.setLiveEnabled === 'function';
}

/**
 * Apply the floated state. With a shell that owns a caption window this is a
 * NO-OP by design and by measurement; without one it is the page's own overlay,
 * which is all a browser probe has. Idempotent either way.
 */
function applyFloat(on) {
  if (shellOwnsCaptionWindow()) return;
  const want = on ? 'on' : 'off';
  if (document.body.getAttribute('data-float') !== want) {
    document.body.setAttribute('data-float', want);
  }
  setStripHeight(STRIP_HEIGHT);
  syncCaptionFloat(want);
}


// ---------------------------------------------------------------------------
// THE PAUSE FLOW — two steps, and the second step says the honest thing
// ---------------------------------------------------------------------------
// Pause means UNLOAD (owner, 2026-10-08): the live engine and the background
// transcript go away, RAM and CPU come back, and resuming costs a model load.
//
// The confirmation exists because of what the OWNER said it must carry, verbatim
// intent: pausing is not necessary for performance — the background transcript is
// extremely light. So the dialog informs, with Cancel focused, and never nags.
//
// The panel cannot unload anything itself: it calls `bridge.pause({reason})` and
// the SHELL unloads. That call does not exist yet, so its absence is stated in
// the dialog BEFORE the owner presses anything and in the confirm button's own
// label, rather than being discovered as a no-op afterwards.

/**
 * THE PAUSE BUTTON IS A TOGGLE, AND IT SAYS WHICH HALF IT IS (owner, 2026-11-06,
 * verbatim): *"o botao de pause tambem nao ta completo. o botao nao muda pra
 * unpause."*
 *
 * THREE STATES, ONE PAINT: running → pause glyph, "Pause · unload the engines";
 * paused → play glyph, "Resume · reload the engines". `data-paused` carries the
 * state on the button itself so CSS can tint it and a probe can read it without
 * guessing from the glyph.
 *
 * The glyph is INLINE SVG, not a character: `⏸`/`▶` come from whatever emoji font
 * Windows picks and are two wildly different weights in the same 28 px box.
 */
function paintPauseControls() {
  for (const button of dom.pauseButtons) {
    button.setAttribute('data-paused', paused ? 'true' : 'false');
    const label = paused ? 'Resume · reload the engines' : 'Pause · unload the engines';
    button.title = label;
    button.setAttribute('aria-label', paused ? 'Resume' : 'Pause');
    const svg = button.querySelector('svg');
    if (!svg) continue;
    svg.replaceChildren();
    if (paused) {
      const play = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      play.setAttribute('d', 'M5.5 3.5 L12.5 8 L5.5 12.5 Z');
      play.setAttribute('fill', 'currentColor');
      play.setAttribute('stroke', 'none');
      svg.appendChild(play);
    } else {
      const bars = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      bars.setAttribute('fill', 'currentColor');
      bars.setAttribute('stroke', 'none');
      const left = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      left.setAttribute('x', '5');
      left.setAttribute('y', '3.5');
      left.setAttribute('width', '2.4');
      left.setAttribute('height', '9');
      left.setAttribute('rx', '0.8');
      const right = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      right.setAttribute('x', '8.6');
      right.setAttribute('y', '3.5');
      right.setAttribute('width', '2.4');
      right.setAttribute('height', '9');
      right.setAttribute('rx', '0.8');
      bars.append(left, right);
      svg.appendChild(bars);
    }
  }
}

/**
 * RESUME = RELOAD THE ENGINES THE PAUSE UNLOADED.
 *
 * `bridge.pause()` stops the worker and frees its CUDA context; there is no
 * "unpause" message and there should not be a second spawn path, so resuming is
 * the shell's existing `revive` (kill + respawn, the same one the status line
 * uses). The button is repainted from the SHELL's answer by `setPaused`, so a
 * refused resume leaves the play glyph where the truth is.
 */
function resumePipeline() {
  if (reviveInFlight) {
    setStatus('Already restarting the pipeline…', 'busy');
    return false;
  }
  const accepted = revivePipeline();
  if (accepted) {
    setPaused(false, null);
    setStatus('Reloading the engines…', 'busy');
  }
  return accepted;
}

function wirePause() {
  applyPauseAvailability();
  paintPauseControls();
  if (dom.pauseCancelButton) {
    dom.pauseCancelButton.addEventListener('click', () => closePauseConfirm());
  }
  if (dom.pauseConfirmButton) {
    dom.pauseConfirmButton.addEventListener('click', () => confirmPause());
  }
  if (dom.pauseDialog) {
    // Escape closes the modal natively, which fires `cancel` BEFORE the dialog
    // is closed; putting focus back and clearing the local state is all that is
    // left to do here.
    dom.pauseDialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      closePauseConfirm();
    });
  }
}

/** Paint whether this shell can actually pause, and say so where the owner looks. */
function applyPauseAvailability() {
  const wired = typeof bridge === 'object' && bridge !== null
    && typeof bridge.pause === 'function';
  pauseSupported = wired;

  for (const button of dom.pauseButtons) {
    button.dataset.wired = wired ? 'true' : 'false';
    // Not `disabled`: the button's job is to OPEN the dialog, and the dialog is
    // where the owner finds out what this shell can and cannot do. `aria-disabled`
    // is the honest announcement without making it unreachable.
    button.setAttribute('aria-disabled', wired ? 'false' : 'true');
    button.title = wired
      ? 'Pause · unload the live and background engines (asks first)'
      : 'Pause · este shell ainda não consegue pausar';
  }
  if (dom.pauseConfirmButton) {
    const label = wired ? 'Pause and unload' : 'Pause · not available in this shell yet';
    dom.pauseConfirmButton.textContent = label;
    dom.pauseConfirmButton.disabled = !wired;
    dom.pauseConfirmButton.title = wired
      ? 'Unload the live and background engines now'
      : 'This shell has no bridge.pause(), so there is nothing to unload: the panel will not pretend it paused';
  }
  if (dom.pauseShellNote) {
    const note = wired
      ? ''
      : 'Este shell ainda não consegue pausar · nada será descarregado.';
    dom.pauseShellNote.textContent = note;
    dom.pauseShellNote.hidden = note === '';
  }
}

// ---------------------------------------------------------------------------
// THE STATUS IS A REPAIR CONTROL — one click revives the WHOLE pipeline
// ---------------------------------------------------------------------------
// The owner's ruling, verbatim (2026-10-08): *"e o botao de error ou de idle sei
// que, ao clicar, deve fazer a pipeline inteira ser revivida, se nao tiver
// funcionando"*. Both status surfaces come with it: the panel's footer
// (`#status`) and the strip's own state (`#strip-state`). One click posts
// `bridge.revive()` and the SHELL does the killing and the respawning
// (`SottoShell.revive_worker`) — the panel never spawns anything itself.
//
// IT IS UNCONDITIONAL, AND THAT IS THE FEATURE. There is no health test here
// that could answer "you do not need this": the owner is looking at the screen
// and this is a repair button, so the only thing standing between him and a
// fresh worker is the model load. That price is stated in the element's own
// `title` BEFORE he clicks, and the click always goes through.
//
// THE WIRING IS DONE FROM JS AND NOT FROM THE MARKUP. `cursor`, `role`,
// `tabindex` and the listeners are all set here for two reasons: the status has
// to LOOK pressable and be reachable by keyboard or the control only exists for
// whoever already knew it was there, and `panel.html`/`panel.css` belong to
// another lane in this same session — a control the module cannot see is a
// control it cannot keep honest about.
//
// The mirror image of `wirePause` above: that one has to say what this shell
// CANNOT do, and so does this one. A shell with no `bridge.revive()` gets the
// sentence instead of a silent no-op.

/** Show the footer's sentence even though the state is not an error. */
function paintReviveSentence(sentence) {
  // `setStatus` KEEPS THE SENTENCE OFF THE SCREEN unless the state is `error` —
  // and it does not merely clip it, it writes an EMPTY STRING into the element
  // (`dom.statusText.textContent = paintsText ? text : ''`). So a repair that
  // only removed the clip class painted NOTHING AT ALL: the owner would click
  // the dead status and watch the footer go blank instead of saying it is
  // restarting. Measured — ARM P of `_main/revive-pipeline-oracle.py` caught the
  // empty footer on its first green-looking run, which is why the text is
  // written HERE, explicitly, and the class comes off with it. No stylesheet is
  // touched (this is the class `panel.css` already has for exactly this job) and
  // the next `setStatus` from the shell puts the icon back.
  const el = dom.statusText;
  if (!el) return;
  el.textContent = sentence;
  el.classList.remove('status__text--offscreen');
}

/** Has this shell ported the repair control? */
function reviveSupported() {
  return typeof bridge === 'object' && bridge !== null
    && typeof bridge.revive === 'function';
}

/** One click on the status: ask the shell to revive the pipeline. */
function revivePipeline() {
  if (reviveInFlight) {
    // The shell refuses a second respawn in flight too (`REVIVE_REFUSED`).
    // Saying it here as well keeps the panel's own words true with no round
    // trip, and keeps the second click from looking like a broken button.
    const already = 'Already restarting the pipeline…';
    setStatus(already, 'busy');
    paintReviveSentence(already);
    return false;
  }
  if (!reviveSupported()) {
    // THE HONESTY RULE, the one `applyPauseAvailability` already follows in the
    // other direction: an absent capability is STATED, never simulated. `busy`
    // and not `error` because nothing has died — this build simply cannot do
    // it, and a red light over a missing function would be a second lie.
    const missing = 'This shell cannot restart the pipeline (no bridge.revive())';
    setStatus(missing, 'busy');
    paintReviveSentence(missing);
    return false;
  }
  reviveInFlight = true;
  // THE STICKY DEATH COMES OFF THE SCREEN HERE, and this is the point of the
  // click for most owners who will ever use it. The shell holds an error until
  // a CAPTION proves recovery (AGENTS.md makes that law, `panel-exit3-oracle`
  // gates it), so "Worker stopped (exit 3)" is exactly the screen he is looking
  // at when he asks the app to try again.
  const sentence = 'Restarting the pipeline…';
  setStatus(sentence, 'busy');
  paintReviveSentence(sentence);
  // The strip says the same thing in its one word, and `updateStripState` has
  // already cleared `is-error`/`is-live` for a non-error, non-live kind.
  if (dom.stripWord) dom.stripWord.textContent = 'Restarting';
  bridge.revive('panel-status');
  // `post` is fire-and-forget and the shell answers on its own thread, so there
  // is no reply to clear the flag with. A ceiling releases it instead: without
  // one, a shell that never answered would make the panel refuse every later
  // click with "already restarting" — a control bricked by its own guard.
  window.setTimeout(() => { reviveInFlight = false; }, 10000);
  return true;
}

/** Make the status clickable, on both surfaces, from JS only. */
function wireRevive() {
  const wired = reviveSupported();
  const targets = [dom.status, dom.stripState].filter(Boolean);
  for (const el of targets) {
    el.style.cursor = 'pointer';
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    // The footer's title is nobody else's (the strip's is written by
    // `updateStripState`, which appends this same hint).
    el.title = wired ? REVIVE_TITLE : REVIVE_TITLE + ' · not in this shell yet';
    el.addEventListener('click', () => revivePipeline());
    el.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar') {
        // Space scrolls by default, and a control that moves the page under the
        // reader is not a control.
        event.preventDefault();
        revivePipeline();
      }
    });
  }
}

/**
 * OPEN THE CONFIRMATION. Two steps, in-panel, and the DEFAULT FOCUS IS CANCEL:
 * pausing is the destructive and slow one (resuming reloads the model), while
 * cancelling is a no-op, so the safe action is the one a reflex Enter takes.
 */
function openPauseConfirm(trigger) {
  if (!dom.pauseDialog) {
    // An older shell without the dialog must not lose the capability silently:
    // the panel says what it can do instead of pretending the click worked.
    setStatus('Pause needs a confirmation dialog this panel does not have', '');
    return;
  }
  applyPauseAvailability();
  // SE NAO HA PAUSE, NAO HA DIALOGO. E a correccao do *"jesus que coisa mais nojenta de
  // feia"* (dono, 2026-10-15, com o print deste dialogo na mao).
  //
  // O RACIOCINIO QUE ESTAVA AQUI, e que e defensavel: *"o trabalho do botao e ABRIR o
  // dialogo, e e no dialogo que o dono descobre o que esta shell pode e nao pode fazer"*.
  // Foi uma decisao de quem escreveu, e o dono REJEITOU-A -- e a palavra dele ganha.
  //
  // O QUE ELE VIA: um dialogo a perguntar "Pause and unload?", com um botao DESACTIVADO
  // a dizer "not available in this shell yet" e uma linha vermelha a explicar que a funcao
  // nao existe. **Oferecer uma funcao que nao existe e pior do que nao a oferecer.**
  // Esta verificacao usa o `disabled` que o `applyPauseAvailability` acabou de pos, portanto
  // nao ha uma segunda copia da verdade sobre o que esta ligado. */
  if (dom.pauseConfirmButton && dom.pauseConfirmButton.disabled) {
    setStatus('Pause is not available in this build yet', '');
    return;
  }
  pendingFocusReturn = (trigger && typeof trigger.focus === 'function')
    ? trigger
    : (document.activeElement && document.activeElement !== document.body
      ? document.activeElement : null);
  try {
    if (typeof dom.pauseDialog.showModal === 'function') dom.pauseDialog.showModal();
    else dom.pauseDialog.setAttribute('open', '');
  } catch (err) {
    dom.pauseDialog.setAttribute('open', '');
  }
  if (dom.pauseCancelButton && typeof dom.pauseCancelButton.focus === 'function') {
    try { dom.pauseCancelButton.focus(); } catch (err) { /* focus stays where it was */ }
  }
}

function closePauseConfirm() {
  if (dom.pauseDialog && dom.pauseDialog.open) {
    try { dom.pauseDialog.close(); } catch (err) { dom.pauseDialog.removeAttribute('open'); }
  } else if (dom.pauseDialog) {
    dom.pauseDialog.removeAttribute('open');
  }
  const back = pendingFocusReturn;
  pendingFocusReturn = null;
  // Focus goes BACK where it came from, and only ever inside this page.
  if (back && typeof back.focus === 'function') {
    try { back.focus(); } catch (err) { /* the element went away; no focus is taken */ }
  }
}

/** Step two: the owner confirmed. Ask the shell to unload, and say what happened. */
function confirmPause() {
  if (!pauseSupported || typeof bridge.pause !== 'function') {
    // Reached only if the button was activated programmatically; the button is
    // disabled in this state and its label already says why.
    if (dom.pauseShellNote) {
      dom.pauseShellNote.textContent = 'Este shell ainda não consegue pausar · nada será descarregado.';
      dom.pauseShellNote.hidden = false;
    }
    return;
  }
  let result = null;
  try {
    result = bridge.pause({ reason: 'panel-confirm' });
  } catch (err) {
    closePauseConfirm();
    setStatus('Pause failed: ' + errorText(err), '');
    return;
  }
  closePauseConfirm();
  if (result && typeof result.then === 'function') {
    result.then((payload) => {
      const ok = !payload || payload.paused !== false;
      if (!ok) {
        setStatus('The shell refused to pause', 'error');
        return;
      }
      setPaused(true, payload && payload.text ? String(payload.text) : null);
    }).catch((err) => {
      setStatus('Pause refused: ' + errorText(err), 'error');
    });
    return;
  }
  setPaused(true, null);
}

/**
 * The paused LOOK, on both surfaces. It does not claim the engines are gone —
 * only the shell can know that — it says the panel asked and is not transcribing.
 */
function setPaused(value, text) {
  paused = Boolean(value);
  paintPauseControls();
  if (dom.panel) dom.panel.classList.toggle('is-paused', paused);
  // The paused state is reported by the strip's one word. `setStatus` below
  // carries it into the snapshot that word reads, so one repaint is enough.
  if (paused) setStatus(text || 'Paused · engines unloaded', '');
  updateStripState();
}

/** Ask the OS file manager to open the entry's file, or the root when null.
 *  THE ONLY "show in folder" AFFORDANCE NOW, on both surfaces: the transcript
 *  bar's path button (`#history-root`) and the per-line button in the drawer
 *  both call this. The deleted HUD's duplicate button called it too. */
function revealPath(path) {
  if (!historyApi || !historyApi.reveal) {
    setHistoryNote('Show in folder unavailable: this shell has no transcript store');
    return;
  }
  historyApi.reveal(path || null);
  setHistoryNote(path ? 'Opening ' + path : 'Opening the transcript folder');
}

/** Save the transcript as a compact .txt and open its folder.
 *
 *  A download dialog is a window on the owner's screen, so the SHELL writes the
 *  file (`history-export-file`) and this reveals it -- the folder button's
 *  gesture. The body is the API's own compact line, context included.
 */
function exportTranscript() {
  if (!historyApi || typeof historyApi.exportFile !== 'function') {
    setHistoryNote('Export unavailable: this shell has no transcript store');
    return;
  }
  setHistoryNote('Exporting the transcript…');
  historyApi.exportFile('txt', 5000).then((res) => {
    const path = res && res.path ? String(res.path) : '';
    const count = res && res.entries ? Number(res.entries) : 0;
    if (!path) {
      setHistoryNote(count ? 'Export failed: ' + ((res && res.error) || 'no path')
        : 'Nothing to export: the transcript is empty');
      return;
    }
    const capped = count >= 5000;
    setHistoryNote(`Exported ${count} line${count === 1 ? '' : 's'}`
      + (capped ? ' (newest 5000)' : '') + ` · ${path}`);
    if (typeof historyApi.reveal === 'function') historyApi.reveal(path);
  }).catch((err) => setHistoryNote('Export failed: ' + errorText(err)));
}

/**
 * THE SEARCH IS A GLYPH UNTIL IT IS ASKED FOR (owner, 2026-11-06, verbatim):
 * *"tira a BARRA de pesquisa de historico, deixa so um botao pequeno com o simbolo
 * de pesquisa."*
 *
 * The bar used to be a permanent row above the feed: a text field, a Search button
 * and a Clear button, three pieces of chrome over a transcript the owner mostly
 * reads. Now the row holds one 24 px magnifier. Pressing it opens the field beside
 * it, focuses it, and Escape (or a second press) closes it and puts the feed back.
 *
 * NOTHING IN `runSearch` CHANGED: the same predicate, the same ranking, the same
 * `searchQuery` state. This is the input surface, and only the input surface.
 */
function wireHistorySearch() {
  const button = document.getElementById('history-search-button');
  const input = document.getElementById('history-search');
  const tools = document.querySelector('.history__tools');
  if (!input) return;
  // NO PLACEHOLDER SENTENCE (owner, 2026-11-09). The field is revealed by the
  // glyph, so its label lives in `aria-label`; the visible slot stays empty.
  input.placeholder = '';
  const open = Boolean(tools) && tools.classList.contains('is-searching');
  const paint = (next) => {
    if (tools) tools.classList.toggle('is-searching', next);
    if (button) button.setAttribute('aria-expanded', next ? 'true' : 'false');
    if (!next) {
      input.value = '';
      if (searchQuery) runSearch('');
    }
  };
  if (button) {
    button.addEventListener('click', () => {
      const next = !(tools && tools.classList.contains('is-searching'));
      paint(next);
      if (next) {
        input.focus();
        input.select();
      }
    });
  }
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      const value = input.value;
      if (String(value).trim()) runSearch(value);
      else paint(false);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      paint(false);
      input.blur();
    }
  });
  void open;
}

async function runSearch(rawQuery) {
  const query = String(rawQuery == null ? '' : rawQuery).trim();
  if (!query) {
    searchQuery = '';
    searchHits = [];
    if (dom.searchClear) dom.searchClear.hidden = true;
    setHistoryNote('');
    renderFeed();
    return;
  }
  if (!historyApi || !historyApi.search) {
    setHistoryNote('Search unavailable: this shell has no transcript store');
    return;
  }
  if (!canonicalProducer) {
    // D1 — the box is disabled for this reason, and a programmatic submit
    // (a probe, or a click on the Search button) gets the same note instead of an
    // empty result set that looks like "no matches". Named as a CAUSE, not a
    // sentence, per the owner's 2026-11-09 order: *"ZERO frases explicativas em
    // qualquer parte"* — it used to read "Search is off · nothing writes the
    // transcript yet."
    setHistoryNote('Search is off · no transcript store');
    return;
  }
  searchQuery = query;
  if (dom.searchClear) dom.searchClear.hidden = false;
  try {
    const r = await historyApi.search(query, 200);
    searchHits = normaliseEntries(r, 'hits');
    renderSearchResults(query, searchHits);
  } catch (err) {
    setHistoryNote('Search failed: ' + errorText(err));
  }
}

function renderSearchResults(query, hits) {
  if (!dom.historyList) return;
  clearList();
  const list = (Array.isArray(hits) ? hits : []).filter(withinHistoryWindow).filter(viaVisible);
  if (!list.length) {
    setHistoryNote('');
    return;
  }
  for (const hit of list) dom.historyList.append(makeRow(hit, query));
  setHistoryNote('');
  const scroller = historyScroller();
  if (scroller) scroller.scrollTop = 0;
}

// -- small helpers ----------------------------------------------------------

function normaliseEntries(result, key) {
  if (Array.isArray(result)) return result;
  if (result && Array.isArray(result.entries)) return result.entries;
  if (key && result && Array.isArray(result[key])) return result[key];
  if (result && Array.isArray(result.hits)) return result.hits;
  return [];
}

function matches(text, query) {
  return String(text || '').toLowerCase().indexOf(query.toLowerCase()) >= 0;
}

/** Split `text` into plain runs and {mark} runs for the first match of `query`. */
function highlight(text, query) {
  const at = text.toLowerCase().indexOf(String(query).toLowerCase());
  if (at < 0) return [text];
  return [text.slice(0, at), { mark: text.slice(at, at + query.length) }, text.slice(at + query.length)];
}

function sameEntry(a, b) {
  return (a.path || '') === (b.path || '') && (a.time || '') === (b.time || '')
    && (a.text || '') === (b.text || '');
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function clockTime() {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

/**
 * THE STAMP IS THE HOUR, AND NOTHING ELSE (owner, 2026-11-06): *"tambem tira a
 * data de mostrar o historico do painel na direita."*
 *
 * The date used to be prepended for any line from another day, which is how a
 * `11-05 23:41:07` chip ended up in the bar he was reading. The feed now spans at
 * most `HISTORY_RETENTION_H`, so the day is context the owner already has and the
 * hour is what he reads.
 */
function stampFor(entry) {
  const time = String(entry.time || '');
  return time.slice(0, 8) || time;
}

/**
 * THE DAY, FOR WHEN THE FEED SPANS MONTHS (2026-11-09).
 *
 * `stampFor` shows the hour only, by the owner's 2026-11-06 order. That order
 * assumed the 48 h window it was written in; the window is 180 days now, so the
 * same hour from two different days is one chip on screen. The date therefore
 * rides in the row's `title` -- no new text in the bar, and the day is one hover
 * away instead of gone. Returns '' when the entry carries no date, so a row
 * without one keeps no misleading tooltip.
 */
function fullStampFor(entry) {
  const date = String((entry && entry.date) || '');
  const time = String((entry && entry.time) || '').slice(0, 8);
  if (!date) return '';
  return `${date} ${time}`.trim();
}

/**
 * The entry's own instant, or NaN when it cannot be read.
 *
 * The store's line is `<YYYY-MM-DD>/<HH>.md` plus a `HH:MM:SS` stamp, so both
 * halves are already on the entry -- nothing here guesses a date from "today".
 */
function entryAt(entry) {
  if (!entry || !entry.date) return NaN;
  const time = String(entry.time || '00:00:00');
  const at = Date.parse(`${entry.date}T${time.slice(0, 8)}`);
  return Number.isFinite(at) ? at : NaN;
}

/**
 * THE HISTORY NOTE NEVER PAINTS A SENTENCE (owner, 2026-11-09: *"NO EXPLANATORY
 * PROSE IN ANY PANEL"*). This slot used to carry "No transcript yet.", "Search
 * is off · nothing writes the transcript yet.", "Exported N lines …" and the
 * match count. The state they described is still kept in the internal values
 * (`canonicalProducer`, `historyEntries.length`, `searchHits`), and the element
 * stays in the DOM for the probes that read it, but it holds no text: every
 * caller below keeps calling it, and the function is the ONE place that decides
 * the slot is empty.
 */
function setHistoryNote(text) {
  void text;
  if (!dom.historyStatus) return;
  dom.historyStatus.textContent = '';
  dom.historyStatus.hidden = true;
}

function errorText(err) {
  return err && err.message ? err.message : String(err);
}

// ---------------------------------------------------------------------------
// Status + controls + readiness (unchanged behaviour, new placeholders).
// ---------------------------------------------------------------------------

function wireStatus() {
  bridge.onStatus((payload) => {
    // F8 — ONE CLASSIFIER, NOT TWO.
    //
    // This used to re-derive the severity from the PROSE with
    // `/stopped|error|dead|no audio|no working/i`, a regex that cannot see this
    // worker's own vocabulary: `silent-device`, `device-exhausted`, and a bare
    // `done` with NO verdict all matched nothing, so a dead worker was painted
    // with the same neutral styling as warm-up. The shell already decides
    // (worker_status_kind, ported from the Electron bridge's STATE_MAP), so the
    // panel now BELIEVES it. Both shapes are accepted: the WebView2 shell sends
    // `{text, kind}`, the earlier Electron arm sends a bare string.
    const { text, kind } = statusPayload(payload);
    if (!text) return;

    // A status change is a natural sentence boundary: close the held tail so
    // the last words are not stranded when the worker pauses mid-thought.
    // EVERY WORKER's engine (STEP 4), or one app's tail is stranded while the
    // other's is closed.
    //
    // AND NOT THE PLAYER'S. THE OWNER'S OWN LOG, 2026-10-21 18:26 (his
    // session, `_main/webview-run.log`), the same sentence painted twice:
    //     18:26:13.632  CAPTION_APPLIED "Estamos aqui já, já fiz o login e ele já." count=6
    //     18:26:13.640  STATUS_APPLIED  "device-rotated (flat)"
    //     18:26:19.967  CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s
    //     18:26:21.665  CAPTION_APPLIED "Estamos aqui já, já fiz o login e ele já." count=7
    //     18:26:21.667  STATUS_APPLIED  "capture-started"
    // The worker's status is the SHELL'S word about the WORKER, and this machine
    // restarts the worker constantly (`device-rotated`, `capture-started`), so
    // every one of those restarts closed the PLAYER's line too -- and the close
    // PAINTED it again, eight seconds later, AFTER the caption window had
    // already blanked itself for six seconds of silence. The sentence came back
    // out of nowhere, which is what the owner reported.
    //
    // The player's line has its own boundary and it is the PLAYER's: the shell
    // sends `final:true` for a closed cue (`sotto_webview.py:9144`), and the
    // panel's `wireExternalCaptions` closes it with `flush('external-final')`.
    // Nothing is stranded by leaving it alone -- and the `external:` prefix is
    // the codebase's own convention for "these words are the PLAYER's"
    // (`panel.js:1056`).
    for (const [key, engine] of engines.entries()) {
      if (key !== null && key.indexOf('external:') === 0) continue;
      engine.flush('status-change');
    }

    const state = statusKind(kind);
    // ONE place records what the shell said, so the strip's single word is
    // painted from that one fact (see `updateStripState`).
    statusSnapshot = { text, kind: kind || null };
    updateStripState();
    if (state === 'error') {
      // An error status keeps the SHELL'S TEXT as the headline — it is the
      // sentence that names the device and the numbers. The readiness copy must
      // never overwrite it.
      setStatus(text, 'error');
      showReadiness({ title: 'Not transcribing', body: text }, true);
      return;
    }
    if (state === 'no-audio') {
      // THE CALM STATE. Same treatment as an error except the colour: the
      // SHELL'S TEXT stays the headline (it names the device and the peak), and
      // the readiness copy must never overwrite it — but the paint is the calm
      // one, not red. The owner's verbatim complaint was "com erro vermelho"
      // on every cold start with a quiet desktop; the red is now reserved for
      // a worker that FAILED.
      setStatus(text, 'no-audio');
      showReadiness({ title: 'No audio to transcribe', body: text }, true);
      return;
    }
    if (state === 'live') {
      // Captions are flowing. The footer goes live; the placeholder is left
      // alone because readiness copy is only for the NEUTRAL states, and a real
      // caption has already put the placeholder away.
      setStatus(text, 'live');
      return;
    }
    // Neutral (the shell's `busy`, an empty kind, or a kind this panel does not
    // know): the footer carries the shell's sentence and the placeholder carries
    // the one honest warm-up state, with the measured seconds.
    setStatus(text, '');
    showReadiness(window.SottoFormulation.describeReadiness(Date.now() - pipelineStartedAt));
  });

  bridge.onGeometry((geometry) => {
    // The renderer is told the real slab size so CSS can match the window
    // instead of guessing, which is how a panel ends up misaligned on a
    // different monitor.
    if (geometry && geometry.width) {
      document.documentElement.style.setProperty('--panel-width', `${geometry.width}px`);
    }
    // AND WHICH SURFACE that size belongs to. `place_panel` resizes the window
    // to the strip's dock or the panel's, and that resize used to be the only
    // signal: the document kept `data-surface="panel"` inside a 1040x150 strip
    // window, so the panel's own grid squeezed `.captions` to zero height and
    // `.stripbar` never left `display:none` -- Alt+C opened a bar with no live
    // box and no controls. Measured 2026-10-09 (`body=1040x150
    // surface=panel`).
    //
    // The name is REFUSED when it is not one of the two the panel owns
    // (`SottoSurfaces.set` returns the CURRENT surface for an unknown name), so
    // a shell that omits the field, or sends a misspelling, leaves the document
    // exactly where it was rather than guessing. That is why this is safe to
    // call on every geometry message.
    if (geometry && typeof geometry.surface === 'string') {
      setSurface(geometry.surface);
    }
  });
}

/**
 * Read ONE status event into `{text, kind}`.
 *
 *   `{text:'…', kind:'error'|'live'|'busy'}`  the WebView2 shell (the app)
 *   `'…'`                                     the Electron arm (a bare string)
 *
 * Anything else — a missing payload, a non-string text — is `{text:'', kind:null}`,
 * i.e. no state change, never a guess.
 */
function statusPayload(payload) {
  if (typeof payload === 'string') return { text: payload, kind: null };
  if (payload && typeof payload === 'object') {
    const text = typeof payload.text === 'string' ? payload.text : '';
    const kind = typeof payload.kind === 'string' ? payload.kind.trim().toLowerCase() : '';
    return { text, kind: kind || null };
  }
  return { text: '', kind: null };
}

/**
 * The shell's kind, VERBATIM: `'error'` -> error, `'live'` -> live, everything
 * else (its `'busy'`, an empty string, a word nobody taught this panel) ->
 * neutral. No prose is read here, and no word list is re-invented: the fallback
 * that classified by regex is the defect this replaces.
 */
function statusKind(kind) {
  if (kind === 'error') return 'error';
  if (kind === 'live') return 'live';
  // THE CALM STATE (owner, 2026-10-14): the worker reported that the endpoint
  // it opened carries nothing to transcribe. NOT a fault -- red would read as
  // "coisa nao carregada" (his own words for the defect) -- and not warm-up
  // either, so the worker's own sentence stays on screen.
  if (kind === 'no-audio') return 'no-audio';
  return '';
}

/**
 * The "behind" chip in the live bar — OPTIONAL, and silent when unsupported.
 *
 * It is subscribed ONLY when the hosting shell exposes `onStats` — and the
 * WebView2 shell DOES (`sotto_webview.py` `onStats` :2601, `getStats` :2641), so
 * it subscribes; the chip then appears only if a payload carries the field it
 * reads, which is a MEASUREMENT question, not a wiring one. (This comment said
 * "neither shell does today, so this returns immediately" until 2026-10-11;
 * re-measured and corrected — the stale form was a false claim about the shell.)
 * The day the shell measures queue drops or a decode rate under real time, the
 * panel lights up by itself. Fail-closed in the same way as the rest of this file: a
 * missing field is not a fact, so it cannot make the chip appear.
 */
/**
 * THE LEVEL CONSUMER — real data or nothing.
 *
 * `pushLevel` is fed ONLY by a payload that actually carries a level. A missing
 * field is not a measurement, so it cannot make the bars move; the fallback is
 * `LEVEL_FLOOR` and `data-level="none"`, which is the honest picture of a panel
 * that has not been told anything.
 *
 * The smoothing is the part that makes a wave readable: an INSTANT attack (a
 * transient must not be softened away) and a ~200 ms release, applied per
 * measurement rather than per frame, so the shape does not depend on the frame
 * rate.
 */
function pushLevel(peak, blocks) {
  const value = Number(peak);
  if (!Number.isFinite(value)) return;
  const now = (typeof performance !== 'undefined' && performance.now)
    ? performance.now() : Date.now();
  const dt = LEVEL.at === null ? 0 : Math.max(0, now - LEVEL.at);
  LEVEL.at = now;
  const clamped = Math.max(0, Math.min(1, value));
  if (clamped >= LEVEL.level || dt === 0) {
    LEVEL.level = clamped;
  } else {
    // Exponential release towards the new value; `dt` is the real gap between
    // measurements, so a slow feed releases proportionally.
    const k = 1 - Math.exp(-dt / LEVEL_RELEASE_MS);
    LEVEL.level = LEVEL.level + (clamped - LEVEL.level) * k;
  }
  LEVEL.hist[LEVEL.head] = LEVEL.level;
  LEVEL.head = (LEVEL.head + 1) % LEVEL.hist.length;
  LEVEL.n = Math.min(LEVEL.n + 1, LEVEL.hist.length);
  LEVEL.have = true;
  LEVEL.blocks = Number.isFinite(Number(blocks)) ? Number(blocks) : LEVEL.blocks;
  paintLevel();
}

/** The five bars, from the smoothed history. `scaleY` only: no relayout. */
function paintLevel() {
  // The frozen skin's own meter, fed from the SAME smoothed history our bars use.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.level(LEVEL.have ? LEVEL.level : 0);
  }
  const bars = document.querySelectorAll('.chrome__meter i');
  // The floated caption's own meter, fed the SAME smoothed level the five bars use.
  // One number, every surface: the owner's meter is the meter.
  if (window.SottoCaptionFloat) {
    window.SottoCaptionFloat.setMeter(LEVEL.have ? LEVEL.level : 0);
    window.SottoCaptionFloat.setListening(LEVEL.have);
  }
  if (!bars.length) return;
  const want = LEVEL.have ? 'live' : 'none';
  if (document.body.dataset.level !== want) document.body.dataset.level = want;
  if (!LEVEL.have) {
    // Nothing to paint: clear the properties so the CSS floor applies, and say
    // so once rather than on every call.
    for (const bar of bars) bar.style.removeProperty('--meter-h');
    return;
  }
  // Five bars, oldest-to-newest across the most recent fifth of the history, so
  // the row reads as a short envelope rather than five copies of one number.
  const span = Math.max(1, Math.floor(LEVEL.n / bars.length));
  for (let i = 0; i < bars.length; i += 1) {
    const back = (bars.length - 1 - i) * span;
    const idx = (LEVEL.head - 1 - back + LEVEL.hist.length * 2) % LEVEL.hist.length;
    const v = LEVEL.hist[idx];
    bars[i].style.setProperty('--meter-h', String(Math.max(LEVEL_FLOOR, v).toFixed(3)));
  }
}

/**
 * The stats channel, if this shell has one. The WebView2 shell HAS one: it
 * exposes `onStats` (`sotto_webview.py:2601`) and `getStats` (`:2641`), so this
 * subscribes and the bars DO follow `fields.peak`/`fields.blocks`.
 *
 * THIS COMMENT SAID THE OPPOSITE UNTIL 2026-10-11 ("the shell exposes neither
 * `onStats` nor `getStats`, so this returns immediately and the bars stay at the
 * floor") — measured FALSE, and it is why two readers believed the wave was
 * already wired end to end. It then said the missing half was the PRODUCER, and
 * that was TRUE when it was written: `worker/sotto_worker.py` did not emit the
 * `{"type":"meter","peak":…,"blocks":…}` event the shell's `elif kind == 'meter':`
 * branch (`:7475`) parses, so the only input this could receive was the 10 s
 * `WORKER_STATS` running maximum — a staircase that only rises, which IS the
 * owner-reported defect (`_main/receipt-20261011-meter-chain-gap.md`).
 *
 * THE PRODUCER EXISTS NOW — measured 2026-10-11 on `worker/sotto_worker.py` 304762 B
 * sha256 `771ACA94…`: the meter is built ONCE on the live audio path
 * (`AudioMeter(meter_hz, now=time.time(), block_s=block_ms / 1000.0)`, `:4663`), ticked
 * with the SAME per-block peak the tap already had (`:4745`) and emitted as one event
 * per window (`:4747`) behind `if meter.enabled:` (`:4744`); the rate is
 * `--meter-hz` > `SOTTO_METER_HZ` > 10.0 and `--meter-hz 0` is inert. So the chain is
 * complete IN CODE. **NOT MEASURED, and this is the half that matters: the wire has
 * never been exercised.** No meter event has been seen crossing a real stdout pipe into
 * the shell and on to this subscriber, because the owner's stop order forbids launching
 * the app; the evidence is the bytes on both sides plus two in-process oracles
 * (`_main/meter-chain-oracle.py`, `_main/audio-meter-oracle.py`), not a painted bar.
 *
 * A payload is trusted only for the fields it actually carries — `stats.peak`
 * absent means NO measurement, never a zero.
 */
function wireLevel() {
  if (typeof bridge.onStats !== 'function' && typeof bridge.getStats !== 'function') {
    if (document.body) document.body.dataset.level = 'none';
    return;
  }
  if (document.body) document.body.dataset.level = 'none';

  function take(raw) {
    let payload = raw;
    if (typeof payload === 'string') {
      try { payload = JSON.parse(payload); } catch { return; }
    }
    if (!payload || typeof payload !== 'object') return;
    const fields = payload.stats && typeof payload.stats === 'object' ? payload.stats : payload;
    /* O PAUSE E' DO SHELL, NAO DESTA PAGINA (owner, 2026-11-06, verbatim):
     * *"o botao de pause tambem nao ta completo. o botao nao muda pra unpause."*
     *
     * The glyph already flipped on the click, but `paused` was a LOCAL variable:
     * hide the panel and show it again while the engines are unloaded and the
     * button painted PAUSE over a paused shell -- the one state where it lies.
     * The shell now stamps `paused` on the stats payload it already sends every
     * second, and this is the only place that reads it.
     *
     * ABSENT IS NOT FALSE: a payload without the field is "not told", so the
     * local state stays exactly as it was and an older shell keeps working. */
    if (typeof fields.paused === 'boolean' && fields.paused !== paused) {
      setPaused(fields.paused, null);
    }
    pushLevel(fields.peak, fields.blocks);
  }

  if (typeof bridge.onStats === 'function') bridge.onStats(take);
  if (typeof bridge.getStats === 'function') {
    const pull = () => {
      try {
        const result = bridge.getStats();
        if (result && typeof result.then === 'function') result.then(take).catch(() => {});
        else take(result);
      } catch (err) { /* a stats read must never break the panel */ }
    };
    pull();
    setInterval(pull, 1000);
  }
}

function wireStats() {
  if (typeof bridge.onStats !== 'function' || !dom.statsChip) return;
  bridge.onStats((raw) => {
    let stats = raw;
    if (typeof stats === 'string') {
      try {
        stats = JSON.parse(stats);
      } catch {
        return; // an unreadable event is not a reason to claim anything
      }
    }
    if (!stats || typeof stats !== 'object') return;
    const drops = Number.isFinite(Number(stats.queue_drops)) ? Number(stats.queue_drops) : null;
    const rate = Number.isFinite(Number(stats.rate)) ? Number(stats.rate) : null;
    const behind = (drops !== null && drops > 0) || (rate !== null && rate < 1);
    if (!behind) {
      // Recovery is symmetric: the chip goes away when the numbers do.
      dom.statsChip.hidden = true;
      dom.statsChip.textContent = '';
      return;
    }
    const bits = [];
    if (drops !== null && drops > 0) bits.push(`${drops} dropped`);
    if (rate !== null && rate < 1) bits.push(`${rate.toFixed(2)}×`);
    dom.statsChip.textContent = `behind · ${bits.join(' · ')}`;
    dom.statsChip.title = 'The live path is not keeping up with real time '
      + '(queue drops, or a decode rate under 1×). Captions may lag the speaker.';
    dom.statsChip.hidden = false;
  });
}

/**
 * Paint the readiness state into the placeholder area — the one place the
 * owner looks before the first caption exists.
 */
function showReadiness(readiness, isError) {
  if (!dom.placeholder) return;
  const title = dom.placeholder.querySelector('.captions__placeholder-title');
  const body = dom.placeholder.querySelector('.captions__placeholder-body');
  // P1-3 (2026-10-08 audit): each of the five directions owns its empty state —
  // the mockups' `AGUARDANDO ÁUDIO…` / `· · · aguardando fala` are not one
  // string in five fonts. The readiness state (warming vs ready vs error) still
  // decides WHICH message, the theme decides the VOICE. Error keeps the shell's
  // own sentence: an error must name its cause, never wear a costume.
  const theme = (document.documentElement.dataset && document.documentElement.dataset.theme) || 'theme-1';
  // THE WORDS ARE `ready` / `not ready` (owner, 2026-10-21): *"e para de falar
  // 'speak and the line flows' como se fosse uma frase de efeito. é simples:
  // ready, not ready."* The design keeps its own TYPE for these two words; it no
  // longer writes a sentence of its own.
  const voices = {
    'theme-1': { warming: 'not ready', ready: 'ready' },
    'theme-2': { warming: 'not ready', ready: 'ready' },
    'theme-3': { warming: 'not ready', ready: 'ready' },
    'theme-4': { warming: 'not ready', ready: 'ready' },
    'theme-5': { warming: 'not ready', ready: 'ready' },
  };
  const voice = voices[theme] || voices['theme-1'];
  if (title) title.textContent = readiness.state === 'warming' ? voice.warming : voice.ready;
  if (body) body.textContent = '';
  dom.placeholder.classList.toggle('captions__placeholder--warming', !isError);
  if (dom.list && !dom.list.childElementCount) dom.placeholder.hidden = false;
}

/**
 * The ONE word a frozen skin's status badge shows.
 *
 * The design's own vocabulary for the case where it is TRUE — a mockup's
 * `listening` / `paused` badge says exactly what this state is — and plain words
 * for everything else. Never a number, never a confidence: this panel measures
 * neither, and `panel.js`'s own status line (which floats over the skin) is where
 * the worker's cause is printed in full.
 *
 * @param {'live'|'error'|''} state
 */
function skinStateWord(state) {
  // THE BADGE SAYS `ready` / `not ready` (owner, 2026-10-21). The mockup's own
  // vocabulary (`listening` / `paused` / `error`) is a costume the owner asked
  // off: *"é simples: ready, not ready"* and *"para de mostrar erro no painel"*.
  if (state === 'live') return 'ready';
  return 'not ready';
}

/** @param {'live'|'error'|''} state */
function setStatus(text, state) {
  if (!text) return;
  // ── THE SENTENCE IS OFF THE SCREEN EXCEPT WHEN IT IS A DEATH ───────────────
  // The owner ruled, verbatim (2026-10-08): *"tira o 'receiving captions'. deixa
  // só um icone dinamico"* — the healthy state becomes an ICON that changes with
  // the state, not a phrase. `Receiving captions` was the phrase he named.
  //
  // THE ONE EXCEPTION IS AN ERROR, AND IT IS DELIBERATE: `AGENTS.md` makes it law
  // that the panel names the worker's own cause and the DEVICE ("the panel text
  // must name the device, and the death must survive the automatic restart until
  // a CAPTION proves recovery"), and `_main/panel-exit3-oracle.py` gates exactly
  // that. An icon cannot name a device, so an error still paints its sentence and
  // the icon turns red beside it. He asked for the phrase he sees all day to go;
  // he did not ask for a silent death. Stated in the receipt as an exception.
  // THE CALM STATE KEEPS ITS SENTENCE TOO (owner, 2026-10-14). It is not a death,
  // so the icon is not red — but the sentence IS the report ("Silent audio
  // device - <device> [MME] peaked 9.2e-05 < floor 0.002"), and an icon cannot
  // say that. Same access rule as the error path: never off screen.
  // ── THE PANEL SHOWS ONLY `ready` / `not ready` (owner, 2026-10-21) ─────────
  // Verbatim: *"é simples: ready, not ready. e para de mostrar erro no painel. ou
  // que algo parou."* The worker's own cause is NOT deleted -- it is MOVED into the
  // 3-dot menu (`#panel-menu-cause`), which the owner chose, so the panel stays
  // calm and the device/death is still one click away and still on the record
  // (`_main/panel-exit3-oracle.py` was re-baselined to read it there).
  // A PALAVRA SAI DO ECRA (dono, 2026-11-08, verbatim: *"tira qualquer coisa que
  // diz READY embaixo dos temas"*). A ordem de 2026-10-21 que criou `ready` /
  // `not ready` continua cumprida -- no ICONE: o ponto muda por
  // `statusDot.dataset.state`, e o texto segue escrito no DOM para leitor de
  // tela e para os oraculos, permanentemente fora do ecra pela classe que o
  // `panel.css:1541` ja' define. Um `ready` verde fixo embaixo dos temas nao
  // informa nada e ele pediu que saia.
  const word = state === 'live' ? 'ready' : 'not ready';
  if (dom.statusText) {
    dom.statusText.textContent = word;
    dom.statusText.classList.add('status__text--offscreen');
  }
  const cause = (state === 'error' || state === 'no-audio') ? String(text || '') : '';
  document.documentElement.dataset.workerCause = cause;
  const causeEl = document.getElementById('panel-menu-cause');
  if (causeEl) {
    causeEl.textContent = cause;
    causeEl.hidden = !cause;
  }
  if (dom.statusDot) dom.statusDot.dataset.state = state || '';
  if (dom.status) {
    dom.status.classList.toggle('status--live', state === 'live');
    dom.status.classList.toggle('status--error', state === 'error');
    dom.status.classList.toggle('status--noaudio', state === 'no-audio');
  }
  // THE SAME FACT, IN A PLACE THE WHOLE SLAB CAN SEE (2026-10-08). The per-theme
  // state words (`LENDO`/`PAUSA`, `REC`/`STBY`, `ON`/`OFF`, `OUVINDO`/`PAUSA`)
  // live in the header AND in the footer, and `status--live` is a class on the
  // footer alone — CSS cannot select a header from a sibling's class. Mirroring
  // the SAME `state` argument onto `<body data-state>` is one write, adds no
  // second source of truth (it is literally this argument), and is what lets
  // every direction's own indicator light up. Absent/unknown state is the empty
  // string, so "no state" is a value and never a stale one.
  document.body.dataset.state = state || '';
  // The panel's OWN statuses land in the same snapshot the shell's do: the strip
  // would otherwise keep showing a stale shell sentence after Clear.
  statusSnapshot = { text, kind: state || null };
  updateStripState();
  // ── THE STATE WORD ON A FROZEN SKIN ───────────────────────────────────────
  // The design's own badge is a real slot with the design's own typography; what
  // goes in it is OUR state, in the design's own vocabulary for the one case where
  // the design's word is true ("listening") and in plain words for the rest. No
  // number and no confidence is ever printed there — see `skin-host.js`.
  if (window.SottoSkin && SottoSkin.active) {
    SottoSkin.status({ word: skinStateWord(state), state: state || '' });
  }
  bridge.statusApplied(text);
}

function wireControls() {
  // Click-through is ON by default: the shell creates this window with
  // WS_EX_TRANSPARENT (sotto_webview.py:3991, the port of Electron setIgnoreMouseEvents
  // with forward=true) because the slab floats OVER another application and must not
  // swallow clicks meant for it. Turn it off while the pointer is over the slab so
  // these buttons are actually clickable, and put it back on the way out.
  //
  // CORRECTED 2026-10-12: this comment used to say it was on for the transparent
  // margin, naming the transparent band around a centred max-content pill. That band
  // is GONE -- the bar now FILLS the window (panel.css rule 1, THE WINDOW IS THE BAR),
  // which is the fix for the owner report of a solid colour with the bottom panel in
  // the middle of it. The click-through was never about a margin: it is about the
  // window floating over another application, and that reason survives unchanged.
  // Guarded: a harness or an older markup without #panel/#hide-button must not
  // throw here — that throw aborts the whole init block with a blank panel.
  const setInteractive = (active) => bridge.setPointerInteractive(active);
  if (dom.panel) {
    dom.panel.addEventListener('mouseenter', () => setInteractive(true));
    dom.panel.addEventListener('mouseleave', () => setInteractive(false));
  }

  if (dom.hideButton) dom.hideButton.addEventListener('click', () => bridge.hide());

  // TWO HANDLERS USED TO LIVE HERE. Both controls were removed from `panel.html` by
  // the owner, and both handlers went with them in the SAME edit — `wireControls` is
  // called once at module init, so a surviving `dom.clearButton.addEventListener`
  // would have been a `TypeError` on every launch with a blank panel and no captions.
  //
  //  • QUIT — the capability is NOT lost. `bridge.quit()` is still reachable: the tray
  //    menu carries "Quit Sotto" (the `ID_TRAY_QUIT` item in
  //    `app/webview/sotto_webview.py`) and `_main/tray-quit-probe.py` is the probe
  //    that established it. The panel can therefore still close the app.
  //
  //  • CLEAR — the capability IS unreachable, and this is the honest cost of the
  //    removal rather than a claim that nothing was lost. It was the ONLY caller of
  //    an engine's `reset()`; the body that went with it also did
  //    `retireProvisional()` (now per source), dropped `holdTimer`, emptied
  //    `#caption-list`, reset `committedByStart`, restored the placeholder and told
  //    the shell via `bridge.clearApplied(0)`. Nothing else calls any engine's
  //    `reset()` and there is no tray equivalent, so after this edit the live box
  //    can only be emptied by the worker's own `final:true` line boundary. Reported
  //    to the owner, not hidden: receipt §11.
}

/** Tell main the page is painted and what it is showing. */
function announceReady() {
  if (!dom.placeholder || !dom.list) return;
  const placeholder = dom.placeholder.textContent.replace(/\s+/g, ' ').trim();
  bridge.ready({
    captions: dom.list.childElementCount,
    placeholder,
    hasBridge: true,
  });
}

// ---------------------------------------------------------------------------
// THE DIRECTION'S OWN CLOCK (2026-10-08)
// ---------------------------------------------------------------------------
// `bcast` prints a timecode in its header (`CH·01` … `HH:MM:SS` in the mockup).
// A clock that never ticks is a screenshot, so the elements the markup marks
// `data-chrome-clock` are repainted once a second.
//
// THE COST IS DELIBERATE AND TINY: one `setInterval` at 1 Hz writing a 8-char
// string into 0 or 1 elements (`display: none` blocks are not in the document's
// painted tree, but `textContent` is still written to them — so the write is
// gated on the element being the ACTIVE theme's, which is one `offsetParent`
// read per second). It is NOT a rAF loop and it animates nothing:
// `_main/_panel-anim-cost-arm.py` measures the panel with it running.
//
// It is armed HERE, at the bottom of the module, and not in the init block: it
// touches no state the init block owns, and arming it later cannot delay the
// first paint.
(function startChromeClock() {
  const nodes = document.querySelectorAll('[data-chrome-clock]');
  if (!nodes.length) return;
  const tick = () => {
    const now = clockTime();
    for (const el of nodes) {
      // `offsetParent === null` is the cheap "this element is not rendered"
      // test (`display: none` anywhere up the tree). A hidden direction's clock
      // is not worth a DOM write.
      if (el.offsetParent === null) continue;
      if (el.textContent !== now) el.textContent = now;
    }
  };
  tick();
  setInterval(tick, 1000);
}());
