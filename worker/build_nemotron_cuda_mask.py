"""Prepare the pinned Nemotron encoder's equivalent CUDA mask broadcast."""

import argparse
import hashlib
import os
import tempfile
from pathlib import Path


SOURCE_SHA = "0b05217594ec0bda442e43a90a298ac2471a3bdcea9b169de34214e61a730e17"
DERIVED_SHA = "d564b5570c04a69c2b45c5d6c317cf47f236409bb7c2a0a9b9f3be3cd4716696"


def transform(data):
    import onnx
    from onnx import helper, numpy_helper

    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError("unexpected Nemotron source encoder SHA-256")
    model = onnx.load_model_from_string(data)
    graph = model.graph
    node = next(n for n in graph.node if n.name == "node_repeat")
    input_type = next(v.type.tensor_type for v in graph.value_info if v.name == "val_177")
    dimensions = tuple(d.dim_value for d in input_type.shape.dim)
    repeats = next(t for t in graph.initializer if t.name == "val_178")
    if (node.op_type, list(node.input), list(node.output)) != (
            "Tile", ["val_177", "val_178"], ["repeat"]):
        raise ValueError("unexpected mask operation")
    if (input_type.elem_type != onnx.TensorProto.BOOL or dimensions != (1, 1, 63)
            or list(numpy_helper.to_array(repeats)) != [1, 63, 1]):
        raise ValueError("unexpected mask shape")

    graph.initializer.append(helper.make_tensor(
        "sotto_mask_shape", onnx.TensorProto.INT64, [3], [1, 63, 63]))
    node.op_type = "Expand"
    node.input[1] = "sotto_mask_shape"
    derived = model.SerializeToString(deterministic=True)
    if hashlib.sha256(derived).hexdigest() != DERIVED_SHA:
        raise ValueError("unexpected derived encoder SHA-256")
    return derived


def main():
    import onnx

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("encoder", type=Path)
    args = parser.parse_args()
    source = args.encoder
    if source.name != "encoder.onnx" or source.stat().st_size != 2677548:
        parser.error("expected the pinned encoder.onnx")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        parser.error("unexpected Nemotron source encoder SHA-256")
    target = source.with_name("encoder.cuda-mask.onnx")
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == DERIVED_SHA:
        print(f"CACHE HIT {DERIVED_SHA}")
        return
    data = transform(data)
    fd, temp_name = tempfile.mkstemp(suffix=".onnx", prefix="encoder.cuda-mask-", dir=target.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        onnx.checker.check_model(str(temp))
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    print(f"MISS {DERIVED_SHA}")


if __name__ == "__main__":
    main()
