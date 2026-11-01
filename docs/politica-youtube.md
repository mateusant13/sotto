# Politica de lingua do track do YouTube (ORDEM 1)

## A REGRA ABSOLUTA (ordem do dono, 2026-10-30, verbatim)

> *"regra nunca que pode ser quebrada: legendas nao traduzem entre ingles pt br e espanhol.
> só outras linguas, todas pro ingles."*

| língua ORIGINAL do vídeo | o que é servido |
|---|---|
| inglês, português ou espanhol | **a própria língua, e nada mais** — nenhuma tradução em nenhuma direcção entre as três |
| qualquer outra (chinês, japonês, alemão…) | **inglês** (a auto-tradução do YouTube), e a língua do vídeo só como último recurso quando não há faixa inglesa |

Implementação: `app/webview/youtube_captions.py` — `UNTRANSLATED_LANGS = ('en', 'pt', 'es')`
e `_target_langs(orig)`, que devolve **um** elemento para as três (sem fallback: um
`(orig, 'en')` seria exactamente a tradução proibida).

**A ESCOLHA EXPLÍCITA DO MENU NÃO É UM BURACO NA REGRA.** O `TARGET_OVERRIDE` (pedido do
dono em 2026-10-21, quando a política permitia traduzir entre as três) passou a ser
**fechado pela regra**: a escolha continua a ser registada no log (`TRANSLATION_TARGET`),
mas não muda o que chega ao ecrã. Medido por dois braços e um mutante:
`a59` (3 origens × 4 escolhas → a própria língua sempre), `a60` (outra língua → inglês
sempre) e o mutante `the-explicit-pick-wins-over-the-rule`, que é apanhado pelos dois.

Portão: `python _main/youtube-captions-oracle.py` → **62 arms / 16 mutantes**;
`--neg-arm` sai **1 por desenho**.


> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 1. O track da YouTube tem de ser a LÍNGUA ORIGINAL
> *"to vendo que o transcript atual ta sendo traduzido. nao e pra traduzir. e pra ser lingua original.
> quando ingles, e quando pt br. quando chines ou japones, ou qualquer outra, pode traduzir. ah, menos
> espanhol."*

**REGRA SUBSTITUÍDA (2026-10-21) — fica escrita para ninguém a "arrumar" de volta; a regra em
vigor é a ABSOLUTA, no topo deste ficheiro.** O texto abaixo descreve o que o código fazia até
2026-10-30 (espanhol → `es,en`, com fallback inglês; `NEVER_TRANSLATED_LANGS`); os nomes de
símbolo que ele cita (`NEVER_TRANSLATED_LANGS`) **já não existem** — o conjunto passou a
`UNTRANSLATED_LANGS = ('en','pt','es')` e a lista das três passou a ter UM elemento, sem fallback.

**A REGRA DE 2026-10-21 (revista pelo próprio dono mais tarde no MESMO dia):**
*"para de traduzir pra pt br do ingles e do espanhol. o resto, traduza para ingles. qualquer
outra lingua pra ingles."* ⇒ **a legenda é INGLÊS para qualquer vídeo**, e **ESPANHOL** para um
vídeo espanhol (o espanhol **nunca** é traduzido). Implementado em
`app/webview/youtube_captions.py`: `TARGET_LANG = 'en'` (`:464`),
`NEVER_TRANSLATED_LANGS = ('es',)` (`:469`), `_target_langs(orig)` (`:472` — vídeo es → es,en;
vídeo en → en; qualquer outro → en, e a **própria língua** como último recurso, para um vídeo sem
faixa de inglês) e `_original_language(info)` (`:500`, o campo `language`, base `en-US` → `en`).
O portão tem **três** mutantes para a política (a língua original não lida, o destino em
português outra vez, o esquecimento da excepção espanhola) ⇒ **uma política que não se pode
quebrar é um comentário.**

**A REGRA ANTERIOR (substituída — fica escrita para ninguém a "arrumar" de volta):** original para
**en, pt-BR, es**; tradução **permitida** para zh/ja/qualquer outra; **espanhol NUNCA traduzido.**
O defeito vivia em `app/webview/youtube_captions.py` (`_auto_lang_keys`), que pedia
`pref` (traduzido, `tlang=`) antes de esgotar as chaves `-orig`.

**MEDIDO 2026-10-21 (a chave do defeito):** no vídeo que o dono estava a ver
(`-LODwSuymII`), `yt-dlp` diz **`language = 'en-US'`** — o vídeo é **INGLÊS** — e a
tabela tem **177 línguas**. A entrada portuguesa **não** é a original: é a
**auto-tradução** do YouTube, e o URL dela **não traz `tlang`** — por isso "a chave
que parece original" **não prova** a língua original. **O campo `language` é que
prová.** O serviço servia a **tradução** de um vídeo inglês (e o dono reclamou
exactamente disso). **A CORRECÇÃO (2026-10-21):** `_original_language(info)` (o campo `language`,
base `en-US` → `en`) + `_target_langs(orig)` (a política acima) → a faixa do **player** só conta
se for **da língua que a política pede** (o "1:1 com o vídeo" é sobre a legenda ser **do vídeo**,
não sobre seguir uma tradução que o player ligou). Portão:
`_main/youtube-captions-oracle.py` → **53/53 arms, 13/13 mutantes** (dois novos: a
língua original não lida, e a política a permitir tudo). **Re-medir antes de citar
linha.**
