"""
Global Systems Adapter
=======================

Manages global system-level capabilities (e.g., caching policy, routing scheduler, retrieval config)
that are shared across all specialist agents while keeping specialist domain knowledge isolated.

Architecture:
    - Specialist adapters: Per-agent domain-specific knowledge (LoRA/IA³/adapters). Isolated.
    - Global systems adapter: Shared infrastructure improvements (cache policy, scheduler, retriever).
    
Credit assignment:
    - Only update the winning specialist's adapter + router on RL step.
    - Global systems adapter updated separately through neutral benchmarks (see scripts/promote_systems_capability.py).
    
Promotion pipeline:
    1) Specialist proposes caching/routing/retrieval improvement.
    2) Orchestrator classifies as "algorithmic" (not domain-specific).
    3) Run neutral benchmark suite (no domain data) to verify improvement.
    4) If verified, promote to global config or global adapter weights.
    5) All specialists benefit without sharing domain knowledge.
"""

from __future__ import annotations
import json
import hashlib
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from utilities.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ParameterMask:
    """
    Defines which parameters can be updated by different training lanes.
    
    - global_params: Parameters shared across all specialists (e.g., cache policy, retriever config).
    - specialist_params: Per-specialist parameters (indexed by specialist_id).
    - router_params: Router/bandit selection parameters.
    """
    global_params: Set[str] = field(default_factory=set)
    specialist_params: Dict[str, Set[str]] = field(default_factory=dict)
    router_params: Set[str] = field(default_factory=set)
    
    def is_global(self, param_name: str) -> bool:
        return param_name in self.global_params
    
    def is_specialist(self, param_name: str, specialist_id: str) -> bool:
        return param_name in self.specialist_params.get(specialist_id, set())
    
    def is_router(self, param_name: str) -> bool:
        return param_name in self.router_params
    
    def get_specialist_params(self, specialist_id: str) -> Set[str]:
        return self.specialist_params.get(specialist_id, set())
    
    def add_global(self, param_name: str) -> None:
        self.global_params.add(param_name)
    
    def add_specialist(self, specialist_id: str, param_name: str) -> None:
        if specialist_id not in self.specialist_params:
            self.specialist_params[specialist_id] = set()
        self.specialist_params[specialist_id].add(param_name)
    
    def add_router(self, param_name: str) -> None:
        self.router_params.add(param_name)


@dataclass
class CachePolicy:
    """
    Caching policy configuration that can be promoted from specialist to global.
    """
    policy: str = "LRU"  # LRU, LFU, ARC, tinyLFU
    ttl_seconds: int = 900
    soft_ttl_seconds: int = 300
    max_size_mb: int = 512
    prefetch_k: int = 0
    admission_policy: str = "always"  # always, tinyLFU, W-TinyLFU
    eviction_batch_size: int = 16
    enable_compression: bool = True
    compression_threshold_kb: int = 64
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'policy': self.policy,
            'ttl_seconds': self.ttl_seconds,
            'soft_ttl_seconds': self.soft_ttl_seconds,
            'max_size_mb': self.max_size_mb,
            'prefetch_k': self.prefetch_k,
            'admission_policy': self.admission_policy,
            'eviction_batch_size': self.eviction_batch_size,
            'enable_compression': self.enable_compression,
            'compression_threshold_kb': self.compression_threshold_kb,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CachePolicy':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
    
    def fingerprint(self) -> str:
        """Deterministic fingerprint for policy identity."""
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass
class RoutingPolicy:
    """
    Routing/scheduler policy configuration.
    """
    strategy: str = "epsilon_greedy"  # epsilon_greedy, UCB1, Thompson
    epsilon: float = 0.1
    ucb_c: float = 1.414
    thompson_alpha: float = 1.0
    thompson_beta: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy': self.strategy,
            'epsilon': self.epsilon,
            'ucb_c': self.ucb_c,
            'thompson_alpha': self.thompson_alpha,
            'thompson_beta': self.thompson_beta,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoutingPolicy':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class RetrieverPolicy:
    """
    Retrieval/RAG policy configuration.
    """
    retrieval_k: int = 10
    rerank_top_n: int = 5
    enable_hybrid: bool = True
    sparse_weight: float = 0.3
    dense_weight: float = 0.7
    enable_mmap: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 64
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'retrieval_k': self.retrieval_k,
            'rerank_top_n': self.rerank_top_n,
            'enable_hybrid': self.enable_hybrid,
            'sparse_weight': self.sparse_weight,
            'dense_weight': self.dense_weight,
            'enable_mmap': self.enable_mmap,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetrieverPolicy':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class GlobalSystemsAdapter:
    """
    Manages global system capabilities that specialists can propose improvements to.
    
    When a specialist proposes a caching/routing/retrieval improvement:
    1) Orchestrator checks if it's "algorithmic" (not domain-specific).
    2) If yes, triggers neutral benchmark suite (see scripts/neutral_cache_bench.py).
    3) If improvement verified on neutral tasks, promote to global config.
    4) All specialists benefit immediately without weight sharing.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.cache_policy = CachePolicy()
        self.routing_policy = RoutingPolicy()
        self.retriever_policy = RetrieverPolicy()
        
        self.promotion_log: List[Dict[str, Any]] = []
        self.parameter_mask = self._build_default_mask()
        
        if config_path:
            self.load_from_config(config_path)
    
    def _build_default_mask(self) -> ParameterMask:
        """Build default parameter mask."""
        mask = ParameterMask()
        
        # Global parameters (shared infrastructure)
        for param in [
            'cache.policy', 'cache.ttl_seconds', 'cache.admission_policy',
            'routing.strategy', 'routing.epsilon',
            'retriever.retrieval_k', 'retriever.enable_hybrid',
        ]:
            mask.add_global(param)
        
        # Router parameters (specialist selection)
        for param in ['router.weights', 'router.counts', 'router.rewards']:
            mask.add_router(param)
        
        return mask
    
    def load_from_config(self, config_path: str) -> None:
        """Load global systems config from YAML."""
        try:
            import yaml
            from pathlib import Path
            path = Path(config_path)
            if not path.exists():
                logger.warning(f"Config path not found: {config_path}")
                return
            
            with open(path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
            
            if 'cache' in cfg and isinstance(cfg['cache'], dict):
                self.cache_policy = CachePolicy.from_dict(cfg['cache'])
            
            if 'routing' in cfg and isinstance(cfg['routing'], dict):
                self.routing_policy = RoutingPolicy.from_dict(cfg['routing'])
            
            if 'retriever' in cfg and isinstance(cfg['retriever'], dict):
                self.retriever_policy = RetrieverPolicy.from_dict(cfg['retriever'])
            
            logger.info(f"Loaded global systems config from {config_path}")
            
        except Exception as e:
            logger.warning(f"Failed to load global systems config: {e}")
    
    def save_to_config(self, config_path: str) -> None:
        """Save global systems config to YAML."""
        try:
            import yaml
            from pathlib import Path
            
            data = {
                'cache': self.cache_policy.to_dict(),
                'routing': self.routing_policy.to_dict(),
                'retriever': self.retriever_policy.to_dict(),
                'promotion_log': self.promotion_log[-10:],  # Last 10 promotions
            }
            
            path = Path(config_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Saved global systems config to {config_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save global systems config: {e}")
    
    def is_algorithmic_proposal(self, proposal: Dict[str, Any]) -> bool:
        """
        Determine if a proposal is algorithmic (global capability) vs domain-specific.
        
        Heuristics:
        - Title/description mentions caching, routing, retrieval, scheduling.
        - Changes target infrastructure code (not domain adapters).
        - No domain-specific knowledge embedded in code.
        """
        title = proposal.get('title', '').lower()
        description = proposal.get('changes', {}).get('description', '').lower()
        code = proposal.get('changes', {}).get('code', '').lower()
        
        # Algorithmic keywords
        algorithmic_keywords = [
            'cache', 'caching', 'ttl', 'eviction', 'admission',
            'route', 'routing', 'schedule', 'scheduler',
            'retriev', 'rag', 'rerank', 'chunk',
            'prefetch', 'mmap', 'compression',
        ]
        
        # Domain-specific keywords (exclude if present)
        domain_keywords = [
            'domain', 'specialist', 'knowledge', 'corpus',
            'expert', 'embedding', 'fine-tune', 'adapter',
        ]
        
        text = f"{title} {description} {code}"
        
        has_algorithmic = any(kw in text for kw in algorithmic_keywords)
        has_domain = any(kw in text for kw in domain_keywords)
        
        return has_algorithmic and not has_domain
    
    def promote_cache_improvement(
        self,
        proposal_id: str,
        new_policy: CachePolicy,
        benchmark_results: Dict[str, Any],
        proposer_specialist_id: Optional[str] = None,
    ) -> bool:
        """
        Promote a caching improvement to global config if neutral benchmarks pass.
        
        Args:
            proposal_id: ID of the proposal
            new_policy: Proposed new cache policy
            benchmark_results: Results from neutral benchmark suite
            proposer_specialist_id: ID of the specialist that proposed this
        
        Returns:
            True if promoted, False otherwise
        """
        # Check if neutral benchmarks show improvement
        current_hit_rate = benchmark_results.get('baseline_hit_rate', 0.5)
        new_hit_rate = benchmark_results.get('new_hit_rate', 0.0)
        current_latency = benchmark_results.get('baseline_latency_ms', 100.0)
        new_latency = benchmark_results.get('new_latency_ms', 100.0)
        
        # Promotion criteria
        hit_rate_improved = new_hit_rate > current_hit_rate * 1.05  # 5% improvement
        latency_maintained = new_latency <= current_latency * 1.10  # <10% degradation
        
        if hit_rate_improved and latency_maintained:
            old_fingerprint = self.cache_policy.fingerprint()
            self.cache_policy = new_policy
            new_fingerprint = new_policy.fingerprint()
            
            self.promotion_log.append({
                'timestamp': datetime.now().isoformat(),
                'type': 'cache_policy',
                'proposal_id': proposal_id,
                'proposer_specialist_id': proposer_specialist_id,
                'old_fingerprint': old_fingerprint,
                'new_fingerprint': new_fingerprint,
                'benchmark_results': benchmark_results,
                'promoted': True,
            })
            
            logger.info(
                f"Promoted cache policy from proposal {proposal_id}: "
                f"{new_policy.policy}, hit_rate {current_hit_rate:.3f}→{new_hit_rate:.3f}"
            )
            
            return True
        else:
            self.promotion_log.append({
                'timestamp': datetime.now().isoformat(),
                'type': 'cache_policy',
                'proposal_id': proposal_id,
                'proposer_specialist_id': proposer_specialist_id,
                'benchmark_results': benchmark_results,
                'promoted': False,
                'reason': 'insufficient_improvement',
            })
            
            logger.info(
                f"Rejected cache policy promotion from proposal {proposal_id}: "
                f"hit_rate {current_hit_rate:.3f}→{new_hit_rate:.3f}, "
                f"latency {current_latency:.1f}→{new_latency:.1f}ms"
            )
            
            return False
    
    def get_current_cache_policy(self) -> CachePolicy:
        """Get the current global cache policy."""
        return self.cache_policy
    
    def get_current_routing_policy(self) -> RoutingPolicy:
        """Get the current global routing policy."""
        return self.routing_policy
    
    def get_current_retriever_policy(self) -> RetrieverPolicy:
        """Get the current global retriever policy."""
        return self.retriever_policy
    
    def get_promotion_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent promotion history."""
        return self.promotion_log[-limit:]
    
    def get_parameter_mask(self) -> ParameterMask:
        """Get the parameter mask for training."""
        return self.parameter_mask


# Global singleton
_global_systems_adapter: Optional[GlobalSystemsAdapter] = None


def get_global_systems_adapter(config_path: Optional[str] = None) -> GlobalSystemsAdapter:
    """Get or create the global systems adapter singleton."""
    global _global_systems_adapter
    if _global_systems_adapter is None:
        _global_systems_adapter = GlobalSystemsAdapter(config_path)
    return _global_systems_adapter
