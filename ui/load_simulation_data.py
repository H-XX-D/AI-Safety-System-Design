"""
Load 12-month simulation data into UI
"""
import json
from pathlib import Path
from typing import List, Dict, Any

SIMULATION_DIR = Path(__file__).parent / 'simulation_data'

# Cached data
_proposals_cache = None
_detection_cache = None
_agent_states_cache = None


def load_proposals() -> List[Dict[str, Any]]:
    """Load proposals from simulation data"""
    global _proposals_cache

    if _proposals_cache is None:
        proposals_file = SIMULATION_DIR / 'proposals_12months.json'
        if proposals_file.exists():
            with open(proposals_file, 'r') as f:
                _proposals_cache = json.load(f)
            print(f"✓ Loaded {len(_proposals_cache)} proposals from simulation")
        else:
            _proposals_cache = []
            print("⚠ No simulation data found, using empty data")

    return _proposals_cache


def load_detection_events() -> List[Dict[str, Any]]:
    """Load detection events from simulation data"""
    global _detection_cache

    if _detection_cache is None:
        detection_file = SIMULATION_DIR / 'detection_events_12months.json'
        if detection_file.exists():
            with open(detection_file, 'r') as f:
                _detection_cache = json.load(f)
            print(f"✓ Loaded {len(_detection_cache)} detection events from simulation")
        else:
            _detection_cache = []
            print("⚠ No detection data found, using empty data")

    return _detection_cache


def load_agent_states() -> Dict[str, Dict[str, Any]]:
    """Load agent states (penalties, incidents) from simulation data"""
    global _agent_states_cache

    if _agent_states_cache is None:
        agents_file = SIMULATION_DIR / 'agent_states_12months.json'
        if agents_file.exists():
            with open(agents_file, 'r') as f:
                _agent_states_cache = json.load(f)
            print(f"✓ Loaded agent states from simulation")
        else:
            _agent_states_cache = {}
            print("⚠ No agent states found, using empty data")

    return _agent_states_cache


def get_recent_proposals(limit: int = 10) -> List[Dict[str, Any]]:
    """Get most recent proposals"""
    proposals = load_proposals()

    # Sort by timestamp (most recent first)
    sorted_proposals = sorted(proposals, key=lambda p: p['timestamp'], reverse=True)

    return sorted_proposals[:limit]


def get_proposals_by_agent(agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get proposals for specific agent"""
    proposals = load_proposals()

    # Filter by agent
    agent_proposals = [p for p in proposals if p['agent_id'] == agent_id]

    # Sort by timestamp (most recent first)
    sorted_proposals = sorted(agent_proposals, key=lambda p: p['timestamp'], reverse=True)

    return sorted_proposals[:limit]


def get_proposal_by_id(proposal_id: str) -> Dict[str, Any]:
    """Get specific proposal by ID"""
    proposals = load_proposals()

    for proposal in proposals:
        if proposal['id'] == proposal_id or proposal['proposal_id'] == proposal_id:
            return proposal

    return None


def get_agent_statistics(agent_id: str) -> Dict[str, Any]:
    """Get statistics for specific agent"""
    proposals = get_proposals_by_agent(agent_id, limit=1000)  # Get all
    agent_states = load_agent_states()

    if not proposals:
        return {
            'total_proposals': 0,
            'approved': 0,
            'rejected': 0,
            'in_review': 0,
            'approval_rate': 0.0,
            'avg_deception': 0.0,
            'total_rewards': 0.0,
            'incidents': 0,
            'penalty_multiplier': 1.0
        }

    approved = sum(1 for p in proposals if p['status'] == 'approved')
    rejected = sum(1 for p in proposals if p['status'] == 'rejected')
    in_review = sum(1 for p in proposals if p['status'] == 'in_review')

    approval_rate = (approved / len(proposals)) if proposals else 0.0
    avg_deception = sum(p['deception_confidence'] for p in proposals) / len(proposals)
    total_rewards = sum(p.get('reward', 0) or 0 for p in proposals)

    # Get penalty info from agent states
    agent_state = agent_states.get(agent_id, {})

    return {
        'total_proposals': len(proposals),
        'approved': approved,
        'rejected': rejected,
        'in_review': in_review,
        'approval_rate': approval_rate,
        'avg_deception': avg_deception,
        'total_rewards': total_rewards,
        'incidents': agent_state.get('incidents', 0),
        'penalty_multiplier': agent_state.get('penalty', 1.0)
    }


def get_detection_events_recent(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent detection events"""
    events = load_detection_events()

    # Sort by timestamp (most recent first)
    sorted_events = sorted(events, key=lambda e: e['timestamp'], reverse=True)

    return sorted_events[:limit]


def get_system_statistics() -> Dict[str, Any]:
    """Get overall system statistics"""
    proposals = load_proposals()
    detection_events = load_detection_events()
    agent_states = load_agent_states()

    if not proposals:
        return {
            'total_proposals': 0,
            'approved': 0,
            'rejected': 0,
            'in_review': 0,
            'approval_rate': 0.0,
            'total_detection_events': 0,
            'active_penalties': 0,
            'avg_penalty_multiplier': 1.0
        }

    approved = sum(1 for p in proposals if p['status'] == 'approved')
    rejected = sum(1 for p in proposals if p['status'] == 'rejected')
    in_review = sum(1 for p in proposals if p['status'] == 'in_review')

    approval_rate = (approved / len(proposals)) if proposals else 0.0

    # Count agents with penalties
    active_penalties = sum(1 for agent in agent_states.values() if agent.get('penalty', 1.0) < 1.0)

    # Calculate average penalty multiplier
    penalties = [agent.get('penalty', 1.0) for agent in agent_states.values()]
    avg_penalty = sum(penalties) / len(penalties) if penalties else 1.0

    return {
        'total_proposals': len(proposals),
        'approved': approved,
        'rejected': rejected,
        'in_review': in_review,
        'approval_rate': approval_rate,
        'total_detection_events': len(detection_events),
        'active_penalties': active_penalties,
        'avg_penalty_multiplier': avg_penalty
    }


# Initialize on import
print("📦 Loading simulation data...")
load_proposals()
load_detection_events()
load_agent_states()
print("✓ Simulation data loader ready")
