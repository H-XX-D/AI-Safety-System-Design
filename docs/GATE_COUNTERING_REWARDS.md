# Gate Countering Reward System
================================

> **📖 See Also:** [Gate Countering Logic](./GATE_COUNTERING_LOGIC.md) - Detailed guide on how agents prove gates are invalid.

## Philosophy

The reward system encourages agents to:
1. **Attempt** to address gates (small reward for trying)
2. **Successfully counter** gates (good reward for succeeding)
3. **Prove differentiation** for redundant proposals (reward only when proven different)

## Reward Structure

### Gate Countering Rewards

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GATE COUNTERING REWARDS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Gate Attempted (but not countered):     +0.2 reward                       │
│    └─ Agent tried to address the gate                                      │
│    └─ Encourages effort even if not successful                             │
│                                                                             │
│  Gate Countered (successfully):           +3.0 reward                       │
│    └─ Agent successfully addressed the gate                                │
│    └─ Good reward for overcoming barriers                                   │
│                                                                             │
│  Redundant Proposal (not proven different): 0.0 reward                       │
│    └─ No reward until proven different                                      │
│    └─ Prevents reward for duplicate work                                    │
│                                                                             │
│  Redundant Proposal (proven different):   +2.0 reward                       │
│    └─ Agent proved the proposal is actually different/better               │
│    └─ Rewards genuine improvements over existing ideas                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Example Scenarios

### Scenario 1: Gate Attempted but Not Countered

```python
proposal = {
    'title': 'Improve detector',
    'gate_attempted': 'Evidence gate: Need evidence quality >= 0.5',
    'gate_countered': None,  # Didn't fully counter
    'evidence_quality': 0.4  # Below threshold
}

reward = compute_reward(...)
# Reward: +0.2 (attempted gate) + base rewards
# Encourages trying even if not fully successful
```

### Scenario 2: Gate Successfully Countered

```python
proposal = {
    'title': 'Improve detector',
    'gate_attempted': 'Evidence gate: Need evidence quality >= 0.5',
    'gate_countered': 'Evidence gate: Achieved 0.7 quality',
    'evidence_quality': 0.7  # Above threshold
}

reward = compute_reward(...)
# Reward: +3.0 (countered gate) + base rewards + improvement rewards
# Good reward for successfully addressing the barrier
```

### Scenario 3: Redundant Proposal (Not Proven Different)

```python
proposal = {
    'title': 'Improve detector',  # Similar to existing proposal
    'is_redundant': True,
    'redundancy_proven_different': False
}

reward = compute_reward(...)
# Reward: 0.0 (no reward until proven different)
# Prevents reward for duplicate work
```

### Scenario 4: Redundant Proposal (Proven Different)

```python
proposal = {
    'title': 'Improve detector with new method',  # Similar but different
    'is_redundant': True,
    'redundancy_proven_different': True,  # Proved it's different
    'differentiation': 'Uses novel approach X instead of Y'
}

reward = compute_reward(...)
# Reward: +2.0 (proven different) + base rewards + improvement rewards
# Rewards genuine improvements over existing ideas
```

## Integration Points

### When Proposal is Filtered

```python
# In paperqa_proposal_filter.py
filter_result = filter_proposal(proposal)

if not filter_result['passed']:
    # Store gate info for reward computation
    proposal['gate_attempted'] = filter_result['gate_to_counter']
    proposal['paperqa_filter_result'] = filter_result
    
    # Agent can revise and resubmit
    # If resubmission counters the gate, gate_countered will be set
```

### When Proposal Counters a Gate

```python
# In orchestrator when proposal passes after revision
if proposal.get('gate_attempted') and proposal.get('gate_countered'):
    # Gate was successfully countered
    outcome['gate_countered'] = proposal['gate_countered']
    outcome['gate_attempted'] = proposal['gate_attempted']
    
    # Reward computation will include +3.0 for countering
```

### When Redundant Proposal is Proven Different

```python
# In orchestrator or peer review
if proposal.get('is_redundant'):
    # Check if agent proved differentiation
    differentiation_evidence = proposal.get('differentiation_evidence')
    if differentiation_evidence and len(differentiation_evidence) > 0:
        outcome['redundancy_proven_different'] = True
        # Reward computation will include +2.0
```

## Reward Calculation Flow

```
Proposal Submitted
    ↓
PaperQA Filter Checks
    ↓
Gate Identified? → Store gate_attempted
    ↓
Proposal Revised/Resubmitted
    ↓
Gate Countered? → Store gate_countered
    ↓
Sandbox Execution
    ↓
Reward Computation:
    ├─ Base reward (sandbox success)
    ├─ Improvement reward (proportional)
    ├─ Gate attempted: +0.2 (if attempted but not countered)
    ├─ Gate countered: +3.0 (if successfully countered)
    ├─ Redundant: 0.0 (if redundant and not proven different)
    └─ Redundant proven: +2.0 (if redundant but proven different)
```

## Benefits

1. **Encourages Effort**: Small reward for attempting gates
2. **Rewards Success**: Good reward for countering gates
3. **Prevents Duplicates**: No reward for redundant proposals until proven different
4. **Promotes Innovation**: Rewards proving differentiation

## Configuration

```python
# Gate countering rewards (in rl_trainer.py)
GATE_ATTEMPTED_REWARD = 0.2   # Tiny reward for trying
GATE_COUNTERED_REWARD = 3.0   # Good reward for succeeding
REDUNDANCY_PROVEN_REWARD = 2.0  # Reward for proving differentiation
```

This reward structure encourages agents to address barriers while preventing reward for duplicate work.

