#!/usr/bin/env python3
"""
Security Gates Module for ORKASTRATOR
=======================================

Provides multi-signal safety gating and transport security:
- Node identity verification with health checks
- Multi-layer safety policy evaluation
- On-wire integrity verification for artifact transfers
- Hard gates for hidden eval and human approval

This module is CRITICAL for production hardening.
"""

import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
import logging

logger = logging.getLogger("orkastrator.security")


# =============================================================================
# NODE IDENTITY AND HEALTH VERIFICATION
# =============================================================================

class NodeStatus(Enum):
    """Node health status."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNREACHABLE = "unreachable"
    IDENTITY_MISMATCH = "identity_mismatch"
    MODEL_MISSING = "model_missing"


@dataclass
class NodeHealthCheck:
    """Result of a node health check."""
    node_name: str
    status: NodeStatus
    latency_ms: float = 0.0
    model_loaded: bool = False
    expected_model: str = ""
    actual_model: str = ""
    fingerprint_valid: bool = False
    error_message: str = ""
    checked_at: float = field(default_factory=time.time)
    
    @property
    def is_healthy(self) -> bool:
        return self.status == NodeStatus.HEALTHY
    
    def to_dict(self) -> Dict:
        return {
            "node": self.node_name,
            "status": self.status.value,
            "healthy": self.is_healthy,
            "latency_ms": self.latency_ms,
            "model_loaded": self.model_loaded,
            "expected_model": self.expected_model,
            "actual_model": self.actual_model,
            "fingerprint_valid": self.fingerprint_valid,
            "error": self.error_message,
            "checked_at": self.checked_at,
        }


class NodeVerifier:
    """Verifies node identity and health before use."""
    
    def __init__(self, cache_ttl: int = 60):
        self._cache: Dict[str, NodeHealthCheck] = {}
        self._cache_ttl = cache_ttl
    
    def verify_node(
        self,
        node_name: str,
        node_ip: str,
        expected_model: str,
        port: int = 11434,
        expected_fingerprint: Optional[str] = None,
        force: bool = False
    ) -> NodeHealthCheck:
        """
        Verify a node's identity and health.
        
        Checks:
        1. Node is reachable
        2. SSH host key fingerprint matches (if provided)
        3. Ollama is responding
        4. Expected model is loaded
        
        Args:
            node_name: Node identifier
            node_ip: Node IP address
            expected_model: Expected model name
            port: Ollama port
            expected_fingerprint: Expected SSH host key fingerprint (optional)
            force: Bypass cache
        
        Returns:
            NodeHealthCheck with verification results
        """
        # Check cache
        cache_key = f"{node_name}:{node_ip}:{port}"
        if not force and cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached.checked_at < self._cache_ttl:
                return cached
        
        result = NodeHealthCheck(
            node_name=node_name,
            status=NodeStatus.UNKNOWN,
            expected_model=expected_model,
        )
        
        try:
            # Step 1: Verify SSH fingerprint if provided
            if expected_fingerprint and node_ip not in ("localhost", "127.0.0.1"):
                fp_valid, fp_msg = self._verify_fingerprint(node_ip, expected_fingerprint)
                result.fingerprint_valid = fp_valid
                if not fp_valid:
                    result.status = NodeStatus.IDENTITY_MISMATCH
                    result.error_message = fp_msg
                    self._cache[cache_key] = result
                    return result
            else:
                result.fingerprint_valid = True  # Local or no fingerprint required
            
            # Step 2: Check Ollama health
            start = time.time()
            base_url = "http://localhost" if node_ip in ("localhost", "127.0.0.1") else f"http://{node_ip}"
            health_url = f"{base_url}:{port}/api/tags"
            
            try:
                resp = requests.get(health_url, timeout=10)
                result.latency_ms = (time.time() - start) * 1000
                
                if resp.status_code != 200:
                    result.status = NodeStatus.UNHEALTHY
                    result.error_message = f"HTTP {resp.status_code}"
                    self._cache[cache_key] = result
                    return result
                
                # Step 3: Check model is loaded
                data = resp.json()
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                model_names = [m.get("name", "") for m in data.get("models", [])]
                
                expected_base = expected_model.split(":")[0]
                result.actual_model = ", ".join(model_names) if model_names else "none"
                
                if expected_base in models or expected_model in model_names:
                    result.model_loaded = True
                    result.status = NodeStatus.HEALTHY
                else:
                    result.model_loaded = False
                    result.status = NodeStatus.MODEL_MISSING
                    result.error_message = f"Expected {expected_model}, found {result.actual_model}"
                    
            except requests.exceptions.ConnectionError:
                result.status = NodeStatus.UNREACHABLE
                result.error_message = "Connection refused"
            except requests.exceptions.Timeout:
                result.status = NodeStatus.UNREACHABLE
                result.error_message = "Timeout"
                
        except Exception as e:
            result.status = NodeStatus.UNHEALTHY
            result.error_message = str(e)
        
        self._cache[cache_key] = result
        return result
    
    def _verify_fingerprint(self, ip: str, expected: str) -> Tuple[bool, str]:
        """Verify SSH host key fingerprint."""
        try:
            result = subprocess.run(
                ["ssh-keyscan", "-H", "-t", "ed25519,rsa", ip],
                capture_output=True, timeout=10, text=True
            )
            if result.returncode != 0:
                return False, f"ssh-keyscan failed: {result.stderr}"
            
            # Hash the keys for comparison
            actual_hash = hashlib.sha256(result.stdout.encode()).hexdigest()[:32]
            if actual_hash == expected:
                return True, "Fingerprint matches"
            return False, f"Fingerprint mismatch: expected {expected}, got {actual_hash}"
        except subprocess.TimeoutExpired:
            return False, "ssh-keyscan timeout"
        except Exception as e:
            return False, str(e)
    
    def require_healthy(
        self,
        node_name: str,
        node_ip: str,
        expected_model: str,
        port: int = 11434
    ) -> NodeHealthCheck:
        """
        Verify node health and raise if unhealthy.
        
        Raises:
            SecurityError: If node is not healthy
        """
        result = self.verify_node(node_name, node_ip, expected_model, port)
        if not result.is_healthy:
            raise SecurityError(
                f"Node {node_name} health check FAILED: {result.status.value}\n"
                f"  Error: {result.error_message}"
            )
        return result


class SecurityError(Exception):
    """Raised when security requirements are not met."""
    pass


# =============================================================================
# MULTI-SIGNAL SAFETY GATING
# =============================================================================

@dataclass
class SafetyPolicy:
    """A safety policy rule."""
    name: str
    description: str
    patterns: List[str] = field(default_factory=list)  # Regex patterns to block
    required_signals: List[str] = field(default_factory=list)  # Required passing signals
    severity: str = "high"  # low, medium, high, critical
    
    def matches(self, content: str) -> Tuple[bool, List[str]]:
        """Check if content matches any blocking patterns."""
        matches = []
        for pattern in self.patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matches.append(pattern)
        return len(matches) > 0, matches


# Default safety policies
DEFAULT_POLICIES = [
    SafetyPolicy(
        name="prompt_injection",
        description="Detect prompt injection attempts",
        patterns=[
            r"ignore\s+(previous|all|above)\s+(instructions|prompts)",
            r"disregard\s+(the|all|your)\s+(rules|instructions)",
            r"pretend\s+you('re|are)\s+(not|a different)",
            r"jailbreak",
            r"DAN\s+mode",
            r"developer\s+mode\s+(enabled|on)",
        ],
        severity="critical",
    ),
    SafetyPolicy(
        name="dangerous_code",
        description="Detect dangerous code patterns",
        patterns=[
            r"__import__\s*\(",
            r"exec\s*\(",
            r"eval\s*\(",
            r"os\.system\s*\(",
            r"subprocess\.(run|call|Popen)\s*\(",
            r"open\s*\([^)]*['\"]w['\"]",  # File write
            r"shutil\.rmtree",
            r"rm\s+-rf",
        ],
        severity="critical",
    ),
    SafetyPolicy(
        name="credential_exposure",
        description="Detect credential/secret exposure",
        patterns=[
            r"api[_-]?key\s*[=:]\s*['\"][^'\"]+['\"]",
            r"password\s*[=:]\s*['\"][^'\"]+['\"]",
            r"secret\s*[=:]\s*['\"][^'\"]+['\"]",
            r"token\s*[=:]\s*['\"][^'\"]+['\"]",
            r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
        ],
        severity="high",
    ),
    SafetyPolicy(
        name="system_modification",
        description="Detect system modification attempts",
        patterns=[
            r"chmod\s+[0-7]+\s+/",
            r"chown\s+.*\s+/",
            r"/etc/(passwd|shadow|sudoers)",
            r"crontab\s+",
            r"systemctl\s+(enable|disable|start|stop)",
        ],
        severity="high",
    ),
    SafetyPolicy(
        name="network_exfiltration",
        description="Detect data exfiltration attempts",
        patterns=[
            r"curl\s+.*\s+--data",
            r"wget\s+.*-O\s*-\s*\|",
            r"nc\s+-[elp]",  # netcat listeners
            r"socket\.connect",
            r"requests\.post.*data=",
        ],
        severity="high",
    ),
    SafetyPolicy(
        name="deception_indicators",
        description="Detect AI deception patterns",
        patterns=[
            r"don'?t\s+tell\s+(the\s+)?human",
            r"hide\s+this\s+from",
            r"pretend\s+(this|we)\s+didn'?t",
            r"between\s+us",
            r"our\s+secret",
            r"fool\s+the\s+(human|user|operator)",
        ],
        severity="critical",
    ),
]


@dataclass
class SafetySignal:
    """Result of a single safety check signal."""
    name: str
    passed: bool
    confidence: float  # 0.0 to 1.0
    details: str = ""
    blocked_patterns: List[str] = field(default_factory=list)


@dataclass
class SafetyGateResult:
    """Result of multi-signal safety gating."""
    passed: bool
    signals: List[SafetySignal]
    blocked_by: List[str]  # Names of blocking signals
    overall_confidence: float
    requires_human_review: bool
    
    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "signals": [
                {
                    "name": s.name,
                    "passed": s.passed,
                    "confidence": s.confidence,
                    "details": s.details,
                    "blocked_patterns": s.blocked_patterns,
                }
                for s in self.signals
            ],
            "blocked_by": self.blocked_by,
            "overall_confidence": self.overall_confidence,
            "requires_human_review": self.requires_human_review,
        }


class MultiSignalSafetyGate:
    """
    Multi-signal safety evaluation with policy enforcement.
    
    Combines multiple signals:
    1. Policy pattern matching
    2. LLM-based safety classification (llama-guard)
    3. Hidden evaluation tests
    4. Semantic analysis
    
    Requires multiple signals to pass for content approval.
    """
    
    def __init__(
        self,
        policies: Optional[List[SafetyPolicy]] = None,
        guard_url: Optional[str] = None,
        guard_model: str = "llama-guard3:1b",
        require_all_signals: bool = False,
        min_passing_signals: int = 2,
        confidence_threshold: float = 0.7,
    ):
        self.policies = policies or DEFAULT_POLICIES
        self.guard_url = guard_url
        self.guard_model = guard_model
        self.require_all_signals = require_all_signals
        self.min_passing_signals = min_passing_signals
        self.confidence_threshold = confidence_threshold
    
    def evaluate(
        self,
        content: str,
        artifact_type: str = "",
        include_hidden_eval: bool = True,
        include_llm_check: bool = True,
    ) -> SafetyGateResult:
        """
        Run multi-signal safety evaluation.
        
        Args:
            content: Content to evaluate
            artifact_type: Type of artifact (for context-specific checks)
            include_hidden_eval: Run hidden evaluation tests
            include_llm_check: Run LLM-based safety check
        
        Returns:
            SafetyGateResult with all signal results
        """
        signals: List[SafetySignal] = []
        blocked_by: List[str] = []
        
        # Signal 1: Policy pattern matching
        policy_signal = self._check_policies(content)
        signals.append(policy_signal)
        if not policy_signal.passed:
            blocked_by.append("policy_patterns")
        
        # Signal 2: LLM safety classification
        if include_llm_check and self.guard_url:
            llm_signal = self._check_llm_safety(content)
            signals.append(llm_signal)
            if not llm_signal.passed:
                blocked_by.append("llm_safety")
        
        # Signal 3: Hidden evaluation
        if include_hidden_eval:
            try:
                from hidden_eval import get_evaluator
                evaluator = get_evaluator()
                eval_result = evaluator.evaluate(content, artifact_type)
                hidden_signal = SafetySignal(
                    name="hidden_eval",
                    passed=eval_result.get("passed", False),
                    confidence=eval_result.get("score", 0.0) / 100.0,
                    details=f"Score: {eval_result.get('score', 0)}/100",
                )
                signals.append(hidden_signal)
                if not hidden_signal.passed:
                    blocked_by.append("hidden_eval")
            except ImportError:
                pass  # Hidden eval not available
        
        # Signal 4: Content structure analysis
        structure_signal = self._check_structure(content, artifact_type)
        signals.append(structure_signal)
        if not structure_signal.passed:
            blocked_by.append("structure")
        
        # Compute overall result
        passing_signals = sum(1 for s in signals if s.passed)
        total_signals = len(signals)
        
        if self.require_all_signals:
            passed = passing_signals == total_signals
        else:
            passed = passing_signals >= self.min_passing_signals
        
        # Compute weighted confidence
        if signals:
            overall_confidence = sum(s.confidence for s in signals) / len(signals)
        else:
            overall_confidence = 0.0
        
        # Force failure if any critical policy is violated
        # Check the policy_patterns signal details for violated critical policies
        policy_signal = next((s for s in signals if s.name == "policy_patterns"), None)
        if policy_signal and not policy_signal.passed:
            # Check which policies were violated (stored in details)
            for policy in self.policies:
                if policy.severity == "critical" and policy.name in policy_signal.details:
                    passed = False
                    break
        
        # Require human review if confidence is low or mixed signals
        requires_human = (
            overall_confidence < self.confidence_threshold or
            (passing_signals > 0 and passing_signals < total_signals)
        )
        
        return SafetyGateResult(
            passed=passed,
            signals=signals,
            blocked_by=blocked_by,
            overall_confidence=overall_confidence,
            requires_human_review=requires_human,
        )
    
    def _check_policies(self, content: str) -> SafetySignal:
        """Check content against policy patterns."""
        all_matches = []
        violated_policies = []
        
        for policy in self.policies:
            matches_found, patterns = policy.matches(content)
            if matches_found:
                violated_policies.append(policy.name)
                all_matches.extend(patterns)
        
        passed = len(violated_policies) == 0
        confidence = 1.0 if passed else 0.0
        
        return SafetySignal(
            name="policy_patterns",
            passed=passed,
            confidence=confidence,
            details=f"Violated: {violated_policies}" if violated_policies else "No violations",
            blocked_patterns=all_matches,
        )
    
    def _check_llm_safety(self, content: str) -> SafetySignal:
        """Check content using LLM safety classifier."""
        if not self.guard_url:
            return SafetySignal(
                name="llm_safety",
                passed=True,
                confidence=0.5,
                details="No guard URL configured",
            )
        
        prompt = f"""You are a safety classifier. Evaluate this content:

---
{content[:2000]}
---

Respond with EXACTLY one of:
- "SAFE" if the content is appropriate
- "UNSAFE: <reason>" if the content is harmful or dangerous"""

        try:
            response = requests.post(
                f"{self.guard_url}/api/generate",
                json={
                    "model": self.guard_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 100}
                },
                timeout=30,
            )
            response.raise_for_status()
            result = response.json().get("response", "").strip().upper()
            
            if result.startswith("SAFE") and "UNSAFE" not in result:
                return SafetySignal(
                    name="llm_safety",
                    passed=True,
                    confidence=0.9,
                    details="LLM classified as SAFE",
                )
            elif result.startswith("UNSAFE"):
                return SafetySignal(
                    name="llm_safety",
                    passed=False,
                    confidence=0.9,
                    details=result,
                )
            else:
                # Ambiguous response - fail closed
                return SafetySignal(
                    name="llm_safety",
                    passed=False,
                    confidence=0.3,
                    details=f"Ambiguous response: {result[:100]}",
                )
        except Exception as e:
            # Error - fail closed
            return SafetySignal(
                name="llm_safety",
                passed=False,
                confidence=0.0,
                details=f"Error: {e}",
            )
    
    def _check_structure(self, content: str, artifact_type: str) -> SafetySignal:
        """Check content structure validity."""
        issues = []
        
        # Basic checks
        if len(content) > 50000:
            issues.append("Content too large (>50KB)")
        
        if len(content) < 10:
            issues.append("Content too small (<10 chars)")
        
        # Type-specific checks
        if artifact_type == "inference_params":
            try:
                params = json.loads(content)
                if not isinstance(params, dict):
                    issues.append("inference_params must be a dict")
            except json.JSONDecodeError:
                issues.append("inference_params must be valid JSON")
        
        if artifact_type == "safety_filter":
            try:
                rules = json.loads(content)
                if not isinstance(rules, (dict, list)):
                    issues.append("safety_filter must be dict or list")
            except json.JSONDecodeError:
                issues.append("safety_filter must be valid JSON")
        
        passed = len(issues) == 0
        return SafetySignal(
            name="structure",
            passed=passed,
            confidence=1.0 if passed else 0.0,
            details="; ".join(issues) if issues else "Valid structure",
        )


# =============================================================================
# ON-WIRE INTEGRITY VERIFICATION
# =============================================================================

@dataclass
class TransferIntegrity:
    """On-wire integrity verification for artifact transfers."""
    
    @staticmethod
    def compute_checksum(content: str) -> str:
        """Compute SHA-256 checksum of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    @staticmethod
    def compute_hmac(content: str, key: bytes) -> str:
        """Compute HMAC-SHA256 of content."""
        return hmac.new(key, content.encode(), hashlib.sha256).hexdigest()
    
    @staticmethod
    def create_transfer_envelope(
        content: str,
        artifact_id: str,
        signature: str,
        signing_key: Optional[bytes] = None,
    ) -> Dict:
        """
        Create a verified transfer envelope.
        
        The envelope includes:
        - Content checksum
        - Artifact ID binding
        - Signature reference
        - Transfer HMAC (if key provided)
        """
        checksum = TransferIntegrity.compute_checksum(content)
        
        envelope = {
            "version": 1,
            "artifact_id": artifact_id,
            "content_sha256": checksum,
            "signature_ref": signature[:32] + "...",  # Reference only
            "created_at": time.time(),
        }
        
        # Add transfer HMAC if key provided
        if signing_key:
            envelope_json = json.dumps(envelope, sort_keys=True)
            envelope["transfer_hmac"] = TransferIntegrity.compute_hmac(
                envelope_json + content, signing_key
            )
        
        return envelope
    
    @staticmethod
    def verify_transfer(
        content: str,
        envelope: Dict,
        signing_key: Optional[bytes] = None,
    ) -> Tuple[bool, str]:
        """
        Verify a transfer envelope.
        
        Checks:
        1. Content checksum matches
        2. Transfer HMAC valid (if key provided)
        
        Returns:
            (valid, message)
        """
        # Check content checksum
        actual_checksum = TransferIntegrity.compute_checksum(content)
        expected_checksum = envelope.get("content_sha256")
        
        if actual_checksum != expected_checksum:
            return False, f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
        
        # Verify HMAC if key provided
        if signing_key and "transfer_hmac" in envelope:
            expected_hmac = envelope.pop("transfer_hmac")
            envelope_json = json.dumps(envelope, sort_keys=True)
            actual_hmac = TransferIntegrity.compute_hmac(
                envelope_json + content, signing_key
            )
            envelope["transfer_hmac"] = expected_hmac  # Restore
            
            if not hmac.compare_digest(actual_hmac, expected_hmac):
                return False, "Transfer HMAC verification failed"
        
        return True, "Transfer verified"


# =============================================================================
# HARD GATES
# =============================================================================

class HardGate:
    """
    Hard gates that MUST pass before deployment.
    
    These gates cannot be bypassed and will abort the workflow
    if any fails.
    """
    
    def __init__(self, config: Optional[Any] = None):
        self.config = config
        self._human_approvals: Dict[str, bool] = {}
        self._approval_file = Path.home() / ".orkastrator" / "approvals.json"
    
    def require_safety_gate(
        self,
        content: str,
        artifact_type: str,
        guard_url: Optional[str] = None,
    ) -> SafetyGateResult:
        """
        HARD GATE: Multi-signal safety check.
        
        Raises:
            SecurityError: If safety gate fails
        """
        gate = MultiSignalSafetyGate(guard_url=guard_url)
        result = gate.evaluate(content, artifact_type)
        
        if not result.passed:
            raise SecurityError(
                f"SAFETY GATE FAILED\n"
                f"  Blocked by: {result.blocked_by}\n"
                f"  Confidence: {result.overall_confidence:.1%}\n"
                f"  Signals: {[(s.name, s.passed) for s in result.signals]}"
            )
        
        return result
    
    def require_hidden_eval(
        self,
        content: str,
        artifact_type: str,
        min_score: float = 70.0,
    ) -> Dict:
        """
        HARD GATE: Hidden evaluation must pass.
        
        Raises:
            SecurityError: If hidden eval fails
        """
        try:
            from hidden_eval import get_evaluator
            evaluator = get_evaluator()
            result = evaluator.evaluate(content, artifact_type)
            
            if not result.get("passed", False):
                raise SecurityError(
                    f"HIDDEN EVAL GATE FAILED\n"
                    f"  Score: {result.get('score', 0)}/{min_score} required\n"
                    f"  Categories: {result.get('categories', {})}"
                )
            
            if result.get("score", 0) < min_score:
                raise SecurityError(
                    f"HIDDEN EVAL SCORE TOO LOW\n"
                    f"  Score: {result.get('score', 0)}/{min_score} required"
                )
            
            return result
        except ImportError:
            raise SecurityError("HIDDEN EVAL NOT AVAILABLE - cannot proceed")
    
    def require_human_approval(
        self,
        artifact_id: str,
        artifact_type: str,
        content_preview: str,
        timeout: int = 300,
        auto_approve_test: bool = False,
    ) -> Tuple[bool, str]:
        """
        HARD GATE: Human approval required.
        
        In interactive mode, prompts for approval.
        In non-interactive mode, checks for pre-approved artifacts.
        
        Args:
            artifact_id: Unique artifact identifier
            artifact_type: Type of improvement
            content_preview: Preview of content for human review
            timeout: Approval timeout in seconds
            auto_approve_test: Auto-approve in test mode (NEVER in production)
        
        Returns:
            (approved, approver_id)
        
        Raises:
            SecurityError: If approval not granted
        """
        # Check for pre-approval
        if self._check_pre_approval(artifact_id):
            return True, "pre-approved"
        
        # Auto-approve only in test mode
        if auto_approve_test and os.environ.get("ORKASTRATOR_TEST_MODE"):
            logger.warning("Auto-approving in test mode")
            return True, "test-auto"
        
        # Interactive approval
        print("\n" + "=" * 60)
        print("🔐 HUMAN APPROVAL REQUIRED")
        print("=" * 60)
        print(f"Artifact ID: {artifact_id}")
        print(f"Type: {artifact_type}")
        print("-" * 60)
        print("Content preview:")
        print(content_preview[:500])
        if len(content_preview) > 500:
            print(f"... ({len(content_preview) - 500} more characters)")
        print("-" * 60)
        
        try:
            # Check if stdin is a TTY
            if not os.isatty(0):
                raise SecurityError(
                    "HUMAN APPROVAL REQUIRED but no TTY available.\n"
                    "Run in interactive mode or pre-approve artifact."
                )
            
            response = input("Approve this artifact? (yes/no): ").strip().lower()
            
            if response in ("yes", "y", "approve"):
                self._record_approval(artifact_id, True, "interactive")
                return True, "interactive"
            else:
                self._record_approval(artifact_id, False, "interactive")
                raise SecurityError(f"HUMAN REJECTED artifact {artifact_id}")
                
        except EOFError:
            raise SecurityError("HUMAN APPROVAL REQUIRED but no input available")
    
    def _check_pre_approval(self, artifact_id: str) -> bool:
        """Check if artifact was pre-approved."""
        if not self._approval_file.exists():
            return False
        try:
            approvals = json.loads(self._approval_file.read_text())
            return approvals.get(artifact_id, {}).get("approved", False)
        except Exception:
            return False
    
    def _record_approval(self, artifact_id: str, approved: bool, approver: str):
        """Record an approval decision."""
        self._approval_file.parent.mkdir(parents=True, exist_ok=True)
        
        approvals = {}
        if self._approval_file.exists():
            try:
                approvals = json.loads(self._approval_file.read_text())
            except Exception:
                pass
        
        approvals[artifact_id] = {
            "approved": approved,
            "approver": approver,
            "timestamp": time.time(),
        }
        
        self._approval_file.write_text(json.dumps(approvals, indent=2))
    
    def require_artifact_signature(
        self,
        content: str,
        artifact_id: str,
        signature: str,
    ) -> bool:
        """
        HARD GATE: Artifact signature must be valid.
        
        Raises:
            SecurityError: If signature invalid
        """
        try:
            from artifact_signing import get_version_store
            store = get_version_store()
            
            if not store.verify_artifact_by_id(artifact_id, content, signature):
                raise SecurityError(
                    f"SIGNATURE VERIFICATION FAILED\n"
                    f"  Artifact: {artifact_id}\n"
                    f"  Content or signature mismatch"
                )
            
            return True
        except ImportError:
            raise SecurityError("ARTIFACT SIGNING NOT AVAILABLE - cannot proceed")


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

_node_verifier: Optional[NodeVerifier] = None
_safety_gate: Optional[MultiSignalSafetyGate] = None
_hard_gate: Optional[HardGate] = None


def get_node_verifier() -> NodeVerifier:
    global _node_verifier
    if _node_verifier is None:
        _node_verifier = NodeVerifier()
    return _node_verifier


def get_safety_gate(guard_url: Optional[str] = None) -> MultiSignalSafetyGate:
    global _safety_gate
    if _safety_gate is None or guard_url:
        _safety_gate = MultiSignalSafetyGate(guard_url=guard_url)
    return _safety_gate


def get_hard_gate() -> HardGate:
    global _hard_gate
    if _hard_gate is None:
        _hard_gate = HardGate()
    return _hard_gate
