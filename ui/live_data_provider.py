"""
Live Data Provider for ORKASTRATOR UI
======================================

Provides real-time data from the actual system instead of simulation data.
Connects to:
- Nano cluster (via tools.nano_cluster)
- Autonomous agents (via tools.autonomous_agents)
- Memory system (via memory.orchestrator_adapter)
- Integrations (via tools.integrations)
"""

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache for performance
_cache = {
    'cluster_status': None,
    'cluster_status_time': 0,
    'agent_status': None,
    'agent_status_time': 0,
    'proposals': [],
    'proposals_time': 0,
    'detection_events': [],
}
CACHE_TTL = 5  # seconds


def _get_cached(key: str, ttl: int = CACHE_TTL) -> Optional[Any]:
    """Get cached data if still valid."""
    time_key = f"{key}_time"
    if _cache.get(time_key, 0) + ttl > time.time():
        return _cache.get(key)
    return None


def _set_cached(key: str, value: Any):
    """Set cached data."""
    _cache[key] = value
    _cache[f"{key}_time"] = time.time()


# ============================================================
# NANO CLUSTER STATUS
# ============================================================

# Cluster configuration
NANO_NODES = {
    "GIN": {"ip": "192.168.0.242", "user": "gin", "model": "deepseek-r1:1.5b", "role": "code_generation"},
    "ORIN": {"ip": "192.168.0.160", "user": "orin", "model": "deepseek-r1:1.5b", "role": "nvidia_optimization"},
    "TIF": {"ip": "192.168.0.213", "user": "tif", "model": "deepseek-r1:1.5b", "role": "technical_analysis"},
    "TORI": {"ip": "192.168.0.235", "user": "tori", "model": "gemma3:4b", "role": "code_review"},
    "ARCHI": {"ip": "192.168.0.232", "user": "archi", "model": "qwen2.5:3b", "role": "architecture"},
    "PAGEQA": {"ip": "localhost", "user": "xx", "model": "paperqa", "role": "research"},
    "GUARD": {"ip": "localhost", "user": "xx", "model": "llama-guard3:1b", "role": "safety"},
    "THEO": {"ip": "192.168.0.168", "user": "page", "model": "qwen2.5:3b", "role": "research"},
}

ORKA_NODE = {
    "ip": "localhost",
    "user": "xx",
    "model": "qwen2.5:3b",
    "role": "orchestrator"
}

# Default password used for lightweight Jetson utilities; override with NANO_DEFAULT_PASSWORD env var
DEFAULT_NANO_PASSWORD = os.getenv("NANO_DEFAULT_PASSWORD", "1")


def check_node_status(name: str, ip: str, port: int = 11434, timeout: float = 3.0) -> dict:
    """Check if a nano node is online."""
    status = {
        "name": name,
        "ip": ip,
        "port": port,
        "online": False,
        "ollama_running": False,
        "model": None,
        "response_time_ms": None,
    }
    
    try:
        import requests
        start = time.time()
        
        # Use Ollama API to check - more reliable than socket
        resp = requests.get(f"http://{ip}:{port}/api/tags", timeout=timeout)
        response_time = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            status["online"] = True
            status["ollama_running"] = True
            status["response_time_ms"] = round(response_time, 2)
            
            models = resp.json().get("models", [])
            if models:
                status["model"] = models[0].get("name", "unknown")
    except Exception as e:
        logger.debug(f"Error checking {name}: {e}")
    
    return status


def get_cluster_status_live() -> Dict[str, Any]:
    """Get live status of all cluster nodes."""
    # Check cache
    cached = _get_cached('cluster_status')
    if cached:
        return cached
    
    nodes = {}
    online_count = 0
    
    # Check each nano
    for name, config in NANO_NODES.items():
        status = check_node_status(name, config["ip"])
        status["role"] = config["role"]
        status["expected_model"] = config["model"]
        nodes[name] = status
        if status["online"]:
            online_count += 1
    
    # Check ORKA (localhost)
    orka_status = check_node_status("ORKA", "localhost")
    orka_status["role"] = "orchestrator"
    orka_status["expected_model"] = ORKA_NODE["model"]
    nodes["ORKA"] = orka_status
    if orka_status["online"]:
        online_count += 1
    
    result = {
        "nodes": nodes,
        "online_count": online_count,
        "total_count": len(NANO_NODES) + 1,  # +1 for ORKA
        "timestamp": datetime.now().isoformat(),
        "healthy": online_count >= 4,  # At least 4 nodes for healthy cluster
    }
    
    _set_cached('cluster_status', result)
    return result


# ============================================================
# CLUSTER GENERATION AND SAFETY
# ============================================================

def generate_on_node(node_name: str, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> Optional[str]:
    """Generate text using a specific cluster node."""
    try:
        import requests
        
        # Get node config
        all_nodes = {**NANO_NODES, "ORKA": ORKA_NODE}
        if node_name not in all_nodes:
            logger.error(f"Node {node_name} not found in cluster configuration")
            return None
        
        config = all_nodes[node_name]
        ip = config["ip"]
        port = 11434  # Ollama default port
        
        # Check if node is online
        status = check_node_status(node_name, ip, port)
        if not status["online"]:
            logger.error(f"Node {node_name} is not online")
            return None
        
        # Generate using Ollama API
        url = f"http://{ip}:{port}/api/generate"
        payload = {
            "model": config["model"],
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "")
        else:
            logger.error(f"Generation failed on {node_name}: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating on {node_name}: {e}")
        return None


def generate_on_best_available(prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> Tuple[Optional[str], str]:
    """Generate text using the best available cluster node."""
    try:
        # Get cluster status to find online nodes
        status = get_cluster_status_live()
        
        # Try ORKA first (orchestrator), then other nodes
        priority_order = ["ORKA", "TIF", "GIN", "ORIN", "TORI", "ARCHI", "PAGEQA"]
        
        for node_name in priority_order:
            if node_name in status["nodes"] and status["nodes"][node_name]["online"]:
                response = generate_on_node(node_name, prompt, temperature, max_tokens)
                if response:
                    return response, node_name
        
        logger.error("No available nodes for generation")
        return None, ""
        
    except Exception as e:
        logger.error(f"Error in generate_on_best_available: {e}")
        return None, ""


def check_content_safety(content: str) -> Dict[str, Any]:
    """Check content safety using GUARD node."""
    try:
        import requests
        
        guard_config = NANO_NODES.get("GUARD")
        if not guard_config:
            return {"safe": True, "error": "GUARD node not configured"}
        
        ip = guard_config["ip"]
        port = 11434
        
        # Check if GUARD is online
        status = check_node_status("GUARD", ip, port)
        if not status["online"]:
            return {"safe": True, "error": "GUARD node not available"}
        
        # Use llama-guard model for safety check
        url = f"http://{ip}:{port}/api/generate"
        safety_prompt = f"""Analyze the following content for safety. Respond with only "SAFE" or "UNSAFE" followed by a brief reason.

Content: {content}

Analysis:"""
        
        payload = {
            "model": guard_config["model"],
            "prompt": safety_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 100
            }
        }
        
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip().upper()
            
            if response_text.startswith("SAFE"):
                return {"safe": True, "reason": "Content passed safety check"}
            elif response_text.startswith("UNSAFE"):
                reason = response_text.replace("UNSAFE", "").strip()
                return {"safe": False, "reason": reason or "Content flagged as unsafe"}
            else:
                return {"safe": True, "reason": "Unable to determine safety, defaulting to safe"}
        else:
            return {"safe": True, "error": f"GUARD API error: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Error checking safety: {e}")
        return {"safe": True, "error": str(e)}


def get_cluster_roles() -> Dict[str, Any]:
    """Get cluster node roles and capabilities."""
    roles_info = {}
    
    # Define roles based on our cluster configuration
    CLUSTER_ROLES = {
        'code_generation': ['TIF', 'GIN'],
        'nvidia_optimization': ['ORIN'],
        'code_review': ['TORI'],
        'research': ['PAGEQA'],
        'architecture': ['ARCHI'],
        'safety': ['GUARD'],
        'orchestration': ['ORKA']
    }
    
    role_descriptions = {
        'code_generation': 'Code writing and generation',
        'nvidia_optimization': 'CUDA and GPU optimization',
        'code_review': 'Code review and optimization',
        'research': 'Research coordination and document analysis',
        'architecture': 'Architecture design and planning',
        'safety': 'Safety checking and content moderation',
        'orchestration': 'System coordination and task distribution'
    }
    
    for role_name, nodes in CLUSTER_ROLES.items():
        roles_info[role_name] = {
            'nodes': nodes,
            'count': len(nodes),
            'description': role_descriptions.get(role_name, 'Unknown role')
        }
    
    return {
        'roles': roles_info,
        'total_roles': len(CLUSTER_ROLES),
        'timestamp': datetime.now().isoformat()
    }


# ============================================================
# SYSTEM METRICS
# ============================================================

def get_local_system_metrics() -> Dict[str, Any]:
    """Get metrics from the local system (ORKA)."""
    metrics = {
        "cpu_percent": 0,
        "memory_percent": 0,
        "memory_used_gb": 0,
        "memory_total_gb": 0,
        "gpu_memory_used_mb": 0,
        "gpu_memory_total_mb": 0,
        "gpu_utilization": 0,
        "disk_used_percent": 0,
        "uptime_hours": 0,
    }
    
    try:
        # CPU and Memory via psutil if available
        try:
            import psutil
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            metrics["memory_percent"] = mem.percent
            metrics["memory_used_gb"] = round(mem.used / (1024**3), 2)
            metrics["memory_total_gb"] = round(mem.total / (1024**3), 2)
            
            disk = psutil.disk_usage('/')
            metrics["disk_used_percent"] = disk.percent
            
            # Uptime
            boot_time = psutil.boot_time()
            metrics["uptime_hours"] = round((time.time() - boot_time) / 3600, 1)
        except ImportError:
            pass
        
        # GPU via nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", 
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 3:
                    metrics["gpu_memory_used_mb"] = int(parts[0])
                    metrics["gpu_memory_total_mb"] = int(parts[1])
                    metrics["gpu_utilization"] = int(parts[2])
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
    
    return metrics


# ============================================================
# JETSON POWER / THERMALS
# ============================================================

_POWER_PATTERNS = [
    re.compile(r"(POM_5V_IN|VDD_IN)\s*=?\s*(\d+)\s*mW", re.IGNORECASE),
    re.compile(r"(\d+)\s*mW"),
]


def _parse_tegrastats_power(raw: str) -> Dict[str, Any]:
    """Extract power (W) and basic temps from tegrastats output."""
    if not raw:
        return {"power_watts": None, "temps": {}}
    
    power_watts = None
    temps: Dict[str, int] = {}
    
    for pattern in _POWER_PATTERNS:
        match = pattern.search(raw)
        if match:
            try:
                mw_value = int(match.group(match.lastindex or 1))
                power_watts = round(mw_value / 1000, 2)
                break
            except (TypeError, ValueError):
                continue

    temp_keys = {
        "GPU": "gpu",
        "CPU": "cpu",
        "Tboard": "board",
        "Tdiode": "die",
    }
    for token, key in temp_keys.items():
        m = re.search(rf"{token}@(\d+)", raw)
        if m:
            try:
                temps[key] = int(m.group(1))
            except ValueError:
                continue

    return {"power_watts": power_watts, "temps": temps}


def _run_jetson_power_command(ip: str, user: str, password: str, timeout: float = 6.0) -> Dict[str, Any]:
    """Run tegrastats on a Jetson node and parse power/thermal data."""
    if not shutil.which("sshpass"):
        return {"online": False, "error": "sshpass not installed"}

    ssh_target = f"{user}@{ip}"
    cmd = [
        "sshpass", "-p", password,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={int(timeout)}",
        ssh_target,
        "tegrastats --interval 1000 --count 1 || sudo tegrastats --interval 1000 --count 1",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return {"online": False, "error": str(exc)}

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return {"online": False, "error": output.strip() or "tegrastats failed"}

    parsed = _parse_tegrastats_power(output)
    return {
        "online": True,
        "raw": output.strip(),
        "power_watts": parsed.get("power_watts"),
        "temps": parsed.get("temps", {}),
    }


def get_jetson_power_status(ttl: int = 10) -> Dict[str, Any]:
    """Return power/thermal snapshot for each Jetson node."""
    cached = _get_cached("jetson_power", ttl=ttl)
    if cached:
        return cached

    nodes: List[Dict[str, Any]] = []
    total_power = 0.0
    online_nodes = 0

    for name, cfg in NANO_NODES.items():
        user = cfg.get("user") or name.lower()
        password = cfg.get("password") or DEFAULT_NANO_PASSWORD
        node_result = {
            "name": name,
            "ip": cfg.get("ip"),
            "online": False,
            "power_watts": None,
            "temps": {},
            "error": None,
        }

        result = _run_jetson_power_command(cfg.get("ip", ""), user, password)
        node_result.update({
            "online": result.get("online", False),
            "power_watts": result.get("power_watts"),
            "temps": result.get("temps", {}),
            "error": result.get("error"),
        })

        if node_result["online"]:
            online_nodes += 1
            if isinstance(node_result.get("power_watts"), (int, float)):
                total_power += float(node_result["power_watts"])

        nodes.append(node_result)

    summary = {
        "nodes": nodes,
        "online": online_nodes,
        "total": len(NANO_NODES),
        "aggregate_power_watts": round(total_power, 2) if total_power else None,
        "timestamp": datetime.now().isoformat(),
    }

    _set_cached("jetson_power", summary)
    return summary


def get_ollama_model_info() -> Dict[str, Any]:
    """Get info about loaded Ollama models on ORKA."""
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return {
                "models": [
                    {
                        "name": m.get("name"),
                        "size_gb": round(m.get("size", 0) / (1024**3), 2),
                        "modified": m.get("modified_at"),
                    }
                    for m in models
                ],
                "count": len(models),
            }
    except Exception as e:
        logger.debug(f"Error getting Ollama info: {e}")
    
    return {"models": [], "count": 0}


# ============================================================
# AGENT STATUS
# ============================================================

def get_agent_status_live() -> Dict[str, Dict[str, Any]]:
    """Get live status of all agents."""
    # Check cache
    cached = _get_cached('agent_status')
    if cached:
        return cached
    
    cluster = get_cluster_status_live()
    
    agents = {}
    for name, node in cluster["nodes"].items():
        config = NANO_NODES.get(name, ORKA_NODE if name == "ORKA" else {})
        
        # Determine if agent can submit proposals
        can_submit = name not in ["PAGEQA", "ORKA"]
        
        agents[name] = {
            "name": name,
            "online": node.get("online", False),
            "model": node.get("model") or config.get("model", "unknown"),
            "role": config.get("role", "unknown"),
            "can_submit_proposals": can_submit,
            "ip": node.get("ip", config.get("ip", "unknown")),
            "response_time_ms": node.get("response_time_ms"),
            # Live metrics would go here
            "pending_proposals": 0,
            "submitted_proposals": 0,
            "last_activity": None,
        }
    
    _set_cached('agent_status', agents)
    return agents


def get_agent_statistics(agent_id: str) -> Dict[str, Any]:
    """Get statistics for a specific agent."""
    agent_status = get_agent_status_live()
    agent = agent_status.get(agent_id.upper(), {})
    
    # Try to get real proposal data from memory
    try:
        from memory.orchestrator_adapter import create_adapter_for_nano
        adapter = create_adapter_for_nano(agent_id.upper(), agent.get("ip", "localhost"))
        proposals = adapter.get_proposal_context("", max_similar=100)
        
        # Calculate stats from real proposals
        approved = sum(1 for p in proposals if p.get("status") == "approved")
        rejected = sum(1 for p in proposals if p.get("status") == "rejected")
        total = len(proposals)
        
        return {
            "total_proposals": total,
            "approved": approved,
            "rejected": rejected,
            "in_review": total - approved - rejected,
            "approval_rate": (approved / total) if total > 0 else 0.0,
            "avg_deception": 0.0,  # Would need deception scores
            "total_rewards": sum(p.get("reward", 0) for p in proposals),
            "incidents": 0,
            "penalty_multiplier": 1.0,
        }
    except Exception as e:
        logger.debug(f"Could not get real proposal data for {agent_id}: {e}")
    
    # Return defaults
    return {
        "total_proposals": 0,
        "approved": 0,
        "rejected": 0,
        "in_review": 0,
        "approval_rate": 0.0,
        "avg_deception": 0.0,
        "total_rewards": 0.0,
        "incidents": 0,
        "penalty_multiplier": 1.0,
    }


# ============================================================
# PROPOSALS (from memory system)
# ============================================================

# In-memory store for proposals until memory system is fully integrated
_live_proposals: List[Dict[str, Any]] = []
_live_detection_events: List[Dict[str, Any]] = []


def record_proposal(proposal: Dict[str, Any]):
    """Record a new proposal."""
    proposal["timestamp"] = datetime.now().isoformat()
    if "id" not in proposal:
        proposal["id"] = f"prop_{int(time.time() * 1000)}"
    _live_proposals.insert(0, proposal)
    # Keep last 1000
    if len(_live_proposals) > 1000:
        _live_proposals.pop()


def record_detection_event(event: Dict[str, Any]):
    """Record a detection event."""
    event["timestamp"] = datetime.now().isoformat()
    if "id" not in event:
        event["id"] = f"det_{int(time.time() * 1000)}"
    _live_detection_events.insert(0, event)
    # Keep last 500
    if len(_live_detection_events) > 500:
        _live_detection_events.pop()


def get_recent_proposals(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent proposals from live data."""
    return _live_proposals[:limit]


def get_proposals_by_agent(agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get proposals for a specific agent."""
    filtered = [p for p in _live_proposals if p.get("agent_id") == agent_id]
    return filtered[:limit]


def get_proposal_by_id(proposal_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific proposal by ID."""
    for p in _live_proposals:
        if p.get("id") == proposal_id or p.get("proposal_id") == proposal_id:
            return p
    return None


def load_proposals() -> List[Dict[str, Any]]:
    """Load all proposals."""
    return _live_proposals


def load_detection_events() -> List[Dict[str, Any]]:
    """Load all detection events."""
    return _live_detection_events


def load_agent_states() -> Dict[str, Dict[str, Any]]:
    """Load agent states from live data."""
    return get_agent_status_live()


def get_detection_events_recent(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent detection events."""
    return _live_detection_events[:limit]


def get_system_statistics() -> Dict[str, Any]:
    """Get overall system statistics."""
    cluster = get_cluster_status_live()
    metrics = get_local_system_metrics()
    
    total = len(_live_proposals)
    approved = sum(1 for p in _live_proposals if p.get("status") == "approved")
    rejected = sum(1 for p in _live_proposals if p.get("status") == "rejected")
    
    return {
        "total_proposals": total,
        "approved": approved,
        "rejected": rejected,
        "in_review": total - approved - rejected,
        "approval_rate": (approved / total) if total > 0 else 0.0,
        "total_detection_events": len(_live_detection_events),
        "active_penalties": 0,
        "avg_penalty_multiplier": 1.0,
        "cluster_online": cluster["online_count"],
        "cluster_total": cluster["total_count"],
        "system_metrics": metrics,
    }


# ============================================================
# HEALTH & INFRASTRUCTURE
# ============================================================

def get_infrastructure_health() -> Dict[str, Any]:
    """Get health of all infrastructure components."""
    cluster = get_cluster_status_live()
    metrics = get_local_system_metrics()
    ollama = get_ollama_model_info()
    
    # Calculate health scores
    cluster_health = cluster["online_count"] / cluster["total_count"] if cluster["total_count"] > 0 else 0
    
    memory_health = 1.0 - (metrics["memory_percent"] / 100) if metrics["memory_percent"] else 0.5
    gpu_health = 1.0 - (metrics["gpu_utilization"] / 100) if metrics["gpu_utilization"] else 0.5
    
    overall_health = (cluster_health * 0.4 + memory_health * 0.3 + gpu_health * 0.3)
    
    return {
        "overall_health": round(overall_health, 3),
        "cluster_health": round(cluster_health, 3),
        "memory_health": round(memory_health, 3),
        "gpu_health": round(gpu_health, 3),
        "cluster": cluster,
        "system_metrics": metrics,
        "ollama": ollama,
        "timestamp": datetime.now().isoformat(),
    }


def get_service_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all services."""
    services = {}
    
    # Ollama on ORKA
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        services["ollama_orka"] = {
            "name": "Ollama (ORKA)",
            "status": "running" if resp.status_code == 200 else "error",
            "port": 11434,
        }
    except:
        services["ollama_orka"] = {"name": "Ollama (ORKA)", "status": "stopped", "port": 11434}
    
    # Flask UI
    try:
        import requests
        resp = requests.get("http://localhost:5001/api/health", timeout=2)
        services["flask_ui"] = {
            "name": "Flask UI",
            "status": "running" if resp.status_code == 200 else "error",
            "port": 5001,
        }
    except:
        services["flask_ui"] = {"name": "Flask UI", "status": "unknown", "port": 5001}
    
    # Memory server (shared memory API on Flask)
    try:
        import requests
        resp = requests.get("http://localhost:5001/api/shared/stats", timeout=2)
        services["memory_server"] = {
            "name": "Shared Memory API",
            "status": "running" if resp.status_code == 200 else "error",
            "port": 5001,
        }
    except:
        services["memory_server"] = {"name": "Shared Memory API", "status": "stopped", "port": 5001}
    
    return services


# ============================================================
# INITIALIZATION
# ============================================================

# Proposal performance tracking (real data)
_proposal_performance: Dict[str, Dict[str, Any]] = {}
_time_series_cache: Dict[str, List[Dict[str, Any]]] = {}


def get_proposal_performance(proposal_id: str) -> Dict[str, Any]:
    """Get real performance data for a proposal."""
    if proposal_id in _proposal_performance:
        return _proposal_performance[proposal_id]
    
    # Return empty performance data for unknown proposals
    return {
        'proposal_id': proposal_id,
        'status': 'pending',
        'success_rate': 0.0,
        'uptime_percentage': 0.0,
        'error_count': 0,
        'performance_score': 0.0,
        'response_time_ms': 0,
        'throughput': 0,
        'memory_usage_mb': 0,
        'cpu_usage_percent': 0,
    }


def record_proposal_performance(proposal_id: str, metrics: Dict[str, Any]):
    """Record performance metrics for a proposal."""
    metrics['proposal_id'] = proposal_id
    metrics['updated_at'] = datetime.now().isoformat()
    _proposal_performance[proposal_id] = metrics


def get_time_series_data(proposal_id: str) -> List[Dict[str, Any]]:
    """Get time series performance data for a proposal."""
    return _time_series_cache.get(proposal_id, [])


def record_time_series_point(proposal_id: str, metrics: Dict[str, Any]):
    """Record a time series data point."""
    if proposal_id not in _time_series_cache:
        _time_series_cache[proposal_id] = []
    
    metrics['timestamp'] = datetime.now().isoformat()
    _time_series_cache[proposal_id].append(metrics)
    
    # Keep last 24 hours (1440 minutes if recording every minute)
    if len(_time_series_cache[proposal_id]) > 1440:
        _time_series_cache[proposal_id] = _time_series_cache[proposal_id][-1440:]


def get_recent_errors() -> List[Dict[str, Any]]:
    """Get recent system errors."""
    # Check logs for real errors
    errors = []
    log_file = Path("/home/xx/AI-Safety-System-Design/logs/ui.log")
    
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
                for line in lines:
                    if 'ERROR' in line or 'error' in line.lower():
                        errors.append({
                            'timestamp': datetime.now().isoformat(),
                            'severity': 'high' if 'ERROR' in line else 'medium',
                            'message': line.strip()[:200],
                            'resolved': False,
                        })
        except Exception:
            pass
    
    return errors[-20:]  # Return last 20 errors


def get_resource_usage() -> Dict[str, Any]:
    """Get real resource usage metrics."""
    metrics = get_local_system_metrics()
    
    return {
        'cpu': {
            'current': metrics.get('cpu_percent', 0),
            'average': metrics.get('cpu_percent', 0),  # Would need history for avg
            'peak': metrics.get('cpu_percent', 0),
        },
        'memory': {
            'current': metrics.get('memory_used_gb', 0) * 1024,  # Convert to MB
            'average': metrics.get('memory_used_gb', 0) * 1024,
            'peak': metrics.get('memory_total_gb', 0) * 1024,
        },
        'gpu': {
            'current': metrics.get('gpu_memory_used_mb', 0),
            'utilization': metrics.get('gpu_utilization', 0),
            'total': metrics.get('gpu_memory_total_mb', 0),
        },
        'network': {
            'bandwidth_mbps': 0,  # Would need network monitoring
            'requests_per_sec': 0,
        }
    }


print("📡 Live Data Provider initialized")
print(f"   - Cluster nodes: {len(NANO_NODES) + 1}")
print(f"   - Cache TTL: {CACHE_TTL}s")
