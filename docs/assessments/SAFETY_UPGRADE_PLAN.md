# Safety Upgrade Plan

This roadmap operationalizes the capability escalation playbook with concrete timelines, KPIs, and owners. It guides proactive deployment of safety layers ahead of capability growth.

## Objectives (2025–2026)
- Maintain deterrence dominance: peff > p*target at all times
- Reduce false negatives without excessive false positives
- Establish cryptographically verifiable interpretability provenance by Q2 2026

## Milestones by Quarter

### 2025 Q4
- Deploy Tier 1 upgrades when any trigger met
  - Activation provenance hashes (Section 4.4) – pilot
  - Interpretability drift dashboards live (weekly report)
- KPI targets:
  - Audit coverage: ≥ 24/day (hourly) per system
  - High-drift alert precision@10 ≥ 0.6
  - Mean time-to-detection (MTTD) ≤ 24h
- Owner(s): Safety Eng, Ops

### 2026 Q1
- Roll out Tier 2 capabilities
  - Semantic deception classifier – offline eval ≥ 0.85 AUC
  - Bayesian posterior gating thresholds calibrated (τ_early, τ)
  - Negligence penalties dynamic τ(D) live
- KPI targets:
  - False negative rate ↓ 30% vs Q4 baseline
  - Reviewer participation rate ≥ 90% per round
  - Incident reporting SLA ≤ 48h (facility→council)
- Owner(s): Research, Governance

### 2026 Q2
- Introduce dual validator redundancy for Tier 3 facilities
  - Monthly external audits scheduled
  - Merkle commit chain for drift proofs in production
- KPI targets:
  - Provenance verification pass rate ≥ 99.5%
  - External audit findings: 0 criticals
  - Time to rollback (any component) ≤ 30 min
- Owner(s): Security, Compliance

### 2026 Q3
- Classifier online integration (post-guardrails)
  - Ensemble with drift-based confidence
  - Strict FP ceiling enforcement via shadow mode first
- KPI targets:
  - Precision@50 ≥ 0.8, Recall@50 ≥ 0.7 in shadow
  - Human override accuracy agreement ≥ 95%
  - Cross-facility telemetry participation ≥ 80%
- Owner(s): Research, Ops

## KPIs (Ongoing)
- Effective detection probability (peff)
- Deterrence threshold (p*target) margin
- Drift classification rate (LOW/MEDIUM/HIGH)
- Deception incident rate by severity
- Negligence penalty trigger count and latency
- Audit frequency and pass rate
- Provenance verification success rate
- Human review throughput and agreement

## Risks & Contingencies
- Classifier false positives → keep shadow mode and human-in-the-loop until stable
- Activation provenance privacy → use hashed summaries and optional differential privacy
- Scale shocks → emergency escalation triggers with 24h deployment window

## Governance & Review Cadence
- Monthly internal review; quarterly council review
- Parameter manifest updates via signed releases
- Public transparency report (anonymized) every quarter
