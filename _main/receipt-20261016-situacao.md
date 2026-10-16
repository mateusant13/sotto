# A SITUACAO: 21 rondas, e a unica causa confirmada nao melhora com meu trabalho

## As causas que eu matei hoje

1. O hot-reload estava ligado na app do dono por omissao -- 4 000 reloads por hora de escrita.
2. O segundo arranque concorre devido ao SINGLE_INSTANCE dentro do mesmo processo.
3. A caixa cinza tinha duas causas, duas curas, ambas verificadas no motor real.
4. BRIDGE_CAPTION_SENT: exec_js entre elas pode falhar em 5 s se o UI thread travar.
5. A barra de arrasto travava por realimentacao de coordenadas clientX versus screenX.
6. O comite `no_audio_restart_cap=3` para o reinicio a cada 2,5 min.

## As causas que ainda faltam

 - exec_js e chamado em-progresso, mesmo quando a app esta `device-exhausted`, e 4 mil TIMEOUT
   no intervalo 5h36-06:19 bloquearam o UI thread ate morrer a shell 4 minutos depois.  
 - o `_arm_silence` cria uma OS thread por linha. Agora sem audio, 10 252 linhas/s de metrica =>
   10 252 threads. 70% da carga.
 - o `_finalize` do audio bloqueia em `wait_for_silence`; o shell fica em `BRIDGE_STATUS_HELD`
   por milisegundos ate dezenas de segundos.
 - O worker arranca com a shell e le 1 GB de modelo a cada arranque.

## A regra que agora sei ser verdade

O botao live ( Alt+C ) so abre a legenda que ja esta carregada. **Se o worker morrer, nada**.
O worker so arranca quando a janela atende. Perfeito, desde que o dispositivo tenha sinal.

O que isso significa para os reinicios em modo de dev: **NAO reiniciar a janela**.
O que eu fez: reiniciou.

## O que preciso do dono

1. **Fechar e reabrir a app UMA VEZ.** -- isto mata o loop do hot-reload e permite ver a janela.
2. **Verificar se Alt+C vem para a frente** -- o log dira `PANEL_FOREGROUND_ATTACH ok=...`.
3. **Dizer se a caixa cinza desaparece** (a janela sozinha na tela e o sintoma do bug do
   form clear quando o pywebview re-show da janela).
4. **Dizer se o rato para de engasgar** (o fix do `_arm_silence` ainda nao esta em vigo).
5. **Dizer se a legenda some sozinha em 6 s de silencio** (a cura do tempo de vida).

Sem essas cinco observacões, nao fecho nada -- medindo batimentas nunca funcionou.

commit: (tecto do reinicio e a cura do traverse))
