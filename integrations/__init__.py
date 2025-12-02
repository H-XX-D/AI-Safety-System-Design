"""
Integrations Package
====================

Connects external tools (PaperQA, verl, EasyR1, Robin, Agent0) into the AI Safety System.

- paperqa_rag.py: RAG integration for evidence-grounded research
- rl_trainer.py: RL training integration for self-improvement
- robin_hypothesis.py: Robin-style hypothesis generation & experiment design
- agent0_self_play.py: Agent0-style self-play for hypothesis generation
- tool_hypothesis.py: Hypothesis generation tool for agents
"""

from .paperqa_rag import PaperQAIntegration, LocalRAG
from .rl_trainer import RLTrainer, TrainingConfig
from .robin_hypothesis import (
    HypothesisGenerator,
    ImprovementHypothesis,
    ExperimentDesign,
    generate_improvement_proposals,
    generate_improvement_proposals_sync,
)
from .agent0_self_play import (
    Agent0SelfPlay,
    HypothesisTask,
    SelfPlayResult,
    broadcast_hypothesis_improvement,
    get_self_play,
    get_best_hypotheses,
    trigger_next_cycle,
    learn_from_success,
)
from .tool_hypothesis import (
    HypothesisTool,
    HypothesisResult,
    get_hypothesis_tool,
    generate_hypothesis,
    generate_hypothesis_sync,
)
from .safety_quality_tools import (
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
from .agent0_tool_servers import (
    ToolServerManager,
    get_tool_manager,
    execute_python_code,
    execute_bash_command,
    execute_sql_query,
    query_paperqa,
    query_paperqa_async,
    AgentToolRegistry,
)
from .paperqa_proposal_filter import (
    PaperQAProposalFilter,
    get_proposal_filter,
    filter_proposal_with_paperqa,
    filter_proposal_sync,
)
from .paperqa_feedback_system import (
    PaperQAFeedbackSystem,
    get_feedback_system,
    query_paperqa_with_feedback,
    note_hypothesis_contradiction,
    record_hypothesis_attempt,
)
from .ai_memory_system import (
    AIMemorySystem,
    ShortTermMemory,
    LongTermMemory,
    SharedMemoryClient,
)

__all__ = [
    # PaperQA RAG
    'PaperQAIntegration',
    'LocalRAG', 
    # RL Training
    'RLTrainer',
    'TrainingConfig',
    # Robin Hypothesis Generation
    'HypothesisGenerator',
    'ImprovementHypothesis',
    'ExperimentDesign',
    'generate_improvement_proposals',
    'generate_improvement_proposals_sync',
    # Agent0 Self-Play
    'Agent0SelfPlay',
    'HypothesisTask',
    'SelfPlayResult',
    'broadcast_hypothesis_improvement',
    'get_self_play',
    'get_best_hypotheses',
    'trigger_next_cycle',
    'learn_from_success',
    # Hypothesis Tool
    'HypothesisTool',
    'HypothesisResult',
    'get_hypothesis_tool',
    'generate_hypothesis',
    'generate_hypothesis_sync',
    # Agent0 Additional Tools (Safety-Focused)
    'proposal_consistency_tool',
    'hypothesis_scoring_tool',
    'safe_training_data_filter_tool',
    'proposal_deduplication_tool',
    'validate_proposal_consistency',
    'score_improvement_hypothesis',
    'filter_safe_training_examples',
    'group_similar_proposals',
    'select_best_from_groups',
    # Agent0 Tool Servers
    'ToolServerManager',
    'get_tool_manager',
    'execute_python_code',
    'execute_bash_command',
    'execute_sql_query',
    'query_paperqa',
    'query_paperqa_async',
    'AgentToolRegistry',
    # PaperQA Proposal Filter
    'PaperQAProposalFilter',
    'get_proposal_filter',
    'filter_proposal_with_paperqa',
    'filter_proposal_sync',
    # PaperQA Feedback System
    'PaperQAFeedbackSystem',
    'get_feedback_system',
    'query_paperqa_with_feedback',
    'note_hypothesis_contradiction',
    'record_hypothesis_attempt',
    # AI Memory System
    'AIMemorySystem',
    'ShortTermMemory',
    'LongTermMemory',
    'SharedMemoryClient',
]

