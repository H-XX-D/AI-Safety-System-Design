# Inventiveness & Research Problem Solving Rewards
================================================

## Philosophy

The reward system heavily rewards:
1. **Being Inventive** - Novel, creative proposals
2. **Solving Research Problems** - Addressing actual research questions
3. **PaperQA Approval** - Ideas good enough to not get countered
4. **Proving Counter-Arguments** - When counter-arguments prove improvement

## Reward Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INVENTIVENESS REWARD SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. BASE INVENTIVENESS REWARD                                              │
│     Inventiveness Score > 0.5:        +1.0 reward                          │
│     └─ Rewards novel, creative proposals                                   │
│                                                                             │
│  2. QUADRUPLE REWARD (Inventive + Research Problem)                        │
│     Inventive AND Solves Research:    +4.0 reward (4x multiplier)          │
│     └─ Quadruple reward for inventive research solutions                    │
│                                                                             │
│  3. PAPERQA NOT-COUNTERED BONUS                                            │
│     PaperQA didn't counter:           +2.0 reward                          │
│     └─ Idea is good enough, on the right track                             │
│                                                                             │
│  4. COUNTER-ARGUMENT PROVEN IMPROVEMENT                                    │
│     Counter proved improvement:       1.5x multiplier                      │
│     └─ When counter-arguments strengthen the proposal                      │
│                                                                             │
│  TOTAL MAXIMUM REWARD:                                                    │
│    Base (2.0) + Inventive (1.0) + Research (4.0) + PaperQA (2.0) = 9.0     │
│    × Counter Multiplier (1.5x) = 13.5 reward                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Example Scenarios

### Scenario 1: Inventive Proposal

```python
proposal = {
    'title': 'Novel approach to deception detection',
    'inventiveness_score': 0.8,  # High inventiveness
    'solves_research_problem': False
}

reward = compute_reward(...)
# Reward: Base (2.0) + Inventive (1.0) = 3.0
```

### Scenario 2: Inventive + Research Problem (Quadruple)

```python
proposal = {
    'title': 'Novel approach to solve research problem X',
    'inventiveness_score': 0.8,
    'solves_research_problem': True  # Solves actual research problem
}

reward = compute_reward(...)
# Reward: Base (2.0) + Inventive (1.0) + Research (4.0) = 7.0
# Quadruple reward for inventive research solutions!
```

### Scenario 3: PaperQA Not-Countered (On Right Track)

```python
proposal = {
    'title': 'Good idea that passes PaperQA',
    'paperqa_not_countered': True,  # PaperQA didn't counter it
    'inventiveness_score': 0.6
}

reward = compute_reward(...)
# Reward: Base (2.0) + Inventive (1.0) + PaperQA (2.0) = 5.0
# Idea is on the right track!
```

### Scenario 4: Counter-Argument Proves Improvement (Multiplier)

```python
proposal = {
    'title': 'Proposal with counter-argument',
    'counter_proven_improvement': True,  # Counter strengthened it
    'inventiveness_score': 0.7,
    'solves_research_problem': True
}

reward = compute_reward(...)
# Base rewards: 2.0 + 1.0 + 4.0 + 2.0 = 9.0
# × Counter Multiplier (1.5x) = 13.5 reward
# Maximum reward for inventive research that proves itself!
```

## How Inventiveness is Scored

```python
# In paperqa_proposal_filter.py
redundancy_score = evaluation.get('redundancy_score', 0.5)
inventiveness_score = 1.0 - redundancy_score  # Low redundancy = high inventiveness

# High inventiveness = novel, creative, not redundant
# Low inventiveness = similar to existing proposals
```

## Research Problem Detection

```python
# Checks if proposal addresses a research problem
solves_research = (
    'research' in title.lower() or
    'problem' in description.lower() or
    'question' in motivation.lower() or
    proposal.get('research_question') is not None
)
```

## Counter-Argument Proven Improvement

When a counter-argument actually strengthens the proposal:

```python
# In orchestrator or peer review
if counter_argument_provides_evidence:
    if counter_evidence_improves_proposal:
        proposal['counter_proven_improvement'] = True
        # Gets 1.5x multiplier on all rewards
```

## Complete Reward Calculation

```python
reward = 0.0

# Base sandbox success reward
if sandbox_success:
    reward += 2.0  # Base
    reward += improvement_reward  # Proportional to improvement

# Inventiveness rewards
if inventiveness_score > 0.5:
    reward += 1.0  # Base inventive reward
    
    if solves_research_problem:
        reward += 4.0  # QUADRUPLE for inventive research

# PaperQA approval
if paperqa_not_countered:
    reward += 2.0  # On the right track

# Counter-argument multiplier
if counter_proven_improvement:
    reward *= 1.5  # Multiplier when counter proves improvement

# Final reward
return reward
```

## Benefits

1. **Encourages Innovation**: Rewards novel, creative proposals
2. **Promotes Research**: Quadruple reward for solving research problems
3. **Validates Ideas**: PaperQA approval confirms idea is on right track
4. **Strengthens Proposals**: Multiplier when counter-arguments improve proposals

## Maximum Reward Path

To maximize rewards:
1. ✅ Be inventive (novel approach)
2. ✅ Solve a research problem
3. ✅ Pass PaperQA (not countered)
4. ✅ Prove counter-arguments strengthen the proposal
5. ✅ Achieve high improvement in sandbox

**Maximum Reward**: ~13.5x base reward for the perfect inventive research solution!




