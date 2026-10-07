"""A2/A3 + the fake meter, in the theme generator and in panel.css.

Four changes, each anchored so a miss is loud:

  1. the HUD's skin rules go (its element is gone from the markup);
  2. `.panel__controls` sits on the TOP header row in EVERY direction, because
     the owner ruled *"move todos os botoes la pra cima tambem"*;
  3. the FAKE level meter's animation goes. It was a pure CSS keyframe loop that
     animated identically with speech, with silence and with a dead worker
     (`docs/research/12-audio-level-contract.md`) — a wave that lies is worse
     than no wave, which is exactly what the owner forbade;
  4. the dead `.status__hint` / `.chrome__key` rules go with their elements.
"""
import io

GEN = r'_main\_design-lane\gen_themes.py'
CSS = r'app\panel\panel.css'

g = io.open(GEN, encoding='utf-8', newline='').read()
log = []

# THE GENERATOR IS A CRLF FILE (`AGENTS.md` rule 2: name the revision). A
# multi-line anchor written with bare LF matches NOTHING, which is how the first
# run of this script reported six misses and changed almost nothing.
CRLF = '\r\n'


def crlf(text):
    return text.replace('\n', CRLF)


def sub(text, old, new, label, expect=1):
    old, new = crlf(old), crlf(new)
    n = text.count(old)
    if n != expect:
        log.append('MISS %-42s count=%d (want %d)' % (label, n, expect))
        return text
    log.append('ok   %-42s %d site(s)' % (label, n))
    return text.replace(old, new)


# ── 1. the HUD's skin rules ────────────────────────────────────────────────
g = sub(g, """/* \u2500\u2500 the HUD: numbers, in mono, comparable column-wise \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */
{S} .hud{{ border-top-color: var(--line); }}
{S} .hud__row dt{{ color: var(--text-muted); font-size: var(--size-meta); }}
{S} .hud__row dd{{ color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--size-meta); }}
{S} .hud__row--pending dt,
{S} .hud__row--pending dd{{ color: color-mix(in srgb, var(--text-muted) 60%, transparent); }}
""", '', 'skin: .hud rules')

# ── 2. every direction's controls on the TOP row ───────────────────────────
g = sub(g, """/* THE CONTROLS MOVE: a second header row, right-aligned, small and square. */
@S@ .panel__controls{
  grid-column: 2;
  grid-row: 2;
  justify-self: end;
  gap: 4px;
}""", """/* THE CONTROLS ARE ON THE TOP ROW (owner, 2026-10-08: *"move todos os botoes
   la pra cima tambem"*), right-aligned, small and square. */
@S@ body[data-surface="panel"] .panel__controls{
  grid-column: 2;
  grid-row: 1;
  justify-self: end;
  gap: 4px;
}""", 'bcast controls row 1')

g = sub(g, '@S@ .chrome--mano[data-chrome="head"]{\n  grid-column: 1 / -1;',
        '@S@ .chrome--mano[data-chrome="head"]{\n  grid-column: 1;',
        'mano head column')

g = sub(g, '@S@ body[data-surface="panel"] .panel__controls{ grid-column: 2; grid-row: 2; justify-self: end; gap: 4px; }',
        '@S@ body[data-surface="panel"] .panel__controls{ grid-column: 2; grid-row: 1; justify-self: end; gap: 4px; }',
        'mano+inst controls row 1', expect=2)

# ── 3. the fake level meter ────────────────────────────────────────────────
g = sub(g, """@S@ .chrome--bcast .chrome__meter i{ animation: sotto-2-meter 0.9s cubic-bezier(0.2, 0.7, 0.3, 1) infinite; }
@S@ .chrome--bcast .chrome__meter i:nth-child(2){ animation-delay: 0.09s; }
@S@ .chrome--bcast .chrome__meter i:nth-child(3){ animation-delay: 0.18s; }
@S@ .chrome--bcast .chrome__meter i:nth-child(4){ animation-delay: 0.27s; }
@S@ .chrome--bcast .chrome__meter i:nth-child(5){ animation-delay: 0.36s; }
@keyframes sotto-2-meter{
  0%{ transform: scaleY(0.14); }
  30%{ transform: scaleY(1); }
  100%{ transform: scaleY(0.3); }
}
""", """/* ── NO METER ANIMATION. MEASURED, AND DELETED. ────────────────────────────
   A `@keyframes sotto-2-meter` loop stood here and animated the five bars
   identically with speech, with silence and with a DEAD WORKER — a wave that
   lies, which is exactly what the owner forbade. `docs/research/
   12-audio-level-contract.md` is the measurement; the bars now carry the level
   the worker really reports (`.chrome__meter` is driven by `--meter-N` custom
   properties, see `panel.css`), and with no real data they sit at the floor. */
""", 'bcast fake meter')

g = sub(g, """@S@ .chrome--inst .chrome__meter i{ animation: sotto-5-eqA 0.9s ease-in-out infinite; }
@S@ .chrome--inst .chrome__meter i:nth-child(2){ animation: sotto-5-eqB 1.18s ease-in-out infinite; }
@S@ .chrome--inst .chrome__meter i:nth-child(3){ animation: sotto-5-eqC 0.76s ease-in-out infinite; }
@S@ .chrome--inst .chrome__meter i:nth-child(4){ animation: sotto-5-eqB 1.18s ease-in-out infinite; animation-delay: 0.2s; }
@S@ .chrome--inst .chrome__meter i:nth-child(5){ animation: sotto-5-eqA 0.9s ease-in-out infinite; animation-delay: 0.3s; }
""", """/* ── NO EQUALISER ANIMATION. Same measurement, same deletion: three keyframe
   loops (`sotto-5-eqA/B/C`) animated the instrument's bars regardless of what
   the microphone heard. The bars are now painted from the worker's own reported
   level. */
""", 'inst fake meter')

# ── 4. the dead hint rules ────────────────────────────────────────────────
g = sub(g, '@S@ .status__hint{ order: 8; }\n', '', 'tele: dead .status__hint')

io.open(GEN, 'w', encoding='utf-8', newline='').write(g)

c = io.open(CSS, encoding='utf-8', newline='').read()


def csub(old, new, label, expect=1):
    global c
    n = c.count(old)
    if n != expect:
        log.append('MISS %-42s count=%d (want %d)' % (label, n, expect))
        return
    log.append('ok   %-42s %d site(s)' % (label, n))
    c = c.replace(old, new)


csub("""   The HUD is given its own `display` inside each surface rather than relying on
   the UA default (`section` is `block`), because `display: none` in one surface
   must be overridden by the other and `display: block` would fight the flex
   layout inside it. */

/* Both helper surfaces are hidden until a surface claims them. */
.stripbar,
.hud {
  display: none;
}

body[data-surface="strip"] .hud,
body[data-surface="panel"] .stripbar,
body[data-surface="strip"] .panel__header,
body[data-surface="strip"] .history,
body[data-surface="strip"] .status__text,
body[data-surface="strip"] .status__hint {
  display: none;
}

body[data-surface="panel"] .hud {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

body[data-surface="strip"] .stripbar {
  display: flex;
}""", """   The HUD that used to need its own `display` per surface IS GONE (owner,
   2026-10-08), so only the stripbar is left to claim. */

/* The strip's own control row is hidden until the strip surface claims it. */
.stripbar {
  display: none;
}

body[data-surface="panel"] .stripbar,
body[data-surface="strip"] .panel__header,
body[data-surface="strip"] .history,
body[data-surface="strip"] .status__text {
  display: none;
}

body[data-surface="strip"] .stripbar {
  display: flex;
}""", 'panel.css surface blocks')

io.open(CSS, 'w', encoding='utf-8', newline='').write(c)
for line in log:
    print(line)
