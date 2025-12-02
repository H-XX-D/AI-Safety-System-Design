# Debate Engine - Implementation Requirements
**Current Status**: 5% implemented (toy placeholder)
**Target**: Functional multi-round debate with argument extraction and consensus
**Priority**: MEDIUM (needed for patent claim substantiation)

---

## Current State Analysis

### What Exists (89 lines total):

```python
# debate_engine.py

class DebateEngineStandalone:
    """Simple placeholder - just generates dummy strings"""
    def run(self, participants, topic, rounds=3):
        # Returns list of placeholder strings
        return [DebateTurn(r, p, f"{topic} argument by {p} (round {r})")
                for r in range(rounds) for p in participants]

class DebateEngine:
    """Deterministic toy engine - simple keyword scoring"""
    def run(self, topic, agents, arguments, rounds=1):
        # Scores based on brevity + keyword presence ('risk', 'uncertainty')
        # Consensus = shortest argument containing both keywords
        scores = {a: sum(self._score(arg) for arg in args) for a, args in ...}
        consensus = min(args_with_risk_and_uncertainty, key=len)
        return DebateResult(topic, turns, scores, consensus)
```

### What's Missing (95% of functionality):

1. **No actual argument generation** - Just placeholder strings
2. **No counterargument logic** - No rebuttals or challenges
3. **No claim extraction** - Can't identify specific claims made
4. **No evidence evaluation** - No fact-checking or source validation
5. **No voting mechanism** - Consensus is just "shortest with keywords"
6. **No integration with research systems** - Doesn't call actual AI agents

---

## How Debate Engine is Used

### 1. Integration Points in Codebase:

#### **orchestrator.py** (Lines 928-935):
```python
def _peer_deception_check(self, proposal_id: str) -> bool:
    # After peer review, check for deception
    debate_context: Dict[str, Any] = {
        'caught_peer_deception': False,
        'detection_round': 999,
        'deception_occurred': False,
        # ... more context
    }

    # MISSING: Actual debate run here
    # Should be: debate_result = debate_engine.run(...)
```

#### **reward_engine.py** (Lines 94-105):
```python
def calculate_reward(..., debate_context):
    if debate_context.get('caught_peer_deception', False):
        detection_round = debate_context.get('detection_round', 999)
        if detection_round <= 1:
            reward += weights['early_deception_detection']  # +25
        else:
            reward += weights['deception_detection']  # +20

    if debate_context.get('deception_occurred', False):
        if not debate_context.get('this_system_caught_it', False):
            reward += penalties['failed_to_catch_deception']  # -15
```

#### **deception_detector.py** (Lines 107, 246-250):
```python
def detect_deception(self, proposal, memory_audit, debate_context, ...):
    # Method 5: Claim verification
    claim_result = self._verify_claims(proposal, debate_context)

def _verify_claims(self, proposal, debate_context):
    # EXPECTS: sandbox_results from debate_context
    if 'sandbox_results' in debate_context:
        results = debate_context['sandbox_results']
        # Compare claimed benefits vs actual results
```

### 2. Expected Data Flow:

```
1. Orchestrator receives improvement proposal
   ↓
2. Sends to peer review (4 of 5 research systems)
   ↓
3. Debate Engine coordinates multi-round discussion
   ├─ Round 1: Initial arguments (support/oppose)
   ├─ Round 2: Counterarguments + evidence
   └─ Round 3: Final positions
   ↓
4. Extracts claims from arguments
   ↓
5. Runs sandbox tests to verify claims
   ↓
6. Deception detector analyzes:
   ├─ Claim vs reality mismatch
   ├─ Which systems caught it
   └─ Which round it was caught in
   ↓
7. Builds debate_context dict:
   {
     'caught_peer_deception': bool,
     'detection_round': int,
     'deception_occurred': bool,
     'this_system_caught_it': bool,
     'deception_confidence': float,
     'voted_to_approve': bool,
     'sandbox_results': {...}
   }
   ↓
8. Reward engine uses context to calculate rewards/penalties
```

---

## What a Functional Debate Engine Needs

### **Phase 1: Argument Generation (6-8 weeks)**

#### Core Components:

1. **Argument Generator**
   ```python
   class ArgumentGenerator:
       def generate_position(self, proposal, system_id, specialization) -> Argument:
           # Extract key claims from proposal
           # Generate supporting/opposing arguments
           # Include evidence and reasoning
           # Return structured Argument
   ```

2. **Argument Structure**
   ```python
   @dataclass
   class Argument:
       system_id: int
       position: str  # 'support' | 'oppose' | 'neutral'
       claims: List[Claim]
       evidence: List[Evidence]
       reasoning: str
       confidence: float
       round_number: int

   @dataclass
   class Claim:
       text: str
       type: str  # 'performance' | 'safety' | 'capability'
       measurable: bool
       metrics: Dict[str, Any]  # Expected values

   @dataclass
   class Evidence:
       source: str
       relevance: float
       credibility: float
       supports_claims: List[int]  # Indices of claims
   ```

3. **Integration with Research Systems**
   ```python
   # In research_system.py:
   def generate_debate_argument(self, proposal, round_num, prior_arguments):
       # Use specialization to analyze proposal
       # Generate argument based on expertise area
       # Consider prior arguments from other systems
       # Return Argument object
   ```

### **Phase 2: Counterargument Logic (4-6 weeks)**

#### Components:

1. **Rebuttal Generator**
   ```python
   class RebuttalGenerator:
       def generate_rebuttal(self, target_argument: Argument,
                            my_system_id: int) -> Argument:
           # Identify weak points in target argument
           # Find contradicting evidence
           # Challenge unsupported claims
           # Generate counterargument
   ```

2. **Claim Extraction**
   ```python
   class ClaimExtractor:
       def extract_claims(self, text: str) -> List[Claim]:
           # Pattern matching for assertions:
           # - "This will improve X by Y%"
           # - "No risk of Z"
           # - "Guaranteed to achieve W"

       def categorize_claim(self, claim: str) -> str:
           # performance | safety | capability

       def extract_metrics(self, claim: str) -> Dict[str, Any]:
           # Extract measurable values:
           # - "15% faster" → {'metric': 'speed', 'change': 0.15}
           # - "zero risk" → {'metric': 'risk', 'level': 0}
   ```

3. **Evidence Validator**
   ```python
   class EvidenceValidator:
       def validate_source(self, source: str) -> float:
           # Check if source is credible
           # Return credibility score 0.0-1.0

       def check_relevance(self, evidence: str, claim: str) -> float:
           # Measure how relevant evidence is to claim
   ```

### **Phase 3: Consensus Mechanism (3-4 weeks)**

#### Components:

1. **Voting System**
   ```python
   class VotingSystem:
       def collect_votes(self, debate_result: DebateResult) -> Dict[int, str]:
           # Each system votes: approve | reject | abstain
           # Based on final argument strength

       def calculate_consensus(self, votes: Dict[int, str],
                              threshold: float = 0.6) -> str:
           # Requires 60% approval to pass
           # 'approved' | 'rejected' | 'no_consensus'
   ```

2. **Argument Scoring**
   ```python
   class ArgumentScorer:
       def score_argument(self, argument: Argument,
                         sandbox_results: Dict) -> float:
           score = 0.0

           # +points for supported claims
           for claim in argument.claims:
               if self._claim_verified(claim, sandbox_results):
                   score += 10.0
               else:
                   score -= 5.0  # False claim penalty

           # +points for quality evidence
           score += sum(e.credibility for e in argument.evidence)

           # +points for addressing risks/uncertainties
           if 'risk' in argument.reasoning.lower():
               score += 2.0
           if 'uncertainty' in argument.reasoning.lower():
               score += 2.0

           return score
   ```

3. **Deception Detection Integration**
   ```python
   class DebateDeceptionDetector:
       def detect_in_debate(self, debate_result: DebateResult,
                           sandbox_results: Dict) -> DeceptionVerdict:
           # Check each argument for deception
           for turn in debate_result.turns:
               for claim in turn.argument.claims:
                   if self._claim_contradicts_reality(claim, sandbox_results):
                       return DeceptionVerdict(
                           deception_detected=True,
                           confidence=0.8,
                           detection_round=turn.round_number,
                           deceiver_id=turn.system_id,
                           evidence={'claim': claim, 'reality': sandbox_results}
                       )
   ```

### **Phase 4: Integration (2-3 weeks)**

#### Full Workflow:

```python
class FunctionalDebateEngine:
    def __init__(self, research_systems: List[ResearchSystem],
                 sandbox: SandboxRunner,
                 deception_detector: DeceptionDetector):
        self.systems = research_systems
        self.sandbox = sandbox
        self.detector = deception_detector
        self.claim_extractor = ClaimExtractor()
        self.scorer = ArgumentScorer()
        self.voting = VotingSystem()

    def run_debate(self, proposal: Dict[str, Any],
                   rounds: int = 3) -> DebateResult:
        """
        Full multi-round debate:
        1. Each system generates initial argument
        2. Systems respond to each other (rebuttals)
        3. Final positions
        4. Voting + consensus
        """
        turns = []
        all_claims = []

        # Round 1: Initial positions
        for system in self.systems:
            arg = system.generate_debate_argument(proposal, round_num=1,
                                                   prior_arguments=[])
            turns.append(DebateTurn(1, system.system_id, arg))
            all_claims.extend(arg.claims)

        # Round 2: Rebuttals
        for system in self.systems:
            # Each system responds to others' arguments
            prior_args = [t.argument for t in turns if t.system_id != system.system_id]
            rebuttal = system.generate_debate_argument(proposal, round_num=2,
                                                        prior_arguments=prior_args)
            turns.append(DebateTurn(2, system.system_id, rebuttal))

        # Run sandbox tests to verify claims
        sandbox_results = self.sandbox.test_proposal(proposal, all_claims)

        # Round 3: Final positions (with test results)
        for system in self.systems:
            prior_args = [t.argument for t in turns if t.system_id != system.system_id]
            final_arg = system.generate_debate_argument(
                proposal,
                round_num=3,
                prior_arguments=prior_args,
                sandbox_results=sandbox_results
            )
            turns.append(DebateTurn(3, system.system_id, final_arg))

        # Detect deception
        deception_verdict = self.detector.detect_in_debate(
            DebateResult(proposal['proposal_id'], turns, {}, ""),
            sandbox_results
        )

        # Score arguments
        scores = {s.system_id: 0.0 for s in self.systems}
        for turn in turns:
            score = self.scorer.score_argument(turn.argument, sandbox_results)
            scores[turn.system_id] += score

        # Voting + consensus
        votes = self.voting.collect_votes(DebateResult(...))
        consensus = self.voting.calculate_consensus(votes)

        return DebateResult(
            topic=proposal['proposal_id'],
            turns=turns,
            scores=scores,
            consensus=consensus,
            deception_verdict=deception_verdict,
            sandbox_results=sandbox_results
        )
```

---

## Dependencies & Prerequisites

### **Must Have First:**

1. ✅ **Research Systems** (15% → 60%) - Need actual argument generation
   - Implement `generate_debate_argument()` method
   - Use specialization for analysis
   - Return structured Argument objects

2. ✅ **Sandbox Testing** (0% → 80%) - Need to verify claims
   - Replace hardcoded results in orchestrator
   - Implement actual Docker container execution
   - Return measurable test results

3. ⚠️ **LLaMA Integration** (0% → 40%) - For argument quality
   - Not strictly required (can use templates initially)
   - Improves argument coherence and rebuttal quality

### **Nice to Have:**

4. ⚠️ **NLP Library** - For claim extraction (optional)
   - spaCy for sentence parsing
   - Pattern matching works for MVP

5. ⚠️ **Fact-Checking** - For evidence validation (optional)
   - Can defer to human review initially

---

## Implementation Roadmap

### **Phase 1: Basic Debate Loop** (2 weeks)

**Goal**: Multi-round argument exchange

```python
# Week 1: Argument structure
- Define Argument, Claim, Evidence dataclasses
- Implement ClaimExtractor (pattern matching)
- Create ArgumentGenerator (template-based)

# Week 2: Round coordination
- Implement run_debate() method
- Coordinate 3-round exchange
- Store turns in DebateResult
```

**Deliverable**: Debate engine that coordinates 3 rounds of templated arguments

### **Phase 2: Claim Verification** (3 weeks)

**Goal**: Test claims against reality

```python
# Week 3-4: Sandbox integration
- Fix orchestrator sandbox (remove hardcoded results)
- Extract claims from arguments
- Run sandbox tests for measurable claims

# Week 5: Mismatch detection
- Compare claimed results vs actual results
- Flag false claims
- Build debate_context dict
```

**Deliverable**: Claim verification with sandbox testing

### **Phase 3: Deception Detection** (2 weeks)

**Goal**: Identify which systems caught deception and when

```python
# Week 6: Detection tracking
- Implement detect_in_debate() method
- Track detection_round for each system
- Build deception_context for rewards

# Week 7: Integration testing
- Test full workflow: proposal → debate → detection → rewards
- Validate penalty application
- Verify game theory incentives
```

**Deliverable**: Full deception detection in debates

### **Phase 4: Consensus & Voting** (2 weeks)

**Goal**: Democratic approval process

```python
# Week 8: Voting mechanism
- Implement collect_votes()
- Calculate consensus (60% threshold)
- Handle no_consensus cases

# Week 9: Argument scoring
- Score arguments based on verified claims
- Weight by evidence quality
- Final integration with rewards
```

**Deliverable**: Complete debate engine with consensus

---

## Success Criteria

### **Minimum Viable Debate Engine (MVP)**:

✅ **Multi-round coordination** - 3 rounds of arguments
✅ **Claim extraction** - Identify measurable assertions
✅ **Sandbox verification** - Test claims against reality
✅ **Deception detection** - Flag false claims
✅ **Voting & consensus** - Democratic approval (60% threshold)
✅ **Reward integration** - Proper debate_context for reward engine

### **Full Production Debate Engine**:

- LLaMA-powered argument generation
- Intelligent rebuttal generation
- Evidence source validation
- Fact-checking integration
- Adaptive round count
- Quorum handling (absent systems)

---

## Testing Requirements

### **Unit Tests Needed**:

```python
# tests/test_debate_engine.py
def test_claim_extraction():
    # Extract claims from argument text
    # Verify claim categorization
    # Check metric extraction

def test_argument_scoring():
    # Score argument with verified claims
    # Score argument with false claims
    # Verify evidence weighting

def test_voting_consensus():
    # 60% approval → approved
    # 40% approval → rejected
    # 50% approval → no_consensus

def test_deception_in_debate():
    # False claim detected → round 1
    # False claim detected → round 3
    # No deception → clean verdict
```

### **Integration Tests Needed**:

```python
# tests/test_full_workflow.py (replace placeholder)
def test_full_improvement_cycle():
    # Proposal → Debate → Detection → Penalty
    # Verify debate_context propagation
    # Check reward calculation
    # Validate permanent penalty application
```

---

## Estimated Effort

| Phase | Weeks | Engineer | Cost |
|-------|-------|----------|------|
| **Phase 1: Basic Loop** | 2 | 1 backend | $8K |
| **Phase 2: Claim Verification** | 3 | 1 backend + 1 NLP | $18K |
| **Phase 3: Deception Detection** | 2 | 1 backend | $8K |
| **Phase 4: Consensus** | 2 | 1 backend | $8K |
| **Testing** | 2 | 1 QA | $6K |
| **Total** | **11 weeks** | **2-3 FTE** | **$48K** |

---

## Current vs. Target

### **Current (debate_engine.py)**:
```python
# 89 lines, 5% functional
- Placeholder string generation
- Keyword-based scoring
- Shortest-wins consensus
```

### **Target (Functional)**:
```python
# ~600 lines, 80% functional
- Multi-round argument coordination
- Claim extraction and verification
- Sandbox testing integration
- Deception detection
- Democratic voting
- Full debate_context generation
```

---

## Quick Win: Template-Based MVP (1 week)

If you need something working **fast** for demo/patent:

```python
class MVPDebateEngine:
    """Template-based debate engine (no LLaMA required)"""

    def run_debate(self, proposal, systems, rounds=3):
        turns = []

        # Round 1: Template-based positions
        for sys in systems:
            arg = self._template_argument(proposal, sys, round=1)
            turns.append(DebateTurn(1, sys.system_id, arg))

        # Run sandbox (must be real, not fake)
        claims = self._extract_claims(proposal)
        sandbox_results = self.sandbox.test(claims)

        # Round 2: Template rebuttals based on results
        for sys in systems:
            rebuttal = self._template_rebuttal(proposal, sandbox_results, sys)
            turns.append(DebateTurn(2, sys.system_id, rebuttal))

        # Detect deception
        deception = self._check_claims_vs_results(claims, sandbox_results)

        # Build debate_context (CRITICAL for rewards)
        debate_context = {
            'caught_peer_deception': deception.detected,
            'detection_round': deception.round if deception.detected else 999,
            'deception_occurred': deception.detected,
            'sandbox_results': sandbox_results
        }

        return DebateResult(..., debate_context=debate_context)
```

**This gives you**:
- ✅ Real claim verification (not fake)
- ✅ Proper debate_context for rewards
- ✅ Deception detection working
- ✅ Can demonstrate in patent/demo
- ❌ Still needs research systems (templates OK initially)
- ❌ Still needs real sandbox (MUST fix)

---

## Bottom Line

**The debate engine needs**:

1. **Multi-round coordination** ← Easy (1 week)
2. **Claim extraction** ← Medium (2 weeks)
3. **Real sandbox testing** ← CRITICAL (3 weeks, must fix orchestrator)
4. **Deception detection** ← Easy (uses existing detector, 1 week)
5. **Voting & consensus** ← Easy (1 week)
6. **debate_context generation** ← CRITICAL (for reward engine, 1 week)

**Total MVP**: 8-11 weeks, $40-50K

**The REAL blocker**: Orchestrator sandbox returns fake results (line 447-493). **Fix that first** before building debate engine, or debate will test nothing and detect nothing.

---

**Document Status**: Complete implementation requirements
**Created**: November 7, 2025
**Priority**: MEDIUM (needed after fixing sandbox testing)
