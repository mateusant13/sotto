# RECEIPT 2026-11-03 — o cue do YouTube chega ao ecrã 1:1 (revelação no relógio do player)

Lane: `YtLand`. Repo: `H:/sotto`.
Ficheiros da lane: `app/webview/caption_overlay.py` (editado),
`_main/youtube-land-oracle.py` (novo), este receipt.

## 1. O observado, reconferido no log vivo

```
$ grep -c "why=painted-other-track" _main/webview-run.log
434
$ grep -c "YOUTUBE_CAPTION" _main/webview-run.log
8710
$ python _main/youtube-land-oracle.py
LOG       H:\sotto\_main\webview-run.log (416975 linhas, 0 CAPTION_LAND)
CUES      pintados=0 descartados=0 decididos=1195
VERDICT   SEM DADOS -- nenhum CAPTION_LAND no log (a app viva ainda nao tem a linha)
```

`decididos=1195` são os cues distintos que o shell decidiu (`YOUTUBE_CAPTION ... cue=<start> t=<t>`);
os 8710 são todas as linhas `YOUTUBE_CAPTION` (as outras variantes logam `lines=` e não `cue=`).
As 18 linhas da instância viva (pid 28888) que o ticket cita são o recorte dessa sessão.

O que o código dizia, lido antes de mexer: `sotto_webview.push_caption_to_window`
(12099–12140) converte as `rows` do player em TEXTO e força `instant=True`;
`CaptionOverlay.set_text(..., instant=True)` (docstring antigo: *"chega já revelada …
nada aqui a volta a temporizar"*) desenhava o texto inteiro. Resultado: o cue chega
de segundo a segundo, inteiro, e é pintado inteiro no instante da chegada.

## 2. O que foi construído

### `app/webview/caption_overlay.py`

* `_PlayerCue` — a janela do player com o **relógio do próprio player**:
  `rows` (forma de `youtube_reveal.rows_from_cues`: `text`/`words`/`start`/`end`/`cap`),
  `t` (segundos de vídeo na leitura) e `at` (`time.monotonic()` da leitura).
  `clock(now) = t + (now - at)`, limitado a `PLAYER_HOLD_S = 3.0` (o mesmo
  `YT_ANCHOR_MAX_S` do shell): entre duas leituras do UIA a palavra seguinte aparece
  no instante em que o player a desenha, não no instante em que o UIA respondeu.
* **Resync a cada cue**: `set_text(..., cue={...})` cria uma instância nova por cue.
  O relógio **nunca recua** (`floor` = instante mais adiantado já desenhado), e um
  seek para trás não herda o piso (folga de 0,05 s em `_cue_from`).
* `_display()` ganhou o ramo do cue; `_next_delay()` arma o tick **no instante da
  próxima palavra** (`_PlayerCue.next_clock`), não num compasso fixo.
* `_clamp_rows()`: no máximo `PLAYER_ROWS = 2` linhas **físicas** (uma linha do
  payload que traga `\n` vale por duas); sai a do topo, nunca a que cresce.
* `_log_land()`: `CAPTION_LAND cue_t0=… paint_t=… lag_ms=… rows=… words=… text=…`,
  escrito **depois** do `UpdateLayeredWindow` devolver OK.
  `lag_ms = (relógio do player na 1.ª pintura) − t0 do cue`.
* `CAPTION_CUE_DROP cue_t0=… reason=superseded` quando um cue é substituído antes
  de pintar; `CAPTION_CUE_INVALID` / `CAPTION_CUE_EMPTY` quando o payload não serve.
* `_blank_pixels()` + `_blank`: um cue legitimamente pode ter 0 palavras reveladas
  (antes do `start` da linha). Antes, o caminho vazio chamava `hide()` — limpava o
  estado e **não armava tick**, logo a revelação nunca voltava; e `show(True)`
  re-mostrava o bitmap do cue anterior. Agora os píxeis saem, o cue fica, o tick
  fica armado, e `show()` recusa mostrar uma janela sem pixel novo.
* `instant=True` **sem** `cue` continua a desenhar o texto inteiro: sem relógio
  nenhum não há como revelar sem inventar tempo (é o caminho vivo de hoje, ver §5).
* `_fail_open` larga também o cue: um motor partido desenha o texto que já chegou.

### `_main/youtube-land-oracle.py`

Lê o log, por cue pintado: `land_lag_ms`. Refaz `paint_t − cue_t0` e recusa um
ficheiro onde os três números não concordam (um instrumento que acredita no seu
próprio campo resumido não mede nada). `cues_pintados`, `cues_descartados`
(`CAPTION_CUE_DROP` + `CAPTION_DROP_EPOCH`), mediana/p95/max; `rows > 2` é
violação da segunda metade da aceitação.

Contrato de saída: `0` PASS (mediana ≤ 150 ms com ≥ 5 cues, nenhuma pintura > 2
linhas); `1` FAIL; `2` SEM DADOS (nenhum `CAPTION_LAND`, menos de 5 cues, log
ilegível, números inconsistentes).

`--neg-arm` constrói em memória (o processo vivo é anterior à mudança) um log
sintético VERDE, exige PASS nele, e aplica 6 mutantes — todos têm de cair.

## 3. O que mediu (comandos e saída)

```
$ python -m py_compile app/webview/caption_overlay.py _main/youtube-land-oracle.py
py_compile rc=0
$ python _main/youtube-land-oracle.py --help >/dev/null
--help rc=0
$ python _main/youtube-land-oracle.py --neg-arm
NEG-ARM fixture  log sintetico VERDE
CUES      pintados=8 descartados=2 decididos=8
LAG       mediana=15ms p95=19ms max=19ms (limiar 150ms, minimo 5 cues)
VERDICT   PASS -- mediana 15 ms <= 150 ms em 8 cues
NEG-ARM control  rc=0 PASS
NEG-ARM late       pintura 500 ms atrasada                want rc=1 got rc=1 CAIU
NEG-ARM no-land    sem CAPTION_LAND nenhum                want rc=2 got rc=2 CAIU
NEG-ARM one-cue    um cue so' (amostra pequena)           want rc=2 got rc=2 CAIU
NEG-ARM lying-lag  lag_ms a mentir contra paint_t         want rc=2 got rc=2 CAIU
NEG-ARM no-t0      linha sem cue_t0 (nao se le')          want rc=2 got rc=2 CAIU
NEG-ARM three-rows pintura com 3 linhas                   want rc=1 got rc=1 CAIU
NEG-ARM real       saltado: o log vivo ainda nao tem CAPTION_LAND
NEG-ARM 6 of 6 mutant(s) caught
NEG-ARM PASS
neg rc=0
```

Ensaio da revelação sem janela (objeto `NativeCaptionOverlay` sem `hwnd`, só o motor):

```
t0 -> 'uno\n'
t0+0.6 -> 'uno dos\n' next_delay 0.4     # um tick por PALAVRA, não um compasso
dup cue_t0 -> CAPTION_CUE_DROP cue_t0=5.000 reason=superseded / True
string rows -> [{'text': 'linha um', …}, {'text': 'linha dois', …}]
empty rows -> CAPTION_CUE_EMPTY t=3.000 / None   # cai no texto inteiro
```

E com `words` + `end` (o caso real do payload), no mesmo ensaio: `0,0 s → 'So'`,
`0,45 → 'So the'`, `0,9 → 'So the compiler'`, `1,6 → 'So the compiler would'`,
`2,05 → 'have'` (a linha do cue anterior saiu no seu `end`; nunca 3 linhas).

## 4. Diff e hashes

```
$ git diff --stat -- app/webview/caption_overlay.py
 app/webview/caption_overlay.py | 296 +++++++++++++++++++++++++++++++++++++++--
 1 file changed, 286 insertions(+), 10 deletions(-)
```

| | sha256 |
|---|---|
| antes | `dbc82ec9edcac02b7b18e1f8f62626aa27894270179198e47a393aa0143d3115` |
| depois | `584aadaa98e7ea50c3defac894799c8db0b0c9ac238715d0f1925f851e151153` |

`_main/youtube-land-oracle.py` (novo): `1ef67038f11c695d21b8444ac77b20e5b3b14cf4eaa934068969fdb4b26c5fe8`.

Crescimento estrutural: `caption_overlay.py` 657 → 933 linhas, 29431 → 42656 bytes.
O baseline de `_main/code-health-oracle.py` tem `{bytes: 27819, lines: 625,
defs: 1, except_pass: 2, max_func: 81}` para este ficheiro — o ficheiro **já estava**
acima do baseline antes desta lane (29431 bytes / 657 linhas); esta lane aumenta a
dívida publicada. `defs` e `except_pass` não mudam (as funções novas são métodos).
Se a lane do ratchet quiser fechar isto, é `code-health --update` — **fora** desta lane.

## 5. O que NÃO prova (a prova viva é do assento principal)

1. **Nenhum pixel foi observado.** Não larguei a app (regra do repo) e o processo
   vivo (pid 28888) corre o `caption_overlay.py` anterior: o log vivo tem
   `0 CAPTION_LAND` e é por isso que o oráculo devolve `SEM DADOS` (rc=2). O caminho
   do cue está provado só por ensaio headless (motor + `_next_delay` + log).
2. **O overlay ainda não recebe o relógio**: o shell de hoje chama
   `ov.set_text(text, prev, instant)` sem `cue=` (§6). Enquanto essa chamada não
   mudar, o comportamento em produção é o de antes (`instant=True` desenha o cue
   inteiro) e o oráculo continua `SEM DADOS`. Isto é deliberado: sem relógio não se
   inventa tempo.
3. **O `land_lag_ms` nunca foi medido com a app viva** — só contra fixtures. O braço
   `real-late` do `--neg-arm` está escrito e hoje imprime `saltado`; no primeiro log
   com `CAPTION_LAND` ele passa a exigir RED sobre o log real.
4. **A quebra de linha não foi re-medida.** `_layout`/`caption_wrap` não foram
   tocados (o `_main/youtube-rows-oracle.py` mede exactamente `_layout`), e o canal
   do texto já vem pré-quebrado (`rows_text`); o que esta lane acrescenta é o tecto
   de 2 linhas **físicas**. Uma linha do payload com `\n` interno que antes passava
   como duas linhas continua a passar — agora contada no tecto.
5. **`PLAYER_ROWS = 2`** corta a 3.ª linha do roll-up (medida em 94 % dos quadros como
   2 linhas, 3 nas transições). Foi a leitura literal de "maximo 2 linhas" do ticket;
   se o dono quiser o roll-up de 3, é uma constante.

## 6. Linhas que precisam de mudança FORA do meu ownership (`app/webview/sotto_webview.py`)

O overlay já aceita `cue=`; falta o shell levá-lo até lá. A mudança mínima, em 4 sítios.
**Números de linha de hoje** (2026-11-03, e o ficheiro está a ser editado por outras
lanes: procure pelo SÍMBOLO, não pelo número).

**(a) `_drain_caption_pending` / `_push_caption_window`** — a fila. O `instant` já vive
num slot próprio (`self._caption_pending_instant`, 12102); o `cue` segue o mesmo
caminho, um slot ao lado:
```python
self._caption_pending_cue = cue           # junto do `_caption_pending_instant`
...
ov.set_text(new_text, new_prev, instant, cue=cue)   # linha 12111 hoje
```
(o slot `self._caption_pending = (now, text, prev, epoch)` em 12235 fica como está).

**(b) `push_caption_to_window` (12169) / `external_caption` (12366) / a chamada de
12446** — os três saltos que hoje deixam as `rows` cair:
```python
def push_caption_to_window(self, text, previous=None, credits=None, instant=False,
                           rows=None, cue=None):
...
def external_caption(self, text, source, final=False, instant=False, rows=None,
                     cue=None):
...
    self.push_caption_to_window(text, instant=instant, rows=rows, cue=cue)
```

**(c) `_tick` (a janela de rows em 4220)** — o único ponto por onde todo o caminho do
YouTube passa; é lá que o payload se monta (uma vez, não por ramo):
```python
    def _yt_cue_payload(self):
        """O cue com o RELOGIO do player. Ver `caption_overlay._PlayerCue`."""
        anchor = getattr(self, '_yt_anchor', None)
        track = getattr(self, '_yt_track', None)
        if not anchor or not track:
            return None
        import youtube_reveal
        base_t, base_mono = anchor
        rows = youtube_reveal.rows_from_cues(track.get('cues') or ())
        # A JANELA, e nao a faixa toda: `_PlayerCue.frame` corre a cada tick.
        rows = [r for r in rows
                if (r['end'] is None or r['end'] >= base_t - 1.0)
                and r['start'] <= base_t + 3.0]
        return {'rows': rows, 't': float(base_t), 'at': float(base_mono)}
```
e nas chamadas `self.shell.external_caption(line, source, final=…, instant=bool(yt_mode),
rows=rows)` acrescentar `cue=self._yt_cue_payload()`.

`_yt_anchor` já é gravado exactamente nos três ramos que interessam (hoje 3744
`painted`, 3796 `painted-other-track:clock`, 3876 `has-cue`), com
`(relogio do player, time.monotonic())` — que é precisamente o par `t`/`at`.

**(d) o `instant = True` forçado quando há `rows` (hoje 12205)** — pode ficar; o
overlay ignora `instant` quando recebe `cue`, e o texto continua a viajar como
reserva para o caso `cue=None`. A nota de 12202 (*"a rows window is ALREADY the
player's painted frame: it must never reveal again"*) descreve o defeito: a janela
que chega não é a pintura do player, é o cue inteiro — é por isso que ela precisa
de relógio, não de supressão de revelação.

Depois disto, o oráculo desta lane passa de `SEM DADOS` (rc=2) a um veredicto real
sobre `land_lag_ms`, e o `real-late` do `--neg-arm` deixa de imprimir `saltado`.
