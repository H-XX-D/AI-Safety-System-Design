"""
AURA Context Streaming - Just-in-Time Decompression for LLM Context

Keeps context compressed off-GPU and decodes just-in-time for tokenization.

Architecture:
1. Store context as compressed AURA blobs (4-16 KB slices)
2. Stream and decode only needed slices on CPU
3. Pipe directly to tokenizer without materializing full text
4. Send only token IDs to GPU

Usage:
    from communication.aura_context_stream import ContextStream, ContextStore
    
    # Store compressed context
    store = ContextStore()
    store.add_chunk("System 5 approves proposal 042", chunk_id="ctx_001")
    
    # Stream decompress → tokenize → GPU
    stream = ContextStream(store, tokenizer, max_tokens=4096)
    for token_ids in stream.iter_tokens(["ctx_001", "ctx_002"]):
        # token_ids ready for GPU
        model.forward(token_ids)
"""

import os
import mmap
import struct
import threading
from dataclasses import dataclass, field
from typing import Optional, Iterator, Callable, List, Dict, Any
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

# Try native extension first
try:
    from .aura_native import aura_compress as _native
    NATIVE_AVAILABLE = True
except ImportError:
    _native = None
    NATIVE_AVAILABLE = False

# Fallback to Python
from .aura_bitpacked_extension import BitPackedCompressor


@dataclass
class CompressedChunk:
    """A compressed context chunk with metadata."""
    chunk_id: str
    data: bytes
    offset: int = 0  # Offset in backing store
    size: int = 0    # Compressed size
    original_len: int = 0  # Original text length
    
    def __post_init__(self):
        self.size = len(self.data)


@dataclass 
class StreamConfig:
    """Configuration for context streaming."""
    max_slice_size: int = 16 * 1024      # 16 KB max per slice
    batch_size: int = 8                   # Decompress N slices at once
    max_context_tokens: int = 4096        # Rolling window limit
    prealloc_buffer_size: int = 64 * 1024 # 64 KB preallocated decode buffer
    evict_after_tokenize: bool = True     # Free decoded text after tokenizing


class AURADecoder:
    """
    Singleton AURA decoder with preallocated buffers.
    
    Thread-safe, reuses buffers to avoid per-call allocations.
    """
    _instance: Optional['AURADecoder'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        """Initialize decoder with preallocated resources."""
        self._py_decoder = BitPackedCompressor()
        self._decode_buffer = bytearray(64 * 1024)  # 64 KB buffer
        self._native = _native
        self._prewarmed = False
        
        # Prewarm if native available
        if self._native:
            try:
                self._native.prewarm()
                self._prewarmed = True
                logger.info("AURA decoder prewarmed (native)")
            except Exception as e:
                logger.warning(f"Native prewarm failed: {e}")
    
    def decompress_chunk(self, blob: bytes) -> str:
        """
        Decompress a single AURA blob to string.
        
        Fast path uses native C extension if available.
        """
        if not blob:
            return ""
        
        # Try native decompress first (2.6M ops/sec)
        if self._native:
            try:
                result = self._native.decompress(blob)
                if result is not None:
                    return result
            except Exception:
                pass
        
        # Check method byte for Python fallback
        method = blob[0] if blob else 0
        
        if method == 0x06:  # METHOD_BITPACKED (4 bytes)
            return self._py_decoder.decompress(blob) or ""
        elif method == 0x16:  # METHOD_BITPACKED_SECURE (6 bytes)
            return self._py_decoder.decompress_secure(blob) or ""
        else:
            # Not AURA format - treat as raw text
            try:
                return blob.decode('utf-8')
            except UnicodeDecodeError:
                return blob.decode('latin-1')
    
    def decompress_batch(self, blobs: List[bytes]) -> List[str]:
        """
        Batch decompress multiple blobs.
        
        Amortizes Python call overhead.
        """
        results = []
        for blob in blobs:
            results.append(self.decompress_chunk(blob))
        return results
    
    def is_native(self) -> bool:
        return self._native is not None and self._prewarmed


class ContextStore:
    """
    Compressed context storage with chunk management.
    
    Stores context as AURA-compressed blobs with offsets/IDs.
    Supports disk-backed and memory-mapped storage.
    """
    
    def __init__(self, backing_file: Optional[str] = None, 
                 max_memory_mb: int = 256):
        """
        Args:
            backing_file: Optional file path for disk-backed storage
            max_memory_mb: Max RAM for in-memory chunks before eviction
        """
        self._chunks: OrderedDict[str, CompressedChunk] = OrderedDict()
        self._backing_file = backing_file
        self._max_memory = max_memory_mb * 1024 * 1024
        self._current_memory = 0
        self._encoder = BitPackedCompressor()
        self._mmap: Optional[mmap.mmap] = None
        self._lock = threading.RLock()
        
        if backing_file and os.path.exists(backing_file):
            self._load_from_disk()
    
    def add_chunk(self, text: str, chunk_id: Optional[str] = None) -> str:
        """
        Add text as compressed chunk.
        
        Returns chunk_id for later retrieval.
        """
        if chunk_id is None:
            chunk_id = f"ctx_{len(self._chunks):06d}"
        
        # Try AURA compression first
        compressed = self._encoder.compress_secure(text)
        if compressed is None:
            # Fall back to raw UTF-8
            compressed = text.encode('utf-8')
        
        chunk = CompressedChunk(
            chunk_id=chunk_id,
            data=compressed,
            original_len=len(text)
        )
        
        with self._lock:
            # Evict if over memory limit
            while self._current_memory + chunk.size > self._max_memory and self._chunks:
                evicted_id, evicted = self._chunks.popitem(last=False)
                self._current_memory -= evicted.size
                logger.debug(f"Evicted chunk {evicted_id}")
            
            self._chunks[chunk_id] = chunk
            self._current_memory += chunk.size
        
        return chunk_id
    
    def add_chunks_batch(self, texts: List[str], 
                         chunk_ids: Optional[List[str]] = None) -> List[str]:
        """Add multiple chunks efficiently."""
        if chunk_ids is None:
            base = len(self._chunks)
            chunk_ids = [f"ctx_{base + i:06d}" for i in range(len(texts))]
        
        result_ids = []
        for text, cid in zip(texts, chunk_ids):
            result_ids.append(self.add_chunk(text, cid))
        return result_ids
    
    def get_chunk(self, chunk_id: str) -> Optional[CompressedChunk]:
        """Get compressed chunk by ID."""
        with self._lock:
            chunk = self._chunks.get(chunk_id)
            if chunk:
                # Move to end (LRU)
                self._chunks.move_to_end(chunk_id)
            return chunk
    
    def get_chunks(self, chunk_ids: List[str]) -> List[CompressedChunk]:
        """Get multiple chunks by IDs."""
        return [c for c in (self.get_chunk(cid) for cid in chunk_ids) if c]
    
    def iter_chunk_data(self, chunk_ids: List[str]) -> Iterator[bytes]:
        """Iterate over raw compressed data for given chunk IDs."""
        for chunk_id in chunk_ids:
            chunk = self.get_chunk(chunk_id)
            if chunk:
                yield chunk.data
    
    def stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with self._lock:
            total_original = sum(c.original_len for c in self._chunks.values())
            total_compressed = sum(c.size for c in self._chunks.values())
            return {
                'chunks': len(self._chunks),
                'memory_bytes': self._current_memory,
                'memory_mb': self._current_memory / (1024 * 1024),
                'original_bytes': total_original,
                'compressed_bytes': total_compressed,
                'compression_ratio': total_original / total_compressed if total_compressed else 0,
            }
    
    def _load_from_disk(self):
        """Load chunks from disk-backed file."""
        # TODO: Implement memory-mapped chunk loading
        pass
    
    def save_to_disk(self, path: Optional[str] = None):
        """Save all chunks to disk."""
        path = path or self._backing_file
        if not path:
            raise ValueError("No backing file specified")
        
        with open(path, 'wb') as f:
            # Header: magic, version, chunk_count
            f.write(b'AURA')
            f.write(struct.pack('<HI', 1, len(self._chunks)))
            
            # Index: chunk_id_len, chunk_id, offset, size, original_len
            offset = 0
            index_data = []
            for chunk in self._chunks.values():
                chunk_id_bytes = chunk.chunk_id.encode('utf-8')
                index_data.append((chunk_id_bytes, offset, chunk.size, chunk.original_len))
                offset += chunk.size
            
            # Write index
            for chunk_id_bytes, off, size, orig_len in index_data:
                f.write(struct.pack('<H', len(chunk_id_bytes)))
                f.write(chunk_id_bytes)
                f.write(struct.pack('<III', off, size, orig_len))
            
            # Write data
            for chunk in self._chunks.values():
                f.write(chunk.data)


class ContextStream:
    """
    Streaming context decompressor with tokenizer integration.
    
    Decompresses AURA blobs just-in-time and pipes to tokenizer.
    Only token IDs are sent to GPU; all text stays on CPU.
    """
    
    def __init__(self, store: ContextStore, 
                 tokenizer: Optional[Any] = None,
                 config: Optional[StreamConfig] = None):
        """
        Args:
            store: ContextStore with compressed chunks
            tokenizer: Tokenizer with encode() method (HuggingFace-style)
            config: StreamConfig for tuning
        """
        self.store = store
        self.tokenizer = tokenizer
        self.config = config or StreamConfig()
        self._decoder = AURADecoder()
        self._token_buffer: List[int] = []
        self._tokens_emitted = 0
    
    def iter_tokens(self, chunk_ids: List[str], 
                    add_special_tokens: bool = True) -> Iterator[List[int]]:
        """
        Iterate over token batches from compressed chunks.
        
        Decompresses and tokenizes incrementally, yielding token batches.
        Respects max_context_tokens limit.
        
        Args:
            chunk_ids: IDs of chunks to decompress and tokenize
            add_special_tokens: Add BOS/EOS tokens
            
        Yields:
            Lists of token IDs ready for GPU
        """
        if self.tokenizer is None:
            raise ValueError("Tokenizer required for iter_tokens()")
        
        self._tokens_emitted = 0
        remaining_tokens = self.config.max_context_tokens
        
        # Process in batches
        batch_size = self.config.batch_size
        for i in range(0, len(chunk_ids), batch_size):
            batch_ids = chunk_ids[i:i + batch_size]
            
            # Get compressed blobs
            blobs = list(self.store.iter_chunk_data(batch_ids))
            
            # Batch decompress on CPU
            texts = self._decoder.decompress_batch(blobs)
            
            # Tokenize and yield
            for text in texts:
                if not text or remaining_tokens <= 0:
                    continue
                
                # Tokenize this slice
                tokens = self.tokenizer.encode(
                    text, 
                    add_special_tokens=add_special_tokens and self._tokens_emitted == 0
                )
                
                # Respect token limit
                if len(tokens) > remaining_tokens:
                    tokens = tokens[:remaining_tokens]
                
                remaining_tokens -= len(tokens)
                self._tokens_emitted += len(tokens)
                
                yield tokens
                
                # Evict decoded text if configured
                if self.config.evict_after_tokenize:
                    del text
    
    def decompress_to_tokens(self, chunk_ids: List[str]) -> List[int]:
        """
        Decompress all chunks and return flat token list.
        
        For cases where you need all tokens at once.
        """
        all_tokens = []
        for tokens in self.iter_tokens(chunk_ids):
            all_tokens.extend(tokens)
            if len(all_tokens) >= self.config.max_context_tokens:
                break
        return all_tokens[:self.config.max_context_tokens]
    
    def iter_text(self, chunk_ids: List[str]) -> Iterator[str]:
        """
        Iterate over decompressed text chunks.
        
        For cases where you need text, not tokens.
        """
        batch_size = self.config.batch_size
        for i in range(0, len(chunk_ids), batch_size):
            batch_ids = chunk_ids[i:i + batch_size]
            blobs = list(self.store.iter_chunk_data(batch_ids))
            texts = self._decoder.decompress_batch(blobs)
            for text in texts:
                if text:
                    yield text
    
    def decompress_chunk(self, blob: bytes) -> str:
        """Decompress a single blob (convenience method)."""
        return self._decoder.decompress_chunk(blob)


# Convenience functions
_default_store: Optional[ContextStore] = None
_default_decoder: Optional[AURADecoder] = None


def get_decoder() -> AURADecoder:
    """Get singleton decoder instance."""
    global _default_decoder
    if _default_decoder is None:
        _default_decoder = AURADecoder()
    return _default_decoder


def decompress_chunk(blob: bytes) -> str:
    """Decompress a single AURA blob to string."""
    return get_decoder().decompress_chunk(blob)


def decompress_chunks(blobs: List[bytes]) -> List[str]:
    """Batch decompress multiple blobs."""
    return get_decoder().decompress_batch(blobs)


def create_context_store(max_memory_mb: int = 256) -> ContextStore:
    """Create a new context store."""
    return ContextStore(max_memory_mb=max_memory_mb)


# Example usage
if __name__ == "__main__":
    import time
    
    # Create store and add some context
    store = ContextStore(max_memory_mb=64)
    
    # Simulate adding conversation context
    messages = [
        "System 5 approves proposal 042 with high confidence",
        "System 3 rejects proposal 100",
        "System 1 reviews proposal 255",
        "System 7 approves proposal 001",
    ]
    
    chunk_ids = store.add_chunks_batch(messages)
    print(f"Added {len(chunk_ids)} chunks")
    print(f"Stats: {store.stats()}")
    
    # Stream decompress
    stream = ContextStream(store, tokenizer=None)
    
    # Just decompress (no tokenizer)
    print("\nDecompressed:")
    for text in stream.iter_text(chunk_ids):
        print(f"  {text}")
    
    # Benchmark
    iterations = 10000
    blobs = [store.get_chunk(cid).data for cid in chunk_ids]
    decoder = get_decoder()
    
    start = time.perf_counter()
    for _ in range(iterations):
        for blob in blobs:
            decoder.decompress_chunk(blob)
    elapsed = time.perf_counter() - start
    
    ops = iterations * len(blobs) / elapsed
    print(f"\nDecompress: {ops:,.0f} ops/sec")
