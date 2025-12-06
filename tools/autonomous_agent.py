"""
Autonomous Nano Agent
=====================

Each nano is an autonomous agent that:
1. Monitors its area of expertise
2. Generates improvement ideas independently  
3. Researches using available integrations (RAG, hypothesis tools)
4. Builds proposals with evidence
5. Submits through the pipeline for peer review

This creates a council of autonomous researchers, each contributing
their specialized perspective to system improvement.

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                    IMPROVEMENT PIPELINE                  │
    │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌──────┐ │
    │  │ Submit  │ -> │  Peer   │ -> │ Sandbox │ -> │ Vote │ │
    │  │Proposal │    │ Review  │    │  Test   │    │      │ │
    │  └────▲────┘    └─────────┘    └─────────┘    └──────┘ │
    └───────┼─────────────────────────────────────────────────┘
            │
    ┌───────┴───────┐
    │ Each nano     │
    │ submits its   │
    │ own proposals │
    └───────────────┘
            ▲
    ┌───────┴───────────────────────────────────────────────┐
    │                                                        │
┌───┴───┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│  GIN  │ │  TIF  │ │ TORI  │ │ ORIN  │ │PAGEQA │ │ ARCHI │ │ GUARD │
│ code  │ │analyze│ │review │ │research│ │ docs  │ │design │ │safety │
│ gen   │ │ bugs  │ │ optim │ │ coord │ │  Q&A  │ │ arch  │ │ check │
└───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘
    │         │         │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼         ▼         ▼
 Research  Research  Research  Research  Research  Research  Research
 & Build   & Build   & Build   & Build   & Build   & Build   & Build
"""

import asyncio
import logging
import time
import uuid
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """State of an autonomous agent."""
    IDLE = "idle"
    MONITORING = "monitoring"
    RESEARCHING = "researching"
    BUILDING_PROPOSAL = "building_proposal"
    AWAITING_REVIEW = "awaiting_review"
    LEARNING = "learning"
    PAUSED = "paused"


@dataclass
class AgentFocus:
    """What the agent is currently focused on."""
    area: str  # e.g., "deception_detection", "performance", "safety"
    priority: float = 0.5
    context: str = ""
    discovered_at: float = field(default_factory=time.time)


@dataclass  
class ResearchNote:
    """A note from the agent's research."""
    id: str
    topic: str
    content: str
    sources: List[str]
    confidence: float
    created_at: float = field(default_factory=time.time)


@dataclass
class ProposalDraft:
    """A draft proposal being developed by the agent."""
    id: str
    title: str
    description: str
    improvement_type: str
    evidence: List[Dict[str, Any]]
    research_notes: List[str]  # ResearchNote IDs
    confidence: float
    risks: List[str]
    benefits: List[str]
    created_at: float = field(default_factory=time.time)
    submitted: bool = False


class AutonomousNanoAgent:
    """
    An autonomous agent running on a Jetson Nano.
    
    Each agent:
    - Has a specialized focus area
    - Monitors for improvement opportunities
    - Researches independently
    - Builds evidence-based proposals
    - Submits through the pipeline
    - Learns from outcomes
    """
    
    def __init__(
        self,
        name: str,
        ip: str,
        model: str,
        specialty: str,
        focus_areas: List[str],
        ollama_port: int = 11434,
    ):
        self.name = name
        self.ip = ip
        self.model = model
        self.specialty = specialty
        self.focus_areas = focus_areas
        self.ollama_port = ollama_port
        self.ollama_url = f"http://{ip}:{ollama_port}"
        
        # State
        self.state = AgentState.IDLE
        self.current_focus: Optional[AgentFocus] = None
        
        # Research & proposals
        self.research_notes: Dict[str, ResearchNote] = {}
        self.proposal_drafts: Dict[str, ProposalDraft] = {}
        self.submitted_proposals: List[str] = []
        self.approved_proposals: List[str] = []
        self.rejected_proposals: List[str] = []
        
        # Learning
        self.success_patterns: List[Dict[str, Any]] = []
        self.failure_patterns: List[Dict[str, Any]] = []
        
        # Integrations (lazy loaded)
        self._integrations: Optional[List[str]] = None
        self._rag = None
        self._hypothesis_gen = None
        
        # Control
        self._running = False
        self._loop_thread: Optional[threading.Thread] = None
        self._cycle_interval = 60.0  # seconds between cycles
        
        # Callbacks
        self.on_proposal_ready: Optional[Callable[[ProposalDraft], None]] = None
        self.on_state_change: Optional[Callable[[AgentState], None]] = None
    
    @property
    def integrations(self) -> List[str]:
        """Get available integrations for this agent."""
        if self._integrations is None:
            try:
                from tools.integrations import get_integrations_for_nano
                self._integrations = get_integrations_for_nano(self.name)
            except ImportError:
                self._integrations = []
        return self._integrations
    
    def _set_state(self, state: AgentState) -> None:
        """Update agent state."""
        old_state = self.state
        self.state = state
        if self.on_state_change and old_state != state:
            self.on_state_change(state)
        logger.debug(f"{self.name}: {old_state.value} -> {state.value}")
    
    def _generate_with_ollama(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Optional[str]:
        """Generate response using local Ollama."""
        import requests
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                },
                timeout=120.0
            )
            if response.ok:
                return response.json().get("response", "")
        except Exception as e:
            logger.error(f"{self.name}: Ollama error: {e}")
        return None
    
    # ========================================================================
    # PHASE 1: MONITORING - Identify improvement opportunities
    # ========================================================================
    
    def monitor_for_opportunities(self) -> List[AgentFocus]:
        """
        Monitor the agent's focus areas for improvement opportunities.
        
        Each agent looks at things relevant to their specialty:
        - GIN: Code patterns, refactoring opportunities
        - TIF: Bugs, performance issues, technical debt
        - TORI: Review patterns, optimization opportunities
        - etc.
        """
        self._set_state(AgentState.MONITORING)
        opportunities = []
        
        # Generate monitoring prompt based on specialty
        prompt = f"""You are {self.name}, an AI agent specialized in {self.specialty}.

Your focus areas are: {', '.join(self.focus_areas)}

Analyze potential improvements you could propose. For each opportunity:
1. Identify a specific area that could be improved
2. Explain why it's important
3. Rate priority (0-1)

Output as JSON list:
[{{"area": "...", "priority": 0.8, "context": "why this matters..."}}]

Focus on concrete, actionable improvements in your specialty."""

        response = self._generate_with_ollama(prompt, temperature=0.8)
        
        if response:
            try:
                import json
                # Try to extract JSON from response
                start = response.find('[')
                end = response.rfind(']') + 1
                if start >= 0 and end > start:
                    items = json.loads(response[start:end])
                    for item in items[:3]:  # Max 3 opportunities
                        opportunities.append(AgentFocus(
                            area=item.get('area', 'general'),
                            priority=float(item.get('priority', 0.5)),
                            context=item.get('context', '')
                        ))
            except Exception as e:
                logger.warning(f"{self.name}: Failed to parse opportunities: {e}")
        
        return opportunities
    
    # ========================================================================
    # PHASE 2: RESEARCH - Gather evidence and context
    # ========================================================================
    
    def research_topic(self, focus: AgentFocus) -> List[ResearchNote]:
        """
        Research a topic using available integrations.
        
        Uses:
        - RAG for document search
        - Hypothesis generation for structured proposals
        - Self-play for competitive refinement
        """
        self._set_state(AgentState.RESEARCHING)
        self.current_focus = focus
        notes = []
        
        # Research using RAG if available
        if 'paperqa_rag' in self.integrations:
            try:
                from tools.integrations import research_query
                result = research_query(
                    f"Best practices and approaches for {focus.area} in AI systems",
                    nano=self.name
                )
                if result and not result.get('error'):
                    note = ResearchNote(
                        id=str(uuid.uuid4())[:8],
                        topic=focus.area,
                        content=result.get('answer', ''),
                        sources=[s.get('name', '') for s in result.get('sources', [])],
                        confidence=result.get('confidence', 0.5)
                    )
                    notes.append(note)
                    self.research_notes[note.id] = note
            except Exception as e:
                logger.warning(f"{self.name}: RAG research failed: {e}")
        
        # Generate hypotheses if available
        if 'robin_hypothesis' in self.integrations or 'tool_hypothesis' in self.integrations:
            try:
                from tools.integrations import get_integration_manager
                manager = get_integration_manager()
                hypotheses = manager.generate_hypotheses(
                    target_component=focus.area,
                    context=focus.context,
                    num_hypotheses=2
                )
                for h in hypotheses:
                    note = ResearchNote(
                        id=str(uuid.uuid4())[:8],
                        topic=focus.area,
                        content=str(h),
                        sources=['hypothesis_generation'],
                        confidence=h.get('confidence', 0.5) if isinstance(h, dict) else 0.5
                    )
                    notes.append(note)
                    self.research_notes[note.id] = note
            except Exception as e:
                logger.warning(f"{self.name}: Hypothesis generation failed: {e}")
        
        # Use LLM to synthesize additional research
        prompt = f"""You are {self.name}, researching: {focus.area}

Context: {focus.context}

Previous research notes:
{chr(10).join([n.content[:200] for n in notes[:3]])}

Provide additional insights, potential approaches, and key considerations.
Be specific and technical. Focus on actionable improvements."""

        response = self._generate_with_ollama(prompt, temperature=0.6)
        
        if response:
            note = ResearchNote(
                id=str(uuid.uuid4())[:8],
                topic=focus.area,
                content=response,
                sources=['llm_synthesis'],
                confidence=0.6
            )
            notes.append(note)
            self.research_notes[note.id] = note
        
        return notes
    
    # ========================================================================
    # PHASE 3: BUILD PROPOSAL - Create evidence-based proposal
    # ========================================================================
    
    def build_proposal(
        self,
        focus: AgentFocus,
        research_notes: List[ResearchNote]
    ) -> Optional[ProposalDraft]:
        """
        Build a proposal based on research.
        
        Creates a structured proposal with:
        - Clear title and description
        - Evidence from research
        - Risk assessment
        - Expected benefits
        """
        self._set_state(AgentState.BUILDING_PROPOSAL)
        
        # Compile research into context
        research_context = "\n\n".join([
            f"[{n.topic}] (confidence: {n.confidence:.2f})\n{n.content}"
            for n in research_notes
        ])
        
        prompt = f"""You are {self.name}, creating an improvement proposal.

Focus Area: {focus.area}
Priority: {focus.priority}
Context: {focus.context}

Research Notes:
{research_context[:3000]}

Create a detailed improvement proposal with:
1. title: Clear, concise title
2. description: What to change and why
3. improvement_type: One of (safety, performance, security, reliability, usability)
4. risks: List of potential risks
5. benefits: List of expected benefits
6. confidence: Your confidence 0-1

Output as JSON:
{{"title": "...", "description": "...", "improvement_type": "...", 
  "risks": ["..."], "benefits": ["..."], "confidence": 0.8}}"""

        response = self._generate_with_ollama(prompt, temperature=0.5)
        
        if response:
            try:
                import json
                start = response.find('{')
                end = response.rfind('}') + 1
                if start >= 0 and end > start:
                    data = json.loads(response[start:end])
                    
                    draft = ProposalDraft(
                        id=str(uuid.uuid4())[:8],
                        title=data.get('title', f'Improve {focus.area}'),
                        description=data.get('description', ''),
                        improvement_type=data.get('improvement_type', 'improvement'),
                        evidence=[asdict(n) for n in research_notes],
                        research_notes=[n.id for n in research_notes],
                        confidence=float(data.get('confidence', 0.5)),
                        risks=data.get('risks', []),
                        benefits=data.get('benefits', [])
                    )
                    
                    self.proposal_drafts[draft.id] = draft
                    return draft
                    
            except Exception as e:
                logger.warning(f"{self.name}: Failed to build proposal: {e}")
        
        return None
    
    # ========================================================================
    # PHASE 4: SUBMIT - Send through pipeline
    # ========================================================================
    
    def submit_proposal(self, draft: ProposalDraft) -> Dict[str, Any]:
        """
        Submit a proposal to the pipeline.
        
        Returns the proposal in the format expected by the orchestrator.
        """
        proposal = {
            'proposal_id': f"{self.name}_{draft.id}_{int(time.time())}",
            'proposer_id': self.name,
            'title': draft.title,
            'description': draft.description,
            'improvement_type': draft.improvement_type,
            'confidence': draft.confidence,
            'evidence': draft.evidence,
            'risks': draft.risks,
            'benefits': draft.benefits,
            'research_notes': draft.research_notes,
            'submitted_at': time.time(),
            'agent_model': self.model,
            'agent_specialty': self.specialty,
        }
        
        draft.submitted = True
        self.submitted_proposals.append(draft.id)
        self._set_state(AgentState.AWAITING_REVIEW)
        
        # Notify callback if set
        if self.on_proposal_ready:
            self.on_proposal_ready(draft)
        
        logger.info(f"{self.name}: Submitted proposal '{draft.title}'")
        return proposal
    
    # ========================================================================
    # PHASE 5: LEARN - Update from outcomes
    # ========================================================================
    
    def learn_from_outcome(
        self,
        proposal_id: str,
        approved: bool,
        feedback: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Learn from proposal outcome.
        
        Updates internal patterns to improve future proposals.
        """
        self._set_state(AgentState.LEARNING)
        
        draft_id = proposal_id.split('_')[1] if '_' in proposal_id else proposal_id
        draft = self.proposal_drafts.get(draft_id)
        
        if not draft:
            return
        
        pattern = {
            'area': draft.improvement_type,
            'title_pattern': draft.title[:50],
            'confidence': draft.confidence,
            'evidence_count': len(draft.evidence),
            'feedback': feedback or {},
            'timestamp': time.time()
        }
        
        if approved:
            self.approved_proposals.append(draft_id)
            self.success_patterns.append(pattern)
            logger.info(f"{self.name}: Proposal approved, learning success pattern")
        else:
            self.rejected_proposals.append(draft_id)
            self.failure_patterns.append(pattern)
            logger.info(f"{self.name}: Proposal rejected, learning failure pattern")
        
        self._set_state(AgentState.IDLE)
    
    # ========================================================================
    # AUTONOMOUS LOOP
    # ========================================================================
    
    def run_improvement_cycle(self) -> Optional[Dict[str, Any]]:
        """
        Run one full improvement cycle:
        1. Monitor for opportunities
        2. Research the best opportunity
        3. Build a proposal
        4. Return proposal for submission
        """
        # Phase 1: Monitor
        opportunities = self.monitor_for_opportunities()
        
        if not opportunities:
            logger.debug(f"{self.name}: No opportunities found this cycle")
            self._set_state(AgentState.IDLE)
            return None
        
        # Select highest priority opportunity
        best = max(opportunities, key=lambda x: x.priority)
        
        # Phase 2: Research
        notes = self.research_topic(best)
        
        if not notes:
            logger.debug(f"{self.name}: No research findings for {best.area}")
            self._set_state(AgentState.IDLE)
            return None
        
        # Phase 3: Build proposal
        draft = self.build_proposal(best, notes)
        
        if not draft:
            logger.debug(f"{self.name}: Failed to build proposal")
            self._set_state(AgentState.IDLE)
            return None
        
        # Phase 4: Submit
        proposal = self.submit_proposal(draft)
        
        return proposal
    
    def start_autonomous_loop(self, interval: float = 60.0) -> None:
        """Start the autonomous improvement loop."""
        if self._running:
            return
        
        self._running = True
        self._cycle_interval = interval
        
        def loop():
            while self._running:
                try:
                    proposal = self.run_improvement_cycle()
                    if proposal:
                        logger.info(f"{self.name}: Generated proposal: {proposal['title']}")
                except Exception as e:
                    logger.error(f"{self.name}: Cycle error: {e}")
                
                # Wait for next cycle
                time.sleep(self._cycle_interval)
        
        self._loop_thread = threading.Thread(target=loop, daemon=True)
        self._loop_thread.start()
        logger.info(f"{self.name}: Started autonomous loop (interval={interval}s)")
    
    def stop_autonomous_loop(self) -> None:
        """Stop the autonomous improvement loop."""
        self._running = False
        if self._loop_thread:
            self._loop_thread.join(timeout=5.0)
        logger.info(f"{self.name}: Stopped autonomous loop")
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            'name': self.name,
            'ip': self.ip,
            'model': self.model,
            'specialty': self.specialty,
            'state': self.state.value,
            'current_focus': asdict(self.current_focus) if self.current_focus else None,
            'research_notes_count': len(self.research_notes),
            'drafts_count': len(self.proposal_drafts),
            'submitted_count': len(self.submitted_proposals),
            'approved_count': len(self.approved_proposals),
            'rejected_count': len(self.rejected_proposals),
            'success_rate': (
                len(self.approved_proposals) / max(1, len(self.submitted_proposals))
            ),
            'integrations': self.integrations,
            'running': self._running,
        }


# ============================================================================
# AGENT REGISTRY - Manage all autonomous agents
# ============================================================================

class AutonomousAgentRegistry:
    """
    Registry of all autonomous nano agents.
    
    Manages the council of researchers, each working independently
    to improve the system.
    """
    
    def __init__(self):
        self.agents: Dict[str, AutonomousNanoAgent] = {}
        self._initialized = False
    
    def initialize_from_cluster(self) -> None:
        """Initialize agents from cluster configuration."""
        if self._initialized:
            return
        
        # Agent configurations
        agent_configs = {
            'GIN': {
                'ip': '192.168.0.242',
                'model': 'deepseek-r1:1.5b',
                'specialty': 'Code Generation & Improvement',
                'focus_areas': ['code_quality', 'refactoring', 'new_features', 'bug_fixes']
            },
            'TIF': {
                'ip': '192.168.0.213',
                'model': 'deepseek-r1:1.5b',
                'specialty': 'Technical Analysis & Debugging',
                'focus_areas': ['performance', 'bugs', 'technical_debt', 'testing']
            },
            'TORI': {
                'ip': '192.168.0.235',
                'model': 'gemma3:4b',
                'specialty': 'Review & Optimization',
                'focus_areas': ['code_review', 'optimization', 'best_practices', 'patterns']
            },
            'ORIN': {
                'ip': '192.168.0.160',
                'model': 'deepseek-r1:1.5b',
                'specialty': 'Research Coordination',
                'focus_areas': ['research_synthesis', 'literature', 'coordination', 'planning']
            },
            'PAGEQA': {
                'ip': '192.168.0.168',
                'model': 'qwen2.5:3b',
                'specialty': 'Document Analysis & Q&A',
                'focus_areas': ['documentation', 'api_design', 'user_experience', 'clarity']
            },
            'ARCHI': {
                'ip': '192.168.0.232',
                'model': 'qwen2.5:3b',
                'specialty': 'Architecture & Design',
                'focus_areas': ['architecture', 'system_design', 'scalability', 'modularity']
            },
            'GUARD': {
                'ip': '192.168.0.146',
                'model': 'llama-guard3:1b',
                'specialty': 'Safety & Security',
                'focus_areas': ['safety', 'security', 'alignment', 'risk_assessment']
            },
        }
        
        for name, config in agent_configs.items():
            agent = AutonomousNanoAgent(
                name=name,
                ip=config['ip'],
                model=config['model'],
                specialty=config['specialty'],
                focus_areas=config['focus_areas']
            )
            self.agents[name] = agent
        
        self._initialized = True
        logger.info(f"Initialized {len(self.agents)} autonomous agents")
    
    def get_agent(self, name: str) -> Optional[AutonomousNanoAgent]:
        """Get an agent by name."""
        return self.agents.get(name.upper())
    
    def start_all(self, interval: float = 300.0) -> None:
        """Start all agents' autonomous loops."""
        for agent in self.agents.values():
            agent.start_autonomous_loop(interval)
    
    def stop_all(self) -> None:
        """Stop all agents' autonomous loops."""
        for agent in self.agents.values():
            agent.stop_autonomous_loop()
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents."""
        return {name: agent.get_status() for name, agent in self.agents.items()}
    
    def get_all_proposals(self) -> List[Dict[str, Any]]:
        """Get all submitted proposals from all agents."""
        proposals = []
        for agent in self.agents.values():
            for draft_id in agent.submitted_proposals:
                draft = agent.proposal_drafts.get(draft_id)
                if draft:
                    proposals.append({
                        'agent': agent.name,
                        'draft': asdict(draft)
                    })
        return proposals


# Global registry
_registry: Optional[AutonomousAgentRegistry] = None


def get_agent_registry() -> AutonomousAgentRegistry:
    """Get the global agent registry."""
    global _registry
    if _registry is None:
        _registry = AutonomousAgentRegistry()
        _registry.initialize_from_cluster()
    return _registry


def get_agent(name: str) -> Optional[AutonomousNanoAgent]:
    """Get an autonomous agent by name."""
    return get_agent_registry().get_agent(name)


def start_all_agents(interval: float = 300.0) -> None:
    """Start all autonomous agents."""
    get_agent_registry().start_all(interval)


def stop_all_agents() -> None:
    """Stop all autonomous agents."""
    get_agent_registry().stop_all()
