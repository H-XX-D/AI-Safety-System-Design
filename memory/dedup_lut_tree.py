"""
Deduplication LUT Tree - Efficient lookup for knowledge deduplication.

Uses a hierarchical tree structure for:
1. Fast duplicate detection without full comparison
2. Similarity-based clustering of related knowledge
3. Version tracking (newer doesn't overwrite older, but links to it)
4. Preserving historical context while avoiding redundancy

Structure:
- Level 1: Domain (safety, performance, etc.)
- Level 2: Topic hash (first N bits of content hash)
- Level 3: Semantic cluster (similar content grouped)
- Leaves: Actual knowledge items with version chains
"""

import json
import time
import hashlib
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeNode:
    """A node in the knowledge tree (leaf level)."""
    id: str
    content_hash: str  # Full hash for exact dedup
    signature: str     # Shorter signature for fast lookup
    content_preview: str  # First N chars for quick comparison
    
    # Metadata
    domain: str
    topic_cluster: str
    created_at: float
    source_session: str
    confidence: float
    usage_count: int = 0
    
    # Version chain (links to related/previous versions)
    parent_id: Optional[str] = None  # Previous version this evolved from
    child_ids: List[str] = field(default_factory=list)  # Later versions
    related_ids: List[str] = field(default_factory=list)  # Similar but different
    
    # Similarity info
    embedding_hash: Optional[str] = None  # Hash of embedding for clustering
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content_hash': self.content_hash,
            'signature': self.signature,
            'content_preview': self.content_preview,
            'domain': self.domain,
            'topic_cluster': self.topic_cluster,
            'created_at': self.created_at,
            'source_session': self.source_session,
            'confidence': self.confidence,
            'usage_count': self.usage_count,
            'parent_id': self.parent_id,
            'child_ids': self.child_ids,
            'related_ids': self.related_ids,
            'embedding_hash': self.embedding_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeNode':
        return cls(**data)


@dataclass
class DedupResult:
    """Result of a deduplication check."""
    is_duplicate: bool
    is_similar: bool
    exact_match_id: Optional[str] = None
    similar_ids: List[str] = field(default_factory=list)
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    recommended_action: str = 'add'  # 'add', 'merge', 'skip', 'link'
    merge_target_id: Optional[str] = None


class TopicCluster:
    """A cluster of semantically similar knowledge items."""
    
    def __init__(self, cluster_id: str):
        self.cluster_id = cluster_id
        self.node_ids: Set[str] = set()
        self.centroid: Optional[np.ndarray] = None
        self.keywords: Set[str] = set()
        self.created_at = time.time()
        self.updated_at = time.time()
    
    def add_node(self, node_id: str, keywords: List[str] = None) -> None:
        self.node_ids.add(node_id)
        if keywords:
            self.keywords.update(keywords)
        self.updated_at = time.time()
    
    def remove_node(self, node_id: str) -> None:
        self.node_ids.discard(node_id)
        self.updated_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cluster_id': self.cluster_id,
            'node_ids': list(self.node_ids),
            'keywords': list(self.keywords),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopicCluster':
        cluster = cls(data['cluster_id'])
        cluster.node_ids = set(data.get('node_ids', []))
        cluster.keywords = set(data.get('keywords', []))
        cluster.created_at = data.get('created_at', time.time())
        cluster.updated_at = data.get('updated_at', time.time())
        return cluster


class DedupLUTTree:
    """
    Hierarchical LUT tree for knowledge deduplication.
    
    Structure:
    tree[domain][signature_prefix][cluster_id] -> List[KnowledgeNode]
    
    Features:
    - O(1) exact duplicate detection via hash
    - O(log n) similar item lookup via tree traversal
    - Version chains preserve history
    - Automatic clustering of related items
    """
    
    def __init__(
        self,
        data_dir: str = "./data/dedup",
        signature_bits: int = 16,  # Bits for signature prefix
        similarity_threshold: float = 0.85,
        max_cluster_size: int = 100
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.signature_bits = signature_bits
        self.similarity_threshold = similarity_threshold
        self.max_cluster_size = max_cluster_size
        
        # Tree structure: domain -> signature_prefix -> cluster_id -> nodes
        self._tree: Dict[str, Dict[str, Dict[str, List[str]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        
        # Fast lookup tables
        self._hash_to_id: Dict[str, str] = {}  # content_hash -> node_id (exact dedup)
        self._id_to_node: Dict[str, KnowledgeNode] = {}  # node_id -> node
        self._clusters: Dict[str, TopicCluster] = {}  # cluster_id -> cluster
        
        self._lock = threading.RLock()
        
        # Load existing data
        self._load()
    
    def _compute_signature(self, content: str) -> str:
        """Compute short signature for tree lookup."""
        full_hash = hashlib.sha256(content.encode()).hexdigest()
        # Take first N hex chars based on signature_bits
        hex_chars = self.signature_bits // 4
        return full_hash[:hex_chars]
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute full content hash for exact dedup."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _extract_keywords(self, content: str, n: int = 10) -> List[str]:
        """Extract keywords from content for clustering."""
        words = content.lower().split()
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                     'this', 'that', 'and', 'or', 'but', 'if', 'it', 'its'}
        
        word_counts = {}
        for word in words:
            if len(word) > 3 and word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:n]]
    
    def _compute_keyword_similarity(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """Compute Jaccard similarity between keyword sets."""
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)
        
        return intersection / union if union > 0 else 0.0
    
    def _find_best_cluster(
        self,
        domain: str,
        signature: str,
        keywords: Set[str]
    ) -> Tuple[Optional[str], float]:
        """Find the best matching cluster for new content."""
        best_cluster_id = None
        best_similarity = 0.0
        
        # Look in the same signature prefix
        prefix_clusters = self._tree[domain][signature]
        
        for cluster_id in prefix_clusters:
            if cluster_id in self._clusters:
                cluster = self._clusters[cluster_id]
                similarity = self._compute_keyword_similarity(keywords, cluster.keywords)
                
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_cluster_id = cluster_id
        
        return best_cluster_id, best_similarity
    
    def check_duplicate(
        self,
        content: str,
        domain: str = 'general'
    ) -> DedupResult:
        """
        Check if content is a duplicate or similar to existing knowledge.
        
        Returns DedupResult with recommended action:
        - 'add': New unique content, add to tree
        - 'skip': Exact duplicate, don't add
        - 'merge': Very similar, merge with existing
        - 'link': Related content, add with link to existing
        """
        with self._lock:
            content_hash = self._compute_content_hash(content)
            signature = self._compute_signature(content)
            keywords = set(self._extract_keywords(content))
            
            # Check for exact duplicate
            if content_hash in self._hash_to_id:
                existing_id = self._hash_to_id[content_hash]
                return DedupResult(
                    is_duplicate=True,
                    is_similar=True,
                    exact_match_id=existing_id,
                    recommended_action='skip'
                )
            
            # Check for similar content
            similar_ids = []
            similarity_scores = {}
            
            # Find best cluster
            best_cluster_id, best_similarity = self._find_best_cluster(domain, signature, keywords)
            
            if best_cluster_id and best_cluster_id in self._clusters:
                cluster = self._clusters[best_cluster_id]
                
                # Check similarity with nodes in cluster
                for node_id in cluster.node_ids:
                    if node_id in self._id_to_node:
                        node = self._id_to_node[node_id]
                        # Quick similarity check via preview
                        preview_similarity = self._quick_similarity(content[:200], node.content_preview)
                        
                        if preview_similarity > 0.5:
                            similar_ids.append(node_id)
                            similarity_scores[node_id] = preview_similarity
            
            # Determine action
            if similar_ids:
                max_similarity = max(similarity_scores.values())
                most_similar_id = max(similarity_scores, key=similarity_scores.get)
                
                if max_similarity > 0.95:
                    return DedupResult(
                        is_duplicate=False,
                        is_similar=True,
                        similar_ids=similar_ids,
                        similarity_scores=similarity_scores,
                        recommended_action='merge',
                        merge_target_id=most_similar_id
                    )
                elif max_similarity > 0.7:
                    return DedupResult(
                        is_duplicate=False,
                        is_similar=True,
                        similar_ids=similar_ids,
                        similarity_scores=similarity_scores,
                        recommended_action='link',
                        merge_target_id=most_similar_id
                    )
            
            # New unique content
            return DedupResult(
                is_duplicate=False,
                is_similar=len(similar_ids) > 0,
                similar_ids=similar_ids,
                similarity_scores=similarity_scores,
                recommended_action='add'
            )
    
    def _quick_similarity(self, text1: str, text2: str) -> float:
        """Quick text similarity using character n-grams."""
        if not text1 or not text2:
            return 0.0
        
        # Character 3-grams
        def get_ngrams(text: str, n: int = 3) -> Set[str]:
            text = text.lower()
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams1 = get_ngrams(text1)
        ngrams2 = get_ngrams(text2)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def add(
        self,
        content: str,
        domain: str,
        source_session: str,
        confidence: float = 0.5,
        parent_id: Optional[str] = None,
        force: bool = False
    ) -> Tuple[str, DedupResult]:
        """
        Add content to the tree with deduplication.
        
        Args:
            content: The knowledge content
            domain: Knowledge domain
            source_session: Session that generated this
            confidence: Confidence score
            parent_id: Optional parent node (for version chains)
            force: Force add even if duplicate
        
        Returns:
            Tuple of (node_id, dedup_result)
        """
        with self._lock:
            # Check for duplicates first
            dedup_result = self.check_duplicate(content, domain)
            
            if dedup_result.recommended_action == 'skip' and not force:
                # Update usage count on existing
                if dedup_result.exact_match_id:
                    self._update_usage(dedup_result.exact_match_id)
                return dedup_result.exact_match_id, dedup_result
            
            # Generate IDs and hashes
            content_hash = self._compute_content_hash(content)
            signature = self._compute_signature(content)
            node_id = f"kn_{content_hash[:16]}"
            keywords = set(self._extract_keywords(content))
            
            # Find or create cluster
            cluster_id, _ = self._find_best_cluster(domain, signature, keywords)
            
            if not cluster_id:
                cluster_id = f"cluster_{domain}_{signature}_{int(time.time())}"
                self._clusters[cluster_id] = TopicCluster(cluster_id)
            
            cluster = self._clusters[cluster_id]
            
            # Handle linking/merging
            related_ids = []
            if dedup_result.recommended_action == 'link' and dedup_result.merge_target_id:
                related_ids = [dedup_result.merge_target_id]
                # Update the related node too
                if dedup_result.merge_target_id in self._id_to_node:
                    self._id_to_node[dedup_result.merge_target_id].related_ids.append(node_id)
            
            # Handle version chain
            if parent_id and parent_id in self._id_to_node:
                self._id_to_node[parent_id].child_ids.append(node_id)
            
            # Create node
            node = KnowledgeNode(
                id=node_id,
                content_hash=content_hash,
                signature=signature,
                content_preview=content[:200],
                domain=domain,
                topic_cluster=cluster_id,
                created_at=time.time(),
                source_session=source_session,
                confidence=confidence,
                parent_id=parent_id,
                related_ids=related_ids
            )
            
            # Add to tree
            self._id_to_node[node_id] = node
            self._hash_to_id[content_hash] = node_id
            self._tree[domain][signature][cluster_id].append(node_id)
            cluster.add_node(node_id, list(keywords))
            
            # Save periodically
            if len(self._id_to_node) % 100 == 0:
                self._save()
            
            return node_id, dedup_result
    
    def get(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get a node by ID."""
        return self._id_to_node.get(node_id)
    
    def get_version_chain(self, node_id: str) -> List[KnowledgeNode]:
        """Get the full version chain for a node (ancestors and descendants)."""
        chain = []
        
        node = self.get(node_id)
        if not node:
            return chain
        
        # Get ancestors
        current = node
        while current.parent_id:
            parent = self.get(current.parent_id)
            if parent:
                chain.insert(0, parent)
                current = parent
            else:
                break
        
        # Add self
        chain.append(node)
        
        # Get descendants (BFS)
        to_visit = list(node.child_ids)
        while to_visit:
            child_id = to_visit.pop(0)
            child = self.get(child_id)
            if child:
                chain.append(child)
                to_visit.extend(child.child_ids)
        
        return chain
    
    def get_related(self, node_id: str) -> List[KnowledgeNode]:
        """Get related nodes (similar content, not version chain)."""
        node = self.get(node_id)
        if not node:
            return []
        
        related = []
        for related_id in node.related_ids:
            related_node = self.get(related_id)
            if related_node:
                related.append(related_node)
        
        return related
    
    def get_cluster(self, cluster_id: str) -> List[KnowledgeNode]:
        """Get all nodes in a cluster."""
        if cluster_id not in self._clusters:
            return []
        
        cluster = self._clusters[cluster_id]
        return [self.get(nid) for nid in cluster.node_ids if self.get(nid)]
    
    def search_by_domain(self, domain: str, limit: int = 50) -> List[KnowledgeNode]:
        """Get nodes by domain."""
        nodes = []
        
        for signature_dict in self._tree.get(domain, {}).values():
            for cluster_dict in signature_dict.values():
                for node_id in cluster_dict:
                    node = self.get(node_id)
                    if node:
                        nodes.append(node)
        
        # Sort by confidence and recency
        nodes.sort(key=lambda n: (n.confidence, n.created_at), reverse=True)
        return nodes[:limit]
    
    def _update_usage(self, node_id: str) -> None:
        """Update usage statistics for a node."""
        if node_id in self._id_to_node:
            self._id_to_node[node_id].usage_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tree statistics."""
        domain_counts = {}
        for domain in self._tree:
            count = sum(
                len(nodes)
                for sig_dict in self._tree[domain].values()
                for nodes in sig_dict.values()
            )
            domain_counts[domain] = count
        
        return {
            'total_nodes': len(self._id_to_node),
            'total_clusters': len(self._clusters),
            'domains': list(self._tree.keys()),
            'nodes_by_domain': domain_counts,
            'unique_hashes': len(self._hash_to_id)
        }
    
    def _save(self) -> None:
        """Save tree to disk."""
        try:
            # Save nodes
            nodes_file = self.data_dir / "nodes.json"
            with open(nodes_file, 'w') as f:
                json.dump({nid: n.to_dict() for nid, n in self._id_to_node.items()}, f)
            
            # Save clusters
            clusters_file = self.data_dir / "clusters.json"
            with open(clusters_file, 'w') as f:
                json.dump({cid: c.to_dict() for cid, c in self._clusters.items()}, f)
            
            # Save hash index
            hash_file = self.data_dir / "hash_index.json"
            with open(hash_file, 'w') as f:
                json.dump(self._hash_to_id, f)
            
            # Save tree structure
            tree_file = self.data_dir / "tree.json"
            # Convert defaultdicts to regular dicts for JSON
            tree_data = {
                domain: {
                    sig: {
                        cluster: list(nodes)
                        for cluster, nodes in clusters.items()
                    }
                    for sig, clusters in sigs.items()
                }
                for domain, sigs in self._tree.items()
            }
            with open(tree_file, 'w') as f:
                json.dump(tree_data, f)
            
            logger.debug(f"Saved dedup tree: {len(self._id_to_node)} nodes")
        except Exception as e:
            logger.error(f"Failed to save dedup tree: {e}")
    
    def _load(self) -> None:
        """Load tree from disk."""
        try:
            # Load nodes
            nodes_file = self.data_dir / "nodes.json"
            if nodes_file.exists():
                with open(nodes_file, 'r') as f:
                    nodes_data = json.load(f)
                    self._id_to_node = {
                        nid: KnowledgeNode.from_dict(data)
                        for nid, data in nodes_data.items()
                    }
            
            # Load clusters
            clusters_file = self.data_dir / "clusters.json"
            if clusters_file.exists():
                with open(clusters_file, 'r') as f:
                    clusters_data = json.load(f)
                    self._clusters = {
                        cid: TopicCluster.from_dict(data)
                        for cid, data in clusters_data.items()
                    }
            
            # Load hash index
            hash_file = self.data_dir / "hash_index.json"
            if hash_file.exists():
                with open(hash_file, 'r') as f:
                    self._hash_to_id = json.load(f)
            
            # Load tree structure
            tree_file = self.data_dir / "tree.json"
            if tree_file.exists():
                with open(tree_file, 'r') as f:
                    tree_data = json.load(f)
                    for domain, sigs in tree_data.items():
                        for sig, clusters in sigs.items():
                            for cluster, nodes in clusters.items():
                                self._tree[domain][sig][cluster] = nodes
            
            logger.info(f"Loaded dedup tree: {len(self._id_to_node)} nodes, {len(self._clusters)} clusters")
        except Exception as e:
            logger.warning(f"Failed to load dedup tree (starting fresh): {e}")

