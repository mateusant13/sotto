import sys, pathlib
root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src" / "index"))
import store, search   # noqa
print("index modules import OK")