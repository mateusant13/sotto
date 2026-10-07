import onnxruntime_genai as og, inspect
for t in ("Model","Config","GeneratorParams","Generator","Tokenizer"):
    c=getattr(og,t)
    print("==== "+t)
    for n in ("__init__","encode","decode","apply_chat_template","append_tokens","generate_next_token","get_sequence","is_done","token_count","set_search_options","append_provider","clear_providers","overlay","get_search_options"):
        f=getattr(c,n,None)
        if f is None: continue
        try: sig=str(inspect.signature(f))
        except Exception: sig="(builtin)"
        print("  %s %s" % (n,sig))
        d=(getattr(f,"__doc__","") or "").strip().splitlines()
        for L in d[:10]: print("      |",L.strip())
print("is_cuda_available", og.is_cuda_available())
