# A ordem dos candidatos — qual das três hipóteses é verdadeira, e a cura

Lane **SottoOrdemCandidatos**, 2026-10-06. Alvos: `H:/sotto/worker/wasapi_loopback.py`,
`H:/sotto/worker/sotto_worker.py`. A app do dono está a correr durante todo o trabalho.

---

## 0. Resposta curta

**(a) é a verdadeira.** A lista É ordenada pelo medidor ao vivo e a ordem CHEGA ao
`device_candidates()` (logo **(b) é falsa**), e o primeiro candidato É o rung (a) — um
`WASAPI loopback: <endpoint>` — e não o rung (b) `CABLE Output` (logo **(c) é falsa**).
Mas a leitura que ordena a lista é feita **quando nada está a renderizar**: nesse
instante os SEIS endpoints ativos medem `0.000000`, o `sort` não tem por onde ordenar e
o desempate `not is_default` entrega a PRIMEIRA janela ao endpoint **default**
(`VoiceMeeter Input`), que é precisamente o que esta máquina nunca usa. A rotação é a
escada a recuperar disso.

A formulação do brief ("a lista foi ordenada com dados VELHOS") **não** se confirma tal
e qual: a leitura não é feita no arranque do processo, é feita 9–18 s depois, já dentro
da escada. O que falha não é a idade do dado — é que `0.000000` é a resposta honesta a
"nada está a renderizar", e o desempate inventa uma ordem a partir dela.

**Cura:** a escolha passa a ser feita **no momento da escolha** — antes de abrir cada
candidato WASAPI, os medidores dos candidatos ainda não tentados são lidos DE NOVO e o
que está a renderizar agora toma o lugar. Custo medido: **0.749 s** por leitura (6
endpoints a `meter_ms=0.12`), contra os **6.0 s** de janela que ela evita.

---

## 1. A medição que decide — (b) e (c) são FALSAS

### 1.1 Com áudio a renderizar (o dono a tocar, 13:24)

```
$ "C:/Program Files/Python311/python.exe" -u _main/ordem-dos-candidatos-probe.py NOW
[NOW] BEFORE (list as list_render_endpoints returns it) t=1791293064.400 n=6
    #0 peak=0.299878865480423 default=False name='CABLE Input (VB-Audio Virtual Cable)'
    #1 peak=0.0 default=True name='VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'
    #2 peak=0.0 default=False name='Speakers (NVIDIA Broadcast)'
    #3 peak=0.0 default=False name='Fones de ouvido (soundcore Space Q45)'
    #4 peak=0.0 default=False name='AG251F1WG2 (NVIDIA High Definition Audio)'
    #5 peak=0.0 default=False name='Alto-falantes (HyperX Quadcast)'
[NOW] SUMMARY first_candidate='WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)'
     rung='a' meter_at_selection=0.3195343613624573
```

O `meter_peak` que o `sort` usou **está** no candidato (`meter_at_selection=0.3195`) e o
primeiro candidato é o endpoint que mede 0.3195, **não** o default. Portanto:

* **(b) FALSA** — a ordenação chega intacta ao `device_candidates()`. Se o `sort`
  "se perdesse", este `SUMMARY` diria `VoiceMeeter Input`.
* **(c) FALSA** — o primeiro candidato é `rung='a'`, `WASAPI loopback: ...`. O rung (b)
  `CABLE Output (VB-Audio Virtual ` aparece em **#7 de 10** (ver §1.2). E não há rung
  (c): o shell exporta `SOTTO_AUDIO_DEVICE=(unset)`
  (`_main/webview-run.log`, `BRIDGE_SPAWNED ... SOTTO_AUDIO_DEVICE=(unset)`), logo
  `wanted is None` e o bloco "explicit override" nunca corre.

### 1.2 Com NADA a renderizar (13:04, medido duas vezes)

```
$ "C:/Program Files/Python311/python.exe" -u _main/ordem-dos-candidatos-probe.py A1
[A1] BEFORE ... n=6
    #0 peak=0.0 default=True name='{0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}'
    #1 peak=0.0 ... #5 peak=0.0        (SEIS endpoints, TODOS a 0.0)
[A1] device_candidates() n=10
    #0 rung='a' meter=0.0 name='WASAPI loopback: {55395a4e-...}'   <- O DEFAULT
    #6 rung='b' ... VoiceMeeter Output     #7 rung='b' ... CABLE Output
[A1] SUMMARY first_candidate='WASAPI loopback: {55395a4e-...}' rung='a' meter_at_selection=0.0
```

O mesmo código, a mesma máquina, a única diferença é haver áudio: **com áudio, CABLE
Input primeiro; sem áudio, o default primeiro.** É o desempate
`out.sort(key=lambda e: (-(e["meter_peak"] or 0.0), not e["is_default"]))`
(`worker/wasapi_loopback.py`, `_list_render_endpoints`).

Os ids, resolvidos pelo registo do Windows (`MMDevices\Audio\Render\...\Properties`,
`{a45c254e-...},2` — a leitura que o código NÃO conseguia fazer, ver §4):

| endpoint id | nome | estado |
|---|---|---|
| `{55395a4e-97b2-4b96-9878-18be1ed894e0}` | `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)` | **DEFAULT**, mede 0.0 |
| `{2f1295af-8529-4f15-b00d-7b9bba575ac0}` | `CABLE Input (VB-Audio Virtual Cable)` | o que o dono usa |
| `{1aee4592-2e18-4248-bf54-2fa14af8315c}` | `Speakers (NVIDIA Broadcast)` | |
| `{6780e74d-2f7e-42e0-bcb4-ee85911b5259}` | `Fones de ouvido (soundcore Space Q45)` | |
| `{7d427fc9-5cff-431f-ae0c-c1abd1229f8b}` | `AG251F1WG2 (NVIDIA High Definition Audio)` | |
| `{b1e02bd0-0cc2-40b4-8eb8-7827f979ff73}` | `Alto-falantes (HyperX Quadcast)` | |

### 1.3 Quando o medidor PODE responder, a rotação não acontece

`_main/audio-escopo-worker-cable.jsonl` (já existente, corrida anterior): o primeiro
candidato foi `{2f1295af}` = **CABLE Input**, `attempt 1 of 10`, `rung_why` =
`"WASAPI loopback of an active render endpoint (rendering now, meter peak 0.191)"`,
**ZERO rotações**, primeira legenda ao 0.56 s de tap. É a mesma escada, com o medidor
capaz de responder.

---

## 2. O que a ordem errada custa — ANTES, medido

### 2.1 No log da app viva (o sintoma do brief)

```
_main/webview-run.log:4297
sotto: BRIDGE_SILENT_BENIGN ms=15000 pid=27084 state=no-audio because="device-rotated reason=flat peak=0.0 floor=0.002" restarts=1
_main/webview-run.log:4300
sotto: BRIDGE_SILENT_BENIGN ms=15000 pid=38560 state=no-audio because="device-rotated reason=flat peak=0.142383 floor=0.002" restarts=3
```

**Aviso de instrumento (importante para o brief):** este ficheiro **não consegue contar
rotações**. `WorkerBridge.no_audio_evidence` guarda SÓ a última evidência e
`_on_silence` re-imprime a MESMA linha a cada 15 s enquanto a escada continua calada
(`app/webview/sotto_webview.py:2957`). As duas linhas acima repetem-se dezenas de vezes
com o mesmo `peak` e o mesmo `restarts`. O "um por respawn" do brief não é verificável
por este log; o instrumento que conta é o JSONL do worker.

### 2.2 A rotação contada, com o código ANTES

`_main/_ordem-arm.py` corre o worker empacotado a partir de um directório escolhido e
carimba cada linha de stdout com o instante de chegada. Arranque com SILÊNCIO (nada a
renderizar), `--max-seconds 16`:

```
$ "C:/Program Files/Python311/python.exe" -u _main/_ordem-arm.py _main/_ordem-before \
      _main/_ordem-BEFORE-delay2 spawn 2.0 16
   18.435 device            WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)
   18.725 capture-started   VoiceMeeter Input            attempt 1 of 10
   24.758 device-rotated    flat  from=VoiceMeeter Input   to=Speakers          peak=0.0
   24.949 capture-started   Speakers                     attempt 2 of 10
   30.985 device-rotated    flat  from=Speakers            to=CABLE Input       peak=0.0
   31.185 capture-started   CABLE Input                  attempt 3 of 10
```

**DUAS rotações (24.758 e 30.985) e 12.46 s até abrir o endpoint que carrega o áudio** —
e as duas linhas são `reason=flat peak=0.0`, exactamente o que o log da app mostra. O
primeiro candidato é o default; o endpoint do dono está a DUAS janelas de distância.

`_main/_ordem-BEFORE-delay2.summary.json`: `rotations_total: 2`,
`first_capture: [18.725, "VoiceMeeter Input", 1, 10]`.

---

## 3. A cura — a escolha feita no momento da escolha

### 3.1 O que mudou

* **`worker/wasapi_loopback.py`**: nova `live_render_peaks(meter_ms=0.12)` — devolve
  `{endpoint_id: peak}` de todos os endpoints de render ATIVOS, lido AGORA. Deliberadamente
  mais barata que `list_render_endpoints()`: não ativa `IAudioClient` nem faz parse de mix
  format, porque só o medidor é pedido. `{}` (nunca levanta) quando a plataforma ou a
  enumeração falham — quem recebe `{}` fica com a ordem que já tinha.
* **`worker/sotto_worker.py`**: nova `prefer_rendering_now(candidates, attempt_no)`,
  chamada no topo do ciclo de candidatos, imediatamente antes de abrir o tap:

  ```python
  for attempt_no, dev in enumerate(candidates):
      # THE CHOICE, MADE WHEN IT IS MADE ...
      dev = prefer_rendering_now(candidates, attempt_no)
      device = dev
  ```

  Só entre candidatos **ainda não tentados**, só entre candidatos WASAPI. Se não houver
  mais ninguém a renderizar (`peak <= 0.0`), a ordem antiga fica de pé — é o caminho de
  falha-segura, e é o que se mediu: com tudo calado a re-leitura **não** mexeu na ordem.

Não se tocou no ASR, no `endpoint_id`, nem em `_on_silence`.

### 3.2 ANTES/DEPOIS na escolha, com o medidor AO VIVO

Oráculo `_main/_ordem-cura-oracle.py`: constrói a lista que uma leitura SILENCIOSA deixa
(o default à frente), e pergunta a escolha DE NOVO, com o medidor real, enquanto o áudio
do dono está a renderizar.

```
$ ... _main/_ordem-cura-oracle.py            # COM a cura (worker/)
live meter now:  0.130238 {2f1295af-...}=CABLE Input ; 0.000000 nos outros 5
order BEFORE the choice: ['VoiceMeeter Input', 'Speakers', 'CABLE Input', ...]
WORKER_CHOICE at=attempt-1 picked=WASAPI loopback: CABLE Input (VB-Audio Virtual Cable)
              peak=0.386425 over=WASAPI loopback: VoiceMeeter Input (...) peak=0.000000
re-read cost = 0.749 s
order AFTER  the choice: ['CABLE Input', 'Speakers', 'VoiceMeeter Input', ...]
VERDICT GREEN -- live endpoint is 'CABLE Input ...', attempt 1 opens 'CABLE Input ...'
rc=0

$ ... _main/_ordem-cura-oracle.py _main/_ordem-before      # SEM a cura (o código de hoje)
order AFTER  the choice: ['VoiceMeeter Input', 'Speakers', 'CABLE Input', ...]
attempt 1 would open  : VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)
VERDICT RED -- live endpoint is 'CABLE Input ...', attempt 1 opens 'VoiceMeeter Input ...'
rc=3
```

Mesma máquina, mesma leitura, mesma lista: **sem a cura a tentativa 1 abre um endpoint
que mede 0.000000; com a cura abre o que mede 0.386425.** Custo da re-leitura: **0.749 s**.
É este o ANTES/DEPOIS do número de rotações até à primeira legenda:
**ANTES = 2 rotações / 12.46 s; DEPOIS = 1 rotação (a primeira já é o endpoint vivo)**.

### 3.3 Efeito no custo de arranque

`live_render_peaks()` é chamada uma vez por candidato WASAPI aberto. Com 6 endpoints a
`meter_ms=0.12` = 0.72 s teóricos, **0.746 / 0.749 / 0.795 s medidos**. No caso em que o
medidor JÁ respondia (o áudio a renderizar na altura da leitura) a função é um no-op —
medido em `_main/_ordem-AFTER-live`: os três intervalos `device-rotated → capture-started`
são 0.755 / 0.748 s e **nenhuma** linha `WORKER_CHOICE` foi emitida, porque o candidato à
frente já era o mais alto. Custo total acrescentado num arranque em que nada muda: +0.75 s
antes do primeiro tap.

---

## 4. Achado colateral, medido e corrigido: a app não sabia o NOME de nenhum endpoint

A cura do `endpoint_id` fez o tap acertar, mas os nomes que a app publica eram GUIDs:
`WASAPI loopback: {0.0.0.00000000}.{55395a4e-...}`. `_friendly_name()` devolvia `None`
para **os seis** endpoints.

`_main/friendly-name-probe.py` mediu as três causas, todas no mesmo `_friendly_name`:

```
---- {0.0.0.00000000}.{1aee4592-...}
   (i)  Activate(IPropertyStore)     hr=0x80004002 store=None     <- E_NOINTERFACE, OS SEIS
   (ii) OpenPropertyStore(STGM_READ) hr=0x00000000 store=2080404235520
       GetValue hr=0x00000000 vt=0x001F name='Speakers (NVIDIA Broadcast)'
---- {0.0.0.00000000}.{2f1295af-...} name='CABLE Input (VB-Audio Virtual Cable)'
---- {0.0.0.00000000}.{55395a4e-...} name='VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'
---- {0.0.0.00000000}.{6780e74d-...} name='Fones de ouvido (soundcore Space Q45)'
---- {0.0.0.00000000}.{7d427fc9-...} name='AG251F1WG2 (NVIDIA High Definition Audio)'
---- {0.0.0.00000000}.{b1e02bd0-...} name='Alto-falantes (HyperQuadcast)'
```

1. chegava ao property store por `Activate(IPropertyStore, CLSCTX_INPROC_SERVER, ...)`,
   que devolve **E_NOINTERFACE (0x80004002) nos seis**. A via documentada é
   `IMMDevice::OpenPropertyStore(STGM_READ)` (vtable 4) → `S_OK` nos mesmos seis;
2. lia o LPWSTR no **offset 0** do PROPVARIANT. Num x64 o cabeçalho tem 8 bytes e a união
   começa no **offset 8**; ler o offset 0 reinterpreta o cabeçalho como ponteiro —
   medido: **matou a sonda com access violation (rc=5)**. Só depois de corrigir (1) é que
   o (2) ficou visível — as duas correcções têm de ir juntas;
3. comparava `vt` com `0x001B`, que não é tipo PROPVARIANT nenhum. O `vt` medido de um
   nome é `VT_LPWSTR = 0x001F`.

Corrigidas as três, o mesmo `device_candidates()` passou a devolver nomes legíveis: o
bloco `[A1]` do §1.2 (corrido às 13:04, ANTES desta correcção) ainda mostra os GUIDs; o
`[NOW]` do §1.1 (13:24, depois) mostra `CABLE Input (VB-Audio Virtual Cable)`,
`VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)` e os outros quatro.

---

## 5. O que NÃO está provado, e por quem

### 5.1 A app VIVA não consegue correr o worker (bloqueio, não é meu alvo)

O processo da app que está a correr (pid 20656, `--log H:\sotto\_main\webview-run.log`)
morre em ciclo:

```
sotto: BRIDGE_SPAWNED pid=21788 argv=["I:\\!manager\\.venv\\Scripts\\python.EXE", "H:\\sotto\\worker\\sotto_worker.py"]
sotto: BRIDGE_EXIT pid=21788 rc=1 ... stderr_tail=["  File \"H:\\sotto\\worker\\sotto_worker.py\", line 1307, in choose_providers",
                                                   "    import onnxruntime as ort", "ModuleNotFoundError: No module named 'onnxruntime'"]
sotto: BRIDGE_RESTART reason=exit in_ms=30000 restart=6     (chegou a restart=45)
```

```
$ "I:/!manager/.venv/Scripts/python.exe" -c "import onnxruntime"   -> ModuleNotFoundError
$ "C:/Program Files/Python311/python.exe" -c "import onnxruntime"  -> OK 1.30.0
```

O shell resolve o intérprete uma vez, no arranque (`default_python()` =
`shutil.which("python") or sys.executable`, `app/webview/sotto_webview.py:3059`) e foi
lançado com o PATH onde `python` resolve para o venv do manager, que não tem
`onnxruntime`. **A app não transcreve nada neste estado**, e por isso o log da app viva
não pode servir de prova DEPOIS: não chega a tocar no dispositivo. Isto não é do meu
alvo (não é o ASR nem a escolha) e não matei nem relancei a app.

**Dono:** quem lança a app (o mesmo lane que a pôs a correr com `--with-worker`).
Correcção mínima, uma linha, no local do defeito: `default_python()` deve testar o
intérprete (`python -c "import onnxruntime"`) e cair para `sys.executable` quando falha.
O meu lane **não** tem dispatch nem mandato sobre `sotto_webview.py`.

### 5.2 A transição "silêncio → áudio" não foi reproduzível em arm hoje

O áudio do dono está a renderizar em CABLE Input durante todo o trabalho (medido:
0.130238 a 0.386425 em pontos diferentes). Com áudio a renderizar, a leitura da ordem
**acerta** e escolhe CABLE Input à primeira — tanto ANTES como DEPOIS. Logo o cenário do
defeito (leitura feita em silêncio, áudio a aparecer depois) só foi reproduzido no arm
com SILÊNCIO (acima: as 2 rotações `peak=0.0`), nunca com áudio a aparecer a meio da
caminhada. Quem conseguir pedir ao dono para parar o áudio 15 s reproduz a transição
inteira com `_main/_ordem-arm.py <dir> <prefixo> capture 1.0 40`.

### 5.3 A rotação que NÃO é da escolha (fora de âmbito, inalterada)

Em `_main/_ordem-AFTER-live` (áudio do dono a renderizar, sem estímulo meu) a escada
rodou 3 vezes com **peak ≠ 0**:

```
  9.154 capture-started   CABLE Input          attempt 1 of 10     (escolha CERTA)
 15.202 device-rotated    flat  CABLE -> VoiceMeeter   peak=0.106745
 22.001 device-rotated    flat  VoiceMeeter -> Speakers peak=0.378515
 28.785 device-rotated    flat  Speakers -> Fones       peak=0.316431
```

Nenhuma linha `WORKER_CHOICE` — a re-leitura correu (0.755 / 0.748 s entre rotação e o
tap seguinte) e não mexeu, porque o candidato à frente já era o mais alto. Aqui
`reason=flat` **não** quer dizer "não ouvi nada": quer dizer "não saiu legenda na janela
de 6 s" (`sotto_worker.py:2163` só assenta numa LEGENDA; `blank_frac=1.0`, `captions=0`
nas duas linhas de `WORKER_STATS`). Esta rotação é o comportamento que o brief diz estar
JÁ CURADO (`BRIDGE_SILENT_BENIGN`) e **não foi tocado**.

### 5.4 Se a rotação for inevitável por desenho

Quando a leitura é feita em silêncio, **nenhuma ordenação pode acertar** — não há sinal
para ordenar. O que a cura muda é o preço: antes, a escada abria VoiceMeeter (0.0), gastava
6 s, abria Speakers (0.0), gastava 6 s, e só então abria CABLE Input — **12.46 s medidos**.
Depois, a primeira rotação já leva ao endpoint que está a renderizar — **6 s + 0.75 s**.
E o dono não vê silêncio nenhum destes: a shell pinta
`"Audio tap silent - nothing to transcribe"` / `"No audio to transcribe"` enquanto a
escada procura (`STATUS_APPLIED` / `PLACEHOLDER_APPLIED` no log, ao lado de cada
`BRIDGE_SILENT_BENIGN`). A janela é de 6 s no worker (`TAP_WINDOW_S = 6.0`,
`sotto_worker.py:218`); os 15 s do brief são o watchdog da shell (`silence_ms=15000`).

---

## 6. Ficheiros e como reproduzir

| o quê | caminho |
|---|---|
| a ordem, com e sem áudio | `_main/ordem-dos-candidatos-probe.py` |
| a cura na escolha, RED/GREEN | `_main/_ordem-cura-oracle.py` (`worker/` e `_main/_ordem-before/`) |
| o código ANTES (sem a cura) | `_main/_ordem-before/` (cópia do worker com as duas hunks revertidas) |
| a escada ponta-a-ponta, cronometrada | `_main/_ordem-arm.py <dir> <prefixo> <spawn\|capture\|-> <delay> <max-s>` |
| porquê o nome do endpoint era None | `_main/friendly-name-probe.py` |

Alterações de produção: `worker/wasapi_loopback.py` (constantes, `_friendly_name`,
`live_render_peaks`) e `worker/sotto_worker.py` (`prefer_rendering_now` + a chamada no
ciclo). `python -m py_compile` nos dois: rc=0.
