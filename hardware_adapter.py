"""
Simple hardware profile loader for sandbox simulations.

This module exposes a tiny helper to load a hardware profile from the
environment or config so the sandbox can simulate device capabilities and
include a `hardware` section in its test results. Keep it intentionally
lightweight to avoid pulling heavy platform-specific dependencies.
"""
from typing import Optional, Dict, Any
import os
import json
from copy import deepcopy

try:
    from config_loader import load_config
except Exception:
    # Fallback if config loader isn't available in some test environments
    def load_config():
        return {}


_PROFILE_CATALOG: Dict[str, Dict[str, Any]] = {
    'jetson_nano': {
        'name': 'jetson_nano',
        'device_name': 'NVIDIA Jetson Nano (sim)',
        'gpu_present': True,
        'gpu_memory_mb': 4096,
        'simulated_cpu_cores': 4,
        'simulated_max_memory_kb': 4 * 1024 * 1024,
        'memory_mb': 4096,
        'network_bandwidth_gbps': 1.0,
        'storage': {'type': 'emmc', 'capacity_gb': 32},
        'cluster_size': 1,
        'notes': 'Single Jetson Nano developer kit profile.'
    },
    'nvidia_super_nano': {
        'name': 'nvidia_super_nano',
        'device_name': 'NVIDIA Super Nano (sim)',
        'gpu_present': True,
        'gpu_memory_mb': 8192,
        'simulated_cpu_cores': 6,
        'simulated_max_memory_kb': 8 * 1024 * 1024,
        'memory_mb': 8192,
        'network_bandwidth_gbps': 2.5,
        'storage': {'type': 'nvme', 'capacity_gb': 128},
        'cluster_size': 1,
        'notes': 'Upgraded Nano module with extra RAM for ML workloads.'
    },
    'nano_cluster_6x8gb': {
        'name': 'nano_cluster_6x8gb',
        'device_name': '6× NVIDIA Super Nano Cluster (sim)',
        'gpu_present': True,
        'gpu_memory_mb': 6 * 8192,
        'simulated_cpu_cores': 6 * 6,
        'simulated_max_memory_kb': 6 * 8 * 1024 * 1024,
        'cluster_size': 6,
        'memory_mb': 6 * 8 * 1024,
        'network_bandwidth_gbps': 10.0,
        'storage': {'type': 'nvme_array', 'capacity_gb': 6 * 256},
        'power_draw_watts': {'idle': 90, 'peak': 450},
        'notes': 'Represents six 8GB Super Nanos pooled for inference with 10Gb fabric.'
    },
    'hp_z6_24core_5060ti': {
        'name': 'hp_z6_24core_5060ti',
        'device_name': 'HP Z6 (24-core Xeon, 5060 Ti 16GB sim)',
        'gpu_present': True,
        'gpu_memory_mb': 16 * 1024,
        'simulated_cpu_cores': 24,
        'simulated_max_memory_kb': 128 * 1024 * 1024,
        'memory_mb': 128 * 1024,
        'network_bandwidth_gbps': 2.5,
        'storage': {'type': 'nvme', 'capacity_gb': 2048, 'layout': 'RAID1'},
        'power_draw_watts': {'idle': 180, 'peak': 650},
        'notes': 'Mirrors lab workstation with Xeon Gold and RTX 5060 Ti 16GB.'
    },
    'esp32_s3_touch_panel': {
        'name': 'esp32_s3_touch_panel',
        'device_name': 'ESP32-S3 7" Touch Panel (sim)',
        'gpu_present': False,
        'gpu_memory_mb': 0,
        'simulated_cpu_cores': 2,
        'simulated_max_memory_kb': 512 * 1024,
        'memory_mb': 8,
        'network_bandwidth_gbps': 0.1,
        'storage': {'type': 'flash', 'capacity_mb': 16},
        'cluster_size': 1,
        'notes': 'Used for touch display proof-of-concept harness.'
    },
    'worm_usb_station': {
        'name': 'worm_usb_station',
        'device_name': 'macOS WORM USB Station (sim)',
        'gpu_present': False,
        'gpu_memory_mb': 0,
        'simulated_cpu_cores': 8,
        'simulated_max_memory_kb': 16 * 1024 * 1024,
        'memory_mb': 16 * 1024,
        'network_bandwidth_gbps': 1.0,
        'storage': {'type': 'ssd', 'capacity_gb': 512, 'removable_media': 'read_only_usb'},
        'cluster_size': 1,
        'notes': 'Read-only USB signing station for WORM exports.'
    },
}

_PROFILE_ALIASES: Dict[str, str] = {
    'nano_cluster': 'nano_cluster_6x8gb',
    'super_nano_cluster': 'nano_cluster_6x8gb',
    'nano_poc_cluster': 'nano_cluster_6x8gb',
    'nvidia_super_nano_cluster': 'nano_cluster_6x8gb',
    'hp_z6': 'hp_z6_24core_5060ti',
    'hpz6': 'hp_z6_24core_5060ti',
    'hpz6_lab': 'hp_z6_24core_5060ti',
    'hp_z6_workstation': 'hp_z6_24core_5060ti',
    'xeon_lab': 'hp_z6_24core_5060ti',
    'mac_worm_usb': 'worm_usb_station',
    'worm_mac_station': 'worm_usb_station',
    'esp32_s3': 'esp32_s3_touch_panel',
    'esp32_touch': 'esp32_s3_touch_panel',
}


def _resolve_profile_key(raw_name: str) -> str:
    key = raw_name.strip().lower()
    if not key:
        return key
    return _PROFILE_ALIASES.get(key, key)


def _profile_for_key(key: str) -> Optional[Dict[str, Any]]:
    profile = _PROFILE_CATALOG.get(key)
    if profile is None:
        return None
    # Return a shallow copy to keep catalog immutable
    data = deepcopy(profile)
    data.setdefault('name', key)
    if not data.get('device_name'):
        data['device_name'] = key
    data.setdefault('cluster_size', 1)
    return data


def load_hardware_profile() -> Optional[Dict[str, Any]]:
    """Return a hardware profile dict or None if no profile is configured.

    Checks, in order:
    - SANDBOX_HARDWARE_PROFILE environment variable
    - config()['sandbox']['hardware_profile']

    Known profile names are mapped to a small capability dict. Unknown names
    are returned as a minimal profile with the provided name.
    """
    profile_name = os.getenv('SANDBOX_HARDWARE_PROFILE')
    if not profile_name:
        cfg = load_config() or {}
        profile_name = None
        try:
            profile_name = cfg.get('sandbox', {}).get('hardware_profile')
        except Exception:
            profile_name = None

    if not profile_name:
        return None

    canonical_key = _resolve_profile_key(str(profile_name))
    resolved = _profile_for_key(canonical_key)

    extra_cfg: Dict[str, Any] = {}
    try:
        cfg = load_config() or {}
        sandbox_cfg = cfg.get('sandbox', {}) if isinstance(cfg, dict) else {}
        profile_overrides = sandbox_cfg.get('hardware_profiles', {}) if isinstance(sandbox_cfg, dict) else {}
        if isinstance(profile_overrides, dict):
            override_key = _resolve_profile_key(str(profile_name))
            if override_key in profile_overrides:
                extra_cfg = deepcopy(profile_overrides[override_key])
    except Exception:
        extra_cfg = {}

    json_override = os.getenv('SANDBOX_HARDWARE_PROFILE_JSON')
    json_data: Dict[str, Any] = {}
    if json_override:
        try:
            parsed = json.loads(json_override)
            if isinstance(parsed, dict):
                json_data = parsed
        except json.JSONDecodeError:
            json_data = {}

    def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = _merge(deepcopy(base[key]), value)
            else:
                base[key] = value
        return base

    if resolved is None and (extra_cfg or json_data):
        resolved = {'name': canonical_key}

    if resolved is not None:
        merged = deepcopy(resolved)
        if extra_cfg:
            merged = _merge(merged, extra_cfg)
        if json_data:
            merged = _merge(merged, json_data)
        merged.setdefault('name', canonical_key)
        merged.setdefault('device_name', merged.get('name'))
        merged.setdefault('cluster_size', 1)
        return merged

    # Unknown profile: return a minimal descriptor so callers can still
    # report the name and a couple of defaults.
    try:
        simulated_max = int(128 * 1024)
    except Exception:
        simulated_max = 128 * 1024

    key = canonical_key or str(profile_name).strip().lower()
    return {
        'name': key,
        'device_name': str(profile_name),
        'gpu_present': False,
        'gpu_memory_mb': 0,
        'simulated_cpu_cores': 1,
        'simulated_max_memory_kb': simulated_max,
    }
