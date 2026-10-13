import ast, os, sys
src = open(r'H:/sotto/worker/sotto_worker.py', encoding='utf-8').read()
tree = ast.parse(src)
fn = None
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_second_pass_enabled":
        fn = node; break
if fn is None:
    print("FALHOU: a funcao nao existe"); raise SystemExit(2)
body = [ast.unparse(n) for n in fn.body
        if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
src2 = "import os\n" + "\ndef _f():\n    " + "\n    ".join(body)
ns = {}
exec(src2, ns)
_f = ns["_f"]
def val(env):
    os.environ.pop("SOTTO_SECOND_PASS", None)
    for k, v in env.items(): os.environ[k] = v
    return _f()
cases = [({}, False, "omissao -> DESLIGADO"),
         ({"SOTTO_SECOND_PASS": "1"}, True, "=1 -> LIGADO"),
         ({"SOTTO_SECOND_PASS": "0"}, False, "=0 -> DESLIGADO"),
         ({"SOTTO_SECOND_PASS": "true"}, True, "=true -> LIGADO"),
         ({"SOTTO_SECOND_PASS": ""}, False, "=vazio -> DESLIGADO"),
         ({"SOTTO_SECOND_PASS": "yes"}, True, "=yes -> LIGADO")]
ok = True
for env, want, label in cases:
    got = val(env)
    good = (got == want)
    if not good: ok = False
    print(("  ok   " if good else "  FAIL ") + label + " -> " + str(got))
print("VERDICT: " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)