#!/usr/bin/env python3
"""
Apply cube-compressed weights back into a Hugging Face model and evaluate accuracy.

This provides an end-to-end calibration harness for the full encoder: we compress
DistilBERT, reconstruct weights via CubeLayer, load them into a fresh model copy,
and measure accuracy on SST-2 (subset).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import torch
from datasets import load_dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_converter import ModelConverter, CompressedModel

def load_texts(num_samples: int, split: str = "validation") -> Tuple[List[str], List[int]]:
    dataset = load_dataset("glue", "sst2")
    sentences = dataset[split]["sentence"][:num_samples]
    labels = dataset[split]["label"][:num_samples]
    return sentences, labels


def reconstruct_dense(cube_layer) -> torch.Tensor:
    data = cube_layer.compressed_data
    if isinstance(data, torch.Tensor):
        cube_tensor = data.to(torch.float32)
    else:
        cube_tensor = torch.tensor(data, dtype=torch.float32)

    flat = cube_tensor.reshape(-1)
    total_elements = 1
    for dim in cube_layer.original_shape:
        total_elements *= dim

    if flat.numel() < total_elements:
        pad = torch.zeros(total_elements - flat.numel(), dtype=flat.dtype, device=flat.device)
        flat = torch.cat([flat, pad], dim=0)
    else:
        flat = flat[:total_elements]

    dense = flat.view(*cube_layer.original_shape)
    scale = cube_layer.scale_factor
    if isinstance(scale, torch.Tensor):
        scale = scale.to(dense.device, dtype=dense.dtype)
        if scale.numel() == 1:
            dense = dense * scale
        else:
            view_shape = [scale.shape[0]] + [1] * (dense.dim() - 1)
            if scale.numel() != dense.shape[0]:
                scale = scale.flatten()
                if scale.shape[0] != dense.shape[0]:
                    scale = scale.mean().view(1)
                    view_shape = [1] + [1] * (dense.dim() - 1)
            dense = dense * scale.view(*view_shape)
    else:
        dense = dense * float(scale)
    return dense


def apply_compressed_weights(model, compressed: CompressedModel):
    """Overwrite model.distilbert weights with cube reconstructions."""
    cube_layers = compressed.layers
    for name, module in model.distilbert.named_modules():
        weight_attr = getattr(module, "weight", None)
        bias_attr = getattr(module, "bias", None)
        if weight_attr is None:
            continue
        key = f"{name}.weight" if name else "weight"
        if key not in cube_layers:
            continue
        cube_layer = cube_layers[key]
        dense = reconstruct_dense(cube_layer).to(module.weight.data.device)
        module.weight.data.copy_(dense)
        if bias_attr is not None and cube_layer.bias is not None:
            module.bias.data.copy_(cube_layer.bias.to(module.bias.data.device))


def evaluate(model, tokenizer, texts: List[str], labels: List[int]) -> float:
    device = torch.device("cpu")
    model = model.to(device)
    correct = 0
    with torch.no_grad():
        for text, label in zip(texts, labels):
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(device)
            logits = model(**inputs).logits
            pred = torch.argmax(logits, dim=-1).item()
            correct += int(pred == label)
    return correct / len(texts)


def main():
    parser = argparse.ArgumentParser(description="Full-model cube calibration benchmark.")
    parser.add_argument("--model", default="distilbert-base-uncased-finetuned-sst-2-english")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--output", default="/tmp/distilbert_encoder_cube.npz")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    baseline = AutoModelForSequenceClassification.from_pretrained(args.model)
    baseline.eval()

    texts, labels = load_texts(args.samples)
    baseline_acc = evaluate(baseline, tokenizer, texts, labels)

    converter = ModelConverter(use_gpu=False)
    compressed = converter.compress_pytorch_model(baseline.distilbert)
    converter.save_compressed_model(compressed, args.output)

    quantized_model = AutoModelForSequenceClassification.from_pretrained(args.model)
    quantized_model.eval()
    apply_compressed_weights(quantized_model, compressed)
    cube_acc = evaluate(quantized_model, tokenizer, texts, labels)

    print(f"Baseline accuracy: {baseline_acc*100:.2f}%")
    print(f"Cube accuracy: {cube_acc*100:.2f}%")
    print(f"Compression ratio: {compressed.compression_ratio:.2f}x")


if __name__ == "__main__":
    main()

