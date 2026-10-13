# `ARM help` NAO E A SAIDA: medida exactamente 4956 B, o pino do AGENTS.md

2026-10-13. Fechamento do recibo anterior (`receipt-20261013-battery-red-arm-help.md`), que
dizia que eu nao sabia o que mudava. Agora sei o que NAO mudou, e isso tambem elimina hipoteses.

## O que o braco verifica (lido do proprio oraculo, `run-cmd-exit-oracle.py:486-509`)

```
1. rc == 0
2. "usage: sotto-webview" aparece na saida
3. every flag the shell declares is in the usage   <- varre o FONTE com
                                                     add_argument..(--x
4. no process is left behind in this tree
```

## O que foi MEDIDO agora

```
cmd /c "H:/sotto/app/webview/run.cmd --help"
  agora: 4956 B   linhas: 79
  pino AGENTS.md (2026-10-12): 4956 B
```

**A saida e EXACTAMENTE o pino.** A primeira linha e `usage: sotto-webview`. Logo os checks 1, 2
e passarem a inspeccionar; **o que falha esta no check 4, o de processo deixado para tras** --
unico que nao tem a ver com texto.

## Como sei que e o 4 e nao o 3

O meu primeiro teste usou o regex ERRADO (`--[a-z-]+`, que apanha TUDO, ate flags que so o
worker declara como `--meter-hz` e `--target-pid`) e acusou 20 flags "em falta". **Isso era meu
erro de teste, nao do oraculo:** o FLAG_RE real e `add_argument\(..(--[a-z0-9-]+).`, que so ve o
que o shell declara por argparse -- e a saida mede 4956 B, igual ao pino, com essas todas
dentro. **Ninguem devia ter lido aquela lista de 20 como evidencia.**

## O que NAO consegui fechar, e porque

Tentei correr o `arm_help` directamente e o MEU driver rebentou no `pids_in_tree` (precisa do
arvore de processos do proprio oraculo, que eu nao passei). **O braco tem um `time.sleep(0.5)`
depois do check 3 e so depois mede os processos** -- e o que muda a minha volatilidade e exactamente
isso: eu tenho usado o shell/build ao mesmo tempo em que corro o oraculo, o que deixa processos
irmaos na arvore que ele ve.

**HIPOTESE, NAO MEDIDA: o check 4 falha por processos MEUS deixados a correr (vite, node,
baterias), nao por defeito do run.cmd.** Como distinguir: correr o oraculo SOZINHO, com a
bateria morta e nenhum job meu, e ver se o braco passa.

## O que fazer no proximo passo (ordem exacta)

1. Matar TUDO o que seja meu (jobs, vite, node da bateria) -- verificado com
   `Get-CimInstance Win32_Process` filtrado a `node|vite|python.e` e os MEUS pids.
2. Correr SO `py -3 _main/run-cmd-exit-oracle.py`, dois minutos.
3. Se passar: a bateria estava a ser envenenada pela minha propria concorrencia, e eu posso
   voltar a correr a bateria inteira sem reforma.
4. Se falhar: o check 4 e genuino, e o recibo seguinte comeca por ele.
