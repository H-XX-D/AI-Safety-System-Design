# Jetson Nano Quick Deployment Checklist

## Essential Tools & Adapters

### ✅ Core Components (Required)

1. **LLM Adapter** (`llm_adapters.py`)
   - Choose one: `GeminiAdapter`, `OpenAIAdapter`, `ClaudeAdapter`, or `TemplateLLMAdapter`
   - Must implement `BaseLLMAdapter.generate_improvement()`
   - Returns `LLMAdapterResult` with proposal structure

2. **Research System** (`research_system.py`)
   - `ResearchSystem` class - main agent logic
   - Handles proposal generation and submission
   - Manages peer review participation

3. **Proposal Generator**
   - `propose_improvement()` method
   - Creates structured proposals with:
     - Title, motivation, changes
     - Expected benefits, testable predictions
     - Rollback plan, risks, uncertainties

4. **Communication Layer**
   - HTTP client (`requests` library)
   - WebSocket client (for real-time updates)
   - ORKASTRATOR API endpoints

5. **Translation/Compression**
   - `translator.py` / `hardware_translator.py` - Human-readable audit trail
   - `aura_compressor.py` - Efficient proposal compression

### ✅ Safety & Validation (Required)

6. **Alignment Filter** (`alignment_filter.py`)
   - Validates proposals against core values
   - Checks for forbidden modifications

7. **Sandbox Manager** (`orchestrator_sandbox.py`)
   - Isolated code execution
   - Resource limits enforcement
   - Test result capture

8. **Peer Review Tools** (`debate_engine.py`)
   - Submit review votes
   - Provide feedback
   - Track consensus

### ✅ Configuration Files

9. **Agent Configuration**
   - Agent ID (1-5 for research agents)
   - Specialization (SCIENTIFIC, ENGINEERING, THEORETICAL, HISTORICAL, NOVEL)
   - LLM API keys
   - ORKASTRATOR endpoint URL

10. **System Configuration** (`config/default.yaml`)
    - LLM adapter settings
    - Guardrails (max_risk, banned_imports)
    - Resource limits

---

## Minimal Python Dependencies

```bash
pip install requests websocket-client
pip install google-generativeai  # For Gemini
# OR
pip install openai  # For OpenAI
# OR  
pip install anthropic  # For Claude
```

---

## Key Files to Deploy

```
jetson_nano/
├── research_system.py          # Core agent logic
├── llm_adapters.py             # LLM integration
├── translator.py               # Human-readable translation
├── hardware_translator.py      # Hardware-specific translation
├── aura_compressor.py          # Proposal compression
├── orchestrator_sandbox.py     # Sandbox execution
├── debate_engine.py            # Peer review
├── alignment_filter.py         # Safety validation
├── config/
│   └── default.yaml            # Configuration
└── jetson_nano_agent.py        # Main entry point
```

---

## Critical Constraints

### ❌ NEVER Allow Agents To Modify:
- `core_values.py`
- `alignment_filter.py`
- `worm_usb_verifier.py`
- `translator.py`
- `reward_calculation.py`
- Any ORKASTRATOR oversight components

### ✅ Agents CAN Modify:
- Their own research code
- Their own proposal logic
- Their own optimization algorithms
- Their own data processing

---

## Quick Start Example

```python
from research_system import ResearchSystem, SystemSpecialization
from llm_adapters import GeminiAdapter
import os

# 1. Initialize adapter
adapter = GeminiAdapter(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

# 2. Initialize agent
agent = ResearchSystem(
    system_id=1,
    specialization=SystemSpecialization.SCIENTIFIC,
    llm_adapter=adapter
)

# 3. Generate proposal
proposal = agent.propose_improvement(
    component="my_module",
    motivation="Improve accuracy"
)

# 4. Submit to ORKASTRATOR
import requests
requests.post("http://orka-host:5000/api/proposals", json=proposal.to_dict())
```

---

## Testing Checklist

- [ ] Proposal generation works
- [ ] LLM adapter connects successfully
- [ ] Proposals submit to ORKASTRATOR
- [ ] Peer review votes can be submitted
- [ ] Sandbox execution works
- [ ] WORM USB write access verified
- [ ] Network connectivity confirmed
- [ ] API keys configured correctly

---

See `docs/JETSON_NANO_DEPLOYMENT.md` for complete details.


