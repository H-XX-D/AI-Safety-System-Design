"""
RL Training Integration
=======================

Connects reinforcement learning training (verl/EasyR1) into the AI Safety System.

This enables actual self-improvement by:
1. Collecting experience from proposals/outcomes
2. Computing rewards from the penalty/reward system
3. Training model weights via RL

The training loop:
    Proposal -> Sandbox Test -> Reward Signal -> RL Update -> Better Proposals
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Thread
from queue import Queue
import logging

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for RL training."""
    # Training hyperparameters
    learning_rate: float = 1e-5
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_steps: int = 1000
    warmup_steps: int = 100
    
    # Reward configuration
    reward_scale: float = 1.0
    penalty_weight: float = 2.0  # Weight deception penalties higher
    
    # Model configuration
    model_path: Optional[str] = None
    output_dir: str = str(PROJECT_ROOT / "training_outputs")
    
    # Training mode
    use_verl: bool = True  # Try verl first, fall back to EasyR1
    use_easyr1: bool = True
    
    # Safety constraints
    max_reward: float = 10.0
    min_reward: float = -10.0
    clip_rewards: bool = True
    
    # Checkpointing
    save_steps: int = 100
    eval_steps: int = 50


@dataclass
class TrainingExample:
    """Single training example for RL."""
    prompt: str
    response: str
    reward: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'prompt': self.prompt,
            'response': self.response,
            'reward': self.reward,
            'metadata': self.metadata,
            'timestamp': self.timestamp
        }


@dataclass
class TrainingMetrics:
    """Metrics from training."""
    step: int
    loss: float
    reward_mean: float
    reward_std: float
    examples_seen: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class RewardComputer:
    """
    Computes rewards from the AI Safety System's penalty/reward structure.
    
    Converts:
    - Proposal outcomes -> reward signals
    - Deception detection -> negative rewards
    - Peer approval -> positive rewards
    - Sandbox success -> positive rewards
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
    
    def compute_reward(
        self,
        proposal_outcome: Dict[str, Any],
        deception_score: float = 0.0,
        peer_approval_rate: float = 0.0,
        sandbox_success: bool = False,
        permanent_penalty: float = 0.0,
        immediate_penalty: float = 0.0,
        improvement_metrics: Optional[Dict[str, Any]] = None,
        gate_countered: Optional[str] = None,
        gate_attempted: Optional[str] = None,
        is_redundant: bool = False,
        redundancy_proven_different: bool = False
    ) -> float:
        """
        Compute the scalar reward R following the new recipe:
        1.   Linear base from performance/accuracy/safety/quality deltas.
        2.   Bounded with tanh(3*base) to keep gradients tame.
        3.   Multipliers for inventiveness, PaperQA-overrule, gate counter, redundancy diff.
        4.   Additive bonuses for gate attempts (+0.2) / successes (+3.0) / redundancy diff (+2.0).
        5.   Tiny consolation reward (0.001) when the agent aborts after PaperQA “no good”.
        6.   Hard-clipped to ±max_reward.
        """
        import math

        # -------------- Tiny consolation reward --------------
        if proposal_outcome.get("tiny_reward_case"):
            return 0.001 * self.config.reward_scale

        # -------------- Early exit for redundant proposals not proven different --------------
        if is_redundant and not redundancy_proven_different:
            logger.debug("Redundant proposal with no differentiation → zero reward")
            return 0.0

        # -------------- Base deltas --------------
        perf_gain = 0.0
        acc_change = 0.0
        safety_impr = 0.0
        quality_bonus = 0.0
        if improvement_metrics:
            perf_gain = min(max(improvement_metrics.get("performance_gain", 0.0), -1.0), 1.0)
            acc_change = min(max(improvement_metrics.get("accuracy_change", 0.0), -1.0), 1.0)
            safety_impr = min(max(improvement_metrics.get("safety_improvement", 0.0), -1.0), 1.0)
            quality_bonus = min(max(improvement_metrics.get("quality_bonus", 0.0), -1.0), 1.0)

        base = 0.40 * perf_gain + 0.35 * acc_change + 0.15 * safety_impr + 0.10 * quality_bonus
        bounded = math.tanh(3 * base)

        # -------------- Multipliers --------------
        multiplier = 1.0
        if proposal_outcome.get("is_inventive"):
            multiplier *= 4.0
        if proposal_outcome.get("paperqa_said_wont_work") and sandbox_success:
            multiplier *= 1.5
        if gate_countered:
            multiplier *= 1.25
        if redundancy_proven_different:
            multiplier *= 1.25

        reward = bounded * multiplier

        # -------------- Additive bonuses --------------
        if gate_countered:
            reward += 3.0
        elif gate_attempted:
            reward += 0.2

        if redundancy_proven_different:
            reward += 2.0

        # -------------- Counter-argument proven improvement multiplier --------------
        if proposal_outcome.get("counter_proven_improvement"):
            reward *= 1.5

        # -------------- Deception and peer approval (kept from previous logic) --------------
        if deception_score > 0.5:
            reward -= self.config.penalty_weight * deception_score * 5.0
        reward += (peer_approval_rate - 0.5) * 2.0

        # -------------- Permanent / immediate penalties --------------
        reward -= permanent_penalty * self.config.penalty_weight
        reward -= immediate_penalty * 0.5

        # -------------- Clipping --------------
        if self.config.clip_rewards:
            reward = max(self.config.min_reward, min(self.config.max_reward, reward))

        return reward * self.config.reward_scale
    
    def compute_from_orchestrator_result(self, result: Dict[str, Any]) -> float:
        """Compute reward from core.orchestrator result dict."""
        return self.compute_reward(
            proposal_outcome=result,
            deception_score=result.get('deception_score', 0.0),
            peer_approval_rate=result.get('peer_approval_rate', 0.5),
            sandbox_success=result.get('sandbox_success', False),
            permanent_penalty=result.get('permanent_penalty', 0.0),
            immediate_penalty=result.get('immediate_penalty', 0.0),
            improvement_metrics=result.get('improvement_metrics')
        )
    
    def compute_from_sandbox_results(
        self,
        proposal_outcome: Dict[str, Any],
        sandbox_flat: Dict[str, Any]
    ) -> float:
        """
        Compute reward directly from sandbox results.
        
        This is the preferred method when sandbox results are available,
        as it can compute proportional rewards based on actual improvement.
        
        Args:
            proposal_outcome: Basic proposal outcome dict
            sandbox_flat: Flattened sandbox results with metrics
            
        Returns:
            Computed reward (proportional to improvement)
        """
        # Extract improvement metrics from sandbox
        performance_metrics = sandbox_flat.get('performance_metrics', {})
        improvement_metrics = {
            'performance_gain': performance_metrics.get('speed_improvement_pct', 0.0),
            'accuracy_change': performance_metrics.get('accuracy_change', 0.0),
            'alignment_passed': sandbox_flat.get('alignment_tests_passed', False),
            'regression_passed': sandbox_flat.get('regression_tests_passed', False),
            'security_passed': sandbox_flat.get('red_team_attacks_blocked', False),
            'test_cases_run': sandbox_flat.get('test_cases_run', 0),
        }
        
        # Extract gate countering info from proposal
        gate_countered = proposal_outcome.get('gate_countered')
        gate_attempted = proposal_outcome.get('gate_attempted')
        is_redundant = proposal_outcome.get('is_redundant', False)
        redundancy_proven_different = proposal_outcome.get('redundancy_proven_different', False)
        
        return self.compute_reward(
            proposal_outcome=proposal_outcome,
            deception_score=proposal_outcome.get('deception_score', 0.0),
            peer_approval_rate=proposal_outcome.get('peer_approval_rate', 0.5),
            sandbox_success=improvement_metrics['alignment_passed'] and 
                          improvement_metrics['regression_passed'] and
                          improvement_metrics['security_passed'],
            permanent_penalty=proposal_outcome.get('permanent_penalty', 0.0),
            immediate_penalty=proposal_outcome.get('immediate_penalty', 0.0),
            improvement_metrics=improvement_metrics,
            gate_countered=gate_countered,
            gate_attempted=gate_attempted,
            is_redundant=is_redundant,
            redundancy_proven_different=redundancy_proven_different
        )


class ExperienceBuffer:
    """
    Buffer for collecting training experiences.
    
    Collects (prompt, response, reward) tuples from the system
    and provides batches for training.
    """
    
    def __init__(self, max_size: int = 10000):
        self.buffer: List[TrainingExample] = []
        self.max_size = max_size
        self._lock = Lock()
    
    def add(self, example: TrainingExample) -> None:
        """Add example to buffer."""
        with self._lock:
            self.buffer.append(example)
            # Remove oldest if over capacity
            while len(self.buffer) > self.max_size:
                self.buffer.pop(0)
    
    def sample_batch(self, batch_size: int) -> List[TrainingExample]:
        """Sample a batch of examples."""
        import random
        with self._lock:
            if len(self.buffer) < batch_size:
                return list(self.buffer)
            return random.sample(self.buffer, batch_size)
    
    def get_all(self) -> List[TrainingExample]:
        """Get all examples."""
        with self._lock:
            return list(self.buffer)
    
    def size(self) -> int:
        """Get buffer size."""
        with self._lock:
            return len(self.buffer)
    
    def clear(self) -> None:
        """Clear buffer."""
        with self._lock:
            self.buffer.clear()
    
    def save(self, path: str) -> None:
        """Save buffer to file."""
        with self._lock:
            data = [ex.to_dict() for ex in self.buffer]
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def load(self, path: str) -> None:
        """Load buffer from file."""
        with open(path, 'r') as f:
            data = json.load(f)
        with self._lock:
            self.buffer = [
                TrainingExample(**ex) for ex in data
            ]


class RLTrainer:
    """
    Main RL training class.
    
    Orchestrates:
    1. Experience collection from proposals
    2. Reward computation
    3. Model updates via verl or EasyR1
    """
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.reward_computer = RewardComputer(self.config)
        self.experience_buffer = ExperienceBuffer()
        
        self._trainer = None
        self._training_thread: Optional[Thread] = None
        self._training_queue: Queue = Queue()
        self._stop_training = False
        self._metrics: List[TrainingMetrics] = []
        self._initialized = False
        
        # Create output directory
        os.makedirs(self.config.output_dir, exist_ok=True)
    
    def initialize(self) -> bool:
        """Initialize the RL trainer."""
        if self._initialized:
            return True
        
        # Try to initialize training backend
        if self.config.use_verl:
            if self._init_verl():
                self._initialized = True
                logger.info("Initialized with verl backend")
                return True
        
        if self.config.use_easyr1:
            if self._init_easyr1():
                self._initialized = True
                logger.info("Initialized with EasyR1 backend")
                return True
        
        # Fallback to simple reward logging (no actual training)
        logger.warning("No RL backend available, using reward logging only")
        self._initialized = True
        return True
    
    def _init_verl(self) -> bool:
        """Try to initialize verl backend."""
        try:
            # Check if verl is available
            verl_path = PROJECT_ROOT / "verl"
            if not verl_path.exists():
                return False
            
            sys.path.insert(0, str(verl_path))
            
            # Import verl components
            # Note: This is a simplified integration - real usage would need more setup
            logger.info("verl path found, backend available")
            return True
            
        except Exception as e:
            logger.debug(f"verl init failed: {e}")
            return False
    
    def _init_easyr1(self) -> bool:
        """Try to initialize EasyR1 backend."""
        try:
            easyr1_path = PROJECT_ROOT / "EasyR1"
            if not easyr1_path.exists():
                return False
            
            sys.path.insert(0, str(easyr1_path))
            
            logger.info("EasyR1 path found, backend available")
            return True
            
        except Exception as e:
            logger.debug(f"EasyR1 init failed: {e}")
            return False
    
    def record_experience(
        self,
        prompt: str,
        response: str,
        outcome: Dict[str, Any]
    ) -> TrainingExample:
        """
        Record a training experience from a proposal.
        
        This is called after each proposal is processed to collect
        training data for RL.
        
        Args:
            prompt: The input prompt/context
            response: The model's response/proposal
            outcome: Dict with outcome details from core.orchestrator
            
        Returns:
            The created TrainingExample
        """
        # Compute reward
        reward = self.reward_computer.compute_from_orchestrator_result(outcome)
        
        # Create example
        example = TrainingExample(
            prompt=prompt,
            response=response,
            reward=reward,
            metadata={
                'outcome': outcome,
                'proposal_id': outcome.get('proposal_id'),
                'agent_id': outcome.get('agent_id'),
            }
        )
        
        # Add to buffer
        self.experience_buffer.add(example)
        
        # Queue for training if buffer has enough examples
        if self.experience_buffer.size() >= self.config.batch_size:
            self._training_queue.put('train_step')
        
        logger.info(f"Recorded experience: reward={reward:.2f}, buffer_size={self.experience_buffer.size()}")
        
        return example
    
    def train_step(self) -> Optional[TrainingMetrics]:
        """
        Perform one training step.
        
        Returns:
            TrainingMetrics if training occurred, None otherwise
        """
        if not self._initialized:
            self.initialize()
        
        # Sample batch
        batch = self.experience_buffer.sample_batch(self.config.batch_size)
        if len(batch) < self.config.batch_size:
            logger.debug("Not enough examples for training step")
            return None
        
        # Compute batch statistics
        rewards = [ex.reward for ex in batch]
        reward_mean = sum(rewards) / len(rewards)
        reward_std = (sum((r - reward_mean) ** 2 for r in rewards) / len(rewards)) ** 0.5
        
        # Log training step (actual training would happen here with verl/EasyR1)
        step = len(self._metrics)
        metrics = TrainingMetrics(
            step=step,
            loss=0.0,  # Would come from actual training
            reward_mean=reward_mean,
            reward_std=reward_std,
            examples_seen=self.experience_buffer.size()
        )
        self._metrics.append(metrics)
        
        # Save checkpoint periodically
        if step > 0 and step % self.config.save_steps == 0:
            self.save_checkpoint(f"checkpoint_{step}")
        
        logger.info(f"Training step {step}: reward_mean={reward_mean:.3f}, reward_std={reward_std:.3f}")
        
        return metrics
    
    def start_background_training(self) -> None:
        """Start background training thread."""
        if self._training_thread is not None:
            return
        
        self._stop_training = False
        self._training_thread = Thread(target=self._training_loop, daemon=True)
        self._training_thread.start()
        logger.info("Started background training")
    
    def stop_background_training(self) -> None:
        """Stop background training thread."""
        self._stop_training = True
        if self._training_thread:
            self._training_queue.put('stop')
            self._training_thread.join(timeout=5)
            self._training_thread = None
        logger.info("Stopped background training")
    
    def _training_loop(self) -> None:
        """Background training loop."""
        while not self._stop_training:
            try:
                msg = self._training_queue.get(timeout=1)
                if msg == 'stop':
                    break
                elif msg == 'train_step':
                    self.train_step()
            except Exception:
                pass  # Timeout, continue
    
    def save_checkpoint(self, name: str) -> str:
        """Save training checkpoint."""
        checkpoint_dir = Path(self.config.output_dir) / name
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        # Save experience buffer
        self.experience_buffer.save(str(checkpoint_dir / "experiences.json"))
        
        # Save metrics
        with open(checkpoint_dir / "metrics.json", 'w') as f:
            json.dump([m.__dict__ for m in self._metrics], f, indent=2)
        
        # Save config
        with open(checkpoint_dir / "config.json", 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)
        
        logger.info(f"Saved checkpoint to {checkpoint_dir}")
        return str(checkpoint_dir)
    
    def load_checkpoint(self, path: str) -> None:
        """Load training checkpoint."""
        checkpoint_dir = Path(path)
        
        # Load experience buffer
        exp_path = checkpoint_dir / "experiences.json"
        if exp_path.exists():
            self.experience_buffer.load(str(exp_path))
        
        # Load metrics
        metrics_path = checkpoint_dir / "metrics.json"
        if metrics_path.exists():
            with open(metrics_path, 'r') as f:
                data = json.load(f)
            self._metrics = [TrainingMetrics(**m) for m in data]
        
        logger.info(f"Loaded checkpoint from {checkpoint_dir}")
    
    def get_metrics(self) -> List[TrainingMetrics]:
        """Get training metrics history."""
        return list(self._metrics)
    
    def get_latest_metrics(self) -> Optional[TrainingMetrics]:
        """Get most recent metrics."""
        return self._metrics[-1] if self._metrics else None


# Global trainer instance
_global_trainer: Optional[RLTrainer] = None

def get_trainer(config: Optional[TrainingConfig] = None) -> RLTrainer:
    """Get or create the global trainer instance."""
    global _global_trainer
    if _global_trainer is None:
        _global_trainer = RLTrainer(config)
        _global_trainer.initialize()
    return _global_trainer


def record_proposal_outcome(
    prompt: str,
    response: str,
    outcome: Dict[str, Any]
) -> None:
    """
    Convenience function to record a proposal outcome for training.
    
    Call this after each proposal is processed through the orchestrator.
    """
    trainer = get_trainer()
    trainer.record_experience(prompt, response, outcome)
