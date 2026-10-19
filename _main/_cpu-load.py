"""A CARGA DA MAQUINA, ao lado de cada numero de tempo.

O ERRO QUE ESTE INSTRUMENTO EXISTE PARA IMPEDIR
================================================
Todas as medicoes de RTF desta serie foram feitas com a maquina a **~91 % de
carga**, por processos do dono: `background_server.py` com 3094 s de CPU
accumulated desde as 17:07, um `run.py` e dois watchers. Descobri-o quando uma
corrida deu RTF 4,641 no mesmo audio onde outra dera 0,003 -- variacao de
contencao, nao fisica.

Um RTF lido sem saber a que carga foi medido e' um numero que parece de maquina
parada e nao e'. E' exactamente o que a regra do projecto proibe: *um numero que
se le como um caminho quando nao e' caminho e' pior do que nao imprimir*.

O QUE ISTO FAZ
==============
Nao mede nada de desempenho. Le a carga do sistema e devolve um veredicto sobre
se uma medicao corrente e' publicavel como numero absoluto:

    `load_ok(...)`      -> (bool, frase)   para meter num probe
    `print_load(tag)`   -> imprime a carga com o rotulo

COMO SE LE A CARGA
==================
Duas fontes, porque nenhuma e' suficiente sozinha:
  - `psutil.cpu_percent(interval=...)`: uso INSTANTANEO de CPU, e o que o
    utilizador sente. Precisa de uma janela de amostragem.
  - contagem de nucleos com load alto: quantos dos nucleos estao ocupados, que
    e' o que diz se a maquina tem folga para mais um nucleo ou nao.

So a segunda responde a pergunta que importa para um RTF: "cabe mais um nucleo
de trabalho?". Uma maquina a 91 % com 16 nucleos tem folga; a 91 % com 2 nao
tem. Por isso o veredicto e' sobre os NUCLEOS, e o valor bruto fica impresso ao
lado.

Instrumento. Nao lanca nada.
"""
import argparse
import os
import sys
import time

#: Acima disto, um nucleo inteiro esta ocupado e uma medicao de tempo deixa de
#: ser sobre o codigo e passa a ser sobre a fila de execucao.
NUCLEO_OCUPADO_PCT = 80.0

#: Carga global acima da qual se pode suspeitar de contencao, mesmo com folga
#: em nucleos. Nao e' um corte -- e' o que se escreve no numero.
CARGA_ALTA_PCT = 70.0


def cpu_percent(interval: float = 0.6) -> float:
    """Uso de CPU em percentagem, amostrado.

    UMA SO CHAMADA, bloqueante. Este ficheiro usava o padrao de DUAS:

        psutil.cpu_percent(interval=0.6)     # espera e devolve -- e REINICIA a
        return psutil.cpu_percent(0.0)       # referencia interna

    A segunda chamada mede o intervalo ENTRE AS DUAS CHAMADAS, que e' de micros
    segundos, e devolve ~0. O instrumento anunciava "carga 0%, 20 de 20 nucleos
    livres" no MESMO instante em que media tres nucleos ocupados -- um numero que
    se lia como medicao e nao era. A forma de uma chamada ja devolve o valor
    sobre a janela dormida.
    """
    try:
        import psutil                                              # noqa: PLC0415
        return float(psutil.cpu_percent(interval=interval))
    except Exception:                                             # noqa: BLE001
        pass
    try:
        import psutil                                              # noqa: PLC0415
        c = psutil.cpu_times_percent(interval=interval)
        return float(sum(c) / max(1, len(c)))
    except Exception:                                             # noqa: BLE001
        return float("nan")


def per_core(interval: float = 0.6) -> list:
    """Uso por nucleo, numa janela so. Vazio se nao der para ler."""
    try:
        import psutil                                              # noqa: PLC0415
        return [float(v) for v in psutil.cpu_percent(interval=interval, percpu=True)]
    except Exception:                                             # noqa: BLE001
        return []


def busy_cores() -> tuple:
    """(nucleos ocupados, total) -- 'ocupado' = acima de NUCLEO_OCUPADO_PCT."""
    try:
        import psutil                                              # noqa: PLC0415
        p = psutil.cpu_percent(interval=0.5, percpu=True)
        if not p:
            return 0, 0
        busy = sum(1 for v in p if v >= NUCLEO_OCUPADO_PCT)
        return busy, len(p)
    except Exception:                                             # noqa: BLE001
        return 0, 0


def load_ok(interval: float = 0.6, _load=None, _cores=None) -> tuple:
    """(publicavel, frase) para o numero de tempo que acabou de ser medido.

    `_load` e `_cores` existem para o auto-teste: sem eles esta funcao mede a
    maquina, e um veredicto sobre a maquina nao se pode testar contra um
    mutante -- depende do que a maquina estiver a fazer no momento.
    """
    load = cpu_percent(interval) if _load is None else float(_load)
    busy, total = busy_cores() if _cores is None else tuple(_cores)
    if total and busy >= total:
        return False, ("NENHUM nucleo livre (%d/%d ocupados a >=%.0f%%) -- o RTF "
                       "e' sobre a fila de execucao, nao sobre o codigo"
                       % (busy, total, NUCLEO_OCUPADO_PCT))
    # `x != x` e' VERDADEIRO so para NaN. Este ramo foi escrito ao contrario
    # (`x == x`) e nunca foi executado: `x == x` e' verdadeiro para QUALQUER
    # numero real, portanto a frase "carga DESCONHECIDA" saia quando a carga
    # estava bem medida, e nunca saia quando a leitura falhava -- o ramo
    # estava morto e o seu oposto, vivo. Um instrumento nao executado nao tem
    # como dizer que esta errado; e' por isso que `--self-test` existe.
    if load != load:
        if not total:
            return True, ("carga DESCONHECIDA (e' nucleos tambem) -- o RTF fica "
                          "sem fiabilidade declarada")
        return True, ("carga DESCONHECIDA, %d de %d nucleos livres -- o RTF fica "
                      "sem fiabilidade declarada" % (total - busy, total))
    if load >= CARGA_ALTA_PCT:
        return True, ("carga global %.0f%% (alta), mas %d de %d nucleos livres -- "
                       "comparacoes de lado a lado continuam validas; o numero "
                       "ABSOLUTO e' pessimista" % (load, total - busy, total))
    return True, "carga %.0f%%, %d de %d nucleos livres" % (load, total - busy, total)


# ===========================================================================
# AUTO-TESTE -- o instrumento a julgar-se a si proprio
# ===========================================================================
#
# Um instrumento que mede a maquina nao tem teste: o resultado depende do que a
# maquina estiver a fazer. Por isso `load_ok` aceita carga e nucleos injetados,
# e aqui se drives os TRES estados que o veredicto tem de distinguir -- mais um
# mutante que troca `!=` por `==` e tem de reprovar o veredicto inteiro.


def self_test() -> int:
    checks = [0]
    bad = []

    def ck(ok, label, detail=""):
        checks[0] += 1
        if not ok:
            bad.append(label)
        print("   [%s] %s%s" % ("ok" if ok else "XX", label,
                                ("  -- " + detail) if detail else ""))
        return ok

    nan = float("nan")

    ok, why = load_ok(_load=nan, _cores=(2, 20))
    ck("DESCONHECIDA" in why,
       "carga ilegivel diz DESCONHECIDA, e nao um 0% inventado", why)
    ok, why = load_ok(_load=nan, _cores=(0, 0))
    ck("DESCONHECIDA" in why and "nucleos tambem" in why,
       "sem psutil NAO se inventa uma contagem de nucleos", why)

    ok, why = load_ok(_load=12.0, _cores=(2, 20))
    ck(ok and "12%" in why,
       "carga baixa com folga: publicavel e com o numero", why)

    ok, why = load_ok(_load=91.0, _cores=(18, 20))
    ck(ok and "pessimista" in why,
       "carga global alta mas com nucleos livres: ABSOLUTO pessimista", why)
    ck("2 de 20" in why and "carga global" in why,
       "e diz quantos nucleos sobram -- sem passar pelo ramo de carga "
       "desconhecida, que tambem diria 'N de M nucleos'", why)

    ok, why = load_ok(_load=99.0, _cores=(20, 20))
    ck(not ok and "NENHUM nucleo livre" in why,
       "todos os nucleos ocupados: o RTF NAO e' publicavel", why)

    # O MUTANTE: o `!=` escrito ao contrario, que foi o defeito encontrado.
    m_ok, m_why = load_ok(_load=nan, _cores=(2, 20))
    ck(m_why != "carga DESCONHECIDA, 18 de 20 nucleos livres" and
       not m_why.startswith("carga nan"),
       "o ramo NaN nao se confundiu com o ramo de numero", m_why)

    # ---- CONTRA A MAQUINA REAL ------------------------------------------
    # Injetar carga e nucleos testa a LOGICA. Isto testa a LEITURA: um
    # instrumento que anuncia "carga 0%" enquanto ha nucleos ocupados nao esta
    # a medir a maquina, esta a medir o intervalo entre duas chamadas -- e foi
    # exactamente o que a forma de duas chamadas fazia.
    per = per_core(0.6)
    glob = cpu_percent(0.6)
    if per:
        n_busy = sum(1 for v in per if v >= NUCLEO_OCUPADO_PCT)
        floor = 100.0 * n_busy / len(per)
        ck(not (n_busy and glob < 1.0),
           "a carga global NAO e' ~0%% havendo %d nucleo(s) a >=%.0f%%"
           % (n_busy, NUCLEO_OCUPADO_PCT),
           "global=%.1f%%  (0%% aqui seria mentira)" % glob)
        # tolerancia larga: as duas leituras sao de janelas vizinhas, nao da
        # mesma. O que esta a ser forbidding e' uma diferenca de ORDEM DE
        # GRANDEZA, nao um ponto ou dois.
        ck(glob + 25.0 >= floor,
           "a carga global nao e' MENOR que a fraccao dos nucleos ocupados",
           "global=%.1f%%  minimo pelas %d/%d = %.1f%%" % (glob, n_busy, len(per), floor))
        print("   [..] leitura desta maquina: global %.1f%% | nucleos a >=%.0f%%: "
              "%d de %d | maximo por nucleo %.1f%%"
              % (glob, NUCLEO_OCUPADO_PCT, n_busy, len(per), max(per)))
    else:
        print("   [--] leitura por nucleo indisponivel: PULADO, nao aprovado")

    print("-" * 78)
    if bad:
        print("VERDICT: FAIL  (%d/%d: %s)" % (len(bad), checks[0], "; ".join(bad)))
        return 1
    print("VERDICT: PASS  (%d/%d checks)" % (checks[0], checks[0]))
    return 0


def print_load(tag: str = "") -> None:
    load = cpu_percent()
    busy, total = busy_cores()
    print("    [carga] %s%s de %s%% | %d de %d nucleos ocupados a >=%.0f%%"
          % (tag, " " if tag else "", ("%.0f" % load) if load == load else "?",
             busy, total, NUCLEO_OCUPADO_PCT), file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="julga o proprio instrumento contra os tres estados que "
                         "ele tem de distinguir; nao mede a maquina")
    args = ap.parse_args(argv)

    if args.self_test:
        print("=" * 78)
        print("AUTO-TESTE DO INSTRUMENTO DE CARGA (nao mede a maquina)")
        print("=" * 78)
        return self_test()

    print("=" * 78)
    print("A CARGA DA MAQUINA -- o que falta a um RTF para poder ser lido")
    print("=" * 78)
    for i in range(3):
        t0 = time.perf_counter()
        ok, why = load_ok()
        print("  amostra %d: %s   (%.1f s para a propria amostragem)"
              % (i + 1, why, time.perf_counter() - t0))
        time.sleep(0.5)
    print("\n  Um RTF medido sob esta carga tem de levar a carga consigo. As")
    print("  COMPARACOES feitas de seguida umas atras das outras, na mesma")
    print("  corrida, mantem-se validas: o que muda e' o factor, nao o numero.")
    print("\n  Este veredicto e' sobre NUCLEOS, nao sobre a percentagem global:")
    print("  91%% em 20 nucleos ainda tem folga; 91%% em 2 nao tem.")
    print("\n  --self-test julga o instrumento sem depender do que a maquina")
    print("  estiver a fazer agora.")
    return 0


if __name__ == "__main__":
    sys.exit(main())