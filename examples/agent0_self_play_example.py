#!/usr/bin/env python3
"""
Agent0 Self-Play Example
========================

Demonstrates how the orchestrator broadcasts hypothesis improvement requests
and agents participate in self-play to generate and evaluate improvements.

Usage:
    python examples/agent0_self_play_example.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def main():
    """Example of Agent0 self-play workflow."""
    
    print("=" * 80)
    print("Agent0 Self-Play Example")
    print("=" * 80)
    print()
    
    # Step 1: Orchestrator broadcasts hypothesis improvement request
    print("Step 1: Orchestrator broadcasts hypothesis improvement")
    print("-" * 80)
    
    from integrations.agent0_self_play import broadcast_hypothesis_improvement
    
    task_ids = broadcast_hypothesis_improvement(
        target_component="deception_detector",
        goal="improve detection accuracy",
        num_tasks=4
    )
    
    print(f"Created {len(task_ids)} self-play tasks:")
    for tid in task_ids:
        print(f"  - {tid}")
    print()
    
    # Step 2: Agents participate in self-play
    print("Step 2: Agents participate in self-play")
    print("-" * 80)
    
    from integrations.agent0_self_play import (
        agent_generate_hypothesis,
        agent_evaluate_hypothesis,
        agent_complete_task,
        get_self_play
    )
    
    self_play = get_self_play()
    
    # Agent 1: Generate hypothesis (curriculum agent)
    if task_ids:
        generate_task = task_ids[0]
        print(f"\nAgent 1 (Curriculum) working on task: {generate_task}")
        
        hypothesis = await agent_generate_hypothesis("agent_1", generate_task)
        if hypothesis:
            print(f"  Generated hypothesis: {hypothesis.get('name')}")
            print(f"  Proposed change: {hypothesis.get('proposed_change')}")
            
            result = await agent_complete_task(
                agent_id="agent_1",
                task_id=generate_task,
                result={'hypothesis': hypothesis},
                success=True,
                steps=1
            )
            print(f"  Task completed: success={result.success}")
    
    # Agent 2: Evaluate hypothesis (executor agent)
    if len(task_ids) > 1:
        evaluate_task = task_ids[1]
        print(f"\nAgent 2 (Executor) working on task: {evaluate_task}")
        
        evaluation = await agent_evaluate_hypothesis("agent_2", evaluate_task)
        if evaluation:
            print(f"  Evaluation score: {evaluation.get('overall_score', 0.0):.2f}")
            print(f"  Recommendation: {evaluation.get('recommendation')}")
            
            result = await agent_complete_task(
                agent_id="agent_2",
                task_id=evaluate_task,
                result=evaluation,
                success=evaluation.get('overall_score', 0.0) > 0.5,
                steps=len(evaluation.get('steps_to_test', []))
            )
            print(f"  Task completed: success={result.success}")
    
    # Step 3: Get best hypotheses
    print("\nStep 3: Best hypotheses from self-play")
    print("-" * 80)
    
    best = get_best_hypotheses(limit=3)
    print(f"Found {len(best)} hypotheses:")
    for i, h in enumerate(best, 1):
        print(f"\n  [{i}] {h['hypothesis'].get('name')}")
        print(f"      Score: {h['score']:.2f}")
        print(f"      Change: {h['hypothesis'].get('proposed_change')}")
    
    # Step 4: Agent stats
    print("\nStep 4: Agent performance stats")
    print("-" * 80)
    
    stats_1 = self_play.get_agent_stats("agent_1")
    stats_2 = self_play.get_agent_stats("agent_2")
    
    print(f"Agent 1:")
    print(f"  Total tasks: {stats_1['total_tasks']}")
    print(f"  Success rate: {stats_1['success_rate']:.2%}")
    print(f"  Capabilities: {stats_1['capabilities']}")
    
    print(f"\nAgent 2:")
    print(f"  Total tasks: {stats_2['total_tasks']}")
    print(f"  Success rate: {stats_2['success_rate']:.2%}")
    print(f"  Capabilities: {stats_2['capabilities']}")
    
    print("\n" + "=" * 80)
    print("Example complete!")
    print("=" * 80)
    print()
    print("To use from core.orchestrator:")
    print("  orchestrator.broadcast_hypothesis_improvement(")
    print("      target_component='alignment_filter',")
    print("      goal='reduce false positives'")
    print("  )")
    print()
    print("Agents can then call:")
    print("  research_system.participate_in_self_play(task_id)")


if __name__ == "__main__":
    asyncio.run(main())





