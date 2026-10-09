# FRICTION LEDGER

Uma fricção por passagem. Regra: **estado** = o que foi pedido · **fricção** = o que
travou · **lição** = o que muda na próxima vez. Sem_item, não se inventa.

---

## 2026-10-07 — `cron_restore` · 4 passagens · CRON-VERDICT.md aditivo

**P1 — contagem com fronteira que apara a própria linha**

- **Estado**: `SELECT COUNT(*) … WHERE created_at_ms > <2026-10-06T13:11:00.000Z>`
  devolveu **`rows_after_cutoff=1`**, lido como "houve 1 execução nova".
- **Fricção**: o dono perguntou exactamente `> 13:11:00Z`. A última linha tem
  `13:11:00.**022**Z` — 22 ms à direita da fronteira. A contagem devolve **a
  própria linha que já existia**, e o número parece uma prova de vida.
- **Lição**: **nunca boundary numa tabela temporal com o valor que se quer
  refutar.** Âncora no `MAX()` medido e pergunte `> MAX()`. Um "1" onde se
  esperava "0" é o formato exacto de um falso verde.

---

**P2 — prova sem controlo**

- **Estado**: P2 confirmou `MAX` inalterado e 0 linhas depois do máximo.
- **Fricção**: essa resposta é **trivialmente compatível** com *"o processo estava
  morto o tempo todo"*. Uma tabela parada não distingue "cron parado" de
  "máquina parada". Eu teria escrito "cron não restaurou" sem o ver.
- **Lição**: toda a afirmação negativa sobre um sistema vivo precisa de um
  **controlo positivo na mesma janela**. Aqui: contagem horária de `cron_runs` ao
  lado de `message_rows` / `sessions`. A hora de maior tráfego (3077 mensagens) com
  **zero** crons é o que fecha a pergunta.

---

**P3 — o "processo freshly started" testado uma vez só**

- **Estado**: o briefing diz *"vai correr no próximo arranque"*. Um arranque
  chega para um job de 30 h de atraso? **Não chega como evidência.**
- **Fricção**: um único arranque não distingue "hidratação não acontece" de
  "esta instância é a errada". Corre o risco de medir uma coincidência e generalizar.
- **Lição**: mede ** quantas vezes a hipótese foi testada**. Aqui: **18 horas
  distintas com sessão nova, 0 execuções**, mais `sched-7f2c94e` — job **nascido
  hoje**, armado para +1 min, `OVERDUE 5.4 h`. Um job recente não pode ter
  "dormido desde terça".

---

**P4 — número citado de uma coluna que não existe**

- **Estado**: §2 do `CRON-VERDICT.md` afirmava `prompt_bytes=8553` "da base de
  dados", e um ficheiro em disco com 8612. Apresentado como divergência de
  **conteúdo**.
- **Fricção**: `cron_definitions` **não tem** `prompt_bytes`. O número vinha de
  `length(prompt)` — que conta **CARACTERES**; 8612 é o ficheiro em **BYTES**.
  Os "59 bytes" são encoding UTF-8. Havia um bug de conteúdo fantasma.
- **Lição**: antes de chamar "divergência" a dois números, pergunta **o que cada
  um conta**. `length()` em SQLite é caracteres; `length(CAST(x AS BLOB))` é
  bytes. Duas colunas, um facto.

---

**P5 (transversal, do mesmo ficheiro) — store viva não é store a ler**

- **Estado**: o briefing afirmava *"não há loja de cron em `.minimax\v2`"*. Dois
  dias antes, o root escrevera isso em memória — com um grep atrás, sem abrir o
  ficheiro.
- **Fricção**: `sqlite/runtime-state.sqlite` existe, **3.36 GB**, com 1442
  execuções e 30 jobs. A memória era falsa e **dirigia acção** (reiniciar o
  runtime).
- **Lição**: **uma memória derivada não é uma medição.** Abre o ficheiro.