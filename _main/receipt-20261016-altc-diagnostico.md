# ALT+C: O DIAGNOSTICO DO SUBAGENTE, E A LINHA QUE FALTAVA

## A pergunta que ninguem respondia

O dono: *alt c nao ta funcionando*. Havia duas hipoteses e nenhuma medida que as separasse:

  (a) a tecla NAO CHEGA ao shell (registro, foco, outra app a roubou);
  (b) a tecla chega e o ciclo IGNORA-a.

**As duas produziam o mesmo log (nada).** E era isso o defeito de instrumentacao.

## O que o subagente MEDIU (so leitura, nao lancou nada)

  * Na shell de 05:43 o thread da hotkey estava VIVO e a espera (TID 25476), registo intacto
    (`HOTKEY_REGISTERED register=true`), e ZERO linhas de erro da familia HOTKEY em todo o
    log -- nenhum DISABLED/REGISTER_FAILED/TRY_FAILED/FALLBACK/UNAVAILABLE/HANDLER_FAILED.
  * Censo: UMA so shell; `SINGLE_INSTANCE already_running=false` em cada arranque. Ninguem
    roubou o Alt+C.
  * O contador `transitions` ficou em 5 durante 11 minutos -- **nenhum WM_HOTKEY foi
    processado depois de 05:57:11.327**.
  * HWND 655502 existia com `IsWindowVisible=false`: escondido a serio.
  * **`PANEL_FOREGROUND_ATTACH` = 0 em TODO o log.** A minha cura do primeiro plano (72b4cbb)
    NUNCA CORREU -- e nao podia: o `PANEL_SHOWN reason=hotkey` desde as 08:08 tambem e 0.
  * A shell de 08:08 (pid 44100) **morreu as 08:43:47 SEM `SHELL_CLOSING`** -- morte dura.
    Nos ultimos 40 s dela: **198 `exec_js TIMEOUT after 5.0s`**, depois device-exhausted, depois
    silencio.
  * `PANEL_FOREGROUND_UNLOCK`: **160 no total, ok=true 146, ok=false 14** -- e em cada ok=false
    o `PANEL_SHOWN` diz `visible=true`. **A janela FOI mapeada; so o foco falhou.** Logo o foco
    NAO explica 'nada no ecra'.
  * `ForegroundLockTimeout=200000` ms (default), `AllowSetForegroundWindow` e
    `SPI_SETFOREGROUNDLOCKTIMEOUT` em ZERO ocorrencias na shell.

## DUAS CORRECCOES AO QUE EU TINHA DITO, e sao dele

  1. **Eu disse que o worker estava ausente. FALSO: o pid 20164 corria.** O censo anterior era
     meu e estava errado.
  2. **Eu apontei o foreground como a causa de 'Alt+C nao funciona'. Nao e:** dos 14 ok=false
     do log inteiro, 4 foram hoje, e em todos a janela foi mapeada. **O que explica e a shell
     estar MORTA.**

## A linha que faltava, e esta aplicada

O `HotkeyThread` conta as pressoes (`self.pressed += 1`) desde sempre. **E nunca escreveu esse
numero numa linha.** Acrescentado:

    self.log_fn(f'HOTKEY_PRESSED count={self.pressed} thread={self.thread_id}')

A partir do proximo arranque, cada pressao deixa rasto proprio -- e a pergunta (a) contra (b)
passa a ter resposta directa, em vez de se deduzir pela ausencia de outras linhas.

`py_compile` rc=0.

## O que NAO esta medido, e o subagente di-lo

  * Se o SO chegou a POSTAR o WM_HOTKEY (isso exige uma tecla fisica ou o selftest).
  * **Porque morreu a shell de 08:08** -- e a pista mais forte que existe: 198 `exec_js
    TIMEOUT` em 40 s antes de morrer. **Uma thread de UI bloqueada 5 s por chamada, 198 vezes,
    e a causa candidata numero um.** Nao atribuida.
  * O efeito do meu `AttachThreadInput` -- nunca correu.
