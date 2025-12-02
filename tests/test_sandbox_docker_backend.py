import logging
from types import SimpleNamespace

import pytest

from sandbox import SandboxExecutionManager


class DummyContainer:
    def __init__(self, record):
        self._record = record

    def start(self):
        self._record["started"] = True

    def wait(self, timeout=None):
        self._record["wait_timeout"] = timeout
        return {"StatusCode": 0}

    def logs(self, stdout=True, stderr=False):
        if stdout and not stderr:
            return b"stdout"
        if stderr and not stdout:
            return b"stderr"
        return b""

    def stats(self, stream=False):
        return {
            "memory_stats": {"usage": 1024},
            "cpu_stats": {"cpu_usage": {"total_usage": 2048}},
        }

    def remove(self, force=True):
        self._record["removed"] = force


class DummyContainers:
    def __init__(self, record):
        self.record = record

    def create(self, **kwargs):
        self.record["create_kwargs"] = kwargs
        return DummyContainer(self.record)


def test_docker_backend_honors_resource_limits():
    record = {}
    mock_client = SimpleNamespace(containers=DummyContainers(record))
    raw_cfg = {
        "engine": "docker",
        "image": "test-image:latest",
        "exec_timeout_sec": 7,
        "max_memory_mb": 64,
        "pids_limit": 32,
        "cpus": 0.5,
        "disk_quota_mb": 128,
        "workdir": "/sandbox",
    }
    manager = SandboxExecutionManager(mock_client, raw_cfg, logging.getLogger(__name__))
    result = manager.execute_code("print('hello')")
    assert result["engine"] == "docker"
    kwargs = record["create_kwargs"]
    assert kwargs["mem_limit"] == "64m"
    assert kwargs["pids_limit"] == 32
    assert kwargs["nano_cpus"] == 500_000_000
    assert kwargs["storage_opt"] == {"size": "128m"}
    assert record["started"] is True
    assert record["wait_timeout"] == pytest.approx(7)
    assert record["removed"] is True
