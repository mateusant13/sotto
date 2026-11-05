# Recibo — censo dos dois roots temporarios (`G:/Temp`, `I:/cc-tmp`) — 2026-11-05

**Ordem:** censo read-only. **Nada foi apagado.** Nenhuma janela foi aberta, nenhum modelo carregado,
nenhum audio renderizado. O app vivo do dono nao foi tocado.

**Estado do entregavel: `DARK`** — o censo e' leitura pura (nao ha nada para "ligar").

---

## 1. Instrumento — o que foi corrido, e o que NAO foi possivel correr

Esta lane **nao tem shell, nem `bash`, nem `python`, nem `du`**. Toolset disponivel: `read`, `grep`,
`glob`, `web_search`, `write`. Confirmado por duas vias:

- `read proc://` → so' devolve `CdpBootArms [task] running` e `WordSplitFast [task] running`. **Nao ha
  service com stdin** (nem REPL de python), portanto `write proc://<id>` nao executa nada.
- `grep` sobre estes roots **expira aos 30 s** (ver erro de instrumento, abaixo).

Logo **todos os bytes abaixo vem do listador de directorias** (`read <dir>`), que faz o equivalente a
`os.scandir` + `st_size`/`st_mtime` e imprime tamanhos com 1 decimal em unidades 1024-based.

### O limite duro deste instrumento (a razao do "piso")

O listador imprime `tamanho` para **ficheiros** e **apenas a `mtime` para directorias**:

```
  - models-src/ 14h ago             <- directoria: sem bytes
    - ultra.safetensors 1.2GB 1d ago <- ficheiro: com bytes
```

Nenhum `du` de subarvore existe; `read` numa subarvore devolve os filhos **sem** tamanho agregado e
corta em 12 filhos (`… N more`). Por isso:

- **bytes exactos** para todo o ficheiro cujo tamanho o listador imprimiu (profundidade <= 1 do root);
- **bytes UNKNOWN** para directorias com conteudo mais fundo — e sao exactamente essas que explicam a
  maior parte dos 14 GB / 4.8 GB (perfis `EBWebView`, `.git`, clones de worktree).

**O dono (ou o Main, que tem shell) deve fechar o numero com uma linha:**

```
du -sb /g/Temp /i/cc-tmp
du -sb /g/Temp/*    | sort -n | tail -25
du -sb /i/cc-tmp/*  | sort -n | tail -25
# PowerShell: Get-ChildItem -Force -Recurse | Measure-Object -Property Length -Sum
```

### Comandos exactos por tabela

| tabela | chamada que a produziu |
|---|---|
| §2 totais | `read G:/Temp` (15 851 linhas, paginado), `read I:/cc-tmp` (completa) |
| §3 top-25 | `read G:/Temp:1-1599`, `:1600-3200`, `:3200-4800` + `read I:/cc-tmp` |
| §4 histograma | sondas de offset: `read G:/Temp:760-768` (1 h), `:1100-1108` e `:1215-1225` (2 h), `:8100-8110` (9 h), `:11400-11408` (14 h), `:11990-12000`, `:14700-14710`, `:14800` (1 d), `:15600-15608` (1 d), `:15835-15851` (3 d) |
| §4 homogenidade | amostras `read G:/Temp:6000-6008`, `:9000-9008`, `:13000-13008` |
| §5 perfis WebView2 | `glob G:/Temp/*/EBWebView` |
| §5 `.bun-*`/`.ses` | `glob G:/Temp/.bun-*;G:/Temp/.ses;G:/Temp/.ses*` |
| §7 familias de mutante | `glob G:/Temp/yt-wiring-*`, `G:/Temp/freeze-oracle-*`, `G:/Temp/hist-mut-*`, `G:/Temp/paintrow-*;G:/Temp/churn-neg-*;G:/Temp/capbudget-*` — todas devolveram a lista **completa** (nenhum `… N more`) |

**Erro de instrumento registado:** `grep` sobre `G:/Temp;I:/cc-tmp` **expira aos 30 s** (dois padroes
tentados: `Directory of|bytes free|Total files|du -sh` e um de tamanhos) — 15 k+ entradas com centenas
de `*.txt`/`*.log` tornam a varredura textual inviavel. Nao repetido; substituido por sondas de offset.

**Amostragem da regiao nao lida.** Li as linhas `1–4 800` de 15 851. Para confirmar que o resto nao
esconde um ficheiro grande (que falsificaria o top-25) sondei `:6000`, `:9000`, `:13000`: todas
mostram KB (probes `0B`–`1.1KB`, `__PSScriptPolicyTest_*.psm1` 69 B, logs 0 B) e directorias com
`repo/`, `yt-dlp-cache/`, `archive.db 0B`. Nenhum ficheiro de escala GB na regiao amostrada.

---

## 2. Totais

| root | total | fonte |
|---|---|---|
| `G:/Temp` | **14 GB** | **reportado pelo dono** (brief). Nao re-medido: sem `du`. |
| `I:/cc-tmp` | **4.8 GB** | **reportado pelo dono** (brief). Nao re-medido: sem `du`. |
| `G:/Temp` — linhas de listagem | 15 851 → ~15 892 durante o censo (lanes a escrever) | `read G:/Temp`, rodapes `Showing lines 1-1599 of 15851` / `[41 more lines … :15852]` |
| `I:/cc-tmp` — linhas | ~1 100 (listagem **completa**, sem rodape de truncagem) | `read I:/cc-tmp` |
| `I:/cc-tmp/models-src/ultra.safetensors` | **1.2 GB** (um unico ficheiro) | listador |
| `G:/Temp` — 127 snapshots de mutante | **~292 MB** medidos (§7) | listador + `glob` |

Calibracao: `_main/receipt-20261101-disk-census.md` mediu `du -sh /i/cc-tmp` = **28 GB / 11 212
entradas**, limpou com politica ">3 dias por `mtime`" e ficou **392 MB**. `I:/cc-tmp` voltou a
**4.8 GB em 4 dias** — todo o crescimento e' desta semana.

---

## 3. Top 25 entradas por tamanho (medidas)

Só entradas cujo tamanho o instrumento imprimiu. `proc` = processo dono **inferido** do nome; `psutil`
nao e' executavel aqui (§1), portanto **nao houve `open_files`**. `[INF]` = inferencia, nao medicao.

| # | caminho | bytes (impresso) | mtime | proc dono `[INF]` |
|---|---|---|---|---|
| 1 | `I:/cc-tmp/models-src/ultra.safetensors` | 1.2 GB | 1 d | pesos ASR do produto (parakeet-ultra) — **vivo, nao apagar** |
| 2 | `G:/Temp/092b6d27-30c8-41a5-ac40-5e96228097e3.tmp` | 379.3 MB | 34 m | `GetTempFileName`/`tempfile` de lane viva |
| 3 | `G:/Temp/b2-burst-ds4nggdh/jobs.sqlite3` | 49.3 MB | 2 h | jcode job-runtime (teste de burst) |
| 4 | `G:/Temp/b2-burst-35eozr3n/jobs.sqlite3` | 49.3 MB | 3 h | idem |
| 5 | `G:/Temp/b2-burst-4lbnd233/jobs.sqlite3` | 49.3 MB | 3 h | idem |
| 6 | `G:/Temp/b2-burst-jr0480tn/jobs.sqlite3` | 49.3 MB | 2 h | idem |
| 7 | `I:/cc-tmp/webview-run-before-lane.log` | 44.6 MB | 2 d | log de arranque do `sotto_webview` (morto) |
| 8 | `I:/cc-tmp/log-before-run.log` | 41.5 MB | 6 d | log de arranque (morto) |
| 9 | `G:/Temp/b64fa995-42fc-48c3-9868-d87f6675bc1d.tmp` | 16.9 MB | 26 m | `tempfile` de lane viva |
| 10 | `G:/Temp/b2-livecopy-5_h3lhxu/live-copy.sqlite3` | 14.6 MB | 2 h | jcode job-runtime |
| 11 | `G:/Temp/b2-livecopy-tr7ahimb/live-copy.sqlite3` | 14.6 MB | 2 h | jcode job-runtime |
| 12 | `G:/Temp/0b96078a-33f5-416c-a2a7-b3b3676b11ee.tmp` | 11.0 MB | 11 m | `tempfile` de lane viva |
| 13 | `G:/Temp/b2-dedupe-capmau3s/jobs.sqlite3` | 10.9 MB | 2 h | jcode job-runtime |
| 14 | `G:/Temp/b2-dedupe-dc09o0zw/jobs.sqlite3` | 10.9 MB | 2 h | jcode job-runtime |
| 15 | `G:/Temp/b2-dedupe-d510l7az/jobs.sqlite3` | 10.9 MB | 3 h | jcode job-runtime |
| 16 | `G:/Temp/b2-dedupe-gjk8alsu/jobs.sqlite3` | 10.9 MB | 3 h | jcode job-runtime |
| 17 | `G:/Temp/aw2/libaws_lc_sys-f96ebe167dc32fbe.rlib` | 7.9 MB | 2 h | `rustc`/`cargo` (build de lane) |
| 18 | `G:/Temp/awslc/libaws_lc_sys-f96ebe167dc32fbe.rlib` | 7.9 MB | 3 h | idem (**duplicado** do #17) |
| 19 | `G:/Temp/b2-wal-zzyh3pvw/jobs.sqlite3` | 3.6 MB | 2 h | jcode job-runtime (teste WAL) |
| 20 | `I:/cc-tmp/freeze-census-live.log` | 2.6 MB | 5 h | sonda de freeze (lane viva) |
| 21 | `G:/Temp/2d23094e-ce51-4702-bd59-aa92f2c17ab0.tmp` | 2.5 MB | 3 h | `tempfile` de lane |
| 22 | `G:/Temp/605cdd92-8f91-4062-bb8c-42e1192f50a7.tmp` | 2.2 MB | 3 h | `tempfile` de lane |
| 23 | `G:/Temp/wv2repair/MicrosoftEdgeWebview2Setup.exe` | 1.8 MB | 28 m | instalador WebView2 (lane de reparacao) |
| 24 | `G:/Temp/b96d9609-8d8c-4c54-9b37-ff1559d9a48e.tmp` | 1.3 MB | just now | `tempfile` de lane viva |
| 25 | `G:/Temp/92f61763-0daf-4d6c-bb26-3d19cb5264da.tmp` | 1.3 MB | 1 h | `tempfile` de lane |

**Classe repetida que domina a contagem (127 directorias, ~292 MB medidos — §7):** copias de mutante de
~1.0–1.1 MB (`sotto_webview_mut.py`, `*_m1..m5.py`, `shell_mutant.py`, `cap_removed.py`,
`route_removed.py`, `sink_removed.py`).

**Entradas grandes conhecidas com bytes UNKNOWN** (directorias, sem `du`):

| caminho | mtime | porque e' grande `[INF]` | proc dono `[INF]` |
|---|---|---|---|
| `G:/Temp/*/EBWebView` (**12** perfis, §5) | 16 m – 9 h | perfil WebView2 completo (`Default/`, `GrShaderCache/`, `ShaderCache/`, `Safe Browsing/`, `component_crx_cache/`) — tipicamente 100–400 MB cada | `msedgewebview2.exe` do painel |
| `G:/Temp/jcode-ws/` | 1 h – 4 d | **139** workspaces (12 + `… 127 more`) | jcode |
| `G:/Temp/jcode-bg-tasks/` | 1 h – 1 d | **219** ficheiros (12 + `… 207 more`) | jcode |
| `G:/Temp/gitattr-verify/` | 34 m (`.agents` 1 d) | arvore de repo (`app/`, `worker/`, `tools/`, `scripts/`, `runs/`, 47 ficheiros de topo) | lane git-attributes |
| `G:/Temp/pytest-of-Administrador/` | 36 m – 1 d | 18 subdirs `pytest-*` | pytest de lanes |
| `G:/Temp/.tmp*/repo`, `tmp.*/repo`, `rp-packet-*/repo`, `.tmp*/durable-state`, `.tmp*/optchat` | 1 h – 3 d | clones de repo / estado | builders de lane |
| `I:/cc-tmp/nemo-venv/` | 1 d | venv (`Scripts/`, `Lib/`, `Include/`) | instalar de `nemo` (1 d) |
| `I:/cc-tmp/cdp-panel2/` | 2 d | perfil Chrome (26+ subdirs) | Chrome CDP (morto) |
| `I:/cc-tmp/torchinductor_Administrador/` | 1 d | cache de compilacao torch | python/torch (morto) |
| `I:/cc-tmp/headtree/`, `old-tree/`, `deepinfer/.git`, `ark_asr_hf_home/` | 1 d – 4 d | arvores `.git`/repo | lanes antigas |

---

## 4. Histograma de idade

`G:/Temp` — a listagem vem **ordenada por `mtime` descendente**, portanto as fronteiras foram
localizadas por offset de linha. Total 15 851 linhas = **entradas de topo + 1 nivel de filhos** (nao e'
contagem pura de entradas; e' a metrica que o instrumento permite).

| banda | linhas (offset) | quota | evidencia |
|---|---|---|---|
| `<= 1 h` | `1 – ~1 050` | **~6.6 %** | 1 h em `:760`; 2 h ja' em `:1100` e `:1215` |
| `<= 24 h` (1 h–1 d) | `~1 050 – ~11 450` | **~65.6 %** | 9 h em `:8100`; 14 h em `:11400`; 1 d a partir de `:11990` |
| `<= 7 d` (1 d–3 d) | `~11 450 – 15 892` | **~27.8 %** | 1 d em `:14700` e `:15600`; **3 d** em `:15835-15851` (fim da listagem) |
| `> 7 d` | **0 linhas** | **0 %** | o fim da listagem e' `3d ago` |

Amostra medida por banda: `<=1h` → `b96d9609…tmp` 1.3 MB · `<=24h` → `092b6d27…tmp` **379.3 MB**,
`b2-burst` 49.3 MB ×4, `b2-livecopy` 14.6 MB ×2 · `1d–3d` → `gate-gb-*` 570.4 KB,
`rebuilt-80.patch` 166.1 KB, `yt-wiring-*` 1.0–1.1 MB por ficheiro.

`I:/cc-tmp` — listagem completa, bandas lidas directamente:

| banda | conteudo observado | quota |
|---|---|---|
| `<= 1 h` | `census_todo_marker.txt` (meu), `battery*.log`, `ytboot.log`, `neg1/2.log` | ~2 % |
| `<= 24 h` | `gate-probe-*` (6), `chn/ch/shr/ss.txt`, `precommit*.log`, `models-src/`, `code-health-baseline.before.json` | ~5 % |
| `<= 7 d` | `1 d`: `nemo-venv/`, `torchinductor_Administrador/`, `freeze-oracle-*`, `yt-wiring-*`, `hist-mut-*`, `battery-class-*`, `pov-*`; `2 d`: `cdp-panel2/`, `headtree/`, `sw-new.py`, `shell-current.py`; `3–6 d`: `old-tree/`, `mutants/`, `_falsify/`, `pre_*/` (6 d), `log-before-run.log` (6 d) | ~90 % |
| `> 7 d` | um unico `py` (0 B, `1w ago`) | <1 % |

---

## 5. Cuidado especial: o que uma lane viva ainda pode precisar

| entrada | factos medidos | veredicto |
|---|---|---|
| `G:/Temp/.bun-1576330339-3cba9b8dc4fa4e45.node` | existe (`glob`); `mtime` nao lida | **HOLD** — artefacto de extracção do `bun` (escreve `.bun-<epoch>-<hash>.node/.dll` ao spawnar; o epoch identifica a invocacao) |
| `G:/Temp/.bun-1576330339-ff51b3648e1aa3dc.dll` | existe (`glob`) | **HOLD** — par do anterior |
| `G:/Temp/.ses` | existe (`glob`, sem filhos) | **HOLD** — estado de sessao; o brief diz que uma lane viva o pode usar e nao ha como provar o contrario sem `psutil` |
| `G:/Temp/hydra-launcher.lock` | 0 B, 14 m | **HOLD** — lockfile escrito ha 14 m |
| 12 x `G:/Temp/*/EBWebView` | `tmpdd3x2xdn` 9 m · `tmpj_6qubwp` 16 m · `wv2-arm-plain` 39 m · `wv2-arm-nogpu` 42 m · `wv2-arm-nosandbox` 43 m · `wv2-det-prof`, `wv2-probe-prof{3,4}`, `wv2-probe-prof` 48–51 m · `tmph5gj_q4l` 53 m · `hydra-wv2-test2` 59 m · `hydra-wv2-test` 1 h | **HOLD** — perfis WebView2; `msedgewebview2.exe` mantem `Default/`, `ShaderCache/` abertos. **Nenhum com `>24 h`.** |
| `G:/Temp/wtguard-winpid.*`, `*.pid`, `ledger.jsonl.lock`, `child.pid` | 2 h – 3 h | **HOLD** — marcadores de processo; apagar deixa o guard sem referencia |
| `G:/Temp/jcode-ws/`, `jcode-bg-tasks/`, `jcode_destructive_gate_test_*` | 1 h – 4 d | **HOLD** — estado do jcode (219 ficheiros de task, 139 workspaces) |
| `G:/Temp/b2-window-*` com `jobs.sqlite3-wal` + `-shm` | 293–309 KB `-wal`, 32 KB `-shm` | **HOLD** — `-wal`/`-shm` provam DB SQLite **aberto** |
| `G:/Temp/b2-livecopy-*/live-copy.sqlite3` | 14.6 MB, 2 h | **HOLD** — copia de DB viva |
| `G:/Temp/092b6d27…tmp` | 379.3 MB, 34 m | **HOLD** — escrito ha 34 m |
| `G:/Temp/sotto-deadline-*` (`filho.txt`/`neto.txt`) | 1 h – 2 h | **HOLD** — sondas de deadline activas |
| `I:/cc-tmp/models-src/ultra.safetensors` | 1.2 GB, 1 d | **HOLD** — **pesos do ASR em uso**; `receipt-20261102-worker-models-emptied.md` documenta que ja' desapareceram uma vez. Nunca apagar por idade. |
| `I:/cc-tmp/models-src/parakeet-{ultra,redux}-onnx/` | 16 h – 1 d | **HOLD** — pesos |
| `I:/cc-tmp/freeze-census-live.log` | 2.6 MB, 5 h | **HOLD** — sonda viva |
| `I:/cc-tmp/gate-probe-*/_profile` | 8 h – 15 h | **HOLD** — perfis de browser de sondas recentes |
| `I:/cc-tmp/battery*.log`, `run-battery.py` | 9 m – 2 h | **HOLD** — bateria em curso |

---

## 6. Classificacao

Regra aplicada, na ordem: **HOLD** se ha' prova ou forte indicio de processo vivo (`mtime <= 24 h`,
lockfile, `-wal`/`-shm`, perfil de browser, estado de job, pesos do produto) -> **UNKNOWN** se precisa
de decisao do dono (bytes inmediveis, ou ficheiro insubstituivel / regeneravel a custo alto) ->
**SAFE-TO-DELETE** so' quando `mtime > 24 h` **e** nenhum indicio de detentor.

| classe | `G:/Temp` | `I:/cc-tmp` | veredicto |
|---|---|---|---|
| `*.tmp` UUID no topo (379 MB, 16.9 MB, 11 MB, …) | dezenas, 0 B – 379.3 MB | – | `<=11 m` → **HOLD** |
| `b2-*` / `n02-*` / `jobrt-test-*` / `jobtest-*` (SQLite de teste) | **centenas**, 60–76 KB cada, `2 h – 1 d` | – | `2–14 h` → **HOLD**; `1 d` → **SAFE** |
| `jcode-subagent-intent-test-*` | ~700 dirs, `1 h – 1 d` | – | `1 h` → **HOLD**; `1 d` → **SAFE** |
| snapshots de mutante (§7) | **127 dirs**, `1 h – 6 d` | `1 d – 6 d` | `<=24 h` → **HOLD**; `>24 h` → **SAFE** |
| `shadowplay-*/` | **~40 dirs quase VAZIAS** (so' a `mtime`), 2 h | – | **UNKNOWN** — 0 B medidos; nome do capturador NVIDIA |
| `EBWebView` (12) | 16 m – 1 h | – | **HOLD** |
| `.bun-*`, `.ses`, `hydra-launcher.lock` | §5 | – | **HOLD** |
| `gitattr-verify/`, `jcode-ws/`, `pytest-of-Administrador/`, `.tmp*/repo` | 34 m – 3 d | – | **HOLD** se `<24 h`; senao **UNKNOWN** (bytes) |
| logs de arranque grandes | – | `webview-run-before-lane.log` 44.6 MB (2 d), `log-before-run.log` 41.5 MB (6 d) | **SAFE** — ambos "before"; o instrumento vivo e' `_main/webview-run.log` |
| snapshots `pre_*` / `pre_crlf_*` (~40 ficheiros, 6 d) | – | 6 d | **SAFE** — copias pre-edicao; o git guarda a historia |
| `old_sotto_webview.py`, `_falsify-uncured-shell.py`, `shell-current.py`, `sw-new.py`, `*.bak` | – | 2 d – 6 d | **SAFE** |
| `nemo-venv/` | – | 1 d | **UNKNOWN** — venv reconstruivel (o precedente apagou venvs), mas e' o runtime do ark/nemo; dono decide |
| `torchinductor_Administrador/` | – | 1 d | **SAFE** — cache de compilacao, regenera-se |
| `cdp-panel2/`, `headtree/`, `old-tree/`, `mutants/`, `_falsify/`, `_falsify-pip/`, `deepinfer/` | – | 2 d – 4 d | **SAFE** (sem detentor) mas **bytes UNKNOWN** |
| `*.wav` de teste | – | 2 d – 6 d | **SAFE** — ~3.9 MB medidos |
| `enc-opt.onnx` 1.4 MB | – | 2 d | **UNKNOWN** — artefacto de modelo |
| `census_todo_marker.txt` | – | 96 B, just now | **HOLD** — **artefacto meu** (marcador do contrato); nao e' lixo de lane |

---

## 7. Bottom line

`RECLAIMABLE: >= 350 MB (~0.35 GB)` — piso medido (≈102 MB em `I:/cc-tmp` + ≈250 MB em `G:/Temp`),
**nao** o total: as subarvores `EBWebView`, `jcode-ws`, `nemo-venv`, `.git` ficam por medir (§1).

### `G:/Temp` — 127 directorias de snapshot, 292 MB medidos por listador

Contagem exacta por `glob` (sem `… N more` em nenhuma) x tamanho medido por directoria:

| familia | dirs | MB/dir (medido) | subtotal |
|---|---|---|---|
| `yt-wiring-*` | 23 | 5.0–5.5 (5 x `sotto_webview_m{1..5}.py` 1.0–1.1 MB) | ~120.8 MB |
| `churn-neg-*` | 30 | ~1.55 (`sotto_worker_mut.py` 437.5/413.2 KB + `sotto_webview_mut.py` 1.0–1.1 MB) | ~46.5 MB |
| `freeze-oracle-*` | 19 | ~2.3 (`sotto_webview_m4.py` 1.0–1.1 MB + 3 x `sotto_worker_m{1..3}.py` ~382–430 KB) | ~43.7 MB |
| `hist-mut-*` | 32 | ~1.05 (`sotto_webview_mut.py`) | ~33.6 MB |
| `paintrow-*` | 10 | 3.3 (`cap_`+`route_`+`sink_removed.py`, 1.1 MB cada) | ~33.0 MB |
| `capbudget-*` | 13 | ~1.11 (`shell_mutant.py` 1.1 MB + `corpus.log` 8.4 KB) | ~14.4 MB |
| **total** | **127** | | **~292 MB** |

A `mtime` de cada uma nao foi lida individualmente; a amostra que li mostra 2–5 dirs frescas (`1 m – 1 h`)
por familia e o resto `1 d – 6 d`. **A fracção `>24 h` (SAFE) e' a maior parte** — dai o piso de
~250 MB acima. `[INF]` na divisão; **medido** no tamanho e na contagem.

Demais SAFE medidos em `G:/Temp`: `rebuilt-80.patch` 166.1 KB (1 d) · `mut-C.log` 1.1 KB (1 d) ·
`droid-bg-*.out` (1 d) · `.tmp*/repo`, `ii-review3/`, `receipt-audit-lane-*`, `r10b-gitcone*`,
`sp-frames-*` (3 d) · centenas de `n02-*`/`b2-*`/`jobrt-test-*`/`jobtest-*`/
`jcode-subagent-intent-test-*` a `1 d` (60–76 KB cada, **nao contados**).

### `I:/cc-tmp` — ~102 MB medidos

| caminho | bytes | mtime |
|---|---|---|
| `webview-run-before-lane.log` | 44.6 MB | 2 d |
| `log-before-run.log` | 41.5 MB | 6 d |
| `pre_*` + `pre_crlf_*` (~40 ficheiros) | ~4.5 MB | 6 d |
| `cap.wav`, `cap-norm.wav`, `silence-click[s/room].wav`, `cap-game.wav`, `en-us/pt-br-sample-16k.wav` | ~3.9 MB | 2 d – 6 d |
| `enc-opt.onnx` | 1.4 MB | 2 d |
| `bridge-before300.log`, `bridge-after600.log`, `bridge-toolcheck.log` | ~1.08 MB | 4 d |
| `shell-current.py` | 928.0 KB | 2 d |
| `sw-new.py` | 806.4 KB | 2 d |
| `sotto_webview.bak` | 775.5 KB | 6 d |
| `old_sotto_webview.py`, `_falsify-uncured-shell.py` | 766.0 KB cada | 4 d |
| `pov-selftest-*.{log,out,cmd}` (~16) | ~0.42 MB | 1 d – 4 d |
| `falsify-altc{,3,4}/report-*.json`, `hotkey-spam-falsify/` (74 ficheiros) | ~0.9 MB | 4 d |
| `old-tree/`, `mutants/`, `_falsify/`, `_falsify-pip/`, `deepinfer/`, `cdp-panel2/`, `headtree/`, `torchinductor_Administrador/` | **UNKNOWN** (bytes) | 1 d – 4 d |

### O que isto significa para o dono (o achado, nao o numero)

1. **`G:/Temp` nao tem lixo velho: 0 entradas com mais de 3 dias.** Os 14 GB sao scratch desta semana
   (66 % com menos de 24 h). Apagar por idade no `G:` **nao resolve** — o que resolve e' as lanes
   pararem de escrever no `G:`: `_main/AGENTS-AUDIT.md:24` ja' registou *"`TMPDIR=I:\cc-tmp`
   (`G:` → ENOSPC) undocumentado"*. O `TMPDIR` tem de apontar para `I:\cc-tmp` (ou `C:`) em **todas** as
   lanes; sem isso o `G:` enche outra vez em dias.
2. **O desperdicio do `G:` e' estrutural, nao cronologico:** 127 snapshots de mutante a ~1–5 MB por
   execucao (so' `yt-wiring-*` = 23 copias de um ficheiro de 1.1 MB), 12 perfis WebView2 completos,
   219 ficheiros de `jcode-bg-tasks`, 139 workspaces de `jcode-ws`. Cada lane que corre
   `oracle`/`mutante`/`wv2` deixa uma arvore inteira e **ninguem a reap a seguir**. Sem reaping por
   `mtime` (3 dias, como no censo de 2026-11-01), o `G:` volta a encher.
3. **`I:/cc-tmp` e' 4.8 GB mas ~1.2 GB e' o `ultra.safetensors` do ASR** — vivo. A regra "apagar o que
   tem >24 h" **destruiria os pesos**; e' exactamente o acidente que `receipt-20261102-worker-models-emptied.md`
   ja' documentou. Pesos e `nemo-venv/` ficam fora da regra, sempre.
4. **A politica de 3 dias do censo anterior e' mais segura que a regra de 24 h deste brief.** Com a
   regra antiga (`>3 d`) o `RECLAIMABLE` medido cai para os bens de 4–6 d: `log-before-run.log` 41.5 MB,
   `pre_*` 4.5 MB, `.wav`, `old-tree/`, `mutants/`, `_falsify/`, `hotkey-spam-falsify/` →
   **>= 47 MB**. Com a regra do brief (`>24 h`) sao **>= 350 MB**.
5. Nada disto substitui `du -sb` (§1). O Main tem shell; a linha esta' em §1.

---

## SELF-AUDIT

- **protocolos em falta** — (a) O brief mandava "use `python` scripts escritos em `I:/cc-tmp`"; a minha
  toolset **nao tem shell/exec**, portanto nao corri python nenhum. Devia ter declarado esse limite
  **antes** de paginar 4 800 linhas de listagem. (b) O bloco `CACHE/PRICE` exige
  `cache-task-report.sh` — tambem nao e' executavel aqui (abaixo). (c) O bloco `COMECAR` manda
  `todo init`, tool que nao existe nesta toolset; registei o card num ficheiro,
  `I:/cc-tmp/census_todo_marker.txt` (96 B) — que **aparece no censo do `I:`** e esta' classificado em
  §6 como `HOLD (meu artefacto)`, nao como lixo.
- **verificacao adicional** — o que teria mudado o resultado: `du -sb` por entrada de topo nos dois
  roots (~2 s cada, no shell do Main). Custo: uma chamada que eu nao tenho.
- **checkboxes novas** — mecanico, para esta classe: `command -v du >/dev/null || { echo "TOTAL: UNMEASURED"; }`
  no inicio, e **`psutil.Process(...).open_files()` obrigatorio para cada linha `HOLD`** — aqui nao foi
  possivel correr, e a coluna "proc dono" ficou `[INF]`; o recibo devia ser recusado sem ela.
- **review por outro subagente** — `sim-com-escopo` — a coluna "proc dono" e a divisao `>24 h` dentro
  das 127 familias de mutante (a unica parte `[INF]` do §7).

**gate-doubt:**

- `verde-de-verdade:` — nenhum gate/oraculo foi corrido (censo read-only). O unico verde e' o do
  instrumento: 12 sondas de offset devolveram `1h`, `2h`, `9h`, `14h`, `1d`, `3d` de forma **monotona e
  coerente**, confirmando que a ordenacao por `mtime` e' real e que as fronteiras da §4 nao passaram por
  construcao. O que **podia** ter passado vacuoso era a contagem dos perfis e das familias
  (`glob` com `limit=100`): todas devolveram a lista completa, **sem `… N more`** — o limite nao truncou,
  os 12 / 23 / 19 / 32 / 10 / 13 / 30 sao reais. E o proprio §7 **corrigiu** um erro meu: o primeiro
  rascunho dizia `G:/Temp` SAFE = "~0.17 MB", porque eu so' tinha somado ficheiros avulsos e ignorado
  127 directorias de 1–5 MB; o numero real medido e' **~292 MB**.
- `falta-no-gate:` — o instrumento **nao** verifica (i) bytes de subarvore, (ii) ficheiros a
  profundidade >= 2, (iii) quem tem o ficheiro aberto, (iv) `mtime` por entrada dentro de uma familia.
  Cenario concreto que atravessa o buraco: uma lane escreve 3 GB em
  `G:/Temp/<x>/EBWebView/Default/Cache/` e o meu censo continua a dizer `0 B medidos` para `<x>` — o
  root parecia saudavel enquanto enchia o disco do dono (foi exactamente o que aconteceu com os 14 GB).
- `gate-melhor:` — check mecanico que fecha o buraco, para o Main:
  `du -sb /g/Temp/* /i/cc-tmp/* | sort -n` tem de **imprimir uma linha por entrada de topo**; o input
  que o deixa RED e' qualquer entrada com `du -sb > 1 GB` que **nao** apareca na tabela §3 (prova de que
  a tabela mentia por omissao). Correr antes de aceitar o meu `RECLAIMABLE`.

`confianca: media` — alta nas `mtime`, na ordenacao, nos 12 perfis, nas 127 contagens e nos bytes de
ficheiro; **baixa** nos totais por root (fonte = dono), na divisao SAFE/HOLD dentro das familias, e em
qualquer coisa a profundidade >= 2.

`nao verificado:` (1) bytes reais de `G:/Temp` e `I:/cc-tmp` (sem `du`); (2) bytes de toda a directoria
com profundidade >1 (`EBWebView`, `jcode-ws`, `nemo-venv`, `.git`); (3) `open_files` por processo (sem
`psutil`) — toda a coluna "proc dono" e' `[INF]`; (4) contagem exacta de entradas de topo (o listador
da' linhas, nao entradas); (5) `G:/Temp` linhas `4 801–15 851`: nao lidas na integra, **amostradas** em
`:6000`, `:9000`, `:13000` (todas KB/`0B`, nenhum ficheiro de escala GB) e as fronteiras de idade
sondadas; (6) `mtime` exacta de `.ses` e `.bun-*` — existem, ficam **HOLD** por precaucao; (7) `mtime`
por entrada dentro das 127 familias (so' a amostra).

## CACHE/PRICE

`UNKNOWN — o script I:/!manager/scripts/cache-task-report.sh nao e' executavel nesta lane: a toolset
tem apenas read/grep/glob/web_search/write, sem shell (confirmado em §1: read proc:// = 0 services).
Sem exec nao ha' leitura do meu proprio transcript .jsonl nem linhas WHEN / WHERE failed para colar.`

---

**done (fecho do card do brief):** `_main/receipt-20261105-temp-census.md` — censo dos dois roots com
totais, top-25, histograma, classificacao, `RECLAIMABLE: >= 350 MB` (piso medido) e a lista de caminhos
SAFE. **Zero bytes apagados.**
