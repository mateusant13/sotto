# Vendored third-party source — provenance

Why this directory exists: `_main/diar-models/mossformer2/last_best_checkpoint.pt`
(670 353 271 B) is a **weight file**, not a program. Loading it requires the
architecture that defines its key names. Measured on this box (2026-11-17):

```
$ python -c "import importlib.util as u; [print(m, bool(u.find_spec(m))) for m in ['clearvoice','modelscope','rotary_embedding_torch','mossformer2']]"
clearvoice False      modelscope False      rotary_embedding_torch False      mossformer2 False
$ python -c "import torch, onnxruntime, einops; print('torch/ort/einops installed')"
```

so nothing here was importable. Three options, and why this one:

| option | why not |
|---|---|
| `pip install clearvoice` | pulls its own torch/numpy constraints into `H:\Python311`, the interpreter that holds this repo's torch 2.15/numpy 1.26 and the ONNX Runtime that `worker/` depends on. The owner's standing rule is not to disturb that. |
| a requirements pin | same install, plus it would be a *runtime* dependency of a bench arm that must be runnable on a box with no network. |
| vendor the minimum source | **chosen**: 10 files, 3 911 lines, importable by path, zero effect on the shipping interpreter. |

## What each part is

| vendored path | upstream project | licence |
|---|---|---|
| `mossformer2/` (`mossformer2.py`, `mossformer2_block.py`, `conv_module.py`, `fsmn.py`, `layer_norm.py`, `__init__.py`) | **modelscope/ClearerVoice-Studio**, `clearvoice/models/mossformer2_sep/` — the repo named by the checkpoint's own README (`_main/diar-models/mossformer2/README.md`: "The MossFormer2_SS_16K model weights … in ClearerVoice-Studio repo") | Apache-2.0. `layer_norm.py` carries the upstream notice verbatim: `Copyright 2018 Northwestern Polytechnical University (author: Ke Wang)` |
| `rotary_embedding_torch/` (`rotary_embedding_torch.py`, `__init__.py`, `flash_attn_with_rotary.py`, `flash_fused_rotary.py`) | **lucidrains/rotary-embedding-torch** | MIT (upstream project licence) |

## UNKNOWN, stated rather than invented

**The upstream commit/tag is NOT recorded.** Whoever copied this tree did not write it
down, and there is no `__version__` in any of the 10 files (`mossformer2/__init__.py` is
0 bytes). Do not "fix" this by adding a version string that was guessed.

What makes the gap closable: the per-file hashes below. Diff them against
ClearerVoice-Studio and `rotary-embedding-torch` tags to identify the exact revision.

```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  mossformer2/__init__.py
b413aa0cb0df34742460a1f1af2e2cd1d2005900af8ac17e8de8675b8f80de86  mossformer2/conv_module.py
62c376b2708ac1c59853c13cbe9acb7ea011082c39f1a42e1af0f8213a00bb76  mossformer2/fsmn.py
d28fea41b3c5a2dd8bb7a1a8c1c97492fcc7eb88cc7b46283fc21e4dbf19f062  mossformer2/layer_norm.py
66f14af8efc0758d8c79bd7d1054851558081c5f6f1150cdf133ae4b6ca9c442  mossformer2/mossformer2.py
9ef7fe9cac808e0df7f5024d2bc8c54192f0aa3e670755916cc2687ea2536f08  mossformer2/mossformer2_block.py
8ec84018dc9d8df95d94d8b8ba1b16579706cbd159ce719c2faca2bed1550d67  rotary_embedding_torch/__init__.py
6080a157f328eda6a6f818d228b96b7f3a0d57a7677c99333ea843eb551eaa91  rotary_embedding_torch/flash_attn_with_rotary.py
4fafdb59f7d85531896fcdad415662640d86c30a6b2e23a8ce73a9d2287c17a2  rotary_embedding_torch/flash_fused_rotary.py
755926542e3478d0f27d99b75db7e374b29df83b489e1251b8abee2bca3c79c7  rotary_embedding_torch/rotary_embedding_torch.py
```

(`sha256sum _main/bench/_vendor/**/*.py`, 2026-11-17.)

## What actually loads, and what is dead weight

`mossformer2/mossformer2_block.py:16` is the only consumer:
`from rotary_embedding_torch import RotaryEmbedding`, which resolves through
`rotary_embedding_torch/__init__.py` to `rotary_embedding_torch.py` alone.

**`flash_attn_with_rotary.py` (529 lines) and `flash_fused_rotary.py` are never imported
by this path**, and `flash_attn` is not installed. They are 2 of the 10 files — dead
weight carried because the copy was wholesale. They are left in place rather than
deleted: deleting files out of a vendored tree without recording the upstream revision
would make the next diff against upstream look modified.

## Scope

Everything vendored lives under `_main/bench/_vendor/`. Nothing outside `_main/bench/`
was touched, no package was installed, and the shipping interpreter's imports are
unchanged (`separate.py` inserts this directory into `sys.path` at load time only).
