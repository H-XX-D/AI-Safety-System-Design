"""Simple configuration loader with graceful fallbacks.

Priority order for selecting config file:
- Environment variable APP_ENV in {development, production, default}
- Defaults to 'default.yaml' when not set or invalid.

YAML parsing strategy:
- Try to import PyYAML. If unavailable, use a very small indentation-based
  parser that supports nested mappings with scalar values (str/float/int/bool).
  This is sufficient for our current config files.
"""
from __future__ import annotations

import os
from typing import Any, Dict
from binascii import unhexlify
from typing import List
from resource_guard import ResourceBudget


def _parse_scalar(value: str) -> Any:
    v = value.strip()
    if not v:
        return ""
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        items: list[Any] = []
        current: list[str] = []
        depth = 0
        for ch in inner:
            if ch == ',' and depth == 0:
                item = ''.join(current).strip()
                if item:
                    items.append(_parse_scalar(item))
                current = []
                continue
            if ch in "[(":
                depth += 1
            elif ch in ")]" and depth > 0:
                depth -= 1
            current.append(ch)
        tail = ''.join(current).strip()
        if tail:
            items.append(_parse_scalar(tail))
        return items
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _tiny_yaml_parse(text: str) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    stack: list[tuple[int, Dict[str, Any]]] = [(0, root)]
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while stack and indent < stack[-1][0]:
            stack.pop()
        if ":" in line:
            key, val = line.strip().split(":", 1)
            key = key.strip()
            # Remove inline comments that follow the value (e.g., "value  # comment")
            # This small parser ignores # occurring inside quotes but handles typical inline comments.
            if "#" in val:
                val = val.split("#", 1)[0]
            if val.strip() == "":
                # New nested mapping
                new_map: Dict[str, Any] = {}
                stack[-1][1][key] = new_map
                stack.append((indent + 2, new_map))
            else:
                stack[-1][1][key] = _parse_scalar(val)
    return root


def load_config() -> Dict[str, Any]:
    env = os.getenv("APP_ENV", "default").lower()
    filename = {
        "development": "config/development.yaml",
        "production": "config/production.yaml",
        "default": "config/default.yaml",
    }.get(env, "config/default.yaml")
    try:
        with open(filename, "r") as f:
            text = f.read()
        # Optional config signature verification
        pub_hex = os.getenv("CONFIG_PUBKEY_HEX")
        pub_hexes = os.getenv("CONFIG_PUBKEYS_HEX")
        sig_path = f"{filename}.sig"
        if (pub_hex or pub_hexes) and os.path.exists(sig_path):
            try:
                with open(sig_path, "r") as sf:
                    sig_hex = sf.read().strip()
                # Optional resource budget
                budget_env = os.getenv("CONFIG_VERIFY_BUDGET_MS")
                try:
                    budget_ms = float(budget_env) if budget_env else None
                except Exception:
                    budget_ms = None
                def _do_verify() -> bool:
                    if pub_hexes:
                        keys = [s.strip() for s in pub_hexes.split(",") if s.strip()]
                        revoked = set([s.strip() for s in os.getenv("CONFIG_REVOKED_PUBKEYS_HEX", "").split(",") if s.strip()])
                        return verify_signature_with_keyring(text.encode("utf-8"), sig_hex, keys, revoked)
                    elif pub_hex:
                        return verify_signature_ed25519(text.encode("utf-8"), sig_hex, pub_hex)
                    return False
                ok = False
                if budget_ms is not None:
                    with ResourceBudget(budget_ms):
                        ok = _do_verify()
                else:
                    ok = _do_verify()
                if not ok:
                    if os.getenv("CONFIG_STRICT", "0") == "1":
                        raise RuntimeError("config signature verification failed")
                    # Non-strict: return empty to avoid using possibly tampered config
                    return {}
            except Exception:
                if os.getenv("CONFIG_STRICT", "0") == "1":
                    raise
                # Soft-fail: continue without config
                return {}
        try:
            import yaml  # type: ignore

            return dict(yaml.safe_load(text) or {})  # type: ignore[no-any-return]
        except Exception:
            return _tiny_yaml_parse(text)
    except Exception:
        return {}


def validate_production_readiness(cfg: Dict[str, Any]) -> None:
    """Raise RuntimeError if production config violates critical security requirements."""
    env = os.getenv('APP_ENV', 'default').lower()
    if env != 'production':
        return
    worm = (cfg.get('worm', {}) or {})
    if not bool(worm.get('halt_on_failure', False)):
        raise RuntimeError('worm.halt_on_failure must be true in production')
    st = (cfg.get('secure_transport', {}) or {})
    if not bool(st.get('enabled', False)):
        raise RuntimeError('secure_transport.enabled must be true in production')
    key_hex = str(st.get('hmac_key_hex') or '')
    if len(key_hex) < 64 or key_hex.startswith('00112233'):
        raise RuntimeError('secure_transport.hmac_key_hex is invalid or default-like in production')
    val = (cfg.get('val', {}) or {})
    if int(val.get('required_signers', 0)) < 2:
        raise RuntimeError('val.required_signers must be >= 2 in production')


def verify_signature_ed25519(message: bytes, sig_hex: str, pub_hex: str) -> bool:
    """Verify Ed25519 signature for message using PyNaCl if available.

    Returns False if verification library not available or verification fails.
    """
    try:
        from nacl.signing import VerifyKey  # type: ignore
        from nacl.exceptions import BadSignatureError  # type: ignore
    except Exception:  # pragma: no cover - dependency optional
        return False
    try:
        vk = VerifyKey(unhexlify(pub_hex))
        sig = unhexlify(sig_hex)
        vk.verify(message, sig)
        return True
    except Exception:
        return False


def verify_signature_with_keyring(message: bytes, sig_hex: str, pubkeys_hex: List[str], revoked_hex: set[str] | None = None) -> bool:
    """Try verifying against any pubkey in the keyring; respect revoked list.

    To reduce timing leakage about which key matches, we do not early-return; we
    evaluate all candidates and OR the result. For large rings, this is O(n).
    """
    revoked_hex = revoked_hex or set()
    found = False
    for pub in pubkeys_hex:
        if pub in revoked_hex:
            # still perform a dummy verify to reduce timing correlation
            _ = verify_signature_ed25519(message, sig_hex, pub)
            continue
        if verify_signature_ed25519(message, sig_hex, pub):
            found = True
    return found
