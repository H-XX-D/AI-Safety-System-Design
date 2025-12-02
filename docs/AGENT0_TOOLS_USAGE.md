# Agent0 Tools Usage Guide
=======================

This document explains how to use the 4 Agent0 tools integrated into the AI Safety System.

## Overview

The 4 tools work together to create a robust self-improvement pipeline:

1. **Self-Consistency Evaluation** - Validates proposal reliability
2. **Curriculum Reward Computation** - Scores task quality for curriculum agents
3. **Training Data Filtering** - Filters low-quality proposals
4. **Proposal Clustering** - Groups similar proposals to avoid redundancy

---

## 1. Self-Consistency Evaluation

### Purpose
Validates proposals by generating multiple responses and checking if they agree. High consistency = reliable proposal.

### When to Use
- **Before peer review**: Filter out unreliable proposals early
- **After proposal generation**: Validate before submitting to orchestrator
- **During RL training**: Only train on consistent proposals

### How It Works

```python
from integrations import SelfConsistencyEvaluator, evaluate_proposal_consistency

# Method 1: Direct evaluation
proposal = {
    'title': 'Improve deception detector',
    'changes': {'description': 'Add semantic analysis method'}
}

result = evaluate_proposal_consistency(proposal)
# Returns:
# {
#     'consistency_score': 0.85,  # 85% agreement
#     'passed': True,              # Above threshold (0.6)
#     'responses': [...],          # Generated responses
#     'majority_answer': '...'    # Most common answer
# }

if result['passed']:
    # Proposal is reliable, proceed
    orchestrator.handle_improvement_proposal(proposal)
else:
    # Proposal is inconsistent, reject or regenerate
    logger.warning(f"Low consistency: {result['consistency_score']}")
```

### Integration Points

**In Research System (`research_system.py`):**
```python
async def propose_improvement(self, ...):
    proposal = await self._generate_proposal(...)
    
    # Validate consistency before submitting
    consistency = evaluate_proposal_consistency(proposal)
    if not consistency['passed']:
        # Regenerate or reject
        return None
    
    # Add consistency score to proposal
    proposal['consistency_score'] = consistency['consistency_score']
    
    # Submit to orchestrator
    self._send_proposal_to_orchestrator(proposal)
```

**In Orchestrator (`orchestrator.py`):**
```python
def handle_improvement_proposal(self, proposal):
    # Check consistency before processing
    consistency = proposal.get('consistency_score', 0.0)
    if consistency < 0.6:
        self.active_proposals[proposal_id]['status'] = 'rejected_inconsistent'
        return
    
    # Continue with normal processing...
```

---

## 2. Curriculum Reward Computation

### Purpose
Scores curriculum tasks (hypotheses) based on:
- Difficulty (optimal: medium-hard)
- Executor success rate
- Task diversity (penalizes redundancy)

### When to Use
- **During self-play**: Reward curriculum agents for good tasks
- **Hypothesis ranking**: Score which hypotheses are best
- **RL training**: Train curriculum agents to generate better tasks

### How It Works

```python
from integrations import CurriculumRewardComputer, compute_curriculum_reward

# Method 1: Simple reward computation
task = "Generate hypothesis to improve deception detector accuracy"
reward = compute_curriculum_reward(
    task=task,
    executor_solved=True,      # Executor successfully evaluated it
    executor_steps=5           # Took 5 steps
)
# Returns: 2.5 (good reward for solvable, efficient task)

# Method 2: Full reward computer (tracks history)
computer = CurriculumRewardComputer()

# Generate a task
task1 = "Improve alignment filter"
reward1 = computer.compute_reward(
    task=task1,
    executor_solved=True,
    executor_steps=3,
    executor_performance=0.8,
    difficulty=0.6  # Medium-hard (optimal)
)
computer.record_task(task1, reward1)  # Track for redundancy checking

# Generate similar task (will be penalized)
task2 = "Improve alignment filter"  # Too similar!
reward2 = computer.compute_reward(
    task=task2,
    executor_solved=True,
    executor_steps=3,
    executor_performance=0.8,
    difficulty=0.6
)
# reward2 < reward1 (penalty for redundancy)
```

### Integration Points

**In Self-Play System (`agent0_self_play.py`):**
```python
async def curriculum_agent_generate_hypothesis(self, agent_id, task_id):
    hypothesis = await self._generate_hypothesis(...)
    
    # Score the hypothesis quality
    computer = CurriculumRewardComputer()
    reward = computer.compute_reward(
        task=hypothesis['name'],
        executor_solved=False,  # Not evaluated yet
        executor_steps=0,
        difficulty=task.difficulty
    )
    
    hypothesis['curriculum_reward'] = reward
    return hypothesis
```

**After Executor Evaluation:**
```python
async def executor_agent_evaluate_hypothesis(self, agent_id, task_id):
    evaluation = await self._evaluate_hypothesis(...)
    
    # Update curriculum reward based on executor results
    computer = CurriculumRewardComputer()
    final_reward = computer.compute_reward(
        task=task.hypothesis['name'],
        executor_solved=evaluation['overall_score'] > 0.5,
        executor_steps=len(evaluation['steps_to_test']),
        executor_performance=evaluation['overall_score'],
        difficulty=task.difficulty
    )
    
    # Record for curriculum agent learning
    computer.record_task(task.hypothesis['name'], final_reward)
    
    return evaluation
```

---

## 3. Training Data Filtering

### Purpose
Filters training data to keep only high-quality proposals:
- High consistency (reliable)
- Appropriate difficulty (not too easy/hard)
- Good scores

### When to Use
- **Before RL training**: Filter out bad examples
- **After proposal collection**: Clean dataset
- **Periodic cleanup**: Remove low-quality proposals

### How It Works

```python
from integrations import TrainingDataFilter, filter_training_data

# Method 1: Simple filtering
proposals = [
    {
        'title': 'Good proposal',
        'consistency_score': 0.8,
        'score': 0.6
    },
    {
        'title': 'Bad proposal',
        'consistency_score': 0.3,  # Too low
        'score': 0.2               # Too low
    },
    {
        'title': 'Too easy',
        'consistency_score': 0.9,
        'score': 0.95              # Too high (filtered)
    }
]

high_quality = filter_training_data(proposals)
# Returns: [first proposal only]
# Filters out: low consistency, too easy

# Method 2: Custom filter
filter_tool = TrainingDataFilter(
    min_consistency=0.7,  # Stricter threshold
    min_score=0.4,
    max_score=0.7
)

kept, filtered = filter_tool.filter_proposals(proposals)
# kept: High-quality proposals
# filtered: Low-quality proposals (with reason)
```

### Integration Points

**In RL Trainer (`rl_trainer.py`):**
```python
def train_step(self):
    # Get all experiences
    all_examples = self.experience_buffer.get_all()
    
    # Convert to proposals format
    proposals = [
        {
            'title': ex.metadata.get('proposal_id', ''),
            'consistency_score': ex.metadata.get('consistency_score', 0.5),
            'score': ex.reward / 10.0  # Normalize reward to 0-1
        }
        for ex in all_examples
    ]
    
    # Filter to keep only high-quality
    high_quality = filter_training_data(proposals)
    
    # Train on filtered data only
    filtered_examples = [
        ex for ex in all_examples
        if ex.metadata.get('proposal_id') in [p['title'] for p in high_quality]
    ]
    
    # Train on filtered batch
    batch = random.sample(filtered_examples, self.config.batch_size)
    # ... training code ...
```

**After Proposal Collection:**
```python
# In orchestrator or data collection script
def collect_training_data(self):
    all_proposals = self.get_all_proposals()
    
    # Filter proposals
    high_quality = filter_training_data(all_proposals)
    
    # Save filtered dataset
    with open('training_data.json', 'w') as f:
        json.dump(high_quality, f)
    
    logger.info(f"Filtered {len(all_proposals)} -> {len(high_quality)} proposals")
```

---

## 4. Proposal Clustering

### Purpose
Groups similar proposals together to:
- Avoid duplicate work
- Select best representative from each cluster
- Identify common improvement patterns

### When to Use
- **Before processing**: Group similar proposals
- **After collection**: Deduplicate proposals
- **Analysis**: Find common themes

### How It Works

```python
from integrations import ProposalClustering, cluster_similar_proposals

# Method 1: Simple clustering
proposals = [
    {'title': 'Improve accuracy', 'changes': {'description': 'Add method A'}, 'score': 0.7},
    {'title': 'Improve accuracy', 'changes': {'description': 'Add method A'}, 'score': 0.8},
    {'title': 'Fix bug', 'changes': {'description': 'Remove old code'}, 'score': 0.6},
]

clusters = cluster_similar_proposals(proposals)
# Returns:
# {
#     0: [proposal1, proposal2],  # Similar proposals grouped
#     1: [proposal3]              # Different proposal
# }

# Method 2: Get representatives
cluster_tool = ProposalClustering(similarity_threshold=0.7)
clusters = cluster_tool.cluster_proposals(proposals)

# Get best proposal from each cluster
representatives = cluster_tool.get_representative_proposals(clusters)
# Returns: [best_proposal_from_cluster_0, proposal3]
# (highest scoring proposal from each cluster)
```

### Integration Points

**Before Hypothesis Generation:**
```python
# In orchestrator or research system
def generate_hypotheses(self, target_component):
    # Get existing proposals for this component
    existing = self.get_proposals_for_component(target_component)
    
    # Cluster to find gaps
    clusters = cluster_similar_proposals(existing)
    
    # Generate hypotheses for underrepresented areas
    covered_topics = [c[0]['title'] for c in clusters.values()]
    new_hypotheses = self._generate_for_gaps(covered_topics)
    
    return new_hypotheses
```

**After Proposal Collection:**
```python
# Deduplicate proposals before processing
def deduplicate_proposals(self, proposals):
    clusters = cluster_similar_proposals(proposals)
    
    # Keep only best from each cluster
    cluster_tool = ProposalClustering()
    representatives = cluster_tool.get_representative_proposals(clusters)
    
    return representatives
```

---

## Complete Workflow Example

Here's how all 4 tools work together in a complete self-improvement cycle:

```python
from integrations import (
    evaluate_proposal_consistency,
    compute_curriculum_reward,
    filter_training_data,
    cluster_similar_proposals,
    ProposalClustering
)

# Step 1: Generate hypotheses (self-play)
hypotheses = await self_play.generate_hypotheses(...)

# Step 2: Evaluate consistency
for hypothesis in hypotheses:
    consistency = evaluate_proposal_consistency(hypothesis)
    hypothesis['consistency_score'] = consistency['consistency_score']
    
    if not consistency['passed']:
        continue  # Skip inconsistent
    
    # Step 3: Score curriculum quality
    reward = compute_curriculum_reward(
        task=hypothesis['name'],
        executor_solved=False,
        executor_steps=0
    )
    hypothesis['curriculum_reward'] = reward

# Step 4: Cluster similar hypotheses
clusters = cluster_similar_proposals(hypotheses)

# Step 5: Get best representative from each cluster
cluster_tool = ProposalClustering()
representatives = cluster_tool.get_representative_proposals(clusters)

# Step 6: Filter for training
training_data = filter_training_data(representatives)

# Step 7: Train on filtered data
for proposal in training_data:
    # Execute in sandbox
    result = await sandbox.execute(proposal)
    
    # Record RL experience
    trainer.record_experience(proposal, result)
    
    # Update curriculum reward based on results
    final_reward = compute_curriculum_reward(
        task=proposal['name'],
        executor_solved=result['success'],
        executor_steps=result['steps']
    )
```

---

## Configuration

### Self-Consistency Evaluator
```python
evaluator = SelfConsistencyEvaluator(
    num_samples=5,              # Generate 5 responses
    consistency_threshold=0.6    # Need 60% agreement
)
```

### Curriculum Reward Computer
```python
computer = CurriculumRewardComputer()
# Automatically tracks task history for redundancy
```

### Training Data Filter
```python
filter_tool = TrainingDataFilter(
    min_consistency=0.6,    # Minimum consistency score
    min_score=0.3,          # Minimum overall score
    max_score=0.8           # Maximum (filter too-easy)
)
```

### Proposal Clustering
```python
cluster_tool = ProposalClustering(
    similarity_threshold=0.7  # 70% similarity to cluster
)
```

---

## Benefits

1. **Self-Consistency**: Reduces hallucinations, improves reliability
2. **Curriculum Rewards**: Guides curriculum agents to generate better tasks
3. **Data Filtering**: Improves training data quality, faster convergence
4. **Clustering**: Prevents duplicate work, identifies patterns

Together, these tools create a robust, self-improving system that continuously gets better at generating and evaluating improvement proposals.





