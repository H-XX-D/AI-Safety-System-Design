import importlib

from config_loader import load_config


def test_production_config_sandbox_block(monkeypatch):
    """Production profile ships strict sandbox defaults."""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    cfg = load_config()
    sandbox = cfg['sandbox']

    assert sandbox['exec_timeout_sec'] == 3
    assert sandbox['cpu_time_sec'] == 1
    assert sandbox['max_memory_mb'] == 64
    assert sandbox['use_virtual_manager'] is True
    assert sandbox['policy_allowlists']['default'] == ['math', 'statistics', 'json']


def test_production_sandbox_manager_applies_limits(monkeypatch):
    """SandboxEnvironmentManager mirrors production config values."""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    import orchestrator_sandbox

    importlib.reload(orchestrator_sandbox)
    mgr = orchestrator_sandbox.SandboxEnvironmentManager()

    assert mgr.exec_timeout_sec == 3.0
    assert mgr.cpu_time_sec == 1.0
    assert mgr.max_memory_kb == 64 * 1024
    assert mgr.use_virtual_manager is True
    assert mgr.policy_allowlists['default'] == {'math', 'statistics', 'json'}


def test_env_flag_overrides_virtual_manager(monkeypatch):
    """SANDBOX_USE_VIRTUAL has precedence over config file."""
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('SANDBOX_USE_VIRTUAL', '0')

    import orchestrator_sandbox

    importlib.reload(orchestrator_sandbox)
    mgr = orchestrator_sandbox.SandboxEnvironmentManager()

    assert mgr.use_virtual_manager is False


def test_default_profile_sandbox_defaults(monkeypatch):
    """Default profile keeps deterministic sandbox with baseline allowlist."""
    monkeypatch.setenv('APP_ENV', 'default')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    cfg = load_config()
    sandbox = cfg['sandbox']

    assert sandbox['exec_timeout_sec'] == 5
    assert sandbox['cpu_time_sec'] == 2
    assert sandbox['max_memory_mb'] == 128
    assert sandbox['use_virtual_manager'] is False
    assert sandbox['policy_allowlists']['dummy_component'] == ['math', 'json', 'datetime']


def test_default_sandbox_manager_allowlists(monkeypatch):
    """Manager seeded from default config exposes configured allowlists."""
    monkeypatch.setenv('APP_ENV', 'default')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    import orchestrator_sandbox

    importlib.reload(orchestrator_sandbox)
    mgr = orchestrator_sandbox.SandboxEnvironmentManager()

    assert mgr.use_virtual_manager is False
    assert mgr.policy_allowlists['dummy_component'] == {'math', 'json', 'datetime'}


def test_development_profile_relaxed_limits(monkeypatch):
    """Development profile keeps relaxed runtime limits and delegation."""
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    cfg = load_config()
    sandbox = cfg['sandbox']

    assert sandbox['exec_timeout_sec'] == 10
    assert sandbox['cpu_time_sec'] == 3
    assert sandbox['max_memory_mb'] == 256
    assert sandbox['use_virtual_manager'] is True
    assert sandbox['policy_allowlists']['demo_component'] == ['math', 'json', 'datetime']


def test_development_sandbox_manager_settings(monkeypatch):
    """SandboxEnvironmentManager honors development overrides."""
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('SANDBOX_USE_VIRTUAL', raising=False)

    import orchestrator_sandbox

    importlib.reload(orchestrator_sandbox)
    mgr = orchestrator_sandbox.SandboxEnvironmentManager()

    assert mgr.exec_timeout_sec == 10.0
    assert mgr.cpu_time_sec == 3.0
    assert mgr.max_memory_kb == 256 * 1024
    assert mgr.use_virtual_manager is True
    assert mgr.policy_allowlists['demo_component'] == {'math', 'json', 'datetime'}
