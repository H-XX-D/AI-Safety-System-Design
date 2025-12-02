"""
Research System Components
===========================

This package contains research agents, LLM adapters, and improvement
mechanisms for the AI Safety System.
"""

from .research_system import ResearchSystem, SystemSpecialization
from .llm_adapters import ThirdLMAdapter
from .llm_adapter_factory import create_llm_adapter
from .debate_engine import DebateEngine
from .research_system import TemplateLLMAdapter

__all__ = [
    'ResearchSystem',
    'SystemSpecialization',
    'ThirdLMAdapter',
    'create_llm_adapter',
    'DebateEngine',
    'TemplateLLMAdapter'
]
