# A PINTURA DA LEGENDA DO YOUTUBE CONGELA COM A ABA ESCONDIDA (medido 2026-11-04, 11:0x-11:2x)

Instrumento: CDP directo (`127.0.0.1:9222`, `Runtime.evaluate`) na aba DO DONO, video
`https://www.youtube.com/watch?v=r-AsGBMDI6c`. Nada foi largado por mim: a aba ja' estava aberta.

## O que a aba entrega (facts)

| leitura | valor |
|---|---|
| faixa servida | `languageCode=en`, `kind=asr`, `vssId=a.en` |
| janela de legenda | `ytp-caption-window-container` > `ytp-caption-window-rollup` |
| linhas por cue | **DUAS** ao mesmo tempo (`.caption-visual-line`, 39 px de distancia, um text node cada) |

## O defeito

`document.visibilityState === 'hidden'` (aba numa janela atras; `Target.activateTarget` **nao** a levanta).

1. **40 s de reproducao**, `video.currentTime` a andar 523.9 -> 563.0: as duas linhas NUNCA mudaram
   (uma unica assinatura em 790 amostras a 50 ms).
2. Numa janela anterior, 40 s + um seek para `t=300`: as MESMAS duas linhas. A pintura esta' congelada
   mesmo atraves de um salto de tempo.
3. Depois de `location.reload()`: a legenda pintou certo durante alguns segundos,
   `['>> I am kind of impressed.', 'Are you E6 before the the rank up?']` a `t=518.6`, e **congelou outra vez**
   com `visibilityState` de volta a `hidden`.
4. `#movie_player.setOption('captions','track', {})` e de volta: `getOption('captions','tracklist')` devolve
   `[]` -- o subsistema de legendas NAO se recupera pela API; so' um reload o traz de volta, por segundos.
5. `video.currentTime` **e' legivel e avanca** com a aba escondida.

## Porque isto e' do Sotto, e nao so' do YouTube

A fonte do YouTube do Sotto le' exactamente esse DOM (`_cdp_painted_lines`). Uma pintura congelada
publica a linha velha indefinidamente, e a revelacao palavra-a-palavra re-desenha texto que ja' passou --
que e' a queixa do dono, verbatim: *"a legenda nao ta sincronizada direito. e parece que repete a
legenda de instantes atras no ao vivo, depois desbuga, e mostra ao vivo"*.

AGENTS.md ja' registava esta dependencia para a ARVORE DE ACESSIBILIDADE (*"com a aba do YouTube em
segundo plano o Chrome para de expor a legenda na arvore de acessibilidade"*, medido 2026-11-03: 3
minutos com um UNICO `YOUTUBE_CAPTION`). O que fica medido hoje e' que a fonte CDP **do DOM** tem a
mesma dependencia.

## A cura (lane `YtHiddenClock`)

Detector de pintura parada com a FAIXA como segunda testemunha (nao um limiar de tempo sozinho):
texto pintado inalterado + `video.currentTime` avancou mais que `STALE_S` + a faixa servida tem outra
cue no instante -> a pintura esta' velha, e desenha-se a cue da faixa no relogio do video ate' uma
linha distinta provar que a pintura voltou. `Emulation.setFocusEmulationEnabled` continua PROIBIDO
(medido: 108 ms de mediana e 5 s de p90 contra 2-5 ms sem ele).

## O que este instrumento NAO prova

- Nao prova a causa do congelamento dentro do Chrome (throttling de aba em segundo plano e' a hipotese,
  nao uma medicao do scheduler).
- Nao mede a aba em primeiro plano no ecra dele: `visibilityState` ficou `hidden` em todas as minhas
  leituras, incluindo depois de `Target.activateTarget`.
- Uma unica aba, um unico video, uma conta. `[INFERENCE]` para outro video.
