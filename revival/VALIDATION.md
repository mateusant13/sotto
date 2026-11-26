# Behavioral Validation Contract — sotto

Cada linha e' uma afirmacao que o **consumidor real** faz sobre o produto, com o braco adverso que a
pode derrubar. Um `proof_cmd` que sai 0 sem nenhuma linha `PASS` nao conta; e um `CANNOT-MEASURE`
nomeado e' um HOLE declarado, nunca um verde.

| ID | User Surface | Happy Path Expected | Adverse / Failure Arm | Proof Command |
|---|---|---|---|---|
| VAL-01 | Legenda do YouTube no ecra | a linha pintada corresponde ao instante do player; pausa real apaga o ecra | pausa DESMENTIDA pelo relogio em movimento nao apaga (`why=disagreed`); foto velha nao prova pausa | `python _main/yt-pause-disagreement-oracle.py --log _main/webview-run.log` → `CLEAN` rc 0 |
| VAL-02 | Seek / skip do video | um recuo > `SEEK_BACK_S` e' um seek nomeado, uma vez, e o relogio re-ancora | recuo menor (jitter de 1,0 s) NAO e' seek; duas leituras do mesmo carimbo nao sao duas medidas | `python _main/youtube-monotonic-oracle.py` (30 arms) |
| VAL-03 | Captura do player como bytes | 466 amostras a 50 ms com `currentTime`/`paused`/`rows`, acoes carimbadas no instante pedido | fixture sem faixa de legenda nao pode passar o braco da pintura; um congelamento e' provavel contra a track | `python _main/yt-capture-replay-oracle.py` → 43 arms PASS, rc 0 (+ `--neg-arm` 7/7, rc 1) |
| VAL-04 | Pixels da legenda | tinta existe para a linha, a largura segue o texto, A→B→A volta ao raster de A | legenda vazia = zero tinta; cache de pintura nunhuma serve outra linha | `python _main/overlay-ink-oracle.py` |
| VAL-05 | Relogio de pintura fora do ecra | pior erro <= 16,667 ms em 745 amostras reais; nada e' aberto no ecra | orcamento de um frame por 60 Hz derruba o braco | `python _main/yt-headless-paint-oracle.py` → `WORST TIMING ERROR: 12.133 ms` |
| VAL-06 | Historico de legendas | 200 legendas pela regra real dao 200 linhas distintas, idempotente | a mesma linha entregue duas vezes nao duplica (a forma do defeito "517 de 2077") | `python _main/history-replay-oracle.py` |
| VAL-07 | Transcricao ao vivo | o worker publica linhas reais carimbadas por voz (`source=voice:speaker-N`) | payload `"fake": true` e' RECUSADO pelo nome; silencio responde `CANNOT-MEASURE reason=silence` | `python _main/speaker-sidecar-oracle.py` → arms 114/114, mutants 16/16 |
| VAL-08 | Microfone no mesmo stream | o audio do dono entra no mesmo bloco do loopback, ganho constante, resto carregado para o bloco seguinte | sem microfone o tap de loopback volta INTACTO; um cabo virtual nao vira "microfone" | bateria `mic_battery` dentro de `_main/speaker-sidecar-oracle.py` |
| VAL-09 | Gestos Alt+C | 1 toque = faixa de baixo; 2.º toque dentro de 0,40 s = painel da direita; fora da janela esconde | 200 toques nao abrem o painel da direita por toque unico e nao crescem nenhum contentor | `python _main/altc-gesture-oracle.py` e `python _main/altc-soak-oracle.py` |
| VAL-10 | Gates da bateria | o exit code E' o veredicto; `BATTERY-VERDICT` diz GREEN/RED e o numero de passos | um passo saltado nao e' um portao que passou; um `red-as-expected` cujo mutante nao derrubar e' `MISSED` | `python _main/battery-launch.py --verify` |
| VAL-11 | Orcamento de metrica por I/O | `benchmark_history.py run --gate` recusa qualquer metrica acima do tecto | o proprio runner ja' foi apanhado a dar verde falso (17,9 s de um comando quebrado) e a linha foi apagada do historico | `python benchmarks/budgets.json` -> `python C:/Users/Administrador/.agents/skills/project-revival/scripts/benchmark_history.py run --repo . --label check --gate` |
| VAL-12 | Triagem de DMs do watcher | um DM que se declara `CANNOT-MEASURE` devolve `why=no-rate-in-claim` com a identidade resolvida | pid morto sai `UNKNOWN`, nunca `MISATTRIBUTED`; assunto sem classe sai `unparsed-section` | `python _main/dm-triage-oracle.py` → 6 arms PASS (+ `--neg-arm` 3/3, rc 1) |
| VAL-13 | Holes declarados | cada metade que exige o dono e' `CANNOT-MEASURE why=<nome>` num doc, nunca um pedido a ele | distro WSL ausente sai `BEND-GATE SKIPPED: NOT INSTALLED` (rc 0) e as leis ficam `UNMEASURED` | `python _main/bend-laws-gate.py` + `docs/por-medir.md` |
