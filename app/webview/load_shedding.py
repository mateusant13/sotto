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

#: Pressao de commit a partir da qual a maquina esta' "alta".
HIGH_PCT = 88.0

#: ... e a partir da qual esta' "muito alta". O dono mediu a maquina dele com a
#: pressao de commit em 92,5 % quando o gate central ficou RED; 94 deixa margem
#: para esse valor nao ser o unico regime em que o parakeet tambem cai.
VERY_HIGH_PCT = 94.0

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

    # -- a leitura -------------------------------------------------------
    def observe(self, commit_pct):
        """Regista uma leitura e devolve (nivel_novo, mudou, razao).

        `mudou` existe para o chamador nao ter de comparar: a ACCAO (parar um
        motor) so' se executa quando o nivel MUDA, e um log a cada amostra
        afogaria o ficheiro.
        """
        self.last_reading = commit_pct
        wanted = level_for(commit_pct)
        self._recent.append(wanted)
        if len(self._recent) > WINDOW_SAMPLES:
            self._recent.pop(0)

        # SUBIR: imediato, e sem passar por degraus -- uma maquina que salta de
        # 87 % para 96 % nao quer que o nemotron fique a correr enquanto o
        # parakeet "confirma". O nivel pedido agora e' mais severo do que o vigente.
        if LEVELS.index(wanted) > LEVELS.index(self.level):
            return self._set(wanted, 'subiu: %.1f%% >= limiar de %s' % (float(commit_pct), wanted))

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
            if calm and self._recent.count(wanted) >= min(CONFIRM_SAMPLES, len(self._recent)):
                one_down = LEVELS[LEVELS.index(self.level) - 1]
                return self._set(one_down, 'desceu um degrau: %.1f%% < %.0f%% por %d amostras'
                                 % (float(commit_pct), RESUME_PCT, CONFIRM_SAMPLES))
            return (self.level, False, 'segurado em %s: %.1f%% ainda nao confirmou a descida'
                    % (self.level, float(commit_pct) if self._is_number(commit_pct) else -1.0))

        return (self.level, False, '')

    @staticmethod
    def _is_number(value):
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

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
                'engines': self.engines(), 'stopped': self.stopped()}
