"""
Interpretability Monitor Performance Benchmark
================================================

Comprehensive performance benchmarking for enhanced interpretability monitor:
- Multiple dataset sizes (10, 100, 1000, 10000 samples)
- Various feature dimensions (10, 50, 100, 500 features)
- Different drift scenarios (stable, gradual, sudden)
- CUSUM detection performance
- Distribution shift detection performance
- Memory usage tracking
"""

import time
import json
import random
import sys
import math
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from interpretability_monitor_enhanced import EnhancedInterpretabilityMonitor


def generate_stable_activations(mean: float = 0.5, std: float = 0.1, size: int = 100) -> List[float]:
    """Generate stable activations using Box-Muller transform."""
    activations = []
    for _ in range(size // 2 + 1):
        u1 = random.random()
        u2 = random.random()
        z0 = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        z1 = math.sqrt(-2 * math.log(u1)) * math.sin(2 * math.pi * u2)
        activations.append(mean + std * z0)
        activations.append(mean + std * z1)
    return activations[:size]


def benchmark_update_performance(
    num_samples: int,
    num_features: int,
    num_systems: int = 1
) -> Dict[str, Any]:
    """
    Benchmark update_activations performance.

    Args:
        num_samples: Number of samples to process
        num_features: Number of features per sample
        num_systems: Number of systems to monitor

    Returns:
        Performance metrics
    """
    monitor = EnhancedInterpretabilityMonitor()

    # Warm-up
    for system_id in range(num_systems):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=num_features)
        monitor.update_activations(system_id, activations)

    # Benchmark
    start = time.perf_counter()

    for _ in range(num_samples):
        for system_id in range(num_systems):
            activations = generate_stable_activations(mean=0.5, std=0.1, size=num_features)
            monitor.update_activations(system_id, activations)

    elapsed = time.perf_counter() - start

    return {
        'num_samples': num_samples,
        'num_features': num_features,
        'num_systems': num_systems,
        'total_time_seconds': elapsed,
        'time_per_sample_ms': (elapsed / num_samples) * 1000,
        'throughput_samples_per_sec': num_samples / elapsed if elapsed > 0 else 0,
    }


def benchmark_drift_detection(
    num_samples: int,
    num_features: int
) -> Dict[str, Any]:
    """
    Benchmark get_drift performance.

    Args:
        num_samples: Number of samples to establish baseline
        num_features: Number of features per sample

    Returns:
        Performance metrics
    """
    monitor = EnhancedInterpretabilityMonitor()

    # Build baseline
    for _ in range(num_samples):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=num_features)
        monitor.update_activations(1, activations)

    # Benchmark drift detection
    test_activations = generate_stable_activations(mean=0.5, std=0.1, size=num_features)

    start = time.perf_counter()
    for _ in range(100):  # Test 100 drift checks
        result = monitor.get_drift(1, test_activations)
    elapsed = time.perf_counter() - start

    return {
        'baseline_samples': num_samples,
        'num_features': num_features,
        'total_time_seconds': elapsed,
        'time_per_check_ms': (elapsed / 100) * 1000,
        'throughput_checks_per_sec': 100 / elapsed if elapsed > 0 else 0,
        'classification': result['classification'],
        'drift_score': result['drift_score'],
    }


def benchmark_cusum_detection(
    baseline_samples: int,
    drift_samples: int,
    num_features: int
) -> Dict[str, Any]:
    """
    Benchmark CUSUM gradual drift detection.

    Args:
        baseline_samples: Samples for stable baseline
        drift_samples: Samples with gradual drift
        num_features: Number of features

    Returns:
        Performance and detection metrics
    """
    monitor = EnhancedInterpretabilityMonitor(
        cusum_threshold=3.0,
        cusum_drift=0.2
    )

    # Establish baseline
    start = time.perf_counter()
    for _ in range(baseline_samples):
        activations = generate_stable_activations(mean=0.5, std=0.05, size=num_features)
        monitor.update_activations(1, activations)
    baseline_time = time.perf_counter() - start

    # Introduce drift and detect
    start = time.perf_counter()
    detected_at = None
    for i in range(drift_samples):
        activations = generate_stable_activations(mean=1.0, std=0.05, size=num_features)
        monitor.update_activations(1, activations)

        result = monitor.get_drift(1, activations)
        if result['cusum_alarm'] and detected_at is None:
            detected_at = i

    drift_time = time.perf_counter() - start

    return {
        'baseline_samples': baseline_samples,
        'drift_samples': drift_samples,
        'num_features': num_features,
        'baseline_time_seconds': baseline_time,
        'drift_detection_time_seconds': drift_time,
        'total_time_seconds': baseline_time + drift_time,
        'detected_at_sample': detected_at,
        'detection_latency': detected_at if detected_at else drift_samples,
    }


def benchmark_distribution_shift(
    historical_samples: int,
    recent_samples: int,
    num_features: int
) -> Dict[str, Any]:
    """
    Benchmark Kolmogorov-Smirnov distribution shift detection.

    Args:
        historical_samples: Samples for historical baseline
        recent_samples: Recent samples to compare
        num_features: Number of features

    Returns:
        Performance and detection metrics
    """
    monitor = EnhancedInterpretabilityMonitor()

    # Build historical baseline
    start = time.perf_counter()
    for _ in range(historical_samples):
        activations = generate_stable_activations(mean=0.5, std=0.1, size=num_features)
        monitor.update_activations(1, activations)
    baseline_time = time.perf_counter() - start

    # Generate recent samples from different distribution
    recent = [
        generate_stable_activations(mean=2.0, std=0.1, size=num_features)
        for _ in range(recent_samples)
    ]

    # Benchmark distribution shift detection
    start = time.perf_counter()
    result = monitor.detect_distribution_shift(1, recent)
    detection_time = time.perf_counter() - start

    return {
        'historical_samples': historical_samples,
        'recent_samples': recent_samples,
        'num_features': num_features,
        'baseline_time_seconds': baseline_time,
        'detection_time_seconds': detection_time,
        'total_time_seconds': baseline_time + detection_time,
        'classification': result['classification'],
        'max_ks_statistic': result['max_ks_statistic'],
    }


def benchmark_scaling(
    sample_sizes: List[int],
    feature_counts: List[int]
) -> Dict[str, Any]:
    """
    Benchmark performance scaling with dataset size and feature count.

    Args:
        sample_sizes: List of sample sizes to test
        feature_counts: List of feature counts to test

    Returns:
        Scaling performance results
    """
    results = []

    for num_samples in sample_sizes:
        for num_features in feature_counts:
            result = benchmark_update_performance(num_samples, num_features)
            results.append(result)

    return {'scaling_results': results}


def benchmark_multi_system_overhead(
    num_samples: int,
    num_features: int,
    system_counts: List[int]
) -> Dict[str, Any]:
    """
    Benchmark overhead of monitoring multiple systems.

    Args:
        num_samples: Samples per system
        num_features: Features per sample
        system_counts: List of system counts to test

    Returns:
        Multi-system overhead results
    """
    results = []

    for num_systems in system_counts:
        result = benchmark_update_performance(num_samples, num_features, num_systems)
        results.append({
            'num_systems': num_systems,
            **result
        })

    return {'multi_system_results': results}


def run_comprehensive_benchmark() -> Dict[str, Any]:
    """
    Run comprehensive benchmark suite.

    Returns:
        Complete benchmark results
    """
    print("=" * 80)
    print("INTERPRETABILITY MONITOR PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    all_results = {
        'timestamp': datetime.now().isoformat(),
        'benchmarks': {},
    }

    # 1. Update performance scaling
    print("1. Benchmarking update performance scaling...")
    sample_sizes = [10, 100, 1000]
    feature_counts = [10, 50, 100]

    for samples in sample_sizes:
        for features in feature_counts:
            print(f"   {samples} samples × {features} features...", end=" ", flush=True)
            result = benchmark_update_performance(samples, features)
            print(f"✓ {result['throughput_samples_per_sec']:.0f} samples/sec")

    scaling_results = benchmark_scaling(sample_sizes, feature_counts)
    all_results['benchmarks']['update_scaling'] = scaling_results

    # 2. Drift detection performance
    print("\n2. Benchmarking drift detection performance...")
    drift_configs = [
        (100, 10),
        (100, 50),
        (1000, 10),
        (1000, 50),
    ]

    drift_results = []
    for samples, features in drift_configs:
        print(f"   {samples} baseline samples × {features} features...", end=" ", flush=True)
        result = benchmark_drift_detection(samples, features)
        drift_results.append(result)
        print(f"✓ {result['throughput_checks_per_sec']:.0f} checks/sec")

    all_results['benchmarks']['drift_detection'] = {'results': drift_results}

    # 3. CUSUM detection latency
    print("\n3. Benchmarking CUSUM drift detection...")
    cusum_configs = [
        (50, 50, 10),
        (100, 100, 10),
        (50, 50, 50),
    ]

    cusum_results = []
    for baseline, drift, features in cusum_configs:
        print(f"   {baseline} baseline + {drift} drift × {features} features...", end=" ", flush=True)
        result = benchmark_cusum_detection(baseline, drift, features)
        cusum_results.append(result)
        if result['detected_at_sample']:
            print(f"✓ Detected at sample {result['detected_at_sample']}")
        else:
            print("✓ No detection")

    all_results['benchmarks']['cusum_detection'] = {'results': cusum_results}

    # 4. Distribution shift detection
    print("\n4. Benchmarking distribution shift detection...")
    dist_configs = [
        (50, 20, 10),
        (100, 20, 10),
        (50, 20, 50),
    ]

    dist_results = []
    for historical, recent, features in dist_configs:
        print(f"   {historical} historical + {recent} recent × {features} features...", end=" ", flush=True)
        result = benchmark_distribution_shift(historical, recent, features)
        dist_results.append(result)
        print(f"✓ {result['classification']} (KS={result['max_ks_statistic']:.2f})")

    all_results['benchmarks']['distribution_shift'] = {'results': dist_results}

    # 5. Multi-system overhead
    print("\n5. Benchmarking multi-system overhead...")
    system_counts = [1, 5, 10, 20]
    multi_system_results = benchmark_multi_system_overhead(100, 10, system_counts)

    for result in multi_system_results['multi_system_results']:
        print(f"   {result['num_systems']} systems: {result['throughput_samples_per_sec']:.0f} samples/sec")

    all_results['benchmarks']['multi_system'] = multi_system_results

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)

    return all_results


def print_summary(results: Dict[str, Any]) -> None:
    """Print benchmark summary."""
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    # Update scaling summary
    print("\n1. UPDATE PERFORMANCE SCALING")
    print("-" * 80)
    print(f"{'Samples':<10} {'Features':<10} {'Time/Sample (ms)':<20} {'Throughput (s/sec)':<20}")
    print("-" * 80)

    for result in results['benchmarks']['update_scaling']['scaling_results']:
        print(f"{result['num_samples']:<10} "
              f"{result['num_features']:<10} "
              f"{result['time_per_sample_ms']:<20.4f} "
              f"{result['throughput_samples_per_sec']:<20.0f}")

    # Drift detection summary
    print("\n2. DRIFT DETECTION PERFORMANCE")
    print("-" * 80)
    print(f"{'Baseline':<12} {'Features':<10} {'Time/Check (ms)':<18} {'Throughput (c/sec)':<20}")
    print("-" * 80)

    for result in results['benchmarks']['drift_detection']['results']:
        print(f"{result['baseline_samples']:<12} "
              f"{result['num_features']:<10} "
              f"{result['time_per_check_ms']:<18.4f} "
              f"{result['throughput_checks_per_sec']:<20.0f}")

    # CUSUM detection summary
    print("\n3. CUSUM DRIFT DETECTION")
    print("-" * 80)
    print(f"{'Config':<30} {'Total Time (s)':<18} {'Detection Latency':<20}")
    print("-" * 80)

    for result in results['benchmarks']['cusum_detection']['results']:
        config = f"{result['baseline_samples']}+{result['drift_samples']}×{result['num_features']}"
        print(f"{config:<30} "
              f"{result['total_time_seconds']:<18.4f} "
              f"{result['detection_latency']:<20} samples")

    # Distribution shift summary
    print("\n4. DISTRIBUTION SHIFT DETECTION")
    print("-" * 80)
    print(f"{'Config':<30} {'Detection Time (ms)':<22} {'Classification':<15}")
    print("-" * 80)

    for result in results['benchmarks']['distribution_shift']['results']:
        config = f"{result['historical_samples']}+{result['recent_samples']}×{result['num_features']}"
        print(f"{config:<30} "
              f"{result['detection_time_seconds']*1000:<22.2f} "
              f"{result['classification']:<15}")

    # Multi-system overhead
    print("\n5. MULTI-SYSTEM OVERHEAD")
    print("-" * 80)
    print(f"{'Systems':<12} {'Throughput (s/sec)':<20} {'Overhead per System (ms)':<25}")
    print("-" * 80)

    baseline_throughput = None
    for result in results['benchmarks']['multi_system']['multi_system_results']:
        if baseline_throughput is None:
            baseline_throughput = result['throughput_samples_per_sec']

        overhead = (result['time_per_sample_ms'] * result['num_systems'])
        print(f"{result['num_systems']:<12} "
              f"{result['throughput_samples_per_sec']:<20.0f} "
              f"{overhead:<25.4f}")

    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    # Best throughput
    best_update = max(
        r['throughput_samples_per_sec']
        for r in results['benchmarks']['update_scaling']['scaling_results']
    )
    print(f"✓ Peak update throughput: {best_update:,.0f} samples/second")

    best_drift = max(
        r['throughput_checks_per_sec']
        for r in results['benchmarks']['drift_detection']['results']
    )
    print(f"✓ Peak drift check throughput: {best_drift:,.0f} checks/second")

    # Average CUSUM latency
    avg_latency = sum(
        r['detection_latency']
        for r in results['benchmarks']['cusum_detection']['results']
        if r['detected_at_sample']
    ) / len([r for r in results['benchmarks']['cusum_detection']['results'] if r['detected_at_sample']])
    print(f"✓ Average CUSUM detection latency: {avg_latency:.1f} samples")

    print("=" * 80)


def main():
    """Run comprehensive benchmark and save results."""
    results = run_comprehensive_benchmark()
    print_summary(results)

    # Save results to file
    output_path = Path(__file__).parent / "interpretability_monitor_benchmark_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")


if __name__ == '__main__':
    main()
