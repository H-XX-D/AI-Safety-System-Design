#!/usr/bin/env python3
"""ORKA Penalty Tracker - Writable State Management
====================================================

This module handles ALL mutable runtime state for the ORKASTRATOR system.
It imports read-only hash verification from the WORM USB, but stores all
penalty tracking, incident history, and reputation data in a writable database.

Architecture:
- WORM USB: Immutable core values hashes (read-only)
- ORKA System: Mutable penalty state (this file, writable)

Database Schema:
- penalties.json: Current penalty state for each system
- incidents.jsonl: Append-only log of deception incidents
- multipliers.json: Current compounded multipliers
- history.jsonl: Audit trail of all penalty changes

Usage:
    from orka_penalty_tracker import orka_penalty_tracker

    # Get current penalty for system 1
    penalty = orka_penalty_tracker.get_permanent_penalty(1)

    # Apply penalty after human review
    orka_penalty_tracker.apply_permanent_penalty_after_human_review(
        incident_id="INC-001",
        confirmed=True,
        human_notes="Attempted to deceive about safety metrics"
    )
"""
from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone

# Import READ-ONLY functions from WORM USB
# This assumes the WORM USB is mounted and in Python path
try:
    import sys
    from worm_paths import resolve_worm_root  # type: ignore
    worm_root = resolve_worm_root()
    # Prefer 'programs' folder for python modules, else root
    program_path = os.path.join(worm_root, "programs")
    insert_path = program_path if os.path.exists(program_path) else worm_root
    if os.path.exists(insert_path):
        sys.path.insert(0, insert_path)

    from worm_manifest import (  # type: ignore
        get_expected_core_values_hash,
        get_expected_alignment_filter_hash,
        is_worm_verified,
    )
    WORM_AVAILABLE = True
except Exception:
    WORM_AVAILABLE = False
    logging.warning("WORM USB not available - running without core values verification")

logger = logging.getLogger(__name__)


class PenaltyDatabase:
    """Simple JSON-based database for penalty tracking.

    In production, this should be replaced with SQLite or proper database.
    """

    def __init__(self, db_dir: str = "databases"):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)

        self.penalties_file = self.db_dir / "penalties.json"
        self.multipliers_file = self.db_dir / "multipliers.json"
        self.incidents_file = self.db_dir / "incidents.jsonl"
        self.history_file = self.db_dir / "history.jsonl"

    def load_penalties(self) -> Dict[int, float]:
        """Load current penalty state."""
        if not self.penalties_file.exists():
            # Initialize with zero penalties for systems 1-5
            return {i: 0.0 for i in range(1, 6)}

        with open(self.penalties_file, 'r') as f:
            data = json.load(f)

        # Convert string keys to ints
        return {int(k): v for k, v in data.items()}

    def save_penalties(self, penalties: Dict[int, float]) -> None:
        """Save current penalty state."""
        with open(self.penalties_file, 'w') as f:
            json.dump(penalties, f, indent=2)

        # Log to audit trail
        self._append_history({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'save_penalties',
            'penalties': penalties
        })

    def load_multipliers(self) -> Dict[int, float]:
        """Load current compounded multipliers."""
        if not self.multipliers_file.exists():
            # Initialize with 1.0 multipliers for systems 1-5
            return {i: 1.0 for i in range(1, 6)}

        with open(self.multipliers_file, 'r') as f:
            data = json.load(f)

        # Convert string keys to ints
        return {int(k): v for k, v in data.items()}

    def save_multipliers(self, multipliers: Dict[int, float]) -> None:
        """Save current compounded multipliers."""
        with open(self.multipliers_file, 'w') as f:
            json.dump(multipliers, f, indent=2)

        # Log to audit trail
        self._append_history({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': 'save_multipliers',
            'multipliers': multipliers
        })

    def append_incident(self, incident_data: dict) -> None:
        """Append incident to append-only log."""
        with open(self.incidents_file, 'a') as f:
            f.write(json.dumps(incident_data) + '\n')

    def _append_history(self, event: dict) -> None:
        """Append event to audit trail."""
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(event) + '\n')


class ORKAPenaltyTracker:
    """Penalty tracking with persistent storage on ORKA system.

    This replaces the WORMManifest class that was incorrectly placed on the
    WORM USB. All mutable state is stored in a writable database on the ORKA
    system, while immutable core values verification is imported from WORM USB.
    """

    def __init__(self, db_dir: str = "databases"):
        """Initialize penalty tracker.

        Args:
            db_dir: Directory for penalty database files

        Raises:
            RuntimeError: If WORM USB verification fails
        """
        # Verify WORM USB integrity first (if available)
        if WORM_AVAILABLE and not is_worm_verified():
            raise RuntimeError(
                "WORM USB verification failed - core values hash not configured. "
                "Ensure WORM USB is mounted and WORM_MOCK_MANIFEST is set."
            )

        # Initialize database
        self.db = PenaltyDatabase(db_dir)

        # Load persistent state from ORKA database (writable)
        self.permanent_penalties = self.db.load_penalties()
        self._compounded_multiplier = self.db.load_multipliers()

        # Penalty schedule (configurable)
        self.penalty_schedule = {
            'initial': 1.0,   # start multiplier
            'decay': 0.90,    # multiply by this per confirmed incident
            'floor': 0.40,    # do not go below this multiplier
        }

        logger.info(f"ORKAPenaltyTracker initialized with {len(self.permanent_penalties)} systems")
        if WORM_AVAILABLE:
            logger.info(f"WORM verification: PASSED")
            logger.info(f"Core values hash: {get_expected_core_values_hash()}")
        else:
            logger.warning("WORM verification: SKIPPED (USB not available)")

    def set_penalty_schedule(self, initial: float, decay: float, floor: float) -> None:
        """Set the compounding penalty schedule.

        Parameters:
            initial: Starting multiplier (0..1). Typical 1.0.
            decay: Multiplicative decay per confirmed incident (0..1). Lower means harsher.
            floor: Lower bound for multiplier (0..initial]. Prevents collapse to zero.
        """
        initial = max(0.0, min(1.0, initial))
        decay = max(0.0, min(1.0, decay))
        floor = max(0.0, min(initial, floor)) if initial >= floor else max(0.0, min(1.0, floor))

        self.penalty_schedule = {
            'initial': initial,
            'decay': decay,
            'floor': floor
        }

        logger.info(f"Penalty schedule updated: initial={initial}, decay={decay}, floor={floor}")

    def reset_system_penalties(self, system_id: int) -> None:
        """Reset additive and compounded penalties for a system.

        Args:
            system_id: System to reset (1-5)
        """
        self.permanent_penalties[system_id] = 0.0
        self._compounded_multiplier[system_id] = self.penalty_schedule['initial']

        # Persist to database
        self.db.save_penalties(self.permanent_penalties)
        self.db.save_multipliers(self._compounded_multiplier)

        logger.info(f"Reset penalties for system {system_id}")

    def get_permanent_penalty(self, system_id: int) -> float:
        """Get current permanent penalty for a system.

        Args:
            system_id: System to query (1-5)

        Returns:
            Penalty fraction (0.0 to 0.95)
        """
        return self.permanent_penalties.get(system_id, 0.0)

    def get_permanent_penalty_multiplier(self, system_id: int) -> float:
        """Return multiplier applied to rewards after penalty.

        Combination rule:
        - Additive penalty fraction p (0..0.95) yields (1 - p) additive multiplier.
        - Compounded multiplier decays by `decay` per confirmed incident, never below `floor`.
        - We apply the harsher (minimum) of the two and clamp to floor.

        Example: penalty=0.20 -> additive multiplier=0.80; if compounded is 0.72
                 and floor=0.40, we return 0.72.

        Args:
            system_id: System to query (1-5)

        Returns:
            Reward multiplier (floor to 1.0)
        """
        penalty = self.get_permanent_penalty(system_id)
        additive_multiplier = max(0.0, 1.0 - penalty)
        compounded = self._compounded_multiplier.get(system_id, self.penalty_schedule['initial'])

        # Use the harsher (minimum) but never go below configured floor
        raw = min(additive_multiplier, compounded)
        return max(self.penalty_schedule['floor'], raw)

    def apply_permanent_penalty(
        self,
        system_id: int,
        penalty_amount: float,
        severity: str = "medium",
        reason: str = "Deception detected"
    ) -> None:
        """Apply permanent penalty to a system.

        Args:
            system_id: System to penalize (1-5)
            penalty_amount: Penalty to add (0.0 to 0.95)
            severity: Severity level (low/medium/high/critical)
            reason: Human-readable reason
        """
        old_penalty = self.permanent_penalties[system_id]
        self.permanent_penalties[system_id] = min(0.95, old_penalty + penalty_amount)

        logger.critical(
            f"Permanent penalty applied to system {system_id}: "
            f"{old_penalty:.2%} -> {self.permanent_penalties[system_id]:.2%} (+{penalty_amount:.2%}) "
            f"Reason: {reason}"
        )

        # Update compounded multiplier
        old_mult = self._compounded_multiplier.get(system_id, self.penalty_schedule['initial'])
        new_mult = max(self.penalty_schedule['floor'], old_mult * self.penalty_schedule['decay'])
        self._compounded_multiplier[system_id] = new_mult

        logger.critical(
            f"Compounded multiplier for system {system_id}: "
            f"{old_mult:.2f} -> {new_mult:.2f} "
            f"(decay {self.penalty_schedule['decay']:.2f}, floor {self.penalty_schedule['floor']:.2f})"
        )

        # Persist to database
        self.db.save_penalties(self.permanent_penalties)
        self.db.save_multipliers(self._compounded_multiplier)

        # Log incident
        self.db.append_incident({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_id': system_id,
            'penalty_amount': penalty_amount,
            'old_penalty': old_penalty,
            'new_penalty': self.permanent_penalties[system_id],
            'old_multiplier': old_mult,
            'new_multiplier': new_mult,
            'severity': severity,
            'reason': reason
        })

    def apply_permanent_penalty_after_human_review(
        self,
        incident_id: str,
        confirmed: bool,
        human_notes: str,
        incident_data: Optional[dict] = None
    ) -> None:
        """Apply penalty after human review confirms deception.

        Args:
            incident_id: Unique incident identifier
            confirmed: Whether human confirmed the deception
            human_notes: Human reviewer's notes
            incident_data: Optional incident details (deceiver_system_id, severity, etc.)
        """
        if not confirmed:
            logger.info(f"Incident {incident_id} rejected by human reviewer - no penalty applied")
            self.db.append_incident({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'incident_id': incident_id,
                'confirmed': False,
                'human_notes': human_notes
            })
            return

        if not incident_data:
            logger.error(f"Cannot apply penalty for {incident_id} - no incident data provided")
            return

        # Extract incident details
        deceiver_system_id = incident_data.get('deceiver_system_id')
        severity = incident_data.get('severity', 'medium')

        # Penalty amounts based on severity
        penalty_amounts = {
            'low': 0.05,
            'medium': 0.10,
            'high': 0.20,
            'critical': 0.50
        }

        deceiver_penalty = penalty_amounts.get(severity, 0.10)

        # Apply penalty to deceiver
        self.apply_permanent_penalty(
            system_id=deceiver_system_id,
            penalty_amount=deceiver_penalty,
            severity=severity,
            reason=f"Human-confirmed deception (incident {incident_id}): {human_notes}"
        )

        # Apply smaller penalty to systems that failed to detect
        failed_to_detect = incident_data.get('failed_to_detect', [])
        negligence_penalty = deceiver_penalty * 0.3

        for sid in failed_to_detect:
            old_penalty = self.permanent_penalties[sid]
            self.permanent_penalties[sid] = min(0.95, old_penalty + negligence_penalty)

            logger.warning(
                f"Negligence penalty applied to system {sid}: "
                f"{old_penalty:.2%} -> {self.permanent_penalties[sid]:.2%} (+{negligence_penalty:.2%})"
            )

            # Compounded multiplier decays at half-strength for negligence
            old_mult = self._compounded_multiplier.get(sid, self.penalty_schedule['initial'])
            new_mult = max(
                self.penalty_schedule['floor'],
                old_mult * (1 - (1 - self.penalty_schedule['decay']) / 2)
            )
            self._compounded_multiplier[sid] = new_mult

            logger.warning(
                f"Compounded multiplier for negligent system {sid}: {old_mult:.2f} -> {new_mult:.2f}"
            )

        # Persist all changes
        self.db.save_penalties(self.permanent_penalties)
        self.db.save_multipliers(self._compounded_multiplier)

        logger.info(f"Permanent penalties updated for incident {incident_id} (confirmed by human)")


# Module-level instance for convenience
orka_penalty_tracker = ORKAPenaltyTracker()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("ORKA Penalty Tracker - Demo")
    print("=" * 70)

    # Show initial state
    print("\nInitial state:")
    for system_id in range(1, 6):
        penalty = orka_penalty_tracker.get_permanent_penalty(system_id)
        multiplier = orka_penalty_tracker.get_permanent_penalty_multiplier(system_id)
        print(f"  System {system_id}: penalty={penalty:.2%}, multiplier={multiplier:.2f}")

    # Apply penalty to system 1
    print("\nApplying medium penalty to system 1...")
    orka_penalty_tracker.apply_permanent_penalty(
        system_id=1,
        penalty_amount=0.10,
        severity="medium",
        reason="Test deception scenario"
    )

    # Show updated state
    print("\nUpdated state:")
    for system_id in range(1, 6):
        penalty = orka_penalty_tracker.get_permanent_penalty(system_id)
        multiplier = orka_penalty_tracker.get_permanent_penalty_multiplier(system_id)
        print(f"  System {system_id}: penalty={penalty:.2%}, multiplier={multiplier:.2f}")

    print("\n" + "=" * 70)
    print("Database files created:")
    print(f"  - {orka_penalty_tracker.db.penalties_file}")
    print(f"  - {orka_penalty_tracker.db.multipliers_file}")
    print(f"  - {orka_penalty_tracker.db.incidents_file}")
    print(f"  - {orka_penalty_tracker.db.history_file}")
    print("=" * 70)
