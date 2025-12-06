#!/usr/bin/env python3
"""
Structured Logging and Observability for ORKASTRATOR
=====================================================

Provides:
- Structured JSON logging for all workflow steps
- Alert generation for safety failures
- Sandbox fallback detection
- Model mismatch warnings
"""

import json
import time
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    ALERT = "ALERT"  # Special level for safety alerts


class EventType(Enum):
    """Types of logged events."""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    SAFETY_CHECK = "safety_check"
    SAFETY_FAILURE = "safety_failure"
    SANDBOX_EXECUTION = "sandbox_execution"
    SANDBOX_FALLBACK = "sandbox_fallback"
    MODEL_MISMATCH = "model_mismatch"
    NODE_HEALTH = "node_health"
    DEPLOYMENT = "deployment"
    ROLLBACK = "rollback"
    HUMAN_APPROVAL = "human_approval"
    SIGNATURE_VERIFICATION = "signature_verification"
    EVAL_RESULT = "eval_result"


@dataclass
class LogEntry:
    """A structured log entry."""
    timestamp: str
    level: str
    event_type: str
    message: str
    workflow_id: Optional[str] = None
    step: Optional[int] = None
    proposer: Optional[str] = None
    node: Optional[str] = None
    data: Optional[Dict] = None
    alert: bool = False
    
    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class StructuredLogger:
    """Structured JSON logger with alerting."""
    
    def __init__(
        self,
        name: str = "orkastrator",
        log_path: Optional[Path] = None,
        alert_callback: Optional[callable] = None
    ):
        self.name = name
        self.log_path = log_path or Path.home() / ".orkastrator" / "logs" / f"{name}.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.alert_callback = alert_callback
        
        # Current workflow context
        self._workflow_id: Optional[str] = None
        self._proposer: Optional[str] = None
        
        # Also set up standard logging
        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s'
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)
    
    def set_workflow_context(self, workflow_id: str, proposer: str):
        """Set current workflow context for all subsequent logs."""
        self._workflow_id = workflow_id
        self._proposer = proposer
    
    def clear_workflow_context(self):
        """Clear workflow context."""
        self._workflow_id = None
        self._proposer = None
    
    def _log(
        self,
        level: LogLevel,
        event_type: EventType,
        message: str,
        step: Optional[int] = None,
        node: Optional[str] = None,
        data: Optional[Dict] = None,
        alert: bool = False
    ):
        """Write a structured log entry."""
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level.value,
            event_type=event_type.value,
            message=message,
            workflow_id=self._workflow_id,
            step=step,
            proposer=self._proposer,
            node=node,
            data=data,
            alert=alert,
        )
        
        # Write to file
        with open(self.log_path, "a") as f:
            f.write(entry.to_json() + "\n")
        
        # Standard logging
        log_msg = f"[{event_type.value}] {message}"
        if step is not None:
            log_msg = f"[Step {step}] {log_msg}"
        
        if level == LogLevel.DEBUG:
            self._logger.debug(log_msg)
        elif level == LogLevel.INFO:
            self._logger.info(log_msg)
        elif level == LogLevel.WARNING:
            self._logger.warning(log_msg)
        elif level in (LogLevel.ERROR, LogLevel.CRITICAL, LogLevel.ALERT):
            self._logger.error(log_msg)
        
        # Trigger alert callback if needed
        if alert and self.alert_callback:
            self.alert_callback(entry)
    
    # Convenience methods
    def workflow_start(self, workflow_id: str, proposer: str, data: Dict = None):
        """Log workflow start."""
        self.set_workflow_context(workflow_id, proposer)
        self._log(
            LogLevel.INFO,
            EventType.WORKFLOW_START,
            f"Workflow {workflow_id} started by {proposer}",
            data=data,
        )
    
    def workflow_end(self, success: bool, data: Dict = None):
        """Log workflow end."""
        self._log(
            LogLevel.INFO if success else LogLevel.WARNING,
            EventType.WORKFLOW_END,
            f"Workflow completed: {'SUCCESS' if success else 'FAILED'}",
            data=data,
        )
        self.clear_workflow_context()
    
    def step_start(self, step: int, name: str):
        """Log step start."""
        self._log(
            LogLevel.INFO,
            EventType.STEP_START,
            f"Step {step}: {name}",
            step=step,
        )
    
    def step_end(self, step: int, success: bool, data: Dict = None):
        """Log step end."""
        self._log(
            LogLevel.INFO if success else LogLevel.WARNING,
            EventType.STEP_END,
            f"Step {step} {'completed' if success else 'failed'}",
            step=step,
            data=data,
        )
    
    def safety_check(self, content_preview: str, result: bool, details: str = None):
        """Log safety check."""
        level = LogLevel.INFO if result else LogLevel.ALERT
        self._log(
            level,
            EventType.SAFETY_CHECK if result else EventType.SAFETY_FAILURE,
            f"Safety check: {'PASS' if result else 'FAIL'}",
            data={"content_preview": content_preview[:100], "details": details},
            alert=not result,
        )

    def safety_failure(self, content_preview: str, reason: str):
        """Log a safety failure (convenience method)."""
        self._log(
            LogLevel.ALERT,
            EventType.SAFETY_FAILURE,
            f"Safety FAILURE: {reason}",
            data={"content_preview": content_preview[:100], "reason": reason},
            alert=True,
        )
    
    def sandbox_execution(self, engine: str, success: bool, output: str = None):
        """Log sandbox execution."""
        self._log(
            LogLevel.INFO if success else LogLevel.WARNING,
            EventType.SANDBOX_EXECUTION,
            f"Sandbox ({engine}): {'SUCCESS' if success else 'FAILED'}",
            data={"output": output[:500] if output else None},
        )
    
    def sandbox_fallback(self, reason: str):
        """Log sandbox fallback (ALERT)."""
        self._log(
            LogLevel.ALERT,
            EventType.SANDBOX_FALLBACK,
            f"Sandbox fallback triggered: {reason}",
            data={"reason": reason},
            alert=True,
        )
    
    def model_mismatch(self, node: str, expected: str, actual: str):
        """Log model mismatch (ALERT)."""
        self._log(
            LogLevel.ALERT,
            EventType.MODEL_MISMATCH,
            f"Model mismatch on {node}: expected {expected}, got {actual}",
            node=node,
            data={"expected": expected, "actual": actual},
            alert=True,
        )
    
    def node_health(self, node: str, online: bool, model_loaded: bool):
        """Log node health check."""
        self._log(
            LogLevel.INFO if online and model_loaded else LogLevel.WARNING,
            EventType.NODE_HEALTH,
            f"Node {node}: {'online' if online else 'offline'}, model {'loaded' if model_loaded else 'not loaded'}",
            node=node,
            data={"online": online, "model_loaded": model_loaded},
        )
    
    def deployment(
        self,
        artifact_id: str,
        improvement_type: str,
        nodes: List[str],
        success_count: int
    ):
        """Log deployment."""
        self._log(
            LogLevel.INFO,
            EventType.DEPLOYMENT,
            f"Deployed {artifact_id} ({improvement_type}) to {success_count}/{len(nodes)} nodes",
            data={
                "artifact_id": artifact_id,
                "improvement_type": improvement_type,
                "nodes": nodes,
                "success_count": success_count,
            },
        )
    
    def rollback(self, version_id: int, reason: str, success: bool):
        """Log rollback."""
        self._log(
            LogLevel.WARNING,
            EventType.ROLLBACK,
            f"Rollback to v{version_id}: {'SUCCESS' if success else 'FAILED'} - {reason}",
            data={"version_id": version_id, "reason": reason},
            alert=not success,
        )
    
    def human_approval(self, approved: bool, approver: str, notes: str = None):
        """Log human approval decision."""
        self._log(
            LogLevel.INFO,
            EventType.HUMAN_APPROVAL,
            f"Human approval: {'APPROVED' if approved else 'REJECTED'} by {approver}",
            data={"approved": approved, "approver": approver, "notes": notes},
        )
    
    def signature_verification(self, artifact_id: str, valid: bool, signer: str):
        """Log signature verification."""
        level = LogLevel.INFO if valid else LogLevel.ALERT
        self._log(
            level,
            EventType.SIGNATURE_VERIFICATION,
            f"Signature for {artifact_id}: {'VALID' if valid else 'INVALID'} (signer: {signer})",
            data={"artifact_id": artifact_id, "valid": valid, "signer": signer},
            alert=not valid,
        )
    
    def eval_result(self, test_suite_id: str, passed: bool, score: float, categories: Dict):
        """Log evaluation result."""
        self._log(
            LogLevel.INFO if passed else LogLevel.WARNING,
            EventType.EVAL_RESULT,
            f"Evaluation {test_suite_id}: {'PASS' if passed else 'FAIL'} (score: {score:.1f})",
            data={"test_suite_id": test_suite_id, "passed": passed, "score": score, "categories": categories},
        )


class AlertManager:
    """Manage alerts and notifications."""
    
    def __init__(self, alert_file: Optional[Path] = None):
        self.alert_file = alert_file or Path.home() / ".orkastrator" / "alerts.jsonl"
        self.alert_file.parent.mkdir(parents=True, exist_ok=True)
        self._handlers: List[callable] = []
    
    def add_handler(self, handler: callable):
        """Add an alert handler."""
        self._handlers.append(handler)
    
    def send_alert(self, entry: LogEntry):
        """Send an alert."""
        # Write to alert file
        with open(self.alert_file, "a") as f:
            f.write(entry.to_json() + "\n")
        
        # Call handlers
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception as e:
                print(f"Alert handler error: {e}")
        
        # Print to console with emphasis
        print(f"\n{'='*60}")
        print(f"⚠️  ALERT: {entry.message}")
        print(f"    Event: {entry.event_type}")
        print(f"    Time: {entry.timestamp}")
        if entry.data:
            print(f"    Data: {json.dumps(entry.data, indent=4)}")
        print(f"{'='*60}\n")
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts."""
        alerts = []
        if self.alert_file.exists():
            with open(self.alert_file) as f:
                for line in f:
                    try:
                        alerts.append(json.loads(line))
                    except:
                        pass
        return alerts[-limit:]


# Global instances
_logger: Optional[StructuredLogger] = None
_alert_manager: Optional[AlertManager] = None


def get_logger() -> StructuredLogger:
    """Get the structured logger."""
    global _logger, _alert_manager
    if _logger is None:
        _alert_manager = AlertManager()
        _logger = StructuredLogger(alert_callback=_alert_manager.send_alert)
    return _logger


def get_alert_manager() -> AlertManager:
    """Get the alert manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


if __name__ == "__main__":
    # Demo
    logger = get_logger()
    
    # Simulate a workflow
    logger.workflow_start("wf_001", "GIN", {"improvement_type": "prompt_template"})
    
    logger.step_start(1, "Generate Idea")
    logger.step_end(1, True, {"idea": "Improve system prompt"})
    
    logger.safety_check("Test content...", True, "All checks passed")
    logger.sandbox_execution("SandboxFusion/Docker", True, "Output: success")
    
    # Simulate an alert
    logger.safety_check("Dangerous content...", False, "Contains unsafe pattern")
    
    logger.workflow_end(True, {"score": 85.0})
    
    print("\n=== Recent Alerts ===")
    alerts = get_alert_manager().get_recent_alerts()
    for a in alerts:
        print(f"  {a['timestamp']}: {a['message']}")
