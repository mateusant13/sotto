# RECIBO — "por que a merda do meu audio ainda some? arruam caralho"
**Data:** 2026-10-30 · **Repos:** `H:/sotto` · **Autor:** lane (assento principal)
**Queixa verbatim do dono:** *"por que a merda do meu audio ainda some? arruam caralho"*
**Veredicto do registo:** `FIXED, LIVE INSTALLED — NOT VERIFIED` (a cura foi instalada na app
viva às **08:58:31** pelo único caminho que executa em nome do dono,
`_main/sotto-relaunch.py --relaunch`, e o `live-code-freshness` mediu **hash do processo ==
hash do disco**; o que falta é uma corrida em que a legenda limpe o veredicto, não um arranque).

---

## 1. O que estava medido ANTES (instrumentos e números de hoje)

| # | medição | instrumento | resultado |
|---|---|---|---|
| 1 | o áudio dele **não** está mudo nem em volume zero | `pycaw` `IAudioEndpointVolume` em todos os endpoints ACTIVOS | `muted=False` em todos; `Fones de ouvido (soundcore Space Q45)` vol **62,2 %** |
| 2 | o áudio dele **está** a tocar, num endpoint só | `worker/wasapi_loopback.live_render_peaks` | **1** endpoint com sinal: `{2f1295af-…}` = `CABLE Input`, pico **0,6486**; os outros 5 = **0,000000** |
| 3 | a **captura** desse endpoint está sã | `WasapiLoopbackTap(endpoint_id=…)` directo, 3 s | **30 blocos / 30 com sinal**, pico **0,6613**, intervalo médio **0,100 s** |
| 4 | a escada do worker rodava a **fundo** sem chegar lá | `_main/webview-run.log` | **3 060** linhas `device-rotated reason=flat`; `BRIDGE_SILENT_BENIGN … evidence_age_s=259` a repetir `No audio to transcribe` a cada 30 s |
| 5 | a app **reiniciava-se** enquanto ele ouvia | `_main/shell-relaunch.log` | **7** relancamentos reais no dia (`06:53:40`, `06:56:54`, `07:01:00`, `07:53:43`, `08:10:44`, `08:12:48`, …), cada um `kill pid=… confirmado morto` + `schtasks /run` |
| 6 | a ordem dos candidatos é decidida **uma vez** | `device_candidates()` lido e executado nesta máquina | hoje dá `rung=a #0 = CABLE Input pico=0,6748` — porque **agora** há sinal; no arranque do worker (08:13) não havia |

**Conclusão do diagnóstico.** O áudio dele não "desaparece" do Windows: desaparece do
**alcance do Sotto**. A escada decide a ordem no arranque do worker e, quando ele ainda não
estava a tocar, todas as janelas caem em endpoints silenciosos; a rotação seguinte é
`candidates[attempt_no + 1]` — a **lista fixa**, nunca o medidor. Como o worker dá a cada
candidato uma janela de 6 s e nunca volta a perguntar "quem está a tocar agora", o Sotto fica
minutos a tapar dispositivos mudos, escreve `No audio to transcribe` no painel e só por
sorte acerta. Somam-se **dois** cortes audíveis de outra origem: o auto-relancamento da app
(7 hoje) e o veredicto de silêncio que ficava **preso** (259 s) depois de o sinal voltar.

## 2. O que foi mudado (3 curas, todas medidas)

1. **Rotação com o medidor vivo** — `worker/sotto_worker.py`, nova
   `signal_ranked_next(candidates, k)`: em cada rotação pergunta a
   `wasapi_loopback.live_render_peaks()` e **traz para o lugar da rotação o endpoint que
   está a tocar agora** (troca de posições; nenhum candidato é saltado). Sem leitura (`{}`)
   ou tudo abaixo do piso (`0,002`) a ordem **fica como está** — "sem leitura" nunca é "sem
   sinal". O leitor resolve-se **antes** do import, para um medidor injectado não depender do
   `sys.path` do worker (defeito apanhado pelo próprio oráculo: devolvia a ordem estática
   por dentro do ramo que existe para a corrigir).
2. **O veredicto de silêncio deixa de ficar preso** — `app/webview/sotto_webview.py`, ramo
   de INGESTÃO da legenda (`if kind == 'caption':`): uma **legenda** limpa `self.no_audio` e
   o log escreve `NO_AUDIO_CLEARED reason=caption captions=… evidence=…`, uma linha por
   episódio.

   > **PRIMEIRA TENTATIVA, REJEITADA POR MEDIÇÃO (fica escrita).** Cheguei a limpar o
   > veredicto com `peak >= 0.002` em `on_worker_stats`. Está **errado** pelo docstring do
   > próprio shell: `reason=flat` significa "nada transcrevível NESTA janela", e o pico pode
   > ser alto (música, uma chamada noutro endpoint) sem haver fala — medido ao vivo às
   > `09:00:57`: `evidence='device-rotated reason=flat peak=0.78539 floor=0.002'`, pico 0,79 e
   > zero fala. Um pico não prova transcrição; **uma legenda prova**. A constante
   > `TAP_SIGNAL_FLOOR` foi removida e o braço do oráculo passou a exigir a sua AUSÊNCIA.
3. **O vigia não reinicia a app com som a tocar** — novo `app/webview/audio_playing.py`
   (só leitura: `IAudioMeterInformation` nos endpoints de renderização ACTIVOS; nada abre
   cliente de áudio, nada muda volume nem mute) ligado a `shell_relaunch.arm()`:
   `SHELL_RELAUNCH_DEFERRED reason=audio` e a mudança **espera** (aplica-se no primeiro
   `tick` depois de o som parar). A recusa do tecto passou a falar **uma vez por minuto**
   (medido: 14 linhas em 67 s antes desta taxa).

## 3. Provas (comando → veredicto, corridas hoje)

```
python _main/ladder-signal-oracle.py                 -> LADDER-SIGNAL GREEN  arms=13 pass=13 fail=0 (rc=0)
python _main/ladder-signal-oracle.py --neg-arm       -> NEG-ARM PASS -- RED as designed (rc=1)
python app/webview/shell_relaunch.py --selftest      -> SHELL-RELAUNCH SELFTEST PASS (0 falha(s))
mutante de shell_relaunch.py (if sounding -> if False) -> rc=1, 4 falhas (os braços do som têm dentes)
python _main/agents-md-pins-oracle.py                -> AGENTS-PINS PASS -- 2 pin(s) checked live
python _main/tooling-intent-oracle.py                -> TOOLING-INTENT VERDICT PASS (vermelhas: 0)
python _main/battery-wiring-oracle.py                -> BATTERY-VERDICT battery-wiring PASS checks=7 fail=0
python app/webview/audio_playing.py                  -> PLAYING=False loudest=('Microphone (HyperQuadcast)', 9,1e-05)
```

**Bateria:** dois passos novos em `_main/_audit-verify-all.cmd` — `ladder-signal` e
`red-as-expected-ladder-signal` (ambos `always`; o último lê o resultado vivo do
`--selftest`). Pin re-medido e gravado em `AGENTS.md`:
`150181 B`, `1944 CRLF` / 0 bare LF,
sha256 `43461331168EDE4A1910F90B076A23FF291BA3ECDF9F3E34AAFB1AAF42B26F5D`.

## 4. SELF-AUDIT (o que este recibo NÃO prova)

* **Não provado:** a app em corrida real com a cura carregada. O worker vivo é de **08:13:13**
  e corre código **anterior** (`live-code-freshness-oracle` dirá `STALE`); a pane é `medium`
  e o worker é `high`, logo `taskkill /F` dá `Acesso negado` (medido). A cura entra no próximo
  arranque natural do worker (morte/relancamento), e é a guarda que eu próprio acrescentei que
  agora **adia** esse relancamento enquanto houver som — de propósito.
* **Não provado:** que `NO_AUDIO_CLEARED reason=caption` dispare na app viva; a prova é o
  braço 6 do oráculo (lê o CÓDIGO, a posição do ramo e a ausência da limpeza por pico), não
  uma corrida. O que **está** medido é o estado que ele corrige
  (`namedState=no-audio` + `live.count=1` com a legenda `'fuve da |'` às 09:00:57).
* **Sinal medido do recovery espontâneo:** às **08:26:13** o log dela escreveu
  `STATUS_APPLIED text="Receiving captions"` — a escada, por sorte, chegou ao endpoint que
  tocava. Isto mostra que o caminho está são e que o defeito era **de ordem/tempo**, não de
  captura.
* **`code-health`:** `worker/sotto_worker.py` e `app/webview/sotto_webview.py` continuam RED
  por tamanho e já estavam RED antes desta lane; este trabalho **acrescenta**
  (`+7 196 B` no worker). Não é regressão nova e não se pode corrigir sem partir o ficheiro —
  fica nomeado, não escondido.
* **Excluído por medição (não é a causa):** áudio em mute (nenhum endpoint), volume zero,
  modo exclusivo (`AUDCLNT_SHAREMODE_SHARED` é o único usado em `worker/`), mudança do
  dispositivo predefinido (não há `PolicyConfig`/`SetDefaultEndpoint` em lado nenhum da app) e
  perfil HFP do Bluetooth (`is_bluetooth_audio_device` já exclui o auscultador de todas as
  rungs desde a queixa de 2026-10-17).

## 5. Repetição ("recurrence-watch")

* **Instrumento:** `_main/ladder-signal-oracle.py` (arm 5 lê a chamada no worker, arm 1-4 o
  comportamento com medidor injectado).
* **Janela:** o passo `ladder-signal` da bateria corre a cada bateria (`always`).
* **Sinal de regressão:** `device-rotated reason=flat` a repetir sem candidato escolhido por
  sinal, ou `SHELL_RELAUNCH files=…` com som a tocar no `loudest` — qualquer dos dois quer
  dizer que a cura saiu.
