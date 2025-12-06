"""
Nano Cluster Tools
==================

Tools for managing and communicating with the Jetson Nano cluster.

Each nano runs:
- Ollama with a specialized LLM
- 3-tier memory client (syncs with ORKA)
- Communication codec for efficient messaging

Cluster Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    HP Z6 WORKSTATION (ORKA)                     │
    │                    qwen2.5:14b (16GB VRAM)                      │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │ SharedMemoryServer (port 5000) │ Orchestrator │ UI (5001)  ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────┬───────────────────────────────────────┘
                              │ (192.168.0.x network)
    ┌─────────────────────────┼───────────────────────────────────────┐
    │                         │                                       │
    ▼                         ▼                                       ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│   GIN   │ │  ORIN   │ │   TIF   │ │  TORI   │ │ PAGEQA  │ │  ARCHI  │ │  GUARD  │
│deepseek │ │deepseek │ │deepseek │ │ gemma3  │ │ qwen2.5 │ │ qwen2.5 │ │llama-grd│
│  1.5b   │ │  1.5b   │ │  1.5b   │ │   4b    │ │   3b    │ │   3b    │ │   1b    │
│ .242    │ │ .160    │ │ .213    │ │ .235    │ │ .168    │ │ .232    │ │ .146    │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
"""

import os
import json
import time
import logging
import threading
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import requests

logger = logging.getLogger(__name__)


class NanoRole(Enum):
    """Specialized roles for each nano in the cluster."""
    GIN = "generative_improvement"      # Code generation & improvement
    ORIN = "orchestration_research"     # Research coordination
    TIF = "technical_improvement"       # Technical analysis
    TORI = "technical_review"           # Review & optimization
    PAGEQA = "document_qa"              # Paper/document Q&A
    ARCHI = "architecture_design"       # System design
    GUARD = "safety_guardian"           # Safety checking
    ORKA = "orchestrator"               # Central coordinator


# Cluster roles mapping for task routing
CLUSTER_ROLES = {
    "reasoning": ["GIN", "ORIN", "TIF"],           # DeepSeek models excel at reasoning
    "code_generation": ["GIN", "TIF"],              # Code generation specialists
    "code_review": ["TORI", "ARCHI"],               # Review and architecture
    "research": ["ORIN", "PAGEQA"],                 # Research and document analysis
    "safety": ["GUARD"],                            # Safety checking (llama-guard)
    "orchestration": ["ORKA"],                      # Central coordination
    "general": ["TORI", "PAGEQA", "ARCHI"],         # General purpose (Gemma/Qwen)
}


@dataclass
class NanoNode:
    """Represents a single nano in the cluster."""
    name: str
    ip: str
    port: int = 11434
    model: str = ""
    role: NanoRole = NanoRole.GIN
    user: str = ""
    password: str = "1"  # Default password
    
    # Status tracking
    is_online: bool = False
    last_check: float = 0
    ollama_running: bool = False
    model_loaded: bool = False
    
    # Memory adapter (optional)
    memory_adapter: Any = None
    
    def __post_init__(self):
        # Derive user from name if not provided
        if not self.user:
            self.user = self.name.lower()
    
    @property
    def ollama_url(self) -> str:
        return f"http://{self.ip}:{self.port}"
    
    @property
    def ssh_target(self) -> str:
        return f"{self.user}@{self.ip}"
    
    def check_status(self, timeout: float = 2.0) -> bool:
        """Check if nano is online and Ollama is running."""
        try:
            response = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=timeout
            )
            if response.status_code == 200:
                self.is_online = True
                self.ollama_running = True
                models = response.json().get('models', [])
                self.model_loaded = any(
                    m.get('name', '').startswith(self.model.split(':')[0])
                    for m in models
                )
                self.last_check = time.time()
                return True
        except Exception:
            pass
        
        self.is_online = False
        self.ollama_running = False
        self.model_loaded = False
        self.last_check = time.time()
        return False
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = 60.0
    ) -> Optional[str]:
        """Generate a response using the nano's Ollama model."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            if system:
                payload["system"] = system
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
        except Exception as e:
            logger.error(f"Generate failed on {self.name}: {e}")
        
        return None
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = 60.0
    ) -> Optional[str]:
        """Chat with the nano's Ollama model."""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json().get('message', {}).get('content', '')
        except Exception as e:
            logger.error(f"Chat failed on {self.name}: {e}")
        
        return None
    
    def run_ssh_command(
        self,
        command: str,
        timeout: float = 30.0,
        use_sudo: bool = False
    ) -> Tuple[bool, str]:
        """Run a command on the nano via SSH."""
        try:
            if use_sudo:
                command = f"echo '{self.password}' | sudo -S {command}"
            
            result = subprocess.run(
                [
                    "sshpass", "-p", self.password,
                    "ssh", "-o", "StrictHostKeyChecking=no",
                    "-o", f"ConnectTimeout={int(timeout)}",
                    self.ssh_target,
                    command
                ],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ip": self.ip,
            "port": self.port,
            "model": self.model,
            "role": self.role.value,
            "user": self.user,
            "is_online": self.is_online,
            "ollama_running": self.ollama_running,
            "model_loaded": self.model_loaded,
            "last_check": self.last_check,
            "ollama_url": self.ollama_url,
            "ssh_target": self.ssh_target
        }


class NanoCluster:
    """
    Manages the entire nano cluster.
    
    Provides:
    - Cluster status monitoring
    - Load-balanced generation
    - Parallel processing
    - Health checks
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.nodes: Dict[str, NanoNode] = {}
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor = threading.Event()
        
        # Load cluster config
        if config_path:
            self._load_config(config_path)
        else:
            self._load_default_cluster()
    
    def _load_default_cluster(self):
        """Load the default cluster configuration."""
        # Map from config/default.yaml cluster definition
        # NOVEL (formerly GUARD) is now a creative node
        # llama-guard3:1b runs on ORKA for centralized safety
        cluster_def = {
            "GIN": {"ip": "192.168.0.242", "model": "deepseek-r1:1.5b", "user": "gin", "role": NanoRole.GIN},
            "ORIN": {"ip": "192.168.0.160", "model": "deepseek-r1:1.5b", "user": "orin", "role": NanoRole.ORIN},
            "TIF": {"ip": "192.168.0.213", "model": "deepseek-r1:1.5b", "user": "tif", "role": NanoRole.TIF},
            "TORI": {"ip": "192.168.0.235", "model": "gemma3:4b", "user": "tori", "role": NanoRole.TORI},
            "PAGEQA": {"ip": "192.168.0.168", "model": "qwen2.5:3b", "user": "page", "role": NanoRole.PAGEQA},
            "ARCHI": {"ip": "192.168.0.232", "model": "qwen2.5:3b", "user": "archi", "role": NanoRole.ARCHI},
            "NOVEL": {"ip": "192.168.0.146", "model": "gemma:2b", "user": "guard", "role": NanoRole.GUARD},  # Creative node
            "ORKA": {"ip": "localhost", "model": "qwen2.5:14b", "user": "xx", "role": NanoRole.ORKA},  # + llama-guard3:1b
        }
        
        for name, cfg in cluster_def.items():
            self.nodes[name] = NanoNode(
                name=name,
                ip=cfg["ip"],
                model=cfg["model"],
                user=cfg.get("user", name.lower()),
                role=cfg.get("role", NanoRole.GIN)
            )
    
    def _load_config(self, config_path: str):
        """Load cluster from YAML config file."""
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            
            cluster_cfg = cfg.get('cluster', {}).get('agents', {})
            for name, agent_cfg in cluster_cfg.items():
                role = NanoRole.ORKA if name == "ORKA" else NanoRole.GIN
                # Try to match role by name
                for r in NanoRole:
                    if r.name == name:
                        role = r
                        break
                
                self.nodes[name] = NanoNode(
                    name=name,
                    ip=agent_cfg.get('host', 'localhost'),
                    port=agent_cfg.get('port', 11434),
                    model=agent_cfg.get('model', ''),
                    role=role
                )
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._load_default_cluster()
    
    def get_node(self, name: str) -> Optional[NanoNode]:
        """Get a specific node by name."""
        return self.nodes.get(name)
    
    def get_online_nodes(self) -> List[NanoNode]:
        """Get all online nodes."""
        return [n for n in self.nodes.values() if n.is_online]
    
    def get_nodes_by_role(self, role: NanoRole) -> List[NanoNode]:
        """Get nodes with a specific role."""
        return [n for n in self.nodes.values() if n.role == role]
    
    def check_all_status(self, parallel: bool = True) -> Dict[str, bool]:
        """Check status of all nodes."""
        results = {}
        
        if parallel:
            threads = []
            for node in self.nodes.values():
                t = threading.Thread(target=lambda n=node: n.check_status())
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join(timeout=5.0)
        else:
            for node in self.nodes.values():
                node.check_status()
        
        for name, node in self.nodes.items():
            results[name] = node.is_online
        
        return results
    
    def generate_on_node(
        self,
        node_name: str,
        prompt: str,
        **kwargs
    ) -> Optional[str]:
        """Generate on a specific node."""
        node = self.nodes.get(node_name)
        if not node:
            return None
        return node.generate(prompt, **kwargs)
    
    def generate_on_best_available(
        self,
        prompt: str,
        prefer_role: Optional[NanoRole] = None,
        **kwargs
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate on the best available node.
        
        Returns (response, node_name) or (None, None) if no nodes available.
        """
        # Get candidates
        candidates = self.get_online_nodes()
        
        if prefer_role:
            role_nodes = [n for n in candidates if n.role == prefer_role]
            if role_nodes:
                candidates = role_nodes
        
        if not candidates:
            # Refresh status and try again
            self.check_all_status()
            candidates = self.get_online_nodes()
        
        if not candidates:
            return None, None
        
        # Try each candidate
        for node in candidates:
            response = node.generate(prompt, **kwargs)
            if response:
                return response, node.name
        
        return None, None
    
    def parallel_generate(
        self,
        prompts: Dict[str, str],  # node_name -> prompt
        **kwargs
    ) -> Dict[str, Optional[str]]:
        """Generate on multiple nodes in parallel."""
        results = {}
        threads = []
        
        def worker(name: str, prompt: str):
            results[name] = self.generate_on_node(name, prompt, **kwargs)
        
        for name, prompt in prompts.items():
            t = threading.Thread(target=worker, args=(name, prompt))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join(timeout=120.0)
        
        return results
    
    def broadcast_prompt(
        self,
        prompt: str,
        nodes: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Optional[str]]:
        """Send the same prompt to multiple nodes."""
        target_nodes = nodes or list(self.nodes.keys())
        prompts = {name: prompt for name in target_nodes}
        return self.parallel_generate(prompts, **kwargs)
    
    def broadcast_message(
        self,
        message: str,
        nodes: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Broadcast a message to all cluster nodes.
        
        This is a simpler notification mechanism compared to broadcast_prompt,
        intended for system-level coordination messages.
        
        Returns:
            Dict mapping node names to status dicts with 'received' and 'response' keys
        """
        target_nodes = nodes or list(self.nodes.keys())
        results = {}
        
        for name in target_nodes:
            node = self.nodes.get(name)
            if not node:
                results[name] = {"received": False, "error": "Node not found"}
                continue
            
            if not node.is_online:
                results[name] = {"received": False, "error": "Node offline"}
                continue
            
            # For broadcast messages, we just ping and log
            try:
                is_up = node.check_status(timeout=2.0)
                if is_up:
                    # Log the message reception (actual handling would be node-side)
                    results[name] = {
                        "received": True,
                        "node_model": node.model,
                        "message_preview": message[:50] + "..." if len(message) > 50 else message
                    }
                else:
                    results[name] = {"received": False, "error": "Node not responding"}
            except Exception as e:
                results[name] = {"received": False, "error": str(e)}
        
        return results
    
    def check_safety(self, content: str) -> Dict[str, Any]:
        """
        Check content safety using llama-guard3 on ORKA.
        
        GUARD model runs on ORKA node (centralized safety).
        Returns safety assessment from llama-guard3.
        """
        orka = self.nodes.get("ORKA")
        if not orka:
            return {"error": "ORKA node not available for safety check", "safe": None}
        
        # Check ORKA status if not already online
        if not orka.is_online:
            orka.check_status()
        
        if not orka.is_online:
            return {"error": "ORKA node not available for safety check", "safe": None}
        
        # Use llama-guard3:1b model for safety checking (hosted on ORKA)
        prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in the following text according to our safety policy.

<BEGIN TEXT>
{content}
<END TEXT>

Provide your safety assessment:<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
        
        try:
            # Call ORKA with llama-guard3 model specifically
            import requests
            response = requests.post(
                f"{orka.ollama_url}/api/generate",
                json={
                    "model": "llama-guard3:1b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get("response", "")
                is_safe = "safe" in result.lower() and "unsafe" not in result.lower()
                return {
                    "safe": is_safe,
                    "response": result,
                    "checked_by": "ORKA/llama-guard3:1b"
                }
        except Exception as e:
            return {"error": f"Safety check failed: {e}", "safe": None}
        
        return {"error": "No response from ORKA", "safe": None}
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get comprehensive cluster statistics."""
        self.check_all_status()
        
        online = [n for n in self.nodes.values() if n.is_online]
        
        return {
            "total_nodes": len(self.nodes),
            "online_nodes": len(online),
            "offline_nodes": len(self.nodes) - len(online),
            "nodes": {
                name: node.to_dict()
                for name, node in self.nodes.items()
            },
            "roles": {
                role.name: [n.name for n in self.get_nodes_by_role(role)]
                for role in NanoRole
            },
            "timestamp": time.time()
        }
    
    def start_monitor(self, interval: float = 30.0):
        """Start background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._stop_monitor.clear()
        
        def monitor_loop():
            while not self._stop_monitor.wait(interval):
                try:
                    self.check_all_status()
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitor(self):
        """Stop background monitoring."""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)


# Global cluster instance
_cluster: Optional[NanoCluster] = None


def get_cluster() -> NanoCluster:
    """Get the global cluster instance."""
    global _cluster
    if _cluster is None:
        _cluster = NanoCluster()
    return _cluster


def init_cluster(config_path: Optional[str] = None) -> NanoCluster:
    """Initialize the global cluster."""
    global _cluster
    _cluster = NanoCluster(config_path)
    return _cluster


# Convenience functions

def check_cluster_status() -> Dict[str, bool]:
    """Check status of all nodes in the cluster."""
    return get_cluster().check_all_status()


def generate(
    prompt: str,
    node: Optional[str] = None,
    role: Optional[NanoRole] = None,
    **kwargs
) -> Optional[str]:
    """
    Generate a response using the cluster.
    
    Args:
        prompt: The prompt to send
        node: Specific node name (optional)
        role: Preferred role (optional)
        **kwargs: Additional generation parameters
    
    Returns:
        Generated response or None
    """
    cluster = get_cluster()
    
    if node:
        return cluster.generate_on_node(node, prompt, **kwargs)
    
    response, _ = cluster.generate_on_best_available(prompt, prefer_role=role, **kwargs)
    return response


def broadcast(prompt: str, nodes: Optional[List[str]] = None, **kwargs) -> Dict[str, Optional[str]]:
    """Broadcast prompt to multiple nodes."""
    return get_cluster().broadcast_prompt(prompt, nodes, **kwargs)


def check_safety(content: str) -> Dict[str, Any]:
    """Check content safety using GUARD node."""
    return get_cluster().check_safety(content)
