#!/usr/bin/env python3
"""
Streaming Hugging Face -> Cube converter.

Downloads safetensors shards, converts each tensor on the fly to cube format,
and emits the universal metadata + NPZ without ever storing the full FP32 model.

Currently handles linear layers using the existing ModelConverter logic; will be
extended via adapters for embeddings/attention/etc.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import torch
from huggingface_hub import hf_hub_download
from safetensors import safe_open

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cube_schema import LayerGraphNode
from model_converter import ModelConverter, CompressedModel
from converters.layer_adapters import get_adapter_config


def iter_safetensors(path: Path):
    with safe_open(path, framework="pt", device="cpu") as f:
        keys = list(f.keys())
        for key in keys:
            yield key, f.get_tensor(key), f


def create_empty_model(architecture: str) -> CompressedModel:
    return CompressedModel(
        architecture=architecture,
        layers={},
        metadata={
            "framework": "PyTorch",
            "quantization": "ternary",
            "cube_format": "3D_morton",
            "gpu_accelerated": False,
            "model_name": architecture,
        },
        compression_ratio=1.0,
        original_size_mb=0.0,
        compressed_size_mb=0.0,
        total_parameters=0,
        graph=[],
    )


def stream_convert(model_name: str, repo_revision: str, output: Path):
    converter = ModelConverter(use_gpu=False)
    compressed = create_empty_model(model_name)

    snapshot = hf_hub_download(
        repo_id=model_name,
        filename="model.safetensors",
        revision=repo_revision,
        local_dir=output.parent,
        local_dir_use_symlinks=False,
    )

    total_original = 0
    total_compressed_bytes = 0
    graph_nodes: List[LayerGraphNode] = []
    prev_output = "input"
    position = 0

    with safe_open(Path(snapshot), framework="pt", device="cpu") as f:
        keys = list(f.keys())
        for name in keys:
            tensor = f.get_tensor(name)

            if tensor.ndim < 2 or not name.endswith("weight"):
                continue

            bias_name = name.replace(".weight", ".bias")
            bias = f.get_tensor(bias_name) if bias_name in keys else None

            adapter_cfg = get_adapter_config(name.replace(".weight", ""))
            if not adapter_cfg.quantized:
                layer = converter.compress_dense_layer(name, tensor, bias=bias, adapter_cfg=adapter_cfg)
            else:
                layer = converter.compress_layer(name, tensor, bias=bias, adapter_cfg=adapter_cfg)
            compressed.layers[name] = layer

            bytes_orig = tensor.numel() * tensor.element_size()
            if bias is not None:
                bytes_orig += bias.numel() * bias.element_size()
            total_original += bytes_orig
            per_element = (
                0.25 if layer.extra.get("quantized", True) else layer.compressed_data.element_size()
            )
            total_compressed_bytes += layer.compressed_data.numel() * per_element

            node_name = layer.name
            graph_nodes.append(
                LayerGraphNode(
                    name=node_name,
                    layer_type=layer.layer_type,
                    inputs=[prev_output],
                    outputs=[f"{node_name}_out"],
                    activation=None,
                    extra={
                        "position": position,
                        "quantized": layer.extra.get("quantized", True),
                        "role": layer.tensor_role,
                    },
                )
            )
            prev_output = f"{node_name}_out"
            position += 1

            print(f"[stream] {name} {tensor.shape} -> {layer.cube_shape}")

    compressed.original_size_mb = total_original / (1024 * 1024)
    compressed.compressed_size_mb = total_compressed_bytes / (1024 * 1024)
    compressed.compression_ratio = (
        total_original / (total_compressed_bytes or 1)
    )
    compressed.total_parameters = sum(
        layer.original_shape[0] * layer.original_shape[1] if len(layer.original_shape) == 2 else 0
        for layer in compressed.layers.values()
    )
    compressed.graph = graph_nodes

    converter.save_compressed_model(compressed, str(output))


def main():
    parser = argparse.ArgumentParser(description="Stream HF model into cube format.")
    parser.add_argument("--model", required=True, help="HF model repo")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--output", required=True, help="Path to .npz output")
    args = parser.parse_args()

    stream_convert(args.model, args.revision, Path(args.output))


if __name__ == "__main__":
    main()

