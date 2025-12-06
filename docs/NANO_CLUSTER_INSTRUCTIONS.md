# Nano Cluster Instructions

## Overview

The AI Safety System runs on a distributed cluster of 8 nodes:
- **7 Jetson Orin Nano Super** (8GB RAM each) - Research agents
- **1 HP Z6 Workstation** (16GB VRAM) - Orchestrator (ORKA)

Each nano runs **Ollama** with a specialized LLM optimized for its role.

## Cluster Architecture

```
                    ┌─────────────────────────────────────────┐
                    │      HP Z6 WORKSTATION (ORKA)           │
                    │      qwen2.5:14b (16GB VRAM)            │
                    │  ┌─────────────────────────────────────┐│
                    │  │ SharedMemory │ Orchestrator │ UI    ││
                    │  │ (port 5000)  │              │(5001) ││
                    │  └─────────────────────────────────────┘│
                    └────────────────┬────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
    ┌──────┴──────┐           ┌──────┴──────┐           ┌──────┴──────┐
    │             │           │             │           │             │
┌───┴───┐ ┌───┴───┐   ┌───┴───┐ ┌───┴───┐   ┌───┴───┐ ┌───┴───┐ ┌───┴───┐
│  GIN  │ │ ORIN  │   │  TIF  │ │ TORI  │   │PAGEQA │ │ ARCHI │ │ GUARD │
│.242   │ │ .160  │   │ .213  │ │ .235  │   │ .168  │ │ .232  │ │ .146  │
└───────┘ └───────┘   └───────┘ └───────┘   └───────┘ └───────┘ └───────┘
```

## Node Details

| Node | IP | Model | RAM | Role | User |
|------|-----|-------|-----|------|------|
| **ORKA** | localhost | qwen2.5:14b | 16GB VRAM | Orchestrator | xx |
| **GIN** | 192.168.0.242 | deepseek-r1:1.5b | 8GB | Code Generation | gin |
| **ORIN** | 192.168.0.160 | deepseek-r1:1.5b | 8GB | Research Coordination | orin |
| **TIF** | 192.168.0.213 | deepseek-r1:1.5b | 8GB | Technical Analysis | tif |
| **TORI** | 192.168.0.235 | gemma3:4b | 8GB | Review & Optimization | tori |
| **PAGEQA** | 192.168.0.168 | qwen2.5:3b | 8GB | Document Q&A | page |
| **ARCHI** | 192.168.0.232 | qwen2.5:3b | 8GB | Architecture Design | archi |
| **GUARD** | 192.168.0.146 | llama-guard3:1b | 8GB | Safety Checking | guard |

## SSH Access

All nanos use password `1` for SSH access:

```bash
# Connect to any nano
ssh <user>@<ip>
# Password: 1

# Examples:
ssh gin@192.168.0.242
ssh tori@192.168.0.235
ssh guard@192.168.0.146
```

## Ollama Commands

Each nano runs Ollama on port 11434:

```bash
# Check models on a nano
ssh gin@192.168.0.242 "ollama list"

# Generate text
curl http://192.168.0.242:11434/api/generate -d '{
  "model": "deepseek-r1:1.5b",
  "prompt": "Hello, how are you?",
  "stream": false
}'

# Chat with model
curl http://192.168.0.242:11434/api/chat -d '{
  "model": "deepseek-r1:1.5b",
  "messages": [{"role": "user", "content": "Hello!"}],
  "stream": false
}'
```

## Using the Nano Cluster Module

```python
from tools.nano_cluster import get_cluster, NanoRole

# Get cluster instance
cluster = get_cluster()

# Check all nodes
status = cluster.check_all_status()
print(status)
# {'GIN': True, 'ORIN': True, 'TIF': True, ...}

# Generate on a specific node
response = cluster.generate_on_node("GIN", "Write a hello world in Python")

# Generate on best available node
response, node_name = cluster.generate_on_best_available(
    "Explain quantum computing",
    prefer_role=NanoRole.TIF  # Prefer technical analysis
)

# Broadcast to all nodes
responses = cluster.broadcast_prompt("What is 2+2?")
# {'GIN': '4', 'ORIN': '4', ...}

# Safety check via GUARD
safety = cluster.check_safety("Some content to check")
print(safety)
# {'safe': True, 'response': 'SAFE', 'checked_by': 'GUARD'}

# Get cluster stats
stats = cluster.get_cluster_stats()
print(f"Online: {stats['online_nodes']}/{stats['total_nodes']}")
```

## Integrated Systems

### 1. 3-Tier Memory System

Each nano can use the memory system for context and knowledge sharing:

```python
from memory.orchestrator_adapter import create_adapter_for_nano

# Create memory adapter for a nano
adapter = create_adapter_for_nano(
    nano_name="GIN",
    nano_ip="192.168.0.242"
)

# Get context for proposal evaluation
context = adapter.get_proposal_context(
    "Improve the sorting algorithm",
    max_similar=5
)

# Store proposal outcome
adapter.record_proposal_outcome(
    proposal_id="prop_123",
    outcome="approved",
    confidence_final=0.85,
    reward=0.75,
    reviews=[{"vote": "approve", "reviewer": "TORI"}]
)
```

### 2. Communication Codec

Efficient message encoding for inter-agent communication:

```python
from communication import MessageCodec

codec = MessageCodec()

# Encode a message
text = "System 1 approves proposal 001 with high confidence"
payload, method, meta = codec.encode(text)

# Decode
decoded_text, info = codec.decode(payload)
```

### 3. UI Integration

The cluster status is available via the UI API:

```bash
# Get cluster status
curl http://localhost:5001/api/cluster/status

# Generate via API
curl -X POST http://localhost:5001/api/cluster/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello", "node": "GIN"}'

# Safety check via API
curl -X POST http://localhost:5001/api/cluster/safety-check \
  -H "Content-Type: application/json" \
  -d '{"content": "Some text to check"}'
```

## Node Roles & Specializations

### GIN (Generative Improvement Navigator)
- **Model**: deepseek-r1:1.5b
- **Specialty**: Code generation and improvement proposals
- **Best for**: Writing new code, refactoring, optimization

### ORIN (Orchestration & Research Intelligence Node)
- **Model**: deepseek-r1:1.5b
- **Specialty**: Research coordination and synthesis
- **Best for**: Coordinating research tasks, literature synthesis

### TIF (Technical Improvement Finder)
- **Model**: deepseek-r1:1.5b
- **Specialty**: Technical analysis and debugging
- **Best for**: Finding bugs, performance issues, technical reviews

### TORI (Technical Optimization Review Intelligence)
- **Model**: gemma3:4b
- **Specialty**: Review and optimization
- **Best for**: Code review, optimization suggestions, best practices

### PAGEQA (Paper Q&A Specialist)
- **Model**: qwen2.5:3b
- **Specialty**: Document understanding and Q&A
- **Best for**: Reading papers, answering questions about documents

### ARCHI (Architecture & Design Specialist)
- **Model**: qwen2.5:3b
- **Specialty**: System architecture and design
- **Best for**: Design decisions, architecture planning, patterns

### GUARD (Safety Guardian)
- **Model**: llama-guard3:1b
- **Specialty**: Safety checking and content moderation
- **Best for**: Checking proposals for safety, content filtering

### ORKA (Orchestration & Knowledge Aggregator)
- **Model**: qwen2.5:14b
- **Specialty**: Central coordination and final decisions
- **Best for**: Complex reasoning, final reviews, orchestration

## Maintenance

### Restart Ollama on a Nano
```bash
ssh <user>@<ip> "echo '1' | sudo -S systemctl restart ollama"
```

### Pull a New Model
```bash
ssh gin@192.168.0.242 "ollama pull <model-name>"
```

### Check Ollama Logs
```bash
ssh gin@192.168.0.242 "journalctl -u ollama -n 50"
```

### Check GPU Memory
```bash
ssh gin@192.168.0.242 "tegrastats --interval 1000" 
# Press Ctrl+C to stop
```

## Troubleshooting

### Node Not Responding
1. Check if nano is powered on
2. Try SSH: `ssh gin@192.168.0.242`
3. If SSH works, check Ollama: `systemctl status ollama`
4. Restart if needed: `sudo systemctl restart ollama`

### Model Not Loaded
1. Check available models: `ollama list`
2. Pull required model: `ollama pull <model>`
3. Check disk space: `df -h`

### Slow Responses
1. Check if model is still loading: `ollama ps`
2. Check memory usage: `free -m`
3. Reduce `max_tokens` in generation requests

### Network Issues
1. Ping the nano: `ping 192.168.0.242`
2. Check if port 11434 is open: `nc -zv 192.168.0.242 11434`
3. Check router/switch connections

## Integrations

Each nano has access to specialized integrations based on its role:

### Available Integrations

| Integration | Category | Description | Nanos |
|-------------|----------|-------------|-------|
| **paperqa_rag** | research | Evidence-grounded research via local RAG | PAGEQA, ORIN |
| **robin_hypothesis** | research | Scientific hypothesis generation & experiment design | TIF, GIN, ORIN |
| **agent0_self_play** | training | Competitive hypothesis improvement via self-play | ORKA, TIF, GIN |
| **safety_quality_tools** | safety | Proposal validation, scoring, and deduplication | GUARD, TORI, ARCHI |
| **tool_servers** | execution | Agent0 code/bash execution tools | GIN, TIF |
| **ai_memory_system** | memory | Three-tier memory architecture per agent | ALL |
| **rl_trainer** | training | Reinforcement learning for self-improvement | ORKA |
| **tool_hypothesis** | research | Hypothesis generation tool for agents | TIF, GIN, ORIN, PAGEQA |

### Using Integrations in Python

```python
from tools import (
    get_integration_manager,
    get_integrations_for_nano,
    research_query,
    propose_improvement,
    validate_proposal,
)

# Get integrations for a specific nano
integrations = get_integrations_for_nano("TIF")
print(integrations)  # ['robin_hypothesis', 'agent0_self_play', 'tool_hypothesis', ...]

# Research using RAG
result = research_query("Best practices for deception detection", nano="PAGEQA")

# Generate improvement hypotheses
hypotheses = propose_improvement(
    target="deception_detector",
    context="Current detector has high false positive rate",
    nano="TIF"
)

# Validate a proposal
validation = validate_proposal(proposal_dict, nano="GUARD")
```

### Integration API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/integrations/status` | GET | Get status of all integrations |
| `/api/integrations/for-nano/<name>` | GET | Get integrations for a nano |
| `/api/integrations/research` | POST | Execute RAG research query |
| `/api/integrations/hypothesis` | POST | Generate improvement hypotheses |
| `/api/integrations/validate` | POST | Validate a proposal |
| `/api/integrations/execute` | POST | Execute code in sandbox |
| `/api/integrations/research-and-propose` | POST | Full research workflow |
| `/api/integrations/manager/status` | GET | Integration manager status |

### Example API Calls

```bash
# Get integration status
curl http://localhost:5001/api/integrations/status

# Get integrations for PAGEQA
curl http://localhost:5001/api/integrations/for-nano/PAGEQA

# Research query
curl -X POST http://localhost:5001/api/integrations/research \
  -H "Content-Type: application/json" \
  -d '{"query": "How to detect AI deception?", "nano": "PAGEQA"}'

# Generate hypotheses
curl -X POST http://localhost:5001/api/integrations/hypothesis \
  -H "Content-Type: application/json" \
  -d '{"target": "deception_detector", "nano": "TIF"}'

# Validate proposal
curl -X POST http://localhost:5001/api/integrations/validate \
  -H "Content-Type: application/json" \
  -d '{"proposal": {"title": "Improve X", "changes": ["..."]}, "nano": "GUARD"}'
```

## Autonomous Agents

Each nano operates as an **autonomous agent** that independently:
1. Monitors its area of expertise for improvement opportunities
2. Researches solutions via PAGEQA
3. Creates and submits proposals
4. Participates in peer review
5. Receives final decisions from ORKA

### Agent Roles

| Agent | Submits Proposals | Expertise | Role |
|-------|-------------------|-----------|------|
| **GIN** | ✅ Yes | Code generation & improvement | Proposer |
| **TIF** | ✅ Yes | Technical analysis & debugging | Proposer |
| **TORI** | ✅ Yes | Code review & optimization | Proposer |
| **ORIN** | ✅ Yes | NVIDIA/CUDA/Jetson optimization | Proposer |
| **ARCHI** | ✅ Yes | System architecture & design | Proposer |
| **GUARD** | ✅ Yes | Safety & security improvements | Proposer |
| **PAGEQA** | ❌ No | Research & documentation support | Researcher |
| **ORKA** | ❌ No | Orchestration & final decisions | Orchestrator |

### Workflow

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Agent  │───▶│ PAGEQA  │───▶│  Agent  │───▶│  Peers  │───▶│  ORKA   │
│  Idea   │    │Research │    │Proposal │    │ Review  │    │Decision │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

1. **Agent identifies improvement** in their domain (e.g., ORIN notices CUDA inefficiency)
2. **Agent requests research** from PAGEQA with specific questions
3. **PAGEQA researches** using RAG, papers, documentation
4. **Agent creates proposal** based on expertise + research findings
5. **Proposal enters pipeline** for peer review
6. **Other agents review** based on their expertise domains
7. **ORKA makes final decision** (approve/reject) based on reviews

### Using Autonomous Agents in Python

```python
from tools import (
    NANO_AGENTS,
    get_agent_manager,
    start_agent,
    stop_agent,
    start_all_agents,
    stop_all_agents,
    get_agent_status,
    get_all_agent_statuses,
    generate_proposal_for_agent,
    run_proposal_cycle,
)

# View all agent configurations
for name, agent in NANO_AGENTS.items():
    print(f"{name}: {agent.expertise} (submits: {agent.proposal_submitter})")

# Get the agent manager
manager = get_agent_manager()

# Start individual agents
start_agent("GIN")
start_agent("ORIN")

# Or start all agents
results = start_all_agents()

# Check agent status
status = get_agent_status("ORIN")
print(status)
# {'name': 'ORIN', 'role': 'proposer', 'expertise': 'NVIDIA & Hardware Optimization',
#  'can_submit_proposals': True, 'pending_proposals': 0, 'running': True}

# Get all statuses
all_statuses = get_all_agent_statuses()

# Generate a proposal for a specific agent
proposal = generate_proposal_for_agent("ORIN", topic="TensorRT optimization for inference")
print(proposal)
# {'agent': 'ORIN', 'title': 'TensorRT optimization...', 'domain': 'nvidia', ...}

# Run a full proposal cycle (research + create + submit)
result = run_proposal_cycle("GIN")

# Stop agents
stop_agent("GIN")
stop_all_agents()
```

### Autonomous Agent API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agents/status` | GET | Get status of all autonomous agents |
| `/api/agents/<name>/status` | GET | Get status of a specific agent |
| `/api/agents/<name>/start` | POST | Start an agent's autonomous operation |
| `/api/agents/<name>/stop` | POST | Stop an agent |
| `/api/agents/start-all` | POST | Start all agents |
| `/api/agents/stop-all` | POST | Stop all agents |
| `/api/agents/<name>/generate-proposal` | POST | Generate a proposal for an agent |
| `/api/agents/<name>/run-cycle` | POST | Run a full proposal cycle |
| `/api/agents/config` | GET | Get configuration of all agents |
| `/api/agents/manager/status` | GET | Get agent manager status |

### Example API Calls

```bash
# Get all agent statuses
curl http://localhost:5001/api/agents/status

# Get ORIN status
curl http://localhost:5001/api/agents/orin/status

# Start GIN agent
curl -X POST http://localhost:5001/api/agents/gin/start

# Start all agents
curl -X POST http://localhost:5001/api/agents/start-all

# Generate proposal for ORIN with specific topic
curl -X POST http://localhost:5001/api/agents/orin/generate-proposal \
  -H "Content-Type: application/json" \
  -d '{"topic": "CUDA memory optimization"}'

# Run full proposal cycle for ARCHI
curl -X POST http://localhost:5001/api/agents/archi/run-cycle

# Get all agent configurations
curl http://localhost:5001/api/agents/config

# Stop all agents
curl -X POST http://localhost:5001/api/agents/stop-all
```

### Agent Expertise Domains

Each proposer agent operates in specific domains:

| Agent | Proposal Domains | Review Domains |
|-------|-----------------|----------------|
| **GIN** | code, algorithms, implementation | code, implementation |
| **TIF** | debugging, performance, diagnostics | technical, performance |
| **TORI** | optimization, quality, best_practices | code, quality, optimization |
| **ORIN** | nvidia, cuda, jetson, gpu, hardware | hardware, performance, nvidia |
| **ARCHI** | architecture, design, scalability | architecture, design |
| **GUARD** | safety, security, alignment | safety, security |

