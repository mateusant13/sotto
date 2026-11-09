# Receipt — history `ctx1=` codec parity (malformed escapes, NEL, U+FEFF)

Date: 2026-11-09 · Lane: CodecParity · Handoff item 3 ("Decide codec edge parity")

## Verdict

`fixed, NOT runtime-verified` (no app was launched; this is a pure codec/gate change).

The two readers of the SAME on-disk format are `app/webview/history_context.py`
(`urllib.parse.unquote`) and `app/panel/history-context-store.js`
(`decodeURIComponent`). They diverged on exactly the three input classes in the
assignment. **The Python reader is canonical** (it keeps data where Node erased
the whole field, and Unicode White_Space is what Python's `str.split()` uses),
and the Node reader was aligned to it in ONE file:
`app/panel/history-context-store.js`.

## Why these inputs are inside the supported contract

Quoting the writers' encoders, both of which produce the token body:

`app/webview/history_context.py:encode()`:

```python
        quoted = quote(value, safe='')
```

`app/panel/history-context-store.js:percentEncode()`:

```js
  return encodeURIComponent(String(value == null ? '' : value))
    .replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);
```

Measured (`python -c "from urllib.parse import quote; ..."`):

```
'a\x85b'  -> a%C2%85b
'a\ufeffb' -> a%EF%BB%BFb
'100%zz'  -> 100%25zz
'50%'     -> 50%25
```

Consequence, stated per class:

| class | can a WRITER emit it? | contract |
|---|---|---|
| `%zz`, `%2`, trailing `%`, `%E0%A4` (invalid UTF-8) | **No** — both encoders escape every `%` to `%25` and emit only `%HH`, so a malformed escape can only come from a hand-edited or corrupted line | outside the write path, INSIDE the read path: the line exists, and erasing a field is the wrong answer |
| U+0085 (NEL), U+FEFF | **Yes** — both are ordinary title bytes and both encoders write `%C2%85` / `%EF%BB%BF` | inside the contract: a real window title carrying one read differently on each host |
| ordinary records | Yes | positive control |

So the alignment is not a nicety: the whitespace edge is reachable by the
product, and the malformed-escape edge must not cost the line its context.

## Change (one place)

`app/panel/history-context-store.js`:

1. `percentDecode()` — a byte-exact mirror of
   `urllib.parse.unquote(value, 'utf-8', 'replace')`: `%HH` decodes, a `%` not
   followed by two hex digits stays literal, the joined bytes decode once with
   `TextDecoder('utf-8', {fatal:false, ignoreBOM:true})` (non-fatal → U+FFFD;
   `ignoreBOM` because Python's utf-8 codec KEEPS a leading U+FEFF),
   `no '%' → returned untouched` (matching `unquote`'s short circuit), a
   non-ASCII character beside an escape raises and the field is omitted exactly
   as Python's `UnicodeError` branch does, and U+DC80..U+DCFF is the
   `surrogateescape` byte. `decodeContext()` now calls it instead of
   `decodeURIComponent` (which threw on every malformed input and the catch
   erased the field).
2. `collapseSpace()` — the field and the URL now share ONE whitespace
   reduction using Unicode White_Space (the `str.split()` set: TAB/LF/FF/CR,
   U+0085, U+00A0, U+1680, U+2000–U+200A, U+2028, U+2029, U+202F, U+205F,
   U+3000), instead of `\s` (which eats U+FEFF and misses U+0085). The trailing
   strip after the bounded slice is a SPACE strip, not `.trim()` (`trim` eats
   U+FEFF).
3. `cleanContextValue()` bounds by CODE POINT (`Array.from`), like Python's
   `value[:MAX_LEN]`; a UTF-16 `.slice()` cut a surrogate pair in half on a
   non-BMP title.

The file header now documents both edges and the canonical direction.

## Side-by-side, BEFORE the change

Command: `python C:/Users/Administrador/AppData/Local/Temp/codec-parity-probe.py`
(Python `history_context.decode` vs Node `history-context-store.decodeContext`
on the same token body; node launched through `_main/hidden-launch.py`).

```
[A malformed escape] pct-zz: token='t:100%zz'
    py  : '{"viewingTitle": "100%zz"}'
    node: '{}'
    parity: DIVERGES
[A malformed escape] pct-trailing: token='t:50%'
    py  : '{"viewingTitle": "50%"}'
    node: '{}'
    parity: DIVERGES
[A malformed escape] pct-short: token='t:a%2b'
    py  : '{"viewingTitle": "a+"}'
    node: '{"viewingTitle": "a+"}'
    parity: SAME
[A malformed escape] pct-invalid-utf8: token='t:%E0%A4'
    py  : '{"viewingTitle": "�"}'
    node: '{}'
    parity: DIVERGES
[A malformed escape] pct-mixed: token='t:a%20b%zzc'
    py  : '{"viewingTitle": "a b%zzc"}'
    node: '{}'
    parity: DIVERGES
[B whitespace] nel-0x85: token='t:a\x85b'
    py  : '{"viewingTitle": "a b"}'
    node: '{"viewingTitle": "a\x85b"}'
    parity: DIVERGES
[B whitespace] feff: token='t:a\ufeffb'
    py  : '{"viewingTitle": "a\ufeffb"}'
    node: '{"viewingTitle": "a b"}'
    parity: DIVERGES
[B whitespace] nel-in-url: token='u:https%3A%2F%2Fexample.com%2Fa%C2%85b'
    py  : '{"viewingUrl": "https://example.com/a%20b"}'
    node: '{"viewingUrl": "https://example.com/a%C2%85b"}'
    parity: DIVERGES
[C ordinary] plain: token='a:chrome.exe|t:main.py'
    py  : '{"sourceApp": "chrome.exe", "viewingTitle": "main.py"}'
    node: '{"sourceApp": "chrome.exe", "viewingTitle": "main.py"}'
    parity: SAME
[C ordinary] youtube-url: token='u:https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DMOZIBMBHK-8'
    py  : '{"viewingUrl": "https://www.youtube.com/watch?v=MOZIBMBHK-8"}'
    node: '{"viewingUrl": "https://www.youtube.com/watch?v=MOZIBMBHK-8"}'
    parity: SAME

PARITY: FAIL (3/10 same)
```

Note `t:a%2b` is a VALID escape with lowercase hex: both readers always agreed
there, which is why it is kept as a control inside the malformed class.

## Side-by-side, AFTER the change

Same command, same inputs:

```
[A malformed escape] pct-zz: token='t:100%zz'
    py  : '{"viewingTitle": "100%zz"}'
    node: '{"viewingTitle": "100%zz"}'
    parity: SAME
[A malformed escape] pct-trailing: token='t:50%'
    py  : '{"viewingTitle": "50%"}'
    node: '{"viewingTitle": "50%"}'
    parity: SAME
[A malformed escape] pct-short: token='t:a%2b'
    py  : '{"viewingTitle": "a+"}'
    node: '{"viewingTitle": "a+"}'
    parity: SAME
[A malformed escape] pct-invalid-utf8: token='t:%E0%A4'
    py  : '{"viewingTitle": "�"}'
    node: '{"viewingTitle": "�"}'
    parity: SAME
[A malformed escape] pct-mixed: token='t:a%20b%zzc'
    py  : '{"viewingTitle": "a b%zzc"}'
    node: '{"viewingTitle": "a b%zzc"}'
    parity: SAME
[B whitespace] nel-0x85: token='t:a\x85b'
    py  : '{"viewingTitle": "a b"}'
    node: '{"viewingTitle": "a b"}'
    parity: SAME
[B whitespace] feff: token='t:a\ufeffb'
    py  : '{"viewingTitle": "a\ufeffb"}'
    node: '{"viewingTitle": "a\ufeffb"}'
    parity: SAME
[B whitespace] nel-in-url: token='u:https%3A%2F%2Fexample.com%2Fa%C2%85b'
    py  : '{"viewingUrl": "https://example.com/a%20b"}'
    node: '{"viewingUrl": "https://example.com/a%20b"}'
    parity: SAME
[C ordinary] plain: token='a:chrome.exe|t:main.py'
    py  : '{"sourceApp": "chrome.exe", "viewingTitle": "main.py"}'
    node: '{"sourceApp": "chrome.exe", "viewingTitle": "main.py"}'
    parity: SAME
[C ordinary] youtube-url: token='u:https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DMOZIBMBHK-8'
    py  : '{"viewingUrl": "https://www.youtube.com/watch?v=MOZIBMBHK-8"}'
    node: '{"viewingUrl": "https://www.youtube.com/watch?v=MOZIBMBHK-8"}'
    parity: SAME

PARITY: PASS (10/10 same)
```

## Oracle extended (existing instrument, not a new one)

`_main/history-context-oracle.py` — it already owned this reader and compared
both hosts through `CODEC_FIXTURE`. Added:

- `CODEC_FIXTURE`: `nel-no-titulo`, `bom-no-titulo`, `nel-no-caminho`,
  `nao-bmp-no-limite` (normalise → encode → decode parity, arms `p-*`).
- `TOKEN_FIXTURE` + `JS_NODE_PROBE`'s `rawDecoded`: raw token bodies decoded
  WITHOUT either encoder (`q-escapado-zz`, `q-escapado-curto`,
  `q-percent-final`, `q-utf8-invalido`, `q-valido-e-invalido`,
  `q-escape-no-url`, `q-nel-cru`, `q-bom-cru`, `q-bom-escapado`,
  `q-varios-campos`).
- Three mutants: `n12-node-decode-estrito` (back to `decodeURIComponent`),
  `n13-node-espaco-do-js` (back to `\s`), `n14-node-bom-comido`
  (`TextDecoder` without `ignoreBOM`).
- Oracle defect found by its own neg-arm: the child's JSON was parsed with
  `str.splitlines()`, which splits on U+0085/U+2028, so a reader that PRESERVES
  NEL made `n13` die with `JSONDecodeError` (`NEG-ARM LOAD-FAILED`) instead of
  going red — a parse failure is not a verdict. Fixed once in `_json_line()`
  (`rsplit('\n', 1)[-1]`), used by all four probe parsers.

Results:

```
$ python _main/history-context-oracle.py
VERDICT: PASS arms 116/116

$ python _main/history-context-oracle.py --neg-arm
ok  n12-node-decode-estrito -> RED: q-escapado-zz,q-percent-final,q-utf8-invalido,q-valido-e-invalido,q-escape-no-url
ok  n13-node-espaco-do-js -> RED: p-nel-no-titulo,p-bom-no-titulo,p-nel-no-caminho,q-nel-cru,q-bom-cru,q-bom-escapado
ok  n14-node-bom-comido -> RED: q-bom-escapado
NEG-ARM PASS mutants 14/14
```

(All other mutants still caught: `n1`..`n11` each printed `ok ... -> RED`.)

## Not done / not verified

- No battery run (`_main/_audit-verify-all.cmd` untouched and not executed).
- No app launch, no window, no synthetic input; no runtime claim.
- `worker/sotto_worker.py`, `app/webview/sotto_webview.py` (including its
  history-context region), `_main/code-health-baseline.json` untouched.
- The transient probe lives at
  `C:/Users/Administrador/AppData/Local/Temp/codec-parity-probe.py`, outside the
  repo; no scaffold was added to the tree.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: CodecParity
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodecParity']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodecParity']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T16:53:15.444436+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodecParity']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodecParity']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — `bug-hunt-sotto` was not invoked. This was a
  parity/contract decision found by executing both readers, not a reported
  defect in the product, so I used the oracle-as-instrument path; the measured
  before/after output stands in place of a repro capsule. A different call would
  have been to treat the NEL/U+FEFF divergence as a defect cluster (it is
  reachable from a real title) and run the 11 steps. If this is repeated, I
  would run step 3 (repro in a file) from the start.
- **verificacao adicional** — an end-to-end `HISTORY_APPEND` with a
  `viewingTitle` containing U+0085 through BOTH writers and then reading the
  same line back with the OTHER host, i.e. `x1`/`x2` arms with the edge title
  instead of `main.py`. Cheap (the oracle already has both hosts wired) and not
  run; the unit-level `p-`/`q-` arms cover the codec but not the shell's
  `_history_provenance` path for that title.
- **checkboxes novas** — mechanical: `python _main/history-context-oracle.py
  --neg-arm` must print `mutants N/N` with `N == ` the number of declared
  mutants, AND every mutant line must be `ok ... -> RED`; a `LOAD-FAILED` line
  is a gate failure, not a skip. Plus: any arm whose output can carry
  U+0085/U+2028 must parse with `rsplit('\n')`, never `splitlines()`.
- **review por outro subagente** — `sim-com-escopo` — review the exact
  `percentDecode`→`unquote` equivalence (notably `errors='replace'` grouping of
  invalid UTF-8 runs and the `surrogateescape` branch) and whether the canonical
  direction should instead have been "Node is canonical".
- **gate-doubt** —
  - `verde-de-verdade:` `VERDICT: PASS arms 116/116` was a real run on the
    shipped bytes (`app/panel/history-context-store.js` untracked-new file, read
    from disk by both hosts); `NEG-ARM PASS mutants 14/14` is also real, and it
    caught a defect in the instrument itself (`_json_line`) before it could pass
    vacuously. Non-vacuity is proven per mutant by the printed RED arm names; a
    green run cannot pass by construction because `judge()` compares Node output
    against an independently computed Python value, including the raw-token arms
    that bypass both encoders.
  - `falta-no-gate:` the oracle still does not exercise the SHELL's write path
    with an edge title (`_history_provenance` → `encode`), nor the panel gallery
    reading NEL/FEFF-typed titles; a future change to `history_append`'s context
    stamping would not be caught by the `p-`/`q-` arms.
  - `gate-melhor:` add `x3` — write a line via the shell with
    `viewingTitle='a\x85b'`, read it with `js_read`, expect `a b`; INPUT that
    must leave it RED: revert `collapseSpace` to `\s` and the arm returns
    `a\x85b`.
- **confianca** — `alta` for codec parity (executed, both directions, negative
  arm non-vacuous); `media` for the claim that no other reader of this token
  exists in the tree (`grep -rn "decodeURIComponent"` leaves only
  `surface.js`'s hash handling).
- **nao verificado** — runtime read of a hand-edited history file in the app; the
  panel gallery rendering NEL/U+FEFF titles; the battery wiring of the extended
  oracle; `x1`/`x2` cross-host arms with an edge title.
