# Recibo do Lead — ronda 1 dos 7 fronts (2026-10-12, ~04:35–05:15 -03:00)

Ronda 1 do objectivo em `docs/owner-brief-20261012.md`. O Lead não fecha frente nenhuma
nesta ronda: fecha **o chão** onde elas trabalham e **verifica por si** o que já aterrou.

---

## 1. O que o Lead mediu/corrigiu no chão (tudo com instrumento)

| facto | medição |
|---|---|
| 5 ficheiros *tracked* apagados em disco | `_main/_audio-{dlls.bat,exclusive-hold.cpp,mft-probe.cpp,tone-inject.py,tone-render.cpp}` — `git checkout --` repôs os 5 (`onDisk=True` 5/5); `git status --porcelain` **256 → 246** entradas |
| o painel do dono está vivo | `_main/panel-state.json` (19,1 KB, mtime 2026-10-12T08:10:28Z) = `panel.live.count=72`, **72 linhas**, `panel.live.hidden=false`, `namedState=done`, `shell.visible=false` (certo: o dono carrega Alt+C); última linha `"Your router sends a packet of data it sends."` |
| custo do app a correr, 30 s a 1 s | shell pid 8588: **0,63 s de CPU em 19 s** (3,3% de um core), RSS **114 MB**; worker pid 22172: **0,47 s em 19 s** (2,5%), RSS **2 479 MB** (máx 2 481); **2** processos WebView2 filhos. Áudio parado neste janela |
| legendas a fechar medido 1/s | `CAPTION_APPLIED`: contagem 11 528 constante no janela → o dono **não** estava com áudio a tocar; 0,5–0,7 legendas/s medido quando há áudio |

**Retracção minha, registada:** o valor "96,78 s de CPU" do span anterior está **ERRADO**.
Veio de `Get-Process.CPU`, que no pwsh 7 devolve um `TimeSpan`, não um número — o "`-f`"
formatou como texto e a conversão deu NaN. A medida válida usa
`TotalProcessorTime.TotalSeconds` (linha da tabela acima). Quem citar 96,78 s está a citar o
meu bug.

**Falso alarme meu, registado:** li `panel-state.json` a meio de uma escrita e li
`panel: null`. Não há painel partido: ver §1, segunda linha.

---

## 2. Frente S5 — FECHADA, com recibo e verificação do Lead

Recibo: `_main/receipt-20261012-s5.md` (6 392 B). Entregável: `docs/research/speaker-separation.md`
(15 984 B). O Lead **leu as duas** e verificou o instrumento central.

**Resposta ao dono (Discord, por-falante):**

1. **Não precisa de modelo nenhum** para saber *quem fala quando*: o Discord entrega um fluxo
   **por participante** (`discord.js` `VoiceReceiver.subscribe(user_id)` → `ssrcMap` SSRC→user)
   — é preciso um **bot** na call. E o Sotto **já tem** captura por processo
   (`--target-pid`, live em `worker/sotto_worker.py:4073 / :1044-1045 / :2226 / :2506 / :2547`,
   pin do trabalhador **310 593 B / 5 929 linhas / sha256 246BF809…**, mtime 2026-10-12T02:11:19Z)
   = 1 stream por processo, zero modelo.
2. O que **não** existe é separação de **falas sobrepostas**. A diarização está viva e medida
   (controlo reproduzido hoje: 10 segmentos / 4 falantes / **DER 0,03 %**; áudio do dono, 90 s:
   3 falantes, RTF 0,3207, pico RSS 382,9 MB) — mas o veredito mantém-se: **DER ≈ 61,6 %**
   previsto no áudio do dono contra limiar de morte ~25 % → **morta** para este uso.
3. A única família de *source separation* instalável aqui separa **música**: S5 descarregou e
   correu `UVR_MDXNET_9482.onnx` (29 704 738 B): 2 stems, RTF 0,8048 (**mais lento que tempo
   real**), pico RSS **3 237,2 MB**, `reconstruction_delta_rms 0,0`. Distribuição: 25 assets /
   1 137 734 500 B, **todos música**.

---

## 3. O modelo que separa falantes — INSTALADO (pedido do dono: *"se nao temos, instala"*)

| campo | valor medido |
|---|---|
| modelo | `alibabasglab/MossFormer2_SS_16K`, **Apache-2.0** (README 345 B gravado com ele) |
| para que serve (palavras do README) | *"separa discursos de falantes misturados em fala individual de cada falante"* — 16 kHz |
| bytes | **670 353 271** |
| sha256 | `00A3A48BDA492DB1E829B85DD443F8F43A43039A3E90F1A24962EA9CAF14A11A` |
| verificação | **igual ao `oid` do ponteiro LFS do próprio servidor** → sha-match=True, size-match=True, **medido duas vezes**: uma em `I:/cc-tmp` e outra já em `_main/diar-models/mossformer2/` |
| runtime | `torch 2.7.0+cu128` medido no Python de sistema → potencialmente corrido aqui |

**UNMEASURED:** nunca o executei; o código de inferência (ClearerVoice-Studio) não está
instalado; e a rota Discord **não precisa dele** (ver §2.1). Fica instalado, verificado e
disponível — não ligado a nada.

O directorio `_main/diar-models/` passou a **git-ignorado** nesta ronda (como `worker/models/`
e `history/`): são pesos locais, nunca conteúdo do repositório.

---

## 4. Oráculos dos fronts corridos pelo LEAD (não aceito a palavra deles)

| frente | instrumento | resultado do Lead |
|---|---|---|
| S6 (dropdown com pré-visualização) | `node _main/theme-preview-oracle.js` | **VERDICT: FAIL, rc=1** — ARM7 (o último tema pairado devia ganhar: veio `undefined`; uma moldura = 8 applies; 15 eventos para 8), ARM8 (a deferral não contou: `false`; 0 applies no commit), ARM9 (o caminho quente não correu: fonts=0 imagens=0 ms=0). Em voo — `theme-tune.js` ainda a ser escrito às 05:06 |
| S1 (inventário dos zips) | `node docs/design-intake/gap-oracle.mjs` | **não corre**: `SyntaxError: Unexpected end of input` na linha **429** (última linha, a meio de uma expressão) = ficheiro **truncado**. Em voo |
| S4 (animação por letra) | `node --check app/panel/letter-swap.js` | **rc=0**, e os comentários do ficheiro descrevem exactamente a regra do dono: diff de Myers com limite, letras iguais ficam **quietas** (`changedNew`/`inserted`). Sem oráculo próprio ainda |

S1 já desembrulhou os 5 zips (89/19/17/21/14 ficheiros em `docs/design-intake/**`, incl.
`themes.ts` com `CaptionStyle { className, reveal, ghostClassName }` e a nota
*"tailwind classes for the caption text itself (**no background, ever**)"* — instrução directa
para a frente S2 e para o S4).

---

## 5. O que o Lead NÃO fez nesta ronda, e porquê (bloqueado, não esquecido)

| pedido | razão do bloqueio |
|---|---|
| braços do arranque do S7 (`--no-worker` / `SOTTO_NO_WORKER=1` vs completo, para o "stutter") | `SINGLE_INSTANCE name=Local\SottoShell` está tomado pela app **do dono** (pid 8588). Um segundo lançamento sairia no lock; e eu **não mato** a instância do dono. Braços a correr quando a app fechar |
| `_main/_audit-verify-all.cmd` (bateria 77/77) | a bateria lança o shell dezenas de vezes — neste momento lutaria com a instância do dono. **A bateria desta ronda é a do §4** |

---

## 6. Estado do chão no fim da ronda

- `git status --porcelain` = 246 entradas (antes: 256; os 5 `_audio-*` foram repostos e não
  são trabalho de frente).
- App do dono: **aberta, a transcrever, sem janela visível** (shell 8588 pythonw, worker 22172).
- Frentes fechadas: **S5** (1 de 7). Em voo: S6 (oráculo vermelho), S1 (oráculo truncado),
  S4 (parse ok). Sem artefactos ainda: S2, S3, S7.
