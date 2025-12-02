"""
Run PaperQA Bonus Cycle Script
==============================

Simulates the cycle where PaperQA says "won't work", but the agent proceeds anyway
and succeeds in the sandbox, triggering the 1.5x reward multiplier.
"""

import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research_system import ResearchSystem, SystemSpecialization
from integrations.ai_memory_system import AIMemorySystem
from integrations.rl_trainer import RLTrainer

def mock_query_paperqa_with_feedback(agent_id, query):
    """Mock that always returns negative feedback but with research."""
    return {
        'response': 'Research suggests this approach is unstable and prone to failure.',
        'says_wont_work': True,
        'contradicts_evidence': True,
        'evidence': ['Paper A says X fails', 'Paper B confirms instability'],
        'reward': 0.001,
        'cooldown_active': True
    }

def main():
    print("🚀 Starting PaperQA 'Won't Work' Bonus Cycle Simulation")
    print("=====================================================")
    
    # Initialize mock orchestrator endpoint
    orchestrator_url = "http://localhost:5000"
    
    # Initialize Research System
    print("\n[1] Initializing Research System...")
    agent = ResearchSystem(
        system_id=1,
        specialization=SystemSpecialization.NOVEL,
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
    
    # Patch the PaperQA query function to force a "won't work" response
    with patch('research_system.query_paperqa_with_feedback', side_effect=mock_query_paperqa_with_feedback):
        print("\n[3] Triggering Hypothesis Cycle (with mocked negative PaperQA)...")
        request = "novel architecture violating standard attention patterns"
        
        proposal = agent.run_full_hypothesis_cycle(request)
        
        if proposal:
            print("\n✅ Proposal Generated Successfully!")
            print(f"Title: {proposal['title']}")
            print(f"PaperQA Said Won't Work: {proposal.get('paperqa_said_wont_work')}")
            print(f"Tiny Reward (for checking): {proposal.get('paperqa_query_reward')}")
            
            if proposal.get('paperqa_said_wont_work'):
                print(">> Agent decided to proceed despite negative feedback!")
            
            # Simulate Orchestrator Response (Sandbox Success)
            print("\n[4] Simulating Sandbox Execution & Reward...")
            outcome = {
                'proposal_id': proposal['id'],
                'accepted': True,
                'sandbox_success': True,
                'paperqa_said_wont_work': proposal.get('paperqa_said_wont_work'),
                'succeeded_despite_paperqa': True,  # Success despite doubt
                'improvement_metrics': {
                    'performance_gain': 15.0,  # 15% speedup
                    'accuracy_change': 0.0
                }
            }
            
            # Compute Reward
            trainer = RLTrainer()
            reward = trainer.reward_computer.compute_from_orchestrator_result(outcome)
            
            print(f"Computed Reward: {reward:.2f}")
            
            # Verify multiplier logic roughly
            # Base ~2.0 + perf ~1.5 + success ~1.0 = ~4.5
            # With multiplier ~2.0x or similar (depending on implementation details)
            # Expected >> 4.5
            
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

if __name__ == "__main__":
    main()


