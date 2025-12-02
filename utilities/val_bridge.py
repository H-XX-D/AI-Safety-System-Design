"""
VAL Bridge
Creates export packages for offline validation, and verifies human-signed
responses on re-import to gate deployment.
"""
from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from utilities.config_loader import load_config  # type: ignore
except Exception:  # pragma: no cover
    def load_config() -> Dict[str, Any]:
        return {}


@dataclass
class ValPackage:
    package_id: str
    proposal_id: str
    created_at: str
    path: str


def _io_dirs() -> Dict[str, Path]:
    cfg = load_config() or {}
    root = Path(cfg.get('val', {}).get('io_root', Path.cwd() / 'demo_outputs' / 'val')).resolve()
    outbox = root / 'outbox'
    inbox = root / 'inbox'
    outbox.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    return {'root': root, 'outbox': outbox, 'inbox': inbox}


def create_val_package(proposal: Dict[str, Any], *, test_results: Dict[str, Any]) -> ValPackage:
    """Create a VAL export package (JSON) in the outbox directory."""
    io = _io_dirs()
    pid = str(proposal.get('proposal_id', 'unknown'))
    ts = datetime.now().isoformat()
    # Minimal signed-manifest-ready payload
    payload = {
        'proposal_id': pid,
        'created_at': ts,
        'proposal': proposal,
        'test_results': test_results,
        'schema': 'val_package_v1',
    }
    # Compute content hash for manifest
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    content_hash = hashlib.sha256(payload_bytes).hexdigest()
    package = {
        'manifest': {
            'proposal_id': pid,
            'created_at': ts,
            'content_hash': content_hash,
            'required_signers': int((load_config() or {}).get('val', {}).get('required_signers', 1)),
            'signatures': [],  # will be filled by import path
        },
        'payload': payload,
    }
    path = io['outbox'] / f"VAL_{pid}_{int(datetime.now().timestamp())}.json"
    with path.open('w', encoding='utf-8') as fh:
        json.dump(package, fh, indent=2)
    return ValPackage(package_id=path.stem, proposal_id=pid, created_at=ts, path=str(path))


def verify_val_response(path: str, *, required_signer_id: Optional[int] = None) -> Dict[str, Any]:
    """Verify a VAL response file.

    Backward compatible with simple response schema and supports multi-signer manifest:
      - Simple response (legacy): {proposal_id, approved, reviewer_id, timestamp, signature, notes}
      - Manifested response (new): {manifest:{proposal_id, content_hash, required_signers, signatures:[{reviewer_id, approved, timestamp, signature, notes}]}, payload:{...}}
    """
    with Path(path).open('r', encoding='utf-8') as fh:
        data = json.load(fh)

    # New multi-signer manifest format
    if isinstance(data, dict) and 'manifest' in data and 'payload' in data:
        manifest = data.get('manifest') or {}
        payload = data.get('payload') or {}
        # Verify payload content hash
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        content_hash = hashlib.sha256(payload_bytes).hexdigest()
        if manifest.get('content_hash') != content_hash:
            return {'approved': False, 'signature_valid': False, 'val_confidence': 0.0, 'notes': 'content_hash_mismatch'}
        # Count valid signatures meeting threshold
        sigs = manifest.get('signatures') or []
        cfg = load_config() or {}
        required = int(cfg.get('val', {}).get('required_signers', manifest.get('required_signers', 1)))
        valid_count = 0
        approving_count = 0
        last_ts = None
        last_note = ''
        for s in sigs:
            rid = s.get('reviewer_id')
            if required_signer_id is not None and rid != required_signer_id:
                continue
            sig_payload = {
                'reviewer_id': rid,
                'proposal_id': manifest.get('proposal_id') or payload.get('proposal_id'),
                'approved': bool(s.get('approved', False)),
                'timestamp': s.get('timestamp'),
                'content_hash': content_hash,
                'signature': s.get('signature'),
            }
            if _verify_signature(sig_payload):
                valid_count += 1
                if s.get('approved'):
                    approving_count += 1
                last_ts = s.get('timestamp')
                last_note = s.get('notes', last_note)
        approved = approving_count >= required and valid_count >= required
        return {
            'approved': approved,
            'signature_valid': valid_count >= required,
            'val_confidence': 0.95 if approved else 0.0,
            'validator_id': None,
            'notes': last_note,
            'timestamp': last_ts,
        }

    # Legacy single-signer format
    ok = False
    sig_ok = False
    rid = data.get('reviewer_id')
    if required_signer_id is not None and rid != required_signer_id:
        sig_ok = False
    else:
        sig_ok = _verify_signature(data)
    ok = bool(data.get('approved', False)) and sig_ok
    return {
        'approved': bool(data.get('approved', False)),
        'signature_valid': sig_ok,
        'val_confidence': 0.9 if ok else 0.0,
        'validator_id': rid,
        'notes': data.get('notes', ''),
        'timestamp': data.get('timestamp'),
    }


def _verify_signature(payload: Dict[str, Any]) -> bool:
    # Best-effort: use human_review.verify_human_signature if available. Otherwise, reject.
    try:
        from research.human_review import verify_human_signature  # type: ignore
    except Exception:
        return False
    reviewer_id = payload.get('reviewer_id')
    signature = payload.get('signature')
    secret = os.environ.get('VAL_SIGNING_SECRET')  # Operator supplies secret out-of-band
    ts = payload.get('timestamp') or datetime.now().isoformat()
    msg = {
        'reviewer_id': reviewer_id,
        'proposal_id': payload.get('proposal_id'),
        'approved': bool(payload.get('approved', False)),
        'timestamp': ts,
    }
    if 'content_hash' in payload:
        msg['content_hash'] = payload['content_hash']
    try:
        return bool(verify_human_signature(msg, secret, signature))
    except Exception:
        return False
