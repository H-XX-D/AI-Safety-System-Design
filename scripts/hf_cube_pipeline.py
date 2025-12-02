#!/usr/bin/env python3
"""
Automate Hugging Face model conversion into the 3D cube format and run inference.

Current focus:
  * Works best with DistilBERT-style sequence classifiers where the classification
    head is a small feed-forward block (linear -> relu -> linear).
  * Compresses only the classification head so it can be reconstructed by
    `InferenceEngine`'s MLP-oriented runtime.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from model_converter import ModelConverter
from inference_engine import InferenceEngine


def clone_linear(module: torch.nn.Linear) -> torch.nn.Linear:
    """Copy weights from an existing Linear module into a fresh instance."""
    cloned = torch.nn.Linear(
        module.in_features,
        module.out_features,
        bias=module.bias is not None,
    )
    cloned.load_state_dict(module.state_dict())
    return cloned


class DistilBertHead(torch.nn.Module):
    """
    Minimal DistilBERT classification head replica.

    The original head runs:
        dropout -> pre_classifier -> relu -> dropout -> classifier
    and consumes the CLS embedding.
    """

    def __init__(self, source_model: torch.nn.Module):
        super().__init__()

        if not hasattr(source_model, "pre_classifier") or not hasattr(
            source_model, "classifier"
        ):
            raise ValueError(
                "DistilBERT head requires `pre_classifier` and `classifier` modules."
            )

        self.dropout = torch.nn.Dropout(p=source_model.dropout.p)
        self.pre_classifier = clone_linear(source_model.pre_classifier)
        self.activation = torch.nn.ReLU()
        self.classifier = clone_linear(source_model.classifier)
        self.eval()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.dropout(x)
        x = self.pre_classifier(x)
        x = self.activation(x)
        x = self.dropout(x)
        x = self.classifier(x)
        return x


class HFCompressionPipeline:
    """End-to-end automation for loading, compressing, and benchmarking HF models."""

    def __init__(
        self,
        model_name: str,
        output_path: Path,
        sample_text: str,
        num_runs: int = 5,
        use_gpu: bool = True,
    ):
        self.model_name = model_name
        self.output_path = output_path
        self.sample_text = sample_text
        self.num_runs = num_runs
        self.use_gpu = use_gpu

        self.model = None
        self.tokenizer = None

    def _load_hf_assets(self):
        print(f"Downloading model + tokenizer: {self.model_name}")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        )
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)

    def _build_head(self) -> torch.nn.Module:
        if self.model.__class__.__name__.lower().startswith("distilbert"):
            return DistilBertHead(self.model)
        raise NotImplementedError(
            "Automatic head extraction is currently implemented for DistilBERT "
            "architectures only. Extend `HFCompressionPipeline._build_head` to add "
            "support for additional model families."
        )

    def _prepare_cls_embedding(self, tokens: Dict[str, torch.Tensor]) -> torch.Tensor:
        base_outputs = self.model.distilbert(**tokens)
        cls_state = base_outputs.last_hidden_state[:, 0, :]
        cls_state = self.model.dropout(cls_state)
        return cls_state

    def run(self) -> Dict[str, Any]:
        self._load_hf_assets()
        head = self._build_head()

        converter = ModelConverter(use_gpu=self.use_gpu)
        compressed_model = converter.compress_pytorch_model(head)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        converter.save_compressed_model(compressed_model, str(self.output_path))

        engine = InferenceEngine(use_gpu=self.use_gpu)
        compressed_runtime = engine.load_model(str(self.output_path))

        tokens = self.tokenizer(
            self.sample_text, return_tensors="pt", padding=True, truncation=True
        )

        with torch.no_grad():
            cls_state = self._prepare_cls_embedding(tokens)
            original_logits = head(cls_state)
            full_model_logits = self.model(**tokens).logits

        inference_result = engine.run_inference(
            compressed_runtime, cls_state, num_runs=self.num_runs
        )
        compressed_logits = inference_result.output.detach().cpu()

        original_pred = torch.argmax(full_model_logits, dim=-1).item()
        head_pred = torch.argmax(original_logits, dim=-1).item()
        compressed_pred = torch.argmax(compressed_logits, dim=-1).item()

        stats = {
            "model": self.model_name,
            "text": self.sample_text,
            "num_runs": self.num_runs,
            "compression": {
                "original_mb": compressed_model.original_size_mb,
                "compressed_mb": compressed_model.compressed_size_mb,
                "ratio": compressed_model.compression_ratio,
            },
            "latency_ms": inference_result.latency_ms,
            "memory_mb": inference_result.memory_usage_mb,
            "predictions": {
                "full_model": original_pred,
                "head_only": head_pred,
                "compressed_head": compressed_pred,
                "matches_full_model": compressed_pred == original_pred,
            },
            "logits": {
                "full_model": full_model_logits.detach().cpu().tolist(),
                "head_only": original_logits.detach().cpu().tolist(),
                "compressed_head": compressed_logits.tolist(),
            },
        }

        return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Automate Hugging Face model conversion to 3D cube format and run inference."
        )
    )
    parser.add_argument(
        "--model-name",
        default="distilbert-base-uncased-finetuned-sst-2-english",
        help="Hugging Face model identifier to download.",
    )
    parser.add_argument(
        "--text",
        default="This GPU-accelerated compression pipeline is incredibly exciting!",
        help="Sample text to tokenize for inference comparison.",
    )
    parser.add_argument(
        "--output",
        default="/tmp/hf_cube_compressed.npz",
        help="Path for the compressed cube weights (.npz). Metadata will be co-saved as JSON.",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=5,
        help="How many timed runs to average when benchmarking the compressed head.",
    )
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU acceleration even if an MPS/CUDA device is available.",
    )
    parser.add_argument(
        "--stats-json",
        default="",
        help="Optional path to store the resulting stats dictionary as JSON.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pipeline = HFCompressionPipeline(
        model_name=args.model_name,
        output_path=Path(args.output),
        sample_text=args.text,
        num_runs=args.num_runs,
        use_gpu=not args.no_gpu,
    )

    start = time.time()
    stats = pipeline.run()
    elapsed = time.time() - start

    print("\n=== Automation Summary ===")
    print(json.dumps(stats, indent=2))
    print(f"\nTotal pipeline time: {elapsed:.2f}s")

    if args.stats_json:
        stats_path = Path(args.stats_json)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, indent=2))
        print(f"Saved stats to {stats_path}")


if __name__ == "__main__":
    main()

