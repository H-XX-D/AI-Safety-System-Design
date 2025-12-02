import os


def test_sandbox_limits_follow_config_dev(monkeypatch):
    # Development defaults from config/development.yaml
    monkeypatch.setenv('APP_ENV', 'development')
    from core.orchestrator_sandbox import SandboxEnvironmentManager
    s = SandboxEnvironmentManager()
    # Values from development.yaml
    assert s.exec_timeout_sec == 10
    assert s.cpu_time_sec == 3
    # MB to KB conversion
    assert s.max_memory_kb == 256 * 1024


def test_sandbox_limits_follow_config_prod(monkeypatch):
    # Production values from config/production.yaml
    monkeypatch.setenv('APP_ENV', 'production')
    from core.orchestrator_sandbox import SandboxEnvironmentManager
    s = SandboxEnvironmentManager()
    assert s.exec_timeout_sec == 3
    assert s.cpu_time_sec == 1
    assert s.max_memory_kb == 64 * 1024

