"""
Cube compression metadata schema.

Defines a universal, versioned metadata structure describing how tensors are
quantized and packed into 3D cubes so that converters and runtimes can remain
decoupled from specific model architectures.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple, Any, Union, List, Optional

SCHEMA_VERSION = "1.0.0"


def _tuple_to_list(value):
    if isinstance(value, tuple):
        return list(value)
    return value


def _list_to_tuple(value):
    if isinstance(value, list):
        return tuple(value)
    return value


@dataclass
class CompressionStats:
    """Aggregate compression information for the entire model artifact."""

    original_size_mb: float
    compressed_size_mb: float
    compression_ratio: float
    total_parameters: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompressionStats":
        return cls(**data)


@dataclass
class LayerMetadata:
    """Metadata required to reconstruct a single tensor from cube storage."""

    name: str
    layer_type: str
    tensor_role: str
    original_shape: Tuple[int, ...]
    cube_shape: Tuple[int, int, int]
    quantization: str
    scale_factor: Union[float, List[float]]
    has_bias: bool
    dtype: str = "float32"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["original_shape"] = _tuple_to_list(self.original_shape)
        data["cube_shape"] = _tuple_to_list(self.cube_shape)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerMetadata":
        payload = dict(data)
        payload["original_shape"] = _list_to_tuple(payload["original_shape"])
        payload["cube_shape"] = _list_to_tuple(payload["cube_shape"])
        return cls(**payload)


@dataclass
class LayerGraphNode:
    """Describes the execution graph for a single layer/operator."""

    name: str
    layer_type: str
    inputs: List[str]
    outputs: List[str]
    activation: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LayerGraphNode":
        return cls(**data)


@dataclass
class CubeModelMetadata:
    """
    Top-level schema document describing a compressed model artifact.
    """

    model_name: str
    architecture: str
    framework: str
    backend: str
    device: str
    quantization: str
    cube_format: str
    compression: CompressionStats
    layers: Dict[str, LayerMetadata]
    graph: List[LayerGraphNode] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_name": self.model_name,
            "architecture": self.architecture,
            "framework": self.framework,
            "backend": self.backend,
            "device": self.device,
            "quantization": self.quantization,
            "cube_format": self.cube_format,
            "compression": self.compression.to_dict(),
            "layers": {name: meta.to_dict() for name, meta in self.layers.items()},
            "graph": [node.to_dict() for node in self.graph],
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CubeModelMetadata":
        layers = {
            name: LayerMetadata.from_dict(layer_meta)
            for name, layer_meta in data.get("layers", {}).items()
        }
        compression = CompressionStats.from_dict(data["compression"])
        return cls(
            model_name=data["model_name"],
            architecture=data["architecture"],
            framework=data["framework"],
            backend=data.get("backend", "cube"),
            device=data.get("device", "cpu"),
            quantization=data.get("quantization", "ternary"),
            cube_format=data.get("cube_format", "3D_morton"),
            compression=compression,
            layers=layers,
            graph=[LayerGraphNode.from_dict(node) for node in data.get("graph", [])],
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            extra=data.get("extra", {}),
        )


def build_metadata_dict(metadata: CubeModelMetadata) -> Dict[str, Any]:
    """Helper for callers that only need the raw dict representation."""
    return metadata.to_dict()


def load_metadata_dict(payload: Dict[str, Any]) -> CubeModelMetadata:
    """Helper that converts a dict back into the strongly-typed schema."""
    return CubeModelMetadata.from_dict(payload)

