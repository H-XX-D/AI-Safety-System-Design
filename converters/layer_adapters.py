"""
Heuristics for classifying tensors into semantic roles (embedding, attention,
FFN, classifier, etc.) and adjusting compression strategies accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class AdapterConfig:
    role: str = "linear"
    quantized: bool = True
    target_cube_size: Optional[int] = None
    extra: Dict[str, str] = field(default_factory=dict)
    activation: Optional[str] = None
    store_as_cube: bool = True


def _match(name: str, needle: str) -> bool:
    return needle in name


def get_adapter_config(layer_name: str) -> AdapterConfig:
    name = layer_name.lower()

    if "embeddings" in name:
        return AdapterConfig(
            role="embedding",
            quantized=False,
            extra={"precision": "dense"},
            store_as_cube=False,
        )

    if ".attention" in name:
        if ".q_lin" in name:
            return AdapterConfig(role="attention_q", extra={"head": "Q"})
        if ".k_lin" in name:
            return AdapterConfig(role="attention_k", extra={"head": "K"})
        if ".v_lin" in name:
            return AdapterConfig(role="attention_v", extra={"head": "V"})
        if ".out_lin" in name:
            return AdapterConfig(role="attention_out")

    if ".ffn.lin1" in name:
        return AdapterConfig(role="ffn_in", activation="gelu")

    if ".ffn.lin2" in name:
        return AdapterConfig(role="ffn_out")

    if "pre_classifier" in name:
        return AdapterConfig(
            role="pre_classifier", quantized=False, extra={"precision": "dense"}
        )

    if "classifier" in name:
        return AdapterConfig(
            role="classifier",
            quantized=False,
            extra={"precision": "dense"},
            store_as_cube=False,
        )

    if "layernorm" in name or "layer_norm" in name:
        return AdapterConfig(
            role="layer_norm",
            quantized=False,
            extra={"precision": "dense"},
            store_as_cube=False,
        )

    return AdapterConfig()


def get_activation_for_role(role: Optional[str]) -> Optional[str]:
    if role == "ffn_in":
        return "gelu"
    return None

