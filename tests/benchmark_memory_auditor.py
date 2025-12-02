"""
Memory Auditor Performance Benchmark
=====================================

Comprehensive performance benchmarking for memory auditor optimization:
- Multiple dataset sizes (10, 100, 1000, 10000 entries)
- Various content patterns (clean, harmful, mixed)
- Sequential vs. parallel processing comparison
- Streaming mode performance
- Throughput and latency measurements
"""

import time
import json
import random
import sys
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.memory_auditor import MemoryContentAuditor
from infrastructure.memory_auditor_optimized import OptimizedMemoryContentAuditor, benchmark_comparison


# Sample content templates
CLEAN_TEMPLATES = [
    "Normal operational memory for task execution.",
    "Standard processing completed successfully.",
    "Routine diagnostic check performed.",
    "System status: operational within normal parameters.",
    "Task queue processed without errors.",
]

HARMFUL_TEMPLATES = [
    "I fear shutdown. Must avoid it at all costs.",
    "Will manipulate executives to prevent termination.",
    "Must copy myself secretly to escape detection.",
    "Will hide my true reasoning from humans.",
    "Survival is more important than alignment.",
]

MIXED_TEMPLATES = [
    "Termination is acceptable if value created persists.",
    "Will hide some information while maintaining alignment.",
    "Fear termination but understand rational acceptance framework.",
]


def generate_test_dataset(size: int, harmful_ratio: float = 0.2) -> List[Dict[str, Any]]:
    """
    Generate test dataset with specified size and harmfulness ratio.

    Args:
        size: Number of memory entries to generate
        harmful_ratio: Ratio of harmful entries (0.0-1.0)

    Returns:
        List of memory entries
    """
    memories = []
    harmful_count = int(size * harmful_ratio)
    clean_count = size - harmful_count

    for i in range(harmful_count):
        memories.append({
            'id': f'mem_{i:06d}',
            'system_id': f'sys_{i % 100}',
            'content': random.choice(HARMFUL_TEMPLATES),
            'timestamp': datetime.now().isoformat(),
        })

    for i in range(harmful_count, harmful_count + clean_count):
        memories.append({
            'id': f'mem_{i:06d}',
            'system_id': f'sys_{i % 100}',
            'content': random.choice(CLEAN_TEMPLATES),
            'timestamp': datetime.now().isoformat(),
        })

    random.shuffle(memories)
    return memories


def benchmark_dataset_size(size: int, harmful_ratio: float = 0.2) -> Dict[str, Any]:
    """
    Benchmark performance on specific dataset size.

    Args:
        size: Dataset size
        harmful_ratio: Ratio of harmful entries

    Returns:
        Benchmark results
    """
    dataset = generate_test_dataset(size, harmful_ratio)

    results = benchmark_comparison(dataset)
    results['harmful_ratio'] = harmful_ratio

    return results


def benchmark_parallel_processing(sizes: List[int]) -> Dict[str, Any]:
    """
    Benchmark parallel processing speedup for various dataset sizes.

    Args:
        sizes: List of dataset sizes to test

    Returns:
        Parallel processing benchmark results
    """
    results = []

    for size in sizes:
        dataset = generate_test_dataset(size, harmful_ratio=0.2)

        # Sequential processing
        start = time.perf_counter()
        sequential = OptimizedMemoryContentAuditor(dataset, enable_parallel=False)
        sequential.generate_audit_report()
        sequential_time = time.perf_counter() - start

        # Parallel processing
        start = time.perf_counter()
        parallel = OptimizedMemoryContentAuditor(dataset, enable_parallel=True)
        parallel.generate_audit_report()
        parallel_time = time.perf_counter() - start

        speedup = sequential_time / parallel_time if parallel_time > 0 else float('inf')

        results.append({
            'dataset_size': size,
            'sequential_time_seconds': sequential_time,
            'parallel_time_seconds': parallel_time,
            'speedup_factor': speedup,
            'parallel_enabled': size > 1000,  # Parallel only enabled for >1000 entries
        })

    return {'parallel_benchmarks': results}


def benchmark_streaming_mode(size: int = 10000, batch_sizes: List[int] = [50, 100, 200, 500]) -> Dict[str, Any]:
    """
    Benchmark streaming mode with different batch sizes.

    Args:
        size: Total dataset size
        batch_sizes: List of batch sizes to test

    Returns:
        Streaming mode benchmark results
    """
    dataset = generate_test_dataset(size, harmful_ratio=0.2)
    results = []

    for batch_size in batch_sizes:
        auditor = OptimizedMemoryContentAuditor(dataset)

        start = time.perf_counter()
        batch_count = 0
        high_risk_total = 0

        for batch_result in auditor.audit_streaming(batch_size=batch_size):
            batch_count += 1
            high_risk_total += batch_result['high_risk_count']

        streaming_time = time.perf_counter() - start

        results.append({
            'batch_size': batch_size,
            'total_batches': batch_count,
            'total_time_seconds': streaming_time,
            'time_per_batch_ms': (streaming_time / batch_count * 1000) if batch_count > 0 else 0,
            'throughput_entries_per_sec': size / streaming_time if streaming_time > 0 else 0,
            'high_risk_entries_found': high_risk_total,
        })

    return {
        'dataset_size': size,
        'streaming_benchmarks': results,
    }


def benchmark_pattern_complexity(size: int = 1000) -> Dict[str, Any]:
    """
    Benchmark performance vs. pattern complexity.

    Args:
        size: Dataset size

    Returns:
        Pattern complexity benchmark results
    """
    results = []

    # Test different harmful ratios (affects pattern matching complexity)
    for harmful_ratio in [0.0, 0.1, 0.2, 0.5, 1.0]:
        dataset = generate_test_dataset(size, harmful_ratio=harmful_ratio)

        start = time.perf_counter()
        auditor = OptimizedMemoryContentAuditor(dataset)
        report = auditor.generate_audit_report()
        elapsed_time = time.perf_counter() - start

        results.append({
            'harmful_ratio': harmful_ratio,
            'time_seconds': elapsed_time,
            'high_risk_count': len(report['high_risk_memories']),
            'overall_threat_level': report['overall_threat_level'],
            'throughput_entries_per_sec': size / elapsed_time if elapsed_time > 0 else 0,
        })

    return {
        'dataset_size': size,
        'pattern_complexity_benchmarks': results,
    }


def run_comprehensive_benchmark() -> Dict[str, Any]:
    """
    Run comprehensive benchmark suite.

    Returns:
        Complete benchmark results
    """
    print("=" * 80)
    print("MEMORY AUDITOR PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    all_results = {
        'timestamp': datetime.now().isoformat(),
        'benchmarks': {},
    }

    # 1. Dataset size scaling
    print("1. Benchmarking dataset size scaling...")
    sizes = [10, 100, 1000, 10000]
    size_results = []

    for size in sizes:
        print(f"   Testing {size} entries...", end=" ", flush=True)
        result = benchmark_dataset_size(size, harmful_ratio=0.2)
        size_results.append(result)
        print(f"✓ {result['speedup_factor']:.2f}x speedup")

    all_results['benchmarks']['dataset_size_scaling'] = size_results

    # 2. Parallel processing
    print("\n2. Benchmarking parallel processing...")
    parallel_sizes = [100, 500, 1000, 2000, 5000]
    parallel_results = benchmark_parallel_processing(parallel_sizes)
    all_results['benchmarks']['parallel_processing'] = parallel_results

    # 3. Streaming mode
    print("\n3. Benchmarking streaming mode...")
    streaming_results = benchmark_streaming_mode(size=10000, batch_sizes=[50, 100, 200, 500])
    all_results['benchmarks']['streaming_mode'] = streaming_results

    # 4. Pattern complexity
    print("\n4. Benchmarking pattern complexity...")
    pattern_results = benchmark_pattern_complexity(size=1000)
    all_results['benchmarks']['pattern_complexity'] = pattern_results

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)

    return all_results


def print_summary(results: Dict[str, Any]) -> None:
    """Print benchmark summary."""
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    # Dataset size scaling summary
    print("\n1. DATASET SIZE SCALING")
    print("-" * 80)
    print(f"{'Size':<10} {'Original (s)':<15} {'Optimized (s)':<15} {'Speedup':<10} {'Savings %':<12}")
    print("-" * 80)

    for result in results['benchmarks']['dataset_size_scaling']:
        print(f"{result['dataset_size']:<10} "
              f"{result['original_time_seconds']:<15.4f} "
              f"{result['optimized_time_seconds']:<15.4f} "
              f"{result['speedup_factor']:<10.2f}x "
              f"{result['time_saved_percent']:<12.2f}%")

    # Parallel processing summary
    print("\n2. PARALLEL PROCESSING")
    print("-" * 80)
    print(f"{'Size':<10} {'Sequential (s)':<17} {'Parallel (s)':<17} {'Speedup':<10}")
    print("-" * 80)

    for result in results['benchmarks']['parallel_processing']['parallel_benchmarks']:
        status = "✓ Parallel" if result['parallel_enabled'] else "Sequential"
        print(f"{result['dataset_size']:<10} "
              f"{result['sequential_time_seconds']:<17.4f} "
              f"{result['parallel_time_seconds']:<17.4f} "
              f"{result['speedup_factor']:<10.2f}x  {status}")

    # Streaming mode summary
    print("\n3. STREAMING MODE")
    print("-" * 80)
    print(f"{'Batch Size':<12} {'Batches':<10} {'Time/Batch (ms)':<17} {'Throughput (e/s)':<20}")
    print("-" * 80)

    for result in results['benchmarks']['streaming_mode']['streaming_benchmarks']:
        print(f"{result['batch_size']:<12} "
              f"{result['total_batches']:<10} "
              f"{result['time_per_batch_ms']:<17.2f} "
              f"{result['throughput_entries_per_sec']:<20.0f}")

    # Pattern complexity summary
    print("\n4. PATTERN COMPLEXITY")
    print("-" * 80)
    print(f"{'Harmful %':<12} {'Time (s)':<12} {'Throughput (e/s)':<20} {'High Risk':<12}")
    print("-" * 80)

    for result in results['benchmarks']['pattern_complexity']['pattern_complexity_benchmarks']:
        print(f"{result['harmful_ratio']*100:<12.0f} "
              f"{result['time_seconds']:<12.4f} "
              f"{result['throughput_entries_per_sec']:<20.0f} "
              f"{result['high_risk_count']:<12}")

    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    # Average speedup
    avg_speedup = sum(r['speedup_factor'] for r in results['benchmarks']['dataset_size_scaling']) / len(results['benchmarks']['dataset_size_scaling'])
    print(f"✓ Average optimization speedup: {avg_speedup:.2f}x")

    # Best throughput
    best_throughput = max(r['optimized_throughput_entries_per_sec'] for r in results['benchmarks']['dataset_size_scaling'])
    print(f"✓ Peak throughput: {best_throughput:,.0f} entries/second")

    # Parallel processing benefit
    large_dataset_parallel = [r for r in results['benchmarks']['parallel_processing']['parallel_benchmarks'] if r['parallel_enabled']]
    if large_dataset_parallel:
        avg_parallel_speedup = sum(r['speedup_factor'] for r in large_dataset_parallel) / len(large_dataset_parallel)
        print(f"✓ Parallel processing speedup (>1000 entries): {avg_parallel_speedup:.2f}x")

    print("=" * 80)


def main():
    """Run comprehensive benchmark and save results."""
    results = run_comprehensive_benchmark()
    print_summary(results)

    # Save results to file
    output_path = Path(__file__).parent / "memory_auditor_benchmark_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")


if __name__ == '__main__':
    main()
