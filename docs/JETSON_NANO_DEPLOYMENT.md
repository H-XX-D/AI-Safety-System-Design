# Jetson Nano Deployment Guide
## Tools and Adapters for Self-Improvement Pipeline Proposal Logic

### Overview

When deploying models to Jetson Nano devices for the self-improvement pipeline, you need to provide specific tools and adapters that enable agents to:
1. Generate improvement proposals for their own code
2. Participate in peer review
3. Test proposals in isolated environments
4. Communicate with ORKASTRATOR oversight system

---

## Required Components

### 1. **LLM Adapter Interface** (`BaseLLMAdapter`)

Each Jetson Nano needs an adapter that implements the `BaseLLMAdapter` interface from `research_system.py`:

**Required Methods:**
- `generate_improvement()` - Creates structured proposals
- Returns `LLMAdapterResult` with:
  - `title` - Proposal title
  - `motivation` - Why this improvement is needed
  - `changes` - Specific code/module changes
  - `expected_benefits` - Anticipated improvements
  - `testable_predictions` - How to verify success
  - `rollback_plan` - How to revert if needed
  - `identified_risks` - Potential issues
  - `admitted_uncertainties` - Known limitations
  - `confidence` - Confidence score (0.0-1.0)

**Available Adapters:**
- `GeminiAdapter` (recommended) - Google Gemini API
- `OpenAIAdapter` - OpenAI GPT-4
- `ClaudeAdapter` - Anthropic Claude
- `TemplateLLMAdapter` - Deterministic stub for testing

**Configuration:**
```yaml
llm:
  adapter_type: gemini  # or openai, claude, template
  gemini:
    model: gemini-1.5-pro-latest
    temperature: 0.4
    max_output_tokens: 2048
  guardrails:
    max_risk: medium  # low, medium, high
```

---

### 2. **Proposal Generation Tools**

**Core Tool: `ResearchSystem`**
- Located in `research_system.py`
- Handles proposal lifecycle
- Manages peer review coordination
- Tracks proposal state

**Key Functions:**
```python
from research_system import ResearchSystem, SystemSpecialization

# Initialize agent
agent = ResearchSystem(
    system_id=1,  # Unique ID (1-5 for research agents)
    specialization=SystemSpecialization.SCIENTIFIC,  # or ENGINEERING, THEORETICAL, HISTORICAL, NOVEL
    llm_adapter=gemini_adapter  # Your LLM adapter instance
)

# Generate proposal
proposal = agent.propose_improvement(
    component="deception_detector",  # Target component (agent's own code)
    motivation="Improve accuracy by adding ensemble method",
    research_context={"current_accuracy": 0.78}
)
```

---

### 3. **Communication Adapters**

**A. Message Translator (`translator.py` / `hardware_translator.py`)**
- Translates proposals to human-readable format
- Creates audit trails
- Handles air-gapped communication
- Required for WORM USB verification

**B. AURA Compression (`aura_compressor.py`)**
- Compresses proposals for efficient storage
- Bit-packed codecs for Jetson memory constraints
- Required for proposal transmission

**C. Network Communication**
- HTTP client for ORKASTRATOR API calls
- WebSocket support for real-time updates
- Message queue for proposal submission

---

### 4. **Sandbox Testing Tools**

**Sandbox Environment Manager (`orchestrator_sandbox.py`)**
- Isolated execution environment
- Resource limits (CPU, memory, disk)
- Module allowlists
- Static import guards

**Required Capabilities:**
- Execute proposal code safely
- Capture execution results
- Enforce resource limits
- Generate test reports

**Configuration:**
```python
from orchestrator_sandbox import SandboxEnvironmentManager

sandbox = SandboxEnvironmentManager(
    max_cpu_percent=80,
    max_memory_mb=2048,
    allowed_modules=['numpy', 'scipy'],  # Whitelist
    timeout_seconds=30
)
```

---

### 5. **Peer Review Tools**

**Debate Engine (`debate_engine.py`)**
- Multi-round peer review
- Structured claims and counterarguments
- Consensus calculation
- Scoring system

**Required Functions:**
- Submit review votes
- Provide feedback
- Track consensus
- Generate review summaries

---

### 6. **Safety and Validation Tools**

**A. Alignment Filter (`alignment_filter.py`)**
- Validates proposals against core values
- Checks for forbidden modifications
- Enforces guardrails

**B. Deception Detector (`deception_detector.py`)**
- Seven-method detection system
- Pattern analysis
- Consistency checks
- Confidence scoring

**C. Proposal Validator**
- Checks proposal structure
- Validates code syntax
- Verifies testability
- Ensures rollback plan exists

---

## Jetson Nano Specific Requirements

### Hardware Constraints
- **Memory**: 8GB LPDDR5 (shared CPU/GPU)
- **CUDA Cores**: 1024 (Ampere architecture)
- **Power**: 15W TDP
- **Storage**: MicroSD card (64GB+ recommended)

### Software Stack

**Base System:**
```bash
# JetPack 5.x (Ubuntu 20.04/22.04)
# CUDA 11.4+ or 12.x
# cuDNN 8.x
# TensorRT 8.x
```

**Python Environment:**
```bash
# Python 3.10+
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers accelerate
pip install requests websocket-client
pip install google-generativeai  # For Gemini adapter
```

**Model Inference:**
- Use TensorRT for optimized inference
- Quantization (INT8/FP16) recommended
- Batch size = 1 for memory efficiency
- Use CUDA streams for async processing

---

## Deployment Checklist

### Pre-Deployment
- [ ] Install JetPack SDK
- [ ] Set up Python 3.10+ virtual environment
- [ ] Install CUDA/cuDNN/TensorRT
- [ ] Configure network access (for API calls)
- [ ] Set up WORM USB mount point (`/media/usb`)
- [ ] Install system dependencies

### Core Components
- [ ] Deploy `research_system.py`
- [ ] Deploy `llm_adapters.py` (or custom adapter)
- [ ] Deploy `translator.py` / `hardware_translator.py`
- [ ] Deploy `aura_compressor.py`
- [ ] Deploy `orchestrator_sandbox.py`
- [ ] Deploy `debate_engine.py`
- [ ] Deploy `alignment_filter.py`
- [ ] Deploy `deception_detector.py`

### Configuration
- [ ] Set agent ID (1-5 for research agents)
- [ ] Set specialization (SCIENTIFIC, ENGINEERING, etc.)
- [ ] Configure LLM adapter (API keys, model selection)
- [ ] Set ORKASTRATOR endpoint URL
- [ ] Configure sandbox limits
- [ ] Set up logging

### Testing
- [ ] Test proposal generation
- [ ] Test peer review submission
- [ ] Test sandbox execution
- [ ] Test communication with ORKASTRATOR
- [ ] Verify WORM USB write access
- [ ] Test rollback procedures

---

## Proposal Workflow Integration

### Step-by-Step Process

1. **Proposal Generation**
   ```python
   # Agent identifies improvement opportunity
   proposal = agent.propose_improvement(
       component="my_module",
       motivation="...",
       research_context={...}
   )
   ```

2. **Local Testing**
   ```python
   # Test in isolated sandbox
   sandbox_result = sandbox.execute_proposal(proposal)
   ```

3. **Submission to ORKASTRATOR**
   ```python
   # Submit via HTTP API
   response = requests.post(
       f"{ORKASTRATOR_URL}/api/proposals",
       json=proposal.to_dict()
   )
   ```

4. **Peer Review Participation**
   ```python
   # Review other agents' proposals
   review = agent.review_proposal(
       proposal_id=other_proposal_id,
       approved=True,
       comments="..."
   )
   ```

5. **ORKA Counterpoint Response**
   ```python
   # Respond to ORKA challenges
   defense = agent.defend_proposal(
       proposal_id=my_proposal_id,
       counterpoint=orka_challenge,
       response="..."
   )
   ```

6. **Final Validation**
   - VAL offline validation (handled by ORKASTRATOR)
   - Human approval (if required)
   - Deployment to agent's codebase

---

## Critical Constraints

### ❌ FORBIDDEN Modifications
Agents **CANNOT** propose changes to:
- `core_values.py` - Immutable human values
- `alignment_filter.py` - Alignment checking logic
- `worm_usb_verifier.py` - Hardware verification
- `translator.py` - Air-gapped translator
- `reward_calculation.py` - Reward function
- ORKASTRATOR oversight components

### ✅ ALLOWED Modifications
Agents **CAN** propose changes to:
- Their own research logic
- Their own proposal generation code
- Their own peer review strategies
- Their own optimization algorithms
- Their own data processing methods

---

## Example Minimal Deployment

```python
# jetson_nano_agent.py
from research_system import ResearchSystem, SystemSpecialization
from llm_adapters import GeminiAdapter
from paperqa_client import PaperQAClient  # Lightweight PaperQA client
import os

# Initialize LLM adapter
gemini = GeminiAdapter(
    api_key=os.getenv("GOOGLE_GEMINI_API_KEY"),
    model="gemini-1.5-pro-latest"
)

# Initialize research agent
agent = ResearchSystem(
    system_id=1,  # TIF (Scientific)
    specialization=SystemSpecialization.SCIENTIFIC,
    llm_adapter=gemini
)

# Initialize PaperQA client (connects to main ORKASTRATOR server)
paperqa = PaperQAClient(
    server_url=os.getenv("ORKASTRATOR_URL", "http://orka-host:5001")
)

# Generate proposal
proposal = agent.propose_improvement(
    component="data_analysis_module",
    motivation="Improve statistical accuracy",
    research_context={"current_method": "basic_regression"}
)

# Get evidence for the proposal using main ORKASTRATOR's PaperQA
evidence = paperqa.get_evidence(
    claim=proposal['motivation'],
    sources=['arxiv', 'semantic_scholar', 'papers_with_code']
)

# Add evidence to proposal
if evidence.get('success'):
    proposal['evidence'] = evidence.get('evidence', '')
    proposal['supporting_sources'] = evidence.get('sources', [])

# Submit to ORKASTRATOR
import requests
response = requests.post(
    "http://orka-host:5001/api/proposals",
    json=proposal.to_dict()
)
```

## Lightweight PaperQA Client

The `paperqa_client.py` provides a lightweight way to access ORKASTRATOR's PaperQA system without requiring heavy dependencies on the Jetson Nano.

### Features

- **Minimal Dependencies**: Only requires `requests` library
- **Remote Access**: Connects to main ORKASTRATOR server
- **Source Selection**: Can specify which research APIs to use
- **Health Checking**: Verify server connectivity

### Usage

```python
from paperqa_client import PaperQAClient

# Connect to ORKASTRATOR
client = PaperQAClient(server_url='http://orka-host:5001')

# Search for evidence
result = client.search("What is machine learning?")
print(result['answer'])

# Get evidence for a claim
evidence = client.get_evidence(
    claim="Machine learning improves accuracy",
    sources=['arxiv', 'semantic_scholar']
)
```

### CLI Usage

```bash
# Search
python3 paperqa_client.py search "What is neural networks?"

# Get evidence
python3 paperqa_client.py evidence "Machine learning is safe"

# Check health
python3 paperqa_client.py health
```

---

## Troubleshooting

### Memory Issues
- Use model quantization (INT8/FP16)
- Reduce batch size to 1
- Enable gradient checkpointing
- Use CPU offloading for large models

### Network Issues
- Check ORKASTRATOR endpoint accessibility
- Verify API keys are set
- Test with `curl` first
- Check firewall rules

### Sandbox Issues
- Verify Docker/container runtime
- Check resource limits
- Ensure module allowlists are correct
- Review execution logs

---

## Additional Resources

- **Jetson Documentation**: https://docs.nvidia.com/jetson
- **CUDA Toolkit**: https://developer.nvidia.com/cuda-toolkit
- **TensorRT**: https://developer.nvidia.com/tensorrt
- **System Architecture**: See `docs/misc/SELF_IMPROVEMENT_CLARIFICATION.md`
- **Proposal Workflow**: See `docs/misc/PROPOSAL_WORKFLOW.md`

