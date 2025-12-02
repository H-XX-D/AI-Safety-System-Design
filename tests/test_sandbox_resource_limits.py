import logging

from sandbox import HostCgroupLimiter
from sandbox.isolation import SandboxConfig


def test_sandbox_config_resource_limits():
    raw = {
        "engine": "docker",
        "cpus": 1.5,
        "cpu_shares": 512,
        "disk_quota_mb": 256,
        "max_memory_mb": 64,
        "pids_limit": 64,
    }
    cfg = SandboxConfig.from_dict(raw)
    assert cfg.cpus == 1.5
    assert cfg.cpu_shares == 512
    assert cfg.disk_quota_mb == 256
    assert cfg.max_memory_mb == 64
    assert cfg.pids_limit == 64


def test_host_cgroup_limiter(tmp_path):
    logger = logging.getLogger(__name__)
    limiter = HostCgroupLimiter(
        memory_max_bytes=2048,
        cpu_max_usec=200000,
        pids_max=8,
        logger=logger,
        root=tmp_path,
    )
    assert limiter.create() is True
    limiter.attach(1234)
    memory_file = limiter.path / "memory.max"  # type: ignore[union-attr]
    cpu_file = limiter.path / "cpu.max"  # type: ignore[union-attr]
    pids_file = limiter.path / "pids.max"  # type: ignore[union-attr]
    procs_file = limiter.path / "cgroup.procs"  # type: ignore[union-attr]
    assert memory_file.read_text() == "2048"
    assert cpu_file.read_text() == "200000 100000"
    assert pids_file.read_text() == "8"
    assert procs_file.read_text() == "1234"
    limiter.cleanup()
    assert limiter.path is None
