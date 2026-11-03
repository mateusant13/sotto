# A maquina calada nao e' um dispositivo partido — a escada que espera

Data: 2026-11-02, 21:0x-21:2x (sessao viva, pid 4404 -> 15940)
Alvo: `worker/sotto_worker.py` (`silent_desktop_hold`, o ramo da janela plana)
Portao: `_main/tap-silent-desktop-oracle.py` (8 arms + 6 bracos de fiacao + `--neg-arm`)

## 1. O que foi observado (verbatim do log, nao uma reconstrucao)

Instancia do dono, fresca e saudavel (`LIVE_CODE FRESH`, pid 4404, hotkeys registados,
painel nunca visivel, `PAINT_ACK ack=true wait_ms=16.0`). Com o desktop em SILENCIO:

    20:57:42.237  STATUS_APPLIED text="device-rotated (flat)"
    20:57:50.051  STATUS_APPLIED text="device-rotated (flat)"
    20:57:55.191  STATUS_APPLIED text="device-rotated (open-denied)"
    20:58:01.982  STATUS_APPLIED text="device-rotated (flat)"
    20:58:16.808  STATUS_APPLIED text="device-rotated (flat)"
    20:58:31.635  STATUS_APPLIED text="device-rotated (flat)"
    20:58:46.573  STATUS_APPLIED text="device-rotated (flat)"
    20:59:01.442  STATUS_APPLIED text="device-rotated (flat)"
    20:59:16.277  STATUS_APPLIED text="device-rotated (flat)"
    20:59:31.294  STATUS_APPLIED text="device-rotated (flat)"
    20:59:45.352  STATUS_APPLIED text="device-rotated (flat)"

**12 clientes WASAPI abertos em ~3 minutos** (`grep -c device-rotated` = 12), sempre
`peak=0.0`, a cada ~15 s, ate' um caption chegar por acidente (`NO_AUDIO_CLEARED
reason=caption captions=1`). Cada abertura e' um hitch no motor de audio que o dono
partilha com todas as outras apps -- o proprio ficheiro ja' documentava o custo
(*"a hard hitch on the audio engine ... which the owner read as a strong freeze every
few seconds"*).

## 2. A CLASSE, e por que os guardas que ja existiam nao a apanhavam

A escada pergunta *"este candidato produz um caption?"* (so' um caption assenta a janela,
de proposito) e, quando o audio muda de sitio, pergunta ao medidor VIVO
(`signal_ranked_next`). Faltava a pergunta simetrica: **"e se ninguem estiver a tocar
nada em endpoint nenhum?"** Nesse caso a tap actual JA' e' a resposta certa e reabri-la
so' custa o hitch. O tecto `MAX_ROTATIONS_WITHOUT_SIGNAL` nao serve aqui: mede
`counters["peak"]` (o maximo da RUN, pegajoso) e um unico pico de 0.79 no arranque
desarma-o para o resto da sessao.

## 3. A correcao (uma funcao pura + um ramo, nenhum protocolo novo)

`silent_desktop_hold(device_peak, tap_floor, live, window_s, silent_windows, max_window_s)`:

|o que o medidor diz|resposta|
|---|---|
|`{}` (nao consegui ler)|`None` -> rotaciona pela ordem que ja' tem (comportamento anterior)|
|existe endpoint acima do piso|`None` -> o audio mudou de sitio, rotacionar e' o movimento certo|
|TODOS abaixo do piso e a janela desta tap tambem plana|a janela SEGUINTE: 6 -> 12 -> 24 -> 48 -> 60 (tecto), **sem fechar a tap**|

No ramo `if now >= window_end:` o medidor vivo e' consultado ANTES de o `finally`
fechar a tap; a espera estende `window_end` e escreve `tap-silent-desktop` UMA vez por
candidato. `stop.wait`, nunca `time.sleep` (regra do proprio ficheiro, :5989).

## 4. A prova

Oraculo (`_main/tap-silent-desktop-oracle.py`): 8 arms verdes (dobra, tecto, `{}`,
sinal noutro endpoint, tap acima do piso, lixo no payload) + 6 bracos de fiacao.
`--neg-arm`: a guarda desligada numa COPIA ao lado do original, e os arms 1-2 caem —
`NEG-ARM PASS`.

Ao vivo, o MESMO desktop calado, worker novo (`worker_disk=828843083d7fd82d`):

    sessao antiga (4404): 12 device-rotated em ~180 s
    sessao nova  (15940):  1 device-rotated, e depois
    21:04:03.171 STATUS_APPLIED text="tap-silent-desktop"
    21:04:33.178 BRIDGE_SILENT_BENIGN ms=30000 state=no-audio restarts=0

Zero reaberturas depois da espera, e o no-audio continua BENIGNO (`restarts=0`): a tap
fica onde devia estar, a espera que o dono ja' conhecia do painel nao muda.

## 5. Uma licao de instrumento (custou-me dois minutos de diagnostico errado)

Tentei matar o worker com `Get-CimInstance | Where-Object { $_.CommandLine -match
'sotto_worker\.py' }` e o filtro devolveu VAZIO com a app viva: o `CommandLine` de um
processo que nao e' nosso vem vazio, e eu estava a um passo de publicar "a shell morreu
em silencio" (o log nao tinha `SHELL_EXIT`). O `sotto-relaunch.py --relaunch` mostrou a
verdade em duas linhas (`kill pid=4404 taskkill rc=128 'Acesso negado'` -> via token
`ok=True` -> `confirmado morto`). **A identidade de um processo desta app prova-se pelo
`pid=` do LOG** -- e' a regra que o AGENTS.md ja' impoe aos filtros de kill, e eu
quebrei-a com um censo, que e' o mesmo erro com outro nome.

## 6. O que fica por medir

* O custo da consulta (`live_render_peaks`, 0.76 s para seis endpoints) passa a
  acontecer no fim de cada janela plana. Nas janelas de 6 s isso e' ~13 % de um core
  durante 0.76 s; a partir da segunda espera a janela ja' e' >= 12 s e o peso cai.
  Medir no proximo dia de uso real, nao por estimativa.
* `BRIDGE_SILENT_BENIGN ... because="device-rotated reason=flat ..."` cita a ULTIMA
  rotacao como se ela fosse a evidencia corrente. Com a espera, a frase passou a
  descrever um evento antigo. Cosmetico, mas e' uma frase que mente sobre o presente.

## 7. Censo de disco e de latencia (medido, nao estimado)

O dono nomeou "espaco em disco desperdicado" como inaceitavel, por isso o censo foi feito com
`os.walk` e nao por impressao:

|o que|MB|o que e'|
|---|---|---|
|`_main/_ordem-before/`|1229,9|4 ficheiros TRACKED (o backup do "antes" da ordem de 2026-10-30) + os binarios ao lado|
|`_main/diar-models/`|800,9|pesos de diarizacao, **0 ficheiros tracked**; carregados so' por `_main/_diar-*.py` (sondas)|
|`_main/_redux-long/`|243,1|52 ficheiros tracked (amostras longas do Redux)|
|`_main/_design-lane/`|89,9|172 ficheiros tracked (instrumentos da lane de design)|
|`_main/_render-1710/`|72,8|9 ficheiros tracked (render do "antes")|
|`_main/_tmp-panel-noreveal/`|28,1|88 ficheiros tracked (sondas de painel)|
|`_cache/youtube-captions/`|9,4|89 ficheiros, o maior com 1 MB|

NADA disto foi apagado: 5 das 7 pastas tem ficheiros TRACKED (sao registo, nao lixo) e
`diar-models/` e' peso de sondas que o dono ainda referencia. O numero que importa hoje: o
`H:` tem **55 GB livres** de 517 GB, logo este censo nao e' a causa de nenhum ENOSPC -- e o que
estava a encher `G:` era outro disco.

LATENCIA DA LEGENDA (`CAPTION_OVERLAY_LAG age_ms=`, instrumento que ja' existia, sessao real
pid 36532): **246 / 873 / 202 / 162 ms**. O `age_ms` e' a idade da legenda no instante em que e'
pintada, portanto "aparece na hora" tem numero hoje: mediana ~200 ms, com um pico de 873 ms. O
pico nao foi investigado nesta passagem e fica como pista: e' o unico valor que se nota a olho.

O TOGGLE AO VIVO, nas pressoes REAIS dele (33 `HOTKEY_PRESSED role=live` em 36532): 33
`LIVE_ENABLED` a alternarem **on=true / on=false** sem uma falha. O gesto nao esta' a colar.

## 8. O ratchet do `code-health` recusou a minha primeira versao, e tinha razao

A guarda nasceu INLINE no `main` do worker e o `code-health` deu RED: `max_func piorou de
2333 para 2361`. O baseline so' se regenera *"com o dono de acordo"* (cabecalho do proprio
oraculo), portanto a resposta foi ENCOLHER o `main`, nao reescrever a meta:

* a decisao foi para `window_ended(...)` (module level, com a razao inteira na docstring);
* o estado da janela vive em `counters['silent']` (um dict), nao em dois locais novos;
* a linha do `tap_ledger` foi extraida para `tap_ledger_row(...)` -- construcao de dados pura,
  sem um campo mudado.

Medido depois: `LESS worker/sotto_worker.py 370327 B 6928 linhas maior funcao=2322 (main)` ->
`CODE-HEALTH VERDICT PASS`. O `main` ficou **11 linhas mais curto** do que estava antes desta
tarefa, e a escada ganhou uma espera.

## 9. O worker depois da extracao (o decode nao foi tocado, e prova-se)

    python worker/sotto_worker.py --selftest
    audio_s=13.440  load_s=41.654  infer_wall_s=7.905  rtf=0.588
    tokens=119  vad_gated=0  music_gated=0  peak_rss_mb=813.1
    providers=['CUDAExecutionProvider','CPUExecutionProvider']  quality=ok

Mesmo RTF e mesma qualidade do caminho de sempre: a espera nova nao encostou no infer.
