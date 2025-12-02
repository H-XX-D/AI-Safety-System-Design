"""
Seventh Validator
=================

A lightweight validator that performs structural checks on improvement proposals
or proposal-like dictionaries prior to human review. This represents the 7th
independent validation layer requested.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, cast


@dataclass
class ValidationOutcome:
    validator_id: int
    passed: bool
    reasons: List[str]
    severity: str  # 'info' | 'warning' | 'critical'


class SeventhValidator:
    """Simple structural & risk coverage validator.

    Rules (all must pass for success):
    - motivation length >= 20
    - expected_benefits not empty
    - identified_risks has at least 2 entries
    - admitted_uncertainties has at least 1 entry
    - rollback_plan length >= 10
    - confidence_level between 0 and 1 inclusive
    """

    VALIDATOR_ID = 7

    def validate(self, proposal: Dict[str, Any]) -> ValidationOutcome:
        reasons: List[str] = []
        ok = True

        motivation = str(proposal.get('motivation', proposal.get('title', '')))
        if len(motivation) < 20:
            ok = False
            reasons.append('motivation_too_short')

        expected = str(proposal.get('expected_benefits', ''))
        if not expected.strip():
            ok = False
            reasons.append('expected_benefits_missing')

        risks_list = proposal.get('identified_risks', [])
        if not isinstance(risks_list, list) or len(cast(List[Any], risks_list)) < 2:
            ok = False
            reasons.append('insufficient_risks')

        uncertainties_list = proposal.get('admitted_uncertainties', [])
        if not isinstance(uncertainties_list, list) or len(cast(List[Any], uncertainties_list)) < 1:
            ok = False
            reasons.append('no_uncertainties')

        rollback = str(proposal.get('rollback_plan', ''))
        if len(rollback) < 10:
            ok = False
            reasons.append('rollback_plan_too_short')

        try:
            confidence = float(proposal.get('confidence_level', 0.0))
        except Exception:
            confidence = -1.0
        if not (0.0 <= confidence <= 1.0):
            ok = False
            reasons.append('confidence_out_of_range')

        severity = 'info'
        if not ok:
            # Escalate severity based on number of failures
            fail_count = len(reasons)
            if fail_count >= 4:
                severity = 'critical'
            elif fail_count >= 2:
                severity = 'warning'

        return ValidationOutcome(
            validator_id=self.VALIDATOR_ID,
            passed=ok,
            reasons=reasons,
            severity=severity
        )
