# font-fix-fraunces.py — conserta, numa CÓPIA, a causa medida:
# a tabela STAT do Fraunces não marca como ELIDABLE (0x0002) os nomes dos
# valores de eixo que são os DEFAULT do ficheiro (opsz=9 -> '9pt', wght=900 ->
# 'Black'; no itálico também ital=1 -> 'Italic'). O DirectWrite (backend de
# fontes do Chromium no Windows) cola ao nome da família os nomes dos valores
# de eixo NÃO elidíveis, e por isso expõe `Fraunces 9pt` / `Fraunces 9pt
# SuperSoft` — e NENHUMA família `Fraunces`.
#
# O original NUNCA é tocado: lê-se, escreve-se uma cópia nova.
#
# Uso: py -3 H:\aireplay\_main\font-fix-fraunces.py
import os
import shutil
import sys

from fontTools.ttLib import TTFont

SRC = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "Fonts")
BACKUP = r"H:\aireplay\_main\_fontes-fix"
ELIDABLE = 0x0002

# (ficheiro original, ficheiro novo na pasta de fontes do utilizador)
PAIRS = [
    ("Fraunces-Variable.ttf", "Fraunces-Variable-STATfix.ttf"),
    ("Fraunces-Italic-Variable.ttf", "Fraunces-Italic-Variable-STATfix.ttf"),
]


def log(*a):
    print(*a)
    sys.stdout.flush()


def involved(f, av):
    """[(axisIndex, value)] de um AxisValue da STAT, em qualquer formato."""
    fmt = av.Format
    if fmt == 1:
        return [(av.AxisIndex, av.Value)]
    if fmt == 2:
        return [(av.AxisIndex, av.NominalValue)]
    if fmt == 3:
        return [(av.AxisIndex, av.Value)]
    if fmt == 4:
        return [(r.AxisIndex, r.Value) for r in av.AxisValueRecord]
    raise ValueError("STAT AxisValue format desconhecido: %r" % fmt)


def fix_one(src, dst):
    f = TTFont(src)
    st = f["STAT"].table
    defaults = {a.axisTag: a.defaultValue for a in f["fvar"].axes}
    tags = [a.AxisTag for a in st.DesignAxisRecord.Axis]
    changed = []
    for i, av in enumerate(st.AxisValueArray.AxisValue):
        nm = f["name"].getDebugName(av.ValueNameID)
        coords = involved(f, av)
        is_default = all(
            abs(float(v) - float(defaults.get(tags[ai], v))) < 1e-6
            for ai, v in coords
        )
        if is_default and not (av.Flags & ELIDABLE):
            av.Flags = av.Flags | ELIDABLE
            changed.append((i, nm, [(tags[ai], v) for ai, v in coords], av.Flags))
    f.save(dst)
    f.close()
    log("  -> %s" % dst)
    for i, nm, coords, fl in changed:
        log("     AxisValue[%d] %r %s  flags=0x%04x  (agora ELIDABLE)" % (i, nm, coords, fl))
    if not changed:
        log("     (nada a mudar — já estava tudo elidível)")
    return changed


def main():
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    for orig, new in PAIRS:
        src = os.path.join(SRC, orig)
        log("=" * 78)
        log("%s  (%d B)" % (src, os.path.getsize(src)))
        # cópia de segurança dos ORIGINAIS, byte a byte, na pasta da lane
        bak = os.path.join(BACKUP, orig)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
            log("  backup byte-a-byte: %s" % bak)
        fix_one(src, os.path.join(BACKUP, new))
        # a cópia CORRIGIDA vai para a pasta de fontes do utilizador
        shutil.copy2(os.path.join(BACKUP, new), os.path.join(SRC, new))
        log("  instalada (cópia): %s" % os.path.join(SRC, new))
    log("")
    log("ORIGINAIS intactos: %s" % ", ".join(o for o, _ in PAIRS))


if __name__ == "__main__":
    main()
