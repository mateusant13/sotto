# RECIBO — dois oraculos voltam a medir o que dizem medir (2026-11-03)

Dois portoes estavam VERMELHOS por o INSTRUMENTO ter ficado para tras do codigo. Em nenhum
dos dois se afrouxou uma regra: cada um continua a exigir o mesmo facto, e o braco negativo
de cada um apanha os mesmos mutantes que apanhava.

## 1. `_main/youtube-verbatim-oracle.py` — `shell-calls-painted-lines` (`calls=0`)

O QUE MUDOU NO CODIGO. Os dois ramos que pintam as palavras do player sairam de `_youtube` e
passaram a helpers (`_yt_painted_lines_match`, `_yt_aligned_painted`, `_yt_no_clock_lines`,
`_yt_clock_cue`). O `_youtube` delega. A arm procurava `_yt_rows(painted,` DENTRO do corpo do
`_youtube` e o corpo deixou de o conter.

O QUE A ARM PASSOU A MEDIR. As mesmas DUAS chamadas reais, contadas por AST nas funcoes que
pintam: `total >= 2`, com o nome das funcoes no `evidence` (`calls=3 em ['_yt_aligned_painted',
'_yt_no_clock_lines', '_yt_painted_lines_match']`). Uma chamada a menos volta a dar RED.

```
$ python _main/youtube-verbatim-oracle.py | tail -2
{"cases": 11, "caught": 11}
YOUTUBE-VERBATIM VERDICT: PASS      rc=0
$ python _main/youtube-verbatim-oracle.py --neg-arm; echo rc=$?
rc=1
```

## 2. `_main/youtube-track-wiring-oracle.py` — 2/12 arms (agora 12/12)

A arm que estava certa era a do CODIGO; o cenario estava a modelar um app que ja' nao existe.
QUATRO factos novos, cada um medido no shell vivo:

1. **A FONTE E' PUBLICADA POR UMA THREAD** (`_yt_src_resolver_start`, 2026-11-03): `_read`
   ja' nao pergunta `player_source` no caminho — le' `_yt_src_cache`, que expira aos 6 s e e'
   republicada de 2 em 2 s. Sem publicar a cache, o primeiro tick via `source=''` e caia na
   varredura da pagina: `text []`, `page_reads 1` em dez arms. O cenario publica a fonte a
   cada tick, que e' o que a thread faz.
2. **A PORTA CDP MANDA** (`_yt_cdp_ensure`, `_yt_identify`): com uma fonte viva e o id
   conhecido, `_yt_identify` devolve `wait=True` e o tick devolve `[]` sem ler a faixa. Este
   oraculo mede a rota da FAIXA; a porta CDP tem os seus proprios instrumentos
   (`_main/_yt-cdp-*`). A porta e' fechada no cenario (`_yt_cdp_ensure -> None`).
3. **O RELOGIO DO PLAYER NAO ANDA COM O `at` DO CENARIO** (`_ensure_clock_sampler`): a shell
   amostra e interpola com `monotonic()`. Medido: com `at` a +2 s e `t` 19,5 -> 30,0 a leitura
   devolvia **t=21,5** — dentro da PRIMEIRA cue — e o a2 (buraco entre cues) ficava vermelho
   com o codigo certo. O par `(at, t)` passou a ser coerente: o mesmo intervalo de parede que
   o video andou.
4. **O ESTACIONAMENTO VIROU UM PEDIDO** (`set_engine_park`, 2026-11-03): o release ja' nao
   mata o processo — limpa o pedido (`parks=['captions', None]`) e o motor recarrega sozinho.
   `parked`/`resumes` passaram a ler `parks`; `resumes` conta o pedido LIMPO, e `spawns`
   (`start_worker`) fica registado como facto separado, porque um spawn aqui seria a recaida
   das duas cargas de 1,2 GB em tres minutos.

```
$ python _main/youtube-track-wiring-oracle.py | tail -1
VERDICT: PASS  arms 12/12  mutants 5/5        rc=0
$ python _main/youtube-track-wiring-oracle.py --neg-arm; echo rc=$?
rc=1
```

O `mutants 5/5` e' o que garante que o cenario novo nao ficou cego: os cinco mutantes que
quebram a regra (a pagina nao e' despromovida, sem faixa o micro nao volta, a faixa real
liberta como a pagina, a cue real nunca e' emitida, o Stremio e' despromovido) continuam a
derrubar arms depois das quatro correccoes.

## NAO medido aqui

* Nada disto correu com a app a tocar o YouTube do dono: e' comportamento do WATCHER com as
  tres costuras de ecra substituidas (`GetForegroundWindow`, `caption_lines`, `player_time`).
  A prova viva continua a ser o log da instancia dele.
