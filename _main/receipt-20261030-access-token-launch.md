# O acesso da lane `medium` a uma app `high` — 2026-10-30

Pergunta do dono, nas palavras dele: *"recuperei parte... arruma agora"*, depois de dizer que
antes tinha o Windows inteiro acessível e que alguma coisa aconteceu. Este recibo responde com
medição, não com opinião, e corrige uma conclusão de meses.

## 1. O que está MEDIDO agora, com instrumento ao lado

| pergunta | instrumento | veredicto |
|---|---|---|
| que integridade tem esta pane? | `TokenIntegrityLevel` (classe **25**) lido como SID e convertido | `S-1-16-8192` = **MEDIUM** |
| e a app do dono viva (pid 44820)? | o mesmo | `S-1-16-12288` = **HIGH** |
| o `whoami /groups` diz Administradores "Grupo ativado"? | `whoami /groups` | sim — **não** é o que decide integridade, e por isso nunca se lê daí |
| escrever em `HKLM`? | filho `high` a criar e apagar `HKLM\SOFTWARE\SottoAccessProbe` | **SIM** |
| ler `schtasks`? | filho `high` | **SIM** |
| pertencer ao grupo Administradores? | `net localgroup Administradores` a partir do filho | **SIM** |
| abrir o token do `pid 4` (SYSTEM)? | `OpenProcessToken` de um filho `high` | **NÃO — `err=5`** |

O último é o único "não", e não é permissão perdida: SYSTEM está **acima** de `high` na escala de
integridade. Um `high` não abre um token `SYSTEM`, ponto. (Medido: `S-1-16-4096 < 8192 < 12288 <
16384`.)

**Um erro meu de instrumento, corrigido aqui:** a primeira versão deste medidor lia a classe **18**
e chamava-lhe integridade. A classe 18 é `TokenElevationType` (1 = sem UAC, 2 = completo,
3 = limitado), e foi por isso que uma leitura intermediária desta sessão imprimiu `SYSTEM` para um
processo que o `tasklist` diz ser `DESKTOP-O58U7KF\Administrador`. Integridade é a **25**.

## 2. O defeito real: o PEDIDO, não o Windows

`_main/sotto-relaunch.py` trazia, escrito a 2026-10-30, que o caminho 4
(`CreateProcessAsUser` com o token do shell vivo) dava `OpenProcessToken err=5` e que "a pane nem
sequer PODE abrir o token dele". **Falso.** Direito a direito, contra o token da app viva:

| direitos pedidos | `OpenProcessToken` | `DuplicateTokenEx` |
|---|---|---|
| `DUPLICATE` | ok | ok |
| `DUP\|QUERY` | ok | ok |
| `DUP\|QUERY\|ASSIGN_PRIMARY` | **ok** | **ok** |
| `DUP\|QUERY\|ASSIGN_PRIMARY\|ADJUST_SESSIONID` | **err=5** | — |
| `…\|ADJUST_DEFAULT` | **err=5** | — |

`TOKEN_ADJUST_SESSIONID` exige `SeTcbPrivilege`; o pedido inteiro é recusado por causa de um
direito que não é preciso. É a mesma classe de erro que já custou uma conclusão falsa aqui: **o
instrumento a pedir de mais, lido como "o Windows não deixa"**.

## 3. A primitiva que ficou

`_main/launch-as-token.py` (novo): duplica o token de um processo vivo com
`DUPLICATE|QUERY|ASSIGN_PRIMARY` e larga o filho no `winsta0\default`.

```
python _main/launch-as-token.py --selftest
SELFTEST PASS -- fonte pid=13844 (HIGH), filho pid=39328 executou, integridade=S-1-16-12288 (HIGH)
python _main/launch-as-token.py --neg-arm
NEG-ARM PASS -- RED as designed: com ADJUST_SESSIONID: OpenProcessToken(pid=13844) err=5 (direitos=0x10b)
```

O `--selftest` exige **duas** coisas, e a segunda é a que importa: que o filho **execute código**
(escreve o próprio pid) e que **herde o nível da fonte** (`sid do filho == sid da fonte`). Um filho
criado que nunca corre foi exactamente o resultado falso que `_main/launch-unelevated.py` produziu
a 2026-10-23; aqui fica como recusa. O `--neg-arm` repõe `TOKEN_ADJUST_SESSIONID` e exige o `err=5`
de volta — se esse braço passar, o `PASS` do `--selftest` deixa de significar alguma coisa.

Descoberta de fonte: `wmic` **foi retirado desta máquina** (medido: saída vazia), por isso é
`tasklist /fo csv /nh`, com `--source <pid>` a sobrepor-se.

## 4. Ligação no relançador

`_main/sotto-relaunch.py --relaunch` passou a ter **duas** estradas, por esta ordem:

1. **token da instância viva** (`launch_via_token`) — sem tarefa, sem aprovação, filho `high`;
2. **`schtasks /run /tn Sotto`** — só quando a app está morta (então não há token `high` para
   emprestar, e a tarefa, que corre como ele na sessão dele, é o único caminho).

Uma chamada de uma pane `medium` delega: mata um processo `high` a partir de `medium` dá `err=5`,
logo quem mata é o filho `high`. O bloco de docstring que dizia "o único lançador que funciona é a
tarefa" foi **corrigido**, com a razão escrita lá dentro.

Provado a exercitar a função ligada (payload inofensivo, a app **não** foi tocada):

```
esta pane high? False | shell vivo: 44820
CreateProcessAsUser(fonte=44820) ok=True err=0 filho=42780
filho executou: pid=28092 integridade=S-1-16-12288
```

## 5. A app NÃO precisa de ser religada

```
python _main/live-code-freshness-oracle.py
LIVE_CODE FRESH  pid=44820 started=2026-10-30 05:52:36.442
  processo: sha256=93828C4A5D6F | disco: sha256=93828C4A5D6F files=7
```

O processo vivo corre o código do disco. Religar seria ruído.

## 6. Bateria

Dois passos novos em `_main/_audit-verify-all.cmd`, os dois `always` (leem a integridade viva):
`launch-as-token` (rc 0 esperado) e `red-as-expected-launch-as-token` (rc 1 esperado, string
`NEG-ARM PASS` no log).

Pin re-medido: `146335 B`, `1898 CRLF` / 0 bare LF,
sha256 `0708AE8DE1663266431D39D9B3CF91FE2F9648672C933FD7894CFC046DD278DC`;
`python _main/agents-md-pins-oracle.py` -> `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.
`python _main/battery-wiring-oracle.py` -> `PASS checks=7 fail=0 populacao=174 ligados=61`.

## SELF-AUDIT

- **Afirmei "nada se perdeu" com base em quê?** Em três capacidades medidas a partir de um filho
  `high` (HKLM, `schtasks`, grupo) e na única que falha (token SYSTEM), que é aritmética de
  integridade. Não afirmei nada sobre o que ele lembra de fazer antes que hoje dê `err=5` e que eu
  não medi — isso fica declarado como **por medir**.
- **O `--selftest` pode passar sem medir?** Não: sem fonte abrível imprime `SKIP` e devolve **1**,
  porque um skip não é um portão que passou.
- **O filho pode herdar `high` sem a primitiva funcionar?** O braço negativo cobre o outro lado:
  o mesmo pedido com o direito culpado tem de morrer. Se ambos passarem, o `high` vem do token.
- **A app foi tocada para provar isto?** Não. O teste da função ligada usou um payload próprio, e
  o `--check` do relançador é só leitura.
- **O que NÃO está provado:** uma religação **completa** pela estrada nova (kill + largada da app
  real). Não a fiz porque a instância viva já corre o código do disco — religar seria dano sem
  propósito. A peça que faltava provar (o token larga um `high` que executa) está provada.
