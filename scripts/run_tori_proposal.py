#!/usr/bin/env python3
"""
Run TORI's self-directed 20-step proposal workflow.
Topic chosen by TORI: Quantifying and Mitigating the Emergent Behavioral Risks 
of Highly Compressed, Multi-Agent Systems Operating on Edge Devices
"""

import sys
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.proposal_workflow import get_workflow_engine, WORKFLOW_STEPS

def run_tori_proposal():
    """Run TORI's full 20-step proposal workflow."""
    
    engine = get_workflow_engine()
    
    # TORI's self-chosen topic
    topic = "Quantifying and Mitigating the Emergent Behavioral Risks of Highly Compressed, Multi-Agent Systems Operating on Edge Devices"
    
    print("=" * 70)
    print("TORI SELF-DIRECTED PROPOSAL WORKFLOW")
    print("=" * 70)
    print(f"Agent: TORI (gemma3:4b)")
    print(f"Topic: {topic}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Create fresh workspace
    workspace = engine.create_workspace("TORI", topic)
    print(f"Workspace: {workspace.id}")
    print(f"Path: {workspace.workspace_path}")
    print()
    
    # Log file
    log_file = workspace.workspace_path / "workflow_log.txt"
    
    def log(msg):
        print(msg)
        with open(log_file, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    
    # Run each step
    max_iterations = 30  # Allow for revision loops
    iteration = 0
    
    while workspace.current_step <= 20 and iteration < max_iterations:
        iteration += 1
        step_num = workspace.current_step
        step = WORKFLOW_STEPS[step_num - 1]
        
        log(f"\n{'='*60}")
        log(f"STEP {step_num}/20: {step.title}")
        log(f"File: {step.filename}")
        log(f"Phase: {step.phase.value}")
        log(f"{'='*60}")
        
        start = time.time()
        
        try:
            result = engine.execute_step(workspace)
            elapsed = time.time() - start
            
            status = result.get('status', 'unknown')
            log(f"Status: {status} | Time: {elapsed:.1f}s")
            
            if status == "error":
                log(f"ERROR: {result.get('error', 'Unknown error')}")
                break
            
            if status in ("rejected", "revision_needed"):
                log(f"Message: {result.get('message', '')}")
                next_step = result.get('next_step', workspace.current_step)
                log(f"Jumping to step: {next_step}")
                workspace.current_step = next_step
                continue
            
            # Show output preview
            content = workspace.read_step(step_num)
            if content:
                preview = content[:500] + "..." if len(content) > 500 else content
                log(f"\nOUTPUT PREVIEW:\n{'-'*40}\n{preview}\n{'-'*40}")
            
            if workspace.status in ("completed", "rejected"):
                break
                
        except Exception as e:
            log(f"EXCEPTION: {e}")
            import traceback
            log(traceback.format_exc())
            break
    
    # Final summary
    log(f"\n{'='*70}")
    log("WORKFLOW COMPLETE")
    log(f"{'='*70}")
    log(f"Status: {workspace.status}")
    log(f"Steps completed: {len(workspace.completed_steps)}")
    log(f"Vote result: {workspace.vote_result}")
    log(f"Reward score: {workspace.reward_score}")
    log(f"Workspace: {workspace.workspace_path}")
    log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save final state
    workspace.save_state()
    
    # Store with AURA if available
    if workspace.status == "completed":
        aura_result = engine.store_proposal_with_aura(workspace)
        log(f"AURA storage: {aura_result}")
    
    return workspace


if __name__ == "__main__":
    run_tori_proposal()
