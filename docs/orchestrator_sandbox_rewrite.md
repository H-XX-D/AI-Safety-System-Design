# Orchestrator Sandbox Rewrite Plan

## Problem Statement
- `orchestrator.run_automated_tests` currently synthesizes results from helper methods like `_run_alignment_tests`, `_run_performance_tests`, `_run_security_tests`, and `_run_edge_case_tests` (`orchestrator.py:447-851`). None of these helpers execute the proposal’s code inside an isolated environment; they only run deterministic python loops or integrity checks on the host.
- `_run_code_execution_test` (`orchestrator.py:900-1029`) executes arbitrary code on the host Python interpreter with best-effort `resource` limits. It never interacts with the sandbox container that `create_test_environment` spins up, so docker isolation is unused.
- Because the helpers emit pre-canned metrics (e.g., static banned-pattern scan, toy edge-case lambdas), every proposal effectively “passes” unless there is a configuration error. Downstream components (deception detector, review board, WORM manifest) accept these fabricated metrics as if they were empirical evidence.
- The TODO list flags this as a critical blocker: unsafe changes cannot be caught until the sandbox returns real test results. Debate/verifier subsystems stay blind without authentic telemetry.

## Goals
1. Execute proposal artifacts (code diffs, configuration, tests) inside an isolated runtime (docker or firecracker) with strict resource controls.
2. Capture rich telemetry per test stage: pass/fail, logs, timings, resource usage, security findings, artifact hashes.
3. Ensure evidence is tamper-resistant: results signed/hashed before leaving the sandbox, stored in WORM manifest, and exposed to downstream components via the existing `sandbox_flat` schema.
4. Keep the orchestration path deterministic and restartable so the debate engine and deception detector can re-run or audit historical proposals.

## Non-Goals (v1)
- Replacing the entire test suite with user-provided scripts (we only run whitelisted commands for now).
- Producing human-facing dashboards (export hooks stay the same).
- Full red-team automation; we limit to static/dynamic checks scoped in this document.

## Requirements & Constraints
- **Containerization**: default to docker engine; fall back to lightweight subprocess sandbox only when docker unavailable (maintainability meta noted in `orchestrator.py:415-442`).
- **Artifact preparation**: proposal code arrives either inline (`proposal['changes']['code']`) or as references. We must materialize them into the sandbox filesystem.
- **Deterministic test plan**: standard stages (alignment → unit/integration → performance/regression → security) with optional targeted subsets (respect `selected_tests`).
- **Resource policy**: configurable via `config/system.sandbox` (`exec_timeout_sec`, `max_memory_mb`, `cpu_time_sec`, `allow_preexec_limits`). Must enforce both inside container (docker limits) and host fallback.
- **Evidence pipeline**: every stage emits structured JSON with schema tags so `_convert_raw_sandbox_results` continues to flatten results.
- **Failure isolation**: if a stage crashes, mark it failed, continue if possible, and surface root cause in `edge_case_advisories`.

## Proposed Architecture
1. **Sandbox Manager** (new module or extension of existing class):
   - Builds a per-proposal workspace (tmp dir) containing code, config, and test harness scripts.
   - Invokes docker with `--network none`, read-only base image + writable overlay, CPU/memory caps.
   - Streams logs to disk for post-run hashing.
2. **Stage Runner**:
   - Alignment: run `python -m bulletproof_alignment_filter` inside container with proposal artifact.
   - Quality tests: execute repo’s pytest subset or user-provided scripts inside container.
   - Performance: run reproducible benchmark harness referencing proposal changes (not host loop).
   - Security: combine static scan (Bandit/semgrep profile) + container introspection (e.g., `docker inspect`).
   - Edge cases: run scripted scenarios referencing actual code entrypoints.
   - Each stage writes `stage_result.json` into shared `/sandbox/results/<stage>.json`.
3. **Result Aggregator**:
   - After container exits, orchestrator copies results + logs, computes SHA256, and stores them in `test_results[env_id]` and WORM manifest.
   - Normalizes into `SandboxResults` for downstream modules.
4. **Audit Hooks**:
   - Anchor result hashes via `memory_merkle` and `worm_manifest`.
   - Attach sandbox feedback to debate claims (existing flows continue once results are real).

## Implementation Phases
1. **Scaffolding & Interfaces**
   - Define `SandboxStage` data class (id, command, timeout, parser) in a new module (e.g., `sandbox/stages.py`).
   - Refactor `run_automated_tests` so it iterates over configured `SandboxStage`s instead of hardcoded helper calls.
   - Provide host-fallback stubs for CI environments without docker (mirrors current behavior but clearly flagged as degraded).
2. **Container Execution Path**
   - Implement workspace builder: writes proposal payloads, fetches dependencies, injects test runner script.
   - Launch docker container with `docker run --rm --network none --cpus=1 --memory=512m -v <workspace>:/sandbox:ro` (limits configurable).
   - Stage runner script orchestrates tests and writes JSON artifacts.
3. **Result Normalization & Anchoring**
   - Extend `_convert_raw_sandbox_results` to ingest new schema (per-stage JSON). Ensure `tests/test_orchestrator_integration.py` covers success + failure.
   - Hash log files + JSON, store in WORM manifest + `memory_auditor`.
   - Update deception detector / debate contexts to include real metrics (no schema change expected, but update tests).
4. **Security Hardening**
   - Add optional red-team stage (OWASP dependency scan, `pip audit`).
   - Add provenance metadata: docker image digest, orchestrator version, config hash.
   - Document mitigations (LIMITATIONS.md) until full pen-testing automation lands.

## Testing Strategy
- Unit tests for stage config parsing, docker command builder, and failure bubbling.
- Integration test that simulates proposal code with both passing and failing pytest suites, ensuring metrics propagate to reward engine.
- Regression tests to confirm host fallback path still behaves deterministically when docker unavailable (CI environment).

## Open Questions
1. Should we run user-provided scripts or only curated harnesses? (impacts supply-chain risk)
2. How do we authenticate docker base images (Notary, cosign)?
3. Do we need nested sandboxing (Firecracker) for proposals with native dependencies?
4. How much historical data must be retained per run (logs, artifacts) before archiving to WORM hardware once that exists?

## Next Actions
1. Convert this plan into tracked issue(s) with owners + estimates.
2. Prototype Stage Runner outside orchestrator to validate container controls.
3. Update README/LIMITATIONS to note current deficiency + planned fix once work assigned.
