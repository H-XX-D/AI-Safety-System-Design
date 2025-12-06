"""
Autonomous Agent System
========================

Each nano operates as an autonomous agent that:
1. Monitors its area of expertise
2. Generates improvement proposals independently
3. Requests research from PAGEQA
4. Submits proposals through the pipeline
5. Gets peer reviewed by other agents
6. ORKA makes final approval decisions

Agent Roles:
- GIN: Code generation & improvement proposals
- TIF: Technical analysis & debugging proposals
- TORI: Code review & optimization proposals
- ORIN: NVIDIA/CUDA/Jetson optimization proposals
- ARCHI: System architecture & design proposals
- GUARD: Safety & security improvement proposals
- PAGEQA: Research support (does NOT submit proposals)
- ORKA: Orchestration & final approval (does NOT submit proposals)

Workflow:
1. Agent identifies improvement opportunity in its domain
2. Agent requests research from PAGEQA
3. PAGEQA researches and returns findings
4. Agent creates proposal based on expertise + research
5. Proposal enters pipeline for peer review
6. Other agents review based on their expertise
7. ORKA makes final approval/rejection decision
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import json
import threading

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Role types for agents."""
    PROPOSER = "proposer"       # Creates and submits proposals
    RESEARCHER = "researcher"   # Supports with research (PAGEQA)
    ORCHESTRATOR = "orchestrator"  # Reviews and approves (ORKA)


@dataclass
class AgentProfile:
    """Profile defining an agent's capabilities and behavior."""
    name: str
    role: AgentRole
    expertise: str
    specialty_areas: List[str]
    model: str
    ip: str
    can_submit_proposals: bool
    proposal_domains: List[str]  # What domains can this agent propose in?
    review_domains: List[str]    # What domains can this agent review?
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'role': self.role.value,
            'expertise': self.expertise,
            'specialty_areas': self.specialty_areas,
            'model': self.model,
            'ip': self.ip,
            'can_submit_proposals': self.can_submit_proposals,
            'proposal_domains': self.proposal_domains,
            'review_domains': self.review_domains,
        }


# Define all agent profiles
AGENT_PROFILES: Dict[str, AgentProfile] = {
    "GIN": AgentProfile(
        name="GIN",
        role=AgentRole.PROPOSER,
        expertise="Code Generation & Improvement",
        specialty_areas=[
            "code_generation",
            "refactoring",
            "algorithm_optimization",
            "python_development",
            "api_design",
        ],
        model="deepseek-r1:1.5b",
        ip="192.168.0.242",
        can_submit_proposals=True,
        proposal_domains=["code", "algorithms", "implementation"],
        review_domains=["code", "implementation"],
    ),
    
    "TIF": AgentProfile(
        name="TIF",
        role=AgentRole.PROPOSER,
        expertise="Technical Analysis & Debugging",
        specialty_areas=[
            "debugging",
            "performance_analysis",
            "error_detection",
            "system_diagnostics",
            "technical_investigation",
        ],
        model="deepseek-r1:1.5b",
        ip="192.168.0.213",
        can_submit_proposals=True,
        proposal_domains=["debugging", "performance", "diagnostics"],
        review_domains=["technical", "performance"],
    ),
    
    "TORI": AgentProfile(
        name="TORI",
        role=AgentRole.PROPOSER,
        expertise="Code Review & Optimization",
        specialty_areas=[
            "code_review",
            "optimization",
            "best_practices",
            "code_quality",
            "maintainability",
        ],
        model="gemma3:4b",
        ip="192.168.0.235",
        can_submit_proposals=True,
        proposal_domains=["optimization", "quality", "best_practices"],
        review_domains=["code", "quality", "optimization"],
    ),
    
    "ORIN": AgentProfile(
        name="ORIN",
        role=AgentRole.PROPOSER,
        expertise="NVIDIA & Hardware Optimization",
        specialty_areas=[
            "nvidia_cuda",
            "jetson_optimization",
            "gpu_acceleration",
            "tensorrt",
            "embedded_ai",
            "hardware_integration",
        ],
        model="deepseek-r1:1.5b",
        ip="192.168.0.160",
        can_submit_proposals=True,
        proposal_domains=["nvidia", "cuda", "jetson", "gpu", "hardware"],
        review_domains=["hardware", "performance", "nvidia"],
    ),
    
    "ARCHI": AgentProfile(
        name="ARCHI",
        role=AgentRole.PROPOSER,
        expertise="System Architecture & Design",
        specialty_areas=[
            "system_architecture",
            "design_patterns",
            "scalability",
            "microservices",
            "api_architecture",
        ],
        model="qwen2.5:3b",
        ip="192.168.0.232",
        can_submit_proposals=True,
        proposal_domains=["architecture", "design", "scalability"],
        review_domains=["architecture", "design"],
    ),
    
    "GUARD": AgentProfile(
        name="GUARD",
        role=AgentRole.PROPOSER,
        expertise="Safety & Security",
        specialty_areas=[
            "ai_safety",
            "security_audit",
            "deception_detection",
            "alignment",
            "safety_mechanisms",
        ],
        model="llama-guard3:1b",
        ip="192.168.0.146",
        can_submit_proposals=True,
        proposal_domains=["safety", "security", "alignment"],
        review_domains=["safety", "security"],
    ),
    
    "PAGEQA": AgentProfile(
        name="PAGEQA",
        role=AgentRole.RESEARCHER,
        expertise="Research & Documentation",
        specialty_areas=[
            "literature_review",
            "documentation",
            "information_retrieval",
            "summarization",
            "citation",
        ],
        model="qwen2.5:3b",
        ip="192.168.0.168",
        can_submit_proposals=False,  # Does NOT submit proposals
        proposal_domains=[],  # Cannot propose
        review_domains=["documentation", "research"],
    ),
    
    "ORKA": AgentProfile(
        name="ORKA",
        role=AgentRole.ORCHESTRATOR,
        expertise="Orchestration & Final Decisions",
        specialty_areas=[
            "coordination",
            "decision_making",
            "consensus",
            "resource_allocation",
            "priority_management",
        ],
        model="qwen2.5:14b",
        ip="localhost",
        can_submit_proposals=False,  # Does NOT submit proposals
        proposal_domains=[],  # Cannot propose
        review_domains=["all"],  # Reviews everything
    ),
}


@dataclass
class Proposal:
    """A proposal created by an agent."""
    id: str
    title: str
    description: str
    proposer: str  # Agent name
    domain: str
    expertise_area: str
    changes: List[str]
    benefits: List[str]
    risks: List[str]
    research_references: List[Dict[str, Any]]
    status: str = "draft"  # draft, submitted, reviewing, approved, rejected
    created_at: float = field(default_factory=time.time)
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    orka_decision: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class ResearchRequest:
    """A request for research from PAGEQA."""
    id: str
    requester: str  # Agent requesting research
    topic: str
    context: str
    specific_questions: List[str]
    status: str = "pending"  # pending, in_progress, completed
    created_at: float = field(default_factory=time.time)
    response: Optional[Dict[str, Any]] = None


class AutonomousAgent:
    """
    An autonomous agent that operates on a nano.
    
    Each agent:
    - Monitors its domain for improvement opportunities
    - Requests research from PAGEQA when needed
    - Creates proposals based on expertise
    - Participates in peer review
    """
    
    def __init__(self, profile: AgentProfile):
        self.profile = profile
        self.name = profile.name
        self.pending_proposals: List[Proposal] = []
        self.submitted_proposals: List[Proposal] = []
        self.research_requests: List[ResearchRequest] = []
        self._running = False
        self._proposal_counter = 0
        self._research_counter = 0
    
    def _generate_proposal_id(self) -> str:
        self._proposal_counter += 1
        return f"{self.name}_PROP_{int(time.time())}_{self._proposal_counter}"
    
    def _generate_research_id(self) -> str:
        self._research_counter += 1
        return f"{self.name}_RES_{int(time.time())}_{self._research_counter}"
    
    def request_research(
        self,
        topic: str,
        context: str = "",
        questions: Optional[List[str]] = None
    ) -> ResearchRequest:
        """
        Request research from PAGEQA.
        
        This agent needs information to make a proposal.
        PAGEQA will research and return findings.
        """
        request = ResearchRequest(
            id=self._generate_research_id(),
            requester=self.name,
            topic=topic,
            context=context,
            specific_questions=questions or [],
        )
        self.research_requests.append(request)
        logger.info(f"{self.name} requested research on: {topic}")
        return request
    
    def create_proposal(
        self,
        title: str,
        description: str,
        domain: str,
        changes: List[str],
        benefits: List[str],
        risks: List[str],
        research: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Proposal]:
        """
        Create a new proposal in this agent's area of expertise.
        
        Returns None if agent cannot propose in this domain.
        """
        if not self.profile.can_submit_proposals:
            logger.warning(f"{self.name} cannot submit proposals (role: {self.profile.role})")
            return None
        
        if domain not in self.profile.proposal_domains and "all" not in self.profile.proposal_domains:
            logger.warning(f"{self.name} cannot propose in domain '{domain}'. Allowed: {self.profile.proposal_domains}")
            return None
        
        proposal = Proposal(
            id=self._generate_proposal_id(),
            title=title,
            description=description,
            proposer=self.name,
            domain=domain,
            expertise_area=self.profile.expertise,
            changes=changes,
            benefits=benefits,
            risks=risks,
            research_references=research or [],
        )
        
        self.pending_proposals.append(proposal)
        logger.info(f"{self.name} created proposal: {title}")
        return proposal
    
    def submit_proposal(self, proposal: Proposal) -> bool:
        """Submit a proposal to the pipeline for peer review."""
        if proposal not in self.pending_proposals:
            logger.warning(f"Proposal {proposal.id} not in pending list")
            return False
        
        proposal.status = "submitted"
        self.pending_proposals.remove(proposal)
        self.submitted_proposals.append(proposal)
        logger.info(f"{self.name} submitted proposal: {proposal.title}")
        return True
    
    def review_proposal(
        self,
        proposal: Proposal,
        vote: str,  # "approve", "reject", "needs_revision"
        comments: str,
        concerns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Review another agent's proposal.
        
        Returns review dict to be added to proposal.
        """
        # Check if we can review this domain
        can_review = (
            proposal.domain in self.profile.review_domains or 
            "all" in self.profile.review_domains
        )
        
        if not can_review:
            logger.warning(f"{self.name} cannot review domain '{proposal.domain}'")
            return {}
        
        review = {
            "reviewer": self.name,
            "expertise": self.profile.expertise,
            "vote": vote,
            "comments": comments,
            "concerns": concerns or [],
            "timestamp": time.time(),
        }
        
        logger.info(f"{self.name} reviewed {proposal.id}: {vote}")
        return review
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "name": self.name,
            "role": self.profile.role.value,
            "expertise": self.profile.expertise,
            "can_submit_proposals": self.profile.can_submit_proposals,
            "pending_proposals": len(self.pending_proposals),
            "submitted_proposals": len(self.submitted_proposals),
            "pending_research": len([r for r in self.research_requests if r.status == "pending"]),
        }


class PageQAResearcher(AutonomousAgent):
    """
    PAGEQA - The research specialist.
    
    Does NOT submit proposals, but provides research support
    to other agents who do.
    """
    
    def __init__(self):
        super().__init__(AGENT_PROFILES["PAGEQA"])
        self.research_queue: List[ResearchRequest] = []
        self.completed_research: List[ResearchRequest] = []
    
    def receive_research_request(self, request: ResearchRequest) -> None:
        """Receive a research request from another agent."""
        request.status = "in_progress"
        self.research_queue.append(request)
        logger.info(f"PAGEQA received research request from {request.requester}: {request.topic}")
    
    def complete_research(
        self,
        request: ResearchRequest,
        findings: str,
        sources: List[Dict[str, str]],
        recommendations: List[str]
    ) -> Dict[str, Any]:
        """Complete a research request with findings."""
        response = {
            "findings": findings,
            "sources": sources,
            "recommendations": recommendations,
            "completed_at": time.time(),
            "researcher": "PAGEQA",
        }
        
        request.response = response
        request.status = "completed"
        
        if request in self.research_queue:
            self.research_queue.remove(request)
        self.completed_research.append(request)
        
        logger.info(f"PAGEQA completed research for {request.requester}: {request.topic}")
        return response


class OrkaOrchestrator(AutonomousAgent):
    """
    ORKA - The orchestrator and final decision maker.
    
    Does NOT submit proposals, but:
    - Coordinates the review process
    - Makes final approval/rejection decisions
    - Manages the overall workflow
    """
    
    def __init__(self):
        super().__init__(AGENT_PROFILES["ORKA"])
        self.pending_decisions: List[Proposal] = []
        self.approved_proposals: List[Proposal] = []
        self.rejected_proposals: List[Proposal] = []
    
    def receive_for_decision(self, proposal: Proposal, reviews: List[Dict[str, Any]]) -> None:
        """Receive a proposal that has completed peer review."""
        proposal.reviews = reviews
        proposal.status = "awaiting_decision"
        self.pending_decisions.append(proposal)
        logger.info(f"ORKA received proposal for decision: {proposal.title}")
    
    def make_decision(
        self,
        proposal: Proposal,
        decision: str,  # "approve", "reject"
        reasoning: str,
        conditions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Make final decision on a proposal."""
        orka_decision = {
            "decision": decision,
            "reasoning": reasoning,
            "conditions": conditions or [],
            "decided_at": time.time(),
            "decided_by": "ORKA",
        }
        
        proposal.orka_decision = orka_decision
        proposal.status = "approved" if decision == "approve" else "rejected"
        
        if proposal in self.pending_decisions:
            self.pending_decisions.remove(proposal)
        
        if decision == "approve":
            self.approved_proposals.append(proposal)
            logger.info(f"ORKA APPROVED: {proposal.title}")
        else:
            self.rejected_proposals.append(proposal)
            logger.info(f"ORKA REJECTED: {proposal.title}")
        
        return orka_decision
    
    def get_review_summary(self, reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize peer reviews for decision making."""
        if not reviews:
            return {"approve": 0, "reject": 0, "needs_revision": 0, "consensus": None}
        
        votes = {"approve": 0, "reject": 0, "needs_revision": 0}
        for review in reviews:
            vote = review.get("vote", "")
            if vote in votes:
                votes[vote] += 1
        
        total = sum(votes.values())
        consensus = None
        if total > 0:
            if votes["approve"] / total >= 0.6:
                consensus = "approve"
            elif votes["reject"] / total >= 0.4:
                consensus = "reject"
            else:
                consensus = "needs_revision"
        
        return {
            **votes,
            "total_reviews": total,
            "consensus": consensus,
        }


class AgentCouncil:
    """
    The council of all autonomous agents.
    
    Manages:
    - All agent instances
    - Research request routing
    - Proposal pipeline
    - Peer review coordination
    - ORKA final decisions
    """
    
    def __init__(self):
        # Create all agents
        self.proposers: Dict[str, AutonomousAgent] = {}
        for name in ["GIN", "TIF", "TORI", "ORIN", "ARCHI", "GUARD"]:
            self.proposers[name] = AutonomousAgent(AGENT_PROFILES[name])
        
        self.researcher = PageQAResearcher()
        self.orchestrator = OrkaOrchestrator()
        
        # Pipeline state
        self.proposal_queue: List[Proposal] = []
        self.review_queue: List[Proposal] = []
        
    def get_agent(self, name: str) -> Optional[AutonomousAgent]:
        """Get agent by name."""
        name = name.upper()
        if name in self.proposers:
            return self.proposers[name]
        if name == "PAGEQA":
            return self.researcher
        if name == "ORKA":
            return self.orchestrator
        return None
    
    def submit_research_request(
        self,
        requester: str,
        topic: str,
        context: str = "",
        questions: Optional[List[str]] = None
    ) -> Optional[ResearchRequest]:
        """Route a research request to PAGEQA."""
        agent = self.get_agent(requester)
        if not agent:
            return None
        
        request = agent.request_research(topic, context, questions)
        self.researcher.receive_research_request(request)
        return request
    
    def submit_proposal(
        self,
        proposer: str,
        title: str,
        description: str,
        domain: str,
        changes: List[str],
        benefits: List[str],
        risks: List[str],
        research: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Proposal]:
        """Create and submit a proposal from an agent."""
        agent = self.get_agent(proposer)
        if not agent or not agent.profile.can_submit_proposals:
            logger.warning(f"{proposer} cannot submit proposals")
            return None
        
        proposal = agent.create_proposal(
            title=title,
            description=description,
            domain=domain,
            changes=changes,
            benefits=benefits,
            risks=risks,
            research=research,
        )
        
        if proposal:
            agent.submit_proposal(proposal)
            self.proposal_queue.append(proposal)
            proposal.status = "reviewing"
            self.review_queue.append(proposal)
        
        return proposal
    
    def get_reviewers_for_proposal(self, proposal: Proposal) -> List[str]:
        """Get list of agents who should review a proposal."""
        reviewers = []
        for name, agent in self.proposers.items():
            # Don't review your own proposal
            if name == proposal.proposer:
                continue
            # Check if agent can review this domain
            if proposal.domain in agent.profile.review_domains:
                reviewers.append(name)
        return reviewers
    
    def collect_reviews(self, proposal: Proposal) -> List[Dict[str, Any]]:
        """Collect reviews from all relevant reviewers."""
        reviewers = self.get_reviewers_for_proposal(proposal)
        reviews = []
        
        for reviewer_name in reviewers:
            agent = self.proposers.get(reviewer_name)
            if agent:
                # In real implementation, this would call the agent's LLM
                # For now, placeholder for the review process
                reviews.append({
                    "reviewer": reviewer_name,
                    "status": "pending",
                })
        
        return reviews
    
    def send_to_orka(self, proposal: Proposal) -> None:
        """Send a reviewed proposal to ORKA for final decision."""
        if proposal in self.review_queue:
            self.review_queue.remove(proposal)
        self.orchestrator.receive_for_decision(proposal, proposal.reviews)
    
    def get_council_status(self) -> Dict[str, Any]:
        """Get overall council status."""
        return {
            "proposers": {
                name: agent.get_status()
                for name, agent in self.proposers.items()
            },
            "researcher": self.researcher.get_status(),
            "orchestrator": self.orchestrator.get_status(),
            "pipeline": {
                "proposal_queue": len(self.proposal_queue),
                "review_queue": len(self.review_queue),
                "pending_decisions": len(self.orchestrator.pending_decisions),
                "approved": len(self.orchestrator.approved_proposals),
                "rejected": len(self.orchestrator.rejected_proposals),
            },
        }
    
    def get_agent_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all agent profiles."""
        return {name: profile.to_dict() for name, profile in AGENT_PROFILES.items()}


# Global council instance
_council: Optional[AgentCouncil] = None


def get_council() -> AgentCouncil:
    """Get the global agent council."""
    global _council
    if _council is None:
        _council = AgentCouncil()
    return _council


def get_agent_profile(name: str) -> Optional[Dict[str, Any]]:
    """Get profile for a specific agent."""
    name = name.upper()
    if name in AGENT_PROFILES:
        return AGENT_PROFILES[name].to_dict()
    return None


def get_proposer_agents() -> List[str]:
    """Get list of agents that can submit proposals."""
    return [name for name, profile in AGENT_PROFILES.items() if profile.can_submit_proposals]


def get_research_agent() -> str:
    """Get the research agent name (PAGEQA)."""
    return "PAGEQA"


def get_orchestrator_agent() -> str:
    """Get the orchestrator agent name (ORKA)."""
    return "ORKA"


# ============================================================
# COMPATIBILITY LAYER - Exports expected by __init__.py
# ============================================================

@dataclass
class NanoAgent:
    """
    Simplified agent representation for external API.
    
    This provides the interface expected by the UI and tools package.
    """
    name: str
    ip: str
    port: int
    model: str
    expertise: str
    role: str
    proposal_submitter: bool
    integrations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Build NANO_AGENTS from AGENT_PROFILES
NANO_AGENTS: Dict[str, NanoAgent] = {}
for _name, _profile in AGENT_PROFILES.items():
    _integrations = []
    if _name == "PAGEQA":
        _integrations = ["paperqa_rag", "robin_hypothesis"]
    elif _name == "GUARD":
        _integrations = ["safety_quality_tools", "agent0_self_play"]
    elif _name == "GIN":
        _integrations = ["tool_servers", "tool_hypothesis"]
    elif _name == "ARCHI":
        _integrations = ["ai_memory_system", "tool_servers"]
    elif _name == "ORIN":
        _integrations = ["rl_trainer", "tool_hypothesis"]
    
    NANO_AGENTS[_name] = NanoAgent(
        name=_name,
        ip=_profile.ip,
        port=11434,  # Default Ollama port
        model=_profile.model,
        expertise=_profile.expertise,
        role=_profile.role.value,
        proposal_submitter=_profile.can_submit_proposals,
        integrations=_integrations,
    )


class AutonomousAgentManager:
    """
    Manager for controlling autonomous agents.
    
    This is the simplified interface used by the UI.
    """
    
    def __init__(self):
        self.council = get_council()
        self._running_agents: Dict[str, bool] = {name: False for name in AGENT_PROFILES}
        self._threads: Dict[str, Optional[threading.Thread]] = {name: None for name in AGENT_PROFILES}
    
    def start_agent(self, name: str) -> bool:
        """Start an agent's autonomous operation."""
        name = name.upper()
        if name not in AGENT_PROFILES:
            logger.warning(f"Unknown agent: {name}")
            return False
        
        if self._running_agents.get(name, False):
            logger.info(f"Agent {name} already running")
            return True
        
        self._running_agents[name] = True
        logger.info(f"Started agent: {name}")
        return True
    
    def stop_agent(self, name: str) -> bool:
        """Stop an agent's autonomous operation."""
        name = name.upper()
        if name not in AGENT_PROFILES:
            return False
        
        self._running_agents[name] = False
        logger.info(f"Stopped agent: {name}")
        return True
    
    def start_all(self) -> Dict[str, bool]:
        """Start all agents."""
        results = {}
        for name in AGENT_PROFILES:
            results[name] = self.start_agent(name)
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """Stop all agents."""
        results = {}
        for name in AGENT_PROFILES:
            results[name] = self.stop_agent(name)
        return results
    
    def get_agent_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent."""
        name = name.upper()
        agent = self.council.get_agent(name)
        if not agent:
            return None
        
        status = agent.get_status()
        status['running'] = self._running_agents.get(name, False)
        return status
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents."""
        statuses = {}
        for name in AGENT_PROFILES:
            status = self.get_agent_status(name)
            if status:
                statuses[name] = status
        return statuses
    
    def generate_proposal(
        self,
        agent_name: str,
        topic: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a proposal using the actual nano LLM.
        
        Workflow:
        1. Query PAGEQA for research on the topic
        2. Send research + topic to the agent's nano LLM
        3. Parse the proposal from the response
        4. Return structured proposal
        """
        agent_name = agent_name.upper()
        profile = AGENT_PROFILES.get(agent_name)
        
        if not profile or not profile.can_submit_proposals:
            return None
        
        # Import nano cluster for LLM access
        try:
            from tools.nano_cluster import get_cluster
            from tools.integrations import get_integration_manager
        except ImportError:
            logger.warning("Cannot import nano cluster or integrations")
            return self._generate_proposal_fallback(agent_name, profile, topic)
        
        cluster = get_cluster()
        if not cluster:
            return self._generate_proposal_fallback(agent_name, profile, topic)
        
        # Get the nano node for this agent
        nano = cluster.get_node(agent_name)
        if not nano:
            logger.warning(f"No nano node found for {agent_name}")
            return self._generate_proposal_fallback(agent_name, profile, topic)
        
        domain = profile.proposal_domains[0] if profile.proposal_domains else "general"
        title = topic if topic else f"{agent_name} Improvement Proposal"
        
        # Step 1: Get research from PAGEQA via RAG
        research_context = ""
        integration_mgr = get_integration_manager()
        if integration_mgr:
            research_query = f"{profile.expertise}: {title}"
            rag_result = integration_mgr.query_rag(research_query)
            if rag_result and not rag_result.get('error'):
                research_context = f"\n\nResearch from PAGEQA:\n{rag_result.get('answer', '')}"
                sources = rag_result.get('sources', [])
                if sources:
                    research_context += f"\nSources: {', '.join(s.get('name', 'unknown') for s in sources[:3])}"
        
        # Step 2: Generate proposal using the nano's LLM
        system_prompt = f"""You are {agent_name}, an AI agent specialized in {profile.expertise}.
Your specialty areas: {', '.join(profile.specialty_areas)}
You can propose improvements in these domains: {', '.join(profile.proposal_domains)}

Generate a structured improvement proposal. Be specific and actionable.
Focus on your area of expertise. Include concrete implementation steps."""

        user_prompt = f"""Generate an improvement proposal for: {title}
Domain: {domain}
{research_context}

Provide your proposal in this format:
TITLE: [specific title]
DESCRIPTION: [2-3 sentence description]
CHANGES:
- [change 1]
- [change 2]
- [change 3]
BENEFITS:
- [benefit 1]
- [benefit 2]
RISKS:
- [risk 1]
- [risk 2]
IMPLEMENTATION: [brief implementation plan]"""

        try:
            # Call the nano's Ollama instance
            response = nano.generate(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7,
                max_tokens=1024,
                timeout=120.0
            )
            
            if response:
                # Parse the response into structured proposal
                proposal = self._parse_proposal_response(
                    response=response,
                    agent_name=agent_name,
                    domain=domain,
                    profile=profile
                )
                proposal['research_context'] = research_context
                proposal['generated_by_llm'] = True
                proposal['nano_ip'] = nano.ip
                proposal['model'] = nano.model
                return proposal
        except Exception as e:
            logger.error(f"LLM generation failed for {agent_name}: {e}")
        
        return self._generate_proposal_fallback(agent_name, profile, topic)
    
    def _generate_proposal_fallback(
        self,
        agent_name: str,
        profile: AgentProfile,
        topic: Optional[str]
    ) -> Dict[str, Any]:
        """Fallback when LLM is not available."""
        domain = profile.proposal_domains[0] if profile.proposal_domains else "general"
        title = topic if topic else f"{agent_name} Improvement Proposal"
        
        return {
            "agent": agent_name,
            "title": title,
            "domain": domain,
            "expertise": profile.expertise,
            "status": "generated",
            "generated_at": time.time(),
            "generated_by_llm": False,
            "fallback": True,
        }
    
    def _parse_proposal_response(
        self,
        response: str,
        agent_name: str,
        domain: str,
        profile: AgentProfile
    ) -> Dict[str, Any]:
        """Parse LLM response into structured proposal."""
        lines = response.strip().split('\n')
        
        proposal = {
            "agent": agent_name,
            "domain": domain,
            "expertise": profile.expertise,
            "status": "generated",
            "generated_at": time.time(),
            "title": "",
            "description": "",
            "changes": [],
            "benefits": [],
            "risks": [],
            "implementation": "",
            "raw_response": response,
        }
        
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.upper().startswith('TITLE:'):
                proposal['title'] = line[6:].strip()
            elif line.upper().startswith('DESCRIPTION:'):
                proposal['description'] = line[12:].strip()
                current_section = 'description'
            elif line.upper().startswith('CHANGES:'):
                current_section = 'changes'
            elif line.upper().startswith('BENEFITS:'):
                current_section = 'benefits'
            elif line.upper().startswith('RISKS:'):
                current_section = 'risks'
            elif line.upper().startswith('IMPLEMENTATION:'):
                proposal['implementation'] = line[15:].strip()
                current_section = 'implementation'
            elif line.startswith('- ') or line.startswith('* '):
                item = line[2:].strip()
                if current_section == 'changes':
                    proposal['changes'].append(item)
                elif current_section == 'benefits':
                    proposal['benefits'].append(item)
                elif current_section == 'risks':
                    proposal['risks'].append(item)
            elif current_section == 'description' and not proposal['description']:
                proposal['description'] = line
            elif current_section == 'implementation':
                proposal['implementation'] += ' ' + line
        
        # Use first line as title if not found
        if not proposal['title'] and lines:
            proposal['title'] = lines[0][:100]
        
        return proposal
    
    def run_full_20_step_workflow(self, agent_name: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete 20-step proposal workflow.
        
        This is the full research-to-reward workflow from WORKFLOW_GROUND_TRUTH.md:
        - PHASE 1: Research (Steps 1-5) - idea, papers, triage, deep notes, synthesis
        - PHASE 2: Hypothesis (Steps 6-7) - hypothesis, experiment design
        - PHASE 3: Early Review (Steps 8-12) - proposal, self-checks, peer review, revision
        - PHASE 4: Validation (Steps 13-14) - PaperQA validation
        - PHASE 5: Late Review (Steps 15-17) - collusion check, vote, ORKA challenge
        - PHASE 6: Completion (Steps 18-20) - final proposal, sandbox, reward
        
        Each step creates a file in the proposal workspace for full auditability.
        """
        agent_name = agent_name.upper()
        profile = AGENT_PROFILES.get(agent_name)
        
        if not profile or not profile.can_submit_proposals:
            return {"status": "error", "message": f"Agent {agent_name} cannot submit proposals"}
        
        if not topic:
            topic = f"Improve {profile.specialty_areas[0] if profile.specialty_areas else 'capabilities'}"
        
        try:
            from tools.proposal_workflow import run_20_step_workflow
            return run_20_step_workflow(agent_name, topic)
        except ImportError as e:
            logger.error(f"Failed to import workflow engine: {e}")
            return {"status": "error", "message": str(e)}
    
    def run_cycle(self, agent_name: str, full_workflow: bool = False) -> Optional[Dict[str, Any]]:
        """
        Run a proposal cycle for an agent.
        
        Args:
            agent_name: Name of the agent (e.g., "GIN")
            full_workflow: If True, runs the full 20-step workflow. 
                          If False, runs the quick 6-step cycle (default).
        
        Quick Workflow (6 steps):
        1. Generate proposal using agent's nano LLM + PAGEQA research
        2. Get ORKA counterpoint analysis
        3. Collect peer reviews from other agents
        4. Run sandbox testing (if code-related)
        5. Calculate RL reward based on results
        6. Submit for final decision
        
        Full Workflow (20 steps):
        See run_full_20_step_workflow() for details.
        """
        agent_name = agent_name.upper()
        
        # Use full workflow if requested
        if full_workflow:
            return self.run_full_20_step_workflow(agent_name)
        
        # Step 1: Generate proposal
        proposal = self.generate_proposal(agent_name)
        if not proposal:
            return None
        
        result = {
            "agent": agent_name,
            "proposal": proposal,
            "cycle_started": time.time(),
            "stages": {},
        }
        
        try:
            from tools.nano_cluster import get_cluster
            from tools.integrations import get_integration_manager
            cluster = get_cluster()
        except ImportError:
            cluster = None
        
        # Step 2: Get ORKA counterpoint analysis
        if cluster:
            orka = cluster.get_node("ORKA")
            if orka and orka.is_online:
                counterpoint_prompt = f"""Analyze this proposal and provide counterpoints:

PROPOSAL: {proposal.get('title', 'Unknown')}
FROM: {agent_name}
DOMAIN: {proposal.get('domain', 'general')}
DESCRIPTION: {proposal.get('description', '')}
CHANGES: {', '.join(proposal.get('changes', []))}
BENEFITS: {', '.join(proposal.get('benefits', []))}
RISKS: {', '.join(proposal.get('risks', []))}

Provide:
1. CONCERNS: What could go wrong?
2. ALTERNATIVES: Other approaches to consider
3. EVIDENCE NEEDED: What proof would validate this?
4. RECOMMENDATION: proceed/revise/reject"""

                try:
                    counterpoint = orka.generate(
                        prompt=counterpoint_prompt,
                        system="You are ORKA, the orchestrator. Provide critical analysis of proposals. Be constructive but thorough.",
                        temperature=0.3,
                        max_tokens=512,
                        timeout=90.0
                    )
                    result['stages']['orka_counterpoint'] = {
                        'completed': True,
                        'response': counterpoint,
                        'timestamp': time.time()
                    }
                except Exception as e:
                    logger.warning(f"ORKA counterpoint failed: {e}")
                    result['stages']['orka_counterpoint'] = {'completed': False, 'error': str(e)}
        
        # Step 3: Collect peer reviews from other proposer agents
        peer_reviews = []
        if cluster:
            profile = AGENT_PROFILES.get(agent_name)
            proposal_domain = proposal.get('domain', 'general')
            
            for reviewer_name in ["GIN", "TIF", "TORI", "ORIN", "ARCHI", "GUARD"]:
                if reviewer_name == agent_name:
                    continue  # Don't review your own proposal
                
                reviewer_profile = AGENT_PROFILES.get(reviewer_name)
                if not reviewer_profile:
                    continue
                
                # Check if reviewer can review this domain
                can_review = proposal_domain in reviewer_profile.review_domains or "all" in reviewer_profile.review_domains
                if not can_review:
                    continue
                
                reviewer_node = cluster.get_node(reviewer_name)
                if not reviewer_node or not reviewer_node.is_online:
                    continue
                
                review_prompt = f"""Review this proposal from {agent_name}:

TITLE: {proposal.get('title', 'Unknown')}
DESCRIPTION: {proposal.get('description', '')}
CHANGES: {', '.join(proposal.get('changes', []))}

As {reviewer_name} (expert in {reviewer_profile.expertise}), provide:
VOTE: approve/reject/needs_revision
COMMENTS: [your assessment]
CONCERNS: [any concerns]"""

                try:
                    review_response = reviewer_node.generate(
                        prompt=review_prompt,
                        system=f"You are {reviewer_name}, expert in {reviewer_profile.expertise}. Review this proposal critically.",
                        temperature=0.5,
                        max_tokens=256,
                        timeout=60.0
                    )
                    
                    # Parse vote from response
                    vote = "needs_revision"  # default
                    if review_response:
                        response_lower = review_response.lower()
                        if "vote: approve" in response_lower or "vote:approve" in response_lower:
                            vote = "approve"
                        elif "vote: reject" in response_lower or "vote:reject" in response_lower:
                            vote = "reject"
                    
                    peer_reviews.append({
                        "reviewer": reviewer_name,
                        "expertise": reviewer_profile.expertise,
                        "vote": vote,
                        "response": review_response,
                        "timestamp": time.time()
                    })
                except Exception as e:
                    logger.warning(f"Peer review from {reviewer_name} failed: {e}")
        
        result['stages']['peer_reviews'] = {
            'completed': True,
            'count': len(peer_reviews),
            'reviews': peer_reviews
        }
        
        # Step 4: Run sandbox testing if code-related
        sandbox_result = None
        if proposal.get('domain') in ['code', 'implementation', 'algorithms']:
            integration_mgr = get_integration_manager() if 'get_integration_manager' in dir() else None
            if integration_mgr:
                try:
                    # Check if there's code to test in the proposal
                    implementation = proposal.get('implementation', '')
                    if implementation and len(implementation) > 50:
                        sandbox_result = integration_mgr.execute_tool(
                            'python',
                            f"# Sandbox test for proposal\n# {proposal.get('title', '')}\nprint('Proposal validation passed')",
                            timeout=30.0
                        )
                        result['stages']['sandbox'] = {
                            'completed': True,
                            'result': sandbox_result,
                            'timestamp': time.time()
                        }
                except Exception as e:
                    logger.warning(f"Sandbox testing failed: {e}")
                    result['stages']['sandbox'] = {'completed': False, 'error': str(e)}
        
        # Step 5: Calculate RL reward
        reward = self._calculate_reward(proposal, peer_reviews, sandbox_result)
        result['reward'] = reward
        
        # Step 6: Determine final status
        approve_votes = sum(1 for r in peer_reviews if r.get('vote') == 'approve')
        reject_votes = sum(1 for r in peer_reviews if r.get('vote') == 'reject')
        total_votes = len(peer_reviews)
        
        if total_votes > 0:
            approval_rate = approve_votes / total_votes
            if approval_rate >= 0.6:
                proposal['status'] = 'approved'
            elif reject_votes / total_votes >= 0.4:
                proposal['status'] = 'rejected'
            else:
                proposal['status'] = 'needs_revision'
        
        result['cycle_completed'] = True
        result['cycle_ended'] = time.time()
        result['duration'] = result['cycle_ended'] - result['cycle_started']
        
        return result
    
    def _calculate_reward(
        self,
        proposal: Dict[str, Any],
        peer_reviews: List[Dict[str, Any]],
        sandbox_result: Optional[Dict[str, Any]]
    ) -> float:
        """
        Calculate RL reward for the proposal.
        
        Reward factors:
        - Peer review votes (+0.2 per approve, -0.1 per reject)
        - Research evidence cited (+0.1 if has research)
        - Sandbox test passed (+0.2)
        - Proposal completeness (+0.1 per filled section)
        """
        reward = 0.0
        
        # Peer review component
        for review in peer_reviews:
            vote = review.get('vote', '')
            if vote == 'approve':
                reward += 0.2
            elif vote == 'reject':
                reward -= 0.1
            else:
                reward += 0.05  # needs_revision is neutral-positive
        
        # Research component
        if proposal.get('research_context'):
            reward += 0.1
        
        # Sandbox component
        if sandbox_result and not sandbox_result.get('error'):
            reward += 0.2
        
        # Completeness component
        completeness_fields = ['title', 'description', 'changes', 'benefits', 'risks', 'implementation']
        filled = sum(1 for f in completeness_fields if proposal.get(f))
        reward += filled * 0.05
        
        # Normalize to [0, 1] range
        reward = max(0.0, min(1.0, reward))
        
        return round(reward, 3)
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall manager status."""
        running = sum(1 for r in self._running_agents.values() if r)
        return {
            "running_agents": running,
            "total_agents": len(AGENT_PROFILES),
            "agents": self._running_agents.copy(),
            "council_status": self.council.get_council_status(),
        }


# Global manager instance
_manager: Optional[AutonomousAgentManager] = None


def get_agent_manager() -> AutonomousAgentManager:
    """Get the global agent manager."""
    global _manager
    if _manager is None:
        _manager = AutonomousAgentManager()
    return _manager


# Convenience functions for direct use
def start_agent(name: str) -> bool:
    """Start a specific agent."""
    return get_agent_manager().start_agent(name)


def stop_agent(name: str) -> bool:
    """Stop a specific agent."""
    return get_agent_manager().stop_agent(name)


def start_all_agents() -> Dict[str, bool]:
    """Start all agents."""
    return get_agent_manager().start_all()


def stop_all_agents() -> Dict[str, bool]:
    """Stop all agents."""
    return get_agent_manager().stop_all()


def get_agent_status(name: str) -> Optional[Dict[str, Any]]:
    """Get status of a specific agent."""
    return get_agent_manager().get_agent_status(name)


def get_all_agent_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status of all agents."""
    return get_agent_manager().get_all_statuses()


def generate_proposal_for_agent(
    name: str,
    topic: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Generate a proposal for a specific agent."""
    return get_agent_manager().generate_proposal(name, topic)


def run_proposal_cycle(name: str, full_workflow: bool = False) -> Optional[Dict[str, Any]]:
    """
    Run a proposal cycle for an agent.
    
    Args:
        name: Agent name (e.g., "GIN")
        full_workflow: If True, runs the full 20-step workflow.
                       If False, runs the quick 6-step cycle.
    """
    return get_agent_manager().run_cycle(name, full_workflow=full_workflow)


def run_full_proposal_workflow(name: str, topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the complete 20-step proposal workflow for an agent.
    
    This is the full research-to-reward workflow with file-based tracking:
    - 20 steps across 6 phases
    - Full paper research via PAGEQA
    - Multiple peer reviews
    - Deception and collusion checks
    - ORKA adversarial challenge
    - Sandbox testing
    - Reward calculation
    
    Each step creates an auditable file in the proposal workspace.
    """
    return get_agent_manager().run_full_20_step_workflow(name, topic)


def list_proposal_workspaces() -> List[Dict[str, Any]]:
    """List all proposal workspaces."""
    try:
        from tools.proposal_workflow import list_proposal_workspaces as list_ws
        return list_ws()
    except ImportError:
        return []


def resume_proposal_workflow(workspace_id: str) -> Dict[str, Any]:
    """Resume an interrupted proposal workflow."""
    try:
        from tools.proposal_workflow import resume_workflow
        return resume_workflow(workspace_id)
    except ImportError as e:
        return {"status": "error", "message": str(e)}
