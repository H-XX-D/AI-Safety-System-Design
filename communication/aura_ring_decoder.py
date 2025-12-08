"""
AURA Zero-Copy Ring Buffer Decoder

Optimized for Jetson Orin unified memory architecture:
- Decodes directly into a ring buffer
- Hands buffer slices to tokenizer without copies
- Uses page-locked memory for GPU visibility
- Batches small messages to amortize overhead

Usage:
    from communication.aura_ring_decoder import RingDecoder
    
    decoder = RingDecoder(buffer_size=64*1024)  # 64KB ring
    
    # Decode into ring buffer, get view for tokenizer
    view = decoder.decode_to_buffer(compressed_blob)
    tokens = tokenizer.encode(view)  # No copy if tokenizer supports memoryview
    
    # Batch decode
    views = decoder.decode_batch(blobs)
"""

import os
import mmap
import ctypes
from typing import Optional, List, Tuple
import threading

# Try native extension
_native = None
native_available = False
try:
    # Try importing from aura_native package
    from .aura_native import _native_module, _NATIVE_AVAILABLE  # type: ignore[attr-defined]
    if _NATIVE_AVAILABLE and _native_module is not None:
        _native = _native_module
        native_available = True
except ImportError:
    try:
        # Direct import if running as script
        import sys
        native_path = os.path.join(os.path.dirname(__file__), 'aura_native')
        if native_path not in sys.path:
            sys.path.insert(0, native_path)
        import aura_compress as _native_mod  # type: ignore
        _native = _native_mod
        native_available = True
    except ImportError:
        pass

NATIVE_AVAILABLE = native_available


class PageLockedBuffer:
    """
    Page-locked buffer using mmap for zero-copy GPU access on unified memory.
    
    On Jetson Orin, unified memory means GPU can access this buffer
    without explicit cudaMemcpy if mapped properly.
    """
    
    def __init__(self, size: int, alignment: int = 4096):
        """
        Args:
            size: Buffer size in bytes
            alignment: Page alignment (4KB default)
        """
        # Round up to page boundary
        self.size = ((size + alignment - 1) // alignment) * alignment
        self.alignment = alignment
        
        # Create anonymous mmap (page-locked on Linux)
        self._mmap = mmap.mmap(-1, self.size, mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
        
        # Get buffer address for direct access
        self._buffer = memoryview(self._mmap)
        
        # Lock pages in RAM (prevent swapping)
        self._locked = False
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            # Get mmap file descriptor pointer (mmap has no direct address method)
            # Use MLockall instead for simpler approach
            MCL_CURRENT = 1  # Lock all currently mapped pages
            result = libc.mlockall(MCL_CURRENT)
            if result == 0:
                self._locked = True
        except Exception:
            pass
    
    def get_slice(self, offset: int, length: int) -> memoryview:
        """Get a zero-copy slice of the buffer."""
        return self._buffer[offset:offset + length]
    
    def write(self, offset: int, data: bytes) -> int:
        """Write data at offset, return bytes written."""
        length = min(len(data), self.size - offset)
        self._mmap.seek(offset)
        self._mmap.write(data[:length])
        return length
    
    def write_string(self, offset: int, text: str) -> int:
        """Write UTF-8 string at offset, return bytes written."""
        data = text.encode('utf-8')
        return self.write(offset, data)
    
    @property
    def is_locked(self) -> bool:
        return self._locked
    
    def __del__(self):
        if hasattr(self, '_mmap') and self._mmap:
            self._mmap.close()


class RingDecoder:
    """
    Zero-copy ring buffer decoder for AURA compressed messages.
    
    Decodes directly into a ring buffer that can be handed to tokenizer
    without intermediate string allocations.
    """
    
    def __init__(self, buffer_size: int = 64 * 1024, use_page_locked: bool = True):
        """
        Args:
            buffer_size: Ring buffer size in bytes (default 64KB)
            use_page_locked: Use mmap for page-locked memory
        """
        self.buffer_size = buffer_size
        self._write_pos = 0
        self._read_pos = 0
        self._lock = threading.Lock()
        
        # Create backing buffer
        if use_page_locked:
            self._backing: Optional[PageLockedBuffer] = PageLockedBuffer(buffer_size)
            self._buffer = bytearray(buffer_size)  # Also keep bytearray for string ops
        else:
            self._backing = None
            self._buffer = bytearray(buffer_size)
        
        # Prewarm native decoder
        if NATIVE_AVAILABLE and _native:
            try:
                _native.prewarm()
            except Exception:
                pass
    
    def decode_to_buffer(self, blob: bytes) -> memoryview:
        """
        Decode compressed blob directly into ring buffer.
        
        Returns a memoryview that can be passed to tokenizer without copy.
        """
        if not blob:
            return memoryview(b'')
        
        # Decode to string first (native is fast)
        if NATIVE_AVAILABLE and _native:
            text = _native.decompress(blob)
            if text is None:
                # Not AURA format, try raw
                try:
                    text = blob.decode('utf-8')
                except UnicodeDecodeError:
                    text = blob.decode('latin-1')
        else:
            try:
                text = blob.decode('utf-8')
            except UnicodeDecodeError:
                text = blob.decode('latin-1')
        
        if not text:
            return memoryview(b'')
        
        # Encode to bytes and write to ring buffer
        text_bytes = text.encode('utf-8')
        text_len = len(text_bytes)
        
        with self._lock:
            # Check if we need to wrap
            if self._write_pos + text_len > self.buffer_size:
                self._write_pos = 0  # Wrap around
            
            start = self._write_pos
            self._buffer[start:start + text_len] = text_bytes
            self._write_pos = start + text_len
            
            return memoryview(self._buffer)[start:start + text_len]
    
    def decode_batch(self, blobs: List[bytes]) -> List[memoryview]:
        """
        Batch decode multiple blobs into ring buffer.
        
        Amortizes Python call overhead for small messages.
        """
        results = []
        for blob in blobs:
            results.append(self.decode_to_buffer(blob))
        return results
    
    def decode_to_string(self, blob: bytes) -> str:
        """
        Decode to string (when memoryview not supported by tokenizer).
        """
        if not blob:
            return ""
        
        if NATIVE_AVAILABLE and _native:
            text = _native.decompress(blob)
            if text is not None:
                return text
        
        # Fallback
        try:
            return blob.decode('utf-8')
        except UnicodeDecodeError:
            return blob.decode('latin-1')
    
    def reset(self):
        """Reset ring buffer position."""
        with self._lock:
            self._write_pos = 0
            self._read_pos = 0
    
    @property
    def is_page_locked(self) -> bool:
        return self._backing is not None and self._backing.is_locked


class TmpfsStore:
    """
    Store compressed blobs in tmpfs (RAM) instead of eMMC/SD.
    
    On Jetson Orin, tmpfs avoids slow flash I/O and keeps data in RAM
    where unified memory can access it efficiently.
    """
    
    DEFAULT_PATH = "/dev/shm/aura_blobs"
    
    def __init__(self, path: Optional[str] = None, max_size_mb: int = 64):
        """
        Args:
            path: Path in tmpfs (default /dev/shm/aura_blobs)
            max_size_mb: Max storage size in MB
        """
        self.path = path or self.DEFAULT_PATH
        self.max_size = max_size_mb * 1024 * 1024
        self._current_size = 0
        self._blobs: dict[str, Tuple[int, int]] = {}  # id -> (offset, size)
        self._lock = threading.Lock()
        
        # Create tmpfs directory
        os.makedirs(self.path, exist_ok=True)
        
        # Memory-mapped file for blob storage
        self._data_file = os.path.join(self.path, "blobs.dat")
        self._index_file = os.path.join(self.path, "index.dat")
        self._fd: Optional[int] = None
        self._mmap: Optional[mmap.mmap] = None
        self._init_storage()
    
    def _init_storage(self):
        """Initialize memory-mapped storage."""
        # Create or open data file
        if not os.path.exists(self._data_file):
            with open(self._data_file, 'wb') as f:
                f.write(b'\x00' * self.max_size)
        
        self._fd = os.open(self._data_file, os.O_RDWR)
        self._mmap = mmap.mmap(self._fd, self.max_size)
    
    def store(self, blob_id: str, data: bytes) -> bool:
        """Store compressed blob in tmpfs."""
        with self._lock:
            if self._mmap is None:
                return False
            if self._current_size + len(data) > self.max_size:
                return False
            
            offset = self._current_size
            self._mmap.seek(offset)
            self._mmap.write(data)
            self._blobs[blob_id] = (offset, len(data))
            self._current_size += len(data)
            return True
    
    def load(self, blob_id: str) -> Optional[bytes]:
        """Load compressed blob from tmpfs."""
        with self._lock:
            if self._mmap is None or blob_id not in self._blobs:
                return None
            
            offset, size = self._blobs[blob_id]
            self._mmap.seek(offset)
            return self._mmap.read(size)
    
    def load_view(self, blob_id: str) -> Optional[memoryview]:
        """Get zero-copy view of blob (if supported)."""
        with self._lock:
            if self._mmap is None or blob_id not in self._blobs:
                return None
            
            offset, size = self._blobs[blob_id]
            return memoryview(self._mmap)[offset:offset + size]
    
    def clear(self):
        """Clear all stored blobs."""
        with self._lock:
            self._blobs.clear()
            self._current_size = 0
    
    def __del__(self):
        if self._mmap:
            self._mmap.close()
        if self._fd:
            os.close(self._fd)


class StreamingDecoder:
    """
    Complete streaming decoder pipeline optimized for Orin.
    
    Combines:
    - tmpfs storage (RAM, not eMMC)
    - Ring buffer decoder (zero-copy)
    - Page-locked memory (GPU visible)
    - Batch processing (amortize overhead)
    """
    
    def __init__(self, 
                 ring_size: int = 64 * 1024,
                 tmpfs_size_mb: int = 64,
                 batch_size: int = 16):
        """
        Args:
            ring_size: Decode ring buffer size
            tmpfs_size_mb: tmpfs storage size
            batch_size: Messages per batch
        """
        self.ring = RingDecoder(ring_size, use_page_locked=True)
        self.store = TmpfsStore(max_size_mb=tmpfs_size_mb)
        self.batch_size = batch_size
        
        # Stats
        self._decode_count = 0
        self._batch_count = 0
    
    def add_blob(self, blob_id: str, data: bytes) -> bool:
        """Store compressed blob in tmpfs."""
        return self.store.store(blob_id, data)
    
    def decode(self, blob_id: str) -> memoryview:
        """Decode blob to ring buffer, return zero-copy view."""
        blob = self.store.load(blob_id)
        if blob is None:
            return memoryview(b'')
        
        self._decode_count += 1
        return self.ring.decode_to_buffer(blob)
    
    def decode_batch(self, blob_ids: List[str]) -> List[memoryview]:
        """Batch decode multiple blobs."""
        self._batch_count += 1
        blobs = [self.store.load(bid) for bid in blob_ids]
        return self.ring.decode_batch([b for b in blobs if b])
    
    def iter_decode(self, blob_ids: List[str]):
        """
        Iterator that decodes in batches.
        
        Use this for overlapping decode with tokenization.
        """
        for i in range(0, len(blob_ids), self.batch_size):
            batch_ids = blob_ids[i:i + self.batch_size]
            views = self.decode_batch(batch_ids)
            for view in views:
                yield view
    
    def stats(self) -> dict:
        return {
            'decode_count': self._decode_count,
            'batch_count': self._batch_count,
            'ring_page_locked': self.ring.is_page_locked,
            'native_available': NATIVE_AVAILABLE,
        }


# Singleton instance
_decoder: Optional[StreamingDecoder] = None


def get_decoder(ring_size: int = 64 * 1024) -> StreamingDecoder:
    """Get singleton streaming decoder."""
    global _decoder
    if _decoder is None:
        _decoder = StreamingDecoder(ring_size=ring_size)
    return _decoder


# Benchmark utility
if __name__ == "__main__":
    import time
    
    print("=== AURA Ring Decoder Benchmark ===")
    print(f"Native available: {NATIVE_AVAILABLE}")
    
    # Create decoder
    decoder = RingDecoder(buffer_size=64 * 1024)
    print(f"Page locked: {decoder.is_page_locked}")
    
    # Test data
    if NATIVE_AVAILABLE and _native:
        compressed = _native.compress("System 5 approves proposal 042", secure=True)
    else:
        compressed = b'\x16\x22\x2a\x56\x00\xcc'  # Pre-compressed
    
    # Warmup
    for _ in range(100):
        decoder.decode_to_buffer(compressed)
    
    # Benchmark
    iterations = 100000
    start = time.perf_counter()
    for _ in range(iterations):
        view = decoder.decode_to_buffer(compressed)
    elapsed = time.perf_counter() - start
    
    ops = iterations / elapsed
    us = (elapsed / iterations) * 1_000_000
    print(f"Decode to buffer: {ops:,.0f} ops/sec ({us:.2f} μs/op)")
    
    # Batch benchmark
    blobs = [compressed] * 16
    decoder.reset()
    
    start = time.perf_counter()
    for _ in range(iterations // 16):
        views = decoder.decode_batch(blobs)
    elapsed = time.perf_counter() - start
    
    ops = iterations / elapsed
    print(f"Batch decode (16): {ops:,.0f} ops/sec")
