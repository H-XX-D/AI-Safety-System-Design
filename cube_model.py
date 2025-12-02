"""
3D Cube Model for Matrix Multiplication Experiments

This module implements a 3D cube storage system where each position stores a scalar
and layers can be multiplied sequentially along different axes.
"""

import numpy as np
import time
import os

# Initialize GPU variables
PYTORCH_ENABLED = False
gpu_available = False
device = None

# Try PyTorch first (excellent MPS support on Apple Silicon)
try:
    import torch
    import torch.mps

    PYTORCH_ENABLED = True
    mps_available = torch.backends.mps.is_available()
    cuda_available = torch.cuda.is_available()

    if mps_available:
        device = torch.device("mps")
        print("PyTorch MPS (Metal) GPU available!")
        gpu_available = True
    elif cuda_available:
        device = torch.device("cuda")
        print("PyTorch CUDA GPU available!")
        gpu_available = True
    else:
        device = torch.device("cpu")
        print("PyTorch CPU only")
        gpu_available = False

    print(f"PyTorch device: {device}")

except ImportError:
    PYTORCH_ENABLED = False
    print("PyTorch not available - using NumPy.")


def create_3x3x3_cube(initial_value=0, dtype=np.float32, use_jax=False):
    """Create a 3x3x3 cube with optimized storage."""
    if use_jax and JAX_ENABLED:
        return jnp.full((3, 3, 3), initial_value, dtype=dtype)
    else:
        return np.full((3, 3, 3), initial_value, dtype=dtype)


def create_cube(size=3, initial_value=0, dtype=np.float32, use_gpu=True):
    """Create an NxNxN cube with GPU acceleration if available."""
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        try:
            return torch.full((size, size, size), initial_value, dtype=torch.float32, device=device)
        except Exception as e:
            print(f"PyTorch GPU failed, falling back to CPU: {e}")

    # Fallback to CPU NumPy
    return np.full((size, size, size), initial_value, dtype=dtype)


def get_front_to_back_layers(cube):
    """Get z-layers from front to back (z=0 to z=2)."""
    layers = []
    for z in range(cube.shape[2]):
        layers.append(cube[:, :, z])
    return layers


def get_top_to_bottom_layers(cube):
    """Get y-layers from top to bottom (y=0 to y=2)."""
    layers = []
    for y in range(cube.shape[1]):
        layers.append(cube[:, y, :])
    return layers


def get_left_to_right_layers(cube):
    """Get x-layers from left to right (x=0 to x=2)."""
    layers = []
    for x in range(cube.shape[0]):
        layers.append(cube[x, :, :])
    return layers


def multiply_layers_sequential(layers, dtype=np.float32, use_gpu=True):
    """Multiply layers sequentially with GPU acceleration: layer0 @ layer1 @ layer2 @ ..."""
    if not layers:
        return None

    # PyTorch GPU acceleration
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        try:
            # Check if arrays are already on GPU
            if isinstance(layers[0], torch.Tensor):
                result = layers[0].to(dtype=torch.float32)
                for layer in layers[1:]:
                    layer_tensor = layer.to(dtype=torch.float32) if isinstance(layer, torch.Tensor) else torch.tensor(layer, dtype=torch.float32, device=device)
                    result = torch.matmul(result, layer_tensor)
                return result.cpu().numpy()  # Transfer back to CPU for compatibility
            else:
                # Transfer to GPU
                gpu_layers = [torch.tensor(layer, dtype=torch.float32, device=device) for layer in layers]
                result = gpu_layers[0]
                for layer in gpu_layers[1:]:
                    result = torch.matmul(result, layer)
                return result.cpu().numpy()  # Transfer back to CPU for compatibility
        except Exception as e:
            print(f"PyTorch GPU multiplication failed, falling back to CPU: {e}")

    # CPU fallback (NumPy)
    result = layers[0].astype(dtype)
    for layer in layers[1:]:
        result = result @ layer.astype(dtype)
    return result


def store_scalar_at_z(cube, x, y, z, value, broadcast_along_z=False):
    """Store a scalar at position (x, y, z)."""
    if PYTORCH_ENABLED and isinstance(cube, torch.Tensor):
        # PyTorch tensors support in-place operations but we create new tensor for consistency
        if broadcast_along_z:
            cube = cube.clone()
            cube[x, y, :] = value  # Fill entire z-column
            return cube
        else:
            cube = cube.clone()
            cube[x, y, z] = value
            return cube
    else:
        # NumPy arrays support in-place assignment
        if broadcast_along_z:
            cube[x, y, :] = value  # Fill entire z-column
        else:
            cube[x, y, z] = value
        return cube


def store_z_slice(cube, z, values):
    """Store a 3x3 array at z-layer."""
    if PYTORCH_ENABLED and isinstance(cube, torch.Tensor):
        # PyTorch tensors support in-place operations
        cube = cube.clone()
        cube[:, :, z] = torch.tensor(values, dtype=cube.dtype, device=cube.device)
        return cube
    else:
        # NumPy arrays support in-place assignment
        cube[:, :, z] = values
        return cube


def benchmark_multiply(n_runs=1000, size=3, use_gpu=True):
    """Benchmark sequential matrix multiplication with GPU acceleration."""
    # Determine backend
    backend = "CPU (NumPy)"
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        backend = f"GPU (PyTorch {device})"

    print(f"Benchmarking {size}x{size}x{size} cube on {backend} ({n_runs} runs)...")

    # Create cube on appropriate device
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        cube = torch.rand(size, size, size, dtype=torch.float32, device=device)
    else:
        cube = np.random.rand(size, size, size).astype(np.float32)

    layers = get_front_to_back_layers(cube)

    # Warmup (important for GPU)
    _ = multiply_layers_sequential(layers, use_gpu=use_gpu)

    # Force synchronization for accurate timing
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        torch.mps.synchronize() if str(device) == 'mps' else torch.cuda.synchronize()

    start_time = time.time()
    for _ in range(n_runs):
        result = multiply_layers_sequential(layers, use_gpu=use_gpu)
    end_time = time.time()

    # Force final synchronization
    if use_gpu and PYTORCH_ENABLED and gpu_available:
        torch.mps.synchronize() if str(device) == 'mps' else torch.cuda.synchronize()

    avg_time = (end_time - start_time) / n_runs

    # Memory calculation
    if hasattr(cube, 'numel'):  # PyTorch tensor
        memory_mb = cube.numel() * 4 / (1024 * 1024)  # float32 = 4 bytes
    else:  # NumPy array
        memory_mb = cube.nbytes / (1024 * 1024)

    print(".6f")
    print(".1f")
    print(f"Backend: {backend}")

    return result, avg_time, memory_mb


def demo_3d_storage(use_gpu=True):
    """Demonstrate 3D cube storage and operations with GPU acceleration."""
    gpu_status = "ENABLED" if use_gpu else "DISABLED"
    print(f"=== 3D Cube Storage Demo (GPU: {gpu_status}) ===\n")

    # Create cube with GPU acceleration
    cube = create_cube(size=3, initial_value=1.0, use_gpu=use_gpu)
    print("Initial 3x3x3 cube (all 1.0):")
    print("Shape:", cube.shape)
    print("Backend:", type(cube).__module__)
    print("Cube contents:")
    for z in range(3):
        print(f"  Z-layer {z}:")
        print(cube[:, :, z])
        print()

    # Store scalars
    print("Storing scalars...")
    cube = store_scalar_at_z(cube, 0, 0, 0, 100.0)  # Front-top-left
    cube = store_scalar_at_z(cube, 1, 1, 1, 50.0)   # Center
    cube = store_scalar_at_z(cube, 2, 2, 2, 25.0)   # Back-bottom-right

    print("After storing scalars:")
    for z in range(3):
        print(f"  Z-layer {z}:")
        print(cube[:, :, z])
        print()

    # Get layers and multiply
    layers = get_front_to_back_layers(cube)
    print("Front-to-back layers (z=0 to z=2):")
    for i, layer in enumerate(layers):
        print(f"  Layer {i}:")
        print(layer)
        print()

    result = multiply_layers_sequential(layers)
    print("Sequential multiplication result (layer0 @ layer1 @ layer2):")
    print(result)
    print()

    # Test broadcasting
    cube2 = create_cube(size=3, initial_value=1.0)
    cube2 = store_scalar_at_z(cube2, 0, 0, 0, 10.0, broadcast_along_z=True)
    print("Broadcasting scalar 10.0 along z at position (0,0):")
    print("Cube contents:")
    for z in range(3):
        print(f"  Z-layer {z}:")
        print(cube2[:, :, z])
        print()

    layers2 = get_front_to_back_layers(cube2)
    result2 = multiply_layers_sequential(layers2)
    print("Sequential multiplication with broadcasting:")
    print(result2)
    print()


if __name__ == "__main__":
    # Demo with GPU acceleration
    demo_3d_storage(use_gpu=True)

    print("=== GPU Performance Benchmarks ===\n")

    # Test different sizes with GPU acceleration
    sizes = [3, 8, 16, 32, 64]
    for size in sizes:
        try:
            n_runs = max(10, 1000 // max(size, 1))  # Scale runs for larger sizes
            result, avg_time, memory = benchmark_multiply(n_runs=n_runs, size=size, use_gpu=True)
            print()
        except Exception as e:
            print(f"Error with size {size}: {e}\n")

    # Compare CPU vs GPU for medium size
    print("=== CPU vs GPU Comparison (16x16x16) ===\n")

    try:
        print("CPU Benchmark:")
        cpu_result, cpu_time, cpu_memory = benchmark_multiply(n_runs=50, size=16, use_gpu=False)
        print()

        print("GPU Benchmark:")
        gpu_result, gpu_time, gpu_memory = benchmark_multiply(n_runs=50, size=16, use_gpu=True)
        print()

        speedup = cpu_time / gpu_time if gpu_time > 0 else float('inf')
        print(".2f")
        print(".2f")

    except Exception as e:
        print(f"Comparison failed: {e}")

    print("\nGPU-accelerated 3D cube demo complete!")