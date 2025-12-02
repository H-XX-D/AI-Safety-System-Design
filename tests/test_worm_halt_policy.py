import os
import importlib
import types


def test_worm_halt_on_failure_and_clear(monkeypatch):
    # Simulate production policy (halt_on_failure true)
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('ORCH_SKIP_WORM_HALT', raising=False)

    # Patch worm_manifest.verify_integrity to fail initially
    import security.worm_manifest as wm
    monkeypatch.setattr(wm, 'verify_integrity', lambda: {'verified': False}, raising=False)

    # Reload orchestrator to apply policy
    if 'orchestrator' in importlib.sys.modules:
        importlib.reload(importlib.import_module('orchestrator'))
    from core.orchestrator import Orchestrator
    from core.orchestrator_sandbox import SandboxEnvironmentManager
    from infrastructure.memory_merkle import MemoryStorage

    orch = Orchestrator(MemoryStorage(system_id=1, private_key='k'), environment_manager=SandboxEnvironmentManager())
    assert getattr(orch, '_halted', False) is True

    # Now patch verify_integrity to succeed
    monkeypatch.setattr(wm, 'verify_integrity', lambda: {'verified': True}, raising=False)
    # Clear halt
    still_halted = orch.verify_and_clear_worm_halt()
    assert still_halted is False

