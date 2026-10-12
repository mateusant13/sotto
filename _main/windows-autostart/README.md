# Sotto arranca com o Windows (entregue 2026-10-12, pedido do dono)

**Estado medido:** tarefa agendada **`Sotto`** registada (`state=Ready`, trigger `MSFT_TaskLogonTrigger`,
accao `H:\sotto\app\webview\run.cmd`, working dir `H:\sotto\app\webview`, principal
`Interactive / Limited`, `Hidden=true`, `MultipleInstancesPolicy=IgnoreNew`).

```powershell
schtasks /query /tn "Sotto" /v /fo LIST
schtasks /run /tn Sotto      # lancar agora, sem esperar pelo proximo logon
schtasks /delete /tn Sotto /f
```

## Porque e que o launch passa pela tarefa e nao por um `Start-Process` meu

Medido hoje: um `Start-Process run.cmd` feito de dentro de uma sessao de trabalho do Lead
**morre com essa sessao**. O registo da shell mostra o app a transcrever normalmente e depois:

```
sotto: SHELL_CLOSING
sotto: BRIDGE_STOP reason=closing pid=29900
sotto: HOT_RELOAD_STOPPED reason=closing watchers=0 droppedUnsettledEvents=0
sotto: BRIDGE_EXIT pid=29900 rc=1073807364 spawns=1 captions=26 statuses=30 malformed=0
```

Ou seja: a app subiu, ouviu 26 legendas e foi morta quando o prazo do programa do Lead estoirou
(ficou presa a arvore de processos do Lead). A tarefa corre a app num contexto proprio: medido,
`shell pid=33248 ppid=14640` (Task Scheduler) e `worker pid=35872 ppid=33248`.

`IgnoreNew` + o lock de instancia unica do proprio app (`SINGLE_INSTANCE name=Local\SottoShell`)
significam que um segundo logon nao duplica a app.

## NAO MEDIDO

- nenhum logoff/logon real: o trigger `onlogon` esta registado e a accao foi testada por
  `schtasks /run`, mas o arranque automatico no boot do utilizador **nao foi observado**.
- se a consola do `run.cmd` aparece 1 frame no logon (a tarefa corre escondida, mas isso e
  inferencia do `Hidden=true`, nao uma amostragem).