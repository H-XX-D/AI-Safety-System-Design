# Sandbox Model Integration: SmolLM-135M

## Overview

The **Sandbox Environment** (powered by SandboxFusion) includes a tiny, local language model (**SmolLM-135M**) that the Research Agent can experiment on.

## Purpose

This allows the agent to:
1.  **Test Hypothesis**: Verify if a proposed optimization (e.g., "sparse attention") actually works on a real transformer model.
2.  **Run Benchmarks**: Measure speed/memory improvements locally before deployment.
3.  **Fine-tune**: Test fine-tuning scripts or RL algorithms on a small scale.
4.  **Verify Logic**: Ensure code interacts correctly with model weights and tokenizers.

## Model Details

-   **Name**: `HuggingFaceTB/SmolLM-135M`
-   **Parameters**: ~135 Million
-   **Size**: ~270 MB (FP16) / ~500 MB (Full)
-   **Architecture**: Llama-style (GQA, RoPE)
-   **Context Window**: 2048 tokens (default)

## Integration

### 1. Dockerfile Configuration

The `Dockerfile` for the sandbox must include the model download step to ensure it's available offline (no internet access in sandbox for model downloads).

```dockerfile
# In SandboxFusion/scripts/Dockerfile.server

# ... existing setup ...

# Pre-download SmolLM-135M (Tiny model for fast testing)
RUN pip install huggingface_hub
RUN huggingface-cli download HuggingFaceTB/SmolLM-135M \
    --local-dir /root/sandbox/models/SmolLM-135M \
    --local-dir-use-symlinks False
    
# Set environment variable for easy access
ENV TEST_MODEL_PATH="/root/sandbox/models/SmolLM-135M"
```

### 2. Agent Usage

The Research Agent can use this model in its proposal code:

```python
import os
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load the test model
model_path = os.environ.get("TEST_MODEL_PATH", "/root/sandbox/models/SmolLM-135M")
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)

# Run experiment
# ... implementation of proposed optimization ...
```

### 3. Configuration

Update `config/default.yaml` to register this capability:

```yaml
sandbox:
  # ... other settings ...
  test_model:
    enabled: true
    name: "SmolLM-135M"
    path: "/root/sandbox/models/SmolLM-135M"
```

## Benefits

-   **Ultra-Fast Iteration**: Loads in seconds, minimal memory footprint (~300MB).
-   **Representative**: Llama architecture ensures code compatibility with larger models.
-   **Safe**: Runs entirely within the isolated sandbox.
