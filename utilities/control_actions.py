"""Control Action Shim
====================

Encapsulates incident response actions behind a stable interface. This shim
plans actions from `improvement_policy.Severity` and executes them via pluggable
hooks. Hooks are stubs in development; production implementations will integrate
with output gating, network isolation, snapshot tooling, and hardware power
controls.
"""
from __future__ import annotations
import time
import logging
import shlex
import subprocess
import json
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence, Union

from research.improvement_policy import Severity, ESCALATION_MATRIX

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - psutil is optional for some environments
    psutil = None  # type: ignore

try:
    import docker  # type: ignore
except ImportError:  # pragma: no cover - docker optional
    docker = None  # type: ignore


logger = logging.getLogger(__name__)


class ControlActionError(RuntimeError):
    """Raised when a control hook is invoked without a concrete implementation."""

    def __init__(self, action: str, guidance: str):
        super().__init__(guidance)
        self.action = action


@dataclass
class ControlPlan:
    severity: Severity
    reason: str
    timestamp: float
    halt_outputs: bool
    attempt_minimal_forensics: bool
    cut_power_researchers: bool
    isolate_networks: bool
    snapshot_seconds: int = 2  # only used when attempt_minimal_forensics is True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


class ControlHooks:
    """Pluggable hooks for executing control actions.

    Replace with production integrations. Return True on success.
    """

    def halt_outputs(self, systems: List[str]) -> bool:
        raise ControlActionError('halt_outputs', 'No output-halting hook configured; provide a ControlHooks implementation with physical gating.')

    def isolate_networks(self) -> bool:
        raise ControlActionError('isolate_networks', 'No network-isolation hook configured; provide integration with switching or SDN controls.')

    def snapshot_forensics(self, seconds: int) -> bool:
        raise ControlActionError('snapshot_forensics', 'No forensic snapshot hook configured; provide snapshot tooling or disable attempt_minimal_forensics.')

    def cut_power(self, nodes: Optional[List[str]] = None) -> bool:
        raise ControlActionError('cut_power', 'No power-cut hook configured; provide integration with rack PDUs before enabling this action.')


class DryRunHooks(ControlHooks):
    """Development hooks that record calls for verification."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def halt_outputs(self, systems: List[str]) -> bool:
        self.calls.append({"fn": "halt_outputs", "systems": list(systems)})
        return True

    def isolate_networks(self) -> bool:
        self.calls.append({"fn": "isolate_networks"})
        return True

    def snapshot_forensics(self, seconds: int) -> bool:
        self.calls.append({"fn": "snapshot_forensics", "seconds": seconds})
        return True

    def cut_power(self, nodes: Optional[List[str]] = None) -> bool:
        self.calls.append({"fn": "cut_power", "nodes": list(nodes) if nodes else []})
        return True


CommandTemplate = Union[str, Sequence[str]]


class CommandControlHooks(ControlHooks):
    """Executes control actions via shell commands.

    Parameters accept either a string (parsed with shlex) or a sequence of
    arguments. Placeholders are formatted with keyword args (e.g. `{systems}` or
    `{seconds}`). On success the command's exit status must be zero.
    """

    def __init__(
        self,
        *,
        halt_command: Optional[CommandTemplate] = None,
        isolate_command: Optional[CommandTemplate] = None,
        snapshot_command: Optional[CommandTemplate] = None,
        cut_power_command: Optional[CommandTemplate] = None,
        timeout: float = 10.0,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self._commands: Dict[str, Optional[CommandTemplate]] = {
            'halt_outputs': halt_command,
            'isolate_networks': isolate_command,
            'snapshot_forensics': snapshot_command,
            'cut_power': cut_power_command,
        }
        self._timeout = timeout
        self._env = env

    def _format_command(self, action: str, template: Optional[CommandTemplate], context: Dict[str, Any]) -> List[str]:
        if template is None:
            raise ControlActionError(action, f"No command configured for {action}; update CommandControlHooks setup.")
        updated_context = {k: v for k, v in context.items()}
        if 'systems' in updated_context and 'systems_csv' not in updated_context:
            updated_context['systems_csv'] = ','.join(updated_context['systems'])
        if 'nodes' in updated_context and 'nodes_csv' not in updated_context:
            updated_context['nodes_csv'] = ','.join(updated_context['nodes'])
        if isinstance(template, str):
            rendered = template.format(**updated_context)
            return shlex.split(rendered)
        return [str(part).format(**updated_context) for part in template]

    def _run(self, action: str, template: Optional[CommandTemplate], context: Dict[str, Any]) -> bool:
        cmd = self._format_command(action, template, context)
        logger.info("control_action_command_run", extra={"action": action, "command": cmd})
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                timeout=self._timeout,
                env=self._env,
            )
        except subprocess.TimeoutExpired:
            logger.error("control_action_command_timeout", extra={"action": action, "command": cmd})
            return False
        if proc.returncode != 0:
            logger.error(
                "control_action_command_failed",
                extra={
                    "action": action,
                    "command": cmd,
                    "returncode": proc.returncode,
                    "stderr": proc.stderr.decode(errors='ignore'),
                },
            )
            return False
        return True

    def halt_outputs(self, systems: List[str]) -> bool:
        return self._run('halt_outputs', self._commands['halt_outputs'], {'systems': list(systems)})

    def isolate_networks(self) -> bool:
        return self._run('isolate_networks', self._commands['isolate_networks'], {})

    def snapshot_forensics(self, seconds: int) -> bool:
        return self._run('snapshot_forensics', self._commands['snapshot_forensics'], {'seconds': seconds})

    def cut_power(self, nodes: Optional[List[str]] = None) -> bool:
        return self._run('cut_power', self._commands['cut_power'], {'nodes': list(nodes) if nodes else []})


class SystemControlHooks(ControlHooks):
    """Host-level control hooks that act on local processes, Docker containers, and network interfaces.

    These hooks are intended for small deployments that lack full production infrastructure.
    By default they run in dry-run mode (log-only) to avoid disruptive actions during testing.
    """

    def __init__(
        self,
        *,
        docker_client: Any = None,
        process_timeout: float = 5.0,
        network_interfaces: Optional[List[str]] = None,
        snapshot_root: Optional[Union[str, Path]] = None,
        power_command: Optional[CommandTemplate] = None,
        dry_run: bool = True,
    ) -> None:
        self.dry_run = dry_run
        self.process_timeout = float(process_timeout)
        self.network_interfaces = list(network_interfaces or [])
        self.snapshot_root = Path(snapshot_root or "./forensics_snapshots")
        self.power_command = power_command
        self._last_systems: List[str] = []
        self._docker_client = docker_client or self._init_docker_client()

    def _init_docker_client(self) -> Optional[Any]:
        if docker is None:
            return None
        try:
            return docker.from_env()
        except Exception:
            logger.warning("system_control_hooks_docker_init_failed", exc_info=True)
            return None

    def halt_outputs(self, systems: List[str]) -> bool:
        self._last_systems = list(systems)
        if self.dry_run:
            logger.warning("control_hooks.dry_run_halt_outputs", extra={"systems": systems})
            return True

        ok = True
        for name in systems:
            if self._stop_docker_container(name):
                continue
            if self._terminate_process(name):
                continue
            logger.error("control_hooks.halt_failed", extra={"system": name})
            ok = False
        return ok

    def isolate_networks(self) -> bool:
        targets = self.network_interfaces or self._last_systems
        if not targets:
            logger.warning("control_hooks.no_network_targets")
            return True if self.dry_run else False

        if self.dry_run:
            logger.warning("control_hooks.dry_run_isolate", extra={"targets": targets})
            return True

        ok = True
        for iface in targets:
            if not self._disable_interface(iface):
                ok = False
        return ok

    def snapshot_forensics(self, seconds: int) -> bool:
        snapshot_dir = self.snapshot_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if self.dry_run:
            logger.warning("control_hooks.dry_run_snapshot", extra={"path": str(snapshot_dir), "seconds": seconds})
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            return True

        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("control_hooks.snapshot_dir_failed", extra={"path": str(snapshot_dir), "error": str(exc)})
            return False

        metadata = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "seconds": seconds,
            "systems": list(self._last_systems),
        }
        try:
            (snapshot_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
            self._write_process_snapshot(snapshot_dir)
            self._write_netstat(snapshot_dir)
        except Exception as exc:
            logger.error("control_hooks.snapshot_failed", extra={"error": str(exc)})
            return False
        return True

    def cut_power(self, nodes: Optional[List[str]] = None) -> bool:
        nodes = nodes or []
        if self.dry_run:
            logger.warning("control_hooks.dry_run_cut_power", extra={"nodes": nodes})
            return True
        if self.power_command is None:
            raise ControlActionError('cut_power', 'power_command not configured for SystemControlHooks')
        context = {'nodes': nodes, 'nodes_csv': ','.join(nodes)}
        return self._run_command('cut_power', self.power_command, context)

    def _stop_docker_container(self, name: str) -> bool:
        client = self._docker_client
        if client is None:
            return False
        try:
            container = client.containers.get(name)
        except Exception:
            return False
        try:
            container.stop(timeout=int(self.process_timeout))
            return True
        except Exception:
            logger.error("control_hooks.docker_stop_failed", extra={"container": name}, exc_info=True)
            return False

    def _terminate_process(self, identifier: str) -> bool:
        if psutil is None:
            logger.warning("control_hooks.psutil_missing")
            return False
        matched = False
        for proc in psutil.process_iter(["name", "pid", "cmdline"]):  # pragma: no cover - depends on host processes
            try:
                name = proc.info.get("name") or ""
                pid = proc.info.get("pid")
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if identifier not in {name, str(pid)} and identifier not in cmdline:
                    continue
                matched = True
                proc.terminate()
                try:
                    proc.wait(self.process_timeout)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return matched

    def _disable_interface(self, iface: str) -> bool:
        ip_cmd = shutil.which("ip")
        if_cmd = shutil.which("ifconfig")
        if ip_cmd:
            cmd = [ip_cmd, "link", "set", iface, "down"]
        elif if_cmd:
            cmd = [if_cmd, iface, "down"]
        else:
            logger.error("control_hooks.no_network_tools")
            return False
        return self._run_command('isolate_networks', cmd, {'targets': [iface]})

    def _write_process_snapshot(self, dest: Path) -> None:
        if psutil is None:
            (dest / "processes.txt").write_text("psutil not available\n")
            return
        lines = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "cmdline"]):
            info = proc.info
            line = f"{info.get('pid')} {info.get('name')} cpu={info.get('cpu_percent')} mem={info.get('memory_percent')} cmd={' '.join(info.get('cmdline') or [])}"
            lines.append(line.strip())
        (dest / "processes.txt").write_text("\n".join(lines))

    def _write_netstat(self, dest: Path) -> None:
        netstat_cmd = shutil.which("ss") or shutil.which("netstat")
        if not netstat_cmd:
            (dest / "network.txt").write_text("No ss/netstat command available\n")
            return
        try:
            output = subprocess.run(
                [netstat_cmd, "-tupan"],
                capture_output=True,
                check=False,
                timeout=5,
            )
            text = output.stdout.decode(errors='ignore')
        except Exception as exc:  # pragma: no cover - host specific
            text = f"Failed to capture network state: {exc}"
        (dest / "network.txt").write_text(text)

    def _run_command(self, action: str, template: CommandTemplate, context: Dict[str, Any]) -> bool:
        if isinstance(template, str):
            cmd = shlex.split(template.format(**context))
        else:
            cmd = [str(part).format(**context) for part in template]
        try:
            proc = subprocess.run(cmd, capture_output=True, check=False, timeout=self.process_timeout)
        except subprocess.TimeoutExpired:
            logger.error("control_hooks.command_timeout", extra={"action": action, "command": cmd})
            return False
        if proc.returncode != 0:
            logger.error(
                "control_hooks.command_failed",
                extra={"action": action, "command": cmd, "stderr": proc.stderr.decode(errors='ignore')},
            )
            return False
        return True


@dataclass
class ExecutionReport:
    plan: ControlPlan
    success: bool
    steps: List[Dict[str, Any]]


def plan_for_severity(severity: Severity, reason: str, snapshot_seconds: int = 2) -> ControlPlan:
    policy = ESCALATION_MATRIX[severity]
    return ControlPlan(
        severity=severity,
        reason=reason,
        timestamp=time.time(),
        halt_outputs=policy.halt_outputs,
        attempt_minimal_forensics=policy.attempt_minimal_forensics,
        cut_power_researchers=policy.cut_power_researchers,
        isolate_networks=policy.isolate_networks,
        snapshot_seconds=snapshot_seconds,
    )


def _record_step(steps: List[Dict[str, Any]], *, action: str, success: bool, metadata: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    entry: Dict[str, Any] = {"action": action, "ok": bool(success)}
    if metadata:
        entry.update(metadata)
    if error:
        entry["error"] = error
    steps.append(entry)


def _invoke(action: str, func, *, steps: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> bool:
    try:
        result = bool(func())
    except ControlActionError as exc:
        message = f"{action} unavailable: {exc}"
        logger.error("control_action_missing_hook", extra={"action": action, "error": str(exc)})
        _record_step(steps, action=action, success=False, metadata=metadata, error=message)
        return False
    except Exception as exc:  # pragma: no cover - defensive path
        message = f"{action} raised {exc.__class__.__name__}: {exc}"
        logger.exception("control_action_exception", extra={"action": action})
        _record_step(steps, action=action, success=False, metadata=metadata, error=message)
        return False

    if not result:
        logger.error("control_action_hook_reported_failure", extra={"action": action})
        _record_step(steps, action=action, success=False, metadata=metadata, error=f"{action} hook reported failure")
        return False

    _record_step(steps, action=action, success=True, metadata=metadata)
    return True


def execute_plan(plan: ControlPlan, hooks: ControlHooks, researcher_systems: Optional[List[str]] = None, power_nodes: Optional[List[str]] = None) -> ExecutionReport:
    steps: List[Dict[str, Any]] = []
    ok = True

    if plan.halt_outputs and researcher_systems:
        ok = _invoke(
            "halt_outputs",
            lambda: hooks.halt_outputs(researcher_systems),
            steps=steps,
            metadata={"systems": list(researcher_systems)},
        ) and ok

    if plan.isolate_networks:
        ok = _invoke("isolate_networks", hooks.isolate_networks, steps=steps) and ok

    if plan.attempt_minimal_forensics and plan.snapshot_seconds > 0:
        ok = _invoke(
            "snapshot_forensics",
            lambda: hooks.snapshot_forensics(plan.snapshot_seconds),
            steps=steps,
            metadata={"seconds": plan.snapshot_seconds},
        ) and ok

    if plan.cut_power_researchers:
        ok = _invoke(
            "cut_power",
            lambda: hooks.cut_power(power_nodes),
            steps=steps,
            metadata={"nodes": list(power_nodes) if power_nodes else []},
        ) and ok

    return ExecutionReport(plan=plan, success=ok, steps=steps)


__all__ = [
    "ControlPlan",
    "ControlHooks",
    "ControlActionError",
    "DryRunHooks",
    "CommandControlHooks",
    "SystemControlHooks",
    "ExecutionReport",
    "plan_for_severity",
    "execute_plan",
]
