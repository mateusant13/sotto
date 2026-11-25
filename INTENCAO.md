# INTENÇÃO FINAL — o que "o Sotto funciona" significa

**2026-10-23.** Este ficheiro existe porque a pergunta do dono foi certeira: *"e tu sabe como ele deve?
ou a gente tem que fazer um arquivo de INTENCAO FINAL?"*. Enquanto a resposta a "está funcionando?"
for uma sensação, cada sessão discute de novo. Aqui cada item tem **uma prova** e **um instrumento**.

## A aceitação, verbatim (é a única fonte de verdade)

> *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer audio do meu pc. e legendas."*

Tudo o resto são as quatro ordens de 2026-10-21 (`AGENTS.md`) e as reclamações registadas.

## A REGRA

`PASS` só com o instrumento a dizer PASS. `UNKNOWN` **não** é PASS. E `fixed` nunca se apresenta como
`verified` sem um verificador que não seja o autor. O instrumento é `_main/sotto-doctor.py`.

| id | o que tem de ser verdade | como se prova (evidência no log / instrumento) | estado hoje (medido) |
|---|---|---|---|
| **INT-1** | A app abre e fica sã | `SINGLE_INSTANCE already_running=false` + `CAPTION_OVERLAY_CREATED layered=true` + `TRAY_ICON_ADD ok=true` + **sem** `WEBVIEW2_INIT_FAILED` | **PASS** na largada do dono (19:46, pid 19872). **FAIL** de uma pane (4 mecanismos, ver `AGENTS.md`) |
| **INT-2** | Alt+C mostra legendas ao vivo de qualquer áudio do PC | `HOTKEY_REGISTERED isRegistered=true` + uma linha de legenda `route=final` depois da pressão | **UNKNOWN** — não há uma única linha de hotkey depois das 19:46; ninguém pressionou com o log a correr |
| **INT-3** | O worker carrega e transcreve | `BRIDGE_LOAD_MS` dentro de 60 s de `BRIDGE_SPAWNED` + pelo menos uma legenda | **FAIL** às 19:47 — `BRIDGE_SPAWNED pid=55308` e **nenhum** `BRIDGE_LOAD_MS` em todo o log |
| **INT-4** | ~~1/2/3 pressões = legenda / painel de baixo / painel da direita~~ **CONTRATO RETIRADO**: o HOLD morreu a 2026-11-01, o ciclo de três casas a 2026-11-24. Em vigor: 1 toque → faixa, 2. toque dentro de `DOUBLE_TAP_S = 0,40 s` → painel da direita, fora da janela → esconde; `Ctrl+Space` comuta a legenda | `python _main/altc-gesture-oracle.py` → `ALTC-GESTURE GREEN -- arms=104 pass=104 fail=0` (2026-11-25), `--neg-arm` RED-as-expected | **PASS do contrato actual em 2026-11-25**; o resultado de 2026-10-21 é histórico e não descreve o código de hoje |
| **INT-5** | YouTube: inglês→inglês, espanhol **nunca** traduzido, o resto→inglês | `youtube-captions` (53 arms) + `youtube-foreign-paint` | **PASS** na bateria |
| **INT-6** | Parakeet é o segundo pass e o lifecycle não deixa órfão | `external-resume` 8/8 + `BRIDGE_STOP`/`BRIDGE_DEATH` sem órfão | **PASS** nos portões; **UNKNOWN** numa corrida real |
| **INT-7** | O PC não degrada (rato) | `input-path` 10/10 + hook **ausente** com o painel escondido | **PASS** nos portões; o dono confirmou o rato |
| **INT-8** | A bateria não abre o mundo do dono | classe `heavy` + `battery-heavy-gate` | **PASS** |
| **INT-9** | Nenhuma afirmação sem data e instrumento | `docs/factos-medidos.md` + recibos | **parcial** (é para isso que este ficheiro existe) |


## ENTRADAS DE 2026-11-25 — o que passou a fazer parte da intenção, e a prova de cada uma

A regra deste ficheiro continua a ser a de 2026-10-23: `PASS` só com o instrumento a dizer PASS; `UNKNOWN` não é PASS; `fixed` não é `verified`. Estas quatro entradas são **adições datadas**, não uma reescrita da história acima.

| id | o que passou a ser objectivo | instrumento que prova (comando corrido nesta árvore em 2026-11-25) | veredito medido |
|---|---|---|---|
| **INT-10** | **Separar as camadas e transcrever cada voz em paralelo É o objectivo.** `worker/speaker_sidecar.py` + `worker/speaker_bridge.py` carimbam `voice:speaker-N` por default; o painel pinta slots por voz. NOMES de pessoas e "quem falava quando" **não** são metas, e o DER **não** é métrica de aceitação. Cores/rótulos são slots efémeros: slot não resolvível → cor nova, nunca nome errado | `_main/speaker-sidecar-oracle.py`; os números da refutação em `_main/receipt-20261124-per-voice-default.md` e em `AGENTS.md` §PREMISSAS PROIBIDAS | **PASS** do instrumento de sidecar na data do recibo; coseno mesma voz **min +0,655** vs vozes diferentes **max +0,743** → limiar vazio, logo nenhuma identidade é inferida. A pintura de N vozes na tela do dono fica **CANNOT-MEASURE** (uma lane não abre janela na tela dele) |

| **INT-11** | **O micro do dono entra na transcrição em TODOS os rungs que abrem dispositivo**, e um único stream misturado serve worker e sidecar. Um cliente, fila limitada com queda contada, `SOTTO_CAPTURE_SHARE=0` desliga o leitor | `python _main/capture-share-oracle.py` | `CAPTURE SHARE VERDICT: PASS (8/8 arms)`, braço `f`: `worker_taps=1 worker_mics=1 sidecar_taps=0`, braço `g`: um estranho calado não despe o leitor, braço `h`: um stop ordenado não é falha |
| **INT-12** | **A pontuação de modelo corre em CPU por nome (`PROVIDER = "cpu"`)** para `en`, fail-closed e fail-identity para tudo o resto; `pt-BR` nunca é pontuado por este modelo | `python _main/punctuation-oracle.py` | `5/5 arms green`, `VERDICT: PASS` (provider-cpu, lang-pt-skip, model-absent, env-off, cuda-refused), sem pesos carregados |
| **INT-13** | **O que o dono vê está em PT-BR e a faixa abre no monitor do cursor.** Bandeja `Abrir painel` / `Sair do Sotto`; geometria clampada à work area do monitor escolhido | `python _main/tray-menu-oracle.py`; `python _main/multi-monitor-oracle.py` | `CHECK arms=27 failed=0`, `VERDICT: PASS`; `MULTI-MONITOR PASS -- 6 arm(s), 30 check(s), 0 failure(s)`, `--neg-arm` → `CONTROL PASS -- all 11 mutants reddened their own arm`. O resultado em dois monitores reais fica **CANNOT-MEASURE** nesta máquina de um monitor |

**A ressalva que a lei obriga:** estes vereditos julgam FICHEIROS e funções extraídas do código, não o processo que o dono está a usar. O estado dele continua sujeito a `python _main/live-code-freshness-oracle.py --strict`; um `STALE` não vira `verified` por causa destas linhas.

## O que este ficheiro NÃO é

Não é uma lista de desejos nem um roadmap: o roadmap é `docs/roadmap-observability.md`. Aqui só entra o
que o dono **pediu com palavras dele**, e cada linha tem de poder ser julgada por uma máquina.

## MEDIÇÃO 2026-10-23 22:32 (pid 68572) — a largada do dono, lida do log

Esta secção existe porque os estados da tabela acima são de antes desta corrida. Números, não opinião:

| item | o que o log diz | veredicto |
|---|---|---|
| INT-1 | `SINGLE_INSTANCE already_running=false`, `TRAY_ICON_ADD ok=true`, `CAPTION_OVERLAY_CREATED hwnd=172960364 layered=true`, sem `WEBVIEW2_INIT_FAILED` | **PASS** |
| INT-2 | `PANEL_SHOWN reason=hotkey-double mode=strip visible=true` e, 1,6 s depois, `CAPTION_APPLIED text="We explain everything there." count=5` | **PASS** (a legenda **apareceu** ao Alt+C) |
| INT-3 | `WORKER_PANEL_START_SKIPPED source=show-strip external=true` — o worker foi **saltado** porque havia legendas externas; não há `BRIDGE_LOAD_MS` nesta sessão | **UNKNOWN** (a legenda veio do YouTube, não do worker) |
| INT-4 | `mode=strip` na segunda pressão, como a ordem manda | **PASS** |
| — | **A app congelou às 22:32:56.566**: o log parou, as duas janelas (`SottoNativeCaption` e `Sotto`) ficaram presas no ecrã até o processo ser morto | **DEFEITO ABERTO** |

O congelamento não é "a app não funciona": é a app a funcionar e **parar**. A cura tem duas partes, e as
duas estão feitas nesta data:

1. **O cão-de-guarda da thread de UI** (`sotto_webview.py::_start_ui_watchdog`): pergunta ao Windows, de
   5 em 5 s, se a janela do painel responde (`SendMessageTimeoutW` + `SMTO_ABORTIFHUNG`, 4 s). À segunda
   falta de resposta, **despeja a pilha de todas as threads** (`UI_HUNG_THREAD` / `UI_HUNG_FRAME`) e sai
   com código 9 — para nunca mais deixar uma janela congelada no ecrã. O detector tem portão próprio,
   `_main/ui-watchdog-oracle.py`: **PASS 3/3** (janela saudável responde em 0,00 s; janela congelada não
   responde e esgota 4,00 s; hwnd=0 não responde).
2. A prova que faltava passa a existir na próxima vez que ele travar: a linha exacta do bloqueio.

**RESSALVA, porque a lei é esta:** o cão-de-guarda **detecta e limpa**, não impede a causa. A causa
(a thread de UI a parar depois de `FORM_SHOW_TRANSPARENCY_HACK ... on the UI thread`) ainda não está
provada nem corrigida; o despejo de pilhas é o que a vai provar. `FIXED, NOT VERIFIED`.

## O próximo passo, e é um só

**INT-3 é o bloqueio real**: a app abre, o worker arranca e nunca carrega. Enquanto isso for verdade, o
Alt+C não tem nada para mostrar — e é por isso que "abrir o Sotto" hoje não mostra legenda nenhuma.
A ordem é: (1) instrumentar o spawn do worker para o log dizer **onde** ele parou; (2) só depois discutir
desempenho.
