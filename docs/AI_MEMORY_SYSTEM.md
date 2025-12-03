# AI Memory System

## Overview

Each AI agent has a **three-tier memory architecture**:

1. **Short-term temporary memory** - On-board disk (local to each AI)
2. **Long-term memory** - On disk (persistent storage)
3. **Shared memory** - On orchestrator (shared across all AIs)

## Architecture

### 1. Short-Term Memory (On-Board Disk)

**Location**: `data/agents/{agent_id}/short_term/memory.json`

**Purpose**: Fast, local storage for recent information that may be discarded after a period of time.

**Use Cases**:
- Recent research queries and results
- Current proposal context
- Temporary calculations
- Session-specific data

**Characteristics**:
- Fast read/write (local disk)
- Can be cleared periodically
- Agent-specific (not shared)

### 2. Long-Term Memory (On Disk)

**Location**: `data/agents/{agent_id}/long_term/memory.json`

**Purpose**: Important information that should persist across sessions and be available long-term.

**Use Cases**:
- Hypothesis contradictions (what doesn't work)
- Learned patterns and strategies
- Important research findings
- Agent-specific knowledge base

**Characteristics**:
- Persistent across sessions
- Searchable
- Agent-specific (not shared)

### 3. Shared Memory (On Orchestrator)

**Location**: `data/orchestrator/shared_memory.json`

**Purpose**: Information accessible to all AIs for collaboration and coordination.

**Use Cases**:
- Shared research findings
- Common knowledge base
- Coordination signals
- System-wide insights

**Characteristics**:
- Accessible to all agents
- Centralized on orchestrator
- Can be read/written by any agent

## Usage

### Initialization

```python
from integrations.ai_memory_system import AIMemorySystem

# In ResearchSystem.__init__
agent_id = f"agent_{system_id}"
self.memory = AIMemorySystem(
    agent_id=agent_id,
    orchestrator_endpoint=orchestrator_endpoint
)
```

### Writing to Memory

```python
# Short-term memory (temporary)
self.memory.short_term.write(
    key="current_research_query",
    value="transformer optimization",
    metadata={'timestamp': '2024-01-15'}
)

# Long-term memory (persistent)
self.memory.long_term.write(
    key="learned_pattern:attention_optimization",
    value={"method": "sparse attention", "improvement": "30%"},
    metadata={'source': 'research', 'verified': True}
)

# Shared memory (accessible to all)
self.memory.shared.write(
    key="shared_finding:new_optimization",
    value={"technique": "flash attention", "speedup": "2x"},
    metadata={'discovered_by': 'agent_1'}
)
```

### Reading from Memory

```python
# Read from short-term
current_query = self.memory.short_term.read("current_research_query")

# Read from long-term
pattern = self.memory.long_term.read("learned_pattern:attention_optimization")

# Read from shared
shared_finding = self.memory.shared.read("shared_finding:new_optimization")
```

### Hypothesis Contradiction Notes

When PaperQA says a hypothesis won't work, the AI can note it in long-term memory:

```python
# Note hypothesis contradiction
self.memory.note_hypothesis_contradiction(
    hypothesis_id="hyp_123",
    hypothesis="Use method X for optimization",
    evidence="Research shows method X fails under load"
)

# Later, check if hypothesis was noted
note = self.memory.get_hypothesis_note("hyp_123")
if note:
    print(f"Hypothesis contradicts evidence: {note['evidence']}")
```

## Storage Structure

### Short-Term Memory File

```json
{
  "key1": {
    "key": "key1",
    "value": "...",
    "timestamp": "2024-01-15T10:30:00",
    "metadata": {}
  }
}
```

### Long-Term Memory File

```json
{
  "hypothesis_contradiction:hyp_123": {
    "key": "hypothesis_contradiction:hyp_123",
    "value": {
      "hypothesis": "...",
      "evidence": "...",
      "noted_at": "2024-01-15T10:30:00"
    },
    "timestamp": "2024-01-15T10:30:00",
    "metadata": {"type": "hypothesis_contradiction"}
  }
}
```

### Shared Memory File (Orchestrator)

```json
{
  "shared_finding:new_optimization": {
    "value": {...},
    "timestamp": "2024-01-15T10:30:00",
    "agent_id": "agent_1",
    "metadata": {}
  }
}
```

## Integration with PaperQA Feedback

When PaperQA says a hypothesis won't work:

1. **Tiny reward** (+0.00001) for querying
2. **Cooldown** activated for queries
3. **Note in long-term memory** if hypothesis contradicts evidence
4. **If agent tries anyway and succeeds** → Big reward multiplier

```python
# In paperqa_feedback_system.py
if contradicts_evidence and agent_memory:
    agent_memory.note_hypothesis_contradiction(
        hypothesis_id=hypothesis_id,
        hypothesis=hypothesis,
        evidence=evidence_contradiction
    )
```

## Orchestrator Shared Memory API

The orchestrator provides methods for shared memory:

```python
# Write to shared memory
orchestrator.write_shared_memory(
    key="shared_key",
    value={"data": "..."},
    agent_id="agent_1",
    metadata={}
)

# Read from shared memory
value = orchestrator.read_shared_memory("shared_key")

# List all keys
keys = orchestrator.list_shared_memory_keys()
```

## Benefits

1. **Separation of Concerns**: Different memory types for different purposes
2. **Performance**: Short-term memory is fast, long-term is persistent
3. **Collaboration**: Shared memory enables coordination
4. **Learning**: Long-term memory stores what doesn't work
5. **Scalability**: Each agent has its own storage

## File Locations

```
data/
├── agents/
│   ├── agent_1/
│   │   ├── short_term/
│   │   │   └── memory.json
│   │   └── long_term/
│   │       └── memory.json
│   ├── agent_2/
│   │   ├── short_term/
│   │   │   └── memory.json
│   │   └── long_term/
│   │       └── memory.json
│   └── ...
└── orchestrator/
    └── shared_memory.json
```

## Thread Safety

All memory operations are thread-safe using locks:
- Short-term memory: `_lock`
- Long-term memory: `_lock`
- Shared memory: `shared_memory_lock` (on orchestrator)

## Error Handling

Memory operations gracefully handle errors:
- Failed loads → Empty cache
- Failed saves → Logged but don't crash
- Network errors (shared memory) → Return None, log error






