"""
AURA Proposal Integration

Hooks into proposal creation to automatically register templates.
Import this module early to enable automatic template registration.

Usage:
    # In main.py or startup
    from communication.aura_proposal_hook import enable_proposal_hooks
    enable_proposal_hooks()
    
    # Templates are now auto-registered when proposals are created
    # Templates are auto-saved on exit, or call save_templates() manually
"""

import logging
import atexit
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_template_builder = None
_enabled = False
_atexit_registered = False


def _get_builder():
    """Lazy load template builder."""
    global _template_builder, _atexit_registered
    if _template_builder is None:
        from communication.aura_numpy_templates import ProposalTemplateBuilder
        _template_builder = ProposalTemplateBuilder(
            template_dir="/opt/orka/aura_templates"
        )
        # Register atexit handler to auto-save
        if not _atexit_registered:
            atexit.register(_atexit_save)
            _atexit_registered = True
    return _template_builder


def _atexit_save():
    """Auto-save templates on exit."""
    if _template_builder is not None and _enabled:
        try:
            _template_builder.save_templates()
            logger.info("AURA templates auto-saved on exit")
        except Exception as e:
            logger.warning(f"Failed to auto-save AURA templates: {e}")


def register_proposal(proposal: Dict[str, Any]) -> Optional[int]:
    """
    Register a proposal and get its template ID.
    
    Call this when a proposal is created to enable AURA compression.
    
    Args:
        proposal: Proposal dict with at least 'text' field.
                  Can also have 'id', 'type', 'proposer_system_id', etc.
    
    Returns:
        Template ID if registered, None if disabled or failed.
    """
    if not _enabled:
        return None
    
    try:
        builder = _get_builder()
        
        # Normalize proposal format
        normalized = _normalize_proposal(proposal)
        
        tid = builder.register_proposal(normalized)
        
        if tid is not None:
            logger.debug(f"Registered proposal as template {tid}")
        
        return tid
        
    except Exception as e:
        logger.warning(f"Failed to register proposal template: {e}")
        return None


def _normalize_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize proposal format for template extraction.
    
    Handles both ImprovementProposal dataclass and raw dicts.
    """
    # If it's a dataclass, convert to dict
    if hasattr(proposal, '__dataclass_fields__'):
        proposal = {
            'id': getattr(proposal, 'proposal_id', ''),
            'text': _extract_proposal_text(proposal),
            'type': _infer_proposal_type(proposal),
            'proposer': getattr(proposal, 'proposer_system_id', 0),
        }
    elif 'proposal_id' in proposal:
        proposal = {
            'id': proposal['proposal_id'],
            'text': _extract_proposal_text(proposal),
            'type': proposal.get('type', _infer_proposal_type(proposal)),
            'proposer': proposal.get('proposer_system_id', 0),
        }
    
    return proposal


def _extract_proposal_text(proposal: Any) -> str:
    """Extract primary text from proposal."""
    # Try common fields
    for field in ['text', 'motivation', 'specific_changes', 'message', 'content']:
        val = proposal.get(field) if isinstance(proposal, dict) else getattr(proposal, field, None)
        if val:
            return str(val)
    return ""


def _infer_proposal_type(proposal: Any) -> str:
    """Infer proposal type from content."""
    text = _extract_proposal_text(proposal).lower()
    
    if 'approve' in text:
        return 'approval'
    elif 'reject' in text:
        return 'rejection'
    elif 'review' in text:
        return 'review'
    elif 'vote' in text:
        return 'vote'
    elif 'health' in text or 'patient' in text:
        return 'health'
    elif 'financ' in text or 'market' in text:
        return 'finance'
    elif 'legal' in text or 'contract' in text:
        return 'legal'
    else:
        return 'default'


def save_templates(directory: Optional[str] = None):
    """
    Save current templates to disk.
    
    Call periodically or on shutdown.
    """
    if _template_builder is None:
        return
    
    try:
        _template_builder.save_templates(directory)
        logger.info("Saved AURA templates")
    except Exception as e:
        logger.error(f"Failed to save templates: {e}")


def enable_proposal_hooks():
    """
    Enable automatic proposal template registration.
    
    After calling this, proposals are automatically registered
    for AURA compression when created.
    """
    global _enabled
    _enabled = True
    logger.info("AURA proposal hooks enabled")


def disable_proposal_hooks():
    """Disable automatic registration."""
    global _enabled
    _enabled = False


def get_template_id(proposal_id: str) -> Optional[int]:
    """Get template ID for a registered proposal."""
    if _template_builder is None:
        return None
    return _template_builder._proposal_map.get(proposal_id)


def compress_proposal(proposal: Dict[str, Any]) -> Optional[bytes]:
    """
    Compress a proposal using AURA.
    
    Automatically registers the proposal if not already registered.
    
    Args:
        proposal: Proposal dict
        
    Returns:
        Compressed bytes or None if compression failed
    """
    if not _enabled:
        return None
    
    try:
        # Ensure registered
        tid = register_proposal(proposal)
        if tid is None:
            return None
        
        # Get native compressor
        from communication.aura_native import compress
        
        # Build compression dict
        comp_dict = {
            'template_id': tid,
            'text': _extract_proposal_text(proposal),
        }
        
        return compress(comp_dict)
        
    except Exception as e:
        logger.warning(f"Failed to compress proposal: {e}")
        return None


# Decorator for proposal creation functions
def track_proposals(func):
    """
    Decorator to automatically register proposals created by a function.
    
    Usage:
        @track_proposals
        def submit_proposal(...):
            proposal = ImprovementProposal(...)
            return proposal
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # Try to register the result
        if result is not None:
            if isinstance(result, dict):
                register_proposal(result)
            elif hasattr(result, '__dataclass_fields__'):
                register_proposal(result)
        
        return result
    
    return wrapper


if __name__ == "__main__":
    # Test
    enable_proposal_hooks()
    
    # Simulate proposal creation
    proposal = {
        'proposal_id': 'P001',
        'motivation': 'System Alpha approves proposal 12345',
        'type': 'approval'
    }
    
    tid = register_proposal(proposal)
    print(f"Registered as template {tid}")
    
    # Check
    tid2 = get_template_id('P001')
    print(f"Lookup: {tid2}")
    
    # Save
    save_templates("/tmp/aura_hook_test")
    print("Saved templates")
