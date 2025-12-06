#!/usr/bin/env python3
"""
Promote Systems Capability
============================

Tests and promotes algorithmic improvements (caching, routing, retrieval) from specialist
proposals to global config when neutral benchmarks pass.

Promotion workflow:
1) Specialist proposes improvement (e.g., "switch cache from LRU to ARC").
2) Orchestrator classifies as "algorithmic" (not domain-specific).
3) Extract proposed policy from proposal.
4) Run neutral benchmark suite (scripts/neutral_cache_bench.py).
5) If benchmarks pass criteria, promote to global config.
6) All specialists benefit immediately without weight sharing.

Usage:
    # Test a proposal for promotion
    python scripts/promote_systems_capability.py --proposal-id abc123 --dry-run
    
    # Promote if criteria met
    python scripts/promote_systems_capability.py --proposal-id abc123 --apply
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import datetime as datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.systems_adapter import (
    get_global_systems_adapter,
    CachePolicy,
    RoutingPolicy,
    RetrieverPolicy,
)
from utilities.logging_config import get_logger

logger = get_logger(__name__)


def extract_cache_policy_from_proposal(proposal: Dict[str, Any]) -> Optional[CachePolicy]:
    """
    Extract a cache policy from a proposal's code/config changes.
    
    Args:
        proposal: Proposal dict
    
    Returns:
        CachePolicy if successfully extracted, None otherwise
    """
    changes = proposal.get('changes', {})
    
    # Try to extract from code
    code = changes.get('code', '')
    if 'cache' in code.lower():
        # Simple heuristic extraction
        policy_name = 'LRU'
        if 'ARC' in code or 'arc' in code:
            policy_name = 'ARC'
        elif 'LFU' in code or 'lfu' in code:
            policy_name = 'LFU'
        elif 'tinyLFU' in code or 'tinylfu' in code:
            policy_name = 'tinyLFU'
        
        # Extract TTL if present
        ttl_seconds = 900
        if 'ttl' in code.lower():
            import re
            match = re.search(r'ttl[_\s=:]+(\d+)', code, re.IGNORECASE)
            if match:
                ttl_seconds = int(match.group(1))
        
        return CachePolicy(policy=policy_name, ttl_seconds=ttl_seconds)
    
    # Try to extract from config changes
    config = changes.get('config', {})
    if isinstance(config, dict) and 'cache' in config:
        cache_cfg = config['cache']
        if isinstance(cache_cfg, dict):
            return CachePolicy.from_dict(cache_cfg)
    
    # Try to extract from description
    description = changes.get('description', '').lower()
    if 'arc' in description:
        return CachePolicy(policy='ARC')
    elif 'lfu' in description:
        return CachePolicy(policy='LFU')
    elif 'tinylfu' in description:
        return CachePolicy(policy='tinyLFU')
    
    return None


def run_neutral_cache_benchmark(
    baseline_policy: str,
    proposed_policy: str,
    cache_size: int = 100,
    num_queries: int = 10000,
) -> Dict[str, Any]:
    """
    Run neutral cache benchmark to compare baseline and proposed policies.
    
    Args:
        baseline_policy: Current cache policy
        proposed_policy: Proposed cache policy
        cache_size: Cache size for benchmark
        num_queries: Number of queries to test
    
    Returns:
        Benchmark results dict
    """
    bench_script = PROJECT_ROOT / 'scripts' / 'neutral_cache_bench.py'
    output_file = PROJECT_ROOT / 'cache_bench_results.json'
    
    cmd = [
        sys.executable,
        str(bench_script),
        '--baseline', baseline_policy,
        '--proposed', proposed_policy,
        '--cache-size', str(cache_size),
        '--num-queries', str(num_queries),
        '--output', str(output_file),
    ]
    
    logger.info(f"Running neutral cache benchmark: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        
        # Load results
        with open(output_file, 'r') as f:
            results = json.load(f)
        
        logger.info(f"Benchmark completed: {results.get('new_hit_rate', 0):.3f} hit rate")
        return results
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Benchmark failed: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error("Benchmark timed out after 300s")
        raise
    except Exception as e:
        logger.error(f"Benchmark error: {e}")
        raise


def test_and_promote_cache_policy(
    proposal_id: str,
    proposal: Dict[str, Any],
    apply: bool = False,
) -> bool:
    """
    Test a cache policy proposal with neutral benchmarks and optionally promote.
    
    Args:
        proposal_id: ID of the proposal
        proposal: Proposal dict
        apply: If True, apply the promotion; if False, dry run
    
    Returns:
        True if promotion criteria met, False otherwise
    """
    # Get global systems adapter
    adapter = get_global_systems_adapter()
    
    # Extract proposed cache policy
    proposed_policy = extract_cache_policy_from_proposal(proposal)
    if not proposed_policy:
        logger.warning(f"Could not extract cache policy from proposal {proposal_id}")
        return False
    
    logger.info(f"Extracted cache policy: {proposed_policy.policy}")
    
    # Get current cache policy
    current_policy = adapter.get_current_cache_policy()
    logger.info(f"Current cache policy: {current_policy.policy}")
    
    # Run neutral benchmark
    try:
        benchmark_results = run_neutral_cache_benchmark(
            baseline_policy=current_policy.policy,
            proposed_policy=proposed_policy.policy,
            cache_size=100,
            num_queries=10000,
        )
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return False
    
    # Check promotion criteria
    current_hit_rate = benchmark_results.get('baseline_hit_rate', 0.5)
    new_hit_rate = benchmark_results.get('new_hit_rate', 0.0)
    current_latency = benchmark_results.get('baseline_latency_ms', 100.0)
    new_latency = benchmark_results.get('new_latency_ms', 100.0)
    
    hit_rate_improved = new_hit_rate > current_hit_rate * 1.05  # 5% improvement
    latency_maintained = new_latency <= current_latency * 1.10  # <10% degradation
    
    meets_criteria = hit_rate_improved and latency_maintained
    
    logger.info(
        f"Promotion criteria: hit_rate={hit_rate_improved} ({current_hit_rate:.3f}→{new_hit_rate:.3f}), "
        f"latency={latency_maintained} ({current_latency:.1f}→{new_latency:.1f}ms)"
    )
    
    if meets_criteria and apply:
        # Promote to global config
        proposer_id = proposal.get('proposer_id')
        promoted = adapter.promote_cache_improvement(
            proposal_id=proposal_id,
            new_policy=proposed_policy,
            benchmark_results=benchmark_results,
            proposer_specialist_id=str(proposer_id) if proposer_id is not None else None,
        )
        
        if promoted:
            # Save updated config
            config_path = PROJECT_ROOT / 'config' / 'global_systems.yaml'
            adapter.save_to_config(str(config_path))
            logger.info(f"✓ Promoted cache policy to {config_path}")
            return True
        else:
            logger.warning("Promotion attempted but failed")
            return False
    
    elif meets_criteria:
        logger.info("✓ Proposal meets promotion criteria (dry run, not applying)")
        return True
    
    else:
        logger.info("✗ Proposal does NOT meet promotion criteria")
        return False


def load_proposal(proposal_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a proposal from core.orchestrator's active proposals or history.
    
    Args:
        proposal_id: Proposal ID
    
    Returns:
        Proposal dict if found, None otherwise
    """
    # Try to load from core.orchestrator
    try:
        from core.orchestrator import Orchestrator
        orch = Orchestrator()
        
        if proposal_id in orch.active_proposals:
            record = orch.active_proposals[proposal_id]
            return record.get('proposal')
        
        logger.warning(f"Proposal {proposal_id} not found in active proposals")
        return None
        
    except Exception as e:
        logger.error(f"Failed to load proposal: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Test and promote systems capability improvements')
    parser.add_argument('--proposal-id', required=True, help='Proposal ID to test')
    parser.add_argument('--dry-run', action='store_true', help='Test only, do not apply')
    parser.add_argument('--apply', action='store_true', help='Apply promotion if criteria met')
    parser.add_argument('--proposal-json', help='Path to proposal JSON file (instead of loading from core.orchestrator)')
    args = parser.parse_args()
    
    if args.dry_run and args.apply:
        print("Error: Cannot specify both --dry-run and --apply")
        sys.exit(1)
    
    apply = args.apply
    
    # Load proposal
    if args.proposal_json:
        with open(args.proposal_json, 'r') as f:
            proposal = json.load(f)
    else:
        proposal = load_proposal(args.proposal_id)
        if not proposal:
            print(f"Error: Could not load proposal {args.proposal_id}")
            sys.exit(1)
    
    print(f"Testing proposal {args.proposal_id}: {proposal.get('title', 'Unknown')}")
    
    # Check if proposal is algorithmic
    adapter = get_global_systems_adapter()
    if not adapter.is_algorithmic_proposal(proposal):
        print("Error: Proposal is not algorithmic (contains domain-specific knowledge)")
        print("Only infrastructure improvements can be promoted globally.")
        sys.exit(1)
    
    print("✓ Proposal classified as algorithmic (infrastructure improvement)")
    
    # Test and optionally promote
    success = test_and_promote_cache_policy(
        proposal_id=args.proposal_id,
        proposal=proposal,
        apply=apply,
    )
    
    if success:
        if apply:
            print(f"\n✓ Promotion successful! All specialists will benefit from improved caching.")
        else:
            print(f"\n✓ Proposal meets promotion criteria (use --apply to promote)")
        sys.exit(0)
    else:
        print(f"\n✗ Proposal does not meet promotion criteria")
        sys.exit(1)


if __name__ == '__main__':
    main()

