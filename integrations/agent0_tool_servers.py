"""
Agent0 Tool Servers Integration
===============================

Integrates Agent0's verl_tool tool servers so agents can use tools during:
- Proposal generation (execute code, query research, etc.)
- Hypothesis testing (run experiments)
- Research (query PaperQA for evidence-grounded information)

Available tools:
- python_code: Execute Python code safely
- bash_terminal: Execute bash commands
- ipython_code: IPython code execution
- sandbox_fusion: Sandbox execution (for testing proposals)
- sql: SQL database queries
- paperqa_query: Query PaperQA for research (replaces web search)
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
AGENT0_PATH = PROJECT_ROOT / "Agent0" / "Agent0" / "executor_train"

# Try to add Agent0 verl_tool to path
if (AGENT0_PATH / "verl_tool").exists():
    sys.path.insert(0, str(AGENT0_PATH))
    TOOLS_AVAILABLE = True
else:
    TOOLS_AVAILABLE = False
    logger.warning("Agent0 verl_tool not found")


class ToolServerManager:
    """
    Manages Agent0 tool servers for agent use.
    
    Agents can call tools like:
    - python_code: Execute Python code
    - bash_terminal: Run bash commands
    - search: Search the web
    - sql: Query databases
    """
    
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize available tools."""
        if not TOOLS_AVAILABLE:
            logger.warning("Agent0 tools not available")
            return False
        
        if self._initialized:
            return True
        
        try:
            # Import tool base
            from verl_tool.servers.tools.base import get_tool_cls, ALL_TOOLS
            
            # Initialize available tools
            available_tool_types = [
                'python_code',
                'bash_terminal',
                'ipython_code',
                'sandbox_fusion',
                'sql',
            ]
            
            for tool_type in available_tool_types:
                try:
                    tool_cls = get_tool_cls(tool_type)
                    tool_instance = tool_cls(num_workers=1)
                    self.tools[tool_type] = tool_instance
                    logger.info(f"Initialized tool: {tool_type}")
                except Exception as e:
                    logger.debug(f"Failed to initialize {tool_type}: {e}")
            
            self._initialized = True
            logger.info(f"Tool server manager initialized with {len(self.tools)} tools")
            return True
            
        except ImportError as e:
            logger.warning(f"Failed to import verl_tool: {e}")
            return False
        except Exception as e:
            logger.error(f"Tool initialization failed: {e}")
            return False
    
    def get_tool(self, tool_name: str) -> Optional[Any]:
        """Get a tool by name."""
        if not self._initialized:
            self.initialize()
        
        # PaperQA is not an Agent0 tool, but is available
        if tool_name == 'paperqa_query':
            return 'paperqa_query'  # Return marker to indicate it's available
        
        return self.tools.get(tool_name)
    
    def list_available_tools(self) -> List[str]:
        """List all available tools."""
        if not self._initialized:
            self.initialize()
        
        # Include PaperQA query tool (not an Agent0 tool, but available)
        tools_list = list(self.tools.keys())
        if 'paperqa_query' not in tools_list:
            tools_list.append('paperqa_query')
        
        return tools_list
    
    async def execute_tool(
        self,
        tool_name: str,
        action: str,
        trajectory_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a tool action.
        
        Args:
            tool_name: Name of tool (e.g., 'python_code', 'paperqa_query')
            action: Action to execute (e.g., Python code string or research query)
            trajectory_id: ID for maintaining tool state
            **kwargs: Additional tool-specific parameters
            
        Returns:
            Dict with:
            - observation: Tool output
            - is_valid: Whether execution succeeded
            - extra_field: Additional metadata
        """
        if not self._initialized:
            self.initialize()
        
        # Special handling for PaperQA (not an Agent0 tool)
        if tool_name == 'paperqa_query':
            depth = kwargs.get('depth', 'moderate')
            return await query_paperqa_async(action, depth)
        
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                'observation': f"Tool {tool_name} not available",
                'is_valid': False,
                'extra_field': {}
            }
        
        try:
            # Load/create environment for this trajectory
            env = tool.load_env(trajectory_id)
            
            # Execute tool action
            # Tool interface: execute(trajectory_id, action, env, **kwargs)
            result = tool.execute(trajectory_id, action, env, **kwargs)
            
            # Update environment
            tool.update_env(
                trajectory_id,
                env,
                action=action,
                is_valid=result.get('is_valid', False),
                extra_field=result.get('extra_field', {}),
                observation=result.get('observation', ''),
                **kwargs
            )
            
            # Save environment
            tool.save_env(trajectory_id, env)
            
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                'observation': f"Error: {str(e)}",
                'is_valid': False,
                'extra_field': {'error': str(e)}
            }
    
    def execute_tool_sync(
        self,
        tool_name: str,
        action: str,
        trajectory_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """Synchronous wrapper for execute_tool."""
        import asyncio
        return asyncio.run(self.execute_tool(tool_name, action, trajectory_id, **kwargs))


# Global tool manager
_tool_manager: Optional[ToolServerManager] = None

def get_tool_manager() -> ToolServerManager:
    """Get or create the global tool manager."""
    global _tool_manager
    if _tool_manager is None:
        _tool_manager = ToolServerManager()
        _tool_manager.initialize()
    return _tool_manager


# Convenience functions for agents
def execute_python_code(code: str, trajectory_id: str = "default") -> Dict[str, Any]:
    """Execute Python code using Agent0's python_code tool."""
    manager = get_tool_manager()
    return manager.execute_tool_sync('python_code', code, trajectory_id)


def execute_bash_command(command: str, trajectory_id: str = "default") -> Dict[str, Any]:
    """Execute bash command using Agent0's bash_terminal tool."""
    manager = get_tool_manager()
    return manager.execute_tool_sync('bash_terminal', command, trajectory_id)




def execute_sql_query(query: str, trajectory_id: str = "default") -> Dict[str, Any]:
    """Execute SQL query using Agent0's sql tool."""
    manager = get_tool_manager()
    return manager.execute_tool_sync('sql', query, trajectory_id)


async def query_paperqa_async(query: str, depth: str = "moderate") -> Dict[str, Any]:
    """
    Query PaperQA for research information.
    
    This is the tool agents should use instead of web search.
    PaperQA provides evidence-grounded answers from the research database.
    
    Args:
        query: Research question or topic
        depth: Research depth ("shallow", "moderate", "deep")
        
    Returns:
        Dict with:
        - findings: Research findings/answer
        - sources: List of source documents
        - confidence: Confidence score (0-1)
        - observation: Formatted response for agent
    """
    try:
        from integrations.paperqa_rag import PaperQARAG
        
        rag = PaperQARAG()
        result = await rag.research_topic(query, depth=depth)
        
        # Format as tool observation
        observation = f"Research Findings:\n{result.get('findings', 'No findings')}\n\n"
        observation += f"Sources ({len(result.get('sources', []))}):\n"
        for i, source in enumerate(result.get('sources', [])[:5], 1):
            observation += f"  {i}. {source}\n"
        observation += f"\nConfidence: {result.get('confidence', 0.0):.2f}"
        
        return {
            'observation': observation,
            'is_valid': True,
            'extra_field': {
                'findings': result.get('findings'),
                'sources': result.get('sources', []),
                'confidence': result.get('confidence', 0.0),
                'topic': query
            }
        }
        
    except ImportError:
        return {
            'observation': 'PaperQA not available',
            'is_valid': False,
            'extra_field': {'error': 'PaperQA import failed'}
        }
    except Exception as e:
        logger.error(f"PaperQA query failed: {e}")
        return {
            'observation': f'Error querying PaperQA: {str(e)}',
            'is_valid': False,
            'extra_field': {'error': str(e)}
        }


def query_paperqa(query: str, depth: str = "moderate") -> Dict[str, Any]:
    """
    Synchronous wrapper for PaperQA query.
    
    Agents should use this tool to get research information instead of web search.
    
    Args:
        query: Research question or topic
        depth: Research depth ("shallow", "moderate", "deep")
        
    Returns:
        Dict with research findings, sources, and confidence
    """
    return asyncio.run(query_paperqa_async(query, depth))


# Tool registry for agents
class AgentToolRegistry:
    """
    Registry of tools available to agents.
    
    Agents can query this to see what tools they can use.
    """
    
    def __init__(self):
        self.manager = get_tool_manager()
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available tools."""
        tools = {}
        
        tool_descriptions = {
            'python_code': 'Execute Python code safely in isolated environment',
            'bash_terminal': 'Execute bash/terminal commands',
            'ipython_code': 'Execute Python code in IPython environment',
            'sandbox_fusion': 'Execute code in sandbox (for testing proposals)',
            'sql': 'Execute SQL queries on databases',
            'paperqa_query': 'Query PaperQA for evidence-grounded research (use instead of web search)',
        }
        
        available = self.manager.list_available_tools()
        for tool_name in available:
            if tool_name in tool_descriptions:
                tools[tool_name] = tool_descriptions[tool_name]
        
        return tools
    
    def get_tool_usage(self, tool_name: str) -> str:
        """Get usage instructions for a tool."""
        tool = self.manager.get_tool(tool_name)
        if tool:
            return tool.get_usage_inst()
        return f"Tool {tool_name} not available"


# Export
__all__ = [
    'ToolServerManager',
    'get_tool_manager',
    'execute_python_code',
    'execute_bash_command',
    'execute_sql_query',
    'query_paperqa',
    'query_paperqa_async',
    'AgentToolRegistry',
]

