
## 2026-10-06T08:36:30Z — Sotto: dois fixes medidos + o erro do denominador (duas vezes)

**Pergunta do dono:** "tu parou por qual motivo?" — resposta honesta: parei porque ENTREGUEI, nao porque
estava bloqueado. O `#612` estava identificado e eu nao o executei. Regra que fica: **entregar um
resultado nao e' um ponto de parada quando existe trabalho identificado e desbloqueado.**

**#612 FECHADO E VERIFICADO.** `sotto_webview.py` chamava `self._ui(_run)` DUAS vezes em `exec_js`
(uma no `try`, outra incondicional) — cada script entrava na pagina a dobrar. Removida a segunda.
Prova: `pythonw sotto_webview.py --with-worker --log _v612.log` -> `PRELOAD_INSTALLED
where=initialization-completed`, `PRELOAD_ACTIVE hasSotto=true methods=14`, `WORKER_AUTOSTART=started`,
`PANEL_VISIBILITY_ON_SCREEN visible=false`, **`exec_js failed count = 0`** (3133 B de log).

**O periodo do pump do WASAPI — curado e medido.** `worker/wasapi_loopback.py:475` tinha
`period = max(0.005, block_ms/1000/4)` = **25 ms**, mais LENTO que o anel deste endpoint
(`GetBufferSize` = 1056 frames = **22 ms** a 48 kHz), logo o anel transbordava em cada ciclo.
Agora `period = min(0.005, max(0.001, block_ms/1000.0/20.0))` = 5 ms.
**Medido:** 100 blocos em 10 s = **10.0 blocos/s**; 200 em 20 s = **10.0 blocos/s**.
Antes: 8.15 blocos/s.

**E o `blank_frac=1.0` NAO era a taxa de captura.** Com o audio a chegar a 100%, o modelo continua a
devolver `blanks=35/35`. Hipótese morta; a busca estreita-se para o conteudo (`peak=0.10` = ambiente,
nao fala) ou o front-end.

**ERRO PROPRIO, DUAS VEZES, O MESMO:** dividir `audio_s` pelo WALL DA INVOCACAO (que inclui o
arranque: carregar o modelo + abrir o dispositivo). Produziu duty=0.366 e depois 0.815/"36%" — ambos
FALSOS. O correto e' o tempo desde que o STREAM ABRIU. Regra mecanica: **todo ratio carrega o seu
numerador E o seu denominador na mesma linha.**

**Despachado:** `SottoRunCmdGaps` (#613, as 4 lacunas do run.cmd) e `SottoConfigInert`
(#614 + #610, chaves inertes + provider no modelo errado + o oraculo de cadencia em falta).
Registados em `state/progress/registro-em-voo.jsonl` (+1729 B).

**Auditoria: 8/8 eixos entregues** em `H:/sotto/docs/audit/`. `AuditWindowVisibility` fecha com:
o painel ALCANCA o ecra sem accao do dono por ate ~63 ms no arranque; o censo da casa esta ERRADO
para este eixo (`MainWindowHandle != 0` = IsWindowVisible SEM teste de monitor, logo dispara para
uma janela WS_VISIBLE estacionada fora do ecra).
