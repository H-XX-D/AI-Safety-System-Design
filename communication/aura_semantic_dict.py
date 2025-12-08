"""
Lightweight loader for mined n-gram dictionaries stored as NumPy buffers.

Expected NPZ keys:
  - phrases: uint8 blob of concatenated UTF-8 strings
  - offsets: uint32 offsets into phrases
  - lengths: uint16 lengths
  - counts: uint32 occurrence counts (optional for lookup)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class SemanticDictionary:
    def __init__(self, phrases: bytes, offsets: np.ndarray, lengths: np.ndarray):
        self._blob = phrases
        self._offsets = offsets
        self._lengths = lengths
        
        # Always build Python map for get_index (BINARY_SEMANTIC) support
        self._phrase_to_index: Dict[str, int] = {}
        self._max_phrase_len = 0
        for idx, (off, length) in enumerate(zip(offsets, lengths)):
            s = phrases[off : off + length].decode("utf-8", errors="ignore")
            self._phrase_to_index[s] = idx
            if len(s) > self._max_phrase_len:
                self._max_phrase_len = len(s)

        # Try to initialize native C extension for hybrid compression speed
        self._native_enabled = False
        try:
            from communication.aura_native import init_semantic_hybrid
            import ctypes
            
            # Ensure arrays are contiguous
            if not offsets.flags['C_CONTIGUOUS']: offsets = np.ascontiguousarray(offsets)
            if not lengths.flags['C_CONTIGUOUS']: lengths = np.ascontiguousarray(lengths)
            
            # Get pointers
            # phrases is bytes, use ctypes to get address
            phrases_ptr = ctypes.cast(ctypes.c_char_p(phrases), ctypes.c_void_p).value
            offsets_ptr = offsets.ctypes.data
            lengths_ptr = lengths.ctypes.data
            
            init_semantic_hybrid(
                phrases_ptr, 
                offsets_ptr, 
                lengths_ptr, 
                len(offsets), 
                self._max_phrase_len
            )
            self._native_enabled = True
            logger.info("Initialized native C semantic hybrid compressor")
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"Native semantic hybrid init failed ({e}), using Python fallback")
            self._native_enabled = False

    def get_index(self, phrase: str) -> Optional[int]:
        return self._phrase_to_index.get(phrase)

    def compress_hybrid(self, text: str) -> Optional[bytes]:
        """
        Compress text using dictionary substrings and literals.
        Format: 0xB2 [OpCode Data]...
        OpCodes:
          0x00 <len> <bytes>: Literal (len 1-127)
          0x80 <idx_hi> <idx_lo>: Token (idx 0-32767)
        """
        if not text:
            return None
            
        # Try native path first
        if self._native_enabled:
            try:
                from communication.aura_native import compress_hybrid
                res = compress_hybrid(text)
                if res is not None:
                    return res
            except Exception:
                pass
            
        output = bytearray([0xB2])
        i = 0
        n = len(text)
        literal_buffer: list[str] = []
        
        while i < n:
            # Greedy match: try longest possible phrase starting at i
            match_found = False
            # Limit lookahead to max_phrase_len
            limit = min(n, i + self._max_phrase_len)
            
            # Try lengths from max down to 2 (min phrase length)
            for end in range(limit, i + 1, -1):
                candidate = text[i:end]
                idx = self._phrase_to_index.get(candidate)
                if idx is not None:
                    # Found a match!
                    # Flush literals if any
                    if literal_buffer:
                        self._flush_literals(output, literal_buffer)
                        literal_buffer = []
                    
                    # Emit token (0x80 | high, low)
                    # Ensure index fits in 15 bits (0-32767)
                    if idx <= 0x7FFF:
                        output.append(0x80 | ((idx >> 8) & 0x7F))
                        output.append(idx & 0xFF)
                        i = end
                        match_found = True
                        break
            
            if not match_found:
                literal_buffer.append(text[i])
                i += 1
        
        # Flush remaining literals
        if literal_buffer:
            self._flush_literals(output, literal_buffer)
            
        return bytes(output)

    def _flush_literals(self, output: bytearray, buffer: list) -> None:
        """Helper to write literals to output."""
        # Chunk into blocks of 127
        s = "".join(buffer).encode("utf-8")
        # Note: simple encoding, might split multibyte chars if not careful?
        # Actually buffer is chars, so "".join(buffer) is safe string.
        # But encoding to bytes might increase length.
        # The format expects <len> <bytes>.
        # Let's just write chunks of bytes.
        
        pos = 0
        while pos < len(s):
            chunk = s[pos:pos+127]
            output.append(0x00) # Literal marker
            output.append(len(chunk))
            output.extend(chunk)
            pos += len(chunk)

    def decompress_hybrid(self, payload: bytes) -> Optional[str]:
        """Decompress hybrid semantic payload."""
        if not payload or payload[0] != 0xB2:
            return None
        
        parts = []
        i = 1
        n = len(payload)
        
        while i < n:
            op = payload[i]
            i += 1
            
            if op == 0x00: # Literal
                if i >= n: break
                length = payload[i]
                i += 1
                if i + length > n: break
                parts.append(payload[i:i+length].decode('utf-8', errors='ignore'))
                i += length
            elif (op & 0x80) == 0x80: # Token
                # High bit set. 
                # Format: 0x80 | (idx >> 8), idx & 0xFF
                if i >= n: break
                idx_hi = op & 0x7F
                idx_lo = payload[i]
                i += 1
                idx = (idx_hi << 8) | idx_lo
                phrase = self.get_phrase(idx)
                if phrase:
                    parts.append(phrase)
            else:
                # Unknown opcode
                return None
                
        return "".join(parts)

    def get_phrase(self, index: int) -> Optional[str]:
        if index < 0 or index >= len(self._offsets):
            return None
        off = int(self._offsets[index])
        length = int(self._lengths[index])
        return self._blob[off : off + length].decode("utf-8", errors="ignore")


_semantic_dict: Optional[SemanticDictionary] = None


def load_semantic_dictionary(path: Optional[Path] = None) -> Optional[SemanticDictionary]:
    """Load dictionary from NPZ if available."""
    global _semantic_dict
    if _semantic_dict is not None:
        return _semantic_dict

    if path is None:
        # Check environment variable first
        env_dir = os.environ.get("AURA_TEMPLATE_DIR")
        if env_dir:
            path = Path(env_dir) / "mined_ngrams.npz"
        else:
            path = Path("worm_usb_dir/aura_templates/mined_ngrams.npz")

    if not path.exists():
        # Fallback to local relative path if env var path failed or wasn't set
        if os.environ.get("AURA_TEMPLATE_DIR") and not path.exists():
             fallback = Path("worm_usb_dir/aura_templates/mined_ngrams.npz")
             if fallback.exists():
                 path = fallback
             else:
                 logger.info(f"Semantic dictionary not found at {path} or {fallback}")
                 return None
        else:
             logger.info(f"Semantic dictionary not found at {path}")
             return None

    try:
        data = np.load(path)
        phrases = data["phrases"].tobytes()
        offsets = data["offsets"]
        lengths = data["lengths"]
        _semantic_dict = SemanticDictionary(phrases, offsets, lengths)
        logger.info(f"Loaded semantic dictionary from {path} (entries={len(offsets)})")
    except Exception as exc:
        logger.warning(f"Failed to load semantic dictionary {path}: {exc}")
        _semantic_dict = None
    return _semantic_dict
