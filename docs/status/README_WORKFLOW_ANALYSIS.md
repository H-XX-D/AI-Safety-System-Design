# Web UI Workflow Analysis - Complete Documentation

**Date**: November 12, 2025  
**Status**: ANALYSIS COMPLETE

---

## Overview

This analysis compares the **documented Web UI workflow** with the **actual production system implementation** to identify gaps, discrepancies, and missing features.

**Key Finding**: Significant gap between documented 9-phase workflow and simplified 4-5 phase actual implementation. Web UI displays simulation data, not real workflow state.

---

## Files in This Analysis

### 1. **WEB_UI_WORKFLOW_ANALYSIS.md** (18 KB)
**Comprehensive technical comparison** (READ THIS FIRST)

Contains:
- Executive Summary
- Full documentation of 9-phase workflow from `/docs/misc/PROPOSAL_WORKFLOW.md`
- Actual implementation analysis from `/orchestrator.py`
- Critical discrepancies (6 major gaps identified)
- Missing features list (7 items)
- Web UI implementation status
- Risk assessment with severity levels
- Detailed recommendations (9 actionable items)
- Summary table showing phase-by-phase comparison

**When to use**: For detailed technical understanding of what's different

**Key sections**:
- Part 3: Critical Discrepancies (peer review, counterpoint, testing, human notification, VAL, components)
- Part 8: Deficiencies and Risks (with impact analysis)
- Part 9: Recommendations (organized by priority)

---

### 2. **WORKFLOW_ANALYSIS_SUMMARY.txt** (Text format)
**Executive summary for quick reference**

Contains:
- Key findings (3 critical points)
- Workflow implementation status (all 9 phases assessed)
- Web UI implementation status
- Risk assessment (severity: MEDIUM, 5 specific risks)
- Priority actions (3 levels: immediate, medium, long-term)
- Line of code analysis
- Conclusion and recommendation

**When to use**: For quick briefing or high-level understanding

**Good for**: Status reports, presentations, decision-making

---

## Analysis Summary

### What Was Documented

The user created comprehensive workflow documentation in `/docs/misc/PROPOSAL_WORKFLOW.md` describing:

**9 Sequential Phases**:
1. Proposal Submission (Agent → ORKA)
2. Agent Testing (Private venv, finds flaws)
3. Peer Review Cycle (Multi-round, iterative feedback)
4. ORKA Counterpoint (Adversarial review)
5. Agent Defense & Revision (Response to challenges)
6. Final Testing (Comprehensive sandbox testing)
7. Human Notification (Complete package sent)
8. VAL Offline Validation (Physical USB exchange)
9. Deployment (Human-approved deployment)

**Key Features**:
- Multi-round peer review with feedback/revision cycles
- Explicit counterpoint/challenge phase
- Agent can defend or revise based on feedback
- Final testing before final vote
- Human oversight and decision
- Offline validation via separate VAL system
- Physical medium exchange for security

---

### What Was Actually Implemented

The `/orchestrator.py` implements a **simpler workflow**:

**~4-5 Phases (Implicit)**:
1. Proposal Submission ✓
2. Immediate Deception Check (not documented)
3. Peer Review (single round, no iteration)
4. Debate Execution (using DebateEngine)
5. Testing (deferred, unclear when it runs)
6. Deployment (with WORM guard check)

**Missing Features**:
- ✗ Multi-round iteration (promised but not implemented)
- ✗ Explicit counterpoint phase (early deception check instead)
- ✗ Agent defense/revision mechanism (no code for responses)
- ✗ VAL offline validation (only WORM USB hash verification)
- ✗ Phase tracking in workflow (can't see progress)
- ✗ Workflow visualization in UI

**Extra Features**:
- Deferred validation queue (not mentioned in docs)
- Interpretability monitoring (not mentioned in docs)
- Memory auditing for deception (not mentioned in docs)

---

### What the Web UI Actually Does

The `/ui/` directory implements a **read-only simulation dashboard**:

**Current Functionality**:
- Displays mock proposal data (from load_simulation_data.py)
- Shows simulated agents (TIF, GIN, TORI, THEO, NOVEL, ORKA, VAL)
- Renders debate votes as checkmarks
- Shows deception confidence scores
- Provides proposal filtering and search
- Real-time updates via WebSocket

**Does NOT Do**:
- ✗ Connect to actual orchestrator workflow
- ✗ Show real proposal phase/stage
- ✗ Display peer reviews or feedback
- ✗ Show test results or sandbox output
- ✗ Track human decision timing
- ✗ Display VAL validation status
- ✗ Visualize workflow progression
- ✗ Provide workflow control interface

**API Endpoints**:
- `/api/proposals/recent` - Returns simulation data
- `/api/penalties/agents` - Returns real ORKA penalty data ✓
- `/api/detection/stats` - Returns simulated stats
- Other endpoints return mocked data

---

## Critical Gaps Identified

### 1. **Multi-Round Peer Review**
- **Documented**: Agents revise proposals based on feedback, re-submit, get voted on again, repeat until unanimous
- **Actual**: Single-pass review, no feedback mechanism, no re-submission
- **Impact**: Proposals cannot be iteratively improved

### 2. **ORKA Counterpoint Phase**
- **Documented**: Separate phase where ORKA challenges proposal and agents respond
- **Actual**: Deception check runs at start, no separate challenge phase
- **Impact**: No adversarial review mechanism found

### 3. **Agent Defense & Revision**
- **Documented**: Agents respond to ORKA's challenges with defense or revisions
- **Actual**: No code for agent responses
- **Impact**: Proposals cannot be defended or improved

### 4. **VAL Offline Validation**
- **Documented**: Physical USB exchange, offline independent validation required
- **Actual**: Only WORM USB hash verification
- **Impact**: No offline safety checkpoint

### 5. **Human Notification**
- **Documented**: ORKA sends complete package to human (proposal, reviews, challenges, tests, votes)
- **Actual**: Methods assume human already has access
- **Impact**: Unclear when/how humans are notified

### 6. **Workflow Phase Tracking**
- **Documented**: 9 distinct phases with progression
- **Actual**: No phase field, simplified status values
- **Impact**: Cannot see proposal progress

---

## Risk Assessment

### Severity: MEDIUM

**Key Risks**:

1. **Expectation Mismatch** (Users expect 9 phases, system delivers ~4)
2. **Lack of Visibility** (Operators cannot see real workflow progress)
3. **Missing Fail-Safes** (Single-pass review less thorough than multi-round)
4. **VAL Integration Missing** (No offline validation checkpoint)
5. **No Defense Mechanism** (Proposals cannot be improved via feedback)

---

## Recommended Actions

### IMMEDIATE (High Priority - Fix Accuracy)
1. **Update PROPOSAL_WORKFLOW.md** to match actual implementation
   - Remove multi-round peer review description
   - Clarify ORKA counterpoint mechanism
   - Replace VAL description with WORM verification
   - Document deferred validation queue

### MEDIUM (Implementation - Add Visibility)
2. **Add phase tracking to proposals**
   - Create 'phase' field in orchestrator
   - Update phase as proposal progresses
   
3. **Create workflow visualization in Web UI**
   - New proposal timeline/workflow page
   - Show phase progression
   - Display reviews, tests, decisions
   
4. **Connect UI to real data**
   - Stop using simulation data
   - Pull from orchestrator.active_proposals
   - Show real phase and metadata

### LONG-TERM (Implementation - Complete Missing Features)
5. **Implement multi-round peer review** (if required)
6. **Clarify ORKA counterpoint phase** (if required)
7. **Decide on VAL integration** (implement or remove from docs)

---

## File Locations

**Documentation Files Referenced**:
- `/docs/misc/PROPOSAL_WORKFLOW.md` - Original workflow documentation (9 phases)
- `/docs/status/WEB_UI_COMPLETION_REPORT.md` - Web UI status report
- `/ui/README.md` - Web UI documentation
- `/ui/QUICKSTART.md` - Web UI quick start

**Code Files Analyzed**:
- `/orchestrator.py` - Main orchestrator implementation (~3700 lines)
  - Lines 1653-1688: `handle_improvement_proposal()`
  - Lines 1693-1701: `record_peer_review()`
  - Lines 1703-1779: `_run_peer_debate()`
  - Lines 2574-2614: `_deployment_guard()`
  - Lines 2616-2637: `deploy_improvement()`
  - Lines 2638-2768: `_peer_deception_check()`
  
- `/ui/app.py` - Web UI backend (497 lines)
  - Lines 36-44: Import simulation data
  - Lines 273-281: Proposals API endpoint
  
- `/ui/templates/proposals.html` - Proposals view
  - Lines 41-46: Component filters
  - Lines 120-145: Proposals table
  
- `/ui/load_simulation_data.py` - Simulation data loader

**New Analysis Files Created**:
- `/docs/status/WEB_UI_WORKFLOW_ANALYSIS.md` (18 KB) - Full technical analysis
- `/docs/status/WORKFLOW_ANALYSIS_SUMMARY.txt` (13 KB) - Executive summary
- `/docs/status/README_WORKFLOW_ANALYSIS.md` - This navigation document

---

## How to Use This Analysis

### For Understanding the Gap:
1. Start with **WORKFLOW_ANALYSIS_SUMMARY.txt** (5-10 min read)
2. Review the "Key Findings" and "Risk Assessment" sections
3. Check "Recommended Actions" for priorities

### For Implementation:
1. Read **WEB_UI_WORKFLOW_ANALYSIS.md** Part 3 (Critical Discrepancies)
2. Note specific line numbers and methods referenced
3. Follow Part 9 (Recommendations) for implementation plan

### For Decision-Making:
1. Review **WORKFLOW_ANALYSIS_SUMMARY.txt**
2. Focus on "Risk Assessment" section
3. Check "Recommended Priority Actions"
4. Make go/no-go decision on implementation

### For Documentation:
1. Read Part 1 of **WEB_UI_WORKFLOW_ANALYSIS.md** (Documented Workflow)
2. Read Part 2 (Actual Implementation)
3. Update `/docs/misc/PROPOSAL_WORKFLOW.md` accordingly

---

## Summary Table: Phase-by-Phase Status

| Phase | Documented | Implemented | Match | Notes |
|-------|-----------|-------------|-------|-------|
| Proposal Submission | Phase 1 | ✓ handle_improvement_proposal() | ✓ FULL | Agent submits to ORKA |
| Agent Testing | Phase 2 | ⚠ _initiate_sandbox_testing() | ⚠ PARTIAL | ORKA runs, not agent |
| Peer Review Cycle | Phase 3 | ⚠ record_peer_review() | ✗ NO MULTI-ROUND | Single pass only |
| ORKA Counterpoint | Phase 4 | ⚠ _peer_deception_check() | ⚠ DIFFERENT | Early check, not separate phase |
| Agent Defense | Phase 5 | ✗ Not found | ✗ NONE | No response mechanism |
| Final Testing | Phase 6 | ⚠ Partial | ⚠ UNCLEAR | Timing uncertain |
| Final Peer Vote | Phase 6 | ⚠ _run_peer_debate() | ⚠ ONCE | Not "after testing" |
| Human Notification | Phase 7 | ⚠ record_human_decision() | ⚠ UNCLEAR | Assumes access |
| VAL Validation | Phase 8 | ✗ Not implemented | ✗ NONE | Only WORM check |
| Deployment | Phase 9 | ✓ deploy_improvement() | ✓ FULL | Checks WORM guard |

---

## Contact & Questions

This analysis was conducted on November 12, 2025.

For questions about:
- **Specific code locations**: See Part 2 and Part 7 of WEB_UI_WORKFLOW_ANALYSIS.md
- **Risk impact**: See Part 8 (Deficiencies and Risks)
- **Next steps**: See Part 9 (Recommendations) or WORKFLOW_ANALYSIS_SUMMARY.txt
- **Technical details**: See full WEB_UI_WORKFLOW_ANALYSIS.md

---

**Last Updated**: November 12, 2025  
**Status**: ANALYSIS COMPLETE - Ready for implementation decisions
