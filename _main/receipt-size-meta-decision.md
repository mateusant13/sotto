# RECEIPT — `--size-meta`: THE DESIGN DECISION I DID NOT TAKE

Date 2026-10-13. Found by the base-themes lane and left open BY ITS CHOICE, then
measured again here. **This is the clearest design decision still outstanding.**

## The defect, measured

Every `pd-*` design declares `--size-meta` with its OWN value, and **no rule reads it**:

| file | design | `--size-meta` |
|---|---|---|
| `panel-designs.css:122` | `pd-tele` | 11px |
| `panel-designs.css:841` | `pd-bcast` | 9.5px |
| `panel-designs.css:1611` | `pd-mano` | 10px |
| `panel-designs.css:2346` | `pd-cine` | 13px |
| `panel-designs.css:3074` | `pd-instr` | 10px |
| `theme-1.css:134` (+ theme-2..5) | the five base themes | 10px |

**Ten declarations, zero readers.** And `cinematic.css` declares it 25 times with only
10 readers — the shared set block reads it once for all of them.

## Why it is a DECISION and not a bug fix

The rule that should read it is the CHROME block, and **that block is SHARED** and its
`font-size` literals are **PER FAMILY**. The lane measured what happens when the rule
starts reading the token: **the painted chrome size of FIVE of the ten designs
changes** — `pd-tele`, `pd-bcast`, `pd-mano`, `pd-cine`, `pd-instr`.

**The five designs of the second zip paint their chrome at the size of the FIRST zip
design of the same family.** That is the defect, and it is a real one under the owner
rule: *"cada tema encontrado dentro dos .zip, fiquem com o design IGUAL"*.

## Why I did not fix it

Because taking it correctly needs a per-design check — what size each zip MANDATES,
and which rule should read the token for each — and I did not have the context budget
to do that properly. **A design change to five visible designs, made in a hurry, is
how a design gets broken.** The lane reached the same conclusion and declined for the
same reason.

## What the owner needs to decide

Should each `pd-*` design paint its chrome at ITS OWN `--size-meta`, as its zip
mandates, even though that visibly changes five designs? Under his stated rule the
answer is yes. The alternative is to delete the ten dead declarations and keep the
family-shared sizes, which is cheaper and visibly changes nothing.

**Either way the ten dead declarations should not stay.** What must not happen is the
token staying declared-and-unread, which is the same defect class this session closed
four times already.
