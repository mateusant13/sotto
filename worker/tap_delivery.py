# -*- coding: utf-8 -*-
"""O QUE "SEM BLOCOS" SIGNIFICA -- e como isso deixa de ser invisivel.

Extraido de `sotto_worker.py` em 2026-11-17 (o `code-health` recusa crescer
aquele ficheiro, com razao: `main` ja' tem 2 800 linhas). O worker importa daqui
o censo e a linha de diagnostico; a POLITICA (`tap_stall_reason`) continua no
worker porque duas oracles lhe extraem o fonte por AST.

## O DEFEITO MEDIDO (2026-11-16, chamada de Discord real)

5 h 22 de parede, 3 h 45 de audio no ring. O escritor do ring guardou 96,4 % do
que a TAP lhe entregou, logo a perda e' a montante: a tap parou de entregar
durante 2 325,2 s DENTRO do mesmo ficheiro (`173532.24k.opus`: 2 525,2 s de
parede, 200 s de som). Tres rotacoes do mesmo worker no dia, e a rotacao
`AG251F1WG2 (NVIDIA High Definition Audio)` com `blocks=0 packets=0` em 630,3 s
assenta no mesmo buraco.

A politica de tap parada (`tap_stall_reason`, 2026-10-12) tinha UMA resposta
para "nao ha' blocos": `endpoint-idle` -- "nada esta' partido, o endpoint nao
renderiza" -- e a unica cura (`idle-rearm`) chegava aos 300 s e reabria o MESMO
endpoint, ate' 20 vezes. Um endpoint que se cala porque o audio MUDOU de sitio
ficava entao a esperar exactamente o que nunca ia acontecer, porque a pergunta
seguinte era feita no mesmo sitio.

## AS QUATRO COISAS QUE "ZERO BLOCOS" ESCONDE

O medidor vivo (`wasapi_loopback.live_render_peaks`: so' `IAudioMeterInformation`,
nenhum `IAudioClient` aberto, ~0,76 s para 6 endpoints) responde:

  * `elsewhere` -- o audio esta' a sair NOUTRO endpoint: re-resolver JÁ'.
  * `here`      -- o NOSSO endpoint renderiza e a tap entrega zero: o cliente
                   esta' encravado; um cliente novo e' a cura.
  * `quiet`     -- nada renderiza na maquina: esperar e' honesto (o ring nao
                   perde nada porque nada ha' para gravar).
  * `unknown`   -- sem leitura: NAO e' "sem sinal" (a mesma direcao de falha de
                   `silent_desktop_hold`), logo nao justifica churn.

## O PRECEDENTE: A TAP NOVA JÁ ERA CENSADA, A TAP SETTLE NAO

`dead_first_block_plan` (2026-11-04) faz exactamente esta pergunta aos 2 s de um
candidato novo: `capture-started` 09:57:41 -> `device-rotated (flat)` 09:58:25
com `device_blocks=0` o tempo todo, e o candidato morto passou a cair aos 2 s em
vez dos 44. A tap SETTLE -- que e' onde uma chamada de 5 h passa 99 % do tempo --
nunca recebeu o mesmo censo. Era o unico caminho do laco sem medidor.

## PORQUE A LINHA TEM DE LEVAR NUMEROS

O buraco de 2 325,2 s nao deixou UMA linha com a duracao no log da shell: ele
aparece como `device-rotated (idle-rearm)` com `repetidas_silenciadas=357`,
porque `_status_applied` (`app/webview/sotto_webview.py`) regista so' o texto
que MUDA. Uma frase sem numeros e' silenciada para sempre. Pior: `tap-engine-
parked` responde ao pedido "o motor esta' largado" e a `window_ended` isso
bastava para esticar a janela 12 vezes -- o motor largado cala as LEGENDAS, nao
o tap, e o ring continuou a gravar 200 s de som em 42 minutos.

## O PARQUE LEGITIMO QUE DUROU DUAS HORAS (o mesmo dia, o outro buraco)

`_main/webview-run.log` 2026-11-16: `EXTERNAL_CAPTIONS_ENGINE_PARKED
source=external:youtube:track pid=20584` as 16:55:44 e `..._RESUMED
reason=player-stopped` so' as **18:07:16** -- 1 h 11 m 32 s. Parque outra vez as
18:07:44, retomado as 19:08:39: mais 1 h 00 m 55 s. O parque NAO estava errado
(o dono estava a ver um video com legendas externas, e a shell tinha o motor
emprestado); e o resume TAMBEM chegou (`RESUMED` esta' no log, 13 vezes no dia,
logo nao e' um resume edge-triggered comido). O que estava errado e' a tap nao
ter perguntado NADA nesse tempo: enquanto `parked` e' verdade, `window_ended`
devolve `now + grown` sem ler o medidor, e no tecto de 12 janelas so' re-varre a
escada. Resultado medido: **19 `capture-started` em 2 h 26**, um endpoint a cada
~7,7 min, `tap-engine-park-rescan` 12 vezes, e um deles foi o `AG251F1WG2
(NVIDIA High Definition Audio)` com `window_s=630,3 blocks=0` -- o HDMI que nao
tem altifalantes. As 19:07:19 a primeira legenda depois do buraco
(`NO_AUDIO_CLEARED reason=caption`, `evidence="device-rotated reason=flat
peak=0.05202 from=VoiceMeeter Input"`) prova que havia audio a renderizar
durante o parque, noutro endpoint.

E o que o corpus guardou desse tempo: **nenhuma linha com duracao**. Os `err()`
do worker nem chegam ao log -- a shell so' encaminha as etiquetas de
`ENGINE_VISIBLE_TAGS` (`app/webview/sotto_webview.py:1642`, `:24860`), e
`TAP_STALLED`/`TAP_IDLE` nao estao la' (0 ocorrencias em 60 MB de log). O canal
duravel e' o STATUS, cujo texto e' `state (reason)` (`:25193`) e que a shell
desduplica por texto EXACTO (`_status_applied`, `:12741`). Logo a linha
duravel tem de ser um status com os numeros dentro do `reason` -- e' isso que
`delivery_stall_line` produz, e `_main/tap-delivery-stall-oracle.py` fixa.

## A TAP SETTLE QUE MORREU CALADA (2026-10-11, o precedente)

`device_blocks` congelou em 59 (5,6 s de audio, 6 legendas) e o worker ficou 34
minutos ali enquanto o endpoint por omissao levava `peak=0.1444`: o painel dizia
"Audio tap silent", Alt+C nao mostrava nada, e o laco girava a 10 Hz sem nunca
perguntar se a tap ainda entregava. O sinal e' CHEGADA DE BLOCO, nao pico: um
endpoint bombeado mas calado entrega blocos SILENCIOSOS, um esfomeado ou morto
nao entrega nenhum.

## O QUE NAO ESTA' AQUI

Nao ha' keep-alive. Nao ha' timer que refresque um carimbo. `last_block_at` e'
escrito pelo callback do tap, e e' contra ele (e nao contra a abertura da janela)
que `window_ended` mede a stall: a pergunta e' "ha' quanto tempo ninguem entrega",
e a resposta vem do unico ponto por onde passa todo o bloco.
"""
import os


def tap_census_verdict(live, own, floor=0.002):
    """('here'|'elsewhere'|'quiet'|'unknown') para UMA leitura do medidor. PURE.

    `{}` NUNCA vira `quiet`: sem leitura nao e' sem sinal. `own` ausente (rung
    sem `endpoint_id`) nao pode localizar o audio, logo nao justifica churn.
    """
    if not live:
        return 'unknown'
    try:
        peak = max(float(v) for v in live.values())
    except (TypeError, ValueError):
        return 'unknown'
    if peak <= float(floor):
        return 'quiet'
    if own is None:
        return 'unknown'
    try:
        return 'here' if float(live.get(own) or 0.0) > float(floor) else 'elsewhere'
    except (TypeError, ValueError):
        return 'unknown'


def delivery_stall_line(counters, endpoint, stalled_s, action, next_name=None):
    """`TAP_DELIVERY_STALLED ...` UMA vez por episodio, ou None. PURE (sem I/O).

    A chave do episodio e' o contador de blocos MAIS o endpoint: um bloco
    entregue abre um episodio novo, um segundo aviso com a mesma chave e' o
    mesmo episodio. O texto leva a duracao, o endpoint e o pid porque e' isso
    que o corpus seguinte precisa de ver -- a shell so' loga texto diferente.
    """
    key = (counters.get('blocks'), endpoint)
    if counters.get('delivery_said') == key:
        return None
    counters['delivery_said'] = key
    return ("TAP_DELIVERY_STALLED endpoint=%r stalled_s=%.1f pid=%d action=%s next=%r"
            % (endpoint, float(stalled_s), os.getpid(), action, next_name))
