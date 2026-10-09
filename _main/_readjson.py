import json
p = r"H:\sotto-wt-IndexImpl\_moved\aireplay\_main\index-final.json"
d = json.load(open(p, encoding="utf-8"))
def walk(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                walk(v, pre + k + ".")
            else:
                print(f"  {pre}{k} = {v}")
    elif isinstance(o, list):
        print(f"  {pre[:-1]}[] len={len(o)}")
walk(d)
