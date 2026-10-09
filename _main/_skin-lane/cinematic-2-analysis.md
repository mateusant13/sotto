# cinematic-2 mockup — freeze analysis

Subject: `H:\sotto\_main\_design-lane\zips\cinematic-2\` (React 19 + Vite 7 + Tailwind v4, `vite-plugin-singlefile`).
Purpose: everything a freeze step needs to render each design's panels as static skins.

**Revision note (the AGENTS.md rule that line citations need a revision).** All citations below are
against the tree as read in this session. Sizes: `src/App.tsx` 9007 B, `src/themes.ts` 33299 B,
`src/components/LiveCaptions.tsx` 15414 B, `src/components/TopChrome.tsx` 12981 B,
`src/components/HistoryPanel.tsx` 18221 B, `src/components/Stage.tsx` 5201 B,
`src/components/DesignGallery.tsx` 7828 B, `src/hooks/useTranscription.ts` 7241 B,
`src/lib/scripts.ts` 10853 B, `src/index.css` 4267 B, `index.html` 1117 B. No `node_modules/`, no
`dist/`, no `public/` in the tree — **nothing was built by this analysis and nothing outside this file
was written.** Anything that requires the built CSS is marked NOT DETERMINED with what would determine it.

---

## 1. Named designs / themes

**20 designs. One exported array: `THEMES: Theme[]`, source order = display order, `id` = 1-based `n`.**
`src/themes.ts:82` `export const THEMES: Theme[] = [`. Lookup helper `src/themes.ts:885`
`export const themeById = (id: string): Theme => THEMES.find((t) => t.id === id) ?? THEMES[0];`

| # | `n` | `id` | `name` (human label) |
|---|---|---|---|
| 1 | 01 | `rainline` | Rainline |
| 2 | 02 | `blue-plate` | Blue Plate |
| 3 | 03 | `cellar` | Cellar Sessions |
| 4 | 04 | `linen` | Linen Hours |
| 5 | 05 | `side-b` | Side B |
| 6 | 06 | `north-window` | North Window |
| 7 | 07 | `adobe` | Adobe Afternoon |
| 8 | 08 | `glasshouse` | Glasshouse |
| 9 | 09 | `film-club` | Film Club |
| 10 | 10 | `nightswim` | Night Swim |
| 11 | 11 | `reading-hour` | Reading Hour |
| 12 | 12 | `snowline` | Snowline |
| 13 | 13 | `last-train` | Last Train |
| 14 | 14 | `dusk-highway` | Dusk Highway |
| 15 | 15 | `harbor` | Harbor Lights |
| 16 | 16 | `fireside` | Fireside |
| 17 | 17 | `blue-hour` | Blue Hour |
| 18 | 18 | `paper-rain` | Paper Rain |
| 19 | 19 | `terrace` | Terrace Sun |
| 20 | 20 | `quiet-marina` | Quiet Marina |

Entry shape (`src/themes.ts:18-49`):

```ts
export interface Theme {
  n: string; id: string; name: string; mood: string;
  scene: string; sceneNote: string;
  wall: Wallpaper;                 // { src: string; thumb: string }
  filter: string; overlays: string[]; vignette: number; grain: number;
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

Variants (`src/themes.ts:8-11`):
`CaptionStyle = "bare" | "glass" | "plate" | "chip" | "stack" | "karaoke"`;
`PanelStyle = "sheet" | "rail" | "list" | "memo" | "cards"`;
`ChromeStyle = "bar" | "float" | "sidebarHead"`; `Particle = "rain" | "dust" | "ember" | "snow" | "none"`.

Verbatim entry #1 (the template every entry follows), `src/themes.ts:83-122`:

```ts
  {
    n: "01",
    id: "rainline",
    name: "Rainline",
    mood: "Rain on the glass at one in the morning. Cold blue room, warm tea, everything slow.",
    scene: "Ext. rain-specked window",
    sceneNote: "late shift · recorder on the sill",
    wall: px("9488153"),
    filter: "saturate(0.78) contrast(1.06) brightness(0.78)",
    overlays: [ /* two CSS gradient strings */ ],
    vignette: 0.85, grain: 0.05, particle: "rain", particleColor: "rgba(214,236,245,.55)",
    time24: true,
    fonts: { ui: '"Manrope", sans-serif', display: '"Manrope", sans-serif', caption: '"Manrope", sans-serif', fontLabel: "Manrope" },
    caption: { style: "bare", align: "center", maxw: "62ch", bottom: "6.5rem", size: "1.72rem", weight: 300, tracking: "-0.01em", leading: 1.42 },
    panel: { style: "sheet", width: 384 },
    chrome: "bar",
    vars: { /* 15 keys — see §5 */ },
  },
```

Label maps: `CAPTION_LABELS` `src/themes.ts:59`, `PANEL_LABELS` `:68`, `CHROME_LABELS` `:76`.

**Per-design matrix (the freeze step's work list).** `bl = noborder` — 5 designs use `chrome:"sidebarHead"`.

| id | caption.style | caption.align | caption.bottom | caption.size/weight/tracking/leading | ital/upper | panel.style / width | chrome | particle | time24 | wall pexels id |
|---|---|---|---|---|---|---|---|---|---|---|
| rainline | bare | center | 6.5rem | 1.72rem/300/-0.01em/1.42 | – | sheet / 384 | bar | rain | ✔ | 9488153 |
| blue-plate | plate | center | 5.5rem | 1.5rem/400/0em/1.34 | – | sheet / 392 | bar | none | – | 8887627 |
| cellar | glass | center | 6rem | 1.78rem/400/0.005em/1.4 | – | rail / 368 | float | dust | ✔ | 35258949 |
| linen | plate | center | 5.5rem | 1.55rem/400/0em/1.38 | – | list / 380 | bar | dust | – | 18405036 |
| side-b | stack | center | 6rem | 1.5rem/400/0em/1.35 | – | memo / 376 | float | dust | – | 31272472 |
| north-window | glass | center | 6rem | 1.62rem/300/0.005em/1.42 | – | cards / 372 | bar | snow | ✔ | 35542566 |
| adobe | chip | center | 5.8rem | 1.42rem/400/0em/1.4 | – | cards / 384 | bar | dust | – | 34686220 |
| glasshouse | bare | **left** | 6.2rem | 1.6rem/300/0.005em/1.44 | – | list / 360 | **sidebarHead** | rain | ✔ | 38663879 (`.png`) |
| film-club | plate | center | 5.2rem | 1.62rem/400/0.06em/1.3 | upper:false | memo / 372 | bar | dust | ✔ | 20494415 |
| nightswim | bare | center | 6.5rem | 1.95rem/400/0.01em/1.36 | **italic** | rail / 356 | float | none | – | 34569888 |
| reading-hour | chip | center | 6rem | 1.46rem/400/0em/1.44 | – | cards / 372 | bar | dust | ✔ | 13278838 |
| snowline | glass | center | 6rem | 1.56rem/400/0em/1.42 | – | cards / 372 | **sidebarHead** | snow | ✔ | 30252333 |
| last-train | stack | center | 6rem | 1.48rem/300/0.01em/1.4 | – | rail / 368 | bar | none | ✔ | 18502603 |
| dusk-highway | bare | **left** | 6.2rem | 1.58rem/300/0em/1.46 | – | memo / 372 | float | dust | – | 7022830 |
| harbor | glass | center | 6rem | 1.6rem/400/0.005em/1.42 | **italic** | sheet / 388 | bar | none | ✔ | 16966474 |
| fireside | stack | center | 6rem | 1.5rem/400/0em/1.44 | – | cards / 372 | **sidebarHead** | ember | – | 33454123 |
| blue-hour | bare | center | 6.5rem | 1.5rem/300/0.005em/1.46 | – | rail / 364 | float | none | – | 15183904 |
| paper-rain | chip | center | 5.9rem | 1.44rem/400/0em/1.44 | – | memo / 380 | bar | rain | – | 38026077 |
| terrace | **karaoke** | center | 5.9rem | 1.5rem/400/0.005em/1.42 | – | list / 364 | **sidebarHead** | dust | – | 14955235 |
| quiet-marina | **karaoke** | center | 6rem | 1.5rem/400/0em/1.42 | – | sheet / 384 | bar | snow | ✔ | 10636454 |

Fonts per design (`fontLabel`): Manrope ×3 (1,12,14), Fraunces ×3 (2,9→Instrument Serif,15), Cormorant
×2 (3,10), Newsreader ×4 (4,6,18,20), Jost ×4 (5,8,13,19), Inter ×2 (7,17), Instrument Serif ×1 (9),
Lora ×2 (11,16). Only `fonts.ui` / `fonts.display` / `fonts.caption` are consumed; `fontLabel` is a
gallery chip only.

---

## 2. How the active design is selected at runtime

**There is NO URL query, NO hash, NO localStorage, NO sessionStorage, NO React Router.** Verified by
grep over `src/`: the only `document.` uses are `src/main.tsx:6` (`getElementById("root")`) and
`src/App.tsx:64` (the export blob's `<a>`). Zero matches for `location.`, `URLSearchParams`, `hash`,
`history.`, `localStorage`, `sessionStorage`.

The selection is **plain React state in `App`**, initialised to a hard-coded index, `src/App.tsx:13`:

```tsx
  const [themeId, setThemeId] = useState(THEMES[2].id); // cellar rose — a warm, low-lit opener
```

**Default design = index 2 = `cellar`** (`THEMES[2]`, 0-based).

Every writer of that state:

- Keyboard, `src/App.tsx:72-103` (listener on **`window`**, `:101`):

```tsx
      } else if (e.key === "ArrowRight") {
        cycle(1);
      } else if (e.key === "ArrowLeft") {
        cycle(-1);
      } else if (e.key.toLowerCase() === "g") {
        setGallery((v) => !v);
      ...
      } else if (/^[1-9]$/.test(e.key)) {
        const i = Math.min(Number(e.key) - 1, THEMES.length - 1);
        setThemeId(THEMES[i].id);
      }
```

  Note: the digit shortcut covers **only `1`–`9`** (`/^[1-9]$/`) — designs 10–20 are unreachable by
  digit, only by arrow-cycling or by the gallery.

- `cycle`, `src/App.tsx:37-42`:

```tsx
  const cycle = useCallback((dir: number) => {
    setThemeId((cur) => {
      const i = THEMES.findIndex((x) => x.id === cur);
      return THEMES[(i + dir + THEMES.length) % THEMES.length].id;
    });
  }, []);
```

- The gallery pick, wired at `src/App.tsx:249`:
  `onPick={(id) => setThemeId(id)}` — the overlay opens on `g` (`src/App.tsx:86-87`) or the chrome
  gallery button (`src/App.tsx:150` `onGallery={() => setGallery(true)}`); each card is a `<button>`
  with `onClick={() => onPick(t.id)}` `src/components/DesignGallery.tsx:86`.
- The chrome `‹` / `›` (prev/next), `src/App.tsx:153-154` → same `cycle`.

Nothing persists the choice and nothing reads it back at mount.

### EXACTLY how a headless browser forces design N

There is no deep link to set, so the freezer must drive the UI. Deterministic, in order of robustness:

**A. Arrow-cycling from the known default (recommended — no selector, no overlay, works for all 20).**
The default index is 2 (`cellar`), so to reach 0-based index `i`:

```js
// after load + React mount; i = 0..19  (design N has i = N-1)
const k = (i - 2 + 20) % 20;                 // ArrowRight presses from the default
for (let n = 0; n < k; n++)
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
```

Why this is exact: the handler is registered on `window` (`src/App.tsx:101`) and the branch tests
`e.key === "ArrowRight"` (`:82`); `cycle` uses a **functional** updater (`setThemeId((cur) => …)`,
`:38`), so N synchronous dispatches queue and compose in order — the result is exactly N steps, not 1.
Then await a paint (React commits on the next microtask/frame) before capturing, and add a settle delay
for the transitions (`transition-[right] duration-500` on the caption wrapper `:160`,
`transition-opacity duration-[1100ms]` on the Stage wallpaper layers `Stage.tsx:73`,
`transition-all duration-500` on the slate `Stage.tsx:113`). **≥1.2 s settle** if the previous design's
wallpaper layer is still cross-fading.
*Caveat:* keep the keydown target out of the `INPUT`/`TEXTAREA` guard (`:74-78`) — that guard returns
early for key events whose `e.target` is an input; dispatching on `window` gives `e.target === window`,
so the guard does not fire. Do not focus the history search input before dispatching.

**B. Gallery click (needed if a specific design must be reached without cycling).**
`window.dispatchEvent(new KeyboardEvent('keydown',{key:'g',bubbles:true}))` opens the overlay
(`:86`), then click the card. There is **no `data-*` attribute, id, or class per design** — the only
per-design hooks in the DOM are the visible texts `t.n` ("07") and `t.name` ("Adobe Afternoon")
(`DesignGallery.tsx:109`, `:120`). So:

```js
const btn = [...root.querySelectorAll('button')]
  .find(b => b.textContent.includes('Adobe Afternoon'));   // unique — names are unique
btn.click();
```

(The card also contains the mood text and chip labels; the name string is unique across the 20.)
Then close/ignore the overlay (picking does **not** auto-close — `onClose` is bound to the backdrop
click and the `close` button, `DesignGallery.tsx:22`, `:63`), so **press `Escape`** (`App.tsx:94-95`)
or click the backdrop after picking.

**C. Do NOT** look for `?design=`, `#design-`, or a `select`/radio — none exist. Forcing via React
state requires the devtools hook into the React root, which is not exposed by the app.

**D. Deterministic content note (affects every capture).** The simulated transcript is
time- and randomness-driven (§6). For the first ~900 ms after mount the state is fully deterministic:
`engine.nextAt = performance.now() + 900` (`useTranscription.ts:68`) so no partial exists yet, `partial
= null`, the caption shows the last seed entry, and `running === true` ("listening"). Capturing all 20
designs inside that window (or with `Math.random`/timers stubbed via `addInitScript`, then a fixed
virtual time) yields reproducible skins. Otherwise every capture samples a different line and a
different `revealed` count.

---

## 3. DOM topology of the visible screen — theme `cellar` (the default, `THEMES[2]`)

`cellar` = `caption.style:"glass"`, `panel.style:"rail"`, `chrome:"float"`, `particle:"dust"`,
`panel.width:368`, `caption.bottom:"6rem"`, `caption.maxw:"64ch"`, `align:"center"`.
Class list is verbatim; `[style …]` abbreviates the inline style object (only the design-dependent
keys are spelled out). React renders no wrapper elements of its own — fragments collapse.

```
#root                                       ← index.css:15 html,body,#root{height:100%}
└─ div.relative.h-full.w-full.overflow-hidden                       [App.tsx:129]
   │   [style = theme.vars, the 15 custom props of §5 — THIS is the only element that gets them]
   │
   ├─ Stage → div.absolute.inset-0.overflow-hidden                  [Stage.tsx:69-151]
   │  │   [style background:"var(--page)"]
   │  ├─ div.absolute.inset-0.bg-cover.bg-center.transition-opacity.duration-\[1100ms\].ease-out
   │  │     ×1 (transiently ×2 during a design change, Stage.tsx:20-25)
   │  │     [style backgroundImage:`url(${theme.wall.src})`, filter:theme.filter,
   │  │            transform:"scale(1.04)", opacity: 1 (newest) | 0 (previous)]
   │  ├─ div.absolute.inset-0.pointer-events-none  ×2 (theme.overlays, Stage.tsx:84-86)
   │  │     [style background: <gradient string>]
   │  ├─ div.absolute.inset-0.pointer-events-none
   │  │     [style background:`radial-gradient(115% 90% at 50% 45%, transparent 42%, rgba(0,0,0,${vignette}) 100%)`]
   │  ├─ (particle !== "none") div.absolute.inset-0.pointer-events-none.overflow-hidden   [Stage.tsx:97-103]
   │  │  └─ span.drift-mote  ×26   (dust|ember → 26, snow → 60, rain → 46; Stage.tsx:29)
   │  │        [style left/bottom/width/height/opacity/background/animationDuration/animationDelay/boxShadow]
   │  │        (rain instead: span.rain-streak ×46, [style left/height/width/opacity/animation*,
   │  │         background:"linear-gradient(to bottom, transparent, <particleColor>)"], Stage.tsx:34-47)
   │  ├─ div.absolute.inset-0.pointer-events-none.mix-blend-overlay.grain-layer   [Stage.tsx:106-109]
   │  │     [style opacity: theme.grain]
   │  ├─ div.absolute.left-6.sm\:left-9.pointer-events-none.select-none.transition-all.duration-500
   │  │     [Stage.tsx:112-134] [style top: topInset+18 (=82 for float), fontFamily: fonts.ui]
   │  │  ├─ div.flex.items-center.gap-2\.5
   │  │  │  ├─ span.h-\[7px\].w-\[7px\].rounded-full
   │  │  │  │     [style background:var(--accent), boxShadow:"0 0 14px var(--accent)"]
   │  │  │  └─ span.text-\[10px\].tracking-\[0\.32em\].uppercase
   │  │  │        [style color:color-mix(in srgb, var(--text) 78%, transparent)]  → {theme.scene}
   │  │  └─ div.mt-1\.5.text-\[10\.5px\].tracking-\[0\.18em\].italic
   │  │        [style color:color-mix(in srgb, var(--text) 46%, transparent)]     → {theme.sceneNote}
   │  └─ div.absolute.inset-0.pointer-events-none
   │     └─ span.absolute.h-5.w-5.{top-4 left-4 border-t border-l | top-4 right-4 border-t border-r |
   │                                bottom-4 left-4 border-b border-l | bottom-4 right-4 border-b border-r} ×4
   │           [style borderColor:color-mix(in srgb, var(--text) 22%, transparent)]
   │
   ├─ {!immersive} TopChrome, chrome==="float" → fragment of 3 siblings      [TopChrome.tsx:238-299]
   │  ├─ div.absolute.top-4.left-4.z-30.hidden.xl\:block.sm\:top-6.sm\:left-7   ← INVISIBLE at 380px
   │  │     [style padding:2]
   │  │  └─ div.flex.items-center.gap-3.rounded-full.px-4.py-2\.5
   │  │        [style background:var(--surface), backdropFilter:blur(var(--blur)),
   │  │               border:1px solid var(--line), boxShadow:var(--shadow)]
   │  │     ├─ Mark: div.flex.items-center.gap-2\.5.select-none
   │  │     │  ├─ span.relative.flex.h-6.w-6.items-center.justify-center
   │  │     │  │  ├─ span.absolute.inset-0.rounded-full
   │  │     │  │  │     [style background:color-mix(in srgb,var(--accent) 24%,transparent),
   │  │     │  │  │            border:1px solid color-mix(in srgb,var(--accent) 46%,transparent)]
   │  │     │  │  └─ span.h-1\.5.w-1\.5.rounded-full  [style background:var(--accent)]
   │  │     │  └─ span [style fontFamily:fonts.display, .98rem, color:var(--text)] → "Mumble"
   │  │     ├─ span.h-4.w-px [style background:var(--line)]
   │  │     └─ span [style fonts.ui .62rem uppercase color:var(--dim)] → scriptTitle ("Late Shift Radio")
   │  ├─ div.absolute.top-4.left-1\/2.z-30.-translate-x-1\/2.sm\:top-6      ← THE visible top chrome at 380px
   │  │  └─ div.flex.items-center.gap-2.rounded-full.px-2\.5.py-2
   │  │        [style background:var(--surface), backdropFilter:blur(var(--blur)),
   │  │               border:1px solid var(--line), boxShadow:var(--shadow)]
   │  │     ├─ LivePill: button.inline-flex.items-center.gap-2.rounded-full.transition-colors.duration-200
   │  │     │              .px-3.py-1\.5.whitespace-nowrap.order-first   [TopChrome.tsx:127-146]
   │  │     │     [style running ? {color:"#0c1013", background:var(--live), border:1px solid var(--live),
   │  │     │              boxShadow:"0 10px 30px -14px var(--live)"}
   │  │     │            : {color:var(--text), background:var(--surface-2), border:1px solid var(--line)}]
   │  │     │     ├─ svg 13×13  (IconPause when running | IconPlay when paused)
   │  │     │     └─ text node → "Listening" | "Paused"        ← the status pill
   │  │     ├─ span.hidden.items-center.gap-2\.5.px-1\.5.sm\:flex   ← INVISIBLE at 380px
   │  │     │  ├─ LEVEL METER (TopChrome.Level): span.flex.items-end.gap-\[2\.5px\].h-3
   │  │     │  │  └─ span.w-\[2px\].rounded-full.transition-\[height\].duration-150 ×6
   │  │     │  │        [style height:`${Math.max(3, level*12*m)}px`, background:running?var(--live):var(--dim),
   │  │     │  │               opacity:0.4+level*0.55*m], m = [.55,.85,1,.7,.45,.3]
   │  │     │  └─ span [style fonts.ui .62rem, color:var(--dim)] → mmss(elapsed)
   │  │     ├─ Switcher: div.flex.items-center.overflow-hidden.rounded-full
   │  │     │     [style border:1px solid var(--line), background:var(--surface-2)]
   │  │     │  ├─ button.px-2\.5.py-1\.5 → "‹"           [title "Previous design (←)"]
   │  │     │  ├─ button.px-1.py-1\.5.whitespace-nowrap
   │  │     │  │     → {theme.n} · <span.hidden.xl\:inline>{theme.name}</span>   ← name INVISIBLE at 380px
   │  │     │  └─ button.px-2\.5.py-1\.5 → "›"           [title "Next design (→)"]
   │  │     ├─ button.btn [btnStyle()]        → "{speed}×"           (speed default 1 → "1×")
   │  │     ├─ button.btn [btnStyle(false)]   → svg IconGrid         [title "Designs (G)"]
   │  │     │     └─ span.hidden.sm\:inline → "{NN}/{20}"            ← INVISIBLE at 380px
   │  │     ├─ button.btn [btnStyle(panelOpen)] → svg IconPanel
   │  │     └─ button.btn [btnStyle(false)]   → svg IconEye
   │  │        btn = "inline-flex items-center gap-2 rounded-full transition-colors duration-200 px-3 py-1.5 whitespace-nowrap"
   │  │        btnStyle(a) = [fonts.ui .62rem uppercase, color:a?var(--text):color-mix(var(--text) 72%),
   │  │                        background:a?color-mix(var(--accent) 20%,transparent):var(--surface-2),
   │  │                        border:1px solid a?color-mix(var(--accent) 42%,transparent):var(--line)]
   │  └─ div.absolute.top-\[74px\].left-1\/2.z-30.hidden.-translate-x-1\/2.sm\:block   ← INVISIBLE at 380px
   │        → statsText ("3 speakers · 12 lines · 94% conf.")
   │
   ├─ CAPTION WRAPPER                                               [App.tsx:159-183]
   │  div.pointer-events-none.absolute.z-\[25\].transition-\[right\].duration-500
   │     [style left:0, right: panelVisible ? theme.panel.width+34 : 0  (=402 for cellar),
   │            bottom: theme.caption.bottom (= "6rem")]
   │  └─ div.px-5.sm\:px-10
   │        [style width:"100%", maxWidth: theme.caption.maxw ("64ch"),
   │               marginLeft/marginRight: align==="center" ? "auto" : "4vw"]
   │     └─ div.pointer-events-auto
   │        └─ LiveCaptions, glass variant                        [LiveCaptions.tsx:190-237]
   │           div.soft-in.px-6.py-4.sm\:px-8.sm\:py-5
   │              [style  base={fontFamily:fonts.caption, fontSize:`clamp(1.02rem, 1.78rem, 2.3rem)`,
   │                       fontWeight:400, letterSpacing:"0.005em", lineHeight:1.4,
   │                       fontStyle:"normal", textTransform:"none"},
   │                      background:var(--cap-bg), border:1px solid var(--cap-edge),
   │                      borderRadius:var(--radius),
   │                      backdropFilter:"blur(var(--blur)) saturate(1.15)",
   │                      boxShadow:"0 30px 80px -40px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.06)"]
   │           ├─ div.mb-2\.5.flex.items-center.justify-between.gap-6
   │           │  ├─ div.flex.items-center.gap-2\.5
   │           │  │  ├─ span.h-1\.5.w-1\.5.rounded-full
   │           │  │  │     [style background: tone, boxShadow:`0 0 10px ${tone}`]
   │           │  │  └─ span.uppercase [style .66rem / .26em / color:tone / fontFamily:fonts.ui]
   │           │  │        → speakerShort(speaker)   ← "June" for June; "Sofia" for "Sofia (caller)"
   │           │  └─ span.{"" when running | "opacity-0" when paused}       [:214]
   │           │     └─ LEVEL METER (LiveCaptions.LevelBars): span.flex.items-end.gap-\[3px\].h-3\.5
   │           │        └─ span.w-\[2\.5px\].rounded-full.transition-\[height,opacity\].duration-150 ×5
   │           │              [style height:`${Math.max(3, level*13*mult)}px`,
   │           │                     background:`color-mix(in srgb, var(--cap-text) 55%, transparent)`,
   │           │                     opacity:0.35+level*0.6*mult], mult=[.5,.8,1,.66,.4]
   │           ├─ div [style color: var(--cap-text)]        ← THE live-caption text container
   │           │  ├─ WordRun → ONE span PER WORD, always the WHOLE line       [LiveCaptions.tsx:92-117]
   │           │  │     span [className = i === revealed-1 ? "word-in" : undefined]
   │           │  │          [style {...(i < revealed ? bright : dim), display:"inline-block", whiteSpace:"pre"}]
   │           │  │       → text node: the word (+ a literal " " for every word but the last)
   │           │  │       ⚠ for "glass" (and bare/plate/chip/stack) `bright`/`dim` are NOT passed
   │           │  │         (only the karaoke variant passes them, :436-437) → no visual
   │           │  │         confirmed/provisional distinction; the only per-word marker is `.word-in`
   │           │  │         on index `revealed-1`.
   │           │  │       ⚠ there is NO per-character wrapper anywhere (grep: `word-in` is the only
   │           │  │         animation class on text; no `split("")` in the tree).
   │           │  └─ Caret (only when isLive = partial && running): span.caret.ml-1\.5.inline-block.align-baseline
   │           │        [style width:"2px", height:"0.92em", background:tone, borderRadius:2,
   │           │               transform:"translateY(0.06em)"]
   │           └─ div.mt-2\.5.flex.items-center.justify-between.gap-4 [style fontFamily:fonts.ui]
   │              ├─ Meta: div.flex.items-center.gap-3.text-\[9\.5px\].uppercase
   │              │     [style letterSpacing:"0.26em",
   │              │            color:color-mix(in srgb, var(--text) 42%, transparent)]
   │              │  ├─ span → "transcribing June" | "last line"
   │              │  ├─ span.h-3.w-px [style background:color-mix(in srgb,var(--text) 20%,transparent)]
   │              │  └─ span → "on-device · 240 ms"
   │              └─ span.text-\[9\.5px\].uppercase
   │                    [style .24em, color:color-mix(in srgb,var(--cap-text) 38%,transparent)]
   │                    → "live track" | "hold"
   │
   ├─ {panelVisible} HistoryPanel, panel.style==="rail"            [HistoryPanel.tsx:383-423]
   │  aside.absolute.z-20.flex.flex-col.overflow-hidden.{right-3 top-3 bottom-3}
   │     [style width: 368, maxWidth:"calc(100vw - 48px)",
   │            background:var(--surface), backdropFilter:blur(var(--blur)),
   │            border:"1px solid var(--line)", borderRadius:var(--radius), boxShadow:var(--shadow)]
   │     (rail|cards → the rounded/floating branch, :86-87; sheet|list|memo → ":88"
   │      {background,borderLeft:"1px solid var(--line), NO radius} + class `right-0 top-0 bottom-0`, :386)
   │  ├─ Header div.px-5.pt-5.pb-3 [style borderBottom:"1px solid var(--line)"]      [:98-180]
   │  │  ├─ div.flex.items-start.justify-between.gap-3
   │  │  │  ├─ div
   │  │  │  │  ├─ div.flex.items-center.gap-2
   │  │  │  │  │  ├─ span.h-1\.5.w-1\.5.rounded-full   [style background:running?var(--live):var(--dim)]
   │  │  │  │  │  └─ span.uppercase  [tagStyle + color:var(--dim)] → "transcript history"
   │  │  │  │  └─ h2.mt-1\.5 [style fonts.display, 1.2rem, color:var(--text)] → "The room, so far"
   │  │  │  │       ("session log" + monospace + 1.05rem when panel.style==="memo", :114-122)
   │  │  │  └─ button.rounded-full.px-2.py-1 → text "HIDE"
   │  │  ├─ div.mt-3.flex.items-center.gap-2
   │  │  │  └─ input.w-full.bg-transparent.outline-none  placeholder="Search this transcript…"
   │  │  │        [style fonts.ui .76rem, color:var(--text),
   │  │  │               padding/border/background branch on panel.style list|cards vs rest, :145-149]
   │  │  └─ div.mt-3.flex.flex-wrap.items-center.gap-1\.5
   │  │     └─ button.rounded-full.px-2\.5.py-1  ×(1 + #speakers)
   │  │           ["All", ...speakers] → "everyone" | speakerShort(s)   [style uses speakerColor(s)]
   │  ├─ div.quiet-scroll.min-h-0.flex-1.overflow-y-auto        (ref=scroller, :391)
   │  │  ├─ (if nothing matches) div.px-5.py-10.text-center → "Nothing matches that. The room keeps talking either way."
   │  │  ├─ GROUP div  ×N   (one per contiguous `session`, :397-417)
   │  │  │  ├─ div.sticky.top-0.z-10.flex.items-center.gap-2.px-5.py-2
   │  │  │  │     [style background:color-mix(in srgb,var(--surface) 92%,transparent),
   │  │  │  │            backdropFilter:"blur(8px)",
   │  │  │  │            borderBottom:"1px solid color-mix(in srgb,var(--line) 60%,transparent)"]
   │  │  │  │  ├─ span [fonts.ui .58rem uppercase, var(--dim)] → group.session   "Earlier tonight"
   │  │  │  │  ├─ span.h-px.flex-1 [style background:color-mix(in srgb,var(--line) 70%,transparent)]
   │  │  │  │  └─ span [fonts.ui .58rem, var(--dim)] → group.items.length
   │  │  │  └─ ROW, panel.style==="rail" — div.group.relative.cursor-pointer.pl-7.pr-4.py-2\.5  [:211-231]
   │  │  │     │   (onClick = copy the line to the clipboard)
   │  │  │     ├─ span.absolute.left-\[18px\].top-0.bottom-0.w-px
   │  │  │     │     [style background:color-mix(in srgb,var(--line) 70%,transparent)]
   │  │  │     ├─ span.absolute.left-\[14px\].top-\[17px\].h-\[9px\].w-\[9px\].rounded-full
   │  │  │     │     [style background:color-mix(in srgb,${tone} 90%,transparent),
   │  │  │     │            border:"2px solid color-mix(in srgb,var(--surface) 100%,transparent)",
   │  │  │     │            boxShadow:`0 0 0 1px ${tone}`]
   │  │  │     ├─ div.flex.items-baseline.gap-2\.5
   │  │  │     │  ├─ span [tagStyle, color:tone] → speakerShort(e.speaker)
   │  │  │     │  ├─ span [timeStyle] → fmtClock(e.at, time24)     "11:41:07 pm"
   │  │  │     │  └─ span.ml-auto.text-\[0\.6rem\] [style color:var(--dim), opacity:active?1:0] → "copied"
   │  │  │     └─ p.mt-1 [fonts.caption .84rem/1.55, color:var(--text)]
   │  │  │        └─ Highlight → alternates <mark> (query hit) and <span> (plain) nodes   [:22-41]
   │  │  ├─ LiveRow (only while `partial`) — div.relative      [:312-338]
   │  │  │     [style background:color-mix(in srgb,var(--accent) 9%,transparent),
   │  │  │            borderLeft:`2px solid ${speakerColor(partial.speaker)}`,
   │  │  │            padding:"12px 20px 14px"]
   │  │  │  ├─ div.flex.items-center.gap-2
   │  │  │  │  ├─ span.h-1\.5.w-1\.5.rounded-full.breathe [style background:var(--live)]
   │  │  │  │  ├─ span [tagStyle, color:speakerColor] → speakerShort(partial.speaker)
   │  │  │  │  └─ span.ml-auto [tagStyle, var(--dim), .18em] → "in progress"
   │  │  │  └─ p.mt-1 [fonts.caption .85rem/1.55 italic, color:var(--text)]
   │  │  │     ├─ TEXT NODE: partial.words.slice(0, partial.revealed).join(" ")
   │  │  │     │     ⚠ ONLY the confirmed words — no spans, no per-word hooks, provisional tail absent
   │  │  │     └─ span.caret.ml-0\.5.inline-block
   │  │  │           [style width:1.5, height:"0.85em", background:var(--accent), verticalAlign:baseline]
   │  │  └─ div.h-2
   │  └─ Footer div.shrink-0.px-5.py-3\.5 [style borderTop:"1px solid var(--line)"]    [:340-381]
   │     ├─ div.flex.items-center.justify-between.gap-2
   │     │  ├─ button → "Export .txt"        (color var(--text))
   │     │  ├─ button → "Follow on" | "Follow off"   (color var(--accent) | var(--dim))
   │     │  └─ button → "Clear"              (color var(--dim))
   │     └─ div.mt-2.flex.items-center.justify-between [fonts.ui .6rem, var(--dim)]
   │        ├─ span → sessionLabel ("Tonight · 11:41 pm")
   │        └─ span → "{entries.length} lines · {wpm} wpm"
   │
   ├─ {!panelOpen && !immersive} button.absolute.bottom-6.right-6.z-30.rounded-full.px-3\.5.py-2
   │     .transition-all.duration-500 → "history · H"                          [App.tsx:204-225]
   ├─ {immersive} button.absolute.top-6.right-6.z-30.rounded-full.px-4.py-2
   │     .transition-opacity.duration-500 → "leave immersive · I"              [App.tsx:229-246]
   └─ {gallery} DesignGallery → div.fade-in.absolute.inset-0.z-50.flex.items-center.justify-center
        .p-3.sm\:p-6                                                          [DesignGallery.tsx:14-181]
```

**Provenance summary.** `LiveCaptions.tsx` owns the caption plate and everything inside it (status dot,
per-word spans, caret, level meter `LevelBars`, Meta). `TopChrome.tsx` owns the three chrome variants
including the `Listening`/`Paused` pill, its own 6-bar `Level` meter, and the `‹ n ›` switcher.
`HistoryPanel.tsx` owns the `<aside>`, header, search, speaker chips, session group headers, rows and
the live/in-progress row. `Stage.tsx` owns the wallpaper stack, overlays, vignette, particles, grain,
scene slate and corner marks. `App.tsx` owns only the wrapper div (CSS vars), the caption wrapper's
geometry, and the two floating buttons.

---

## 4. Per-design vs shared JSX — **structurally DIFFERENT, not just recoloured**

This is the decisive answer and it contradicts the app's own marketing copy. `DesignGallery.tsx:54`
claims *"Same transcript engine underneath — only the light in the room changes"*, but the engine is
the only shared part: **four independent switch statements change the element tree, the class list and
the style objects.**

### 4.1 `LiveCaptions.tsx` — SIX mutually exclusive return blocks, keyed on `theme.caption.style`

| `caption.style` | branch | shape |
|---|---|---|
| `"bare"` | `LiveCaptions.tsx:152` | `div.flex.flex-col.gap-3.5` > [StatusBadge row] + [text w/ inline speaker span] + [Meta row]. **No plate, no border, no background.** |
| `"glass"` | `:190` | one plate div (bg `--cap-bg`, border, radius, backdrop-blur) > header row (speaker dot + LevelBars) + text + footer row (Meta + "live track"/"hold") |
| `"plate"` | `:240` | plate div > `div.flex.items-start.gap-4` > [vertical rail: dot + 1px line] + [text column with speaker+state line] |
| `"chip"` | `:288` | plate div > header row with a **rounded speaker chip** (`color-mix` pill) + state + `ml-auto` LevelBars, then the text |
| `"stack"` | `:342` | plate div with `borderLeft: 2px solid tone` > header (StatusBadge `plain` + "rolling") + **a second, previous-line div** (`showPrev`, `:344`, `:371-383`) + current text |
| `"karaoke"` | `:397` (the fallthrough `return`) | plate > header (speaker + divider + LevelBars + "read-along") + text where WordRun **is** given `bright`/`dim` (`:436-437`) + Meta |

Plus three intra-branch conditionals that change the tree per *state* (not per design):
`speaker && <span>` (`:161`), `words.length === 0 ? <placeholder span> : <WordRun>` (×6),
`isLive && <Caret>` (×6), `running && <LevelBars>` (`:74` inside StatusBadge), `showPrev && <div>`
(`:371`).

Verbatim, the karaoke-only distinction (`LiveCaptions.tsx:433-439`):

```tsx
          <WordRun
            words={words}
            revealed={revealed}
            bright={{ color: capText, filter: "blur(0px)", transition: "color .3s ease, filter .3s ease" }}
            dim={{ color: "color-mix(in srgb, var(--cap-text) 30%, transparent)", filter: "blur(1.1px)", transition: "color .3s ease, filter .3s ease" }}
          />
```

### 4.2 `HistoryPanel.tsx` — FIVE row shapes, keyed on `theme.panel.style`, plus container/header/input/LiveRow branches

- `Row` is a **local component with 5 returns**: `"sheet"` `:188`, `"rail"` `:211`, `"list"` `:233`,
  `"memo"` `:262`, cards (fallthrough) `:285`. They differ in grid vs flex, in whether an avatar
  circle / timeline rail / card border-left exists, and `memo` switches to monospace + a `%` confidence
  readout and forces `fmtClock(e.at, true)` (24h) regardless of `theme.time24` (`:270`).
- The `<aside>` class and style branch: `panel.style === "rail" || "cards"` → `"right-3 top-3 bottom-3"`
  + `borderRadius` (`:386`, `:86-87`); otherwise `"right-0 top-0 bottom-0"` + `borderLeft` only (`:88`).
- Header title: `panel.style === "memo" ? "session log" : "The room, so far"`, monospace + uppercase
  (`:114-122`).
- Search input: `list|cards` → pill, `--surface-2`, 1px border; others → underline only (`:145-149`).
- Speaker chips' radius: `memo → 3` else `999` (`:171`).
- `LiveRow`: `cards` → `--surface-2` + radius + margins; else `color-mix(accent 9%)` + `padding "12px 20px 14px"`;
  `rail` → **no** `borderLeft` (`:316-320`).
- `timeStyle`: `memo` → monospace else `fonts.ui` (`:92`).

### 4.3 `TopChrome.tsx` — THREE entirely different layouts, keyed on `theme.chrome`

`"bar"` `:185` (a `<header>` at `top-0 left-0 h-[62px]`, `right: rightInset`, gradient scrim);
`"float"` `:238` (a fragment: brand pill top-left + control pill top-centre + stats line at `top-[74px]`);
`"sidebarHead"` `:303` (a `div.absolute.bottom-6.left-6` stack with **no top bar at all** — the panel
heading replaces it). Element sets differ; e.g. the level meter + elapsed appear in all three but in a
different parent with a different `hidden`/`xl`/`sm` gate, and the `NN/20` counter exists only in the
`bar` branch (`:222-224`).

The only cross-cutting chrome decision outside TopChrome: `App.tsx:123`
`const topInset = chromeHidden ? 0 : theme.chrome === "sidebarHead" ? 0 : 64;` — feeds the Stage slate
only.

### 4.4 `Stage.tsx` — SIX per-design structural choices

- `theme.particle` picks count and branch: `rain` → 46 `span.rain-streak` (`:34-47`); `snow` → 60,
  `dust`/`ember` → 26 `span.drift-mote` (`:48-61`); `"none"` → the whole particle container is **not
  rendered** (`:97`). `particleClass` `:66`.
- `theme.overlays` is a per-design **array** → 0..n children (`:84-86`).
- `theme.wall.src` drives the `<div>` background-image; the layer list is a **stateful array** that
  grows to 2 entries during a design change and is `.slice(-2)` (`:16-25`).
- `motes` is a `useMemo` array of per-particle style objects, deterministically seeded by
  `Math.sin(seed*12.9898)*43758.5453` (`:10-13`) — so particle positions are **reproducible per design**
  (not random), which is good news for freezing.

### 4.5 What is genuinely shared

One JSX shell in `App.tsx:128-253`; the caption wrapper geometry; `DesignGallery` (all 20 cards from one
map, `DesignGallery.tsx:81`); `speakerColor` (`App.tsx:26-34`); `Highlight`, `Meta`, `Caret`,
`LevelBars`/`Level`, `StatusBadge`.

**Consequence for the freeze step:** a generic "swap the CSS variables" freeze **cannot** work. The
freezer must capture **20 distinct element trees** (or capture once per distinct pair of
`(caption.style, panel.style, chrome, particle)` — 6×5×3×5 = 450 combinations exist in principle, but
only **20 concrete tuples** occur, and each of the 20 is distinct: every design differs from every other
in at least one axis, and 18 of 20 differ in more than one). If instead the skins are hand-written,
they must be generated per design, not per variable set.

---

## 5. CSS variables a design sets

**Exactly 15 custom properties, all in `theme.vars`, applied as an inline style on ONE element — the
App root div** (`src/App.tsx:129`):

```tsx
  return (
    <div className="relative h-full w-full overflow-hidden" style={theme.vars as CSSProperties}>
```

`theme.vars` is `Record<string, string>` (`src/themes.ts:48`). Verified complete: `grep '^\s*"--'` over
`src/themes.ts` returns **300** matches = 20 designs × 15 keys, and every design carries the identical
15 key set (no design adds or omits one).

| variable | meaning / where consumed | rainline value (specimen) |
|---|---|---|
| `--page` | page/stage backdrop — `Stage.tsx:69` (`background:"var(--page)"`), `TopChrome.tsx:191` (header scrim), `DesignGallery.tsx:18` | `#060c11` |
| `--text` | primary text/icon colour — ~30 sites | `#eaf3f7` |
| `--dim` | secondary text — `HistoryPanel` `:95,:107,:129,:168,:222,:326,:358,:366,:373,:393,:407,:411`; `TopChrome` `:201,:209,:210,:254,:274`; `LiveCaptions:47,:70` | `#93a9b4` |
| `--accent` | brand dot, active buttons, caret, follow toggle — `TopChrome:108,:109,:117,:119`; `HistoryPanel:316,:335,:358`; `Stage:119,:147`; `App:215-241` | `#9fc9dd` |
| `--accent-2` | 3rd speaker tone — `App.tsx:30` palette | `#d9b486` |
| `--live` | the "live/listening" green — `LiveCaptions:47,:257,:324`; `TopChrome:137-139,:209,:273`; `HistoryPanel:105,:324` | `#8fd0c9` |
| `--surface` | panel/plate backgrounds — `HistoryPanel:87,:88,:402`; `TopChrome:245,:264,:308`; `App:216,:237` | `rgba(10,20,27,.74)` |
| `--surface-2` | raised/hover fills — `HistoryPanel:149,:194,:238,:290,:316`; `TopChrome:108,:137,:155`; `DesignGallery:70,:91` | `rgba(255,255,255,.055)` |
| `--line` | 1px hairlines — ~20 sites | `rgba(200,226,238,.14)` |
| `--radius` | plate/panel corner — `LiveCaptions:198,:248,:296,:352,:404`; `HistoryPanel:87,:293,:318` | `16px` |
| `--blur` | the *radius value inside* `blur()` — `LiveCaptions:60,:199,:297,:353,:405`; `HistoryPanel:87,:88`; `TopChrome:246,:265,:309`; `App:218,:239` | `22px` |
| `--shadow` | panel/toolbar drop shadow — `HistoryPanel:87,:88`; `TopChrome:249,:268,:312` | `0 24px 70px -30px rgba(0,0,0,.85)` |
| `--cap-bg` | caption plate fill — `LiveCaptions:58,:196,:246,:294,:350,:402` | `rgba(8,18,24,.62)` |
| `--cap-text` | caption text — `LiveCaptions:144` → `color: "var(--cap-text)"` on each variant's text div | `#f2f8fb` |
| `--cap-edge` | caption plate border — `LiveCaptions:59,:197,:247,:295,:403` | `rgba(220,240,250,.16)` |

**Not design variables** (do not look for them in `vars`): `--font-sans` is a Tailwind v4 `@theme`
token (`src/index.css:3-5`, `--font-sans: "Inter", …`); Tailwind's own `--tw-*` internals are injected
by utilities; `index.css` references `var(--accent, …)`, `var(--dim, …)`, `var(--line, …)` **with
fallbacks** (`:30`, `:37`, `:47`, `:53`, `:133`, `:142`) because those rules can match nodes outside the
App root div.

**Where the variables are consumed outside App.descendants.** `src/index.css`'s own rules
(`::selection`, `.quiet-scroll`, `.hairline`, `.shimmer-text`) read `--accent`/`--dim`/`--line`.
Since they are *not inherited into* and *not applied on* those nodes' ancestors in the frozen shadow
tree unless the values are also set on the shadow host/`:host`, `::selection` and scrollbar colours
would fall back to the hard-coded fallbacks (`#9fc4d4`, `#8fa0aa`, `#fff`).

Fonts are **not** CSS variables: they are passed as whole `fontFamily` strings from
`theme.fonts.*` into inline styles (`LiveCaptions:131`, `TopChrome:103`, `HistoryPanel:92`, …).

---

## 6. Data shape and cadence (`src/hooks/useTranscription.ts`)

Types (`:4-21`), verbatim:

```ts
export interface Entry {
  id: string;
  speaker: string;
  text: string;
  session: string;
  at: number;            // epoch ms
  confidence: number;    // 0..1
  duration: number;      // seconds
  marker: number;        // word count of that line
}

export interface Partial {
  speaker: string;
  words: string[];       // the WHOLE line, all words, from the first tick of the line
  revealed: number;      // how many of `words` are "confirmed" (1-based count)
  lineKey: number;       // monotonic id of the current line
  live: boolean;         // always true when constructed
}
```

Exposed state (`:52-59`, `:201`, returned at `:201`):

```ts
  return { entries, partial, running, speed, level, elapsed, sessionLabel, stats, scriptMeta, autoScroll, actions };
```

- `entries: Entry[]` — `useState(() => seededHistory())`, i.e. **12 seed entries at mount**
  (`:53`, seeds from `src/lib/scripts.ts:159-172`).
- `partial: Partial | null` — `:54`.
- `running: boolean` — `:55`, initial **true**.
- `speed: number` — `:56`, initial 1; `SPEEDS = [0.75, 1, 1.5, 2]` (`App.tsx:10`).
- `level: number` — `:57`, initial 0.18.
- `elapsed: number` (seconds) — `:58`.
- `autoScroll: boolean` — `:59`, initial true.
- `sessionLabel` — `:61` `Tonight · ${h}:${mm} ${AM|PM}`, computed once (`useMemo`, `[]`).
- `stats` — `:175-191`: `{ entries, words, wpm, speakers: string[], avgConf, minutes, seconds }`.
- `scriptMeta: Script` — `:75`, `SCRIPTS[0]` at mount, advanced with `scriptIdx` (`:116`).
- `actions` — `:193-199`: `{ toggle, setSpeed, clearHistory, restoreSeed, setAutoScroll }`
  (`restoreSeed` is never wired to the UI).

**Timers / cadence** (all `window.setInterval`):

| what | period | line | notes |
|---|---|---|---|
| caption engine tick | **55 ms** | `:95`, `:151` | the gate is `if (now < e.nextAt) return;` — the real cadence is `nextAt` |
| inter-word delay | `rand(115,205) + punct + long` ms, ÷ `speed` | `:124` | `punct = 190` if the word ends `,;:!?`, `260` if `.`, else 0 (`:122`); `long = 55` if the word is >8 chars (`:123`) |
| line-start delay | `rand(200,420) ms ÷ speed` | `:149` | from the "gap" phase into "speaking" |
| inter-line gap | `rand(620,1750) ms ÷ speed` | `:119` | after a line commits |
| first line | `performance.now() + 900` | `:68` | ⇒ ~0.9 s of deterministic idle state after mount |
| level meter | **90 ms** | `:158` | EMA toward `rand(0.4,0.94)` while speaking else `rand(0.03,0.16)`; ease .42/.22; clamped `[0.02,1]` |
| session clock | **1000 ms** | `:169` | `elapsed++` only while running |

**Fake script text and bounds.** `SCRIPTS` (`src/lib/scripts.ts:29-138`) holds **6 scripts**:
`late-radio` "Late Shift Radio" (12 lines), `film-club` "Film Club, Reel Two" (12), `support`
"Reservation Desk, Evening" (12), `lecture` "Evening Lecture: Tides" (11), `poetry`
"Reading Room: Open Mic" (10), `studio` "Field Notes, Studio B" (9) — 66 lines total, speakers:
June, Marlow, Sofia (caller), Toma, Cleo, Alun, Dr. Vasquez, Pia, Host, Reader, Ines.

**It LOOPs forever and is NOT length-bounded** — `:113-117`:

```ts
          if (e.lineIdx >= script.lines.length) {
            e.lineIdx = 0;
            e.scriptIdx = (e.scriptIdx + 1) % SCRIPTS.length;
            setScriptMeta(SCRIPTS[e.scriptIdx]);
          }
```

Every gap has a **14 % chance** of injecting a random line from `INTERJECTIONS` (6 short lines,
`scripts.ts:140-147`, e.g. `Mm.`, `Yeah, exactly.`) instead of the script's next line (`:138-141`).
`sessionLabel` and the 12 seed entries are the only content tied to wall-clock time.

**Freeze implication.** Nothing about the caption text is deterministic except the first ~900 ms
(§2D) and the 12 seed rows. To freeze a *specific* visible caption (e.g. 4 of 9 words revealed),
either (a) stub `Math.random` and the timers via `addInitScript` and drive a fixed number of ticks, or
(b) capture at the deterministic pre-first-tick instant (last seed line, `note = "last line"`, no
`LiveRow`, `elapsed = 0:00`, level ≈ 0.18 decayed). Anything else is a race.

---

## 7. Fonts, images, and every external URL

**Fonts: one Google Fonts stylesheet `<link>`, `index.html:11-16`** (plus two `preconnect`s):

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500;600&family=Jost:wght@300;400;500&family=Lora:ital,wght@0,400;0,500;1,400&family=Manrope:wght@300;400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,300..500;1,6..72,300..400&display=swap"
      rel="stylesheet"
    />
```

Families actually referenced by themes: **Cormorant Garamond, Fraunces, Instrument Serif, Inter, Jost,
Lora, Manrope, Newsreader** (8) — every one is present in that URL. `histoPanel` also hard-codes
`"ui-monospace, SFMono-Regular, Menlo, monospace"` for `memo` rows (`HistoryPanel.tsx:92`, `:114`,
`:267`) — a system font, no download. Tailwind's `--font-sans: "Inter"` (`index.css:4`) and the `body`
stack (`index.css:23`) are the fallbacks.

**No `public/` directory exists** and there are **no local asset imports** anywhere in `src/` —
every image is remote.

**Images: 20 Pexels photos, each fetched at TWO sizes** (`themes.ts:51-57`):

```ts
const px = (id: string, ext = "jpeg"): Wallpaper => {
  const base = `https://images.pexels.com/photos/${id}/pexels-photo-${id}.${ext}?auto=compress&cs=tinysrgb`;
  return {
    src: `${base}&fit=crop&h=900&w=1600`,
    thumb: `${base}&fit=crop&h=300&w=520`,
  };
};
```

`src` is the Stage background; `thumb` is used only by the gallery cards
(`DesignGallery.tsx:99`) — **a frozen single-design skin needs `src` only**. IDs in source order:
`9488153`(jpeg), `8887627`, `35258949`, `18405036`, `31272472`, `35542566`, `34686220`,
`38663879`(**png** — only non-jpeg), `20494415`, `34569888`, `13278838`, `30252333`, `18502603`,
`7022830`, `16966474`, `33454123`, `15183904`, `38026077`, `14955235`, `10636454`.

**Full runtime external-URL list** (nothing else is fetched):

1. `https://fonts.googleapis.com/css2?family=…` (stylesheet)
2. `https://fonts.gstatic.com/…` (the woff2 files that stylesheet pulls)
3. `https://images.pexels.com/photos/<id>/pexels-photo-<id>.{jpeg|png}?auto=compress&cs=tinysrgb&fit=crop&h=900&w=1600` — 1 per design for the live view
4. `https://images.pexels.com/photos/<id>/pexels-photo-<id>.{jpeg|png}?auto=compress&cs=tinysrgb&fit=crop&h=300&w=520` — 20, gallery only

Inline, no network: the film-grain SVG is a `data:image/svg+xml` URI with an `feTurbulence` filter
(`index.css:67`); all iconography is inline `<svg>` in `TopChrome.tsx:27-57`; every gradient is CSS.
The 2 `preconnect` hints are not fetches.

---

## 8. `position: fixed`, viewport assumptions, breakpoints

**There is no `position: fixed` anywhere in `src/`** (grep for `fixed` → zero property matches; the
only hits are `overflow-hidden`). Every layer is `position: absolute` inside the App root
`div.relative` (`App.tsx:129`) — so the whole layout is self-contained against that one ancestor.

**Viewport-dependent expressions that DO escape the root box:**

| site | code | effect |
|---|---|---|
| `HistoryPanel.tsx:388` | `style={{ width: panel.width, maxWidth: "calc(100vw - 48px)", … }}` | panel clamps to `viewport − 48px`. At a **380 px viewport → 332 px**, so **all 20 designs' panels (356–392 px) are clamped**; at a wide host page the clamp disappears |
| `App.tsx:168` | `marginLeft: align === "center" ? "auto" : "4vw"` | left-aligned captions (`glasshouse`, `dusk-highway`) indent `4vw` → 15.2 px at 380 |
| `DesignGallery.tsx:45` | `fontSize: "clamp(1.4rem, 2.4vw, 2rem)"` | gallery heading only |
| `Stage.tsx:39` | rain streak `height: \`${h}vh\`` (8–26 vh) | particle geometry is viewport-height relative |
| `index.css:90` | `translate3d(14px, -90vh, 0)` in `@keyframes driftUp` | motes rise 90 vh; taller host ⇒ longer travel |
| `LiveCaptions.tsx:132` | `fontSize: \`clamp(1.02rem, ${caption.size}, 2.3rem)\`` | **container-independent** — no vw; the middle value (1.42–1.95 rem) always wins |

**Tailwind breakpoints** (v4 defaults, min-width media queries, evaluated against the **window**
viewport, never the host element): `sm 640`, `lg 1024`, `xl 1280`, `2xl 1536`. At a 380×900 viewport
**only the base (mobile) branch of every responsive utility applies**, which hides a large part of the
chrome:

- `TopChrome` `bar`: `hidden … lg:flex` (`:197`, script title + session label) → **gone**;
  `hidden xl:flex` (`:208`, level meter + elapsed + conf.) → **gone**; `hidden 2xl:inline` (`:211`) →
  **gone**; `hidden sm:inline` (`:222`, `NN/20`) → **gone**; `hidden xl:inline` (`:171`, theme name) →
  **gone (only "03 ·" shows)**.
- `TopChrome` `float`: the whole brand pill is `hidden xl:block` (`:241`) → **gone**;
  `hidden … sm:flex` (`:272`, meter + elapsed) → **gone**; `hidden … sm:block` (`:293`, stats line) →
  **gone**.
- `TopChrome` `sidebarHead`: `hidden sm:inline` (`:327`, the word "Designs") → **gone**.
- `App.tsx:164` `px-5 sm:px-10` → 20 px padding.
- `LiveCaptions`: `px-6 py-4 sm:px-8 sm:py-5` etc. → the `sm:` half never applies.
- `TopChrome` `bar`/`Stage` `px-5 sm:px-8` / `left-6 sm:left-9` → base values.

**The single most important 380 px consequence — the caption column collapses.**
`App.tsx:124`:

```tsx
  const captionRight = panelVisible ? theme.panel.width + 34 : 0;
```

With `panelOpen = true` (default) this is e.g. **402 px for `cellar`** (`368 + 34`), applied at
`App.tsx:161` as `style={{ left: 0, right: captionRight, bottom: … }}` on an absolutely positioned div.
Against a **380 px** containing block: `width = 380 − 0 − 402 = −22 → used width 0` (CSS 2.1 §10.3.7,
clamped at used-value time). The inner `div.px-5` then resolves `width:100%` against 0 and `maxWidth`
against 0, and the WordRun spans are `display:inline-block; white-space:pre`, so the caption wraps one
word per line inside a ~40 px box and overflows the collapsed box. **The arithmetic is from the source;
the pixel consequence should be confirmed by one 380 px render.** Note that the `maxWidth` clamp on the
panel (`calc(100vw − 48px)`) is *not* mirrored in `captionRight`, so the two are computed from different
widths — that mismatch is the bug. Two ways to get a usable 380 px skin:
(i) render with the panel hidden (`panelVisible === false` ⇒ `captionRight = 0`, caption spans the full
width) and freeze the panel separately; or (ii) render at a wide viewport and scale/crop. Both lose
something; the decision belongs to the freeze step.

Also at 380×900 the Stage scene slate sits at `top: topInset + 18` = **82 px** for `bar`/`float`
chrome, and the frame corner marks are `h-5 w-5` at 16 px insets — both survive, but the left slate and
top-centre control pill overlap horizontally at 380 px (the pill is centred, the slate at `left-6`/24 px).

---

## 9. What breaks if the same markup is rendered in a Shadow DOM in a foreign page

Ordered by how likely it is to visibly corrupt the skin. "Outer stylesheet" = the built single-file
bundle (`vite-plugin-singlefile` inlines all CSS into a `<style>` in `<head>` — `vite.config.ts:13`).

**9.1 Global CSS that will not cross the shadow boundary unless the stylesheet is re-inserted inside
the shadow root.** All of `index.css` is document-scoped; an outer `*`, `body`, `html`, `#root`,
`button`, `::selection`, `::-webkit-scrollbar` and `@keyframes` rule does **not** apply to elements
inside a shadow tree (an outer universal selector does not match shadow-inner elements; an outer
`::selection` is a different pseudo-element scope). So **every one of these must be duplicated inside
the shadow root** (or the whole built stylesheet must be adopted into it, which is the clean move — note
that Tailwind's own preflight and all utility classes are in that same sheet, so *nothing* renders
correctly without it):

| # | reliance | code | consequence if lost |
|---|---|---|---|
| a | height chain | `index.css:13-17` `html, body, #root { height: 100% }` | the App root is `h-full` (`App.tsx:129`) = `height:100%` of a parent with no definite height → **collapses to 0 height, nothing paints**. Must set `:host{display:block;height:<px>}` or an explicit height on the wrapper. This is the #1 breakage. |
| b | body defaults | `index.css:19-27` `margin:0; background:#0a0d10; color:#e8eef2; font-family:"Inter"…; -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; overflow:hidden` | `margin:8px` on the host side, wrong inherited text colour/rendering for any node without an explicit colour, and the document-level scroll **suppression** is gone. (The App root's own `overflow-hidden` at `App.tsx:129` does survive, so clipping inside is fine.) |
| c | box-sizing reset | `index.css:7-11` `*, *::before, *::after { box-sizing: border-box }` | **geometry shifts everywhere**: `width:100%` + `px-5` (caption wrapper), `px-5 py-4` plates, `h-full w-full`, `maxWidth:calc(100vw-48px)` all change. Must be duplicated. |
| d | `::selection` | `index.css:29-32` `background: var(--accent,…); color:#0a0d10` | text selection loses the themed colour. Low severity, but it **also silently reads `--accent` from a fallback** because the var is set on the App root inside the shadow tree, not on `:host`. |
| e | scrollbar skin | `index.css:34-55` `.quiet-scroll{scrollbar-width:thin;scrollbar-color:…}` + 4 `::-webkit-scrollbar*` rules | the history scroller and the gallery scroller (`HistoryPanel.tsx:391`, `DesignGallery.tsx:25,:79`) fall back to the **Chromium default 15 px scrollbar**, which steals ~15 px of the panel's inner width and changes the text wrapping of every row. `scrollbar-color` IS inherited so it may partially survive via the host; `scrollbar-width` is **not** inherited and `::-webkit-scrollbar` is not inherited at all. Deliberate reproduction recommended (or force overlay scrollbars). |
| f | button reset | `index.css:135` `button { font: inherit; color: inherit }` | buttons inherit the host page's font/colour on any button that does not set `fontFamily` explicitly — most do set it, but `HistoryPanel`'s "HIDE" (`:125-131`) and the footer buttons (`:343,:350,:363`) rely on both the class and inherit. |
| g | `@theme` token | `index.css:3-5` `--font-sans: "Inter"` | Tailwind's `font-sans` default changes; this app mostly sets `fontFamily` inline, so low severity. |
| h | keyframe animations | `index.css:58-69` `grainShift`+`.grain-layer`; `:72-83` `rainFall`+`.rain-streak`; `:86-96` `driftUp`+`.drift-mote`; `:99-105` `wordIn`+`.word-in`; `:107-111` `softIn`+`.soft-in`; `:113-114` `fadeIn`+`.fade-in`; `:117-121` `breathe`+`.breathe`; `:123-127` `caretBlink`+`.caret`; `:137-147` `shimmer`+`.shimmer-text` | if the class names are present but their `@keyframes` are not resolvable in that tree, **every animated element is frozen at its initial/`both`-fill state**: `.soft-in` would stay `opacity:0; transform:translateY(10px)` (the whole caption plate **invisible**), `.fade-in` (the gallery) invisible, `.caret` visible-but-not-blinking, `.grain-layer` static, rain/motes static. **Whether an outer `@keyframes` is visible inside a shadow tree is a browser tree-scoping question that the source cannot answer → NOT DETERMINED from source. Determined by: build + render in Chromium with the stylesheet ONLY in the outer document and check `getComputedStyle(plate).opacity` after 1 s. Treat as NOT AVAILABLE and declare the keyframes inside the shadow stylesheet** — that is unconditionally safe. |
| i | `@property` / `@layer` from Tailwind v4 | generated CSS, not in the tree | Tailwind v4 registers `--tw-*` via `@property` and puts its rules in `@layer`. If `@property` registrations are ignored inside a shadow root (browser-dependent — NOT DETERMINED from source; determine by `CSS.registerProperty`-style probing or by checking a `transition-*` utility's computed `transition-duration`), some utilities fall back to un-registered-custom-property behaviour (e.g. `transition-property` shorthand defaults). Low visual risk, but the built sheet should be inspected. |
| j | dead `.noise` | — | **the question's `.noise` does not exist.** The nearest thing is `.grain-layer` (`index.css:66-69`) with an inline `data:image/svg+xml` `feTurbulence` background, animated by `grainShift`. No `.noise` class anywhere in the tree. |

**9.2 Viewport-unit and media-query leakage.** Tailwind's `sm:`/`lg:`/`xl:`/`2xl:` utilities and every
`vw`/`vh` value resolve against the **top-level viewport**, not the 380 px host box. If the frozen
markup is put inline into a 1440 px-wide foreign page, the breakpoints flip on and the app suddenly
renders the *desktop* chrome (`xl:flex` meter, `lg:flex` title block, `xl:inline` theme name) that the
380 px capture deliberately hides — i.e. **the skin would not match its own reference screenshot**.
`100vw` at `HistoryPanel.tsx:388` likewise stops clamping (panel becomes 368 px instead of 332).
Fixes: keep the skin in an `<iframe>` of exactly 380×900, or replace viewport units/breakpoints with
container-relative values in the frozen copy. Same for `vh` at `Stage.tsx:39` and `index.css:90`.

**9.3 `backdrop-filter` and `mix-blend-mode` sample the FOREIGN page's backdrop.** The backdrop root is
not reset by a shadow boundary. The app is *internally* opaque — the `Stage` div paints
`background: var(--page)` (a solid hex, `Stage.tsx:69`) over `inset-0` and then the photo — so the
translucent plates (`--surface: rgba(…,.74)`, `--cap-bg: rgba(…,.62)`) and every
`backdropFilter: blur(var(--blur))` (`LiveCaptions.tsx:60,:199,:297,:353,:405`;
`HistoryPanel.tsx:87,:88`; `TopChrome.tsx:246,:265,:309`; `App.tsx:218,:239`) blur the app's own
wallpaper **as long as the Stage is present and opaque**. Two live risks: (i) `mix-blend-overlay` on
`.grain-layer` (`Stage.tsx:107`) blends with *everything* painted behind it, and the App root creates
**no stacking context** (`position: relative` with `z-index: auto`), so in a foreign page the grain can
blend with the host page's content; (ii) if the frozen skin renders **only a panel/caption fragment**
without the Stage, `backdrop-filter` will sample the foreign page. Mitigation: `isolation: isolate` (or
`filter`/`opacity`) on the frozen wrapper and always include an opaque Stage or set an opaque
background on `:host`.

**9.4 `position: absolute` containment is safe.** The App root is `relative` and every layer is
`absolute` inside it, so nothing depends on `body`/`documentElement` for positioning. No
`position: fixed` exists (§8). Positive finding — the freeze does **not** need `position: static`
resets.

**9.5 Custom properties are shadow-safe.** `theme.vars` is set as an inline style on the App root
(`App.tsx:129`), so the 15 design variables cascade to every descendant *inside the shadow tree* with
no `:root` dependency. Only the outer `index.css` rules (`::selection`, `.quiet-scroll`, `.hairline`,
`.shimmer-text`, all with hard-coded fallbacks) read them from a scope the inline style does not reach
— set the same 15 properties on `:host` if those rules are duplicated inside the shadow root.

**9.6 Fonts are shadow-safe but must be loaded by the host.** `@font-face` matching is
document-global, so text inside a shadow root uses the Google Fonts families once the outer document
has the `<link>`; the frozen page must carry that link (or self-host the woff2). If the link is absent,
the inline `fontFamily: '"Manrope", sans-serif'` silently degrades to a fallback — every design's
typography is wrong, and because each design names a *different* family the error is not uniform.

**9.7 Rem/root font size.** All type sizes are `rem`/`clamp(...rem...)`; `rem` follows the **document**
root font-size. A foreign page that sets `html{font-size:…}` rescales the whole frozen skin. Pin it with
`:host{font-size:16px}` or convert to px in the frozen copy.

**9.8 React-specific (only if the frozen thing stays a live React app).** `createRoot(document.getElementById("root"))`
(`main.tsx:6`) needs a `#root` **in the same tree as the container**; React 19 attaches its delegated
listeners to the container, which works inside a shadow root, but `getElementById` will not find a
shadow-inner `#root` from the document — it must be `shadowRoot.getElementById(...)`. The keyboard
listener is on `window` (`App.tsx:101`) and `keydown` is composed, so it still receives shadow-inner
key events; `navigator.clipboard` (`HistoryPanel.tsx:80`) and the export `<a download>` blob
(`App.tsx:62-68`) are unaffected by shadow DOM but are blocked in some headless contexts.

**9.9 One more silent-difference risk.** `body`'s `color:#e8eef2` and `font-family` inherit into the
app today; inside a shadow root, inheritance comes from the **host element**, so any descendant without
an explicit colour/family takes the foreign page's. Grep shows the app sets colour on essentially every
text container, so the practical exposure is small — but the *placeholder* text of the search input
(`HistoryPanel.tsx:139`) and the `<mark>` inherits are the two places worth checking in a captured
render.

---

## 10. NOT DETERMINED (and what would determine each)

1. **The exact built CSS** (Tailwind v4 output, preflight selectors, `@property` registrations, whether
   theme vars are emitted under `:root, :host`). No `node_modules/`, no `dist/`, and this analysis
   wrote only this file, so nothing was built. *Would be determined by* `npm ci && npm run build` and
   reading the single inlined `<style>` from `dist/index.html`.
2. **Whether outer-document `@keyframes` are visible inside the shadow tree in the target Chromium**
   (§9.1 h) and **whether `@property` registers from inside a shadow root** (§9.1 i). Browser
   behaviour, not source. *Would be determined by* a 2-minute render test: put the built sheet in the
   outer document only, render the markup in a shadow root, and read `getComputedStyle` of a
   `.soft-in` plate (opacity 1 vs 0 proves keyframe resolution) and of a `transition-*` utility.
3. **The exact pixel result of the collapsed caption column at 380 px** (§8). The `captionRight` formula
   and the containing-block arithmetic are read from source (`App.tsx:124`, `:161`); the rendered
   outcome (0 width, one word per line, overflow) is a computed inference. *Would be determined by* a
   single 380×900 headless render of the default design with the panel open.
4. **Whether the Pexels URLs still resolve** and in what format/size (each theme's `wall.src` is a
   runtime URL, `themes.ts:51-57`). Not a source question. *Would be determined by* fetching one URL
   per design and recording bytes + `Content-Type`; the freeze step should cache them locally.
5. **The DPR/colour profile the reference screenshots assume.** Nothing in the source sets it. The
   target 380×900 CSS-px panel at DPR 1 vs 2 changes only rasterisation, not layout, but the grain
   (`opacity: theme.grain`, 0.03–0.12) and `backdrop-filter` look different. Not specified anywhere.
