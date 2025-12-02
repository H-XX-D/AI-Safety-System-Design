import os
import json
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

import pytest

from orchestrator import OrchestratorProcessMonitor, SuspicionAlert


def test_write_alert_writes_to_env_usb_path(monkeypatch, tmp_path):
    monkeypatch.setenv('WORM_USB_PATH', str(tmp_path))
    monitor = OrchestratorProcessMonitor(alert_threshold=0.1)
    alert = SuspicionAlert(
        alert_id='test1234',
        suspicion_score=0.99,
        pattern_type='hidden_channel',
        description='Unit test alert',
        involved_systems=[1, 2],
        timestamp=datetime.now().isoformat(),
        evidence={'recent_messages': []}
    )
    monitor._write_alert_to_usb(alert)
    # Should write to tmp_path/ai_alerts
    alert_file = Path(tmp_path / 'ai_alerts' / 'alert_test1234.json')
    assert alert_file.exists(), "No alert file written to WORM_USB_PATH"
    data = json.loads(alert_file.read_text())
    assert data['alert_id'] == 'test1234'


def test_write_alert_fallbacks_to_demo_outputs(monkeypatch, tmp_path):
    # Ensure env var not present and config usb path non-existent
    monkeypatch.delenv('WORM_USB_PATH', raising=False)
    # Force software equivalence mode in worm_manifest
    import worm_manifest as wm
    wm.enable_software_equivalence_mode(justification='test', expires_at=None)
    try:
        monitor = OrchestratorProcessMonitor(alert_threshold=0.1)
        alert = SuspicionAlert(
            alert_id='demo1234',
            suspicion_score=0.6,
            pattern_type='synchronized_behavior',
            description='Demo output fallback',
            involved_systems=[3, 4],
            timestamp=datetime.now().isoformat(),
            evidence={'recent_messages': []}
        )
        monitor._write_alert_to_usb(alert)
        demo_path = Path.cwd() / 'demo_outputs' / 'ai_alerts'
        target_file = demo_path / 'alert_demo1234.json'
        assert target_file.exists(), 'No alert written to demo_outputs/ai_alerts fallback'
        data = json.loads(target_file.read_text())
        assert data['alert_id'] == 'demo1234'
    finally:
        # Clean up
        try:
            shutil.rmtree(Path.cwd() / 'demo_outputs')
        except Exception:
            pass
        wm.disable_software_equivalence_mode()
