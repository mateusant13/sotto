# RECIBO — a primeira conversão CLR acontece sozinha (2026-11-12)

Tudo o que segue foi medido nesta árvore, hoje. Onde a linha diz `PASS`, o comando está ao lado.

## 1. O defeito, e como ele foi encontrado

O dono reportou que a app não abria. O `run.cmd` dizia:

```
HANG rc=4 by=run.cmd-readiness
```

O log da app parava a meio do arranque sem uma linha de erro — porque o processo **morria**, e um
processo morto não escreve despedida. A fonte é o log de eventos do Windows:

```
Get-WinEvent -FilterHashtable @{LogName='Application';ProviderName='.NET Runtime'}
```

**Oito eventos `NullReferenceException`, os oito hoje** (19:32:09, 19:53:53, 19:58:30, 20:00:41,
20:03:26, 20:06:20, 20:08:15, 20:16:58). Nos dez dias anteriores: **ZERO**. Cada um coincide com uma
largada real da app, não com as minhas sondas.

As duas formas de pilha são a mesma classe:

```
TypeManager.AllocateTypeObject <- ReflectedClrType.GetOrCreate
    <- Converter.ToPython <- MethodBinder.Invoke
BorrowedReference.DangerousGetAddress <- Converter.ToPython
    <- MethodBinder.Invoke <- ManagedType.Init <- ClassBase.Init
```

## 2. A causa

O pythonnet constrói o tipo Python que representa um tipo .NET na **primeira** conversão e guarda-o
num cache global. Quando a primeira conversão do **mesmo** tipo acontece em duas threads ao mesmo
tempo, ele desreferencia um ponteiro que a outra thread ainda não publicou. E é uma
`NullReferenceException` **gerida**: mata o processo, e o `try/except` de Python não a apanha —
por isso não havia nada no log.

Esta app arranca exactamente nesse estado. `webview.start()` entrega a thread da UI a um
`_on_before_show` que converte `Icon`, `Color`, `Size`, `Rectangle` e `Func[Type]` enquanto as
threads da shell já correm (o observador do `Ctrl+Space`, o laço de leitura, o `_ui`).

## 3. A cura

`app/webview/sotto_webview.py:warm_clr_types()`, chamada na **primeira linha útil** do `main()` —
antes de `_start_startup_stack_watch`, antes do `Timer` do `--exit-after` e antes de qualquer
`Thread`. Converte 9 tipos uma vez, sozinha:

```
CLR_WARM ok=True types=Icon,Color,Size,Rectangle,DockStyle,Func[Type],Func[Object],Action[String],Task failed=none ms=703.0
```

A POSIÇÃO é parte da cura. A primeira versão que escrevi chamava a cura depois do `Thread` da
varredura de perfis — e a arm A4 do oráculo apanhou-a: `FAIL A4 warm_linha=27063
threads_antes=[27037]`. Uma conversão a seguir ao primeiro fio não impede corrida nenhuma; é o mesmo
defeito com outro nome.

## 4. Custo

6 processos, um por amostra: **min 689 / mediana 879 / max 1506 ms**. Com o disco saturado a mesma
função deu **2279,8 ms**. O tecto da arm A3 é **4000 ms** — o primeiro tecto que escrevi, 2200,
reprovava a cura **correta** por contenda de disco, que é exactamente o defeito de um portão que
acusa quem está certo.

Não é custo novo: o `import clr` e os `AddReference` são pagos uma vez por processo, e o
`webview.start()` pagá-los-ia de qualquer maneira.

## 5. O instrumento

`_main/clr-warm-oracle.py`, 4 arms sobre o código REAL:

| arm | o que exige | medido |
|---|---|---|
| A1 existe-e-é-chamada | a função existe **e** `main()` a chama antes do `webview.start()` | `funcao=sim chamadas=1 antes_do_start=sim` |
| A2 cobre-os-tipos | os 9 tipos, lidos da tupla `(rótulo, lambda)` do fonte | `cobertos=9/9 faltam=nenhum` |
| A3 executa-e-é-rápido | a função real num subprocesso devolve `True` dentro do tecto | `call=True warm_ms=885.7 budget_ms=4000` |
| A4 antes-da-thread | nenhum `Thread` construído antes da chamada dentro do `main()` | `threads_antes=nenhuma` |

`VERDICT: PASS (4/4)`, rc=0.

**Negativo:** `--neg-arm` muta uma **cópia** em três sítios e exige que as arms caiam —
`NEG-ARM: PASS -- 3/3`, rc=1. As três mutações: chamada apagada, `Icon` trocado por `lambda: None`,
chamada movida para depois do `webview.start()`.

## 6. Duas correções do próprio instrumento, as duas apanhadas pelo negativo

1. **`path=SHELL` como default de argumento.** Um default é avaliado uma vez, na definição; o
   `--neg-arm` troca `SHELL` por uma cópia mutada **depois** disso. Resultado medido: todos os
   mutantes corriam contra o ficheiro original e o negativo publicava `INERTE 0/3`.
2. **A arm A2 aceitava o rótulo `'Icon'` como prova.** O mutante que troca a conversão por
   `lambda: None` deixa o nome lá dentro, e o braço passava a medir a ETIQUETA em vez do trabalho:
   `INERTE M2`. A correção seguinte (exigir uma chamada `Nome(`) caiu no defeito oposto e reprovava
   conversões legítimas por atributo — `FAIL A2 cobertos=6/9 faltam=Color,DockStyle,Task`
   (`Color.Transparent`, `DockStyle.Fill`, `Task.CompletedTask`). A forma final lê a estrutura: a
   tupla `(rótulo, lambda)`, exigindo que o corpo nomeie o tipo **e** não seja `None`.

## 7. A bateria

O par `clr-warm` + `red-as-expected-clr-warm` entrou em `_main/_audit-verify-all.cmd`. Portões
medidos depois:

| portão | resultado |
|---|---|
| `agents-md-pins-oracle.py` | `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` |
| `battery-wiring-oracle.py` | `PASS checks=7 fail=0`, `ligados=208 sem_passo=107 populacao=315` |
| `battery-class-oracle.py` | `PASS -- arms=3 fail=0` |
| `battery-record-pairing-oracle.py` | `509 passos, 509 nomes com registo, 0 achados` |
| `undefined-names-oracle.py` | `GREEN -- 19 ficheiros, 0 nomes usados e nunca definidos` |

**Duas dívidas alheias fechadas no mesmo bloco.** O `battery-record-pairing` acusou dois blocos com
`:record` a mais — o meu e o de `caption-status-hide`, que o pin anterior já tinha dado por bom. Um
`:step ... 1` seguido de `:record` exige rc=0 de um passo que tem de sair 1, e o `:expectred` a
seguir relia o `!STEP_RC!` do primeiro. A forma correcta é `:step <nome> 1` + `:expectred <nome>` e
nada mais. E havia **16 bare LF** em `_main/_audit-verify-all.cmd`, deixados por três inserções
anteriores; o ficheiro foi normalizado para 0.

## 8. O QUE NÃO ESTÁ VERIFICADO

**Que a app do dono deixou de morrer.** Essa prova exige um arranque real com WebView2 a subir, e
esta árvore não o consegue de uma pane `medium`: o WebView2 falha antes, em
`0x80010108 RPC_E_DISCONNECTED` (medido nesta sessão na corrida com a cura já instalada). O que está
provado é que o cache de tipos fica quente, que a função corre onde e quando deve, e que nenhuma das
suas próprias conclusões é falsa. A contagem de mortes novas — zero, à hora em que este recibo foi
escrito — só o próximo arranque dele a mede.
