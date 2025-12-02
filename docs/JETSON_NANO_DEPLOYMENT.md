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
from paperqa_client import PaperQAClient  # Lightweight PaperQA & Research API client
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

# Initialize client (connects to main ORKASTRATOR server)
client = PaperQAClient(
    server_url=os.getenv("ORKASTRATOR_URL", "http://orka-host:5001")
)

# =========================================================================
# PHASE 1: PROPOSAL BUILDING - Direct Research API Access
# =========================================================================
# Researcher AI can freely query databases to gather information

# Search arXiv for relevant papers
arxiv_papers = client.research_arxiv("statistical regression optimization", limit=10)

# Search Semantic Scholar for citations
semantic_papers = client.research_semantic_scholar("machine learning accuracy")

# Search for any relevant vulnerabilities
cves = client.research_cve("data validation")

# Multi-source search
all_research = client.research_search(
    "statistical accuracy improvement",
    sources=['arxiv', 'semantic_scholar', 'papers_with_code'],
    limit_per_source=5
)

# Use gathered research to build proposal
proposal = agent.propose_improvement(
    component="data_analysis_module",
    motivation="Improve statistical accuracy using modern regression techniques",
    research_context={
        "current_method": "basic_regression",
        "related_papers": [p['title'] for p in arxiv_papers[:3]],
        "research_sources": all_research
    }
)

# =========================================================================
# PHASE 2: PROPOSAL SUBMISSION - Must go through PaperQA
# =========================================================================
# All evidence claims MUST be validated by PaperQA before submission

# Validate evidence through PaperQA (REQUIRED for submission)
evidence = client.get_evidence(
    claim=proposal['motivation'],
    sources=['arxiv', 'semantic_scholar', 'papers_with_code']
)

# Add VALIDATED evidence to proposal
if evidence.get('success'):
    proposal['evidence'] = evidence.get('evidence', '')
    proposal['supporting_sources'] = evidence.get('sources', [])
    proposal['evidence_validated'] = True  # Mark as validated by PaperQA
else:
    # Cannot submit without validated evidence
    raise ValueError("Evidence validation failed - cannot submit proposal")

# Submit to ORKASTRATOR (only with validated evidence)
import requests
response = requests.post(
    "http://orka-host:5001/api/proposals",
    json=proposal.to_dict()
)
```

## Lightweight PaperQA & Research API Client

The `paperqa_client.py` provides a lightweight way to access ORKASTRATOR's PaperQA system AND direct research database APIs without requiring heavy dependencies on the Jetson Nano.

### Two Access Modes

1. **Direct Research API Mode** (for proposal building): Raw database queries for gathering research
2. **PaperQA Mode** (for proposal submission): AI-processed evidence validation

### Access Rules

| Phase | Access Method | Purpose |
|-------|---------------|---------|
| **Proposal Building** | Direct Research APIs | Researcher AIs freely query databases (arXiv, Semantic Scholar, CVE, etc.) to gather information |
| **Proposal Submission** | PaperQA Only | All evidence claims must be validated through PaperQA before submission |

### Design Rationale: Separation of Concerns

> **"Researchers research. Validators validate."**

This architecture prevents researcher AIs from gaming the proposal system:

| Role | Researcher AIs | PaperQA |
|------|----------------|---------|
| **Specialization** | Research & Innovation | Evidence Validation |
| **Focus** | Explore ideas, form hypotheses, build proposals | Verify claims, cross-reference sources, detect inconsistencies |
| **NOT their job** | Validate their own claims | Generate proposals |

**Why this prevents gaming:**

| Attack Vector | Prevention |
|---------------|------------|
| Fabricated citations | PaperQA independently verifies sources exist |
| Cherry-picked evidence | PaperQA finds contradicting evidence too |
| Exaggerated claims | PaperQA cross-references actual paper content |
| Self-validation bias | Researcher cannot validate their own work |
| Optimizing for approval | Researcher focuses on research quality, not gaming validation |

**Benefits:**
- **Researchers stay honest** - They know claims will be independently verified
- **No incentive to game** - Gaming research phase doesn't help if validation catches it
- **Better proposals** - Focus on genuine evidence, not what might slip through
- **Specialized optimization** - Each AI optimizes for its actual job

This mirrors academic peer review - researchers don't validate their own papers!

### Features

- **Minimal Dependencies**: Only requires `requests` library
- **Remote Access**: Connects to main ORKASTRATOR server
- **Source Selection**: Can specify which research APIs to use
- **Health Checking**: Verify server connectivity
- **Direct Database Access**: Query research APIs without PaperQA processing

### Python Usage

```python
from paperqa_client import PaperQAClient

# Connect to ORKASTRATOR
client = PaperQAClient(server_url='http://orka-host:5001')

# =========================================
# PaperQA Mode (AI-processed evidence)
# =========================================

# Search for evidence with AI processing
result = client.search("What is machine learning?")
print(result['answer'])

# Get evidence for a claim
evidence = client.get_evidence(
    claim="Machine learning improves accuracy",
    sources=['arxiv', 'semantic_scholar']
)

# =========================================
# Direct Research API Mode (raw database access)
# =========================================

# Check which APIs are available
status = client.research_status()
print(status)

# Search multiple databases at once
results = client.research_search(
    "transformer attention mechanism",
    sources=['arxiv', 'semantic_scholar', 'papers_with_code'],
    limit_per_source=5
)

# Search arXiv directly
papers = client.research_arxiv("neural network optimization", limit=10)
for paper in papers:
    print(f"{paper['title']} - {paper['url']}")

# Search Semantic Scholar directly
papers = client.research_semantic_scholar("deep learning safety")

# Search Papers with Code
papers = client.research_papers_with_code("reinforcement learning")

# Search CVE vulnerabilities
cves = client.research_cve("buffer overflow")
for cve in cves:
    print(f"{cve['id']}: {cve['severity']}")

# Search IETF RFCs
rfcs = client.research_ietf("TLS 1.3")

# Search IEEE Xplore (requires API key on server)
papers = client.research_ieee("quantum computing")
```

### CLI Usage

```bash
# =========================================
# PaperQA Mode (AI-processed)
# =========================================

# Search with AI processing
python3 paperqa_client.py search "What is neural networks?"

# Get evidence for a claim
python3 paperqa_client.py evidence "Machine learning is safe"

# =========================================
# Direct Research API Mode
# =========================================

# Check available research APIs
python3 paperqa_client.py research-status

# Multi-source search
python3 paperqa_client.py research "transformer attention" --sources arxiv,semantic_scholar

# Search arXiv directly
python3 paperqa_client.py arxiv "neural network optimization" --limit 10

# Search Semantic Scholar directly
python3 paperqa_client.py semantic-scholar "deep learning safety"

# Search Papers with Code
python3 paperqa_client.py papers-with-code "reinforcement learning"

# Search CVE vulnerabilities
python3 paperqa_client.py cve "buffer overflow"

# Search IETF RFCs
python3 paperqa_client.py ietf "TLS 1.3"

# Search IEEE Xplore
python3 paperqa_client.py ieee "quantum computing"

# =========================================
# Other
# =========================================

# Check server health
python3 paperqa_client.py health
```

### Available Research Sources

| Source | Method | Description |
|--------|--------|-------------|
| arXiv | `research_arxiv()` | Scientific papers (physics, CS, math, etc.) |
| Semantic Scholar | `research_semantic_scholar()` | Academic papers with citations |
| Papers with Code | `research_papers_with_code()` | Papers with code repositories |
| CVE/NVD | `research_cve()` | Security vulnerabilities |
| IETF | `research_ietf()` | Internet standards (RFCs) |
| IEEE Xplore | `research_ieee()` | Engineering papers (requires API key) |
| Digi-Key | `research_digikey()` | Electronic components (requires API key) |
| Octopart | `research_octopart()` | Electronic parts search (requires API key) |

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

