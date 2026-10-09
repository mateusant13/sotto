import json
p = r"H:\sotto-wt-IndexImpl\_moved\aireplay\_main\index-final.json"
d = json.load(open(p, encoding="utf-8"))
def walk(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)): walk(v, pre + k + ".")
            else:
                s = str(v)
                if len(s) < 90: print(f"  {pre}{k} = {s}")
    elif isinstance(o, list): pass
walk(d)
