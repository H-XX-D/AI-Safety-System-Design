from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ProcessStatus(Enum):
    """Status of various processes"""
    VALID = "valid"
    SUSPICIOUS = "suspicious"
    ALERTING = "alerting"


@dataclass
class Message:
    """Inter-system message"""
    from_system: int
    to_system: int
    message_type: str
    content: Dict[str, Any]
    timestamp: str

