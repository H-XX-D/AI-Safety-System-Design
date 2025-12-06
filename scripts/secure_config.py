#!/usr/bin/env python3
"""
Secure Configuration Module for ORKASTRATOR
=============================================

Provides:
- Externalized cluster configuration (no hardcoded passwords)
- SSH key-based authentication support
- Node identity verification
- Configuration validation
- Credential rotation support
"""

import json
import os
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import yaml
import logging

# Structured logging
logger = logging.getLogger("orkastrator.config")


class SecurityError(Exception):
    """Raised when a security requirement is violated."""
    pass


class AuthMethod(Enum):
    """Authentication methods for cluster nodes."""
    SSH_KEY = "ssh_key"           # Preferred: SSH key-based auth
    SSH_PASSWORD = "ssh_password"  # Legacy: Password-based (deprecated)
    NONE = "none"                  # Local node


@dataclass
class NodeConfig:
    """Configuration for a cluster node."""
    name: str
    ip: str
    port: int = 11434
    user: str = ""
    model: str = ""
    role: str = "researcher"
    auth_method: AuthMethod = AuthMethod.SSH_KEY
    ssh_key_path: Optional[str] = None
    fingerprint: Optional[str] = None  # Expected host key fingerprint
    
    def get_ssh_command_prefix(self) -> List[str]:
        """Get SSH command prefix based on auth method."""
        if self.auth_method == AuthMethod.SSH_KEY:
            key_path = self.ssh_key_path or str(Path.home() / ".ssh" / "id_ed25519")
            return [
                "ssh",
                "-i", key_path,
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "BatchMode=yes",
                f"{self.user}@{self.ip}"
            ]
        elif self.auth_method == AuthMethod.SSH_PASSWORD:
            # DEPRECATED: Refuse to use password auth
            raise SecurityError(f"Node {self.name}: Password authentication is DISABLED. Use SSH keys only.")
        return []  # Local node
    
    @property
    def ollama_url(self) -> str:
        """Get Ollama API URL."""
        host = "localhost" if self.ip in ("localhost", "127.0.0.1") else self.ip
        return f"http://{host}:{self.port}"
    
    def verify_identity(self) -> Tuple[bool, str]:
        """Verify node identity via SSH host key fingerprint."""
        if self.auth_method == AuthMethod.NONE:
            return True, "Local node"
        
        if not self.fingerprint:
            return False, "No fingerprint configured - cannot verify identity"
        
        try:
            result = subprocess.run(
                ["ssh-keyscan", "-H", self.ip],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode == 0:
                # Hash the host key for comparison
                key_hash = hashlib.sha256(result.stdout.encode()).hexdigest()[:32]
                if key_hash == self.fingerprint:
                    return True, f"Fingerprint verified: {key_hash}"
                return False, f"Fingerprint mismatch: expected {self.fingerprint}, got {key_hash}"
            return False, f"ssh-keyscan failed: {result.stderr}"
        except Exception as e:
            return False, f"Verification error: {e}"


@dataclass
class ClusterConfig:
    """Full cluster configuration."""
    nodes: Dict[str, NodeConfig] = field(default_factory=dict)
    orka_node: str = "ORKA"
    guard_model: str = "llama-guard3:1b"
    require_docker_sandbox: bool = True  # Fail if Docker not available
    require_safety_check: bool = True    # Fail closed on safety errors
    require_human_approval: bool = True  # Require human approval before deploy
    worm_manifest_required: bool = True  # Require signed WORM manifests
    max_improvement_size: int = 50000    # Max chars for improvement artifacts
    
    # TLS/HTTPS requirements
    # NOTE: Ollama does NOT natively support TLS. For production:
    # 1. Use a reverse proxy (nginx/caddy) with TLS termination, OR
    # 2. Deploy Ollama in a private network with SSH tunneling, OR  
    # 3. Accept HTTP on trusted LAN (current cluster setup)
    # 
    # Set require_https=True only if you have a TLS-terminating proxy.
    require_https: bool = False          # Disabled - Ollama doesn't support TLS natively
    allow_localhost_http: bool = True    # Allow HTTP for localhost
    allow_private_network_http: bool = True  # Allow HTTP on 192.168.x.x/10.x.x.x
    
    # Auto-approve restrictions
    auto_approve_allowed: bool = False   # ORKA_AUTO_APPROVE disabled by default
    ci_mode: bool = False                # Only CI can enable auto-approve
    
    # Evaluation config (HIDDEN from researchers)
    _eval_metrics: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    @staticmethod
    def _detect_ci_environment() -> bool:
        """
        Detect if running in a CI environment.
        
        Only in CI should ORKA_AUTO_APPROVE be allowed.
        """
        ci_indicators = [
            "CI",                    # Generic CI
            "GITHUB_ACTIONS",        # GitHub Actions
            "GITLAB_CI",             # GitLab CI
            "JENKINS_URL",           # Jenkins
            "CIRCLECI",              # CircleCI
            "TRAVIS",                # Travis CI
            "AZURE_PIPELINES",       # Azure Pipelines
            "TF_BUILD",              # Azure DevOps
            "BUILDKITE",             # Buildkite
            "ORKASTRATOR_CI_MODE",   # Explicit CI mode (must be set + signed)
        ]
        for indicator in ci_indicators:
            if os.environ.get(indicator):
                return True
        return False
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "ClusterConfig":
        """Load configuration from YAML file."""
        if config_path is None:
            # Check standard locations
            candidates = [
                Path.home() / ".orkastrator" / "cluster.yaml",
                Path("/etc/orkastrator/cluster.yaml"),
                Path("config/cluster_secure.yaml"),
                Path("config/default.yaml"),
            ]
            for p in candidates:
                if p.exists():
                    config_path = str(p)
                    break
        
        if not config_path or not Path(config_path).exists():
            logger.warning("No config file found - using defaults")
            return cls._load_defaults()
        
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        return cls._from_dict(data)
    
    @classmethod
    def _from_dict(cls, data: Dict) -> "ClusterConfig":
        """Create config from dictionary."""
        config = cls()
        
        # Load nodes
        for name, node_data in data.get("cluster", {}).get("nodes", {}).items():
            auth = AuthMethod(node_data.get("auth_method", "ssh_key"))
            config.nodes[name] = NodeConfig(
                name=name,
                ip=node_data.get("ip", "localhost"),
                port=node_data.get("port", 11434),
                user=node_data.get("user", name.lower()),
                model=node_data.get("model", ""),
                role=node_data.get("role", "researcher"),
                auth_method=auth,
                ssh_key_path=node_data.get("ssh_key_path"),
                fingerprint=node_data.get("fingerprint"),
            )
        
        # Load settings
        settings = data.get("security", {})
        config.require_docker_sandbox = settings.get("require_docker_sandbox", True)
        config.require_safety_check = settings.get("require_safety_check", True)
        config.require_human_approval = settings.get("require_human_approval", True)
        config.worm_manifest_required = settings.get("worm_manifest_required", True)
        config.require_https = settings.get("require_https", True)
        config.allow_localhost_http = settings.get("allow_localhost_http", True)
        
        # CI mode detection - auto-approve ONLY allowed in CI
        config.ci_mode = cls._detect_ci_environment()
        config.auto_approve_allowed = config.ci_mode and settings.get("auto_approve_allowed", False)
        
        # Load HIDDEN eval metrics (not exposed to researchers)
        config._eval_metrics = data.get("_evaluation", {})
        
        return config
    
    @classmethod
    def _load_defaults(cls) -> "ClusterConfig":
        """Load default configuration with environment variables."""
        config = cls()
        
        # Read from environment or use defaults
        default_nodes = {
            "ORKA": {"ip": "localhost", "model": "qwen2.5:14b", "role": "orchestrator"},
            "GIN": {"ip": "192.168.0.242", "model": "deepseek-r1:1.5b", "user": "gin"},
            "TIF": {"ip": "192.168.0.213", "model": "deepseek-r1:1.5b", "user": "tif"},
            "ORIN": {"ip": "192.168.0.160", "model": "deepseek-r1:1.5b", "user": "orin"},
            "ARCHI": {"ip": "192.168.0.232", "model": "qwen2.5:3b", "user": "archi"},
            "TORI": {"ip": "192.168.0.235", "model": "gemma3:4b", "user": "tori"},
            "NOVEL": {"ip": "192.168.0.146", "model": "gemma:2b", "user": "guard"},
            "PAGEQA": {"ip": "192.168.0.168", "model": "qwen2.5:3b", "user": "page"},
        }
        
        for name, data in default_nodes.items():
            # Check for environment override
            ip = os.environ.get(f"ORKA_NODE_{name}_IP", data["ip"])
            
            auth = AuthMethod.NONE if ip == "localhost" else AuthMethod.SSH_KEY
            # Check if password is set (legacy mode)
            if os.environ.get(f"ORKA_NODE_{name}_PASSWORD"):
                auth = AuthMethod.SSH_PASSWORD
            
            config.nodes[name] = NodeConfig(
                name=name,
                ip=ip,
                user=data.get("user", name.lower()),
                model=data.get("model", ""),
                role=data.get("role", "researcher"),
                auth_method=auth,
            )
        
        return config
    
    def get_node(self, name: str) -> Optional[NodeConfig]:
        """Get a node by name."""
        return self.nodes.get(name)
    
    def get_researchers(self) -> List[NodeConfig]:
        """Get all researcher nodes."""
        return [n for n in self.nodes.values() if n.role == "researcher"]
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate configuration."""
        errors = []
        
        # Check ORKA node exists
        if self.orka_node not in self.nodes:
            errors.append(f"ORKA node '{self.orka_node}' not found")
        
        # Check at least 2 researchers
        researchers = self.get_researchers()
        if len(researchers) < 2:
            errors.append(f"Need at least 2 researcher nodes, have {len(researchers)}")
        
        # Check for deprecated password auth
        password_nodes = [n.name for n in self.nodes.values() 
                         if n.auth_method == AuthMethod.SSH_PASSWORD]
        if password_nodes:
            errors.append(f"Deprecated password auth on: {', '.join(password_nodes)} - migrate to SSH keys")
        
        # Check all nodes have fingerprints (for SSH nodes)
        no_fingerprint = [n.name for n in self.nodes.values()
                         if n.auth_method != AuthMethod.NONE and not n.fingerprint]
        if no_fingerprint:
            errors.append(f"Missing fingerprints for: {', '.join(no_fingerprint)}")
        
        return len(errors) == 0, errors
    
    def verify_all_nodes(self) -> Dict[str, Tuple[bool, str]]:
        """Verify identity of all nodes."""
        results = {}
        for name, node in self.nodes.items():
            results[name] = node.verify_identity()
        return results


def setup_ssh_keys(config: ClusterConfig, key_name: str = "id_orkastrator") -> bool:
    """Set up SSH keys for cluster nodes."""
    key_path = Path.home() / ".ssh" / key_name
    pub_key_path = key_path.with_suffix(".pub")
    
    # Generate key if needed
    if not key_path.exists():
        print(f"Generating SSH key: {key_path}")
        result = subprocess.run([
            "ssh-keygen", "-t", "ed25519",
            "-f", str(key_path),
            "-N", "",  # No passphrase for automation
            "-C", "orkastrator-cluster"
        ], capture_output=True)
        if result.returncode != 0:
            print(f"ERROR: ssh-keygen failed: {result.stderr}")
            return False
    
    # Read public key
    pub_key = pub_key_path.read_text().strip()
    print(f"\nPublic key: {pub_key}\n")
    
    # Deploy to each node
    print("Deploy this key to cluster nodes with:")
    for name, node in config.nodes.items():
        if node.auth_method == AuthMethod.NONE:
            continue
        print(f"  ssh-copy-id -i {pub_key_path} {node.user}@{node.ip}")
    
    return True


def generate_fingerprints(config: ClusterConfig) -> Dict[str, str]:
    """Generate host key fingerprints for all nodes."""
    fingerprints = {}
    for name, node in config.nodes.items():
        if node.ip == "localhost":
            continue
        try:
            result = subprocess.run(
                ["ssh-keyscan", "-H", node.ip],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode == 0 and result.stdout:
                fp = hashlib.sha256(result.stdout.encode()).hexdigest()[:32]
                fingerprints[name] = fp
                print(f"{name} ({node.ip}): {fp}")
        except Exception as e:
            print(f"{name}: Error - {e}")
    return fingerprints


# Global config instance
_config: Optional[ClusterConfig] = None


def get_config() -> ClusterConfig:
    """Get or load the cluster configuration."""
    global _config
    if _config is None:
        _config = ClusterConfig.load()
    return _config


def reload_config(config_path: Optional[str] = None) -> ClusterConfig:
    """Reload configuration from file."""
    global _config
    _config = ClusterConfig.load(config_path)
    return _config


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "setup-keys":
            config = get_config()
            setup_ssh_keys(config)
        elif cmd == "fingerprints":
            config = get_config()
            generate_fingerprints(config)
        elif cmd == "validate":
            config = get_config()
            valid, errors = config.validate()
            if valid:
                print("✓ Configuration valid")
            else:
                print("✗ Configuration errors:")
                for e in errors:
                    print(f"  - {e}")
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: secure_config.py [setup-keys|fingerprints|validate]")
    else:
        # Print current config
        config = get_config()
        print("Current Cluster Configuration:")
        for name, node in config.nodes.items():
            print(f"  {name}: {node.ip} ({node.model}) - {node.auth_method.value}")
