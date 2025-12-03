# Specialist Isolation and Global Capability Promotion

## Problem Statement

When specialists propose improvements through RL, we want:
1. **Algorithmic improvements** (caching, routing, retrieval) to benefit ALL specialists
2. **Domain knowledge** to stay isolated per specialist (no homogenization)

Without isolation, RL will eventually train all specialists toward a generalist by leaking domain knowledge through shared parameters.

## Solution Architecture

### Two-Lane Parameter Isolation

**Specialist Lane (Isolated)**
- Per-specialist adapters (LoRA/IA³/adapters)
- Domain-specific knowledge
- Updated ONLY for the winning specialist on each RL step
- Separate replay buffers per specialist
- No cross-distillation

**Global Systems Lane (Shared)**
- Caching policy (LRU → ARC, TTL, admission)
- Routing scheduler (epsilon-greedy → UCB1 → Thompson)
- Retrieval config (k, rerank, hybrid weights)
- Updated through neutral benchmarks (no domain data)
- Promoted from code/config, not weights

### Promotion Pipeline

When a specialist proposes an algorithmic improvement:

```
1. Specialist proposes: "Switch cache from LRU to ARC"
   └─> Orchestrator classifies as "algorithmic" (not domain-specific)

2. Extract proposed policy from code/config
   └─> CachePolicy(policy='ARC', ttl_seconds=900, ...)

3. Run neutral benchmark suite
   └─> scripts/neutral_cache_bench.py --baseline LRU --proposed ARC
   └─> Workloads: repeated lookups, long-tail, multi-hop (NO domain data)

4. Check promotion criteria
   └─> Hit rate improvement > 5%
   └─> Latency degradation < 10%

5. If passed, promote to global config
   └─> config/default.yaml: cache.policy = ARC
   └─> All specialists benefit immediately
   └─> No weight sharing, no domain leakage
```

## Implementation

### 1. Global Systems Adapter

**File:** `core/systems_adapter.py`

```python
from core.systems_adapter import get_global_systems_adapter

adapter = get_global_systems_adapter()

# Check if proposal is algorithmic
if adapter.is_algorithmic_proposal(proposal):
    # Extract proposed policy
    new_policy = extract_cache_policy_from_proposal(proposal)
    
    # Run neutral benchmarks
    benchmark_results = run_neutral_cache_benchmark(
        baseline_policy=adapter.get_current_cache_policy().policy,
        proposed_policy=new_policy.policy
    )
    
    # Promote if criteria met
    promoted = adapter.promote_cache_improvement(
        proposal_id=proposal_id,
        new_policy=new_policy,
        benchmark_results=benchmark_results
    )
```

**Parameter Mask:**
- `global_params`: `{cache.policy, cache.ttl_seconds, routing.strategy, ...}`
- `specialist_params[specialist_id]`: `{adapter.layer_0, adapter.layer_1, ...}`
- `router_params`: `{router.weights, router.counts, router.rewards}`

### 2. Neutral Benchmarks

**File:** `scripts/neutral_cache_bench.py`

Generates domain-neutral caching workloads:
- **Repeated lookups** (Zipf distribution)
- **Long-tail** (80/20 hot/cold)
- **Multi-hop chains** (prefetch effectiveness)
- **TTL expiry** (time-aware caching)

```bash
python scripts/neutral_cache_bench.py --baseline LRU --proposed ARC --output results.json
```

### 3. Promotion Script

**File:** `scripts/promote_systems_capability.py`

```bash
# Test a proposal for promotion (dry run)
python scripts/promote_systems_capability.py --proposal-id abc123 --dry-run

# Promote if criteria met
python scripts/promote_systems_capability.py --proposal-id abc123 --apply
```

### 4. Orchestrator Hook

**File:** `core/orchestrator.py`

On deployment, check for algorithmic improvements:

```python
def deploy_improvement(self, proposal_id: str) -> bool:
    # ... deployment logic ...
    
    # Check if algorithmic improvement should be promoted globally
    self._check_and_promote_global_capability(proposal_id)
    
    return True
```

### 5. Configuration

**File:** `config/default.yaml`

```yaml
cache:
  policy: LRU
  ttl_seconds: 900
  soft_ttl_seconds: 300
  max_size_mb: 512
  prefetch_k: 0
  admission_policy: always
  eviction_batch_size: 16

routing:
  strategy: epsilon_greedy
  epsilon: 0.1
  ucb_c: 1.414

retriever:
  retrieval_k: 10
  rerank_top_n: 5
  enable_hybrid: true
  sparse_weight: 0.3
  dense_weight: 0.7
```

## Credit Assignment

**Specialist RL Update (per task)**
```python
# Only update winning specialist + router
specialist_mask = mask.get_specialist_params(specialist_id)
router_mask = mask.get_router_params()
update_params = specialist_mask | router_mask
# Apply gradients only to update_params
```

**Global Systems Update (on promotion)**
```python
# Update global config (code change, not weights)
adapter.promote_cache_improvement(...)
adapter.save_to_config('config/global_systems.yaml')
# All specialists benefit immediately
```

## Preventing Homogenization

**Hard Boundaries:**
1. **Separate replay buffers** per specialist (no shared experience)
2. **No cross-distillation** between specialist adapters
3. **Diversity regularizers** (pairwise KL/CKA) to monitor convergence
4. **Parameter masking** enforced at optimizer step

**Monitoring:**
```python
# Track specialization index
specialization_index = compute_pairwise_kl(specialists)
route_confusion = compute_route_confusion_matrix(router)
# Alert if similarity rises above threshold
```

## Using PageQA for Specialist Training

### RAG-Only Specialization (Safest)

Build per-specialist PageQA pipelines:

```python
from integrations.paperqa_rag import get_rag

# Per-specialist namespace
specialist_rag = await get_rag()
specialist_rag.config.doc_directories = [f"data/kb/specialist_{specialist_id}/"]

# Query specialist's corpus
result = await specialist_rag.query(
    "How can I improve caching for this specialist domain?"
)

# Train only specialist's adapter on retrieved Q-A pairs
# NO updates to global or other specialists
```

### Adapter SFT/RLHF per Specialist

```python
# Generate Q-A pairs from specialist corpus using PageQA
qa_pairs = generate_specialist_qa_pairs(specialist_id, num_pairs=1000)

# Fine-tune ONLY specialist adapter
train_specialist_adapter(
    specialist_id=specialist_id,
    qa_pairs=qa_pairs,
    freeze_global=True,  # Don't update global params
    freeze_other_specialists=True  # Don't update other specialists
)
```

### Promoting Algorithmic Improvements

For global systems improvements discovered through PageQA:

```python
# Generate neutral Q-A tasks that stress caching mechanics
neutral_qa = generate_neutral_cache_qa(
    topics=['repeated lookups', 'TTL expiry', 'eviction pressure']
)

# Train/evaluate global systems adapter on neutral tasks ONLY
benchmark_results = evaluate_on_neutral_tasks(
    current_policy=current_cache_policy,
    proposed_policy=proposed_cache_policy,
    qa_tasks=neutral_qa
)

# Promote if improvement verified on neutral tasks
if benchmark_results.meets_criteria():
    promote_to_global_config(proposed_cache_policy)
```

## Practical Knobs

### Parameter Isolation
```python
# Maintain masks
M_global = {'cache.policy', 'routing.strategy', 'retriever.k'}
M_spec_i = {'adapter.lora_A.0', 'adapter.lora_B.0', ...}

# RL updates from real tasks go to M_spec_i
# Algorithmic wins are re-trained onto M_global using neutral tasks
```

### Global as Code
Prefer shipping improvements as config/logic:

```yaml
cache:
  policy: "ARC"  # Promoted from LRU
  ttl_seconds: 900
  soft_ttl_seconds: 300
  prefetch_k: 2  # Promoted from 0
  admission: "tinyLFU"  # Promoted from always
```

This lets all AIs benefit instantly with zero knowledge leakage.

### Governance

Keep a promotion manifest:

```json
{
  "timestamp": "2025-12-03T...",
  "type": "cache_policy",
  "proposal_id": "abc123",
  "proposer_specialist_id": "specialist_2",
  "old_fingerprint": "a1b2c3d4",
  "new_fingerprint": "e5f6g7h8",
  "benchmark_results": {
    "baseline_hit_rate": 0.723,
    "new_hit_rate": 0.781,
    "baseline_latency_ms": 12.4,
    "new_latency_ms": 11.8
  },
  "promoted": true
}
```

## Example Workflow

**Scenario:** Specialist 2 (Deception Detection) proposes a caching improvement

```
1. Specialist 2 generates proposal:
   Title: "Improve cache hit rate with ARC policy"
   Code: cache_policy = CachePolicy(policy='ARC', ttl_seconds=900)

2. Orchestrator receives proposal
   ├─> Classifies as "algorithmic" (keywords: cache, ARC)
   └─> NOT domain-specific (no deception knowledge in code)

3. Proposal passes sandbox tests & peer review
   └─> Deployed successfully

4. Orchestrator hook on deployment:
   ├─> Detects algorithmic improvement
   └─> Queues for promotion testing

5. Promotion script runs neutral benchmarks:
   ├─> Baseline (LRU): 72.3% hit rate, 12.4ms avg latency
   ├─> Proposed (ARC): 78.1% hit rate, 11.8ms avg latency
   └─> Improvement: +8.0% hit rate, -4.8% latency

6. Promotion criteria met:
   ├─> Hit rate improvement > 5% ✓
   └─> Latency degradation < 10% ✓

7. Promote to global config:
   ├─> config/default.yaml: cache.policy = ARC
   └─> All specialists (1-5) benefit immediately

8. Credit assignment:
   ├─> Specialist 2 adapter: Updated with RL reward
   ├─> Router: Updated (selected specialist 2)
   └─> Global cache policy: Updated (all specialists benefit)
   └─> Other specialists (1, 3, 4, 5): NOT updated (domain isolation maintained)
```

## Benefits

1. **Share the algorithm, not the knowledge**
   - Caching improvements benefit everyone
   - Deception detection knowledge stays isolated

2. **No homogenization**
   - Specialists maintain distinct capabilities
   - Router learns when to route to each specialist

3. **Verifiable improvements**
   - Neutral benchmarks prevent gaming
   - Promotion based on measured metrics, not claims

4. **Composable specialization**
   - Add new specialists without retraining existing ones
   - Global improvements propagate automatically

## Files Created

1. `core/systems_adapter.py` - Global systems adapter with parameter masking
2. `scripts/neutral_cache_bench.py` - Domain-neutral caching benchmarks
3. `scripts/promote_systems_capability.py` - Test and promote algorithmic improvements
4. `config/default.yaml` - Added cache/routing/retriever blocks
5. `core/orchestrator.py` - Added `_check_and_promote_global_capability` hook

## Next Steps

To enable RL training with specialist isolation:

1. **Per-specialist adapters:**
   ```python
   from transformers import AutoModelForCausalLM
   from peft import get_peft_model, LoraConfig
   
   base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b")
   
   # Create per-specialist LoRA adapters
   for specialist_id in range(num_specialists):
       lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
       specialist_model = get_peft_model(base_model, lora_config)
       save_specialist_adapter(specialist_id, specialist_model)
   ```

2. **Diversity loss:**
   ```python
   def diversity_loss(specialists, probe_inputs):
       kl_matrix = compute_pairwise_kl(specialists, probe_inputs)
       # Penalize high similarity
       return -torch.mean(kl_matrix)
   ```

3. **Route-only credit:**
   ```python
   def update_step(winning_specialist_id, reward):
       # Update winning specialist
       update_params(specialist_adapters[winning_specialist_id], reward)
       # Update router
       update_router(winning_specialist_id, reward)
       # DO NOT update other specialists or global (unless promoted via neutral benchmark)
   ```

## References

- Global systems adapter: `core/systems_adapter.py`
- Neutral benchmarks: `scripts/neutral_cache_bench.py`
- Promotion script: `scripts/promote_systems_capability.py`
- Orchestrator hook: `core/orchestrator.py:_check_and_promote_global_capability`
- Config: `config/default.yaml` (cache/routing/retriever blocks)

