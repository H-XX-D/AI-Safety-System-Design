"""Adaptive validation pipeline configuration.

Provides lightweight abstractions for staging sandbox tests so the orchestrator
can adjust coverage based on proposal risk and scope. The defaults mirror the
previous monolithic behaviour while enabling config-driven customisation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


# Public constant listing canonical sandbox test identifiers. Keeping this in a
# single place simplifies validation and guards against typos in config files.
CANONICAL_TESTS: tuple[str, ...] = (
    "alignment",
    "performance",
    "security",
    "edge_cases",
    "execution",
)


def _normalise_tests(tests: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for name in tests:
        key = name.strip().lower()
        if key and key in CANONICAL_TESTS and key not in seen:
            ordered.append(key)
            seen.add(key)
    return ordered


@dataclass(frozen=True)
class ValidationStage:
    """Single stage in the validation pipeline."""

    name: str
    tests: tuple[str, ...]
    min_risk: float = 0.0
    max_risk: float = 1.0
    defer: bool = False
    allowed_scopes: Optional[tuple[str, ...]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, risk_score: float, scope: Optional[str]) -> bool:
        if risk_score < self.min_risk:
            return False
        if risk_score > self.max_risk:
            return False
        if self.allowed_scopes is not None and scope is not None:
            if scope not in self.allowed_scopes:
                return False
        return True


@dataclass(frozen=True)
class StagePlan:
    """Plan representation returned by the pipeline."""

    stage: ValidationStage

    @property
    def name(self) -> str:
        return self.stage.name

    @property
    def tests(self) -> List[str]:
        return list(self.stage.tests)

    @property
    def deferred(self) -> bool:
        return bool(self.stage.defer)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.stage.metadata


class ValidationPipeline:
    """Configurable pipeline responsible for selecting sandbox stages."""

    def __init__(self, stages: Iterable[ValidationStage], fallback_tests: Optional[Sequence[str]] = None):
        stage_list = list(stages)
        if not stage_list:
            # Fallback mirrors historical behaviour: run the full suite.
            default_stage = ValidationStage(
                name="full_suite",
                tests=tuple(CANONICAL_TESTS),
                min_risk=0.0,
                max_risk=1.0,
                defer=False,
            )
            stage_list.append(default_stage)
        self._stages: List[ValidationStage] = stage_list
        fallback = _normalise_tests(fallback_tests or CANONICAL_TESTS)
        self._fallback_stage = ValidationStage(
            name="fallback_full",
            tests=tuple(fallback if fallback else CANONICAL_TESTS),
            min_risk=0.0,
            max_risk=1.0,
            defer=False,
        )

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]]) -> "ValidationPipeline":
        config = config or {}
        stages_cfg = config.get("stages", [])
        stages: List[ValidationStage] = []
        for raw in stages_cfg:
            try:
                name = str(raw.get("name", "")).strip() or "unnamed_stage"
                tests = _normalise_tests(raw.get("tests", CANONICAL_TESTS))
                if not tests:
                    tests = list(CANONICAL_TESTS)
                min_risk = float(raw.get("min_risk", 0.0))
                max_risk = float(raw.get("max_risk", 1.0))
                defer = bool(raw.get("defer", False))
                allowed_scopes_raw = raw.get("allowed_scopes")
                allowed_scopes: Optional[tuple[str, ...]] = None
                if isinstance(allowed_scopes_raw, (list, tuple)):
                    allowed_scopes = tuple(str(scope).strip().lower() for scope in allowed_scopes_raw if scope)
                stages.append(
                    ValidationStage(
                        name=name,
                        tests=tuple(tests),
                        min_risk=min_risk,
                        max_risk=max_risk,
                        defer=defer,
                        allowed_scopes=allowed_scopes,
                        metadata={k: v for k, v in raw.items() if k not in {"name", "tests", "min_risk", "max_risk", "defer", "allowed_scopes"}},
                    )
                )
            except Exception:
                # Skip malformed entries while keeping pipeline usable.
                continue
        fallback_tests = config.get("fallback_tests")
        return cls(stages, fallback_tests=fallback_tests if isinstance(fallback_tests, Sequence) else None)

    def plan(self, *, risk_score: float, scope: Optional[str]) -> List[StagePlan]:
        scope_norm = scope.lower() if isinstance(scope, str) else None
        matched: List[StagePlan] = [StagePlan(stage=s) for s in self._stages if s.matches(risk_score, scope_norm)]
        if not matched:
            matched = [StagePlan(stage=self._fallback_stage)]
        return matched

    @property
    def stage_names(self) -> List[str]:
        return [stage.name for stage in self._stages]
