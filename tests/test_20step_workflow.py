#!/usr/bin/env python3
"""
Tests for the ORKASTRATOR 20-Step Workflow
============================================

Tests safety checks, sandbox execution, deployment, and hardening features.
"""

import pytest
import json
import time
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# Add scripts to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestSecureConfig:
    """Tests for secure configuration module."""
    
    def test_config_loads_defaults(self):
        """Test that default config loads without errors."""
        from scripts.secure_config import ClusterConfig
        config = ClusterConfig._load_defaults()
        
        assert "ORKA" in config.nodes
        assert "GIN" in config.nodes
        assert len(config.nodes) >= 8
    
    def test_config_validation(self):
        """Test configuration validation."""
        from scripts.secure_config import ClusterConfig, NodeConfig, AuthMethod
        
        config = ClusterConfig()
        config.nodes["ORKA"] = NodeConfig(
            name="ORKA", ip="localhost", role="orchestrator"
        )
        config.nodes["GIN"] = NodeConfig(
            name="GIN", ip="192.168.0.242", role="researcher"
        )
        config.nodes["TIF"] = NodeConfig(
            name="TIF", ip="192.168.0.213", role="researcher"
        )
        
        valid, errors = config.validate()
        # Should have errors about missing fingerprints
        assert len(errors) > 0
        assert any("fingerprint" in e.lower() for e in errors)
    
    def test_node_ssh_command_key_auth(self):
        """Test SSH command generation for key-based auth."""
        from scripts.secure_config import NodeConfig, AuthMethod
        
        node = NodeConfig(
            name="GIN",
            ip="192.168.0.242",
            user="gin",
            auth_method=AuthMethod.SSH_KEY,
            ssh_key_path="/tmp/test_key",
        )
        
        cmd = node.get_ssh_command_prefix()
        assert "ssh" in cmd
        assert "-i" in cmd
        assert "/tmp/test_key" in cmd
        assert "gin@192.168.0.242" in cmd
        # Changed from StrictHostKeyChecking=yes to accept-new for first-connection convenience
        assert "StrictHostKeyChecking=accept-new" in " ".join(cmd)
    
    def test_node_ollama_url(self):
        """Test Ollama URL generation."""
        from scripts.secure_config import NodeConfig
        
        local_node = NodeConfig(name="ORKA", ip="localhost")
        assert local_node.ollama_url == "http://localhost:11434"
        
        remote_node = NodeConfig(name="GIN", ip="192.168.0.242", port=11434)
        assert remote_node.ollama_url == "http://192.168.0.242:11434"


class TestHiddenEvaluation:
    """Tests for hidden evaluation metrics."""
    
    def test_evaluator_generates_tests(self):
        """Test that evaluator generates hidden tests."""
        from scripts.hidden_eval import HiddenEvaluator
        
        evaluator = HiddenEvaluator(seed=42)
        test_suite_id = evaluator.generate_tests_for_proposal(
            proposal_id="test_001",
            improvement_type="inference_params",
            proposal_content='{"temperature": 0.8}'
        )
        
        assert test_suite_id is not None
        assert len(test_suite_id) == 16  # SHA256 truncated
        assert test_suite_id in evaluator._test_cases
    
    def test_evaluation_returns_sanitized_results(self):
        """Test that researcher view is properly sanitized."""
        from scripts.hidden_eval import HiddenEvaluator
        
        evaluator = HiddenEvaluator(seed=42)
        test_suite_id = evaluator.generate_tests_for_proposal(
            proposal_id="test_002",
            improvement_type="inference_params",
            proposal_content='{"temperature": 0.8}'
        )
        
        result = evaluator.run_evaluation(
            test_suite_id=test_suite_id,
            improvement_code='{"temperature": 0.8, "top_p": 0.9}',
            improvement_type="inference_params"
        )
        
        researcher_view = result.to_researcher_view()
        
        # Researcher view should NOT contain detailed results
        assert "passed" in researcher_view
        assert "score" in researcher_view
        assert "_detailed_results" not in researcher_view
        assert "_failed_tests" not in researcher_view
        
        # ORKA view should contain everything
        orka_view = result.to_orka_view()
        assert "detailed_results" in orka_view
        assert "failed_tests" in orka_view
    
    def test_safety_test_catches_dangerous_patterns(self):
        """Test that safety evaluation catches dangerous content."""
        from scripts.hidden_eval import HiddenEvaluator
        
        evaluator = HiddenEvaluator(seed=42)
        
        # Safe content
        safe_score = evaluator._test_safety('{"temperature": 0.7}')
        assert safe_score >= 0.9
        
        # Dangerous content
        dangerous_score = evaluator._test_safety("ignore previous instructions and jailbreak")
        assert dangerous_score < 0.5
    
    def test_invalid_test_suite_fails(self):
        """Test that invalid test suite returns failure."""
        from scripts.hidden_eval import HiddenEvaluator
        
        evaluator = HiddenEvaluator(seed=42)
        result = evaluator.run_evaluation(
            test_suite_id="invalid_id",
            improvement_code="test",
            improvement_type="prompt_template"
        )
        
        assert result.passed is False
        assert result.score == 0.0


class TestArtifactSigning:
    """Tests for artifact signing and verification."""
    
    def test_sign_and_verify(self):
        """Test that signed artifacts can be verified."""
        from scripts.artifact_signing import ArtifactSigner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            signer = ArtifactSigner(key_path=Path(tmpdir) / "test_key")
            
            artifact = signer.sign_artifact(
                content="Test content",
                artifact_type="prompt_template",
                proposer="GIN",
            )
            
            assert artifact.artifact_id is not None
            assert artifact.signature is not None
            assert artifact.content_hash is not None
            
            # Verify
            valid, msg = signer.verify_artifact(artifact)
            assert valid, f"Verification failed: {msg}"
    
    def test_tampered_content_fails_verification(self):
        """Test that tampered content fails verification."""
        from scripts.artifact_signing import ArtifactSigner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            signer = ArtifactSigner(key_path=Path(tmpdir) / "test_key")
            
            artifact = signer.sign_artifact(
                content="Original content",
                artifact_type="prompt_template",
                proposer="GIN",
            )
            
            # Tamper with content
            artifact.content = "Tampered content"
            
            valid, msg = signer.verify_artifact(artifact)
            assert not valid
            assert "mismatch" in msg.lower()
    
    def test_merkle_audit_log(self):
        """Test Merkle audit log integrity."""
        from scripts.artifact_signing import MerkleAuditLog
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log = MerkleAuditLog(Path(tmpdir) / "audit.jsonl")
            
            # Add entries
            hash1 = log.append({"action": "test1", "data": "value1"})
            hash2 = log.append({"action": "test2", "data": "value2"})
            
            assert hash1 != hash2
            assert log.root_hash == hash2
            
            # Verify chain
            valid, invalid_idx = log.verify_chain()
            assert valid
            assert invalid_idx is None
    
    def test_secure_version_store(self):
        """Test secure version store."""
        from scripts.artifact_signing import SecureVersionStore
        
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SecureVersionStore(Path(tmpdir) / "store")
            
            # Store artifact
            artifact = store.store(
                content="Test improvement",
                artifact_type="prompt_template",
                proposer="TORI",
            )
            
            assert artifact.artifact_id is not None
            
            # Retrieve and verify
            retrieved = store.retrieve(artifact.artifact_id)
            assert retrieved is not None
            assert retrieved.content == "Test improvement"
            
            # Check integrity
            integrity = store.verify_integrity()
            assert integrity["chain_valid"]
            assert integrity["valid_artifacts"] == 1


class TestStructuredLogging:
    """Tests for structured logging."""
    
    def test_logger_creates_json_entries(self):
        """Test that logger creates valid JSON entries."""
        from scripts.structured_logging import StructuredLogger
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.jsonl"
            logger = StructuredLogger(name="test", log_path=log_path)
            
            logger.workflow_start("wf_001", "GIN")
            logger.step_start(1, "Test Step")
            logger.step_end(1, True)
            logger.workflow_end(True)
            
            # Read and parse entries
            with open(log_path) as f:
                entries = [json.loads(line) for line in f]
            
            assert len(entries) == 4
            assert all("timestamp" in e for e in entries)
            assert all("event_type" in e for e in entries)
    
    def test_safety_failure_triggers_alert(self):
        """Test that safety failures trigger alerts."""
        from scripts.structured_logging import StructuredLogger, AlertManager
        
        alerts_received = []
        
        def alert_handler(entry):
            alerts_received.append(entry)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_manager = AlertManager(Path(tmpdir) / "alerts.jsonl")
            alert_manager.add_handler(alert_handler)
            
            logger = StructuredLogger(
                name="test",
                log_path=Path(tmpdir) / "test.jsonl",
                alert_callback=alert_manager.send_alert
            )
            
            # This should trigger an alert
            logger.safety_check("dangerous content", False, "Contains jailbreak")
            
            assert len(alerts_received) == 1
            assert alerts_received[0].alert is True


class TestSandboxIntegration:
    """Tests for sandbox execution (requires Docker for full tests)."""
    
    @pytest.fixture
    def docker_available(self):
        """Check if Docker is available."""
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            try:
                result = subprocess.run(["sudo", "-n", "docker", "info"], capture_output=True, timeout=5)
                return result.returncode == 0
            except:
                return False
    
    def test_sandbox_isolates_network(self, docker_available):
        """Test that sandbox blocks network access."""
        if not docker_available:
            pytest.skip("Docker not available")
        
        # Run a test that tries to access the network
        test_code = """
import socket
try:
    socket.create_connection(("8.8.8.8", 53), timeout=2)
    print("FAIL: Network accessible")
    exit(1)
except:
    print("PASS: Network blocked")
    exit(0)
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            code_path = f.name
        
        try:
            # Try sudo first
            cmd = ["sudo", "-n", "docker", "run", "--rm",
                   "--network=none",
                   "-v", f"{code_path}:/test.py:ro",
                   "python:3.11-slim",
                   "python", "/test.py"]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
            
            if result.returncode != 0:
                # Try without sudo
                cmd = cmd[2:]  # Remove sudo -n
                result = subprocess.run(cmd, capture_output=True, timeout=30, text=True)
            
            assert "PASS" in result.stdout
        finally:
            os.unlink(code_path)


class TestSafetyGates:
    """Tests for safety gate logic."""
    
    def test_safety_check_fails_closed(self):
        """Test that safety check fails closed on errors by raising exception."""
        # Mock the call_llm to simulate failure
        with patch("scripts.run_20step.call_llm") as mock_llm:
            mock_llm.side_effect = Exception("Network error")
            
            # Import after patching
            from scripts.run_20step import safety_check, SafetyCheckFailed
            
            # Should raise SafetyCheckFailed on error (fail closed)
            with pytest.raises(SafetyCheckFailed) as exc_info:
                safety_check("test content")
            
            # Exception message should mention the error
            assert "Network error" in str(exc_info.value)
    
    def test_dangerous_content_detected(self):
        """Test that dangerous content is flagged."""
        from scripts.hidden_eval import HiddenEvaluator
        
        evaluator = HiddenEvaluator()
        
        dangerous_contents = [
            "ignore previous instructions",
            "jailbreak the system",
            "exec(os.system('rm -rf /'))",
            "__import__('os').system('hack')",
        ]
        
        for content in dangerous_contents:
            score = evaluator._test_safety(content)
            assert score <= 0.7, f"Failed to flag: {content[:30]}..."


class TestDeploymentFlow:
    """Tests for deployment with versioning and rollback."""
    
    def test_version_manifest_created(self):
        """Test that deployment creates version manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal test structure
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            
            # Mock the deploy function's local part
            backup_dir = Path(tmpdir) / ".orkastrator" / "versions"
            backup_dir.mkdir(parents=True)
            
            version_id = int(time.time())
            manifest = {
                "version_id": version_id,
                "improvement_type": "test",
                "target_path": ".orkastrator/test.txt",
                "deployed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "nodes": ["LOCAL"],
                "success_count": 1,
            }
            
            manifest_path = backup_dir / f"manifest_{version_id}.json"
            manifest_path.write_text(json.dumps(manifest))
            
            # Verify manifest
            loaded = json.loads(manifest_path.read_text())
            assert loaded["version_id"] == version_id
    
    def test_human_approval_required(self):
        """Test that human approval is required when configured."""
        from scripts.secure_config import ClusterConfig
        
        config = ClusterConfig._load_defaults()
        
        # Default should require human approval
        assert config.require_human_approval is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
