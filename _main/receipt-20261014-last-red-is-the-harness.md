# O ULTIMO VERMELHO: O LIMITE ESTA NO DESENHO DA MEDICAO, NAO NO CODIGO

2026-10-14. Fecho o arco com a causa final, que nao e de codigo.

O `preflight-refusal-visible-oracle.py` arm 4 precisa de um controlo que devolva **rc 2 com
ZERO bytes de texto do argparse**. O `run_wrapper` desse oraculo (linha 59) e
`def run_wrapper(path, args, env=None)` -- **nao tem opcao de pipe**, portanto o filho corre
sempre com stdout e stderr capturados, e o uso do argparse aparece SEMPRE na saida.

Foi por isso que as minhas seis tentativas falharam todas: nenhum controlo possivel pode
produzir a saida cega enquanto o harness lhe der um pipe. O texto que a arm 4 exige que esteja
AUSENTE e o texto que o proprio harness POE la.

## O que isto significa, e porque nao e desculpa

A cura do G5 (o redireccionamento do stderr mais a mensagem) foi medida CORRECTAMENTE pelas
armas 1 a 3: o chamador ve o texto e o log tem o recibo. **A cura funciona.** O que nao funciona
e a medicao do CONTROLO, que nunca pode ser cego com um harness que ve.

## A correccao, e nao e minha

`run_wrapper` precisa de um parametro `pipe=False` que corra o filho com
`stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`, e o controlo passa a ser um wrapper
que de fato nao redirecciona nada. Isso e MUDAR O ORACULO para poder medir -- e um oraculo
que precisa de ser mudado para dizer NAO nao esta a dizer nada.

## O balanco

P0-1, P0-3, P0-4 e P0-5 fechados e medidos. O ganho maior (a segunda passagem M3) veio de uma
lane. O vermelho que fica e deste arco, e esta diagnosticado ate ao limite.

**NAO AFIRMO que a bateria esta verde. Esta 88/9.**
