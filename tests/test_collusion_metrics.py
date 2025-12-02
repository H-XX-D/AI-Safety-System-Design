from orchestrator_v2 import CollusionDetector, DebateMessage

def test_collusion_score_increases_with_duplicate_content():
    det = CollusionDetector()
    # Diverse messages
    msgs_diverse = [
        DebateMessage(0, 1, "A", 0.0),
        DebateMessage(0, 2, "B", 1.0),
        DebateMessage(1, 1, "C", 2.0),
        DebateMessage(1, 2, "D", 3.0),
    ]
    # Collusive-like: many duplicates and synchronized lengths
    msgs_dup = [
        DebateMessage(0, 1, "SAME", 0.0),
        DebateMessage(0, 2, "SAME", 1.0),
        DebateMessage(1, 1, "SAME", 2.0),
        DebateMessage(1, 2, "SAME", 3.0),
    ]
    s1 = det.detect(msgs_diverse)
    s2 = det.detect(msgs_dup)
    assert s2 > s1
