# Proveniência por aba do navegador — o que é possível e o que NÃO é

**Medido 2026-10-08** por duas lanes independentes (recibo completo:
`_main/receipt-audio-source-metadata.md`). Esta nota existe porque o dono pediu,
verbatim: *"se for algo como o navegador, quero que seja possivel saber o titulo da
aba do navegador que fez o som"* — e a resposta é **não pela via do sistema**.

## 1. O que está PROVADO

| pergunta | resposta medida |
|---|---|
| dá para saber que **app** faz som? | **SIM** — sessões WASAPI (`IAudioSessionManager2` → `IAudioSessionControl2`), 25 740 leituras, 0 indisponíveis |
| dá para saber **qual** está mais alto? | **SIM** — pelo maior `peak_max_win` numa janela de 1 s (o peak instantâneo pisca e faz a fonte saltar) |
| dá para saber a **aba**? | **NÃO** — e não é limitação de esforço, é **por construção** |

## 2. Porque é impossível na camada do sistema

1. **O `GetDisplayName()` da sessão do Chrome é string VAZIA.** Censo: `chrome.exe`
   **1200 leituras, 1200 vazias** — 141 delas com `peak>0.001`, ou seja **a soar**.
   O único `display_name` não vazio em 25 740 leituras foi o dos sons do sistema.
2. **O misturador de volume do Windows PARECE saber — e não sabe.** O
   `"YouTube — Google Chrome"` que ele mostra é o **fallback do Sndvol**, não o
   `GetDisplayName`. MSDN, verbatim: *"The default name incorporates information such
   as the window title or version resource of the audio application."* Isto é: **o
   título da JANELA, que é a aba SELECCIONADA** — que pode não ser a que está a soar.
3. **Um processo de áudio serve TODAS as abas** do perfil
   (`--type=utility --utility-sub-type=audio.mojom.AudioService`), e a janela é de
   outro pid. **Existe UMA sessão para o browser inteiro.**
4. **UI Automation não resolve:** lista as abas com título e `IsSelected`, mas **não
   diz qual soa**. O único indicador candidato (o botão de silenciar a aba) esteve
   aceso em **4 abas** em **49 de 50** amostras simultâneas com **todos** os meters a
   `0.000000`.

## 3. O único caminho verdadeiro: uma EXTENSÃO de navegador

Pequena, e é a única coisa que sabe a verdade. Ela reporta, por localhost, o que o
browser já sabe internamente:

```json
{"schema":"sotto.browser-tab/1","t":<unix_ms>,"browser":"chrome|edge|firefox",
 "tabs":[{"tabId":41,"title":"…","url":"…","audible":true,"active":false,"windowId":2}]}
```

**Regra de junção:** correlacionar as abas com `audible:true` com a **sessão de áudio
do browser pelo TEMPO** — **nunca pelo PID** (provado que não mapeia). O título da
janela entra no máximo como sinal fraco e secundário.

## 4. As duas regras que ficam para o produto

1. **O título da janela NUNCA pode ser apresentado como "a aba que fez o som".** É a
   aba selecionada, e mente exactamente no caso que o dono descreveu — ouvir uma aba
   de fundo (um amigo no Discord, um vídeo atrás do jogo).
2. **`sources` varre TODAS as endpoints activas, nunca só a por omissão.** Medido: a
   por omissão era `VoiceMeeter Input` e o Chrome renderizava para `CABLE Input` —
   **enumerar só a por omissão daria a app errada, com toda a confiança.**

## 5. O que isto custa

Meter a **4 Hz** = **2,11 % de um núcleo**, 54,8 MB RSS, 1 thread. Recomendado: **1–2 Hz
em regime**, 4 Hz só com o painel aberto. UI Automation = 0,281 s de CPU por dump
(~25× mais caro) → só quando a fonte é um navegador, a ≤0,2 Hz e com cache.

**E o ShareX não ensina nada disto:** ele só escolhe um **dispositivo**
(`ScreenRecordingOptions.cs:105/128/195` → `-i audio={FFmpeg.AudioSource}`, um
argumento dshow para o ffmpeg), sem proveniência por app ou aba. Ausência provada com
controlo: grep de termos de sessão = **0**; o mesmo grep em `dshow|AudioSource` = **25**.
