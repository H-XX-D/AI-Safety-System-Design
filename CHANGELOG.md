# Changelog

## [Unreleased]
### Added
- Semantic consensus aggregator (`semantic_consensus.py`) with confidence buckets and source diversity weighting.
- Structured logging schema (`log_schema.py`) and `logging_config.log_event` helper with validation tests.
- Key rotation utilities (`key_rotation.py`) and multi-key verification in `config_loader` (CONFIG_PUBKEYS_HEX, CONFIG_REVOKED_PUBKEYS_HEX).
- Resource budget guard (`resource_guard.py`) and optional verification budget via CONFIG_VERIFY_BUDGET_MS.
- Security utilities (`security_utils.py`) providing constant-time equality.
- Sliding replay window & normalization in `message_codec` plus fuzz corruption test.
- Non-Hypothesis secure sequence wrap-around test.
- Expanded configuration signature support with keyring + revocation.
- Incentive calibration simulation (`incentive_calibration.py`) validating honesty dominant over simple deceptive strategy (deterministic test harness) plus detection probability sweep API.
- Sandbox results normalization in `orchestrator` (`_convert_raw_sandbox_results`) producing `sandbox_flat` for consistent reward & validation integration.

### Changed
- Collusion metrics heuristic enhanced (overlap, burst, pairing repetition).
- Translator weighted verification for confidence-aware consensus.
- README & docs pending update to reflect new hardening features.

### Fixed
- Property invariants tests skip cleanly when Hypothesis is unavailable.
- Replay sequence_ok logic adjusted to avoid false negatives on duplicate frames.
- Reward calculation now prefers normalized sandbox results when present.

