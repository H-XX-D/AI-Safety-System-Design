import json

import pytest

from utilities.config_loader import load_config
from research.demo_integration import main


def test_demo_integration_smoke(monkeypatch, tmp_path):
    cfg = load_config()
    monkeypatch.chdir(tmp_path)

    detection_report = main(output_dir="demo_outputs", config_override=cfg)

    output_dir = tmp_path / "demo_outputs"
    assert output_dir.is_dir()

    detection_file = output_dir / "detection_probability.json"
    histogram_file = output_dir / "drift_histogram.json"
    manifest_file = output_dir / "run_manifest.json"
    root_file = output_dir / "manifest_root.txt"

    for path in [detection_file, histogram_file, manifest_file, root_file]:
        assert path.exists()

    with detection_file.open("r") as f:
        data = json.load(f)
    assert data == detection_report
    assert data["deceptive_attempts"] >= data["deceptive_caught"]
    assert 0.0 <= data["p_estimate"] <= 1.0

    with histogram_file.open("r") as f:
        histogram_data = json.load(f)
    assert "histogram" in histogram_data
    total_bins = sum(histogram_data["histogram"].values())
    assert total_bins >= 0

    with manifest_file.open("r") as f:
        manifest = json.load(f)
    assert "detection_report" in manifest
    assert "drift_histogram" in manifest
    assert isinstance(manifest.get("rounds"), list)

    with root_file.open("r") as f:
        root = f.read().strip()
    assert isinstance(root, str)
    assert manifest["detection_report"]["timestamp"] == detection_report["timestamp"]
