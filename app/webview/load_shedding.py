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


class LoadShedding:
    """O estado: o nivel EM VIGOR, e porque e' que ele mudou.

    A ordem de severidade e' `LEVELS`; subir e' imediato (uma maquina sob pressao
    nao espera pela confirmacao de uma leitura que ja' esta' acima do limiar),
    descer precisa de `CONFIRM_SAMPLES` leituras abaixo de `RESUME_PCT`.
    """

    def __init__(self, level='leve'):
        self.level = level if level in LEVELS else 'leve'
        self._recent = []
        self.last_reading = None
        self.last_cpu = None

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
                'cpu_pct': self.last_cpu,
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
