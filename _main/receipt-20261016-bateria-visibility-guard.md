# BATERIA 135/145: o `visibility-guard` era MEU, e esta fechado

## O vermelho, e a causa

    rc=1 visibility-guard (rows #60/#61)
         AttributeError: 'Probe' object has no attribute 'show_caption_window'
    rc=1 visibility-guard neg   (o mesmo)

O `hide_panel` REAL passou a chamar `self.show_caption_window(False)` -- fui eu que
acrescentei, para a janela da legenda esconder quando o painel se esconde. E o oraculo dirige
o `hide_panel` com um stub (`_main/panel-visibility-guard-oracle.py:76 class Probe`) que
carrega so o que os metodos dirigidos tocam. **O stub nao tinha o metodo novo, e o oraculo
morreu com AttributeError.** Os dois vermelhos eram o mesmo defeito, visto de dois angulos.

## A cura

Acrescentado ao stub, com o motivo escrito no proprio ficheiro:

    def show_caption_window(self, on):
        self.caption_window_calls.append(on)
        return True

E o `self.caption_window_calls = []` no `__init__`. **Nao e afrouxar o gate: o stub tem de
modelar o que o metodo dirigido toca, e o metodo dirigido mudou porque o PRODUTO mudou.**

## Medido depois

    VERDICT: BOTH ROWS CLOSED      RUN=0
    NEG-ARM PASS                   NEG=0   (wrong: [])

Ou seja: o braco negativo continua a discriminar -- remover a guarda do re-assert vira o caso
D sozinho, e tirar a clausula de precisao do run.cmd quebra o check da promessa. **A cura nao
tornou o oraculo cego.**

## E a bateria inteira, na mesma corrida

    SUMMARY: 135/145 rc=0; failed=10; launches=0

Tres oraculos meus, corridos a parte, TODOS verdes:

    three-overlays-oracle ......... 32 checks, 0 failed, PASS; neg-arm todo RED
    strip-drag-loop-oracle ........ PASS 5/5
    emit-hot-path-oracle .......... PASS

## Os NOVE vermelhos que ficam, por atribuicao

  * `AGENTS.md pins` -- os pins estao velhos (o tamanho do --help e a linha da bateria).
    Esperado depois de mexer na bateria; precisa de re-baseline, nao de cura.
  * `theme gen reproduces (regra 10)` -- **o gerador e os ficheiros shipped nao batem.**
    `git status` mostra `_main/_design-lane/gen_themes.py` E os `theme-*.css` modificados na
    arvore. **Nao sei ainda se e trabalho meu ou de outra lane em voo, e NAO mexo em
    ficheiro de outra lane sem saber.**
  * `panel state atomic neg`, `caption independent of panel`, `botoes lane oracle`,
    `botoes lane gesture`, `theme switching` e `theme switching neg` -- **nao atribuidos.**
    Cada um precisa da sua leitura antes de eu tocar em nada.
