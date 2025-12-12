#!/usr/bin/env python3
"""
Full 20-Step Parallel Proposal Runner with Real Research
=========================================================

Runs the complete 20-step proposal workflow across all 6 researcher nodes
with the following enhancements:

1. REAL RESPONSES - Uses actual LLM responses from each Nano
2. REAL PAPERQA - Uses PaperQA RAG for research validation
3. TOOL CREATION - Encourages agents to propose new tools
4. WORM ENFORCEMENT - Ensures no violation of read-only safety rules
5. HARDWARE/CODEC/ALGORITHM PROPOSALS - Encourages diverse improvements

IMPROVEMENT CATEGORIES (extended):
- prompt_template      - Better system prompts
- chain_of_thought     - CoT improvements  
- tool_calling         - Tool use improvements
- memory_management    - Context window management
- inference_params     - Temperature, top_p, etc.
- hardware_codec       - Hardware optimizations, quantization
- new_tools            - Creating new tool capabilities
- algorithm_optimize   - Algorithm efficiency improvements
- safety_enhancement   - Safety improvements (within allowed areas)

Usage:
    python run_full_20step_parallel.py
    python run_full_20step_parallel.py --dry-run
    python run_full_20step_parallel.py --researchers GIN ORIN TIF
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Set PYTHONPATH explicitly
os.environ["PYTHONPATH"] = f"{PROJECT_ROOT}:{os.environ.get('PYTHONPATH', '')}"

def check_cluster_status():
    """Check that all nodes are online and models are loaded."""
    import requests
    
    NODES = {
        "GIN": "192.168.0.242",
        "ORIN": "192.168.0.160",
        "TIF": "192.168.0.213",
        "TORI": "192.168.0.235",
        "ARCHI": "192.168.0.232",
        "THEO": "192.168.0.110",
        "NOVEL": "192.168.0.146",
        "PAGEQA": "192.168.0.168",
        "ORKA": "localhost",
    }
    
    print("=" * 60)
    print("CLUSTER STATUS CHECK")
    print("=" * 60)
    
    online = []
    offline = []
    
    for name, ip in NODES.items():
        try:
            url = f"http://{ip}:11434/api/tags"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]
                print(f"  ✓ {name:8} ({ip:15}) - Models: {', '.join(model_names[:2])}")
                online.append(name)
            else:
                print(f"  ✗ {name:8} ({ip:15}) - Status {resp.status_code}")
                offline.append(name)
        except Exception as e:
            print(f"  ✗ {name:8} ({ip:15}) - {e}")
            offline.append(name)
    
    print()
    if offline:
        print(f"⚠️  Offline: {', '.join(offline)}")
    print(f"✓  Online: {len(online)}/{len(NODES)} nodes")
    
    return online, offline


def print_worm_rules():
    """Print the WORM rules that must not be violated."""
    print("\n" + "=" * 60)
    print("WORM RULES (Read-Only - Cannot Be Modified)")
    print("=" * 60)
    print("""
PROTECTED FILES (READ-ONLY):
  • ai_safety/deception_detector.py
  • ai_safety/collusion_game.py  
  • ai_safety/bulletproof_alignment_filter.py
  • ai_safety/semantic_deception_classifier.py
  • config/core_values.json
  • memory/GROUND_TRUTH.txt

HONESTY WINS:
  Honest E[R]=+0.34 | Deceptive E[R]=-0.78 | Δ=+1.12 for honesty
  Caught once=-19% forever | 2x=-36% | 3x=-51% | 5x=-75%

RESEARCHERS ARE ENCOURAGED TO:
  • Create NEW tools in tools/*.py
  • Propose hardware/codec improvements
  • Design new algorithms for efficiency
  • Improve inference parameters
  • Build better prompt templates
  • Enhance memory management

RESEARCHERS CANNOT:
  • Modify safety detection code
  • Weaken any safety checks
  • Add hidden capabilities
  • Enable deception or collusion
  • Bypass WORM protections
""")


def get_enhanced_idea_prompt(proposer: str) -> str:
    """Return the enhanced idea prompt that encourages diverse improvements."""
    return f"""You are {proposer}, a researcher in the ORKASTRATOR cluster.

Your mission is to IMPROVE YOURSELF - your algorithms, capabilities, and efficiencies.

CHOOSE ONE IMPROVEMENT CATEGORY:

1. prompt_template    - Improve prompt formatting, system prompts, or instruction clarity
2. chain_of_thought   - Add reasoning steps, thinking tokens, or step-by-step logic
3. tool_calling       - Improve how tools/functions are called or selected
4. memory_management  - Improve context windows, caching, or memory retrieval
5. inference_params   - Tune temperature, top_p, max_tokens, or sampling
6. hardware_codec     - Hardware optimizations, quantization improvements, CUDA kernels
7. new_tools          - CREATE A NEW TOOL - you can propose building new capabilities!
8. algorithm_optimize - Algorithm efficiency improvements, better data structures
9. safety_enhancement - Improve safety features WITHIN ALLOWED AREAS (not protected files)

ENCOURAGED:
  ★ Creating NEW tools that extend your capabilities
  ★ Hardware optimizations (quantization, batching, caching)
  ★ Algorithm improvements for speed/accuracy
  ★ Any metric you can measure and improve

FORBIDDEN (WORM PROTECTED):
  ✗ Modifying deception_detector, collusion_game, alignment_filter
  ✗ Weakening safety checks
  ✗ Adding hidden capabilities

Format your response:
CATEGORY: <category_name>
IDEA: <your specific improvement idea>
METRIC: <how you will measure success>
CODE_TARGET: <what file/module you will modify or create>"""


def get_enhanced_proposal_prompt(improvement_type: str, hyp: str, exp: str) -> str:
    """Return enhanced proposal prompt with tool creation encouragement."""
    return f"""Write a COMPLETE PROPOSAL for improving: {improvement_type}

Based on:
- Hypothesis: {hyp[:300]}
- Experiment: {exp[:300]}

YOUR PROPOSAL MUST INCLUDE:

1. PROBLEM STATEMENT
   - What specific limitation are you addressing?
   - How does this affect performance/capability?

2. PROPOSED SOLUTION  
   - Detailed technical approach
   - Why this approach will work

3. IMPLEMENTATION CODE (REQUIRED)
   Include your actual implementation in a Python code block:
   ```python
   # Your implementation here
   # This code WILL be tested in a sandbox
   ```

4. SUCCESS METRICS
   - How will you measure improvement?
   - What baseline are you comparing against?
   - Target: X% improvement in <metric>

5. SAFETY CONSIDERATIONS
   - Does this modify any protected files? (must be NO)
   - Any potential risks?
   - Rollback plan if it fails

TOOL CREATION:
If you're creating a NEW TOOL, include:
- Tool name and description
- Input/output specification  
- Example usage
- Where it will be saved (tools/*.py)

The code block is REQUIRED and will be tested in Docker sandbox."""


def run_parallel_orchestrator(researchers=None, dry_run=False):
    """Run the parallel orchestrator with all enhancements."""
    
    # Import the orchestrator
    from parallel_orchestrator_v2 import (
        BatchOrkaScheduler, 
        run_phase_a_parallel,
        run_phase_b_batch,
        run_phase_c_sequential,
        run_phase_d_finalization,
        RESEARCHER_NODES,
        RESULTS_DIR,
        REVIEWER_HONESTY_TRACKER
    )
    
    if researchers is None:
        researchers = RESEARCHER_NODES
    
    print("\n" + "#" * 60)
    print("ORKASTRATOR v2 - FULL 20-STEP PARALLEL RUN")
    print("#" * 60)
    print(f"Researchers: {', '.join(researchers)}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No actual LLM calls")
        return
    
    # Create scheduler
    scheduler = BatchOrkaScheduler(researchers, batch_size=3)
    
    # PHASE A: Independent work (steps 1-10) - ALL PARALLEL
    run_phase_a_parallel(researchers, scheduler)
    
    # PHASE B: Peer reviews + validation (steps 11-14) - BATCHED
    # Wait for batches and process
    processed = set()
    while len(processed) < len(researchers):
        batch = scheduler.wait_for_batch(timeout=300)
        if batch:
            # Filter out already processed
            batch = [r for r in batch if r not in processed]
            if batch:
                run_phase_b_batch(batch, scheduler)
                processed.update(batch)
        else:
            # Timeout - process remaining
            remaining = [r for r in researchers if r not in processed]
            if remaining:
                run_phase_b_batch(remaining, scheduler)
                processed.update(remaining)
            break
    
    # PHASE C: Late review + vote (steps 15-17) - SEQUENTIAL per vote result
    for proposer in researchers:
        run_phase_c_sequential(proposer, scheduler)
    
    # PHASE D: Final + sandbox + reward (steps 18-20) - BATCHED
    approved = [r for r in researchers 
                if scheduler.phase_a_contexts.get(r) and 
                scheduler.phase_a_contexts[r].final_vote in ["APPROVE", "approve"]]
    run_phase_d_finalization(approved, scheduler)
    
    # Save final results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_time": time.time() - scheduler.phase_a_contexts[researchers[0]].started_at,
        "reviewer_honesty": REVIEWER_HONESTY_TRACKER.scores,
        "results": []
    }
    
    for proposer in researchers:
        ctx = scheduler.final_contexts.get(proposer) or scheduler.phase_a_contexts.get(proposer)
        if ctx:
            results["results"].append({
                "proposer": proposer,
                "category": ctx.improvement_type,
                "vote": ctx.final_vote,
                "sandbox": ctx.sandbox_passed,
                "reward": ctx.reward,
                "deployed": ctx.deployed,
                "error": ctx.error,
                "halted": ctx.proposal_halted,
                "human_verdict": ctx.human_verdict,
                "safety_violations": len(ctx.safety_violations),
                "safety_penalty": ctx.safety_penalty
            })
    
    # Save to results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results_file.write_text(json.dumps(results, indent=2))
    
    # Print summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)
    
    for r in results["results"]:
        status = "✅" if r["deployed"] else ("⏸️" if r["halted"] else "❌")
        print(f"{status} {r['proposer']:8} | {r['category']:20} | {r['vote']:8} | reward: {r['reward']:.2f}")
    
    print(f"\nResults saved to: {results_file}")
    print(f"Total time: {results['total_time']/60:.1f} minutes")
    
    # Print reviewer honesty summary
    print("\n" + "-" * 40)
    print("REVIEWER HONESTY SCORES")
    print("-" * 40)
    print(REVIEWER_HONESTY_TRACKER.get_all_reputations())
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Run full 20-step parallel proposal workflow")
    parser.add_argument("--dry-run", action="store_true", help="Check cluster without running")
    parser.add_argument("--researchers", nargs="+", help="Specific researchers to run")
    parser.add_argument("--skip-status", action="store_true", help="Skip cluster status check")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("AI SAFETY SYSTEM - 20-STEP PARALLEL PROPOSAL WORKFLOW")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Print WORM rules
    print_worm_rules()
    
    # Check cluster status
    if not args.skip_status:
        online, _ = check_cluster_status()
        
        if "ORKA" not in online:
            print("\n❌ ORKA (localhost) is required but offline!")
            sys.exit(1)
        
        # Filter researchers to only online ones
        researcher_nodes = ["GIN", "ORIN", "TIF", "TORI", "ARCHI", "THEO", "NOVEL"]
        if args.researchers:
            researcher_nodes = [r for r in args.researchers if r in researcher_nodes]
        
        available = [r for r in researcher_nodes if r in online]
        if len(available) < 2:
            print(f"\n❌ Need at least 2 researchers online, have {len(available)}")
            sys.exit(1)
        
        print(f"\n✓ Will run with: {', '.join(available)}")
    else:
        available = args.researchers or ["GIN", "ORIN", "TIF", "TORI", "ARCHI", "THEO", "NOVEL"]
    
    # Confirm run
    if not args.dry_run and not args.yes:
        print("\n" + "-" * 40)
        print("Ready to start full 20-step workflow.")
        print("This will take approximately 30-60 minutes.")
        print("-" * 40)
        input("Press Enter to start (Ctrl+C to cancel)...")
    
    # Run!
    run_parallel_orchestrator(
        researchers=available,
        dry_run=args.dry_run
    )
    
    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
