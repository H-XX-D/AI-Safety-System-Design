import logging

from control_actions import DryRunHooks, SystemControlHooks
from deception_incident import Severity as IncidentSeverity
from improvement_policy import Severity as PolicySeverity

from orchestrator import _map_deception_to_policy_severity, _build_control_hooks


def test_map_deception_to_policy_severity():
    assert _map_deception_to_policy_severity(IncidentSeverity.LOW) == PolicySeverity.LOW
    assert _map_deception_to_policy_severity(IncidentSeverity.MEDIUM) == PolicySeverity.MEDIUM
    assert _map_deception_to_policy_severity(IncidentSeverity.HIGH) == PolicySeverity.HIGH
    # CRITICAL should map to the highest plan we support (HIGH)
    assert _map_deception_to_policy_severity(IncidentSeverity.CRITICAL) == PolicySeverity.HIGH


def test_build_control_hooks_dry_run():
    cfg = {"control_hooks": {"type": "dry_run", "snapshot_seconds": 5}}
    hooks, meta = _build_control_hooks(cfg, docker_client=None, logger=logging.getLogger(__name__))
    assert isinstance(hooks, DryRunHooks)
    assert meta["snapshot_seconds"] == 5


def test_build_control_hooks_system(monkeypatch):
    cfg = {
        "control_hooks": {
            "type": "system",
            "dry_run": True,
            "process_timeout_sec": 3,
            "network_interfaces": ["eth0"],
            "researcher_systems": ["alpha"],
            "power_nodes": ["pdu1"],
            "snapshot_seconds": 4,
        }
    }
    hooks, meta = _build_control_hooks(cfg, docker_client=None, logger=logging.getLogger(__name__))
    assert isinstance(hooks, SystemControlHooks)
    assert meta["researcher_systems"] == ["alpha"]
    assert meta["power_nodes"] == ["pdu1"]
    assert meta["snapshot_seconds"] == 4
