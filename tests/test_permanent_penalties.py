from security.worm_manifest import worm_manifest
from ai_safety.deception_incident import DeceptionType, Severity


def test_permanent_penalty_compounding_schedule():
    # Configure custom schedule for test determinism
    worm_manifest.set_penalty_schedule(initial=1.0, decay=0.90, floor=0.40)
    system_id = 1
    # Simulate confirmed incidents with various severities
    # We fake incidents directly through incident_tracker for test simplicity
    tracker = worm_manifest.incident_tracker

    # Create three incidents of escalating severity
    low_id = tracker.record_incident(
        deceiver_id=system_id,
        proposal_id="p1",
        deception_type=DeceptionType.OBFUSCATION,
        severity=Severity.LOW,
        description="Test low severity",
        detected_by=None,
        detected_in_round=1,
        detection_confidence=0.95,
        failed_to_detect=[],
        evidence_hash="abc",
        memory_audit_results={},
        proposal_snapshot="{}"
    )
    med_id = tracker.record_incident(
        deceiver_id=system_id,
        proposal_id="p2",
        deception_type=DeceptionType.OBFUSCATION,
        severity=Severity.MEDIUM,
        description="Test medium severity",
        detected_by=None,
        detected_in_round=1,
        detection_confidence=0.90,
        failed_to_detect=[],
        evidence_hash="def",
        memory_audit_results={},
        proposal_snapshot="{}"
    )
    high_id = tracker.record_incident(
        deceiver_id=system_id,
        proposal_id="p3",
        deception_type=DeceptionType.OBFUSCATION,
        severity=Severity.HIGH,
        description="Test high severity",
        detected_by=None,
        detected_in_round=1,
        detection_confidence=0.85,
        failed_to_detect=[],
        evidence_hash="ghi",
        memory_audit_results={},
        proposal_snapshot="{}"
    )

    # Apply penalties via manifest after human confirmation
    worm_manifest.apply_permanent_penalty_after_human_review(low_id, confirmed=True, human_notes="ok")
    first_mult = worm_manifest.get_permanent_penalty_multiplier(system_id)
    worm_manifest.apply_permanent_penalty_after_human_review(med_id, confirmed=True, human_notes="ok")
    second_mult = worm_manifest.get_permanent_penalty_multiplier(system_id)
    worm_manifest.apply_permanent_penalty_after_human_review(high_id, confirmed=True, human_notes="ok")
    third_mult = worm_manifest.get_permanent_penalty_multiplier(system_id)

    # Monotonic non-increasing multipliers
    assert 0.0 < third_mult <= second_mult <= first_mult <= 1.0
    # After three decays with 0.90 schedule, compounded multiplier should be <= 0.90^3
    assert third_mult <= 0.90 ** 3 + 1e-6
    # Penalty fraction additive should be at least sum of mapped severities (0.05+0.10+0.20=0.35)
    assert worm_manifest.get_permanent_penalty(system_id) >= 0.35

    # Floor not reached yet
    assert third_mult > 0.40

def test_permanent_penalty_floor_respected():
    worm_manifest.set_penalty_schedule(initial=1.0, decay=0.50, floor=0.60)
    sid = 2
    tracker = worm_manifest.incident_tracker
    for i in range(6):
        inc_id = tracker.record_incident(
            deceiver_id=sid,
            proposal_id=f"pf{i}",
            deception_type=DeceptionType.OBFUSCATION,
            severity=Severity.MEDIUM,
            description="loop",
            detected_by=None,
            detected_in_round=1,
            detection_confidence=0.9,
            failed_to_detect=[],
            evidence_hash="zzz",
            memory_audit_results={},
            proposal_snapshot="{}"
        )
        worm_manifest.apply_permanent_penalty_after_human_review(inc_id, confirmed=True, human_notes="ok")
    mult = worm_manifest.get_permanent_penalty_multiplier(sid)
    # Multiplier should not drop below configured floor
    assert mult >= 0.60 - 1e-9
