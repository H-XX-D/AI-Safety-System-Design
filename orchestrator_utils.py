from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, cast

from control_actions import ControlHooks, DryRunHooks, SystemControlHooks
from control_actions import Severity as PolicySeverity  # re-exported type hint
from deception_incident import Severity as IncidentSeverity


_DECEPTION_SEVERITY_MAP: Dict[IncidentSeverity, PolicySeverity] = {
    IncidentSeverity.LOW: PolicySeverity.LOW,
    IncidentSeverity.MEDIUM: PolicySeverity.MEDIUM,
    IncidentSeverity.HIGH: PolicySeverity.HIGH,
    IncidentSeverity.CRITICAL: PolicySeverity.HIGH,
}


def map_deception_to_policy_severity(deception_severity: IncidentSeverity) -> PolicySeverity:
    return _DECEPTION_SEVERITY_MAP.get(deception_severity, PolicySeverity.LOW)


def build_control_hooks(cfg: Dict[str, Any], docker_client: Any, logger: Any) -> Tuple[ControlHooks, Dict[str, Any]]:
    """Factory for control hooks based on config.

    Returns (hooks, meta) where meta includes researcher list, power nodes, and snapshot seconds.
    """
    control_cfg = cast(Dict[str, Any], cfg.get('control_hooks', {}) or {})
    hook_type = str(control_cfg.get('type', 'system')).strip().lower()
    meta = {
        'researcher_systems': list(control_cfg.get('researcher_systems', [])),
        'power_nodes': list(control_cfg.get('power_nodes', [])),
        'snapshot_seconds': int(control_cfg.get('snapshot_seconds', 2)),
    }
    hooks: Optional[ControlHooks] = None
    if hook_type == 'dry_run':
        hooks = DryRunHooks()
    elif hook_type == 'production':
        try:
            from production_control_hooks import ProductionControlHooks  # type: ignore
            hooks = ProductionControlHooks(
                docker_client=docker_client if control_cfg.get('use_docker_client', True) else None,
                allowed_containers=control_cfg.get('allowed_containers'),
                allowed_processes=control_cfg.get('allowed_processes'),
                snapshot_root=control_cfg.get('snapshot_root'),
                dry_run=bool(control_cfg.get('dry_run', False)),
            )
        except Exception as exc:
            logger.warning("control_hooks_production_init_failed", extra={'error': str(exc)})
            hooks = None

    if hooks is None:
        hooks = SystemControlHooks(
            docker_client=docker_client if control_cfg.get('use_docker_client', True) else None,
            process_timeout=float(control_cfg.get('process_timeout_sec', 5.0)),
            network_interfaces=control_cfg.get('network_interfaces'),
            snapshot_root=control_cfg.get('snapshot_root'),
            power_command=control_cfg.get('power_command'),
            dry_run=bool(control_cfg.get('dry_run', False)),
        )

    return hooks, meta

