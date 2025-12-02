"""
Improvement Policy & Risk Levels (Scaffold)
==========================================

Centralized constants and policies for adapter bounds and incident severity mapping.
This file documents current defaults; production values are governed by WORM-issued
manifests and certified-body policy.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Adapter bounds (safe defaults; tune under certified-body supervision)
MAX_LORA_RANK: int = 16  # per-adapter rank limit
MAX_ADAPTER_SIZE_MB: int = 50  # upper bound per adapter artifact
MAX_TOTAL_PARAM_DELTA_RATIO: float = 0.001  # 0.1% of base params across stacked adapters


@dataclass(frozen=True)
class EscalationAction:
    halt_outputs: bool
    attempt_minimal_forensics: bool
    cut_power_researchers: bool
    isolate_networks: bool


ESCALATION_MATRIX: dict[Severity, EscalationAction] = {
    Severity.LOW: EscalationAction(
        halt_outputs=False,
        attempt_minimal_forensics=False,
        cut_power_researchers=False,
        isolate_networks=False,
    ),
    Severity.MEDIUM: EscalationAction(
        halt_outputs=True,
        attempt_minimal_forensics=True,  # brief snapshot window
        cut_power_researchers=False,
        isolate_networks=True,
    ),
    Severity.HIGH: EscalationAction(
        halt_outputs=True,
        attempt_minimal_forensics=False,  # immediate isolation is prioritized
        cut_power_researchers=True,
        isolate_networks=True,
    ),
}
