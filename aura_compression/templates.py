"""Minimal template library compatible with the tests.

The real project ships a very large immutable library; for the purposes of the
unit tests we only need a predictable, read-only mapping that can return a
human-readable pattern for a handful of structured messages.
"""
from __future__ import annotations

from typing import Dict, Optional


class TemplateLibrary:
    """Tiny read-only template library."""

    def __init__(self) -> None:
        self._templates: Dict[int, str] = {
            0: "{slot0}",
            1: "System {system} approves proposal {proposal}",
            2: "System {system} rejects proposal {proposal}",
            3: "System {system} reviews proposal {proposal} with {confidence} confidence",
        }

    def get(self, template_id: int) -> Optional[str]:
        """Return a template pattern if known."""
        return self._templates.get(int(template_id))

    def list_templates(self) -> Dict[int, str]:  # pragma: no cover - diagnostic helper
        return dict(self._templates)
