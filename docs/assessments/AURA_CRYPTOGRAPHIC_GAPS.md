# AURA Cryptographic Gaps Analysis

## The Question

**What cryptographic "hardening" actually covers that incentives do not?**

## Gap Analysis

| Property | Incentive System | Crypto Primitive | Gap Today |
|----------|-----------------|------------------|-----------|
| **Integrity** (bit flip/tamper detect) | Detected only if semantic diff noticed | CRC / MAC / signature | Silent corruption not guaranteed caught if still parseable |
| **Authenticity** (sender cannot be forged) | Relies on identity attribution + audit logs | HMAC / signature | Log forgery or injected frame not inherently blocked |
| **Replay protection** | Economic logs may notice duplicates later | Nonce / sequence + MAC | Reactive vs proactive blocking |
| **Channel substitution / MITM** | Depends on auditors noticing anomalies | MAC + context binding | No cryptographic binding to session/context |
| **Covert data injection resistance** | Relies on template discipline & review | Format-level constraints + hashing | Some residual side-channel capacity (timing, ordering) |

## Detailed Gap Analysis

### Gap 1: Silent Corruption (Integrity)

**Current State:**
```python
# AURA compression without integrity protection
compressed = compressor.compress("System 1 approves proposal 042")
# compressed = b'\x06\x22\x2a\x16'

# Bit flip during transmission
corrupted = b'\x06\x22\x2b\x16'  # 0x2a → 0x2b (proposal 42 → 43)

# Decompression succeeds!
decompressed = compressor.decompress(corrupted)
# "System 1 approves proposal 043"  ← WRONG PROPOSAL!
```

**Problem:**
- Corruption is semantically valid (proposal 43 exists)
- No detection until human notices wrong proposal approved
- **Reactive detection, not proactive prevention**

**Cryptographic Solution:**
```python
# Add HMAC to detect tampering
import hmac
import hashlib

def compress_with_integrity(text, secret_key):
    compressed = compressor.compress(text)
    mac = hmac.new(secret_key, compressed, hashlib.sha256).digest()
    return compressed + mac[:16]  # Append 16-byte MAC

def decompress_with_verification(data, secret_key):
    compressed = data[:-16]
    received_mac = data[-16:]

    # Verify integrity BEFORE decompression
    expected_mac = hmac.new(secret_key, compressed, hashlib.sha256).digest()[:16]

    if not hmac.compare_digest(received_mac, expected_mac):
        raise IntegrityError("Message tampered!")

    return compressor.decompress(compressed)
```

**Result:**
- Bit flips detected immediately (before decompression)
- Cannot approve wrong proposal due to corruption
- **Proactive prevention**

### Gap 2: Sender Forgery (Authenticity)

**Current State:**
```python
# Malicious AI System 5 forges message from System 1
forged_message = compressor.compress("System 1 approves proposal 666")

# No cryptographic proof of sender
# Relies on network-level attribution (IP address, session ID)

# If attacker controls network, can inject forged message
# Audit logs show "System 1" approved, but it was actually System 5
```

**Problem:**
- No cryptographic binding of message to sender
- Log forgery possible if attacker has database access
- **Trust depends on infrastructure security**

**Cryptographic Solution:**
```python
# Digital signature proves sender identity
from cryptography.hazmat.primitives.asymmetric import ed25519

class SignedMessage:
    def __init__(self, sender_id, private_key):
        self.sender_id = sender_id
        self.private_key = private_key

    def sign_and_compress(self, text):
        # Compress
        compressed = compressor.compress(text)

        # Create signature
        signature = self.private_key.sign(
            self.sender_id.to_bytes(1, 'big') + compressed
        )

        # Format: [sender_id][signature][compressed_data]
        return bytes([self.sender_id]) + signature + compressed

    def verify_and_decompress(self, data, sender_public_key):
        sender_id = data[0]
        signature = data[1:65]  # Ed25519 signature is 64 bytes
        compressed = data[65:]

        # Verify signature BEFORE decompression
        try:
            sender_public_key.verify(
                signature,
                bytes([sender_id]) + compressed
            )
        except Exception:
            raise AuthenticationError("Invalid signature - sender forged!")

        return compressor.decompress(compressed)
```

**Result:**
- Only System 1 can create messages attributed to System 1
- Forgery detected cryptographically (not just in audit)
- **Proactive prevention**

### Gap 3: Replay Attacks

**Current State:**
```python
# System 1 approves proposal 042 at timestamp T1
msg1 = "System 1 approves proposal 042"
compressed1 = compressor.compress(msg1)

# ... later, proposal 042 is modified ...

# Attacker replays old approval message at timestamp T2
# System thinks proposal 042 (new version) is approved
# But approval was for old version!
```

**Problem:**
- No cryptographic freshness guarantee
- Economic logs may notice duplicate later
- **Reactive detection, not proactive prevention**

**Cryptographic Solution:**
```python
# Add nonce/sequence number + timestamp
import time

class ReplayProtectedMessage:
    def __init__(self):
        self.sequence_counter = 0

    def compress_with_nonce(self, text, session_id):
        compressed = compressor.compress(text)

        # Add metadata
        timestamp = int(time.time())
        nonce = self.sequence_counter
        self.sequence_counter += 1

        # Format: [nonce][timestamp][session_id][compressed]
        header = struct.pack('>QQI', nonce, timestamp, session_id)

        # Sign everything
        mac = hmac.new(secret_key, header + compressed, hashlib.sha256).digest()[:16]

        return header + compressed + mac

    def verify_freshness(self, data, expected_nonce, max_age_seconds=60):
        nonce, timestamp, session_id = struct.unpack('>QQI', data[:20])

        # Check nonce (must be strictly increasing)
        if nonce != expected_nonce:
            raise ReplayError("Nonce mismatch - replay detected!")

        # Check timestamp (must be recent)
        age = time.time() - timestamp
        if age > max_age_seconds:
            raise ReplayError("Message too old - possible replay!")

        # Verify MAC
        # ... (as above)
```

**Result:**
- Replay detected immediately (before processing)
- Old approvals cannot be reused
- **Proactive prevention**

### Gap 4: Man-in-the-Middle / Channel Substitution

**Current State:**
```python
# System 1 sends approval to System 6 (human)
msg = "System 1 approves proposal 042"
compressed = compressor.compress(msg)

# Attacker intercepts and modifies destination
# Message now goes to System 5 (malicious AI) instead of System 6 (human)

# No cryptographic binding to intended recipient
# Relies on network routing (can be subverted)
```

**Problem:**
- No cryptographic proof of intended recipient
- Channel substitution not detected cryptographically
- **Depends on network-level security**

**Cryptographic Solution:**
```python
# Bind message to sender + recipient + context
def compress_with_context(text, sender_id, recipient_id, session_id, secret_key):
    compressed = compressor.compress(text)

    # Create context binding
    context = struct.pack('>BBQ', sender_id, recipient_id, session_id)

    # MAC covers both message and context
    mac = hmac.new(
        secret_key,
        context + compressed,
        hashlib.sha256
    ).digest()[:16]

    return context + compressed + mac

def verify_context(data, expected_sender, expected_recipient, expected_session, secret_key):
    context = data[:10]
    compressed = data[10:-16]
    mac = data[-16:]

    # Verify MAC
    expected_mac = hmac.new(secret_key, context + compressed, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(mac, expected_mac):
        raise IntegrityError("MAC verification failed!")

    # Verify context
    sender_id, recipient_id, session_id = struct.unpack('>BBQ', context)

    if sender_id != expected_sender:
        raise AuthenticationError("Sender mismatch - MITM detected!")

    if recipient_id != expected_recipient:
        raise ChannelSubstitutionError("Recipient mismatch - message redirected!")

    if session_id != expected_session:
        raise SessionError("Session mismatch - replay from old session!")

    return compressor.decompress(compressed)
```

**Result:**
- MITM detected immediately
- Channel substitution detected immediately
- **Proactive prevention**

### Gap 5: Covert Channels (Timing, Ordering)

**Current State:**
```python
# Bit-packed format accounts for all bits
compressed = b'\x06\x22\x2a\x16'

# But timing and ordering are not controlled:
# - Message sent at 10:42:17.123456 vs 10:42:17.987654
# - Message is 3rd in queue vs 7th in queue
# - Message compressed in 2ms vs 5ms

# These could encode hidden information:
# - Fast compression = "proceed"
# - Slow compression = "abort"
# - 3rd in queue = "low priority"
# - 7th in queue = "high priority"
```

**Problem:**
- Side channels exist in timing and ordering
- Not covered by template/bit-field accounting
- **Residual covert channel capacity**

**Cryptographic Solution:**
```python
# Normalize timing and ordering
import random

def compress_with_timing_normalization(text):
    compressed = compressor.compress(text)

    # Add deterministic padding (removes timing info)
    padding_size = 64 - (len(compressed) % 64)
    padding = b'\x00' * padding_size

    # Add random delay (normalizes compression time)
    # Note: Use deterministic RNG seeded from message content
    seed = hashlib.sha256(compressed).digest()
    rng = random.Random(seed)
    delay_ms = rng.randint(10, 50)  # 10-50ms random delay

    time.sleep(delay_ms / 1000.0)

    return compressed + padding

# In the queue, shuffle messages (removes ordering info)
def process_message_queue(queue):
    # Batch messages
    batch = queue.get_batch(max_size=10, max_wait_seconds=1)

    # Shuffle using deterministic seed (prevents ordering covert channel)
    seed = hashlib.sha256(b''.join(batch)).digest()
    rng = random.Random(seed)
    rng.shuffle(batch)

    # Process in shuffled order
    for msg in batch:
        process_message(msg)
```

**Result:**
- Timing covert channel eliminated (deterministic delay)
- Ordering covert channel eliminated (deterministic shuffle)
- **Proactive prevention**

## Summary of Gaps

| Gap | Current Detection | Crypto Detection | Impact |
|-----|------------------|------------------|--------|
| **Silent corruption** | Reactive (audit) | Proactive (MAC) | **HIGH** - Wrong proposals could be approved |
| **Sender forgery** | Reactive (audit) | Proactive (signature) | **HIGH** - Malicious AI could frame others |
| **Replay attacks** | Reactive (audit) | Proactive (nonce) | **MEDIUM** - Old approvals reused |
| **MITM/channel substitution** | Reactive (audit) | Proactive (context binding) | **MEDIUM** - Messages redirected |
| **Timing/ordering covert channels** | None | Normalization | **LOW** - Limited bandwidth |

## Recommended Hardening

### Priority 1: Integrity Protection (HIGH IMPACT)

**Add HMAC to all compressed messages:**

```python
# In aura_compression/compressor_refactored.py

class ProductionHybridCompressor:
    def __init__(self, ..., enable_integrity=True, hmac_key=None):
        self.enable_integrity = enable_integrity
        self.hmac_key = hmac_key or os.urandom(32)  # 256-bit key

    def compress(self, text, ...):
        compressed, method, metadata = self._compress_internal(text, ...)

        if self.enable_integrity:
            # Add HMAC
            mac = hmac.new(self.hmac_key, compressed, hashlib.sha256).digest()[:16]
            compressed = compressed + mac
            metadata['integrity_protected'] = True

        return compressed, method, metadata

    def decompress(self, payload: bytes) -> str:
        if self.enable_integrity:
            # Verify HMAC before decompression
            data = payload[:-16]
            received_mac = payload[-16:]

            expected_mac = hmac.new(self.hmac_key, data, hashlib.sha256).digest()[:16]

            if not hmac.compare_digest(received_mac, expected_mac):
                raise IntegrityError("Message integrity check failed - possible tampering!")

            payload = data

        return self._decompress_internal(payload)
```

**Overhead:** 16 bytes per message (MAC)

### Priority 2: Sender Authentication (HIGH IMPACT)

**Add digital signatures:**

```python
from cryptography.hazmat.primitives.asymmetric import ed25519

class AuthenticatedCompressor:
    def __init__(self, system_id, private_key, public_keys_registry):
        self.system_id = system_id
        self.private_key = private_key  # Ed25519 private key
        self.public_keys = public_keys_registry  # {system_id: public_key}

    def compress_and_sign(self, text):
        compressed, method, metadata = compressor.compress(text)

        # Create signature
        message_to_sign = bytes([self.system_id]) + compressed
        signature = self.private_key.sign(message_to_sign)

        # Format: [system_id][signature][compressed]
        authenticated = bytes([self.system_id]) + signature + compressed

        metadata['authenticated'] = True
        return authenticated, method, metadata

    def verify_and_decompress(self, authenticated_payload):
        sender_id = authenticated_payload[0]
        signature = authenticated_payload[1:65]
        compressed = authenticated_payload[65:]

        # Get sender's public key
        public_key = self.public_keys.get(sender_id)
        if not public_key:
            raise AuthenticationError(f"Unknown sender: {sender_id}")

        # Verify signature
        try:
            public_key.verify(signature, bytes([sender_id]) + compressed)
        except Exception:
            raise AuthenticationError(f"Invalid signature from system {sender_id}")

        # Decompress
        return compressor.decompress(compressed), sender_id
```

**Overhead:** 65 bytes per message (1 byte sender_id + 64 bytes signature)

### Priority 3: Replay Protection (MEDIUM IMPACT)

**Add sequence numbers:**

```python
class ReplayProtectedCompressor:
    def __init__(self):
        self.send_sequence = {}  # {recipient_id: next_sequence}
        self.recv_sequence = {}  # {sender_id: expected_sequence}

    def compress_with_sequence(self, text, recipient_id):
        compressed = compressor.compress(text)

        # Get next sequence number
        seq = self.send_sequence.get(recipient_id, 0)
        self.send_sequence[recipient_id] = seq + 1

        # Add sequence + timestamp
        timestamp = int(time.time())
        header = struct.pack('>QQ', seq, timestamp)

        return header + compressed

    def verify_sequence(self, payload, sender_id, max_age_seconds=60):
        seq, timestamp = struct.unpack('>QQ', payload[:16])
        compressed = payload[16:]

        # Verify sequence (must be strictly increasing)
        expected_seq = self.recv_sequence.get(sender_id, 0)
        if seq != expected_seq:
            raise ReplayError(f"Expected sequence {expected_seq}, got {seq}")

        # Update expected sequence
        self.recv_sequence[sender_id] = seq + 1

        # Verify timestamp
        age = time.time() - timestamp
        if age > max_age_seconds:
            raise ReplayError(f"Message age {age}s exceeds maximum {max_age_seconds}s")

        return compressor.decompress(compressed)
```

**Overhead:** 16 bytes per message (8 bytes sequence + 8 bytes timestamp)

### Priority 4: Context Binding (MEDIUM IMPACT)

Already covered by signature + sequence number (sender + recipient + session implicitly bound).

### Priority 5: Covert Channel Mitigation (LOW IMPACT)

**Normalize timing and ordering in orchestrator, not AURA.**

## Complete Hardened Format

```
Hardened AURA Message Format:
┌────────────────────────────────────────────────────────────────┐
│ Sender ID (1 byte)                                             │
├────────────────────────────────────────────────────────────────┤
│ Signature (64 bytes) - Ed25519 signature                       │
├────────────────────────────────────────────────────────────────┤
│ Sequence Number (8 bytes) - Replay protection                  │
├────────────────────────────────────────────────────────────────┤
│ Timestamp (8 bytes) - Freshness check                          │
├────────────────────────────────────────────────────────────────┤
│ Compressed Message (variable) - AURA/bit-packed                │
├────────────────────────────────────────────────────────────────┤
│ HMAC (16 bytes) - Integrity protection                         │
└────────────────────────────────────────────────────────────────┘

Total Overhead: 97 bytes
```

**Overhead Analysis:**

| Message Size | Overhead | Overhead % |
|--------------|----------|------------|
| 4 bytes (bit-packed) | 97 bytes | 2425% 😱 |
| 30 bytes (small) | 97 bytes | 323% 😬 |
| 100 bytes (medium) | 97 bytes | 97% 🤔 |
| 500 bytes (large) | 97 bytes | 19% ✅ |

**Problem:** Overhead is prohibitive for small messages!

## Optimized Hardening (Batch Signing)

**Instead of signing each message, sign batches:**

```python
# Batch format
batch = {
    'sender_id': 1,
    'sequence_start': 1000,
    'timestamp': 1699564800,
    'messages': [
        compressed_msg1,  # sequence 1000
        compressed_msg2,  # sequence 1001
        compressed_msg3,  # sequence 1002
    ],
}

# Sign the entire batch
batch_data = msgpack.packb(batch)
signature = private_key.sign(batch_data)

# Format: [batch_data][signature]
signed_batch = batch_data + signature
```

**Overhead:** 64 bytes for entire batch (amortized across N messages)

**For batch of 10 messages:**
- Per-message overhead: 6.4 bytes ✅
- Much better than 97 bytes per message!

## Recommendation

### Implement Hardening If:

1. ✅ **Network is untrusted** (messages traverse public internet)
2. ✅ **Storage is untrusted** (messages stored on shared infrastructure)
3. ✅ **High-stakes decisions** (wrong approval has catastrophic consequences)
4. ✅ **External attackers possible** (not just misbehaving AI systems)

### Skip Hardening If:

1. ❌ **Trusted network** (private infrastructure, isolated systems)
2. ❌ **Trusted storage** (WORM media, tamper-evident logs)
3. ❌ **Low stakes** (proposals can be reverted easily)
4. ❌ **Only internal threat model** (misbehaving AI systems, not external attackers)

### Your Situation:

Based on AI Safety System design:
- ✅ High-stakes decisions (AI improvements affect safety)
- ✅ Potential for external attackers (if deployed to production)
- ✅ Untrusted network (messages between distributed AI systems)
- ✅ Long-lived system (replay attacks possible over time)

**Verdict: IMPLEMENT HARDENING** ✅

**Priority order:**
1. **Integrity (HMAC)** - Prevents silent corruption
2. **Authentication (signatures)** - Prevents sender forgery
3. **Replay protection (sequence)** - Prevents old message reuse
4. **Batch signing** - Reduces overhead

**Use batch signing to minimize overhead on small messages (bit-packed format).**
