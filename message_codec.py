"""
Message codec for AI-to-AI transport with sizing-based selection and robust decode.

- Outbound: classify by size/structure and compress via bit-packed (secure preferred)
  or delegate to AURA compressor (ML disabled).
- Inbound: strict decode path supporting secure bit-packed (CRC verified), classic
  bit-packed, or AURA blob; includes simple per-sender sequence replay detection.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple, Set, Protocol, Deque
from collections import deque

from aura_compressor import classify_and_compress, create_compressor
from aura_bitpacked_extension import BitPackedCompressor
from aura_secure_transport import TransportContext, pack_secure, unpack_secure, IntegrityError, AuthenticationError, ReplayError
from config_loader import load_config

logger = logging.getLogger("message_codec")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Module-level state for replay detection on secure frames (0x16)
_last_sequence_by_sender: Dict[int, int] = {}
# Track seen nonces (sequence values) per sender for replay rejection beyond immediate equality.
# Sliding window approach would be better; here we keep a bounded set per sender and prune when large.
_seen_sequences_by_sender: Dict[int, Deque[int]] = {}
_MAX_SEQ_MEMORY_DEFAULT = 256  # default capacity per sender

# Lazy global AURA compressor for decode of AURA blobs
class _AuraDecoderProto(Protocol):
    def decompress(self, payload: bytes) -> str: ...

_AURA_DECODER: _AuraDecoderProto | None = None


def _get_aura_decoder() -> _AuraDecoderProto:
    global _AURA_DECODER
    if _AURA_DECODER is None:
        _AURA_DECODER = create_compressor(enable_aura=True)
    return _AURA_DECODER


def reset_replay_state() -> None:
    """Reset global replay tracking state (for tests or reinitialization)."""
    _last_sequence_by_sender.clear()
    _seen_sequences_by_sender.clear()


class MessageCodec:
    def __init__(self,
                 prefer_secure_bitpacked: bool = True,
                 min_compression_size: int = 18,
                 replay_capacity: int = _MAX_SEQ_MEMORY_DEFAULT) -> None:
        self.prefer_secure_bitpacked = prefer_secure_bitpacked
        self.min_compression_size = min_compression_size
        self.replay_capacity = max(8, replay_capacity)
        self.bitpacker = BitPackedCompressor()
        # Secure transport feature flag and context
        cfg = {}
        try:
            cfg = load_config() or {}
        except Exception:
            cfg = {}
        st_cfg = cfg.get('secure_transport', {}) if isinstance(cfg.get('secure_transport', {}), dict) else {}
        self.secure_enabled = bool(st_cfg.get('enabled', False))
        self.st_sender_id = int(st_cfg.get('sender_id', 0)) & 0xFF
        self.st_recipient_id = int(st_cfg.get('recipient_id', 0)) & 0xFF
        self.st_session_id = int(st_cfg.get('session_id', 0)) or 1
        key_hex = st_cfg.get('hmac_key_hex') or ''
        self.st_key = bytes.fromhex(key_hex) if isinstance(key_hex, str) and len(key_hex) >= 32 else b''
        # Optional fallback key for rotation on decode
        fb_hex = st_cfg.get('hmac_key_hex_fallback') or ''
        self.st_fallback_key = bytes.fromhex(fb_hex) if isinstance(fb_hex, str) and len(fb_hex) >= 32 else b''
        self.st_priv = st_cfg.get('ed25519_private_hex') if isinstance(st_cfg.get('ed25519_private_hex'), str) else None
        self.st_pub = st_cfg.get('ed25519_public_hex') if isinstance(st_cfg.get('ed25519_public_hex'), str) else None
        self._sequence_counter = 0

    def encode(self, text: str, **kwargs: Any) -> Tuple[bytes, str, Dict[str, Any]]:
        """Classify and compress the text per policy."""
        payload, method, meta = classify_and_compress(
            text,
            prefer_secure_bitpacked=self.prefer_secure_bitpacked,
            min_compression_size=self.min_compression_size,
            **kwargs,
        )
        # Optional secure framing for AURA/bitpacked payloads
        if self.secure_enabled and self.st_key:
            ctx = TransportContext(
                sender_id=self.st_sender_id,
                recipient_id=self.st_recipient_id,
                session_id=self.st_session_id,
                secret_key=self.st_key,
                ed25519_private_hex=self.st_priv,
                ed25519_public_hex=self.st_pub,
            )
            seq = self._sequence_counter
            self._sequence_counter = (self._sequence_counter + 1) & 0xFFFFFFFFFFFFFFFF
            framed = pack_secure(payload, ctx=ctx, sequence=seq)
            meta['secure_transport'] = True
            return framed, f"SECURE_{method}", meta
        logger.debug("encoded text", extra={
            'method': method,
            'original_size': len(text.encode('utf-8')),
            'compressed_size': len(payload),
            'reason': meta.get('reason')
        })
        return payload, method, meta

    def decode(self, payload: bytes) -> Tuple[str, Dict[str, Any]]:
        """Decode payload from secure/standard bit-packed or AURA blob.
        Returns (text, info) where info includes method, and replay/integrity flags.
        """
        info: Dict[str, Any] = {
            'method': None,
            'sequence_ok': None,
            'crc_ok': None,
            'replay_detected': None,
        }
        if not payload:
            raise ValueError("Empty payload")

        # Secure frame handling: detect by length and HMAC position (last 16 bytes); attempt unwrap first when enabled
        if self.secure_enabled and len(payload) >= (1 + 1 + 8 + 8 + 8 + 1 + 16):
            try:
                ctx = TransportContext(
                    sender_id=self.st_sender_id,
                    recipient_id=self.st_recipient_id,
                    session_id=self.st_session_id,
                    secret_key=self.st_key,
                    ed25519_public_hex=self.st_pub,
                )
                # Apply strict freshness and limited future skew tolerance
                inner, seq, ts = unpack_secure(payload, ctx=ctx, max_age_seconds=300, max_future_skew_seconds=15)
                payload = inner
                info['secure_transport'] = True
                info['sequence'] = seq
                info['timestamp'] = ts
            except IntegrityError:
                # Try fallback HMAC key for rotation
                if self.st_fallback_key:
                    fbctx = TransportContext(
                        sender_id=self.st_sender_id,
                        recipient_id=self.st_recipient_id,
                        session_id=self.st_session_id,
                        secret_key=self.st_fallback_key,
                        ed25519_public_hex=self.st_pub,
                    )
                    inner, seq, ts = unpack_secure(payload, ctx=fbctx, max_age_seconds=300, max_future_skew_seconds=15)
                    payload = inner
                    info['secure_transport'] = True
                    info['sequence'] = seq
                    info['timestamp'] = ts
                else:
                    info['secure_transport'] = False
            except (AuthenticationError, ReplayError):
                # Fall through to legacy decoders if secure unwrap fails
                info['secure_transport'] = False

        method_byte = payload[0]
        # Secure bit-packed
        if method_byte == self.bitpacker.SECURE_METHOD_BYTE and len(payload) == 6:
            text = self.bitpacker.decompress_secure(payload)
            info['method'] = 'BITPACKED_SECURE'
            if text is None:
                info['crc_ok'] = False
                raise ValueError("Invalid secure bit-packed frame (CRC or format)")
            info['crc_ok'] = True
            # Replay/sequence check
            system_ids = payload[3]
            from_sys = (system_ids >> 4) & 0xF
            seq = payload[4]
            last = _last_sequence_by_sender.get(from_sys)
            existing = _seen_sequences_by_sender.get(from_sys)
            if existing is None:
                dq = deque()
                _seen_sequences_by_sender[from_sys] = dq
            elif isinstance(existing, set):
                # Backward compatibility: normalize old set to deque
                dq = deque(existing)
                _seen_sequences_by_sender[from_sys] = dq
            else:
                dq = existing
            replay = (seq in dq)
            _last_sequence_by_sender[from_sys] = seq
            dq.append(seq)
            if len(dq) > self.replay_capacity:
                # Evict oldest
                dq.popleft()
            info['sequence_ok'] = (last is None) or (((last + 1) & 0xFF) == seq) or (last == seq)
            if replay:
                # Treat duplicate sequence as non-monotonicity-violating for compatibility
                info['sequence_ok'] = True
            info['replay_detected'] = replay
            if replay:
                info['method'] = 'BITPACKED_SECURE'
                # Mark replay explicitly; upstream can decide rejection
                return text, info
            return text, info

        # Classic bit-packed
        if method_byte == self.bitpacker.METHOD_BYTE and len(payload) == 4:
            text = self.bitpacker.decompress(payload)
            info['method'] = 'BITPACKED'
            if text is None:
                raise ValueError("Invalid classic bit-packed frame")
            return text, info

        # Otherwise assume AURA blob
        aura = _get_aura_decoder()
        text = aura.decompress(payload)
        info['method'] = 'AURA'
        return text, info
