from worm_guard import WormGuard


def test_guard_chain_verify_pass_and_tamper(monkeypatch):
    # Ensure verification preconditions are met
    import worm_manifest
    worm_manifest.enable_software_equivalence_mode(justification='test')
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'a'*64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'b'*64)

    g = WormGuard()
    # Generate a few events through normal APIs
    assert g.verify_worm()
    assert g.advance_version(1)
    assert g.verify_worm()

    # Chain should verify cleanly
    assert g.verify_event_chain() is True

    chain = g.export_audit_chain()
    assert len(chain) >= 2

    # Tamper case 1: modify last event detail (breaks hash/signature)
    ev = g._events[-1]
    original_detail = ev.detail
    ev.detail = ev.detail + ' tampered'
    assert g.verify_event_chain() is False
    # Restore for further tests to avoid cascading failure
    ev.detail = original_detail
    ev.hash_event = ev.hash_event  # no-op clarify

    # Restore by re-running a fresh guard instance to avoid bleed-over
    g2 = WormGuard()
    monkeypatch.setenv('CORE_VALUES_KNOWN_HASH', 'a'*64)
    monkeypatch.setenv('CORE_ALIGNMENT_FILTER_HASH', 'b'*64)
    assert g2.verify_worm()
    assert g2.advance_version(1)
    assert g2.verify_event_chain() is True

    # Tamper case 2: keep payload but flip signature bytes
    # Tamper case 2: keep payload but flip signature nibble
    ev2 = g2._events[-1]
    sig = ev2.signature
    flipped = ('0' if sig[0] != '0' else '1') + sig[1:]
    ev2.signature = flipped
    assert g2.verify_event_chain() is False
    # Rollback tamper: simulate removal of last event
    removed = g2._events.pop()
    # After removal verification should fail because internal linkage breaks when recomputed expectations differ
    assert g2.verify_event_chain() is False
    # Restore removed event to keep state consistent for any subsequent tests referencing singleton patterns
    g2._events.append(removed)
