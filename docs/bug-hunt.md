# MODO BUG-HUNT (protocolo completo)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


> As três notas que o dono mandou ler, por caminho e data (medidas nesta máquina):
> `G:\superharness\runs\workflow-quality-loop-findings.md` (20:20),
> `I:\!manager\state\research\bug-hunt-workflow-approaches.md` (20:12),
> `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt\.agents\work\bug-hunting-workflow\bug-hunting-workflow-findings.md` (20:33).
> A frase que manda nisto tudo: *"reported and fixed must never be presented as verified"*.

**Esta secção não é uma sugestão nem um estilo.** Quando o dono reporta um defeito, o trabalho É
BUG-HUNT, e os artefactos abaixo são exigidos — não porque um documento o diz, mas porque **quatro
portões na bateria recusam o contrário**. Um campo em falta é um passo vermelho, não uma nota de
rodapé.

### PASSO 0 — PROVAR QUE O PROCESSO É O DA ÁRVORE (novo, 2026-10-30)

```cmd
python _main/live-code-freshness-oracle.py --strict
```

`FRESH` → segue. `STALE` → **a primeira acção é reiniciar a app, não corrigir código**, e tudo o
que se disser sobre o sintoma fica em espera. `UNKNOWN` não é `FRESH`.

**Porque é que este passo existe, medido na pele dele.** Ele carregou Alt+C e reclamou: *"EU TO
APERTANDO ALT C E TA LIGANDO E DESLIGANDO A LEGENDA PORRA"*. O contrato novo já estava no disco; a
instância que ele carregava era de **01:12:39** e o log dela escrevia `HOTKEY_SINGLE` ×186 —
etiqueta com **zero** ocorrências no fonte. Quatro oráculos estavam verdes e tinham razão: julgam
**FICHEIROS**, e ele carrega num **PROCESSO**. Nenhum instrumento comparava os dois, e o custo desse
buraco foi um ciclo inteiro de diagnóstico a olhar para código que não estava a correr.

Duas provas, porque uma só não chega: **(A)** o shell regista `SHELL_CODE_ID sha256=…` no arranque e
o oráculo compara com o `code_identity()` calculado agora — exacto, mas só para processos que já
nasçam com a etiqueta; **(B)** o instante do `SHELL_STARTUP_STAGE` contra o `mtime` de cada ficheiro
de código — retroactiva, e é a que apanha a instância que já estava a correr. Os dois sentidos são
provados contra logs sintéticos em `--control` (5 casos, incluindo `UNKNOWN`).

### O laço (11 passos, comprimido; a ordem importa)

1. **Entrar em BUG-HUNT.** Nomear o cluster e o impacto. Nada de capacidades novas nem refactor
   largo: uma ferramenta só entra se **nomear o bug** que desbloqueia (`# BLOCKS:`) ou declarar
   `# NO-BUG:` com razão.
2. **Triar observações, não palpites.** Esperado vs observado, palavras do dono verbatim, data.
3. **Reproduzir** com relógio e log completo, e guardar a evidência **como texto num ficheiro**
   (`reproduced.source` + `reproduced.evidence`) — uma reprodução que só existe na conversa não conta.
4. **Uma hipótese + o que a refutaria** (`hypothesis` + `falsifier`). Sem falsificador escrito não é
   hipótese, é narrativa.
5. **Minimizar** (delta debugging): `minimal_repro`.
6. **Corrigir a CLASSE, não a instância** — e varrer os irmãos com a **mesma sonda** (`siblings[]`,
   cada um com `instance`/`probe`/`verdict`/`why`; `unproven` é permitido e é **impresso**).
7. **Regressão no estilo certo** (`regression.style` ∈ `example|property|stateful|differential|replay`).
8. **Provar o detector**: o braço negativo tem de derrubar **aquele** braço (`seam-coverage`), e o
   mutante tem de ser apanhado pela razão nomeada.
9. **Cobertura por invocador**: `invocadores provados / enumerados`; um invocador sem positivo **e**
   negativo bloqueia a entrega.
10. **Replay/medição** e depois **revisão independente**. Sem verificador ≠ autor, o estado é
    `fixed`, não `verified`.
11. **Cápsula de incidente** + `recurrence-watch` com instrumento **e** janela.

### Os quatro portões que o tornam obrigatório

| portão | o que recusa |
|---|---|
| `input-path` (10 braços / 10 mutantes) | um hook global vivo sem o painel precisar dele |
| `seam-coverage` (9 invocadores) | um invocador sem controlo positivo **e** negativo naquele braço |
| `bug-ledger` (9 mutantes) | `fixed` sem passo da bateria; `verified` sem verificador ≠ autor; hipótese sem falsificador; reprodução sem ambiente/revisão/sha; `fixed` sem irmãos; `unknown` sem próximo passo |
| `tooling-intent` (4 mutantes + controlo positivo) | ferramenta nova sem `# BLOCKS:`/`# NO-BUG:`; `BLOCKS` a apontar para bug fora do ledger; dívida sem declaração a **crescer** |

**Estado honesto hoje:** os dois bugs do ledger estão `fixed` e o portão imprime **FIXED, NOT
VERIFIED**; há **2 irmãos `unproven`** (janela layered da legenda; arranque do WebView2). Isto não é
uma falha a esconder — é o estado que a lei permite e que ninguém pode ler como fecho.

**A regra que fica:** *um portão sem intenção declarada é uma promessa; um estado sem verificador é
uma opinião.* Este repo passou a recusar as duas por máquina.
