"""
3D Cube Model Converter

Converts standard neural network models (PyTorch, TensorFlow) to compressed 3D cube format
for efficient storage and GPU-accelerated inference.
"""

import torch
import torch.nn as nn
import numpy as np
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import pickle
import sys

from cube_schema import (
    CubeModelMetadata,
    LayerMetadata as SchemaLayerMetadata,
    LayerGraphNode,
    CompressionStats,
)
from converters.layer_adapters import get_adapter_config, AdapterConfig

# Import our 3D cube system
try:
    from models.cube_model import (
        create_cube, store_scalar_at_z, get_front_to_back_layers,
        multiply_layers_sequential, PYTORCH_ENABLED, gpu_available, device
    )
    CUBE_AVAILABLE = True
except ImportError:
    CUBE_AVAILABLE = False

@dataclass
class CubeLayer:
    """Represents a compressed layer in 3D cube format"""
    name: str
    original_shape: Tuple[int, ...]
    cube_shape: Tuple[int, int, int]
    compressed_data: torch.Tensor
    scale_factor: torch.Tensor
    bias: Optional[torch.Tensor] = None
    layer_type: str = "Linear"
    tensor_role: str = "weight"
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CompressedModel:
    """Complete compressed model"""
    architecture: str
    layers: Dict[str, CubeLayer]
    metadata: Dict[str, Any]
    compression_ratio: float
    original_size_mb: float
    compressed_size_mb: float
    total_parameters: int = 0
    graph: List[LayerGraphNode] = field(default_factory=list)

class ModelConverter:
    """Converts neural network models to 3D cube compressed format"""

    def __init__(self, use_gpu: bool = True, preserve_last_linear: bool = True):
        self.use_gpu = use_gpu and PYTORCH_ENABLED and gpu_available
        self.preserve_last_linear = preserve_last_linear
        print(f"Model converter initialized - GPU: {self.use_gpu}")

    def quantize_to_ternary(
        self, weights: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Quantize weights to ternary {-1, 0, +1} with per-output scaling."""
        if weights.ndim != 2:
            flat = weights.view(weights.size(0), -1)
        else:
            flat = weights

        # Compute per-output-channel thresholds (adaptive to each row)
        abs_flat = torch.abs(flat)
        std_per_row = torch.std(flat, dim=1, keepdim=True)
        threshold = std_per_row * 0.7

        ternary = torch.zeros_like(flat)
        ternary[flat > threshold] = 1.0
        ternary[flat < -threshold] = -1.0

        # Per-row scale factor (mean magnitude above threshold, fallback to eps)
        # Least-squares optimal scale per row (project original onto ternary pattern)
        dot = torch.sum(flat * ternary, dim=1)
        denom = torch.sum(ternary * ternary, dim=1) + 1e-8
        scale = torch.abs(dot / denom)

        # Reshape back to original tensor layout
        ternary = ternary.view_as(weights)
        return ternary, scale

    def reshape_to_cube(self, weights: torch.Tensor, target_cube_size: Optional[int] = None) -> Tuple[torch.Tensor, Tuple[int, int, int]]:
        """Reshape weight matrix into 3D cube format"""
        flat_weights = weights.flatten()

        if target_cube_size is None:
            # Find optimal cube size (power of 2 for efficiency)
            total_elements = len(flat_weights)
            cube_size = int(np.ceil(total_elements ** (1/3)))

            # Round up to nearest power of 2 for efficiency
            cube_size = 2 ** int(np.ceil(np.log2(cube_size)))
        else:
            cube_size = target_cube_size

        # Pad or truncate to fit cube
        target_elements = cube_size ** 3

        if len(flat_weights) < target_elements:
            # Pad with zeros
            padding = torch.zeros(target_elements - len(flat_weights),
                                dtype=flat_weights.dtype,
                                device=flat_weights.device)
            cube_data = torch.cat([flat_weights, padding])
        else:
            # Truncate (take first N elements)
            cube_data = flat_weights[:target_elements]

        # Reshape to 3D cube
        cube = cube_data.view(cube_size, cube_size, cube_size)

        return cube, (cube_size, cube_size, cube_size)

    def compress_layer(
        self,
        name: str,
        weights: torch.Tensor,
        bias: Optional[torch.Tensor] = None,
        layer_type: str = "Linear",
        adapter_cfg: Optional[AdapterConfig] = None,
    ) -> CubeLayer:
        """Compress a single layer to 3D cube format"""
        print(f"Compressing layer: {name}, shape: {weights.shape}")

        # Quantize to ternary
        ternary_weights, scale_factor = self.quantize_to_ternary(weights)
        scale_factor = scale_factor.to(weights.device)
        scale_extra = {"scale_type": "vector" if scale_factor.numel() > 1 else "scalar"}

        # Reshape to 3D cube
        target_size = adapter_cfg.target_cube_size if adapter_cfg and adapter_cfg.target_cube_size else None
        cube, cube_shape = self.reshape_to_cube(ternary_weights, target_size)

        # Move to GPU if available
        if self.use_gpu:
            cube = cube.to(device)

        extra = scale_extra.copy()
        extra["quantized"] = True
        if adapter_cfg and adapter_cfg.extra:
            extra.update(adapter_cfg.extra)

        return CubeLayer(
            name=name,
            original_shape=tuple(weights.shape),
            cube_shape=cube_shape,
            compressed_data=cube,
            scale_factor=scale_factor,
            bias=bias,
            layer_type=layer_type,
            tensor_role=adapter_cfg.role if adapter_cfg else "weight",
            extra=extra,
        )

    def compress_dense_layer(
        self,
        name: str,
        weights: torch.Tensor,
        bias: Optional[torch.Tensor] = None,
        layer_type: str = "Linear",
        adapter_cfg: Optional[AdapterConfig] = None,
    ) -> CubeLayer:
        """Store weights without ternary quantization (for tiny layers)."""
        flat_weights = weights.flatten()
        cube_size = int(np.ceil(len(flat_weights) ** (1 / 3)))
        cube_size = 2 ** int(np.ceil(np.log2(cube_size)))
        target_elements = cube_size ** 3

        if len(flat_weights) < target_elements:
            padding = torch.zeros(
                target_elements - len(flat_weights),
                dtype=flat_weights.dtype,
                device=flat_weights.device,
            )
            cube_data = torch.cat([flat_weights, padding])
        else:
            cube_data = flat_weights[:target_elements]

        cube = cube_data.view(cube_size, cube_size, cube_size)
        if self.use_gpu:
            cube = cube.to(device)

        extra = {"scale_type": "scalar", "precision": "dense", "quantized": False}
        if adapter_cfg and adapter_cfg.extra:
            extra.update(adapter_cfg.extra)

        return CubeLayer(
            name=name,
            original_shape=tuple(weights.shape),
            cube_shape=(cube_size, cube_size, cube_size),
            compressed_data=cube,
            scale_factor=torch.tensor(1.0, device=cube.device),
            bias=bias,
            layer_type=layer_type,
            tensor_role=adapter_cfg.role if adapter_cfg else "weight",
            extra=extra,
        )

    def compress_pytorch_model(self, model: nn.Module) -> CompressedModel:
        """Convert PyTorch model to compressed 3D cube format"""
        print(f"Converting PyTorch model: {model.__class__.__name__}")

        compressed_layers = {}
        total_original_size = 0
        total_compressed_size = 0
        total_params = 0

        layer_modules = [
            (name, module)
            for name, module in model.named_modules()
            if hasattr(module, 'weight') and module.weight is not None
        ]

        graph_nodes: List[LayerGraphNode] = []
        previous_output = "input"

        for idx, (name, module) in enumerate(layer_modules):
            weights = module.weight.data
            bias = module.bias.data if hasattr(module, 'bias') and module.bias is not None else None
            layer_type = module.__class__.__name__
            total_params += weights.numel()

            adapter_cfg = get_adapter_config(name)
            is_last_linear = (
                self.preserve_last_linear
                and idx == len(layer_modules) - 1
                and isinstance(module, nn.Linear)
            )

            force_dense = is_last_linear or not adapter_cfg.quantized or adapter_cfg.role == "pre_classifier"

            if force_dense:
                compressed_layer = self.compress_dense_layer(
                    f"{name}.weight", weights, bias, layer_type=layer_type, adapter_cfg=adapter_cfg
                )
            else:
                compressed_layer = self.compress_layer(
                    f"{name}.weight", weights, bias, layer_type=layer_type, adapter_cfg=adapter_cfg
                )

            compressed_layers[compressed_layer.name] = compressed_layer

            node_name = compressed_layer.name
            node_output = f"{node_name}_out"
            graph_nodes.append(
                LayerGraphNode(
                    name=node_name,
                    layer_type=layer_type,
                    inputs=[previous_output],
                    outputs=[node_output],
                    activation=adapter_cfg.activation if adapter_cfg else None,
                    extra={
                        "position": idx,
                        "quantized": compressed_layer.extra.get("quantized", True),
                        "role": compressed_layer.tensor_role,
                        "module_name": name,
                    },
                )
            )
            previous_output = node_output

            original_size = weights.numel() * weights.element_size()
            if compressed_layer.extra.get("quantized", True):
                per_element_bytes = 0.25  # stored as 2 bits logically
            else:
                per_element_bytes = compressed_layer.compressed_data.element_size()
            compressed_size = compressed_layer.compressed_data.numel() * per_element_bytes

            total_original_size += original_size
            total_compressed_size += compressed_size

            print(f"  Layer {name}: {weights.shape} -> {compressed_layer.cube_shape} cube")

        compression_ratio = total_original_size / total_compressed_size

        return CompressedModel(
            architecture=model.__class__.__name__,
            layers=compressed_layers,
            metadata={
                'framework': 'PyTorch',
                'quantization': 'ternary',
                'cube_format': '3D_morton',
                'gpu_accelerated': self.use_gpu,
                'model_name': model.__class__.__name__,
            },
            compression_ratio=compression_ratio,
            original_size_mb=total_original_size / (1024 * 1024),
            compressed_size_mb=total_compressed_size / (1024 * 1024),
            total_parameters=total_params,
            graph=graph_nodes,
        )

    def save_compressed_model(self, model: CompressedModel, filepath: str):
        """Save compressed model to disk using JSON + binary format"""
        import json

        framework = model.metadata.get('framework', 'PyTorch')
        quantization = model.metadata.get('quantization', 'ternary')
        cube_format = model.metadata.get('cube_format', '3D_morton')
        gpu_accelerated = model.metadata.get('gpu_accelerated', False)

        # Prepare binary data and schema metadata
        binary_data = {}
        schema_layers = {}

        for name, layer in model.layers.items():
            if isinstance(layer.scale_factor, torch.Tensor):
                scale_value = layer.scale_factor.detach().cpu().tolist()
                scale_type = "vector" if isinstance(scale_value, list) else "scalar"
            else:
                scale_value = layer.scale_factor
                scale_type = "scalar"

            layer_extra = dict(layer.extra or {})
            layer_extra.setdefault("scale_type", scale_type)

            schema_layers[name] = SchemaLayerMetadata(
                name=layer.name,
                layer_type=layer.layer_type,
                tensor_role=layer.tensor_role,
                original_shape=layer.original_shape,
                cube_shape=layer.cube_shape,
                quantization=quantization,
                scale_factor=scale_value,
                has_bias=layer.bias is not None,
                dtype=str(layer.compressed_data.dtype),
                extra=layer_extra,
            )

            binary_data[f'{name}_data'] = layer.compressed_data.cpu().numpy()
            if layer.bias is not None:
                binary_data[f'{name}_bias'] = layer.bias.cpu().numpy()

        metadata_doc = CubeModelMetadata(
            model_name=model.metadata.get('model_name', model.architecture),
            architecture=model.architecture,
            framework=framework,
            backend='cube',
            device='gpu' if gpu_accelerated else 'cpu',
            quantization=quantization,
            cube_format=cube_format,
            compression=CompressionStats(
                original_size_mb=model.original_size_mb,
                compressed_size_mb=model.compressed_size_mb,
                compression_ratio=model.compression_ratio,
                total_parameters=model.total_parameters,
            ),
            layers=schema_layers,
            graph=model.graph,
            extra=model.metadata,
        )

        # Save metadata as JSON
        json_path = filepath.replace('.npz', '.json')
        with open(json_path, 'w') as f:
            json.dump(metadata_doc.to_dict(), f, indent=2)

        # Save binary data as compressed numpy
        np.savez_compressed(filepath, **binary_data)
        print(f"Saved compressed model to: {filepath} (metadata: {json_path})")

    def load_compressed_model(self, filepath: str) -> CompressedModel:
        """Load compressed model from disk"""
        import json

        # Load metadata
        json_path = filepath.replace('.npz', '.json')
        with open(json_path, 'r') as f:
            metadata_doc = CubeModelMetadata.from_dict(json.load(f))

        # Load binary data
        binary_data = np.load(filepath)

        layers = {}
        for layer_name, layer_info in metadata_doc.layers.items():
            # Load compressed data
            data_key = f'{layer_name}_data'
            compressed_data = torch.tensor(binary_data[data_key])
            if self.use_gpu:
                compressed_data = compressed_data.to(device)

            # Load bias if present
            bias = None
            bias_key = f'{layer_name}_bias'
            if bias_key in binary_data:
                bias = torch.tensor(binary_data[bias_key])
                if self.use_gpu:
                    bias = bias.to(device)

            scale_value = layer_info.scale_factor
            scale_tensor = torch.tensor(scale_value, dtype=torch.float32)
            if self.use_gpu:
                scale_tensor = scale_tensor.to(device)

            layers[layer_name] = CubeLayer(
                name=layer_info.name,
                original_shape=layer_info.original_shape,
                cube_shape=layer_info.cube_shape,
                compressed_data=compressed_data,
                scale_factor=scale_tensor,
                bias=bias,
                layer_type=layer_info.layer_type,
                tensor_role=layer_info.tensor_role,
                extra=layer_info.extra or {},
            )

        base_metadata = {
            'framework': metadata_doc.framework,
            'quantization': metadata_doc.quantization,
            'cube_format': metadata_doc.cube_format,
            'gpu_accelerated': metadata_doc.device != 'cpu',
            'schema_version': metadata_doc.schema_version,
            'graph': [node.to_dict() for node in metadata_doc.graph],
        }
        base_metadata.update(metadata_doc.extra or {})

        return CompressedModel(
            architecture=metadata_doc.architecture,
            layers=layers,
            metadata=base_metadata,
            compression_ratio=metadata_doc.compression.compression_ratio,
            original_size_mb=metadata_doc.compression.original_size_mb,
            compressed_size_mb=metadata_doc.compression.compressed_size_mb,
            total_parameters=metadata_doc.compression.total_parameters,
             graph=metadata_doc.graph,
        )

# Example usage and testing
def create_test_model():
    """Create a simple test model for demonstration"""
    class SimpleMLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(784, 256)
            self.fc2 = nn.Linear(256, 128)
            self.fc3 = nn.Linear(128, 10)

        def forward(self, x):
            return self.fc3(torch.relu(self.fc2(torch.relu(self.fc1(x)))))

    return SimpleMLP()

def demo_conversion():
    """Demonstrate model conversion"""
    print("=== 3D Cube Model Conversion Demo ===\n")

    # Create test model
    model = create_test_model()
    print(f"Original model: {model}")

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Total parameters: {total_params:,}")

    # Convert to compressed format
    converter = ModelConverter(use_gpu=True)
    compressed_model = converter.compress_pytorch_model(model)

    print("\nCompression Results:")
    print(f"  Original size: {compressed_model.original_size_mb:.2f} MB")
    print(f"  Compressed size: {compressed_model.compressed_size_mb:.1f} MB")
    print(f"  Compression ratio: {compressed_model.compression_ratio:.1f}x")

    # Save and reload
    save_path = "/tmp/compressed_model.npz"
    converter.save_compressed_model(compressed_model, save_path)

    loaded_model = converter.load_compressed_model(save_path)
    print("\nModel successfully saved and loaded!")

    return compressed_model, loaded_model

if __name__ == "__main__":
    if not CUBE_AVAILABLE:
        print("Error: 3D cube system not available. Please run from project root.")
        sys.exit(1)

    demo_conversion()
