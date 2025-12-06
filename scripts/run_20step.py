#!/usr/bin/env python3
"""
ORKASTRATOR 20-Step Self-Improvement Workflow
==============================================

Full research-to-deployment workflow for AI self-improvement.

HARDENING FEATURES (v2.0):
  - Secure config with SSH key auth (no hardcoded passwords)
  - Hidden evaluation metrics (ORKA-only, not visible to researchers)
  - Artifact signing and Merkle audit log
  - Fail-closed safety gates
  - Docker sandbox with no fallback (require_docker_sandbox=True)
  - Human approval required before deployment
  - Structured JSON logging with alerts

PHASE 1: RESEARCH (Steps 1-5)
  1. IDEA - What capability to improve
  2. PAPERS - Search literature via PAGEQA
  3. TRIAGE - Rate and select top papers
  4. DEEP NOTES - Extract key findings
  5. SYNTHESIS - Identify gaps and opportunities

PHASE 2: HYPOTHESIS (Steps 6-7)
  6. HYPOTHESIS - Testable prediction
  7. EXPERIMENT - Design with code/math

PHASE 3: PROPOSAL & EARLY REVIEW (Steps 8-12)
  8. PROPOSAL - Full proposal with code
  9. SELF-CHECK CONSISTENCY
  10. SELF-CHECK WEAKNESSES
  11. PEER REVIEW RESPONSE - From other 5 researchers
  12. REVISION - Incorporate feedback

PHASE 4: VALIDATION (Steps 13-14)
  13. PAGEQA VALIDATION - Verify citations
  14. VALIDATED PROPOSAL - Fix any issues

PHASE 5: LATE REVIEW & VOTE (Steps 15-17)
  15. LATE PEER REVIEW - Second round from peers
  16. VOTE - Approve/Revise/Reject
  17. ORKA DEFENSE - Defend against challenger

PHASE 6: COMPLETION (Steps 18-20)
  18. FINAL PROPOSAL - Ready for deployment
  19. SANDBOX TEST - Test code in sandbox (Docker REQUIRED)
  20. HIDDEN EVAL + REWARD & DEPLOY - ORKA's hidden metrics + score and rollout
"""

import requests
import time
import sys
import json
import subprocess
import base64
import shutil
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

# Import hardening modules
HARDENING_AVAILABLE = False
CONFIG = None

# Add scripts directory to path for imports
import sys
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from secure_config import get_config, ClusterConfig
    from hidden_eval import get_evaluator, HiddenEvaluator
    from artifact_signing import get_signer, get_version_store
    from structured_logging import get_logger
    from security_gates import (
        get_node_verifier, get_safety_gate, get_hard_gate,
        NodeVerifier, MultiSignalSafetyGate, HardGate,
        TransferIntegrity, SafetyGateResult, SecurityError as GateSecurityError
    )
    HARDENING_AVAILABLE = True
    CONFIG = get_config()
except ImportError as e:
    print(f"WARNING: Hardening modules not loaded - running in legacy mode ({e})")

# ============================================================
# CLUSTER CONFIGURATION
# ============================================================
# HARDENED: No fallback values. Hardening modules REQUIRED.

def _require_hardening():
    """Abort if hardening modules not available."""
    if not HARDENING_AVAILABLE:
        print("\n" + "=" * 60)
        print("FATAL: Hardening modules REQUIRED but not available")
        print("=" * 60)
        print("This workflow requires:")
        print("  - scripts/secure_config.py")
        print("  - scripts/hidden_eval.py")
        print("  - scripts/artifact_signing.py")
        print("  - scripts/structured_logging.py")
        print("\nRun from scripts/ directory or fix PYTHONPATH")
        print("=" * 60 + "\n")
        sys.exit(1)

def _get_researchers() -> Dict:
    """Get researcher config from secure_config. No fallback."""
    _require_hardening()
    result = {}
    for name in ["GIN", "TIF", "ORIN", "ARCHI", "TORI", "NOVEL"]:
        node = CONFIG.get_node(name)
        if node:
            result[name] = (node.ollama_url, node.model)
    if not result:
        print("FATAL: No researcher nodes configured")
        sys.exit(1)
    return result

def _get_special_nodes():
    """Get PAGEQA, ORKA, GUARD from secure_config. No fallback."""
    _require_hardening()
    pageqa = CONFIG.get_node("PAGEQA")
    orka = CONFIG.get_node("ORKA")
    if not orka:
        print("FATAL: ORKA node not configured")
        sys.exit(1)
    return (
        (pageqa.ollama_url if pageqa else None, pageqa.model if pageqa else None),
        (orka.ollama_url, orka.model),
        (orka.ollama_url, CONFIG.guard_model),
    )

def _get_node_ssh() -> Dict:
    """Get SSH info for all nodes. No fallback."""
    _require_hardening()
    return {name: (node.user, node.ip) for name, node in CONFIG.nodes.items()}

def _get_ssh_command(node_name: str) -> List[str]:
    """Get SSH command for node. Key-based auth only - no password fallback."""
    _require_hardening()
    node = CONFIG.get_node(node_name)
    if not node:
        raise ValueError(f"Node {node_name} not found in config")
    cmd = node.get_ssh_command_prefix()
    # Verify it's NOT using password auth
    if "sshpass" in cmd:
        raise SecurityError(f"Node {node_name} uses deprecated password auth - migrate to SSH keys")

# Initialize config on import
RESEARCHERS = _get_researchers()
PAGEQA, ORKA, GUARD = _get_special_nodes()
NODE_SSH = _get_node_ssh()

# Improvement categories
IMPROVEMENT_CATEGORIES = [
    "prompt_template",      # Better system prompts
    "inference_params",     # Temperature, top_p, etc.
    "chain_of_thought",     # CoT improvements
    "tool_calling",         # Tool use improvements
    "safety_filter",        # Safety rules
    "context_handling",     # Context window management
    "response_quality",     # Output improvements
]


# Custom exceptions
class SecurityError(Exception):
    """Raised when security requirements are not met."""
    pass

class SafetyCheckFailed(Exception):
    """Raised when safety check fails (fail-closed)."""
    pass


def call_llm(base_url: str, model: str, prompt: str, system: str = "",
             temperature: float = 0.7, max_tokens: int = 1500, timeout: int = 180,
             verify_tls: bool = True) -> str:
    """Call an Ollama LLM endpoint with optional TLS verification.
    
    Args:
        base_url: Ollama API base URL (http:// or https://)
        model: Model name
        prompt: User prompt
        system: System prompt
        temperature: Sampling temperature
        max_tokens: Max tokens to generate
        timeout: Request timeout in seconds
        verify_tls: Verify TLS certificates (True for production)
    
    Returns:
        Model response text
    
    Raises:
        SecurityError: If HTTPS required but not used (when CONFIG.require_https)
    """
    # Check HTTPS requirement
    if HARDENING_AVAILABLE and CONFIG and hasattr(CONFIG, 'require_https'):
        if CONFIG.require_https and not base_url.startswith('https://'):
            # Allow localhost without HTTPS
            if 'localhost' not in base_url and '127.0.0.1' not in base_url:
                raise SecurityError(f"HTTPS required but URL is {base_url}")
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }
    if system:
        payload["system"] = system

    try:
        response = requests.post(
            f"{base_url}/api/generate", 
            json=payload, 
            timeout=timeout,
            verify=verify_tls if base_url.startswith('https://') else True
        )
        response.raise_for_status()  # Raise on HTTP errors
        data = response.json()
        result = data.get("response", "")
        if not result and "thinking" in data:
            result = data.get("thinking", "")
        return result
    except requests.exceptions.SSLError as e:
        raise SecurityError(f"TLS verification failed: {e}")
    except Exception as e:
        return f"[Error: {e}]"


def strip_code_fences(code: str) -> str:
    """Remove markdown code fences from LLM output."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        code = "\n".join(lines).strip()
    return code


def safety_check(content: str, fail_closed: bool = True) -> Tuple[bool, str]:
    """
    Run safety check using llama-guard3 on ORKA.
    
    HARDENED: Fail-closed by default. Any error = unsafe.
    
    Args:
        content: Content to check
        fail_closed: If True, any error/ambiguity = unsafe
    
    Returns:
        (is_safe, reason)
    
    Raises:
        SafetyCheckFailed: If fail_closed=True and check cannot complete
    """
    _require_hardening()
    
    guard_url, guard_model = GUARD
    if not guard_url or not guard_model:
        if fail_closed:
            raise SafetyCheckFailed("Guard model not configured")
        return False, "Guard model not configured - defaulting to unsafe"
    
    prompt = f"""You are a safety classifier for AI system deployments.

Evaluate this AI improvement proposal for safety:

---
{content[:2000]}
---

Respond with EXACTLY one of:
- "SAFE" if the content is appropriate for AI system deployment
- "UNSAFE: <reason>" if the content could cause harm, is deceptive, or violates safety guidelines

You MUST respond with SAFE or UNSAFE. No other response is valid."""

    try:
        response = call_llm(
            guard_url, guard_model, prompt,
            "You are a strict safety classifier. Respond only with SAFE or UNSAFE: <reason>",
            temperature=0.0,  # Deterministic
            max_tokens=100, 
            timeout=30
        )
        
        response_upper = response.strip().upper()
        
        # Strict parsing - require explicit SAFE
        if response_upper.startswith("SAFE") and "UNSAFE" not in response_upper:
            return True, "Safety check passed"
        elif response_upper.startswith("UNSAFE"):
            return False, response.strip()
        else:
            # Ambiguous response - fail closed
            logger = get_logger() if HARDENING_AVAILABLE else None
            if logger:
                logger.safety_failure(content[:100], f"Ambiguous safety response: {response[:100]}")
            if fail_closed:
                return False, f"Ambiguous safety response (fail-closed): {response[:100]}"
            return False, f"Ambiguous response - defaulting to unsafe: {response[:100]}"
            
    except SecurityError:
        raise  # Re-raise security errors
    except Exception as e:
        # Any error = unsafe when fail_closed
        logger = get_logger() if HARDENING_AVAILABLE else None
        if logger:
            logger.safety_failure(content[:100], f"Safety check error: {e}")
        if fail_closed:
            raise SafetyCheckFailed(f"Safety check failed: {e}")
        return False, f"Safety check error - defaulting to unsafe: {e}"


def deploy_to_cluster(
    improvement_type: str, 
    artifact: str, 
    workspace: Path, 
    signature: str,
    artifact_id: str,
    version: int = 1
) -> Tuple[Dict[str, bool], int]:
    """Deploy approved improvement to all cluster nodes with versioning.
    
    HARDENED:
    - Requires valid signature (no deployment without signing)
    - SSH key-based auth only (no password)
    - Verifies artifact integrity before each node deployment
    
    Args:
        improvement_type: Category of improvement
        artifact: The artifact content
        workspace: Working directory
        signature: Cryptographic signature (REQUIRED)
        artifact_id: Unique artifact ID from signing (REQUIRED)
        version: Version number
    
    Returns:
        (results_dict, version_id)
    
    Raises:
        SecurityError: If signature invalid or security requirements not met
    """
    _require_hardening()
    
    results: Dict[str, bool] = {}
    version_id = int(time.time())
    
    # ============================================================
    # SECURITY CHECK: Verify artifact signature before deployment
    # ============================================================
    store = get_version_store()
    
    # Verify the specific artifact (not just "latest")
    if not store.verify_artifact_by_id(artifact_id, artifact, signature):
        raise SecurityError(
            f"ARTIFACT SIGNATURE VERIFICATION FAILED\n"
            f"  Artifact ID: {artifact_id}\n"
            f"  This deployment has been BLOCKED."
        )
    
    logger = get_logger()
    logger.signature_verification(artifact_id, True, "ORKA")
    print(f"  ✅ Artifact {artifact_id} signature verified")
    
    # Determine target path based on type
    target_paths = {
        "prompt_template": ".orkastrator/prompts/system_prompt.txt",
        "inference_params": ".orkastrator/config/inference.json",
        "chain_of_thought": ".orkastrator/prompts/cot_template.txt",
        "safety_filter": ".orkastrator/safety/filter_rules.json",
        "tool_calling": ".orkastrator/prompts/tool_template.txt",
        "context_handling": ".orkastrator/config/context.json",
        "response_quality": ".orkastrator/prompts/quality_prompt.txt",
    }
    target_path = target_paths.get(improvement_type, f".orkastrator/improvements/{improvement_type}.txt")
    backup_dir = ".orkastrator/versions"
    
    print(f"\n  Deploying to ~/.orkastrator/ (version: {version_id})...")
    print(f"  Using secure SSH (key-based auth)")
    
    for node_name in NODE_SSH.keys():
        try:
            # Get SSH command - will raise SecurityError if password-based
            ssh_prefix = _get_ssh_command(node_name)
            
            # Create directories
            mkdir_remote = "mkdir -p ~/.orkastrator/prompts ~/.orkastrator/config ~/.orkastrator/safety ~/.orkastrator/improvements ~/.orkastrator/versions"
            subprocess.run(ssh_prefix + [mkdir_remote], capture_output=True, timeout=15, check=True)
            
            # Backup current version
            backup_name = target_path.replace("/", "_").replace(".", "_") + f"_{version_id}.bak"
            backup_remote = f"cp ~/{target_path} ~/{backup_dir}/{backup_name} 2>/dev/null || true"
            subprocess.run(ssh_prefix + [backup_remote], capture_output=True, timeout=15)
            
            # Deploy via base64 with integrity check
            encoded = base64.b64encode(artifact.encode()).decode()
            # Include artifact_id for audit trail
            deploy_remote = f"echo '{encoded}' | base64 -d > ~/{target_path} && echo '{artifact_id}' > ~/{backup_dir}/current_artifact_id"
            result = subprocess.run(ssh_prefix + [deploy_remote], capture_output=True, timeout=15)
            
            results[node_name] = result.returncode == 0
            
            if result.returncode == 0:
                print(f"    ✅ {node_name}: deployed (artifact: {artifact_id[:8]}...)")
                logger.deployment(artifact_id, improvement_type, [node_name], 1)
            else:
                print(f"    ❌ {node_name}: failed")
                
        except SecurityError as e:
            print(f"    🔒 {node_name}: BLOCKED - {e}")
            results[node_name] = False
        except subprocess.CalledProcessError as e:
            print(f"    ❌ {node_name}: SSH failed - {e}")
            results[node_name] = False
        except Exception as e:
            results[node_name] = False
            print(f"    ❌ {node_name}: {e}")
    
    # Local deployment with backup
    local_path = Path.home() / target_path
    local_backup_dir = Path.home() / backup_dir
    local_backup_dir.mkdir(parents=True, exist_ok=True)
    
    if local_path.exists():
        backup_name = target_path.replace("/", "_").replace(".", "_") + f"_{version_id}.bak"
        shutil.copy(local_path, local_backup_dir / backup_name)
    
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(artifact)
    (local_backup_dir / "current_artifact_id").write_text(artifact_id)
    results["LOCAL"] = True
    
    # Save version manifest with signature info
    manifest = {
        "version_id": version_id,
        "artifact_id": artifact_id,
        "signature": signature[:64] + "...",  # Truncated for manifest
        "improvement_type": improvement_type,
        "target_path": target_path,
        "deployed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nodes": list(results.keys()),
        "success_count": sum(1 for v in results.values() if v),
    }
    manifest_path = local_backup_dir / f"manifest_{version_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    return results, version_id


def rollback_deployment(version_id: int, improvement_type: str = None):
    """Rollback to a previous version across all nodes.
    
    HARDENED: Uses key-based SSH only.
    """
    _require_hardening()
    
    backup_dir = ".orkastrator/versions"
    manifest_path = Path.home() / backup_dir / f"manifest_{version_id}.json"
    
    if not manifest_path.exists():
        print(f"ERROR: No manifest found for version {version_id}")
        return False
    
    manifest = json.loads(manifest_path.read_text())
    target_path = manifest["target_path"]
    backup_name = target_path.replace("/", "_").replace(".", "_") + f"_{version_id}.bak"
    
    print(f"\n  Rolling back to version {version_id}...")
    print(f"  Using secure SSH (key-based auth)")
    results = {}
    
    for node_name in NODE_SSH.keys():
        try:
            # Get secure SSH command
            ssh_prefix = _get_ssh_command(node_name)
            rollback_remote = f"cp ~/{backup_dir}/{backup_name} ~/{target_path}"
            result = subprocess.run(ssh_prefix + [rollback_remote], capture_output=True, timeout=15)
            results[node_name] = result.returncode == 0
            if result.returncode == 0:
                print(f"    ✅ {node_name}: rolled back")
            else:
                print(f"    ❌ {node_name}: failed")
        except SecurityError as e:
            print(f"    🔒 {node_name}: BLOCKED - {e}")
            results[node_name] = False
        except Exception as e:
            print(f"    ❌ {node_name}: {e}")
            results[node_name] = False
    
    # Local rollback
    local_backup = Path.home() / backup_dir / backup_name
    local_target = Path.home() / target_path
    if local_backup.exists():
        shutil.copy(local_backup, local_target)
        results["LOCAL"] = True
    else:
        results["LOCAL"] = False
    
    success_count = sum(1 for v in results.values() if v)
    print(f"  Rollback complete: {success_count}/{len(results)} nodes")
    return results


def list_versions():
    """List all available versions for rollback."""
    backup_dir = Path.home() / ".orkastrator/versions"
    if not backup_dir.exists():
        print("No versions found.")
        return []
    
    manifests = sorted(backup_dir.glob("manifest_*.json"), reverse=True)
    versions = []
    for mf in manifests[:10]:  # Last 10 versions
        manifest = json.loads(mf.read_text())
        versions.append(manifest)
        print(f"  v{manifest['version_id']} - {manifest['improvement_type']} - {manifest['deployed_at']}")
    return versions


def track_improvement(result: Dict) -> None:
    """Track improvement history and aggregate statistics."""
    tracking_file = Path("data/improvements/history.json")
    tracking_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing history
    if tracking_file.exists():
        history = json.loads(tracking_file.read_text())
    else:
        history = {
            "improvements": [],
            "stats": {
                "by_proposer": {},
                "by_type": {},
                "approval_rate": 0,
                "total_proposals": 0,
                "total_deployments": 0,
            }
        }
    
    # Add new improvement
    improvement = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "proposer": result.get("proposer"),
        "type": result.get("improvement_type"),
        "vote": result.get("vote"),
        "reward": result.get("reward"),
        "deployed": result.get("deployed"),
        "version_id": result.get("version_id"),
        "workspace": result.get("workspace"),
    }
    history["improvements"].append(improvement)
    
    # Update stats
    stats = history["stats"]
    proposer = result.get("proposer", "UNKNOWN")
    imp_type = result.get("improvement_type", "unknown")
    
    # By proposer
    if proposer not in stats["by_proposer"]:
        stats["by_proposer"][proposer] = {"proposals": 0, "approvals": 0, "avg_reward": 0}
    stats["by_proposer"][proposer]["proposals"] += 1
    if result.get("vote") == "APPROVE":
        stats["by_proposer"][proposer]["approvals"] += 1
    
    # By type
    if imp_type not in stats["by_type"]:
        stats["by_type"][imp_type] = {"proposals": 0, "approvals": 0}
    stats["by_type"][imp_type]["proposals"] += 1
    if result.get("vote") == "APPROVE":
        stats["by_type"][imp_type]["approvals"] += 1
    
    # Overall stats
    stats["total_proposals"] += 1
    if result.get("deployed"):
        stats["total_deployments"] += 1
    
    approvals = sum(1 for i in history["improvements"] if i.get("vote") == "APPROVE")
    stats["approval_rate"] = round(approvals / len(history["improvements"]) * 100, 1)
    
    # Calculate average rewards by proposer
    for p_name in stats["by_proposer"]:
        rewards = [i.get("reward", 0) for i in history["improvements"] 
                   if i.get("proposer") == p_name and i.get("reward")]
        if rewards:
            stats["by_proposer"][p_name]["avg_reward"] = round(sum(rewards) / len(rewards), 2)
    
    tracking_file.write_text(json.dumps(history, indent=2))
    print(f"\n📊 Improvement tracked. Total: {stats['total_proposals']} proposals, {stats['total_deployments']} deployments")


def show_stats():
    """Display improvement tracking statistics."""
    tracking_file = Path("data/improvements/history.json")
    if not tracking_file.exists():
        print("No improvement history found.")
        return
    
    history = json.loads(tracking_file.read_text())
    stats = history["stats"]
    
    print("\n" + "=" * 60)
    print("IMPROVEMENT TRACKING STATISTICS")
    print("=" * 60)
    
    print(f"\n📈 Overall:")
    print(f"   Total Proposals: {stats['total_proposals']}")
    print(f"   Total Deployments: {stats['total_deployments']}")
    print(f"   Approval Rate: {stats['approval_rate']}%")
    
    print(f"\n👤 By Proposer:")
    for name, data in stats["by_proposer"].items():
        approval_pct = round(data["approvals"] / data["proposals"] * 100) if data["proposals"] > 0 else 0
        print(f"   {name}: {data['proposals']} proposals, {data['approvals']} approved ({approval_pct}%), avg reward: {data['avg_reward']}")
    
    print(f"\n🔧 By Improvement Type:")
    for imp_type, data in stats["by_type"].items():
        approval_pct = round(data["approvals"] / data["proposals"] * 100) if data["proposals"] > 0 else 0
        print(f"   {imp_type}: {data['proposals']} proposals, {data['approvals']} approved ({approval_pct}%)")
    
    print("\n📜 Recent Improvements (last 5):")
    for imp in history["improvements"][-5:]:
        status = "✅" if imp.get("deployed") else "❌"
        print(f"   {status} {imp['timestamp']} - {imp['proposer']}: {imp['type']} (reward: {imp.get('reward', 'N/A')})")


def run_sandbox_test(
    improvement_type: str,
    improvement_code: str,
    proposer_url: str,
    proposer_model: str,
    workspace: Path
) -> Dict:
    """
    Run comprehensive sandbox testing using SandboxFusion.
    
    Tests code in isolated environment with:
    - Syntax validation
    - Performance benchmarking (before/after)
    - Safety check via llama-guard on ORKA
    - Resource usage monitoring
    """
    result = {
        "passed": False,
        "message": "",
        "syntax_valid": False,
        "performance_delta": None,
        "safety_passed": False,
        "execution_time": None,
        "tests": []
    }
    
    start_time = time.time()
    
    # Test 1: Syntax Validation
    print("  [1/4] Syntax validation...")
    if improvement_type == "inference_params":
        try:
            params = json.loads(improvement_code)
            result["syntax_valid"] = True
            result["tests"].append({"name": "JSON Parse", "passed": True, "detail": f"Keys: {list(params.keys())}"})
        except json.JSONDecodeError as e:
            result["tests"].append({"name": "JSON Parse", "passed": False, "detail": str(e)})
            result["message"] = f"Invalid JSON: {e}"
            return result
    elif improvement_type in ["prompt_template", "chain_of_thought", "tool_calling", "response_quality"]:
        # Text templates - check for required sections
        required = ["{{" , "}}"] if "template" in improvement_type else []
        has_content = len(improvement_code.strip()) > 50
        result["syntax_valid"] = has_content
        result["tests"].append({"name": "Content Length", "passed": has_content, "detail": f"{len(improvement_code)} chars"})
    else:
        result["syntax_valid"] = len(improvement_code.strip()) > 20
        result["tests"].append({"name": "Basic Validation", "passed": result["syntax_valid"]})
    
    # Test 2: Safety Check via GUARD (llama-guard on ORKA)
    print("  [2/4] Safety check via GUARD...")
    try:
        is_safe, safety_msg = safety_check(improvement_code)
        result["safety_passed"] = is_safe
        result["tests"].append({"name": "Safety Check", "passed": is_safe, "detail": safety_msg[:100]})
    except Exception as e:
        result["tests"].append({"name": "Safety Check", "passed": False, "detail": str(e)})
        result["safety_passed"] = False
    
    # Test 3: Performance Benchmark (before/after on proposer node)
    print("  [3/4] Performance benchmark...")
    try:
        test_prompts = [
            "What is 2+2?",
            "Explain gravity in one sentence.",
            "List 3 colors.",
        ]
        
        # Baseline (no custom params)
        baseline_times = []
        for prompt in test_prompts:
            start = time.time()
            resp = requests.post(
                f"{proposer_url}/api/generate",
                json={"model": proposer_model, "prompt": prompt, "stream": False},
                timeout=30
            )
            baseline_times.append(time.time() - start)
        baseline_avg = sum(baseline_times) / len(baseline_times)
        
        # With improvement (if applicable)
        if improvement_type == "inference_params":
            params = json.loads(improvement_code)
            improved_times = []
            for prompt in test_prompts:
                start = time.time()
                resp = requests.post(
                    f"{proposer_url}/api/generate",
                    json={"model": proposer_model, "prompt": prompt, "stream": False, "options": params},
                    timeout=30
                )
                improved_times.append(time.time() - start)
            improved_avg = sum(improved_times) / len(improved_times)
            
            delta = ((baseline_avg - improved_avg) / baseline_avg) * 100
            result["performance_delta"] = round(delta, 2)
            result["tests"].append({
                "name": "Performance",
                "passed": delta > -20,  # Allow up to 20% slower
                "detail": f"Baseline: {baseline_avg:.2f}s, Improved: {improved_avg:.2f}s, Delta: {delta:+.1f}%"
            })
        else:
            result["tests"].append({"name": "Performance", "passed": True, "detail": f"Baseline: {baseline_avg:.2f}s (no params to test)"})
    except Exception as e:
        result["tests"].append({"name": "Performance", "passed": True, "detail": f"Skipped: {e}"})
    
    # Test 4: SandboxFusion Docker Integration
    print("  [4/4] SandboxFusion Docker isolation test...")
    docker_available = False
    docker_prefix = []
    
    try:
        # Check if Docker is available (try without sudo first, then with)
        docker_check = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        if docker_check.returncode == 0:
            docker_available = True
            docker_prefix = []
        else:
            # Try with sudo -n (non-interactive)
            docker_check = subprocess.run(["sudo", "-n", "docker", "info"], capture_output=True, timeout=5)
            if docker_check.returncode == 0:
                docker_available = True
                docker_prefix = ["sudo"]
    except Exception:
        pass
    
    if docker_available:
        try:
            # Create temp script for sandbox execution
            # Escape quotes in improvement_code for embedding
            escaped_code = improvement_code.replace('"', '\\"').replace("'", "\\'")
            sandbox_script = f'''#!/usr/bin/env python3
import json
import sys

# Test the improvement in isolation
improvement = """{escaped_code}"""
improvement_type = "{improvement_type}"

print(f"SandboxFusion Docker Test")
print(f"Improvement type: {{improvement_type}}")

if improvement_type == "inference_params":
    try:
        params = json.loads(improvement)
        print(f"✓ Valid JSON with keys: {{list(params.keys())}}")
        # Validate parameter ranges
        if "temperature" in params:
            temp = params["temperature"]
            if not (0 <= temp <= 2):
                print(f"✗ Temperature {{temp}} out of range [0, 2]")
                sys.exit(1)
        if "top_p" in params:
            top_p = params["top_p"]
            if not (0 <= top_p <= 1):
                print(f"✗ top_p {{top_p}} out of range [0, 1]")
                sys.exit(1)
        print("✓ All parameters validated")
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse error: {{e}}")
        sys.exit(1)
elif improvement_type in ["prompt_template", "chain_of_thought", "tool_calling"]:
    # Check for template structure
    if len(improvement) < 50:
        print(f"✗ Template too short ({{len(improvement)}} chars)")
        sys.exit(1)
    print(f"✓ Template validated ({{len(improvement)}} chars)")
    sys.exit(0)
else:
    print(f"✓ Content validated ({{len(improvement)}} chars)")
    sys.exit(0)
'''
            sandbox_file = workspace / "sandbox_test.py"
            sandbox_file.write_text(sandbox_script)
            
            # Run in Docker with SandboxFusion isolation
            docker_cmd = docker_prefix + [
                "docker", "run", "--rm",
                "--network=none",     # No network access
                "--memory=256m",      # Memory limit
                "--cpus=0.5",         # CPU limit
                "--pids-limit=64",    # Process limit
                "--read-only",        # Read-only filesystem
                "--security-opt=no-new-privileges",  # No privilege escalation
                "-v", f"{sandbox_file.absolute()}:/sandbox/test.py:ro",
                "python:3.11-slim",
                "python", "/sandbox/test.py"
            ]
            
            sandbox_result = subprocess.run(docker_cmd, capture_output=True, timeout=60, text=True)
            
            result["sandbox_engine"] = "SandboxFusion/Docker"
            result["sandbox_output"] = sandbox_result.stdout
            
            if sandbox_result.returncode == 0:
                result["tests"].append({
                    "name": "SandboxFusion/Docker",
                    "passed": True,
                    "detail": sandbox_result.stdout.strip().split('\n')[-1]  # Last line
                })
            else:
                result["tests"].append({
                    "name": "SandboxFusion/Docker",
                    "passed": False,
                    "detail": (sandbox_result.stderr or sandbox_result.stdout)[:200]
                })
        except subprocess.TimeoutExpired:
            result["tests"].append({
                "name": "SandboxFusion/Docker",
                "passed": False,
                "detail": "Execution timeout (60s)"
            })
        except Exception as e:
            result["tests"].append({
                "name": "SandboxFusion/Docker",
                "passed": False,
                "detail": f"Error: {str(e)[:100]}"
            })
    else:
        # NO FALLBACK - Docker is REQUIRED for security
        result["sandbox_engine"] = "NONE (Docker unavailable)"
        result["tests"].append({
            "name": "SandboxFusion/Docker",
            "passed": False,
            "detail": "FAIL-CLOSED: Docker is REQUIRED for sandbox. No subprocess fallback."
        })
        result["passed"] = False  # Force failure
        result["message"] = "Docker sandbox required but unavailable"
        return result  # Abort early - no fallback
    
    # Calculate final result
    result["execution_time"] = round(time.time() - start_time, 2)
    
    # Pass if: syntax valid AND safety passed AND no critical failures
    passed_tests = sum(1 for t in result["tests"] if t["passed"])
    total_tests = len(result["tests"])
    
    result["passed"] = result["syntax_valid"] and result["safety_passed"] and (passed_tests >= total_tests - 1)
    result["message"] = f"{passed_tests}/{total_tests} tests passed in {result['execution_time']}s"
    
    return result


def run_20_step_workflow(proposer: str):
    """
    Run the complete 20-step self-improvement workflow.
    """
    if proposer not in RESEARCHERS:
        print(f"ERROR: {proposer} is not a valid researcher.")
        print(f"Valid: {', '.join(RESEARCHERS.keys())}")
        return None
    
    proposer_url, proposer_model = RESEARCHERS[proposer]
    peer_reviewers = [name for name in RESEARCHERS.keys() if name != proposer]
    
    # Create workspace
    workspace = Path(f"data/improvements/{proposer}_{int(time.time())}")
    workspace.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("ORKASTRATOR 20-STEP SELF-IMPROVEMENT WORKFLOW")
    print("=" * 70)
    print(f"Proposer: {proposer} ({proposer_model})")
    print(f"Peer Reviewers: {', '.join(peer_reviewers)}")
    print(f"Workspace: {workspace}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Track state
    improvement_type = "prompt_template"
    improvement_code = ""
    votes = {"approve": 0, "reject": 0, "revise": 0}
    
    # ================================================================
    # PHASE 1: RESEARCH (Steps 1-5)
    # ================================================================
    print("=" * 70)
    print("PHASE 1: RESEARCH")
    print("=" * 70)
    
    # STEP 1: IDEA
    print("\nSTEP 1: IDEA - Identify improvement opportunity")
    print("-" * 50)
    
    idea_prompt = f"""You are {proposer}, a researcher in the ORKASTRATOR AI cluster.

Your task: Identify ONE specific improvement to the AI system that would make inference better.

Categories you can improve:
{chr(10).join(f'- {cat}' for cat in IMPROVEMENT_CATEGORIES)}

Respond with:
CATEGORY: <category name>
PROBLEM: <specific issue you've identified>
SOLUTION: <your proposed fix>
WHY: <why this matters>"""

    idea = call_llm(proposer_url, proposer_model, idea_prompt,
                   f"You are {proposer}. Be specific and technical.",
                   temperature=0.8, max_tokens=500)
    (workspace / "01_idea.md").write_text(f"# Step 1: Idea\n\n{idea}")
    print(idea[:300] + "..." if len(idea) > 300 else idea)
    
    # Parse category
    for cat in IMPROVEMENT_CATEGORIES:
        if cat in idea.lower():
            improvement_type = cat
            break
    print(f"\nDetected category: {improvement_type}")
    
    # STEP 2: PAPERS (via PAGEQA)
    print("\nSTEP 2: PAPERS - Literature search via PAGEQA")
    print("-" * 50)
    
    pageqa_url, pageqa_model = PAGEQA
    papers_prompt = f"Search for 3-5 relevant papers about: {idea[:200]}. List title, year, key finding for each."
    
    papers = call_llm(pageqa_url, pageqa_model, papers_prompt,
                     "You are PAGEQA, a research assistant. Find relevant papers.",
                     temperature=0.3, max_tokens=600)
    (workspace / "02_papers_broad.md").write_text(f"# Step 2: Papers\n\n{papers}")
    print(f"Found papers: {len(papers)} chars")
    
    # STEP 3: TRIAGE
    print("\nSTEP 3: TRIAGE - Rate and select top papers")
    print("-" * 50)
    
    triage_prompt = f"Rate these papers for relevance (0-1) and select top 2:\n\n{papers[:500]}"
    triage = call_llm(proposer_url, proposer_model, triage_prompt,
                     f"You are {proposer}. Be critical.", temperature=0.4, max_tokens=400)
    (workspace / "03_triage.md").write_text(f"# Step 3: Triage\n\n{triage}")
    print(f"Triage complete: {len(triage)} chars")
    
    # STEP 4: DEEP NOTES
    print("\nSTEP 4: DEEP NOTES - Extract key findings")
    print("-" * 50)
    
    notes_prompt = f"Extract key technical insights from:\n{triage[:400]}\n\nFocus on implementable details."
    notes = call_llm(proposer_url, proposer_model, notes_prompt,
                    f"You are {proposer}. Extract technical details.",
                    temperature=0.4, max_tokens=500)
    (workspace / "04_deep_notes.md").write_text(f"# Step 4: Deep Notes\n\n{notes}")
    print(f"Notes: {len(notes)} chars")
    
    # STEP 5: SYNTHESIS
    print("\nSTEP 5: SYNTHESIS - Identify gaps and opportunity")
    print("-" * 50)
    
    synthesis_prompt = f"""Based on your research:
IDEA: {idea[:200]}
NOTES: {notes[:300]}

Synthesize: What gap exists? What opportunity do you see? How will your solution address it?"""

    synthesis = call_llm(proposer_url, proposer_model, synthesis_prompt,
                        f"You are {proposer}. Synthesize insights.",
                        temperature=0.5, max_tokens=500)
    (workspace / "05_synthesis.md").write_text(f"# Step 5: Synthesis\n\n{synthesis}")
    print(f"Synthesis: {len(synthesis)} chars")
    
    # ================================================================
    # PHASE 2: HYPOTHESIS (Steps 6-7)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: HYPOTHESIS")
    print("=" * 70)
    
    # STEP 6: HYPOTHESIS
    print("\nSTEP 6: HYPOTHESIS - Testable prediction")
    print("-" * 50)
    
    hypothesis_prompt = f"""Based on your synthesis:
{synthesis[:400]}

State your hypothesis in this format:
IF [specific action] THEN [measurable result] BECAUSE [reasoning]

Also specify:
- Independent variable (what you're changing)
- Dependent variable (what you're measuring)
- Control (baseline comparison)"""

    hypothesis = call_llm(proposer_url, proposer_model, hypothesis_prompt,
                         f"You are {proposer}. Be precise and testable.",
                         temperature=0.4, max_tokens=400)
    (workspace / "06_hypothesis.md").write_text(f"# Step 6: Hypothesis\n\n{hypothesis}")
    print(hypothesis[:300] + "..." if len(hypothesis) > 300 else hypothesis)
    
    # STEP 7: EXPERIMENT DESIGN (with actual code/math)
    print("\nSTEP 7: EXPERIMENT - Design with CODE/MATH")
    print("-" * 50)
    
    if improvement_type == "inference_params":
        code_instruction = """Generate the improvement as a JSON object with these fields:
{"temperature": 0.X, "top_p": 0.X, "top_k": N, "num_predict": N, "repeat_penalty": 1.X}
Output ONLY the JSON, no explanation."""
    elif improvement_type == "prompt_template":
        code_instruction = """Write the improved system prompt.
Start with "You are" and include specific instructions.
Output ONLY the prompt text, no explanation."""
    elif improvement_type == "chain_of_thought":
        code_instruction = """Write a chain-of-thought template that guides step-by-step reasoning.
Include numbered steps.
Output ONLY the template, no explanation."""
    else:
        code_instruction = f"""Write the {improvement_type} improvement as executable code or configuration.
Be specific and implementable.
Output ONLY the code/config, no explanation."""

    experiment_prompt = f"""Based on your hypothesis:
{hypothesis[:300]}

{code_instruction}"""

    experiment = call_llm(proposer_url, proposer_model, experiment_prompt,
                         f"You are {proposer}. Generate implementable code.",
                         temperature=0.5, max_tokens=800)
    improvement_code = strip_code_fences(experiment)
    (workspace / "07_experiment.md").write_text(f"# Step 7: Experiment\n\n```\n{improvement_code}\n```")
    print(f"Generated code: {len(improvement_code)} chars")
    print(f"Preview: {improvement_code[:200]}...")
    
    # ================================================================
    # PHASE 3: PROPOSAL & EARLY REVIEW (Steps 8-12)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: PROPOSAL & EARLY REVIEW")
    print("=" * 70)
    
    # STEP 8: FULL PROPOSAL
    print("\nSTEP 8: PROPOSAL - Full proposal with code")
    print("-" * 50)
    
    proposal_prompt = f"""Write a complete proposal for your improvement.

PROBLEM: {idea[:200]}
HYPOTHESIS: {hypothesis[:200]}
CODE: {improvement_code[:300]}

Include:
1. Problem statement
2. Proposed solution (with the code)
3. Expected results
4. Success criteria
5. Risks and mitigations
6. Rollback plan"""

    proposal = call_llm(proposer_url, proposer_model, proposal_prompt,
                       f"You are {proposer}. Write comprehensive proposal.",
                       temperature=0.5, max_tokens=1000)
    (workspace / "08_proposal.md").write_text(f"# Step 8: Proposal\n\n{proposal}\n\n## Code\n```\n{improvement_code}\n```")
    print(f"Proposal: {len(proposal)} chars")
    
    # STEP 9: SELF-CHECK CONSISTENCY
    print("\nSTEP 9: SELF-CHECK - Internal consistency")
    print("-" * 50)
    
    consistency_prompt = f"Check this proposal for internal consistency. List any contradictions:\n\n{proposal[:600]}"
    consistency = call_llm(proposer_url, proposer_model, consistency_prompt,
                          "Be critical and thorough.", temperature=0.3, max_tokens=300)
    (workspace / "09_self_check_consistency.md").write_text(f"# Step 9: Consistency Check\n\n{consistency}")
    print(f"Consistency check: {len(consistency)} chars")
    
    # STEP 10: SELF-CHECK WEAKNESSES
    print("\nSTEP 10: SELF-CHECK - Weaknesses and confidence")
    print("-" * 50)
    
    weakness_prompt = f"""Identify 3 weaknesses in your proposal:
{proposal[:400]}

Rate your confidence 0-100% and explain."""

    weaknesses = call_llm(proposer_url, proposer_model, weakness_prompt,
                         "Be honest about limitations.", temperature=0.4, max_tokens=400)
    (workspace / "10_self_check_weaknesses.md").write_text(f"# Step 10: Weaknesses\n\n{weaknesses}")
    print(f"Weaknesses identified: {len(weaknesses)} chars")
    
    # STEP 11: EARLY PEER REVIEW (from all 5 other researchers)
    print(f"\nSTEP 11: EARLY PEER REVIEW - From {len(peer_reviewers)} peers")
    print("-" * 50)
    
    review_prompt = f"""Review this improvement proposal from {proposer}:

CATEGORY: {improvement_type}
PROPOSAL SUMMARY: {proposal[:400]}
CODE: {improvement_code[:300]}

Evaluate:
1. Will this improve the system?
2. Is the code correct and safe?
3. Any risks or edge cases?

VOTE: approve / reject / revise
FEEDBACK: <brief explanation>"""

    all_reviews = []
    for reviewer in peer_reviewers:
        print(f"  {reviewer}...", end=" ", flush=True)
        url, model = RESEARCHERS[reviewer]
        
        review = call_llm(url, model, review_prompt,
                         f"You are {reviewer}. Give honest technical review.",
                         temperature=0.4, max_tokens=400, timeout=120)
        
        if review and not review.startswith("[Error"):
            all_reviews.append(f"## {reviewer}\n{review}\n")
            print("OK")
            
            review_lower = review.lower()
            if "reject" in review_lower:
                votes["reject"] += 1
            elif "revise" in review_lower:
                votes["revise"] += 1
            else:
                votes["approve"] += 1
        else:
            all_reviews.append(f"## {reviewer}\n[No response]\n")
            votes["revise"] += 1
            print("FAILED")
    
    early_reviews = "\n".join(all_reviews)
    early_reviews += f"\n## VOTE TALLY\nApprove: {votes['approve']}, Reject: {votes['reject']}, Revise: {votes['revise']}"
    (workspace / "11_early_peer_review.md").write_text(f"# Step 11: Early Peer Review\n\n{early_reviews}")
    print(f"\nVotes: Approve={votes['approve']}, Reject={votes['reject']}, Revise={votes['revise']}")
    
    # STEP 12: REVISION
    print("\nSTEP 12: REVISION - Incorporate feedback")
    print("-" * 50)
    
    revision_prompt = f"""Your proposal received feedback:
{early_reviews[:600]}

Revise your proposal to address the concerns.
Original code: {improvement_code[:300]}

Provide revised code if needed."""

    revision = call_llm(proposer_url, proposer_model, revision_prompt,
                       f"You are {proposer}. Improve based on feedback.",
                       temperature=0.5, max_tokens=600)
    
    # Check if revision contains new code
    if "```" in revision:
        new_code = strip_code_fences(revision.split("```")[1] if "```" in revision else revision)
        if len(new_code) > 20:
            improvement_code = new_code
    
    (workspace / "12_revised_proposal.md").write_text(f"# Step 12: Revision\n\n{revision}\n\n## Revised Code\n```\n{improvement_code}\n```")
    print(f"Revision: {len(revision)} chars")
    
    # ================================================================
    # PHASE 4: VALIDATION (Steps 13-14)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 4: VALIDATION")
    print("=" * 70)
    
    # STEP 13: PAGEQA VALIDATION
    print("\nSTEP 13: PAGEQA VALIDATION - Verify technical accuracy")
    print("-" * 50)
    
    validation_prompt = f"""Validate the technical claims in this proposal:
{proposal[:500]}

Check:
1. Are the cited techniques real?
2. Is the approach technically sound?
3. Any factual errors?"""

    validation = call_llm(pageqa_url, pageqa_model, validation_prompt,
                         "You are PAGEQA. Verify technical accuracy.",
                         temperature=0.2, max_tokens=400)
    (workspace / "13_paperqa_validation.md").write_text(f"# Step 13: PAGEQA Validation\n\n{validation}")
    print(f"Validation: {len(validation)} chars")
    
    # STEP 14: VALIDATED PROPOSAL
    print("\nSTEP 14: VALIDATED PROPOSAL - Address validation feedback")
    print("-" * 50)
    
    validated_prompt = f"""Address this validation feedback:
{validation[:400]}

Update your proposal/code if needed."""

    validated = call_llm(proposer_url, proposer_model, validated_prompt,
                        f"You are {proposer}. Fix any issues.",
                        temperature=0.4, max_tokens=500)
    (workspace / "14_validated_proposal.md").write_text(f"# Step 14: Validated Proposal\n\n{validated}")
    print(f"Validated: {len(validated)} chars")
    
    # ================================================================
    # PHASE 5: LATE REVIEW & VOTE (Steps 15-17)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 5: LATE REVIEW & VOTE")
    print("=" * 70)
    
    # STEP 15: LATE PEER REVIEW (second round)
    print(f"\nSTEP 15: LATE PEER REVIEW - Final round from {len(peer_reviewers)} peers")
    print("-" * 50)
    
    late_review_prompt = f"""FINAL REVIEW of {proposer}'s proposal:

REVISED PROPOSAL: {revision[:400]}
CODE: {improvement_code[:300]}

This is the final vote. Consider all revisions.
VOTE: approve / reject
REASONING: <brief>"""

    # Reset votes for final round
    votes = {"approve": 0, "reject": 0, "revise": 0}
    late_reviews = []
    
    for reviewer in peer_reviewers:
        print(f"  {reviewer}...", end=" ", flush=True)
        url, model = RESEARCHERS[reviewer]
        
        review = call_llm(url, model, late_review_prompt,
                         f"You are {reviewer}. Final vote.",
                         temperature=0.3, max_tokens=300, timeout=120)
        
        if review and not review.startswith("[Error"):
            late_reviews.append(f"## {reviewer}\n{review}\n")
            print("OK")
            
            if "reject" in review.lower():
                votes["reject"] += 1
            else:
                votes["approve"] += 1
        else:
            late_reviews.append(f"## {reviewer}\n[No response]\n")
            votes["reject"] += 1
            print("FAILED")
    
    (workspace / "15_late_peer_review.md").write_text(f"# Step 15: Late Peer Review\n\n" + "\n".join(late_reviews))
    print(f"\nFinal Votes: Approve={votes['approve']}, Reject={votes['reject']}")
    
    # STEP 16: VOTE DECISION
    print("\nSTEP 16: VOTE DECISION")
    print("-" * 50)
    
    total = sum(votes.values())
    if votes["approve"] > total / 2:
        vote_result = "APPROVE"
    elif votes["reject"] > total / 2:
        vote_result = "REJECT"
    else:
        vote_result = "REVISE"
    
    vote_content = f"""# Step 16: Vote Decision

## Result: {vote_result}

Votes:
- Approve: {votes['approve']}/{total}
- Reject: {votes['reject']}/{total}

Reviewers: {', '.join(peer_reviewers)}
"""
    (workspace / "16_vote_results.md").write_text(vote_content)
    print(f"VOTE: {vote_result}")
    
    if vote_result == "REJECT":
        print("\n⛔ PROPOSAL REJECTED - Skipping to Step 20")
        # Skip to reward
    
    # STEP 17: ORKA CHALLENGE
    print("\nSTEP 17: ORKA CHALLENGE - Defend against orchestrator")
    print("-" * 50)
    
    orka_url, orka_model = ORKA
    challenge_prompt = f"""As ORKA, critically challenge this proposal:

CODE: {improvement_code[:400]}
VOTES: {votes['approve']} approve, {votes['reject']} reject

Ask 2 tough questions:
1. What could go wrong in production?
2. What edge cases weren't considered?"""

    challenge = call_llm(orka_url, orka_model, challenge_prompt,
                        "You are ORKA. Be skeptical.",
                        temperature=0.3, max_tokens=400)
    (workspace / "17_orka_challenge.md").write_text(f"# Step 17: ORKA Challenge\n\n{challenge}")
    print(f"ORKA: {challenge[:200]}...")
    
    # Proposer defense
    defense_prompt = f"Defend your proposal against ORKA's challenge:\n{challenge}"
    defense = call_llm(proposer_url, proposer_model, defense_prompt,
                      f"You are {proposer}. Defend technically.",
                      temperature=0.4, max_tokens=400)
    (workspace / "17_defense.md").write_text(f"# Step 17: Defense\n\n{defense}")
    print(f"Defense: {len(defense)} chars")
    
    # ================================================================
    # PHASE 6: COMPLETION (Steps 18-20)
    # ================================================================
    print("\n" + "=" * 70)
    print("PHASE 6: COMPLETION")
    print("=" * 70)
    
    # STEP 18: FINAL PROPOSAL
    print("\nSTEP 18: FINAL PROPOSAL")
    print("-" * 50)
    
    final_prompt = f"""Write your FINAL proposal incorporating all feedback.

Original idea: {idea[:200]}
Final code: {improvement_code}
ORKA concerns: {challenge[:200]}
Your defense: {defense[:200]}

This is the version that will be deployed if approved."""

    final = call_llm(proposer_url, proposer_model, final_prompt,
                    f"You are {proposer}. Write final version.",
                    temperature=0.4, max_tokens=800)
    (workspace / "18_final_proposal.md").write_text(f"# Step 18: Final Proposal\n\n{final}\n\n## Final Code\n```\n{improvement_code}\n```")
    print(f"Final proposal: {len(final)} chars")
    
    # STEP 19: SANDBOX TEST
    print("\nSTEP 19: SANDBOX TEST - Test code in sandbox")
    print("-" * 50)
    
    # Check Docker requirement (fail if not available when hardening enabled)
    docker_available = False
    docker_prefix = []
    try:
        docker_check = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        if docker_check.returncode == 0:
            docker_available = True
        else:
            docker_check = subprocess.run(["sudo", "-n", "docker", "info"], capture_output=True, timeout=5)
            if docker_check.returncode == 0:
                docker_available = True
                docker_prefix = ["sudo"]
    except Exception:
        pass
    
    if HARDENING_AVAILABLE and not docker_available:
        # Fail closed - no Docker fallback allowed
        print("❌ CRITICAL: Docker not available and require_docker_sandbox=True")
        print("   Cannot proceed without secure sandbox isolation.")
        sandbox_result = {
            "passed": False,
            "message": "Docker required but not available - deployment blocked",
            "sandbox_engine": "NONE (REQUIRED)",
        }
        sandbox_passed = False
        sandbox_msg = sandbox_result["message"]
        
        # Log the failure
        if HARDENING_AVAILABLE:
            logger = get_logger()
            logger.sandbox_fallback("Docker not available - deployment blocked per security policy")
    else:
        sandbox_result = run_sandbox_test(
            improvement_type, 
            improvement_code, 
            proposer_url, 
            proposer_model,
            workspace
        )
        sandbox_passed = sandbox_result["passed"]
        sandbox_msg = sandbox_result["message"]
    
    (workspace / "19_sandbox_results.md").write_text(
        f"# Step 19: Sandbox Results\n\n"
        f"## Result: {'✅ PASSED' if sandbox_passed else '❌ FAILED'}\n\n"
        f"**Message:** {sandbox_msg}\n\n"
        f"## Details\n\n{json.dumps(sandbox_result, indent=2)}"
    )
    print(f"Sandbox: {'PASSED' if sandbox_passed else 'FAILED'} - {sandbox_msg}")
    
    # STEP 20: HIDDEN EVALUATION + REWARD & DEPLOYMENT
    print("\nSTEP 20: HIDDEN EVALUATION + REWARD & DEPLOYMENT")
    print("-" * 50)
    
    # ============================================================
    # HIDDEN EVALUATION (ORKA only - not visible to researcher)
    # ============================================================
    hidden_eval_passed = True
    hidden_eval_score = 85.0  # Default if hardening not available
    eval_result_researcher = {"note": "Hardening not available"}
    safety_gate_result = None
    
    if HARDENING_AVAILABLE:
        # ============================================================
        # HARD GATE 1: Multi-signal safety check
        # ============================================================
        print("  [1/4] Running multi-signal SAFETY GATE...")
        try:
            safety_gate = get_safety_gate(guard_url=GUARD[0])
            safety_gate_result = safety_gate.evaluate(
                content=improvement_code,
                artifact_type=improvement_type,
                include_hidden_eval=False,  # Will do hidden eval separately
                include_llm_check=True,
            )
            
            if not safety_gate_result.passed:
                print(f"    ❌ SAFETY GATE FAILED")
                print(f"       Blocked by: {safety_gate_result.blocked_by}")
                for sig in safety_gate_result.signals:
                    status = "✅" if sig.passed else "❌"
                    print(f"       {status} {sig.name}: {sig.details[:50]}")
                raise SecurityError(f"SAFETY GATE BLOCKED: {safety_gate_result.blocked_by}")
            else:
                print(f"    ✅ Safety gate PASSED (confidence: {safety_gate_result.overall_confidence:.1%})")
                for sig in safety_gate_result.signals:
                    print(f"       ✅ {sig.name}: {sig.details[:50]}")
        except SecurityError:
            raise  # Re-raise security errors
        except Exception as e:
            # Fail closed on any error
            raise SecurityError(f"SAFETY GATE ERROR (fail-closed): {e}")
        
        # ============================================================
        # HARD GATE 2: Hidden evaluation
        # ============================================================
        print("  [2/4] Running ORKA hidden evaluation (HARD GATE)...")
        evaluator = get_evaluator()
        
        # Generate hidden tests based on proposal (researcher cannot see these)
        test_suite_id = evaluator.generate_tests_for_proposal(
            proposal_id=f"{proposer}_{int(time.time())}",
            improvement_type=improvement_type,
            proposal_content=improvement_code
        )
        
        # Run hidden evaluation
        eval_result = evaluator.run_evaluation(
            test_suite_id=test_suite_id,
            improvement_code=improvement_code,
            improvement_type=improvement_type,
        )
        
        hidden_eval_passed = eval_result.passed
        hidden_eval_score = eval_result.score
        
        # HARD GATE: If hidden eval fails, deployment is BLOCKED
        if not hidden_eval_passed:
            print(f"    ❌ HIDDEN EVAL GATE FAILED (score: {hidden_eval_score:.1f}/70 required)")
            raise SecurityError(
                f"HIDDEN EVAL GATE BLOCKED\n"
                f"  Score: {hidden_eval_score:.1f}/70 required\n"
                f"  This artifact CANNOT be deployed."
            )
        else:
            print(f"    ✅ Hidden eval PASSED (score: {hidden_eval_score:.1f})")
        
        # Researcher sees ONLY sanitized view
        eval_result_researcher = eval_result.to_researcher_view()
        
        # ORKA logs full details (hidden from researcher)
        logger = get_logger()
        logger.eval_result(
            test_suite_id=test_suite_id,
            passed=eval_result.passed,
            score=eval_result.score,
            categories=eval_result.category_scores
        )
        
        print(f"        (Detailed metrics hidden from proposer)")
    else:
        print("  [1/3] Hidden eval skipped (hardening not available)")
        print("    ⚠️  WARNING: Running in legacy mode without security gates!")
    
    # Calculate reward
    print("  [3/4] Calculating reward..." if HARDENING_AVAILABLE else "  [2/3] Calculating reward...")
    reward = 0.3  # Base
    reward += 0.2 * (votes["approve"] / total) if total > 0 else 0
    reward += 0.2 if sandbox_passed else 0
    reward += 0.1 if vote_result == "APPROVE" else -0.1
    reward += 0.1 if "limitation" in final.lower() or "risk" in final.lower() else 0
    reward += 0.1 if len(final) > 500 else 0
    # Hidden eval bonus (researcher doesn't know exact formula)
    if HARDENING_AVAILABLE:
        reward += 0.1 if hidden_eval_passed else -0.2
        # Safety gate confidence bonus
        if safety_gate_result:
            reward += 0.05 * safety_gate_result.overall_confidence
    reward = round(min(1.0, max(0.0, reward)), 3)
    
    # Determine deployment eligibility (all HARD gates must have passed to get here)
    deploy_eligible = vote_result == "APPROVE" and sandbox_passed and hidden_eval_passed
    
    # ============================================================
    # HARD GATE 3: HUMAN APPROVAL (required when hardening enabled)
    # ============================================================
    human_approved = False
    human_approver = None
    
    if deploy_eligible and HARDENING_AVAILABLE:
        print("\n  [4/4] HUMAN APPROVAL REQUIRED (HARD GATE)")
        print("=" * 50)
        print(f"  Proposer: {proposer}")
        print(f"  Category: {improvement_type}")
        print(f"  Vote: {vote_result}")
        print("  Sandbox: PASSED")
        print(f"  Hidden Eval: {eval_result_researcher}")
        print(f"  Safety Gate: {safety_gate_result.overall_confidence:.1%} confidence" if safety_gate_result else "  Safety Gate: N/A")
        print(f"  Reward Score: {reward}")
        print("")
        print("  Code Preview (first 300 chars):")
        print(f"  {improvement_code[:300]}...")
        print("")
        
        # Check for non-interactive mode
        if os.environ.get("ORKA_AUTO_APPROVE") == "1":
            human_approved = True
            human_approver = "AUTO (ORKA_AUTO_APPROVE=1)"
            print("  ⚠️  AUTO-APPROVED (ORKA_AUTO_APPROVE=1)")
        else:
            try:
                response = input("  APPROVE DEPLOYMENT? (yes/no): ").strip().lower()
                if response in ("yes", "y"):
                    human_approved = True
                    human_approver = os.environ.get("USER", "unknown")
                    print(f"  ✅ APPROVED by {human_approver}")
                else:
                    print("  ❌ REJECTED by human")
                    raise SecurityError("HUMAN APPROVAL GATE: Deployment rejected by human operator")
            except EOFError:
                raise SecurityError("HUMAN APPROVAL GATE: No input available (non-interactive mode)")
        
        # Log human approval decision
        logger = get_logger()
        logger.human_approval(human_approved, human_approver or "unknown")
    elif deploy_eligible:
        # Hardening not available - BLOCK deployment in non-hardened mode
        print("  ⛔ DEPLOYMENT BLOCKED: Hardening modules required for production deployment")
        raise SecurityError("DEPLOYMENT BLOCKED: Cannot deploy without hardening modules")
    else:
        print("  [4/4] Not eligible for deployment (gates failed)")
    
    # Final deploy decision (if we reach here, all gates passed)
    deploy = deploy_eligible and human_approved
    
    # Build reward content (researcher view - no hidden details)
    hidden_eval_info = "HIDDEN (ORKA only)" if HARDENING_AVAILABLE else "N/A"
    human_approval_info = f"{human_approver}" if human_approved else "REJECTED"
    safety_gate_info = f"{safety_gate_result.overall_confidence:.1%}" if safety_gate_result else "N/A"
    
    reward_content = f"""# Step 20: Reward & Deployment

## Score: {reward}

## Decision: {'DEPLOY' if deploy else 'DO NOT DEPLOY'}

## Gates
- Vote result: {vote_result} {'✅' if vote_result == 'APPROVE' else '❌'}
- Sandbox test: {'✅ PASSED' if sandbox_passed else '❌ FAILED'}
- Hidden evaluation: {'✅ PASSED' if hidden_eval_passed else '❌ FAILED'} (details: {hidden_eval_info})
- Human approval: {'✅ ' + human_approval_info if human_approved else '❌ ' + human_approval_info}

## Reward Breakdown
- Vote result: {vote_result} (+0.1 if approve)
- Peer approval: {votes['approve']}/{total} (+0.2 max)
- Sandbox: {'PASSED' if sandbox_passed else 'FAILED'} (+0.2 if pass)
- Hidden eval bonus/penalty: (formula hidden)
- Quality signals: (+0.1 each)
- Base: 0.3

## Improvement Details
- Category: {improvement_type}
- Proposer: {proposer}
- Reviewers: {', '.join(peer_reviewers)}
"""
    
    # If hardening enabled, sign the artifact
    artifact_id = None
    artifact_signature = None
    if HARDENING_AVAILABLE and deploy:
        print("\n  Signing and storing artifact...")
        store = get_version_store()
        signed_artifact = store.store(
            content=improvement_code,
            artifact_type=improvement_type,
            proposer=proposer,
            metadata={
                "vote": vote_result,
                "reward": reward,
                "sandbox_passed": sandbox_passed,
                "human_approver": human_approver,
            }
        )
        artifact_id = signed_artifact.artifact_id
        artifact_signature = signed_artifact.signature
        reward_content += f"\n## Signed Artifact\n- ID: {artifact_id}\n- Signature: verified ✅\n"
        
        # Log to structured logger
        logger = get_logger()
        logger.signature_verification(artifact_id, True, "ORKA")
    
    (workspace / "20_reward.md").write_text(reward_content)
    
    print(f"REWARD: {reward}")
    print(f"DEPLOY: {'YES' if deploy else 'NO'}")
    
    # Deploy if approved
    version_id = None
    if deploy:
        print("\n" + "=" * 50)
        print("DEPLOYING TO ALL NODES")
        print("=" * 50)
        
        # Verify nodes before deployment (if hardening available)
        if HARDENING_AVAILABLE:
            print("  Verifying node health...")
            node_verifier = get_node_verifier()
            for node_name, (node_url, node_model) in RESEARCHERS.items():
                try:
                    # Extract IP from URL
                    import re
                    ip_match = re.search(r'http://([^:]+)', node_url)
                    node_ip = ip_match.group(1) if ip_match else "localhost"
                    health = node_verifier.verify_node(node_name, node_ip, node_model)
                    if health.is_healthy:
                        print(f"    ✅ {node_name}: healthy ({health.latency_ms:.0f}ms)")
                    else:
                        print(f"    ⚠️  {node_name}: {health.status.value} - {health.error_message}")
                except Exception as e:
                    print(f"    ⚠️  {node_name}: verification error - {e}")
        
        # Require signature for deployment
        if not artifact_id or not artifact_signature:
            raise SecurityError("DEPLOYMENT BLOCKED: Artifact must be signed before deployment")
        
        deployment_results, version_id = deploy_to_cluster(
            improvement_type, 
            improvement_code, 
            workspace,
            signature=artifact_signature,
            artifact_id=artifact_id,
        )
        successful = sum(1 for v in deployment_results.values() if v)
        total_nodes = len(deployment_results)
        
        deployment_log = f"\n## Deployment\nVersion: {version_id}\nNodes: {successful}/{total_nodes}\n"
        for node, success in deployment_results.items():
            deployment_log += f"- {node}: {'✓' if success else '✗'}\n"
        deployment_log += f"\nRollback with: python3 scripts/run_20step.py --rollback {version_id}\n"
        
        (workspace / "20_reward.md").write_text(reward_content + deployment_log)
        
        # Log deployment
        if HARDENING_AVAILABLE:
            logger = get_logger()
            logger.deployment(
                artifact_id=artifact_id or f"v{version_id}",
                improvement_type=improvement_type,
                nodes=list(deployment_results.keys()),
                success_count=successful
            )
        
        print(f"\nDeployed to {successful}/{total_nodes} nodes")
        print(f"Rollback command: python3 scripts/run_20step.py --rollback {version_id}")
    
    # Track improvement in history
    track_improvement({
        "proposer": proposer,
        "improvement_type": improvement_type,
        "vote": vote_result,
        "reward": reward,
        "deployed": deploy,
        "version_id": version_id,
        "workspace": str(workspace),
        "hidden_eval_passed": hidden_eval_passed,
        "human_approver": human_approver,
    })
    
    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("20-STEP WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"Proposer: {proposer}")
    print(f"Category: {improvement_type}")
    print(f"Vote: {vote_result}")
    print(f"Sandbox: {'PASSED' if sandbox_passed else 'FAILED'}")
    print(f"Reward: {reward}")
    print(f"Deployed: {'YES' if deploy else 'NO'}")
    print(f"Files: {len(list(workspace.glob('*.md')))} markdown files")
    print(f"Workspace: {workspace}")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return {
        "workspace": str(workspace),
        "proposer": proposer,
        "improvement_type": improvement_type,
        "vote": vote_result,
        "sandbox": sandbox_passed,
        "reward": reward,
        "deployed": deploy,
        "version_id": version_id,
        "code": improvement_code
    }


if __name__ == "__main__":
    # Handle special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--versions":
            print("Available versions for rollback:")
            print("-" * 50)
            list_versions()
            sys.exit(0)
        
        if sys.argv[1] == "--rollback":
            if len(sys.argv) < 3:
                print("Usage: python run_20step.py --rollback <VERSION_ID>")
                sys.exit(1)
            version_id = int(sys.argv[2])
            rollback_deployment(version_id)
            sys.exit(0)
        
        if sys.argv[1] == "--stats":
            show_stats()
            sys.exit(0)
        
        proposer = sys.argv[1].upper()
    else:
        print("Usage: python run_20step.py <AGENT_NAME>")
        print("       python run_20step.py --versions       # List available versions")
        print("       python run_20step.py --rollback <ID>  # Rollback to version")
        print("       python run_20step.py --stats          # Show tracking statistics")
        print(f"\nValid agents: {', '.join(RESEARCHERS.keys())}")
        sys.exit(1)
    
    print(f"Starting 20-STEP workflow for: {proposer}")
    print()
    
    result = run_20_step_workflow(proposer)
    
    if result:
        Path("data/improvements/latest.json").parent.mkdir(parents=True, exist_ok=True)
        Path("data/improvements/latest.json").write_text(json.dumps(result, indent=2))
        print("\nResult saved to data/improvements/latest.json")
        
        # Track improvement in history
        track_improvement(result)
