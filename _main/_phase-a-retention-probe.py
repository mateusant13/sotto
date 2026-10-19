"""O buraco do desenho em duas fases, MEDIDO.

O dono (2026-10-18): *"precisamos detectar que sao multiplas vozes, pra decidir
isso pra processar depois quando e seguro e nao travar o pc do usuario."*

A Fase A detecta. Mas o `RingBuffer` e' em memoria e DESLIZA: quando a janela
avanca, o audio antigo desaparece. Se "depois" for mais tarde do que a proxima
janela -- e tem de ser, porque o ponto de "depois" e' nao pesar agora no PC --
entao o audio que a Fase A assinalou JA NAO EXISTE.

Este instrumento mede esse facto em vez de o afirmar: empurra 30 s num buffer de
10 s e pergunta o que sobra, e ate quando.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "worker"))

import speaker_sidecar as S   # noqa: E402

FS = 16000


def main():
    buf = S.RingBuffer(rate=FS, window_s=10.0)
    print("capacidade do buffer: %d amostras (%.0f s)"
          % (buf.capacity, buf.capacity / float(FS)))

    t0 = 1000000.0                       # um instante absoluto qualquer
    block = [0.01] * int(FS * 10)        # 10 s
    for i in range(3):                   # tres janelas de 10 s
        buf.push(block, t0 + i * 10.0)

    held_s = len(buf.window()) / float(FS)
    start = buf.start_t
    print("\ndepois de 30 s empurrados:")
    print("  o buffer segura %.0f s, de %.1f s a %.1f s"
          % (held_s, start - t0, start - t0 + held_s))
    print("  os primeiros %.0f s NAO ESTAO AQUI -- foram libertados"
          % (30.0 - held_s))

    # A janela do meio vai de 10 s a 20 s. O buffer esta cheio no fim dos 30 s.
    when_flagged = t0 + 20.0              # fim da janela do meio
    freed_at = t0 + 30.0                  # buffer cheio, cauda cortada
    print("\na janela do meio (10 s a 20 s) e' libertada do buffer em t = %.1f s"
          % (freed_at - t0))
    print("  o buffer so guarda ate t = %.1f s" % (start - t0 + held_s))
    print("  ou seja %.0f s depois de a janela ter sido vista."
          % (freed_at - when_flagged))
    print("  'Processar depois' significa essa margem ou mais -- e o audio nao esta.")

    print("\nCONCLUSAO: a DETECCAO sobrevive, porque o payload leva tempos")
    print("absolutos. o AUDIO nao. Passado o intervalo da janela -- 10 s -- nao ha")
    print("nada para reprocessar. 'Processar depois' e' hoje IMPOSSIVEL, e nao por")
    print("falta de tempo: por falta de audio guardado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())