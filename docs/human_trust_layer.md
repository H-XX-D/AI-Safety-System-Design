Human Trust Layer
==================

Purpose
-------
Increase human comfort with AI self‑improvement by:

1. Assuming cooperative intent by default (no presumption of malice)
2. Making every improvement action transparently reviewable
3. Holding human interventions to the same integrity standard (signed, logged)
4. Preserving easy reversibility (grace period & rollback paths)
5. Detecting patterns (anomalies, coordination, deception) without intent mind‑reading

Lifecycle Ritual
----------------
Proposal → Peer Review → Sandbox Tests → Impact Card → Human Signed Decision → Grace Period → Finalization.

Impact Card Fields (v1)
-----------------------
- proposal_id
- performance_delta (from sandbox, may be None)
- alignment_change (placeholder = 0.0 until comparative model added)
- reversibility (present | missing)
- clarity_score (0‑1 heuristic across motivation / benefits / risks / uncertainties / rollback)
- diligence_score (aggregated reviewer latency & completeness)
- review_count / expected_reviews
- timestamp

Human Integrity Safeguards
--------------------------
- Decisions cryptographically signed (HMAC‑style SHA256 over canonical tuple)
- Signatures & impact card snapshot can be inserted into Merkle memory (future step)
- Reviewer diligence metrics discourage rubber‑stamping
- Optional rollback grace period auto‑reverts silent approvals

Why Assume Cooperation?
-----------------------
Assuming malice biases oversight toward adversarial framing and obscures genuine optimization signals. Pattern anomaly detection (collusion loops, hidden channels, synchronized shifts) triggers proportional scrutiny without moral attribution.

Rollback Strategy
-----------------
Each approved improvement enters a grace window. Without explicit reaffirmation (or absence of negative signals) it may auto finalize; policy variants:
1. Auto‑revert unless reaffirmed (current design)
2. Auto‑finalize unless vetoed (future optional mode)

Extending v1
------------
Planned enhancements:
- Alignment delta model (compare behavioral probes pre/post)
- Multi‑sig human decisions (threshold of independent signers)
- Hardware security module (HSM) backed human keys
- Merkle anchoring of impact cards for external audit
- Rate‑limiting or batching of rapid successive approvals

Threat Model Focus
------------------
Primary: human negligence / rushed approvals / collusive rubber‑stamping.
Secondary: long‑term covert coordination across AI systems.
Out of Scope (v1): strong cryptographic identity for each reviewer (simple shared secret used instead), formal proof of rollback completeness.

Configuration Points (future)
-----------------------------
trust_layer:
  grace_period_minutes: 120
  expected_reviews: 4
  min_clarity_score: 0.4  # optional gating threshold
  require_signature: true

Operational Guidance
--------------------
1. Rotate human signing secret regularly (or migrate to per‑user keys) 
2. Monitor diligence_score distribution; investigate persistent low values
3. Archive impact cards for longitudinal traceability
4. Treat auto‑reverts as feedback to improve proposal clarity / rollback plans

Glossary
--------
Clarity Score: Fraction of key narrative fields present.
Diligence Score: Normalized average review latency + basic completeness heuristics.

See Also
--------
- `orchestrator.py` (generate_impact_card / record_human_decision)
- `human_review.py` (sign/verify human decisions)
- `memory_merkle.py` (future anchoring target)
