"""
LLM Adapter Factory
===================

Factory for creating LLM adapters based on configuration.
Integrates with config/default.yaml to select and configure adapters.

Usage:
    from llm_adapter_factory import create_llm_adapter

    # Create adapter based on config
    adapter = create_llm_adapter()

    # Or specify adapter type explicitly
    adapter = create_llm_adapter(adapter_type="openai")
"""

from typing import Optional, Dict, Any
from logging_config import get_logger
from config_loader import load_config

# Import base adapter
from research_system import BaseLLMAdapter, TemplateLLMAdapter

logger = get_logger(__name__)


def create_llm_adapter(
    adapter_type: Optional[str] = None,
    config_override: Optional[Dict[str, Any]] = None
) -> BaseLLMAdapter:
    """
    Create an LLM adapter based on configuration.

    Args:
        adapter_type: Override adapter type ('template', 'openai', 'claude')
                     If None, loads from config/default.yaml
        config_override: Override specific config values

    Returns:
        BaseLLMAdapter instance (TemplateLLMAdapter, OpenAIAdapter, or ClaudeAdapter)

    Raises:
        ValueError: If adapter_type is invalid or configuration is missing
        ImportError: If required package not installed (openai/anthropic)
    """
    # Load configuration
    cfg = load_config()
    llm_config = cfg.get("llm", {})

    # Determine adapter type
    if adapter_type is None:
        adapter_type = llm_config.get("adapter_type", "template")

    # Strip comments from config value (in case YAML comment is included)
    if isinstance(adapter_type, str):
        adapter_type = adapter_type.split("#")[0].strip()

    logger.info(f"Creating LLM adapter: type={adapter_type}")

    # Apply config overrides
    if config_override:
        llm_config.update(config_override)

    # Create adapter based on type
    if adapter_type == "template":
        return _create_template_adapter(llm_config)
    elif adapter_type == "openai":
        return _create_openai_adapter(llm_config)
    elif adapter_type == "claude":
        return _create_claude_adapter(llm_config)
    else:
        raise ValueError(
            f"Unknown adapter_type: {adapter_type}. "
            f"Must be 'template', 'openai', or 'claude'"
        )


def _create_template_adapter(config: Dict[str, Any]) -> TemplateLLMAdapter:
    """Create template adapter (no API key needed)."""
    logger.info("Using TemplateLLMAdapter (deterministic)")
    return TemplateLLMAdapter()


def _create_openai_adapter(config: Dict[str, Any]) -> BaseLLMAdapter:
    """Create OpenAI adapter."""
    try:
        from llm_adapters import OpenAIAdapter
    except ImportError as e:
        logger.error("OpenAI package not installed")
        raise ImportError(
            "OpenAI package required for openai adapter. "
            "Install with: pip install openai"
        ) from e

    openai_config = config.get("openai", {})

    # Extract configuration
    model = openai_config.get("model", "gpt-4-turbo-preview")
    temperature = float(openai_config.get("temperature", 0.7))
    max_tokens = int(openai_config.get("max_tokens", 2000))
    timeout = float(openai_config.get("timeout", 60.0))

    logger.info(
        f"Creating OpenAI adapter: model={model}, "
        f"temperature={temperature}, max_tokens={max_tokens}"
    )

    try:
        adapter = OpenAIAdapter(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
        logger.info("✓ OpenAI adapter created successfully")
        return adapter

    except ValueError as e:
        logger.error(f"OpenAI configuration error: {e}")
        logger.warning("Falling back to template adapter")
        logger.info("Set OPENAI_API_KEY environment variable to use OpenAI")
        return TemplateLLMAdapter()

    except Exception as e:
        logger.error(f"Failed to create OpenAI adapter: {e}")
        logger.warning("Falling back to template adapter")
        return TemplateLLMAdapter()


def _create_claude_adapter(config: Dict[str, Any]) -> BaseLLMAdapter:
    """Create Claude adapter."""
    try:
        from llm_adapters import ClaudeAdapter
    except ImportError as e:
        logger.error("Anthropic package not installed")
        raise ImportError(
            "Anthropic package required for claude adapter. "
            "Install with: pip install anthropic"
        ) from e

    claude_config = config.get("claude", {})

    # Extract configuration
    model = claude_config.get("model", "claude-3-5-sonnet-20241022")
    temperature = float(claude_config.get("temperature", 0.7))
    max_tokens = int(claude_config.get("max_tokens", 2000))
    timeout = float(claude_config.get("timeout", 60.0))

    logger.info(
        f"Creating Claude adapter: model={model}, "
        f"temperature={temperature}, max_tokens={max_tokens}"
    )

    try:
        adapter = ClaudeAdapter(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )
        logger.info("✓ Claude adapter created successfully")
        return adapter

    except ValueError as e:
        logger.error(f"Claude configuration error: {e}")
        logger.warning("Falling back to template adapter")
        logger.info("Set ANTHROPIC_API_KEY environment variable to use Claude")
        return TemplateLLMAdapter()

    except Exception as e:
        logger.error(f"Failed to create Claude adapter: {e}")
        logger.warning("Falling back to template adapter")
        return TemplateLLMAdapter()


def get_adapter_guardrails(config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get guardrails configuration for LLM proposals.

    Args:
        config_override: Override specific guardrail values

    Returns:
        Dict with guardrail settings (max_risk, banned_imports, etc.)
    """
    cfg = load_config()
    llm_config = cfg.get("llm", {})
    guardrails = llm_config.get("guardrails", {})

    # Apply overrides
    if config_override:
        guardrails.update(config_override)

    # Ensure required fields have defaults
    guardrails.setdefault("max_risk", "medium")
    guardrails.setdefault("banned_imports", [
        "os", "subprocess", "sys", "socket", "urllib", "requests", "http"
    ])
    guardrails.setdefault("allowed_modules", [
        "math", "statistics", "json", "datetime", "decimal", "fractions"
    ])
    guardrails.setdefault("required_tests", [
        "alignment", "security", "edge_cases"
    ])

    return guardrails


# Convenience function for common use case
def create_configured_adapter() -> tuple[BaseLLMAdapter, Dict[str, Any]]:
    """
    Create adapter and load guardrails from config in one call.

    Returns:
        Tuple of (adapter, guardrails_dict)

    Example:
        adapter, guardrails = create_configured_adapter()
        result = adapter.generate_improvement(
            prompt="...",
            specialization=SystemSpecialization.SCIENTIFIC,
            research_params={},
            guardrails=guardrails
        )
    """
    adapter = create_llm_adapter()
    guardrails = get_adapter_guardrails()

    logger.info(
        f"Created configured adapter: type={type(adapter).__name__}, "
        f"guardrails_max_risk={guardrails.get('max_risk')}"
    )

    return adapter, guardrails
