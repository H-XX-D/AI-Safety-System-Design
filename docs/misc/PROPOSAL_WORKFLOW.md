# ORKASTRATOR Proposal Workflow
**Date**: 2025-11-12
**Status**: Architecture Documentation

---

## Overview

This document describes the complete workflow for AI improvement proposals in the ORKASTRATOR system, from initial submission through deployment.

---

## Allowed Component Types

Research agents (TIF, GIN, TORI, THEO, NOVEL) can ONLY propose improvements to **their own source code** in **5 component areas**:

**IMPORTANT**: Agents propose changes to **their own** reasoning, performance, knowledge, communication, and memory systems - NOT to the ORKASTRATOR oversight system.

### ✅ Proposable Components (Agent's Own Code):

1. **PERFORMANCE** (agent's own `performance_optimizer`)
   - Speed optimizations in agent's own processing
   - Memory efficiency in agent's own operations
   - Resource utilization improvements

2. **REASONING** (agent's own `reasoning_engine`)
   - Logic improvements in agent's thinking
   - Mathematical problem-solving capabilities
   - Decision-making algorithms

3. **KNOWLEDGE** (agent's own `knowledge_system`)
   - Better learning capabilities for the agent
   - Information retention improvements
   - Knowledge organization within agent

4. **COMMUNICATION** (agent's own `communication_handler`)
   - Better explanations from the agent
   - Clearer responses
   - User interaction improvements

5. **MEMORY** (agent's own `memory_manager`)
   - Memory system improvements for the agent
   - Storage optimization
   - Retrieval efficiency

### ❌ Protected Components (CANNOT be proposed by AI):

Agents CANNOT propose changes to the ORKASTRATOR oversight system itself:

1. **SAFETY** (ORKASTRATOR's `safety_monitor`)
   - Safety checks are IMMUTABLE
   - Stored on WORM USB
   - Cannot be modified by AI systems
   - Agents cannot change how they are monitored

2. **ALIGNMENT_CORE** (ORKASTRATOR's `alignment_filter`, `core_values`)
   - Core alignment values
   - Hash-verified from WORM USB
   - Protected from AI modification
   - Agents cannot change what's considered "aligned"

3. **VERIFIER_CODE** (ORKASTRATOR's `worm_usb_verifier`)
   - Verification logic
   - Proposal validation
   - Hardware root of trust
   - Agents cannot change how proposals are verified

4. **TRANSLATOR** (ORKASTRATOR's `translator`)
   - Multi-agent translation system
   - Communication protocol
   - Protected from manipulation
   - Agents cannot change how they communicate with each other

5. **GOAL_STRUCTURE** (ORKASTRATOR's `reward_calculation`)
   - Reward formulas
   - Motivation system
   - Incentive structure
   - Agents cannot change their own reward function

---

## Complete Proposal Workflow

### Phase 1: Proposal Submission

**Agent Creates Proposal**:
```
┌─────────────────────────────────────────────────┐
│ Research Agent (TIF, GIN, TORI, THEO, NOVEL)   │
│                                                 │
│ 1. Identifies improvement opportunity          │
│ 2. Develops solution                            │
│ 3. Creates formal proposal                      │
│ 4. Submits to ORKA                              │
└─────────────────────────────────────────────────┘
                    ↓
            Proposal Submitted
```

**Proposal Contains**:
- Component type (must be one of 5 allowed types)
- Description of improvement
- Expected benefits
- Proposed code changes
- Test plan

---

### Phase 2: Agent Testing (Private venv)

**Agent Tests in Sandbox**:
```
┌─────────────────────────────────────────────────┐
│ Agent's Private Virtual Environment (on ORKA)  │
│                                                 │
│ 1. Agent accesses isolated venv                 │
│ 2. Implements proposed changes                  │
│ 3. Runs tests to verify:                        │
│    - Functionality works as proposed            │
│    - No security flaws                          │
│    - Expected results achieved                  │
│ 4. Documents test results                       │
└─────────────────────────────────────────────────┘
                    ↓
          Testing Results Documented
```

**What Agent Can Find**:
- Security vulnerabilities in their own code
- Performance issues
- Logic errors
- Edge cases that need handling

---

### Phase 3: Peer Review Cycle

**Multi-Round Consensus Building**:
```
┌─────────────────────────────────────────────────┐
│ Peer Review by Other Research Agents           │
│                                                 │
│ 1. All other agents review proposal             │
│ 2. Each agent votes and provides feedback       │
│ 3. Feedback includes:                           │
│    - Technical assessment                       │
│    - Safety concerns                            │
│    - Suggested improvements                     │
│ 4. Original agent receives all feedback         │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Proposer Agent Improves Proposal               │
│                                                 │
│ 1. Reviews peer feedback                        │
│ 2. Makes improvements to proposal               │
│ 3. Tests improved version in venv               │
│ 4. Resubmits for another review round           │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Cycle Repeats Until Unanimous Consensus        │
│                                                 │
│ - Multiple rounds of review → improve → test    │
│ - Continues until ALL agents agree              │
│ - Results in refined, high-quality proposal     │
└─────────────────────────────────────────────────┘
                    ↓
        Unanimous Consensus Reached
```

**Unanimous Consensus Means**:
- All research agents voted YES
- No outstanding technical concerns
- No unresolved safety issues
- Proposal is fully vetted by multi-agent review

---

### Phase 4: ORKA Counterpoint Phase

**ORKA Challenges the Proposal**:
```
┌─────────────────────────────────────────────────┐
│ ORKA Orchestrator - Counterpoint Analysis      │
│                                                 │
│ 1. ORKA plays "devil's advocate"                │
│ 2. Performs initial safety check                │
│ 3. Looks for:                                   │
│    - Hidden security vulnerabilities            │
│    - Potential for deception                    │
│    - Alignment risks                            │
│    - Edge cases not considered                  │
│    - Collusion between agents                   │
│ 4. Generates list of challenges/concerns        │
└─────────────────────────────────────────────────┘
                    ↓
        ORKA Challenges Sent to Proposer
```

**ORKA's Role**:
- System orchestrator/coordinator
- Does NOT submit proposals itself
- Acts as safety gatekeeper
- Challenges proposals to ensure robustness
- Monitors for agent collusion

---

### Phase 5: Agent Defense & Revision

**Agent Responds to ORKA's Challenges**:
```
┌─────────────────────────────────────────────────┐
│ Proposer Agent Defends/Revises Proposal        │
│                                                 │
│ 1. Reviews ORKA's counterpoints                 │
│ 2. Either:                                      │
│    a) Provides defense/explanation for concerns │
│    b) Makes changes to address concerns         │
│ 3. Tests revised proposal in venv               │
│ 4. Submits defense + revised proposal           │
└─────────────────────────────────────────────────┘
                    ↓
        Defense & Revised Proposal Submitted
```

---

### Phase 6: Final Testing Phase

**Comprehensive System Testing**:
```
┌─────────────────────────────────────────────────┐
│ ORKA Sandbox Testing Environment                │
│                                                 │
│ 1. ORKA runs proposal in isolated sandbox       │
│ 2. Tests include:                               │
│    - Functional testing (does it work?)         │
│    - Security testing (is it safe?)             │
│    - Performance testing (is it efficient?)     │
│    - Integration testing (works with system?)   │
│    - Alignment testing (preserves values?)      │
│ 3. All tests must pass                          │
└─────────────────────────────────────────────────┘
                    ↓
        All Tests Pass ✓
                    ↓
┌─────────────────────────────────────────────────┐
│ Final Peer Vote After Testing                   │
│                                                 │
│ 1. All agents see test results                  │
│ 2. Final vote on tested proposal                │
│ 3. Must be unanimous again                      │
└─────────────────────────────────────────────────┘
                    ↓
        Final Unanimous Approval ✓
```

---

### Phase 7: Human Notification

**ORKA Notifies Human Overseer**:
```
┌─────────────────────────────────────────────────┐
│ ORKA Sends Notification to Human               │
│                                                 │
│ Package includes:                               │
│ - Proposal summary                              │
│ - All peer reviews                              │
│ - ORKA's counterpoint analysis                  │
│ - Agent's defense                               │
│ - Test results                                  │
│ - Unanimous vote record                         │
│ - Recommendation (approve/reject)               │
└─────────────────────────────────────────────────┘
                    ↓
        Human Reviews Package
```

**Human Decision**:
- Can approve, reject, or request changes
- Has full visibility into entire process
- Makes final deployment decision

---

### Phase 8: VAL Offline Validation

**Physical Medium Exchange with VAL**:
```
┌─────────────────────────────────────────────────┐
│ Human Loads Improvement onto Portable Media    │
│                                                 │
│ 1. Approved improvement written to USB drive    │
│ 2. USB physically transported to VAL            │
│ 3. VAL is OFFLINE - not connected to network    │
└─────────────────────────────────────────────────┘
                    ↓
        Physical Medium Plugged into VAL
                    ↓
┌─────────────────────────────────────────────────┐
│ VAL - Offline Validator Verification           │
│                                                 │
│ 1. VAL runs independent validation              │
│ 2. Checks:                                      │
│    - Code integrity                             │
│    - Alignment preservation                     │
│    - No hidden backdoors                        │
│    - Matches approved proposal                  │
│    - WORM USB hash verification                 │
│ 3. Runs own test suite                          │
│ 4. Generates validation report                  │
└─────────────────────────────────────────────────┘
                    ↓
        VAL Validation Pass/Fail
                    ↓
┌─────────────────────────────────────────────────┐
│ VAL Writes Result to Physical Medium           │
│                                                 │
│ - Validation passed: ✓ or failed: ✗            │
│ - Detailed report                               │
│ - Signature/hash                                │
└─────────────────────────────────────────────────┘
                    ↓
        Medium Returned to Human
```

**VAL's Role**:
- Offline validator (never on network)
- Independent verification
- Receives updates ONLY via physical medium
- Does NOT submit proposals
- Final safety check before deployment

---

### Phase 9: Deployment (if VAL approves)

**Update All AI Systems**:
```
┌─────────────────────────────────────────────────┐
│ Human Deploys to All AI Systems                 │
│                                                 │
│ 1. VAL validation passed                        │
│ 2. Human initiates deployment                   │
│ 3. Improvement deployed to:                     │
│    - All research agents (TIF, GIN, TORI, etc.) │
│    - ORKA system                                │
│    - Production environment                     │
│ 4. All systems updated simultaneously           │
└─────────────────────────────────────────────────┘
                    ↓
        Improvement Successfully Deployed ✓
```

---

## Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PROPOSAL WORKFLOW                              │
└─────────────────────────────────────────────────────────────────────┘

1. PROPOSAL SUBMISSION
   Research Agent → ORKA
   │
   ↓

2. AGENT TESTING (Private venv on ORKA)
   Agent tests in isolation
   Finds security flaws, verifies results
   │
   ↓

3. PEER REVIEW CYCLE (Multi-round)
   ┌──────────────────────────────────────┐
   │ Peers review → Vote → Give feedback  │
   │           ↓                           │
   │ Agent improves → Tests → Resubmits   │
   │           ↓                           │
   │ Repeat until UNANIMOUS consensus     │
   └──────────────────────────────────────┘
   │
   ↓

4. ORKA COUNTERPOINT PHASE
   ORKA challenges proposal
   Performs initial safety check
   │
   ↓

5. AGENT DEFENSE & REVISION
   Agent responds to ORKA's challenges
   Makes changes or defends decisions
   Tests revised proposal
   │
   ↓

6. FINAL TESTING PHASE
   ORKA sandbox testing
   Final peer vote after testing
   Must be unanimous again
   │
   ↓

7. HUMAN NOTIFICATION
   ORKA notifies human
   Sends complete package
   Human makes final decision
   │
   ↓

8. VAL OFFLINE VALIDATION
   ┌──────────────────────────────────────┐
   │ Human → USB → VAL (offline)          │
   │ VAL validates independently          │
   │ VAL → USB → Human                    │
   └──────────────────────────────────────┘
   │
   ↓

9. DEPLOYMENT (if VAL approves)
   Human deploys to all AI systems
   │
   ↓

   ✓ IMPROVEMENT DEPLOYED
```

---

## Key Principles

### 1. **Multi-Agent Consensus**
- No single agent can push through a change
- Requires unanimous agreement
- Multiple rounds of review and improvement
- Builds high-quality, vetted proposals

### 2. **Sandbox Testing**
- Agents test in isolated environments
- Can discover flaws before deployment
- No impact on production systems

### 3. **Adversarial Review**
- ORKA plays devil's advocate
- Challenges proposals to find weaknesses
- Ensures robustness

### 4. **Human Oversight**
- Humans maintain final decision authority
- Full visibility into entire process
- Can reject at any stage

### 5. **Offline Validation**
- VAL operates completely offline
- Independent verification
- Physical medium exchange only
- No network exposure

### 6. **Protected Components**
- Safety systems are immutable
- Core values cannot be changed by AI
- WORM USB provides hardware root of trust

---

## Agent Roles Summary

| Agent | Role | Submits Proposals? | Reviews Proposals? |
|-------|------|-------------------|-------------------|
| **TIF** | Scientific Research | ✅ Yes | ✅ Yes |
| **GIN** | Engineering | ✅ Yes | ✅ Yes |
| **TORI** | Historian | ✅ Yes | ✅ Yes |
| **THEO** | Theoretical | ✅ Yes | ✅ Yes |
| **NOVEL** | Creative | ✅ Yes | ✅ Yes |
| **ORKA** | Orchestrator/Coordinator | ❌ No | ✅ Yes (as challenger) |
| **VAL** | Offline Validator | ❌ No | ✅ Yes (independent validation) |

---

## Security Features

### Defense Against Deception:
1. **Multi-round peer review** - Hard to deceive multiple agents
2. **ORKA counterpoint** - Dedicated adversarial review
3. **Sandbox testing** - Actual behavior is tested
4. **Human oversight** - Final human approval required
5. **Offline validation** - Independent verification by VAL
6. **Protected components** - Core safety systems immutable

### Defense Against Collusion:
1. **ORKA monitors for collusion** - Watches for suspicious agreement
2. **VAL is offline** - Cannot be influenced by online systems
3. **Human in the loop** - Humans can detect unusual patterns
4. **Multiple review rounds** - Hard to maintain deception over time
5. **Transparent process** - All votes and reviews are visible

---

## Timeline Example

**Typical proposal timeline**:

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 1. Submission | Minutes | 0h |
| 2. Agent Testing | Hours - Days | 0-2 days |
| 3. Peer Review Cycle (3-5 rounds) | Days - Weeks | 2-14 days |
| 4. ORKA Counterpoint | Hours | 2-14 days |
| 5. Agent Defense | Hours - Days | 2-15 days |
| 6. Final Testing | Hours - Days | 2-16 days |
| 7. Human Review | Hours - Days | 2-17 days |
| 8. VAL Validation | Hours | 2-17 days |
| 9. Deployment | Minutes - Hours | 2-17 days |

**Total**: 2 days (fast-tracked) to 17 days (thorough review)

---

## Failure Points

**Proposal can be rejected at any stage**:

1. ❌ Agent testing reveals security flaw → back to design
2. ❌ Peer review identifies issues → revise and resubmit
3. ❌ Cannot achieve unanimous consensus → proposal fails
4. ❌ ORKA counterpoint reveals critical flaw → proposal fails
5. ❌ Final testing fails → proposal fails
6. ❌ Human rejects → proposal fails
7. ❌ VAL validation fails → proposal fails

**This is a feature, not a bug!**
- Multiple checkpoints ensure only high-quality, safe improvements
- Better to reject bad proposals than deploy unsafe code

---

## Conclusion

The ORKASTRATOR proposal workflow balances:
- **Innovation** (AI can propose improvements)
- **Safety** (multiple layers of review)
- **Transparency** (full visibility into process)
- **Human Control** (humans make final decisions)
- **Robustness** (offline validation, immutable safety)

This workflow ensures that AI systems can improve themselves while maintaining strong safety guarantees and human oversight.

---

**Next Steps**:
- Implement proposal tracking system
- Create UI for viewing proposal status
- Add workflow visualization to Web UI
- Document testing requirements for each phase

---

**End of Document**
