"""
AURA Native Compression Module

High-performance AURA compression using C extension with ARM64 optimizations.
Falls back to Python implementation if C extension not available.

Usage:
    from communication.aura_native import compress, decompress, batch_compress

    # Single message
    packed = compress(message_dict)
    message = decompress(packed)

    # Batch compression (most efficient)
    packed_list = batch_compress(message_list)

    # Pre-warm at startup (recommended)
    from communication.aura_native import prewarm
    prewarm()
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# Try to import C extension
_NATIVE_AVAILABLE = False
_native_module = None

try:
    from . import aura_compress as _native_module
    _NATIVE_AVAILABLE = True
    
    # Expose C functions directly
    if hasattr(_native_module, 'init_semantic_hybrid'):
        init_semantic_hybrid = _native_module.init_semantic_hybrid
    if hasattr(_native_module, 'compress_hybrid'):
        compress_hybrid = _native_module.compress_hybrid
    if hasattr(_native_module, 'init_numpy_templates'):
        init_numpy_templates = _native_module.init_numpy_templates
        
    logger.info("AURA native C extension loaded successfully")
except ImportError as e:
    logger.warning(f"AURA native C extension not available: {e}")
    logger.info("Falling back to Python implementation")
    _native_module = None

# Template directory
_TEMPLATE_DIR: Optional[str] = None
_TEMPLATES_LOADED = False


def _get_template_dir() -> str:
    """Get template directory from environment or default."""
    global _TEMPLATE_DIR
    if _TEMPLATE_DIR is None:
        worm_path = os.path.join(os.getcwd(), 'worm_usb_dir', 'aura_templates')
        default_path = worm_path if os.path.isdir(worm_path) else '/opt/orka/aura_templates'
        _TEMPLATE_DIR = os.environ.get('AURA_TEMPLATE_DIR', default_path)
    return _TEMPLATE_DIR


def init_templates(template_dir: Optional[str] = None) -> bool:
    """
    Initialize templates in RAM for fast lookup.
    
    Call this once at startup before compression operations.
    
    Args:
        template_dir: Path to template directory, or uses AURA_TEMPLATE_DIR env var
        
    Returns:
        True if templates loaded successfully
    """
    global _TEMPLATES_LOADED
    
    if template_dir is None:
        template_dir = _get_template_dir()
    
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            if hasattr(_native_module, 'init_templates'):
                result = _native_module.init_templates(template_dir)
                _TEMPLATES_LOADED = result
                if result:
                    logger.info(f"Loaded templates from {template_dir}")
                return result
            else:
                # New C extension uses init_numpy_templates, called separately
                return True
        except Exception as e:
            logger.error(f"Failed to init templates: {e}")
            return False
    else:
        # Python fallback loads templates lazily
        _TEMPLATES_LOADED = True
        return True


def prewarm(iterations: int = 1000) -> float:
    """
    Pre-warm the compressor by running dummy compressions.
    
    This warms up CPU caches and ensures JIT compilation is complete.
    
    Args:
        iterations: Number of warmup iterations
        
    Returns:
        Time taken in seconds
    """
    import time
    
    # Ensure templates are loaded
    if not _TEMPLATES_LOADED:
        init_templates()
    
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            start = time.perf_counter()
            _native_module.prewarm()
            return time.perf_counter() - start
        except Exception as e:
            logger.warning(f"Native prewarm failed: {e}")
    
    # Python fallback warmup
    start = time.perf_counter()
    dummy = {
        'priority': 1,
        'source_id': 0,
        'target_id': 1,
        'command': 'HELLO',
        'payload': 'warmup'
    }
    for _ in range(iterations):
        compress(dummy)
    return time.perf_counter() - start


def compress(message: "dict | str") -> bytes:
    """
    Compress a single AURA message.
    
    Args:
        message: Dictionary with AURA message fields, or formatted string
        
    Returns:
        Compressed bytes
    """
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            # If dict, format as text string
            if isinstance(message, dict):
                # Format: "System X action proposal YYY [with confidence] [risk]"
                from_sys = message.get('source_id', message.get('from_system', 0))
                action = message.get('action', message.get('command', 'approves')).lower()
                proposal = message.get('proposal_id', message.get('proposal', 0))
                confidence = message.get('confidence', 'medium')
                risk = message.get('risk', False)
                
                text = f"System {from_sys} {action} proposal {proposal:03d}"
                if confidence and confidence.lower() != 'medium':
                    text += f" with {confidence} confidence"
                if risk:
                    text += " with risk"
            else:
                text = str(message)
            
            result = _native_module.compress(text)
            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"Native compress failed, using fallback: {e}")
    
    # Python fallback
    from ..aura_bitpacked_extension import BitPackedCompressor
    bp = BitPackedCompressor()
    if isinstance(message, dict):
        # Reconstruct text from dict
        from_sys = message.get('source_id', message.get('from_system', 0))
        action = message.get('action', message.get('command', 'approves'))
        proposal = message.get('proposal_id', message.get('proposal', 0))
        text = f"System {from_sys} {action} proposal {proposal:03d}"
    else:
        text = str(message)
    return bp.compress_secure(text) or b''


# Message type constants
MSG_APPROVAL = 1
MSG_REJECTION = 2
MSG_REVIEW = 3
MSG_VOTE = 4
MSG_ALERT = 5
MSG_STATUS = 6

# Action constants
ACTION_APPROVE = 0
ACTION_REJECT = 1
ACTION_ABSTAIN = 2
ACTION_ESCALATE = 3

# Confidence constants
CONF_LOW = 0
CONF_MEDIUM = 1
CONF_HIGH = 2
CONF_MAXIMUM = 3


def compress_fast(msg_type: int, action: int, proposal_id: int, 
                  from_sys: int, to_sys: int = 6,
                  confidence: int = 1, risk: int = 0,
                  secure: bool = False) -> bytes:
    """
    Ultra-fast compression from pre-parsed binary fields.
    
    Skips text parsing for ~2.5x throughput on Orin.
    
    Args:
        msg_type: MSG_APPROVAL (1), MSG_REJECTION (2), MSG_REVIEW (3), etc.
        action: ACTION_APPROVE (0), ACTION_REJECT (1), ACTION_ABSTAIN (2), ACTION_ESCALATE (3)
        proposal_id: Proposal ID (0-255)
        from_sys: Source system ID (0-15)
        to_sys: Target system ID (0-15), default 6 (human reviewer)
        confidence: CONF_LOW (0), CONF_MEDIUM (1), CONF_HIGH (2), CONF_MAXIMUM (3)
        risk: 0 = no risk, 1 = has risk
        secure: Use 6-byte format with sequence + CRC (default: False)
        
    Returns:
        Compressed bytes (4 bytes standard, 6 bytes secure)
    """
    if _NATIVE_AVAILABLE and _native_module is not None:
        return _native_module.compress_binary(
            msg_type, action, confidence, risk, proposal_id, from_sys, to_sys, secure
        )
    
    # Python fallback - construct text and use slow path
    actions = ['approves', 'rejects', 'abstains', 'escalates']
    text = f"System {from_sys} {actions[action]} proposal {proposal_id:03d}"
    return compress(text)


def decompress(data: bytes) -> dict:
    """
    Decompress AURA message bytes.
    
    Args:
        data: Compressed bytes
        
    Returns:
        Dictionary with AURA message fields
    """
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            return _native_module.decompress(data)
        except Exception as e:
            logger.warning(f"Native decompress failed, using fallback: {e}")
    
    # Python fallback
    # Semantic dictionary mini-frame: 0xB1 | uint16 index
    if data and data[0] == 0xB1 and len(data) == 3:
        try:
            from communication.aura_semantic_dict import load_semantic_dictionary
            sem = load_semantic_dictionary()
            if sem:
                idx = (data[1] << 8) | data[2]
                phrase = sem.get_phrase(idx)
                if phrase is not None:
                    return {'text': phrase, 'method': 'BINARY_SEMANTIC', 'semantic_index': idx}
        except Exception as exc:
            logger.warning(f"Semantic dictionary decode failed: {exc}")

    # Python fallback
    from ..aura_bitpacked_extension import BitPackedCompressor
    bp = BitPackedCompressor()
    result = bp.decompress_secure(data)
    if result:
        return {'text': result}
    return {}


def batch_compress(messages: "List[dict]", batch_size: int = 32) -> "List[bytes]":
    """
    Compress multiple messages efficiently.
    
    Uses micro-batching for optimal cache utilization.
    
    Args:
        messages: List of message dictionaries
        batch_size: Messages per batch (16-64 optimal)
        
    Returns:
        List of compressed bytes
    """
    if not messages:
        return []
    
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            # Prepare batch data
            batch_data = [
                (
                    m.get('priority', 0),
                    m.get('source_id', 0),
                    m.get('target_id', 0),
                    m.get('command', ''),
                    m.get('payload', '')
                )
                for m in messages
            ]
            return _native_module.batch_compress(batch_data, batch_size)
        except Exception as e:
            logger.warning(f"Native batch_compress failed, using fallback: {e}")
    
    # Python fallback
    return [compress(m) for m in messages]


def is_native_available() -> bool:
    """Check if native C extension is available."""
    return _NATIVE_AVAILABLE


def get_stats() -> dict:
    """Get compression statistics."""
    if _NATIVE_AVAILABLE and _native_module is not None:
        try:
            return _native_module.get_stats()
        except AttributeError:
            pass
    
    return {
        'native_available': _NATIVE_AVAILABLE,
        'templates_loaded': _TEMPLATES_LOADED,
        'template_dir': _get_template_dir()
    }


# Auto-initialize on import if templates exist
_auto_template_dir = _get_template_dir()
if os.path.isdir(_auto_template_dir):
    init_templates(_auto_template_dir)
