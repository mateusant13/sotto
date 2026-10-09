# Font families named anywhere (exact family names, and which weights are requested)

No `@font-face`, no `<link>`, no font file is declared in any of the seven files. Every family below is
only *named* — the actual loading (Google Fonts etc.) happens outside this list. Weights are the only
numbers attached to type in the code.

| exact family string as written | where | weights requested |
|---|---|---|
| `"Inter", sans-serif` | `themes.ts` `fonts.ui` in 02,03,04,06,07,09,10,15,17,18,20 and `fonts.display`/`fonts.caption` in 07,17; also `--font-sans` in `index.css` | caption weight **400** only (themes that use Inter as `caption`: 07 `1.42rem`/400, 17 `1.5rem`/300 → Inter is asked for **300 and 400** across the set) |
| `"Manrope", sans-serif` | 01 (ui+display+caption), 12 (ui+caption), 14 (ui+caption), 17 (`fonts.display`) | caption weight **300** (01, 14) and **400** (12); display/UI have no weight declared |
| `"Fraunces", serif` | 02 (display+caption), 05 (display), 07 (display), 08 (display), 12 (display), 14 (display), 15 (display+caption), 19 (display) | caption weight **400** (02, 15) |
| `"Cormorant Garamond", serif` | 03 (display+caption), 04 (display), 10 (display+caption) | caption weight **400** |
| `"Newsreader", serif` | 04 (caption), 06 (display+caption), 18 (display+caption), 20 (display+caption) | caption weight **300** (06) and **400** (04, 18, 20) |
| `"Jost", sans-serif` | 05 (ui+caption), 08 (ui+caption), 13 (ui+display+caption), 19 (ui+caption) | caption weight **300** (13) and **400** (05, 08, 19) |
| `"Lora", serif` | 11 (ui+display+caption), 16 (ui+display+caption) | caption weight **400** |
| `"Instrument Serif", serif` | 09 (display+caption) | caption weight **400** |
| `ui-monospace, SFMono-Regular, Menlo, monospace` | `HistoryPanel.tsx:92` (`timeStyle` when `panel.style === "memo"`) | no weight declared |
| `ui-monospace, Menlo, monospace` | `HistoryPanel.tsx:114` (memo `h2`), `:267` (memo row meta line) | `fontWeight: 400` on the `h2` (`:116`) |
| `"Inter", ui-sans-serif, system-ui, sans-serif` | `index.css:4` (`--font-sans`) and `index.css:23` (`body`) | none |
| generic fallbacks written in the code | `sans-serif`, `serif`, `ui-sans-serif`, `system-ui`, `Menlo`, `SFMono-Regular` | — |

Weights that appear anywhere: **300** (`caption.weight` in 01, 06, 08, 13, 14, 17), **400** (`caption.weight`
in every other theme, and `HistoryPanel.tsx:116` `fontWeight: 400` on the panel title). No 500/600/700 exists.

`fonts.fontLabel` is a *display label*, not a family: `"Manrope"`, `"Fraunces"`, `"Cormorant"` (theme 03/10
write the short label for the family `"Cormorant Garamond"`), `"Newsreader"`, `"Jost"`, `"Lora"`, `"Inter"`,
`"Instrument Serif"`.

# The theme record shape

```ts
export type CaptionStyle = "bare" | "glass" | "plate" | "chip" | "stack" | "karaoke";
export type PanelStyle   = "sheet" | "rail" | "list" | "memo" | "cards";
export type ChromeStyle  = "bar" | "float" | "sidebarHead";
export type Particle     = "rain" | "dust" | "ember" | "snow" | "none";

export interface Wallpaper { src: string; thumb: string }
export interface Theme {
  n: string; id: string; name: string; mood: string;
  scene: string; sceneNote: string;
  wall: Wallpaper; filter: string; overlays: string[];
  vignette: number; grain: number;
  particle: Particle; particleColor: string; time24: boolean;
  fonts: { ui: string; display: string; caption: string; fontLabel: string };
  caption: { style: CaptionStyle; align: "left" | "center"; maxw: string; bottom: string;
             size: string; weight: number; tracking: string; leading: number;
             italic?: boolean; upper?: boolean };
  panel: { style: PanelStyle; width: number };
  chrome: ChromeStyle;
  vars: Record<string, string>;
}
```

`THEMES: Theme[]` has exactly 20 entries; `themeById(id)` returns the match or `THEMES[0]` as fallback
(`themes.ts:885`). App start state is `THEMES[2].id` = **`cellar`** (`App.tsx:13`). `theme.vars` is applied
as CSS custom properties on the root element: `<div style={theme.vars as CSSProperties}>` (`App.tsx:129`).

## Every field

| field | meaning / exact usage |
|---|---|
| `n` | two-digit zero-padded string `"01"`…`"20"`. Shown in the chrome switcher as `{theme.n} · {theme.name}`. |
| `id` | kebab-case slug, unique; the React key and the gallery/`themeById` handle. |
| `name` | display name. |
| `mood` | one verbatim sentence, quoted in the design blocks below. Not rendered by any of the listed components. |
| `scene` | slate line over the wallpaper, rendered `text-[10px] tracking-[0.32em] uppercase` in `color-mix(in srgb, var(--text) 78%, transparent)` (`Stage.tsx:121-125`). |
| `sceneNote` | second slate line, `text-[10.5px] tracking-[0.18em] italic` in `color-mix(in srgb, var(--text) 46%, transparent)` (`Stage.tsx:128-132`). |
| `wall.src` / `wall.thumb` | pexels URLs built by `px(id, ext = "jpeg")` (`themes.ts:51-57`): `src = https://images.pexels.com/photos/{ID}/pexels-photo-{ID}.{ext}?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600`, `thumb = …&fit=crop&h=300&w=520`. Only theme 08 passes `ext = "png"`. The `thumb` is **not used** by any listed component. |
| `filter` | CSS `filter` applied to the wallpaper layer (`Stage.tsx:76`), together with `transform: scale(1.04)`. |
| `overlays[]` | array of raw CSS `background` values, each painted as a full-bleed `pointer-events-none` div **in array order, above the wallpaper and below the vignette** (`Stage.tsx:84-86`). Every theme has exactly 2: a top-to-bottom legibility scrim, then a radial warm/cool pool. |
| `vignette` | number 0–1 interpolated into `radial-gradient(115% 90% at 50% 45%, transparent 42%, rgba(0,0,0,{vignette}) 100%)` (`Stage.tsx:92`). Observed 0.28 – 1. |
| `grain` | opacity of the animated film-grain layer (SVG `feTurbulence` data-URI, `mix-blend-overlay`, `animation: grainShift 1.2s steps(3) infinite`). Observed 0.03 – 0.12. |
| `particle` | enum, see below. Drives mote count, class and animation. |
| `particleColor` | colour of every mote/streak. For `dust`/`ember`/`snow` it also becomes the halo: `boxShadow: 0 0 {size*2.4}px {particleColor}` (`Stage.tsx:59`). For `rain` it is the streak's bottom stop: `linear-gradient(to bottom, transparent, {particleColor})` (`Stage.tsx:44`). |
| `time24` | passed to `fmtClock(at, time24)` for the history clock. `true` in 01,03,06,08,09,11,12,13,15,20; `false` in 02,04,05,07,10,14,16,17,18,19 (exactly ten of each). The `memo` panel row clock is hard-coded 24h: `fmtClock(e.at, true)` (`HistoryPanel.tsx:270`). |
| `fonts.ui` | UI/meta typeface: chrome buttons, caption meta rows, panel chrome, slate. |
| `fonts.display` | wordmark "Mumble" and the panel title (except `memo`). |
| `fonts.caption` | the caption text itself (`LiveCaptions.tsx:131`) and the history row text. |
| `fonts.fontLabel` | label only, not a CSS family. |
| `caption.style` | enum, picks the caption component tree (see next section). |
| `caption.align` | `"left"` or `"center"`. Used for `text-align` on the badge row and `justify-content` on the meta row (variants 1 only) and, in `App.tsx:168-169`, for `marginLeft: "auto"` (center) vs `"4vw"` (left) inside a `maxWidth: caption.maxw` box. |
| `caption.maxw` | `ch` string; `maxWidth` of the caption wrapper. Observed `52ch,54ch,58ch,60ch,62ch,64ch,66ch,68ch`. |
| `caption.bottom` | distance from the viewport bottom of the caption container (`App.tsx:161`). Observed `5.2rem` – `6.5rem`. |
| `caption.size` | passed through `fontSize: clamp(1.02rem, {size}, 2.3rem)` (`LiveCaptions.tsx:132`). Observed `1.42rem` – `1.95rem`. Also used raw in the `stack` previous-line: `calc({size} * 0.66)`. |
| `caption.weight` | `fontWeight` of the caption line: 300 or 400. |
| `caption.tracking` | `letterSpacing` of the caption line. Observed `-0.01em`, `0em`, `0.005em`, `0.01em`, `0.06em`. |
| `caption.leading` | `lineHeight` of the caption line. Observed `1.3` – `1.46`. |
| `caption.italic?` | `true` → `fontStyle: "italic"`. Set only on 10 and 15. |
| `caption.upper?` | `true` → `textTransform: "uppercase"`; **false/absent → `"none"`**. Only 09 sets it explicitly (`upper: false`); no theme sets it `true`. |
| `panel.style` | enum, picks the history-panel tree (see below). |
| `panel.width` | px number, `width` of the `<aside>`; `maxWidth: calc(100vw - 48px)`. Observed 356 – 392. It also drives the caption/panel layout: `captionRight = panelVisible ? theme.panel.width + 34 : 0` (`App.tsx:124`) and `rightInset={panelVisible ? theme.panel.width : 0}` for the `bar` chrome (`App.tsx:145`). |
| `chrome` | enum, picks the top-chrome tree. `topInset` = `0` for `sidebarHead`, else `64` (`App.tsx:123`), which moves the scene slate (`top: topInset + 18`). |
| `vars` | the 15 custom properties below. |

## Enum / union allowed values

**`particle`** — `"rain" | "dust" | "ember" | "snow" | "none"`:

- `rain`: count **46**; class `rain-streak`; per mote `left: {r1*108-4}%`, `height: {8+r3*18}vh`, `width: 1.6px` when `r3 > 0.8` else `1px`, `opacity: 0.18+r2*0.4`, `animationDuration: {(0.9+r3*1.3)}s`, `animationDelay: {-r2*3}s`, background gradient in `particleColor`; keyframes `rainFall` (from `translate3d(0,-20%,0); opacity 0` → `10% opacity .5` → to `translate3d(-4%,110%,0); opacity 0`), `.rain-streak` sets `position:absolute; top:-10%; width:1px`. **No halo.**
- `snow`: count **60**; class `drift-mote`; `size = 2 + r3*4` px; `animationDuration: {(12+r3*16)}s`; `animationDelay: {-r2*12}s`; halo `boxShadow: 0 0 {size*2.4}px {particleColor}`.
- `dust`: count **26**; class `drift-mote`; `size = 1.5 + r3*3.5` px; `animationDuration: {(10+r3*18)}s`; same halo rule.
- `ember`: identical maths to `dust` (falls into the same `else` branch: count 26, `size = 1.5 + r3*3.5`, `10+r3*18`s); used only by theme 16.
- `none`: no particle layer is rendered at all (`Stage.tsx:97`).
- All motes: `left: {r1*100}%`, `bottom: {-4 - r2*10}%`, `opacity: 0.15 + r2*0.5`; keyframes `driftUp` (0% `translate3d(0,10%,0) scale(.6)` opacity 0 → 15% `.55` → 80% `.35` → 100% `translate3d(14px,-90vh,0) scale(1)` opacity 0). `rnd(seed) = frac(sin(seed*12.9898)*43758.5453)` — deterministic per index.

**`caption.style`** — 6 values, labels in `CAPTION_LABELS`: `bare` = "Floating type", `glass` = "Frosted glass",
`plate` = "Solid plate", `chip` = "Speaker chip", `stack` = "Two-line roll", `karaoke` = "Read-along".
Full structures in the next section.

**`panel.style`** — 5 values, labels in `PANEL_LABELS`: `sheet` = "Log sheet", `rail` = "Timeline rail",
`list` = "Plain list", `memo` = "Session notes", `cards` = "Stacked cards". All five share one `<aside>`,
one `Header`, one sticky session-group header, one `LiveRow`, one `Footer` and a `.quiet-scroll` scroller;
they differ as follows (`HistoryPanel.tsx`):

- Outer box: `rail` and `cards` are floating cards (`right-3 top-3 bottom-3`, `background var(--surface)`,
  `border 1px solid var(--line)`, `borderRadius var(--radius)`, blur, `boxShadow var(--shadow)`); `sheet`,
  `list`, `memo` are flush right (`right-0 top-0 bottom-0`, `borderLeft: 1px solid var(--line)`, no radius)
  (`:85-88`, `:386`).
- `sheet` row: `grid-cols-[74px_1fr] gap-3 px-5 py-3`, bottom hairline `color-mix(in srgb, var(--line) 60%, transparent)`,
  hover `var(--surface-2)`; left cell = clock, right = 6px speaker dot + speaker tag + text `0.85rem/1.55`.
- `rail` row: `pl-7 pr-4 py-2.5` with a 1px vertical rail at `left-[18px]` full-height in
  `color-mix(in srgb, var(--line) 70%, transparent)` and a 9×9px dot at `left-[14px] top-[17px]`,
  `background: color-mix(in srgb, {tone} 90%, transparent)`, `border: 2px solid color-mix(in srgb, var(--surface) 100%, transparent)`,
  `boxShadow: 0 0 0 1px {tone}`; header line = speaker tag, clock, and a "copied" label at `ml-auto`
  with `opacity: active ? 1 : 0`; text `0.84rem/1.55`.
- `list` row: `flex items-start gap-3.5 px-5 py-3.5`, hover `var(--surface-2)`; a 28×28px round avatar
  (`h-7 w-7 rounded-full`) filled `color-mix(in srgb, {tone} 18%, transparent)` with speaker initials at
  `0.58rem` in `{tone}`; right side = speaker name `0.74rem` in `{tone}` + clock/copied; text `0.85rem/1.55`.
- `memo` row: `px-5 py-2.5`, no rule; meta line in `ui-monospace, Menlo, monospace` `0.63rem tracking 0.08em`
  in `var(--dim)` = zero-padded 3-digit index, 24h clock, speaker uppercased `tracking 0.16em` in `{tone}`,
  `ml-auto` confidence `${(e.confidence*100).toFixed(0)}%` or `"copied ✓"`; text `0.85rem/1.58`. The `memo`
  title is `"session log"` (uppercase, `ui-monospace`, `0.12em` tracking, `1.05rem`) instead of
  `"The room, so far"`; its clock style is monospace; its speaker filter chips get `borderRadius: 3`.
- `cards` row: `mx-4 mb-2.5 px-4 py-3.5`, `background var(--surface-2)`, `border 1px solid var(--line)`,
  `borderLeft: 3px solid {tone}`, `borderRadius: calc(var(--radius) * 0.8)`,
  `boxShadow: 0 12px 26px -22px rgba(0,0,0,.7)`, hover `translateY(-1px)`; header speaker + clock; text `0.85rem/1.55`.
- Shared chrome: title bar `px-5 pt-5 pb-3` with bottom hairline, a 6px dot (`var(--live)` when running else
  `var(--dim)`), the tag "transcript history" (`0.6rem tracking 0.22em uppercase`, `var(--dim)`), title
  `1.2rem` (`1.05rem` for `list`/`memo`) at `fontWeight 400`, `letterSpacing -0.01em`; a `HIDE` pill button;
  a search input (`placeholder "Search this transcript…"`) that is a pill (`borderRadius 999`, `1px` border,
  `var(--surface-2)`, `padding .55rem .85rem`) for `list`/`cards` and an underline only (`borderBottom`,
  `padding .45rem 0`) for the other three; speaker filter chips `All → "everyone"` + names, active state
  `background: color-mix(in srgb, {tone} 16%, transparent)` and `border: 1px solid color-mix(in srgb, {tone} 38%, transparent)`,
  `borderRadius 3` for `memo` else `999`. Footer: `Export .txt` / `Follow on|off` (in `var(--accent)` when on) /
  `Clear` at `0.63rem tracking 0.16em uppercase`, then `{sessionLabel}` and `{entries.length} lines · {wpm} wpm`
  at `0.6rem tracking 0.1em` in `var(--dim)`. Empty state: `px-5 py-10` centred `0.78rem/1.7` in `var(--dim)`:
  "Nothing matches that. The room keeps talking either way."
- `LiveRow` (when a partial exists): background `var(--surface-2)` for `cards`, else
  `color-mix(in srgb, var(--accent) 9%, transparent)`; `borderLeft: 2px solid {speakerColor}` — **omitted for
  `rail`**; radius `calc(var(--radius) * 0.8)` and `margin: 0 16px 14px`, `padding: 12px 14px` for `cards`,
  else `padding: 12px 20px 14px`; a 6px `var(--live)` dot with the `breathe` animation, the speaker tag, and
  `"in progress"` (`tracking 0.18em`, `var(--dim)`) at `ml-auto`; the text is italic and shows
  `partial.words.slice(0, partial.revealed).join(" ")` followed by a 1.5px × 0.85em caret in `var(--accent)`.
- Search matches are wrapped in `<mark>`: `background: color-mix(in srgb, {tone} 30%, transparent)`, `color: inherit`,
  `borderRadius 3`, `padding: 0 1px`.

**`chrome`** — 3 values, labels in `CHROME_LABELS`: `bar` = "Header bar", `float` = "Floating pill",
`sidebarHead` = "Panel heading". Structure:

- `bar`: one `<header>` `absolute top-0 left-0 z-30 flex h-[62px] items-center gap-5 px-5 sm:px-8`, `right: rightInset`
  (0 or `panel.width`) with a 500 ms transition, `background: linear-gradient(180deg, color-mix(in srgb, var(--page) 88%, transparent), transparent)`,
  `backdropFilter: blur(10px)`. Contents left→right: Mark, divider, script title `0.78rem` + session label
  `0.6rem tracking 0.18em uppercase` in `var(--dim)` (both inside `hidden lg:flex`), then `ml-auto` cluster:
  level bars + `m:ss` + stats (hidden below `xl`/`2xl`), Switcher, LivePill, speed button, gallery button
  `NN/20`, panel-toggle icon, immersive eye icon.
- `float`: three independent pieces — top-left pill (hidden below `xl`) with Mark + divider + uppercase script
  title `0.62rem tracking 0.16em` in `var(--dim)`; a centred pill (`top-4 sm:top-6 left-1/2 -translate-x-1/2`)
  holding LivePill, level + time, Switcher, speed, gallery icon, panel icon, eye icon; and, at `top-[74px]`
  centred, the stats line `0.6rem tracking 0.16em uppercase` in `color-mix(in srgb, var(--text) 52%, transparent)`.
  All three use `background var(--surface)`, `backdropFilter: blur(var(--blur))`, `border 1px solid var(--line)`,
  `boxShadow var(--shadow)`, `rounded-full`.
- `sidebarHead`: no top bar. A bottom-left column (`absolute bottom-6 left-6 flex flex-col items-start gap-3`):
  a pill with Mark + divider + `m:ss`; a row with LivePill, Switcher, speed, a "Designs" button, panel icon,
  eye icon; and a line `{scriptTitle} · {statsText}` at `0.6rem tracking 0.16em uppercase` in
  `color-mix(in srgb, var(--text) 46%, transparent)`.
- Shared: the **Mark** is a 24×24px ring (`h-6 w-6`) with `background: color-mix(in srgb, var(--accent) 24%, transparent)`,
  `border: 1px solid color-mix(in srgb, var(--accent) 46%, transparent)` and a 6px `var(--accent)` dot, next to the
  wordmark **"Mumble"** in `fonts.display` at `0.98rem`, `letterSpacing -0.01em`. The **LivePill** reads
  "Listening"/"Paused" with a 13px play/pause SVG; running → `color: #0c1013`, `background var(--live)`,
  `border 1px solid var(--live)`, `boxShadow: 0 10px 30px -14px var(--live)`; paused → `color var(--text)`,
  `background var(--surface-2)`, `border 1px solid var(--line)`, no shadow. Generic buttons use
  `fontFamily fonts.ui, fontSize 0.62rem, letterSpacing 0.16em, uppercase`, colour
  `var(--text)` (active) or `color-mix(in srgb, var(--text) 72%, transparent)`, background
  `color-mix(in srgb, var(--accent) 20%, transparent)` (active) or `var(--surface-2)`, border
  `1px solid color-mix(in srgb, var(--accent) 42%, transparent)` (active) or `var(--line)`. `Level` = 6 bars,
  `2px` wide, `gap-[2.5px]`, `h-3`, height `max(3, level*12*m)px`, opacity `0.4 + level*0.55*m`, multipliers
  `[0.55,0.85,1,0.7,0.45,0.3]`. `statsText = "{speakers} speaker(s) · {lines} lines · {round(conf*100)}% conf."`

## The 15 `vars` keys (every theme declares exactly these, with these units)

`--page` (opaque hex), `--text` (hex), `--dim` (hex), `--accent` (hex), `--accent-2` (hex), `--live` (hex),
`--surface` (`rgba()`), `--surface-2` (`rgba()`), `--line` (`rgba()`), `--radius` (`Npx`, observed 4–22),
`--blur` (`Npx`, observed 14–22), `--shadow` (`0 Npx Mpx -Kpx rgba(...)`), `--cap-bg` (`rgba()`),
`--cap-text` (hex), `--cap-edge` (`rgba()`). `--page` is the stage background behind the wallpaper
(`Stage.tsx:69`), and `color-mix()` is used everywhere on top of these.

# LIVE CAPTION layout variants

`LiveCaptions.tsx` branches on **`caption.style` and nothing else**. There is **no `ov`, no `layout`, no
`variant` variable and no numeric switch** in the file; the only other branches are the two state predicates
`isLive = Boolean(partial) && running` (`:146`) and `words.length === 0`. The six branches start at `:152`
(`bare`), `:190` (`glass`), `:240` (`plate`), `:288` (`chip`), `:342` (`stack`) and `:397` (the fallback, which
is `karaoke` — it is reached by elimination, so any unknown style value renders `karaoke`).

## Shared machinery (all six)

- **Base style** spread into every variant's root (`:130-138`):
  `fontFamily: fonts.caption`, `fontSize: clamp(1.02rem, {caption.size}, 2.3rem)`, `fontWeight: caption.weight`,
  `letterSpacing: caption.tracking`, `lineHeight: caption.leading`, `fontStyle: caption.italic ? "italic" : "normal"`,
  `textTransform: caption.upper ? "uppercase" : "none"`. Because `fontSize`/`letterSpacing`/`lineHeight`/
  `textTransform` are inherited, **inner spans inherit them unless they override**.
- **`tone`** = `speaker ? speakerColor(speaker) : "var(--text)"`. `speakerColor` (`App.tsx:26-34`) cycles
  `["var(--text)", "var(--accent)", "var(--accent-2)"]` by the speaker's index among all seen speakers, mod 3.
- **`capText`** = `"var(--cap-text)"`. `speaker` = `partial?.speaker ?? previous?.speaker ?? ""`.
- **`words`** = `partial?.words ?? previous?.text.split(" ") ?? []`; **`revealed`** = `partial ? partial.revealed : words.length`.
- **`WordRun`** (`:92-117`): one `<span key={i-w}>` per word, `display: "inline-block"`, `whiteSpace: "pre"`,
  a literal `" "` appended to every word except the last, and the span at index `revealed - 1` gets
  `className="word-in"`. Words `i < revealed` get the `bright` style, the rest the `dim` style — **but only
  `karaoke` passes `bright`/`dim` at all; in the other five both are `undefined`, so forming and settled words
  are styled identically.**
- **`.word-in`** = `animation: wordIn 0.42s cubic-bezier(0.22, 1, 0.36, 1) both`; keyframes `wordIn`:
  `0% { opacity: 0; transform: translateY(6px); filter: blur(3px) }` → `100% { opacity: 1; transform: translateY(0); filter: blur(0) }`.
  The `key` includes the word text, so changing a word remounts the span and restarts the animation.
- **`Caret`** (`:119-126`): `<span className="caret ml-1.5 inline-block align-baseline">`, `width: 2px`,
  `height: 0.92em`, `background: {tone}`, `borderRadius: 2`, `transform: translateY(0.06em)`.
  `.caret` = `animation: caretBlink 1.05s steps(1) infinite` (`0%,45% opacity 1; 55%,100% opacity 0`).
  **Rendered only when `isLive`** — i.e. a forming line that is no longer running has no caret.
- **`StatusBadge`** (`:35-77`) — used by `bare` (full pill) and `stack` (`plain`, no pill): an outer flex
  (`gap-2.5`, `justify-center` when `align === "center"`) that, when not `plain`, has `borderRadius: 999`,
  `background var(--cap-bg)`, `border 1px solid var(--cap-edge)`, `backdropFilter: blur(var(--blur))`;
  inside: a 8×8px (`h-2 w-2`) `breathe` dot at `opacity: running ? 0.5 : 0.2` over a solid 6×6px (`h-1.5 w-1.5`)
  dot, both `background: {tint}` where `tint = running ? "var(--live)" : "var(--dim)"`; the word
  **"listening"/"paused"** at `fontSize 0.6rem`, `letterSpacing 0.3em`, `uppercase`, colour
  `var(--text)` when running else `var(--dim)`; and `LevelBars` only while running.
- **`LevelBars`** (`:17-33`): 5 spans, `h-3.5` (`0.875rem`), `gap-[3px]`, `w-[2.5px]`, `rounded-full`,
  `transition-[height,opacity] duration-150`, `height: max(3, level*13*m)px`, `opacity: 0.35 + level*0.6*m`,
  multipliers `[0.5,0.8,1,0.66,0.4]`.
- **`Meta`** (`:79-90`): `flex items-center gap-3 text-[9.5px] uppercase`, `letterSpacing: 0.26em`,
  colour `color-mix(in srgb, var(--text) 42%, transparent)`; content = `{note}` + a 3px-tall (`h-3`) 1px
  divider in `color-mix(in srgb, var(--text) 20%, transparent)` + the literal `"on-device · 240 ms"`.
  `note` = `partial ? \`transcribing ${speakerShort(partial.speaker)}\` : "last line"`.
- **`SPEAKER_SIZE = "0.66rem"`**, `shadow = "0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)"` (used only by `bare`).
- **Placement is in `App.tsx:159-183`, not here**: container `absolute z-[25] left-0 right-{captionRight} bottom-{caption.bottom}`
  with `transition-[right] duration-500`; inner `px-5 sm:px-10`, `width: 100%`, `maxWidth: caption.maxw`,
  `marginLeft: auto` (center) or `4vw` (left), `marginRight: auto` (center).

## 1. `bare` — "Floating type" (`:151-187`)

No box, no border, no background, no `soft-in`; text sits directly on the wallpaper.
Root: `<div className="flex flex-col gap-3.5">`.

1. Badge row: `<div className={align === "center" ? "text-center" : ""}>` → `<span className="inline-flex">` → `StatusBadge`.
2. Text row: `<div style={{ ...base, color: capText, textShadow: shadow }}>`:
   - if `speaker`: `<span className="mr-3 align-middle">` with `fontSize: calc(0.66rem * 1.15)` (= 0.759rem),
     `letterSpacing: 0.3em`, `textTransform: "uppercase"`, `color: tone`, `textShadow: "none"`, text `speakerShort(speaker)`;
   - if `words.length === 0`: `<span style={{ opacity: 0.4, fontStyle: "italic" }}>the room is quiet…</span>`;
   - else `WordRun` (no `bright`/`dim`);
   - if live: `Caret`.
3. Meta row: `<div className={align === "center" ? "flex justify-center" : ""}>` → `Meta`.

## 2. `glass` — "Frosted glass" (`:189-237`)

Root: `<div className="soft-in px-6 py-4 sm:px-8 sm:py-5">` with `...base`, `background var(--cap-bg)`,
`border 1px solid var(--cap-edge)`, `borderRadius var(--radius)`,
`backdropFilter/WebkitBackdropFilter: blur(var(--blur)) saturate(1.15)`,
`boxShadow: 0 30px 80px -40px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.06)`.

1. Header `<div className="mb-2.5 flex items-center justify-between gap-6">`:
   - left `<div className="flex items-center gap-2.5">`: a `h-1.5 w-1.5 rounded-full` dot with
     `background: tone`, `boxShadow: 0 0 10px {tone}`; then `<span className="uppercase">` at
     `fontSize 0.66rem`, `letterSpacing 0.26em`, `color: tone`, `fontFamily: fonts.ui`, content
     `speaker ? speakerShort(speaker) : "—"`;
   - right `<span className={running ? "" : "opacity-0"}>` → `LevelBars` in
     `color-mix(in srgb, var(--cap-text) 55%, transparent)`.
2. Body `<div style={{ color: capText }}>`: empty → `waiting for the first line…` at `opacity 0.45`, italic;
   else `WordRun`; then `Caret` if live.
3. Footer `<div className="mt-2.5 flex items-center justify-between gap-4" style={{ fontFamily: fonts.ui }}>`:
   `Meta` left; right `<span className="text-[9.5px] uppercase">` at `letterSpacing 0.24em`,
   `color: color-mix(in srgb, var(--cap-text) 38%, transparent)`, text `running ? "live track" : "hold"`.

## 3. `plate` — "Solid plate" (`:239-285`)

Root: `<div className="soft-in">` with `...base`, `background var(--cap-bg)`, `border 1px solid var(--cap-edge)`,
`borderRadius var(--radius)`, `padding: "1.05rem 1.6rem 0.95rem"`, `boxShadow: 0 26px 70px -36px rgba(0,0,0,.85)`.

- Inner `<div className="flex items-start gap-4">`:
  - **left rail** `<div className="flex flex-col items-center gap-2 pt-1.5">`: a `h-2 w-2 rounded-full` dot with
    `background: running ? "var(--live)" : "var(--dim)"`, then `<span className="w-px flex-1">` filled
    `color-mix(in srgb, var(--cap-text) 18%, transparent)` — a vertical hairline running the height of the block.
  - **right column** `<div className="flex-1">`:
    1. meta row `<div className="mb-1.5 flex items-center gap-3" style={{ fontFamily: fonts.ui, fontSize: "0.66rem", letterSpacing: "0.28em" }}>`
       → `<span className="uppercase" style={{ color: tone }}>` with `speakerShort(speaker)` or `"—"`, then a span in
       `color-mix(in srgb, var(--cap-text) 40%, transparent)` reading `running ? "speaking now" : "paused"`
       (**this second span has no `uppercase` class, so it stays sentence case unless `caption.upper` is true**);
    2. body `<div style={{ color: capText }}>`: empty → `"…"` at `opacity 0.4`; else `WordRun`; then `Caret` if live.
- No `StatusBadge`, no `LevelBars`, no `Meta` in this variant.

## 4. `chip` — "Speaker chip" (`:287-339`)

Root: `<div className="soft-in flex flex-col gap-2.5 px-5 py-4 sm:px-6">` with `...base`, `background var(--cap-bg)`,
`border 1px solid var(--cap-edge)`, `borderRadius: calc(var(--radius) * 0.9)`,
`backdropFilter: blur(calc(var(--blur) * 0.8))`, `boxShadow: 0 24px 60px -34px rgba(0,0,0,.78)`.

1. Header `<div className="flex items-center gap-3" style={{ fontFamily: fonts.ui }}>`:
   - a pill `<span className="inline-flex items-center gap-2 rounded-full px-3 py-1">` with
     `background: color-mix(in srgb, {tone} 18%, transparent)` and
     `border: 1px solid color-mix(in srgb, {tone} 34%, transparent)`, containing a `h-1.5 w-1.5 rounded-full` dot in
     `{tone}` and `<span className="uppercase">` at `0.66rem`, `letterSpacing 0.24em`, `color: tone` → speaker or `"—"`;
   - `<span className="uppercase">` at `fontSize 0.58rem`, `letterSpacing 0.26em`,
     `color: color-mix(in srgb, var(--cap-text) 40%, transparent)` → `running ? "capturing" : "paused"`;
   - `<span className="ml-auto">` → `LevelBars` in `color-mix(in srgb, var(--cap-text) 50%, transparent)`
     (rendered regardless of `running`).
2. Body `<div style={{ color: capText }}>`: empty → `nothing said yet, that's alright…` at `opacity 0.42`, italic;
   else `WordRun`; then `Caret` if live.

## 5. `stack` — "Two-line roll" (`:341-394`)

Extra state: `prevText = previous ? previous.text : ""` and
`showPrev = Boolean(partial) && prevText && prevText !== words.join(" ")` — the previous finished line is shown
**above** the forming line, and disappears when the two texts match.

Root: `<div className="soft-in px-5 py-4 sm:px-7">` with `...base`, `background var(--cap-bg)`,
**`borderLeft: 2px solid {tone}`** (this is the only border — no top/right/bottom, no `--cap-edge`),
`borderRadius: calc(var(--radius) * 0.55)`, `backdropFilter: blur(calc(var(--blur) * 0.7))`,
`boxShadow: 0 24px 60px -34px rgba(0,0,0,.8)`.

1. Header `<div className="mb-2 flex items-center gap-3" style={{ fontFamily: fonts.ui }}>`:
   `StatusBadge` with `theme`, `running`, `level`, `align="left"` and **`plain`** (so it renders dot + word only,
   no pill background/border/blur), then `<span className="ml-auto uppercase">` at `fontSize 0.56rem`,
   `letterSpacing 0.26em`, `color: color-mix(in srgb, var(--cap-text) 34%, transparent)` → `"rolling"`.
2. Previous line (only if `showPrev`): `<div className="mb-2 truncate">` with
   `color: color-mix(in srgb, var(--cap-text) 34%, transparent)`,
   `fontSize: calc({caption.size} * 0.66)`, `fontFamily: fonts.caption`, `letterSpacing: caption.tracking`.
3. Body `<div style={{ color: capText }}>`: empty → `rolling…` at `opacity 0.42`, italic; else `WordRun`;
   then `Caret` if live.

## 6. `karaoke` — "Read-along" (fallback, `:396-446`)

Root: `<div className="soft-in px-6 py-4 sm:px-8 sm:py-5">` with `...base`, `background var(--cap-bg)`,
`border 1px solid var(--cap-edge)`, `borderRadius var(--radius)`, `backdropFilter: blur(var(--blur))`
(**no `saturate`**, unlike `glass`), `boxShadow: 0 28px 74px -38px rgba(0,0,0,.85)`.

1. Header `<div className="mb-2.5 flex items-center gap-3" style={{ fontFamily: fonts.ui }}>`:
   `<span className="uppercase">` at `fontSize 0.66rem`, `letterSpacing 0.26em`, `color: tone` → speaker or `"—"`;
   a `<span className="h-3 w-px">` divider in `color-mix(in srgb, var(--cap-text) 22%, transparent)`;
   `<span className={running ? "" : "opacity-40"}>` → `LevelBars` in `{tone}`;
   `<span className="ml-auto uppercase">` at `0.56rem`, `letterSpacing 0.26em`,
   `color: color-mix(in srgb, var(--cap-text) 34%, transparent)` → `"read-along"`.
2. Body `<div style={{ color: capText }}>`: empty → `waiting…` at `opacity 0.42`, italic; else
   `WordRun` **with the only `bright`/`dim` pair in the file**:
   - `bright = { color: capText, filter: "blur(0px)", transition: "color .3s ease, filter .3s ease" }` (words `i < revealed`),
   - `dim = { color: "color-mix(in srgb, var(--cap-text) 30%, transparent)", filter: "blur(1.1px)", transition: "color .3s ease, filter .3s ease" }` (words not yet revealed);
   then `Caret` if live.
3. Footer `<div className="mt-2.5">` → `Meta`.

## Forming vs settled text, per variant

| variant | forming (`partial` present) | settled (`partial` null, `words = previous.text.split(" ")`, `revealed = words.length`) |
|---|---|---|
| `bare` | `words`/`revealed` from the partial, blinking `Caret` appended, badge says "listening" (if `running`), `note` = `transcribing {speaker}`, header badge + Meta present | full previous line, no caret, `note` = `last line`; the **last** word still carries `word-in` (index = `words.length - 1`) |
| `glass` | as above; right-hand LevelBars fade to `opacity-0` when not running; footer word `live track`/`hold` | no caret; footer `hold` when not running; same box |
| `plate` | caret; the rail dot switches to `var(--live)`; "speaking now" | no caret; dot `var(--dim)`; "paused" |
| `chip` | caret; "capturing"/"paused"; LevelBars always painted | no caret |
| `stack` | caret + the previous finished line rendered above at `0.66 × size` in 34% cap-text | no caret and **no `showPrev`** (the predicate requires `Boolean(partial)`), so the settled line renders alone |
| `karaoke` | revealed words `bright` (blur 0), unrevealed `dim` (30% cap-text, `blur(1.1px)`), 0.3s colour+filter transitions, caret | all words take `bright` (every word `i < revealed`), so nothing is dimmed or blurred; no caret |

Animations that apply to the caption block itself: `soft-in` (`softIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both`,
`translateY(10px)` → `0`) on every variant **except `bare`**; `word-in` per word (all variants); `caret`
blink (all variants while live); `breathe` on the status dots (variants 1, 5 and the panel `LiveRow`).
`App.tsx` adds `transition-[right] duration-500` on the caption container and `transition-[right] duration-500`
on the `bar` header.

# Design inventory

Wallpaper URLs are all `https://images.pexels.com/photos/{ID}/pexels-photo-{ID}.{ext}?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600`.
Every design's backdrop is `var(--page)` → wallpaper (`background-image`, `bg-cover bg-center`, `transform: scale(1.04)`,
`filter: {theme.filter}`, crossfading the last two layers at `1100ms ease-out`) → `overlays[]` in order →
vignette → particles → grain at `mix-blend-overlay` → scene slate at `left-6 sm:left-9, top: topInset + 18`
(7px `var(--accent)` dot with `boxShadow: 0 0 14px var(--accent)`, `scene` at `10px/0.32em uppercase` in
`color-mix(in srgb, var(--text) 78%, transparent)`, `sceneNote` at `10.5px/0.18em italic` in `46%`) →
four 20×20px corner brackets at `top-4/left-4` etc. with `borderColor: color-mix(in srgb, var(--text) 22%, transparent)`.

## 01 — Rainline
- mood: "Rain on the glass at one in the morning. Cold blue room, warm tea, everything slow."
- fonts: caption `"Manrope", sans-serif` / ui `"Manrope", sans-serif` / display `"Manrope", sans-serif` (fontLabel `Manrope`)
- palette: background `--page: #060c11` / surface `--surface: rgba(10,20,27,.74)` / text `--text: #eaf3f7` / dim `--dim: #93a9b4` / accent `--accent: #9fc9dd`; also `--accent-2: #d9b486`, `--live: #8fd0c9`
- vars: `--surface-2: rgba(255,255,255,.055)`, `--line: rgba(200,226,238,.14)`, `--radius: 16px`, `--blur: 22px`, `--shadow: 0 24px 70px -30px rgba(0,0,0,.85)`, `--cap-bg: rgba(8,18,24,.62)`, `--cap-text: #f2f8fb`, `--cap-edge: rgba(220,240,250,.16)`
- panel style + caption variant: `panel.style` `sheet` (width 384) · `caption.style` `bare` · `chrome` `bar`
- caption typography: align `center`, maxw `62ch`, bottom `6.5rem`, size `1.72rem`, weight `300`, tracking `-0.01em`, leading `1.42`, no italic, `upper` absent
- LIVE CAPTION: variant `bare` (no box at all) with the `0.759rem` uppercase speaker label in `tone` and the `0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)` shadow — the shadow is what keeps a weight-300 light-blue line legible over the photo.
- backdrop: pexels `9488153` jpeg; `filter: saturate(0.78) contrast(1.06) brightness(0.78)`; overlays `linear-gradient(180deg, rgba(6,16,22,.78) 0%, rgba(6,16,22,.24) 34%, rgba(6,16,22,.34) 62%, rgba(4,12,18,.9) 100%)` then `radial-gradient(120% 80% at 78% 18%, rgba(160,205,225,.20), transparent 60%)`; vignette `0.85`; grain `0.05`; particle `rain` × 46 in `rgba(214,236,245,.55)` (no halo)
- top chrome: `bar` — 62px blurred gradient strip showing Mark + "Mumble", script title and session label, then level bars, elapsed, stats, `01 · Rainline` switcher, the `--live` Listening pill, speed, gallery, panel and immersive buttons; the strip's right edge stops at the panel width and its gradient is `color-mix(in srgb, var(--page) 88%, transparent)`.
- prose: The first thing a reader notices is that there is no caption box at all — the line floats on the photograph with only a shadow holding it up. Weight 300 Manrope at `1.72rem` with `-0.01em` tracking reads like a film subtitle rather than UI. A top-to-bottom scrim plus a single blue-cyan radial at `78% 18%` grade the image, while 46 thin rain streaks at `1px`/`1.6px` wide cross it on 0.9–2.2 s loops, so the frame is never completely still. The status pill sits *above* the text with a `gap-3.5` (`0.875rem`) gap and the device note sits *below* it, which makes the caption a three-storey stack rather than one line. The five `2.5px` level bars breathe only while audio is running.

## 02 — Blue Plate
- mood: "An all-night diner with three people left in it. Amber bulbs, coffee going cold."
- fonts: caption `"Fraunces", serif` / ui `"Inter", sans-serif` / display `"Fraunces", serif` (fontLabel `Fraunces`)
- palette: background `--page: #0d0703` / surface `--surface: rgba(24,15,7,.78)` / text `--text: #f7ecda` / dim `--dim: #b9986f` / accent `--accent: #e8a860`; also `--accent-2: #8fc0b6`, `--live: #e8a860`
- vars: `--surface-2: rgba(255,226,182,.07)`, `--line: rgba(240,206,158,.16)`, `--radius: 14px`, `--blur: 20px`, `--shadow: 0 26px 76px -32px rgba(0,0,0,.9)`, `--cap-bg: rgba(12,7,2,.86)`, `--cap-text: #fdf3e3`, `--cap-edge: rgba(240,200,150,.24)`
- panel style + caption variant: `panel.style` `sheet` (width 392) · `caption.style` `plate` · `chrome` `bar`
- caption typography: align `center`, maxw `68ch` (widest in the set), bottom `5.5rem`, size `1.5rem`, weight `400`, tracking `0em`, leading `1.34`
- LIVE CAPTION: variant `plate` — the two-column plate with a dot + vertical hairline rail on the left, the `0.28em` speaker/"speaking now" meta row above, and a static shadow (`0 26px 70px -36px rgba(0,0,0,.85)`); `--cap-bg` is `rgba(12,7,2,.86)`, the most opaque **dark** plate in the set (only the light themes 04 `.9` and 18 `.88` exceed it).
- backdrop: pexels `8887627` jpeg; `filter: saturate(0.92) contrast(1.04) brightness(0.8) sepia(0.14)` (the only `sepia()` in the set); overlays `linear-gradient(180deg, rgba(20,12,6,.8) 0%, rgba(22,13,6,.3) 38%, rgba(24,14,6,.42) 66%, rgba(14,8,3,.92) 100%)` then `radial-gradient(90% 70% at 22% 30%, rgba(232,168,96,.24), transparent 62%)`; vignette `0.9`; grain `0.07`; particle `none`
- top chrome: `bar` chrome; the Listening pill is filled with `--live` `#e8a860` (same as `--accent`), so the single saturated element in the corner is the same amber as the radial glow behind it.
- prose: What reads first is the left rail: an 8px (`h-2 w-2`) dot that turns amber while running, a hairline running the full height of the plate, and the text hanging off it in two columns. `sepia(0.14)` plus a 90%-wide amber pool at 22% 30% makes the whole frame feel like bulb light rather than screen light. At `0.86` the plate is the most opaque dark caption surface in the set, so the photograph never shows through the words. At `68ch` it is also the widest caption measure, so lines run long and low.

## 03 — Cellar Sessions
- mood: "A basement bar after last call. Brass lamp, one table, a long rambling conversation."
- fonts: caption `"Cormorant Garamond", serif` / ui `"Inter", sans-serif` / display `"Cormorant Garamond", serif` (fontLabel `Cormorant`)
- palette: background `--page: #0c0807` / surface `--surface: rgba(20,15,11,.7)` / text `--text: #f3e8d7` / dim `--dim: #a88f6d` / accent `--accent: #d9a94f`; also `--accent-2: #c98f7a`, `--live: #d9a94f`
- vars: `--surface-2: rgba(255,236,196,.06)`, `--line: rgba(226,196,140,.16)`, `--radius: 18px`, `--blur: 18px`, `--shadow: 0 30px 80px -34px rgba(0,0,0,.9)`, `--cap-bg: rgba(18,12,8,.46)`, `--cap-text: #f8efe0`, `--cap-edge: rgba(230,196,138,.22)`
- panel style + caption variant: `panel.style` `rail` (width 368) · `caption.style` `glass` · `chrome` `float`
- caption typography: align `center`, maxw `64ch`, bottom `6rem`, size `1.78rem`, weight `400`, tracking `0.005em`, leading `1.4`, no italic, `upper` absent
- LIVE CAPTION: variant `glass` — frosted panel with `blur(var(--blur)) saturate(1.15)`, a 6px (`h-1.5 w-1.5`) glow dot with `boxShadow: 0 0 10px {tone}` plus a 0.26em speaker label at the top-left, level bars hiding via `opacity-0` when paused, and the "live track / hold" footer on the right; `--cap-bg` is only `0.46` opaque, so the image reads through the glass.
- backdrop: pexels `35258949` jpeg; `filter: saturate(1.02) contrast(1.05) brightness(0.72)` (darkest brightness tied with 16); overlays `linear-gradient(180deg, rgba(14,10,8,.82) 0%, rgba(18,12,8,.34) 40%, rgba(18,12,8,.44) 68%, rgba(10,7,4,.93) 100%)` then `radial-gradient(80% 60% at 70% 26%, rgba(220,168,84,.28), transparent 60%)`; vignette `0.95`; grain `0.08`; particle `dust` × 26 in `rgba(240,206,150,.45)` (each mote haloed at `0 0 {size*2.4}px`)
- top chrome: `float` — a top-left pill (Mark + "Mumble" + uppercase script title), a centred pill (Listening, level, `m:ss`, switcher, speed, gallery, panel, eye), and beneath it the stats line at `top-[74px]`; nothing spans the top edge.
- prose: The two crisp things first: a serif at `1.78rem` and a small round dot with a 10px warm glow beside the speaker name. Because `--cap-bg` is only `0.46`, the caption is a sheet of glass you read *through* rather than a card you read *on*, and the `saturate(1.15)` inside the blur slightly re-warms whatever is behind it. This is also the app's default design (`App.tsx:13`), so it is the one the reader meets before touching anything, and the history panel arrives as a floating timeline card with a hairline rail and 9px dots. Twenty-six glowing dust motes drift upward on 10–28 s loops.

## 04 — Linen Hours
- mood: "A paper-lit café at eight in the morning. Ink on linen, nothing urgent."
- fonts: caption `"Newsreader", serif` / ui `"Inter", sans-serif` / display `"Cormorant Garamond", serif` (fontLabel `Newsreader`)
- palette: background `--page: #efe7da` (light) / surface `--surface: rgba(251,247,240,.86)` / text `--text: #2e2a24` / dim `--dim: #8a7f6f` / accent `--accent: #a8672f`; also `--accent-2: #5f7a6a`, `--live: #7d9c6d`
- vars: `--surface-2: rgba(46,42,36,.05)`, `--line: rgba(90,78,62,.16)`, `--radius: 18px`, `--blur: 16px`, `--shadow: 0 22px 60px -34px rgba(70,54,36,.45)` (the softest shadow in the set), `--cap-bg: rgba(252,249,243,.9)`, `--cap-text: #332d26`, `--cap-edge: rgba(120,104,84,.18)`
- panel style + caption variant: `panel.style` `list` (width 380) · `caption.style` `plate` · `chrome` `bar`
- caption typography: align `center`, maxw `66ch`, bottom `5.5rem`, size `1.55rem`, weight `400`, tracking `0em`, leading `1.38`
- LIVE CAPTION: variant `plate` — but inverted: `--cap-text` is dark `#332d26` on a `rgba(252,249,243,.9)` plate, and everything the variant paints with `color-mix(... var(--cap-text) N%, transparent)` becomes a *darkening* of the paper rather than a fading of light.
- backdrop: pexels `18405036` jpeg; `filter: saturate(0.9) contrast(0.98) brightness(1.06)` (only `contrast()` below 1 in the set, and the brightest filter); overlays `linear-gradient(180deg, rgba(246,240,229,.24) 0%, rgba(246,240,229,.06) 30%, rgba(246,240,229,.2) 60%, rgba(244,236,222,.72) 100%)` then `radial-gradient(90% 70% at 30% 20%, rgba(255,246,226,.4), transparent 62%)`; vignette `0.3`; grain `0.03` (lowest); particle `dust` × 26 in `rgba(255,255,255,.5)`
- top chrome: `bar` chrome in a light theme — the strip is `color-mix(in srgb, var(--page) 88%, transparent)` over `#efe7da`, i.e. a pale frosted band; the Listening pill still fills with `--live` `#7d9c6d`.
- prose: A reader's first impression is that the lights are on: this is one of three light designs, and it is the only one that *adds* brightness (`1.06`) rather than dimming the photo. The plate is a near-opaque cream box (`0.9`) with dark ink text, which makes it read as a printed card sitting on a sunlit table. Its shadow is the softest in the set (`-34px` spread at `rgba(70,54,36,.45)`), so it does not float so much as rest. The panel is the `list` style, whose 28px round initials avatars are the only circular elements besides the header dot.

## 05 — Side B
- mood: "Record room, sleeves on the floor, needle down. Seventies lamp, nine p.m."
- fonts: caption `"Jost", sans-serif` / ui `"Jost", sans-serif` / display `"Fraunces", serif` (fontLabel `Jost`)
- palette: background `--page: #120c07` / surface `--surface: rgba(24,17,11,.74)` / text `--text: #f4e8d4` / dim `--dim: #a9926d` / accent `--accent: #c98a3f`; also `--accent-2: #8ba394`, `--live: #d99a4f`
- vars: `--surface-2: rgba(255,232,190,.06)`, `--line: rgba(232,200,152,.15)`, `--radius: 10px`, `--blur: 18px`, `--shadow: 0 26px 70px -32px rgba(0,0,0,.88)`, `--cap-bg: rgba(20,14,9,.5)`, `--cap-text: #fbf1de`, `--cap-edge: rgba(232,196,142,.2)`
- panel style + caption variant: `panel.style` `memo` (width 376) · `caption.style` `stack` · `chrome` `float`
- caption typography: align `center`, maxw `60ch`, bottom `6rem`, size `1.5rem`, weight `400`, tracking `0em`, leading `1.35`
- LIVE CAPTION: variant `stack` — a 2px solid left border in the speaker tone (no other border), a `plain` status badge so the header is just a dot and "listening" with `"rolling"` pushed to the right, and the finished previous line above the live one at `calc(1.5rem * 0.66)` = `0.99rem` in 34% cap-text.
- backdrop: pexels `31272472` jpeg; `filter: saturate(1.04) contrast(1.02) brightness(0.76)`; overlays `linear-gradient(180deg, rgba(20,14,9,.78) 0%, rgba(24,16,10,.28) 36%, rgba(26,18,11,.42) 66%, rgba(14,9,5,.92) 100%)` then `radial-gradient(70% 60% at 26% 34%, rgba(226,168,88,.26), transparent 62%)`; vignette `0.8`; grain `0.09` (second highest); particle `dust` × 26 in `rgba(250,214,160,.4)`
- top chrome: `float` — the three floating pieces, so the top of the frame is open photograph; the switcher reads `05 · Side B`.
- prose: The two-line roll is the first thing you understand: an older line sits above, truncated, at two-thirds size and 34% opacity, and the live line below it animates its newest word in with a 6px rise out of a 3px blur. Rotation is visible immediately — the `radius` is `10px` and the panel is a `memo`, i.e. monospace, numbered, uppercased session-log rows rather than chat rows. Grain at `0.09` animated in `steps(3)` is the coarsest texture of the set after theme 09, so a static screenshot already looks like scanned film. A single 2px vertical bar at the left edge of the caption takes the speaker's colour and changes as speakers change.

## 06 — North Window
- mood: "First snow outside the cabin. Everything inside is lamplight and quiet."
- fonts: caption `"Newsreader", serif` / ui `"Inter", sans-serif` / display `"Newsreader", serif` (fontLabel `Newsreader`)
- palette: background `--page: #0b161b` / surface `--surface: rgba(14,26,31,.7)` / text `--text: #eaf3f4` / dim `--dim: #9bb3b6` / accent `--accent: #8fc7c2`; also `--accent-2: #e0b183`, `--live: #a8ddd6` (the only theme where `--live` is a lighter tint of `--accent`, not the same value)
- vars: `--surface-2: rgba(226,244,246,.07)`, `--line: rgba(206,232,234,.16)`, `--radius: 20px`, `--blur: 20px`, `--shadow: 0 26px 70px -32px rgba(0,0,0,.85)`, `--cap-bg: rgba(12,24,29,.5)`, `--cap-text: #f1f8f9`, `--cap-edge: rgba(210,236,240,.2)`
- panel style + caption variant: `panel.style` `cards` (width 372) · `caption.style` `glass` · `chrome` `bar`
- caption typography: align `center`, maxw `62ch`, bottom `6rem`, size `1.62rem`, weight `300`, tracking `0.005em`, leading `1.42`
- LIVE CAPTION: variant `glass` with the lightest caption weight in the set at `1.62rem`; the glow dot and speaker label are both in `--accent` `#8fc7c2`, the level bars in 55% cap-text.
- backdrop: pexels `35542566` jpeg; `filter: saturate(0.92) contrast(1.02) brightness(0.86)`; overlays `linear-gradient(180deg, rgba(14,26,32,.74) 0%, rgba(16,28,34,.26) 34%, rgba(16,28,34,.4) 64%, rgba(10,20,26,.9) 100%)` then `radial-gradient(60% 50% at 62% 46%, rgba(255,204,132,.24), transparent 60%)` (the smallest warm pool, dead centre); vignette `0.8`; grain `0.05`; particle `snow` × 60 in `rgba(255,255,255,.75)`
- top chrome: `bar` chrome; the panel is the `cards` style, so each history line is a `mx-4 mb-2.5` card with a `3px` left border in the speaker tone and a `translateY(-1px)` hover.
- prose: Sixty haloed white motes fall on 12–28 s loops, which is the largest number of moving objects in any
  backdrop in the set (rain uses 46 on much faster 0.9–2.2 s loops, dust/ember 26 on 10–28 s), so the room reads
  as "snowing" before you read a word. The glass plate is a rounded `20px` rectangle with a `1px`
  `rgba(210,236,240,.2)` edge and a `0.5`-opaque interior, i.e. the blue-grey photograph stays visible through
  the words. `--live` is deliberately lighter than `--accent`, so the listening pill and the dot read as ice
  rather than brass. The card panel is the one design here whose history rows have their own borders inside
  the panel, giving two nested layers of containers.

## 07 — Adobe Afternoon
- mood: "Terracotta walls, warm tiles, an unhurried interview recorded off the cuff."
- fonts: caption `"Inter", sans-serif` / ui `"Inter", sans-serif` / display `"Fraunces", serif` (fontLabel `Inter`)
- palette: background `--page: #150f0a` / surface `--surface: rgba(28,19,13,.7)` / text `--text: #f8efe3` / dim `--dim: #bfa184` / accent `--accent: #d99055`; also `--accent-2: #8fae9b`, `--live: #d99055`
- vars: `--surface-2: rgba(255,232,206,.07)`, `--line: rgba(238,208,178,.17)`, `--radius: 22px` (largest), `--blur: 18px`, `--shadow: 0 24px 66px -32px rgba(0,0,0,.85)`, `--cap-bg: rgba(24,16,10,.66)`, `--cap-text: #fdf5ea`, `--cap-edge: rgba(238,206,172,.2)`
- panel style + caption variant: `panel.style` `cards` (width 384) · `caption.style` `chip` · `chrome` `bar`
- caption typography: align `center`, maxw `60ch`, bottom `5.8rem`, size `1.42rem` (smallest caption size), weight `400`, tracking `0em`, leading `1.4`
- LIVE CAPTION: variant `chip` — the speaker is the only variant that wraps the name in a filled pill: `background: color-mix(in srgb, #d99055 18%, transparent)` with a `34%` border, then "capturing" in 0.58rem and the level bars pushed to `ml-auto`.
- backdrop: pexels `34686220` jpeg; `filter: saturate(1.04) contrast(0.98) brightness(1.02)`; overlays `linear-gradient(180deg, rgba(37,26,18,.68) 0%, rgba(37,26,18,.22) 34%, rgba(37,26,18,.36) 64%, rgba(28,19,12,.86) 100%)` then `radial-gradient(80% 60% at 34% 24%, rgba(255,222,186,.34), transparent 64%)` (the strongest warm pool, `0.34`); vignette `0.6`; grain `0.05`; particle `dust` × 26 in `rgba(255,230,200,.5)`
- top chrome: `bar` chrome with the largest corner radii (`--radius: 22px`) propagating into the pill radius family; the switcher reads `07 · Adobe Afternoon`.
- prose: The most visible thing is the speaker *chip*: a small rounded capsule filled with a translucent wash of the speaker's tone, holding a dot and an uppercase name, with the audio-level bars at the far right of the same row. It is the smallest caption type in the set (`1.42rem`) but the busiest header row, so the block reads as a device label rather than a subtitle. The photo is barely dimmed (`brightness(1.02)`, `vignette 0.6`), so a bright afternoon terrace shows through a `0.66`-opaque box. Rounded corners of `22px` on the caption and `calc(22 * 0.9)` = `19.8px` from `card`s make this the softest-edged design in the set.

## 08 — Glasshouse
- mood: "Green light through wet glass. Foliage, rain, a voice taking its time."
- fonts: caption `"Jost", sans-serif` / ui `"Jost", sans-serif` / display `"Fraunces", serif` (fontLabel `Jost`)
- palette: background `--page: #08120e` / surface `--surface: rgba(10,20,16,.72)` / text `--text: #e9f2ea` / dim `--dim: #94ae9c` / accent `--accent: #a8d4b0`; also `--accent-2: #d6c48f`, `--live: #9fd0a8`
- vars: `--surface-2: rgba(224,240,226,.06)`, `--line: rgba(200,226,206,.15)`, `--radius: 14px`, `--blur: 20px`, `--shadow: 0 24px 66px -32px rgba(0,0,0,.85)`, `--cap-bg: rgba(8,18,14,.4)`, `--cap-text: #f0f7f0`, `--cap-edge: rgba(206,232,212,.18)`
- panel style + caption variant: `panel.style` `list` (width 360) · `caption.style` `bare` · `chrome` `sidebarHead`
- caption typography: align **`left`**, maxw `54ch`, bottom `6.2rem`, size `1.6rem`, weight `300`, tracking `0.005em`, leading `1.44`
- LIVE CAPTION: variant `bare` at `align: "left"` — in `App.tsx` the wrapper gets `marginLeft: "4vw"` instead of `auto`, and inside the variant the badge row loses `text-center` and the meta row loses `justify-center`, so the dot, the words and the device note all left-align to a column 4vw in from the caption box.
- backdrop: pexels `38663879` **png** (the only non-jpeg wallpaper); `filter: saturate(0.95) contrast(1.04) brightness(0.74)`; overlays `linear-gradient(180deg, rgba(8,18,14,.8) 0%, rgba(10,20,16,.28) 36%, rgba(10,20,16,.42) 66%, rgba(6,14,11,.92) 100%)` then `radial-gradient(90% 70% at 40% 20%, rgba(168,214,178,.22), transparent 62%)`; vignette `0.85`; grain `0.06`; particle `rain` × 46 in `rgba(226,244,232,.45)` (no halo)
- top chrome: `sidebarHead` — **no top bar at all**; the controls live in a bottom-left column (pill with Mark + `m:ss`, a row of buttons, then the `{scriptTitle} · {statsText}` line), and `topInset` becomes `0`, so the scene slate sits at `top: 18px` instead of `82px`.
- prose: Two things stand out immediately: the caption is left-aligned (one of only two designs that are) and there is no header bar — the chrome has dropped to the bottom-left corner, leaving the top of the frame to the photograph. The 4vw offset plus `maxWidth: 54ch` makes a narrow left column of text rather than a centred subtitle. Rain streaks fall without halos here, so the rain is thin bright lines instead of glowing dots. The caption has no box or border at all, so the `#f0f7f0` text over a green image relies entirely on the `0 2px 26px rgba(0,0,0,.72)` shadow.

## 09 — Film Club
- mood: "Black and white on the wall, four chairs, a projector ticking. Subtitles feel at home."
- fonts: caption `"Instrument Serif", serif` / ui `"Inter", sans-serif` / display `"Instrument Serif", serif` (fontLabel `Instrument Serif`)
- palette: background `--page: #080808` / surface `--surface: rgba(14,14,14,.76)` / text `--text: #f3f1ea` / dim `--dim: #9a978e` / accent `--accent: #cfc7b0`; also `--accent-2: #9fb0c0`, `--live: #cfc7b0`
- vars: `--surface-2: rgba(255,255,255,.05)`, `--line: rgba(240,238,230,.16)`, `--radius: 4px` (smallest), `--blur: 14px` (smallest), `--shadow: 0 24px 66px -32px rgba(0,0,0,.95)` (hardest), `--cap-bg: rgba(6,6,6,.8)`, `--cap-text: #fbfaf5`, `--cap-edge: rgba(240,238,230,.22)`
- panel style + caption variant: `panel.style` `memo` (width 372) · `caption.style` `plate` · `chrome` `bar`
- caption typography: align `center`, maxw `58ch`, bottom `5.2rem` (closest to the bottom edge), size `1.62rem`, weight `400`, tracking **`0.06em`** (widest tracking, 12× the next value), leading **`1.3`** (tallest-tightest), `upper: false` — the only theme that writes `upper` at all
- LIVE CAPTION: variant `plate` at `0.06em` tracking on a serif — the widest letter-spacing in the set — inside a `4px`-radius near-black box, with the left rail dot in `--live` `#cfc7b0`; the companion text "speaking now" inherits `textTransform: "none"` because `upper` is `false`.
- backdrop: pexels `20494415` jpeg; `filter: grayscale(0.92) contrast(1.08) brightness(0.78)` (the only grayscale filter and the highest contrast); overlays `linear-gradient(180deg, rgba(8,8,8,.82) 0%, rgba(10,10,10,.3) 36%, rgba(10,10,10,.48) 70%, rgba(6,6,6,.95) 100%)` then `radial-gradient(80% 60% at 50% 30%, rgba(255,255,255,.12), transparent 62%)`; vignette **`1`**; grain **`0.12`** (both maxima); particle `dust` × 26 in `rgba(255,255,255,.35)`
- top chrome: `bar` chrome, but the whole app is monochrome here — `--accent`, `--live` and `--accent-2` are all desaturated off-whites/blues, so the Mark ring, the Listening pill and the button highlights are all bone-coloured.
- prose: It is the only design that hollows the frame out: vignette `1` means the corners are fully black and grain `0.12` animates on top of a `grayscale(0.92)` image, so the room reads as projected film stock. The caption is a near-black plate (`rgba(6,6,6,.8)`) with a 4px radius — almost square-cornered, and the hardest shadow in the set — so it reads as burned-in subtitle rather than UI. `0.06em` tracking on a 1.62rem serif plus `lineHeight 1.3` is the densest, most letter-spaced caption typography of the twenty. The panel is a `memo`: monospace, three-digit numbered, always-24-hour rows, matching the projection-booth conceit.

## 10 — Night Swim
- mood: "A dock at dusk, water going still. Serif type drifting like a title card."
- fonts: caption `"Cormorant Garamond", serif` / ui `"Inter", sans-serif` / display `"Cormorant Garamond", serif` (fontLabel `Cormorant`)
- palette: background `--page: #100c1a` / surface `--surface: rgba(22,17,34,.68)` / text `--text: #f7eceb` / dim `--dim: #ab9bb0` / accent `--accent: #f0a68c`; also `--accent-2: #9fb6d8`, `--live: #f0a68c`
- vars: `--surface-2: rgba(255,226,226,.07)`, `--line: rgba(240,210,214,.17)`, `--radius: 16px`, `--blur: 18px`, `--shadow: 0 26px 72px -32px rgba(0,0,0,.9)`, `--cap-bg: rgba(18,13,28,.44)`, `--cap-text: #fdf1ee`, `--cap-edge: rgba(242,208,204,.2)`
- panel style + caption variant: `panel.style` `rail` (width **356**, narrowest) · `caption.style` `bare` · `chrome` `float`
- caption typography: align `center`, maxw `58ch`, bottom `6.5rem`, size **`1.95rem`** (largest in the set), weight `400`, tracking `0.01em`, leading `1.36`, **`italic: true`**
- LIVE CAPTION: variant `bare` with `italic: true` — so the base style sets `fontStyle: "italic"` on the whole line including the uppercase speaker label (which is a separate span and therefore also italic unless overridden — it is not). No box; the `0 2px 26px rgba(0,0,0,.72)` shadow is the only thing separating 1.95rem italic serif from a dusk photograph.
- backdrop: pexels `34569888` jpeg; `filter: saturate(1.06) contrast(1.02) brightness(0.86)`; overlays `linear-gradient(180deg, rgba(24,20,40,.66) 0%, rgba(26,22,42,.24) 32%, rgba(28,22,34,.34) 62%, rgba(16,12,22,.88) 100%)` then `radial-gradient(80% 60% at 62% 34%, rgba(255,196,168,.28), transparent 62%)`; vignette `0.7`; grain `0.05`; particle `none`
- top chrome: `float` chrome — three floating pieces and an open top edge; the narrowest panel (`356`) means the caption's right inset (`356 + 34 = 390`) is the smallest of the floating-panel designs.
- prose: The largest type in the collection — `1.95rem` Cormorant Garamond in italic — lands first, and it is a *floating* caption with no box, no border and no background, so it reads as a title card laid on the water. There is no particle layer here, so the only motion is the 1100 ms wallpaper crossfade, the per-word rise and the blinking caret: the stillest backdrop of the twenty. A warm `rgba(255,196,168,.28)` pool sits at 62% 34% under a cool `#100c1a` page, so the frame is split warm-over-cold. The panel is the floating `rail` at its narrowest.

## 11 — Reading Hour
- mood: "Lamplight between shelves, armchairs, a very low volume evening."
- fonts: caption `"Lora", serif` / ui `"Lora", serif` / display `"Lora", serif` (fontLabel `Lora`) — one family for all three roles
- palette: background `--page: #110c07` / surface `--surface: rgba(22,16,10,.74)` / text `--text: #f2e6d3` / dim `--dim: #a58e6c` / accent `--accent: #c9a447`; also `--accent-2: #a8b695`, `--live: #c9a447`
- vars: `--surface-2: rgba(255,234,196,.06)`, `--line: rgba(232,200,148,.16)`, `--radius: 12px`, `--blur: 18px`, `--shadow: 0 24px 68px -32px rgba(0,0,0,.88)`, `--cap-bg: rgba(20,14,9,.56)`, `--cap-text: #fbf2e1`, `--cap-edge: rgba(232,198,142,.2)`
- panel style + caption variant: `panel.style` `cards` (width 372) · `caption.style` `chip` · `chrome` `bar`
- caption typography: align `center`, maxw `58ch`, bottom `6rem`, size `1.46rem`, weight `400`, tracking `0em`, leading `1.44`
- LIVE CAPTION: variant `chip` with the smallest `maxw` of any chip design (`58ch` vs 60ch elsewhere) and `1.46rem` type; the speaker capsule is `color-mix(in srgb, #c9a447 18%, transparent)` with a `34%` border and a dot.
- backdrop: pexels `13278838` jpeg; `filter: saturate(0.98) contrast(1.05) brightness(0.76)`; overlays `linear-gradient(180deg, rgba(18,13,9,.78) 0%, rgba(20,15,10,.26) 34%, rgba(20,15,10,.4) 66%, rgba(11,8,5,.92) 100%)` then `radial-gradient(70% 60% at 30% 30%, rgba(240,196,120,.26), transparent 62%)`; vignette `0.9`; grain `0.07`; particle `dust` × 26 in `rgba(250,220,168,.4)`
- top chrome: `bar` chrome; because every role is Lora, the wordmark "Mumble", the script title, the buttons and the caption are all the same serif — only the sizes (`0.98rem` vs `0.62rem` vs `1.46rem`) separate them.
- prose: The single-family typography is the first thing a reader feels: a serif at every size, including the 0.62rem buttons and the wordmark, so the whole surface reads as one printed page. Two nested rounded layers are visible at once — the caption capsule and, inside it, the smaller speaker capsule, both keyed to the same gold tone. The 70%-wide warm pool at 30% 30% is aimed at the left of the frame where the depth cue sits, while the caption is centred. It is one of the calmest arrangements in the set despite carrying the `chip` variant, because `1.46rem` is the third-smallest caption size (after 07's `1.42rem` and 18's `1.44rem`).

## 12 — Snowline
- mood: "A pier in the snow, whistle of a lantern, bright grey light that somehow feels warm."
- fonts: caption `"Manrope", sans-serif` / ui `"Manrope", sans-serif` / display `"Fraunces", serif` (fontLabel `Manrope`)
- palette: background `--page: #e6edf1` (light) / surface `--surface: rgba(248,251,252,.82)` / text `--text: #1d2c33` / dim `--dim: #71858f` / accent `--accent: #3f7c86`; also `--accent-2: #8a7a52`, `--live: #3f7c86`
- vars: `--surface-2: rgba(29,44,51,.05)`, `--line: rgba(60,86,98,.18)`, `--radius: 20px`, `--blur: 18px`, `--shadow: 0 22px 56px -32px rgba(40,64,76,.4)`, `--cap-bg: rgba(252,254,255,.82)`, `--cap-text: #233139`, `--cap-edge: rgba(70,100,112,.16)`
- panel style + caption variant: `panel.style` `cards` (width 372) · `caption.style` `glass` · `chrome` `sidebarHead`
- caption typography: align `center`, maxw `62ch`, bottom `6rem`, size `1.56rem`, weight `400`, tracking `0em`, leading `1.42`
- LIVE CAPTION: variant `glass` in a light theme — an almost-white frosted plate (`rgba(252,254,255,.82)`) with dark `#233139` text, a `1px rgba(70,100,112,.16)` edge, and `blur(var(--blur)) saturate(1.15)`; the glow dot and the speaker name sit in `--accent` `#3f7c86`.
- backdrop: pexels `30252333` jpeg; `filter: saturate(0.82) contrast(1.02) brightness(1.0)` (the **only** theme that leaves brightness at exactly `1.0`); overlays `linear-gradient(180deg, rgba(226,236,240,.2) 0%, rgba(222,234,238,.04) 28%, rgba(220,232,238,.16) 58%, rgba(238,244,247,.7) 100%)` then `radial-gradient(80% 60% at 50% 30%, rgba(255,255,255,.34), transparent 60%)`; vignette `0.28` (second lowest); grain `0.04`; particle `snow` × 60 in `rgba(255,255,255,.85)` (the brightest particles in the set)
- top chrome: `sidebarHead` — no top bar; controls in the bottom-left column, and `topInset = 0` so the scene slate sits near the top of the photograph.
- prose: It reads as an overexposed frame: the filter does not darken anything, the vignette is only `0.28`, and the light gradients push towards `rgba(238,244,247,.7)` at the bottom, so the image stays near-white. The glass plate is `rgba(252,254,255,.82)` over that — a low-separation box on a low-separation backdrop, with dark text doing all the work. Sixty snow motes at the highest particle alpha in the set (`rgba(255,255,255,.85)`) drift across it on 12–28 s loops; against a near-white image they read as soft flares rather than specks. No top bar, so the composition is caption + panel + bottom-left controls only.

## 13 — Last Train
- mood: "Carriage four, mostly empty, window doubling the sky. Sage and graphite."
- fonts: caption `"Jost", sans-serif` / ui `"Jost", sans-serif` / display `"Jost", sans-serif` (fontLabel `Jost`) — one family for all three roles
- palette: background `--page: #0b1113` / surface `--surface: rgba(14,21,21,.72)` / text `--text: #e8efe9` / dim `--dim: #93a399` / accent `--accent: #a9c4a0`; also `--accent-2: #cbb488`, `--live: #a9c4a0`
- vars: `--surface-2: rgba(226,240,226,.06)`, `--line: rgba(200,224,204,.15)`, `--radius: 16px`, `--blur: 18px`, `--shadow: 0 24px 68px -32px rgba(0,0,0,.86)`, `--cap-bg: rgba(10,16,16,.5)`, `--cap-text: #f0f6f0`, `--cap-edge: rgba(204,228,208,.18)`
- panel style + caption variant: `panel.style` `rail` (width 368) · `caption.style` `stack` · `chrome` `bar`
- caption typography: align `center`, maxw `58ch`, bottom `6rem`, size `1.48rem`, weight `300`, tracking `0.01em`, leading `1.4`
- LIVE CAPTION: variant `stack` at weight **300** — the only `stack` theme using the light weight; the 2px left border takes the speaker tone, the badge is the `plain` dot + "listening", and the previous line renders at `calc(1.48rem * 0.66)` = `0.9768rem`.
- backdrop: pexels `18502603` jpeg; `filter: saturate(0.86) contrast(1.04) brightness(0.78)`; overlays `linear-gradient(180deg, rgba(12,18,18,.78) 0%, rgba(14,20,20,.26) 34%, rgba(14,20,20,.4) 64%, rgba(8,13,13,.92) 100%)` then `radial-gradient(70% 60% at 68% 24%, rgba(196,222,196,.2), transparent 62%)`; vignette `0.85`; grain `0.05`; particle `none`
- top chrome: `bar` chrome; sage-grey `#a9c4a0` is the accent everywhere (Mark ring, active buttons, live pill), so the controls and the caption rail share one colour.
- prose: The two-line roll is unmistakable: a truncated, 34%-opacity previous line above the live one, which is itself marked by a single 2px sage bar on its left edge. Because the weight is 300 and the tracking is only `0.01em`, that pair of lines is quiet; there is no dust, no ember and no snow — the only motion is the word rise, the caret blink and the 1100 ms wallpaper crossfade. Nothing is boxed with a full border: one edge only. The floating `rail` panel mirrors the same grammar with its hairline and 9px dots.

## 14 — Dusk Highway
- mood: "Long road, sky going lilac, tape deck low. Field notes read out loud."
- fonts: caption `"Manrope", sans-serif` / ui `"Manrope", sans-serif` / display `"Fraunces", serif` (fontLabel `Manrope`)
- palette: background `--page: #120e20` / surface `--surface: rgba(22,17,34,.7)` / text `--text: #f6ece3` / dim `--dim: #ab9dae` / accent `--accent: #e5a06e`; also `--accent-2: #9db2cf`, `--live: #e5a06e`
- vars: `--surface-2: rgba(255,228,210,.06)`, `--line: rgba(240,214,200,.16)`, `--radius: 14px`, `--blur: 18px`, `--shadow: 0 24px 68px -32px rgba(0,0,0,.88)`, `--cap-bg: rgba(18,13,28,.36)` (the most translucent caption surface), `--cap-text: #fdf3ea`, `--cap-edge: rgba(242,214,198,.18)`
- panel style + caption variant: `panel.style` `memo` (width 372) · `caption.style` `bare` · `chrome` `float`
- caption typography: align **`left`**, maxw **`52ch`** (narrowest measure), bottom `6.2rem`, size `1.58rem`, weight `300`, tracking `0em`, leading **`1.46`** (tallest line-height)
- LIVE CAPTION: variant `bare` at `align: "left"` — `marginLeft: "4vw"` in `App.tsx`, left-aligned badge and meta rows inside the variant; the `bare` variant ignores `--cap-bg` entirely, so the `0.36` value only affects the `StatusBadge` pill above the text.
- backdrop: pexels `7022830` jpeg; `filter: saturate(1.06) contrast(1.0) brightness(0.84)`; overlays `linear-gradient(180deg, rgba(26,20,40,.64) 0%, rgba(28,22,42,.22) 32%, rgba(30,24,38,.32) 62%, rgba(18,14,28,.88) 100%)` then `radial-gradient(90% 60% at 50% 62%, rgba(255,204,168,.26), transparent 62%)` (aimed low, at the horizon); vignette `0.7`; grain `0.07`; particle `dust` × 26 in `rgba(255,226,196,.45)`
- top chrome: `float` chrome; the `memo` panel beyond it is monospace and numbered, so the right edge of the screen is a different typeface family from the caption.
- prose: The left-aligned, narrow (`52ch`), widely-led (`1.46`) column is what registers first — it looks like a field notebook margin rather than a centred subtitle, and at weight 300 it is the lightest large text in the set. The warm pool is aimed at 62% height rather than at the top, which puts the glow at the horizon line and leaves the caption area above it relatively clean. The `memo` panel is the counterweight: monospace, numbered, with a confidence percentage on every row. Dust motes glow at `0.45` alpha and drift upward past the text.

## 15 — Harbor Lights
- mood: "A moored boat, reflections like oil paint, brass fittings on dark teal."
- fonts: caption `"Fraunces", serif` / ui `"Inter", sans-serif` / display `"Fraunces", serif` (fontLabel `Fraunces`)
- palette: background `--page: #061317` / surface `--surface: rgba(8,22,26,.76)` / text `--text: #eaf2f3` / dim `--dim: #95afb2` / accent `--accent: #e0a869`; also `--accent-2: #8fc0c9`, `--live: #e0a869`
- vars: `--surface-2: rgba(226,242,246,.06)`, `--line: rgba(206,232,236,.16)`, `--radius: 16px`, `--blur: 22px`, `--shadow: 0 26px 72px -32px rgba(0,0,0,.9)`, `--cap-bg: rgba(6,19,23,.5)`, `--cap-text: #f4f8f8`, `--cap-edge: rgba(210,236,240,.2)`
- panel style + caption variant: `panel.style` `sheet` (width 388) · `caption.style` `glass` · `chrome` `bar`
- caption typography: align `center`, maxw `62ch`, bottom `6rem`, size `1.6rem`, weight `400`, tracking `0.005em`, leading `1.42`, **`italic: true`**
- LIVE CAPTION: variant `glass` with `italic: true` — so the serif line, the uppercase speaker label and the 0.26em footer all inherit italic; the frosted plate uses the joint-largest blur (`22px`, tied with 01) with `saturate(1.15)`.
- backdrop: pexels `16966474` jpeg; `filter: saturate(1.06) contrast(1.05) brightness(0.78)`; overlays `linear-gradient(180deg, rgba(6,20,24,.8) 0%, rgba(8,22,26,.28) 34%, rgba(8,22,26,.44) 66%, rgba(4,14,17,.93) 100%)` then `radial-gradient(70% 60% at 34% 30%, rgba(255,196,110,.26), transparent 62%)`; vignette `0.9`; grain `0.07`; particle `none`
- top chrome: `bar` chrome; the brass accent `#e0a869` is `--accent` and `--live` at once, so the top strip's Mark ring, the active buttons and the Listening pill are all the same warm metal colour as the pool in the photo.
- prose: The brass-on-teal split is the structure: a `#061317` page and a `rgba(255,196,110,.26)` pool, with an italic Fraunces caption floating in a frosted pane that is only `0.5` opaque. `saturate(1.06)` and `contrast(1.05)` together make this one of the punchier photos in the set, and the vignette at `0.9` pins the corners to black. No particles at all, so the texture comes only from the animated grain and the 22px blur of the glass. The 6px glowing dot at the top-left of the caption pane is the brightest small element on screen.

## 16 — Fireside
- mood: "A lodge with the fire still going. Amber, wool, slow voices, no clock in sight."
- fonts: caption `"Lora", serif` / ui `"Lora", serif` / display `"Lora", serif` (fontLabel `Lora`)
- palette: background `--page: #150c05` / surface `--surface: rgba(26,17,10,.74)` / text `--text: #f6e9d6` / dim `--dim: #b09272` / accent `--accent: #f0b26b` (the brightest accent in the set); also `--accent-2: #93a89a`, `--live: #f0b26b`
- vars: `--surface-2: rgba(255,230,190,.07)`, `--line: rgba(240,206,158,.17)`, `--radius: 18px`, `--blur: 18px`, `--shadow: 0 26px 70px -32px rgba(0,0,0,.9)`, `--cap-bg: rgba(22,14,8,.52)`, `--cap-text: #fdf3e3`, `--cap-edge: rgba(242,208,160,.2)`
- panel style + caption variant: `panel.style` `cards` (width 372) · `caption.style` `stack` · `chrome` `sidebarHead`
- caption typography: align `center`, maxw `58ch`, bottom `6rem`, size `1.5rem`, weight `400`, tracking `0em`, leading `1.44`
- LIVE CAPTION: variant `stack` — one 2px amber left border carrying the speaker tone, a `plain` badge, and the previous line above at `calc(1.5rem * 0.66)` = `0.99rem`; no box border anywhere else.
- backdrop: pexels `33454123` jpeg; `filter: saturate(1.04) contrast(1.04) brightness(0.74)` (darkest brightness tied with 03); overlays `linear-gradient(180deg, rgba(20,13,7,.78) 0%, rgba(22,15,8,.26) 34%, rgba(24,16,9,.42) 66%, rgba(12,8,4,.92) 100%)` then `radial-gradient(80% 70% at 24% 36%, rgba(255,176,96,.3), transparent 64%)` (the only overlay at 70% vertical extent); vignette `0.9`; grain `0.08`; particle **`ember`** × 26 in `rgba(255,176,96,.7)` — the only `ember` theme, and each mote gets a `boxShadow: 0 0 {size*2.4}px rgba(255,176,96,.7)` halo
- top chrome: `sidebarHead` — no top bar; controls sit bottom-left, and `topInset = 0` keeps the scene slate high.
- prose: The embers are the tell: 26 orange motes with a glow halo each, rising on 10–28 s loops over a fire-warm photograph, which is the strongest "moving light" effect in the collection. The caption is a two-line roll defined by a single 2px amber bar at its left edge rather than a box, so the block has no top, right or bottom boundary. Everything is Lora at every size, including the buttons and the wordmark. There is no top bar, and the `memo`-free `cards` panel makes each history line a raised card with a 3px coloured edge.

## 17 — Blue Hour
- mood: "Eight fifteen from a balcony. The city is soft-edged and nobody is hurrying."
- fonts: caption `"Inter", sans-serif` / ui `"Inter", sans-serif` / display `"Manrope", sans-serif` (fontLabel `Inter`)
- palette: background `--page: #0a111c` / surface `--surface: rgba(13,20,32,.72)` / text `--text: #e9eef6` / dim `--dim: #93a2b8` / accent `--accent: #e0a894`; also `--accent-2: #9ab6cf`, `--live: #e0a894`
- vars: `--surface-2: rgba(228,238,250,.06)`, `--line: rgba(208,222,240,.15)`, `--radius: 18px`, `--blur: 20px`, `--shadow: 0 24px 70px -32px rgba(0,0,0,.88)`, `--cap-bg: rgba(10,16,26,.4)`, `--cap-text: #f2f6fb`, `--cap-edge: rgba(212,226,244,.18)`
- panel style + caption variant: `panel.style` `rail` (width 364) · `caption.style` `bare` · `chrome` `float`
- caption typography: align `center`, maxw `60ch`, bottom `6.5rem`, size `1.5rem`, weight `300`, tracking `0.005em`, leading `1.46`
- LIVE CAPTION: variant `bare` at weight 300 — no box, only the `0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)` shadow; the speaker label is a `1.15 × 0.66rem` uppercase span at `0.3em` in the speaker tone.
- backdrop: pexels `15183904` jpeg; `filter: saturate(0.92) contrast(1.04) brightness(0.74)`; overlays `linear-gradient(180deg, rgba(10,17,28,.78) 0%, rgba(12,19,30,.26) 34%, rgba(12,19,30,.4) 66%, rgba(7,12,20,.92) 100%)` then `radial-gradient(80% 60% at 66% 30%, rgba(214,178,168,.24), transparent 64%)`; vignette `0.85`; grain `0.05`; particle `none`
- top chrome: `float` chrome — a top-left pill, a centred control pill and the stats line at `top-[74px]`; `--live` is the same blush `#e0a894` as the accent, so the Listening pill is the only strong colour in the corner.
- prose: A blush accent on a navy page, with nothing boxed: the caption is a floating light-weight line under a small pill, and the panel is a floating `rail` card with a hairline and 9px dots. The takeaway is the restraint — no particles, grain at `0.05`, vignette `0.85`, and a single warm radial aimed at 66% 30%. Everything reads as UI: Inter at three sizes (0.62rem buttons, 0.6rem tags, 1.5rem caption) over a Manrope wordmark. This is structurally the same design as 10, only moved from purple/serif/italic/1.95rem to navy/sans/roman/1.5rem.

## 18 — Paper Rain
- mood: "A suburban afternoon in the rain, mist on glass, grey-blue and unhurried like paper."
- fonts: caption `"Newsreader", serif` / ui `"Inter", sans-serif` / display `"Newsreader", serif` (fontLabel `Newsreader`)
- palette: background `--page: #dee6ec` (light) / surface `--surface: rgba(247,250,252,.84)` / text `--text: #1f2c36` / dim `--dim: #6d818e` / accent `--accent: #4a6b86`; also `--accent-2: #7c7f9a`, `--live: #4a6b86`
- vars: `--surface-2: rgba(31,44,54,.05)`, `--line: rgba(64,86,102,.18)`, `--radius: 14px`, `--blur: 18px`, `--shadow: 0 22px 58px -32px rgba(40,60,76,.38)`, `--cap-bg: rgba(250,252,254,.88)`, `--cap-text: #22303b`, `--cap-edge: rgba(70,96,112,.16)`
- panel style + caption variant: `panel.style` `memo` (width 380) · `caption.style` `chip` · `chrome` `bar`
- caption typography: align `center`, maxw `60ch`, bottom `5.9rem`, size `1.44rem`, weight `400`, tracking `0em`, leading `1.44`
- LIVE CAPTION: variant `chip` in a light theme — the speaker capsule is `color-mix(in srgb, #4a6b86 18%, transparent)` with a `34%` border, "capturing" is `color-mix(in srgb, #22303b 40%, transparent)`, and the level bars are `color-mix(in srgb, #22303b 50%, transparent)`, i.e. grey-blue marks on a near-white plate.
- backdrop: pexels `38026077` jpeg; `filter: saturate(0.6) contrast(1.0) brightness(0.86)` (**lowest saturation in the set**); overlays `linear-gradient(180deg, rgba(226,234,240,.26) 0%, rgba(222,231,238,.06) 28%, rgba(220,230,238,.18) 58%, rgba(236,241,245,.74) 100%)` then `radial-gradient(80% 60% at 40% 26%, rgba(255,255,255,.26), transparent 60%)`; vignette `0.32`; grain `0.05`; particle `rain` × 46 in `rgba(255,255,255,.7)` (no halo — thin white streaks over a white-misted image)
- top chrome: `bar` chrome in the lightest palette of the three light themes; the strip is a pale `color-mix` of `#dee6ec`, and the `memo` panel beyond it is monospace and numbered.
- prose: The near-total desaturation (`0.6`) leaves a grey-blue wash where the rain streaks are white and barely separable from the backdrop, so the frame reads as mist rather than as weather. The `chip` caption is a bright near-white plate (`0.88`) with dark text, sitting on the least-dark part of the image, so the words are the highest-contrast object on screen. The panel is a `memo` — monospace, three-digit numbered, always-24-hour — which visibly changes the texture of the right-hand third even though it inherits the light palette. `1.44rem` with `1.44` leading makes a compact, even block of text.

## 19 — Terrace Sun
- mood: "Late sun on a quiet terrace. Green, cream, unhurried, the whole afternoon to talk."
- fonts: caption `"Jost", sans-serif` / ui `"Jost", sans-serif` / display `"Fraunces", serif` (fontLabel `Jost`)
- palette: background `--page: #171a11` / surface `--surface: rgba(26,29,18,.72)` / text `--text: #f5f2e4` / dim `--dim: #b3b295` / accent `--accent: #c9cf8f` (yellow-green); also `--accent-2: #e0b98a`, `--live: #c9cf8f`
- vars: `--surface-2: rgba(246,246,226,.07)`, `--line: rgba(232,234,208,.16)`, `--radius: 16px`, `--blur: 18px`, `--shadow: 0 24px 66px -32px rgba(0,0,0,.85)`, `--cap-bg: rgba(22,25,15,.56)`, `--cap-text: #faf8ec`, `--cap-edge: rgba(234,236,206,.18)`
- panel style + caption variant: `panel.style` `list` (width 364) · `caption.style` `karaoke` · `chrome` `sidebarHead`
- caption typography: align `center`, maxw `62ch`, bottom `5.9rem`, size `1.5rem`, weight `400`, tracking `0.005em`, leading `1.42`
- LIVE CAPTION: variant `karaoke` — the only variant that dims the not-yet-said words: revealed words at `#faf8ec` with `filter: blur(0px)`, unrevealed words at `color-mix(in srgb, #faf8ec 30%, transparent)` with `filter: blur(1.1px)`, both transitioning `color .3s ease, filter .3s ease`; header row = uppercase speaker at `0.26em`, a 12px-tall hairline divider, level bars in the yellow-green tone, and `"read-along"` at `ml-auto`.
- backdrop: pexels `14955235` jpeg; `filter: saturate(0.94) contrast(1.0) brightness(1.02)`; overlays `linear-gradient(180deg, rgba(30,32,22,.62) 0%, rgba(30,32,22,.2) 32%, rgba(30,32,22,.32) 62%, rgba(24,26,18,.84) 100%)` then `radial-gradient(80% 60% at 62% 22%, rgba(255,240,198,.32), transparent 62%)`; vignette `0.55`; grain `0.04`; particle `dust` × 26 in `rgba(255,248,220,.5)`
- top chrome: `sidebarHead` — no top bar, controls in the bottom-left column; the yellow-green accent is used for the Mark ring, the active buttons and the level bars at once.
- prose: The read-along effect is the whole design: the words you have not heard yet are visibly blurred (`1.1px`) and held at 30% opacity, and they sharpen as they are revealed, so the caption is a progress display rather than a line of text. There is also a `read-along` label at the right of the header row, making the mechanic explicit. The frame is otherwise warm and low-contrast — a cream radial aimed high at 62% 22%, vignette `0.55`, and 26 soft dust motes. No top bar, so the top-left of the photo carries a yellow-green scene dot, and the `list` panel's coloured initials avatars are the only circles besides the status dot.

## 20 — Quiet Marina
- mood: "Frost on the docks, steel blue water, one warm lamp swinging above it all."
- fonts: caption `"Newsreader", serif` / ui `"Inter", sans-serif` / display `"Newsreader", serif` (fontLabel `Newsreader`)
- palette: background `--page: #071119` / surface `--surface: rgba(9,19,27,.76)` / text `--text: #e8eff5` / dim `--dim: #93a8b5` / accent `--accent: #d8a35f`; also `--accent-2: #8fb0c9`, `--live: #d8a35f`
- vars: `--surface-2: rgba(222,236,246,.06)`, `--line: rgba(202,224,238,.16)`, `--radius: 14px`, `--blur: 20px`, `--shadow: 0 26px 70px -32px rgba(0,0,0,.9)`, `--cap-bg: rgba(7,16,23,.54)`, `--cap-text: #f2f7fa`, `--cap-edge: rgba(206,228,242,.2)`
- panel style + caption variant: `panel.style` `sheet` (width 384) · `caption.style` `karaoke` · `chrome` `bar`
- caption typography: align `center`, maxw `62ch`, bottom `6rem`, size `1.5rem`, weight `400`, tracking `0em`, leading `1.42`
- LIVE CAPTION: variant `karaoke` — identical structure to 19 except tracking `0em` instead of `0.005em`; unrevealed words at `color-mix(in srgb, #f2f7fa 30%, transparent)` with `filter: blur(1.1px)`, revealed at full `#f2f7fa` with `blur(0px)`, `0.3s` colour+filter transitions; LevelBars in `--accent` `#d8a35f` at `opacity-40` when paused.
- backdrop: pexels `10636454` jpeg; `filter: saturate(0.94) contrast(1.04) brightness(0.76)`; overlays `linear-gradient(180deg, rgba(8,16,24,.8) 0%, rgba(10,18,26,.28) 34%, rgba(10,18,26,.44) 66%, rgba(5,11,17,.93) 100%)` then `radial-gradient(70% 60% at 30% 26%, rgba(240,196,120,.24), transparent 62%)`; vignette `0.9`; grain `0.06`; particle `snow` × 60 in `rgba(255,255,255,.5)`
- top chrome: `bar` chrome; brass `#d8a35f` is both `--accent` and `--live`, so the Listening pill, the Mark ring and the karaoke level bars share the lamp colour that the radial pool puts into the photo.
- prose: Like 19 this is a read-along caption, so unrevealed words sit behind a `1.1px` blur and lift into focus as they are revealed — the same visible mechanic with a brass tone instead of yellow-green. Behind it, 60 white snow motes glow on a bright blue page and a warm lamp-coloured pool sits at 30% 26%. The caption block is a bordered `0.54`-opaque pane with `--cap-edge: rgba(206,228,242,.2)`, the same grammar as the `glass` panel but without the `saturate` boost. A `sheet` panel flushes to the right edge, so the whole right third of the frame is a flat surface.

# Duplicate / near-duplicate groups

Structural identity here means the same `caption.style` **and** the same `panel.style` (and, when noted, the
same `chrome`). Within a group the designs differ only in palette, fonts, `size`/`tracking`/`leading` and
`panel.width` unless stated otherwise — a re-implementation can carry one layout and swap tokens.

- **10 `nightswim` ≡ 17 `blue-hour`** — the closest pair in the set. Identical `bare` + `rail` + `float`;
  identical `caption.align: "center"`; both `size` in the 1.5–1.95rem band at tracking `0.01em`/`0.005em`.
  They differ in: serif vs sans caption (`"Cormorant Garamond", serif` vs `"Inter", sans-serif`), `italic: true`
  vs absent, `1.95rem` vs `1.5rem`, `leading 1.36` vs `1.46`, purple `#100c1a`/`#f0a68c` vs navy `#0a111c`/`#e0a894`,
  `panel.width 356` vs `364`, particle `none` (both) and `--radius 16px` vs `18px`. Nothing about the *arrangement* differs.
- **07 `adobe` ≡ 11 `reading-hour`** — same `chip` + `cards` + `bar`, same caption weight 400 and leading 1.4
  vs 1.44, same centred alignment, same 372/384 panel width band. They differ in palette (terracotta
  `#d99055` vs gold `#c9a447`), fonts (Inter caption vs Lora caption), `size 1.42rem` vs `1.46rem`,
  `maxw 60ch` vs `58ch`, and `--radius 22px` vs `12px`.
- **19 `terrace` ≈ 20 `quiet-marina`** — both `karaoke`, both centred, both `size 1.5rem` / `leading 1.42` /
  `maxw 62ch`, both weight 400. The caption differs only by `tracking 0.005em` vs `0em` and by palette
  (yellow-green `#c9cf8f` vs brass `#d8a35f`). The panel and chrome differ: `list` + `sidebarHead` vs `sheet` + `bar`.
- **06 `north-window` ≈ 12 `snowline`** — both `glass` + `cards` + centred, `maxw 62ch`, `bottom 6rem`,
  weight 300 vs 400, `size 1.62rem` vs `1.56rem`, and both `particle: "snow"` at 60. They are near-mirror
  images: 06 is dark teal with `--cap-bg rgba(12,24,29,.5)` and a top bar; 12 is light `#e6edf1` with
  `--cap-bg rgba(252,254,255,.82)` and `sidebarHead`. Only the chrome differs structurally.
- **01 `rainline` ≈ 10 `nightswim` ≈ 17 `blue-hour`** — three `bare` designs at `align: "center"` with the
  status pill above and the Meta line below. 01 breaks the tie with `sheet` + `bar` + rain; 10 and 17 are the
  `float` + `rail` pair above.
- **08 `glasshouse` ≈ 14 `dusk-highway`** — the only two `align: "left"` designs, and both are `bare`. 08 is
  `list` + `sidebarHead`, no warm pool at bottom, `54ch`; 14 is `memo` + `float`, `52ch`, `leading 1.46`.
  Both put the text into a narrow left column with `marginLeft: "4vw"`.
- **03 `cellar` ≈ 06 `north-window` ≈ 15 `harbor`** — three dark `glass` designs with `bottom 6rem` and
  `tracking 0.005em`; 15 adds `italic: true` and `saturate(1.15)` is the same for all three. Panels differ:
  `rail` + `float` (03), `cards` + `bar` (06), `sheet` + `bar` (15). 12 joins this layout family from the light side.
- **02 `blue-plate` ≈ 04 `linen` ≈ 09 `film-club`** — all three `plate` + `bar` + centred at weight 400; the
  variant is identical and only the tokens move (bottoms `5.5rem`/`5.5rem`/`5.2rem`, `68ch`/`66ch`/`58ch`,
  `1.5`/`1.55`/`1.62rem`, tracking `0em`/`0em`/`0.06em`). Panels differ (`sheet`/`list`/`memo`). 02 and 09 are
  both warm-neutral serif plates; 04 is the inverted light one.
- **05 `side-b` ≈ 13 `last-train` ≈ 16 `fireside`** — the three `stack` designs, all `align: "center"`, all
  `maxw 58ch` or `60ch`, all `bottom 6rem`, all leading 1.35–1.44. They differ in weight (400/300/400),
  `size` (1.5/1.48/1.5rem), tracking (0em/0.01em/0em) and in panel/chrome (`memo`+`float`, `rail`+`bar`, `cards`+`sidebarHead`).
- **Same panel style, different caption:** `sheet` = 01, 02, 15, 20 · `rail` = 03, 10, 13, 17 ·
  `list` = 04, 08, 19 · `memo` = 05, 09, 14, 18 · `cards` = 06, 07, 11, 12, 16. A re-implementation can
  therefore build five panel layouts and six caption layouts and cover all twenty by pairing them.
- **Repeated font stacks across otherwise unrelated designs:** `"Jost", sans-serif` is the caption in 05, 08,
  13, 19; `"Lora", serif` in 11, 16; `"Manrope", sans-serif` in 01, 12, 14; `"Newsreader", serif` in 04, 06,
  18, 20; `"Inter", sans-serif` in 07, 17. Four themes use one family for `ui`+`display`+`caption` (01 Manrope,
  11 Lora, 13 Jost, 16 Lora).
- **Identical caption geometry with different tokens:** `maxw 62ch` appears in 01, 06, 12, 15, 19, 20;
  `bottom 6rem` appears in 03, 05, 06, 11, 12, 13, 15, 16, 20 (the pair together = 06, 12, 15, 20);
  `size 1.5rem` appears in 02, 05, 16, 17, 19, 20; `leading 1.42` appears in 01, 06, 12, 15, 19, 20;
  `tracking 0em` appears in 02, 04, 05, 07, 11, 12, 14, 16, 18, 20.
- **Identical accent/live pairs:** `--accent === --live` in 15 of 20 (02, 03, 07, 09, 10, 11, 12, 13, 14, 15,
  16, 17, 18, 19, 20). The five that differ are 01 (`#9fc9dd` vs `#8fd0c9`), 04 (`#a8672f` vs `#7d9c6d`),
  05 (`#c98a3f` vs `#d99a4f`), 06 (`#8fc7c2` vs `#a8ddd6`) and 08 (`#a8d4b0` vs `#9fd0a8`).

# Aggressiveness

Ranked from the concrete numbers only (palette alpha/saturation, `filter` brightness/contrast/saturation,
vignette, grain, particle count and glow, caption size/tracking/weight, border and radius hardness,
per-word motion, and whether the caption text is inverted or blurred).

## CALM (6)

- **01 `rainline`** — `saturate(0.78) contrast(1.06) brightness(0.78)`, caption weight `300`, `bare` (no box, no
  border, no `--cap-bg`), grain `0.05`, and rain streaks that are the only particle class with **no**
  `boxShadow` halo, so nothing on screen emits light.
- **03 `cellar`** — `brightness(0.72)` plus a `0.95` vignette pins the frame dark, the caption is only `0.46`
  opaque, and the 26 dust motes run at `rgba(240,206,150,.45)` with `opacity 0.15 + r2*0.5`; the only
  *interface* motion is a 2.4 s dot pulse and a 1.05 s caret blink.
- **04 `linen`** — `contrast(0.98)` (the only sub-1 contrast), grain `0.03` and vignette `0.3` (both lowest or
  near-lowest), the softest shadow in the set (`0 22px 60px -34px rgba(70,54,36,.45)`), caption weight `400`
  at `1.55rem`; the caption plate is `0.9` opaque so the photo never interferes with reading.
- **11 `reading-hour`** — one family (Lora) at every size, `1.46rem` caption with `0em` tracking, grain `0.07`
  but a low-key warm palette; 26 dust motes glow at `rgba(250,220,168,.4)`, but the caption itself carries no
  box blur, no border animation and no per-word dimming — only the `soft-in` rise and the word rise.
- **13 `last-train`** — `saturate(0.86)` with **`particle: "none"`** (no moving specks at all), caption weight
  `300` at `1.48rem`, and the single ornament is a `2px` left border; the only room-scale motion is the
  1100 ms wallpaper crossfade.
- **17 `blue-hour`** — `particle: "none"`, `saturate(0.92) brightness(0.74)`, weight `300`, `bare` with no box,
  and an accent (`#e0a894`) that appears on exactly one small label plus the Listening pill.

## MODERATE (7)

- **05 `side-b`** — grain `0.09` (second highest) animated in `steps(3)`, 26 dust motes **with** glow halos in
  `rgba(250,214,160,.4)`, and the two-line roll adds a second text block above the live one; `--radius 10px`
  is nearly square.
- **06 `north-window`** — 60 snow motes at `rgba(255,255,255,.75)` with a per-mote `boxShadow: 0 0 {size*2.4}px`,
  the joint-highest mote count in the set (tied with 12); the caption itself is calm (`300`, `0.005em`).
- **07 `adobe`** — `brightness(1.02)` and the strongest warm pool (`rgba(255,222,186,.34)`), `--radius: 22px`
  (largest), and the `chip` header stacks a `18%`-filled capsule, a `0.58rem` state label and level bars in one row.
- **08 `glasshouse`** — 46 rain streaks plus a left-aligned `bare` caption over a `0.74`-brightness green frame;
  it is calm in colour but the left column at `54ch` and the missing top bar change where the eye goes.
- **14 `dusk-highway`** — `saturate(1.06)`, `lineHeight 1.46` (the tallest), a very translucent `--cap-bg: rgba(18,13,28,.36)`,
  a left-aligned `bare` caption and 26 glowing dust motes.
- **15 `harbor`** — `saturate(1.06) contrast(1.05)`, italic Fraunces, a `22px`-blur glass pane, a `0.9` vignette
  and a `#e0a869` accent used simultaneously for the Mark, the active buttons and the caption's glow dot.
- **18 `paper-rain`** — `saturate(0.6)` is the lowest saturation of the twenty, but the page is a light
  `#dee6ec` under a `0.86` brightness photo with white `rgba(255,255,255,.7)` rain, and the caption is
  `rgba(250,252,254,.88)` — nine-tenths opaque — so the words sit on a bright plate, not on the picture.

## LOUD (7)

- **02 `blue-plate`** — the most opaque **dark** caption surface in the set (`--cap-bg: rgba(12,7,2,.86)`) under a
  `0.9` vignette, with `sepia(0.14)`, `brightness(0.8)`, a `0.34`-strength amber pool and an accent
  (`#e8a860`) that fills the Listening pill, the left-rail dot and the speaker label at once.
- **09 `film-club`** — `grayscale(0.92) contrast(1.08)`, vignette **`1`** (corners fully black), grain **`0.12`**
  animated in `steps(3)` at 1.2 s, `--radius: 4px` (hard corners), the hardest shadow (`rgba(0,0,0,.95)`),
  a `0.8`-opaque near-black plate with `#fbfaf5` text, and `letterSpacing 0.06em` — 6× the next widest
  tracking (`0.01em`, in 10 and 13).
- **10 `nightswim`** — `1.95rem` (largest caption), italic Cormorant Garamond at weight 400, `saturate(1.06)`,
  with **no box and no border** behind it, so the largest type in the app is also the least contained.
- **12 `snowline`** — `brightness(1.0)` (the only filter that does not darken the photo), vignette `0.28`, light
  scrims up to `rgba(238,244,247,.7)`, 60 snow motes at the highest particle alpha (`rgba(255,255,255,.85)`) with
  halos, and a `rgba(252,254,255,.82)` caption plate — a near-white surface on a near-white frame.
- **16 `fireside`** — the only `ember` theme: 26 motes at `rgba(255,176,96,.7)` (the highest-alpha warm
  particle colour; only 12's `rgba(255,255,255,.85)` is higher), each with a `0 0 {size*2.4}px` orange halo,
  over `brightness(0.74)` with a `0.3` warm pool, grain `0.08`, accent `#f0b26b` on the Mark, the buttons,
  the caption border and the live pill.
- **19 `terrace`** — `karaoke`: every not-yet-said word is rendered at `30%` opacity behind
  `filter: blur(1.1px)` with a continuous `0.3s` transition, so the text a reader is about to read is
  deliberately out of focus and constantly changing.
- **20 `quiet-marina`** — `karaoke` with the same `blur(1.1px)`/`30%` unrevealed treatment, plus 60 haloed snow
  motes at `rgba(255,255,255,.5)`, a `0.9` vignette and a brass accent used on the caption's level bars, the
  live pill and the panel simultaneously.
