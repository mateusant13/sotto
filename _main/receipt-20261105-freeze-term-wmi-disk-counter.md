# O termo dominante do freeze: `Win32_PerfRawData_PerfDisk_LogicalDisk` leva 32 s

Medido 2026-11-05, 10:1x-10:3x, nesta máquina. Responde à queixa do dono — *"o PC
inteiro trava: herdr, os terminais dentro dele, o chrome, tudo ao mesmo tempo"* — com
mecanismo, não com impressão.

## A cadeia, cada elo com o número

1. **O provider do disco é patológico.** Uma enumeração de
   `Win32_PerfRawData_PerfDisk_LogicalDisk` (12 instâncias) leva **32,11 s**. As classes
   vizinhas respondem no tempo normal, na MESMA sessão, no MESMO host:

   |classe|instâncias|wall|
   |---|---|---|
   |`Win32_PerfRawData_PerfDisk_LogicalDisk`|12|**32,11 s**|
   |`Win32_PerfRawData_PerfDisk_PhysicalDisk`|7|1,00 s|
   |`Win32_DiskDrive`|6|4,90 s|
   |`MSFT_PhysicalDisk`|6|1,38 s|
   |`Win32_Process`|701|1,20 s|
   |`MSFT_StorageReliabilityCounter`|0|3,30 s (não pendura: devolve zero)|

   `MSFT_StorageReliabilityCounter` — a pista da w12:p1 — **não** é o gargalo. A classe
   lenta é a dos contadores de performance **por volume**.

2. **Um cliente faz polling dela.** `C:\Program Files\Task Manager TMOG\Task Manager.exe`
   pid 69220: 34,9 % a 68,4 % de UM core em janelas de 6 s e 26 s, 1 902,9 s acumulados,
   67 threads, 194 MB, `CompanyName=TMOG`, lançado às 09:17:51 **pelo `explorer.exe`**
   (pid 14176 — é o dono que o abriu, ou um atalho seu; não é largado por lane nenhuma),
   fora das chaves `Run`, zero conexões `inet`.

3. **O host que serve o cliente queima.** `WmiPrvSE.exe` pid 47760: **278 % de um core**
   (35,69 s de CPU em 12,8 s, 2 687,6 s acumulados), pai `svchost -k DcomLaunch`. É um
   host NOVO — não é o 63440 que a w12:p1 matou às 09:2x: o cliente voltou a emitir a
   query e o Windows levantou outro host. Medido 10:2x ainda a 59,6 %.

4. **A máquina sente.** `freeze-census` 900 ticks × 2 s (09:36:50 → 10:14): `freezes=0`,
   `late_ms p50 0,6 · p95 23,8 · max 328,4`, cpu 84-94 % nas janelas piores, e o
   rankeamento dessas janelas nomeia **exatamente** os dois processos acima
   (`WmiPrvSE 42 031 ms` + `Task Manager.exe 11 500 ms` numa janela de 10 s).

## O que isso manda fazer

- **Fechar o `Task Manager TMOG`** (decisão do dono: é app dele, aberta pelo explorer).
  É o único corte que fecha a cadeia inteira.
- Se ele ficar: nenhum instrumento desta casa deve consultar
  `Win32_PerfRawData_PerfDisk_LogicalDisk`. O Sotto **não** consulta WMI em caminho
  nenhum (verificado: `wbem`/`MSFT_Storage` só aparecem em `app/_legacy-electron`, árvore
  morta, e em sondas antigas); o censo de disco usa `psutil` + `ctypes`, não WMI.
- Se a 32 s for do PROVIDER e não do cliente, a pergunta seguinte é qual volume a
  pendura — 12 instâncias com uma morta penduram a enumeração inteira; medir por
  instância custa uma query de 32 s por volume e fica para quando alguém precisar.

## Comandos (reproduzem tudo)

```bash
python _main/freeze-census.py --out _main/_audit-verify/freeze-census-long.log --report
python -c "import psutil,time;p=psutil.Process(47760);a=sum(p.cpu_times()[:2]);time.sleep(6);print(sum(psutil.Process(47760).cpu_times()[:2])-a)"
python -c "import psutil,time;p=psutil.Process(69220);a=sum(p.cpu_times()[:2]);time.sleep(6);print(sum(psutil.Process(69220).cpu_times()[:2])-a)"
# o 32 s, com o largador escondido da casa:
python -c "import importlib.util;s=importlib.util.spec_from_file_location('hl','_main/hidden-launch.py');hl=importlib.util.module_from_spec(s);s.loader.exec_module(hl);import time;t=time.time();print(hl.run(['powershell','-NoProfile','-WindowStyle','Hidden','-NonInteractive','-Command','(Get-CimInstance -Namespace root/cimv2 -ClassName Win32_PerfRawData_PerfDisk_LogicalDisk).Count'],capture=True,timeout=90), time.time()-t)"
```

`reported`, nunca `verified`: quem prova a cura é o censo da mesma janela depois de a app
fechar. A janela de 900 ticks acima é a de ANTES.
