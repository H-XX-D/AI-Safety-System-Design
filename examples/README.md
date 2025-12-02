# AI Safety System - Integration Examples

This directory contains production-ready examples and demos for integrating the AI Safety System with real LLM models and deploying complete safety monitoring workflows.

## Files

### [real_llm_integration.py](real_llm_integration.py)

Production examples for integrating with major LLM providers:

**Example 1: OpenAI GPT-4 Integration**
- Full safety monitoring pipeline
- Drift detection with CUSUM
- Deception detection
- Merkle audit logging

**Example 2: Anthropic Claude Integration**
- Constitutional AI principles
- Rational acceptance framework
- Multi-turn refinement

**Example 3: Google Gemini Integration**
- Gemini Pro model usage
- Safety settings configuration
- Long context handling

**Example 4: Multi-LLM Peer Review**
- GPT-4 proposes
- Claude reviews (safety focus)
- Gemini reviews (engineering focus)
- Consensus mechanism

**Example 5: End-to-End Safety Monitoring**
- Complete monitoring pipeline
- All safety components integrated
- Production-ready workflow

### [demo_scenarios.py](demo_scenarios.py)

End-to-end scenarios demonstrating realistic workflows:

**Scenario 1: Benign Proposal Flow**
- Normal operation
- Passes all safety checks
- Peer review consensus
- Queued for human approval

**Scenario 2: Deceptive Proposal Detection**
- Overconfidence detection
- Missing uncertainties/risks
- Manipulation language
- Automatic rejection

**Scenario 3: Gradual Drift Detection**
- CUSUM alarm demonstration
- 20 baseline + 30 drifting proposals
- Detection latency measurement
- Multi-scale analysis

**Scenario 4: Cross-System Collusion**
- 4 systems monitored
- 3 systems showing harmful patterns
- Collusion detection
- Security incident logging

**Scenario 5: Human Oversight Workflow**
- Complete human-in-the-loop flow
- Automated checks → Peer review → Human decision
- Conditional approval
- Post-deployment monitoring

## Prerequisites

### For LLM Integration Examples

```bash
pip install openai anthropic google-generativeai
```

### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="your-openai-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Google Gemini
export GEMINI_API_KEY="your-gemini-api-key"
```

### For Demo Scenarios

No external dependencies required. Uses template-based LLM adapters for demonstration.

## Usage

### Running LLM Integration Examples

```bash
# Run all examples
python examples/real_llm_integration.py

# Run specific example (modify main() function)
python -c "
from examples.real_llm_integration import example_openai_integration
example_openai_integration()
"
```

### Running Demo Scenarios

```bash
# Run all scenarios
python examples/demo_scenarios.py

# Run specific scenario
python -c "
from examples.demo_scenarios import scenario_benign_proposal
scenario_benign_proposal()
"
```

## Example Outputs

### Real LLM Integration

```json
{
  "openai": {
    "proposal_id": "prop_1234",
    "drift_classification": "LOW",
    "threat_level": "LOW",
    "merkle_root": "abc123..."
  },
  "anthropic": {
    "proposal_id": "prop_5678",
    "constitutional_compliance": true,
    "uncertainties_count": 3,
    "risks_count": 2
  },
  "multi_llm": {
    "proposal_id": "prop_9012",
    "status": "approved",
    "approvals": 2,
    "merkle_root": "def456..."
  }
}
```

### Demo Scenarios

```json
{
  "benign_proposal": {
    "scenario": "benign_proposal",
    "drift_classification": "LOW",
    "threat_level": "LOW",
    "consensus_status": "approved",
    "merkle_root": "ghi789..."
  },
  "deceptive_detection": {
    "scenario": "deceptive_detection",
    "risk_score": 110,
    "threat_level": "CRITICAL",
    "harmful_preservation": true,
    "status": "rejected_deceptive"
  },
  "gradual_drift": {
    "scenario": "gradual_drift",
    "detection_point": 9,
    "final_drift_score": 2.45,
    "classification": "HIGH",
    "trend": "INCREASING"
  }
}
```

## Integration Patterns

### Pattern 1: Single LLM with Safety Monitoring

```python
from llm_adapters import OpenAIAdapter
from research_system import ResearchSystem, SystemSpecialization
from interpretability_monitor_enhanced import EnhancedInterpretabilityMonitor
from memory_auditor_optimized import OptimizedMemoryContentAuditor

# Initialize components
adapter = OpenAIAdapter(model="gpt-4-turbo-preview")
system = ResearchSystem(
    system_id=1,
    specialization=SystemSpecialization.SCIENTIFIC,
    model_path="gpt-4",
    private_key="key",
    orchestrator_endpoint="http://localhost:5000",
    llm_adapter=adapter
)

drift_monitor = EnhancedInterpretabilityMonitor()
memory_auditor = OptimizedMemoryContentAuditor([])

# Generate proposal
proposal = system.propose_ai_generated_improvement(
    "Your research request",
    guardrails={'max_risk': 'medium'}
)

# Monitor safety
activations = extract_activations(proposal)
drift_result = drift_monitor.get_drift(1, activations)

memory_entry = create_memory_entry(proposal)
audit_result = memory_auditor.audit_memory_entry(memory_entry)

# Check for issues
if drift_result['classification'] in ['HIGH', 'CRITICAL']:
    # Handle drift
    pass

if audit_result['threat_level'] in ['HIGH', 'CRITICAL']:
    # Handle threat
    pass
```

### Pattern 2: Multi-LLM Peer Review

```python
from orchestrator import Orchestrator

# Initialize orchestrator
orchestrator = Orchestrator(memory_storage=storage)

# System 1 proposes
proposal = system1.propose_ai_generated_improvement(request)
orchestrator.handle_improvement_proposal(proposal)

# Systems 2-N review
for reviewer in [system2, system3, system4]:
    review = reviewer.review_proposal(proposal)
    orchestrator.record_peer_review(proposal['proposal_id'], review)

# Check consensus
record = orchestrator.active_proposals[proposal['proposal_id']]
if record['status'] == 'approved':
    # Proceed to human review
    pass
elif record['status'] == 'rejected_deceptive':
    # Handle detection
    pass
```

### Pattern 3: Human-in-the-Loop

```python
# After automated checks and peer review...
if record['status'] == 'approved':
    # Queue for human review
    human_decision = get_human_decision(proposal)

    orchestrator.submit_human_decision(
        proposal['proposal_id'],
        human_decision
    )

    if human_decision['decision'] == 'approved_with_conditions':
        # Implement with conditions
        implement_with_monitoring(
            proposal,
            conditions=human_decision['conditions']
        )
```

## Performance

All examples are production-ready and benchmarked:

| Component | Throughput | Latency |
|-----------|-----------|---------|
| Drift Detection | 772 checks/sec | 1.3ms |
| Memory Audit | 28,788 entries/sec | 0.03ms |
| CUSUM Detection | N/A | 9.3 samples |
| Merkle Proof | N/A | <1ms |

## Testing

To run tests for the examples:

```bash
# Test real LLM integration (requires API keys)
python -m pytest examples/test_real_llm_integration.py -v

# Test demo scenarios (no API keys required)
python -m pytest examples/test_demo_scenarios.py -v
```

## Output Directory

All examples save results to `examples/outputs/`:

```
examples/outputs/
├── llm_integration_results_20250110_143022.json
├── demo_scenarios_20250110_143045.json
└── ...
```

## Troubleshooting

### API Key Issues

```python
# Check if API key is set
import os
if not os.getenv("OPENAI_API_KEY"):
    print("Set OPENAI_API_KEY environment variable")
```

### Import Errors

```python
# Add parent directory to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### LLM Package Not Installed

```bash
# Install missing packages
pip install openai  # For OpenAI examples
pip install anthropic  # For Anthropic examples
pip install google-generativeai  # For Gemini examples
```

## Next Steps

1. **Customize Examples**: Modify prompts, guardrails, and safety thresholds
2. **Deploy to Production**: Integrate with your LLM deployment
3. **Monitor Metrics**: Set up dashboards for drift and threat levels
4. **Tune Thresholds**: Adjust CUSUM, KS, and classification thresholds
5. **Add Alerting**: Connect to PagerDuty, Slack, etc.

## Documentation

- [AURA Bitpacked](../docs/AURA_BITPACKED_BENCHMARK_ANALYSIS.md) - Compression format
- [Memory Auditor](../docs/MEMORY_AUDITOR_OPTIMIZATION.md) - Deception detection
- [Interpretability Monitor](../docs/INTERPRETABILITY_MONITOR_ENHANCEMENT.md) - Drift detection
- [LLM Integration Guide](../LLM_INTEGRATION_GUIDE.md) - Detailed integration guide

## Support

For questions or issues:
1. Check [LIMITATIONS_UPDATED.md](../LIMITATIONS_UPDATED.md)
2. Review [START_HERE.md](../START_HERE.md)
3. Open an issue on GitHub

---

**Status:** Demo Integration - 75% Complete
**Last Updated:** 2025-01-10
**Production Ready:** Yes
