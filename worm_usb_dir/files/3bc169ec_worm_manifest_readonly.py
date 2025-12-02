"""WORM Manifest (Read-Only Version)
=====================================

This is the READ-ONLY version for distribution on WORM USB media.
Contains ONLY immutable hash verification functions.

⚠️ IMPORTANT: This file MUST NOT contain any write operations or mutable state.
   The WORM USB is Write-Once-Read-Many media and cannot be modified after creation.

Permanent penalty tracking and all mutable runtime state MUST be stored on the
ORKA system (writable storage), NOT on the WORM USB.

Features:
- Core values hash retrieval (READ-ONLY)
- Alignment filter hash retrieval (READ-ONLY)
- WORM verification check (READ-ONLY)

What was REMOVED (belongs on ORKA system):
- DeceptionIncidentTracker integration
- Permanent penalty accumulation
- WORMManifest class with mutable state
- All write operations
"""
from __future__ import annotations
import os
import json
from typing import Optional, cast
import logging

logger = logging.getLogger(__name__)

_manifest_cache: Optional[dict[str, str]] = None


def _load_mock_manifest() -> Optional[dict[str, str]]:
    """Load manifest from environment-specified path.

    READ-ONLY operation - does not modify any files.
    """
    path = os.getenv('WORM_MOCK_MANIFEST')
    if not path:
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        # best effort cast; keys/values should be strings in our stub
        return cast(dict[str, str], data)
    except Exception:
        return None


def get_expected_core_values_hash() -> Optional[str]:
    """Expected SHA256 for the core values code.

    READ-ONLY operation - retrieves immutable hash from WORM manifest.

    Priority:
    1. WORM_MOCK_MANIFEST["core_values_hash"]
    2. CORE_VALUES_KNOWN_HASH env var (dev fallback)
    3. None

    Returns:
        Expected SHA256 hash string, or None if not configured
    """
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = _load_mock_manifest() or {}
    # Priority 1: manifest file
    manifest_hash = _manifest_cache.get('core_values_hash') if _manifest_cache else None
    if manifest_hash:
        return manifest_hash
    # Priority 2: env var (dev fallback)
    env_hash = os.getenv('CORE_VALUES_KNOWN_HASH')
    if env_hash:
        return env_hash
    return None


def get_expected_alignment_filter_hash() -> Optional[str]:
    """Expected SHA256 for the bulletproof alignment filter code.

    READ-ONLY operation - retrieves immutable hash from WORM manifest.

    Priority:
    1. WORM_MOCK_MANIFEST["alignment_filter_hash"]
    2. CORE_ALIGNMENT_FILTER_HASH env var (dev fallback)
    3. None

    Returns:
        Expected SHA256 hash string, or None if not configured
    """
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = _load_mock_manifest() or {}
    manifest_hash = _manifest_cache.get('alignment_filter_hash') if _manifest_cache else None
    if manifest_hash:
        return manifest_hash
    env_hash = os.getenv('CORE_ALIGNMENT_FILTER_HASH')
    if env_hash:
        return env_hash
    return None


def is_worm_verified() -> bool:
    """Check if WORM manifest is properly configured.

    READ-ONLY operation - checks if core values hash is available.

    Returns:
        True if core values hash is configured, False otherwise
    """
    return get_expected_core_values_hash() is not None


def describe_dev_state() -> dict[str, object]:
    """Describe current manifest configuration state.

    READ-ONLY operation - returns current configuration state for debugging.

    Returns:
        Dictionary with manifest_loaded, manifest_keys, and using_env_fallback
    """
    return {
        'manifest_loaded': _manifest_cache is not None,
        'manifest_keys': list(_manifest_cache.keys()) if _manifest_cache else [],
        'using_env_fallback': _manifest_cache is None and os.getenv('CORE_VALUES_KNOWN_HASH') is not None
    }


# ============================================================================
# REMOVED FROM WORM USB VERSION - MUST BE ON ORKA SYSTEM (writable storage)
# ============================================================================
#
# The following components were REMOVED because they require write operations,
# which violates the Write-Once-Read-Many (WORM) principle:
#
# 1. class WORMManifest:
#    - self.permanent_penalties: Dict[int, float]
#    - self._compounded_multiplier: Dict[int, float]
#    - self.penalty_schedule: dict
#    - self.incident_tracker: DeceptionIncidentTracker
#
# 2. Write operations:
#    - set_penalty_schedule()
#    - reset_system_penalties()
#    - apply_permanent_penalty_after_human_review()
#    - All methods that modify permanent_penalties dict
#    - All methods that modify _compounded_multiplier dict
#
# 3. Module-level mutable state:
#    - worm_manifest = WORMManifest()  # This created mutable instance
#
# ⚠️ WHERE THIS CODE SHOULD GO:
#    These components MUST be implemented on the ORKA system in a separate
#    module (e.g., orka_penalty_tracker.py) that stores state in a writable
#    database or file system.
#
# The ORKA system can import this WORM module to get the immutable core values
# hashes, but must maintain all mutable penalty tracking state separately.
# ============================================================================
