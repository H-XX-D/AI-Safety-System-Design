"""
Integrations Tools Wrapper
==========================

Provides unified access to all integrations for the nano cluster and workflow.

Available integrations:
- PaperQA RAG: Evidence-grounded research
- Robin Hypothesis: Scientific hypothesis generation
- Agent0 Self-Play: Competitive hypothesis improvement
- Safety Quality Tools: Proposal validation and scoring
- Tool Servers: Agent0 code/bash execution tools
- AI Memory System: Three-tier memory architecture

Each integration is wrapped for consistent access from the cluster tools
and UI endpoints.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

# Track what's available
INTEGRATIONS_AVAILABLE: Dict[str, bool] = {}


# ============================================================================
# IMPORT INTEGRATIONS WITH GRACEFUL FALLBACK
# ============================================================================

# PaperQA RAG
try:
    from integrations.paperqa_rag import (
        PaperQAIntegration,
        LocalRAG,
        RAGResult,
        RAGConfig,
    )
    INTEGRATIONS_AVAILABLE['paperqa_rag'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['paperqa_rag'] = False
    PaperQAIntegration = None
    LocalRAG = None
    RAGResult = None
    RAGConfig = None
    logger.warning(f"PaperQA RAG not available: {e}")

# Robin Hypothesis
try:
    from integrations.robin_hypothesis import (
        HypothesisGenerator,
        ImprovementHypothesis,
        ExperimentDesign,
        generate_improvement_proposals,
        generate_improvement_proposals_sync,
    )
    INTEGRATIONS_AVAILABLE['robin_hypothesis'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['robin_hypothesis'] = False
    HypothesisGenerator = None
    ImprovementHypothesis = None
    ExperimentDesign = None
    generate_improvement_proposals = None
    generate_improvement_proposals_sync = None
    logger.warning(f"Robin Hypothesis not available: {e}")

# Agent0 Self-Play
try:
    from integrations.agent0_self_play import (
        Agent0SelfPlay,
        HypothesisTask,
        SelfPlayResult,
        broadcast_hypothesis_improvement,
        get_self_play,
        get_best_hypotheses,
        trigger_next_cycle,
        learn_from_success,
    )
    INTEGRATIONS_AVAILABLE['agent0_self_play'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['agent0_self_play'] = False
    Agent0SelfPlay = None
    HypothesisTask = None
    SelfPlayResult = None
    broadcast_hypothesis_improvement = None
    get_self_play = None
    get_best_hypotheses = None
    trigger_next_cycle = None
    learn_from_success = None
    logger.warning(f"Agent0 Self-Play not available: {e}")

# Safety Quality Tools
try:
    from integrations.safety_quality_tools import (
        proposal_consistency_tool,
        hypothesis_scoring_tool,
        safe_training_data_filter_tool,
        proposal_deduplication_tool,
        validate_proposal_consistency,
        score_improvement_hypothesis,
        filter_safe_training_examples,
        group_similar_proposals,
        select_best_from_groups,
    )
    INTEGRATIONS_AVAILABLE['safety_quality_tools'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['safety_quality_tools'] = False
    proposal_consistency_tool = None
    hypothesis_scoring_tool = None
    safe_training_data_filter_tool = None
    proposal_deduplication_tool = None
    validate_proposal_consistency = None
    score_improvement_hypothesis = None
    filter_safe_training_examples = None
    group_similar_proposals = None
    select_best_from_groups = None
    logger.warning(f"Safety Quality Tools not available: {e}")

# Tool Servers (Agent0)
try:
    from integrations.agent0_tool_servers import (
        ToolServerManager,
        get_tool_manager,
        TOOLS_AVAILABLE as AGENT0_TOOLS,
    )
    INTEGRATIONS_AVAILABLE['tool_servers'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['tool_servers'] = False
    ToolServerManager = None
    get_tool_manager = None
    AGENT0_TOOLS = False
    logger.warning(f"Tool Servers not available: {e}")

# AI Memory System
try:
    from integrations.ai_memory_system import (
        ShortTermMemory,
        LongTermMemory,
        SharedMemoryClient,
        AIMemorySystem,
    )
    INTEGRATIONS_AVAILABLE['ai_memory_system'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['ai_memory_system'] = False
    ShortTermMemory = None
    LongTermMemory = None
    SharedMemoryClient = None
    AIMemorySystem = None
    logger.warning(f"AI Memory System not available: {e}")

# RL Trainer
try:
    from integrations.rl_trainer import (
        RLTrainer,
        TrainingConfig,
    )
    INTEGRATIONS_AVAILABLE['rl_trainer'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['rl_trainer'] = False
    RLTrainer = None
    TrainingConfig = None
    logger.warning(f"RL Trainer not available: {e}")

# Tool Hypothesis
try:
    from integrations.tool_hypothesis import (
        HypothesisTool,
        HypothesisResult,
        get_hypothesis_tool,
        generate_hypothesis,
        generate_hypothesis_sync,
    )
    INTEGRATIONS_AVAILABLE['tool_hypothesis'] = True
except ImportError as e:
    INTEGRATIONS_AVAILABLE['tool_hypothesis'] = False
    HypothesisTool = None
    HypothesisResult = None
    get_hypothesis_tool = None
    generate_hypothesis = None
    generate_hypothesis_sync = None
    logger.warning(f"Tool Hypothesis not available: {e}")


# ============================================================================
# INTEGRATION STATUS & INFO
# ============================================================================

@dataclass
class IntegrationInfo:
    """Information about an integration."""
    name: str
    available: bool
    description: str
    category: str
    capabilities: List[str]
    nano_nodes: List[str]  # Which nanos can use this


INTEGRATION_REGISTRY: Dict[str, IntegrationInfo] = {
    'paperqa_rag': IntegrationInfo(
        name='PaperQA RAG',
        available=INTEGRATIONS_AVAILABLE.get('paperqa_rag', False),
        description='Evidence-grounded research via local RAG',
        category='research',
        capabilities=['query_documents', 'cite_sources', 'summarize'],
        nano_nodes=['PAGEQA', 'ORIN'],
    ),
    'robin_hypothesis': IntegrationInfo(
        name='Robin Hypothesis',
        available=INTEGRATIONS_AVAILABLE.get('robin_hypothesis', False),
        description='Scientific hypothesis generation & experiment design',
        category='research',
        capabilities=['generate_hypotheses', 'design_experiments', 'rank_hypotheses'],
        nano_nodes=['TIF', 'GIN', 'ORIN'],
    ),
    'agent0_self_play': IntegrationInfo(
        name='Agent0 Self-Play',
        available=INTEGRATIONS_AVAILABLE.get('agent0_self_play', False),
        description='Competitive hypothesis improvement via self-play',
        category='training',
        capabilities=['self_play', 'hypothesis_competition', 'skill_learning'],
        nano_nodes=['ORKA', 'TIF', 'GIN'],
    ),
    'safety_quality_tools': IntegrationInfo(
        name='Safety Quality Tools',
        available=INTEGRATIONS_AVAILABLE.get('safety_quality_tools', False),
        description='Proposal validation, scoring, and deduplication',
        category='safety',
        capabilities=['consistency_check', 'quality_scoring', 'deduplication', 'safe_filtering'],
        nano_nodes=['GUARD', 'TORI', 'ARCHI'],
    ),
    'tool_servers': IntegrationInfo(
        name='Tool Servers',
        available=INTEGRATIONS_AVAILABLE.get('tool_servers', False),
        description='Agent0 code/bash execution tools',
        category='execution',
        capabilities=['python_code', 'bash_terminal', 'sql', 'sandbox'],
        nano_nodes=['GIN', 'TIF'],
    ),
    'ai_memory_system': IntegrationInfo(
        name='AI Memory System',
        available=INTEGRATIONS_AVAILABLE.get('ai_memory_system', False),
        description='Three-tier memory architecture per agent',
        category='memory',
        capabilities=['short_term', 'long_term', 'shared_memory'],
        nano_nodes=['ALL'],
    ),
    'rl_trainer': IntegrationInfo(
        name='RL Trainer',
        available=INTEGRATIONS_AVAILABLE.get('rl_trainer', False),
        description='Reinforcement learning for self-improvement',
        category='training',
        capabilities=['training_config', 'reward_signals', 'policy_updates'],
        nano_nodes=['ORKA'],
    ),
    'tool_hypothesis': IntegrationInfo(
        name='Tool Hypothesis',
        available=INTEGRATIONS_AVAILABLE.get('tool_hypothesis', False),
        description='Hypothesis generation tool for agents',
        category='research',
        capabilities=['generate_hypothesis', 'rank_by_impact'],
        nano_nodes=['TIF', 'GIN', 'ORIN', 'PAGEQA'],
    ),
}


def get_integration_status() -> Dict[str, Any]:
    """Get status of all integrations."""
    return {
        name: {
            'available': info.available,
            'description': info.description,
            'category': info.category,
            'capabilities': info.capabilities,
            'nano_nodes': info.nano_nodes,
        }
        for name, info in INTEGRATION_REGISTRY.items()
    }


def get_available_integrations() -> List[str]:
    """Get list of available integration names."""
    return [name for name, info in INTEGRATION_REGISTRY.items() if info.available]


def get_integrations_by_category(category: str) -> List[str]:
    """Get integrations in a specific category."""
    return [
        name for name, info in INTEGRATION_REGISTRY.items()
        if info.category == category and info.available
    ]


def get_integrations_for_nano(nano_name: str) -> List[str]:
    """Get integrations available for a specific nano."""
    return [
        name for name, info in INTEGRATION_REGISTRY.items()
        if info.available and (nano_name in info.nano_nodes or 'ALL' in info.nano_nodes)
    ]


# ============================================================================
# UNIFIED INTEGRATION MANAGER
# ============================================================================

class IntegrationManager:
    """
    Central manager for all integrations.
    
    Provides unified access to integrations from nano cluster nodes
    and the orchestrator.
    """
    
    def __init__(self):
        self._rag: Optional[Any] = None
        self._hypothesis_gen: Optional[Any] = None
        self._self_play: Optional[Any] = None
        self._tool_manager: Optional[Any] = None
        self._initialized: Dict[str, bool] = {}
    
    def get_rag(self) -> Optional[Any]:
        """Get or create RAG instance."""
        if not INTEGRATIONS_AVAILABLE.get('paperqa_rag'):
            return None
        if self._rag is None:
            self._rag = LocalRAG()
            self._initialized['paperqa_rag'] = True
        return self._rag
    
    def get_hypothesis_generator(self) -> Optional[Any]:
        """Get or create hypothesis generator."""
        if not INTEGRATIONS_AVAILABLE.get('robin_hypothesis'):
            return None
        if self._hypothesis_gen is None:
            self._hypothesis_gen = HypothesisGenerator()
            self._initialized['robin_hypothesis'] = True
        return self._hypothesis_gen
    
    def get_self_play(self) -> Optional[Any]:
        """Get or create self-play instance."""
        if not INTEGRATIONS_AVAILABLE.get('agent0_self_play'):
            return None
        if self._self_play is None:
            self._self_play = Agent0SelfPlay()
            self._initialized['agent0_self_play'] = True
        return self._self_play
    
    def get_tool_manager(self) -> Optional[Any]:
        """Get or create tool server manager."""
        if not INTEGRATIONS_AVAILABLE.get('tool_servers'):
            return None
        if self._tool_manager is None:
            self._tool_manager = ToolServerManager()
            self._tool_manager.initialize()
            self._initialized['tool_servers'] = True
        return self._tool_manager
    
    def query_rag(self, query: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Query RAG for research information.
        
        Uses PAGEQA nano's Ollama for evidence-grounded research.
        Falls back to direct PAGEQA integration if PaperQA not available.
        """
        # Try direct PAGEQA first (more reliable, no PaperQA dependency)
        try:
            from integrations.paperqa_rag import research_with_pageqa
            result = research_with_pageqa(query)
            if result and result.get('answer') and not result['answer'].startswith('Unable to query'):
                return result
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Direct PAGEQA query failed: {e}")
        
        # Fall back to LocalRAG if available
        rag = self.get_rag()
        if rag is None:
            return {'error': 'RAG not available', 'query': query}
        
        try:
            result = rag.query(query, **kwargs)
            if hasattr(result, 'to_dict'):
                return result.to_dict()
            return result
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {'error': str(e)}
    
    def generate_hypotheses(
        self,
        target_component: str,
        context: str = "",
        num_hypotheses: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate improvement hypotheses."""
        gen = self.get_hypothesis_generator()
        if gen is None:
            return []
        
        try:
            hypotheses = gen.generate_improvement_hypotheses(
                target_component=target_component,
                context=context,
                num_hypotheses=num_hypotheses
            )
            return [asdict(h) if hasattr(h, '__dataclass_fields__') else h for h in hypotheses]
        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            return []
    
    def check_proposal_consistency(
        self,
        proposal: Dict[str, Any],
        deception_score: float = 0.0,
        peer_reviews: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Check proposal consistency using safety tools."""
        if not INTEGRATIONS_AVAILABLE.get('safety_quality_tools'):
            return {'error': 'Safety quality tools not available'}
        
        try:
            checker = proposal_consistency_tool()
            return checker.check_proposal(proposal, deception_score, peer_reviews)
        except Exception as e:
            logger.error(f"Proposal consistency check failed: {e}")
            return {'error': str(e)}
    
    def score_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        evidence: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Score a hypothesis using quality tools."""
        if not INTEGRATIONS_AVAILABLE.get('safety_quality_tools'):
            return {'error': 'Safety quality tools not available'}
        
        try:
            scorer = hypothesis_scoring_tool()
            return scorer.score_hypothesis(hypothesis, evidence or [])
        except Exception as e:
            logger.error(f"Hypothesis scoring failed: {e}")
            return {'error': str(e)}
    
    def execute_tool(
        self,
        tool_type: str,
        code: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Execute code using tool servers."""
        manager = self.get_tool_manager()
        if manager is None:
            return {'error': 'Tool servers not available'}
        
        try:
            return manager.execute(tool_type, code, timeout=timeout)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get integration manager status."""
        return {
            'initialized': self._initialized,
            'integrations': get_integration_status(),
            'available_count': len(get_available_integrations()),
            'total_count': len(INTEGRATION_REGISTRY),
        }


# Global manager instance
_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager() -> IntegrationManager:
    """Get the global integration manager."""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = IntegrationManager()
    return _integration_manager


# ============================================================================
# CONVENIENCE FUNCTIONS FOR NANO CLUSTER
# ============================================================================

def research_query(query: str, nano: str = "PAGEQA") -> Dict[str, Any]:
    """
    Execute a research query using the appropriate integration.
    
    Args:
        query: Research question
        nano: Which nano is making the request
    
    Returns:
        Research result with sources
    """
    manager = get_integration_manager()
    result = manager.query_rag(query)
    if result:
        result['queried_by'] = nano
    return result or {'error': 'RAG not available', 'queried_by': nano}


def propose_improvement(
    target: str,
    context: str = "",
    nano: str = "TIF"
) -> List[Dict[str, Any]]:
    """
    Generate improvement proposals using hypothesis generation.
    
    Args:
        target: Component to improve
        context: Additional context
        nano: Which nano is making the request
    
    Returns:
        List of improvement hypotheses
    """
    manager = get_integration_manager()
    hypotheses = manager.generate_hypotheses(target, context)
    for h in hypotheses:
        h['proposed_by'] = nano
    return hypotheses


def validate_proposal(
    proposal: Dict[str, Any],
    nano: str = "GUARD"
) -> Dict[str, Any]:
    """
    Validate a proposal using safety tools.
    
    Args:
        proposal: Proposal to validate
        nano: Which nano is validating
    
    Returns:
        Validation result with consistency score
    """
    manager = get_integration_manager()
    result = manager.check_proposal_consistency(proposal)
    result['validated_by'] = nano
    return result


def run_code_in_sandbox(
    code: str,
    language: str = "python",
    nano: str = "GIN"
) -> Dict[str, Any]:
    """
    Execute code in a sandboxed environment.
    
    Args:
        code: Code to execute
        language: Programming language
        nano: Which nano is running code
    
    Returns:
        Execution result
    """
    manager = get_integration_manager()
    tool_type = "python_code" if language == "python" else "bash_terminal"
    result = manager.execute_tool(tool_type, code)
    result['executed_by'] = nano
    return result


# ============================================================================
# INTEGRATION WORKFLOW HELPERS
# ============================================================================

def research_and_propose(
    topic: str,
    target_component: str,
    num_hypotheses: int = 3
) -> Dict[str, Any]:
    """
    Full workflow: research a topic then propose improvements.
    
    1. Query RAG for background research
    2. Generate hypotheses based on research
    3. Score and rank hypotheses
    
    Returns complete workflow result.
    """
    manager = get_integration_manager()
    
    # Step 1: Research
    research = manager.query_rag(f"Best practices for {topic} in {target_component}")
    
    # Step 2: Generate hypotheses
    context = research.get('answer', '') if research else ''
    hypotheses = manager.generate_hypotheses(
        target_component=target_component,
        context=context,
        num_hypotheses=num_hypotheses
    )
    
    # Step 3: Score hypotheses
    scored = []
    for h in hypotheses:
        score_result = manager.score_hypothesis(h, research.get('sources', []) if research else [])
        h['score'] = score_result.get('score', 0.5)
        h['score_details'] = score_result
        scored.append(h)
    
    # Sort by score
    scored.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return {
        'research': research,
        'hypotheses': scored,
        'best_hypothesis': scored[0] if scored else None,
        'topic': topic,
        'target_component': target_component,
    }


def validate_and_filter_proposals(
    proposals: List[Dict[str, Any]],
    max_deception_score: float = 0.3
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate proposals and filter out unsafe ones.
    
    Returns (passed, rejected) tuple.
    """
    if not INTEGRATIONS_AVAILABLE.get('safety_quality_tools'):
        # No safety tools, pass all with warning
        for p in proposals:
            p['validation_warning'] = 'Safety tools not available'
        return proposals, []
    
    passed = []
    rejected = []
    
    for proposal in proposals:
        result = validate_proposal(proposal)
        proposal['validation'] = result
        
        if result.get('passed', False):
            passed.append(proposal)
        else:
            rejected.append(proposal)
    
    return passed, rejected
