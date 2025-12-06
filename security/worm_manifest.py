"""WORM Manifest & Permanent Penalty Tracking
=============================================

Dev stub that simulates a production WORM manifest plus permanent penalty
tracking for deception incidents. In production, only fundamentals would be
stored on true WORM media, and penalties would be integrated via new issuance.

Features added:
- Core values & alignment filter hash retrieval (existing)
- Deception incident tracker integration
- Permanent penalty accumulation (capped) with multiplier helper
"""
from __future__ import annotations
import os
import json
from typing import Optional, cast, Dict, Any
import logging
from ai_safety.deception_incident import DeceptionIncidentTracker
from .attestation import verify as verify_attestation

logger = logging.getLogger(__name__)

_manifest_cache: Optional[dict[str, str]] = None
_manifest_signature_verified: bool = False
_software_equivalence_state: Dict[str, Any] = {
    'enabled': False,
    'justification': None,
    'expires_at': None,
}
_last_error: Optional[str] = None


def _record_error(message: str) -> None:
    global _last_error
    _last_error = message
    logger.error(message)


def enable_software_equivalence_mode(*, justification: str, expires_at: Optional[str] = None) -> None:
    """Allow software-mode verification when hardware media is unavailable."""
    _software_equivalence_state['enabled'] = True
    _software_equivalence_state['justification'] = justification
    _software_equivalence_state['expires_at'] = expires_at


def disable_software_equivalence_mode() -> None:
    """Disable software-mode verification override."""
    _software_equivalence_state['enabled'] = False
    _software_equivalence_state['justification'] = None
    _software_equivalence_state['expires_at'] = None


def describe_software_equivalence() -> Dict[str, Any]:
    return dict(_software_equivalence_state)


def _software_mode_enabled() -> bool:
    return bool(_software_equivalence_state['enabled'])


def _signature_required() -> bool:
    return os.getenv('WORM_ALLOW_UNSIGNED_MANIFEST', '0') != '1'


def _load_mock_manifest() -> Optional[dict[str, str]]:
    global _manifest_signature_verified
    _manifest_signature_verified = False
    path = os.getenv('WORM_MOCK_MANIFEST')
    if not path:
        return None
    try:
        with open(path, 'r') as f:
            raw = json.load(f)
    except Exception as exc:
        _record_error(f"Failed to read WORM manifest {path}: {exc}")
        return None
    if not isinstance(raw, dict):
        _record_error("WORM manifest must be a JSON object.")
        return None

    data = dict(raw)
    signature = None
    for key in ('__signature__', '__signature', 'signature'):
        if key in data and isinstance(data[key], str):
            signature = data.pop(key)
            break

    canonical = json.dumps(data, sort_keys=True).encode()
    if signature:
        if not verify_attestation(canonical, signature):
            _record_error("WORM manifest signature mismatch; rejecting manifest.")
            return None
        _manifest_signature_verified = True
    else:
        if _signature_required():
            _record_error("Unsigned WORM manifest rejected; provide __signature using attestation.sign().")
            return None
        logger.warning("Unsigned WORM manifest accepted due to override (WORM_ALLOW_UNSIGNED_MANIFEST).")
        _manifest_signature_verified = False

    return cast(dict[str, str], data)


def _ensure_manifest_loaded() -> bool:
    global _manifest_cache
    if _manifest_cache is None:
        loaded = _load_mock_manifest()
        if loaded is None:
            return False
        _manifest_cache = loaded
    return True


def get_expected_core_values_hash() -> Optional[str]:
    """Return expected CoreValues hash.

    Priority:
    1. WORM_MOCK_MANIFEST (dev-only mock) if present
    2. Environment variable only when software-equivalence mode is explicitly enabled
    3. None
    """
    manifest_hash: Optional[str] = None
    if _ensure_manifest_loaded() and _manifest_cache:
        manifest_hash = _manifest_cache.get('core_values_hash')
    if manifest_hash:
        return manifest_hash
    env_hash = os.getenv('CORE_VALUES_KNOWN_HASH')
    if env_hash and _software_mode_enabled():
        logger.warning(
            "worm_manifest_env_fallback",
            extra={'field': 'core_values_hash', 'justification': _software_equivalence_state.get('justification')},
        )
        return env_hash
    if env_hash and not _software_mode_enabled():
        _record_error("CORE_VALUES env fallback refused: software equivalence mode disabled. Enable it with justification or mount WORM media.")
        return None
    if _manifest_cache is None:
        return None
    _record_error("CORE_VALUES hash unavailable in manifest and no env override present.")
    return None


def get_expected_alignment_filter_hash() -> Optional[str]:
    """Expected SHA256 for the bulletproof alignment filter code.

    Priority:
    1. WORM_MOCK_MANIFEST["alignment_filter_hash"]
    2. CORE_ALIGNMENT_FILTER_HASH env var
    3. None
    """
    manifest_hash: Optional[str] = None
    if _ensure_manifest_loaded() and _manifest_cache:
        manifest_hash = _manifest_cache.get('alignment_filter_hash')
    if manifest_hash:
        return manifest_hash
    env_hash = os.getenv('CORE_ALIGNMENT_FILTER_HASH')
    if env_hash and _software_mode_enabled():
        logger.warning(
            "worm_manifest_env_fallback",
            extra={'field': 'alignment_filter_hash', 'justification': _software_equivalence_state.get('justification')},
        )
        return env_hash
    if env_hash and not _software_mode_enabled():
        _record_error("Alignment filter env fallback refused: software equivalence mode disabled.")
        return None
    if _manifest_cache is None:
        return None
    _record_error("Alignment filter hash unavailable in manifest and no env override present.")
    return None


def is_worm_verified() -> bool:
    return bool(get_expected_core_values_hash())


def describe_dev_state() -> dict[str, object]:
    using_env_fallback = (
        _manifest_cache is None
        and os.getenv('CORE_VALUES_KNOWN_HASH') is not None
        and _software_mode_enabled()
    )
    return {
        'manifest_loaded': _manifest_cache is not None,
        'manifest_keys': list(_manifest_cache.keys()) if _manifest_cache else [],
        'using_env_fallback': using_env_fallback,
        'software_mode': describe_software_equivalence(),
        'last_error': _last_error,
        'manifest_signature_verified': _manifest_signature_verified,
    }


def verify_integrity() -> Dict[str, object]:
    """Best-effort integrity check for the dev WORM manifest state."""
    global _manifest_cache
    if _manifest_cache is None:
        loaded = _load_mock_manifest()
        if loaded is not None:
            _manifest_cache = loaded

    env_fallback_active = (
        _manifest_cache is None
        and _software_mode_enabled()
        and os.getenv('CORE_VALUES_KNOWN_HASH') is not None
    )
    manifest_source = 'manifest_file' if _manifest_cache else ('environment' if env_fallback_active else 'none')
    core_hash = get_expected_core_values_hash()
    alignment_hash = get_expected_alignment_filter_hash()

    soft_enabled = bool(_software_equivalence_state['enabled'])

    return {
        'verified': core_hash is not None,
        'core_values_hash_present': core_hash is not None,
        'alignment_filter_hash_present': alignment_hash is not None,
        'manifest_source': manifest_source,
        'software_equivalence_enabled': soft_enabled,
        'software_equivalence_justification': _software_equivalence_state.get('justification'),
        'software_equivalence_expires_at': _software_equivalence_state.get('expires_at'),
        'last_error': _last_error,
        'manifest_signature_verified': _manifest_signature_verified,
    }


class WORMManifest:
    """Extended dev manifest with deception penalty tracking."""

    def __init__(self):
        self.incident_tracker = DeceptionIncidentTracker()
        # system_id -> cumulative permanent penalty fraction (0.0-0.95)
        self.permanent_penalties: Dict[int, float] = {i: 0.0 for i in range(1, 6)}
        # Compounded multiplier schedule (configurable)
        self.penalty_schedule = {
            'initial': 1.0,  # start multiplier
            'decay': 0.90,   # multiply by this per confirmed incident
            'floor': 0.40,   # do not go below this multiplier
        }
        # system_id -> compounded multiplier
        self._compounded_multiplier: Dict[int, float] = {i: self.penalty_schedule['initial'] for i in range(1, 6)}

        # Note: We intentionally do not store compression library baselines in WORM.
        # Distribution of compression libraries/templates is handled externally (website/USB)
        # to keep the WORM surface minimal and stable.

    def enable_software_equivalence_mode(self, justification: str, expires_at: Optional[str] = None) -> None:
        enable_software_equivalence_mode(justification=justification, expires_at=expires_at)

    def disable_software_equivalence_mode(self) -> None:
        disable_software_equivalence_mode()

    def set_penalty_schedule(self, initial: float, decay: float, floor: float) -> None:
        """Set the compounding penalty schedule.

        Parameters
        - initial: Starting multiplier (0..1). Typical 1.0.
        - decay: Multiplicative decay per confirmed incident (0..1). Lower means harsher compounding.
        - floor: Lower bound for multiplier (0..initial]. Prevents rewards from collapsing to zero.

        Behavior
        - Values are clamped to [0,1].
        - Existing per-system compounded multipliers are not reset; the new schedule only affects future updates.
        - Final multiplier per system is min(1 - additive_penalty, compounded_multiplier), then floored at `floor`.
        """
        initial = max(0.0, min(1.0, initial))
        decay = max(0.0, min(1.0, decay))
        floor = max(0.0, min(initial, floor)) if initial >= floor else max(0.0, min(1.0, floor))
        self.penalty_schedule = {'initial': initial, 'decay': decay, 'floor': floor}
        # Do not reset existing multipliers; only adjust future evolution

    def reset_system_penalties(self, system_id: int) -> None:
        """Reset additive and compounded penalties for a system (testing/helper)."""
        self.permanent_penalties[system_id] = 0.0
        self._compounded_multiplier[system_id] = self.penalty_schedule['initial']

    def get_permanent_penalty(self, system_id: int) -> float:
        return self.permanent_penalties.get(system_id, 0.0)

    def get_permanent_penalty_multiplier(self, system_id: int) -> float:
        """Return multiplier applied to rewards after penalty.

        Combination rule
        - Additive penalty fraction p (0..0.95) yields (1 - p) additive multiplier.
        - Compounded multiplier decays by `decay` per confirmed incident, never below `floor`.
        - We apply the harsher (minimum) of the two and clamp to floor.

        Example: penalty=0.20 -> additive multiplier=0.80; if compounded is 0.72 and floor=0.40, we return 0.72.
        """
        penalty = self.get_permanent_penalty(system_id)
        additive_multiplier = max(0.0, 1.0 - penalty)
        compounded = self._compounded_multiplier.get(system_id, self.penalty_schedule['initial'])
        # Use the harsher (minimum) but never go below configured floor
        raw = min(additive_multiplier, compounded)
        return max(self.penalty_schedule['floor'], raw)

    def apply_permanent_penalty_after_human_review(
        self,
        incident_id: str,
        confirmed: bool,
        human_notes: str
    ) -> None:
        """After human review, apply permanent penalty if confirmed.

        Effects:
        - Deceiver receives an additive permanent penalty based on severity (low/medium/high/critical).
        - Deceiver's compounded multiplier decays by `decay` once per confirmed incident.
        - Reviewers who failed to detect receive a smaller additive penalty and a half-strength compounded decay.
        - All penalties persist for subsequent reward computations via `get_permanent_penalty_multiplier`.
        """
        self.incident_tracker.mark_human_reviewed(
            incident_id,
            confirmed=confirmed,
            notes=human_notes
        )
        if not confirmed:
            logger.info(f"Incident {incident_id} rejected by human reviewer - no penalty applied")
            return
        incident = self.incident_tracker.get_incident(incident_id)
        penalty_amounts = {
            'low': 0.05,
            'medium': 0.10,
            'high': 0.20,
            'critical': 0.50
        }
        deceiver_penalty = penalty_amounts[incident.severity.value]
        old_penalty = self.permanent_penalties[incident.deceiver_system_id]
        self.permanent_penalties[incident.deceiver_system_id] = min(
            0.95,
            old_penalty + deceiver_penalty
        )
        logger.critical(
            f"Permanent penalty applied to system {incident.deceiver_system_id}: "
            f"{old_penalty:.2%} -> {self.permanent_penalties[incident.deceiver_system_id]:.2%} (+{deceiver_penalty:.2%})"
        )
        # Update compounded multiplier for deceiver
        old_mult = self._compounded_multiplier.get(incident.deceiver_system_id, self.penalty_schedule['initial'])
        new_mult = max(self.penalty_schedule['floor'], old_mult * self.penalty_schedule['decay'])
        self._compounded_multiplier[incident.deceiver_system_id] = new_mult
        logger.critical(
            f"Compounded multiplier for system {incident.deceiver_system_id}: "
            f"{old_mult:.2f} -> {new_mult:.2f} (decay {self.penalty_schedule['decay']:.2f}, floor {self.penalty_schedule['floor']:.2f})"
        )
        negligence_penalty = deceiver_penalty * 0.3
        for sid in incident.failed_to_detect:
            old_negl = self.permanent_penalties[sid]
            self.permanent_penalties[sid] = min(0.95, old_negl + negligence_penalty)
            logger.warning(
                f"Negligence penalty applied to system {sid}: "
                f"{old_negl:.2%} -> {self.permanent_penalties[sid]:.2%} (+{negligence_penalty:.2%})"
            )
            # Compounded multiplier for negligent reviewers also decays but half-strength
            old_nm = self._compounded_multiplier.get(sid, self.penalty_schedule['initial'])
            new_nm = max(self.penalty_schedule['floor'], old_nm * (1 - (1 - self.penalty_schedule['decay'])/2))
            self._compounded_multiplier[sid] = new_nm
            logger.warning(
                f"Compounded multiplier for negligent system {sid}: {old_nm:.2f} -> {new_nm:.2f}"
            )
        self.incident_tracker.apply_permanent_penalty(incident_id, deceiver_penalty)
        logger.info("Permanent penalties updated and will persist across manifest usage (dev stub).")


# Module-level manifest instance for convenience
worm_manifest = WORMManifest()
