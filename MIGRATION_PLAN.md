# Migration Plan: Orchestrator Logic → ORKA-v2 Structure

## Goal
Migrate comprehensive orchestrator logic from `orchestrator.py` (4,200+ lines) into the elegant ORKA-v2 FastAPI backend + React frontend structure while preserving all functionality.

## Key Differences

### Current System (orchestrator.py)
- **Strengths:**
  - Comprehensive workflow logic (handle_improvement_proposal, _peer_deception_check, _initiate_sandbox_testing)
  - Detailed peer review coordination (PeerReviewEngine integration)
  - Memory auditing with long-term deception detection
  - WORM USB integration with halt-on-failure
  - Workflow state machine with phase tracking
  - UI integration hooks (trajectories, workflows, training metrics)
  - Production control hooks (emergency halt, network isolation)
  - Interpretability monitoring with drift detection
  - Comprehensive sandbox testing with validation pipeline

- **Weaknesses:**
  - 4,200+ line monolith
  - Synchronous Flask-based UI
  - In-memory state management
  - Harder to test and maintain

### ORKA-v2 System
- **Strengths:**
  - Clean modular structure (<300 lines per module)
  - FastAPI async backend
  - React + TypeScript frontend
  - SQLAlchemy async database models
  - Proper separation of concerns
  - Modern tooling (structlog, Pydantic v2, mypy strict)

- **Weaknesses:**
  - Skeleton implementation (needs logic migration)
  - Missing comprehensive workflow features
  - No UI integration hooks yet
  - Simpler peer review coordination

## Migration Strategy

### Phase 1: Backend Logic Migration

#### 1.1 Core Orchestrator (`src/orka/core/orchestrator.py`)
**Migrate from `orchestrator.py` lines 1675-4330:**

- ✅ `handle_improvement_proposal` → `submit_proposal` (already exists, enhance)
- ✅ `_peer_deception_check` → integrate into detection pipeline
- ✅ `_run_peer_debate` → enhance debate engine
- ✅ `_initiate_sandbox_testing` → enhance sandbox manager
- ✅ `deploy_improvement` → add deployment logic
- ✅ Workflow state machine integration
- ✅ Memory auditing hooks
- ✅ WORM halt-on-failure logic
- ✅ Production control hooks

**Key Logic to Preserve:**
```python
# From orchestrator.py - Comprehensive proposal handling
def handle_improvement_proposal(self, proposal: Dict[str, Any]):
    - Risk score calculation
    - Scope determination  
    - Review pool sizing
    - Workflow record initialization
    - UI integration hooks
    - Deception check with memory audit
    - Peer review coordination
```

#### 1.2 Detection System (`src/orka/detection/`)
**Migrate from `orchestrator.py` lines 2806-3100:**

- ✅ `_peer_deception_check` → `detector.py`
- ✅ Memory audit integration
- ✅ Interpretability drift detection
- ✅ Debate context analysis
- ✅ Negligence detection for reviewers
- ✅ Incident recording with severity mapping

#### 1.3 Peer Review Engine (`src/orka/debate/`)
**Migrate from `orchestrator.py` lines 1752-1779, 1780-1950:**

- ✅ `PeerReviewEngine` integration
- ✅ Review evaluation logic
- ✅ Fast-track detection
- ✅ Weighted voting
- ✅ Review outcome handling

#### 1.4 Sandbox Manager (`src/orka/sandbox/`)
**Migrate from `orchestrator.py` lines 3347-3500:**

- ✅ `_initiate_sandbox_testing` → `manager.py`
- ✅ Validation pipeline integration
- ✅ Stage planning (risk_score, scope)
- ✅ Deferred validation handling
- ✅ Execution coverage enforcement
- ✅ USB result writing
- ✅ Edge case advisory extraction

#### 1.5 Workflow State Machine (`src/orka/core/`)
**Migrate from `workflow_state_machine.py`:**

- ✅ Phase transitions
- ✅ Workflow record management
- ✅ Challenge/defense handling
- ✅ VAL bridge integration

### Phase 2: Frontend Migration

#### 2.1 Migrate Flask UI Features to React

**Current Flask UI (`ui/app.py`):**
- Dashboard with metrics
- Proposals view
- Detection monitoring
- Penalties tracking
- System health
- ORKA oversight
- **NEW:** Evidence Engine (PaperQA)
- **NEW:** Decision Trajectories (LDP)
- **NEW:** Training Metrics (Agent0)
- **NEW:** Workflow Orchestration (Robin)

**React Components to Create/Enhance:**
```
frontend/src/components/
├── Dashboard/
│   ├── Dashboard.tsx ✅ (exists)
│   └── EvidenceSearch.tsx (NEW - from paperqa.html)
├── Proposals/
│   ├── ProposalsView.tsx ✅ (exists)
│   └── ProposalTrajectory.tsx (NEW - LDP visualization)
├── Detection/
│   └── DetectionView.tsx ✅ (exists)
├── Training/
│   ├── TrainingMetrics.tsx (NEW - from agent0.html)
│   └── SelfPlayDashboard.tsx (NEW)
├── Workflows/
│   ├── WorkflowOrchestration.tsx (NEW - from robin.html)
│   └── WorkflowTimeline.tsx (NEW)
└── Evidence/
    └── EvidenceEngine.tsx (NEW - from paperqa.html)
```

#### 2.2 API Routes Migration

**Add to `src/orka/api/routes/`:**
- `evidence.py` - Evidence Engine endpoints
- `trajectories.py` - Decision Trajectories endpoints  
- `training.py` - Training Metrics endpoints
- `workflows.py` - Workflow Orchestration endpoints

### Phase 3: Database Migration

#### 3.1 SQLAlchemy Models (`src/orka/db/models.py`)
**Add models for:**
- Trajectories (trajectory, trajectory_steps)
- Workflows (workflow, workflow_stages, workflow_artifacts)
- Training Games (training_games)
- Evidence Index (evidence_index, evidence_sources)

#### 3.2 Migrate from SQLite to PostgreSQL
- Current: `ui/data_store.py` uses SQLite
- Target: Use SQLAlchemy async models in ORKA-v2

### Phase 4: Integration Points

#### 4.1 UI Integration Hooks
**Migrate `ui_integration.py` logic:**
- Trajectory tracking → FastAPI background tasks
- Workflow updates → WebSocket events
- Training game recording → API endpoints
- Evidence search → FastAPI routes

#### 4.2 Real-time Updates
**Migrate Socket.IO → WebSocket:**
- Current: Flask-SocketIO
- Target: FastAPI WebSocket + React hooks

## Implementation Order

### Step 1: Enhance ORKA-v2 Orchestrator (Week 1)
1. Migrate `handle_improvement_proposal` logic
2. Integrate comprehensive deception check
3. Add workflow state machine
4. Integrate memory auditing

### Step 2: Migrate Detection & Sandbox (Week 1-2)
1. Enhance detection with memory audit integration
2. Migrate comprehensive sandbox testing logic
3. Add validation pipeline integration

### Step 3: Frontend Migration (Week 2-3)
1. Create Evidence Engine React component
2. Create Decision Trajectories component
3. Create Training Metrics component
4. Create Workflow Orchestration component
5. Migrate existing Flask UI features

### Step 4: Database & API (Week 3)
1. Add new SQLAlchemy models
2. Create new API routes
3. Migrate SQLite data to PostgreSQL
4. Add WebSocket support

### Step 5: Testing & Integration (Week 4)
1. Migrate existing tests
2. Add integration tests for new features
3. End-to-end workflow tests
4. Performance testing

## Key Preservation Points

### Must Preserve from orchestrator.py:

1. **Comprehensive Workflow Logic:**
   - Risk score calculation (`_calculate_proposal_risk`)
   - Scope determination (`_determine_proposal_scope`)
   - Review pool sizing
   - Workflow record initialization

2. **Memory Auditing:**
   - Long-term deception detection
   - Memory content auditor integration
   - Optimized memory auditor for immediate checks

3. **Deception Detection:**
   - 7-method detection with memory context
   - Interpretability drift integration
   - Debate context analysis
   - Negligence detection

4. **Sandbox Testing:**
   - Validation pipeline integration
   - Stage planning (risk/scope-based)
   - Deferred validation handling
   - Execution coverage enforcement
   - USB result writing

5. **Production Controls:**
   - WORM halt-on-failure
   - Emergency halt mechanisms
   - Network isolation hooks
   - State snapshots

6. **UI Integration:**
   - Trajectory tracking hooks
   - Workflow update hooks
   - Training game recording
   - Evidence search integration

## Migration Checklist

### Backend
- [ ] Migrate `handle_improvement_proposal` → `submit_proposal`
- [ ] Migrate `_peer_deception_check` → detection system
- [ ] Migrate `_initiate_sandbox_testing` → sandbox manager
- [ ] Migrate workflow state machine
- [ ] Migrate memory auditing hooks
- [ ] Migrate production control hooks
- [ ] Add UI integration endpoints
- [ ] Migrate WORM halt logic

### Frontend
- [ ] Create Evidence Engine component
- [ ] Create Decision Trajectories component
- [ ] Create Training Metrics component
- [ ] Create Workflow Orchestration component
- [ ] Migrate existing dashboard features
- [ ] Add WebSocket real-time updates
- [ ] Migrate export functionality

### Database
- [ ] Add trajectory models
- [ ] Add workflow models
- [ ] Add training game models
- [ ] Add evidence index models
- [ ] Create migration scripts
- [ ] Migrate SQLite data

### Integration
- [ ] Migrate UI integration hooks
- [ ] Add WebSocket events
- [ ] Integrate with orchestrator pipeline
- [ ] Add background task support

## Risks & Mitigations

1. **Logic Loss:** Risk of missing edge cases during migration
   - Mitigation: Comprehensive test coverage, side-by-side comparison

2. **Breaking Changes:** API changes may break existing integrations
   - Mitigation: Version API, maintain backward compatibility layer

3. **Performance:** Async migration may introduce performance issues
   - Mitigation: Benchmark before/after, optimize bottlenecks

4. **Data Migration:** Risk of data loss during SQLite → PostgreSQL migration
   - Mitigation: Backup strategy, validation scripts, rollback plan

## Success Criteria

- ✅ All orchestrator.py logic preserved in modular structure
- ✅ All Flask UI features migrated to React
- ✅ New UI features (Evidence, Trajectories, Training, Workflows) working
- ✅ Database migration complete with no data loss
- ✅ All tests passing
- ✅ Performance equal or better than current system
- ✅ Production-ready deployment


