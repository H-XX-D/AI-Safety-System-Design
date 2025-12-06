"""
AI Safety System Design - Tools Package

This package contains tools for:
- Nano cluster management and communication
- Orchestrator debugging
- Firecracker VM management
- Patent search
- Deception evaluation
- PaperQA integration
- Research & hypothesis generation integrations
- Safety quality tools
"""

from .nano_cluster import (
    NanoCluster,
    NanoNode,
    NanoRole,
    CLUSTER_ROLES,
    get_cluster,
    init_cluster,
    check_cluster_status,
    generate,
    broadcast,
    check_safety,
)

from .integrations import (
    # Status & registry
    INTEGRATIONS_AVAILABLE,
    INTEGRATION_REGISTRY,
    IntegrationInfo,
    IntegrationManager,
    get_integration_manager,
    get_integration_status,
    get_available_integrations,
    get_integrations_by_category,
    get_integrations_for_nano,
    # Convenience functions
    research_query,
    propose_improvement,
    validate_proposal,
    run_code_in_sandbox,
    # Workflow helpers
    research_and_propose,
    validate_and_filter_proposals,
)

from .autonomous_agents import (
    # Core types
    NanoAgent,
    NANO_AGENTS,
    # Manager
    AutonomousAgentManager,
    get_agent_manager,
    # Agent control
    start_agent,
    stop_agent,
    start_all_agents,
    stop_all_agents,
    get_agent_status,
    get_all_agent_statuses,
    # Proposal generation
    generate_proposal_for_agent,
    run_proposal_cycle,
    # 20-step workflow
    run_full_proposal_workflow,
    list_proposal_workspaces,
    resume_proposal_workflow,
)

__all__ = [
    # Nano cluster
    "NanoCluster",
    "NanoNode",
    "NanoRole",
    "CLUSTER_ROLES",
    "get_cluster",
    "init_cluster",
    "check_cluster_status",
    "generate",
    "broadcast",
    "check_safety",
    # Integrations
    "INTEGRATIONS_AVAILABLE",
    "INTEGRATION_REGISTRY",
    "IntegrationInfo",
    "IntegrationManager",
    "get_integration_manager",
    "get_integration_status",
    "get_available_integrations",
    "get_integrations_by_category",
    "get_integrations_for_nano",
    "research_query",
    "propose_improvement",
    "validate_proposal",
    "run_code_in_sandbox",
    "research_and_propose",
    "validate_and_filter_proposals",
    # Autonomous agents
    "NanoAgent",
    "NANO_AGENTS",
    "AutonomousAgentManager",
    "get_agent_manager",
    "start_agent",
    "stop_agent",
    "start_all_agents",
    "stop_all_agents",
    "get_agent_status",
    "get_all_agent_statuses",
    "generate_proposal_for_agent",
    "run_proposal_cycle",
    # 20-step workflow
    "run_full_proposal_workflow",
    "list_proposal_workspaces",
    "resume_proposal_workflow",
]
