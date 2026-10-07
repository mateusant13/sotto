"""READ-ONLY graph census of the int8 encoder: is the graph really int8-quantized?

Reports the op-type histogram, the IR version and the opset imports, and the number of
tensors whose element type is an integer type -- i.e. whether the int8 export carries
int8 operators (DynamicQuantizeLinear / MatMulInteger / ConvInteger) or is only
named ".int8" while running float.

Usage: python onnx_graph_census.py PATH [PATH...]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import onnx
from onnx import TensorProto


def census(path: Path) -> dict:
    model = onnx.load(str(path), load_external_data=False)
    graph = model.graph
    ops = Counter(node.op_type for node in graph.node)
    dtype_names = {
        1: "FLOAT", 2: "UINT8", 3: "INT8", 4: "UINT16", 5: "INT16", 6: "INT32",
        7: "INT64", 9: "BOOL", 10: "FLOAT16", 11: "DOUBLE", 16: "BFLOAT16",
    }
    dtypes = Counter()
    for init in graph.initializer:
        dtypes[dtype_names.get(init.data_type, str(init.data_type))] += 1
    return {
        "file": str(path),
        "bytes": path.stat().st_size,
        "ir_version": model.ir_version,
        "opset_imports": {i.domain or "ai.onnx": i.version for i in model.opset_import},
        "node_count": len(graph.node),
        "op_types": dict(ops.most_common()),
        "initializer_dtypes": dict(dtypes.most_common()),
        "quant_ops": {k: v for k, v in ops.items() if "Quant" in k or "Integer" in k},
    }


if __name__ == "__main__":
    out = [census(Path(p)) for p in sys.argv[1:]]
    print(json.dumps(out, indent=2))
