# Recibo 2026-11-27 — a tabela de artefactos, e o portão que faltava

## O que estava por responder

A lei das stores (`H:\pi-agent\AGENTS.md` §8) exige, para cada directoria que uma
ferramenta escreve e nunca relê: raiz declarada, produtor, tecto de bytes e regra
de retenção. `H:/sotto` não tinha `.artifacts.toml` -- `codeintel health` imprimia
`artifacts_toml=False`, e portanto o repo não sabia responder "o que é que isto
consome".

## Medido antes (o censo, um instrumento, 2026-11-27)

| raiz | bytes | ficheiros | git |
|---|---:|---:|---|
| `worker/models` | 1224.5 MB | 147 | ignorado |
| `.codeintel` | 283.2 MB | 27 | ignorado |
| `_main/_design-lane` | 85.9 MB | 3129 | 172 versionados + 2 933 de `node_modules` |
| `_main/_cache` | 78.9 MB | 876 | ignorado |
| `_cache` | 57.1 MB | 580 | 1 versionado |
| `.agent-work` | 48.5 MB | 646 | ignorado |
| `history` | 47.2 MB | 103 | ignorado |
| `_main/_audit-verify` | 10.2 MB | 788 | 16 versionados |
| `_main/fixtures` | 2.6 MB | 25 | 19 versionados |
| `benchmarks` | 0.5 MB | 4 | 3 versionados |
| `_main/_ordem-before/models` | 1224.5 MB | 147 | ignorado |

## Medido depois

```
family                         bytes    files  verdict  cap
engine-weights              1.20 GiB      147  OK        2.50 GiB  [external]
codeintel-index            283.2 MiB       27  OK        1.00 GiB  [reclaimable]
design-lane-node-modules    82.8 MiB     2933  OK        0.15 GiB  [reclaimable]
probe-cache                 78.9 MiB      876  OK        0.50 GiB  [reclaimable]
session-cache               57.1 MiB      580  OK        0.25 GiB  [tracked]
agent-work                  48.5 MiB      646  OK        0.25 GiB  [reclaimable]
caption-history             47.2 MiB      103  OK        0.50 GiB  [external]
battery-step-logs           10.2 MiB      774  OK        0.10 GiB  [reclaimable]
measured-fixtures            2.6 MiB       25  OK        0.25 GiB  [tracked]
design-lane-scratch          2.5 MiB      173  OK        0.10 GiB  [tracked]
benchmark-history          521.5 KiB        4  OK        0.05 GiB  [tracked]
archive-before-checkout    457.5 KiB        4  OK        0.01 GiB  [external]
TOTAL                       1.80 GiB
```

`artifact-manifest.py --gate` → **rc 0**. `--reclaim` → `nothing over its
retention` (nada acima da retenção; `df H:` 577G usados / 92G livres).

## Os dois números que mentiam, e como foram encontrados

1. **Hardlinks contados duas vezes.** `_main/_ordem-before/models` é uma foto
   congelada do worker antes da cura (`_main/_ordem-cura-oracle.py` importa-a como
   braço vermelho). Medido com `st_ino`: **147 de 147 ficheiros são o MESMO inode**
   de `worker/models` (0 separados, 0 bytes diferentes por sha256). A primeira
   tabela declarava as duas famílias e publicava `TOTAL 2.99 GiB` -- 1.20 GiB de
   bytes que não existem. Correcção: `roots = ["_main/_ordem-before"]` com
   `exclude = ["_main/_ordem-before/models"]`, e o comentário diz por quê. Um
   `--reclaim` ali libertaria 0 bytes; reclamar a foto por "grande" seria o erro.
2. **`EMPTY` não reprovava.** Testado num projecto temporário com
   `roots = ["nope"]`: o instrumento imprime `verdict: EMPTY` e o `--gate` devolve
   **rc 0**. Uma declaração que não mede nada ficava registada como família limpa.
   O `--gate` só conhece OVER (rc 2) e TRUNCATED (rc 3).

## O portão que faltava

`_main/artifact-manifest-oracle.py` -- 5 arms sobre o payload real do
instrumento, e 4 mutantes no `--neg-arm`:

| arm | o que exige |
|---|---|
| A1 `tabela-medida` | o instrumento correu e devolveu JSON com famílias |
| A2 `nenhuma-familia-vazia` | nenhuma família `EMPTY` (raiz inexistente) |
| A3 `nenhum-tecto-violado` | nenhuma família `OVER`/`TRUNCATED` |
| A4 `soma-e-o-total` | `Σ bytes == total_bytes` (nenhuma família contada 2x) |
| A5 `toda-familia-nomeia-producer` | uma store sem dono é um despejo |

O juiz `judge(rc, payload)` é uma função **pura** e o braço negativo feeda-lhe
payloads construídos -- o controlo julga o juiz real, não uma cópia.

Medido:

```
$ python _main/artifact-manifest-oracle.py
VERDICT: GREEN -- 5/5 arms, instrumento rc=0        (1,0 s)

$ python _main/artifact-manifest-oracle.py --neg-arm
NEG-ARM familia-vazia          PASS -- A2 vermelho
NEG-ARM tecto-violado          PASS -- A3 vermelho
NEG-ARM familia-sem-producer   PASS -- A5 vermelho
NEG-ARM sem-manifesto          PASS -- A1 vermelho
4/4 mutacoes avermelharam o seu braco
NEG-ARM VERDICT: PASS                                rc=1 (convenção da casa)
```

Ausente o instrumento (`I:/!watcher/tools/artifact-manifest.py`) ou estourado o
prazo de 180 s, o positivo responde `VERDICT: CANNOT-MEASURE` rc 3 -- nunca verde.

## Ligado à bateria

Par `artifact-manifest` + `red-as-expected-artifact-manifest` em
`_main/_audit-verify-all.cmd` (antes de `BATTERY SUMMARY`), com `if exist` para
que uma máquina sem o oráculo publique `MISSING` em vez de um verde.

`battery-launch.py --verify` depois da edição: **PASS** em todas as cinco portas
(pins 0,7 s / wiring 7,7 s / pairing 0,1 s / class 0,1 s / undefined-names 1,2 s).
O `pairing` apanhou a primeira versão do par (`:record` num passo que declara
rc 1); a forma da casa é `:expectred ... "NEG-ARM PASS"`.

Novo pin da bateria (em `AGENTS.md`, re-medido porque o oráculo `agents-md-pins`
o exige): **455291 B**, **5188 CRLF** / 0 bare LF, sha256
`E4648712815CC8FB6965437EB7EFA3022DA4E26161A1FDA4C6261EA051249BCB`.

## O que isto NÃO resolve

`architecture_coherence` continua em 60: o corte dos monólitos é o
`revival/SPLIT-PLAN.md`, e não é deste recibo. `delivery_balance` continua em 88
(janela de 40 commits: 29 produto / 11 meta) -- o tecto antigo (AGENTS.md ≤ 250
linhas) já foi reparado; o que falta é produto, não instrumento.
