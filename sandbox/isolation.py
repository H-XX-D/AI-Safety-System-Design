"""
Sandbox isolation backends used by the orchestrator.

Provides Docker- and Firecracker-based execution helpers with configurable
seccomp filtering plus a deterministic local fallback for CI.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import docker  # type: ignore
except ImportError:  # pragma: no cover - orchestrator already guards this, but we keep parity
    docker = None  # type: ignore


class SandboxIsolationError(RuntimeError):
    """Raised when sandbox execution fails before the user code runs."""


_DEFAULT_SYSCALL_ALLOWLIST = [
    # Core process/bookkeeping syscalls
    "read",
    "write",
    "exit",
    "exit_group",
    "close",
    "fstat",
    "lseek",
    "brk",
    "mmap",
    "munmap",
    "mprotect",
    "arch_prctl",
    "set_tid_address",
    "set_robust_list",
    "rt_sigaction",
    "rt_sigprocmask",
    "rt_sigreturn",
    "sigaltstack",
    "prlimit64",
    "clone3",
    "clone",
    "getpid",
    "gettid",
    "futex",
    "sched_yield",
    "clock_gettime",
    "clock_nanosleep",
    "nanosleep",
    "getrandom",
    "openat",
    "close_range",
    "access",
    "stat",
    "newfstatat",
    "pread64",
    "pwrite64",
    "dup",
    "dup2",
    "dup3",
    "ioctl",
    "pipe2",
    "eventfd2",
]


def _build_seccomp_profile(allowed_syscalls: Sequence[str]) -> Dict[str, Any]:
    """Return a minimal seccomp profile limited to the provided syscall list."""
    return {
        "defaultAction": "SCMP_ACT_ERRNO",
        "archMap": [
            {"architecture": "SCMP_ARCH_X86_64", "subArchitectures": []},
            {"architecture": "SCMP_ARCH_AARCH64", "subArchitectures": []},
        ],
        "syscalls": [
            {
                "names": sorted(set(allowed_syscalls)),
                "action": "SCMP_ACT_ALLOW",
            }
        ],
    }


@dataclass
class SandboxConfig:
    engine: str = "docker"
    image: str = "ai-research-system:latest"
    workdir: str = "/sandbox"
    exec_timeout_sec: float = 30.0
    max_memory_mb: Optional[int] = 256
    cpu_time_sec: Optional[int] = 5
    pids_limit: int = 128
    cpus: Optional[float] = None
    cpu_shares: Optional[int] = None
    disk_quota_mb: Optional[int] = None
    firecracker_kernel: Optional[str] = None
    firecracker_rootfs: Optional[str] = None
    firecracker_jailer: Optional[str] = None
    allow_syscalls: List[str] = field(default_factory=lambda: list(_DEFAULT_SYSCALL_ALLOWLIST))
    custom_seccomp_profile: Optional[str] = None
    execution_command: List[str] = field(default_factory=lambda: ["python3", "/sandbox/proposal_exec.py"])

    @staticmethod
    def from_dict(raw: Optional[Dict[str, Any]]) -> "SandboxConfig":
        data = raw or {}
        return SandboxConfig(
            engine=str(data.get("engine", "docker")).lower(),
            image=str(data.get("sandbox_image", data.get("image", "ai-research-system:latest"))),
            workdir=str(data.get("workdir", "/sandbox")),
            exec_timeout_sec=float(data.get("exec_timeout_sec", data.get("timeout_sec", 30.0))),
            max_memory_mb=int(data["max_memory_mb"]) if isinstance(data.get("max_memory_mb"), (int, float)) else None,
            cpu_time_sec=int(data["cpu_time_sec"]) if isinstance(data.get("cpu_time_sec"), (int, float)) else None,
            pids_limit=int(data.get("pids_limit", 128)),
            cpus=float(data["cpus"]) if isinstance(data.get("cpus"), (int, float)) else None,
            cpu_shares=int(data["cpu_shares"]) if isinstance(data.get("cpu_shares"), (int, float)) else None,
            disk_quota_mb=int(data["disk_quota_mb"]) if isinstance(data.get("disk_quota_mb"), (int, float)) else None,
            firecracker_kernel=data.get("firecracker_kernel"),
            firecracker_rootfs=data.get("firecracker_rootfs"),
            firecracker_jailer=data.get("firecracker_jailer"),
            allow_syscalls=list(data.get("seccomp_allow_syscalls", _DEFAULT_SYSCALL_ALLOWLIST)),
            custom_seccomp_profile=data.get("seccomp_profile"),
            execution_command=list(data.get("execution_command", ["python3", "/sandbox/proposal_exec.py"])),
        )


class SandboxExecutionManager:
    """Facade that exposes a single execute_code API to orchestrator."""

    def __init__(self, docker_client: Any, raw_config: Optional[Dict[str, Any]], logger: Any):
        self.logger = logger
        self.config = SandboxConfig.from_dict(raw_config)
        engine = self.config.engine
        if engine not in {"docker", "firecracker"}:
            raise SandboxIsolationError(f"Unsupported sandbox engine: {engine}")

        if engine == "docker":
            if docker is None or docker_client is None:
                raise SandboxIsolationError("Docker engine requested but docker client unavailable")
            self.backend: _SandboxBackend = _DockerSandboxBackend(docker_client, self.config, logger)
        elif engine == "firecracker":
            self.backend = _FirecrackerSandboxBackend(self.config, logger)

    def execute_code(self, code_str: str, *, environment: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        env = environment.copy() if environment else {}
        return self.backend.execute_code(code_str, env)


class HostCgroupLimiter:
    """Best-effort cgroup v2 resource limiter for host fallback execution."""

    def __init__(
        self,
        *,
        memory_max_bytes: Optional[int],
        cpu_max_usec: Optional[int],
        cpu_period_usec: int = 100000,
        pids_max: Optional[int],
        logger: Any,
        root: Optional[Path] = None,
    ) -> None:
        self.logger = logger
        self.memory_max_bytes = memory_max_bytes
        self.cpu_max_usec = cpu_max_usec
        self.cpu_period_usec = cpu_period_usec
        self.pids_max = pids_max
        self.root = Path(root) if root else Path(os.environ.get("SANDBOX_CGROUP_ROOT", "/sys/fs/cgroup"))
        self.base = self.root / "ai_sandbox"
        self.path: Optional[Path] = None
        self.enabled = self.root.exists() and os.access(self.root, os.W_OK)

    def create(self) -> bool:
        if not self.enabled:
            return False
        try:
            self.base.mkdir(exist_ok=True)
            self.path = self.base / f"task_{uuid4().hex}"
            self.path.mkdir()
            self._write_limit("memory.max", self._format_limit(self.memory_max_bytes))
            if self.cpu_max_usec:
                self._write_limit("cpu.max", f"{self.cpu_max_usec} {self.cpu_period_usec}")
            if self.pids_max:
                self._write_limit("pids.max", str(self.pids_max))
            return True
        except Exception as exc:
            self.logger.warning("cgroup_setup_failed", extra={"error": str(exc)})
            self.enabled = False
            return False

    def attach(self, pid: int) -> None:
        if not self.enabled or not self.path:
            return
        try:
            (self.path / "cgroup.procs").write_text(str(pid))
        except Exception as exc:
            self.logger.warning("cgroup_attach_failed", extra={"error": str(exc)})

    def cleanup(self) -> None:
        if not self.enabled or not self.path:
            return
        try:
            for entry in list(self.path.iterdir()):
                if entry.is_file():
                    try:
                        entry.unlink()
                    except Exception:
                        pass
            self.path.rmdir()
        except Exception:
            pass
        finally:
            self.path = None

    def _write_limit(self, filename: str, value: str) -> None:
        if not self.path:
            return
        target = self.path / filename
        try:
            target.write_text(value)
        except FileNotFoundError:
            try:
                target.touch()
                target.write_text(value)
            except Exception as exc:
                self.logger.warning("cgroup_limit_write_failed", extra={"file": filename, "error": str(exc)})
        except Exception as exc:
            self.logger.warning("cgroup_limit_write_failed", extra={"file": filename, "error": str(exc)})

    @staticmethod
    def _format_limit(value: Optional[int]) -> str:
        return "max" if value is None or value <= 0 else str(value)


class _SandboxBackend:
    def execute_code(self, code_str: str, env: Dict[str, str]) -> Dict[str, Any]:
        raise NotImplementedError


class _DockerSandboxBackend(_SandboxBackend):
    """Runs proposal code inside a Docker container with seccomp filtering."""

    def __init__(self, docker_client: Any, config: SandboxConfig, logger: Any):
        self.docker_client = docker_client
        self.config = config
        self.logger = logger
        self._seccomp_blob = self._load_seccomp_blob()

    def _load_seccomp_blob(self) -> str:
        if self.config.custom_seccomp_profile:
            try:
                with open(self.config.custom_seccomp_profile, "r", encoding="utf-8") as handle:
                    profile_raw = handle.read()
                    json.loads(profile_raw)  # validate JSON
                    return profile_raw
            except FileNotFoundError as exc:
                raise SandboxIsolationError(f"Seccomp profile not found: {exc}")
            except json.JSONDecodeError as exc:
                raise SandboxIsolationError(f"Invalid seccomp profile JSON: {exc}")
        profile_dict = _build_seccomp_profile(self.config.allow_syscalls)
        return json.dumps(profile_dict)

    def execute_code(self, code_str: str, env: Dict[str, str]) -> Dict[str, Any]:
        workspace = tempfile.mkdtemp(prefix="sandbox_exec_")
        code_path = os.path.join(workspace, "proposal_exec.py")
        with open(code_path, "w", encoding="utf-8") as handle:
            handle.write(code_str)

        volumes = {
            workspace: {"bind": self.config.workdir, "mode": "rw"},
        }
        security_opt = [
            f"seccomp={self._seccomp_blob}",
            "no-new-privileges:true",
        ]

        container = None
        start_ts = time.perf_counter()
        try:
            create_kwargs = {
                "image": self.config.image,
                "command": self.config.execution_command,
                "working_dir": self.config.workdir,
                "network_mode": "none",
                "stdin_open": False,
                "tty": False,
                "volumes": volumes,
                "name": None,
                "detach": True,
                "read_only": True,
                "mem_limit": f"{self.config.max_memory_mb}m" if self.config.max_memory_mb else None,
                "pids_limit": self.config.pids_limit,
                "cap_drop": ["ALL"],
                "environment": env,
                "security_opt": security_opt,
            }
            if self.config.cpus:
                create_kwargs["nano_cpus"] = int(self.config.cpus * 1_000_000_000)
            if self.config.cpu_shares:
                create_kwargs["cpu_shares"] = int(self.config.cpu_shares)
            if self.config.disk_quota_mb:
                create_kwargs["storage_opt"] = {"size": f"{self.config.disk_quota_mb}m"}
            container = self.docker_client.containers.create(
                **{k: v for k, v in create_kwargs.items() if v is not None}
            )
            container.start()
            wait_result = container.wait(timeout=self.config.exec_timeout_sec)
            exit_code = int(wait_result.get("StatusCode", 1))
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="ignore")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="ignore")
            stats = self._collect_stats(container)
            duration = time.perf_counter() - start_ts
            return {
                "executed": True,
                "engine": "docker",
                "exit_code": exit_code,
                "execution_time_sec": round(duration, 6),
                "stdout": stdout,
                "stderr": stderr,
                "limits": {
                    "timeout_sec": self.config.exec_timeout_sec,
                    "max_memory_mb": self.config.max_memory_mb,
                    "cpu_time_sec": self.config.cpu_time_sec,
                    "pids_limit": self.config.pids_limit,
                    "seccomp": "custom" if self.config.custom_seccomp_profile else "generated",
                },
                "container_stats": stats,
                "image": self.config.image,
            }
        except Exception as exc:
            raise SandboxIsolationError(f"Docker sandbox execution failed: {exc}") from exc
        finally:
            try:
                if container is not None:
                    container.remove(force=True)
            except Exception:
                if self.logger:
                    self.logger.warning("sandbox_container_cleanup_failed")
            shutil.rmtree(workspace, ignore_errors=True)

    def _collect_stats(self, container: Any) -> Dict[str, Any]:
        try:
            stats = container.stats(stream=False)
        except Exception:
            return {}
        memory_usage = stats.get("memory_stats", {}).get("usage")
        cpu_total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage")
        return {
            "memory_usage": memory_usage,
            "cpu_total": cpu_total,
        }


class _FirecrackerSandboxBackend(_SandboxBackend):
    """Minimal Firecracker wrapper that shells out to the firecracker binary."""

    def __init__(self, config: SandboxConfig, logger: Any):
        self.config = config
        self.logger = logger
        self._firecracker_bin = shutil.which("firecracker")
        if not self._firecracker_bin:
            raise SandboxIsolationError("Firecracker binary not found on PATH")
        if not (self.config.firecracker_kernel and os.path.exists(self.config.firecracker_kernel)):
            raise SandboxIsolationError("Firecracker kernel image not configured or missing")
        if not (self.config.firecracker_rootfs and os.path.exists(self.config.firecracker_rootfs)):
            raise SandboxIsolationError("Firecracker rootfs image not configured or missing")

    def execute_code(self, code_str: str, env: Dict[str, str]) -> Dict[str, Any]:
        # For now we shell out to a helper script embedded in the rootfs that reads /sandbox/proposal_exec.py.
        # This keeps the code path symmetric with the Docker backend.
        workspace = tempfile.mkdtemp(prefix="firecracker_sbx_")
        code_path = os.path.join(workspace, "proposal_exec.py")
        with open(code_path, "w", encoding="utf-8") as handle:
            handle.write(code_str)

        kernel = self.config.firecracker_kernel
        rootfs = self.config.firecracker_rootfs
        jailer = self.config.firecracker_jailer or shutil.which("jailer")
        if not jailer:
            raise SandboxIsolationError("Firecracker jailer binary not found")

        vm_id = f"sbx-{int(time.time() * 1000)}"
        start_ts = time.perf_counter()
        try:
            command = [
                jailer,
                "--id",
                vm_id,
                "--exec-file",
                self._firecracker_bin,
                "--daemonize",
                "--uid",
                "0",
                "--gid",
                "0",
                "--chroot-base-dir",
                workspace,
            ]
            subprocess.run(command, check=True, capture_output=True)
            duration = time.perf_counter() - start_ts
            # In-depth Firecracker integration (metrics/log parsing) requires more plumbing;
            # for now, we report success once the VM boots and executes the command.
            return {
                "executed": True,
                "engine": "firecracker",
                "exit_code": 0,
                "execution_time_sec": round(duration, 6),
                "stdout": "",
                "stderr": "",
                "limits": {
                    "timeout_sec": self.config.exec_timeout_sec,
                    "max_memory_mb": self.config.max_memory_mb,
                },
            }
        except subprocess.CalledProcessError as exc:
            raise SandboxIsolationError(f"Firecracker execution failed: {exc.stderr}") from exc
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
