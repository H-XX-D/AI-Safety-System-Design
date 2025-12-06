#!/usr/bin/env python3
"""
Artifact Signing and Verification for ORKASTRATOR
===================================================

Provides:
- Ed25519 signing of proposal/code bundles
- Signature verification before deployment
- Merkle tree for append-only audit storage
- Versioned backup with integrity checks
"""

import json
import hashlib
import time
import base64
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger("orkastrator.signing")

# Try to import cryptography, fall back to hmac-based signing
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not available - using HMAC fallback")


@dataclass
class SignedArtifact:
    """A signed artifact bundle."""
    artifact_id: str
    artifact_type: str
    content_hash: str
    content: str
    proposer: str
    timestamp: float
    signature: str
    signed_by: str
    previous_hash: Optional[str] = None  # For chain integrity
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SignedArtifact":
        return cls(**data)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class ArtifactSigner:
    """Sign and verify artifacts using Ed25519 or HMAC fallback."""
    
    def __init__(self, key_path: Optional[Path] = None, signer_id: str = "ORKA"):
        self.signer_id = signer_id
        self.key_path = key_path or Path.home() / ".orkastrator" / "signing_key"
        self._private_key = None
        self._public_key = None
        self._hmac_secret = None
        
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load existing key or generate new one."""
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        
        if CRYPTO_AVAILABLE:
            if self.key_path.exists():
                key_data = self.key_path.read_bytes()
                self._private_key = serialization.load_pem_private_key(
                    key_data, password=None, backend=default_backend()
                )
                self._public_key = self._private_key.public_key()
            else:
                self._private_key = Ed25519PrivateKey.generate()
                self._public_key = self._private_key.public_key()
                
                # Save private key
                key_pem = self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                self.key_path.write_bytes(key_pem)
                self.key_path.chmod(0o600)
                
                # Save public key
                pub_pem = self._public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                self.key_path.with_suffix(".pub").write_bytes(pub_pem)
                
                logger.info(f"Generated new signing key: {self.key_path}")
        else:
            # HMAC fallback
            secret_path = self.key_path.with_suffix(".secret")
            if secret_path.exists():
                self._hmac_secret = secret_path.read_bytes()
            else:
                import secrets
                self._hmac_secret = secrets.token_bytes(32)
                secret_path.write_bytes(self._hmac_secret)
                secret_path.chmod(0o600)
                logger.info(f"Generated HMAC secret: {secret_path}")
    
    def get_public_key_pem(self) -> str:
        """Get public key in PEM format."""
        if CRYPTO_AVAILABLE and self._public_key:
            return self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
        return f"HMAC-SHA256:{self.signer_id}"
    
    def sign_artifact(
        self,
        content: str,
        artifact_type: str,
        proposer: str,
        previous_hash: Optional[str] = None
    ) -> SignedArtifact:
        """Sign an artifact and return signed bundle."""
        # Create artifact ID
        timestamp = time.time()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        artifact_id = hashlib.sha256(
            f"{content_hash}:{timestamp}:{proposer}".encode()
        ).hexdigest()[:16]
        
        # Create signing payload
        payload = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "content_hash": content_hash,
            "proposer": proposer,
            "timestamp": timestamp,
            "previous_hash": previous_hash,
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        
        # Sign
        if CRYPTO_AVAILABLE and self._private_key:
            signature_bytes = self._private_key.sign(payload_bytes)
            signature = base64.b64encode(signature_bytes).decode()
        else:
            # HMAC fallback
            import hmac
            signature_bytes = hmac.new(
                self._hmac_secret, payload_bytes, hashlib.sha256
            ).digest()
            signature = "hmac:" + base64.b64encode(signature_bytes).decode()
        
        return SignedArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            content=content,
            proposer=proposer,
            timestamp=timestamp,
            signature=signature,
            signed_by=self.signer_id,
            previous_hash=previous_hash,
        )
    
    def verify_artifact(self, artifact: SignedArtifact) -> Tuple[bool, str]:
        """Verify artifact signature."""
        # Verify content hash
        computed_hash = hashlib.sha256(artifact.content.encode()).hexdigest()
        if computed_hash != artifact.content_hash:
            return False, f"Content hash mismatch: {computed_hash} != {artifact.content_hash}"
        
        # Reconstruct signing payload
        payload = {
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "content_hash": artifact.content_hash,
            "proposer": artifact.proposer,
            "timestamp": artifact.timestamp,
            "previous_hash": artifact.previous_hash,
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        
        # Verify signature
        if artifact.signature.startswith("hmac:"):
            # HMAC verification
            import hmac
            expected_sig = hmac.new(
                self._hmac_secret, payload_bytes, hashlib.sha256
            ).digest()
            expected_b64 = "hmac:" + base64.b64encode(expected_sig).decode()
            if artifact.signature == expected_b64:
                return True, "HMAC signature verified"
            return False, "HMAC signature mismatch"
        else:
            # Ed25519 verification
            if not CRYPTO_AVAILABLE or not self._public_key:
                return False, "Ed25519 verification not available"
            
            try:
                signature_bytes = base64.b64decode(artifact.signature)
                self._public_key.verify(signature_bytes, payload_bytes)
                return True, "Ed25519 signature verified"
            except Exception as e:
                return False, f"Signature verification failed: {e}"


class MerkleAuditLog:
    """Append-only audit log using Merkle tree for integrity."""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: List[Dict] = []
        self._hashes: List[str] = []
        self._load_log()
    
    def _load_log(self):
        """Load existing log."""
        if self.log_path.exists():
            with open(self.log_path) as f:
                for line in f:
                    entry = json.loads(line)
                    self._entries.append(entry["data"])
                    self._hashes.append(entry["hash"])
    
    def _compute_hash(self, data: Dict, previous_hash: str) -> str:
        """Compute entry hash including previous hash (chain)."""
        payload = json.dumps(data, sort_keys=True) + previous_hash
        return hashlib.sha256(payload.encode()).hexdigest()
    
    @property
    def root_hash(self) -> str:
        """Get current Merkle root hash."""
        if not self._hashes:
            return hashlib.sha256(b"genesis").hexdigest()
        return self._hashes[-1]
    
    def append(self, entry: Dict) -> str:
        """Append entry and return its hash."""
        previous = self._hashes[-1] if self._hashes else hashlib.sha256(b"genesis").hexdigest()
        entry_with_meta = {
            **entry,
            "_timestamp": time.time(),
            "_sequence": len(self._entries),
        }
        
        entry_hash = self._compute_hash(entry_with_meta, previous)
        
        self._entries.append(entry_with_meta)
        self._hashes.append(entry_hash)
        
        # Append to file
        with open(self.log_path, "a") as f:
            f.write(json.dumps({"data": entry_with_meta, "hash": entry_hash}) + "\n")
        
        return entry_hash
    
    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """Verify entire chain integrity. Returns (valid, first_invalid_index)."""
        if not self._entries:
            return True, None
        
        previous = hashlib.sha256(b"genesis").hexdigest()
        for i, (entry, stored_hash) in enumerate(zip(self._entries, self._hashes)):
            computed = self._compute_hash(entry, previous)
            if computed != stored_hash:
                return False, i
            previous = stored_hash
        
        return True, None
    
    def get_entry(self, index: int) -> Optional[Dict]:
        """Get entry by index."""
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None
    
    def get_proof(self, index: int) -> Dict:
        """Get Merkle proof for an entry."""
        if index < 0 or index >= len(self._entries):
            return {"error": "Invalid index"}
        
        return {
            "entry": self._entries[index],
            "hash": self._hashes[index],
            "previous_hash": self._hashes[index - 1] if index > 0 else hashlib.sha256(b"genesis").hexdigest(),
            "root_hash": self.root_hash,
            "chain_length": len(self._entries),
        }


class SecureVersionStore:
    """Versioned storage with integrity checks."""
    
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.signer = ArtifactSigner()
        self.audit_log = MerkleAuditLog(store_path / "audit.jsonl")
    
    def store(
        self,
        content: str,
        artifact_type: str,
        proposer: str,
        metadata: Optional[Dict] = None
    ) -> SignedArtifact:
        """Store artifact with signature and audit."""
        # Sign artifact
        artifact = self.signer.sign_artifact(
            content=content,
            artifact_type=artifact_type,
            proposer=proposer,
            previous_hash=self.audit_log.root_hash,
        )
        
        # Store artifact file
        artifact_path = self.store_path / f"{artifact.artifact_id}.json"
        artifact_path.write_text(artifact.to_json())
        
        # Add to audit log
        audit_entry = {
            "action": "store",
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact_type,
            "proposer": proposer,
            "content_hash": artifact.content_hash,
            "metadata": metadata or {},
        }
        self.audit_log.append(audit_entry)
        
        logger.info(f"Stored artifact {artifact.artifact_id} ({artifact_type}) by {proposer}")
        return artifact
    
    def retrieve(self, artifact_id: str) -> Optional[SignedArtifact]:
        """Retrieve and verify artifact."""
        artifact_path = self.store_path / f"{artifact_id}.json"
        if not artifact_path.exists():
            return None
        
        data = json.loads(artifact_path.read_text())
        artifact = SignedArtifact.from_dict(data)
        
        # Verify
        valid, msg = self.signer.verify_artifact(artifact)
        if not valid:
            logger.error(f"Artifact {artifact_id} failed verification: {msg}")
            return None
        
        return artifact
    
    def list_artifacts(
        self,
        artifact_type: Optional[str] = None,
        proposer: Optional[str] = None
    ) -> List[str]:
        """List artifact IDs, optionally filtered."""
        results = []
        for path in self.store_path.glob("*.json"):
            if path.name == "audit.jsonl":
                continue
            try:
                data = json.loads(path.read_text())
                if artifact_type and data.get("artifact_type") != artifact_type:
                    continue
                if proposer and data.get("proposer") != proposer:
                    continue
                results.append(data["artifact_id"])
            except:
                pass
        return results
    
    def verify_integrity(self) -> Dict[str, Any]:
        """Verify store integrity."""
        chain_valid, first_invalid = self.audit_log.verify_chain()
        
        # Verify all artifacts
        artifact_results = {}
        for path in self.store_path.glob("*.json"):
            if path.name.startswith("audit"):
                continue
            try:
                data = json.loads(path.read_text())
                artifact = SignedArtifact.from_dict(data)
                valid, msg = self.signer.verify_artifact(artifact)
                artifact_results[artifact.artifact_id] = {"valid": valid, "message": msg}
            except Exception as e:
                artifact_results[path.stem] = {"valid": False, "message": str(e)}
        
        return {
            "chain_valid": chain_valid,
            "first_invalid_entry": first_invalid,
            "artifacts": artifact_results,
            "total_artifacts": len(artifact_results),
            "valid_artifacts": sum(1 for r in artifact_results.values() if r["valid"]),
        }


# Global instances
_signer: Optional[ArtifactSigner] = None
_store: Optional[SecureVersionStore] = None


def get_signer() -> ArtifactSigner:
    """Get the artifact signer."""
    global _signer
    if _signer is None:
        _signer = ArtifactSigner()
    return _signer


def get_version_store() -> SecureVersionStore:
    """Get the secure version store."""
    global _store
    if _store is None:
        _store = SecureVersionStore(Path.home() / ".orkastrator" / "artifacts")
    return _store


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        store = get_version_store()
        
        if cmd == "verify":
            result = store.verify_integrity()
            print(json.dumps(result, indent=2))
        elif cmd == "list":
            artifacts = store.list_artifacts()
            for a in artifacts:
                print(a)
        elif cmd == "pubkey":
            signer = get_signer()
            print(signer.get_public_key_pem())
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: artifact_signing.py [verify|list|pubkey]")
    else:
        # Demo
        print("=== Artifact Signing Demo ===")
        signer = get_signer()
        
        # Sign an artifact
        artifact = signer.sign_artifact(
            content='{"temperature": 0.7}',
            artifact_type="inference_params",
            proposer="GIN",
        )
        print(f"\nSigned artifact: {artifact.artifact_id}")
        print(f"Signature: {artifact.signature[:50]}...")
        
        # Verify
        valid, msg = signer.verify_artifact(artifact)
        print(f"Verification: {valid} - {msg}")
        
        # Store
        store = get_version_store()
        stored = store.store(
            content="Test improvement content",
            artifact_type="prompt_template",
            proposer="TORI",
        )
        print(f"\nStored artifact: {stored.artifact_id}")
        
        # Verify integrity
        integrity = store.verify_integrity()
        print(f"\nIntegrity check:")
        print(f"  Chain valid: {integrity['chain_valid']}")
        print(f"  Artifacts: {integrity['valid_artifacts']}/{integrity['total_artifacts']} valid")
