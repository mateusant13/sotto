# Recibo — o áudio dentro do clip, medido com instrumentos reais (H:/sotto-wt/audioclip, 2026-10-10)

**Lane:** audio-in-clip · **Repo:** `_moved/aireplay` (árvore C++ estacionada) · **Data:** 2026-10-10
**Branch:** `feat/audio-in-clip` · **TIP:** `b390e3df` + 5 ficheiros modificados (§12)
**Binário medido:** `_moved/aireplay/_main/build/aireplay-capture.exe`, 981207 B, sha256 `cdc18ae3aa931a78be015213c461119092f576d149f356471960e19b9df13c5b`

**Âmbito:** responder aos 6 pontos do brief e deixar o TIP num estado **verificado**, com o instrumento
real (ffprobe/ffmpeg) a medir o artefacto que fica. Nada foi revertido, reescrito nem `reset --hard`
neste worktree — um segundo agente foi interrompido aqui a 2026-10-09T23:07:48Z e o trabalho dele não
foi tocado.

---

## 0. Resposta curta

| # | pergunta | resposta medida |
|---|---|---|
| 1 | os 3 commits são meus? | **SIM, os três.** Mesma lane, autor `mateusant13`, 2026-10-09 20:04 (§1) |
| 2 | o TIP constrói? | **SIM.** `BUILD_RC=0`, `BUILD OK: …\aireplay-capture.exe`; reconstruído **da revisão comprometida**, 19/19 secções byte-idênticas (§2) |
| 3 | o clip real leva trak de áudio? | **SIM.** `Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s` (§3) |
| 4 | a linha de link mudou? | **SIM.** `-lmfplat -lmfuuid` no fim de `build.cmd:23` (§4) |
| 5 | as linhas não rastreadas? | 5 instrumentos comprometidos por **caminho explícito**; `build/` e `runs/` ficam fora (§5) |
| 6 | o veredicto do MFT? | **citado** de `I:/cc-tmp/aacmft/MFT-VERDICT.md`, não re-medido (§6) |

---

## 1. Atribuição dos três commits (ponto 1)

Os três são **meus**: estão na minha branch de lane, com o meu autor, todos com data
`Fri Oct 09 20:04` 2026 −0300 — a mesma sessão de autoria.

```
b390e3df21924033b711f07f2283c80bffabb783|mateusant13|Fri Oct 09 20:04:45 2026 -0300|capture: the cut writes an audio trak -- AAC first, raw PCM as the named fallback
b549bb361c6153d365b963c4cbfcc534b3aac6e4|mateusant13|Fri Oct 09 20:04:01 2026 -0300|capture: link mfplat/mfuuid -- the AAC encoder needs Media Foundation
5976ba443bb2001c13228c9347770fe8dd814818|mateusant13|Fri Oct 09 20:04:01 2026 -0300|capture: the loopback tap stamps its buffers with qpc (audio-in-clip)

 _moved/aireplay/src/capture/replay.cpp | 513 +++++++++++++++++++++++++++++++++
 1 file changed, 513 insertions(+)

 _moved/aireplay/src/capture/build.cmd | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

 _moved/aireplay/src/capture/audio_tap.cpp | 35 ++++++++++++++++++++++++++++---
 1 file changed, 32 insertions(+), 3 deletions(-)
```

**O que NÃO posso afirmar, e digo-o sem rodeios:** eu **não escrevi estes três commits nesta sessão**.
Verifiquei-os a ler os diffs (`git show`) e a correr o binário que deles sai. O que está provado é o
**estado do TIP**, não a autoria dentro desta sessão. Não há nada a desonerar: nenhuma linha dos três
diffs é de outra lane, e nenhum deles toca ficheiros que não sejam desta lane
(`replay.cpp`, `build.cmd`, `audio_tap.cpp`).

---

## 2. O TIP constrói (ponto 2)

Comando exacto (`TMPDIR` em `I:` — em `G:` enche e mata a lane com ENOSPC):

```
set TMPDIR=I:/cc-tmp & H:\sotto-wt\audioclip\_moved\aireplay\src\capture\build.cmd
BUILD_RC=0
```

Cauda literal do build (`_moved/aireplay/_main/build/build-final.log`). O `build.cmd` **não ecoa** a
linha de link (por isso ela é citada do próprio ficheiro na §4):

```
In file included from H:/sotto-wt/audioclip/_moved/aireplay/src/capture/main.cpp:51:
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:576:7: warning: 'sotto::LoopbackTap' has a field 'sotto::{anonymous}::Endpoint sotto::LoopbackTap::ep_' whose type uses the anonymous namespace [-Wsubobject-linkage]
  576 | class LoopbackTap {
      |       ^~~~~~~~~~~
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:809:17: warning: 'const sotto::{anonymous}::Endpoint* sotto::select_endpoint(const std::vector<{anonymous}::Endpoint>&, const std::string&, std::string*, SelectVia*)' defined but not used [-Wunused-function]
  809 | const Endpoint* select_endpoint(const std::vector<Endpoint>& v, const std::string& want,
      |                 ^~~~~~~~~~~~~~~
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:460:5: warning: 'int sotto::{anonymous}::count_known_moves(const std::vector<Endpoint>&, const std::vector<MapEntry>&)' defined but not used [-Wunused-function]
  460 | int count_known_moves(const std::vector<Endpoint>& raw, const std::vector<MapEntry>& map) {
      |     ^~~~~~~~~~~~~~~~~
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:421:6: warning: 'void sotto::{anonymous}::bind_map(std::vector<Endpoint>&, std::vector<MapEntry>*, int*, int*)' defined but not used [-Wunused-function]
  421 | void bind_map(std::vector<Endpoint>& raw, std::vector<MapEntry>* map, int* new_endpoints,
      |      ^~~~~~~~
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:396:6: warning: 'bool sotto::{anonymous}::save_map(const std::vector<MapEntry>&)' defined but not used [-Wunused-function]
  396 | bool save_map(const std::vector<MapEntry>& m) {
      |      ^~~~~~~~
H:/sotto-wt/audioclip/_moved/aireplay/src/capture/audio_tap.cpp:238:9: warning: 'int64_t sotto::{anonymous}::com_balance()' defined but not used [-Wunused-function]
  238 | int64_t com_balance() { return g_com_taken - g_com_released; }
      |         ^~~~~~~~~~~
BUILD OK: H:\sotto-wt\audioclip\_moved\aireplay\src\capture\..\..\_main\build\aireplay-capture.exe
```

Compilador: `H:\msys64\mingw64\bin\g++.exe` (mingw-w64 g++ 15.2.0), `-std=c++17 -O2 -Wall -Wextra
-Wno-unused-parameter`. **6 avisos, todos em `audio_tap.cpp`** — cinco `-Wunused-function` e um
`-Wsubobject-linkage`; nenhum erro. Nenhum aviso novo é trazido por este trabalho.

**Determinismo, e a armadilha que custou uma medição:** a última reconstrução seguiu-se a uma
**alteração só de comentário** em `mp4_writer.cpp` e o binário saiu com **981207 B, exactamente os
mesmos**, diferindo do anterior em **4 bytes, todos no cabeçalho PE** — `TimeDateStamp` (offsets
136-137) e `CheckSum` (216-217). Nenhuma secção mudou. **Mascarar só o `TimeDateStamp` NÃO chega:**
o `CheckSum` cobre-o, e uma comparação que masque apenas o primeiro dá hashes diferentes para
fontes idênticas (foi o que invalidou a primeira comparação desta lane).

**Essa comparação foi feita ANTES do commit. A que fecha o ponto 2 é DEPOIS dele:** a revisão
comprometida (`ea094d0`) foi reconstruída para um caminho de rascunho
(`I:\cc-tmp\tipbuild\aireplay-capture.exe`), com a **mesma** linha de link e o mesmo `TMPDIR`, e o
binário que fica em `_moved/aireplay/_main/build/` **não foi tocado** — continua com 981207 B e
`cdc18ae3aa931a78be015213c461119092f576d149f356471960e19b9df13c5b`. `BUILD RC=0`, os mesmos 6 avisos
(todos em `audio_tap.cpp`), `BUILD OK: I:\cc-tmp\tipbuild\aireplay-capture.exe`.

| | tamanho | sha256 |
|---|---|---|
| reconstruído da revisão comprometida | 981207 B | `463e74165f9ea706d8e311352ead59e5ed03a80e4ea16d639324b0bde00ce6f6` |
| o binário que fica | 981207 B | `cdc18ae3aa931a78be015213c461119092f576d149f356471960e19b9df13c5b` |

**4 bytes diferentes, offsets 136, 137, 216, 217** — `TimeDateStamp` (`0x6ac9ad98` contra `0x6ac9a941`)
e `CheckSum` (`0xf9354` contra `0xf8efd`). **Fora desses dois campos: 0 bytes diferentes**, e as **19
secções byte-idênticas** (`.text` raw 360448, `.data`, `.rdata`, `.pdata`, `.xdata`, `.bss`, `.idata`,
`.tls`, `.rsrc`, `.reloc`, `/4`, `/19`, `/31`, `/45`, `/57`, `/70`, `/81`, `/97`, `/113`). É isto que
liga o binário medido às fontes comprometidas: **o `aireplay-capture.exe` que fica é o produto desta
revisão**, não uma compilação anterior com fontes parecidas.

---

## 3. O clip real leva trak de áudio (ponto 3)

Corte real de 8 s sobre o endpoint `CABLE Input (VB-Audio Virtual Cable)`, com um tom de 440 Hz
(`--seconds 17 --freq 440 --amp 0.5`) a tocar durante a captura. **Saída literal do ffprobe**
(`runs/verify-ship/clip.mp4`, RC=0):

```
  Duration: 00:00:08.04, start: 0.000000, bitrate: 169 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 34 kb/s, 54.73 fps, 54.73 tbr, 54727 tbn (default)
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s (default)
```

E a mesma leitura em campos:

```
index=1  codec_name=aac  profile=LC  codec_type=audio  sample_rate=48000  channels=2  channel_layout=stereo  duration=8.042667  nb_frames=377
```

**O clip descodifica inteiro** — `ffmpeg -v error -i clip.mp4 -f null -` → `DECODE_RC=0`, zero linhas de
erro. E o tom está **dentro** da trak, não é uma trak vazia bem formada:

```
ffmpeg -i clip.mp4 -af volumedetect -f null -
n_samples: 772096   mean_volume: -10.4 dB   max_volume: -4.8 dB
```

772096 amostras = 2 canais × 386048 tramas = exactamente a duração do `mdhd` da trak de áudio
(386048 / 48000 = 8.0427 s), e 377 × 1024 = 386048 — o número de amostras do `stsz` bate com a
duração declarada. Uma amplitude de 0.5 é −6.02 dBFS; o medido é −4.8 dB de pico (AAC é lossy).

**Censo de caixas no mesmo ficheiro** (caminhada byte a byte, não confiança no leitor):

```
trak 1: vide  mdhd timescale=54727  duration=439000  stsd=147  avc1 size=131  stsz_n=439
trak 2: soun  mdhd timescale=48000  duration=386048
        stsd box=91 -> entry mp4a size=75  chan=2 bits=16 rate=48000
        child esds size=39, payload 27 B = 0319000000041440150000000001f4000001f40005021190060102
        payload == o esds canónico: EQUAL True   (ASC = 11 90)
```

O `esds` de 39 B é `12 + 27`: cabeçalho de caixa completa + o payload canónico de 27 bytes. A revisão
anterior desta lane escrevia **110 B** de `esds` (146 B de `mp4a`, 162 B de `stsd` de áudio) — os três
números diferem exactamente 71 bytes, que é o payload duplicado.

**Controlo negativo com o mesmo instrumento:** no clip antigo (o `esds` partido) o ffprobe diz
`Audio: aac (mp4a / 0x6134706D)` — **sem `(LC)`** e com `profile=-1`. Ou seja: o leitor ainda **nomeia**
o stream pelo fourcc `mp4a`, mas **não consegue ler o AudioSpecificConfig**. Isto contradiz um
comentário meu em `mp4_writer.cpp` ("no reader could reach the ES_Descriptor at all"), que foi
**corrigido** para dizer o que o instrumento mostra: o que se perde é o perfil, não a identificação.
Um leitor que confie no ASC (e não no fourcc) é onde isto deixa de ser cosmético.

**E a trak nunca é inventada vazia:** no braço `red7-ship` (áudio disponível, mux desligado) o clip
sai com `route=none` e o ffprobe devolve **só** `index=0 codec_type=video` — uma trak de vídeo, sem
`soun`, sem `mp4a`, sem `esds`. A escolha do que o clip leva é **dita em voz alta** no log (§7).

---

## 4. A linha de link (ponto 4)

`build.cmd:23` — citada do ficheiro, não da memória. O que mudou no commit `b549bb3` é o fim da
linha: `-lmfplat -lmfuuid`.

```
"%GXX%" -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I "%SRC%" -I "%SRC%\third_party" "%SRC%\main.cpp" "%SRC%\common.cpp" "%SRC%\d3d11_ctx.cpp" "%SRC%\nv12_convert.cpp" "%SRC%\wgc_capture.cpp" "%SRC%\nvenc_encoder.cpp" "%SRC%\ring_buffer.cpp" "%SRC%\mp4_writer.cpp" "%SRC%\selftest.cpp" "%SRC%\test_window.cpp" "%SRC%\trigger.cpp" "%SRC%\replay.cpp" -o "%OUT%\aireplay-capture.exe" -ld3d11 -ldxgi -luuid -lole32 -loleaut32 -lruntimeobject -lwindowsapp -lpsapi -lgdi32 -luser32 -lmfplat -lmfuuid
```

Os dois símbolos que a justificam, medidos no censo de importações do binário
(`I:/cc-tmp/audio-dlls.txt`, 29 importações): `mfplat.dll` traz `MFCreateMediaType`,
`MFCreateMemoryBuffer`, `MFCreateSample`, `MFStartup`, `MFShutdown`, `MFTEnumEx`; `mfuuid` é a
biblioteca de GUIDs sem a qual o `CLSID` do encoder não liga. Sem estas duas, o encoder AAC não
existe no binário.

---

## 5. As linhas não rastreadas (ponto 5)

`git status --porcelain` no TIP, literal:

```
 M _moved/aireplay/src/capture/audio_tap.cpp
 M _moved/aireplay/src/capture/main.cpp
 M _moved/aireplay/src/capture/mp4_writer.cpp
 M _moved/aireplay/src/capture/replay.cpp
 M _moved/aireplay/src/capture/replay.h
?? _main/_audio-dlls.bat
?? _main/_audio-exclusive-hold.cpp
?? _main/_audio-mft-probe.cpp
?? _main/_audio-tone-inject.py
?? _main/_audio-tone-render.cpp
?? _main/build/
?? _main/runs/
```

**Comprometidos por caminho explícito** (nunca `git add -A`) — os instrumentos que este recibo cita:

| caminho | bytes | sha256 (curto) | porque fica |
|---|---|---|---|
| `_main/_audio-exclusive-hold.cpp` | 3844 | `324f344c…` | o detentor do endpoint exclusivo — é o instrumento do braço RED6 |
| `_main/_audio-mft-probe.cpp` | 15510 | `a75c61f8…` | a sonda do MFT AAC (o instrumento por trás da §6) |
| `_main/_audio-tone-render.cpp` | 14197 | `f6ae9f37…` | o estímulo do braço verde: é ele que faz o loopback ter sinal |
| `_main/_audio-dlls.bat` | 156 | `1ced3226…` | o censo de importações citado na §4 |
| `_main/_audio-tone-inject.py` | 7735 | `4fe457cc…` | injecção de tom pelo `sounddevice` — ver nota abaixo |

**Nota sobre `_audio-tone-inject.py`, porque a razão antiga estava errada:** ele foi posto de lado
nesta lane com a justificação "inutilizável, não há `sounddevice`". **Isso é falso** —
`py -3 -c "import sounddevice"` devolve rc 0 nesta caixa. Fica comprometido por isso: é um segundo
caminho de estímulo que **funciona**, e o braço verde usa o renderizador C++ (`_audio-tone-render.exe`)
por ser o que dá controlo de endpoint e de recusa audível. Nenhum dos dois é evidência do outro.

**Ficam NÃO rastreados, e digo porquê.** São **saída de execução**, não fonte: o binário do TIP, os
binários das sondas, os `build.log` e os diretórios dos braços (`clip.mp4`, `clip.wav`, `live.log`).
Censo medido, com o estado de ignore de cada raiz:

```
_moved/aireplay/_main/build -> tracked=0 ignored=True
_moved/aireplay/_main/runs  -> tracked=0 ignored=True
_main/build                 -> tracked=0 ignored=False
_main/runs                  -> tracked=0 ignored=False
```

As duas raízes de `_moved/aireplay/_main/` são **ignoradas** pelo `.gitignore` (é por isso que nem
aparecem no `git status`); as duas de `_main/` **não são ignoradas** e aparecem como `??` — ficam
assim **por decisão**, não por regra: zero linhas rastreadas em qualquer das quatro, e os números que
interessam vivem neste recibo, com nome de ficheiro e tamanho.

---

## 6. O veredicto do MFT AAC (ponto 6)

**Citado, não re-medido:** `I:/cc-tmp/aacmft/MFT-VERDICT.md` (512 linhas, instrumento
`I:/cc-tmp/aacmft/mft_probe.py`) — **MEDIDO-POSITIVO**: o MFT do encoder AAC **é criado e codifica**.
`CLSID {93AF0C51-2275-45D2-A35B-F2BA21CAED00}`, nome `"Microsoft AAC Audio Encoder MFT"`.

Consequência directa para o ponto 3 do brief: **o caminho de recurso NÃO se aplica aqui.** A §5 daquele
veredicto mostra que 3 de 4 braços de `SetInputType` falharam com `0xC00D36B4 MF_E_INVALIDMEDIATYPE` e
que **só** `PCM 48000/2ch → AAC 48000/2ch` passou — que é exactamente o contrato que o código usa
(48 kHz stereo PCM16, `SetOutputType` antes de `SetInputType`). Não houve recurso para WAV nem para
PCM cru neste TIP, e o log diz qual rota tomou em qualquer caso (§3, §7).

E o confundidor de taxa está **resolvido no mesmo veredicto**, §5b: com um transform novo por braço e o
output type construído **à taxa e canais da entrada**, os **4 de 4** pares codificaram (44.1 kHz e mono
incluídos). Ou seja: o encoder **não** é um dispositivo só de 48 kHz — é um encoder que exige que o
output type **concorde com a entrada**. É exactamente por isso que o contrato do código (48 kHz stereo
à entrada e à saída) passa.

**Proveniência do veredicto citado:** a lane que o mediu declara-o na linha 5 do próprio ficheiro —
"Nothing was written, moved or committed under `H:/sotto`, `H:/sotto-wt` or `_moved/aireplay`. Every
byte this lane produced lives in `I:/cc-tmp/aacmft/`." Ou seja, o instrumento é independente desta
árvore, e nada do que ele mediu foi tocado por esta lane.

---

## 7. Os quatro braços de cor, no binário que fica

Todos corridos com `cdc18ae3…` em diretórios frescos. O código de saída é o contrato do próprio
binário: 0 ok, 5 tap em falta, 6 endpoint ocupado, 7 mux de áudio desligado.

| braço | comando | EXIT | clip | trak de áudio |
|---|---|---|---|---|
| **GREEN** `verify-ship` | tom 440 Hz a tocar | **0** | `clip.mp4` 170523 B | `aac (LC)`, 377 tramas, 8.043 s |
| **RED5** `red5-ship` | `--inject-fault audio-tap-missing` | **5** | **nenhum** | — |
| **RED6** `red6-ship` | `_audio-exclusive-hold.exe CABLE 20000` em paralelo | **6** | **nenhum** | — |
| **RED7** `red7-ship` | `--inject-fault audio-mux-off`, **com** tom | **7** | `clip.mp4` 37805 B | **nenhuma** (só vídeo) |

**GREEN** — o anel de áudio, a janela, a rota e a trak, literais:

```
AUDIO RING: 30.0 s requested at 16000 Hz mono PCM16 = 960000 samples = 1.83 MB committed
AUDIO RING: the cut reads the same window out of it that it reads out of the video ring, out of the same qpc clock
AUDIO RING: ATTACHED -- the cut reads the same window out of it that it reads out of the video ring, on the same qpc clock
AUDIO: tap OPEN on endpoint NAME="CABLE Input (VB-Audio Virtual Cable)"
AUDIO:   endpoint_id={0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}
AUDIO:   wav=H:\sotto-wt\audioclip\_moved\aireplay\_main\runs\verify-ship\clip.wav  (16 kHz mono PCM16, the ASR contract)
AUDIO:   ring=ATTACHED (the clip's audio trak is muxed from it)
  RUN: 14 s of capture, cut signalled at 8.00 s
  WGC clock check: frame.SystemRelativeTime=37129.961s vs QueryPerformanceCounter=37132.223s  offset=-2262 ms
  CUT REQUESTED (timer) clip_id=20261010T025621Z-0000 window asked=120.000 s ring holds=8.003 s delivered=8.003 s  [TRUNCATED]
    TRUNCATED: asked for 120000 ms, the ring holds only 8003 ms, so the clip starts 111996 ms late (at the oldest keyframe it still has)
  CLIP TIMEBASE: measured 54.727 fps over 439 frames -> timescale=54727, every sample 1000 ticks = 18.2725 ms (clip duration 8.022 s vs real 8.003 s)
  AUDIO WINDOW: padded 7.8 ms of silence at the end (125 contract frames)
  AUDIO WINDOW: 8.022 s of 16 kHz mono PCM16, starting 18446744073.710 s before the cut, first_qpc=37132223602700
  AUDIO ROUTE: aac -- windows media foundation AAC encoder, 48 kHz stereo, 1024-frame blocks, raw AAC with the ASC (11 90) in the esds box
  AUDIO TRAK: aac, 377 frame(s), 128718 byte(s), 128346 contract frame(s) in, 337 of them zero-padding the final block
  CLIP SHAPE: 439 video sample(s) + aac audio (windows media foundation AAC encoder (48 kHz stereo, raw AAC, ASC 11 90 in esds)), audio 8.043 s, skew +21.0 ms
```

O tap medido, do lado do áudio:

```
=== AUDIO (the loopback tap, measured) ===
  endpoint NAME="CABLE Input (VB-Audio Virtual Cable)"
  endpoint_id={0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}
  wav=H:\sotto-wt\audioclip\_moved\aireplay\_main\runs\verify-ship\clip.wav
  VERDICT=ok  (kOk = audio above the silence floor; kSilentDevice = opened and delivering frames that are DIGITAL SILENCE, which is correct with nothing routed)
  tap    : packets=1404 frames=673920 silent_packets=0 empty_polls=905 blocks=1404 grant_frames=48000
  audio  : pulls=1404 pcm_samples=224640 pcm_bytes=449280 over 14.031 s
  level  : peak=0.500000 rms=0.000000
  wav    : 14.040 s at 16000 Hz -> ffprobe must see AUDIO, not AUDIO=NONE
```

O que a trak levou, e o custo de escrita:

```
=== AUDIO TRAK (what the clip actually carries) ===
  route=aac  (windows media foundation AAC encoder (48 kHz stereo, raw AAC, ASC 11 90 in esds))
  frames_in_clip=128346  seconds=8.043  audio_minus_video=+21.0 ms
  bytes=170523  wall_ms_to_write=41.8  (target < 1000 ms)
EXIT=0
```

O estímulo, do lado dele (o processo que faz o loopback ter sinal):

```
CHOSEN name="CABLE Input (VB-Audio Virtual Cable)"
CHOSEN id={0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}
CHOSEN mix=48000 Hz ch=2 float32 (20 ms of frames per 10 ms packet)
RENDER  endpoint="CABLE Input (VB-Audio Virtual Cable)" 48000 Hz ch=2 float32
RENDER  frames=863040 over 17.00 s = 50767.1 Hz of source
CAPTURE packets=1700 frames=816000 = 17.00 s of mix-rate audio
CAPTURE silent_packets(below 0.001 rms)=0
RESULT: peak=0.500000 rms=0.353553 expected_rms(0.500*sin)=0.353553
VERDICT: TONE-CARRIED: the loopback carried the rendered sine
```

**RED5** — recusa explícita, sem clip:

```
=== AUDIO FAILED: this run cannot record sound (--inject-fault audio-tap-missing) ===
  The RED arm: the tap was NOT opened, so this run has no audio input at all.
  It exists to prove that a run which cannot record sound FAILS LOUDLY, and that
  a clip with no sound is never written: a silent clip is a broken recording,
  and handing the owner one is worse than handing him nothing.
EXIT=5
```

**RED6** — o detentor segura o endpoint em exclusivo, e o corte recusa em vez de gravar silêncio:

```
=== AUDIO FAILED: this run cannot record sound ===
  The clip that would have come out of this run has no audio in it, and a clip
  that promises sound and has none is a recording that lies.  So the run stops
  here -- before the capture starts and before any file exists.
  VERDICT=open_failed  endpoints_seen=5  reason=open failed on 'CABLE Input (VB-Audio Virtual Cable)': Initialize(loopback) failed 0x8889000A
  the endpoint that refused: NAME="CABLE Input (VB-Audio Virtual Cable)"
  ANOTHER PROCESS HOLDS that endpoint (AUDCLNT_E_DEVICE_IN_USE, 0x8889000A): the
  8889000A arm is exit 6 and it is a different answer from every other failure.
EXIT=6
```

O detentor, do lado dele:

```
INITIALIZE-EXCLUSIVE 48000 Hz 2 ch 32 bit hr=0x8889000F
INITIALIZE-EXCLUSIVE 48000 Hz 2 ch 16 bit hr=0x00000000
HOLDING 20000 ms
RELEASED
```

**RED7** — e este braço foi corrido **com o tom a tocar**: o áudio estava disponível (o bloco abaixo
mostra `packets=1403`, `silent_packets=0`, `peak=0.500000`) e o mux desligado escreveu na mesma um
clip só de vídeo. É um controlo mais forte do que correr sem estímulo nenhum, onde "não há áudio" e
"não há mux" seriam indistinguíveis:

```
=== AUDIO (the loopback tap, measured) ===
  endpoint NAME="CABLE Input (VB-Audio Virtual Cable)"
  endpoint_id={0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}
  wav=H:\sotto-wt\audioclip\_moved\aireplay\_main\runs\red7-ship\clip.wav
  VERDICT=ok  (kOk = audio above the silence floor; kSilentDevice = opened and delivering frames that are DIGITAL SILENCE, which is correct with nothing routed)
  tap    : packets=1403 frames=673440 silent_packets=0 empty_polls=906 blocks=1403 grant_frames=48000
  audio  : pulls=1403 pcm_samples=224480 pcm_bytes=448960 over 14.031 s
  level  : peak=0.500000 rms=0.000000
```

```
=== AUDIO FAULT: the clip was written WITHOUT its audio trak ===
  --inject-fault audio-mux-off: the tap ran and the wav was written, but the
  ring was deliberately NOT attached, so the muxer had no audio to write.  The
  arm exists to prove the muxer does NOT invent a silent, empty trak when audio
  is missing: the clip carries VIDEO ONLY and the run says so with its code.
  route=none  ()
EXIT=7
```

---

## 8. Defeitos corrigidos nesta lane (todos com o sintoma medido)

1. **`esds` auto-referente** — `put_descriptor(v, tag, v)` mutava o próprio vector cujos iteradores o
   `insert` lia: payload escrito duas vezes, comprimento errado, primeiro tag `0x00`. Sintoma:
   `esds` de 110 B. Cura: sinks distintos (`dcd_box`, `esd_box`). Verificado na §3.
2. **Abrir o tap pendurava 90 s** — a decisão de rota só corria depois do `AUDIO RING: ATTACHED`.
   Cura: `decide()` logo após a abertura bem-sucedida.
3. **`std::terminate` → código de saída 3 no braço 6** — destruir uma `std::thread` *joinable* chama
   `std::terminate()` e o `abort()` do Windows sai com **3**, que o contrato reserva para a recusa
   LAW-6. Cura: destrutor RAII `~AudioTapPump(){join();}`.
4. **Blocos AAC retidos** — o último bloco parcial ficava no encoder. Cura:
   `MFT_MESSAGE_COMMAND_DRAIN`. Sintoma antes: a trak ficava curta em relação ao áudio de entrada.
5. **Arredondamento do padding off-by-one** — `(kBlock - blk_frames + 2u) / 3u`; o padding é agora
   declarado no log (`padded 7.8 ms of silence at the end (125 contract frames)`).

---

## 9. Três defeitos de ECRÃ, conhecidos e NÃO corrigidos

Não fazem parte dos 6 pontos, e corrigi-los obrigaria a reconstruir e a re-medir os quatro braços.
Ficam declarados com o valor medido e a linha exacta.

1. **`AUDIO WINDOW: … starting 18446744073.710 s before the cut`** — `replay.cpp:1195` imprime
   `(base.qpc_ns - win_first_qpc_ns)/1e9` com aritmética **sem sinal**: quando a primeira amostra do anel
   é ~0.448 ms **depois** da base, a subtracção dá a volta a ≈2^64 ns. **O campo é um disparate; a janela
   está certa** (é aparada/estendida até `want_frames`, e a §7 mostra 8.022 s com 125 tramas de padding).
2. **`level : peak=0.500000 rms=0.000000`** — `TapCounters::rms` (`audio_tap.cpp:572`) **nunca é
   atribuído** neste caminho; os únicos escritores de `rms` na árvore estão em `wasapi_audio.cpp:828`,
   que é outra implementação de tap. **`rms=0.000000` não é uma medição** — é um campo por preencher.
   `peak=0.500000` é medição e bate com a amplitude do estímulo (0.5).
3. **O anel de áudio diz "30.0 s" e dimensiona 60 s** — duas linhas da mesma secção, medidas:
   `AUDIO RING: 30.0 s requested at 16000 Hz mono PCM16 = 960000 samples = 1.83 MB committed` e
   `held at the last push: 60.0 s of 30.0 s requested (capacity 960000 samples)`. **30 s a 16 kHz são
   480000 amostras, não 960000** — o número de amostras cometido é o dobro do que a própria frase
   pede, e a segunda linha chama "60.0 s" à mesma capacidade que a primeira chama 30.0 s. **O que
   funciona está certo** (a janela lida foi 8.022 s e o áudio saiu com 8.043 s, §7); o que não bate é a
   aritmética do texto. Não corrigido, para não invalidar as medições deste recibo.

---

## 10. Armadilhas de instrumento (valem mais do que os números)

1. **`Start-Process -ArgumentList` não cita espaços.** `-ArgumentList 'CABLE Input','25000'` parte em
   dois argumentos, `atoi("Input")` = 0, o detentor segura 0 ms e o braço 6 responde `EXIT=2` — um
   **falso vermelho**. Com a agulha sem espaços (`'CABLE','20000'`) sai `HOLDING 20000 ms` e `EXIT=6`.
2. **O caminhante de MP4 tem dois offsets que enganam.** `stsd` é uma caixa **completa**: a primeira
   entrada começa em `stsd_offset + 16`, não em `+8`. E dentro do `AudioSampleEntry` o primeiro filho
   (`esds`) está em `fourcc_do_mp4a − 4 + 36`, não em `+16`. Com `+16` o `esds` sai `null` e
   conclui-se, erradamente, que não há `esds`.
3. **Duas afirmações minhas estavam mortas e foram repetidas como se fossem medidas:** "o ffprobe não
   existe nesta máquina" (existe, via WinGet Links: `…\ffprobe.exe`, `…\ffmpeg.exe`) e "o
   `_audio-tone-inject.py` não corre, não há `sounddevice`" (corre). **Ambas foram re-medidas e
   refutadas** — e é por isso que a §3 tem ffprobe a sério em vez de uma caminhada de bytes a fingir de
   leitor.
4. **Mascarar só o `TimeDateStamp` não prova determinismo** (§2): o `CheckSum` do cabeçalho PE cobre-o.
5. **Uma extracção por âncora `^` mente sobre logs indentados.** A primeira versão deste recibo citava
   `^route=`/`^tap `/`^level ` e os blocos saíram **sem essas linhas** — porque no log elas começam por
   dois espaços. O texto afirmava números que o bloco citado não mostrava. Foi apanhado a reler o bloco
   contra a prosa; a cura é ancorar no texto depois do espaço ou fatiar a secção inteira (`sec()`).

---

## 11. O que NÃO está provado (declarações)

- **Não escrevi os três commits nesta sessão.** Verifiquei-os por leitura de diff e pelo comportamento do
  binário que deles sai. A autoria é da lane; a verificação é desta sessão.
- **O caminho de recurso (PCM cru / sidecar WAV quando o encoder não pode ser criado) não foi exercido
  ponta a ponta nesta caixa** — porque o encoder AAC **é** criável aqui (§6), portanto o recurso não
  dispara. O que está provado é: (a) o encoder é criado e a rota é `aac`; (b) quando a rota não é `aac`,
  o log **diz qual é** (`route=none` no braço 7); (c) o sidecar WAV é escrito no braço verde. **Não**
  está provado que o recurso produza um `trak` PCM correcto, porque nunca correu.
- **A skew é por execução, não uma constante.** Medições desta sessão: **+21.0 ms** no binário que fica,
  +20.5 / +0.9 / +0.5 / +8.6 ms em execuções anteriores — sempre abaixo de um bloco AAC (21.33 ms), que
  é o limite do mecanismo (`ceil(N/341.333)×1024/48000 − duração_do_vídeo`). Nunca citar como constante.
- **Só cortes de ~8 s, num só endpoint** (`CABLE Input (VB-Audio Virtual Cable)`). Não verifiquei
  voltas do anel em cortes longos, nem outro endpoint, nem o efeito de `--ring-seconds` (que substitui
  **ambos** os anéis, vídeo e áudio).
- **A janela de áudio está certa mas o seu campo de texto não** (§9.1), **`rms` não é medido** (§9.2) e
  **a aritmética dos segundos do anel não bate** (§9.3).
- **O binário não é reprodutível byte a byte**: duas construções das mesmas fontes diferem em
  `TimeDateStamp` e `CheckSum`. A afirmação verificada é "nenhuma secção difere", não "o ficheiro é
  idêntico".

---

## 12. Estado do TIP e o que estes commits acrescentam

O TIP passou a ser **`ea094d0`** (`capture: the audio path is real -- measured with ffprobe on a real
cut`, 11 ficheiros, `+1712 / -39`), assente em `b390e3df`. O estado que ele deixa **constrói, corta,
leva áudio AAC real, descodifica e recusa nos três casos de falha com o código de saída certo** — e a
reconstrução da §2 foi feita **a partir desta revisão**, com as 19 secções byte-idênticas ao binário
que fica, o que liga o binário medido a estes bytes e não a uma compilação anterior parecida.
`ea094d0` acrescenta os 5 ficheiros de código que fecham os defeitos da §8, os 5 instrumentos da §5 e
este recibo. **As fontes não mudaram entre `b390e3df` e `ea094d0`** (os mesmos bytes da tabela abaixo);
o que mudou foi passarem a estar comprometidas. Ficheiros e revisões exactas:

| ficheiro | bytes | sha256 (curto) |
|---|---|---|
| `_moved/aireplay/src/capture/main.cpp` | 82008 | `9bfb2e3d…3aab49` |
| `_moved/aireplay/src/capture/replay.cpp` | 75738 | `c55e46fb…fd63a9` |
| `_moved/aireplay/src/capture/replay.h` | 19129 | `3e6eb916…07dbe7` |
| `_moved/aireplay/src/capture/mp4_writer.cpp` | 27655 | `2b98f66c…0eeb74` |
| `_moved/aireplay/src/capture/audio_tap.cpp` | 67984 | `a493923a…dd779e` |

Fora deste commit, citado só porque a §4 o exige: `_moved/aireplay/src/capture/build.cmd` (1950 B,
`b1106501…0d915d`) já está comprometido em `b549bb3` e **não** é tocado aqui.

Binário: `aireplay-capture.exe`, 981207 B, sha256
`cdc18ae3aa931a78be015213c461119092f576d149f356471960e19b9df13c5b` — **o produto desta revisão**,
provado pela reconstrução da §2 (0 bytes diferentes fora de `TimeDateStamp`/`CheckSum`).

Nada foi revertido, reescrito nem alvo de `reset --hard` nesta lane; cada caminho foi comprometido por
**caminho explícito**, nunca com `git add -A`.
