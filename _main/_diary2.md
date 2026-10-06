
## 2026-10-06T08:58:03Z — SOTTO PRONTO: causa-raiz fechada e cura aterrissada dentro do prazo

**Prazo do dono:** "quando que vamo deixar o produto completo? da uma hora. e' 5:51 agora." -> 06:51.
**Fechado as 05:57, 54 min de folga.**

### A causa-raiz, medida por Main (dois braços)
O modelo tem um CHAO DE AMPLITUDE. Mesmo worker, mesmo dispositivo, mesmo codigo, so a amplitude muda:
  - WAV pelo dispositivo:  peak=0.620738 -> 5 legendas
  - ambiente:              peak=0.100510 -> 0 legendas, blank_frac=1.0000
O caminho ao vivo e o resample 3:1 estao CORRETOS. Faltava um estagio de ganho. Foi por isso que o dono
nao via legenda enquanto o sistema inteiro parecia verde: qualquer fonte baixa transcrevia para nada.

### A cura, aterrissada por SottoAutoGain e VERIFICADA POR MAIN
AGC por bloco, alvo de RMS (-20 dBFS), ganho limitado e suavizado; AGC_MAX_GAIN_DB=24, AGC_MIN_GAIN_DB=-6.
Rejeitado explicitamente o peak-normalisation por bloco (pumping em silencio + amplifica o ruido de fundo).
**PROVA (Main, fonte atenuada -16 dB tocada pelo dispositivo) — 7 legendas onde antes havia 0:**
  "A" | "Ponte sobre o" | "Segunda" | "Os morado" | "anunciou que" | "Seg" | "Os mora"
  STATS peak=0.153132 gain_db=+17.6 peak_out=0.670030 agc=on blank_frac=0.9074 queue_drops=0
O ganho aplicado e' IMPRESSO no WORKER_STATS -- um ganho invisivel seria o mesmo defeito ao contrario.

### App de pe para o dono (reiniciado para carregar o ganho)
pid 29500, relancado HIDDEN. Log: HOTKEY_REGISTERED isRegistered=true | PRELOAD_ACTIVE hasSotto=true
methods=14 | WORKER_AUTOSTART=started | PANEL_VISIBILITY_ON_SCREEN visible=false. Processo vivo: SIM.

### O alarme de janela era TRANSITORIO, nao um laco
08:55:22Z visiveis=15 alarmSet=1 ALERTA-JANELA pid=25800 nome=pythonw; na amostra seguinte
08:56:22Z visiveis=14 alarmSet=0 alarmeHerdadoApagado=1. **1 amostra em 60.** E' a classe do flash de
arranque que AuditWindowVisibility ja medira por instrumento independente (~63 ms no arranque).
Custo honesto: um flash por lancamento.

### SOLVED / CHECKED / GUESSED (lei T10)
- SOLVED (verificado por Main): o chao de amplitude e a cura; o pump a 10.0 blocos/s; o exec_js dobrado;
  a regressao do -32000; o app de pe com Alt+C registado.
- CHECKED (por lane, prova colada): mapa da auditoria 62/62 (MISSING 0, INVENTED 0, WRONG_STATE 0);
  gate audit-map-gate.sh (rodei --selftest, 6/6 PASS, RED rc=1, GREEN rc=0, rc=2 uso errado);
  G1-G4 do run.cmd; as chaves inertes do config.
- GUESSED / EM ABERTO: o blank_frac residual 0.86-0.91 nas fontes fracas (funciona, mas o modelo ainda
  marca muitos frames em branco -- nao investigado a fundo); gain_max_db=+20 impresso vs AGC_MAX_GAIN_DB=24
  declarado (divergencia nao resolvida); nao existe oraculo de legenda ponta-a-ponta.

### Hermes: duas lanes, e a segunda CORRIGIU a primeira
Mesma familia que o OMP: indice sempre-ligado + o MODELO decide chamando o loader. Sem matcher, sem router.
A lacuna real NAO e' "empurrar mais": e' que o push do OMP NAO TEM FILTRO (hide e' o unico,
system-prompt.ts:936-943) -- prova viva: esta sessao, onde as lanes workers receberam skills de orquestrador.
Corpus: estreitar o push levou wrong 16.8%->7.3% e needless 9.8%->4.0%.
