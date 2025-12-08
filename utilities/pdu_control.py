#!/usr/bin/env python3
"""
Digital Loggers PDU Control
===========================

Lightweight helper to switch outlets on/off and query outlet state.

Env vars:
    DLI_BASE_URL   e.g. http://192.168.0.200
    DLI_USER       e.g. admin
    DLI_PASS       e.g. 1234
    DLI_OUTLETS    JSON map name->outlet number, e.g. {"GIN":1,"ORIN":2}

Usage:
    python utilities/pdu_control.py --action off --nodes GIN,ORIN
    python utilities/pdu_control.py --action status
"""
import argparse
import json
import os
import sys
from typing import Dict, List

import requests
from requests.auth import HTTPBasicAuth


def load_outlet_map() -> Dict[str, int]:
    raw = os.environ.get("DLI_OUTLETS", "{}")
    try:
        data = json.loads(raw)
        return {str(k).upper(): int(v) for k, v in data.items()}
    except Exception:
        return {}


def control_outlet(base: str, user: str, pwd: str, outlet: int, action: str) -> bool:
    # Digital-Loggers REST API: POST value=0/1 to /restapi/relay/outlets/{id}/state/
    url = f"{base.rstrip('/')}/restapi/relay/outlets/{outlet}/state/"
    value = 0 if action == "off" else 1
    try:
        resp = requests.post(url, data={"value": value}, auth=HTTPBasicAuth(user, pwd), timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Control Digital Loggers PDU outlets")
    parser.add_argument("--action", choices=["off", "on", "status"], required=True)
    parser.add_argument("--nodes", default="", help="Comma-separated node names to control")
    args = parser.parse_args(argv)

    base = os.environ.get("DLI_BASE_URL", "").strip()
    user = os.environ.get("DLI_USER", "").strip()
    pwd = os.environ.get("DLI_PASS", "").strip()
    outlet_map = load_outlet_map()
    targets = [n.strip().upper() for n in args.nodes.split(",") if n.strip()]

    if args.action == "status":
        if not base or not user or not pwd:
            print("Missing DLI creds; cannot query status.")
            return 1
        info = get_status(base, user, pwd)
        print(json.dumps(info, indent=2))
        return 0 if not info.get("error") else 1

    if not base or not user or not pwd:
        print("Missing DLI_BASE_URL / DLI_USER / DLI_PASS; dry-run only")
        print(f"Would set {args.action} for: {targets}")
        return 0

    success = True
    for name in targets:
        outlet = outlet_map.get(name)
        if outlet is None:
            print(f"[WARN] No outlet mapping for {name}")
            success = False
            continue
        ok = control_outlet(base, user, pwd, outlet, args.action)
        if ok:
            print(f"[OK] {args.action.upper()} outlet {outlet} ({name})")
        else:
            print(f"[FAIL] {args.action.upper()} outlet {outlet} ({name})")
            success = False

    return 0 if success else 1


def get_status(base: str, user: str, pwd: str) -> Dict[str, any]:
    """Fetch outlet states; returns {'outlets': [...], 'raw': ...}"""
    try:
        url = f"{base.rstrip('/')}/restapi/relay/outlets/"
        resp = requests.get(url, auth=HTTPBasicAuth(user, pwd), timeout=5)
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "raw": resp.text}
        data = resp.json()
        return {"outlets": data, "raw": data}
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
