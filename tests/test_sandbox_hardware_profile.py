import json

import pytest

import utilities.hardware_adapter
from core.orchestrator_sandbox import SandboxEnvironmentManager


@pytest.mark.parametrize(
    "env_value, expected_name, expected_gpu, expected_cores, expected_notes",
    [
        (
            "jetson_nano",
            "jetson_nano",
            True,
            4,
            'Single Jetson Nano developer kit profile.'
        ),
        (
            "nvidia_super_nano",
            "nvidia_super_nano",
            True,
            6,
            'Upgraded Nano module with extra RAM for ML workloads.'
        ),
        (
            "nano_cluster",
            "nano_cluster_6x8gb",
            True,
            36,
            'Represents six 8GB Super Nanos pooled for inference with 10Gb fabric.'
        ),
        (
            "hpz6_lab",
            "hp_z6_24core_5060ti",
            True,
            24,
            'Mirrors lab workstation with Xeon Gold and RTX 5060 Ti 16GB.'
        ),
        (
            "esp32_s3",
            "esp32_s3_touch_panel",
            False,
            2,
            'Used for touch display proof-of-concept harness.'
        ),
        (
            "mac_worm_usb",
            "worm_usb_station",
            False,
            8,
            'Read-only USB signing station for WORM exports.'
        ),
    ],
)
def test_sandbox_hardware_profile_detection(monkeypatch, env_value, expected_name, expected_gpu, expected_cores, expected_notes):
    # Ensure the sandbox picks up a hardware profile from the environment
    monkeypatch.setenv('SANDBOX_HARDWARE_PROFILE', env_value)

    manager = SandboxEnvironmentManager()
    assert hasattr(manager, 'hardware_profile') and manager.hardware_profile is not None
    profile = manager.hardware_profile
    assert profile.get('name') == expected_name
    assert bool(profile.get('gpu_present')) is expected_gpu
    assert int(profile.get('simulated_cpu_cores')) == expected_cores
    assert profile.get('notes') == expected_notes

    env_id = manager.create_test_environment(
        f'test_hw_{expected_name}',
        {'component': 'default'},
        proposal_metadata={'title': 'hw test'}
    )
    results = manager.run_automated_tests(env_id, selected_tests=['edge_cases'])

    assert 'hardware' in results
    hardware = results['hardware']
    assert hardware['profile_name'] == expected_name
    assert bool(hardware['gpu_present']) is expected_gpu
    assert hardware.get('notes') == expected_notes


def test_hardware_profile_override_from_config(monkeypatch):
    monkeypatch.delenv('SANDBOX_HARDWARE_PROFILE', raising=False)
    monkeypatch.delenv('SANDBOX_HARDWARE_PROFILE_JSON', raising=False)

    override_profile = {
        'device_name': 'Custom Lab Rig',
        'gpu_present': True,
        'gpu_memory_mb': 24576,
        'simulated_cpu_cores': 32,
        'simulated_max_memory_kb': 160 * 1024 * 1024,
        'network_bandwidth_gbps': 5.0,
        'storage': {'type': 'nvme', 'capacity_gb': 4096},
        'notes': 'Config override test profile.'
    }

    def fake_load_config():
        return {
            'sandbox': {
                'hardware_profile': 'lab_override',
                'hardware_profiles': {
                    'lab_override': override_profile
                }
            }
        }

    monkeypatch.setattr(hardware_adapter, 'load_config', fake_load_config)

    manager = SandboxEnvironmentManager()
    profile = manager.hardware_profile
    assert profile.get('device_name') == 'Custom Lab Rig'
    assert profile.get('notes') == 'Config override test profile.'
    assert profile.get('gpu_memory_mb') == 24576
    assert profile.get('network_bandwidth_gbps') == 5.0


def test_hardware_profile_json_override(monkeypatch):
    base_json = {
        'gpu_memory_mb': 1024,
        'notes': 'JSON override applied.',
        'storage': {'type': 'sd_card', 'capacity_gb': 64}
    }
    monkeypatch.setenv('SANDBOX_HARDWARE_PROFILE', 'esp32_s3')
    monkeypatch.setenv('SANDBOX_HARDWARE_PROFILE_JSON', json.dumps(base_json))

    manager = SandboxEnvironmentManager()
    profile = manager.hardware_profile
    assert profile.get('gpu_memory_mb') == 1024
    assert profile.get('notes') == 'JSON override applied.'
    assert profile.get('storage', {}).get('type') == 'sd_card'

