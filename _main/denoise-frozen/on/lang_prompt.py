"""The ASR language prompt, resolved from the model's OWN table — never a bare literal.

WHY THIS MODULE EXISTS (the defect it closes, measured 2026-10-06)

`worker/config.json` carried `"lang_id": 0`, which the model's own `languages.json`
defines as `en-US`, while the owner's audio is Brazilian Portuguese (`pt-BR` = 12).
The value was also DEAD CODE. `main()` had, before this module:

    ap.add_argument("--lang-id", type=int, default=0)                    # default 0
    ...
    lang_id = args.lang_id if args.lang_id is not None else cfg[...]["lang_id"]

`default=0` is never `None`, so the `else` branch could not be reached: the knob was
documented in `worker/README.md` and `docs/model-specs/README.md`, present in the
shipped config, and had no effect on any run. Only the CLI flag reached the model.

This module makes the prompt a first-class setting with ONE resolution path:

    --lang-id (CLI)  >  SOTTO_LANG_ID (env)  >  config.json  >  the "os" sentinel

The shipped CONFIG default is `"auto"` (the model's own `autoSlot` 101) as of
2026-10-06. It replaced `"os"` (host USER locale): on this pt-BR host `"os"` resolved
to 12 (pt-BR), and decoding the bundled ENGLISH sample with prompt 12 collapsed 94
tokens to 10 — the mirror of the damage the older literal `0` (en-US) did to
Portuguese (5 tokens vs 18). `"auto"` scored 89/94 English and 18/18 Portuguese: the
only one of the three good on BOTH. `"os"` is still ACCEPTED (host locale on
request), and it is also the sentinel this resolver falls back to when NO value is
set at all (`--lang-id` default `None` and the config has no `model.lang_id`),
itself falling back to `auto` when the locale names no slot. Whichever value wins is
FIXED for the whole stream. Receipt: `_main/lang-id-default-arms.py`.

A value the model does not declare (999, -1, "klingon") is REFUSED loudly. It is
never clamped, rounded, or ignored: an undeclared id is an undefined embedding row,
and a silent fallback would put the wrong language in front of the model with no
trace anywhere in the run.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from collections import namedtuple

# "Let the host decide" — the sentinel used when NO value is set at all (the config
# key absent). It is NOT the shipped config default (that is "auto" = autoSlot 101).
OS_LOCALE_ALIASES = ("os", "locale", "system", "default")
# The shell's rung. worker-bridge.js#spawn builds argv as
# `python [...extraArgs, workerPath]`, so a flag the shell hands over lands BEFORE
# the script path and is eaten by the interpreter instead of by this worker's
# parser — the same measured reason SOTTO_AUDIO_DEVICE and SOTTO_CAPTURE_MODE
# exist. A shell that must change the prompt therefore travels by env.
ENV_VAR = "SOTTO_LANG_ID"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Resolution = what the run will actually put in front of the model, plus where
# that decision came from. Every field lands in the `state="lang"` status line,
# so a wrong prompt is a readable line and not an inference.
Resolution = namedtuple("Resolution", "lang_id tag source requested table note")


class LangIdError(Exception):
    """A prompt the model does not declare. Never clamped — the run stops."""


# ── the model's own table ─────────────────────────────────────────────────────
class LanguageTable:
    """`languages.json`, as the model ships it. Not a copy, not a summary."""

    def __init__(self, data: dict, path: str):
        self.path = path
        self.prompt = dict(data.get("promptDictionary") or {})
        if not self.prompt:
            raise LangIdError(f"{path} has no promptDictionary — nothing to resolve against")
        self.auto_slot = int(data.get("autoSlot", 101))
        self.num_prompts = int(data.get("numPrompts", len(self.prompt)))
        # The declared set: every id the table names, plus the auto slot. An id
        # outside it is not "probably fine" — it is undeclared.
        self.ids = sorted(set(self.prompt.values()) | {self.auto_slot})
        self._by_id = {}
        for tag, i in self.prompt.items():
            best = self._by_id.get(i)
            # Prefer a region-qualified tag ("pt-BR") over the bare language
            # ("pt") when both name the same slot: the qualified one is what
            # both READMEs quote and it is unambiguous in a log line.
            if best is None or ("-" in tag and "-" not in best):
                self._by_id[i] = tag

    @classmethod
    def load(cls, path: str) -> "LanguageTable":
        with io.open(path, encoding="utf-8") as fh:
            return cls(json.load(fh), path)

    def tag_of(self, lang_id: int) -> str:
        return self._by_id.get(int(lang_id), f"id:{lang_id}")

    def lookup(self, tag) -> tuple | None:
        """(id, canonical key) for a language tag, or None if undeclared.

        Exact keys first; then case-insensitively; then the BCP-47 underscore
        form Windows APIs hand out ("pt_BR" -> "pt-BR"); then the primary
        subtag ("pt-AO" -> "pt"), which is the only lossy step here and it is
        recorded in the resolution note.
        """
        t = str(tag).strip()
        if not t:
            return None
        variants = (t, t.replace("_", "-"), t.replace("-", "_"))
        for v in variants:
            if v in self.prompt:
                return self.prompt[v], v
        low = {k.lower(): (v, k) for k, v in self.prompt.items()}
        for v in variants:
            if v.lower() in low:
                val, key = low[v.lower()]
                return val, key
        base = t.replace("_", "-").split("-")[0].lower()
        if base and base in low:
            val, key = low[base]
            return val, key
        return None


def table_candidates(model_dir: str | None) -> list:
    """Where the table may live, in the order that keeps it model-local.

    Only the fp16 export ships `languages.json`; int4 and int8 do not. The table
    describes the checkpoint's prompt embedding, which all three exports share,
    so a sibling export's copy is the same declaration — but it is named in the
    log rather than assumed. `docs/model-specs/original/fp16/languages.json` is
    the verbatim, sha256-verified copy kept in this repo.
    """
    out = []
    if model_dir:
        out.append(os.path.join(model_dir, "languages.json"))
        parent = os.path.dirname(os.path.abspath(model_dir))
        try:
            for name in sorted(os.listdir(parent)):
                p = os.path.join(parent, name, "languages.json")
                if os.path.isfile(p) and p not in out:
                    out.append(p)
        except OSError:
            pass
    out.append(os.path.join(REPO, "docs", "model-specs", "original", "fp16", "languages.json"))
    return out


def load_language_table(model_dir: str | None = None) -> LanguageTable:
    for p in table_candidates(model_dir):
        if os.path.isfile(p):
            return LanguageTable.load(p)
    raise LangIdError(
        "no languages.json found: looked in "
        + ", ".join(table_candidates(model_dir))
        + " — refusing to guess a language prompt"
    )


# ── the host's locale ─────────────────────────────────────────────────────────
def os_locale_tag() -> str | None:
    """The host's USER locale as a BCP-47 tag ("pt-BR"), or None.

    Windows is asked for the user's own locale — the one that decides the UI
    language — not the OS install language; the two differ on a machine
    installed in one language and set to another. MEASURED on this box:
    GetUserDefaultLocaleName -> 'pt-BR'. POSIX falls back to LC_ALL/LANG, then
    to the stdlib locale module.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(85)  # LOCALE_NAME_MAX_LENGTH
            n = ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
            if n and buf.value:
                return buf.value.replace("_", "-")
        except Exception:
            pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var)
        if v:
            return v.split(".")[0].split("@")[0].replace("_", "-") or None
    try:
        import locale

        loc = locale.getlocale()[0]
        if loc:
            return loc.replace("_", "-")
    except Exception:
        pass
    return None


# ── resolution ────────────────────────────────────────────────────────────────
def _as_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _refuse(value, table: LanguageTable, why: str) -> "LangIdError":
    lo, hi = table.ids[0], table.ids[-1]
    return LangIdError(
        f"lang_id {value!r} is NOT declared by this model ({why}). "
        f"{table.path} declares {len(table.ids)} prompt slots "
        f"(ids {lo}..{hi} named, plus autoSlot {table.auto_slot}; "
        f"e.g. 0=en-US, 12=pt-BR, 13=pt/pt-PT, {table.auto_slot}=auto). "
        "Refused rather than clamped: an undeclared id is an undefined embedding "
        "row, and silently falling back would put the wrong language in front of "
        "the model with no trace in the run. Fix the value (an id, a language tag "
        "like 'pt-BR', 'auto', or 'os') or list the slots with: "
        "py -3 worker/lang_prompt.py --list"
    )


def resolve_lang_id(requested, model_dir: str | None = None, table: LanguageTable | None = None) -> Resolution:
    """Resolve a requested prompt to the id the encoder will be fed.

    `requested` accepts every spelling a caller may hold:
      * an int          -> 12
      * a digit string  -> "12"  (the CLI hands everything over as text)
      * a language tag  -> "pt-BR", "pt", "pt_BR", "auto"
      * the sentinel    -> "os" / None, meaning the host's user locale
    Raises LangIdError, never a clamp.
    """
    if table is None:
        table = load_language_table(model_dir)
    req = requested
    raw = "" if req is None else str(req).strip()

    if req is None or raw == "" or raw.lower() in OS_LOCALE_ALIASES:
        tag = os_locale_tag()
        if not tag:
            return Resolution(
                table.auto_slot, table.tag_of(table.auto_slot), "os-locale-unknown", requested,
                table.path, "no host locale available -> model auto slot",
            )
        hit = table.lookup(tag)
        if hit is None:
            return Resolution(
                table.auto_slot, table.tag_of(table.auto_slot), "os-locale-fallback-auto", requested,
                table.path, f"host locale {tag!r} names no slot -> auto",
            )
        lang_id, key = hit
        lossy = "" if key.lower() in (tag.lower(), tag.replace("-", "_").lower()) else f" (matched {key})"
        return Resolution(
            lang_id, table.tag_of(lang_id), "os-locale", requested, table.path,
            f"host locale {tag!r}{lossy}",
        )

    if raw.lower() == "auto":
        return Resolution(
            table.auto_slot, table.tag_of(table.auto_slot), "auto", requested, table.path,
            "the model's own auto slot, asked for explicitly",
        )

    n = _as_int(raw)
    if n is not None:
        if n not in table.ids:
            raise _refuse(raw, table, "an integer outside the declared slot set")
        return Resolution(n, table.tag_of(n), "id", requested, table.path, "")

    hit = table.lookup(raw)
    if hit is None:
        raise _refuse(raw, table, "not a language tag in the prompt dictionary")
    lang_id, key = hit
    note = "" if key.lower() == raw.lower() else f"matched {key!r}"
    return Resolution(lang_id, table.tag_of(lang_id), "tag", requested, table.path, note)


def validate_lang_id(value, table: LanguageTable) -> tuple:
    """(id, tag) for an already-concrete prompt, or LangIdError. No clamping."""
    return (lambda r: (r.lang_id, r.tag))(resolve_lang_id(value, table=table))


# ── the table, as a readable list ─────────────────────────────────────────────
def _print_list(table: LanguageTable, out=sys.stdout) -> None:
    out.write(f"table      : {table.path}\n")
    out.write(f"numPrompts : {table.num_prompts}\n")
    out.write(f"autoSlot   : {table.auto_slot}\n")
    out.write(f"host locale: {os_locale_tag()}\n")
    out.write("slots      :\n")
    for i in table.ids:
        tags = sorted(t for t, v in table.prompt.items() if v == i)
        out.write(f"  {i:>4}  {', '.join(tags) if tags else '(autoSlot)'}\n")


def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Resolve Sotto's ASR language prompt from the model's own table.")
    ap.add_argument("--list", action="store_true", help="print every declared slot and the host locale")
    ap.add_argument("--model-dir", default=None, help="model dir to look next to (default: the shipped int8 export)")
    ap.add_argument("--lang-id", default=None, help="the value to resolve (id, tag, 'auto', 'os')")
    a = ap.parse_args(argv)
    model_dir = a.model_dir or os.path.join(HERE, "models", "nemotron-3.5-asr-streaming-0.6b-int8")
    try:
        if a.list:
            _print_list(load_language_table(model_dir))
            return 0
        r = resolve_lang_id(a.lang_id, model_dir)
    except LangIdError as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 2
    sys.stdout.write(
        f"lang_id={r.lang_id} tag={r.tag} source={r.source} requested={r.requested!r} table={r.table}\n"
    )
    if r.note:
        sys.stdout.write(f"note={r.note}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
