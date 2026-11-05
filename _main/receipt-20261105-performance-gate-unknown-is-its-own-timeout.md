# O GATE CENTRAL NAO ESTAVA "AMBER": estava UNKNOWN porque o proprio powershell dele expira

**Medido 2026-11-05, 13:3x-13:4x, nesta maquina.** Nao inferido, nao lido de prosa.

## O que apareceu

`python I:/!manager/tools/performance-gate.py status` devolveu:

```
performance-gate: UNKNOWN
  reasons:
    - sample-unknown:disk counter read failed: Command '['powershell', '-NoProfile',
      '-NonInteractive', '-Command', ...] ...
  policy:
    heavy_allowed=False amber_light_allowed=False amber_light_ttl_max=300.0s
    - amber-light-refused:machine-unknown
```

A mensagem e' o `str()` de um `subprocess.TimeoutExpired`, nao de um disco lento
publicado pelo contador: `read_disk_latency()` (`tools/performance-gate.py:355-361`)
faz `subprocess.run(..., timeout=float(th["disk_timeout_s"]))` e `disk_timeout_s = 12.0`
(`:127`).

## A repro: o leitor REAL do gate, cinco vezes

```
cd I:/!manager && python -c "... exec_module('tools/performance-gate.py'); pg.read_disk_latency() x5"
0 FAIL wall=15.34s  disk counter read failed: Command [...] (timeout)
1 OK   wall=3.54s   windows=[4.9, 0.1]
2 OK   wall=2.65s   windows=[0.5, 6.5]
3 OK   wall=9.16s   windows=[2.9, 7.0]
4 OK   wall=1.50s   windows=[0.3, 0.2]
```

A MESMA query, na MESMA sessao: **1,50 s** numa leitura e **mais de 12 s** na outra.
O que varia e' o arranque do `powershell`, medido em separado: **4,10 s a frio** e
**0,85 s a quente** (3 leituras directas do `Get-CimInstance
Win32_PerfRawData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"`:
4,10 s / 0,91 s / 0,85 s, com o contador a responder `OK` nas tres).

## A prova de que era transitorio, e nao a maquina

Cinco minutos depois, tres leituras consecutivas do mesmo comando:

```
run1 rc=0 :: performance-gate: GREEN :: heavy_allowed=True
run2 rc=0 :: performance-gate: GREEN :: heavy_allowed=True
run3 rc=0 :: performance-gate: GREEN :: heavy_allowed=True
```

O veredicto que a frota inteira obedece oscila entre **GREEN/heavy_allowed=True** e
**UNKNOWN/heavy_allowed=False** conforme UMA leitura de 3 amostras caiba ou nao em 12 s.

## Por que isto importa mais do que um timeout chato

`UNKNOWN` nao e' verde por lei desta casa -- e o gate recusa **heavy E light**. Um
instrumento marginal com 1 em 5 de falha transforma-se num **trabalho parado para
todo mundo**, e o estado publicado ("machine-unknown") le-se como *"a maquina esta ma"*
quando o que esta' mau e' o relogio do instrumento.

Isto liga ao mecanismo do freeze fechado hoje
(`_main/receipt-20261105-freeze-term-wmi-disk-counter.md`, commit `c34a976`): a classe
`Win32_PerfRawData_PerfDisk_LogicalDisk` leva **32,11 s** para 12 instancias na mesma
sessao em que `PhysicalDisk` leva **1,00 s**, com o `TMOG pid 69220` e o `WmiPrvSE
pid 47760` a queimar **84-94 %** da maquina. Sob essa contencao o orcamento de 12 s
expira -- os dois achados sao o mesmo WMI a apertar o mesmo instrumento.

## Proposta (nao landada: `I:/!manager` nao e' a minha arvore)

(a) **uma retentativa** quando a excepcao e' `TimeoutExpired` -- hoje a primeira
leitura manda o veredicto para UNKNOWN e a segunda (1,50 s medida) daria GREEN com
numero; (b) `disk_timeout_s` de **12,0 para 25,0** (o dobro do pior tempo medido,
15,34 s); (c) opcional: reutilizar um `powershell` quente em vez de pagar o arranque
de 4,10 s em cada amostra.

## O que fica entregue a quem decide

DM duravel `I:\!manager\state\herdr-inbox\dm-1e13556266bcd2d3c5c8.md` (o inject
falhou: `manager-target-missing` -- nenhum agente `manager` vivo, `lanes.json`
`manager_pane w11:p7` nao esta' vivo). O gate **nao foi editado**: o instrumento
central e' autoridade da frota e a decisao e' de quem o sustenta.

## Limite honesto

Isto e' `reported`, nao `verified`: rodei o leitor do gate e o proprio gate, mas nao
tenho como provar que a retentativa muda o veredicto em producao sem landar o patch e
ver as corridas seguintes.
