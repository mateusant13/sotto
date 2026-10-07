# Como usar o `gpt` (consultgpt) — ChatGPT no terminal, sem API key

O dono pediu isto **permanentemente**: quando houver uma pergunta de engenharia ou de design em
aberto, **perguntar ao ChatGPT por este caminho** em vez de a deixar no ar — e usar as sugestões dele
**que se concordar** (o julgamento continua a ser de quem pergunta; a resposta dele não é uma ordem).

## O binário

```
C:\Program Files\Python311\Scripts\gpt.exe      (entra no PATH; `where.exe gpt` confirma)
gpt help                                        (a ajuda completa)
```

`gpt` é o **`consultgpt`**: fala com o ChatGPT através de um **browser real** — não precisa de API key
nem de token. Instalado globalmente, fora do repo. Não confundir com o `codex`
(`H:\env\npm-global\codex.cmd`), que é outro cliente GPT e cuja autenticação **está morta nesta
caixa** (`refresh token already used` → 401; para o reanimar é `codex logout` e `codex login`).

## A invocação que funciona (e as duas armadilhas)

```powershell
# 1) escrever a pergunta num ficheiro UTF-8 (evita todo o inferno de quoting)
#    e passar --no-code: sem isso ele ERRA — "no code provided. Attach code with -f PATH or @file"
# 2) --prompt-file é a forma PowerShell-safe de a entregar

& gpt --no-code --session <nome-da-sessao> --prompt-file _main\<pergunta>.txt > _main\<resposta>.txt 2>&1
```

- **`--no-code` é obrigatório** para uma pergunta que não traz código. Sem ele: rc=1 e nenhuma
  resposta.
- **`-f caminho` / `@file` no texto** servem para anexar código; com código anexado o `--no-code` sai.
- **O diálogo de sessão não bloqueia**: ele pergunta "Save responses to directory [...]" e, sem stdin
  (EOF), segue com o default. Viu-se a funcionar assim.
- **Demora 30–60 s.** Correr em background (job) e recolher depois; não ficar à espera.
- **A saída vem com ruído**: um cabeçalho tipo `1. Executive Summary / 2. Findings / Evidence / Label`
  (é o template de revisão dele) e, às vezes, uma linha do prompt interactivo colada ao texto. O
  conteúdo útil está lá; a limpeza é nossa antes de citar.
- Sessões ficam em `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt\sessions\`.
- `--headed` mostra o browser, `--headed-offscreen` mostra escondido; **por omissão é headless** (não
  abre janela nenhuma — respeita a regra da casa).
- `--list` / `--show` leem respostas guardadas de uma sessão.

## O MODO DE FALHA que já vimos (importante: ele FALHA em silêncio)

Medido 2026-10-07: uma chamada voltou com **zero conteúdo de resposta** — só o ruído operacional dele —
e no ficheiro ficou este aviso do Playwright:

```
WARNING:tools.session.eval_helpers:Unhandled exception in eval_helpers.py
  ... playwright._impl._errors.Error: Page.evaluate: Execution context was destroyed,
      most likely because of a navigation
```

Traduzido: a **página do ChatGPT navegou/recarregou** enquanto ele esperava pela resposta, o contexto
de execução foi destruído e a resposta perdeu-se. **O rc da chamada não denuncia isto** — há de se
verificar sempre o tamanho do ficheiro e a presença de texto útil, não o código de saída.
**Regra:** depois de cada `gpt`, checar se o ficheiro tem conteúdo real; se tiver só o ruído (tipicamente
< 3 KB com "Prompt size" e o WARNING acima), **a pergunta não foi respondida — repetir**. Já o vimos
funcionar na mesma sessão (a ronda dos cinco designs voltou com 6,2 KB de conteúdo útil), portanto é
intermitente, não permanente.

## O que já se perguntou por aqui

| data | pergunta | onde está a resposta |
|---|---|---|
| 2026-10-07 | direções de design para o painel (5) | `docs/design/gpt-directions.md` |
| 2026-10-07 | encerrar de verdade (Job Object vs um processo), arquitetura do overlay triangular, e se a identidade da linha por `start` é completa | `_main/eng-ask.txt` (pergunta) → resposta recolhida no job; registar em `docs/design/` ou aqui |

## Regra de uso (a que o dono pediu)

1. Pergunta de engenharia ou de design **em aberto** → pergunta-se, não se decide por impressão.
2. **Concordância explícita:** adota-se o que se concorda, e diz-se o que não se adotou e por quê.
   Nada entra no código só porque ele sugeriu.
3. O que ele sugerir e for adotado **fica registado** com o alcance da sugestão (o que se aceitou, o
   que se rejeitou), para não se repetir a mesma pergunta na semana seguinte.
