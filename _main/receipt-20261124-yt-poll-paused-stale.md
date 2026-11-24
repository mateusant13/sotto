# 2026-11-24 — o laço da legenda externa pedia 4 Hz a um vídeo PARADO (6,76 % → 1,69 % de um núcleo)

Ordem, verbatim (governor seat, DM `dm-5541e4bb6ed90343ed9c`): *"Land one measured perf fix
in your own tree with before/after from the same instrument."* Antes dela, o card de stutter
`dm-dab7ea056465d2fea48d` nomeou a minha árvore (`pythonw.exe(11608)` = `sotto_webview.py`).

## 1. O número de ANTES, lido no instrumento do produto

Do log vivo do dono, com ele a assistir a uma live na Twitch e uma aba do YouTube parada na
última linha de um vídeo terminado:

```
2026-11-24 14:56:19 EXTERNAL_CAPTIONS_READ_STATS n=391 mean_ms=16.9 p95_ms=110.0 max_ms=594.0 interval_s=0.10 step_s=0.25
```

`step_s=0.25` = **4 Hz**, e cada volta custa **16,9 ms** → `4 × 16,9 = 67,6 ms/s` = **6,76 % de
um núcleo, continuamente, para reler a MESMA linha**. O degrau existia (`IDLE_INTERVAL_S=0.25`)
mas juntava dois casos diferentes: "não há player nenhum" (tem de perguntar depressa, um player
pode aparecer) e "o player está PARADO" (a legenda não pode mudar). O próprio comment de
2026-11-05 já argumentava "0,45 s chega para ver o `play` voltar".

## 2. A cura — dois degraus novos, escolhidos pelo CONTEÚDO

`app/webview/sotto_webview.py`:

* `PAUSED_INTERVAL_S = 0.50` — pausado, 2 Hz. Medido: **3,38 %** de um núcleo.
* `STALE_CUE_S = 5.0` + `STALE_INTERVAL_S = 1.00` — pausado **e** a assinatura das cues
  (modo + até 4 textos) não muda há 5 s → 1 Hz. Medido: **1,69 %**.
* `poll_step(idle_for, paused, base, idle, slow=False, stale=False)`: o degrau da pausa vem
  PRIMEIRO (uma cue não muda com o vídeo parado); `stale` só refina esse degrau.
* o laço calcula a assinatura por volta (um tuplo de até 4 strings, **nenhuma** chamada ao
  Windows e nenhum ficheiro) e passa `stale=`; no instante em que a cue muda, volta ao base.

**O que NÃO muda:** um vídeo A TOCAR continua a 10 Hz (arm A2-ter), e "sem player" continua a
0,25 s (arm A2-quater). Nada aqui adivinha quando o vídeo volta — a assinatura é do texto.

## 3. Prova

```
python _main/paused-pace-oracle.py           -> 17/17 arms green   VERDICT: PASS
python _main/paused-pace-oracle.py --neg-arm -> 3 mutantes, cada um no seu braço
```

Mutantes (cada um derruba o braço que lhe pertence, senão o controlo é decorativo):
M1 pausa desarmada → A2/A2-bis RED; M2 escada da leitura lenta apagada → A4-bis RED;
M3 assinatura ignorada → A2-bis RED.

O oráculo passou a ler e a parsear o shell **uma vez por corrida**: antes, cada arm re-lia 1,5 MB
e o `--neg-arm` levou >120 s (medido nesta sessão). O custo de uma sonda é do instrumento.

## 4. O que está UNMEASURED, e como se mede

O **depois ao vivo** exige a shell a arrancar com o código novo, e o dono está a emitir: nenhum
restart por 4 % de núcleo. A linha que prova, na próxima abertura dele:

```
EXTERNAL_CAPTIONS_READ_STATS ... step_s=1.00
```

com `mean_ms` igual (a leitura não ficou mais cara) e a frequência a cair de 4 Hz para 1 Hz.

## 5. Teto de COMMIT (ordem 4 do DM) e recenseamento

* `python.exe(9364)` [sotto] = **4,68 GiB** de commit privado (censo do próprio watcher no
  `dm-dab7ea056465d2fea48d`) — abaixo do teto de 6,0 GiB, sem card.
* Medição desta lane por `psutil.memory_full_info().private`: os filhos `msedgewebview2`
  somam **0,32 GiB**; a shell e o worker **CANNOT-MEASURE** por esta pane (`AccessDenied` num
  processo de integridade `high`) — não se afirma zero, afirma-se não medido.
* Subagentes mortos no reboot: **nenhum** — o registo (`proc://`) só tem jobs de bash desta
  sessão, e nenhum `task` foi despachado por esta lane.

## 6. Custo declarado deste trabalho

Nenhum trabalho pesado: uma edição de função pura + um oráculo de 1,5 MB de AST. Threads: 1.
CPU: <2 % de um núcleo, alguns segundos. IO: 0 bytes escritos fora do repo. Um trabalho pesado
(a carga do modelo, para o card do stutter) foi declarado e medido à parte: 1 processo, 3
threads, RSS ≤2,2 GiB, leitura ≤1,7 GB/run, sob `watcher run --cpu 40 --single --io very-low`.
