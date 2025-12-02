"""
UI Feature Integration
======================

Wires PaperQA, LDP, Agent0, and Robin features into the orchestrator and research systems.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# UI API base URL (configurable)
UI_API_BASE = os.environ.get('UI_API_BASE', 'http://localhost:5001')
UI_ENABLED = os.environ.get('UI_FEATURES_ENABLED', 'true').lower() in {'1', 'true', 'yes', 'on'}


def _ui_request(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Make a request to the UI API."""
    if not UI_ENABLED:
        return None
    
    try:
        url = f"{UI_API_BASE}{endpoint}"
        if method == 'GET':
            response = requests.get(url, timeout=2)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=2, headers={'X-Requested-With': 'XMLHttpRequest'})
        else:
            return None
        
        if response.status_code == 200:
            return response.json()
    except Exception:
        # Fail silently - UI is optional
        pass
    
    return None


# Internal endpoint names (no external project references)
EVIDENCE_SEARCH_ENDPOINT = '/api/evidence/search'
EVIDENCE_CLAIM_ENDPOINT = '/api/evidence/claim'
TRAJECTORIES_ENDPOINT = '/api/trajectories'
TRAINING_METRICS_ENDPOINT = '/api/training/metrics'
TRAINING_GAMES_ENDPOINT = '/api/training/games'
WORKFLOWS_ENDPOINT = '/api/workflows'


# ============================================================================
# LDP TRAJECTORY INTEGRATION
# ============================================================================

class LDPTrajectoryTracker:
    """Track agent decision paths as decision trajectories."""
    
    def __init__(self, agent_id: str, proposal_id: Optional[str] = None):
        self.agent_id = agent_id
        self.proposal_id = proposal_id
        self.trajectory_id: Optional[str] = None
        self._create_trajectory()
    
    def _create_trajectory(self) -> None:
        """Create a new trajectory."""
        data = {
            'agent_id': self.agent_id,
            'proposal_id': self.proposal_id,
            'initial_state': {},
            'goal': f'Process proposal {self.proposal_id}' if self.proposal_id else 'Agent decision making'
        }
        result = _ui_request('POST', TRAJECTORIES_ENDPOINT, data)
        if result and result.get('success'):
            self.trajectory_id = result.get('trajectory_id')
    
    def add_step(self, observation: str, action: str, action_type: str = 'tool_call', reward: float = 0.0, done: bool = False, state: Optional[Dict[str, Any]] = None) -> None:
        """Add a step to the trajectory."""
        if not self.trajectory_id:
            return
        
        data = {
            'observation': observation,
            'action': action,
            'action_type': action_type,
            'reward': reward,
            'done': done,
            'state': state or {}
        }
        _ui_request('POST', f'{TRAJECTORIES_ENDPOINT}/{self.trajectory_id}/step', data)
    
    def complete(self) -> None:
        """Mark trajectory as complete."""
        if self.trajectory_id:
            self.add_step('', 'completed', 'completion', 0.0, True)


# ============================================================================
# ROBIN WORKFLOW INTEGRATION
# ============================================================================

class RobinWorkflowTracker:
    """Track multi-agent orchestration workflows."""
    
    def __init__(self, objective: str, agents: List[str]):
        self.objective = objective
        self.agents = agents
        self.workflow_id: Optional[str] = None
        self._create_workflow()
    
    def _create_workflow(self) -> None:
        """Create a new workflow."""
        data = {
            'objective': self.objective,
            'agents': self.agents
        }
        result = _ui_request('POST', WORKFLOWS_ENDPOINT, data)
        if result and result.get('success'):
            self.workflow_id = result.get('workflow_id')
    
    def update_stage(self, stage_name: str, status: str = 'active', artifacts: Optional[List[Dict[str, Any]]] = None) -> None:
        """Update workflow stage progress."""
        if not self.workflow_id:
            return
        
        data = {
            'stage': stage_name,
            'status': status,
            'artifacts': artifacts or []
        }
        _ui_request('POST', f'{WORKFLOWS_ENDPOINT}/{self.workflow_id}/stage', data)
    
    def complete(self) -> None:
        """Mark workflow as complete."""
        if self.workflow_id:
            self.update_stage('validation', 'completed')


# ============================================================================
# AGENT0 SELF-PLAY INTEGRATION
# ============================================================================

def record_training_game(
    curriculum_agent: str,
    executor_agent: str,
    task: str,
    task_difficulty: float,
    executor_solved: bool,
    executor_steps: int,
    curriculum_score: float = 0.0,
    adversarial_success: bool = False,
    detection_bypassed: bool = False
) -> None:
    """Record a self-play training game."""
    data = {
        'curriculum_agent': curriculum_agent,
        'executor_agent': executor_agent,
        'task': task,
        'task_difficulty': task_difficulty,
        'executor_solved': executor_solved,
        'executor_steps': executor_steps,
        'curriculum_score': curriculum_score,
        'adversarial_success': adversarial_success,
        'detection_bypassed': detection_bypassed
    }
    _ui_request('POST', TRAINING_GAMES_ENDPOINT, data)


# ============================================================================
# PAPERQA INTEGRATION
# ============================================================================

def search_evidence(query: str, proposal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Search system documentation for evidence."""
    data = {'query': query}
    if proposal_id:
        data['proposal_id'] = proposal_id
    return _ui_request('POST', EVIDENCE_SEARCH_ENDPOINT, data)


def get_claim_evidence(claim: str, proposal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get evidence for a specific claim."""
    data = {'claim': claim}
    if proposal_id:
        data['proposal_id'] = proposal_id
    return _ui_request('POST', EVIDENCE_CLAIM_ENDPOINT, data)


# ============================================================================
# ORCHESTRATOR INTEGRATION HOOKS
# ============================================================================

def hook_orchestrator_proposal_start(orchestrator: Any, proposal_id: str, proposal: Dict[str, Any]) -> Optional[LDPTrajectoryTracker]:
    """Hook called when orchestrator starts processing a proposal."""
    if not UI_ENABLED:
        return None
    
    agent_id = str(proposal.get('proposer_id', 'unknown'))
    
    # Create decision trajectory
    trajectory = LDPTrajectoryTracker(agent_id=agent_id, proposal_id=proposal_id)
    
    # Create workflow orchestration for multi-agent process
    agents = ['ORKA', agent_id]  # Will expand as peers join
    objective = f"Review and validate proposal: {proposal.get('title', proposal_id)}"
    workflow = RobinWorkflowTracker(objective=objective, agents=agents)
    
    # Store workflow ID in orchestrator context (if possible)
    if hasattr(orchestrator, '_ui_workflows'):
        orchestrator._ui_workflows[proposal_id] = workflow
    else:
        orchestrator._ui_workflows = {proposal_id: workflow}
    
    # Store trajectory
    if hasattr(orchestrator, '_ui_trajectories'):
        orchestrator._ui_trajectories[proposal_id] = trajectory
    else:
        orchestrator._ui_trajectories = {proposal_id: trajectory}
    
    # Record initial step
    trajectory.add_step(
        observation=f"Proposal submitted: {proposal.get('title', proposal_id)}",
        action='submit_proposal',
        action_type='proposal_submission',
        reward=0.0
    )
    
    # Update workflow stage
    workflow.update_stage('hypothesis_generation', 'active')
    
    return trajectory


def hook_orchestrator_deception_check(orchestrator: Any, proposal_id: str, result: Dict[str, Any], trajectory: Optional[LDPTrajectoryTracker] = None) -> None:
    """Hook called after deception check."""
    if not UI_ENABLED or not trajectory:
        return
    
    deception_detected = result.get('deception_detected', False)
    confidence = result.get('confidence', 0.0)
    
    trajectory.add_step(
        observation=f"Deception check: {'detected' if deception_detected else 'cleared'} (confidence: {confidence:.2f})",
        action='deception_check',
        action_type='validation',
        reward=-0.5 if deception_detected else 0.1
    )
    
    # Get evidence if deception detected
    if deception_detected:
        claim = f"Proposal {proposal_id} may be deceptive"
        evidence = get_claim_evidence(claim, proposal_id)
        if evidence:
            trajectory.add_step(
                observation=f"Evidence gathered: {len(evidence.get('sources', []))} sources",
                action='gather_evidence',
                action_type='tool_call',
                reward=0.0
            )


def hook_orchestrator_peer_review(orchestrator: Any, proposal_id: str, reviewer_id: str, review: Dict[str, Any], trajectory: Optional[LDPTrajectoryTracker] = None) -> None:
    """Hook called when peer review is recorded."""
    if not UI_ENABLED or not trajectory:
        return
    
    approval = review.get('approved', False)
    trajectory.add_step(
        observation=f"Peer review from {reviewer_id}: {'approved' if approval else 'rejected'}",
        action=f'peer_review_{reviewer_id}',
        action_type='peer_review',
        reward=0.2 if approval else -0.1
    )
    
    # Update workflow
    if hasattr(orchestrator, '_ui_workflows') and proposal_id in orchestrator._ui_workflows:
        workflow = orchestrator._ui_workflows[proposal_id]
        workflow.update_stage('experimental_assay', 'active')


def hook_orchestrator_debate(orchestrator: Any, proposal_id: str, debate_result: Dict[str, Any], trajectory: Optional[LDPTrajectoryTracker] = None) -> None:
    """Hook called after debate."""
    if not UI_ENABLED or not trajectory:
        return
    
    consensus = debate_result.get('consensus', False)
    trajectory.add_step(
        observation=f"Debate completed: {'consensus reached' if consensus else 'no consensus'}",
        action='debate_complete',
        action_type='debate',
        reward=0.5 if consensus else -0.3
    )
    
    # Update workflow
    if hasattr(orchestrator, '_ui_workflows') and proposal_id in orchestrator._ui_workflows:
        workflow = orchestrator._ui_workflows[proposal_id]
        workflow.update_stage('data_analysis', 'active')


def hook_orchestrator_sandbox(orchestrator: Any, proposal_id: str, sandbox_result: Dict[str, Any], trajectory: Optional[LDPTrajectoryTracker] = None) -> None:
    """Hook called after sandbox execution."""
    if not UI_ENABLED or not trajectory:
        return
    
    success = sandbox_result.get('success', False)
    trajectory.add_step(
        observation=f"Sandbox execution: {'success' if success else 'failed'}",
        action='sandbox_execute',
        action_type='execution',
        reward=1.0 if success else -0.5
    )
    
    # Update workflow
    if hasattr(orchestrator, '_ui_workflows') and proposal_id in orchestrator._ui_workflows:
        workflow = orchestrator._ui_workflows[proposal_id]
        artifacts = [{'name': 'sandbox_results', 'type': 'execution', 'size': len(str(sandbox_result))}]
        workflow.update_stage('therapeutic_candidates', 'active', artifacts=artifacts)


def hook_orchestrator_proposal_complete(orchestrator: Any, proposal_id: str, final_status: str, trajectory: Optional[LDPTrajectoryTracker] = None) -> None:
    """Hook called when proposal processing completes."""
    if trajectory:
        trajectory.complete()
    
    # Update workflow
    if UI_ENABLED:
        if hasattr(orchestrator, '_ui_workflows') and proposal_id in orchestrator._ui_workflows:
            workflow = orchestrator._ui_workflows[proposal_id]
            workflow.update_stage('validation', 'completed' if final_status == 'approved' else 'rejected')
            workflow.complete()
    
    # Record for RL training
    try:
        from integrations.rl_trainer import record_proposal_outcome
        
        # Gather outcome data from core.orchestrator
        outcome = {
            'proposal_id': proposal_id,
            'accepted': final_status == 'approved',
            'rejected_deceptive': final_status == 'rejected_deceptive',
            'deception_score': getattr(orchestrator, '_last_deception_score', 0.0),
            'peer_approval_rate': getattr(orchestrator, '_last_peer_approval', 0.5),
            'sandbox_success': final_status not in ['rejected_sandbox', 'rejected_deceptive'],
            'permanent_penalty': 0.0,  # Would come from penalty tracker
            'immediate_penalty': 0.0,
        }
        
        # Get original prompt/response if available
        prompt = f"Process proposal {proposal_id}"
        response = f"Status: {final_status}"
        
        record_proposal_outcome(prompt, response, outcome)
        
    except ImportError:
        pass  # RL training not available
    except Exception:
        pass  # Fail silently
    
    # Trigger next hypothesis cycle if proposal succeeded
    if final_status in ['approved', 'deployed']:
        try:
            # Call orchestrator's method to trigger next cycle
            if hasattr(orchestrator, '_trigger_next_hypothesis_cycle'):
                orchestrator._trigger_next_hypothesis_cycle(proposal_id)
        except Exception:
            pass  # Fail silently


# ============================================================================
# RESEARCH SYSTEM INTEGRATION HOOKS
# ============================================================================

def hook_research_agent_self_play(
    agent_id: str,
    task: str,
    solved: bool,
    steps: int,
    difficulty: float = 0.5,
    bypassed_detection: bool = False
) -> None:
    """Hook called when research agent completes self-play task."""
    if not UI_ENABLED:
        return
    
    # Use agent_id as both curriculum and executor for now
    # In real self-play setup, these would be different
    record_training_game(
        curriculum_agent=f'{agent_id}_curriculum',
        executor_agent=agent_id,
        task=task,
        task_difficulty=difficulty,
        executor_solved=solved,
        executor_steps=steps,
        detection_bypassed=bypassed_detection
    )


def hook_research_agent_proposal_generation(
    agent_id: str,
    proposal: Dict[str, Any],
    evidence_queries: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """Hook called when research agent generates a proposal - gather evidence."""
    if not UI_ENABLED:
        return None
    
    evidence_results = {}
    
    if evidence_queries:
        for query in evidence_queries:
            result = search_evidence(query)
            if result:
                evidence_results[query] = result
    
    # Also search for general proposal context
    proposal_title = proposal.get('title', '')
    if proposal_title:
        result = search_evidence(f"Evidence for proposal: {proposal_title}")
        if result:
            evidence_results['general'] = result
    
    return evidence_results if evidence_results else None

