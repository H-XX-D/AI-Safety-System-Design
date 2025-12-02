#!/usr/bin/env python3
"""
Calibration + validation harness for cube-compressed models.

Runs a small text dataset through the original and compressed models to collect
CLS embeddings, fit per-layer scale corrections, and report accuracy diffs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from datasets import load_dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers import BitsAndBytesConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from model_converter import ModelConverter
from runtime.compressed_runtime import CompressedGraphRuntime


def load_texts(num_samples: int, split: str = "validation") -> Tuple[List[str], List[int]]:
    dataset = load_dataset("glue", "sst2")
    texts = dataset[split]["sentence"][:num_samples]
    labels = dataset[split]["label"][:num_samples]
    return texts, labels


def collect_embeddings(model, tokenizer, texts: List[str]) -> torch.Tensor:
    embeddings = []
    with torch.no_grad():
        for text in texts:
            tokens = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            output = model.distilbert(**tokens)
            cls_state = model.dropout(output.last_hidden_state[:, 0, :])
            embeddings.append(cls_state.squeeze(0))
    return torch.stack(embeddings, dim=0)


def evaluate(model, tokenizer, texts: List[str]) -> List[int]:
    preds = []
    with torch.no_grad():
        for text in texts:
            tokens = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            logits = model(**tokens).logits
            preds.append(torch.argmax(logits, dim=-1).item())
    return preds


def evaluate_runtime(runtime: CompressedGraphRuntime, embeddings: torch.Tensor) -> List[int]:
    preds = []
    with torch.no_grad():
        logits = runtime(embeddings)
        preds = torch.argmax(logits, dim=-1).tolist()
    return preds


def load_quantized_model(model_name: str, quant_type: str):
    if quant_type == "int8":
        config = BitsAndBytesConfig(load_in_8bit=True)
    elif quant_type == "int4":
        config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    else:
        raise ValueError("Unsupported quant type")
    return AutoModelForSequenceClassification.from_pretrained(model_name, quantization_config=config)


def benchmark_models(model_name: str, tokenizer, texts: List[str], embeddings: torch.Tensor):
    baseline = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
    cube_converter = ModelConverter(use_gpu=False)
    compressed = cube_converter.compress_pytorch_model(baseline.classifier)
    cube_converter.save_compressed_model(compressed, "/tmp/bench_cube.npz")
    runtime = CompressedGraphRuntime(compressed)

    quant8 = load_quantized_model(model_name, "int8").eval()
    quant4 = load_quantized_model(model_name, "int4").eval()

    results = {}
    orig_preds = evaluate(baseline, tokenizer, texts)
    for name, model in [("full_fp32", baseline), ("int8", quant8), ("int4", quant4)]:
        preds = evaluate(model, tokenizer, texts)
        acc = sum(p == l for p, l in zip(preds, orig_preds)) / len(texts)
        results[name] = acc

    cube_preds = evaluate_runtime(runtime, embeddings)
    cube_acc = sum(p == l for p, l in zip(cube_preds, orig_preds)) / len(texts)
    results["cube"] = cube_acc

    for k, v in results.items():
        print(f"{k}: {v*100:.2f}% agreement with FP32")


def main():
    parser = argparse.ArgumentParser(description="Benchmark cube vs HF quantization.")
    parser.add_argument("--model", default="distilbert-base-uncased-finetuned-sst-2-english")
    parser.add_argument("--samples", type=int, default=256)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    texts, labels = load_texts(args.samples)
    baseline_model = AutoModelForSequenceClassification.from_pretrained(args.model).eval()
    embeddings = collect_embeddings(baseline_model, tokenizer, texts)

    cube_converter = ModelConverter(use_gpu=False)
    compressed = cube_converter.compress_pytorch_model(baseline_model.classifier)
    cube_converter.save_compressed_model(compressed, "/tmp/bench_cube.npz")
    runtime = CompressedGraphRuntime(compressed)

    baseline_preds = evaluate(baseline_model, tokenizer, texts)
    cube_preds = evaluate_runtime(runtime, embeddings)

    baseline_acc = sum(int(p == l) for p, l in zip(baseline_preds, labels)) / len(labels)
    cube_acc = sum(int(p == l) for p, l in zip(cube_preds, labels)) / len(labels)
    agreement = sum(int(p == q) for p, q in zip(baseline_preds, cube_preds)) / len(labels)

    print(f"Baseline accuracy: {baseline_acc*100:.2f}%")
    print(f"Cube accuracy: {cube_acc*100:.2f}%")
    print(f"Cube vs baseline agreement: {agreement*100:.2f}%")


if __name__ == "__main__":
    main()

