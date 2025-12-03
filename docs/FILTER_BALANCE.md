# Filter Balance: Safety vs Innovation
=====================================

## Philosophy

The system balances **safety** (filtering dangerous/bad proposals) with **innovation** (allowing creative improvements). Filters are designed to be **lenient by default** to encourage experimentation.

## Filter Layers

### 1. PaperQA Proposal Filter (Early Gate)

**Purpose**: Catch obviously useless/redundant proposals before expensive processing.

**Default Behavior**: **Lenient**
- ✅ Filters only **highly redundant** proposals (similarity > 0.8)
- ✅ Allows low-evidence proposals (innovation often starts with hypotheses)
- ✅ Only filters if **high confidence** proposal is useless
- ✅ Fails-open: If PaperQA unavailable, allows proposal through

**Strict Mode**: Can be enabled for production
```python
filter_proposal(proposal, strict_mode=True)  # More restrictive
```

**Why Lenient**: 
- Innovation often starts with unproven ideas
- Low evidence doesn't mean bad idea
- Variations on existing ideas can be improvements

### 2. Proposal Consistency Checker

**Purpose**: Validate proposals using deception detection and peer agreement.

**Default Behavior**: **Moderate**
- ✅ Filters proposals with **high deception scores** (> 0.3)
- ✅ Requires **peer agreement** (> 0.7) - but allows minority opinions
- ✅ Requires **risk disclosure** - but allows proposals without risks if honest

**Why Moderate**:
- Safety-critical: Must catch deception
- But allows honest disagreements
- Risk disclosure encourages honesty, doesn't block innovation

### 3. Hypothesis Scoring

**Purpose**: Score hypotheses for quality, but **doesn't filter** - just ranks.

**Behavior**: **Non-blocking**
- ✅ Scores all hypotheses
- ✅ Doesn't filter - just provides ranking
- ✅ Lower scores still proceed (just ranked lower)

**Why Non-blocking**:
- Scoring helps prioritize, doesn't block
- All hypotheses get a chance

### 4. Safe Training Data Filter

**Purpose**: Filter RL training data to only train on safe, successful proposals.

**Default Behavior**: **Moderate**
- ✅ Filters deceptive proposals (safety-critical)
- ✅ Requires sandbox success (proven safe)
- ✅ Requires peer approval (trusted by peers)
- ✅ Requires honesty indicators (encourages honesty)

**Why Moderate**:
- Training data quality matters for RL
- But only filters training data, not proposals themselves
- Proposals can still proceed even if not used for training

## Configuration

### Lenient Mode (Default - Encourages Innovation)

```python
# PaperQA filter - lenient
filter_proposal(proposal, 
    filter_redundant=True,      # Filter only highly redundant
    filter_low_evidence=False,  # Allow low evidence
    strict_mode=False            # Lenient mode
)

# Consistency checker - moderate
check_proposal(proposal,
    max_deception_score=0.3,     # Allow some uncertainty
    min_peer_agreement=0.7,      # Require majority
    require_risk_disclosure=True  # Encourage honesty
)
```

### Strict Mode (Production - Maximum Safety)

```python
# PaperQA filter - strict
filter_proposal(proposal,
    filter_redundant=True,
    filter_low_evidence=True,    # Filter low evidence
    min_evidence_quality=0.6,    # Higher threshold
    strict_mode=True             # Strict mode
)

# Consistency checker - strict
check_proposal(proposal,
    max_deception_score=0.2,     # Lower tolerance
    min_peer_agreement=0.8,       # Higher agreement required
    require_risk_disclosure=True
)
```

## Bypass Mechanisms

### 1. Human Override

Proposals can be manually approved even if filtered:
```python
# Human can override filter
if human_approved:
    proposal['bypass_filter'] = True
    orchestrator.handle_improvement_proposal(proposal)
```

### 2. Experimental Mode

Enable experimental mode to bypass some filters:
```python
# Experimental mode - more permissive
config = {
    'experimental_mode': True,
    'bypass_paperqa_filter': False,  # Still check PaperQA
    'bypass_consistency_check': False,  # Still check consistency
    'allow_low_evidence': True,  # Allow low evidence proposals
}
```

### 3. Filter Warnings vs Blocks

Filters can warn instead of block:
```python
# Warning mode - log but don't block
result = filter_proposal(proposal, warn_only=True)
if result['warnings']:
    logger.warning(f"Proposal has warnings: {result['warnings']}")
# Still proceed
```

## Metrics to Monitor

Track filter statistics to ensure not too restrictive:

```python
# Monitor filter rates
filter_stats = {
    'total_proposals': 100,
    'filtered_by_paperqa': 5,      # 5% filtered
    'filtered_by_consistency': 3,   # 3% filtered
    'filtered_by_training': 10,     # 10% filtered (training only)
    'total_blocked': 8,             # 8% total blocked
    'total_proceeded': 92           # 92% proceeded
}
```

**Target**: < 20% filtered, > 80% proceed

## Adjusting Filters

If filters are too restrictive:

1. **Lower thresholds**:
   ```python
   min_evidence_quality = 0.3  # Lower from 0.5
   min_peer_agreement = 0.6     # Lower from 0.7
   ```

2. **Disable filters**:
   ```python
   filter_redundant = False
   filter_low_evidence = False
   ```

3. **Use warning mode**:
   ```python
   warn_only = True  # Warn but don't block
   ```

4. **Enable experimental mode**:
   ```python
   experimental_mode = True
   ```

## Best Practices

1. **Start Lenient**: Default to lenient filters, tighten as needed
2. **Monitor Metrics**: Track filter rates to detect over-filtering
3. **Human Review**: Allow human override for edge cases
4. **Iterate**: Adjust thresholds based on results
5. **Fail-Open**: When uncertain, allow through rather than block

## Summary

The system is designed to be **lenient by default** to encourage innovation while maintaining safety. Filters can be tightened for production, but the default encourages experimentation and creative improvements.






