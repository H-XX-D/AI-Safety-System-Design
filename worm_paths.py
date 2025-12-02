"""
Common helpers for resolving WORM USB paths across modules.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from config_loader import load_config  # type: ignore
except Exception:  # pragma: no cover - fallback when config isn't available
    def load_config() -> dict:
        return {}


def resolve_worm_root(*, fallback: Optional[str] = None) -> str:
    """Resolve the ORKASTRATOR_WORM root directory.

    Checks, in order:
      1) WORM_USB_PATH env var
      2) config['worm']['usb_mount_path']
      3) Common platform mount points
      4) Provided fallback (if any)
    """
    # 1) Env override
    env_path = os.environ.get("WORM_USB_PATH")
    if env_path and os.path.exists(env_path):
        base = Path(env_path)
        if (base / "ORKASTRATOR_WORM").exists():
            return str(base / "ORKASTRATOR_WORM")
        return str(base)

    # 2) Config
    try:
        cfg = load_config() or {}
        worm_cfg = cfg.get("worm", {}) if isinstance(cfg.get("worm", {}), dict) else {}
        usb_mount = worm_cfg.get("usb_mount_path")
        if isinstance(usb_mount, str) and os.path.exists(usb_mount):
            base = Path(usb_mount)
            if (base / "ORKASTRATOR_WORM").exists():
                return str(base / "ORKASTRATOR_WORM")
            return str(base)
    except Exception:
        pass

    # 3) Common mounts
    candidates = [
        "/Volumes/ORKASTRATOR_WORM",
        "/Volumes/NO NAME/ORKASTRATOR_WORM",
        "/media/usb/ORKASTRATOR_WORM",
        "/mnt/usb/ORKASTRATOR_WORM",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # 4) Fallback
    if fallback:
        return fallback
    # last resort: first candidate even if missing
    return candidates[0]

