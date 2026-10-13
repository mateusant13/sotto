# RECIBO — isolamento POR KIND no mapa de handlers do `SottoHost.dispatch`

Data 2026-10-13. Escopo de escrita usado: `app/webview/sotto_webview.py` e
`_main/bridge-handler-map-oracle.py` (mais nada). Sem `git add`/`commit`/`push`.
Nada foi lançado: nem app, nem shell, nem worker (a bateria mede `launches=0`).

## A estrutura escolhida

A tabela dentro de `dispatch` deixou de ser `kind -> VALOR` e passou a ser
`kind -> DESCRITOR`, resolvido entrada a entrada:

| forma | entradas | resolução |
|---|---|---|
| `('host', '_nome')` | 20 | `getattr(self, '_nome', None)` + teste `callable` |
| `('shell', '_nome')` | 2 (`setStripOffset`, `sotto:setStripOffset`) | `getattr(self._shell, '_nome', None)` — eram `self._shell._set_strip_offset` |
| `('shell-call', 'nome', 'page')` | 3 (`hide`, `toggle`, `quit`) | `getattr(self._shell, 'nome')` + lambda que chama com a razão FIXA e descarta o payload, exactamente como a lambda antiga |

**Total medido: 25 entradas** (20 host + 2 shell + 3 shell-call). O plano falava
de "~40"; o número real, contado da tabela, é 25. Os três lambdas e as duas
entradas `self._shell._xxx` foram tratados explicitamente, como o plano exigia.

* `_resolve_handler_map(table)` percorre a tabela **uma entrada de cada vez**,
  cada uma no seu próprio `try/except`. A entrada que não resolve é SALTADA e
  regista-se no log do shell:

      BRIDGE_HANDLER_MAP_FAILED kind='...' name='...' error=... -- THIS kind is dead; every other kind is not

* `_resolve_handler(spec)` é quem resolve: `getattr(owner, name, None)` e o teste
  `callable(...)`. Um nome que não existe levanta
  `AttributeError('SottoHost._x is not callable')` DENTRO do try/except por
  entrada, portanto nunca escapa para a construção do mapa.
* O `try/except` à volta do dict literal **fica**, e é a REDE DE ÚLTIMO RECURSO,
  não o fix: se alguém voltar a escrever um ACESSO A ATRIBUTO na tabela, o mapa
  inteiro falha e a rede di-lo alto (`BRIDGE_HANDLER_MAP_FAILED` SEM `kind=`),
  em vez de morrer em silêncio no logger do pywebview. O comentário que dizia
  "isto NÃO isola" foi reescrito para dizer o que o código faz agora.
* **Não usei `__getattr__` no `SottoHost`** (a alternativa rejeitada no plano).
  `sotto_webview.py:3565-3574` regista que o pywebview percorre este grafo de
  objectos e que nomes com `_` são saltados ANTES de serem lidos. Confirmei o
  mecanismo na fonte: `webview/util.py:190-194` (`for name in dir(obj)` ...
  `if name.startswith('_'): continue`). Os dois métodos novos começam por `_`,
  logo continuam invisíveis para o pywebview — nada muda na leitura de atributo
  ausente para o pywebview.
* Comportamento de um kind cujo descritor não resolve: SÓ esse kind morre, é
  NOMEADO no log do shell, e cai em `BRIDGE_UNKNOWN_KIND` uma linha depois (a
  vista da página, inalterada). Nenhum vocabulário novo foi inventado.

## O que foi medido em processo (sem lançar nada)

* 25 entradas, zero kinds duplicados, zero nomes irresolúveis contra as classes
  reais, e os 25 kinds chegam a um handler (nenhum cai em `BRIDGE_UNKNOWN_KIND`).
* Com `'bogusmutant': ('host', '_no_such_method_at_all')` numa CÓPIA:
  `BRIDGE_HANDLER_MAP_FAILED kind='bogusmutant' name='_no_such_method_at_all'`
  e `renderer-ready` continua a chegar ao handler (`RECEIVER_READY` no log).
  Isto é o isolamento por kind, medido.
* Dos kinds que o preload injectado pode postar (`post('...')` e
  `historyCall('...')` dentro do próprio shell), 22 de 22 têm entrada na tabela.
  (`lazy-asset` é postado por `app/panel/lazy-assets.js`, fora do preload do
  shell; está fixado por nome no contrato do portão.)

## Portão — números antes e depois

`_main/bridge-handler-map-oracle.py`

| | antes | depois |
|---|---|---|
| controlo | `VERDICT: PASS -- 3 check(s), 0 fail`, rc=0 | `VERDICT: PASS -- 7 check(s), 0 fail`, rc=0 |
| `--neg-arm` | `VERDICT: PASS -- 4 check(s), 0 fail`, rc=0 (mutante RED em "unbuildable") | `VERDICT: PASS -- 9 check(s), 0 fail`, rc=0 (M1 RED **e** M3 RED) |

Pins: shell antes `505111 B` / `BDB1B96E3A790558D3BC3D8D54426A10979EB35F9EE1DCC53B5E963667C29282`;
depois `508824 B`, 9872 linhas, 9871 CRLF / 0 bare LF,
`A225E72ECBB0F1A0F6C53F85EDE6EF25393003211A8D22B51D7F83ED8B4C4D94`.
Oráculo antes `5229 B` / `24696D72FDC9408322CD2703F93DE0C1A05A0690674A7A7A502755B9396248DB`;
depois `12769 B` / `7F500EF2F36F9BEE71EBC2CD9F47532781BB66C4E268BC422A67FB6868D3E931`.

**O portão NÃO foi partido: o `--neg-arm` continua RED.** O âncora do mutante
antigo (`'lazy-asset': self._lazy_asset,`) deixou de existir com a tabela em
nomes, portanto foi actualizado; e o oráculo ganhou dois braços porque, com a
tabela em nomes, o mutante antigo já não conseguia testar a propriedade nova:

1. **controlo (7 checks)** — o mapa constrói; NENHUMA entrada se diz irresolúvel;
   um kind desconhecido chega a `BRIDGE_UNKNOWN_KIND`; a tabela tem exactamente
   os 25 kinds do contrato (lidos do texto-fonte, porque a tabela é local ao
   `dispatch`); TODOS os 25 kinds chegam a um handler; e todos os kinds que o
   preload pode postar têm entrada.
2. **isolamento (corre sempre, tem de PASSAR)** — um
   `('host', '_no_such_method_at_all')` injectado numa CÓPIA é saltado, NOMEADO
   e um kind bom continua a despachar. É este braço que mede o fix.
3. **`--neg-arm` M1** — o defeito #1 na forma antiga (um ACESSO A ATRIBUTO na
   tabela): o mapa inteiro falha e a rede di-lo; RED, como antes.
4. **`--neg-arm` M3** — o mesmo nome mau com o `try/except` por entrada
   neutralizado (`except ()`): o `dispatch` volta a morrer e o kind bom morre com
   ele; RED. É este braço que impede o braço 2 de ser vazio.

Nota de honestidade sobre o M3: a primeira versão do braço aplicava só a mutação
da guarda (sem o nome mau) e ficou GREEN — foi a própria corrida que a apanhou,
porque o `check` exigia o vermelho no sítio certo. O `mutant()` passou a aceitar
VÁRIOS pares (âncora, substituição) e a exigir cada âncora exactamente uma vez.

## Bateria da casa

`node _main/instruments-battery.mjs`

* antes: `SUMMARY: 81/81 instrument(s) rc=0; failed=0; launches=0`
* depois: `SUMMARY: 81/81 instrument(s) rc=0; failed=0; launches=0`
  (com `handler-map` 7 checks / 0 fail e `handler-map neg` 9 checks / 0 fail)

Compilação: `py -3 -m py_compile app/webview/sotto_webview.py` -> rc=0 depois de
CADA edição (duas edições no shell, cinco no oráculo). Edições feitas com a
ferramenta `edit` e strings exactas; CRLF preservado (9871 CRLF / 0 bare LF).

## O que NÃO fechei

* **A app do dono está a correr e não recarrega este ficheiro.** A correcção
  está em DISCO, não no processo em execução (pid 44684): só um arranque novo a
  carrega. Lançar/relançar é do Lead, não meu — não lancei nada.
* **Não medi ponta-a-ponta.** Nenhum `BRIDGE_HANDLER_MAP_FAILED kind=... name=...`
  real chegou a um log do shell com a app no ar. A prova é em processo: o
  `dispatch` REAL chamado com um `log` substituído, como no portão anterior.
* **O braço de isolamento prova o despacho, não a página.** Que o painel volte a
  pedir `ready()`/`lazy-asset` depois de um restart é do domínio do shell real.
* **`lazy-asset`** é postado por `app/panel/lazy-assets.js`, fora do preload do
  shell: está fixado por nome no contrato, mas o braço "preload" do portão não o
  vê (conta 22, não 23).
* **Duas entradas são aliases legados** (`sotto:transparency`,
  `sotto:setStripOffset`) que o preload actual já não posta. Ficaram na tabela
  como estavam — não removi nenhuma entrada.
* Não toquei em `worker/`, `app/panel/`, nos mutantes `_main/_*mutant.py` (fora do
  escopo) nem no comentário de `_set_strip_offset` além de corrigir a linha citada
  (`:6950` -> `:7005`, onde o método está hoje).

