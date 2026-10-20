# Recibo 2026-10-20 — o estado medido do ASR vivo na máquina do dono

Este recibo responde a uma pergunta que o dono faria ao ver o painel vazio:
**"o Sotto está a ouvir-me ou não?"**

Resposta curta: **o gate de fala está a funcionar; o que chega ao CABLE não é fala.**

## A medição (na app do dono, a correr, pid 39208, log `I:\cc-tmp\sotto-054348.log`)

`panel-state.json`, escrito pela propria app:

    worker.state          : capture-started
    worker.capturing      : true
    worker.device         : CABLE Output (VB-Audio Virtual ...)
    worker.noAudio        : true
    worker.noAudioEvidence: device-rotated reason=flat peak=0.0 floor=0.002
    worker.noAudioEvidenceAgeS : 3636.6        (a evidencia e antiga; o pico NAO e)

    WORKER_STATS (o tick mais recente):
      peak            0.287506      rms 0.04618680
      chunks          6503          music_gated_chunks 6486      gate_kept 17
      held_blocks     38916         speech_blocks       102
      captions        0             tokens              0
      frames          119           blanks              119        blank_frac 1.0
      gate            on            queue_drops 0       audio_s 3641.68

Ou seja: **o dispositivo TEM sinal** (peak 0,2875, rms 0,0462 — longe do
piso de 0,002), mas **99,7 % dos chunks sao descartados pelo gate de
fala/musica**, e os 17 que passam produzem **100 % de frames em branco**
(zero tokens).

## O gate esta CORRETO (isto e medido, nao um palpite)

`_main/speech-gate-oracle.py` -> `VERDICT: PASS`:

    thresholds: dbrange>=18.0 rms>=0.004 hold=3
      drone  synth:60Hz        chunks= 14  kept=  0  gated= 14   (100 % descartado)
      speech sample1.flac      chunks= 24  kept= 24  gated=  0   (100 % mantido)
      speech sample2.flac      chunks= 25  kept= 25  gated=  0   (100 % mantido)
      speech pt-br-sample.wav  chunks= 26  kept= 26  gated=  0   (100 % mantido)
      speech en-us-sample.wav  chunks= 15  kept= 15  gated=  0   (100 % mantido)

E medido a mao, com o gate real do `worker/sotto_worker.py`:
`pt-br-sample.wav` -> 26 chunks, **26 mantidos, 0 descartados** (100 %);
`sample1.flac` -> 24/24 mantidos.

O gate e um detector de **PRESENCA DE FALA** (o span dB do RMS dos sub-frames
de 20 ms dentro de um chunk de 560 ms), nao um classificador de musica. A
separacao medida: fala 27,5-40,0 dB (p10 = 20,2), drone 9,5-12,5 dB, tom puro
1,3 dB, ruido rosa 7,6 dB. O limiar vive na banda vazia entre 15,6 e 20,2.

**Logo: o sinal que chega ao CABLE tem energia mas nao e modulado como fala.**
Isso e musica, ou um leito ambiente, ou audio que passou por um compressor que
achata a dinamica -- o gate esta a fazer o que foi desenhado para fazer.

## O QUE O DONO TEM DE SABER (e o que NAO e defeito)

1. **O caminho do YouTube e o que funciona, e e 1:1.** A app le o texto que o
   player PINTA e serve a cue que o player esta a mostrar. Medido: 56/56
   amostras comparáveis iguais (`VERDICT: 1:1`).
2. **O ASR vivo so tem audio para transcrever se a FALA chegar ao CABLE
   Input.** E a lei de routing deste repo, escrita desde o inicio: *"a
   percurso de loopback do worker esta correcto. Se o Sotto ouve alguma coisa
   depende inteiramente do que o dono routed para um cabo virtual, e um nome em
   `config.json` nao o pode fazer acontecer."*
3. **O painel NAO esta a reclamar com vermelho.** O `status.kind` e `busy`
   (icone neutro). O `namedState: "no-audio"` e um campo de DIAGNOSTICO, e o
   `no-audio` vermelho -- que era o que o dono reclamou -- foi corrigido em
   2026-10-14 (`sotto_webview.py:852-878`, o no-audio e um sub-conjunto dos
   estados de erro e por isso e testado PRIMEIRO, para nao ser engolido pelo
   teste de erro).

## O que NAO foi medido

- **O que esta exactamente no CABLE.** Para isso era preciso capturar o
  dispositivo, e o device esta tomado pelo worker; nao se abre um segundo
  grabador no dispositivo do dono.
- **Se o video do YouTube esta routed para o CABLE.** O video que o dono estava
  a ver (`KcbdZP01DXM`) **nao tem legendas** (verificado: a faixa de
  `fetch_track` vem vazia, `reason=no-tracks-listed` -- e o video do outro
  teste, `4hKJ9X6rGFo`, tem 6 faixas e serviu a `en-orig` com 3532 cues, que e
  a que o player pintava). Com o ASR vivo parado por o gate, o painel mostra
  apenas a ultima legenda do YouTube.
