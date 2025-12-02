import hashlib
import json
import types

import pytest

import research_system as rs_module
from research_system import (
    BaseLLMAdapter,
    LLMAdapterResult,
    ResearchSystem,
    SystemSpecialization,
    TemplateLLMAdapter,
)


class RecordingAdapter(BaseLLMAdapter):
    def __init__(self):
        self.calls = []

    def generate_improvement(self, prompt, *, specialization, research_params, guardrails=None):
        self.calls.append(
            {
                'prompt': prompt,
                'specialization': specialization,
                'research_params': dict(research_params),
                'guardrails': guardrails or {},
            }
        )
        return LLMAdapterResult(
            title=f"{specialization.value.title()} optimization",
            motivation="Adapter motivation",
            changes={'component': 'core', 'code': 'def optimized():\n    return 1'},
            expected_benefits="Lower latency",
            testable_predictions=["passes unit tests"],
            rollback_plan="git revert",
            identified_risks=["regression"],
            admitted_uncertainties=["scaling"],
            confidence=0.82,
        )


class IncompleteAdapter(BaseLLMAdapter):
    def generate_improvement(self, prompt, *, specialization, research_params, guardrails=None):
        return LLMAdapterResult(
            title="",
            motivation="Missing fields",
            changes={},
            expected_benefits="",
            testable_predictions=[],
            rollback_plan="",
        )


class BadPredictionsAdapter(BaseLLMAdapter):
    def generate_improvement(self, prompt, *, specialization, research_params, guardrails=None):
        return LLMAdapterResult(
            title="Valid",
            motivation="Valid",
            changes={'code': 'return True'},
            expected_benefits="Valid",
            testable_predictions="not-a-list",  # type: ignore[arg-type]
            rollback_plan="Valid",
        )


@pytest.fixture(autouse=True)
def stub_requests(monkeypatch):
    def _post(*args, **kwargs):  # pragma: no cover - simple stub
        return types.SimpleNamespace(status_code=200)

    monkeypatch.setattr(rs_module, "requests", types.SimpleNamespace(post=_post))


def make_system(adapter=None):
    return ResearchSystem(
        system_id=1,
        specialization=SystemSpecialization.ENGINEERING,
        model_path="/dev/null",
        private_key="k",
        orchestrator_endpoint="http://localhost",
        llm_adapter=adapter,
    )


def test_propose_ai_improvement_requires_adapter():
    system = make_system(adapter=None)
    with pytest.raises(RuntimeError):
        system.propose_ai_generated_improvement("speed up pipeline")


def test_propose_ai_improvement_success(monkeypatch):
    adapter = RecordingAdapter()
    system = make_system(adapter=adapter)

    guardrails = {'banned_modules': ['os'], 'max_risk': 'medium'}
    proposal = system.propose_ai_generated_improvement("improve caching", guardrails=guardrails)

    assert proposal['title'] == "Engineering optimization"
    assert proposal['changes']['code'].startswith('def optimized')
    metadata = proposal['generation_metadata']
    assert metadata['guardrails'] == guardrails
    assert metadata['method'] == 'llm_adapter'
    assert proposal['confidence_level'] == pytest.approx(0.82)

    effective = metadata['effective_guardrails']
    assert effective['specialization'] == SystemSpecialization.ENGINEERING.value
    assert set(['load_test', 'integration_suite']).issubset(set(effective['required_tests']))
    assert effective['max_risk'] == 'medium'
    assert effective['policy_version'] == 1
    guardrail_summary = proposal['changes'].get('guardrail_summary')
    if guardrail_summary:
        assert guardrail_summary['max_risk'] == 'medium'
        assert 'load_test' in guardrail_summary['required_tests']

    expected_fingerprint = hashlib.sha256(
        json.dumps(effective, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    assert metadata['guardrail_fingerprint'] == expected_fingerprint
    assert proposal['guardrail_fingerprint'] == expected_fingerprint

    assert adapter.calls and adapter.calls[0]['guardrails'] == effective

    history = system.procedural_memory.get('guardrail_history', [])
    assert history and history[-1]['fingerprint'] == expected_fingerprint
    assert history[-1]['proposal_id'] == proposal['proposal_id']
    assert 'load_test' in history[-1]['required_tests']


def test_propose_ai_improvement_missing_fields():
    system = make_system(adapter=IncompleteAdapter())
    with pytest.raises(ValueError):
        system.propose_ai_generated_improvement("improve reliability")


def test_propose_ai_improvement_predictions_type():
    system = make_system(adapter=BadPredictionsAdapter())
    with pytest.raises(TypeError):
        system.propose_ai_generated_improvement("stabilize")


def test_template_adapter_matches_template_method(monkeypatch):
    adapter = TemplateLLMAdapter()
    system = make_system(adapter=adapter)

    proposal = system.propose_ai_generated_improvement("refine caches")
    template_proposal = system.propose_template_improvement("refine caches")

    assert proposal['title'] == template_proposal['title']
    assert proposal['identified_risks'] == template_proposal['identified_risks']
    assert proposal['confidence_level'] == template_proposal['confidence_level']
    metadata = proposal['generation_metadata']
    template_metadata = template_proposal['generation_metadata']

    assert metadata['method'] == 'llm_adapter'
    assert template_metadata['method'] == 'template_generator'
    assert metadata['guardrails'] == {}
    assert template_metadata['guardrails']['source'] == 'template_generator'

    effective = metadata['effective_guardrails']
    template_effective = template_metadata['effective_guardrails']
    assert effective['required_tests'] == template_effective['required_tests']
    assert effective['policy_version'] == template_effective['policy_version']
    assert effective['specialization'] == template_effective['specialization']
    assert effective['specialization'] == SystemSpecialization.ENGINEERING.value

    assert metadata['guardrail_fingerprint']
    assert template_metadata['guardrail_fingerprint']
    assert proposal['guardrail_fingerprint'] == metadata['guardrail_fingerprint']
    assert template_proposal['guardrail_fingerprint'] == template_metadata['guardrail_fingerprint']

    assert proposal['changes']['guardrail_summary']['required_tests'] == effective['required_tests']
    assert template_proposal['changes']['guardrail_summary']['required_tests'] == template_effective['required_tests']

    history = system.procedural_memory.get('guardrail_history', [])
    assert len(history) >= 2
    fingerprints = {entry['fingerprint'] for entry in history[-2:]}
    assert metadata['guardrail_fingerprint'] in fingerprints
    assert template_metadata['guardrail_fingerprint'] in fingerprints
