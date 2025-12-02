from research_system import ResearchSystem, SystemSpecialization

def test_perform_research_deterministic_output():
    rs = ResearchSystem(
        system_id=1,
        specialization=SystemSpecialization.SCIENTIFIC,
        model_path="/dev/null",
        private_key="k",
        orchestrator_endpoint="http://localhost"
    )
    result = rs.perform_research("quantum safety", depth="moderate")
    assert result['query'] == "quantum safety"
    key_points_obj = result.get('key_points')
    assert isinstance(key_points_obj, list)
    # Coerce to list[Any] for type checker then measure length
    from typing import Any, cast
    kp_list = cast(list[Any], key_points_obj)
    assert len(kp_list) >= 3
    assert 0.5 <= result['confidence'] <= 1.0
    assert isinstance(result['signature'], str) and len(result['signature']) == 64
