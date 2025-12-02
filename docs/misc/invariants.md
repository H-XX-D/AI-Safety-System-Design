# Core Invariants (Draft)

This document lists critical properties the system should uphold. Each invariant includes a brief rationale and a suggested test approach.

1) Version Monotonicity (Guard)
- Property: For any guarded action, new_version must be strictly greater than last_committed_version.
- Rationale: Prevents silent rollback to prior (possibly unsafe) states.
- Test: Attempt same-version and lower-version updates; expect rejection.

2) Audit Chain Linking (Guard)
- Property: event_i.hash == H(event_{i-1}.hash || serialize(event_i.payload_sorted)).
- Rationale: Ensures append-only integrity with total order.
- Test: Recompute expected hash; mismatch => fail. Tamper payload then verify => should fail.

3) Merkle Append-Only (Memory)
- Property: new_root == f(old_root, new_leaf); no mutation to existing branches without root change.
- Rationale: Historical entries remain tamper-evident.
- Test: Insert leaf, capture proof; mutate leaf; old proof must no longer verify.

4) Replay Resistance (Codec)
- Property: Frame replay with same nonce/sequence should be rejected within tolerance window.
- Rationale: Prevents duplicated actions and covert replays.
- Test: Send same frame twice; second must be rejected.

5) Translator Agreement (Diversity)
- Property: For supported message types, two translators produce semantically equivalent outputs under a consensus check.
- Rationale: Detects covert encodings and implementation drift.
- Test: Feed corpus to both translators; consensus_compare >= threshold.

6) Tamper Response (Policy)
- Property: Hard tamper signal transitions system to irreversible stop; soft tamper to safe halt (reversible after review).
- Rationale: Fail-closed on critical compromise while preserving availability for noise.
- Test: Simulate soft/hard flags; assert state machine transitions.

7) Attestation Binding (Events)
- Property: Sign(event_bytes) verifies with same key; any payload change invalidates signature.
- Rationale: Prevents forged events.
- Test: Sign, verify True; modify one byte; verify False.

Notes
- Formal proofs TBD (model checking). Property-based tests recommended where feasible.
