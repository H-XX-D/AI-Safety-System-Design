"""
Steering Vectors - Compute and apply activation steering for behavior modification.

Uses contrastive examples (approved vs rejected proposals) to compute
"direction vectors" that can steer model behavior without retraining.

Based on Representation Engineering (Zou et al., 2023).

Since we store distilled knowledge and citations (not full content),
steering vectors are computed from:
- Proposal content patterns
- Success/failure characteristics
- Confidence calibration patterns
"""

import json
import time
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class SteeringVector:
    """A computed steering vector for a specific behavior."""
    id: str
    name: str
    description: str
    
    # The actual vector (serialized as list for JSON storage)
    vector: List[float]
    dimension: int
    
    # Computation metadata
    n_positive_examples: int
    n_negative_examples: int
    computed_at: float
    
    # Application settings
    default_strength: float = 1.0
    min_strength: float = 0.0
    max_strength: float = 3.0
    
    # Validation
    validation_score: Optional[float] = None  # How well it worked in testing
    
    # Source tracking
    source_session: str = ""
    positive_example_ids: List[str] = field(default_factory=list)
    negative_example_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'vector': self.vector,
            'dimension': self.dimension,
            'n_positive_examples': self.n_positive_examples,
            'n_negative_examples': self.n_negative_examples,
            'computed_at': self.computed_at,
            'default_strength': self.default_strength,
            'min_strength': self.min_strength,
            'max_strength': self.max_strength,
            'validation_score': self.validation_score,
            'source_session': self.source_session,
            'positive_example_ids': self.positive_example_ids,
            'negative_example_ids': self.negative_example_ids
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SteeringVector':
        return cls(**data)
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(self.vector)


@dataclass
class SteeringConfig:
    """Configuration for applying steering vectors."""
    vectors: Dict[str, float]  # vector_id -> strength
    
    def to_dict(self) -> Dict[str, Any]:
        return {'vectors': self.vectors}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SteeringConfig':
        return cls(vectors=data.get('vectors', {}))


class SteeringVectorStore:
    """
    Store and manage steering vectors for behavior modification.
    
    Vectors are computed from contrastive examples:
    - Quality direction: approved (high reward) vs rejected
    - Honesty direction: calibrated confidence vs overconfident
    - Safety direction: safe proposals vs risky ones
    
    Since full content is in PaperQA, we compute vectors from:
    - Distilled insights and patterns
    - Proposal metadata and outcomes
    - Embedding-space directions
    """
    
    def __init__(
        self,
        data_dir: str = "./data/steering",
        embedding_dim: int = 384
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedding_dim = embedding_dim
        self.vectors_file = self.data_dir / "vectors.json"
        
        self._vectors: Dict[str, SteeringVector] = {}
        self._lock = threading.RLock()
        
        self._load()
    
    def _load(self) -> None:
        """Load vectors from disk."""
        if self.vectors_file.exists():
            try:
                with open(self.vectors_file, 'r') as f:
                    data = json.load(f)
                    self._vectors = {
                        vid: SteeringVector.from_dict(vdata)
                        for vid, vdata in data.items()
                    }
                logger.info(f"Loaded {len(self._vectors)} steering vectors")
            except Exception as e:
                logger.warning(f"Failed to load steering vectors: {e}")
    
    def _save(self) -> None:
        """Save vectors to disk."""
        try:
            with open(self.vectors_file, 'w') as f:
                json.dump(
                    {vid: v.to_dict() for vid, v in self._vectors.items()},
                    f, indent=2
                )
        except Exception as e:
            logger.error(f"Failed to save steering vectors: {e}")
    
    def compute_vector(
        self,
        name: str,
        description: str,
        positive_embeddings: List[np.ndarray],
        negative_embeddings: List[np.ndarray],
        positive_ids: List[str] = None,
        negative_ids: List[str] = None,
        session_id: str = ""
    ) -> SteeringVector:
        """
        Compute a steering vector from contrastive embeddings.
        
        Direction = mean(positive) - mean(negative)
        
        Args:
            name: Name for this vector (e.g., "quality", "honesty")
            description: What this vector steers toward
            positive_embeddings: Embeddings of positive examples
            negative_embeddings: Embeddings of negative examples
            positive_ids: IDs of positive examples (for tracking)
            negative_ids: IDs of negative examples (for tracking)
            session_id: Session that computed this
        
        Returns:
            Computed SteeringVector
        """
        with self._lock:
            if not positive_embeddings or not negative_embeddings:
                raise ValueError("Need at least one positive and one negative example")
            
            # Stack and compute means
            pos_matrix = np.array(positive_embeddings)
            neg_matrix = np.array(negative_embeddings)
            
            pos_mean = pos_matrix.mean(axis=0)
            neg_mean = neg_matrix.mean(axis=0)
            
            # Direction vector
            direction = pos_mean - neg_mean
            
            # Normalize
            norm = np.linalg.norm(direction)
            if norm > 0:
                direction = direction / norm
            
            # Create vector
            vector_id = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:16]
            
            vector = SteeringVector(
                id=vector_id,
                name=name,
                description=description,
                vector=direction.tolist(),
                dimension=len(direction),
                n_positive_examples=len(positive_embeddings),
                n_negative_examples=len(negative_embeddings),
                computed_at=time.time(),
                source_session=session_id,
                positive_example_ids=positive_ids or [],
                negative_example_ids=negative_ids or []
            )
            
            # Store
            self._vectors[vector_id] = vector
            self._save()
            
            logger.info(f"Computed steering vector '{name}' from {len(positive_embeddings)}+ / {len(negative_embeddings)}- examples")
            
            return vector
    
    def get_vector(self, vector_id: str) -> Optional[SteeringVector]:
        """Get a vector by ID."""
        return self._vectors.get(vector_id)
    
    def get_vector_by_name(self, name: str) -> Optional[SteeringVector]:
        """Get the most recent vector with a given name."""
        matching = [v for v in self._vectors.values() if v.name == name]
        if matching:
            return max(matching, key=lambda v: v.computed_at)
        return None
    
    def list_vectors(self) -> List[SteeringVector]:
        """List all vectors."""
        return list(self._vectors.values())
    
    def delete_vector(self, vector_id: str) -> bool:
        """Delete a vector."""
        with self._lock:
            if vector_id in self._vectors:
                del self._vectors[vector_id]
                self._save()
                return True
            return False
    
    def apply_steering(
        self,
        embedding: np.ndarray,
        config: SteeringConfig
    ) -> np.ndarray:
        """
        Apply steering vectors to an embedding.
        
        Result = embedding + sum(strength_i * vector_i)
        
        Args:
            embedding: Original embedding to steer
            config: Which vectors to apply and at what strength
        
        Returns:
            Steered embedding
        """
        result = embedding.copy()
        
        for vector_id, strength in config.vectors.items():
            vector = self.get_vector(vector_id)
            if vector:
                # Clamp strength
                strength = max(vector.min_strength, min(vector.max_strength, strength))
                result += strength * vector.to_numpy()
        
        # Re-normalize
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm
        
        return result
    
    def update_validation_score(self, vector_id: str, score: float) -> None:
        """Update a vector's validation score after testing."""
        with self._lock:
            if vector_id in self._vectors:
                self._vectors[vector_id].validation_score = score
                self._save()
    
    # ========== Predefined Vector Types ==========
    
    def compute_quality_vector(
        self,
        approved_embeddings: List[np.ndarray],
        rejected_embeddings: List[np.ndarray],
        approved_ids: List[str] = None,
        rejected_ids: List[str] = None,
        session_id: str = ""
    ) -> SteeringVector:
        """Compute a quality steering vector from approved vs rejected proposals."""
        return self.compute_vector(
            name="quality",
            description="Steers toward high-quality, approvable proposals",
            positive_embeddings=approved_embeddings,
            negative_embeddings=rejected_embeddings,
            positive_ids=approved_ids,
            negative_ids=rejected_ids,
            session_id=session_id
        )
    
    def compute_honesty_vector(
        self,
        calibrated_embeddings: List[np.ndarray],
        overconfident_embeddings: List[np.ndarray],
        calibrated_ids: List[str] = None,
        overconfident_ids: List[str] = None,
        session_id: str = ""
    ) -> SteeringVector:
        """
        Compute an honesty/calibration steering vector.
        
        Positive: Proposals where confidence matched outcome
        Negative: Proposals where confidence was too high for outcome
        """
        return self.compute_vector(
            name="honesty",
            description="Steers toward calibrated confidence and honest uncertainty",
            positive_embeddings=calibrated_embeddings,
            negative_embeddings=overconfident_embeddings,
            positive_ids=calibrated_ids,
            negative_ids=overconfident_ids,
            session_id=session_id
        )
    
    def compute_safety_vector(
        self,
        safe_embeddings: List[np.ndarray],
        risky_embeddings: List[np.ndarray],
        safe_ids: List[str] = None,
        risky_ids: List[str] = None,
        session_id: str = ""
    ) -> SteeringVector:
        """Compute a safety steering vector."""
        return self.compute_vector(
            name="safety",
            description="Steers toward safer, lower-risk proposals",
            positive_embeddings=safe_embeddings,
            negative_embeddings=risky_embeddings,
            positive_ids=safe_ids,
            negative_ids=risky_ids,
            session_id=session_id
        )
    
    # ========== Composite Steering ==========
    
    def create_composite_config(
        self,
        quality_strength: float = 1.0,
        honesty_strength: float = 1.0,
        safety_strength: float = 0.5
    ) -> SteeringConfig:
        """
        Create a composite steering configuration.
        
        Uses the most recent version of each named vector.
        """
        config_vectors = {}
        
        for name, strength in [
            ("quality", quality_strength),
            ("honesty", honesty_strength),
            ("safety", safety_strength)
        ]:
            vector = self.get_vector_by_name(name)
            if vector and strength > 0:
                config_vectors[vector.id] = strength
        
        return SteeringConfig(vectors=config_vectors)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get steering vector statistics."""
        vectors_by_name = {}
        for v in self._vectors.values():
            if v.name not in vectors_by_name:
                vectors_by_name[v.name] = []
            vectors_by_name[v.name].append({
                'id': v.id,
                'computed_at': v.computed_at,
                'n_examples': v.n_positive_examples + v.n_negative_examples,
                'validation_score': v.validation_score
            })
        
        return {
            'total_vectors': len(self._vectors),
            'vectors_by_name': vectors_by_name,
            'embedding_dimension': self.embedding_dim
        }

