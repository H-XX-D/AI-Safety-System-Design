"""
Lightweight terminal dashboard for orchestrator telemetry.

Usage:
    python ui/dashboard.py --events logs/orchestrator_events.jsonl

The dashboard watches the structured JSONL log emitted by the orchestrator
and renders three panes:

1. Sandbox verdicts (latest 5)
2. Control hook activity
3. Translator outputs / alerts

Each log line is expected to be a JSON object with at least a `type` field:

{
  "type": "sandbox",
  "proposal_id": "P-001",
  "overall_pass": true,
  "timestamp": "...",
  ...
}

Types currently handled:
  - sandbox
  - control_action
  - translator
  - alert

Unknown types are shown in a generic feed.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List
from collections import deque

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


@dataclass
class DashboardState:
    sandbox_events: Deque[Dict[str, str]] = field(default_factory=lambda: deque(maxlen=5))
    control_events: Deque[Dict[str, str]] = field(default_factory=lambda: deque(maxlen=5))
    translator_events: Deque[Dict[str, str]] = field(default_factory=lambda: deque(maxlen=5))
    generic_events: Deque[Dict[str, str]] = field(default_factory=lambda: deque(maxlen=5))

    def ingest(self, event: Dict[str, str]) -> None:
        etype = event.get("type", "generic").lower()
        if etype == "sandbox":
            self.sandbox_events.appendleft(event)
        elif etype == "control_action":
            self.control_events.appendleft(event)
        elif etype in {"translator", "alert"}:
            self.translator_events.appendleft(event)
        else:
            self.generic_events.appendleft(event)


def render_table(title: str, events: Deque[Dict[str, str]], columns: List[str]) -> Table:
    table = Table(title=title, box=box.SIMPLE_HEAD)
    for col in columns:
        table.add_column(col, style="bold")
    if not events:
        table.add_row("—" * 5)
        return table
    for event in events:
        row = [str(event.get(col, "")) for col in columns]
        table.add_row(*row)
    return table


def render_dashboard(state: DashboardState) -> Panel:
    sandbox = render_table(
        "Sandbox Verdicts",
        state.sandbox_events,
        ["proposal_id", "overall_pass", "stage", "timestamp"],
    )
    control = render_table(
        "Control Hooks",
        state.control_events,
        ["action", "status", "details", "timestamp"],
    )
    translator = render_table(
        "Translator / Alerts",
        state.translator_events,
        ["summary", "severity", "timestamp"],
    )
    generic = render_table(
        "Other Events",
        state.generic_events,
        ["type", "message", "timestamp"],
    )
    grid = Table.grid(expand=True)
    grid.add_row(sandbox, control)
    grid.add_row(translator, generic)
    return Panel(grid, title="AI Safety Ops Dashboard", border_style="cyan")


def tail_events(path: Path, state: DashboardState, poll_interval: float = 0.5) -> None:
    console = Console()
    with Live(render_dashboard(state), console=console, refresh_per_second=4) as live:
        offset = 0
        while True:
            try:
                current_size = path.stat().st_size
                if current_size < offset:
                    offset = 0  # log rotated
                with path.open("r") as handle:
                    handle.seek(offset)
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        offset = handle.tell()
                        payload = line.strip()
                        if not payload:
                            continue
                        try:
                            event = json.loads(payload)
                            state.ingest(event)
                        except json.JSONDecodeError:
                            state.generic_events.appendleft(
                                {"type": "raw", "message": payload[:80], "timestamp": ""}
                            )
                    live.update(render_dashboard(state))
            except FileNotFoundError:
                live.update(Panel(Align.center(f"Waiting for {path} ...", vertical="middle"), border_style="red"))
            except KeyboardInterrupt:
                break
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream orchestrator events in a terminal dashboard.")
    parser.add_argument(
        "--events",
        default="logs/orchestrator_events.jsonl",
        help="Path to structured JSONL events file (default: logs/orchestrator_events.jsonl)",
    )
    parser.add_argument("--poll", type=float, default=0.5, help="Polling interval in seconds")
    args = parser.parse_args()

    path = Path(args.events)
    state = DashboardState()
    tail_events(path, state, poll_interval=args.poll)


if __name__ == "__main__":
    main()
