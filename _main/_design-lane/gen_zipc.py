#!/usr/bin/env python3
"""GENERATOR for app/panel/themes/zipc-panels.css -- the TEN panel designs of the THIRD zip.

WHY THIS FILE EXISTS (and it is a correction of the record)
-----------------------------------------------------------
zipc-panels.css shipped as a HAND-AUTHORED file: its own header said so
("WHY AUTHORED AND NOT GENERATED"), and 'git log --diff-filter=A' shows ONE
commit (0c25c4f) with no generator behind it -- measured: 'git grep -n zipc --
"*.py"' returns ZERO matches before this file existed. So there was no generator
to re-run, and the AGENTS.md rule 10 proof ("a fresh run reproduces the bytes on
disk") had nothing to be applied to.

This file closes that hole. It has TWO profiles:

  --profile legacy   reproduces the shipped 35 875 B file BYTE FOR BYTE
                     (sha256 9E32F9160C38B855...). That is the proof that the
                     generator is FAITHFUL to what is on disk before it is used
                     to change anything.
  --profile designs  the ten STRUCTURAL designs (the work), each one built from
                     the zip's own component.

Run it with the output REDIRECTED to a scratch path first; only the designs
profile writes the product file, and only when --out names it.

ZIP SOURCE (parsed by hand into DESIGN below, with the file:line that carries
each value):
  src/data/scenes.ts                     the ten scenes: panel palette, radius,
                                         blur, panel font, caption font, size,
                                         weight, variant
  src/components/panels/PanelSetA.tsx    GlassCards Hairline Paper Quotes Ledger
  src/components/panels/PanelSetB.tsx    Feed Bubbles Timeline Chips Gutter
"""
import argparse
import hashlib
import sys

CRLF = "\r\n"

# --------------------------------------------------------------------------
# THE TEN DESIGNS -- the zip's values, one dict each.
#
# 'legacy_comment' is kept VERBATIM so the legacy profile is byte-exact; the
# designs profile writes its own comment from 'zip' and 'structure'.
# --------------------------------------------------------------------------
DESIGNS = [
    dict(
        name="GlassCards", title="Glass Cards",
        legacy_note="wide captions, 22px radius, a dark surface.",
        # scenes.ts:120-129
        surface="rgba(26,18,13,0.52)", line="rgba(255,223,182,0.12)",
        text="#F6E7D4", muted="rgba(246,231,212,0.5)", accent="#E9A85B",
        soft="rgba(255,222,180,0.07)", soft_rgb="255,222,180",
        radius=22, radius_md=13, radius_sm=8,
        panel_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        caption_font='"Newsreader", Georgia, serif',
        size=34, weight=400, tracking="-0.012em",
        body_radius=15, card=True, card_radius=12, card_padding="7px 10px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Hairline", title="Hairline",
        legacy_note="tight captions, 14px radius, a dark surface.",
        # scenes.ts:188-197
        surface="rgba(9,15,21,0.34)", line="rgba(255,255,255,0.09)",
        text="#E4EDF3", muted="rgba(228,237,243,0.46)", accent="#9FC4D8",
        soft="rgba(159,196,216,0.06)", soft_rgb="159,196,216",
        radius=14, radius_md=8, radius_sm=5,
        panel_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        caption_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        size=28, weight=300, tracking="0.002em",
        body_radius=10, card=False, card_radius=0, card_padding="6px 2px",
        latest_weight=400, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Paper", title="Paper",
        legacy_note="italic captions, 10px radius, a DARK surface (light until the owner ruled no white theme, 2026-10-14).",
        # scenes.ts:255-264
        # NO LIGHT SLAB (owner, 2026-10-14: *"e nao e pra ter tema branco"). `scenes.ts`
        # states the design as a LIGHT sheet (`#F6EDE1` with dark ink) and the census
        # measured the painted panel at 0.86 relative luminance -- one of the six themes of
        # 45 that were white. THE SHEET IS INVERTED, NOT THE DESIGN: warm dark linen, warm
        # light ink, the design's own red margin rule kept at a lighter alpha, the ruled
        # 27px page, the 10px radius and the italic Fraunces caption all stay.
        surface="rgba(26,18,13,0.96)", line="rgba(246,231,212,0.12)",
        text="#F6E7D4", muted="rgba(246,231,212,0.52)", accent="#C4562F",
        soft="rgba(196,86,47,0.10)", soft_rgb="246,231,212",
        radius=10, radius_md=6, radius_sm=4,
        panel_font='"DM Mono", ui-monospace, monospace',
        caption_font='"Fraunces", Georgia, serif',
        size=33, weight=400, tracking="0.002em",
        body_radius=7, card=True, card_radius=4, card_padding="8px 12px",
        latest_weight=500, slab_opacity="0.96", light=False,   # NO LIGHT SLAB (owner, 2026-10-14): the sheet is dark now
    ),
    dict(
        name="Quotes", title="Quotes",
        legacy_note="wide captions, 18px radius, a dark surface.",
        # scenes.ts:323-332
        surface="rgba(32,22,16,0.58)", line="rgba(232,198,155,0.13)",
        text="#F3E7D3", muted="rgba(243,231,211,0.5)", accent="#E8C69B",
        soft="rgba(232,198,155,0.07)", soft_rgb="232,198,155",
        radius=18, radius_md=11, radius_sm=6,
        panel_font='"Lora", Georgia, serif',
        caption_font='"Instrument Serif", Georgia, serif',
        size=36, weight=400, tracking="-0.012em",
        body_radius=13, card=True, card_radius=7, card_padding="8px 12px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Ledger", title="Ledger",
        legacy_note="editorial captions, 6px radius, a dark surface.",
        # scenes.ts:390-399
        surface="rgba(17,21,16,0.6)", line="rgba(216,176,96,0.12)",
        text="#E9E4D2", muted="rgba(233,228,210,0.48)", accent="#D8B060",
        soft="rgba(216,176,96,0.07)", soft_rgb="216,176,96",
        radius=6, radius_md=4, radius_sm=3,
        panel_font='"Space Grotesk", ui-sans-serif, sans-serif',
        caption_font='"Lora", Georgia, serif',
        size=31, weight=400, tracking="0.002em",
        body_radius=6, card=True, card_radius=4, card_padding="8px 12px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Feed", title="Feed",
        legacy_note="mono captions, 12px radius, a dark surface.",
        # scenes.ts:457-466
        surface="rgba(12,12,20,0.72)", line="rgba(255,255,255,0.075)",
        text="#E6E9F2", muted="rgba(230,233,242,0.46)", accent="#8B93F2",
        soft="rgba(139,147,242,0.07)", soft_rgb="139,147,242",
        radius=12, radius_md=7, radius_sm=4,
        panel_font='"JetBrains Mono", ui-monospace, monospace',
        caption_font='"JetBrains Mono", ui-monospace, monospace',
        size=24, weight=400, tracking="0.01em",
        body_radius=8, card=True, card_radius=5, card_padding="8px 12px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Bubbles", title="Bubbles",
        legacy_note="italic captions, 20px radius, a dark surface.",
        # scenes.ts:524-533
        surface="rgba(29,23,42,0.56)", line="rgba(240,222,246,0.12)",
        text="#F2E9F7", muted="rgba(242,233,247,0.48)", accent="#D8A7E8",
        soft="rgba(216,167,232,0.08)", soft_rgb="216,167,232",
        radius=20, radius_md=12, radius_sm=7,
        panel_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        caption_font='"Lora", Georgia, serif',
        size=30, weight=400, tracking="0.002em",
        body_radius=14, card=True, card_radius=11, card_padding="7px 10px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Timeline", title="Timeline",
        legacy_note="wide captions, 16px radius, a dark surface.",
        # scenes.ts:591-600
        surface="rgba(13,19,23,0.5)", line="rgba(190,214,220,0.1)",
        text="#E2EBEF", muted="rgba(226,235,239,0.46)", accent="#BED6DC",
        soft="rgba(190,214,220,0.07)", soft_rgb="190,214,220",
        radius=16, radius_md=10, radius_sm=6,
        panel_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        caption_font='"Newsreader", Georgia, serif',
        size=32, weight=300, tracking="-0.012em",
        body_radius=11, card=False, card_radius=0, card_padding="6px 2px",
        latest_weight=400, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Chips", title="Chips",
        legacy_note="editorial captions, 14px radius, a dark surface.",
        # scenes.ts:658-667
        surface="rgba(24,14,11,0.66)", line="rgba(255,196,150,0.12)",
        text="#F6E4D8", muted="rgba(246,228,216,0.48)", accent="#FFC496",
        soft="rgba(255,196,150,0.08)", soft_rgb="255,196,150",
        radius=14, radius_md=8, radius_sm=5,
        panel_font='"Inter", ui-sans-serif, system-ui, sans-serif',
        caption_font='"Fraunces", Georgia, serif',
        size=32, weight=400, tracking="0.002em",
        body_radius=10, card=True, card_radius=8, card_padding="7px 10px",
        latest_weight=500, slab_opacity="0.88", light=False,
    ),
    dict(
        name="Gutter", title="Gutter",
        legacy_note="tight captions, 16px radius, a DARK surface (light until the owner ruled no white theme, 2026-10-14).",
        # scenes.ts:725-734
        # NO LIGHT SLAB (owner, 2026-10-14: *"e nao e pra ter tema branco"). `scenes.ts`
        # states the design as a LIGHT sheet (`rgba(243,239,230,0.94)` with dark ink) and
        # the census measured the painted panel at 0.76 relative luminance -- one of the six
        # themes of 45 that were white. THE SHEET IS INVERTED, NOT THE DESIGN: a deep slate
        # slab with light ink, the design's own teal accent untouched, the 54px timestamp
        # column and the Newsreader caption kept.
        surface="rgba(20,28,30,0.96)", line="rgba(226,235,239,0.12)",
        text="#E2EBEF", muted="rgba(226,235,239,0.55)", accent="#4A6B74",
        soft="rgba(74,107,116,0.10)", soft_rgb="226,235,239",
        radius=16, radius_md=10, radius_sm=6,
        panel_font='"Newsreader", Georgia, serif',
        caption_font='"Newsreader", Georgia, serif',
        size=27, weight=300, tracking="0.002em",
        body_radius=11, card=False, card_radius=0, card_padding="6px 2px",
        latest_weight=400, slab_opacity="0.96", light=False,   # NO LIGHT SLAB (owner, 2026-10-14): the sheet is dark now
    ),
]

LEGACY_DASHES = {"GlassCards": 50, "Hairline": 52, "Paper": 55, "Quotes": 54, "Ledger": 54,
                 "Feed": 56, "Bubbles": 53, "Timeline": 52, "Chips": 55, "Gutter": 54}


def legacy_comment(d):
    """The 3-line banner the shipped file carries above each design, byte-exact.

    The dash count is per design because the shipped banner pads to a column that
    varies (82, 79, 76, 77, 77, 75, 78, 79, 76, 77 chars) -- it was hand-made, so
    the widths are the record and are reproduced rather than re-derived.
    """
    prefix = "/* \u2500\u2500 %s \u2500\u2500 %s " % (d["name"], d["title"])
    return [prefix + "\u2500" * LEGACY_DASHES[d["name"]], " * " + d["legacy_note"], " */"]


LEGACY_HEADER = [
    "/* zipc-panels.css -- the TEN panel designs of the THIRD zip, translated to this panel.",
    " *",
    " * THE SOURCE: \u0060cinematic-transcription-app-designs (1).zip\u0060, unpacked at",
    " * \u0060docs/design-intake/cinematic-transcription-app-designs (1)/\u0060:",
    " *   src/data/scenes.ts        the ten scenes, each with its own panel palette,",
    " *                             radius, blur, panel font, caption font, caption",
    " *                             size/weight and caption variant",
    " *   src/components/panels/PanelSetA.tsx   GlassCards, Hairline, Paper, Quotes, Ledger",
    " *   src/components/panels/PanelSetB.tsx   Feed, Bubbles, Timeline, Chips, Gutter",
    " *   src/components/CaptionStage.tsx       the caption overlay (owned by",
    " *                                         \u0060caption-float.js\u0060, not by this file)",
    " *",
    " * THE TRANSLATION, and the owner's own rule: *\"eu quero que tudo seja traduzido pro",
    " * tamanho atual, e com os botoes atuais. o resto, tem que ser igual.\"* So each design",
    " * keeps ITS OWN palette, radius, type and caption treatment, and takes Sotto's own",
    " * size, Sotto's own buttons and Sotto's own DOM. Nothing is drawn on top of the",
    " * current panel and nothing is added to the panel's div.",
    " *",
    " * WHY AUTHORED AND NOT GENERATED: \u0060_main/_design-lane/gen_themes.py\u0060 covers the two",
    " * earlier zips (its own header says so). This is a THIRD set with its own names,",
    " * and the gate that matters is the one that already scans every stylesheet in this",
    " * directory -- \u0060_main/scope-leak-oracle.js\u0060, which requires every selector member",
    " * to be rooted at a theme scope. That is why every rule below is scoped, and why",
    " * the ten blocks repeat the shared skeleton instead of sharing one unscoped rule.",
    " *",
    " * ONE DEVIATION, and it is in ALPHA ONLY, the same one \u0060panel-designs.css\u0060 makes:",
    " * the zip renders its panel over its own opaque black stage behind a 2-8px backdrop",
    " * blur, and a WebView2 window cannot blur the desktop behind it. So each surface",
    " * below is the zip's own colour at Sotto's own alpha, composited over the same",
    " * black, and the blur is dropped for the same reason.",
    " */",
]


def legacy_theme_blocks(d):
    """The shipped skeleton: 18 blocks per design, identical in shape for all ten.

    That identity IS defect D1 -- every one of the ten themes declares the same
    18 selectors, and only the palette plus six layout declarations differ. The
    designs profile replaces this function; keeping it here is what makes the
    'a fresh run reproduces the bytes on disk' proof possible.
    """
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    hover_soft = "rgba(%s,0.24)" % d["soft_rgb"]
    out = []
    out.append((s, [
        ("--bg-slab-strong", d["surface"]),
        ("--slab-opacity", d["slab_opacity"]),
        ("--text-primary", d["text"]),
        ("--text-secondary", d["muted"]),
        ("--text-muted", d["muted"]),
        ("--line", d["line"]),
        ("--line-strong", d["line"]),
        ("--accent", d["accent"]),
        ("--accent-soft", d["soft"]),
        ("--theme-swatch", d["accent"]),
        ("--radius", "%dpx" % d["radius"]),
        ("--radius-md", "%dpx" % d["radius_md"]),
        ("--radius-sm", "%dpx" % d["radius_sm"]),
        ("--font", d["panel_font"]),
        ("--font-mono", '"JetBrains Mono", ui-monospace, monospace'),
        ("--size-small", "12px"),
        ("--space-2", "8px"),
        ("--space-3", "12px"),
        ("--time-live", d["accent"]),
        ("--time-past", d["muted"]),
        ("--type-step", "45ms"),
    ]))
    out.append((s + " .panel", [
        ("background",
         "\n    radial-gradient(120%% 80%% at 100%% 0%%, rgba(%s,0.14) 0%%, transparent 60%%),\n"
         "    radial-gradient(100%% 60%% at 0%% 100%%, rgba(%s,0.10) 0%%, transparent 55%%),\n"
         "    linear-gradient(180deg, %s 0%%, %s 100%%)" % (d["soft_rgb"], d["soft_rgb"], d["surface"], d["surface"])),
        ("border-color", d["line"]),
    ]))
    out.append((s + " .panel::before", [
        ("background", "linear-gradient(90deg, %s, %s)" % (d["accent"], d["accent"])),
        ("opacity", "0.9"),
    ]))
    out.append((s + " .captions__body", [
        ("background", d["surface"]),
        ("border-color", d["line"]),
        ("border-radius", "%dpx" % d["body_radius"]),
    ]))
    if d["card"]:
        out.append((s + " .caption", [
            ("background", d["soft"]),
            ("border", "1px solid %s" % d["line"]),
            ("border-radius", "%dpx" % d["card_radius"]),
            ("padding", d["card_padding"]),
        ]))
    else:
        out.append((s + " .caption", [
            ("background", "transparent"),
            ("border", "0"),
            ("border-bottom", "1px solid %s" % d["line"]),
            ("border-radius", "0"),
            ("padding", "6px 2px"),
        ]))
    out.append((s + " .caption__text", [
        ("font-family", d["caption_font"]),
        ("font-size", "%dpx" % d["size"]),
        ("font-weight", str(d["weight"])),
        ("color", d["text"]),
        ("letter-spacing", d["tracking"]),
    ]))
    out.append((s + " .caption--latest .caption__text", [
        ("color", d["text"]),
        ("font-weight", str(d["latest_weight"])),
    ]))
    out.append((s + " .caption__time", [("color", d["muted"])]))
    out.append((s + " .caption__led", [("background", d["accent"])]))
    out.append((s + " .captions__placeholder-title,\n" + s + " .captions__placeholder-body",
                [("color", d["muted"])]))
    out.append((s + " .status__dot", [("background", d["muted"])]))
    out.append((s + " .status--live .status__dot", [("background", d["accent"])]))
    out.append((s + " .status__text", [("color", d["muted"])]))
    out.append((s + " .history__label,\n" + s + " .history__note,\n" + s + " .history__count,\n" + s + " .history__source",
                [("color", d["muted"])]))
    out.append((s + " .history__path", [("color", d["text"])]))
    out.append((s + " .strip-button", [
        ("border-color", d["line"]),
        ("background", d["soft"]),
        ("color", d["text"]),
    ]))
    out.append((s + " .strip-button:hover,\n" + s + " .strip-button:focus-visible", [
        ("border-color", d["accent"]),
        ("background", hover_soft),
        ("color", d["text"]),
    ]))
    out.append((s + " .stripbar__brand,\n" + s + " .stripbar__word", [("color", d["muted"])]))
    return out


def render_block(prelude, decls):
    lines = []
    for k, v in decls:
        line = "  %s: %s;" % (k, v.replace("\n", CRLF))
        # a declaration whose value starts on the next line carries no trailing space
        lines.append(line.replace(": " + CRLF, ":" + CRLF))
    body = CRLF.join(lines)
    return prelude.replace("\n", CRLF) + " {" + CRLF + body + CRLF + "}"


def emit_legacy():
    chunks = [CRLF.join(LEGACY_HEADER)]
    for d in DESIGNS:
        blocks = [render_block(p, dec) for p, dec in legacy_theme_blocks(d)]
        chunks.append(CRLF.join(legacy_comment(d)) + CRLF + (CRLF * 2).join(blocks))
    return (CRLF * 2).join(chunks) + CRLF




# ==========================================================================
# THE DESIGNS PROFILE
#
# One structural translation per design, read off the zip's own component.
# The shared vocabulary of CSS means available to a theme here is: gradients
# (including repeating-), grid, pseudo-elements with content, radii, filters,
# counters and order. NO element is added to the panel and no other file is
# touched -- app/panel/panel.html is not in this lane's write scope, so the
# structure has to be BUILT from the DOM the panel already has.
#
# The owner's ONE permitted deviation: "so muda a posicao dos botoes". Every
# design therefore also states where ITS buttons sit (order / justify-content
# on .panel__controls and .stripbar), and nothing else about them is allowed
# to differ from the zip's own control treatment.
# ==========================================================================

# Per-design values that only the STRUCTURE needs: the two type roles the tune
# dialog owns (live = the forming line, closed = every committed row), the
# zip's caption-stage leading/weight/tracking, the panel background pair, and
# the motion duration.
STRUCT = {
    # zip: scenes.ts:106-115 + PanelSetA.tsx:22-141
    "GlassCards": dict(live_size=34, live_leading="1.34", live_weight=400,
                       live_tracking="-0.012em", upper="none",
                       closed_size=13, closed_leading="1.625", closed_weight=400,
                       provisional="#FCEDD8", bg_slab="rgba(16,11,8,0.72)",
                       motion="180ms", scheme="dark"),
    # zip: scenes.ts:174-183 + PanelSetA.tsx:143-247
    "Hairline": dict(live_size=28, live_leading="1.5", live_weight=300,
                     live_tracking="-0.02em", upper="none",
                     closed_size=13, closed_leading="1.65", closed_weight=300,
                     provisional="#E8F1F7", bg_slab="rgba(6,10,14,0.52)",
                     motion="260ms", scheme="dark"),
    # zip: scenes.ts:242-251 + PanelSetA.tsx:249-355
    "Paper": dict(live_size=33, live_leading="1.42", live_weight=400,
                  live_tracking="-0.008em", upper="none",
                  closed_size=12.5, closed_leading="2.16", closed_weight=400,
                  # NO LIGHT SLAB (owner, 2026-10-14: *"e nao e pra ter tema branco").
                  # This row is where `--bg-slab`, the provisional ink and `color-scheme`
                  # come from, so the light sheet `scenes.ts` states lived HERE as well as
                  # in `DESIGNS` above. Both are inverted: dark warm linen, dark scheme.
                  provisional="#F6E7D4", bg_slab="rgba(26,18,13,0.96)",
                  motion="160ms", scheme="dark"),
    # zip: scenes.ts:310-319 + PanelSetA.tsx:357-458
    "Quotes": dict(live_size=36, live_leading="1.3", live_weight=400,
                   live_tracking="-0.01em", upper="none",
                   closed_size=13.5, closed_leading="1.6", closed_weight=400,
                   provisional="#FFF2E0", bg_slab="rgba(20,13,9,0.74)",
                   motion="200ms", scheme="dark"),
    # zip: scenes.ts:377-386 + PanelSetA.tsx:460-545
    "Ledger": dict(live_size=31, live_leading="1.38", live_weight=400,
                   live_tracking="-0.01em", upper="none",
                   closed_size=12.5, closed_leading="1.625", closed_weight=400,
                   provisional="#F2EDDD", bg_slab="rgba(11,14,10,0.78)",
                   motion="140ms", scheme="dark"),
    # zip: scenes.ts:444-453 + PanelSetB.tsx:18-135
    "Feed": dict(live_size=24, live_leading="1.6", live_weight=400,
                 live_tracking="-0.01em", upper="lowercase",
                 closed_size=11.5, closed_leading="1.75", closed_weight=400,
                 provisional="#D9DEF0", bg_slab="rgba(7,7,13,0.86)",
                 motion="700ms", scheme="dark"),
    # zip: scenes.ts:511-520 + PanelSetB.tsx:137-270
    "Bubbles": dict(live_size=30, live_leading="1.42", live_weight=400,
                    live_tracking="-0.008em", upper="none",
                    closed_size=12.5, closed_leading="1.6", closed_weight=400,
                    provisional="#F3E9F4", bg_slab="rgba(19,15,28,0.76)",
                    motion="220ms", scheme="dark"),
    # zip: scenes.ts:578-587 + PanelSetB.tsx:272-395
    "Timeline": dict(live_size=32, live_leading="1.4", live_weight=300,
                     live_tracking="-0.014em", upper="none",
                     closed_size=12.5, closed_leading="1.65", closed_weight=300,
                     provisional="#E7EFF3", bg_slab="rgba(8,12,15,0.72)",
                     motion="500ms", scheme="dark"),
    # zip: scenes.ts:645-654 + PanelSetB.tsx:397-505
    "Chips": dict(live_size=32, live_leading="1.38", live_weight=400,
                  live_tracking="-0.01em", upper="none",
                  closed_size=12.5, closed_leading="1.6", closed_weight=400,
                  provisional="#FFE4CE", bg_slab="rgba(16,9,7,0.82)",
                  motion="500ms", scheme="dark"),
    # zip: scenes.ts:712-721 + PanelSetB.tsx:507-571
    "Gutter": dict(live_size=27, live_leading="1.52", live_weight=300,
                   live_tracking="-0.018em", upper="none",
                   closed_size=13.5, closed_leading="1.62", closed_weight=300,
                   # NO LIGHT SLAB (owner, 2026-10-14: *"e nao e pra ter tema branco").
                   # Same three fields, same inversion: a deep slate sheet and a dark scheme.
                   provisional="#E2EBEF", bg_slab="rgba(20,28,30,0.96)",
                   motion="500ms", scheme="dark"),
}

TUNE_TOKENS = [
    "--font-sans", "--size-caption", "--leading-caption", "--weight-caption",
    "--tracking-caption", "--caption-upper", "--size-closed", "--leading-closed",
    "--weight-closed", "--text-provisional", "--bg-slab", "--bg-slab-strong",
    "--radius-lg", "--motion-in", "--type-step", "--accent", "--text-secondary",
]


def root_block(d):
    """The 17 tune tokens + the palette + the bridge onto panel.css's namespace.

    D2 was: zipc-panels.css contained ZERO var(). Measured on the shipped file:
    21 tokens declared, 0 consumed, 0 of the 17 tune tokens live. Every one of
    the 17 is declared AND consumed below, in this design's own rules.
    """
    st = STRUCT[d["name"]]
    s = ":root[data-theme='%s']" % d["name"]
    return (s, [
        ("--font-sans", d["panel_font"]),
        ("--size-caption", "%spx" % st["live_size"]),
        ("--leading-caption", st["live_leading"]),
        ("--weight-caption", str(st["live_weight"])),
        ("--tracking-caption", st["live_tracking"]),
        ("--caption-upper", st["upper"]),
        ("--size-closed", "%spx" % st["closed_size"]),
        ("--leading-closed", st["closed_leading"]),
        ("--weight-closed", str(st["closed_weight"])),
        ("--text-provisional", st["provisional"]),
        ("--bg-slab", st["bg_slab"]),
        ("--bg-slab-strong", d["surface"]),
        ("--radius-lg", "%dpx" % d["radius"]),
        ("--motion-in", st["motion"]),
        ("--type-step", "45ms"),
        ("--accent", d["accent"]),
        ("--accent-soft", d["soft"]),
        ("--theme-swatch", d["accent"]),
        ("--line", d["line"]),
        ("--line-strong", d["line"]),
        ("--text-primary", d["text"]),
        ("--text-secondary", d["muted"]),
        ("--text-muted", d["muted"]),
        ("--time-live", d["accent"]),
        ("--time-past", d["muted"]),
        ("--radius-md", "%dpx" % d["radius_md"]),
        ("--radius-sm", "%dpx" % d["radius_sm"]),
        ("--font-mono", '"JetBrains Mono", ui-monospace, monospace'),
        ("--size-small", "12px"),
        ("--space-2", "8px"),
        ("--space-3", "12px"),
        ("--bg", "var(--bg-slab)"),
        ("--bg-raised", "var(--bg-slab-strong)"),
        ("--text", "var(--text-primary)"),
        ("--text-dim", "var(--text-secondary)"),
        ("--text-faint", "var(--text-muted)"),
        ("--radius", "var(--radius-lg)"),
        ("--font", "var(--font-sans)"),
        ("--mono", "var(--font-mono)"),
        ("--accent-from", "var(--accent)"),
        ("--accent-to", "var(--accent)"),
        ("--accent-gradient", "var(--accent)"),
        ("color-scheme", st["scheme"]),
    ])


def shared_type(d):
    """The type contract every design honours, all of it through var().

    One rule, ten designs: the tune dialog's two size controls map onto the two
    roles the panel actually has -- the FORMING line and the COMMITTED row.
    """
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .caption__text", [
        ("font-family", "var(--font-sans)"),
        ("font-size", "var(--size-closed)"),
        ("line-height", "var(--leading-closed)"),
        ("font-weight", "var(--weight-closed)"),
        ("letter-spacing", "var(--tracking-caption)"),
        ("color", "var(--text-secondary)"),
        ("text-transform", "var(--caption-upper)"),
    ]))
    out.append((s + " .caption--latest .caption__text,\n" + s + " .caption--provisional .caption__text", [
        ("font-size", "var(--size-caption)"),
        ("line-height", "var(--leading-caption)"),
        ("font-weight", "var(--weight-caption)"),
        ("color", "var(--text-primary)"),
    ]))
    out.append((s + " .caption--provisional .caption__text", [
        ("color", "var(--text-provisional)"),
        ("font-style", "normal"),
    ]))
    out.append((s + " .caption__ch", [
        ("animation-delay", "calc(var(--c-i) * var(--type-step))"),
    ]))
    return out


def shared_chrome(d):
    """The panel chrome every design keeps, in the design's own palette.

    Written once per design (not once globally) because the scope-leak oracle
    requires every selector member to be rooted at a theme scope, and because a
    design is allowed to override any of it in its own section below.
    """
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    return [
        (s + " .panel", [
            ("border-color", "var(--line)"),
            ("border-radius", "var(--radius-lg)"),
            ("color", "var(--text-primary)"),
            ("font-family", "var(--font-sans)"),
        ]),
        (s + " .panel::before", [
            ("background", "linear-gradient(90deg, var(--accent), var(--accent-soft))"),
            ("opacity", "0.9"),
        ]),
        (s + " .caption__time", [
            ("color", "var(--time-past)"),
            ("font-family", "var(--font-mono)"),
        ]),
        (s + " .caption--provisional .caption__time", [("color", "var(--time-live)")]),
        (s + " .caption__led", [("background", "var(--accent)")]),
        (s + " .captions__placeholder-title,\n" + s + " .captions__placeholder-body", [
            ("color", "var(--text-muted)"),
            ("font-family", "var(--font-sans)"),
        ]),
        (s + " .status__dot", [("background", "var(--text-muted)")]),
        (s + " .status--live .status__dot", [("background", "var(--accent)")]),
        (s + " .status__text", [("color", "var(--text-secondary)")]),
        (s + " .history__label,\n" + s + " .history__note,\n" + s + " .history__count", [
            ("color", "var(--text-muted)"),
        ]),
        (s + " .history__path", [
            ("color", "var(--text-primary)"),
            ("font-family", "var(--font-mono)"),
        ]),
        (s + " .strip-button", [
            ("border-color", "var(--line)"),
            ("background", "var(--accent-soft)"),
            ("color", "var(--text-primary)"),
            ("border-radius", "var(--radius-sm)"),
            ("transition", "background-color var(--motion-in) ease, border-color var(--motion-in) ease"),
        ]),
        (s + " .strip-button:hover,\n" + s + " .strip-button:focus-visible", [
            ("border-color", "var(--accent)"),
            ("background", "color-mix(in srgb, var(--accent) 24%, transparent)"),
            ("color", "var(--text-primary)"),
        ]),
        (s + " .stripbar__brand,\n" + s + " .stripbar__word", [("color", "var(--text-muted)")]),
        (s + " .theme-button::after", [
            ("content", '""'),
            ("display", "inline-block"),
            ("width", "6px"),
            ("height", "6px"),
            ("margin-left", "5px"),
            ("border-radius", "99px"),
            ("background", "var(--theme-swatch, var(--accent))"),
            ("vertical-align", "middle"),
        ]),
        (s + " .captions__body", [
            ("border-color", "var(--line-strong)"),
            ("transition", "border-color var(--motion-in) ease"),
        ]),
        # THE ENTRANCE ANIMATION IS REFUSED, and it is not cosmetic:
        # panel.css animates '.caption' with 'caption-in ... both', and a
        # fill-mode of BOTH means the keyframe's final 'opacity: 1' keeps
        # winning over any static opacity a design sets. Design 06's whole idea
        # is a recency opacity ramp, so the animation has to go -- which is
        # exactly what the five owner themes do ('animation: none' in each).
        # The motion token replaces it, so '--motion-in' is live here too.
        (s + " .caption", [
            ("animation", "none"),
            ("transition", "background-color var(--motion-in) ease, border-color var(--motion-in) ease, opacity var(--motion-in) ease"),
        ]),
    ]


# --------------------------------------------------------------------------
# 01 GlassCards -- Midnight Cafe: frosted glass cards, one per segment, each
#    with its own round initials avatar. PanelSetA.tsx:22-141.
#    The design's NAME is the frosted glass: 'backdropFilter: blur(p.blur)'
#    on every card. The blur is kept because it blurs the PANEL's own backdrop
#    inside the page -- only the desktop behind the window is unreachable.
# --------------------------------------------------------------------------
def design_glasscards(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("backdrop-filter", "blur(20px)"),
        ("-webkit-backdrop-filter", "blur(20px)"),
        ("box-shadow", "0 30px 80px -30px rgba(0,0,0,0.85)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "color-mix(in srgb, var(--bg-slab) 82%, transparent)"),
        ("border-radius", "calc(var(--radius-lg) - 7px)"),
        ("backdrop-filter", "blur(20px)"),
        ("-webkit-backdrop-filter", "blur(20px)"),
    ]))
    # THE AVATAR CLUSTER: 'flex -space-x-2' of 'h-6 w-6 rounded-full' over a
    # 'border-t' rule (PanelSetA.tsx:66-79).
    out.append((s + " .captions__bar::before", [
        ("content", '""'),
        ("flex", "none"),
        ("width", "46px"),
        ("height", "22px"),
        ("margin-right", "8px"),
        ("background-image",
         "radial-gradient(circle at 11px 11px, var(--accent-soft) 0 7.5px, var(--accent) 7.5px 9px, transparent 9px),\n"
         "    radial-gradient(circle at 23px 11px, var(--accent-soft) 0 7.5px, var(--line-strong) 7.5px 9px, transparent 9px),\n"
         "    radial-gradient(circle at 35px 11px, var(--accent-soft) 0 7.5px, var(--line-strong) 7.5px 9px, transparent 9px)"),
        ("background-repeat", "no-repeat"),
    ]))
    out.append((s + " .captions__list", [("gap", "10px")]))
    # ONE CARD PER SEGMENT: 'anim-seg flex gap-3 p-3' + blur + a 28px avatar
    # column ('grid h-7 w-7 shrink-0 place-items-center rounded-full').
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "28px 1fr"),
        ("grid-template-rows", "auto auto"),
        ("column-gap", "12px"),
        ("row-gap", "3px"),
        ("padding", "12px"),
        ("border", "1px solid var(--line)"),
        ("border-radius", "max(12px, calc(var(--radius-lg) - 6px))"),
        ("background", "var(--accent-soft)"),
        ("backdrop-filter", "blur(20px)"),
        ("-webkit-backdrop-filter", "blur(20px)"),
    ]))
    out.append((s + " .caption::before", [
        ("content", '""'),
        ("grid-area", "1 / 1 / span 2 / span 1"),
        ("width", "28px"),
        ("height", "28px"),
        ("border-radius", "50%"),
        ("background", "color-mix(in srgb, var(--accent) 13%, transparent)"),
        ("box-shadow", "inset 0 0 0 1px color-mix(in srgb, var(--accent) 20%, transparent)"),
    ]))
    out.append((s + " .caption__time", [("grid-area", "1 / 2"), ("padding-top", "0")]))
    out.append((s + " .caption__text", [("grid-area", "2 / 2")]))
    # the newest card takes the accent edge (PanelSetA.tsx:95-100, 'isLast')
    out.append((s + " .caption--latest", [
        ("border-color", "color-mix(in srgb, var(--accent) 30%, transparent)"),
        ("border-radius", "max(12px, calc(var(--radius-lg) - 6px))"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 02 Hairline -- Rainglass: 'near-invisible panel, hairlines only'
#    (PanelSetA.tsx:143-247). NO surface, NO card: a tab row with an active
#    underline, and every segment a 'grid-cols-[44px_1fr]' row separated by a
#    single hairline.
# --------------------------------------------------------------------------
def design_hairline(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "none"),
        ("border-color", "transparent"),
        ("border-radius", "0"),
        ("box-shadow", "none"),
    ]))
    out.append((s + " .panel::before", [("display", "none")]))
    out.append((s + " .captions__body", [
        ("background", "none"),
        ("border-color", "transparent"),
        ("border-radius", "0"),
        ("box-shadow", "none"),
    ]))
    # THE TAB ROW: transcript / speakers / notes, the active one underlined by
    # 'absolute -bottom-[2px] left-0 h-[1px] w-full' (PanelSetA.tsx:176-192).
    out.append((s + " .captions__bar", [
        ("border-bottom", "1px solid var(--line)"),
        ("align-items", "baseline"),
    ]))
    out.append((s + " .captions__bar::before", [
        ("content", '"transcript"'),
        ("order", "-1"),
        ("flex", "none"),
        ("padding-bottom", "6px"),
        ("margin-bottom", "-1px"),
        ("border-bottom", "1px solid var(--accent)"),
        ("font-size", "11px"),
        ("color", "var(--text-primary)"),
        ("font-family", "var(--font-sans)"),
    ]))
    out.append((s + " .captions__hint", [
        ("margin-left", "16px"),
        ("font-size", "11px"),
        ("color", "var(--text-muted)"),
    ]))
    out.append((s + " .captions__list", [("gap", "0"), ("padding", "10px 0")]))
    # ONE ROW PER SEGMENT: 'grid grid-cols-[44px_1fr] gap-3 border-b py-3'
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "44px 1fr"),
        ("column-gap", "12px"),
        ("padding", "12px 2px"),
        ("border", "0"),
        ("border-bottom", "1px solid var(--line)"),
        ("border-radius", "0"),
        ("background", "transparent"),
    ]))
    out.append((s + " .caption:hover", [
        ("background", "color-mix(in srgb, var(--text-primary) 4%, transparent)"),
    ]))
    # THE 4px SPEAKER DOT: 'h-[4px] w-[4px] rounded-full' before the name
    # (PanelSetA.tsx:213-218).
    out.append((s + " .caption__text::before", [
        ("content", '""'),
        ("display", "inline-block"),
        ("width", "4px"),
        ("height", "4px"),
        ("margin-right", "6px"),
        ("border-radius", "50%"),
        ("background", "var(--accent)"),
        ("vertical-align", "middle"),
    ]))
    out.append((s + " .caption--latest", [("border-left-width", "0px")]))
    out.append((s + " .panel__controls", [("justify-content", "flex-start"), ("order", "0")]))
    return out


# --------------------------------------------------------------------------
# 03 Paper -- Dustlight: 'a typewritten page from a road log'
#    (PanelSetA.tsx:249-355). THE RULED PAGE: a repeating-linear-gradient at a
#    28px pitch over an absolutely positioned layer, a 1.5px margin rule at
#    x=52, rows on a 'grid-cols-[52px_1fr]' with the text on a 27px baseline.
# --------------------------------------------------------------------------
def design_paper(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("box-shadow", "0 34px 80px -34px rgba(0,0,0,0.8)"),
    ]))
    # 'repeating-linear-gradient(180deg, transparent 0 27px,
    #  rgba(60,40,26,0.075) 27px 28px)' at opacity 0.5 (PanelSetA.tsx:256-261).
    out.append((s + " .captions__body", [
        ("background-color", "var(--bg-slab-strong)"),
        ("background-image", "repeating-linear-gradient(180deg, transparent 0 27px, rgba(60,40,26,0.075) 27px 28px)"),
        ("background-position", "0 7px"),
        ("border-radius", "calc(var(--radius-lg) - 3px)"),
        ("box-shadow", "none"),
    ]))
    # THE MARGIN RULE: 'absolute inset-y-0 left-[52px] w-[1.5px]' in the accent
    # at 35% (PanelSetA.tsx:262-264).
    out.append((s + " .captions__body::before", [
        ("content", '""'),
        ("position", "absolute"),
        ("left", "52px"),
        ("top", "0"),
        ("bottom", "0"),
        ("width", "1.5px"),
        ("background", "color-mix(in srgb, var(--accent) 35%, transparent)"),
        ("pointer-events", "none"),
    ]))
    out.append((s + " .captions__list", [("gap", "0"), ("padding", "10px 12px")]))
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "52px 1fr"),
        ("column-gap", "12px"),
        ("padding", "7px 0"),
        ("border", "0"),
        ("border-radius", "0"),
        ("background", "transparent"),
    ]))
    out.append((s + " .caption__time", [("text-align", "right"), ("padding-top", "3px")]))
    # THE 'filed' STAMP on the last committed row (PanelSetA.tsx:305-311).
    out.append((s + " .caption--latest .caption__text::after", [
        ("content", '"filed"'),
        ("margin-left", "8px"),
        ("font-size", "9px"),
        ("letter-spacing", "0.2em"),
        ("text-transform", "uppercase"),
        ("color", "var(--accent)"),
    ]))
    # THE PAGE SIGN-OFF, centred in italics at the foot of the scroll
    # (PanelSetA.tsx:333-335).
    out.append((s + " .captions__list::after", [
        ("content", '"\\2014 continued, please don\'t brake on the gravel \\2014"'),
        ("padding", "16px 0"),
        ("text-align", "center"),
        ("font-size", "10px"),
        ("font-style", "italic"),
        ("color", "var(--text-muted)"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 04 Quotes -- Analog: 'sleeve notes on cocoa paper, one quote per card'
#    (PanelSetA.tsx:357-458). A 2px rule in the speaker's colour on the left
#    edge, a 34px Instrument Serif opening quote, and a 20px attribution rule.
# --------------------------------------------------------------------------
def design_quotes(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("backdrop-filter", "blur(16px)"),
        ("-webkit-backdrop-filter", "blur(16px)"),
        ("box-shadow", "0 30px 80px -30px rgba(0,0,0,0.85)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "color-mix(in srgb, var(--bg-slab) 88%, transparent)"),
        ("border-radius", "calc(var(--radius-lg) - 5px)"),
        ("backdrop-filter", "blur(16px)"),
        ("-webkit-backdrop-filter", "blur(16px)"),
    ]))
    out.append((s + " .captions__list", [("gap", "12px")]))
    # ONE QUOTE PER CARD: 'px-4 py-3.5 pl-5' with 'borderLeft: 2px solid color'
    out.append((s + " .caption", [
        ("position", "relative"),
        ("padding", "14px 16px 14px 20px"),
        ("border", "1px solid var(--line)"),
        ("border-left", "2px solid var(--accent)"),
        ("border-radius", "calc(var(--radius-lg) - 4px)"),
        ("background", "var(--accent-soft)"),
        ("backdrop-filter", "blur(16px)"),
        ("-webkit-backdrop-filter", "blur(16px)"),
    ]))
    # THE OPENING QUOTE: 'absolute -top-1 left-3 text-[34px]' in Instrument
    # Serif at 18% alpha (PanelSetA.tsx:392-397).
    out.append((s + " .caption::before", [
        ("content", '"\\201C"'),
        ("position", "absolute"),
        ("top", "-4px"),
        ("left", "12px"),
        ("font-family", '"Instrument Serif", Georgia, serif'),
        ("font-size", "34px"),
        ("line-height", "1"),
        ("color", "color-mix(in srgb, var(--accent) 18%, transparent)"),
        ("pointer-events", "none"),
    ]))
    # THE ATTRIBUTION RULE: 'h-[1px] w-5' before the speaker name
    # (PanelSetA.tsx:404-407).
    out.append((s + " .caption__time::before", [
        ("content", '""'),
        ("display", "inline-block"),
        ("width", "20px"),
        ("height", "1px"),
        ("margin-right", "8px"),
        ("vertical-align", "middle"),
        ("background", "var(--accent)"),
        ("opacity", "0.6"),
    ]))
    out.append((s + " .caption--latest", [
        ("background", "color-mix(in srgb, var(--accent) 8%, transparent)"),
        ("border-color", "color-mix(in srgb, var(--accent) 20%, transparent)"),
        ("border-left-color", "var(--accent)"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "space-between"), ("order", "1")]))
    return out


# --------------------------------------------------------------------------
# 05 Ledger -- Quiet Shelves: 'a quiet ledger: time / speaker / transcript'
#    (PanelSetA.tsx:460-545). A real three-column ledger with a column band, a
#    hairline under every entry and a zebra on the even rows.
# --------------------------------------------------------------------------
def design_ledger(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("box-shadow", "0 30px 80px -34px rgba(0,0,0,0.88)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    # THE COLUMN BAND: 'grid-cols-[46px_58px_1fr] border-y px-3 py-2 text-[9px]
    # uppercase tracking-[0.2em]' reading time / voice / transcript
    # (PanelSetA.tsx:484-488).
    out.append((s + " .captions__bar", [("flex-wrap", "wrap")]))
    out.append((s + " .captions__bar::before", [
        ("content", '"time\u00a0\u00a0\u00a0\u00a0voice\u00a0\u00a0\u00a0\u00a0transcript"'),
        ("flex", "1 1 100%"),
        ("order", "-1"),
        ("padding", "8px 12px"),
        ("border-top", "1px solid var(--line)"),
        ("border-bottom", "1px solid var(--line)"),
        ("font-size", "9px"),
        ("letter-spacing", "0.2em"),
        ("text-transform", "uppercase"),
        ("color", "var(--text-muted)"),
        ("font-family", "var(--font-sans)"),
    ]))
    out.append((s + " .captions__list", [("gap", "0"), ("padding", "0")]))
    # ONE LEDGER ENTRY: 'grid grid-cols-[46px_58px_1fr] items-baseline gap-2
    # border-b px-3 py-2.5' (PanelSetA.tsx:494-497).
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "46px 58px 1fr"),
        ("column-gap", "8px"),
        ("align-items", "baseline"),
        ("padding", "10px 12px"),
        ("border", "0"),
        ("border-bottom", "1px solid var(--line)"),
        ("border-radius", "0"),
        ("background", "transparent"),
    ]))
    # THE ZEBRA: 'background: i % 2 ? p.soft : transparent' (PanelSetA.tsx:496).
    out.append((s + " .caption:nth-child(even)", [
        ("background", "color-mix(in srgb, var(--accent) 6%, transparent)"),
    ]))
    # THE 'voice' COLUMN is built from the element panel.css hides: a real
    # element, put back in the flow and given the column.
    out.append((s + " .caption__led", [
        ("display", "block"),
        ("position", "static"),
        ("grid-area", "1 / 2"),
        ("align-self", "center"),
        ("width", "8px"),
        ("height", "8px"),
        ("border-radius", "50%"),
        ("background", "var(--accent)"),
    ]))
    out.append((s + " .caption__time", [("grid-area", "1 / 1")]))
    out.append((s + " .caption__text", [("grid-area", "1 / 3")]))
    out.append((s + " .caption--latest", [("border-bottom-color", "var(--accent)")]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 06 Feed -- Lamp Black: 'an ambient event log for a room that never sleeps'
#    (PanelSetB.tsx:18-135). A LOG, not a list of cards: every segment is one
#    inline 'flex gap-2' line, OLDER LINES FADE (opacity ramp), the live line
#    opens with a '>' caret, and the header carries a sweeping sheen bar.
# --------------------------------------------------------------------------
def design_feed(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("backdrop-filter", "blur(18px)"),
        ("-webkit-backdrop-filter", "blur(18px)"),
        ("box-shadow", "0 30px 80px -32px rgba(0,0,0,0.9)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    out.append((s + " .captions__bar", [
        ("border-bottom", "1px solid var(--line)"),
        ("padding-bottom", "10px"),
        ("flex-wrap", "wrap"),
    ]))
    # THE SHEEN BAR: 'mt-2.5 h-[1px] w-full' holding a 'w-1/3' gradient sweep
    # (PanelSetB.tsx:51-56).
    out.append((s + " .captions__bar::after", [
        ("content", '""'),
        ("flex", "1 1 100%"),
        ("order", "99"),
        ("height", "1px"),
        ("margin-top", "10px"),
        ("background-image", "linear-gradient(90deg, transparent, var(--accent), transparent)"),
        ("background-size", "33% 100%"),
        ("background-repeat", "no-repeat"),
        ("animation", "zipc-sheen 3.2s linear infinite"),
    ]))
    out.append((s + " .captions__list", [("gap", "2px"), ("padding", "10px 12px")]))
    # ONE LOG LINE: 'flex gap-2 text-[11.5px] leading-[1.75]' -- no surface,
    # no border, no radius (PanelSetB.tsx:70-72).
    out.append((s + " .caption", [
        ("display", "flex"),
        ("align-items", "baseline"),
        ("gap", "8px"),
        ("padding", "2px 0"),
        ("border", "0"),
        ("border-radius", "0"),
        ("background", "transparent"),
        ("font-family", "var(--font-mono)"),
        ("font-size", "var(--size-closed)"),
        ("line-height", "var(--leading-closed)"),
    ]))
    out.append((s + " .caption__time", [("order", "0"), ("color", "var(--accent)")]))
    out.append((s + " .caption__text", [("order", "1")]))
    # THE CARET: the live line opens with '>' (PanelSetB.tsx:84-86).
    out.append((s + " .caption--provisional::before,\n" + s + " .caption--latest::before", [
        ("content", '">"'),
        ("order", "-1"),
        ("color", "var(--accent)"),
        ("font-family", "var(--font-mono)"),
    ]))
    # THE RECENCY RAMP: 'opacity: Math.max(0.14, 1 - distance * 0.075)'
    # (PanelSetB.tsx:63-66) -- the design's whole idea is that the log fades.
    for k in range(1, 13):
        out.append((s + " .caption:nth-last-child(%d)" % k,
                    [("opacity", "%.3f" % max(0.14, 1 - (k - 1) * 0.075))]))
    out.append((s + " .caption:nth-last-child(n+13)", [("opacity", "0.14")]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 07 Bubbles -- Rooftop Dusk: 'a two-voice conversation in soft bubbles'
#    (PanelSetB.tsx:137-270). Chat bubbles: the second voice is right-aligned
#    and the tail corner is 5px on the side the bubble leans to.
# --------------------------------------------------------------------------
def design_bubbles(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("backdrop-filter", "blur(18px)"),
        ("-webkit-backdrop-filter", "blur(18px)"),
        ("box-shadow", "0 30px 80px -32px rgba(0,0,0,0.85)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    # THE SPEAKER CHIPS: 'inline-flex items-center gap-1.5 rounded-full
    # px-2.5 py-[3px]' with a 5px dot (PanelSetB.tsx:168-178).
    out.append((s + " .captions__bar::before", [
        ("content", '""'),
        ("flex", "none"),
        ("width", "76px"),
        ("height", "19px"),
        ("margin-right", "8px"),
        ("border", "1px solid var(--line)"),
        ("border-radius", "999px"),
        ("background-color", "var(--accent-soft)"),
        ("background-image", "radial-gradient(circle at 11px 50%, var(--accent) 0 2.5px, transparent 2.5px)"),
        ("background-repeat", "no-repeat"),
    ]))
    out.append((s + " .captions__list", [("gap", "10px")]))
    # ONE BUBBLE: 'max-w-[86%] px-3.5 py-2.5', radius 16 with ONE 5px tail
    # corner (PanelSetB.tsx:198-210).
    out.append((s + " .caption", [
        ("display", "block"),
        ("max-width", "86%"),
        ("align-self", "flex-start"),
        ("padding", "10px 14px"),
        ("border", "1px solid var(--line)"),
        ("border-radius", "16px 16px 16px 5px"),
        ("background", "var(--accent-soft)"),
        ("backdrop-filter", "blur(18px)"),
        ("-webkit-backdrop-filter", "blur(18px)"),
    ]))
    # THE OTHER VOICE: 'justify-end' + 'borderBottomRightRadius: 5'
    # (PanelSetB.tsx:190-196).
    out.append((s + " .caption:nth-child(even)", [
        ("align-self", "flex-end"),
        ("border-radius", "16px 16px 5px 16px"),
        ("background", "color-mix(in srgb, var(--accent) 10%, transparent)"),
        ("border-color", "color-mix(in srgb, var(--accent) 18%, transparent)"),
    ]))
    # THE SPEAKING DOTS: three 3px dots (PanelSetB.tsx:243-249).
    out.append((s + " .caption__time::before", [
        ("content", '""'),
        ("display", "inline-block"),
        ("width", "3px"),
        ("height", "3px"),
        ("margin-right", "6px"),
        ("border-radius", "50%"),
        ("background", "var(--accent)"),
        ("box-shadow", "5px 0 0 var(--accent), 10px 0 0 var(--accent)"),
        ("vertical-align", "middle"),
    ]))
    out.append((s + " .caption--provisional", [
        ("border-color", "color-mix(in srgb, var(--accent) 20%, transparent)"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "space-between"), ("order", "1")]))
    return out


# --------------------------------------------------------------------------
# 08 Timeline -- Tideline: 'a shoreline timeline of the take'
#    (PanelSetB.tsx:272-395). A 1px SPINE with a vertical gradient that fades
#    at both ends, and a 7px dot per segment sitting on it with a halo ring.
# --------------------------------------------------------------------------
def design_timeline(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("box-shadow", "0 30px 80px -36px rgba(0,0,0,0.88)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    # THE SPINE: 'absolute bottom-0 left-[26px] top-1 w-[1px]' with
    # 'linear-gradient(180deg, transparent, border 8%, border 92%, transparent)'
    # (PanelSetB.tsx:307-309). Placed in the gap between the two columns.
    out.append((s + " .captions__body::before", [
        ("content", '""'),
        ("position", "absolute"),
        ("left", "69.5px"),
        ("top", "4px"),
        ("bottom", "0"),
        ("width", "1px"),
        ("background", "linear-gradient(180deg, transparent, var(--line) 8%, var(--line) 92%, transparent)"),
        ("pointer-events", "none"),
    ]))
    out.append((s + " .captions__list", [("gap", "0")]))
    out.append((s + " .caption", [
        ("position", "relative"),
        ("display", "grid"),
        ("grid-template-columns", "52px 1fr"),
        ("column-gap", "16px"),
        ("padding", "0 0 16px"),
        ("border", "0"),
        ("border-radius", "0"),
        ("background", "transparent"),
    ]))
    # THE DOT ON THE SPINE: 'absolute -left-[24px] top-[7px] h-[7px] w-[7px]
    # rounded-full' with 'box-shadow: 0 0 0 2px' (PanelSetB.tsx:317-320).
    out.append((s + " .caption::before", [
        ("content", '""'),
        ("position", "absolute"),
        ("left", "56.5px"),
        ("top", "7px"),
        ("width", "7px"),
        ("height", "7px"),
        ("border-radius", "50%"),
        ("background", "var(--bg-slab)"),
        ("box-shadow", "0 0 0 2px var(--line)"),
    ]))
    out.append((s + " .caption--latest::before", [
        ("background", "var(--accent)"),
        ("box-shadow", "0 0 0 4px color-mix(in srgb, var(--accent) 15%, transparent)"),
    ]))
    out.append((s + " .caption__time", [("text-align", "right"), ("padding-top", "1px")]))
    out.append((s + " .caption--latest", [("border-radius", "0"), ("border-left-width", "0px")]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 09 Chips -- Ember: 'chapters of short, warm chip-rows by the stove'
#    (PanelSetB.tsx:397-505). Every FOURTH segment opens a chapter band with a
#    counted label and a rule; the time becomes a pill chip; the header carries
#    the rounded search field.
# --------------------------------------------------------------------------
def design_chips(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("backdrop-filter", "blur(16px)"),
        ("-webkit-backdrop-filter", "blur(16px)"),
        ("box-shadow", "0 30px 80px -30px rgba(0,0,0,0.88)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    out.append((s + " .captions__bar", [("flex-wrap", "wrap")]))
    # THE SEARCH FIELD: 'flex items-center gap-2 rounded-full px-3 py-1.5' with
    # the magnifier and 'search this session...' (PanelSetB.tsx:457-467).
    out.append((s + " .captions__bar::after", [
        ("content", '"search this session\\2026"'),
        ("flex", "1 1 100%"),
        ("order", "99"),
        ("margin-top", "8px"),
        ("padding", "6px 12px"),
        ("border", "1px solid var(--line)"),
        ("border-radius", "999px"),
        ("background", "var(--accent-soft)"),
        ("color", "var(--text-muted)"),
        ("font-size", "10.5px"),
        ("font-family", "var(--font-sans)"),
    ]))
    # THE CHAPTER COUNTER: 'Math.floor(i / 4)' labels each band 'chapter NN'
    # (PanelSetB.tsx:402-408). CSS counters do it without a new element.
    out.append((s + " .captions__list", [
        ("gap", "6px"),
        ("counter-reset", "zipc-chapter"),
    ]))
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "auto 1fr"),
        ("grid-template-rows", "auto auto"),
        ("column-gap", "10px"),
        ("row-gap", "6px"),
        ("padding", "10px 12px"),
        ("border", "1px solid transparent"),
        ("border-radius", "calc(var(--radius-lg) - 6px)"),
        ("background", "transparent"),
    ]))
    out.append((s + " .caption:nth-child(4n+1)", [("counter-increment", "zipc-chapter")]))
    out.append((s + " .caption:nth-child(4n+1)::before", [
        ("content", '"chapter " counter(zipc-chapter, decimal-leading-zero)'),
        ("grid-column", "1 / -1"),
        ("grid-row", "1"),
        ("padding-bottom", "6px"),
        ("border-bottom", "1px solid var(--line)"),
        ("font-size", "9px"),
        ("letter-spacing", "0.24em"),
        ("text-transform", "uppercase"),
        ("color", "var(--text-muted)"),
    ]))
    # THE CHIP: 'rounded-full px-2 py-[2px] text-[9.5px] uppercase'
    # (PanelSetB.tsx:441-446) -- the time carries it.
    out.append((s + " .caption__time", [
        ("grid-area", "2 / 1"),
        ("padding", "2px 8px"),
        ("border-radius", "999px"),
        ("background", "color-mix(in srgb, var(--accent) 11%, transparent)"),
        ("color", "var(--accent)"),
        ("font-size", "9.5px"),
        ("letter-spacing", "0.1em"),
        ("text-transform", "uppercase"),
        ("white-space", "nowrap"),
    ]))
    out.append((s + " .caption__text", [("grid-area", "2 / 2")]))
    out.append((s + " .caption--latest", [
        ("border-color", "var(--line)"),
        ("border-left", "2px solid var(--accent)"),
        ("background", "color-mix(in srgb, var(--accent) 7%, transparent)"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


# --------------------------------------------------------------------------
# 10 Gutter -- Field Notes: 'a light page with a margin gutter, morning after
#    the storm' (PanelSetB.tsx:507-571). A 54px gutter carrying the time AND a
#    24px round avatar under it, one hairline per entry, a 'rec' pill.
# --------------------------------------------------------------------------
def design_gutter(d):
    n = d["name"]
    s = ":root[data-theme='%s']" % n
    out = []
    out.append((s + " .panel", [
        ("background", "linear-gradient(180deg, var(--bg-slab-strong) 0%, var(--bg-slab) 100%)"),
        ("border-radius", "var(--radius-lg)"),
        ("box-shadow", "0 34px 80px -34px rgba(0,0,0,0.75)"),
        ("color", "var(--text-primary)"),
    ]))
    out.append((s + " .captions__body", [
        ("background", "var(--bg-slab)"),
        ("border-radius", "var(--radius-md)"),
        ("box-shadow", "none"),
    ]))
    # THE REC PILL: 'flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1'
    # (PanelSetB.tsx:534-537).
    out.append((s + " .captions__bar", [("align-items", "center")]))
    out.append((s + " .captions__bar::after", [
        ("content", '"rec"'),
        ("flex", "none"),
        ("order", "99"),
        ("margin-left", "auto"),
        ("padding", "4px 10px"),
        ("border-radius", "999px"),
        ("background", "var(--accent-soft)"),
        ("color", "var(--accent)"),
        ("font-size", "9.5px"),
        ("letter-spacing", "0.14em"),
        ("text-transform", "uppercase"),
        ("font-family", "var(--font-mono)"),
    ]))
    out.append((s + " .captions__list", [("gap", "0"), ("padding", "10px 4px")]))
    # ONE NOTE: 'grid grid-cols-[54px_1fr] gap-4 rounded-xl px-1 py-3' with a
    # 'borderBottom' hairline (PanelSetB.tsx:539-544).
    out.append((s + " .caption", [
        ("display", "grid"),
        ("grid-template-columns", "54px 1fr"),
        ("grid-template-rows", "auto auto"),
        ("column-gap", "16px"),
        ("row-gap", "6px"),
        ("padding", "12px 4px"),
        ("border", "0"),
        ("border-bottom", "1px solid var(--line)"),
        ("border-radius", "0"),
        ("background", "transparent"),
    ]))
    # THE AVATAR IN THE GUTTER, under the time: 'grid h-6 w-6 place-items-center
    # rounded-full' (PanelSetB.tsx:548-556).
    out.append((s + " .caption::before", [
        ("content", '""'),
        ("grid-area", "2 / 1"),
        ("width", "24px"),
        ("height", "24px"),
        ("border-radius", "50%"),
        ("background", "color-mix(in srgb, var(--accent) 13%, transparent)"),
        ("box-shadow", "inset 0 0 0 1px color-mix(in srgb, var(--accent) 20%, transparent)"),
    ]))
    out.append((s + " .caption__time", [("grid-area", "1 / 1")]))
    out.append((s + " .caption__text", [("grid-area", "1 / 2 / span 2 / span 1")]))
    out.append((s + " .caption--latest", [
        ("background", "color-mix(in srgb, var(--accent) 7%, transparent)"),
        ("border-left-width", "0px"),
    ]))
    out.append((s + " .panel__controls", [("justify-content", "flex-end"), ("order", "2")]))
    return out


DESIGN_BUILDERS = [
    ("01", "GlassCards", "Midnight Cafe -- frosted glass cards over the room", design_glasscards),
    ("02", "Hairline", "Rainglass -- near-invisible panel, hairlines only", design_hairline),
    ("03", "Paper", "Dustlight -- a typewritten page from a road log", design_paper),
    ("04", "Quotes", "Analog -- sleeve notes on cocoa paper, one quote per card", design_quotes),
    ("05", "Ledger", "Quiet Shelves -- a quiet ledger: time / voice / transcript", design_ledger),
    ("06", "Feed", "Lamp Black -- an ambient event log for a room that never sleeps", design_feed),
    ("07", "Bubbles", "Rooftop Dusk -- a two-voice conversation in soft bubbles", design_bubbles),
    ("08", "Timeline", "Tideline -- a shoreline timeline of the take", design_timeline),
    ("09", "Chips", "Ember -- chapters of short, warm chip-rows by the stove", design_chips),
    ("10", "Gutter", "Field Notes -- a light page with a margin gutter", design_gutter),
]


# --------------------------------------------------------------------------
# THE DESIGNS FILE
# --------------------------------------------------------------------------
DESIGNS_HEADER = [
    "/* zipc-panels.css -- the TEN panel designs of the THIRD zip, as STRUCTURE.",
    " *",
    " * GENERATED. DO NOT HAND-EDIT. The generator is",
    " * '_main/_design-lane/gen_zipc.py'; run it with '--profile designs' and",
    " * redirect to a scratch path first. The same generator also carries a",
    " * '--profile legacy' arm that reproduces the PREVIOUS shipped file byte for",
    " * byte (35 875 B, sha256 9E32F9160C38B855...), which is the proof that it is",
    " * faithful to what was on disk before this rewrite.",
    " *",
    " * THE DEFECT THIS FILE CLOSES (measured, I:/cc-tmp/design-bugs-audit.md D1):",
    " * the ten designs used to be ONE skeleton recoloured ten times. Re-measured",
    " * on the shipped bytes with a byte-level parser: all ten declared the SAME 18",
    " * selectors with the SAME 24 comma members, and only eight layout/typography",
    " * declarations differed (border, border-bottom, border-radius, padding,",
    " * font-family, font-size, font-weight, letter-spacing). Zero occurrences of",
    " * repeating-linear-gradient, grid-template, border-radius: 50%,",
    " * backdrop-filter or ::after. (The audit reported TWO selector sequences,",
    " * seven plus three; that is the '.caption' border DECLARATION splitting the",
    " * ten in 7+3, not the selectors -- the selectors were identical in all ten.)",
    " *",
    " * THE OWNER'S RULE, verbatim: *\"eu quero que, cada tema encontrado dentro dos",
    " * .zip, fiquem com o design IGUAL, e so muda a posicao dos botoes.\"* So each",
    " * design below is built from ITS OWN component in the zip, and the ONLY",
    " * thing allowed to differ from the zip is where the buttons sit (the",
    " * '.panel__controls' order/justify-content line at the end of each design).",
    " *",
    " * THE SOURCE, and the file each structure was read out of:",
    " *   src/components/panels/PanelSetA.tsx  GlassCards(22) Hairline(143)",
    " *                                        Paper(249) Quotes(357) Ledger(460)",
    " *   src/components/panels/PanelSetB.tsx  Feed(18) Bubbles(137) Timeline(272)",
    " *                                        Chips(397) Gutter(507)",
    " *   src/data/scenes.ts                   the ten palettes + the caption",
    " *                                        stage size/leading/weight/tracking",
    " *",
    " * WHAT A THEME IS ALLOWED TO USE HERE. The panel's own document is not part",
    " * of this lane's write scope, so no element is added: every structure below",
    " * is built from the DOM the panel already has, with gradients (including",
    " * repeating-), grid, pseudo-elements with content, radii, filters, counters",
    " * and order. 'rounded-full' avatars, the ruled page, the spine, the chapter",
    " * bands and the tail corners are all CSS, on the nodes that already exist.",
    " *",
    " * ONE ELEMENT CANNOT BE REBUILT, and it is declared rather than faked: the",
    " * zip's avatars carry the SPEAKER'S INITIALS. The panel's caption row has no",
    " * element holding a name and no attribute carrying one, so the circle is",
    " * built (fill + ring) and the initials are not. The audit's own D1 counted",
    " * that as the missing element; it is missing because the data is.",
    " *",
    " * THE TUNE DIALOG (defect D2). 'theme-tune.js' writes 17 tokens inline on",
    " * <html>. On the shipped file zipc-panels.css contained ZERO 'var()' and",
    " * consumed 0 of the 17, so every control in the owner's tuning dialog was",
    " * inert in all ten designs. Every design below DECLARES all 17 in its own",
    " * ':root' block and CONSUMES all 17 with 'var()' in its own scoped rules.",
    " * The two type roles the dialog names map onto the two roles the panel has:",
    " * '--size-caption' is the FORMING line, '--size-closed' is a COMMITTED row.",
    " *",
    " * ONE DEVIATION, and it is in ALPHA ONLY, the same one 'panel-designs.css'",
    " * makes: the zip renders its panel over its own opaque stage, and the",
    " * surfaces below are the zip's own colours composited over the panel's own",
    " * backdrop. 'backdrop-filter' IS kept -- it blurs the panel's own backdrop",
    " * inside the page, which is what the GlassCards design is named for; only",
    " * the desktop behind the window is out of reach.",
    " */",
]

# The sheen bar of design 06. Namespaced: a keyframe name is global.
KEYFRAMES_SHEEN = """@keyframes zipc-sheen {
  from { background-position: -40% 0; }
  to { background-position: 140% 0; }
}"""

DESIGN_EXTRA = {"Feed": [KEYFRAMES_SHEEN]}

BANNER_WIDTH = 82


def design_banner(num, name, subtitle):
    head = "/* \u2500\u2500 %s %s \u2500\u2500 %s " % (num, name, subtitle)
    pad = BANNER_WIDTH - len(head)
    return [head + "\u2500" * max(pad, 3), " */"]


def render_all(items):
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(item.replace("\n", CRLF))
        else:
            out.append(render_block(item[0], item[1]))
    return out


def emit_designs():
    chunks = [CRLF.join(DESIGNS_HEADER)]
    by_name = {d["name"]: d for d in DESIGNS}
    for num, name, subtitle, builder in DESIGN_BUILDERS:
        d = by_name[name]
        items = [root_block(d)] + shared_type(d) + shared_chrome(d)
        items += DESIGN_EXTRA.get(name, [])
        items += builder(d)
        blocks = render_all(items)
        chunks.append(CRLF.join(design_banner(num, name, subtitle)) + CRLF + (CRLF * 2).join(blocks))
    return (CRLF * 2).join(chunks) + CRLF

def main(argv=None):
    ap = argparse.ArgumentParser(description="generate zipc-panels.css")
    ap.add_argument("--profile", choices=["legacy", "designs"], default="designs")
    ap.add_argument("--out", default=None, help="write here (default: stdout)")
    args = ap.parse_args(argv)

    text = emit_legacy() if args.profile == "legacy" else emit_designs()
    data = text.encode("utf-8")
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(data)
    else:
        sys.stdout.buffer.write(data)
    sys.stderr.write("profile=%s bytes=%d sha256=%s\n" % (
        args.profile, len(data), hashlib.sha256(data).hexdigest().upper()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

