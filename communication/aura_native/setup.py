"""
AURA Native Compression Extension - Build Configuration

Build for Jetson Orin (ARM64):
    CFLAGS="-O3 -march=armv8.2-a+crypto" python setup.py build_ext --inplace

Build for generic ARM64:
    CFLAGS="-O3 -march=armv8-a" python setup.py build_ext --inplace

Build for x86_64 (development):
    python setup.py build_ext --inplace

Install:
    pip install -e .
"""

import os
import platform
try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension

# Detect platform
machine = platform.machine().lower()
is_arm64 = machine in ('aarch64', 'arm64')
is_orin = os.path.exists('/etc/nv_tegra_release') or 'tegra' in platform.release().lower()

# Base compiler flags
extra_compile_args = ['-O3', '-Wall', '-Wextra']

# Platform-specific optimizations
if is_arm64:
    if is_orin:
        # Jetson Orin: ARM v8.2-A with crypto extensions
        # Cortex-A78AE cores for maximum performance
        extra_compile_args.extend([
            '-march=armv8.2-a+crypto',
            '-mtune=cortex-a78ae',  # Orin's ARM cores
            '-ffast-math',          # Fast FP for snprintf etc
            '-funroll-loops',       # Unroll small loops
            '-fomit-frame-pointer', # Free up a register
            '-DARM_CRYPTO',
        ])
        print("Building for Jetson Orin (ARM v8.2-A + crypto, tuned for Cortex-A78AE)")
    else:
        # Generic ARM64
        extra_compile_args.extend([
            '-march=armv8-a',
            '-mtune=generic',
        ])
        print("Building for generic ARM64")
else:
    # x86_64 development build
    extra_compile_args.extend([
        '-march=native',
        '-mtune=native',
    ])
    print(f"Building for {machine} (development)")

# Link-time optimization for extra speed
if os.environ.get('AURA_LTO', '0') == '1':
    extra_compile_args.append('-flto')
    print("Link-time optimization enabled")

# Extension definition
aura_compress_ext = Extension(
    'aura_compress',
    sources=['aura_compress.c'],
    extra_compile_args=extra_compile_args,
    extra_link_args=['-O3'],
)

setup(
    name='aura_compress',
    version='1.0.0',
    description='Native AURA compression for AI Safety System',
    author='AI Safety System',
    ext_modules=[aura_compress_ext],
    python_requires='>=3.8',
)
