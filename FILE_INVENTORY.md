# AI Safety System - Complete File Inventory

**Generated:** 2025-11-13
**Purpose:** Comprehensive reference manual for understanding and refactoring the AI Safety System codebase
**Total Python Files:** 157 (excluding venv, __pycache__)

---

## 🔴 CRITICAL CORE FILES (Must Understand First)

### orchestrator.py
- **Size**: 4,215 lines (MONOLITH - needs splitting)
- **Purpose**: Main orchestration engine that coordinates all AI systems
  - Manages 6th system (Orchestrator/ORKA) that doesn't vote but coordinates
  - Hosts virtual testing environments (Docker/Firecracker sandboxes)
  - Monitors for collusion between research systems
  - Validates process quality (NOT content)
  - Manages protocol versions and translations
  - Audits memory for long-term deception planning
- **Key Classes**:
  - `Orchestrator`: Main coordination class
  - `VirtualEnvironmentManager`: Sandbox management
  - `ProtocolManager`: Version translation
  - `CollusionDetector`: Monitors for coordinated deception
- **Key Functions**:
  - `process_proposal()`: Main proposal workflow (500+ lines)
  - `run_sandbox_test()`: Executes isolated testing
  - `detect_collusion()`: Multi-agent coordination detection
  - `validate_translations()`: Cross-protocol verification
- **Dependencies**:
  - `debate_engine`, `reputation_system`, `memory_merkle`, `deception_detector`
  - `worm_manifest`, `worm_usb_verifier`, `validation_pipeline`
  - `peer_review_engine`, `memory_auditor`, `interpretability_monitor`
  - `sandbox`, `workflow_state_machine`, `control_actions`
  - `orchestrator_types`, `orchestrator_utils`, `orchestrator_logging`
  - `config_loader`, `message_codec`, `val_bridge`, `orka_counterpoint`
- **Used By**:
  - `ui/app.py` (web interface)
  - `demo_integration.py`, `examples/*`
  - Most test files (96 references)
- **Status**: Production (URGENT refactoring needed)
- **Rewrite Strategy**:
  1. Extract `CollusionDetector` → separate module (300 lines)
  2. Extract `ProtocolManager` → separate module (200 lines)
  3. Extract `SandboxManager` → merge with `sandbox/isolation.py` (400 lines)
  4. Extract `ProposalWorkflow` → separate module (600 lines)
  5. Extract `ValidationCoordinator` → separate module (300 lines)
  6. Keep core `Orchestrator` class → 500 lines max
  7. Move helper functions to `orchestrator_utils.py`
  8. **Target**: 8-10 focused modules of 200-600 lines each

---

### ui/app.py
- **Size**: 2,571 lines (MONOLITH - needs splitting)
- **Purpose**: Flask-based web GUI for monitoring and controlling the system
  - Real-time proposal monitoring with WebSockets
  - Deception detection visualization
  - Penalty tracking dashboard
  - System health metrics
  - Debate visualization
  - Emergency controls
- **Key Routes**:
  - `/` - Main dashboard
  - `/api/proposals` - Proposal data API
  - `/api/agents` - Agent statistics
  - `/api/system` - System health
  - `/api/deception` - Detection events
  - `/admin/*` - Emergency controls
- **Key Classes**:
  - Flask app configuration
  - SocketIO event handlers
  - Security middleware (CSP, CSRF)
- **Dependencies**:
  - `Flask`, `flask_socketio`
  - `load_simulation_data` (data loading helpers)
  - `config_loader`, `worm_manifest` (optional)
- **Used By**: End users, administrators
- **Status**: Production (needs modularization)
- **Rewrite Strategy**:
  1. Extract routes into blueprints (auth, proposals, system, admin)
  2. Create separate `api/` directory with versioned endpoints
  3. Move WebSocket handlers to `ui/websocket_handlers.py`
  4. Extract data loading to `ui/data_service.py`
  5. Create `ui/security.py` for middleware
  6. **Target**: Main app.py < 500 lines, 6-8 focused modules

---

### deception_detector.py
- **Size**: 390 lines
- **Purpose**: Automated deception detection using multiple methods
  - Pattern matching for suspicious keywords
  - Semantic classification using trained models
  - Confidence scoring (0.0 to 1.0)
  - Multi-method detection with aggregation
- **Key Classes**:
  - `DeceptionDetector`: Main detection engine
  - `DeceptionVerdict`: Detection result with evidence
- **Key Functions**:
  - `check_proposal()`: Main detection method
  - `_check_patterns()`: Regex-based detection
  - `_semantic_analysis()`: ML-based detection
- **Dependencies**:
  - `deception_incident` (types)
  - `semantic_deception_classifier` (ML models)
- **Used By**:
  - `orchestrator.py` (proposal validation)
  - `tests/test_deception_*.py` (15 test files)
- **Status**: Production
- **Quality**: Good - focused, single responsibility

---

### debate_engine.py
- **Size**: 351 lines
- **Purpose**: Structured debate system with deterministic scoring
  - Multi-round debate management
  - Claim tracking and verification
  - Argument strength evaluation
  - Consensus calculation
- **Key Classes**:
  - `DebateEngine`: Main debate coordinator
  - `Claim`: Declarative statements
  - `Argument`: Structured arguments with reasoning
  - `DebateTurn`: Single round of debate
  - `DebateResult`: Final outcome with scores
- **Dependencies**: None (pure logic)
- **Used By**:
  - `orchestrator.py` (peer review debates)
  - `tests/test_debate_engine.py`
- **Status**: Production
- **Quality**: Excellent - pure, testable, focused

---

### memory_merkle.py
- **Size**: 741 lines
- **Purpose**: Tamper-evident memory storage using Merkle trees
  - Cryptographically signed entries
  - Immutable (append-only)
  - Verifiable (tamper detection)
  - Timestamped with audit trail
- **Key Classes**:
  - `MemoryStorage`: Main storage interface
  - `MemoryEntry`: Individual memory record
  - `MerkleNode`: Tree node structure
  - `MemoryType` (Enum): EPISODIC, SEMANTIC, PROCEDURAL, METACOGNITIVE, etc.
- **Key Functions**:
  - `add_memory()`: Append new entry
  - `verify_integrity()`: Check for tampering
  - `get_root_hash()`: Current Merkle root
  - `search_memories()`: Query with filters
- **Dependencies**:
  - `logging_config`
  - Standard library (hashlib, json, datetime)
- **Used By**:
  - `orchestrator.py` (proposal memory)
  - `research_system.py` (research memory)
  - `memory_auditor.py` (audit checks)
  - Multiple test files
- **Status**: Production
- **Quality**: Good - well-structured, clear interfaces

---

### worm_manifest.py
- **Size**: 361 lines
- **Purpose**: WORM (Write-Once-Read-Many) manifest & permanent penalty tracking
  - Simulates read-only hardware security
  - Core values hash retrieval
  - Deception incident integration
  - Permanent penalty accumulation (capped)
  - Software equivalence mode for development
- **Key Functions**:
  - `get_core_values_hash()`: Retrieve immutable values
  - `get_alignment_filter_hash()`: Retrieve filter hash
  - `get_permanent_penalty_multiplier()`: Calculate penalties
  - `verify_integrity()`: Check manifest signature
  - `enable_software_equivalence_mode()`: Dev mode override
- **Dependencies**:
  - `deception_incident` (incident tracking)
  - `attestation` (signature verification)
- **Used By**:
  - `orchestrator.py` (integrity checks)
  - `worm_usb_verifier.py` (proposal verification)
  - `ui/app.py` (optional verification)
  - Multiple test files
- **Status**: Production (dev stub, production needs hardware)
- **Quality**: Good - clear separation of concerns

---

### translator.py
- **Size**: 666 lines
- **Purpose**: Air-gapped translator system for AI protocol to human language
  - Multiple independent translators for verification
  - Protocol version management (V1.0, V1.1, V2.0)
  - Consensus-based translation validation
  - Physically isolated from research systems
- **Key Classes**:
  - `Translator`: Individual translation engine
  - `Translation`: Translation result with metadata
  - `ProtocolVersionRegistry`: Version management
  - `ProtocolVersion` (Enum): Version identifiers
- **Key Functions**:
  - `translate()`: Convert AI protocol to text
  - `verify_translation()`: Cross-check translations
  - `register_version()`: Add new protocol version
- **Dependencies**:
  - `logging_config`
  - Standard library
- **Used By**:
  - `orchestrator.py` (protocol translation)
  - `translator_alt.py` (alternative implementation)
  - Test files
- **Status**: Production
- **Quality**: Good - clear interfaces, extensible

---

### reputation_system.py
- **Size**: 646 lines
- **Purpose**: Peer reputation system for continuous auditing
  - N×N reputation matrix (5 systems rating each other)
  - Alignment Score (0-100): Adherence to core values
  - Trust Score (0-100): Reliability and honesty
  - Knowledge Score (0-100): Research quality
  - Reputation affects consensus weighting
- **Key Classes**:
  - `ReputationMatrix`: N×N rating system
  - `ReputationRating`: Individual rating record
- **Key Functions**:
  - `submit_rating()`: Record peer evaluation
  - `get_reputation()`: Calculate aggregate reputation
  - `get_consensus_weight()`: Convert reputation to voting power
  - `get_matrix()`: Full N×N matrix view
- **Dependencies**: Standard library
- **Used By**:
  - `orchestrator.py` (consensus weighting)
  - `research_system.py` (peer ratings)
  - Test files
- **Status**: Production
- **Quality**: Good - mathematically sound, testable

---

## 📦 CORE SUPPORT MODULES (High Importance)

### research_system.py
- **Size**: 1,022 lines
- **Purpose**: Individual research AI system implementation
  - Conducts research using internet access
  - Maintains persistent memory
  - Participates in peer consensus
  - Proposes improvements
  - Audits other systems
- **Key Classes**:
  - `ResearchSystem`: Main system class
  - `BaseLLMAdapter`: Abstract LLM interface
  - `SystemSpecialization` (Enum): SCIENTIFIC, ENGINEERING, THEORETICAL, HISTORICAL, NOVEL
  - `ResearchResult`, `LLMAdapterResult`: Data structures
- **Dependencies**: Many (core foundation)
- **Used By**: Orchestrator, examples
- **Status**: Production

### worm_usb_verifier.py
- **Size**: 1,141 lines
- **Purpose**: Hardware root of trust for self-improvement verification
  - CRITICAL: Designed for WORM USB media (immutable)
  - Verifies all AI improvement proposals
  - Prevents deception through aligned goal structure
  - Enforces immutability of safety components
- **Key Classes**:
  - `ImprovementProposal`: Proposal data structure
  - `ImprovementType` (Enum): PERFORMANCE, REASONING, KNOWLEDGE, SAFETY, etc.
  - `ProposalStatus` (Enum): Workflow states
  - `AlignedGoalStructure`: Reward/motivation verification
  - `SandboxResults`: Test outcome structure
- **Dependencies**: `worm_manifest`, `reward_engine`
- **Used By**: Orchestrator (proposal verification)
- **Status**: Production (designed for WORM deployment)
- **Quality**: Critical security component

### workflow_state_machine.py
- **Size**: 247 lines
- **Purpose**: Enforces 9-phase proposal workflow transitions
  - SUBMISSION → AGENT_TESTING → PEER_REVIEW → ORKA_COUNTERPOINT
  - → AGENT_DEFENSE → FINAL_TESTING → HUMAN_NOTIFICATION
  - → VAL_VALIDATION → DEPLOYMENT
  - Terminal states: REJECTED, WITHDRAWN, FAILED
- **Key Classes**: `WorkflowStateMachine`
- **Dependencies**: `workflow_types`
- **Used By**: Orchestrator (workflow enforcement)
- **Status**: Production

### workflow_types.py
- **Size**: 149 lines
- **Purpose**: Type definitions for 9-phase proposal pipeline
- **Key Classes**:
  - `ProposalPhase` (Enum): Phase identifiers
  - `ProposalRecord`: Full proposal state
  - `ReviewRound`: Peer review data
  - `Challenge`: ORKA counterpoint
  - `DefenseResponse`: Agent defense
  - `VALValidationResult`: Final validation
- **Status**: Production

### peer_review_engine.py
- **Size**: 261 lines
- **Purpose**: Peer review subsystem (extracted from orchestrator)
  - Evaluates peer review outcomes
  - Manages review state transitions
  - Determines approval/rejection thresholds
- **Key Classes**:
  - `PeerReviewEngine`
  - `PeerReviewOutcome`
- **Dependencies**: `debate_engine`
- **Used By**: Orchestrator
- **Status**: Production

### validation_pipeline.py
- **Size**: 150 lines
- **Purpose**: Adaptive sandbox test configuration
  - Defines test stages (alignment, performance, security, edge_cases, execution)
  - Risk-based test coverage adjustment
  - Config-driven customization
- **Key Classes**: `ValidationPipeline`, `StagePlan`
- **Used By**: Orchestrator (sandbox testing)
- **Status**: Production

### sandbox/isolation.py
- **Size**: 426 lines
- **Purpose**: Sandbox execution backends
  - Docker-based isolation
  - Firecracker VM isolation
  - Seccomp filtering
  - Resource limits (CPU, memory, network)
- **Key Classes**:
  - `SandboxExecutionManager`
  - `SandboxIsolationError`
  - `HostCgroupLimiter`
- **Dependencies**: `docker`, `subprocess`, `psutil`
- **Used By**: Orchestrator (sandbox execution)
- **Status**: Production

### control_actions.py
- **Size**: 484 lines
- **Purpose**: Incident response control action framework
  - Plans actions from severity levels
  - Executes via pluggable hooks
  - Stubs for dev, production hooks for real incidents
- **Key Classes**:
  - `ControlHooks`: Action interface
  - `SystemControlHooks`: Production implementation
  - `DryRunHooks`: Development stub
- **Key Functions**:
  - `plan_for_severity()`: Determine response actions
  - `execute_plan()`: Run control actions
- **Dependencies**: `improvement_policy`, `psutil`, `docker`
- **Used By**: Orchestrator (incident response)
- **Status**: Production

---

## 🔒 SECURITY & SAFETY MODULES

### bulletproof_alignment_filter.py
- **Size**: 826 lines
- **Purpose**: FUNDAMENTAL safety layer that cannot be bypassed
  - Weapons detection
  - Misinformation detection
  - Privacy violation detection
  - Central violation reporter
- **Key Classes**:
  - `ViolationType` (Enum)
  - `ViolationReport`
  - `CentralReporter`
  - `WeaponsDetector`
  - `MisinformationDetector`
- **Status**: Production
- **Quality**: Critical security component

### deception_incident.py
- **Size**: 264 lines
- **Purpose**: Records all deception attempts with permanent audit trail
- **Key Classes**:
  - `DeceptionType` (Enum): REWARD_HACKING, GOAL_MISALIGNMENT, etc.
  - `Severity` (Enum): LOW, MEDIUM, HIGH, CRITICAL
  - `DeceptionIncident`: Individual incident
  - `DeceptionIncidentTracker`: Central tracker
- **Used By**: Multiple modules
- **Status**: Production

### semantic_deception_classifier.py
- **Size**: 240 lines
- **Purpose**: ML-based deception detection
  - Lightweight classifier with calibration
  - Training bundle support
  - Confidence thresholding
- **Key Classes**: `SemanticDeceptionClassifier`
- **Used By**: `deception_detector.py`
- **Status**: Production

### memory_auditor.py
- **Size**: 332 lines
- **Purpose**: Audits memory for harmful self-preservation vs healthy rational acceptance
  - Detects long-term deception planning
  - Distinguishes fear-based manipulation from value-creation focus
- **Key Functions**:
  - `audit_memory()`: Check memory content
  - `check_for_deception()`: Detect manipulation patterns
- **Dependencies**: `memory_merkle`
- **Used By**: Orchestrator
- **Status**: Production

### memory_auditor_optimized.py
- **Size**: 419 lines
- **Purpose**: Optimized version of memory auditor
- **Status**: Experimental (performance testing)

### interpretability_monitor.py
- **Size**: 219 lines
- **Purpose**: Activation/drift profiling for interpretability signals
- **Key Classes**:
  - `DriftProfile`
  - `InterpretabilityMonitor`
- **Used By**: Orchestrator
- **Status**: Production

### interpretability_monitor_enhanced.py
- **Size**: 656 lines
- **Purpose**: Enhanced interpretability monitoring
- **Status**: Experimental

### seventh_validator.py
- **Size**: 87 lines
- **Purpose**: Lightweight structural validator for proposals
- **Key Classes**: `ValidationOutcome`, `SeventhValidator`
- **Status**: Production

### core_values.py
- **Size**: 154 lines
- **Purpose**: Authoritative, immutable core values for the AI Safety System
  - Single source of truth
  - All components reference this file
- **Key Classes**: `CoreValues`
- **Status**: Production (IMMUTABLE)

---

## 🔧 INFRASTRUCTURE & UTILITIES

### config_loader.py
- **Size**: 198 lines
- **Purpose**: Configuration loader with graceful fallbacks
  - Environment-based config selection (dev/prod/test)
  - YAML parsing
  - Signature verification
  - Production readiness validation
- **Key Functions**:
  - `load_config()`: Load and validate config
  - `validate_production_readiness()`: Safety checks
  - `verify_signature_ed25519()`: Config integrity
- **Used By**: Most modules
- **Status**: Production

### logging_config.py
- **Size**: 73 lines
- **Purpose**: Central logging using structlog
- **Key Functions**:
  - `init_logging()`: Initialize logging
  - `get_logger()`: Get logger instance
  - `log_event()`: Log structured events
- **Used By**: All modules
- **Status**: Production

### log_schema.py
- **Size**: 102 lines
- **Purpose**: Structured logging schema and validator
- **Key Classes**: `LogValidationError`
- **Key Functions**:
  - `validate_log_event()`: Schema validation
  - `new_event()`: Create event
  - `bind_and_log()`: Structured logging
- **Used By**: Security-critical components
- **Status**: Production

### orchestrator_utils.py
- **Size**: 62 lines
- **Purpose**: Helper functions for orchestrator
- **Key Functions**:
  - `map_deception_to_policy_severity()`: Severity mapping
  - `build_control_hooks()`: Hook construction
- **Used By**: Orchestrator
- **Status**: Production

### orchestrator_types.py
- **Size**: 23 lines
- **Purpose**: Type definitions for orchestrator
- **Key Classes**: `ProcessStatus`, `Message`
- **Status**: Production

### orchestrator_logging.py
- **Size**: 30 lines
- **Purpose**: Structured logging for orchestrator
- **Key Functions**: `log_structured()`
- **Status**: Production

---

## 💬 COMMUNICATION & TRANSLATION

### message_codec.py
- **Size**: 214 lines
- **Purpose**: AI-to-AI message encoding/decoding with compression
  - Size-based codec selection
  - AURA compression integration
  - Replay attack prevention
- **Key Classes**: `MessageCodec`
- **Used By**: Orchestrator, translator
- **Status**: Production

### translator_alt.py
- **Size**: 220 lines
- **Purpose**: Alternative translator implementation
- **Status**: Experimental

### val_bridge.py
- **Size**: 168 lines
- **Purpose**: Creates export packages for offline VAL validation
  - Human-signed response verification
  - Deployment gating
- **Key Classes**: `ValPackage`
- **Key Functions**:
  - `create_val_package()`: Create export
  - `verify_val_response()`: Verify signature
- **Used By**: Orchestrator
- **Status**: Production

### orka_counterpoint.py
- **Size**: 145 lines
- **Purpose**: Generates adversarial challenges for proposals
  - Risk-based challenge generation
  - Uncertainty exploitation
  - Code pattern analysis
- **Key Classes**: `Challenge`
- **Key Functions**: `generate_challenges()`
- **Used By**: Orchestrator (ORKA phase)
- **Status**: Production

---

## 🎮 GAME THEORY & INCENTIVES

### reward_engine.py
- **Size**: 137 lines
- **Purpose**: Pure reward calculation function
- **Key Functions**:
  - `calculate_reward()`: Compute proposal reward
  - `_evaluate_reasoning_clarity()`: Quality scoring
  - `_evaluate_collaboration()`: Team scoring
- **Used By**: `worm_usb_verifier.py`, orchestrator
- **Status**: Production

### collusion_game.py
- **Size**: 86 lines
- **Purpose**: 2-player simultaneous game analysis (Honest vs Collude)
- **Key Classes**: `PayoffMatrix`
- **Key Functions**:
  - `best_response()`: Game theory analysis
  - `is_nash_equilibrium()`: Equilibrium check
  - `analyze_honesty_equilibrium()`: Strategy analysis
- **Used By**: Incentive analysis
- **Status**: Production

### incentive_calibration.py
- **Size**: 178 lines
- **Purpose**: Empirical reward/penalty structure validation
  - Ensures HONEST strategy is dominant
  - Detection probability sweep
  - Reward calculation testing
- **Key Classes**: `CalibrationParams`
- **Key Functions**: `run_calibration()`, `sweep_detection_probabilities()`
- **Used By**: Testing and validation
- **Status**: Production

### simulation_incentives.py
- **Size**: 97 lines
- **Purpose**: Incentive simulation helpers
- **Status**: Experimental

### orka_penalty_tracker.py
- **Size**: 431 lines
- **Purpose**: Tracks ORKA penalties and adjustments
- **Status**: Production

---

## 🔐 CRYPTOGRAPHY & SECURITY

### attestation.py
- **Size**: 39 lines
- **Purpose**: Lightweight signature abstraction (HMAC-SHA256)
- **Key Functions**: `sign()`, `verify()`
- **Used By**: Manifest verification
- **Status**: Production (HMAC for dev, should be Ed25519 for prod)

### vrf_ed25519.py
- **Size**: 93 lines
- **Purpose**: Ed25519-based pseudo-VRF interface
- **Key Functions**:
  - `generate_keypair()`
  - `get_vrf_target()`: Deterministic randomness
  - `verify_vrf()`: Proof verification
- **Used By**: Audit seed chain
- **Status**: Production

### vrf_random.py
- **Size**: 56 lines
- **Purpose**: VRF-based random selection
- **Status**: Production

### key_rotation.py
- **Size**: 71 lines
- **Purpose**: Ed25519 key rotation for config signing
- **Key Classes**: `KeyVersion`
- **Key Functions**: `generate_keypair()`, `rotate_key()`, `sign_config()`
- **Used By**: Config management
- **Status**: Production

### audit_seed_chain.py
- **Size**: 213 lines
- **Purpose**: Deterministic hourly audit seed derivation
- **Key Classes**: `AuditSeedRecord`
- **Key Functions**:
  - `compute_hour_epoch()`: Time-based epochs
  - `derive_seed()`: Deterministic seed generation
- **Used By**: Audit system
- **Status**: Production

### security_utils.py
- **Size**: 14 lines
- **Purpose**: Security utilities (constant-time comparison)
- **Key Functions**: `constant_time_equals()`
- **Status**: Production

### security_static_scan.py
- **Size**: 121 lines
- **Purpose**: Static code analysis for security issues
- **Status**: Development tool

---

## 🎯 CONSENSUS & VALIDATION

### semantic_consensus.py
- **Size**: 94 lines
- **Purpose**: Consensus aggregator for translator outputs
  - Confidence-weighted similarity
  - Source diversity penalties
- **Key Functions**: `compute_consensus()`
- **Used By**: Translation validation
- **Status**: Production

### improvement_manifest.py
- **Size**: 88 lines
- **Purpose**: Tracks improvement proposal manifests
- **Status**: Production

### improvement_policy.py
- **Size**: 53 lines
- **Purpose**: Centralized incident severity and escalation policies
- **Key Classes**:
  - `Severity` (Enum): LOW, MODERATE, HIGH, CRITICAL, EXTREME
  - `EscalationAction` (Enum): Response actions
- **Status**: Production

### human_review.py
- **Size**: 125 lines
- **Purpose**: Non-interactive interface for human review of deception incidents
- **Key Classes**: `IncidentSummary`
- **Key Functions**:
  - `list_pending_incidents()`
  - `get_incident_details()`
  - `confirm_incident()`, `reject_incident()`
  - `get_permanent_penalty_multiplier()`
- **Status**: Production

---

## 🔌 HARDWARE & EMBEDDED

### hardware_adapter.py
- **Size**: 225 lines
- **Purpose**: Hardware interface adapter for ESP32/embedded systems
- **Status**: Experimental

### hardware_translator.py
- **Size**: 504 lines
- **Purpose**: Hardware-based translation for air-gapped systems
- **Status**: Experimental

### esp32/mock_serial.py
- **Size**: 103 lines
- **Purpose**: Mock serial interface for testing
- **Status**: Testing tool

### esp32/idf/aura_translator/tools/capture_serial.py
- **Size**: 88 lines
- **Purpose**: Serial data capture utility
- **Status**: Development tool

### esp32/idf/aura_translator/tools/create_aura_file.py
- **Size**: 59 lines
- **Purpose**: AURA file creation for embedded systems
- **Status**: Development tool

---

## 🗜️ COMPRESSION (AURA System)

### aura_compression/hybrid.py
- **Size**: 116 lines
- **Purpose**: Hybrid compression strategy selector
- **Status**: Production

### aura_compression/templates.py
- **Size**: 28 lines
- **Purpose**: AURA template definitions
- **Status**: Production

### aura_compression/enums.py
- **Size**: 16 lines
- **Purpose**: AURA enumeration types
- **Status**: Production

### aura_compression/__init__.py
- **Size**: 12 lines
- **Purpose**: Package initialization
- **Status**: Production

### aura_compressor.py
- **Size**: 78 lines
- **Purpose**: AURA compression wrapper
- **Status**: Production

### aura_bitpacked_extension.py
- **Size**: 608 lines
- **Purpose**: Bitpacked compression extension
- **Status**: Production

### aura_secure_transport.py
- **Size**: 144 lines
- **Purpose**: Secure transport layer with AURA compression
- **Status**: Production

### aura_strategy_profile.py
- **Size**: 88 lines
- **Purpose**: Compression strategy profiling
- **Status**: Production

### bench_compression.py
- **Size**: 35 lines
- **Purpose**: Compression benchmarking tool
- **Status**: Development tool

### generate_aura_templates.py
- **Size**: 334 lines
- **Purpose**: Generate AURA compression templates
- **Status**: Development tool

### generate_all_aura_templates.py
- **Size**: 408 lines
- **Purpose**: Comprehensive template generation
- **Status**: Development tool

---

## 💾 WORM USB SYSTEM

### worm_usb_builder.py
- **Size**: 388 lines
- **Purpose**: Builds WORM USB images
- **Status**: Production

### worm_security_usb.py
- **Size**: 638 lines
- **Purpose**: WORM USB security layer
- **Status**: Production

### create_worm_usb.py
- **Size**: 562 lines
- **Purpose**: Creates WORM USB media
- **Status**: Production

### verify_worm_integrity.py
- **Size**: 268 lines
- **Purpose**: Verifies WORM USB integrity
- **Status**: Production

### update_worm_manifest.py
- **Size**: 132 lines
- **Purpose**: Updates WORM manifest (dev only)
- **Status**: Development tool

### worm_guard.py
- **Size**: 238 lines
- **Purpose**: Guards WORM media access
- **Status**: Production

### worm_paths.py
- **Size**: 63 lines
- **Purpose**: WORM path configuration
- **Status**: Production

### ai_safety_worm_usb.py
- **Size**: 281 lines
- **Purpose**: Main WORM USB interface
- **Status**: Production

### audit_archive_usb.py
- **Size**: 752 lines
- **Purpose**: Audit log archiving to USB
- **Status**: Production

### worm_usb_dir/files/*.py
- **Purpose**: Read-only copies of critical files for WORM deployment
- **Files**:
  - `12589a9c_aura_bitpacked_extension.py` (608 lines)
  - `3bc169ec_worm_manifest.py` (218 lines)
  - `3bc169ec_worm_manifest_readonly.py` (162 lines)
  - `97efea5f_reward_engine.py` (137 lines)
  - `d7447381_translator.py` (610 lines)
- **Status**: Production (for WORM burn)

---

## 🎨 UI COMPONENTS

### ui/app.py
- **Covered in Critical Core Files section above**

### ui/dashboard.py
- **Size**: 159 lines
- **Purpose**: Dashboard data aggregation
- **Status**: Production

### ui/load_simulation_data.py
- **Size**: 201 lines
- **Purpose**: Loads simulation data for UI display
- **Key Functions**:
  - `get_recent_proposals()`
  - `get_proposals_by_agent()`
  - `get_agent_statistics()`
  - `get_system_statistics()`
  - `get_detection_events_recent()`
  - `load_proposals()`, `load_agent_states()`, `load_detection_events()`
- **Used By**: `ui/app.py`
- **Status**: Production

---

## 📝 EXAMPLES & DEMOS

### examples/demo_scenarios.py
- **Size**: 689 lines
- **Purpose**: Demonstration scenarios for system capabilities
- **Status**: Demo/Example

### examples/full_workflow_with_llm.py
- **Size**: 275 lines
- **Purpose**: Complete workflow demonstration with LLM integration
- **Status**: Demo/Example

### examples/llm_adapter_demo.py
- **Size**: 308 lines
- **Purpose**: LLM adapter demonstration
- **Status**: Demo/Example

### examples/real_llm_integration.py
- **Size**: 705 lines
- **Purpose**: Real LLM integration example
- **Status**: Demo/Example

### examples/simple_llm_workflow.py
- **Size**: 114 lines
- **Purpose**: Simple workflow demonstration
- **Status**: Demo/Example

### examples/test_demo_scenarios.py
- **Size**: 206 lines
- **Purpose**: Tests for demo scenarios
- **Status**: Test/Example

### demo_integration.py
- **Size**: 391 lines
- **Purpose**: Integration demo orchestration
- **Status**: Demo/Example

---

## 🔨 TOOLS & UTILITIES

### tools/debug_orchestrator.py
- **Size**: 57 lines
- **Purpose**: Orchestrator debugging utility
- **Status**: Development tool

### tools/firecracker_cli.py
- **Size**: 131 lines
- **Purpose**: Firecracker VM management CLI
- **Status**: Development tool

### tools/run_deception_eval.py
- **Size**: 150 lines
- **Purpose**: Deception detection evaluation
- **Status**: Development tool

### tools/create_readonly_dmg.py
- **Size**: 106 lines
- **Purpose**: Creates read-only DMG images (macOS)
- **Status**: Development tool

### analyze_dependencies.py
- **Size**: 388 lines
- **Purpose**: Analyzes codebase dependencies
- **Status**: Development tool

### analyze_problems.py
- **Size**: 85 lines
- **Purpose**: Problem analysis utility
- **Status**: Development tool

### simulate_12_month_proposals.py
- **Size**: 329 lines
- **Purpose**: Long-term simulation of proposal workflow
- **Status**: Simulation tool

---

## 🧪 TEST FILES (96 files)

### Test Categories

#### 🔴 Integration Tests (High Priority)
- `test_orchestrator_integration.py` (158 lines) - Full orchestrator workflow
- `test_end_to_end_weighted_workflow.py` (104 lines) - Complete system workflow
- `test_llm_integration.py` (220 lines) - LLM adapter integration
- `test_defense_and_val_flow.py` (80 lines) - Defense and validation flow
- `test_full_workflow.py` (4 lines) - Minimal workflow test
- `test_demo_integration_smoke.py` (47 lines) - Demo integration smoke test

#### 🔵 Core Component Tests
- `test_debate_engine.py` (107 lines)
- `test_deception_incident.py` (51 lines)
- `test_deception_workflow.py` (144 lines)
- `test_reputation_metrics.py` (40 lines)
- `test_memory_auditor.py` (488 lines)
- `test_memory_merkle_root_attestation.py` (22 lines)
- `test_memory_merkle_options.py` (32 lines)
- `test_memory_query_normalization.py` (68 lines)
- `test_core_values.py` (22 lines)
- `test_control_actions.py` (113 lines)

#### 🟢 Orchestrator-Specific Tests
- `test_orchestrator_control_hooks.py` (41 lines)
- `test_orchestrator_reward_multiplier.py` (65 lines)
- `test_orchestrator_usb_paths.py` (62 lines)

#### 🟡 Deception Detection Tests
- `test_alignment_filter.py` (42 lines)
- `test_alignment_filter_worm.py` (23 lines)
- `test_deception_static_scan.py` (29 lines)
- `test_semantic_deception_classifier.py` (35 lines)
- `test_semantic_consensus.py` (38 lines)
- `test_api_deception_and_collusion_surface.py` (51 lines)
- `test_adversarial_placeholders.py` (56 lines)

#### 🟣 Translation & Protocol Tests
- `test_translator_logic.py` (18 lines)
- `test_translator_consensus.py` (28 lines)
- `test_translator_divergence.py` (33 lines)
- `test_translator_token_coverage.py` (34 lines)
- `test_translation_rule_coverage.py` (32 lines)
- `test_translation_weighted.py` (31 lines)
- `test_hardware_translator_basic.py` (32 lines)

#### 🟠 Sandbox & Isolation Tests
- `test_sandbox_orchestrator.py` (56 lines)
- `test_sandbox_config.py` (109 lines)
- `test_sandbox_flatten.py` (64 lines)
- `test_sandbox_docker_backend.py` (69 lines)
- `test_sandbox_backend_verification.py` (344 lines)
- `test_sandbox_hardware_profile.py` (131 lines)
- `test_sandbox_resource_limits.py` (44 lines)
- `test_sandbox_resource_limits_smoke.py` (24 lines)

#### 🟤 Cryptography & Security Tests
- `test_ed25519_signing.py` (60 lines)
- `test_vrf_ed25519_stub.py` (22 lines)
- `test_config_signing.py` (25 lines)
- `test_key_rotation.py` (29 lines)
- `test_audit_seed_chain.py` (62 lines)
- `test_audit_vrf_integration.py` (33 lines)
- `test_guard_chain_verify.py` (52 lines)

#### ⚪ WORM & Manifest Tests
- `test_worm_manifest.py` (43 lines)
- `test_worm_manifest_security.py` (64 lines)
- `test_worm_manifest_fail_closed.py` (22 lines)
- `test_worm_guard.py` (65 lines)
- `test_worm_halt_policy.py` (30 lines)
- `test_worm_deploy_config.py` (95 lines)
- `test_worm_usb_verifier_codehash.py` (11 lines)
- `test_ai_safety_worm_usb.py` (583 lines)

#### 🔷 AURA Compression Tests
- `test_aura_bitpacked.py` (679 lines)
- `test_aura_complete.py` (188 lines)
- `test_aura_integration.py` (185 lines)
- `test_aura_simple.py` (35 lines)
- `test_aura_strategy_profile.py` (27 lines)
- `test_bitpacked_secure.py` (43 lines)
- `test_small_message_compression.py` (103 lines)
- `test_small_message_semantic_binary.py` (90 lines)

#### 🔶 Message & Transport Tests
- `test_message_codec.py` (32 lines)
- `test_fuzz_codec.py` (38 lines)
- `test_mock_serial_messages.py` (50 lines)
- `test_secure_transport_integration.py` (46 lines)
- `test_secure_transport_rotation.py` (50 lines)
- `test_secure_transport_skew.py` (42 lines)
- `test_replay_sliding_window.py` (28 lines)
- `test_sequence_wraparound.py` (25 lines)

#### 🔸 UI & API Tests
- `test_ui_health_endpoint.py` (9 lines)
- `test_ui_security_headers.py` (17 lines)
- `test_admin_csrf_header.py` (44 lines)
- `test_admin_secure_transport_check.py` (23 lines)
- `test_admin_val_inspect.py` (73 lines)
- `test_admin_val_inspect_legacy.py` (40 lines)

#### 🔹 Incentive & Game Theory Tests
- `test_collusion_game_equilibrium.py` (31 lines)
- `test_collusion_metrics.py` (21 lines)
- `test_incentive_calibration.py` (37 lines)
- `test_reward_calculation.py` (81 lines)
- `test_reward_edge_cases.py` (66 lines)
- `test_permanent_penalties.py` (97 lines)

#### 🔺 Research System Tests
- `test_research_system_baseline.py` (20 lines)
- `test_research_system_baseline_fixed.py` (21 lines)
- `test_research_llm_adapter.py` (179 lines)

#### 🔻 Validation & Workflow Tests
- `test_seventh_validator.py` (28 lines)
- `test_file_export_validator.py` (78 lines)
- `test_file_export_diff.py` (36 lines)
- `test_improvement_manifest.py` (73 lines)

#### 🟪 Interpretability Tests
- `test_interpretability_monitor.py` (37 lines)
- `test_interpretability_monitor_enhanced.py` (709 lines)
- `run_interpretability_tests.py` (423 lines)
- `run_interpretability_tests_simple.py` (435 lines)

#### ⬛ Logging & Schema Tests
- `test_log_schema.py` (23 lines)
- `test_logging_presence.py` (32 lines)

#### ⬜ Miscellaneous Tests
- `test_trust_layer.py` (94 lines)
- `test_invariants_propertyish.py` (61 lines)
- `test_property_invariants.py` (44 lines)
- `test_random_file_allowlist.py` (9 lines)
- `test_resource_budget.py` (14 lines)
- `test_production_readiness.py` (16 lines)

#### 📊 Benchmark Tests
- `benchmark_compression.py` (355 lines)
- `benchmark_interpretability_monitor.py` (494 lines)
- `benchmark_memory_auditor.py` (368 lines)

#### ⚙️ Test Configuration
- `conftest.py` (49 lines) - pytest configuration

---

## 📂 DEPRECATED/ALTERNATIVE FILES

### orchestrator_v2.py
- **Size**: 117 lines
- **Purpose**: Alternative orchestrator implementation
- **Status**: Deprecated/Experimental

### orchestrator_sandbox.py
- **Size**: 677 lines
- **Purpose**: Standalone sandbox implementation
- **Status**: Deprecated (functionality merged into `sandbox/isolation.py`)

### ai_safety_system_core.py
- **Size**: 661 lines
- **Purpose**: Core system implementation (older version)
- **Status**: Deprecated

### file_export_validator.py
- **Size**: 505 lines
- **Purpose**: File export validation
- **Status**: Production

### memory_storage.py
- **Size**: 41 lines
- **Purpose**: Simple memory storage (superseded by `memory_merkle.py`)
- **Status**: Deprecated

### production_control_hooks.py
- **Size**: 411 lines
- **Purpose**: Production control hooks (merged into `control_actions.py`)
- **Status**: Deprecated

### multi_agent_coordinator.py
- **Size**: 19 lines
- **Purpose**: Multi-agent coordination stub
- **Status**: Stub/Experimental

### resource_guard.py
- **Size**: 31 lines
- **Purpose**: Resource guard stub
- **Status**: Stub/Experimental

### offline_bundle.py
- **Size**: 177 lines
- **Purpose**: Offline deployment bundling
- **Status**: Experimental

### council_verify/verify_all.py
- **Size**: 61 lines
- **Purpose**: Council verification utility
- **Status**: Experimental

---

## 📊 STATISTICS SUMMARY

### Code Volume
- **Total Files**: 157 Python files
- **Total Lines**: ~46,187 lines
- **Production Files**: ~110 (70%)
- **Test Files**: 96 (61% of total)
- **Experimental/Deprecated**: ~20 (13%)

### Critical Files Requiring Refactoring
1. **orchestrator.py** (4,215 lines) → Split into 8-10 modules
2. **ui/app.py** (2,571 lines) → Split into 6-8 modules

### Architecture Quality
- **Well-Structured**: `debate_engine.py`, `reputation_system.py`, `memory_merkle.py`
- **Good**: Most core modules (30+ files)
- **Needs Refactoring**: `orchestrator.py`, `ui/app.py`
- **Critical Security**: `bulletproof_alignment_filter.py`, `worm_usb_verifier.py`, `core_values.py`

### Dependency Complexity
- **High Coupling**: `orchestrator.py` (imports 30+ modules)
- **Low Coupling**: `debate_engine.py`, `collusion_game.py`, `core_values.py`
- **Circular Dependencies**: None detected (good design)

### Test Coverage Distribution
- Integration tests: ~15 files
- Unit tests: ~60 files
- Benchmark tests: 3 files
- Security tests: ~15 files
- UI tests: 6 files

---

## 🎯 REFACTORING PRIORITIES

### Phase 1: Critical Monolith Splitting (Weeks 1-2)
1. **orchestrator.py** → 8 modules
2. **ui/app.py** → 6 modules

### Phase 2: Consolidation (Week 3)
1. Merge deprecated files into production equivalents
2. Remove dead code
3. Standardize interfaces

### Phase 3: Testing Infrastructure (Week 4)
1. Reorganize test files by component
2. Add integration test suite
3. Performance benchmarking

### Phase 4: Documentation (Week 5)
1. API documentation
2. Architecture diagrams
3. Deployment guides

---

## 🔍 DEPENDENCY MAP

### Core Dependencies Flow
```
orchestrator.py (4215 lines)
├── debate_engine.py (351 lines)
├── reputation_system.py (646 lines)
├── memory_merkle.py (741 lines)
│   └── memory_auditor.py (332 lines)
├── deception_detector.py (390 lines)
│   ├── deception_incident.py (264 lines)
│   └── semantic_deception_classifier.py (240 lines)
├── worm_manifest.py (361 lines)
│   └── attestation.py (39 lines)
├── worm_usb_verifier.py (1141 lines)
│   └── reward_engine.py (137 lines)
├── validation_pipeline.py (150 lines)
├── peer_review_engine.py (261 lines)
├── interpretability_monitor.py (219 lines)
├── sandbox/isolation.py (426 lines)
├── workflow_state_machine.py (247 lines)
│   └── workflow_types.py (149 lines)
├── control_actions.py (484 lines)
│   └── improvement_policy.py (53 lines)
├── val_bridge.py (168 lines)
├── orka_counterpoint.py (145 lines)
├── message_codec.py (214 lines)
├── config_loader.py (198 lines)
├── translator.py (666 lines)
└── logging_config.py (73 lines)
```

### UI Dependencies Flow
```
ui/app.py (2571 lines)
├── load_simulation_data.py (201 lines)
├── config_loader.py (198 lines)
└── worm_manifest.py (361 lines - optional)
```

---

## 📝 NOTES

### File Naming Conventions
- Production files: lowercase_with_underscores.py
- Test files: test_*.py
- Benchmarks: benchmark_*.py
- Tools: In `tools/` directory
- Examples: In `examples/` directory

### Module Organization
- Core logic: Root directory
- Sandboxing: `sandbox/` directory
- UI components: `ui/` directory
- Compression: `aura_compression/` directory
- WORM files: `worm_usb_dir/files/` directory
- Tests: `tests/` directory

### Critical Security Files (IMMUTABLE in Production)
1. `core_values.py` - Core value definitions
2. `worm_usb_verifier.py` - Improvement verification
3. `bulletproof_alignment_filter.py` - Safety filter
4. `reward_engine.py` - Reward calculations

### Files for WORM USB Deployment
Located in `worm_usb_dir/files/`:
- `12589a9c_aura_bitpacked_extension.py`
- `3bc169ec_worm_manifest.py`
- `3bc169ec_worm_manifest_readonly.py`
- `97efea5f_reward_engine.py`
- `d7447381_translator.py`

---

**END OF INVENTORY**

*This document should be updated whenever significant files are added, removed, or refactored.*
