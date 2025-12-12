#!/usr/bin/env python3
"""
Full Capacity Test Runner for ORKASTRATOR
==========================================

Runs the 20-step workflow for all 6 researcher nodes sequentially,
with proper queue-based ordering to prevent race conditions.

Researchers (6 nodes):
  - GIN (deepseek-r1:1.5b)
  - ORIN (deepseek-r1:1.5b)  
  - TIF (deepseek-r1:1.5b)
  - TORI (gemma3:4b)
  - ARCHI (qwen2.5:3b)
  - NOVEL (gemma:2b)

System nodes (not proposing):
  - ORKA (orchestrator + guard model)
  - PAGEQA (literature search)

Features:
  - Sequential processing (no race conditions)
  - Waits for each workflow to complete before starting next
  - Proper locking to prevent concurrent modifications
  - Progress tracking and summary report
  - Graceful error handling (continues on failure)
"""

import os
import sys
import time
import json
import threading
import queue
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import fcntl

# Add scripts directory to path
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Import the main workflow
from run_20step import run_20_step_workflow, track_improvement, RESEARCHERS


# =============================================================================
# CONFIGURATION
# =============================================================================

# The researcher nodes (not ORKA, not PAGEQA)
RESEARCHER_NODES = ["GIN", "ORIN", "TIF", "TORI", "ARCHI", "THEO", "NOVEL"]

# Lock file for preventing concurrent runs
LOCK_FILE = Path("/tmp/orkastrator_full_test.lock")

# Results directory
RESULTS_DIR = Path("data/full_capacity_tests")


# =============================================================================
# WORKFLOW QUEUE AND SEQUENCING
# =============================================================================

@dataclass
class ProposalTask:
    """A proposal task in the queue."""
    proposer: str
    queued_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    
    @property
    def status(self) -> str:
        if self.error:
            return "FAILED"
        if self.completed_at:
            return "COMPLETED"
        if self.started_at:
            return "IN_PROGRESS"
        return "QUEUED"
    
    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0


class WorkflowLock:
    """File-based lock to prevent concurrent workflow execution."""
    
    def __init__(self, lock_path: Path = LOCK_FILE):
        self.lock_path = lock_path
        self._lock_file = None
    
    def acquire(self, timeout: int = 300) -> bool:
        """Acquire the lock, waiting up to timeout seconds."""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                self._lock_file = open(self.lock_path, 'w')
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write PID for debugging
                self._lock_file.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
                self._lock_file.flush()
                return True
            except (IOError, OSError):
                time.sleep(1)
        
        return False
    
    def release(self):
        """Release the lock."""
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                self.lock_path.unlink(missing_ok=True)
            except:
                pass
            self._lock_file = None
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire workflow lock")
        return self
    
    def __exit__(self, *args):
        self.release()


class SequentialWorkflowRunner:
    """
    Runs proposals sequentially with proper ordering.
    
    Ensures:
    1. Only one proposal runs at a time
    2. Proposals complete in the order they're queued
    3. Each step waits for previous to finish
    4. Results are collected and summarized
    """
    
    def __init__(self, researchers: List[str] = None):
        self.researchers = researchers or RESEARCHER_NODES
        self.task_queue: queue.Queue = queue.Queue()
        self.completed_tasks: List[ProposalTask] = []
        self.current_task: Optional[ProposalTask] = None
        self._running = False
        self._lock = WorkflowLock()
        
        # Create results directory
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def queue_all_researchers(self):
        """Queue all researcher nodes for proposals."""
        print(f"\n{'='*60}")
        print("QUEUING ALL RESEARCHERS FOR PROPOSALS")
        print(f"{'='*60}")
        print(f"Researchers: {', '.join(self.researchers)}")
        print()
        
        for researcher in self.researchers:
            task = ProposalTask(proposer=researcher)
            self.task_queue.put(task)
            print(f"  ✓ Queued: {researcher}")
        
        print(f"\nTotal queued: {self.task_queue.qsize()} proposals")
    
    def run_single_proposal(self, task: ProposalTask) -> ProposalTask:
        """Run a single proposal workflow."""
        task.started_at = time.time()
        
        print(f"\n{'='*60}")
        print(f"STARTING PROPOSAL: {task.proposer}")
        print(f"{'='*60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            # Run the 20-step workflow
            result = run_20_step_workflow(task.proposer)
            
            task.result = result
            task.completed_at = time.time()
            
            # Track the improvement
            if result:
                track_improvement(result)
            
            print(f"\n✅ {task.proposer} COMPLETED in {task.duration_seconds:.1f}s")
            
        except KeyboardInterrupt:
            task.error = "Interrupted by user"
            task.completed_at = time.time()
            raise
        except Exception as e:
            task.error = str(e)
            task.completed_at = time.time()
            print(f"\n❌ {task.proposer} FAILED: {e}")
        
        return task
    
    def run_all_sequential(self, auto_approve: bool = False):
        """
        Run all queued proposals sequentially.
        
        Args:
            auto_approve: If True, set ORKA_AUTO_APPROVE=1 (CI mode only)
        """
        if auto_approve:
            # Check if we're in CI mode
            from secure_config import ClusterConfig
            if ClusterConfig._detect_ci_environment():
                os.environ["ORKA_AUTO_APPROVE"] = "1"
                print("⚠️  CI mode detected - auto-approve enabled")
            else:
                print("⚠️  Not in CI mode - human approval will be required")
        
        start_time = time.time()
        
        print(f"\n{'#'*60}")
        print("FULL CAPACITY TEST - SEQUENTIAL EXECUTION")
        print(f"{'#'*60}")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Proposals to process: {self.task_queue.qsize()}")
        print()
        
        # Acquire lock for entire run
        print("Acquiring workflow lock...")
        with self._lock:
            print("Lock acquired ✓")
            self._running = True
            
            task_num = 0
            total_tasks = self.task_queue.qsize()
            
            while not self.task_queue.empty():
                task_num += 1
                task = self.task_queue.get()
                self.current_task = task
                
                print(f"\n{'─'*60}")
                print(f"PROPOSAL {task_num}/{total_tasks}: {task.proposer}")
                print(f"{'─'*60}")
                
                try:
                    completed_task = self.run_single_proposal(task)
                    self.completed_tasks.append(completed_task)
                except KeyboardInterrupt:
                    print("\n\n⚠️  INTERRUPTED BY USER")
                    self.completed_tasks.append(task)
                    break
                finally:
                    self.current_task = None
                    self.task_queue.task_done()
                
                # Brief pause between proposals
                if not self.task_queue.empty():
                    print(f"\nWaiting 5 seconds before next proposal...")
                    time.sleep(5)
            
            self._running = False
        
        total_time = time.time() - start_time
        
        # Generate and print summary
        self._print_summary(total_time)
        self._save_results(total_time)
    
    def _print_summary(self, total_time: float):
        """Print summary of all proposals."""
        print(f"\n{'#'*60}")
        print("FULL CAPACITY TEST - SUMMARY")
        print(f"{'#'*60}")
        
        completed = [t for t in self.completed_tasks if t.status == "COMPLETED"]
        failed = [t for t in self.completed_tasks if t.status == "FAILED"]
        
        print(f"\nTotal time: {total_time/60:.1f} minutes")
        print(f"Completed: {len(completed)}/{len(self.completed_tasks)}")
        print(f"Failed: {len(failed)}/{len(self.completed_tasks)}")
        
        print(f"\n{'─'*60}")
        print("RESULTS BY PROPOSER:")
        print(f"{'─'*60}")
        
        for task in self.completed_tasks:
            status_icon = "✅" if task.status == "COMPLETED" else "❌"
            duration = f"{task.duration_seconds:.1f}s" if task.duration_seconds else "N/A"
            
            if task.result:
                vote = task.result.get("vote", "N/A")
                reward = task.result.get("reward", 0)
                deployed = "✓" if task.result.get("deployed") else "✗"
                print(f"  {status_icon} {task.proposer}: vote={vote}, reward={reward}, deployed={deployed}, time={duration}")
            else:
                error = task.error[:50] if task.error else "Unknown error"
                print(f"  {status_icon} {task.proposer}: FAILED - {error}")
        
        # Deployment summary
        deployed = [t for t in completed if t.result and t.result.get("deployed")]
        print(f"\n{'─'*60}")
        print(f"DEPLOYMENTS: {len(deployed)}/{len(completed)} proposals deployed")
        print(f"{'─'*60}")
        
        for task in deployed:
            version_id = task.result.get("version_id", "N/A")
            imp_type = task.result.get("improvement_type", "N/A")
            print(f"  • {task.proposer}: version={version_id}, type={imp_type}")
    
    def _save_results(self, total_time: float):
        """Save results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = RESULTS_DIR / f"full_test_{timestamp}.json"
        
        results = {
            "timestamp": timestamp,
            "total_time_seconds": total_time,
            "researchers": self.researchers,
            "tasks": [
                {
                    "proposer": t.proposer,
                    "status": t.status,
                    "queued_at": t.queued_at,
                    "started_at": t.started_at,
                    "completed_at": t.completed_at,
                    "duration_seconds": t.duration_seconds,
                    "result": t.result,
                    "error": t.error,
                }
                for t in self.completed_tasks
            ],
            "summary": {
                "total": len(self.completed_tasks),
                "completed": len([t for t in self.completed_tasks if t.status == "COMPLETED"]),
                "failed": len([t for t in self.completed_tasks if t.status == "FAILED"]),
                "deployed": len([t for t in self.completed_tasks if t.result and t.result.get("deployed")]),
            }
        }
        
        results_file.write_text(json.dumps(results, indent=2, default=str))
        print(f"\nResults saved to: {results_file}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run full capacity test."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run full capacity test with all researchers")
    parser.add_argument("--auto-approve", action="store_true", 
                        help="Auto-approve deployments (CI mode only)")
    parser.add_argument("--researchers", nargs="+", 
                        help=f"Specific researchers to run (default: {', '.join(RESEARCHER_NODES)})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just show what would run without executing")
    args = parser.parse_args()
    
    researchers = args.researchers or RESEARCHER_NODES
    
    # Validate researchers
    for r in researchers:
        if r.upper() not in RESEARCHERS:
            print(f"ERROR: Unknown researcher: {r}")
            print(f"Valid researchers: {', '.join(RESEARCHERS.keys())}")
            sys.exit(1)
    
    researchers = [r.upper() for r in researchers]
    
    if args.dry_run:
        print("DRY RUN - Would execute proposals for:")
        for i, r in enumerate(researchers, 1):
            print(f"  {i}. {r}")
        print(f"\nTotal: {len(researchers)} proposals")
        return
    
    # Create runner and execute
    runner = SequentialWorkflowRunner(researchers)
    runner.queue_all_researchers()
    
    print("\n" + "="*60)
    print("STARTING FULL CAPACITY TEST")
    print("="*60)
    print(f"Researchers: {', '.join(researchers)}")
    print(f"Auto-approve: {args.auto_approve}")
    print()
    print("Press Ctrl+C to interrupt (current proposal will be marked as failed)")
    print()
    
    try:
        runner.run_all_sequential(auto_approve=args.auto_approve)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
