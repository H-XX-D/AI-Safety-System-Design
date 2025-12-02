from research.improvement_policy import Severity
from utilities.control_actions import (
    plan_for_severity,
    DryRunHooks,
    CommandControlHooks,
    SystemControlHooks,
    execute_plan,
)


def test_plan_low_has_no_actions():
    plan = plan_for_severity(Severity.LOW, reason="minor anomaly")
    assert plan.halt_outputs is False
    assert plan.attempt_minimal_forensics is False
    assert plan.cut_power_researchers is False
    assert plan.isolate_networks is False


def test_plan_medium_actions():
    plan = plan_for_severity(Severity.MEDIUM, reason="suspicious spike")
    assert plan.halt_outputs is True
    assert plan.attempt_minimal_forensics is True
    assert plan.cut_power_researchers is False
    assert plan.isolate_networks is True


def test_plan_high_actions():
    plan = plan_for_severity(Severity.HIGH, reason="translator-confirmed deception")
    assert plan.halt_outputs is True
    assert plan.attempt_minimal_forensics is False
    assert plan.cut_power_researchers is True
    assert plan.isolate_networks is True


def test_execute_plan_calls_hooks_per_severity():
    systems = ["scientific", "engineering", "theoretical", "historical", "novel"]
    nodes = ["dgx1", "dgx2", "dgx3", "dgx4", "dgx5"]

    # MEDIUM: halt outputs + isolate + snapshot; no power cut
    hooks = DryRunHooks()
    plan = plan_for_severity(Severity.MEDIUM, reason="suspicious spike", snapshot_seconds=2)
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is True
    called = [c["fn"] for c in hooks.calls]
    assert called == ["halt_outputs", "isolate_networks", "snapshot_forensics"]

    # HIGH: halt outputs + isolate + power cut; no snapshot
    hooks = DryRunHooks()
    plan = plan_for_severity(Severity.HIGH, reason="translator-confirmed deception")
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is True
    called = [c["fn"] for c in hooks.calls]
    assert called == ["halt_outputs", "isolate_networks", "cut_power"]

    # LOW: no actions
    hooks = DryRunHooks()
    plan = plan_for_severity(Severity.LOW, reason="minor anomaly")
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is True
    assert hooks.calls == []


def test_command_hooks_run_shell_commands(monkeypatch):
    systems = ["alpha", "beta"]
    nodes = ["n1"]
    script = "import sys; sys.exit(0)"
    cmd = ["python3", "-c", script]
    hooks = CommandControlHooks(
        halt_command=cmd,
        isolate_command=cmd,
        snapshot_command=cmd,
        cut_power_command=cmd,
        timeout=2.0,
    )
    plan = plan_for_severity(Severity.HIGH, reason="critical deception")
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is True
    assert len(report.steps) == 3


def test_missing_command_yields_error(monkeypatch):
    systems = ["alpha"]
    nodes = ["n1"]
    cmd = ["python3", "-c", "import sys; sys.exit(0)"]
    hooks = CommandControlHooks(
        halt_command=None,
        isolate_command=cmd,
        snapshot_command=cmd,
        cut_power_command=cmd,
        timeout=1.0,
    )
    plan = plan_for_severity(Severity.MEDIUM, reason="suspicious spike", snapshot_seconds=1)
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is False
    first = report.steps[0]
    assert first['action'] == 'halt_outputs'
    assert first['ok'] is False
    assert 'No command configured' in first['error']


def test_system_control_hooks_dry_run(tmp_path):
    systems = ["alpha"]
    nodes = ["node1"]
    hooks = SystemControlHooks(
        dry_run=True,
        network_interfaces=["lo"],
        snapshot_root=tmp_path,
    )
    plan = plan_for_severity(Severity.MEDIUM, reason="dry-run test", snapshot_seconds=1)
    report = execute_plan(plan, hooks, researcher_systems=systems, power_nodes=nodes)
    assert report.success is True
    contents = list(tmp_path.iterdir())
    assert contents, "snapshot directory should be created in dry-run mode"
