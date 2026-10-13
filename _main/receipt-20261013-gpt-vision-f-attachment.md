# The vision instrument exists, and `-f` will not carry a PNG

2026-10-13. Recorded so the next lane does not spend 20 minutes rediscovering it.

## The prompt that made me try

`_moved/aireplay/AGENTS.md` says, of open design questions: "Ask `gpt` (consultgpt) ... it is
a real browser, no API key, and it HAS VISION (the only instrument here that can look at the
owner mockups)." Since **I cannot see images** (read_image refuses: this model does not
declare image input), that read as the missing instrument for item 10.

## What happened

```
gpt --no-code -f zip-E-panels.png panel-live-default.png \
    --session zip-vs-live --prompt-file I:/cc-tmp/pergunta.txt
```

* `--no-code` and `--prompt-file` are exactly what `docs/tools/consultgpt.md` prescribes, and the
  prompt file was written UTF-8 outside the shell to avoid quoting.
* **`-f` attaches files as TEXT.** The 406 698 B PNG became **423 384 characters**, and the
  splitter announced a plan of **13 chunks in multi-turn mode**. It was pasting the bytes of
  a screenshot into ChatGPT as prose.
* Result: ChatGPT is not responding, no response after 57.3 seconds, an initial attempt that
  produced NO response, then its own Layer 1 soft retry. Killed.

## Verified the way the manual demands

`docs/tools/consultgpt.md` warns that the rc does NOT denounce this failure and that the FILE
CONTENT must be checked instead. Done: resposta.txt = 4 791 B, it carries the not-responding
warning, and it has **no** Executive Summary or Findings block. **The question was not answered.**

Cleanup verified after the kill: **0** consultgpt processes, **0** headless browsers, and the
owner app untouched (pids 44684 + 13936).

## What this does NOT establish

**It does not establish that gpt cannot see.** The AGENTS.md claim is probably TRUE and refers
to the path that produced the round of the five designs (6.2 KB of useful content) -- a path that
is not `-f image.png`. The tool has `--headed` and `--headed-offscreen`, exits for `@file`
injection, and a session store; **how the mockups were actually shown to it is not documented in
the how-to**, and whoever reopens this should read `gpt help` in full and look for an image or
screenshot flag before concluding anything about vision.

## Where that leaves the fidelity measurement

**The two renders exist** (`docs/design-intake/rendered/`), produced by the same engine at the
same size, and **the owner can look at them right now** -- that part is done and needs nothing more
from me. What is still missing is a machine that can describe what is in them, and the candidate
for that is `gpt`, reached by a path this receipt does not contain.

## FOLLOW-UP: the full option list, and there is no image path

`gpt help` is 12 213 B and enumerates **39 options**. Every one of them is text or code
oriented: `--files` (code context), `--lines`, `--cite-extract` / `--cite-context` /
`--cite-followup` / `--cite-min-lines`, `--codeintel`, `--prompt`, `--prompt-file`, `--repo`,
`--include-dir`, `--harness`, `--context-window`, `--topic`, `--human`, `--session`,
`--keep-alive`, `--split-parallel`, `--split-multi-turn`, `--auto`, `--both`, `--ouroboros`,
`--audit`, `--verbose`, `--dry-run`, and the browser-visibility flags.

A grep of the same file for `image|screenshot|vision|png|jpg|attach|photo` returns FOUR lines,
and none is a capability: line 27 is the `--files` description ("attach files for code
context"), line 141 is the same flag in the summary table, line 143 is `--no-code`, and line
198 is `reconnect | Re-attach to a kept-alive session`. **There is no flag that sends an image.**

**So the AGENTS.md sentence cannot be exercised through this CLI as written.** That is not the
same as calling it false: the sentence describes what the TOOL is for, and the round of the five
designs may well have been done by showing the mockups some other way -- but the how-to does not
say which way, and 39 documented options do not contain it. **Whoever needs a machine that can
describe a screenshot has to find that path first, and it is not in `gpt help`.**

## What this leaves, stated once and plainly

The renders are produced, they are in the repository, they were made by one engine at one size,
and **the only remaining instrument is the owner looking at them**. Everything else about item 10
that can be measured by a machine has been: 50 of 50 designs implemented, 0 recolours among 45
themes, every zip design mapped to its live theme, and the structural difference for zip C
measured at 0 before and 63 after. The last question -- does it LOOK right -- has no machine
here that can answer it.

## CLOSED: three paths tried, no vision on this box

2026-10-13. The search for a machine that can describe the two renders is over, and the
answer is negative. Three paths, all measured:

| path | result |
|---|---|
| this agent (`read_image`) | refuses: *model "deepseek-v4.1-flash" does not declare image input* |
| a spawned subagent, asked to look and to say so if it could not | **the SAME model**, same refusal: `SEM VISAO NESTE MODELO` |
| `gpt` / consultgpt | 39 documented options, none of which sends an image |

**The subagent behaved exactly as instructed, and that is worth recording**: it made the
two `read_image` calls, hit the refusal, STOPPED, answered only `SEM VISAO NESTE MODELO`,
and explicitly refused to substitute file sizes, metadata or repository reading for a look
at the pixels. It answered none of the four design questions because it had seen nothing.
That is the correct outcome for an instrument that cannot see -- and the opposite of what
this session has had to retract four times.

## So the residual is named precisely

**Everything about item 10 that a machine can measure has been measured**: 50 of 50 zip
designs implemented, 0 recolours among 45 themes, every zip design mapped to its live theme,
zip C structural difference 0 before and 63 after, both generators proven reproducible, and a
reference mockup built and rendered beside the live panel by one engine at one size.

**The one remaining question -- does it LOOK like the zip -- has no instrument here.** It is
not unmade work and it is not a measurement someone forgot to run; it is a question this box
cannot answer, verified along every path available.

The renders are at `docs/design-intake/rendered/` and are the deliverable for that question.
