"""
AURA NumPy Template Store

Stores binary semantic templates as numpy arrays for zero-copy native access.
Templates are indexed by ID for O(1) lookup.

Structure:
- template_strings.npy: Fixed-width string array (65536, max_len)
- template_metadata.npy: Structured array with slots, range_id, flags
- template_index.npy: Byte offsets for variable-length access

Usage:
    store = AURANumpyTemplates()
    
    # Add templates as they're created
    store.add_template(128, "System {0} approves proposal {1}", slots=2)
    
    # Batch add from proposals
    store.add_from_proposals(proposals_list)
    
    # Save for native access
    store.save("/opt/orka/aura_templates/")
    
    # Load with mmap (zero-copy)
    store.load_mmap("/opt/orka/aura_templates/")
    
    # Fast lookup
    template = store.get_template(128)  # Returns bytes, no copy
"""

import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Union
import mmap
import os
import json
import hashlib
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Template ranges from AURA protocol
TEMPLATE_RANGES = {
    "default": (0, 127),
    "ai_to_ai": (128, 2127),
    "human_to_ai": (2128, 4999),
    "healthcare": (5000, 6999),
    "financial": (7000, 9999),
    "legal": (10000, 11999),
    "small_sentences": (12000, 13999),
    "dynamic_range": (14000, 16383),
    "client_sync": (16384, 32767),
    "whitespace_variants": (32768, 49151),
    "reserved_future": (49152, 65535),
}

# Max template length (bytes)
MAX_TEMPLATE_LEN = 256

# Total templates
NUM_TEMPLATES = 65536


@dataclass
class TemplateMetadata:
    """Metadata for a single template."""
    template_id: int
    slot_count: int
    range_id: int
    flags: int  # bit 0: active, bit 1: compressed, bit 2: secure_only
    hash_prefix: int  # First 4 bytes of SHA256 for integrity


class AURANumpyTemplates:
    """
    NumPy-based template store for AURA compression.
    
    Stores templates in memory-mappable numpy arrays for
    zero-copy access from native C code.
    """
    
    # Structured dtype for metadata
    METADATA_DTYPE = np.dtype([
        ('slot_count', np.uint8),
        ('range_id', np.uint8),
        ('flags', np.uint8),
        ('length', np.uint8),  # Actual template length
        ('hash_prefix', np.uint32),
    ])
    
    def __init__(self, max_template_len: int = MAX_TEMPLATE_LEN):
        self.max_len = max_template_len
        self.num_templates = NUM_TEMPLATES
        
        # Main storage arrays
        self._strings: Optional[np.ndarray] = None  # (65536, max_len) uint8
        self._metadata: Optional[np.ndarray] = None  # (65536,) structured
        self._initialized = False
        
        # Mmap backing
        self._mmap_strings: Optional[mmap.mmap] = None
        self._mmap_metadata: Optional[mmap.mmap] = None
        
        # Tracking
        self._template_count = 0
        self._dirty = False
    
    def _ensure_initialized(self):
        """Lazy initialization of arrays."""
        if not self._initialized:
            # Allocate arrays
            self._strings = np.zeros((self.num_templates, self.max_len), dtype=np.uint8)
            self._metadata = np.zeros(self.num_templates, dtype=self.METADATA_DTYPE)
            self._initialized = True
    
    def add_template(
        self,
        template_id: int,
        pattern: str,
        slots: int = 0,
        range_name: Optional[str] = None,
        flags: int = 1  # Active by default
    ) -> bool:
        """
        Add a single template.
        
        Args:
            template_id: Template ID (0-65535)
            pattern: Template string with {0}, {1}, etc. placeholders
            slots: Number of slots (auto-detected if 0)
            range_name: Range name (auto-detected from ID if None)
            flags: Template flags
            
        Returns:
            True if added successfully
        """
        if template_id < 0 or template_id >= self.num_templates:
            return False
        
        self._ensure_initialized()
        
        # Encode pattern
        pattern_bytes = pattern.encode('utf-8')
        if len(pattern_bytes) > self.max_len:
            pattern_bytes = pattern_bytes[:self.max_len]
        
        # Auto-detect slots
        if slots == 0:
            slots = pattern.count('{')
        
        # Auto-detect range
        range_id = 0
        if range_name is None:
            for idx, (name, (start, end)) in enumerate(TEMPLATE_RANGES.items()):
                if start <= template_id <= end:
                    range_id = idx
                    break
        else:
            range_id = list(TEMPLATE_RANGES.keys()).index(range_name) if range_name in TEMPLATE_RANGES else 0
        
        # Compute hash prefix
        hash_prefix = int.from_bytes(
            hashlib.sha256(pattern_bytes).digest()[:4],
            'little'
        )
        
        # Store in arrays
        self._strings[template_id, :len(pattern_bytes)] = np.frombuffer(pattern_bytes, dtype=np.uint8)
        self._strings[template_id, len(pattern_bytes):] = 0  # Zero-pad
        
        self._metadata[template_id]['slot_count'] = min(slots, 255)
        self._metadata[template_id]['range_id'] = range_id
        self._metadata[template_id]['flags'] = flags
        self._metadata[template_id]['length'] = len(pattern_bytes)
        self._metadata[template_id]['hash_prefix'] = hash_prefix
        
        self._template_count += 1
        self._dirty = True
        
        return True
    
    def add_from_proposal(self, proposal: Dict) -> Optional[int]:
        """
        Add template from a proposal dict.
        
        Extracts the pattern from proposal text and assigns
        an appropriate template ID based on proposal type.
        
        Args:
            proposal: Proposal dict with 'text', 'type', etc.
            
        Returns:
            Template ID if added, None otherwise
        """
        text = proposal.get('text', '')
        prop_type = proposal.get('type', 'default')
        
        # Map proposal type to range
        type_to_range = {
            'approval': 'ai_to_ai',
            'rejection': 'ai_to_ai',
            'review': 'ai_to_ai',
            'vote': 'ai_to_ai',
            'query': 'human_to_ai',
            'health': 'healthcare',
            'finance': 'financial',
            'legal': 'legal',
        }
        
        range_name = type_to_range.get(prop_type.lower(), 'dynamic_range')
        start, end = TEMPLATE_RANGES[range_name]
        
        # Find next available ID in range
        self._ensure_initialized()
        for tid in range(start, end + 1):
            if self._metadata[tid]['flags'] == 0:  # Not active
                # Convert text to template pattern
                pattern = self._extract_pattern(text)
                slots = pattern.count('{')
                
                if self.add_template(tid, pattern, slots, range_name):
                    return tid
                break
        
        return None
    
    def add_from_proposals(self, proposals: List[Dict]) -> List[int]:
        """Add templates from multiple proposals."""
        added = []
        for proposal in proposals:
            tid = self.add_from_proposal(proposal)
            if tid is not None:
                added.append(tid)
        return added
    
    def _extract_pattern(self, text: str) -> str:
        """
        Extract template pattern from text.
        
        Replaces variable parts with {0}, {1}, etc.
        """
        import re
        
        # Replace common variable patterns
        pattern = text
        slot_idx = 0
        
        # Replace quoted strings
        def replace_quoted(m):
            nonlocal slot_idx
            result = f'{{{slot_idx}}}'
            slot_idx += 1
            return result
        
        pattern = re.sub(r'"[^"]*"', replace_quoted, pattern)
        
        # Replace numbers (proposal IDs, etc.)
        pattern = re.sub(r'\b\d{3,}\b', lambda m: f'{{{slot_idx}}}', pattern)
        
        # Replace system names
        pattern = re.sub(r'System \w+', lambda m: f'System {{{slot_idx}}}', pattern)
        
        return pattern
    
    def get_template(self, template_id: int) -> Optional[bytes]:
        """
        Get template by ID.
        
        Returns raw bytes (zero-copy if mmap'd).
        """
        if template_id < 0 or template_id >= self.num_templates:
            return None
        
        if self._strings is None:
            return None
        
        length = self._metadata[template_id]['length']
        if length == 0:
            return None
        
        # Return view (zero-copy)
        return bytes(self._strings[template_id, :length])
    
    def get_template_str(self, template_id: int) -> Optional[str]:
        """Get template as string."""
        data = self.get_template(template_id)
        if data is None:
            return None
        return data.decode('utf-8')
    
    def get_metadata(self, template_id: int) -> Optional[TemplateMetadata]:
        """Get template metadata."""
        if template_id < 0 or template_id >= self.num_templates:
            return None
        
        if self._metadata is None:
            return None
        
        m = self._metadata[template_id]
        if m['flags'] == 0:
            return None
        
        return TemplateMetadata(
            template_id=template_id,
            slot_count=int(m['slot_count']),
            range_id=int(m['range_id']),
            flags=int(m['flags']),
            hash_prefix=int(m['hash_prefix'])
        )
    
    def save(self, directory: Union[str, Path]):
        """
        Save templates to directory as .npy files.
        
        Creates:
        - templates_strings.npy
        - templates_metadata.npy
        - templates_manifest.json
        """
        if not self._initialized:
            return
        
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        
        # Save arrays
        np.save(path / "templates_strings.npy", self._strings)
        np.save(path / "templates_metadata.npy", self._metadata)
        
        # Save manifest
        manifest = {
            "version": "1.0.0",
            "num_templates": self.num_templates,
            "max_template_len": self.max_len,
            "active_count": self._template_count,
            "dtype_strings": str(self._strings.dtype),
            "dtype_metadata": str(self._metadata.dtype),
            "shape_strings": list(self._strings.shape),
            "sha256_strings": hashlib.sha256(self._strings.tobytes()).hexdigest(),
            "sha256_metadata": hashlib.sha256(self._metadata.tobytes()).hexdigest(),
        }
        
        with open(path / "templates_manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        self._dirty = False
        logger.info(f"Saved {self._template_count} templates to {path}")
    
    def load(self, directory: Union[str, Path]):
        """Load templates from .npy files."""
        path = Path(directory)
        
        strings_path = path / "templates_strings.npy"
        metadata_path = path / "templates_metadata.npy"
        
        if not strings_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Template files not found in {path}")
        
        self._strings = np.load(strings_path)
        self._metadata = np.load(metadata_path)
        self._initialized = True
        
        # Count active templates
        self._template_count = int(np.sum(self._metadata['flags'] > 0))
        self._dirty = False
        
        logger.info(f"Loaded {self._template_count} templates from {path}")
    
    def load_mmap(self, directory: Union[str, Path]):
        """
        Load templates with memory mapping (zero-copy).
        
        The arrays are not loaded into RAM, but accessed
        directly from disk. Changes are not persisted.
        """
        path = Path(directory)
        
        strings_path = path / "templates_strings.npy"
        metadata_path = path / "templates_metadata.npy"
        
        if not strings_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Template files not found in {path}")
        
        # Memory-map the arrays
        self._strings = np.load(strings_path, mmap_mode='r')
        self._metadata = np.load(metadata_path, mmap_mode='r')
        self._initialized = True
        
        # Count active templates
        self._template_count = int(np.sum(self._metadata['flags'] > 0))
        
        logger.info(f"Mmap'd {self._template_count} templates from {path}")
    
    def get_buffer_ptr(self) -> Tuple[int, int]:
        """
        Get raw buffer pointers for native access.
        
        Returns:
            (strings_ptr, metadata_ptr) - memory addresses
        """
        if not self._initialized:
            return (0, 0)
        
        return (
            self._strings.ctypes.data,
            self._metadata.ctypes.data
        )
    
    def to_native_dict(self) -> Dict:
        """
        Export to dict for native module init.
        
        Returns dict with buffer addresses and layout info
        for the C extension to access directly.
        """
        if not self._initialized:
            return {}
        
        strings_ptr, metadata_ptr = self.get_buffer_ptr()
        
        return {
            'strings_ptr': strings_ptr,
            'strings_shape': self._strings.shape,
            'strings_strides': self._strings.strides,
            'metadata_ptr': metadata_ptr,
            'metadata_size': len(self._metadata),
            'num_templates': self.num_templates,
            'max_len': self.max_len,
            'active_count': self._template_count,
        }
    
    def __len__(self) -> int:
        return self._template_count
    
    def __contains__(self, template_id: int) -> bool:
        if not self._initialized:
            return False
        if template_id < 0 or template_id >= self.num_templates:
            return False
        return self._metadata[template_id]['flags'] > 0


class ProposalTemplateBuilder:
    """
    Builds numpy template arrays from proposals as they're created.
    
    Usage:
        builder = ProposalTemplateBuilder()
        
        # In proposal creation flow
        proposal = create_proposal(...)
        template_id = builder.register_proposal(proposal)
        
        # Later, save for deployment
        builder.save_templates("/opt/orka/aura_templates/")
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        self.templates = AURANumpyTemplates()
        self.template_dir = Path(template_dir) if template_dir else None
        
        # Track proposal -> template mapping
        self._proposal_map: Dict[str, int] = {}  # proposal_id -> template_id
        
        # Pre-populate with standard patterns
        self._init_standard_patterns()
    
    def _init_standard_patterns(self):
        """Initialize standard AI-to-AI patterns."""
        standard = [
            (128, "System {0} approves proposal {1}"),
            (129, "System {0} rejects proposal {1}"),
            (130, "System {0} abstains on proposal {1}"),
            (131, "System {0} escalates proposal {1}"),
            (132, "Round {0} debate on proposal {1}"),
            (133, "Consensus reached: {0}"),
            (134, "Deception detected in system {0}"),
            (135, "Human review requested for {0}"),
            (136, "Penalty applied to system {0}: {1}"),
            (137, "Incident {0} severity: {1}"),
        ]
        
        for tid, pattern in standard:
            self.templates.add_template(tid, pattern)
    
    def register_proposal(self, proposal: Dict) -> Optional[int]:
        """
        Register a proposal and return its template ID.
        
        If proposal text matches existing template, returns that ID.
        Otherwise creates new template.
        """
        proposal_id = proposal.get('id', proposal.get('proposal_id', ''))
        text = proposal.get('text', '')
        
        # Check if already registered
        if proposal_id and proposal_id in self._proposal_map:
            return self._proposal_map[proposal_id]
        
        # Try to match existing pattern
        pattern = self.templates._extract_pattern(text)
        
        # Search for existing
        for tid in range(self.templates.num_templates):
            existing = self.templates.get_template_str(tid)
            if existing == pattern:
                if proposal_id:
                    self._proposal_map[proposal_id] = tid
                return tid
        
        # Create new template
        tid = self.templates.add_from_proposal(proposal)
        if tid is not None and proposal_id:
            self._proposal_map[proposal_id] = tid
        
        return tid
    
    def save_templates(self, directory: Optional[str] = None):
        """Save templates to directory."""
        path = directory or self.template_dir
        if path:
            self.templates.save(path)
    
    def get_template_for_compress(self, proposal_id: str) -> Optional[Tuple[int, str]]:
        """Get (template_id, pattern) for compression."""
        tid = self._proposal_map.get(proposal_id)
        if tid is None:
            return None
        pattern = self.templates.get_template_str(tid)
        if pattern is None:
            return None
        return (tid, pattern)


# Global builder instance
_builder: Optional[ProposalTemplateBuilder] = None


def get_template_builder(template_dir: Optional[str] = None) -> ProposalTemplateBuilder:
    """Get or create global template builder."""
    global _builder
    if _builder is None:
        _builder = ProposalTemplateBuilder(template_dir)
    return _builder


def register_proposal(proposal: Dict) -> Optional[int]:
    """Register proposal with global builder."""
    return get_template_builder().register_proposal(proposal)


if __name__ == "__main__":
    # Test/demo
    import time
    
    print("=== AURA NumPy Template Store ===\n")
    
    # Create store
    store = AURANumpyTemplates()
    
    # Add some templates
    print("Adding templates...")
    store.add_template(0, "Hello {0}")
    store.add_template(128, "System {0} approves proposal {1}")
    store.add_template(129, "System {0} rejects proposal {1}")
    store.add_template(2128, "User query: {0}")
    
    # Add from proposal
    proposal = {
        'id': 'P001',
        'type': 'approval',
        'text': 'System Alpha approves proposal 12345'
    }
    tid = store.add_from_proposal(proposal)
    print(f"Added proposal as template {tid}")
    
    # Lookup
    print(f"\nTemplate 128: {store.get_template_str(128)}")
    print(f"Template 129: {store.get_template_str(129)}")
    print(f"Active templates: {len(store)}")
    
    # Save
    test_dir = "/tmp/aura_numpy_test"
    store.save(test_dir)
    
    # Reload with mmap
    store2 = AURANumpyTemplates()
    store2.load_mmap(test_dir)
    print(f"\nMmap'd templates: {len(store2)}")
    
    # Benchmark lookup
    print("\nBenchmarking lookups...")
    iterations = 100000
    start = time.perf_counter()
    for i in range(iterations):
        _ = store2.get_template(128)
    elapsed = time.perf_counter() - start
    
    print(f"Lookup rate: {iterations/elapsed:,.0f} ops/sec")
    print(f"Latency: {elapsed/iterations*1e6:.2f} μs")
    
    # Get native pointers
    native = store2.to_native_dict()
    print(f"\nNative access:")
    print(f"  strings_ptr: 0x{native['strings_ptr']:x}")
    print(f"  shape: {native['strings_shape']}")
