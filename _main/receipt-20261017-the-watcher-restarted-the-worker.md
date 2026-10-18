O watcher reiniciava o worker por causa de um ficheiro que nao mudou.

O dono, 2026-10-17, furioso: "e tu que ta fazendo meu pc travar por 2 minutos
inteiros?" e depois "vai no disco e o watcher e entenda por que ele nao impediu
essa caga gigante. e arruma ELE. e faz ele funcionar".

A PROVA, E ESTA NO LOG DELE
---------------------------
    22:30:11.891  HOT_RELOAD_WORKER_RESTART files=1 after_idle_ms=35000
    22:30:11.901  WORKER_AUTOSTART=started reason=hot-reload
    22:35:25.683  HOT_RELOAD_WORKER_IDLE_APPLIED files=1
                  reason=no-caption-in-25000ms
                  code_is_stale=False
                  sha256_disk=582b860b3ffe61c4 sha256_at_spawn=582b860b3ffe61c4
                  cost=one-model-warm-up

OS DOIS DIGESTS SAO IGUAIS. O worker ja corria exactamente os bytes do disco. A
politica PERGUNTOU se o codigo estava velho -- `code_is_stale` -- recebeu `False` --
e reiniciou na mesma, pagando ~2 GB na GPU do dono por bytes que ja eram os dele.

Tres defeitos, e so um deles e o que matou a maquina
-----------------------------------------------------
1. A POLITICA (`WorkerReloadPolicy._fire`) imprimia `code_is_stale` em todas as
   suas linhas de log -- o que prova que o calculava -- e tratava-o como um facto
   a reportar, nunca como uma condicao a respeitar. Um digest que se imprime e nao
   se obedece nao e um digest; e decoracao. **E O DEFECTO QUE CUSTOU OS DOIS
   MINUTOS.**

2. A POLITICA tinha tres caminhos que aplicavam, e um deles era um TETO QUE
   FORCAVA o reinicio ao fim de 25 s sem fronteira -- ou seja, precisamente quando
   a maquina esta mais quieta. A maquina quieta e quando se pode estragar a
   maquina. A docstring dela dizia, com conviccao, que "a stale running worker is
   worse than one warm-up". Foi o julgamento de um agente anterior, e o dono
   acabei de o黑的. Nao ha tecto: ha um RELATORIO.

3. O WATCHER (`app/webview/hot_reload.py`) ouvia `FILE_NOTIFY_CHANGE_ALL`, que
   inclui `FILE_NOTIFY_CHANGE_ATTRIBUTES` e `..._CREATION`. Uma mudanca de
   ATRIBUTOS nao e uma mudanca de codigo: um antivirus, um indexador, um backup,
   um `os.utime` ou um `touch` levantam uma. E aceitava QUALQUER `.py` em
   `worker/` -- treze ficheiros, medidos --, quando so o que a ponte EXECUTA
   interessa.

O QUE FOI FEITO
---------------
  watcher: a mascara passou a NAME | LAST_WRITE | SIZE. Um ACL, uma analise e uma
    criacao ja nao sao codigo.
  watcher: aceita o conjunto explicito do que a ponte executa
    (`watched_worker_files()`), nao os treze `.py`. `SOTTO_WATCH_WORKER`
    sobrepoe para layouts、杨 nombrados fora do comum.
  politica: `code_is_stale=False` e AGORA A PRIMEIRA CONDICAO, e sai antes de
    qualquer temporizador. Nao ha nada a aplicar.
  politica: os tres ramos que aplicavam passaram a REPORTAR e a acabar ali. Ja nao
    existe uma unica chamada viva a `self.restart(` dentro de `_fire`.
  shell: `worker_restart_allowed()` nas DUAS portas, fechado por omissao. So
    `SOTTO_HOT_RELOAD_WORKER=1` abre, e a lista de "sim" e fechada.

ORACULO: _main/worker-restart-guard-oracle.py, 15 bracos GREEN
---------------------------------------------------------------
Cinco deles sao um teste AO VIVO da politica REAL -- `WorkerReloadPolicy` de facto,
com uma ponte que LEVANTA se lhe pedirem um reinicio, conduzida por todos os
caminhos que uma vez o fizeram:

  P uma legenda acabou de fechar, floor passado    (o caminho das 22:30)
  P nada em voo, maquina parada                   (o caminho das 22:35)
  P uma fronteira chega muito depois do tecto
  P nenhuma fronteira, muito depois do tecto
  P o worker nem sequer esta a capturar
  P os bytes em execucao JA Sao os do disco       (o caso das 22:35)

Todos: `reinicios=0`. E o sexto diz `skipped_not_stale=True`, que e o caso exacto
do log de las 22:35:25.

POR QUE O TESTE E DE PONTE FALSA E NAO AO VIVO
---------------------------------------------
Porque provar ao vivo exigiria um worker A CORRER, e um worker a correr sao
precisamente os ~2 GB que o guard existe para evitar. Essa prova so se comprava
com o estrago. A ponte de mentira da a mesma evidencia de graca, porque a
politica nunca toca no modelo: ela so DECIDIA pedir um.

TRES INSTRUMENTOS QUE ERRARAM, TODOS MEUS
-----------------------------------------
Vale a pena porque e o mesmo padrao de sempre:

  - Um braco contou o guard como "instrucao #3" de `_do_worker_restart` e deu
    RED contra codigo certo, porque ha uma docstring e duas linhas de comentario
    por cima. Contar LINHAS nao e a invariante; a invariante e o guard vir antes
    de `bridge.stop`, de largar a ponte e de `start_worker` -- as tres linhas que
    carregam 2 GB.
  - Um braco pediu `_apply` quando o metodo se chama `_fire`, nao encontrou nada,
    e reportou "0 chamadas" como um PASS. Um gate que nao distingue "nada ficou"
    de "olhei para nada" nao e um gate. Passou a ser RED.
  - Um braco procurou `endswith('.py')` no texto bruto e deu RED contra o ficheiro
    ja corrigido -- porque a frase que EXPLICA a correcao menciona
    `endswith('.py')`. Um braco que le a propria documentacao e um braco que
    documenta a sua propria falha.

E o selo do watcher: `python app/webview/hot_reload.py --selftest` -> rc=0, ainda
dispara em `sotto_worker.py` e em `panel.css`, e ignora o que nao e activo.