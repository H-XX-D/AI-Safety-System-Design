"""
Generic runtime that rebuilds a model graph from cube-compressed metadata.

Now supports sequential linear graphs plus grouped attention blocks with cached
weights. Additional op types can be registered by extending the planner.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import math

import torch
import torch.nn as nn

from cube_schema import LayerGraphNode
from model_converter import CompressedModel
from converters.layer_adapters import get_activation_for_role
from inference_engine import CubeLayer


class CachedCubeLinear(nn.Module):
    """Wraps a CubeLayer and caches reconstructed weights."""

    def __init__(self, cube_layer: CubeLayer, cache_weights: bool = True):
        super().__init__()
        self.layer = cube_layer
        self.cache_weights = cache_weights
        self._cached_weights: torch.Tensor | None = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.cache_weights:
            if self._cached_weights is None:
                self._cached_weights = self.layer.reconstruct_weights()
            weights = self._cached_weights
        else:
            weights = self.layer.reconstruct_weights()

        bias = self.layer.bias
        return nn.functional.linear(x, weights, bias)


class CubeAttentionBlock(nn.Module):
    """Self-attention block constructed from cube-compressed Q/K/V/Out layers."""

    def __init__(
        self,
        q_layer: CubeLayer,
        k_layer: CubeLayer,
        v_layer: CubeLayer,
        out_layer: CubeLayer,
        cache_weights: bool = True,
    ):
        super().__init__()
        self.q_linear = CachedCubeLinear(q_layer, cache_weights)
        self.k_linear = CachedCubeLinear(k_layer, cache_weights)
        self.v_linear = CachedCubeLinear(v_layer, cache_weights)
        self.out_linear = CachedCubeLinear(out_layer, cache_weights)

        hidden_size = q_layer.original_shape[0]
        self.num_heads = self._infer_num_heads(hidden_size)
        self.head_dim = hidden_size // self.num_heads

    @staticmethod
    def _infer_num_heads(hidden_size: int) -> int:
        for divisor in (16, 12, 8, 6, 4, 2):
            if hidden_size % divisor == 0:
                return divisor
        return 1

    def _reshape_heads(self, tensor: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, hidden_size = tensor.shape
        return (
            tensor.view(batch_size, seq_len, self.num_heads, self.head_dim)
            .transpose(1, 2)
            .contiguous()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        squeeze = False
        if x.dim() == 2:
            x = x.unsqueeze(1)
            squeeze = True

        q = self._reshape_heads(self.q_linear(x))
        k = self._reshape_heads(self.k_linear(x))
        v = self._reshape_heads(self.v_linear(x))

        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        attn_weights = torch.softmax(attn_scores, dim=-1)
        context = torch.matmul(attn_weights, v)
        context = context.transpose(1, 2).contiguous().view(x.size(0), x.size(1), -1)

        out = self.out_linear(context)
        if squeeze:
            out = out.squeeze(1)
        return out


class CompressedGraphRuntime(nn.Module):
    """Executes the serialized graph from CubeModelMetadata."""

    def __init__(self, compressed_model: CompressedModel, cache_weights: bool = True):
        super().__init__()
        self.compressed_model = compressed_model
        self.graph: List[LayerGraphNode] = compressed_model.graph
        self.layers = nn.ModuleDict()
        self.exec_plan: List[Dict[str, Any]] = []

        attention_roles = {"attention_q", "attention_k", "attention_v", "attention_out"}
        attn_groups: Dict[str, Dict[str, LayerGraphNode]] = {}

        for node in self.graph:
            role = node.extra.get("role")
            module_name = node.extra.get("module_name", node.name)
            if role in attention_roles:
                base = module_name.rsplit(".", 1)[0]
                attn_groups.setdefault(base, {})[role] = node

        consumed_nodes = set()
        attn_modules: Dict[str, Dict[str, Any]] = {}
        for base, nodes in attn_groups.items():
            if not attention_roles.issubset(nodes.keys()):
                continue
            try:
                block = CubeAttentionBlock(
                    CubeLayer(
                        self.compressed_model.layers[nodes["attention_q"].name],
                        self.compressed_model.layers[nodes["attention_q"].name].original_shape,
                    ),
                    CubeLayer(
                        self.compressed_model.layers[nodes["attention_k"].name],
                        self.compressed_model.layers[nodes["attention_k"].name].original_shape,
                    ),
                    CubeLayer(
                        self.compressed_model.layers[nodes["attention_v"].name],
                        self.compressed_model.layers[nodes["attention_v"].name].original_shape,
                    ),
                    CubeLayer(
                        self.compressed_model.layers[nodes["attention_out"].name],
                        self.compressed_model.layers[nodes["attention_out"].name].original_shape,
                    ),
                    cache_weights=cache_weights,
                )
            except KeyError:
                continue

            key = base.replace(".", "_") + "_attn"
            self.layers[key] = block
            attn_modules[base] = {
                "key": key,
                "input": nodes["attention_q"].inputs[0],
                "output": nodes["attention_out"].outputs[0],
            }
            consumed_nodes.update(node.name for node in nodes.values())

        for node in self.graph:
            role = node.extra.get("role")
            module_name = node.extra.get("module_name", node.name)
            base = module_name.rsplit(".", 1)[0]
            if (
                role in attention_roles
                and base in attn_modules
                and not attn_modules[base].get("scheduled")
            ):
                attn_modules[base]["scheduled"] = True
                self.exec_plan.append(
                    {
                        "type": "attention",
                        "key": attn_modules[base]["key"],
                        "input": attn_modules[base]["input"],
                        "output": attn_modules[base]["output"],
                    }
                )
                continue

            if node.name in consumed_nodes:
                continue

            cube_layer = self.compressed_model.layers.get(node.name)
            if cube_layer is None:
                continue

            safe_name = node.name.replace(".", "_")
            self.layers[safe_name] = CachedCubeLinear(
                CubeLayer(cube_layer, cube_layer.original_shape), cache_weights=cache_weights
            )
            node.extra["module_key"] = safe_name
            self.exec_plan.append(
                {
                    "type": "linear",
                    "key": safe_name,
                    "input": node.inputs[0] if node.inputs else "input",
                    "output": node.outputs[0] if node.outputs else f"{node.name}_out",
                    "activation": node.activation,
                    "role": role,
                }
            )

        self.output_token = self.graph[-1].outputs[0] if self.graph else "input"

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        activations: Dict[str, torch.Tensor] = {"input": x}

        for op in self.exec_plan:
            module = self.layers[op["key"]]
            current = activations[op["input"]]
            out = module(current)

            if op["type"] == "linear":
                activation = op.get("activation") or get_activation_for_role(op.get("role"))
                if activation == "relu":
                    out = torch.relu(out)
                elif activation == "gelu":
                    out = torch.nn.functional.gelu(out)
                elif activation == "tanh":
                    out = torch.tanh(out)

            activations[op["output"]] = out

        return activations[self.output_token]

