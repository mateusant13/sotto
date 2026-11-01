# Parakeet como segundo pass e lifecycle do worker (ORDEM 3)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 3. O Parakeet é o segundo pass, com lifecycle inteligente
> *"legenda ao vivo, com o modelo nemotron... qualquer legenda que ja passou (nao é mais ao vivo) tem que
> ser processada tambem pelo parakeet, ou imediatamente, ou com delay, ou quando seguro de fazer isso...
> se minha legenda ao vivo ta desativada e eu nao to usando, é só o parakeet que comanda."*

O mecanismo existe (`worker/redux_batch.py`, `worker/redux_live.py`, flag `--redux-when-hidden`,
`SOTTO_REDUX_LIVE=1` em `app/webview/run.cmd`). **BURACO DECLARADO, RE-MEDIDO E FECHADO EM 2026-10-23.**
O texto anterior dizia que `on_external_captions_released()` **não** trazia o worker de volta. Re-lido o
método nesta revisão: **traz** — atrás de **quatro guardas** e de um **piso de 45 s**
(`EXTERNAL_RESUME_MIN_S`): shell a morrer (`exiting` → não arranca, senão fica um órfão que carrega 1,2 GB
depois de a app fechar, medido 2026-10-20), release sem park, em pausa, e sem painel **nem legenda**
visíveis; dentro dos 45 s loga `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED` e **não** mexe no relógio. O
que faltava não era código: era **prova**. Isso é `_main/external-resume-oracle.py` — **8 braços / 8
mutantes** (`sem-guarda-exiting`, `sem-guarda-park`, `sem-guarda-pausa`, `sem-guarda-visivel`,
`legenda-nao-conta`, `sem-piso-45s`, `relogio-antes-do-piso`, `relogio-nao-anda`), na bateria com o braço
negativo `red-as-expected-external-resume`. **A lição:** um `AGENTS.md` que descreve um buraco já fechado
manda trabalho para o sítio errado; re-medir antes de repetir (regra 1).
