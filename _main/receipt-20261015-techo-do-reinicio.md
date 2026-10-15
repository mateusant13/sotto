# O TECTO DO REINICIO: a causa do stutter, e uma ordem tua que nunca foi cumprida

## O que o TEU log diz, preto no branco

    13:53:56  BRIDGE_SPAWNED pid=40600
    13:54:33  BRIDGE_LOAD_MS ms=36547  worker_load_s=33.38
    13:54:36  BRIDGE_STATUS_ERROR "Worker error at open-stream - WasapiError"
    13:56:42  BRIDGE_STATUS_NOAUDIO "Worker finished on silent-device"
    13:56:47  BRIDGE_EXIT rc=3  spawns=7  deaths=6

**36 SEGUNDOS a carregar ~1 GB de modelo**, morre porque o dispositivo esta
silencioso, e o shell reinicia -- para pagar os 36 s outra vez. Ja ia em **6 mortes,
7 arranques**.

## E tu JA tinhas ordenado isto

O AGENTS.md guarda as tuas palavras, verbatim:

> *"o worker morre e recarrega ~1 GB de modelo 88 vezes em 17 minutos (exit 3 a cada
> 2,5 min). arruma"*

**Nunca foi arrumado.** A escada de espera existe (15 s a 300 s) e evita um laco
quente, mas **nunca para**: ao fim de cada espera volta a carregar o modelo inteiro,
para sempre, porque um veredicto `silent-device` diz que a ROTAGEM esta errada -- e
recarregar um modelo nao arranja rotagem nenhuma.

**Esse churn e o teu stutter:** 1 GB de leitura de disco + churn de RAM + init de
CPU/GPU a cada volta. E e tambem porque *"abrir o sotto trava o PC"* -- abrir E
carregar o modelo.

## A cura, em `sotto_webview.py`

    no_audio_restart_cap=3        # depois de 3 mortes por silencio, PARA

E o `_schedule_restart` passou a ter, antes de armar o temporizador:

    if self.no_audio_restarts >= self.no_audio_restart_cap:
        log(BRIDGE_RESTART_SUPPRESSED ... why=restarting-cannot-fix-a-routing-problem)
        self.pending_error = { no-audio, "Nada foi roteado ... aperta Alt+C" }
        return

**E o caminho de volta existe:** o `show_panel` (o Alt+C) reapoe
`no_audio_restarts = 0`, portanto mostrar o painel e a forma de dizer "tenta outra
vez". Nao ha beco sem saida.

`py_compile` rc=0, 538 498 B. **Precisa de um arranque novo para valer.**

## UMA CORRECCAO MINHA, porque a medicao anterior estava contaminada

Eu medi "SEM captura" e vi `System` a 41-109% de um core, e conclui que a captura
estava limpa. **Estava -- mas a medicao estava suja:** o `BRIDGE_SPAWNED` das 13:53:56
caiu DENTRO da janela de medicao. O que eu media era o carregamento do modelo a
acontecer, nao uma maquina em repouso.

## O que fica por fazer

* O driver que come o tempo de DPC nao esta nomeado. O instrumento esta no disco
  (`C:\WINDOWS\system32\wpr.exe`, perfil `dpcisr`) e a corrida e curta.
* A legenda na janela propria continua provada em sonda e NAO confirmada na app.
