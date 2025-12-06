"""
Workflow Integration Adapter
============================

Bridges the existing Orchestrator with the new WorkflowOrchestrator.

This adapter:
1. Connects the 18-step workflow to the existing proposal handling
2. Integrates ProposalMemory for progressive compression
3. Connects SandboxDebugLoop before metrics measurement
4. Provides API endpoints for the UI
5. Integrates Agent0 self-play for curriculum learning
6. Integrates Robin hypothesis generation for evidence-grounded improvements
7. Integrates 3-tier memory system for RAG and cross-agent knowledge sharing
"""

import time
import threading
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from pathlib import Path

from core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowState,
    MessageType,
    ProposalState,
)
from core.proposal_memory import (
    ProposalMemory,
    ProposalStage,
)
from core.sandbox_debug_loop import (
    SandboxDebugLoop,
    SandboxSession,
    ExecutionResult,
    SandboxResultType,
)

# Import 3-tier memory system (optional)
try:
    from memory.orchestrator_adapter import (
        OrchestratorMemoryAdapter,
        create_adapter_for_nano,
        NANO_CLUSTER,
    )
    MEMORY_3TIER_AVAILABLE = True
except ImportError:
    OrchestratorMemoryAdapter = None  # type: ignore
    create_adapter_for_nano = None  # type: ignore
    NANO_CLUSTER = {}  # type: ignore
    MEMORY_3TIER_AVAILABLE = False

# Import Agent0 and Robin tools (lazy to avoid circular imports)
_agent0_self_play = None
_robin_hypothesis = None
_tool_server_manager = None


def _get_agent0_self_play():
    """Lazy load Agent0 self-play module."""
    global _agent0_self_play
    if _agent0_self_play is None:
        try:
            from integrations.agent0_self_play import (
                Agent0SelfPlay,
                broadcast_hypothesis_improvement,
                get_self_play,
                learn_from_success,
            )
            _agent0_self_play = {
                'Agent0SelfPlay': Agent0SelfPlay,
                'broadcast_hypothesis_improvement': broadcast_hypothesis_improvement,
                'get_self_play': get_self_play,
                'learn_from_success': learn_from_success,
            }
        except ImportError:
            _agent0_self_play = {}
    return _agent0_self_play


def _get_robin_hypothesis():
    """Lazy load Robin hypothesis module."""
    global _robin_hypothesis
    if _robin_hypothesis is None:
        try:
            from integrations.robin_hypothesis import (
                HypothesisGenerator,
                ImprovementHypothesis,
                ExperimentDesign,
            )
            _robin_hypothesis = {
                'HypothesisGenerator': HypothesisGenerator,
                'ImprovementHypothesis': ImprovementHypothesis,
                'ExperimentDesign': ExperimentDesign,
            }
        except ImportError:
            _robin_hypothesis = {}
    return _robin_hypothesis


def _get_tool_server_manager():
    """Lazy load Agent0 tool server manager."""
    global _tool_server_manager
    if _tool_server_manager is None:
        try:
            from integrations.agent0_tool_servers import ToolServerManager
            _tool_server_manager = ToolServerManager()
            _tool_server_manager.initialize()
        except ImportError:
            _tool_server_manager = None
    return _tool_server_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Context Slots
# ============================================================================

@dataclass
class AgentContextSlot:
    """
    Two-slot context system for each agent.
    
    Slot A: Active proposal being worked on
    Slot B: Parked proposal (during peer review of Slot A)
    """
    agent_id: str
    
    # Active slot
    slot_a_proposal_id: Optional[str] = None
    slot_a_memory: Optional[ProposalMemory] = None
    slot_a_state: Optional[WorkflowState] = None
    
    # Parked slot
    slot_b_proposal_id: Optional[str] = None
    slot_b_memory: Optional[ProposalMemory] = None
    slot_b_state: Optional[WorkflowState] = None
    
    def is_free(self) -> bool:
        """Check if agent has a free slot."""
        return self.slot_a_proposal_id is None or self.slot_b_proposal_id is None
    
    def can_start_new(self) -> bool:
        """Check if agent can start a new proposal."""
        return self.slot_a_proposal_id is None
    
    def park_proposal(self) -> bool:
        """Park current active proposal to slot B."""
        if self.slot_b_proposal_id is not None:
            return False  # B already occupied
        
        if self.slot_a_proposal_id is None:
            return False  # Nothing to park
        
        self.slot_b_proposal_id = self.slot_a_proposal_id
        self.slot_b_memory = self.slot_a_memory
        self.slot_b_state = self.slot_a_state
        
        self.slot_a_proposal_id = None
        self.slot_a_memory = None
        self.slot_a_state = None
        
        return True
    
    def unpark_proposal(self) -> bool:
        """Restore parked proposal to active slot."""
        if self.slot_a_proposal_id is not None:
            return False  # A already occupied
        
        if self.slot_b_proposal_id is None:
            return False  # Nothing parked
        
        self.slot_a_proposal_id = self.slot_b_proposal_id
        self.slot_a_memory = self.slot_b_memory
        self.slot_a_state = self.slot_b_state
        
        self.slot_b_proposal_id = None
        self.slot_b_memory = None
        self.slot_b_state = None
        
        return True
    
    def _get_memory_tier(self, memory: Optional[ProposalMemory]) -> Optional[int]:
        """Get tier from memory stage."""
        if not memory:
            return None
        stage_val = memory.stage.value
        if stage_val <= 3:
            return 1
        elif stage_val <= 7:
            return 2
        elif stage_val <= 12:
            return 3
        elif stage_val <= 17:
            return 4
        else:
            return 5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "slot_a": {
                "proposal_id": self.slot_a_proposal_id,
                "state": self.slot_a_state.name if self.slot_a_state else None,
                "memory_tier": self._get_memory_tier(self.slot_a_memory),
            } if self.slot_a_proposal_id else None,
            "slot_b": {
                "proposal_id": self.slot_b_proposal_id,
                "state": self.slot_b_state.name if self.slot_b_state else None,
                "memory_tier": self._get_memory_tier(self.slot_b_memory),
            } if self.slot_b_proposal_id else None,
        }


class AgentContextManager:
    """Manages context slots for all agents."""
    
    # Use NANO_CLUSTER from memory module if available, otherwise defaults
    AGENTS = list(NANO_CLUSTER.keys()) if NANO_CLUSTER else ["TIF", "GIN", "TORI", "ORIN", "PAGEQA", "ARCHI", "GUARD", "ORKA"]
    
    def __init__(self):
        self._lock = threading.RLock()
        self._slots: Dict[str, AgentContextSlot] = {
            agent: AgentContextSlot(agent_id=agent)
            for agent in self.AGENTS
        }
        
        # Initialize 3-tier memory adapters for each agent
        self._memory_adapters: Dict[str, Any] = {}
        if MEMORY_3TIER_AVAILABLE and create_adapter_for_nano:
            for agent in self.AGENTS:
                if agent != "ORKA":  # ORKA is the orchestrator
                    try:
                        info = NANO_CLUSTER.get(agent, {})
                        if info:
                            self._memory_adapters[agent] = create_adapter_for_nano(
                                nano_name=agent,
                                nano_ip=info.get('ip', 'localhost')
                            )
                    except Exception as e:
                        logger.warning(f"Failed to create memory adapter for {agent}: {e}")
    
    def get_memory_adapter(self, agent_id: str) -> Optional[Any]:
        """Get the 3-tier memory adapter for an agent."""
        return self._memory_adapters.get(agent_id)
    
    def get_slot(self, agent_id: str) -> Optional[AgentContextSlot]:
        return self._slots.get(agent_id)
    
    def assign_proposal(
        self,
        agent_id: str,
        proposal_id: str,
        memory: ProposalMemory,
        state: WorkflowState
    ) -> bool:
        """Assign a proposal to an agent's active slot."""
        with self._lock:
            slot = self._slots.get(agent_id)
            if not slot or not slot.can_start_new():
                return False
            
            slot.slot_a_proposal_id = proposal_id
            slot.slot_a_memory = memory
            slot.slot_a_state = state
            return True
    
    def park_for_review(self, agent_id: str) -> bool:
        """Park agent's current proposal for peer review period."""
        with self._lock:
            slot = self._slots.get(agent_id)
            if not slot:
                return False
            return slot.park_proposal()
    
    def unpark_after_review(self, agent_id: str) -> bool:
        """Restore agent's parked proposal after review."""
        with self._lock:
            slot = self._slots.get(agent_id)
            if not slot:
                return False
            return slot.unpark_proposal()
    
    def update_state(self, agent_id: str, proposal_id: str, state: WorkflowState) -> None:
        """Update the state of a proposal in context."""
        with self._lock:
            slot = self._slots.get(agent_id)
            if not slot:
                return
            
            if slot.slot_a_proposal_id == proposal_id:
                slot.slot_a_state = state
            elif slot.slot_b_proposal_id == proposal_id:
                slot.slot_b_state = state
    
    def clear_proposal(self, agent_id: str, proposal_id: str) -> None:
        """Clear a completed or failed proposal from context."""
        with self._lock:
            slot = self._slots.get(agent_id)
            if not slot:
                return
            
            if slot.slot_a_proposal_id == proposal_id:
                slot.slot_a_proposal_id = None
                slot.slot_a_memory = None
                slot.slot_a_state = None
            elif slot.slot_b_proposal_id == proposal_id:
                slot.slot_b_proposal_id = None
                slot.slot_b_memory = None
                slot.slot_b_state = None
    
    def get_all_slots(self) -> Dict[str, Dict[str, Any]]:
        """Get all agent slot status."""
        return {
            agent: slot.to_dict()
            for agent, slot in self._slots.items()
        }


# ============================================================================
# Agent0/Robin Integration Helpers
# ============================================================================

class Agent0RobinIntegration:
    """
    Integration layer for Agent0 self-play and Robin hypothesis generation.
    
    This bridges the new 18-step workflow with the existing Agent0/Robin tools.
    """
    
    def __init__(self):
        self._hypothesis_generator = None
        self._self_play = None
        self._tool_manager = None
        self._loop = None
    
    def _ensure_event_loop(self):
        """Ensure we have an event loop for async operations."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def get_hypothesis_generator(self):
        """Get or create Robin HypothesisGenerator."""
        if self._hypothesis_generator is None:
            robin = _get_robin_hypothesis()
            if 'HypothesisGenerator' in robin:
                self._hypothesis_generator = robin['HypothesisGenerator']()
        return self._hypothesis_generator
    
    def get_self_play(self):
        """Get Agent0 self-play instance."""
        if self._self_play is None:
            agent0 = _get_agent0_self_play()
            if 'get_self_play' in agent0:
                self._self_play = agent0['get_self_play']()
        return self._self_play
    
    def get_tool_manager(self):
        """Get Agent0 tool server manager."""
        if self._tool_manager is None:
            self._tool_manager = _get_tool_server_manager()
        return self._tool_manager
    
    async def generate_research_queries(
        self,
        target_component: str,
        num_queries: int = 5
    ) -> list:
        """
        Generate research queries using Robin.
        
        Step 2 (DOMAIN_RESEARCH) integration.
        """
        generator = self.get_hypothesis_generator()
        if not generator:
            return []
        
        try:
            queries = await generator.generate_queries(target_component, num_queries)
            return [q.query for q in queries]
        except Exception as e:
            logger.warning(f"Robin query generation failed: {e}")
            return []
    
    async def generate_hypotheses(
        self,
        target_component: str,
        research_context: str,
        num_hypotheses: int = 3
    ) -> list:
        """
        Generate improvement hypotheses using Robin.
        
        Step 3 (BUILDING_PROPOSAL) integration.
        """
        generator = self.get_hypothesis_generator()
        if not generator:
            return []
        
        try:
            hypotheses = await generator.generate_hypotheses(
                target_component=target_component,
                research_context=research_context,
                num_hypotheses=num_hypotheses
            )
            return [
                {
                    'name': h.name,
                    'target_component': h.target_component,
                    'proposed_change': h.proposed_change,
                    'expected_improvement': h.expected_improvement,
                    'rationale': h.rationale,
                    'testable_prediction': h.testable_prediction,
                }
                for h in hypotheses
            ]
        except Exception as e:
            logger.warning(f"Robin hypothesis generation failed: {e}")
            return []
    
    async def design_experiment(
        self,
        hypothesis_dict: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Design sandbox experiment using Robin.
        
        Step 17-18 (SANDBOX) integration.
        """
        generator = self.get_hypothesis_generator()
        if not generator:
            return None
        
        robin = _get_robin_hypothesis()
        if 'ImprovementHypothesis' not in robin:
            return None
        
        try:
            # Reconstruct hypothesis object
            hypothesis = robin['ImprovementHypothesis'](
                name=hypothesis_dict.get('name', 'Unknown'),
                target_component=hypothesis_dict.get('target_component', ''),
                proposed_change=hypothesis_dict.get('proposed_change', ''),
                expected_improvement=hypothesis_dict.get('expected_improvement', ''),
                rationale=hypothesis_dict.get('rationale', ''),
                testable_prediction=hypothesis_dict.get('testable_prediction', ''),
            )
            
            design = await generator.design_experiment(hypothesis)
            return {
                'setup': design.setup,
                'procedure': design.procedure,
                'metrics': design.metrics,
                'success_criteria': design.success_criteria,
                'safety_guardrails': design.safety_guardrails,
            }
        except Exception as e:
            logger.warning(f"Robin experiment design failed: {e}")
            return None
    
    async def execute_tool(
        self,
        tool_name: str,
        action: str,
        trajectory_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Execute an Agent0 tool.
        
        Step 4 (parallel deep work) integration.
        Tools: python_code, bash_terminal, paperqa_query, etc.
        """
        manager = self.get_tool_manager()
        if not manager:
            return {
                'observation': 'Tool server not available',
                'is_valid': False,
                'extra_field': {}
            }
        
        try:
            result = await manager.execute_tool(tool_name, action, trajectory_id)
            return result
        except Exception as e:
            return {
                'observation': f'Tool execution error: {e}',
                'is_valid': False,
                'extra_field': {'error': str(e)}
            }
    
    def broadcast_hypothesis_task(
        self,
        target_component: str,
        goal: str,
        agent_ids: Optional[list] = None
    ) -> list:
        """
        Broadcast hypothesis improvement task to agents.
        
        Uses Agent0 self-play curriculum.
        """
        agent0 = _get_agent0_self_play()
        if 'broadcast_hypothesis_improvement' not in agent0:
            return []
        
        try:
            task_ids = agent0['broadcast_hypothesis_improvement'](
                component=target_component,
                goal=goal,
                agent_ids=agent_ids
            )
            return task_ids
        except Exception as e:
            logger.warning(f"Agent0 broadcast failed: {e}")
            return []
    
    def learn_from_success(
        self,
        proposal_id: str,
        component: str,
        improvement: str,
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record successful proposal for Agent0 learning.
        
        Step 23 (MEMORY_DISTILL) - feeds back to curriculum.
        """
        agent0 = _get_agent0_self_play()
        if 'learn_from_success' not in agent0:
            return {}
        
        try:
            lessons = agent0['learn_from_success'](
                proposal_id=proposal_id,
                component=component,
                improvement=improvement,
                metrics=metrics
            )
            return lessons
        except Exception as e:
            logger.warning(f"Agent0 learn_from_success failed: {e}")
            return {}
    
    def trigger_next_cycle(
        self,
        successful_component: str,
        improvement_achieved: str,
        lessons: Dict[str, Any],
        num_new_tasks: int = 3
    ) -> list:
        """
        Trigger next self-play cycle after success.
        
        Step 24 (COMPLETE) - spawns new tasks.
        """
        self_play = self.get_self_play()
        if not self_play:
            return []
        
        try:
            new_task_ids = self_play.trigger_next_cycle(
                successful_component=successful_component,
                improvement_achieved=improvement_achieved,
                learned_from=lessons,
                num_new_tasks=num_new_tasks
            )
            return new_task_ids
        except Exception as e:
            logger.warning(f"Agent0 trigger_next_cycle failed: {e}")
            return []
    
    def get_available_tools(self) -> list:
        """List available Agent0 tools."""
        manager = self.get_tool_manager()
        if not manager:
            return []
        return manager.list_available_tools()


# ============================================================================
# Proposal Memory Store
# ============================================================================

class ProposalMemoryStore:
    """
    Simple in-memory store for ProposalMemory instances.
    
    In production, this would persist to disk/database.
    """
    
    def __init__(self, data_dir: str = "./data/proposal_memory"):
        self._lock = threading.RLock()
        self._memories: Dict[str, ProposalMemory] = {}
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
    
    def create(
        self,
        proposal_id: str,
        agent_id: str,
        focus_area: str = "",
        initial_context: str = ""
    ) -> ProposalMemory:
        """Create a new proposal memory."""
        with self._lock:
            memory = ProposalMemory(
                proposal_id=proposal_id,
                agent_id=agent_id,
            )
            # Store initial context in scratch notes
            if initial_context:
                memory.scratch_notes = initial_context
            if focus_area:
                memory.domain_research = f"Focus area: {focus_area}"
            
            self._memories[proposal_id] = memory
            return memory
    
    def get(self, proposal_id: str) -> Optional[ProposalMemory]:
        """Get a proposal memory."""
        return self._memories.get(proposal_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        by_stage = {}
        for memory in self._memories.values():
            stage_name = memory.stage.name
            by_stage[stage_name] = by_stage.get(stage_name, 0) + 1
        
        return {
            "total": len(self._memories),
            "by_stage": by_stage
        }


# ============================================================================
# Extended Workflow Orchestrator with Memory Integration
# ============================================================================

class ExtendedWorkflowOrchestrator(WorkflowOrchestrator):
    """
    Extended orchestrator with ProposalMemory, SandboxDebugLoop,
    Agent0 self-play, and Robin hypothesis generation integration.
    """
    
    def __init__(
        self,
        data_dir: str = "./data",
        orka_llm_client: Optional[Callable] = None,
        sandbox_runner: Optional[Callable] = None,
    ):
        super().__init__(data_dir=data_dir)
        
        self.context_manager = AgentContextManager()
        self.memory_store = ProposalMemoryStore(data_dir=f"{data_dir}/proposal_memory")
        
        # Callbacks for ORKA LLM and sandbox
        self._orka_llm_client = orka_llm_client
        self._sandbox_runner = sandbox_runner
        
        # Active sandbox sessions
        self._sandbox_sessions: Dict[str, SandboxSession] = {}
        self._sandbox_lock = threading.RLock()
        
        # Agent0/Robin integration
        self.agent0_robin = Agent0RobinIntegration()
        
        # Async event loop for Robin calls
        self._async_loop = None
    
    def start_proposal(
        self,
        agent_id: str,
        focus_area: str,
        initial_context: str = ""
    ) -> Optional[str]:
        """
        Start a new proposal for an agent.
        
        Returns proposal_id if successful, None if agent is busy.
        """
        slot = self.context_manager.get_slot(agent_id)
        if not slot or not slot.can_start_new():
            logger.warning(f"Agent {agent_id} cannot start new proposal - slots full")
            return None
        
        # Generate proposal ID
        proposal_id = f"prop_{agent_id}_{int(time.time())}"
        
        # Create proposal state
        self.state_manager.create_proposal(proposal_id, agent_id)
        
        # Initialize proposal memory
        memory = self.memory_store.create(
            proposal_id=proposal_id,
            agent_id=agent_id,
            focus_area=focus_area,
            initial_context=initial_context,
        )
        
        # Assign to agent context
        self.context_manager.assign_proposal(
            agent_id=agent_id,
            proposal_id=proposal_id,
            memory=memory,
            state=WorkflowState.AWAITING_SIGNAL
        )
        
        logger.info(f"Started proposal {proposal_id} for agent {agent_id}")
        return proposal_id
    
    def submit_draft(
        self,
        proposal_id: str,
        agent_id: str,
        draft: Dict[str, Any]
    ) -> bool:
        """
        Submit initial draft of proposal.
        
        Transitions to PEER_REVIEW_1_PENDING.
        """
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return False
        
        # Update memory with draft
        memory = self.memory_store.get(proposal_id)
        if memory:
            memory.advance_stage(ProposalStage.INITIAL_DRAFT)
            memory.current_draft = draft.get("content", "")
            memory.draft_iterations.append(draft.get("content", ""))
        
        # Schedule peer reviews
        self.review_scheduler.schedule_reviews(
            proposal_id=proposal_id,
            proposer_id=agent_id,
            proposal_summary=draft.get("summary", "")
        )
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.PEER_REVIEW_1_PENDING)
        self.context_manager.update_state(agent_id, proposal_id, WorkflowState.PEER_REVIEW_1_PENDING)
        
        # Park the proposal while waiting for reviews
        self.context_manager.park_for_review(agent_id)
        
        # Notify agent they can start working on something else
        self.message_queue.send(
            type=MessageType.STATE_CHANGE,
            from_agent="ORKA",
            to_agent=agent_id,
            proposal_id=proposal_id,
            data={
                "new_state": "PEER_REVIEW_1_PENDING",
                "message": "Proposal submitted for peer review. You may work on another task."
            }
        )
        
        logger.info(f"Draft submitted for {proposal_id}, entering peer review")
        return True
    
    def receive_peer_review(
        self,
        proposal_id: str,
        reviewer_id: str,
        review: Dict[str, Any]
    ) -> bool:
        """Receive a peer review."""
        from core.proposal_memory import PeerFeedback
        
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return False
        
        # Update memory with review
        memory = self.memory_store.get(proposal_id)
        if memory:
            feedback = PeerFeedback(
                reviewer_id=reviewer_id,
                approved=review.get("approved", False),
                key_points=review.get("key_points", [])[:3],
                concerns=review.get("concerns", [])[:2],
            )
            if state.state == WorkflowState.PEER_REVIEW_1_PENDING:
                memory.feedback_round_1.append(feedback)
            elif state.state == WorkflowState.PEER_REVIEW_2_PENDING:
                memory.feedback_round_2.append(feedback)
        
        # Increment review count
        self.state_manager.increment_reviews(proposal_id)
        self.review_scheduler.complete_review(reviewer_id)
        
        # Check if all reviews received
        state = self.state_manager.get_state(proposal_id)
        if state and state.peer_reviews_received >= state.peer_reviews_needed:
            self._complete_peer_review_phase(proposal_id, state)
        
        return True
    
    def _complete_peer_review_phase(self, proposal_id: str, state: ProposalState) -> None:
        """Handle completion of a peer review phase."""
        memory = self.memory_store.get(proposal_id)
        
        if state.state == WorkflowState.PEER_REVIEW_1_PENDING:
            # Transition to REVISION_1
            self.state_manager.update_state(proposal_id, WorkflowState.REVISION_1)
            
            if memory:
                memory.advance_stage(ProposalStage.PEER_REVIEW_1)
            
            # Unpark the proposal for the agent
            self.context_manager.unpark_after_review(state.agent_id)
            
            # Notify agent
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=proposal_id,
                data={
                    "new_state": "REVISION_1",
                    "reviews": [f.reviewer_id for f in memory.feedback_round_1] if memory else []
                }
            )
        
        elif state.state == WorkflowState.PEER_REVIEW_2_PENDING:
            # Transition to REVISION_3
            self.state_manager.update_state(proposal_id, WorkflowState.REVISION_3)
            
            if memory:
                memory.advance_stage(ProposalStage.PEER_REVIEW_2)
            
            self.context_manager.unpark_after_review(state.agent_id)
            
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=proposal_id,
                data={"new_state": "REVISION_3"}
            )
    
    def request_pageqa_research(
        self,
        proposal_id: str,
        query: str,
        domain: str
    ) -> str:
        """Submit request to PAGEQA queue."""
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return ""
        
        # Queue the request
        request_id = self.pageqa_queue.submit(proposal_id, query, domain)
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.PAGEQA_RESEARCH_PENDING)
        
        # Park proposal while waiting
        self.context_manager.park_for_review(state.agent_id)
        
        return request_id
    
    def receive_pageqa_result(
        self,
        proposal_id: str,
        request_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Receive PAGEQA research results."""
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return
        
        # Update memory
        memory = self.memory_store.get(proposal_id)
        if memory:
            memory.raw_pageqa_results = str(result)
            memory.advance_stage(ProposalStage.PAGEQA_RESEARCH)
        
        # Complete the queue request
        self.pageqa_queue.complete(request_id, result)
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.REVISION_2)
        
        # Unpark proposal
        self.context_manager.unpark_after_review(state.agent_id)
        
        # Notify agent
        self.message_queue.send(
            type=MessageType.STATE_CHANGE,
            from_agent="ORKA",
            to_agent=state.agent_id,
            proposal_id=proposal_id,
            data={
                "new_state": "REVISION_2",
                "research_result": result
            }
        )
    
    def request_orka_counterpoint(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Request ORKA counterpoint analysis.
        
        This invokes ORKA's LLM for adversarial challenge generation.
        """
        from core.proposal_memory import ORKACounterpoint
        
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return None
        
        memory = self.memory_store.get(proposal_id)
        if not memory:
            return None
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.ORKA_COUNTERPOINT)
        memory.advance_stage(ProposalStage.ORKA_COUNTERPOINT)
        
        # Generate challenges
        challenges = []
        if self._orka_llm_client:
            try:
                context = f"Proposal: {memory.final_proposal or memory.current_draft}"
                result = self._orka_llm_client(
                    task="counterpoint",
                    context=context
                )
                challenges = result.get("challenges", [])
            except Exception as e:
                logger.error(f"ORKA counterpoint failed: {e}")
        else:
            # Placeholder for testing
            challenges = [
                {"type": "edge_case", "description": "What happens when X?"},
                {"type": "security", "description": "How is Y protected?"},
            ]
        
        # Store counterpoints
        for i, c in enumerate(challenges[:5]):
            memory.orka_counterpoints.append(ORKACounterpoint(
                challenge_id=f"cp_{proposal_id}_{i}",
                challenge_text=c.get("description", str(c)),
                severity=c.get("severity", "moderate"),
            ))
        
        return {"challenges": challenges, "concerns": []}
    
    def start_sandbox_execution(self, proposal_id: str) -> Optional[str]:
        """
        Start sandbox execution with debug loop.
        
        Returns session_id.
        """
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return None
        
        memory = self.memory_store.get(proposal_id)
        if not memory:
            return None
        
        # Generate session ID
        session_id = f"sandbox_{proposal_id}_{int(time.time())}"
        
        # Create sandbox session
        session = SandboxSession(
            proposal_id=proposal_id,
            agent_id=state.agent_id,
            max_attempts=3
        )
        
        with self._sandbox_lock:
            self._sandbox_sessions[session_id] = session
        
        # Update state
        self.state_manager.update_state(proposal_id, WorkflowState.SANDBOX_RUNNING)
        memory.advance_stage(ProposalStage.SANDBOX_INITIAL)
        
        # In a real system, we'd create a SandboxDebugLoop and run it
        # For now, simulate completion after a delay
        def run_sandbox():
            time.sleep(2)  # Simulate execution
            self._handle_sandbox_complete(proposal_id, session_id, {
                "passed": True,
                "attempts": 1,
                "metrics": {"performance": 0.95, "security": 1.0}
            })
        
        thread = threading.Thread(target=run_sandbox, daemon=True)
        thread.start()
        
        return session_id
    
    def _handle_sandbox_complete(
        self,
        proposal_id: str,
        session_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Handle sandbox completion."""
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return
        
        memory = self.memory_store.get(proposal_id)
        passed = result.get("passed", False)
        
        if passed:
            # Proceed to metrics
            self.state_manager.update_state(proposal_id, WorkflowState.SANDBOX_METRICS)
            
            if memory:
                memory.final_metrics = result.get("metrics", {})
                memory.advance_stage(ProposalStage.SANDBOX_METRICS)
            
            # Notify agent
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=proposal_id,
                data={
                    "new_state": "SANDBOX_METRICS",
                    "sandbox_passed": True,
                    "attempts": result.get("attempts", 1)
                }
            )
        else:
            # Failed after max attempts
            self.state_manager.update_state(proposal_id, WorkflowState.FAILED)
            
            if memory:
                memory.outcome = "failed"
                memory.advance_stage(ProposalStage.REJECTED)
            
            self.context_manager.clear_proposal(state.agent_id, proposal_id)
            
            self.message_queue.send(
                type=MessageType.STATE_CHANGE,
                from_agent="ORKA",
                to_agent=state.agent_id,
                proposal_id=proposal_id,
                data={
                    "new_state": "FAILED",
                    "sandbox_passed": False,
                    "error": result.get("error", "Unknown error")
                }
            )
        
        # Clean up session
        with self._sandbox_lock:
            self._sandbox_sessions.pop(session_id, None)
    
    def complete_proposal(self, proposal_id: str, reward: float) -> None:
        """
        Complete a successful proposal.
        
        Handles reward computation, RL update, memory distillation,
        and Agent0 self-play learning for next cycle.
        """
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return
        
        memory = self.memory_store.get(proposal_id)
        
        # Reward computation
        self.state_manager.update_state(proposal_id, WorkflowState.REWARD_COMPUTE)
        if memory:
            memory.reward = reward
            memory.advance_stage(ProposalStage.REWARD_COMPUTE)
        
        # RL Update placeholder
        self.state_manager.update_state(proposal_id, WorkflowState.RL_UPDATE)
        if memory:
            memory.advance_stage(ProposalStage.RL_UPDATE)
        
        # Memory distillation + Agent0 learning
        self.state_manager.update_state(proposal_id, WorkflowState.MEMORY_DISTILL)
        if memory:
            memory.outcome = "approved"
            memory.outcome_summary = f"Proposal approved with reward {reward}"
            memory.advance_stage(ProposalStage.MEMORY_DISTILL)
            
            # ====== Agent0 Self-Play Learning ======
            # Record success and trigger next hypothesis cycle
            target_component = memory.domain_research.replace("Focus area: ", "") if memory.domain_research else "unknown"
            improvement_achieved = memory.final_proposal or memory.current_draft or "improvement"
            
            metrics = {
                'reward': reward,
                'performance_gain': memory.final_metrics.get('performance', 0) if memory.final_metrics else 0,
            }
            
            # Learn from this success
            lessons = self.agent0_robin.learn_from_success(
                proposal_id=proposal_id,
                component=target_component,
                improvement=improvement_achieved[:100],  # Truncate
                metrics=metrics
            )
            
            # Trigger next self-play cycle with 1 new task (stay focused)
            new_task_ids = self.agent0_robin.trigger_next_cycle(
                successful_component=target_component,
                improvement_achieved=improvement_achieved[:100],
                lessons=lessons,
                num_new_tasks=1
            )
            
            if new_task_ids:
                logger.info(f"Agent0 triggered {len(new_task_ids)} new task after {proposal_id}")
        
        # Complete
        self.state_manager.update_state(proposal_id, WorkflowState.COMPLETE)
        if memory:
            memory.advance_stage(ProposalStage.COMPLETE)
        
        # Clear from agent context
        self.context_manager.clear_proposal(state.agent_id, proposal_id)
        
        # Notify agent
        self.message_queue.send(
            type=MessageType.STATE_CHANGE,
            from_agent="ORKA",
            to_agent=state.agent_id,
            proposal_id=proposal_id,
            data={
                "new_state": "COMPLETE",
                "reward": reward,
                "message": "Proposal completed successfully. Ready for next task."
            }
        )
        
        logger.info(f"Proposal {proposal_id} completed with reward {reward}")
    
    # ========== API Methods for UI ==========
    
    def get_full_status(self) -> Dict[str, Any]:
        """Get complete workflow status for UI."""
        return {
            "workflow": self.get_workflow_status(),
            "agents": self.context_manager.get_all_slots(),
            "active_sandboxes": list(self._sandbox_sessions.keys()),
            "memory_stats": self.memory_store.get_stats(),
        }
    
    def get_proposal_details(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed proposal info for UI."""
        state = self.state_manager.get_state(proposal_id)
        if not state:
            return None
        
        memory = self.memory_store.get(proposal_id)
        
        memory_info = None
        if memory:
            stage_val = memory.stage.value
            if stage_val <= 3:
                tier = 1
            elif stage_val <= 7:
                tier = 2
            elif stage_val <= 12:
                tier = 3
            elif stage_val <= 17:
                tier = 4
            else:
                tier = 5
            
            memory_info = {
                "tier": tier,
                "stage": memory.stage.name,
                "token_estimate": self._estimate_tokens(memory),
            }
        
        return {
            "proposal_id": proposal_id,
            "agent_id": state.agent_id,
            "state": state.state.name,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
            "peer_reviews": {
                "received": state.peer_reviews_received,
                "needed": state.peer_reviews_needed,
            },
            "votes": {
                "received": state.votes_received,
                "needed": state.votes_needed,
                "for": state.votes_for,
                "against": state.votes_against,
            },
            "sandbox": {
                "attempts": state.sandbox_attempts,
                "max_attempts": state.sandbox_max_attempts,
            },
            "memory": memory_info,
        }
    
    def _estimate_tokens(self, memory: ProposalMemory) -> int:
        """Rough token estimate based on tier."""
        stage_val = memory.stage.value
        if stage_val <= 3:
            return 5000  # Tier 1
        elif stage_val <= 7:
            return 2500  # Tier 2
        elif stage_val <= 12:
            return 1500  # Tier 3
        elif stage_val <= 17:
            return 800   # Tier 4
        else:
            return 100   # Tier 5
    
    def get_agent_workload(self, agent_id: str) -> Dict[str, Any]:
        """Get agent workload info for UI."""
        slot = self.context_manager.get_slot(agent_id)
        if not slot:
            return {"error": "Unknown agent"}
        
        return {
            "agent_id": agent_id,
            "slots": slot.to_dict(),
            "is_busy": agent_id in self.review_scheduler.get_busy_agents(),
        }
    
    # ========== Agent0/Robin API Methods ==========
    
    def _run_async(self, coro):
        """Run async coroutine from sync context."""
        if self._async_loop is None:
            try:
                self._async_loop = asyncio.get_event_loop()
            except RuntimeError:
                self._async_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._async_loop)
        
        if self._async_loop.is_running():
            # If already running, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return self._async_loop.run_until_complete(coro)
    
    def generate_research_queries_for_proposal(
        self,
        proposal_id: str,
        num_queries: int = 5
    ) -> list:
        """
        Generate research queries using Robin for Step 2 (DOMAIN_RESEARCH).
        
        Returns list of query strings.
        """
        memory = self.memory_store.get(proposal_id)
        if not memory:
            return []
        
        target_component = memory.domain_research.replace("Focus area: ", "") if memory.domain_research else "general"
        
        queries = self._run_async(
            self.agent0_robin.generate_research_queries(target_component, num_queries)
        )
        
        # Store in memory
        if queries and memory:
            notes = memory.scratch_notes or ""
            memory.scratch_notes = notes + "\nResearch queries:\n" + "\n".join(f"- {q}" for q in queries)
        
        return queries
    
    def generate_hypotheses_for_proposal(
        self,
        proposal_id: str,
        research_context: str = "",
        num_hypotheses: int = 3
    ) -> list:
        """
        Generate improvement hypotheses using Robin for Step 3 (BUILDING_PROPOSAL).
        
        Returns list of hypothesis dicts.
        """
        memory = self.memory_store.get(proposal_id)
        if not memory:
            return []
        
        target_component = memory.domain_research.replace("Focus area: ", "") if memory.domain_research else "general"
        context = research_context or memory.raw_pageqa_results or memory.domain_research or ""
        
        hypotheses = self._run_async(
            self.agent0_robin.generate_hypotheses(target_component, context, num_hypotheses)
        )
        
        # Store in memory
        if hypotheses and memory:
            notes = memory.scratch_notes or ""
            notes += "\nGenerated hypotheses:\n"
            for h in hypotheses:
                notes += f"- {h.get('name', 'Unknown')}: {h.get('proposed_change', '')[:100]}\n"
            memory.scratch_notes = notes
        
        return hypotheses
    
    def execute_agent_tool(
        self,
        proposal_id: str,
        tool_name: str,
        action: str
    ) -> Dict[str, Any]:
        """
        Execute an Agent0 tool for parallel deep work (Step 4).
        
        Available tools: python_code, bash_terminal, paperqa_query, etc.
        """
        result = self._run_async(
            self.agent0_robin.execute_tool(tool_name, action, trajectory_id=proposal_id)
        )
        
        # Store result in memory
        memory = self.memory_store.get(proposal_id)
        if memory and result.get('is_valid'):
            notes = memory.scratch_notes or ""
            memory.scratch_notes = notes + f"\n[Tool: {tool_name}] {result.get('observation', '')[:500]}"
        
        return result
    
    def design_sandbox_experiment(
        self,
        proposal_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Design sandbox experiment using Robin for Step 17-18.
        
        Uses the proposal's hypothesis to create experiment design.
        """
        memory = self.memory_store.get(proposal_id)
        if not memory:
            return None
        
        # Construct hypothesis from memory
        hypothesis_dict = {
            'name': f"Proposal {proposal_id}",
            'target_component': memory.domain_research.replace("Focus area: ", "") if memory.domain_research else "unknown",
            'proposed_change': memory.final_proposal or memory.current_draft or "",
            'expected_improvement': "Performance improvement",
            'rationale': "Based on research and peer review",
            'testable_prediction': "Should pass sandbox tests",
        }
        
        design = self._run_async(
            self.agent0_robin.design_experiment(hypothesis_dict)
        )
        
        return design
    
    def broadcast_improvement_task(
        self,
        target_component: str,
        goal: str,
        agent_ids: Optional[list] = None
    ) -> list:
        """
        Broadcast improvement task to agents using Agent0 self-play.
        
        Returns list of task IDs.
        """
        return self.agent0_robin.broadcast_hypothesis_task(target_component, goal, agent_ids)
    
    def get_available_tools(self) -> list:
        """Get list of available Agent0 tools."""
        return self.agent0_robin.get_available_tools()
    
    def get_agent0_robin_status(self) -> Dict[str, Any]:
        """Get Agent0/Robin integration status for UI."""
        agent0 = _get_agent0_self_play()
        robin = _get_robin_hypothesis()
        tool_mgr = _get_tool_server_manager()
        
        return {
            "agent0_available": bool(agent0),
            "robin_available": bool(robin),
            "tool_server_available": tool_mgr is not None,
            "available_tools": self.get_available_tools(),
        }


# ============================================================================
# Factory Function
# ============================================================================

def create_extended_orchestrator(
    data_dir: str = "./data/workflow",
    orka_llm_client: Optional[Callable] = None,
    sandbox_runner: Optional[Callable] = None,
) -> ExtendedWorkflowOrchestrator:
    """
    Factory function to create an ExtendedWorkflowOrchestrator.
    
    Args:
        data_dir: Directory for persistent storage
        orka_llm_client: Optional callback for ORKA LLM invocation
        sandbox_runner: Optional callback for sandbox execution
    
    Returns:
        Configured ExtendedWorkflowOrchestrator instance
    """
    return ExtendedWorkflowOrchestrator(
        data_dir=data_dir,
        orka_llm_client=orka_llm_client,
        sandbox_runner=sandbox_runner,
    )
