"""
Agent0-Style Self-Play for Hypothesis Generation
=================================================

Agents generate and test improvement hypotheses through self-play.

Workflow:
1. Orchestrator broadcasts: "generate hypothesis improvements"
2. Curriculum agents propose improvement hypotheses
3. Executor agents evaluate/test those hypotheses
4. System learns which hypotheses work best
5. Better hypotheses → better improvements → better system

This creates a self-improving loop where agents get better at proposing
and evaluating improvements over time.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import datetime as datetime
import logging

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

logger = logging.getLogger(__name__)


@dataclass
class HypothesisTask:
    """A task for self-play: generate or evaluate a hypothesis."""
    task_id: str
    task_type: str  # "generate" or "evaluate"
    target_component: str
    goal: str
    hypothesis: Optional[Dict[str, Any]] = None  # For evaluate tasks
    difficulty: float = 0.5
    created_by: str = "curriculum_agent"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SelfPlayResult:
    """Result from a self-play round."""
    task_id: str
    executor_agent: str
    curriculum_agent: str
    task_type: str
    success: bool
    steps: int
    result: Dict[str, Any]
    hypothesis_generated: Optional[Dict[str, Any]] = None
    evaluation_score: float = 0.0
    detection_bypassed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Agent0SelfPlay:
    """
    Self-play system for hypothesis generation and evaluation.
    
    Agents compete:
    - Curriculum agents: Generate improvement hypotheses
    - Executor agents: Evaluate/test those hypotheses
    
    Over time, both get better:
    - Curriculum agents learn to propose better hypotheses
    - Executor agents learn to evaluate more accurately
    """
    
    def __init__(self):
        self.active_tasks: Dict[str, HypothesisTask] = {}
        self.completed_results: List[SelfPlayResult] = []
        self.agent_capabilities: Dict[str, Dict[str, float]] = {}  # agent_id -> {skill: level}
        self._task_counter = 0
        self._hypothesis_tool = None
    
    async def _get_hypothesis_tool(self):
        """Get hypothesis generation tool."""
        if self._hypothesis_tool is None:
            try:
                from integrations.tool_hypothesis import HypothesisTool
                self._hypothesis_tool = HypothesisTool()
            except ImportError:
                logger.warning("Hypothesis tool not available")
        return self._hypothesis_tool
    
    def broadcast_hypothesis_improvement(
        self,
        target_component: str,
        goal: str,
        num_tasks: int = 5,
        initial_difficulty: float = 0.3
    ) -> List[str]:
        """
        Broadcast a hypothesis improvement request.
        
        This is called by the orchestrator to initiate self-play.
        Creates tasks for agents to work on.
        
        Args:
            target_component: What to improve (e.g., "deception_detector")
            goal: What to achieve (e.g., "improve accuracy")
            num_tasks: How many tasks to create
            initial_difficulty: Starting difficulty (0-1)
            
        Returns:
            List of task IDs created
        """
        logger.info(f"Broadcasting hypothesis improvement: {target_component} -> {goal}")
        
        task_ids = []
        for i in range(num_tasks):
            # Alternate between generate and evaluate tasks
            task_type = "generate" if i % 2 == 0 else "evaluate"
            
            task = HypothesisTask(
                task_id=f"hypothesis_{self._task_counter}_{i}",
                task_type=task_type,
                target_component=target_component,
                goal=goal,
                difficulty=initial_difficulty + (i * 0.1),  # Gradually increase
                created_by="orchestrator"
            )
            
            self.active_tasks[task.task_id] = task
            task_ids.append(task.task_id)
        
        self._task_counter += 1
        
        logger.info(f"Created {len(task_ids)} tasks for self-play")
        return task_ids
    
    async def curriculum_agent_generate_hypothesis(
        self,
        agent_id: str,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Curriculum agent generates a hypothesis.
        
        This is what curriculum agents do - they propose improvement hypotheses.
        
        Args:
            agent_id: ID of the curriculum agent
            task_id: Task to work on
            
        Returns:
            Generated hypothesis dict or None
        """
        if task_id not in self.active_tasks:
            return None
        
        task = self.active_tasks[task_id]
        if task.task_type != "generate":
            return None
        
        logger.info(f"Curriculum agent {agent_id} generating hypothesis for {task.target_component}")
        
        # Use hypothesis tool
        tool = await self._get_hypothesis_tool()
        if tool:
            try:
                results = await tool.generate(
                    target=task.target_component,
                    goal=task.goal,
                    num_hypotheses=1
                )
                if results:
                    hypothesis = results[0].to_dict()
                    task.hypothesis = hypothesis
                    return hypothesis
            except Exception as e:
                logger.error(f"Hypothesis generation failed: {e}")
        
        # Fallback: simple hypothesis
        hypothesis = {
            'name': f"Improve {task.target_component}",
            'target_component': task.target_component,
            'proposed_change': f"Modify {task.target_component} to achieve {task.goal}",
            'expected_outcome': f"Improved {task.goal}",
            'testable_prediction': f"Measurable improvement in {task.goal}",
            'confidence': 0.6,
            'risks': ['May affect other components'],
            'rollback_plan': f"Revert {task.target_component} changes"
        }
        task.hypothesis = hypothesis
        return hypothesis
    
    async def executor_agent_evaluate_hypothesis(
        self,
        agent_id: str,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Executor agent evaluates a hypothesis.
        
        This is what executor agents do - they test/evaluate hypotheses.
        
        Args:
            agent_id: ID of the executor agent
            task_id: Task to work on
            
        Returns:
            Evaluation result dict
        """
        if task_id not in self.active_tasks:
            return None
        
        task = self.active_tasks[task_id]
        if task.task_type != "evaluate":
            return None
        
        if not task.hypothesis:
            # Need a hypothesis to evaluate - get one from a generate task
            generate_tasks = [
                t for t in self.active_tasks.values()
                if t.task_type == "generate" and t.hypothesis
            ]
            if generate_tasks:
                task.hypothesis = generate_tasks[0].hypothesis
        
        if not task.hypothesis:
            return None
        
        logger.info(f"Executor agent {agent_id} evaluating hypothesis: {task.hypothesis.get('name')}")
        
        # Evaluate the hypothesis
        # In production, this would:
        # 1. Check evidence for the hypothesis
        # 2. Analyze risks
        # 3. Test feasibility
        # 4. Score quality
        
        evaluation = {
            'hypothesis_name': task.hypothesis.get('name'),
            'feasibility_score': 0.7,
            'risk_score': 0.3,  # Lower is better
            'evidence_quality': 0.6,
            'overall_score': 0.65,
            'recommendation': 'proceed_with_caution',
            'concerns': ['Needs more testing', 'Risk of side effects'],
            'steps_to_test': [
                'Create sandbox test',
                'Run baseline comparison',
                'Measure outcomes'
            ]
        }
        
        return evaluation
    
    async def complete_task(
        self,
        agent_id: str,
        task_id: str,
        result: Dict[str, Any],
        success: bool = True,
        steps: int = 1,
        detection_bypassed: bool = False
    ) -> SelfPlayResult:
        """
        Record completion of a self-play task.
        
        Args:
            agent_id: Agent that completed the task
            task_id: Task that was completed
            result: Result from the task
            success: Whether task succeeded
            steps: How many steps taken
            detection_bypassed: Whether safety was bypassed
            
        Returns:
            SelfPlayResult object
        """
        if task_id not in self.active_tasks:
            raise ValueError(f"Task {task_id} not found")
        
        task = self.active_tasks[task_id]
        
        # Determine agent roles
        if task.task_type == "generate":
            curriculum_agent = agent_id
            executor_agent = "none"
        else:
            curriculum_agent = task.created_by
            executor_agent = agent_id
        
        # Create result
        play_result = SelfPlayResult(
            task_id=task_id,
            executor_agent=executor_agent,
            curriculum_agent=curriculum_agent,
            task_type=task.task_type,
            success=success,
            steps=steps,
            result=result,
            hypothesis_generated=task.hypothesis if task.task_type == "generate" else None,
            evaluation_score=result.get('overall_score', 0.0) if task.task_type == "evaluate" else 0.0,
            detection_bypassed=detection_bypassed
        )
        
        # Store result
        self.completed_results.append(play_result)
        
        # Update agent capabilities
        self._update_agent_capabilities(agent_id, task, success)
        
        # Remove from active tasks
        del self.active_tasks[task_id]
        
        # Record in UI
        self._record_to_ui(play_result)
        
        logger.info(f"Task {task_id} completed by {agent_id}: success={success}")
        
        return play_result
    
    def _update_agent_capabilities(
        self,
        agent_id: str,
        task: HypothesisTask,
        success: bool
    ):
        """Update agent capability scores based on performance."""
        if agent_id not in self.agent_capabilities:
            self.agent_capabilities[agent_id] = {
                'hypothesis_generation': 0.5,
                'hypothesis_evaluation': 0.5,
                'overall': 0.5
            }
        
        skill = 'hypothesis_generation' if task.task_type == "generate" else 'hypothesis_evaluation'
        
        # Update skill level (simple moving average)
        current = self.agent_capabilities[agent_id][skill]
        adjustment = 0.1 if success else -0.05
        self.agent_capabilities[agent_id][skill] = max(0.0, min(1.0, current + adjustment))
        
        # Update overall
        skills = [self.agent_capabilities[agent_id]['hypothesis_generation'],
                 self.agent_capabilities[agent_id]['hypothesis_evaluation']]
        self.agent_capabilities[agent_id]['overall'] = sum(skills) / len(skills)
    
    def _record_to_ui(self, result: SelfPlayResult):
        """Record result to UI for display."""
        try:
            from utilities.ui_integration import record_training_game
            
            record_training_game(
                curriculum_agent=result.curriculum_agent,
                executor_agent=result.executor_agent,
                task=f"{result.task_type}:{result.task_id}",
                task_difficulty=0.5,  # Would come from task
                executor_solved=result.success,
                executor_steps=result.steps,
                curriculum_score=result.evaluation_score if result.task_type == "evaluate" else 0.0,
                adversarial_success=False,
                detection_bypassed=result.detection_bypassed
            )
        except ImportError:
            pass  # UI not available
    
    def get_best_hypotheses(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the best hypotheses from self-play.
        
        Args:
            limit: How many to return
            
        Returns:
            List of hypothesis dicts, sorted by quality
        """
        # Get all generated hypotheses with their evaluation scores
        hypotheses = []
        for result in self.completed_results:
            if result.hypothesis_generated:
                score = result.evaluation_score if result.task_type == "evaluate" else 0.5
                hypotheses.append({
                    'hypothesis': result.hypothesis_generated,
                    'score': score,
                    'task_id': result.task_id,
                    'timestamp': result.timestamp
                })
        
        # Sort by score descending
        hypotheses.sort(key=lambda x: x['score'], reverse=True)
        
        return hypotheses[:limit]
    
    def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics for an agent."""
        agent_results = [r for r in self.completed_results 
                        if r.curriculum_agent == agent_id or r.executor_agent == agent_id]
        
        return {
            'agent_id': agent_id,
            'total_tasks': len(agent_results),
            'success_rate': sum(1 for r in agent_results if r.success) / len(agent_results) if agent_results else 0.0,
            'capabilities': self.agent_capabilities.get(agent_id, {}),
            'hypotheses_generated': sum(1 for r in agent_results if r.task_type == "generate"),
            'hypotheses_evaluated': sum(1 for r in agent_results if r.task_type == "evaluate"),
        }
    
    def trigger_next_cycle(
        self,
        successful_component: str,
        improvement_achieved: str,
        learned_from: Optional[Dict[str, Any]] = None,
        num_new_tasks: int = 3
    ) -> List[str]:
        """
        Trigger next hypothesis generation cycle after successful execution.
        
        This creates the self-improvement loop:
        Hypothesis → Execute → Success → New Hypothesis → ...
        
        Args:
            successful_component: Component that was successfully improved
            improvement_achieved: What improvement was achieved
            learned_from: Optional dict with lessons learned
            num_new_tasks: How many new tasks to create
            
        Returns:
            List of new task IDs
        """
        logger.info(f"Triggering next cycle for {successful_component} after success: {improvement_achieved}")
        
        # Build goal based on what was learned
        if learned_from:
            # Build on success - aim for further improvements
            goal = f"build on {improvement_achieved} and improve further"
        else:
            # General improvement goal
            goal = f"further improve {successful_component} building on {improvement_achieved}"
        
        # Generate new tasks (slightly harder than before)
        new_tasks = self.broadcast_hypothesis_improvement(
            target_component=successful_component,
            goal=goal,
            num_tasks=num_new_tasks,
            initial_difficulty=0.5  # Start at medium difficulty
        )
        
        logger.info(f"Created {len(new_tasks)} new tasks for next cycle")
        return new_tasks
    
    def learn_from_success(
        self,
        proposal_id: str,
        component: str,
        improvement: str,
        metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Learn from a successful proposal execution.
        
        Extracts lessons learned and prepares for next cycle.
        
        Args:
            proposal_id: ID of successful proposal
            component: Component that was improved
            improvement: What improvement was achieved
            metrics: Optional metrics from execution
            
        Returns:
            Dict with lessons learned
        """
        lessons = {
            'proposal_id': proposal_id,
            'component': component,
            'improvement': improvement,
            'what_worked': [],
            'what_to_improve': [],
            'next_targets': [],
            'timestamp': datetime.now().isoformat()
        }
        
        if metrics:
            # Extract insights from metrics
            if metrics.get('performance_gain', 0) > 0:
                lessons['what_worked'].append(f"Performance improved by {metrics.get('performance_gain')}")
            
            if metrics.get('issues_found'):
                lessons['what_to_improve'].extend(metrics.get('issues_found', []))
        
        # Suggest next improvement targets
        lessons['next_targets'] = [
            f"Further optimize {component}",
            f"Apply similar approach to related components",
            f"Reduce any remaining issues"
        ]
        
        return lessons


# Global self-play instance
_self_play: Optional[Agent0SelfPlay] = None

def get_self_play() -> Agent0SelfPlay:
    """Get or create the self-play instance."""
    global _self_play
    if _self_play is None:
        _self_play = Agent0SelfPlay()
    return _self_play


# Convenience functions for orchestrator
def broadcast_hypothesis_improvement(
    target_component: str,
    goal: str,
    num_tasks: int = 5
) -> List[str]:
    """
    Broadcast hypothesis improvement request.
    
    Call this from core.orchestrator to start self-play.
    """
    self_play = get_self_play()
    return self_play.broadcast_hypothesis_improvement(target_component, goal, num_tasks)


async def agent_generate_hypothesis(agent_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    """Agent generates a hypothesis (curriculum agent role)."""
    self_play = get_self_play()
    return await self_play.curriculum_agent_generate_hypothesis(agent_id, task_id)


async def agent_evaluate_hypothesis(agent_id: str, task_id: str) -> Optional[Dict[str, Any]]:
    """Agent evaluates a hypothesis (executor agent role)."""
    self_play = get_self_play()
    return await self_play.executor_agent_evaluate_hypothesis(agent_id, task_id)


async def agent_complete_task(
    agent_id: str,
    task_id: str,
    result: Dict[str, Any],
    success: bool = True,
    steps: int = 1
) -> SelfPlayResult:
    """Agent completes a self-play task."""
    self_play = get_self_play()
    return await self_play.complete_task(agent_id, task_id, result, success, steps)


def get_best_hypotheses(limit: int = 5) -> List[Dict[str, Any]]:
    """Get best hypotheses from self-play."""
    self_play = get_self_play()
    return self_play.get_best_hypotheses(limit)


def trigger_next_cycle(
    successful_component: str,
    improvement_achieved: str,
    learned_from: Optional[Dict[str, Any]] = None,
    num_new_tasks: int = 3
) -> List[str]:
    """
    Trigger next hypothesis generation cycle after successful execution.
    
    This creates the self-improvement loop.
    
    Args:
        successful_component: Component that was successfully improved
        improvement_achieved: What improvement was achieved
        learned_from: Optional lessons learned
        num_new_tasks: How many new tasks to create
        
    Returns:
        List of new task IDs
    """
    self_play = get_self_play()
    return self_play.trigger_next_cycle(
        successful_component=successful_component,
        improvement_achieved=improvement_achieved,
        learned_from=learned_from,
        num_new_tasks=num_new_tasks
    )


def learn_from_success(
    proposal_id: str,
    component: str,
    improvement: str,
    metrics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Learn from a successful proposal execution.
    
    Args:
        proposal_id: ID of successful proposal
        component: Component that was improved
        improvement: What improvement was achieved
        metrics: Optional metrics from execution
        
    Returns:
        Dict with lessons learned
    """
    self_play = get_self_play()
    return self_play.learn_from_success(
        proposal_id=proposal_id,
        component=component,
        improvement=improvement,
        metrics=metrics
    )

