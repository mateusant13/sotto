import ast, sys, pathlib
for f in ("src/pipeline/chain.py","src/pipeline/contracts.py"):
    src = pathlib.Path(f).read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    defs = [n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    unused = [d for d in defs if d not in names and not d.startswith("__")]
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports += [a.asname or a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            imports += [a.asname or a.name for a in n.names]
    unused_imp = [i for i in imports if i not in names and i not in src.split("__all__")[0]]
    print(f, "defs:", len(defs), "possibly-unused defs:", unused)
    print("   imports:", len(imports), "unused:", [i for i in imports if src.count(i)<=1])
# stale API references from the old index
stale = ["ingest_clip","ingest_asr_done","ClipRecord","SearchFilter","open_index","index.schema","index.search.search_text","started_at_s="]
for f in ("src/pipeline/chain.py","src/pipeline/contracts.py"):
    t = pathlib.Path(f).read_text(encoding="utf-8")
    hits = [(s, t.count(s)) for s in stale if s in t]
    print("STALE in", f, ":", hits)
