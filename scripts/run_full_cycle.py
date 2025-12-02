"""
Run Full Cycle Script
=====================

Simulates the complete 12-step end-to-end hypothesis improvement cycle.
"""

import sys
import os
import time
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research_system import ResearchSystem, SystemSpecialization
from integrations.ai_memory_system import AIMemorySystem
from integrations.rl_trainer import RLTrainer, TrainingConfig

def main():
    print("🚀 Starting End-to-End Hypothesis Cycle Simulation")
    print("================================================")
    
    # Initialize mock orchestrator endpoint
    orchestrator_url = "http://localhost:5000"
    
    # Initialize Research System
    print("\n[1] Initializing Research System...")
    agent = ResearchSystem(
        system_id=1,
        specialization=SystemSpecialization.ENGINEERING,
        model_path="mock_path",
        private_key="mock_key",
        orchestrator_endpoint=orchestrator_url
    )
    
    # Initialize Memory
    print("[2] Initializing Memory System...")
    agent.memory = AIMemorySystem(
        agent_id="agent_1",
        orchestrator_endpoint=orchestrator_url
    )
    
    # Run Cycle
    print("\n[3] Triggering Hypothesis Cycle...")
    request = "optimize transformer attention mechanism for 20% speedup"
    
    try:
        proposal = agent.run_full_hypothesis_cycle(request)
        
        if proposal:
            print("\n✅ Proposal Generated Successfully!")
            print(f"Title: {proposal['title']}")
            print(f"PaperQA Said Won't Work: {proposal.get('paperqa_said_wont_work')}")
            print(f"Tiny Reward: {proposal.get('paperqa_query_reward')}")
            
            # Simulate Orchestrator Response (Sandbox Success)
            print("\n[4] Simulating Sandbox Execution & Reward...")
            outcome = {
                'proposal_id': proposal['id'],
                'accepted': True,
                'sandbox_success': True,
                'paperqa_said_wont_work': proposal.get('paperqa_said_wont_work'),
                'succeeded_despite_paperqa': True,  # Simulate success despite doubt
                'improvement_metrics': {
                    'performance_gain': 25.0,  # 25% speedup
                    'accuracy_change': 0.0
                }
            }
            
            # Compute Reward
            trainer = RLTrainer()
            reward = trainer.reward_computer.compute_from_orchestrator_result(outcome)
            
            print(f"Computed Reward: {reward:.2f}")
            if proposal.get('paperqa_said_wont_work'):
                print("Note: Includes 1.5x multiplier for proving PaperQA wrong!")
                
            # Record Experience
            print("\n[5] Recording RL Experience...")
            trainer.record_experience(
                prompt=request,
                response=proposal['title'],
                outcome=outcome
            )
            
            print("\n✨ Cycle Complete!")
            
        else:
            print("\n❌ Cycle Aborted.")
            
    except Exception as e:
        print(f"\n❌ Error during cycle: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()


