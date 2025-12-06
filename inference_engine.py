"""
3D Cube Inference Engine

Loads and runs compressed neural networks using 3D cube reconstruction.
Provides GPU-accelerated inference with automatic decompression.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from model_converter import CompressedModel
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sys

# Import our systems
try:
    from models.cube_model import (
        get_front_to_back_layers, multiply_layers_sequential,
        PYTORCH_ENABLED, gpu_available, device
    )
    from model_converter import ModelConverter, CompressedModel, CubeLayer
    SYSTEMS_AVAILABLE = True
except ImportError:
    SYSTEMS_AVAILABLE = False

@dataclass
class InferenceResult:
    """Result of inference operation"""
    output: torch.Tensor
    latency_ms: float
    compression_ratio: float
    memory_usage_mb: float

class CubeLayer(nn.Module):
    """Neural network layer that uses 3D cube compressed weights"""

    def __init__(self, compressed_layer: 'CubeLayer', original_shape: Tuple[int, ...]):
        super().__init__()
        self.compressed_data = compressed_layer.compressed_data
        self.cube_shape = compressed_layer.cube_shape
        self.scale_factor = compressed_layer.scale_factor
        self.bias = compressed_layer.bias

        # Store original layer dimensions
        self.in_features, self.out_features = self._extract_dimensions(original_shape)

    def _extract_dimensions(self, shape: Tuple[int, ...]) -> Tuple[int, int]:
        """Extract input/output dimensions from weight shape"""
        if len(shape) == 2:  # Linear layer
            return shape[1], shape[0]  # (in_features, out_features)
        else:
            raise ValueError(f"Unsupported weight shape: {shape}")

    def reconstruct_weights(self) -> torch.Tensor:
        """Reconstruct original weight matrix from cube by simple reshape."""
        if isinstance(self.compressed_data, torch.Tensor):
            cube_tensor = self.compressed_data.to(dtype=torch.float32)
            target_device = cube_tensor.device
        else:
            target_device = (
                self.scale_factor.device
                if isinstance(self.scale_factor, torch.Tensor)
                else torch.device("cpu")
            )
            cube_tensor = torch.tensor(
                self.compressed_data, dtype=torch.float32, device=target_device
            )

        flat_result = cube_tensor.reshape(-1)
        required_elements = self.out_features * self.in_features

        if flat_result.numel() < required_elements:
            pad = torch.zeros(
                required_elements - flat_result.numel(),
                device=flat_result.device,
                dtype=flat_result.dtype,
            )
            flat_result = torch.cat([flat_result, pad], dim=0)
        else:
            flat_result = flat_result[:required_elements]

        weights = flat_result.view(self.out_features, self.in_features).to(target_device)

        # Apply scale factors (per-row or scalar)
        scale = self.scale_factor
        if isinstance(scale, torch.Tensor):
            scale = scale.to(device=weights.device, dtype=weights.dtype)
            if scale.numel() == 1:
                weights = weights * scale
            else:
                scale = scale.view(-1)
                if scale.shape[0] != weights.shape[0]:
                    # Broadcast if scale length mismatches (fallback)
                    scale = torch.nn.functional.pad(
                        scale, (0, max(0, weights.shape[0] - scale.shape[0]))
                    )[: weights.shape[0]]
                weights = weights * scale.view(-1, 1)
        else:
            weights = weights * float(scale)

        return weights

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Reconstruct weights on-the-fly
        weights = self.reconstruct_weights()

        # Standard linear transformation
        output = F.linear(x, weights, self.bias)
        return output

class CompressedMLP(nn.Module):
    """Multi-layer perceptron using compressed 3D cube weights"""

    def __init__(self, compressed_model: CompressedModel):
        super().__init__()
        self.compressed_model = compressed_model
        self.layers = nn.ModuleDict()

        # Create compressed layers
        for name, layer_data in compressed_model.layers.items():
            layer_name = name.replace('.weight', '')
            cube_layer = CubeLayer(layer_data, layer_data.original_shape)
            self.layers[layer_name] = cube_layer

        # Store activation functions (assume ReLU for hidden layers)
        self.num_layers = len(self.layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Flatten input if needed
        if x.dim() > 2:
            x = x.view(x.size(0), -1)

        # Forward pass through layers
        for i, (name, layer) in enumerate(self.layers.items()):
            x = layer(x)
            # Apply ReLU to all but last layer
            if i < self.num_layers - 1:
                x = F.relu(x)

        return x

class InferenceEngine:
    """High-performance inference engine for compressed 3D cube models"""

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and PYTORCH_ENABLED and gpu_available
        self.device = device if self.use_gpu else torch.device('cpu')
        self.converter = ModelConverter(use_gpu=self.use_gpu)

        print(f"Inference engine initialized - Device: {self.device}")

    def load_model(self, model_path: str) -> CompressedMLP:
        """Load compressed model from disk"""
        compressed_model = self.converter.load_compressed_model(model_path)
        model = CompressedMLP(compressed_model)

        if self.use_gpu:
            model = model.to(self.device)

        print(f"Loaded compressed model: {compressed_model.architecture}")
        print(f"  Original size: {compressed_model.original_size_mb:.1f} MB")
        print(f"  Compressed size: {compressed_model.compressed_size_mb:.1f} MB")
        print(f"  Compression ratio: {compressed_model.compression_ratio:.2f}x")

        return model

    def run_inference(self, model: nn.Module, input_data: torch.Tensor,
                     num_runs: int = 100) -> InferenceResult:
        """Run inference with performance measurement"""
        # Ensure input is on correct device
        if self.use_gpu:
            input_data = input_data.to(self.device)

        # Warmup
        with torch.no_grad():
            _ = model(input_data)

        # Synchronize for accurate timing
        if self.use_gpu:
            torch.mps.synchronize() if str(self.device) == 'mps' else torch.cuda.synchronize()

        # Benchmark inference
        start_time = time.time()

        with torch.no_grad():
            for _ in range(num_runs):
                output = model(input_data)

        end_time = time.time()

        # Synchronize again
        if self.use_gpu:
            torch.mps.synchronize() if str(self.device) == 'mps' else torch.cuda.synchronize()

        avg_latency = (end_time - start_time) / num_runs * 1000  # Convert to ms

        # Calculate memory usage (approximate)
        memory_mb = 0
        for param in model.parameters():
            memory_mb += param.numel() * param.element_size() / (1024 * 1024)

        # Get compression ratio from model
        if hasattr(model, 'compressed_model'):
            compression_ratio = model.compressed_model.compression_ratio
        else:
            compression_ratio = 1.0

        return InferenceResult(
            output=output,
            latency_ms=avg_latency,
            compression_ratio=compression_ratio,
            memory_usage_mb=memory_mb
        )

    def compare_models(self, original_model: nn.Module, compressed_model: nn.Module,
                      test_input: torch.Tensor, num_runs: int = 50) -> Dict[str, Any]:
        """Compare performance between original and compressed models"""

        print("Comparing original vs compressed model performance...")

        # Test original model
        original_result = self.run_inference(original_model, test_input, num_runs)

        # Test compressed model
        compressed_result = self.run_inference(compressed_model, test_input, num_runs)

        # Calculate accuracy difference
        with torch.no_grad():
            orig_output = original_result.output
            comp_output = compressed_result.output

            # For classification, compare argmax predictions
            if orig_output.shape[-1] > 1:  # Multi-class output
                orig_preds = torch.argmax(orig_output, dim=-1)
                comp_preds = torch.argmax(comp_output, dim=-1)
                accuracy = (orig_preds == comp_preds).float().mean().item() * 100
            else:
                # Regression - compare MSE
                mse = F.mse_loss(orig_output, comp_output).item()
                accuracy = 100 * (1 - min(mse / orig_output.var().item(), 1.0))  # Rough accuracy proxy

        return {
            'original_latency': original_result.latency_ms,
            'compressed_latency': compressed_result.latency_ms,
            'speedup': original_result.latency_ms / compressed_result.latency_ms,
            'compression_ratio': compressed_result.compression_ratio,
            'memory_savings': (1 - compressed_result.memory_usage_mb / original_result.memory_usage_mb) * 100,
            'accuracy_preservation': accuracy,
            'original_memory': original_result.memory_usage_mb,
            'compressed_memory': compressed_result.memory_usage_mb
        }

def create_demo_models():
    """Create demo models for testing"""

    class SimpleMLP(nn.Module):
        def __init__(self, input_size=784, hidden_sizes=[256, 128], output_size=10):
            super().__init__()
            layers = []
            prev_size = input_size

            for hidden_size in hidden_sizes:
                layers.extend([
                    nn.Linear(prev_size, hidden_size),
                    nn.ReLU()
                ])
                prev_size = hidden_size

            layers.append(nn.Linear(prev_size, output_size))
            self.model = nn.Sequential(*layers)

        def forward(self, x):
            return self.model(x)

    # Create original model
    original_model = SimpleMLP()

    # Create some dummy compressed model for demo
    converter = ModelConverter(use_gpu=True)
    compressed_model_data = converter.compress_pytorch_model(original_model)

    return original_model, compressed_model_data

def demo_inference():
    """Demonstrate the inference engine"""
    print("=== 3D Cube Inference Engine Demo ===\n")

    if not SYSTEMS_AVAILABLE:
        print("Error: Required systems not available")
        return

    # Initialize engine
    engine = InferenceEngine(use_gpu=True)

    # Create demo models
    original_model, compressed_data = create_demo_models()

    # Save and load compressed model
    model_path = "/tmp/demo_compressed_model.npz"
    converter = ModelConverter()
    converter.save_compressed_model(compressed_data, model_path)

    # Load compressed model
    compressed_model = engine.load_model(model_path)

    # Create test input
    batch_size = 32
    input_size = 784  # MNIST-like
    test_input = torch.randn(batch_size, input_size)

    print(f"\\nRunning inference on batch of {batch_size} samples...")

    # Run inference
    result = engine.run_inference(compressed_model, test_input, num_runs=10)

    print("\nInference Results:")
    print(f'  Latency: {result.latency_ms:.2f} ms')
    print(f'  Compression ratio: {result.compression_ratio:.1f}x')

    # Compare with original model
    print("\nComparing with original model...")
    comparison = engine.compare_models(original_model, compressed_model, test_input, num_runs=10)

    print("\nPerformance Comparison:")
    print(f"  Original latency: {comparison['original_latency']:.2f} ms")
    print(f"  Compressed latency: {comparison['compressed_latency']:.2f} ms")
    print(f"  Speedup: {comparison['speedup']:.2f}x")
    print(f"  Compression ratio: {comparison['compression_ratio']:.1f}x")
    print(f"  Memory savings: {comparison['memory_savings']:.1f}%")
    print(f"  Accuracy preservation: {comparison['accuracy_preservation']:.1f}%")

    print("\n✅ Inference engine demo complete!")
    return result, comparison

if __name__ == "__main__":
    demo_inference()
