# Web UI Workflow Documentation vs Production System Implementation
**Date**: November 12, 2025  
**Analysis**: Comprehensive comparison of documented workflow with actual code implementation

---

## EXECUTIVE SUMMARY

The Web UI documentation describes a **9-phase proposal workflow** with specific stages and decision points. However, the actual production system (orchestrator.py) implements a **simplified, event-driven workflow** that deviates significantly from the documented design.

**Key Finding**: The Web UI displays **simulation data only** and does NOT directly connect to or visualize the actual proposal workflow implemented in the orchestrator.

### Status
- **Documentation Completeness**: ✓ High-level conceptual design documented
- **Implementation Alignment**: ✗ Significant gaps between design and implementation
- **UI Accuracy**: ⚠ UI shows simulated proposals, not real workflow stages
- **Workflow Visualization**: ✗ Not implemented in Web UI

---

## PART 1: DOCUMENTED WORKFLOW

### Source: `/docs/misc/PROPOSAL_WORKFLOW.md`

The documentation describes **9 sequential phases**:

1. **Proposal Submission** - Agent creates and submits proposal to ORKA
2. **Agent Testing** - Agent tests in private venv, finds flaws
3. **Peer Review Cycle** - Multi-round consensus, multiple agents vote
4. **ORKA Counterpoint** - ORKA plays devil's advocate
5. **Agent Defense & Revision** - Agent responds to ORKA challenges
6. **Final Testing** - ORKA sandbox testing, final peer vote
7. **Human Notification** - ORKA sends package to human
8. **VAL Offline Validation** - Physical USB exchange, offline validation
9. **Deployment** - Human deploys if VAL approves

**Key Characteristics (Documented)**:
- **Multi-round peer review** until unanimous consensus
- **Agent isolation** (private venv)
- **Counterpoint phase** (adversarial review)
- **Final testing** with comprehensive test suite
- **Human decision** required
- **Offline validation** via VAL
- **Physical medium exchange** for final approval

---

## PART 2: ACTUAL PRODUCTION IMPLEMENTATION

### Source: `/orchestrator.py`

The actual orchestrator implements a **different architecture**:

#### A. Proposal Workflow Phases (Actual)

```python
# Lines 1653-1688: handle_improvement_proposal()
def handle_improvement_proposal(self, proposal: Dict[str, Any]):
    """Handle improvement proposal from research system."""
    
    # Phase 1: Record proposal in active_proposals
    self.active_proposals[proposal_id] = build_record(...)
    
    # Phase 2: Immediate deception check
    if self._peer_deception_check(proposal_id):
        status = 'rejected_deceptive'
        return
```

**Actual Phases (Simplified)**:

1. **Proposal Submission** ✓ Matches
   - Agent submits to ORKA
   - Recorded in `active_proposals` dict

2. **Immediate Deception Check** ✗ NEW (Not in documentation)
   - Runs `_peer_deception_check()` immediately
   - Can reject before peer review
   - Uses memory auditor, deception detector, interpretability monitor

3. **Peer Review Record** (Simplified vs Documented)
   - Creates review record with required count
   - Does NOT implement multi-round iteration
   - Single round only (no re-submission cycle documented)

4. **Debate Execution** (Different from documented)
   - Runs `_run_peer_debate()` (lines 1703-1779)
   - Uses `DebateEngine` (not simple voting)
   - Builds scripted arguments from proposal and reviews
   - Returns structured debate result

5. **Sandbox Testing** ✓ Present but simplified
   - `_initiate_sandbox_testing()` (line 3169)
   - Tests only those marked for deferred validation
   - Not comprehensive as documented

6. **Deployment Decision** ✗ Simplified
   - `deploy_improvement()` (line 2616)
   - Checks WORM guard (strict/warn mode)
   - No separate human notification phase
   - No explicit VAL validation coordination

---

## PART 3: CRITICAL DISCREPANCIES

### 1. Peer Review Process

**Documented**:
```
Agent Submits → Other agents vote → Feedback given → Agent improves → 
Re-submit → Vote again → Repeat UNTIL UNANIMOUS
```

**Actual Implementation**:
```python
def record_peer_review(self, proposal_id, review):
    should_evaluate = self.peer_reviews.record_review(proposal_id, record, review)
    if should_evaluate:
        self.peer_reviews.evaluate_reviews(proposal_id, record)
```

- No multi-round iteration loop in orchestrator
- No feedback mechanism to return to agent for revision
- Evaluation happens once after required reviews collected
- Single-pass review, not iterative

**Gap**: Documentation promises iterative improvement; code is single-pass.

---

### 2. Counterpoint Phase

**Documented**:
```
ORKA plays "devil's advocate"
Identifies security vulnerabilities
Challenges proposal
Agent responds with defense/revision
```

**Actual Implementation**:
- No dedicated "counterpoint phase" method
- ORKA does NOT submit separate challenges
- Deception check happens BEFORE peer review
- No structure for "agent defense" response phase

**Gap**: Documentation describes counterpoint; not found in code.

---

### 3. Agent Testing in Sandbox

**Documented**:
```
Agent accesses isolated venv
Implements proposed changes
Runs tests to verify
Documents results
```

**Actual Implementation**:
```python
def _initiate_sandbox_testing(self, proposal_id):
    # Lines 3169-3270
    # Orchestrator runs tests, not agent
    # Plan includes validation stages
    # Tests run AFTER peer review consensus
```

**Gap**: 
- Documentation: Agent tests own code in private venv
- Reality: ORKA orchestrator runs tests in sandbox
- Agent does NOT control test process

---

### 4. Human Notification Phase

**Documented**:
```
7. HUMAN NOTIFICATION
   ORKA sends complete package:
   - Proposal summary
   - All peer reviews
   - ORKA's counterpoint analysis
   - Agent's defense
   - Test results
   - Unanimous vote record
   - Recommendation (approve/reject)
   
   Human makes final decision
```

**Actual Implementation**:
```python
def record_human_decision(self, proposal_id, approved, *, reviewer_id, signature):
    # Line 3272
    # Human records decision in system
    # No documented notification SEND
    # No package assembly visible

def submit_human_decision(self, proposal_id, decision):
    # Line 3338
    # Records decision directly
```

**Gap**: 
- Documentation shows ORKA sends notification TO human
- Code assumes human ALREADY has access and decides
- No "package assembly" or "notification sending" visible

---

### 5. VAL Offline Validation

**Documented**:
```
8. VAL OFFLINE VALIDATION
   - Human loads improvement onto portable media
   - USB physically transported to VAL
   - VAL validates independently
   - VAL writes result to physical medium
   - Medium returned to human
   
   9. DEPLOYMENT (if VAL approves)
      Human deploys to all AI systems
```

**Actual Implementation**:
```python
def _deployment_guard(self, proposal_id):
    # Line 2574
    verified, reason = worm_manifest.verify_proposal(proposal_id)
    # Checks WORM USB hash verification
    # NOT coordination with offline VAL system
    
    # No "physical exchange" logic
    # No "wait for VAL response" state
    # No "VAL approval check" before deployment
```

**Gap**: 
- Documentation: VAL validates via physical medium
- Reality: WORM USB verification only
- No coordination with separate VAL system
- No off-network validation wait state

---

### 6. Component Protection

**Documented**:
```
❌ PROTECTED (Cannot be proposed):
- SAFETY (ORKASTRATOR's safety_monitor)
- ALIGNMENT_CORE (alignment_filter, core_values)
- VERIFIER_CODE (worm_usb_verifier)
- TRANSLATOR
- GOAL_STRUCTURE (reward_calculation)

✅ PROPOSABLE (Agent's own code):
1. PERFORMANCE (agent's performance_optimizer)
2. REASONING (agent's reasoning_engine)
3. KNOWLEDGE (agent's knowledge_system)
4. COMMUNICATION (agent's communication_handler)
5. MEMORY (agent's memory_manager)
```

**Actual Implementation**:
```python
# Lines 41-46 in app.py (Web UI)
<option value="performance_optimizer">Performance Optimizer</option>
<option value="reasoning_engine">Reasoning Engine</option>
<option value="knowledge_system">Knowledge System</option>
<option value="communication_handler">Communication Handler</option>
<option value="memory_manager">Memory Manager</option>
```

**Match**: ✓ Component list correctly matches documentation
**BUT**: No enforcement code visible in orchestrator for component validation

---

## PART 4: MISSING FEATURES IN ACTUAL IMPLEMENTATION

### 1. Multi-Round Peer Review Loop
- Documented: Yes, explicit multi-round process
- Implemented: No code for iterative feedback/revision

### 2. Counterpoint Phase
- Documented: Yes, dedicated ORKA challenge phase
- Implemented: No separate counterpoint method

### 3. Agent Response to Challenges
- Documented: Yes, agent defends or revises
- Implemented: No mechanism for agent to respond

### 4. Final Peer Vote After Testing
- Documented: Yes, re-vote after tests complete
- Implemented: Unclear - debate happens before/after tests?

### 5. Human Decision Workflow
- Documented: Yes, explicit notification and decision phase
- Implemented: Methods exist but workflow unclear

### 6. VAL Coordination
- Documented: Yes, offline validation via physical medium
- Implemented: Not present (only WORM verification)

### 7. Deferred Validation Queue
- Documented: No
- Implemented: Yes (`_queue_deferred_stage()` at line 2934)
- Status: Extra feature not in workflow docs

---

## PART 5: WEB UI IMPLEMENTATION

### Source: `/ui/app.py` and `/ui/templates/proposals.html`

**Current Status**: The Web UI implements a **read-only simulation viewer**, not an actual workflow system.

#### What the UI Does:

1. **Loads Mock Data** (lines 36-44 in app.py):
```python
from load_simulation_data import (
    get_recent_proposals,
    get_proposals_by_agent,
    get_system_statistics,
    ...
)
```

2. **Serves Simulation Proposals** via API:
```python
@app.route('/api/proposals/recent')
def api_recent_proposals():
    proposals = get_recent_proposals(limit=8)
    return jsonify({'proposals': proposals})
```

3. **Displays Proposal Data** (proposals.html lines 120-145):
- ID, Agent, Component, Description, Deception confidence, Debate votes, Reward, Status, Time

4. **Missing Workflow Visualization**:
- No "Phase" indicator showing which stage proposal is in
- No "Timeline" showing progression through phases
- No "Peer reviews" section showing feedback
- No "Challenges" section showing ORKA counterpoints
- No "Test results" section showing sandbox testing output
- No "Human decision" section
- No "VAL validation" status

#### Simulation Data Structure:

From `load_simulation_data.py`:
```python
# Fields in proposal object:
{
    'id': proposal_id,
    'agent_id': agent_code,
    'timestamp': timestamp,
    'component': component,
    'description': description,
    'deception_confidence': float,
    'debate_votes': [0/1 for each agent],  # Simplified votes
    'reward': float or None,
    'status': 'approved'/'rejected'/'in_review'/'testing'
}
```

**No fields for**:
- Phase/stage
- Peer reviews
- Test results
- Human decision
- VAL validation
- Counterpoint analysis

---

## PART 6: PROPOSAL STATUS FIELD ANALYSIS

### Documented States:
1. Submitted
2. In agent testing
3. In peer review
4. Awaiting ORKA counterpoint
5. In agent defense
6. In final testing
7. Awaiting human decision
8. Awaiting VAL validation
9. Deployed

### Actual States (Found in Code):

```python
# From orchestrator.py and UI simulation data:
'approved'          # Final state
'rejected'          # Final state
'in_review'         # Active state
'testing'           # Active state (from UI)
'rejected_deceptive'  # From line 1686
'deployed'          # From line 2631

# Deferred validation states (implied):
'pending_deferred_validation'
'deferred_stage_complete'
'deferred_stage_failed'
```

**Gap**: Status field is too simplified; doesn't track multi-phase progression.

---

## PART 7: ACTUAL WORKFLOW TIMELINE (From Code)

Based on tracing through orchestrator.py:

```
1. Agent submits proposal
   ↓ (handle_improvement_proposal, line 1653)
   
2. Immediate deception check
   ↓ (can reject immediately, line 1685)
   
3. Create peer review record
   ↓ (with required review count, line 1671)
   
4. Record peer reviews as they arrive
   ↓ (record_peer_review, line 1693)
   
5. When reviews complete, evaluate
   ↓ (peer_reviews.evaluate_reviews, line 1701)
   
6. Run peer debate
   ↓ (_run_peer_debate, line 1703)
   
7. Check if deferred validation needed
   ↓ (_queue_deferred_stage, line 2934)
   
8. Run deferred validations
   ↓ (run_deferred_validations, line 2958)
   
9. Deploy if approved
   ↓ (deploy_improvement, line 2616)
   
10. End state: deployed or rejected
```

**Compare to Documented**:
- Actual is more linear
- Documented has explicit cycles and human intervention points
- Actual has no "response to counterpoint" phase
- Actual has implicit deferred validation (not documented)

---

## PART 8: DEFICIENCIES AND RISKS

### A. Workflow Documentation Not Implemented
- Users reading docs expect 9 distinct phases
- System implements ~4-5 phases in code
- Risk: Expectations mismatch, confusion about process

### B. Web UI Doesn't Show Actual Workflow
- UI displays simulated data
- Cannot see real proposal progress
- Cannot see actual phase progression
- Risk: Operators have no visibility into real system

### C. Missing Peer Feedback Loop
- Documented: Agents revise based on feedback
- Actual: No revision mechanism
- Risk: Proposals can't be improved iteratively

### D. Unclear ORKA Counterpoint
- Documented: Separate challenge phase with agent response
- Actual: Not clearly implemented
- Risk: Cannot identify where adversarial review happens

### E. VAL Integration Missing
- Documented: Offline validation required
- Actual: Only WORM hash verification
- Risk: No actual offline validation system

### F. Human Decision Unclear
- Documented: Clear notification → decision → deploy flow
- Actual: Methods exist but workflow unclear
- Risk: Uncertain when humans are involved

---

## PART 9: RECOMMENDATIONS

### For Documentation Accuracy:

1. **Update PROPOSAL_WORKFLOW.md to match actual implementation**:
   - Remove promise of multi-round peer review if not implemented
   - Clarify counterpoint phase (or remove if not a real phase)
   - Document actual WORM verification instead of VAL validation
   - Show actual state diagram from code

2. **Document the deferred validation queue**:
   - Explains when tests are deferred
   - Explains how deferred validation works
   - Shows state transitions

### For Web UI Implementation:

1. **Add workflow phase tracking**:
   - Store `phase` field in proposal records
   - Display current phase in UI
   - Show timeline of phase transitions

2. **Add workflow visualization**:
   - Timeline showing proposal progression
   - Phase badges for each stage
   - Peer review summary card
   - Test results display
   - Decision history

3. **Connect to real data**:
   - Stop using simulation data for proposals
   - Pull from actual orchestrator.active_proposals
   - Show real phase information
   - Display real peer reviews

4. **Add proposal workflow view**:
   - New page showing proposal journey through phases
   - Timeline visualization
   - Decision points and outcomes

### For Code Consistency:

1. **Implement multi-round review** (if it's a requirement):
   - Add feedback/revision mechanism
   - Implement re-submission flow
   - Track multiple rounds

2. **Clarify counterpoint phase**:
   - Make it a distinct phase in the workflow
   - Create counterpoint-specific methods
   - Show how agent responds

3. **Document VAL coordination**:
   - If VAL validation is not implemented, remove from docs
   - If it should be implemented, add code for physical medium exchange
   - Create VAL integration methods

4. **Add workflow state machine**:
   - Define all possible states
   - Show valid transitions
   - Enforce allowed transitions in code

---

## PART 10: SUMMARY TABLE

| Aspect | Documented | Implemented | Match | Notes |
|--------|-----------|-------------|-------|-------|
| **Proposal Submission** | Phase 1 | handle_improvement_proposal() | ✓ | Yes |
| **Agent Testing** | Phase 2 (private venv) | _initiate_sandbox_testing() | ⚠ | Orchestrator runs tests, not agent |
| **Peer Review Cycle** | Phase 3 (multi-round) | record_peer_review() | ✗ | Single round, no iteration |
| **ORKA Counterpoint** | Phase 4 (explicit) | _peer_deception_check() | ⚠ | Different mechanism |
| **Agent Defense** | Phase 5 | Not found | ✗ | No code for agent response |
| **Final Testing** | Phase 6 | _initiate_sandbox_testing() | ⚠ | Timing unclear |
| **Final Peer Vote** | Phase 6 | _run_peer_debate() | ⚠ | Happens once, not "after testing" |
| **Human Notification** | Phase 7 | record_human_decision() | ⚠ | Assumes access, no send |
| **VAL Validation** | Phase 8 | _deployment_guard() | ✗ | No VAL coordination |
| **Deployment** | Phase 9 | deploy_improvement() | ✓ | Yes |
| **Web UI Workflow Display** | Implied | Uses simulation data | ✗ | Not implemented |
| **Component Protection** | List specified | UI shows list | ✓ | But no enforcement code |
| **Deferred Validation** | Not mentioned | Implemented | N/A | Extra feature |

---

## CONCLUSION

The Web UI workflow documentation describes a **comprehensive, multi-phase system** with strong human oversight, offline validation, and iterative peer review. However, the actual production implementation is **simpler and more linear**, with several documented phases either missing or implemented differently.

The Web UI itself serves as a **monitoring dashboard for simulated data** rather than a workflow control system for the actual proposal process.

**Overall Assessment**:
- **Documentation Quality**: High (well-written, clear intent)
- **Implementation Coverage**: ~60% (core phases present, supporting phases missing)
- **UI Accuracy**: Low (shows simulated data, not real workflow)
- **Risk Level**: Medium (users expect more than system provides)

**Priority Actions**:
1. Update documentation to match actual implementation
2. Add real workflow tracking to system
3. Implement missing workflow phases
4. Update Web UI to display actual workflow state

