# O CONTROLO FICOU CEGO -- e o que falta e uma linha

2026-10-14. Fiz o `pipe=False` que a nota anterior dizia faltar, e a medida mudou:

```
arm 4  CONTROL : rc=2, caller text=0 B          <- O CONTROLO FICOU CEGO
                    log delta=+52 B, delta names the flag=true   <- mas ainda escreve
```

Antecipei isto ha um round (the control can never be blind under a harness that sees) e
estava ERRADO: o texto vinha do pipe, e sem pipe o controlo da 0 B. O que resta e a OUTRA
metade: o wrapper de 2026-10-06 tambem carrega o recibo no log (+52 B a nomear a flag), e o
oraculo trata qualquer recibo no delta como sinal de que o controlo ja tem a cura.

## O que falta, uma linha

Correr o controlo com o log-append tambem desligado. O delta passa a +0 B e o braco fica
verde. **Reverti o oraculo ao HEAD** porque nao o acabei.
