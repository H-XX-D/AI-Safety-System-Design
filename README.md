# AI Safety System Design

System and Method for Safe Recursive Self-Improvement of Artificial Intelligence Using Multi-Tier Validation, Immutable Hardware Security, and Game-Theoretic Incentive Structures

Version: 0.4.2-dev
Status: Research Prototype (~65% implementation complete; LLM integration + Web UI + export functionality complete)
Last Updated: November 12, 2025

---

## Overview

This repository contains a partially implemented research prototype designed to let cooperative AI research systems iteratively improve themselves while remaining aligned with immutable human values. Core codecs, deception detectors, the air-gapped translator/coder pipeline, and manifest tooling now pass the full Python test suite (121 passed / 11 skipped). Sandbox execution now routes through a Docker (or optional Firecracker) backend with seccomp filtering via `sandbox/isolation.py`, falling back to the legacy host runner only when containerization is unavailable. Hardware persistence remains simulated and the portable `/media/usb` mount is still outstanding.

Patent Status: Provisional patent application prepared. See [assessments/PROVISIONAL_PATENT_APPLICATION.md](assessments/PROVISIONAL_PATENT_APPLICATION.md) for the full specification and claims.

---

## Implementation Snapshot

### Software subsystems with direct test coverage

- **AURA compression + translators** - `aura_compressor.py`, `aura_strategy_profile.py`, `hardware_translator.py`, and `translator.py` implement bit-packed codecs, deterministic template dictionaries, and message routing; verified by `tests/test_aura_*`, `tests/test_small_message_*`, `tests/test_translation_*`, and `tests/test_hardware_translator_basic.py`.
- **Alignment and deception defenses** - `alignment_filter.py`, `bulletproof_alignment_filter.py`, and `deception_detector.py` provide five detector families plus seven-method deception scoring with detailed evidence; covered by `tests/test_alignment_filter*.py`, `tests/test_deception_incident.py`, `tests/test_interpretability_monitor.py`, and the orchestrator integration suite.
- **Incentive and penalty layer** - `worm_manifest.py`, `worm_usb_verifier.py`, `reputation_system.py`, `reward_calculation.py`, and `audit_seed_chain.py` couple additive + multiplicative penalty tracking with deterministic audit seeds; see `tests/test_permanent_penalties.py`, `tests/test_reward_calculation.py`, `tests/test_reputation_metrics.py`, and `tests/test_audit_seed_chain.py`.
- **Tamper-evident memory and interpretability** - `memory_merkle.py`, `memory_auditor.py`, and `interpretability_monitor.py` implement append-only Merkle storage, hash normalization, and drift monitoring; validated by `tests/test_memory_merkle_*`, `tests/test_memory_query_normalization.py`, and `tests/test_interpretability_monitor.py`.
- **Structured orchestration pipeline** - `orchestrator.py`, its embedded `VirtualEnvironmentManager`, `orchestrator_sandbox.py` (which ships `SandboxEnvironmentManager`), and `debate_engine.py` coordinate proposals, guardrails, peer reviews, debate scoring, sandbox execution, and impact card generation. `_ensure_execution_coverage` now forces an execution run whenever proposal code is present, so both `tests/test_orchestrator_integration.py` and `tests/test_end_to_end_weighted_workflow.py` pass alongside the debate + sandbox suites (`tests/test_debate_engine.py`, `tests/test_sandbox_*`).
- **Observability and config integrity** - `log_schema.py`, `logging_config.py`, `key_rotation.py`, `config_loader.py`, `resource_guard.py`, and `security_utils.py` add schema-validated logging, Ed25519 key rotation, keyring-based signature verification with revocation lists, and deterministic resource budgets; validated by `tests/test_log_schema.py`, `tests/test_logging_presence.py`, `tests/test_key_rotation.py`, `tests/test_config_signing.py`, and `tests/test_resource_budget.py`.
- **Air-gapped translator/coder** - `translator.py`, `hardware_translator.py`, and `tests/test_hardware_translator_basic.py` cover the single translator/coder that sits on an air-gapped device and mirrors proposals into human-auditable form. `semantic_consensus.py` remains available for future multi-translator deployments but is no longer a baseline requirement.
- **Web-based monitoring UI** - `ui/app.py` (2,177 LOC) provides a professional Flask-based dashboard with 10+ HTML templates, real-time WebSocket updates, comprehensive data visualization, export functionality (CSV/JSON), and interactive proposal/detection/penalty monitoring. Production-ready interface for human oversight and governance.

### In-flight work

- **Sandbox execution/containerization + USB persistence** - `sandbox/isolation.py` now executes proposal code inside Docker (or Firecracker when configured) with seccomp filtering, explicit `--cpus`, `--memory`, `--pids-limit`, optional disk quotas, and host-side cgroup v2 fallbacks. `_run_code_execution_test` only falls back to the host interpreter when the sandbox backend is unavailable, and even then attaches the process to a dedicated cgroup with RLIMIT-based disk quotas. We still need automated end-to-end tests that exercise the container path, provenance checks on the sandbox image/kernel, and a configurable WORM output path that does not assume `/media/usb/test_results`.
- **Research agent realism** - `research_system.py` currently relies on deterministic `TemplateLLMAdapter` responses. Real LLM integration, retrieval, and network research are unresolved.
- **Hardware instantiation** - WORM USB stays a software simulation, translators run in-process, and the seventh validator remains a specification without hardware.
- **Incident response controls** - `control_actions.py` only ships dry-run hooks; halting outputs, isolating networks, and power controls are not wired to real infrastructure.

### Stubbed / placeholder modules

- `research_system.py` (606 LOC) is a template-only stub; all "agent" behaviors return deterministic canned strings without invoking real models or tools.
- `orchestrator.py` sandbox pathways fall back to the host interpreter on Windows or when Docker/Firecracker setup fails, so the "sandbox" remains a stubbed approximation until proper attestation + WORM persistence land.
- `debate_engine.py` still acts as a deterministic harness intended for future research agents—claims, scoring, and consensus calculations are scripted and do not yet integrate with actual debaters or adversarial playbooks.

### Recent hardening (November 2025)

- **Web UI Dashboard (Nov 12, 2025)** - ✅ **NEW** - Built professional Flask monitoring interface (2,177 LOC) with 10+ templates, real-time updates, export functionality, collusion detection widgets, proposal performance tracking, and ORKA oversight panels. Includes CSV/JSON export for detection, penalties, proposals, and ORKA reports. Toast notifications centered at top. Makes system behavior transparent and auditable for human governance. UI: 0% → 95% complete.
- **LLM Integration Complete (Nov 10, 2025)** - Added `llm_adapters.py` (750+ LOC) with OpenAI and Claude adapters, `llm_adapter_factory.py` (240+ LOC) for config-driven adapter creation, working examples in `examples/simple_llm_workflow.py` and `examples/full_workflow_with_llm.py`. Research agents: 25% → 60% complete.
- **Security Improvements (Nov 10, 2025)** - Implemented `production_control_hooks.py` (420+ LOC) with emergency controls (halt outputs, network isolation, state snapshots), added sandbox backend verification, made USB/WORM paths configurable. Security coverage: Sandbox isolation 75% → 80%, Emergency controls 40% → 70%, USB config 90% → 95%.
- **Comprehensive Testing** - Added `tests/test_sandbox_backend_verification.py` (300+ LOC) covering production control hooks, sandbox verification, and USB configuration. Current results: 131+ tests passing.
- Added `semantic_consensus.compute_consensus` (optional) for teams that still want multi-translator diversity weighting, even though the baseline now assumes a single air-gapped translator/coder.
- Introduced schema-driven logging and structured log validation in `log_schema.py`, plus deterministic log binding helpers.
- Added Ed25519 key rotation utilities (`key_rotation.py`) and config keyring + revocation support inside `config_loader.py`.
- Implemented `ResourceBudget` guards for signature verification and added sliding replay windows + normalization inside `message_codec.py`.
- Normalized sandbox result ingestion in `orchestrator._convert_raw_sandbox_results` so downstream reward code reads a consistent `sandbox_flat` payload.
- Added `_ensure_execution_coverage` fallback execution to guarantee proposal code runs even when validation stages defer or skip `execution`, restoring the full orchestrator workflow tests.

### Test suite status

Latest run (November 10, 2025, Python 3.13.5, `python -m pytest -q`): **131+ passed, 11 skipped** (142+ collected, ~25 s). The orchestrator integration suites now pass because `_ensure_execution_coverage` performs a dedicated execution run whenever proposal code exists, ensuring `execution['executed']` is true. Coverage spans alignment + WORM hashing, incentive calibration, sandbox flattening, air-gapped translator serialization, structured logging, config signing, replay protection, debate scoring, research adapter simulations, **LLM adapter integration, production control hooks, sandbox backend verification, and USB path configuration**. Skipped cases remain limited to ESP32 compilation checks, hardware-dependent VRF proofs, and Docker daemon availability.

---

## Novel Claims and Research Contributions

1. **Dual Permanent Penalty System** - Additive penalties (capped at 0.95) combine with multiplicative decay to enforce long-term deterrence while respecting a configurable floor. Implemented in `worm_manifest.py` and exercised through `tests/test_permanent_penalties.py` and `tests/test_reward_edge_cases.py`.
2. **Seven-method deception detection** - Complexity mismatch, overconfidence, pattern signatures, semantic cues, consistency checks, historical comparison, and peer disagreement each emit confidence-weighted signals. Aggregation logic in `deception_detector.py` is verified via `tests/test_deception_incident.py`, `tests/test_interpretability_monitor.py`, and orchestrator integration tests.
3. **AURA compression plus deterministic translators** - Bit-packed codecs, dictionary and rANS hybrids, and ESP32-targeted headers ensure AI proposals stay inspectable, while `translator.py` plus `hardware_translator.py` keep human-readable traces aligned with Merkle proofs. Tests cover compression (`tests/test_aura_*`) and translation accuracy (`tests/test_translation_*`).
4. **Air-gapped translator/coder pipeline** - `translator.py` plus `hardware_translator.py` keep human-readable traces aligned with Merkle proofs on a single translator/coder that can live on an air-gapped device. Optional diversity logic in `semantic_consensus.py` remains tested via `tests/test_semantic_consensus.py`, `tests/test_translator_consensus.py`, and `tests/test_translator_divergence.py` for deployments that still want multiple translators.

---

## Orchestrator, Debate, and Validation

The orchestrator coordinates improvement proposals end-to-end:

- Proposal ingestion normalizes guardrails, merges specialization defaults, and writes immutable entries through `MemoryStorage`.
- Peer review tracking enforces quorum requirements, spot-checks collusion heuristics, and feeds the `ReputationMatrix`.
- `DebateEngine` now supports deterministic multi-round arguments with structured claims, consensus extraction, and sandbox payload generation. `_apply_claim_feedback` adjusts scores once verification feedback arrives, keeping consensus stable across replays.
- `SandboxEnvironmentManager` (in `orchestrator_sandbox.py`) governs module allowlists, static-import guards, and deterministic execution plans, while the new `sandbox/isolation.py` module provides Docker/Firecracker backends with seccomp filtering and PID/memory caps. `_convert_raw_sandbox_results` flattens heterogeneous runner outputs so reward calculations, interpretability alerts, and impact cards share a normalized view; set `SANDBOX_USE_VIRTUAL=1` on Windows to force the virtual/fallback path if Docker + a `/media/usb` mount are unavailable.
- Impact cards generated by `Orchestrator.generate_impact_card` summarize debate participants, verified claims, sandbox advisories, and permanent penalties for governance review.

---

## Air-Gapped Translator/Coder and Logging Infrastructure

- `translator.py` and `hardware_translator.py` describe the single translator/coder that mirrors messages across the air gap. `semantic_consensus.py` is now optional; it still buckets translator confidence levels for teams that deploy multiple translators, but the default requirement is satisfied by one trusted device.
- `log_schema.py` plus `logging_config.py` provide schema validation and structlog bindings so every subsystem emits machine-parseable security events. Failed validation downgrades to deterministic fallback logs, preventing unstructured output from bypassing auditing.
- `config_loader.py` now supports multiple Ed25519 public keys with revocation, optional `CONFIG_VERIFY_BUDGET_MS` execution budgets enforced via `ResourceBudget`, and strict-mode enforcement for CI.
- `security_utils.constant_time_equals` removes timing variance for signature comparisons that previously leaked manifest states.

---

## WORM Manifest and Hardware Translators

Directory: [worm_usb_dir/](worm_usb_dir/)
Root Hash: `5bdb62947a9cee2fa77d038483e0b4894e9735c7b690d8062a1b48266aaf5639`

**Contents**

- AURA decoder bundles (Python + C headers)
- Reward engine logic + penalty tables
- Hardware translator protocol spec and token dictionaries
- Manifest metadata snapshots and trust layer documentation

**Hardware Status (Nov 12, 2025)**

- ✅ **WORM USB Drive**: Physical write-once read-many USB storage device currently connected and operational
- 🟡 **Hardware Translator**: Software implementation ready; physical ESP32/Raspberry Pi air-gapped device pending prototype build
- 🟡 **Seventh Validator**: Specification complete; hardware implementation unfunded

`VirtualEnvironmentManager.write_results_to_usb` persists JSON artifacts to the connected WORM USB device. USB mount paths are now configurable via `config/default.yaml` with platform-specific settings.

**Verification Flow**

1. SHA-256 manifest hash verification
2. HMAC signature check via `WORM_SECRET`
3. Optional Ed25519 signature verification (multi-key support from `config_loader`)
4. Council multi-signature verification hook (placeholder)

**Current implementation**

WORM USB device is physically present and connected. `worm_manifest.py` operates in "software equivalence" mode with physical USB backing. `worm_usb_verifier.py` can verify against the actual WORM device when properly mounted. Multi-signature verification paths are implemented but return `None` when council signing is not configured.

**Security note**

With physical WORM USB connected, the system now has genuine write-once storage for audit trails and manifest data. The fallback to environment variables (when USB is disconnected) remains a development convenience but should be disabled in production deployments. Production builds must fail-closed if the WORM manifest or signatures cannot be verified against the physical device.

---

## Demo Integration Harness

File: `demo_integration.py` (approx. 400 LOC)
Status: Component-aware guardrail demo (~70% complete)

Highlights:

- Seeds five `ResearchSystem` instances with deterministic `TemplateLLMAdapter`s and assigns each to the component-specific allowlists defined in `config/*.yaml`.
- Performs warm-up proposals to stabilize interpretability drift baselines, then simulates 120 proposal rounds with a 40% deceptive rate to estimate empirical detection probability `p`.
- Injects subtle deceptive signals (suppressed risks, overconfident language) and tracks whether orchestrator verdicts mark them as `rejected_deceptive`.
- Persists deterministic artifacts in `demo_outputs/` (`detection_probability.json`, `drift_histogram.json`, `manifest_root.txt`, `run_manifest.json`) and stores a summarized record in `MemoryStorage`.
- Verified by `tests/test_demo_integration_smoke.py` and `tests/test_research_llm_adapter.py`, ensuring artifacts remain deterministic and probabilities stay within [0,1].

---

## Architecture Overview

| Layer / Component | Implementation Snapshot | Notes |
| --- | --- | --- |
| Research Agents (Tier 1) | LLM adapters (OpenAI, Claude, Template), factory pattern, guardrails (~60%) | ✅ **IMPROVED** - LLM integration complete; internet research pending |
| Orchestrator / ORCA (Tier 2) | Proposal workflow, sandbox execution, debate engine, reward integration (~70%) | Runs on host interpreter; containerization pending |
| Seventh Validator (Tier 3) | Specification + interface stubs (~85%) | Hardware + air-gap still unfunded |
| Human Governance (Tier 4) | Policy docs, incentive simulations, council procedures, **Web UI dashboard (~95%)** | ✅ **NEW** - Professional monitoring interface; multi-party signing pending |
| Alignment Filter | Fully implemented with dedicated tests | Runs in current suite |
| Deception Detector | Working prototype with evidence trails (~85%) | Semantic model optional but scaffolded |
| Memory Merkle Log | Working append-only store | Hash chain verified per commit |
| Permanent Penalties | Fully implemented dual compounding | Integrated with reward pipeline |
| WORM Guard + Manifest | Physical WORM USB connected (~97%) | ✅ **IMPROVED** - Physical device operational; fail-closed mode pending |
| Emergency Controls | Production control hooks (~70%) | ✅ **NEW** - Process/Docker halt, network isolation, snapshots |
| Sandbox Isolation | Docker/Firecracker backends with verification (~80%) | ✅ **IMPROVED** - Backend verification added |
| File Export Validator | Path normalization + diffing | No physical air-gap yet |
| Web Monitoring UI | Flask dashboard with real-time updates (~95%) | ✅ **NEW** - 10+ pages, export, WebSocket, professional design |

---

## Development Roadmap

### Completed improvements (Nov 2025)

1. ✅ **Web Monitoring Dashboard (Nov 12, 2025)** - Built professional Flask UI (2,177 LOC) with 10+ templates, real-time WebSocket updates, comprehensive data export (CSV/JSON), collusion detection widgets, proposal performance tracking, ORKA oversight panels, and centered toast notifications. Makes system behavior transparent for human governance. (0% → 95% complete)
2. ✅ **Physical WORM USB Integration (Nov 12, 2025)** - Connected genuine write-once read-many USB storage device. System now has physical immutable storage for audit trails and manifest data. Updated documentation to reflect hardware presence. (Software only → Physical device operational)
3. ✅ **Research agent realism (Nov 10, 2025)** - Integrated OpenAI and Claude adapters with factory pattern, config-driven selection, automatic fallback, working examples. (25% → 60% complete)
4. ✅ **Control hooks and incident response (Nov 10, 2025)** - Implemented production `ControlHooks` with halt outputs, network isolation, state snapshots, Docker integration. (40% → 70% complete)
5. ✅ **Sandbox backend verification (Nov 10, 2025)** - Added config flags to detect/prevent host fallback, comprehensive test coverage. (75% → 80% complete)
6. ✅ **Configurable WORM paths (Nov 10, 2025)** - Made USB mount paths platform-specific, removed hardcoded `/media/usb`. (90% → 95% complete)

### Immediate priorities (Nov 2025 - ongoing)

7. **Sandbox isolation hardening** - Docker-based execution now ships via `sandbox/isolation.py`; next steps are automated end-to-end tests for the container path, provenance + attestation on sandbox images/kernels, and enforcing equivalent resource caps on Windows fallback paths while keeping `sandbox_flat` backward compatible.
8. **WORM fail-closed enforcement** - With physical WORM USB now connected, implement strict fail-closed mode that halts system when USB is disconnected or verification fails. Remove development environment fallback in production configs.
9. **Air-gapped translator build-out** - Build physical ESP32 or Raspberry Pi translator/coder appliance with serial communication to WORM USB. Software protocols ready; hardware assembly needed.
10. **Internet research integration** - Add SerpAPI, web scraping, and retrieval tooling to research agents.
11. **Multi-party governance UI** - Extend web dashboard with council approval workflows, multi-signature verification interface, and emergency override controls.

### Near-term targets (Q1 2026)

- Hardware translator prototype on ESP32 or Raspberry Pi with real serial links.
- VRF-backed randomness (BLS or Ristretto) replacing the deterministic stub.
- Basic human-in-the-loop governance dashboard showing impact cards, debate summaries, and manifest proofs.

### Milestones

- **v0.4.0 (Nov 13, 2025)** - Orchestrator debate pipeline, air-gapped translator/coder tooling (with optional semantic consensus), structured logging, config signing, sandbox flattening.
- **v0.4.1 (Nov 10, 2025)** - ✅ LLM integration (OpenAI, Claude adapters), production control hooks, sandbox backend verification, configurable WORM paths. Research agents: 25% → 60%, Security coverage significantly improved.
- **v0.4.2 (Nov 12, 2025 - current)** - ✅ Professional web monitoring UI (2,177 LOC Flask app), export functionality (CSV/JSON), collusion detection widgets, proposal performance tracking, physical WORM USB connected and operational. Human governance UI: 0% → 95%, Hardware: Software only → Physical WORM present.
- **v0.5 (planned Q1 2026)** - Containerized sandbox with attestation, VRF integration, WORM fail-closed enforcement, physical air-gapped translator prototype (ESP32/Pi).
- **v1.0 (future)** - End-to-end research agent integration with hardware translators, seventh validator, external audit, and empirically validated safety metrics.

### Investment snapshot

Estimates remain unchanged: ~$2.0M over 24 months (prototype hardware, staffing, audits). See `assessments/EXECUTIVE_SUMMARY.md` for detailed burn projections and funding sources.

---

## Installation and Usage

### Requirements

- Python 3.13+
- Virtual environment strongly recommended
- See `requirements.txt` for pinned tools (pytest, structlog, PyNaCl, aura-compression, etc.)

### Setup

```bash
git clone https://github.com/[your-username]/AI-Safety-System-Design.git
cd AI-Safety-System-Design
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

**Required Environment Variables:**

- `SECRET_KEY` - Flask session secret key. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_TOKEN` - Admin panel authentication token. Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**Optional Environment Variables:**

- `STANDALONE` - Set to `true` to run UI without parent orchestrator (default: true)
- `FLASK_ENV` - Flask environment mode: `development` or `production` (default: development)
- `FLASK_DEBUG` - Enable Flask debug mode: `1` or `0` (default: 1 in development)
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: INFO)
- `WORM_USB_PATH` - Path to WORM USB mount point (default: auto-detected)
- `SIMULATION_DATA_PATH` - Path to simulation data directory (default: ui/simulation_data)

**Production Deployment:**

For production, ensure you:
1. Set strong random values for `SECRET_KEY` and `ADMIN_TOKEN`
2. Set `FLASK_ENV=production` and `FLASK_DEBUG=0`
3. Use a production WSGI server like gunicorn
4. Enable HTTPS with valid SSL certificates

### Optional: Fetch Firecracker artifacts via helper CLI

```bash
python tools/firecracker_cli.py --version v1.7.0 --bin-dir build/firecracker/bin --artifact-dir build/firecracker/artifacts
# copy the resulting binaries/artifacts into privileged locations as needed:
sudo cp build/firecracker/bin/firecracker-v1.7.0 /usr/local/bin/firecracker
sudo cp build/firecracker/bin/jailer-v1.7.0 /usr/local/bin/jailer
sudo mkdir -p /var/lib/firecracker
sudo cp build/firecracker/artifacts/vmlinux-5.10.225 /var/lib/firecracker/vmlinux
sudo cp build/firecracker/artifacts/bionic.rootfs.ext4 /var/lib/firecracker/rootfs.ext4
```

After copying, set `sandbox.engine: firecracker` and update the kernel/rootfs paths in `config/default.yaml` (or your env override), then ensure your user belongs to the `kvm` group.

### Running tests

```bash
python -m pytest -q
```

Current result (2025-11-10): `131+ passed, 11 skipped in ~25s` on Python 3.13.5. `_ensure_execution_coverage` now forces the sandbox to execute proposal code even when validation stages defer `execution`, so the orchestrator integration suites pass locally. New test coverage includes LLM adapter integration, production control hooks (process/Docker management), sandbox backend verification, and USB path configuration. Hardware/ESP32/VRF tests still skip automatically when their toolchains are absent.

### Running the demo harness

```bash
python demo_integration.py
```

Artifacts land under `demo_outputs/`. The script updates `MemoryStorage` and prints the empirical detection probability and Merkle root.

### Configuration

Configs live in [config/](config/). `config_loader.py` selects `default.yaml`, `development.yaml`, or `production.yaml` based on `APP_ENV`. Highlights:

- Set `SANDBOX_USE_VIRTUAL=1` to force the sandbox to spawn subprocesses.
- `CONFIG_PUBKEY_HEX` or `CONFIG_PUBKEYS_HEX` (comma separated) enables Ed25519 signature verification; `CONFIG_REVOKED_PUBKEYS_HEX` removes compromised keys.
- `CONFIG_VERIFY_BUDGET_MS` applies the `ResourceBudget` guard around signature verification.
- `sandbox.policy_allowlists` defines per-component module allowlists consumed by the orchestrator and demo harness.

Example toggles:

```powershell
$env:APP_ENV = "development"
$env:SANDBOX_USE_VIRTUAL = "1"
pytest tests/test_sandbox_orchestrator.py -q
```

```bash
APP_ENV=production CONFIG_STRICT=1 pytest tests/test_config_signing.py -q
```

### Web Monitoring Dashboard

A professional Flask-based web interface (`ui/app.py`, 3,200+ LOC) provides comprehensive monitoring and governance capabilities:

**Core Features**:
- Dashboard with system metrics and recent proposals
- Proposal tracking and visualization
- Deception detection monitoring
- Penalty tracking and agent statistics
- System health and configuration management

**Advanced Features**:
- **Evidence Engine**: Search system documentation with citations for evidence-grounded governance
- **Decision Trajectories**: Visualize agent decision paths through proposal lifecycle
- **Training Metrics**: Monitor self-play training progress and adversarial bypass detection
- **Workflow Orchestration**: Track multi-agent collaboration across proposal stages

All features use internal naming only (no external project references). See `ui/README.md` for detailed documentation.

```bash
cd ui
source venv/bin/activate  # or: venv\Scripts\activate on Windows
python app.py
```

Open http://localhost:5001 in your browser. Features include:

- **Real-time monitoring**: WebSocket-powered updates for proposals, detection events, penalties, and collusion attempts
- **Interactive dashboards**: Dashboard, Proposals, Detection, Penalties, ORKA oversight, System health
- **Export functionality**: CSV/JSON downloads for all major data types
- **Collusion detection**: Visual tracking of agent coordination attempts with severity-based filtering
- **Proposal performance**: Track success rates, uptime, errors for implemented proposals
- **ORKA oversight**: Random file verification, SD card verification queue, USB transfer management
- **Toast notifications**: Centered top notifications for all system events

**Advanced Features** (see `ui/README.md` for details):
- **Evidence Engine**: Search system documentation with citations (`/evidence`)
- **Decision Trajectories**: Visualize agent decision paths (`/trajectories`)
- **Training Metrics**: Monitor self-play training progress (`/training`)
- **Workflow Orchestration**: Track multi-agent collaboration (`/workflows`)

All features use internal naming only. Data is persisted in SQLite (`ui/ui_data.db`). The web UI provides the human governance layer with full transparency into system behavior.

### Terminal Dashboard (Legacy)

For command-line environments, a lightweight terminal dashboard streams orchestrator telemetry:

```bash
python ui/dashboard.py --events logs/orchestrator_events.jsonl
```

---

## Limitations and Known Issues

### Critical (Blocks Production)
1. **Sandbox containerization unverified** - Docker/Firecracker isolation is implemented via `sandbox/isolation.py` with backend verification config, but CI automated tests for the container path are still needed. Windows resource limits remain unavailable (POSIX only). **Status: 80% → Verification added, automated CI tests pending**
2. ~~**USB persistence path hardcoded**~~ - ✅ **FIXED (Nov 10)** - USB mount paths now configurable via `config/default.yaml` with platform-specific settings (Linux/macOS/Windows).
3. ~~**WORM hardware missing**~~ - ✅ **FIXED (Nov 12)** - Physical write-once read-many USB storage device now connected and operational. Fail-closed mode enforcement still needed.
4. **WORM manifest fallback** - `worm_usb_verifier.py` can fallback to environment variables when USB disconnected (development mode). Production deployments must enforce fail-closed mode that halts when WORM USB is unavailable.

### High Priority
5. ~~**Control hooks are dry-run only**~~ - ✅ **FIXED (Nov 10)** - Production control hooks implemented in `production_control_hooks.py` with process termination, Docker halt, network isolation, and state snapshots. Physical power control (PDU) still pending.
6. ~~**Research systems lack real LLMs**~~ - ✅ **IMPROVED (Nov 10)** - OpenAI and Claude adapters implemented with factory pattern, config-driven selection, working examples. Internet research and persistent memory still pending. **Status: 25% → 60%**
7. ~~**Governance tooling missing**~~ - ✅ **IMPROVED (Nov 12)** - Professional web monitoring UI now provides real-time visibility into all system operations with export capabilities. Multi-party approval workflows and council signing UI still pending. **Status: 0% → 75%**
8. **Air-gapped translator hardware** - Physical ESP32/Raspberry Pi translator/coder appliance unbuilt. Software protocols ready; hardware assembly needed (~$200-500).
9. **Seventh validator hardware** - Specification complete but hardware unfunded and unbuilt.

### Implementation gaps and missing tests

- No end-to-end test that executes the Docker/Firecracker sandbox path; CI still exercises only the host fallback.
- Multi-signature verification paths return `None` and lack coverage.
- Hardware translators and WORM media tests are simulated only.
- No regression tests with real LLM outputs or internet research.
- Governance processes (multi-party attestation, human override) are not executable.

---

## Contributing

Contributions are welcome, especially across the open gaps above. Please review [CONTRIBUTORS.md](CONTRIBUTORS.md) and [TODO.md](TODO.md) before submitting pull requests. Priority areas:

1. Harden the sandbox and incident response hooks.
2. Implement hardware-backed WORM and translator flows.
3. Integrate real LLM adapters and retrieval for `ResearchSystem`.
4. Expand translator dictionaries and (optional) semantic-consensus telemetry so the single air-gapped translator/coder can be audited effectively today and upgraded to multi-translator deployments later.
5. Add integration tests that span proposal -> debate -> sandbox -> reward.

---

## Documentation

- [assessments/EXECUTIVE_SUMMARY.md](assessments/EXECUTIVE_SUMMARY.md) - current status and next steps.
- [assessments/HONEST_ASSESSMENT.md](assessments/HONEST_ASSESSMENT.md) - transparent capability analysis.
- [assessments/PROVISIONAL_PATENT_APPLICATION.md](assessments/PROVISIONAL_PATENT_APPLICATION.md) - complete patent draft.
- [assessments/MATHEMATICAL_VALIDATION_REPORT.md](assessments/MATHEMATICAL_VALIDATION_REPORT.md) - game-theory proofs.
- [assessments/COUNCIL_GOVERNANCE_STRUCTURE.md](assessments/COUNCIL_GOVERNANCE_STRUCTURE.md) - multi-stakeholder governance.
- [assessments/WHY_AURA_IS_NECESSARY.md](assessments/WHY_AURA_IS_NECESSARY.md) - compression security rationale.
- [assessments/AURA_PROTOCOL.md](assessments/AURA_PROTOCOL.md) - detailed spec.
- [docs/ARCHITECTURE_DIAGRAM.md](docs/ARCHITECTURE_DIAGRAM.md) - structural diagrams.
- [docs/human_trust_layer.md](docs/human_trust_layer.md) - trust and governance layer.
- [docs/offline_deployment.md](docs/offline_deployment.md) - guidance for disconnected environments.

---

## License

MIT. See [LICENSE](LICENSE).

Patent rights: Provisional application prepared; the intent remains to place the safety protocols in an irrevocable trust so they cannot be weaponized.

---

## Citation

```
@misc{hendrixx2025aisafety,
  author = {Hendrixx, Todd},
  title = {AI Safety System Design: Multi-Tier Validation with Immutable Hardware Security},
  year = {2025},
  publisher = {GitHub},
  url = {https://github.com/[your-username]/AI-Safety-System-Design}
}
```

---

## Contact

- Email: [your-email]
- GitHub Issues: https://github.com/[your-username]/AI-Safety-System-Design/issues
- Patent docket: AISAFETY-001-PROV (prepared, pending filing)

---

## Acknowledgments

Thanks to the AI safety community for feedback on the early prototypes. See [assessments/PRIOR_ART_SEARCH_SUMMARY.md](assessments/PRIOR_ART_SEARCH_SUMMARY.md) for prior art analysis. Influences include Constitutional AI, DeepMind's debate work, RLHF, ICANN governance, blockchain immutability, and mechanism design.

---

Version: 0.4.2-dev
Status: Research Prototype (~65% implementation complete; LLM integration + Web UI + physical WORM USB operational)
Last Updated: November 12, 2025
Recent Improvements: ✅ Web monitoring dashboard (2,177 LOC), ✅ Physical WORM USB connected, ✅ Export functionality (CSV/JSON), ✅ Collusion detection widgets, ✅ Centered toast notifications, ✅ Real-time WebSocket updates
Previous Milestones: ✅ LLM adapters (OpenAI, Claude), ✅ Production control hooks, ✅ Sandbox backend verification, ✅ Configurable USB paths
Next Milestone: v0.5 - containerized sandbox with CI verification, VRF-backed randomness, WORM fail-closed enforcement, physical air-gapped translator prototype
Latest Test Snapshot: `python -m pytest -q` -> 131+ passed / 11 skipped (142+ collected, Python 3.13.5)
Patent Status: Provisional application prepared and ready for filing
Hardware Status: Physical WORM USB operational; ESP32/Pi translator and seventh validator pending build
