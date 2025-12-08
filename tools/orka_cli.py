#!/usr/bin/env python3
"""
ORKA CLI
========

Lightweight CLI to inspect cluster/system status from the ORKASTRATOR repo.

Usage:
    python tools/orka_cli.py status                # Overall status
    python tools/orka_cli.py status --node THEO    # Specific node status
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from ui.live_data_provider import (
        get_cluster_status_live,
        get_agent_status_live,
        get_jetson_power_status,
        get_local_system_metrics,
        get_ollama_model_info,
    )
except Exception as exc:  # pragma: no cover - guard for missing deps
    sys.stderr.write(f"Failed to import live data provider: {exc}\n")
    sys.exit(1)


def _print_json(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def _build_node_view(node_name: str, cluster: dict, agents: dict, power: dict) -> dict:
    node = cluster["nodes"].get(node_name, {})
    agent_cfg = agents.get(node_name, {})
    power_nodes = {n["name"]: n for n in power.get("nodes", [])}
    p = power_nodes.get(node_name, {})
    return {
        "name": node_name,
        "online": node.get("online"),
        "ip": node.get("ip") or agent_cfg.get("ip"),
        "role": agent_cfg.get("role"),
        "model": node.get("expected_model") or agent_cfg.get("model"),
        "response_time_ms": node.get("response_time_ms"),
        "power_watts": p.get("power_watts"),
        "temps": p.get("temps"),
        "error": p.get("error"),
    }


def cmd_status(node):
    cluster = get_cluster_status_live()
    agents = get_agent_status_live()
    power = get_jetson_power_status()
    sys_metrics = get_local_system_metrics()
    ollama = get_ollama_model_info()

    if node:
        if node not in cluster["nodes"]:
            sys.stderr.write(f"Node {node} not found in cluster.\n")
            sys.exit(1)
        data = {
            "node": _build_node_view(node, cluster, agents, power),
            "timestamp": cluster.get("timestamp"),
        }
        _print_json(data)
        return

    data = {
        "cluster": {
            "online": cluster.get("online_count"),
            "total": cluster.get("total_count"),
            "nodes": {
                name: _build_node_view(name, cluster, agents, power)
                for name in cluster.get("nodes", {})
            },
            "healthy": cluster.get("healthy"),
            "timestamp": cluster.get("timestamp"),
        },
        "system": sys_metrics,
        "ollama": ollama,
        "jetson_power": {
            "online": power.get("online"),
            "total": power.get("total"),
            "aggregate_power_watts": power.get("aggregate_power_watts"),
        },
    }
    _print_json(data)


def main():
    parser = argparse.ArgumentParser(description="ORKA cluster/system CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    st = sub.add_parser("status", help="Show cluster/system status")
    st.add_argument("--node", help="Show status for a specific node code (e.g., THEO)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.node)
    else:  # pragma: no cover - defensive
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
