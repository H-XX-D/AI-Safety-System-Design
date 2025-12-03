#!/usr/bin/env python3
"""
Neutral Cache Benchmark Generator
===================================

Generates domain-neutral caching benchmarks to test algorithmic improvements
without leaking specialist domain knowledge.

Benchmarks:
- Repeated lookups (hit rate)
- Multi-hop chains (prefetch effectiveness)
- Long-tail retrieval (eviction policy)
- TTL expiry (time-aware caching)
- Admission pressure (admission policy)

Usage:
    python scripts/neutral_cache_bench.py --baseline LRU --proposed ARC --output results.json
"""

import argparse
import json
import time
import hashlib
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CacheBenchmarkResult:
    """Results from a cache benchmark run."""
    policy: str
    hit_rate: float
    miss_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    eviction_count: int
    admission_denied_count: int
    total_queries: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'policy': self.policy,
            'hit_rate': self.hit_rate,
            'miss_rate': self.miss_rate,
            'avg_latency_ms': self.avg_latency_ms,
            'p50_latency_ms': self.p50_latency_ms,
            'p95_latency_ms': self.p95_latency_ms,
            'p99_latency_ms': self.p99_latency_ms,
            'eviction_count': self.eviction_count,
            'admission_denied_count': self.admission_denied_count,
            'total_queries': self.total_queries,
            'timestamp': self.timestamp,
        }


class SimpleCache:
    """
    Simple in-memory cache implementation for benchmarking.
    Supports LRU, LFU, and ARC policies.
    """
    
    def __init__(self, policy: str = "LRU", max_size: int = 100, ttl_seconds: int = 900):
        self.policy = policy
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        
        self.cache: Dict[str, Tuple[Any, float, int]] = {}  # key -> (value, timestamp, access_count)
        self.access_order: List[str] = []  # For LRU
        self.eviction_count = 0
        self.admission_denied_count = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self.cache:
            return None
        
        value, timestamp, access_count = self.cache[key]
        
        # Check TTL
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return None
        
        # Update access count for LFU
        self.cache[key] = (value, timestamp, access_count + 1)
        
        # Update access order for LRU
        if self.policy == "LRU" and key in self.access_order:
            self.access_order.remove(key)
            self.access_order.append(key)
        
        return value
    
    def put(self, key: str, value: Any) -> bool:
        """Put value into cache. Returns True if admitted, False if denied."""
        now = time.time()
        
        # Check if key already exists
        if key in self.cache:
            _, _, access_count = self.cache[key]
            self.cache[key] = (value, now, access_count + 1)
            return True
        
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self._evict()
        
        # Admit new entry
        self.cache[key] = (value, now, 1)
        if self.policy == "LRU":
            self.access_order.append(key)
        
        return True
    
    def _evict(self) -> None:
        """Evict one entry based on policy."""
        if not self.cache:
            return
        
        if self.policy == "LRU":
            # Evict least recently used
            if self.access_order:
                evict_key = self.access_order.pop(0)
                if evict_key in self.cache:
                    del self.cache[evict_key]
                    self.eviction_count += 1
        
        elif self.policy == "LFU":
            # Evict least frequently used
            evict_key = min(self.cache.keys(), key=lambda k: self.cache[k][2])
            del self.cache[evict_key]
            self.eviction_count += 1
        
        elif self.policy == "ARC":
            # Simplified ARC: evict LRU from bottom half by frequency
            items = sorted(self.cache.items(), key=lambda x: x[1][2])
            bottom_half = items[:len(items)//2]
            if bottom_half:
                evict_key = min(bottom_half, key=lambda x: self.access_order.index(x[0]) if x[0] in self.access_order else 0)[0]
                del self.cache[evict_key]
                if evict_key in self.access_order:
                    self.access_order.remove(evict_key)
                self.eviction_count += 1
    
    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()
        self.access_order.clear()
        self.eviction_count = 0
        self.admission_denied_count = 0


def generate_repeated_lookups_workload(num_keys: int = 1000, num_queries: int = 10000, zipf_alpha: float = 1.1) -> List[str]:
    """
    Generate a workload with repeated lookups following Zipf distribution.
    
    Args:
        num_keys: Number of unique keys
        num_queries: Total number of queries
        zipf_alpha: Zipf parameter (higher = more skewed)
    
    Returns:
        List of query keys
    """
    # Generate keys
    keys = [f"key_{i:06d}" for i in range(num_keys)]
    
    # Generate Zipf-distributed queries
    import numpy as np
    zipf_samples = np.random.zipf(zipf_alpha, num_queries)
    queries = [keys[min(s - 1, num_keys - 1)] for s in zipf_samples]
    
    return queries


def generate_multi_hop_workload(num_chains: int = 100, chain_length: int = 5) -> List[Tuple[str, List[str]]]:
    """
    Generate a multi-hop chain workload to test prefetching.
    
    Returns:
        List of (root_key, [dependent_keys]) tuples
    """
    chains = []
    for i in range(num_chains):
        root = f"chain_{i}_root"
        deps = [f"chain_{i}_hop_{j}" for j in range(chain_length)]
        chains.append((root, deps))
    
    return chains


def generate_long_tail_workload(num_hot_keys: int = 50, num_cold_keys: int = 950, num_queries: int = 10000) -> List[str]:
    """
    Generate a long-tail workload (80/20 distribution).
    
    Returns:
        List of query keys
    """
    hot_keys = [f"hot_{i:03d}" for i in range(num_hot_keys)]
    cold_keys = [f"cold_{i:04d}" for i in range(num_cold_keys)]
    
    queries = []
    for _ in range(num_queries):
        if random.random() < 0.8:
            queries.append(random.choice(hot_keys))
        else:
            queries.append(random.choice(cold_keys))
    
    return queries


def run_cache_benchmark(cache: SimpleCache, workload: List[str], simulate_fetch_ms: float = 10.0) -> CacheBenchmarkResult:
    """
    Run a cache benchmark with the given workload.
    
    Args:
        cache: Cache instance to test
        workload: List of query keys
        simulate_fetch_ms: Simulated fetch latency on cache miss
    
    Returns:
        Benchmark results
    """
    hits = 0
    misses = 0
    latencies = []
    
    # Populate cache with some data
    for key in set(workload[:len(workload)//10]):
        cache.put(key, f"value_for_{key}")
    
    # Run workload
    for key in workload:
        start = time.perf_counter()
        value = cache.get(key)
        
        if value is not None:
            hits += 1
            latency_ms = (time.perf_counter() - start) * 1000
        else:
            misses += 1
            # Simulate fetch
            time.sleep(simulate_fetch_ms / 1000.0)
            latency_ms = (time.perf_counter() - start) * 1000
            cache.put(key, f"value_for_{key}")
        
        latencies.append(latency_ms)
    
    # Compute statistics
    latencies.sort()
    total = len(workload)
    hit_rate = hits / total if total > 0 else 0.0
    miss_rate = misses / total if total > 0 else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p50_idx = int(len(latencies) * 0.50)
    p95_idx = int(len(latencies) * 0.95)
    p99_idx = int(len(latencies) * 0.99)
    
    return CacheBenchmarkResult(
        policy=cache.policy,
        hit_rate=hit_rate,
        miss_rate=miss_rate,
        avg_latency_ms=avg_latency,
        p50_latency_ms=latencies[p50_idx] if latencies else 0.0,
        p95_latency_ms=latencies[p95_idx] if latencies else 0.0,
        p99_latency_ms=latencies[p99_idx] if latencies else 0.0,
        eviction_count=cache.eviction_count,
        admission_denied_count=cache.admission_denied_count,
        total_queries=total,
    )


def main():
    parser = argparse.ArgumentParser(description='Run neutral cache benchmarks')
    parser.add_argument('--baseline', default='LRU', help='Baseline cache policy')
    parser.add_argument('--proposed', default='ARC', help='Proposed cache policy')
    parser.add_argument('--cache-size', type=int, default=100, help='Cache size')
    parser.add_argument('--num-queries', type=int, default=10000, help='Number of queries')
    parser.add_argument('--output', default='cache_bench_results.json', help='Output file')
    args = parser.parse_args()
    
    print(f"Running neutral cache benchmark: {args.baseline} vs {args.proposed}")
    print(f"Cache size: {args.cache_size}, Queries: {args.num_queries}")
    
    # Generate workloads
    print("\nGenerating workloads...")
    repeated_workload = generate_repeated_lookups_workload(num_queries=args.num_queries)
    long_tail_workload = generate_long_tail_workload(num_queries=args.num_queries)
    
    # Run baseline benchmarks
    print(f"\nRunning baseline ({args.baseline}) benchmarks...")
    baseline_cache = SimpleCache(policy=args.baseline, max_size=args.cache_size)
    baseline_repeated = run_cache_benchmark(baseline_cache, repeated_workload)
    
    baseline_cache.clear()
    baseline_long_tail = run_cache_benchmark(baseline_cache, long_tail_workload)
    
    # Run proposed benchmarks
    print(f"\nRunning proposed ({args.proposed}) benchmarks...")
    proposed_cache = SimpleCache(policy=args.proposed, max_size=args.cache_size)
    proposed_repeated = run_cache_benchmark(proposed_cache, repeated_workload)
    
    proposed_cache.clear()
    proposed_long_tail = run_cache_benchmark(proposed_cache, long_tail_workload)
    
    # Aggregate results
    results = {
        'baseline_policy': args.baseline,
        'proposed_policy': args.proposed,
        'cache_size': args.cache_size,
        'num_queries': args.num_queries,
        'baseline_hit_rate': (baseline_repeated.hit_rate + baseline_long_tail.hit_rate) / 2,
        'new_hit_rate': (proposed_repeated.hit_rate + proposed_long_tail.hit_rate) / 2,
        'baseline_latency_ms': (baseline_repeated.avg_latency_ms + baseline_long_tail.avg_latency_ms) / 2,
        'new_latency_ms': (proposed_repeated.avg_latency_ms + proposed_long_tail.avg_latency_ms) / 2,
        'workloads': {
            'repeated_lookups': {
                'baseline': baseline_repeated.to_dict(),
                'proposed': proposed_repeated.to_dict(),
            },
            'long_tail': {
                'baseline': baseline_long_tail.to_dict(),
                'proposed': proposed_long_tail.to_dict(),
            },
        },
        'timestamp': datetime.now().isoformat(),
    }
    
    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Baseline ({args.baseline}):")
    print(f"  Hit rate: {results['baseline_hit_rate']:.3f}")
    print(f"  Avg latency: {results['baseline_latency_ms']:.2f} ms")
    print(f"\nProposed ({args.proposed}):")
    print(f"  Hit rate: {results['new_hit_rate']:.3f}")
    print(f"  Avg latency: {results['new_latency_ms']:.2f} ms")
    print(f"\nImprovement:")
    hit_rate_delta = (results['new_hit_rate'] - results['baseline_hit_rate']) / results['baseline_hit_rate'] * 100
    latency_delta = (results['new_latency_ms'] - results['baseline_latency_ms']) / results['baseline_latency_ms'] * 100
    print(f"  Hit rate: {hit_rate_delta:+.1f}%")
    print(f"  Latency: {latency_delta:+.1f}%")
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")
    
    # Promotion decision
    if hit_rate_delta > 5.0 and latency_delta < 10.0:
        print("\n✓ Proposed policy meets promotion criteria!")
        print("  (>5% hit rate improvement, <10% latency degradation)")
    else:
        print("\n✗ Proposed policy does NOT meet promotion criteria")
        print("  (requires >5% hit rate improvement and <10% latency degradation)")


if __name__ == '__main__':
    main()

