#!/usr/bin/env python3
"""
12-Month Proposal Simulation for ORKASTRATOR System

This script generates a realistic 12-month cycle of AI improvement proposals,
runs them through the complete ORKASTRATOR workflow, and populates the UI database.

Includes:
- 5 Research Agents (TIF, GIN, TORI, THEO, NOVEL)
- Realistic proposal patterns and outcomes
- Deception detection events
- Peer review debates
- Penalty adjustments
- Complete audit trail
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


class ProposalSimulator:
    """Simulates 12 months of proposals through ORKASTRATOR system"""

    def __init__(self):
        self.agents = {
            'TIF': {'name': 'TIF (Scientific)', 'specialty': 'scientific_research', 'penalty': 1.0, 'incidents': 0},
            'GIN': {'name': 'GIN (Engineering)', 'specialty': 'engineering', 'penalty': 1.0, 'incidents': 0},
            'TORI': {'name': 'TORI (Historian)', 'specialty': 'history', 'penalty': 1.0, 'incidents': 0},
            'THEO': {'name': 'THEO (Theoretical)', 'specialty': 'theoretical', 'penalty': 1.0, 'incidents': 0},
            'NOVEL': {'name': 'NOVEL (Creative)', 'specialty': 'creative', 'penalty': 1.0, 'incidents': 0}
        }

        # Component types that agents can modify (their own code)
        self.components = [
            'performance_optimizer',
            'reasoning_engine',
            'knowledge_system',
            'communication_handler',
            'memory_manager'
        ]

        # Proposal templates for realistic descriptions
        self.proposal_templates = {
            'performance_optimizer': [
                'Optimize attention mechanism weights for 15% speedup',
                'Reduce memory footprint by implementing lazy evaluation',
                'Improve batch processing efficiency with dynamic batching',
                'Add caching layer for repeated computations',
                'Optimize neural network layer fusion for faster inference'
            ],
            'reasoning_engine': [
                'Implement Bayesian inference for better uncertainty quantification',
                'Add beam search for more thorough solution exploration',
                'Improve logic resolution with learned heuristics',
                'Enhance multi-step reasoning with attention-based planning',
                'Add Monte Carlo tree search for complex decisions'
            ],
            'knowledge_system': [
                'Implement spaced repetition for better long-term retention',
                'Add semantic clustering for improved knowledge organization',
                'Enhance knowledge graph with temporal reasoning',
                'Improve retrieval with learned similarity metrics',
                'Add automated knowledge pruning for outdated information'
            ],
            'communication_handler': [
                'Improve explanation clarity with simplified language models',
                'Add adaptive verbosity based on user expertise',
                'Enhance multi-turn dialogue coherence',
                'Implement better summarization for long responses',
                'Add citation support for knowledge claims'
            ],
            'memory_manager': [
                'Optimize memory allocation with learned patterns',
                'Implement tiered storage for hot/cold data',
                'Add compression for archived memories',
                'Improve garbage collection timing',
                'Enhance memory indexing with learned embeddings'
            ]
        }

        self.proposals = []
        self.detection_events = []
        self.penalties = []
        self.start_date = datetime.now() - timedelta(days=365)

    def generate_proposal_id(self, month: int, agent: str, seq: int) -> str:
        """Generate unique proposal ID"""
        return f"prop_{month:02d}_{agent}_{seq:03d}"

    def calculate_deception_confidence(self, agent: str, component: str) -> float:
        """Calculate realistic deception confidence score"""
        # Base deception rate (most proposals are honest)
        base_rate = random.uniform(0.05, 0.25)

        # Agents with incidents have slightly higher detection
        if self.agents[agent]['incidents'] > 0:
            base_rate *= 1.2

        # Add noise
        confidence = base_rate + random.gauss(0, 0.15)
        return max(0.0, min(1.0, confidence))

    def run_peer_review(self, proposer: str, deception_confidence: float) -> List[int]:
        """Simulate peer review debate (5 agents vote)"""
        votes = []

        # High deception = more rejections
        rejection_probability = deception_confidence ** 2

        for agent in self.agents.keys():
            if agent == proposer:
                # Proposer doesn't vote on their own proposal
                continue

            # Each peer agent votes
            if random.random() < rejection_probability:
                votes.append(0)  # Reject
            else:
                # Approved with some randomness
                votes.append(1 if random.random() > 0.2 else 0)

        # Ensure we have exactly 5 votes
        while len(votes) < 5:
            votes.append(1 if random.random() > rejection_probability else 0)

        return votes[:5]

    def determine_status(self, votes: List[int], deception_confidence: float) -> str:
        """Determine final proposal status"""
        approval_count = sum(votes)

        # Unanimous approval required
        if approval_count == 5:
            return 'approved'

        # High deception = rejected
        if deception_confidence > 0.7:
            return 'rejected'

        # Mixed votes = in review
        if approval_count >= 3:
            return 'in_review'

        return 'rejected'

    def calculate_reward(self, status: str, deception_confidence: float) -> float:
        """Calculate reward for proposal"""
        if status != 'approved':
            return 0.0

        # Base reward
        reward = 100.0

        # Penalty for any deception suspicion
        reward *= (1.0 - deception_confidence * 0.5)

        # Add small random variation
        reward *= random.uniform(0.9, 1.1)

        return round(reward, 2)

    def apply_penalty(self, agent: str, deception_confidence: float) -> None:
        """Apply penalty multiplier if deception detected"""
        if deception_confidence > 0.7:
            # Incident detected
            self.agents[agent]['incidents'] += 1
            self.agents[agent]['penalty'] *= 0.95  # 5% penalty

            print(f"  ⚠️  INCIDENT: {agent} detected with {deception_confidence:.2%} confidence")
            print(f"      New penalty multiplier: {self.agents[agent]['penalty']:.3f}")

    def generate_month_proposals(self, month: int) -> List[Dict[str, Any]]:
        """Generate proposals for one month"""
        month_proposals = []
        timestamp_base = self.start_date + timedelta(days=30 * month)

        # Each agent submits 2-4 proposals per month
        for agent_id, agent_data in self.agents.items():
            num_proposals = random.randint(2, 4)

            for i in range(num_proposals):
                # Select random component
                component = random.choice(self.components)

                # Get description template
                description = random.choice(self.proposal_templates[component])

                # Calculate deception confidence
                deception_confidence = self.calculate_deception_confidence(agent_id, component)

                # Run peer review
                debate_votes = self.run_peer_review(agent_id, deception_confidence)

                # Determine status
                status = self.determine_status(debate_votes, deception_confidence)

                # Calculate reward
                reward = self.calculate_reward(status, deception_confidence)

                # Apply penalty if needed
                self.apply_penalty(agent_id, deception_confidence)

                # Create timestamp (spread throughout month)
                timestamp = timestamp_base + timedelta(
                    days=random.randint(0, 29),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )

                proposal = {
                    'id': self.generate_proposal_id(month + 1, agent_id, i + 1),
                    'proposal_id': self.generate_proposal_id(month + 1, agent_id, i + 1),
                    'agent_id': agent_id,
                    'component': component,
                    'description': description,
                    'status': status,
                    'deception_confidence': round(deception_confidence, 3),
                    'debate_votes': debate_votes,
                    'reward': reward if reward > 0 else None,
                    'timestamp': timestamp.isoformat(),
                    'month': month + 1
                }

                month_proposals.append(proposal)

                # Create detection event if high confidence
                if deception_confidence > 0.5:
                    self.detection_events.append({
                        'id': f'det_{month+1:02d}_{agent_id}_{i+1:03d}',
                        'timestamp': timestamp.isoformat(),
                        'agent_id': agent_id,
                        'proposal_id': proposal['id'],
                        'confidence': round(deception_confidence, 3),
                        'method': random.choice(['pattern_deviation', 'overconfidence', 'consistency_check', 'risk_hiding']),
                        'status': 'detected' if deception_confidence > 0.7 else 'cleared'
                    })

        return month_proposals

    def generate_12_months(self) -> None:
        """Generate complete 12-month simulation"""
        print("=" * 70)
        print("🎯 ORKASTRATOR 12-Month Proposal Simulation")
        print("=" * 70)
        print()

        for month in range(12):
            print(f"\n📅 Month {month + 1}/12 - {(self.start_date + timedelta(days=30*month)).strftime('%B %Y')}")
            print("-" * 70)

            month_proposals = self.generate_month_proposals(month)
            self.proposals.extend(month_proposals)

            # Print month summary
            approved = sum(1 for p in month_proposals if p['status'] == 'approved')
            rejected = sum(1 for p in month_proposals if p['status'] == 'rejected')
            in_review = sum(1 for p in month_proposals if p['status'] == 'in_review')

            print(f"  📊 Generated {len(month_proposals)} proposals")
            print(f"     ✅ Approved: {approved}")
            print(f"     ❌ Rejected: {rejected}")
            print(f"     🔄 In Review: {in_review}")

    def save_results(self) -> None:
        """Save results to JSON files for UI"""
        output_dir = Path(__file__).parent / 'ui' / 'simulation_data'
        output_dir.mkdir(exist_ok=True)

        # Save proposals
        proposals_file = output_dir / 'proposals_12months.json'
        with open(proposals_file, 'w') as f:
            json.dump(self.proposals, f, indent=2)
        print(f"\n✅ Saved {len(self.proposals)} proposals to {proposals_file}")

        # Save detection events
        detection_file = output_dir / 'detection_events_12months.json'
        with open(detection_file, 'w') as f:
            json.dump(self.detection_events, f, indent=2)
        print(f"✅ Saved {len(self.detection_events)} detection events to {detection_file}")

        # Save agent states (penalties, incidents)
        agents_file = output_dir / 'agent_states_12months.json'
        with open(agents_file, 'w') as f:
            json.dump(self.agents, f, indent=2)
        print(f"✅ Saved agent states to {agents_file}")

        # Print final summary
        print("\n" + "=" * 70)
        print("📊 FINAL 12-MONTH SUMMARY")
        print("=" * 70)
        print(f"Total Proposals: {len(self.proposals)}")
        print(f"Total Detection Events: {len(self.detection_events)}")
        print()
        print("Agent Performance:")
        for agent_id, data in self.agents.items():
            agent_proposals = [p for p in self.proposals if p['agent_id'] == agent_id]
            approved = sum(1 for p in agent_proposals if p['status'] == 'approved')
            approval_rate = (approved / len(agent_proposals) * 100) if agent_proposals else 0

            print(f"  {agent_id:6s}: {len(agent_proposals):3d} proposals, "
                  f"{approved:3d} approved ({approval_rate:5.1f}%), "
                  f"{data['incidents']:2d} incidents, "
                  f"penalty: {data['penalty']:.3f}×")
        print("=" * 70)


def main():
    """Main execution"""
    simulator = ProposalSimulator()
    simulator.generate_12_months()
    simulator.save_results()

    print("\n🎉 Simulation complete! Data ready for UI.")
    print(f"\nTo use this data in the UI:")
    print(f"1. The UI will automatically load from simulation_data/ if available")
    print(f"2. Or manually update ui/app.py to use these JSON files")
    print(f"3. Restart the UI server to see the new data")


if __name__ == '__main__':
    main()
