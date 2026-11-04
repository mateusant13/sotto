"""SHEDDING POR CARGA -- que motor corre, decidido pela pressao da maquina.

ORDEM DO DONO, 2026-10-30:

    *"shedding por carga -- alta: desliga nemotron, so parakeet; muito alta:
      desliga parakeet tambem. AUDIO SEMPRE fica para processar depois"*

O QUE ISTO E'. Uma maquina degradada nao transcreve: ela ENGASGA. O dono mediu a
dele (I: 0,4 % livre, 722 processos) e a app compete com tudo o resto. A regra e'
desigual de proposito -- o nemotron (ao vivo, streaming, GPU/RAM) e' o caro e cai
PRIMEIRO; o parakeet (batch, leve em RAM) aguenta mais e cai depois; e o AUDIO
nunca e' a coisa que se larga.

TRES NIVEIS, e nenhum deles e' uma decisao sobre o audio:

    leve       tudo ligado (nemotron ao vivo + parakeet de fundo)
    alta       nemotron DESLIGADO, parakeet continua
    muito alta parakeet tambem DESLIGADO -- nada a transcodificar agora

PORQUE E' QUE ISTO VIVE NUM MODULO PROPRIO E NAO DENTRO DO SHELL. Porque a
decisao e' a parte que se pode medir sem abrir uma janela: o oraculo executa esta
classe com pressoes sinteticas e pergunta se ela cai e volta nos sitios certos. O
que o shell faz com o veredicto (parar o worker, deixar de arrancar o batch) e'
uma ACCAO e mede-se pelo log.

TRES PROPRIEDADES QUE CUSTAM CARO A APRENDER:

  1. **HISTERESE.** Um numero so' faz o sistema oscilar: em 88 % ele desliga o
     nemotron, o consumo desce, ele liga outra vez, o consumo sobe. Um motor que
     liga e desliga de 10 em 10 s e' pior do que um que nunca liga -- o dono ja'
     pagou este padrao no churn de hot-reload do Sotto. Por isso ha' DOIS
     limiares: entrar em "alta" num numero, sair noutro mais baixo.
  2. **N-DE-M.** Uma leitura so' nao e' uma carga: um pico de 200 ms (um build,
     um antivirus, uma copia) desligaria o motor a meio de uma frase. A descida
     de nivel exige `CONFIRM_SAMPLES` leituras das ultimas `WINDOW_SAMPLES`.
  3. **UM NOME E UMA ACCAO.** O nivel devolve NOMES (`nemotron`/`parakeet`), nao
     um booleano "ligado": quem age precisa de dizer no log QUAL dos dois parou.
"""
from __future__ import annotations

import inspect
import os
import threading
import time

#: Pressao de commit a partir da qual a maquina esta' "alta".
HIGH_PCT = 88.0

#: ... e a partir da qual esta' "muito alta". O dono mediu a maquina dele com a
#: pressao de commit em 92,5 % quando o gate central ficou RED; 94 deixa margem
#: para esse valor nao ser o unico regime em que o parakeet tambem cai.
VERY_HIGH_PCT = 94.0

#: A CPU do SISTEMA tambem e' carga, e o dono nomeou as duas coisas quando disse
#: *"nunca travar o PC do usuario ou stutter"*. A 90 % de CPU o Windows ja' esta'
#: a atrasar o rato e o compositor; a 98 % nao sobra nada para o modelo.
CPU_HIGH_PCT = 90.0
CPU_VERY_HIGH_PCT = 98.0

#: O mesmo tecto de "ja' passou" para a CPU, na descida (histerese).
CPU_RESUME_PCT = 70.0

#: Histerese: so' se VOLTA a um nivel mais leve abaixo disto. Os dois numeros tem
#: de estar separados por mais do que o ruido das leituras (medido nesta maquina:
#: +-0,4 % entre amostras seguidas no `performance-gate`).
RESUME_PCT = 80.0

#: Uma descida de nivel precisa de tantas leituras...
CONFIRM_SAMPLES = 3

#: ... dentro desta janela de amostras.
WINDOW_SAMPLES = 5

LEVELS = ('leve', 'alta', 'muito-alta')

#: O que cada nivel deixa correr. O audio NAO aparece aqui de proposito: nao ha'
#: nivel em que o audio se largue, e um campo `audio: False` seria a tentacao de o
#: acrescentar mais tarde.
ENGINES = {
    'leve': {'nemotron': True, 'parakeet': True},
    'alta': {'nemotron': False, 'parakeet': True},
    'muito-alta': {'nemotron': False, 'parakeet': False},
}


def level_for(commit_pct):
    """O nivel que uma LEITURA so' pede -- sem histerese, sem confirmacao.

    Existe separada de proposito: e' o unico pedaco que e' uma funcao pura do
    numero, e e' o que os limites do oraculo medem.
    """
    try:
        value = float(commit_pct)
    except (TypeError, ValueError):
        return 'leve'
    if value != value:  # NaN
        return 'leve'
    if value >= VERY_HIGH_PCT:
        return 'muito-alta'
    if value >= HIGH_PCT:
        return 'alta'
    return 'leve'


def level_for_cpu(cpu_pct):
    """O nivel que a CPU do SISTEMA pede. `None`/NaN = 'leve' (nao sei = nao desligo)."""
    try:
        value = float(cpu_pct)
    except (TypeError, ValueError):
        return 'leve'
    if value != value:  # NaN
        return 'leve'
    if value >= CPU_VERY_HIGH_PCT:
        return 'muito-alta'
    if value >= CPU_HIGH_PCT:
        return 'alta'
    return 'leve'


def level_for_load(commit_pct, cpu_pct=None):
    """O nivel de DUAS medidas: o pior dos dois. PURE.

    A maquina esta' carregada se qualquer das duas coisas estiver carregada, e o
    dono nomeou as duas: memoria (commit) e CPU. O maximo, e nao a media, porque
    uma media esconde exactamente o caso que trava o PC -- commit a 40 % e CPU a
    99 % e' a maquina a engasgar, e a media diria "leve".
    """
    by_commit = level_for(commit_pct)
    by_cpu = level_for_cpu(cpu_pct)
    return by_commit if LEVELS.index(by_commit) >= LEVELS.index(by_cpu) else by_cpu


def _reading_text(commit_pct, cpu_pct):
    """`commit=91.2% cpu=57.0%` -- os numeros que fizeram a decisao."""
    def _one(value):
        if value is None:
            return 'n/a'
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 'n/a'
        return 'n/a' if value != value else '%.1f%%' % value

    return 'commit=%s cpu=%s' % (_one(commit_pct), _one(cpu_pct))


class SystemCpu:
    """A CPU do sistema em %, sem `psutil` e sem abrir nada (2026-11-04).

    PORQUE E' QUE ISTO EXISTE AQUI E NAO NO SHELL. `observe(commit_pct,
    cpu_pct)` aceita CPU desde a ordem do dono de 2026-10-30, `level_for_load`
    junta as duas medidas, e o `LoadSheddingMonitor` chamava `observe(reading)`
    sem CPU nenhuma: a capacidade existia e era INALCANCAVEL -- a mesma classe
    de defeito que este repo ja' nomeia (capacidade que ninguem chama).

    `GetSystemTimes` e' a leitura do proprio Windows e nao precisa de
    dependencia nem de permissao: idle+kernel+user, como os contadores de
    sistema os dao. Devolve `None` na PRIMEIRA amostra, porque um percentual
    precisa de duas -- e `None` nao pede nada (ver `level_for_cpu`).
    """

    def __init__(self, reader=None):
        self._reader = reader or self._win_reader
        self._prev = None
        self.last = None

    @staticmethod
    def _win_reader():
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [('low', wintypes.DWORD), ('high', wintypes.DWORD)]

        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        if not ok:
            return None

        def ticks(ft):
            return (ft.high << 32) | ft.low

        return ticks(idle), ticks(kernel), ticks(user)

    def sample(self):
        """Devolve a CPU do sistema em % (0-100) ou `None` (primeira amostra)."""
        raw = self._reader()
        if raw is None:
            return None
        idle, kernel, user = raw
        # `kernel` JA' INCLUI `idle` nos contadores do Windows.
        total = kernel + user
        busy = total - idle
        prev = self._prev
        self._prev = (busy, total)
        if prev is None:
            return None
        d_busy = busy - prev[0]
        d_total = total - prev[1]
        if d_total <= 0 or d_busy < 0:
            return self.last
        self.last = round(100.0 * d_busy / d_total, 1)
        return self.last


class LoadShedding:
    """O estado: o nivel EM VIGOR, e porque e' que ele mudou.

    A ordem de severidade e' `LEVELS`; subir e' imediato (uma maquina sob pressao
    nao espera pela confirmacao de uma leitura que ja' esta' acima do limiar),
    descer precisa de `CONFIRM_SAMPLES` leituras abaixo de `RESUME_PCT`.
    """

    def __init__(self, level='leve', floor_s=0.0, clock=None):
        self.level = level if level in LEVELS else 'leve'
        self._recent = []
        self.last_reading = None
        self.last_cpu = None
        #: PISO entre DUAS DESCIDAS (o que recarrega modelo), em segundos. Zero
        #: (o omissao, e o que o worker usa) = o comportamento de sempre. Um
        #: valor > 0 e' a guarda da accao: subir continua a ser imediato (seguranca
        #: primeiro) e descer espera -- porque cada descida de `muito-alta`/`alta`
        #: para `leve` manda o worker recarregar 1,2 GB de modelo, e duas dessas em
        #: menos de 3 minutos e' o triturador que o `VramGuard` pagou.
        self.floor_s = max(0.0, float(floor_s or 0.0))
        self._clock = clock or time.monotonic
        self.last_descent_at = None
        self.held_by_floor = 0

    # -- a leitura -------------------------------------------------------
    def observe(self, commit_pct, cpu_pct=None):
        """Regista uma leitura e devolve (nivel_novo, mudou, razao).

        `mudou` existe para o chamador nao ter de comparar: a ACCAO (parar um
        motor) so' se executa quando o nivel MUDA, e um log a cada amostra
        afogaria o ficheiro.

        `cpu_pct` e' o segundo sinal (ver `level_for_load`) e a RAZAO leva os
        NUMEROS das duas medidas, porque o dono pediu o numero que decidiu:
        *"o numero que o disparou"*. Uma leitura ausente (`None`) nao pede nada.
        """
        self.last_reading = commit_pct
        self.last_cpu = cpu_pct
        wanted = level_for_load(commit_pct, cpu_pct)
        reading = _reading_text(commit_pct, cpu_pct)
        self._recent.append(wanted)
        if len(self._recent) > WINDOW_SAMPLES:
            self._recent.pop(0)

        # SUBIR: imediato, e sem passar por degraus -- uma maquina que salta de
        # 87 % para 96 % nao quer que o nemotron fique a correr enquanto o
        # parakeet "confirma". O nivel pedido agora e' mais severo do que o vigente.
        if LEVELS.index(wanted) > LEVELS.index(self.level):
            return self._set(wanted, 'subiu: %s >= limiar de %s' % (reading, wanted))

        # DESCER: UM DEGRAU DE CADA VEZ, e so' com confirmacao.
        #
        # UM DEGRAU, e nao o nivel pedido. Com a descida a saltar directo para o
        # nivel de uma leitura so', sair de "muito-alta" a 79 % punha o nemotron a
        # carregar 3,9 GB de modelo com a maquina AINDA a 79 % -- o degrau
        # intermédio ("so' parakeet") existe exactamente para essa zona. Medido no
        # proprio oraculo: 99 -> 79 saltava para "leve" e o parakeet nunca ficava
        # sozinho.
        if LEVELS.index(wanted) < LEVELS.index(self.level):
            try:
                calm = float(commit_pct) < RESUME_PCT
            except (TypeError, ValueError):
                calm = False
            try:
                calm_cpu = cpu_pct is None or float(cpu_pct) < CPU_RESUME_PCT
            except (TypeError, ValueError):
                calm_cpu = False
            if calm and calm_cpu and self._recent.count(wanted) >= min(CONFIRM_SAMPLES, len(self._recent)):
                one_down = LEVELS[LEVELS.index(self.level) - 1]
                return self._set(one_down, 'desceu um degrau: %s por %d amostras (calmo abaixo de '
                                 'commit<%.0f%% e cpu<%.0f%%)'
                                 % (reading, CONFIRM_SAMPLES, RESUME_PCT, CPU_RESUME_PCT))
            return (self.level, False, 'segurado em %s: %s ainda nao confirmou a descida'
                    % (self.level, reading))

        return (self.level, False, '')

    def _set(self, level, why):
        """Aplica o nivel. O PISO so' trava a DESCIDA (ver `floor_s`)."""
        if LEVELS.index(level) < LEVELS.index(self.level) and self.floor_s > 0.0:
            last = self.last_descent_at
            if last is not None:
                elapsed = self._clock() - last
                if elapsed < self.floor_s:
                    self.held_by_floor += 1
                    return (self.level, False,
                            'segurado pelo piso de %.0f s: %s (faltam %.0f s)'
                            % (self.floor_s, why, self.floor_s - elapsed))
            self.last_descent_at = self._clock()
        changed = level != self.level
        self.level = level
        return (self.level, changed, why)

    # -- o que corre -----------------------------------------------------
    def engines(self):
        """`{'nemotron': bool, 'parakeet': bool}` para o nivel em vigor."""
        return dict(ENGINES[self.level])

    def stopped(self):
        """Os motores que este nivel MANDA parar -- para o log dizer o nome."""
        live = ENGINES[self.level]
        return [name for name in ('nemotron', 'parakeet') if not live[name]]

    def as_dict(self):
        return {'level': self.level, 'commit_pct': self.last_reading,
                'cpu_pct': self.last_cpu, 'floor_s': self.floor_s,
                'held_by_floor': self.held_by_floor,
                'engines': self.engines(), 'stopped': self.stopped()}


# ── A MEDICAO: a carga da MAQUINA, duas leituras, uma por amostra ────────────
#: De quanto em quanto tempo o worker volta a medir a maquina. E' 5 s porque o
#: nivel NAO precisa de mais: a ordem do dono e' sobre um regime (minutos), e um
#: `psutil.cpu_percent` por bloco de 100 ms seria 50 amostras/s de trabalho de
#: CPU para decidir que nao ha' nada a decidir.
SAMPLE_INTERVAL_S = 5.0


class LoadProbe:
    """Pressao de commit e CPU do sistema, medidas e NAO inventadas.

    PORQUE E' QUE ISTO EXISTE NO WORKER. O nivel chegava de fora, no
    `panel-visibility.json` que a shell escreve (a shell mede a pressao de commit
    com `GlobalMemoryStatusEx`, so' o commit), e o worker obedecia sem medir
    nada. A ordem do dono (2026-11-01) pede as duas coisas e pede o numero:
    *"a decisao do shed le a carga MEDIDA (commit %, CPU) e regista o numero que
    a disparou"*. Um ficheiro que a shell nao escreveu (arranque, shell morta,
    `SOTTO_LOAD_SHED=0`) deixava o worker sem sinal nenhum.

    TRES REGRAS:

      1. **UMA AMOSTRA POR `min_interval_s`.** `sample()` e' chamada a cada bloco
         de 100 ms e devolve a MESMA leitura dentro da janela (`fresh=False`), para
         que o custo no caminho do audio seja uma comparacao de dois floats. So'
         uma leitura NOVA alimenta o `LoadShedding`; repetir a mesma amostra cinco
         vezes contaria como cinco confirmacoes.
      2. **NUNCA BLOQUEIA.** `psutil.cpu_percent(interval=None)` mede desde a
         chamada anterior e volta ja'. A primeira chamada de todas devolve 0.0 --
         que NAO e' uma medicao -- por isso a CPU e' `None` ate' haver duas.
      3. **FALHA = "NAO SEI".** Qualquer medida que rebente ou nao exista devolve
         `None`, e `level_for(None)` e' `leve`: uma medicao falhada nunca desliga
         um motor (a mesma direccao do `PanelVisibilityReader`).
    """

    def __init__(self, min_interval_s=SAMPLE_INTERVAL_S, clock=None,
                 commit_fn=None, cpu_fn=None):
        self.min_interval_s = max(0.0, float(min_interval_s))
        self._clock = clock or time.monotonic
        self._commit_fn = commit_fn
        self._cpu_fn = cpu_fn
        self._last_at = None
        self._last = (None, None)
        self._cpu_primed = False
        self.samples = 0
        self.fresh = 0

    def reread(self):
        """Uma leitura NOVA agora, fora da janela de `min_interval_s`.

        PORQUE E' QUE ISTO NAO E' `sample()`. A janela existe para o caminho do
        audio nao medir a maquina 10x/s; uma RETOMA que reutilizasse a ultima
        amostra decidiria com o numero que autorizou a descida -- exactamente o
        numero que pode ja' ter subido. Esta leitura abre a janela de proposito:
        e' uma so', imediatamente antes de carregar um modelo.
        """
        self._last_at = None
        return self.sample()

    def sample(self, now=None):
        """-> `(commit_pct, cpu_pct, fresh)`. `fresh` diz se e' uma leitura nova."""
        now = self._clock() if now is None else float(now)
        if self._last_at is not None and (now - self._last_at) < self.min_interval_s:
            return self._last[0], self._last[1], False
        self._last_at = now
        commit = self._safe(self._commit_fn, _commit_pct_windows)
        cpu = self._safe(self._cpu_fn, self._cpu_pct_system)
        self._last = (commit, cpu)
        self.samples += 1
        self.fresh += 1
        return commit, cpu, True

    def _safe(self, given, default):
        fn = given if given is not None else default
        try:
            return fn()
        except Exception:  # noqa: BLE001 -- uma medicao falhada nao e' pressao
            return None

    def _cpu_pct_system(self):
        """CPU do sistema (%) desde a chamada anterior, ou None na primeira."""
        import psutil

        value = float(psutil.cpu_percent(interval=None))
        if not self._cpu_primed:
            self._cpu_primed = True
            return None
        return value


def _commit_pct_windows():
    """A pressao de COMMIT do Windows -- A MESMA medida que a shell publica.

    `GlobalMemoryStatusEx` e nao `virtual_memory().percent`: o Windows reserva
    memoria em page file (commit charge) e e' essa a conta que rebenta primeiro
    quando oito modelos e trinta browsers estao abertos. A shell
    (`sotto_webview.py:commit_pct`) le' este mesmo campo; ler o mesmo campo aqui e'
    o que faz as duas medidas serem comparaveis em vez de duas verdades.

    Fora do Windows (ou se a chamada falhar) devolve None = "nao sei".
    """
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total = float(status.ullTotalPageFile or 0)
        if total <= 0:
            return None
        used = total - float(status.ullAvailPageFile or 0)
        return max(0.0, min(100.0, used / total * 100.0))
    except Exception:  # noqa: BLE001 -- nao-Windows, ou a API nao respondeu
        return None


_PROBE = None


def sample_load():
    """Uma leitura da maquina, para quem nao quer manter um `LoadProbe`.

    O singleton e' de proposito: a CPU so' existe a partir da SEGUNDA chamada, e
    um `LoadProbe` novo por chamada devolveria sempre "nao sei".
    """
    global _PROBE
    if _PROBE is None:
        _PROBE = LoadProbe()
    commit, cpu, _fresh = _PROBE.sample()
    return {'commit_pct': commit, 'cpu_pct': cpu}

# ── A RETOMA: a carga liberta, e o motor estacionado carrega SOZINHO ─────────
#
# ORDEM DO DONO (2026-11-04), verbatim: *"modelos carregados dependendo da carga
# do sistema ou nao. quando carga liberar, carrega sozinho (NUNCA TRAVAR O PC DO
# USUARIO OU STUTTER) e processa qualquer audio nao processado, com o parakeet"*.
#
# A METADE QUE FALTAVA. ESTACIONAR ja' existe (`ReduxHiddenSwitch.tick` larga o
# motor em `muito-alta`) e o audio que espera nunca se perde
# (`live_queue.PendingAudio`). RETOMAR nao existia em nenhum sitio: o lote so' e'
# pedido em `mode == "batch"` (`maybe_kick`) e em `shed` o proprio `tick` diz
# "sem maybe_kick: acordar o modelo e' o custo que este nivel existe para
# cortar". Logo, quando o nivel VOLTA, o audio acumulado so' saia por acaso --
# se ainda houvesse `batch_interval_s` de audio e o modo voltasse a `batch`. Um
# backlog de 20 s que chegasse a `leve` ficava em RAM/disco ate' ao `stop()` do
# processo, ou seja o dono recebia a transcricao quando FECHASSE a app. Ele
# pediu "quando a carga liberar, carrega sozinho".
#
# AS DUAS GUARDAS DA RETOMA (a segunda e' o orcamento de stutter):
#
#   1. HISTERESE. A retoma le' o NIVEL (que so' desce abaixo de `RESUME_PCT` e
#      `CPU_RESUME_PCT` com `CONFIRM_SAMPLES` leituras), nunca a leitura crua.
#      Uma amostra calma isolada nao carrega 615 MB de modelo.
#   2. RE-LEITURA. Imediatamente ANTES de carregar, a maquina e' lida OUTRA VEZ
#      (`LoadProbe.reread`). Se ela subiu, o motor FICA estacionado e a recusa e'
#      dita no log. E' a diferenca entre "a carga liberou" e "a carga liberou
#      enquanto eu decidia" -- a segunda poria 615 MB de pesos num PC que voltou
#      aos 95 %, que e' exactamente o stutter que a ordem proibe.

#: De quanto em quanto tempo uma retoma que NAO arrancou (lote anterior ainda a
#: correr, audio abaixo do piso) volta a tentar. Nao e' 0 (o laco corre a 10 Hz e
#: cada tentativa le' a maquina) e nao e' `SAMPLE_INTERVAL_S` (5 s) por acaso:
#: uma tentativa falhada porque o lote anterior ainda moe nao precisa de mais
#: leituras do que a amostragem normal.
RESUME_RETRY_S = 5.0


def resume_calm(commit_pct, cpu_pct=None):
    """PURE: esta leitura autoriza CARREGAR um motor? `(bool, why)`.

    Abaixo da banda nas DUAS medidas -- `commit < RESUME_PCT` e
    `cpu < CPU_RESUME_PCT` --, ou seja exactamente a banda de histerese que faz
    a descida de nivel. Uma CPU ausente (`None`, psutil/`GetSystemTimes` fora)
    nao inventa carga, a mesma direccao de `level_for_cpu`.

    Uma leitura de COMMIT ausente (`None`/NaN) NAO autoriza. E' o oposto de
    `level_for`, e de proposito: ali "nao sei" desliga um motor (seguro); aqui
    "nao sei" CARREGA 615 MB. Quando nao ha' instrumento nenhum, quem decide e'
    o nivel (`ResumeGate` com `probe=None`) -- nao uma leitura que nao existe.
    """
    try:
        commit = float(commit_pct)
    except (TypeError, ValueError):
        return False, 'sem-leitura-de-commit'
    if commit != commit:  # NaN
        return False, 'sem-leitura-de-commit'
    if commit >= RESUME_PCT:
        return False, 'commit>=%.0f%%' % RESUME_PCT
    if cpu_pct is not None:
        try:
            cpu = float(cpu_pct)
        except (TypeError, ValueError):
            return True, 'commit<%.0f%% (cpu ilegivel)' % RESUME_PCT
        if cpu == cpu and cpu >= CPU_RESUME_PCT:
            return False, 'cpu>=%.0f%%' % CPU_RESUME_PCT
    return True, 'calmo'


class ResumeGate:
    """A BORDA da retoma: estacionado -> calmo = carrega SOZINHO, uma vez.

    `tick(level)` e' chamado no laco do audio (10 Hz) e devolve um dicionario.
    Enquanto nao ha' BORDA nao le' a maquina: duas comparacoes de strings, e o
    mesmo custo que o resto do caminho ja' paga. Na borda -- o nivel de carga
    DEIXOU de estar em `PARK_LEVELS` -- ele relê a maquina (`probe.reread`) e so'
    autoriza (`resume=True`) se ela estiver abaixo da banda.

    UMA VEZ POR BORDA. `pending` e' consumido na primeira autorizacao; um lote
    que nao arrancou (in-flight, audio abaixo do piso) volta a tentar por
    `retry()`, com piso de `RESUME_RETRY_S`, e nao por si mesmo. Sem isso o
    caminho de 10 Hz carregaria o modelo outra vez a cada bloco.

    `probe=None` = sem instrumento: o NIVEL decide sozinho (o comportamento de
    antes de haver medicao local), e o log diz isso (`why=o-nivel-decide`).
    """

    def __init__(self, probe=None, log_fn=None, clock=None,
                 retry_s=RESUME_RETRY_S):
        self.probe = probe
        self.log = log_fn or (lambda _m: None)
        self._clock = clock or time.monotonic
        self.retry_s = max(0.0, float(retry_s))
        self.level = None
        self.parked = False
        self.pending = False
        self.resumes = 0
        self.holds = 0
        self.retries = 0
        self.last_attempt_at = None
        self.last = None

    # -- a decisao ---------------------------------------------------------
    def tick(self, level, now=None):
        """-> dict(level, parked, resume, commit_pct, cpu_pct, why, ...)."""
        now = self._clock() if now is None else float(now)
        self.level = level
        was_parked = self.parked
        self.parked = level in PARK_LEVELS
        if self.parked:
            # ESTACIONADO CANCELA UMA TENTATIVA PENDENTE: a maquina voltou a
            # pedir os motores, e carregar um modelo AGORA seria contra a
            # medicao que a acabou de estacionar.
            self.pending = False
            return self._out(False, 'estacionado')
        if was_parked:
            self.pending = True
        if not self.pending:
            return self._out(False, 'sem-borda')
        if (self.last_attempt_at is not None
                and (now - self.last_attempt_at) < self.retry_s):
            return self._out(False, 'a-esperar-a-tentativa-anterior')
        self.last_attempt_at = now
        calm, commit, cpu, why = self._reread()
        if not calm:
            self.pending = False
            self.holds += 1
            self.log('LOAD_RESUME_HELD level=%s %s why=%s — a carga subiu entre a '
                     'descida e a carga do motor; o motor FICA estacionado e o audio '
                     'continua a esperar'
                     % (level, _reading_text(commit, cpu), why))
            return self._out(False, why, commit, cpu)
        self.pending = False
        self.resumes += 1
        return self._out(True, why, commit, cpu)

    def retry(self):
        """A retoma foi autorizada mas o lote nao arrancou: volta a tentar depois."""
        self.retries += 1
        self.pending = True

    def _reread(self):
        """`(calm, commit, cpu, why)` -- a maquina AGORA, nao a da decisao."""
        if self.probe is None:
            return True, None, None, 'o-nivel-decide'
        try:
            reader = getattr(self.probe, 'reread', None)
            reading = reader() if callable(reader) else self.probe.sample()
        except Exception as exc:                                 # noqa: BLE001
            return False, None, None, 'leitura-falhou: %r' % (exc,)
        try:
            commit, cpu = reading[0], reading[1]
        except (TypeError, IndexError, KeyError):
            return False, None, None, 'leitura-ilegivel'
        calm, why = resume_calm(commit, cpu)
        return calm, commit, cpu, why

    def _out(self, resume, why, commit=None, cpu=None):
        out = {'level': self.level, 'parked': self.parked,
               'resume': bool(resume), 'commit_pct': commit, 'cpu_pct': cpu,
               'why': why, 'resumes': self.resumes, 'holds': self.holds,
               'retries': self.retries}
        self.last = out
        return out

# ── A ACCAO: o nivel decide o MODO do worker, e nao a vida do processo ───────
#
# ORDEM DO DONO (2026-11-03), verbatim: *"os modelos entram e saem conforme a
# carga do sistema, e o audio nao processado e' processado sozinho quando a carga
# libera -- SEM NUNCA TRAVAR A MAQUINA DO DONO"*.
#
# O LEVER JA' EXISTE, E NAO E' MATAR O PROCESSO. Medido em 2026-11-03 (assento
# principal): o audio so' existe DENTRO do worker -- quem abre o endpoint WASAPI
# e' o `worker/sotto_worker.py`; a shell nao captura nada. Logo matar o worker
# para libertar a VRAM para a captura no intervalo, e o audio do dono perde-se --
# exactamente o contrario da ordem. O que existe, e ja' esta' provado pelo canal
# `shed` (arms 6-10 deste oraculo), e' o interruptor do proprio worker
# (`ReduxHiddenSwitch.tick`):
#
#   `leve`        -> streaming (nemotron ao vivo)      : os dois modelos em VRAM;
#   `alta`        -> batch    (nemotron largado)        : so' o parakeet;
#   `muito-alta`  -> shed     (os dois largados)        : nenhum modelo, e o audio
#                                                         continua a ser capturado
#                                                         e acumulado.
#
# Nos tres estados A CAPTURA CONTINUA. Por isso a accao desta lane e' uma so':
# ESCREVER O NIVEL no ficheiro que o worker ja' poll (`_main/panel-visibility.json`,
# campo `shed`), com o numero que o disparou. O `PanelVisibilityWriter` faz a
# escrita atomica; o worker muda de modo sozinho; o audio que nao foi transcrito
# fica no spool dele e na fila em disco (`batch_queue.py`), que o executor drena
# quando a carga liberta.
#
# AS TRES GUARDAS, cada uma a fechar um modo de falha medido:
#
#   1. PISO de `ACTION_FLOOR_S` (180 s) entre duas DESCIDAS -- cada descida manda
#      recarregar 1,2 GB de modelo (medido: `BRIDGE_LOAD_MS ms=4531/7672`, 4-7 s
#      de carga), e duas dessas em minutos e' o triturador do `VramGuard`. VIVE NO
#      `LoadShedding` (`floor_s`), para o nivel que o ficheiro diz e o nivel que a
#      decisao tomou serem O MESMO numero -- duas verdades seriam um bug a' espera.
#   2. HISTERESE: a accao le' o NIVEL (que desce um degrau de cada vez, so' com
#      `CONFIRM_SAMPLES` abaixo de `RESUME_PCT`), nunca a leitura crua.
#   3. SUSTENTACAO (`ACTION_SAMPLES` leituras no mesmo nivel) antes de AGIR; subir
#      e' imediato (seguranca), descer e' que espera.
#
# A ACCAO E' ARMADA POR OMISSAO (`ACTION_ARMED_DEFAULT`); `SOTTO_LOAD_SHED_ACT=0`
# desarma-a (mantendo a medicao e o `shed`, como hoje) para as corridas de
# medicao. A env e' lida AQUI e nao no shell: a shell chama `open_action()`.

#: A env que arma/desarma a ACCAO. `SOTTO_LOAD_SHED=0` desliga a MEDICAO (no
#: shell); esta desliga so' a accao -- o nivel continua a ser publicado.
ACTION_ENV = 'SOTTO_LOAD_SHED_ACT'

#: ARMADA POR OMISSAO. E' a ordem do dono de 2026-11-03; o desarme existe para
#: as corridas de medicao, nao para o dia a dia.
ACTION_ARMED_DEFAULT = True

#: PISO entre duas DESCIDAS de nivel (o que recarrega modelo).
ACTION_FLOOR_S = 180.0

#: Leituras SUSTIDAS no mesmo nivel antes de agir.
ACTION_SAMPLES = 3

#: Os niveis em que a maquina esta' carregada (o worker larga modelos).
PARK_LEVELS = ('alta', 'muito-alta')

#: Uma recusa/accao que nao aconteceu escreve no log no maximo uma vez por isto.
SKIP_LOG_INTERVAL_S = 60.0

#: DWELL MINIMO entre duas PUBLICACOES, nas DUAS direccoes.
#:
#: Medido na app do dono (`_main/webview-run.log`, 2026-11-03): QUATRO niveis
#: publicados em ~15 s -- `alta` as 06:0x, `leve` tres amostras depois, `alta`
#: outra vez -- e cada par manda o worker largar e recarregar o nemotron (1,2 GB
#: de pico). Num PC de 722 processos cuja CPU vive entre 88 % e 95 %, "subir e'
#: imediato por seguranca" transforma seguranca em dano: o que o dono ve e'
#: *"o modelo loading ta toda hora saind out de load"* e a legenda ao vivo a
#: morrer. 60 s e' a ordem de grandeza do proprio regime (minutos), nao do
#: ruido das amostras (segundos).
MIN_DWELL_S = 60.0


def action_armed(value=None):
    """A accao esta' armada? `SOTTO_LOAD_SHED_ACT=0` (ou `off`/`false`) desarma.

    `None`/ausente = armada (`ACTION_ARMED_DEFAULT`). Um valor que nao se
    reconhece NAO desarma: uma variavel mal escrita nao pode desligar em silencio
    a unica accao que liberta a maquina -- a mesma direccao do `shed` que falha
    FECHADO para `leve`.
    """
    if value is None:
        value = os.environ.get(ACTION_ENV)
    if value is None:
        return bool(ACTION_ARMED_DEFAULT)
    return str(value).strip().lower() not in ('0', 'off', 'false', 'no', 'nao', 'não')


def _takes_one_arg(fn):
    """O escritor injectado aceita o nivel? Sem funcao, nao ha' o que medir."""
    if fn is None:
        return False
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):                              # noqa: BLE001
        return False
    positional = [p for p in params
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    return bool(positional)


class PublishedView:
    """A unica coisa que o shell pode ler: o nivel que o FICHEIRO diz.

    `SottoShell.shedding_level()` le' `monitor.state.level`, e `monitor.state`
    tem de continuar a ser este objecto -- mas o nivel PUBLICADO nao e' sempre o
    nivel DECIDIDO (com o ao vivo ligado o unico valor publicavel e' `leve`).
    A decisao fica toda no `LoadShedding` real; aqui so' mora a diferenca, para
    duas verdades nunca coexistirem num ficheiro que o worker obedece.
    """

    def __init__(self, real):
        self.real = real
        self._published = real.level

    def set_published(self, level):
        self._published = level
        return self._published

    @property
    def level(self):
        return self._published or self.real.level

    def __getattr__(self, name):
        return getattr(self.real, name)


class LoadAction:
    """A accao do nivel: publicar o modo com piso, histerese e sustentacao.

    PURE o suficiente para ser medido: `probe`, `clock` e `publish` sao
    injectados, e `tick()` devolve -- e o log escreve -- o MESMO dicionario.
    """

    def __init__(self, state=None, publish=None, log_fn=None, probe=None,
                 clock=None, armed=None, samples=ACTION_SAMPLES,
                 live_fn=None, view=None, dwell_s=MIN_DWELL_S):
        self.state = state if state is not None else LoadShedding()
        #: O MOTOR AO VIVO E' DO GESTO DO DONO (`LIVE_ENABLED`), NAO DESTE LACO.
        #: Esta accao decide o que o FUNDO pode correr; nunca larga o nemotron.
        #: `live_fn` devolve True/False; sem fonte, True -- o lado seguro e'
        #: nunca desligar o produto por nao o saber ler.
        self.live_fn = live_fn
        #: A VISTA que o shell le' (`shedding_level()` -> `state.level`). O
        #: `shade` publicado vive nela; a decisao continua no estado real.
        self.view = view
        self.dwell_s = float(dwell_s)
        self.publish_fn = publish
        #: O escritor do shell (`monitor._publish`) nao aceita argumentos; um
        #: escritor de medicao pode aceitar o nivel (para o oraculo saber o que
        #: FOI publicado, e nao o valor que o ficheiro tinha antes).
        self._publish_takes_level = _takes_one_arg(publish)
        self.log = log_fn or (lambda _m: None)
        self.probe = probe if probe is not None else LoadProbe()
        self._clock = clock or time.monotonic
        self.armed = action_armed() if armed is None else bool(armed)
        self.samples = max(1, int(samples))
        self.published = self.state.level
        self.publications = 0
        self.publish_failures = 0
        self.held = 0
        self.last_publish_at = None
        self._high = 0
        self._calm = 0
        #: Leitura SEGUIDAS no nivel em vigor -- a sustentacao que autoriza uma
        #: descida publicada (para `leve` sao as leituras calmas).
        self._stable = 0
        self._last_level = self.state.level
        self._skip_log_at = None
        if self.view is not None:
            self.view.set_published(self.published)

    # -- a leitura --------------------------------------------------------
    def tick(self, now=None):
        """Uma volta: le', decide, e publica quando o NIVEL muda."""
        now = self._clock() if now is None else float(now)
        try:
            commit, cpu, fresh = self.probe.sample()
        except Exception:                                        # noqa: BLE001
            commit, cpu, fresh = None, None, False
        level = self.state.level
        why = ''
        action = 'none'
        if fresh:
            level, changed, why = self.state.observe(commit, cpu)
            self._count(level)
            if changed:
                self.log('LOAD_ACTION_LEVEL level=%s commit_pct=%s cpu_pct=%s why=%s'
                         % (level,
                            'n/a' if commit is None else '%.1f' % float(commit),
                            'n/a' if cpu is None else '%.1f' % float(cpu), why))
            # A PUBLICACAO E' SOBRE A DISTANCIA ENTRE O NIVEL E O QUE O FICHEIRO
            # DIZ, e nao sobre "mudou nesta amostra": o estado pode segurar-se no
            # alto (piso) durante amostras e depois cair, e o ficheiro tem de
            # seguir no instante em que a condicao passa -- sem esperar por outra
            # mudanca de nivel que ja' nao vem.
            target = self.target()
            if not self.armed:
                if changed:
                    # Desarmada: o nivel segue para o ficheiro como sempre (e' a
                    # medicao, e o worker obedece-a); a accao nao o forca.
                    action = self._publish(target, now, why, forced=False)
            elif target != self.published:
                since = (None if self.last_publish_at is None
                         else now - self.last_publish_at)
                clamped = target == 'leve' and level != 'leve'
                if clamped:
                    # O GESTO DO DONO GANHOU: ele ligou o ao vivo com a maquina
                    # carregada. Devolver o `leve` ao ficheiro e' DESLIGAR A
                    # POLITICA, nao carregar modelo -- e' imediato, sem dwell.
                    action = self._publish(target, now, why, forced=True)
                elif since is not None and since < self.dwell_s:
                    self.held += 1
                    self._skip_log('LOAD_ACTION_HELD level=%s published=%s'
                                   ' reason=dwell since=%.0fs dwell=%.0fs'
                                   % (target, self.published, since,
                                      self.dwell_s), now)
                elif (LEVELS.index(target) > LEVELS.index(self.published)
                      and target == 'muito-alta'):
                    # SO' `muito-alta` sobe sem esperar: e' a maquina a sufocar.
                    action = self._publish(target, now, why, forced=True)
                elif self._stable >= self.samples:
                    # SUBIR para `alta` OU DESCER: as MESMAS amostras sustentadas
                    # (o piso das descidas vive no estado, `floor_s`).
                    action = self._publish(target, now, why, forced=True)
                else:
                    self.held += 1
                    self._skip_log('LOAD_ACTION_HELD level=%s published=%s'
                                   ' reason=sustentacao stable=%d/%d'
                                   % (target, self.published, self._stable,
                                      self.samples), now)
            elif target == 'leve' and level in PARK_LEVELS:
                # A DECISAO DIZ "CARREGADO" E O FICHEIRO DIZ `leve`: e' o gesto
                # do dono a ganhar. Fica escrito, uma vez por minuto, para o log
                # nao parecer que a maquina esta' calma quando nao esta'.
                self._skip_log('LOAD_ACTION_LIVE_HELD level=%s published=leve'
                               ' decision=%s reason=o motor ao vivo e o do GESTO'
                               ' -- o FUNDO e que cede'
                               % (level, level), now)
        return self.as_dict(action=action, why=why, now=now)

    def live_on(self):
        """O motor AO VIVO esta' ligado pelo dono? Sem fonte, True."""
        if self.live_fn is None:
            return True
        try:
            return bool(self.live_fn())
        except Exception:                                        # noqa: BLE001
            return True

    def target(self):
        """O nivel que o FICHEIRO passa a dizer -- o do FUNDO, nao o do painel.

        Com o ao vivo ligado o unico valor publicavel e' `leve`: `alta` quer
        dizer "o worker larga o nemotron" (medido, `worker/sotto_worker.py`:
        `mode == 'batch'` salta o decode), e isso e' decisao do GESTO do dono e
        nao de um limiar. O que cede e' o fundo: o executor da fila le' o nivel
        da DECISAO (`sample_load`), nao este ficheiro.
        """
        level = self.state.level
        return 'leve' if (self.live_on() and level in PARK_LEVELS) else level

    def _count(self, level):
        """Conta leituras SUSTIDAS: `_stable` = quantas seguidas no MESMO nivel.

        E' a sustentacao que autoriza uma DESCIDA publicada. Subir nao a consulta
        (seguranca primeiro): uma maquina que salta para 96 % nao espera tres
        amostras para o worker largar os modelos.
        """
        if level == self._last_level:
            self._stable += 1
        else:
            self._stable = 1
            self._last_level = level
        if level in PARK_LEVELS:
            self._high += 1
            self._calm = 0
        else:
            self._high = 0
            self._calm += 1

    def _skip_log(self, message, now):
        last = self._skip_log_at
        if last is not None and (now - last) < SKIP_LOG_INTERVAL_S:
            return
        self._skip_log_at = now
        self.log(message)

    # -- a accao ----------------------------------------------------------
    def _publish(self, level, now, why, forced=True):
        """Escreve o nivel no ficheiro que o worker poll. Nunca levanta."""
        done = False
        try:
            if self.publish_fn is None:
                done = False
            elif self._publish_takes_level:
                done = bool(self.publish_fn(level))
            else:
                done = bool(self.publish_fn())
        except Exception as exc:                                 # noqa: BLE001
            self.publish_failures += 1
            self.log('LOAD_ACTION_PUBLISH_FAILED level=%s error=%r' % (level, exc))
            return 'failed'
        if not done:
            self.publish_failures += 1
            self._skip_log('LOAD_ACTION_PUBLISH_SKIPPED level=%s'
                           ' reason=escritor-indisponivel' % level, now)
            return 'skipped'
        self.published = level
        self.publications += 1
        self.last_publish_at = now
        if self.view is not None:
            self.view.set_published(level)
        order = 'imediatamente' if forced else 'medicao'
        live = 'nemotron-por-gesto' if self.live_on() else 'por-limiar'
        engines = self.state.engines()
        self.log('LOAD_ACTION_PUBLISHED level=%s decision=%s engines=%s'
                 ' stopped=%s live=%s why=%s (%s) -- o worker muda de modo, a'
                 ' captura CONTINUA'
                 % (level, self.state.level,
                    ','.join(k for k, v in engines.items() if v) or 'nenhum',
                    ','.join(self.state.stopped()) or 'nenhum', live, why, order))
        return 'published'

    # -- o que se le' -----------------------------------------------------
    def as_dict(self, action='none', why='', now=None):
        now = self._clock() if now is None else now
        since = None if self.last_publish_at is None else round(
            now - self.last_publish_at, 1)
        return {
            'level': self.state.level,
            'published': self.published,
            'armed': self.armed,
            'action': action,
            'why': why,
            'publications': self.publications,
            'publish_failures': self.publish_failures,
            'held': self.held,
            'since_publish_s': since,
            'high_samples': self._high,
            'calm_samples': self._calm,
            'stable_samples': self._stable,
            'floor_s': self.state.floor_s,
            'samples_required': self.samples,
            'dwell_s': self.dwell_s,
            'target': self.target(),
            'live': self.live_on(),
            'engines': self.state.engines(),
            'worker_channel': (os.environ.get('SOTTO_REDUX_WHEN_HIDDEN')
                               if self.armed else None),
        }


class LoadGuard:
    """A accao a correr: um thread que chama `LoadAction.tick()` e a fila.

    E' o objecto UNICO que a shell constroi (`open_action`); nao tem logica de
    decisao -- esta' no `LoadAction` -- nem de fila -- esta' no `batch_queue`.
    """

    def __init__(self, action, executor=None, interval_s=SAMPLE_INTERVAL_S,
                 log_fn=None):
        self.action = action
        self.executor = executor
        self.interval_s = max(0.2, float(interval_s))
        self.log = log_fn or (lambda _m: None)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop,
                                       name='sotto-load-action', daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.action.tick()
            except Exception as exc:                             # noqa: BLE001
                self.log('LOAD_ACTION_ERROR error=%r' % (exc,))
            self._stop.wait(self.interval_s)

    def start(self):
        self._arm_worker_channel()
        self.thread.start()
        return self

    def _arm_worker_channel(self):
        """Liga o canal que o worker le', ANTES de o shell o lancar.

        O nivel que este laco publica so' vale o que o worker obedece, e o worker
        le' o `shed` apenas com o interruptor armado (`ReduxHiddenSwitch`), cujo
        canal de DEPLOY e' `SOTTO_REDUX_WHEN_HIDDEN=1` -- o mesmo padrao de
        `SOTTO_CAPTURE_MODE`. O shell constroi o ambiente do filho com
        `dict(os.environ)` no `_spawn`, e este arranque corre no boot (medido:
        `_start_slow_read_monitor` na linha 8355, `bridge.start` na 11518), por
        isso escrever aqui chega ao processo do worker.

        Um valor JA' presente no ambiente e' do operador e NAO se reescreve: se
        disser `0`, o log diz que a accao nao tem canal, em vez de a charmar.
        """
        current = os.environ.get('SOTTO_REDUX_WHEN_HIDDEN')
        if current is not None:
            self.log('LOAD_ACTION_WORKER_CHANNEL source=env value=%s '
                     'armed=%s' % (current, str(self.action.armed).lower()))
            return False
        if not self.action.armed:
            self.log('LOAD_ACTION_WORKER_CHANNEL source=none armed=false '
                     'why=a accao esta desarmada')
            return False
        os.environ['SOTTO_REDUX_WHEN_HIDDEN'] = '1'
        self.log('LOAD_ACTION_WORKER_CHANNEL source=load_action '
                 'SOTTO_REDUX_WHEN_HIDDEN=1 why=o nivel publicado so vale se o '
                 'worker o ler')
        return True

    def stop(self):
        self._stop.set()
        if self.executor is not None and hasattr(self.executor, 'stop'):
            try:
                self.executor.stop()
            except Exception:                                    # noqa: BLE001
                pass

    def as_dict(self):
        out = self.action.as_dict()
        if self.executor is not None and hasattr(self.executor, 'as_dict'):
            out['batch'] = self.executor.as_dict()
        return out


def open_action(shell, monitor=None, log_fn=None, interval_s=SAMPLE_INTERVAL_S,
                executor=True, queue_dir=None, state=None, **kwargs):
    """A UNICA chamada da shell. Devolve o `LoadGuard` ja' a correr.

    `monitor` e' o `LoadSheddingMonitor` que a shell ja' construia: desta layer
    ele empreta DUAS coisas e nao corre o laco dele -- o ESTADO (para o nivel que
    o `shedding_level()` publica e o que a decisao tomou ser o mesmo objecto) e o
    PUBLICADOR (`_publish`, que escreve no `panel-visibility.json`). O laco do
    monitor media SO' o commit; o laco daqui mede commit E CPU e e' o unico
    escritor do estado -- dois escritores no mesmo `LoadShedding` somariam
    amostras duas vezes e as confirmacoes chegariam a metade do tempo.

    `queue_dir=None` -> `batch_queue.queue_dir()` (TMPDIR / `I:\\cc-tmp`).
    """
    log = log_fn or (lambda _m: None)
    armed = action_armed()
    if state is None:
        state = LoadShedding(floor_s=ACTION_FLOOR_S if armed else 0.0)
    view = PublishedView(state)
    if monitor is not None:
        try:
            monitor.state = view
        except Exception:                                        # noqa: BLE001
            pass
    live_fn = kwargs.pop('live_fn', None)
    if live_fn is None:
        live_fn = (lambda: bool(getattr(shell, '_caption_wanted', True)))
    publish = getattr(monitor, '_publish', None) if monitor is not None else None
    action = LoadAction(state=state, publish=publish, log_fn=log, armed=armed,
                        live_fn=live_fn, view=view, **kwargs)
    batch = None
    if executor:
        try:
            import batch_queue
        except Exception as exc:                                 # noqa: BLE001
            log('BATCH_QUEUE_IMPORT_FAILED error=%r' % (exc,))
        else:
            try:
                queue = batch_queue.BatchQueue(path=queue_dir, log_fn=log)
                batch = batch_queue.open_executor(queue=queue, log_fn=log)
            except Exception as exc:                             # noqa: BLE001
                log('BATCH_QUEUE_START_FAILED error=%r' % (exc,))
    guard = LoadGuard(action, executor=batch, interval_s=interval_s, log_fn=log)
    return guard.start()
