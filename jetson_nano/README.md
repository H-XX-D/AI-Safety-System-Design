# Jetson Nano Lightweight Tools

## PaperQA Client

**IMPORTANT SECURITY NOTE**: This is a **CLIENT-ONLY** implementation.

- ✅ Jetson Nanos have a lightweight HTTP client (only `requests` library)
- ❌ Jetson Nanos do **NOT** have PaperQA installed
- ❌ Jetson Nanos do **NOT** have access to the PaperQA program
- ✅ All evidence search happens on the main ORKASTRATOR server
- ✅ Jetson Nanos only receive formatted results via HTTP

This ensures that:
- No heavy ML/AI libraries needed on resource-constrained Nanos
- No direct access to evidence documents or search capabilities
- Centralized control and security on ORKASTRATOR server
- Nanos can only query, not modify or access the system directly

### Installation

```bash
# Only requires requests library (already minimal)
pip install requests
```

### Usage

#### Python API

```python
from paperqa_client import PaperQAClient

# Initialize client
client = PaperQAClient(
    server_url='http://orka-host:5001',
    api_key='your-api-key'  # Optional
)

# Search for evidence
result = client.search("What is machine learning?")
print(result['answer'])

# Get evidence for a claim
evidence = client.get_evidence(
    claim="Machine learning improves accuracy",
    sources=['arxiv', 'semantic_scholar']
)
print(evidence['evidence'])
```

#### Command Line

```bash
# Search
python3 paperqa_client.py search "What is neural networks?"

# Get evidence for a claim
python3 paperqa_client.py evidence "Machine learning is safe"

# Use specific sources
python3 paperqa_client.py search "transformer architecture" --sources arxiv papers_with_code

# Check server health
python3 paperqa_client.py health
```

### Configuration

Set environment variables:

```bash
export ORKASTRATOR_URL="http://orka-host:5001"
export ORKASTRATOR_API_KEY="your-api-key"  # Optional
```

### Integration with Research System

```python
from research_system import ResearchSystem
from paperqa_client import PaperQAClient

# Initialize systems
agent = ResearchSystem(system_id=1, specialization=SystemSpecialization.SCIENTIFIC)
paperqa = PaperQAClient()

# Generate proposal
proposal = agent.propose_improvement(
    component="deception_detector",
    motivation="Improve accuracy"
)

# Get evidence for the proposal
evidence = paperqa.get_evidence(
    claim=proposal['motivation'],
    sources=['arxiv', 'semantic_scholar', 'papers_with_code']
)

# Use evidence in proposal submission
if evidence.get('supporting'):
    print("Found supporting evidence!")
    # Submit proposal with evidence
```

### Features

- **Lightweight**: Only requires `requests` library
- **No Heavy Dependencies**: Doesn't need PaperQA, transformers, or LLM libraries on Nano
- **Remote Access**: Connects to main ORKASTRATOR server
- **Source Selection**: Can specify which research APIs to use
- **Health Checking**: Verify server connectivity

### Error Handling

The client handles network errors gracefully:

```python
result = client.search("query")
if not result.get('success'):
    print(f"Error: {result.get('error')}")
    # Fallback logic here
```

### Security

**Client-Side (Jetson Nano):**
- Only HTTP client library (`requests`)
- No access to PaperQA code or data
- Can only send queries and receive results
- Timeout protection (default 30 seconds)

**Server-Side (ORKASTRATOR):**
- Input validation and length limits
- Source whitelisting
- All processing happens server-side
- API key authentication (optional)
- HTTPS support (use `https://` in server URL)

**Architecture:**
```
Jetson Nano (Client)          ORKASTRATOR Server
┌─────────────────┐          ┌──────────────────────┐
│ paperqa_client  │  HTTP    │  PaperQA Engine      │
│ (requests only) │ ────────>│  + Research APIs     │
│                 │          │  + Evidence Docs     │
│ No PaperQA      │ <────────│  + Full Processing   │
│ No ML Libraries │  Results │                      │
└─────────────────┘          └──────────────────────┘
```

This ensures Jetson Nanos have **zero access** to the PaperQA program itself.

