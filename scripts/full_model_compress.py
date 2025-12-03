#!/usr/bin/env python3
"""
Compress an entire Hugging Face model (encoder, classifier, or full stack)
into the cube format.

This is the first step toward full-model calibration: we serialize every module
using the existing ModelConverter, inspect compression stats, and store the
artifact for downstream calibration / runtime tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
from transformers import AutoModelForSequenceClassification, AutoConfig

from model_converter import ModelConverter


def select_component(model, component: str):
    component = component.lower()
    if component == "full":
        return model
    if component == "encoder":
        if hasattr(model, "distilbert"):
            return model.distilbert
        raise ValueError("Model does not expose .distilbert encoder")
    if component == "classifier":
        return model.classifier
    raise ValueError(f"Unknown component '{component}'. Use encoder/classifier/full.")


def main():
    parser = argparse.ArgumentParser(description="Compress a full HF model into cube format.")
    parser.add_argument("--model", default="distilbert-base-uncased-finetuned-sst-2-english")
    parser.add_argument("--component", default="encoder", help="Which module to compress: encoder | classifier | full")
    parser.add_argument("--output", default="/tmp/full_model_cube.npz")
    parser.add_argument("--use-gpu", action="store_true")
    args = parser.parse_args()

    print(f"Loading model: {args.model}")
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.eval()

    target_module = select_component(model, args.component)
    print(f"Selected component: {args.component}")

    converter = ModelConverter(use_gpu=args.use_gpu)
    compressed = converter.compress_pytorch_model(target_module)
    converter.save_compressed_model(compressed, args.output)

    print("\n=== Compression Summary ===")
    print(f"Architecture: {compressed.architecture}")
    print(f"Layers compressed: {len(compressed.layers)}")
    print(f"Original size: {compressed.original_size_mb:.2f} MB")
    print(f"Compressed size: {compressed.compressed_size_mb:.2f} MB")
    print(f"Compression ratio: {compressed.compression_ratio:.2f}x")
    print(f"Metadata saved to: {args.output} (+ .json)")


if __name__ == "__main__":
    main()


