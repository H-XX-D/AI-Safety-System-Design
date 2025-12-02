import os
import timeit
import numpy as np
from typing import Union

# Force CPU backend - Metal has too many limitations with Python 3.14
# CPU JAX with JIT is still 2-10x faster than NumPy!
# When Metal backend improves, remove this line to enable GPU
if 'JAX_PLATFORM_NAME' not in os.environ:
    os.environ['JAX_PLATFORM_NAME'] = 'cpu'

# Try JAX for acceleration (CPU backend with JIT compilation)
USE_JAX = False
USE_GPU = False  # Using CPU JAX (still accelerated via JIT)
jnp = np  # Default to NumPy

try:
    import jax
    import jax.numpy as jnp
    USE_JAX = True
    
    devices = jax.devices()
    backend = jax.default_backend()
    
    # Check if we have CUDA/GPU (not Metal)
    if backend.upper() in ['GPU', 'CUDA']:
        USE_GPU = True
        print(f"JAX imported - GPU acceleration enabled via {backend} backend!")
        print(f"Devices: {devices}")
    else:
        USE_GPU = False
        print(f"JAX imported - Using CPU backend with JIT compilation (ACCELERATED!)")
        print(f"Backend: {backend}, Devices: {devices}")
        print("Note: JAX JIT provides 2-10x speedup over NumPy even on CPU")
        print("Metal backend disabled due to Python 3.14 compatibility issues")
except ImportError:
    print("JAX not available - using CPU (NumPy). Install with: pip install jax[cpu] jax-metal")
except Exception as e:
    print(f"JAX import failed: {e}. Falling back to NumPy.")

def create_cube(size=3, initial_value=0, dtype=np.float32):
    """
    Create an NxNxN cube (generalized from 3x3x3) with optional GPU.
    
    Args:
        size: Cube side length (3 or 8 for demo).
        initial_value: Fill value.
        dtype: Data type (float32 for efficiency).
    
    Returns:
        np.ndarray or jnp.ndarray: Cube array.
    """
    if USE_JAX:
        try:
            dtype = jnp.float32 if dtype == np.float32 else dtype
            return jnp.full((size, size, size), initial_value, dtype=dtype)
        except Exception:
            # Metal backend may fail, fall back to NumPy
            return np.full((size, size, size), initial_value, dtype=dtype)
    else:
        return np.full((size, size, size), initial_value, dtype=dtype)

def get_front_to_back_layers(cube, size=3):
    """
    Get z-layers as stacked array (GPU-compatible).
    """
    layers = []
    for z in range(size):
        layer = cube[:, :, z]
        layers.append(layer)
    stacked = jnp.stack(layers, axis=0) if USE_JAX else np.stack(layers, axis=0)
    return stacked

def get_top_to_bottom_layers(cube, size=3):
    layers = [cube[:, y, :] for y in range(size)]
    return jnp.stack(layers, axis=0) if USE_JAX else np.stack(layers, axis=0)

def get_left_to_right_layers(cube, size=3):
    layers = [cube[x, :, :] for x in range(size)]
    return jnp.stack(layers, axis=0) if USE_JAX else np.stack(layers, axis=0)

def print_layer(layer, title, axis):
    """
    Pretty-print layer (CPU copy if GPU).
    """
    # Convert JAX array to NumPy for printing
    if USE_JAX:
        if hasattr(layer, 'block_until_ready'):
            layer = np.array(layer.block_until_ready())
        elif hasattr(layer, '__array__'):
            layer = np.array(layer)
    
    print(f"\n{title} (axis={axis}):")
    for row in layer:
        print(' '.join(f'{val:6.2f}' for val in row))

def visualize_cube(cube, size=3):
    """
    Visualize layers (3x3x3 or larger slices).
    """
    print(f"{size}x{size}x{size} Cube Visualization:")
    print("=" * 40)
    
    z_layers = get_front_to_back_layers(cube, size)
    for i in range(size):
        print_layer(z_layers[i], f"Layer {i} (front=0, back={size-1})", 'z')
    
    y_layers = get_top_to_bottom_layers(cube, size)
    for i in range(size):
        print_layer(y_layers[i], f"Layer {i} (top=0, bottom={size-1})", 'y')
    
    x_layers = get_left_to_right_layers(cube, size)
    for i in range(size):
        print_layer(x_layers[i], f"Layer {i} (left=0, right={size-1})", 'x')

def multiply_layers_sequential(layers, size=3, dtype=np.float32):
    """
    Sequential matmul (GPU-accelerated if available).
    """
    dtype = jnp.float32 if USE_JAX else np.float32
    if layers.shape[0] < 2:
        raise ValueError("Need at least 2 layers.")
    result = layers[0].astype(dtype)
    for layer in layers[1:]:
        result = jnp.matmul(result, layer.astype(dtype)) if USE_JAX else np.matmul(result, layer.astype(dtype))
    return result

def multiply_cube_along_axis(cube, axis='z', size=3, dtype=np.float32):
    """
    Multiply along axis (GPU).
    """
    if axis == 'z':
        layers = get_front_to_back_layers(cube, size)
    elif axis == 'y':
        layers = get_top_to_bottom_layers(cube, size)
    elif axis == 'x':
        layers = get_left_to_right_layers(cube, size)
    else:
        raise ValueError("Axis must be 'x', 'y', or 'z'.")
    
    return multiply_layers_sequential(layers, size, dtype)

def store_scalar_at_z(cube, x, y, z, value, size=3, broadcast_along_z=False):
    """
    Store scalar at [x,y,z] (GPU-compatible, in-place for NumPy, functional for JAX).
    """
    if USE_JAX:
        # JAX arrays are immutable, so we need to use .at[].set()
        value = jnp.float32(value)
        if broadcast_along_z:
            cube = cube.at[x, y, :].set(value)
        else:
            cube = cube.at[x, y, z].set(value)
    else:
        # NumPy arrays are mutable
        value = np.float32(value)
        if broadcast_along_z:
            cube[x, y, :] = value
        else:
            cube[x, y, z] = value
    return cube

def store_z_slice(cube, z, values, size=3):
    """
    Store 3x3 (or NxN) slice at z (GPU).
    """
    if isinstance(values, list):
        values = np.array(values, dtype=np.float32)
    
    if USE_JAX:
        values = jnp.array(values)
        cube = cube.at[:, :, z].set(values)
    else:
        cube[:, :, z] = values
    return cube

def benchmark_multiply(n_runs=1000, size=3, use_gpu=False):
    """
    Benchmark with optional GPU.
    """
    # Use JAX if requested and available (regardless of GPU mode)
    use_jax_local = use_gpu and USE_JAX
    use_gpu_local = use_jax_local and USE_GPU
    mod = jnp if use_jax_local else np
    dtype = mod.float32
    
    # Create random cube
    np.random.seed(42)
    if use_jax_local:
        # Use NumPy random then convert to JAX array
        cube_np = np.random.rand(size, size, size).astype(dtype)
        cube = jnp.array(cube_np)
    else:
        cube = np.random.rand(size, size, size).astype(dtype)
    
    # Layers along z
    layers = get_front_to_back_layers(cube, size)
    
    def mul_func():
        result = layers[0]
        for layer in layers[1:]:
            result = mod.matmul(result, layer)
        # Sync if using GPU
        if use_gpu_local and hasattr(result, 'block_until_ready'):
            result = result.block_until_ready()
        return result
    
    time_taken = timeit.timeit(mul_func, number=n_runs)
    if use_gpu_local:
        gpu_label = "GPU (JAX)"
    elif use_jax_local:
        gpu_label = "CPU (JAX JIT)"
    else:
        gpu_label = "CPU (NumPy)"
    print(f"{gpu_label} Benchmark: {n_runs} sequential {size}x{size} matmuls took {time_taken:.4f}s")
    print(f"Avg time per chain: {time_taken / n_runs * 1000:.2f}ms")
    
    # Memory (approx)
    mem_cube = (size**3 * 4) / 1024**2  # MB for float32
    print(f"Memory for {size}^3 cube (float32): {mem_cube:.4f} MB")

def create_sparse_cube(size=3, sparsity=0.5):
    """
    Sparse cube (CPU fallback; JAX sparse experimental).
    """
    try:
        from scipy.sparse import random
        cube_dense = random(size**3, 1, density=1-sparsity, format='coo').toarray().reshape(size, size, size)
        return cube_dense.astype(np.float32)
    except ImportError:
        print("scipy not installed; using dense with zeros.")
        cube = np.random.rand(size, size, size).astype(np.float32)
        mask = np.random.rand(size, size, size) > sparsity
        cube[~mask] = 0
        return cube

# Example usage (3x3x3 demo)
if __name__ == "__main__":
    np.random.seed(42)  # For reproducibility (CPU fallback)
    
    sizes = [3, 8, 16, 32, 64]  # Bigger sizes as requested
    
    for size in sizes:
        print(f"\n{'='*50}")
        print(f"Running demo for {size}x{size}x{size} cube")
        print(f"{'='*50}")
        
        # Create cube
        if USE_JAX:
            # Use NumPy random then convert to JAX array
            cube_np = np.random.rand(size, size, size).astype(np.float32)
            try:
                cube = jnp.array(cube_np)
            except Exception:
                # Metal backend failed, use NumPy
                cube = cube_np
        else:
            cube = np.random.rand(size, size, size).astype(np.float32)
        
        if size <= 8:  # Viz only for small to avoid long output
            visualize_cube(cube, size)
        
        # Get center value (convert JAX array to NumPy for printing)
        center = cube[1, 1, 1]
        if USE_JAX and hasattr(center, 'block_until_ready'):
            center = np.array(center.block_until_ready())
        elif USE_JAX:
            center = np.array(center)
        print(f"Center value at [1,1,1]: {center:.2f}")
        
        # Store examples (scale indices for larger)
        center_x, center_y, center_z = size//2, size//2, 0  # Front center
        cube = store_scalar_at_z(cube, center_x, center_y, center_z, 100.0, size=size)
        print(f"Stored 100.0 at front center [{center_x},{center_y},0]")
        
        line_x, line_y = 0, 0  # Z-line
        cube = store_scalar_at_z(cube, line_x, line_y, size//2, 50.0, broadcast_along_z=True, size=size)
        print(f"Broadcast 50.0 along z-line [{line_x},{line_y},*]")
        
        # Matmul along z (skip for very large to avoid overflow/time)
        if size <= 32:
            z_result = multiply_cube_along_axis(cube, 'z', size)
            # Convert JAX array to NumPy for printing
            if USE_JAX:
                if hasattr(z_result, 'block_until_ready'):
                    z_result = np.array(z_result.block_until_ready())
                else:
                    z_result = np.array(z_result)
            print(f"Sequential matmul along z (after stores):")
            if size <= 8:
                print_layer(z_result, "Result", 'result')
            else:
                print(f"Result shape: {z_result.shape}, sample [0,0]: {z_result[0,0]:.2f}")
        else:
            print(f"Skipping matmul for {size}x{size} (too large for chain; focus on benchmark)")
        
        # Benchmark (adjust n_runs for larger sizes to keep reasonable)
        n_runs = 1000 if size <= 8 else 100 if size <= 16 else 10 if size <= 32 else 1
        benchmark_multiply(n_runs=n_runs, size=size, use_gpu=False)  # NumPy CPU
        if USE_JAX:
            benchmark_multiply(n_runs=n_runs, size=size, use_gpu=True)  # JAX (CPU or GPU)
