#!/usr/bin/env python3
"""
Fix broken imports after repository reorganization.

This script updates all import statements to reflect the new folder structure:
- orchestrator* modules -> core.orchestrator*
- research_system, llm_adapters, etc. -> research.*
- memory_auditor, workflow*, etc. -> infrastructure.*
- deception_detector, interpretability* -> ai_safety.*
- aura_compressor, translator, message_codec -> communication.*
- config_loader, logging_config, etc. -> utilities.*
- cube_model, orka_counterpoint -> models.*
- worm_*, attestation, etc. -> security.*
"""

import os
import re
from pathlib import Path

# Mapping of old module names to new paths
IMPORT_MAPPING = {
    # Core system
    'orchestrator': 'core.orchestrator',
    'orchestrator_v2': 'core.orchestrator_v2',
    'orchestrator_logging': 'core.orchestrator_logging',
    'orchestrator_sandbox': 'core.orchestrator_sandbox',
    'orchestrator_types': 'core.orchestrator_types',
    'orchestrator_utils': 'core.orchestrator_utils',
    'ai_safety_system_core': 'core.ai_safety_system_core',

    # Research system
    'research_system': 'research.research_system',
    'llm_adapters': 'research.llm_adapters',
    'llm_adapter_factory': 'research.llm_adapter_factory',
    'improvement_policy': 'research.improvement_policy',
    'improvement_manifest': 'research.improvement_manifest',
    'human_review': 'research.human_review',
    'peer_review_engine': 'research.peer_review_engine',
    'debate_engine': 'research.debate_engine',
    'demo_integration': 'research.demo_integration',
    'multi_agent_coordinator': 'research.multi_agent_coordinator',
    'simulate_12_month_proposals': 'research.simulate_12_month_proposals',
    'simulation_incentives': 'research.simulation_incentives',

    # Security
    'ai_safety_worm_usb': 'security.ai_safety_worm_usb',
    'attestation': 'security.attestation',
    'audit_archive_usb': 'security.audit_archive_usb',
    'audit_seed_chain': 'security.audit_seed_chain',
    'create_worm_usb': 'security.create_worm_usb',
    'security_static_scan': 'security.security_static_scan',
    'security_utils': 'security.security_utils',
    'verify_worm_integrity': 'security.verify_worm_integrity',
    'worm_guard': 'security.worm_guard',
    'worm_manifest': 'security.worm_manifest',
    'worm_paths': 'security.worm_paths',
    'worm_security_usb': 'security.worm_security_usb',
    'worm_usb_builder': 'security.worm_usb_builder',
    'worm_usb_verifier': 'security.worm_usb_verifier',
    'update_worm_manifest': 'security.update_worm_manifest',

    # AI Safety
    'deception_detector': 'ai_safety.deception_detector',
    'deception_incident': 'ai_safety.deception_incident',
    'bulletproof_alignment_filter': 'ai_safety.bulletproof_alignment_filter',
    'interpretability_monitor': 'ai_safety.interpretability_monitor',
    'interpretability_monitor_enhanced': 'ai_safety.interpretability_monitor_enhanced',
    'semantic_deception_classifier': 'ai_safety.semantic_deception_classifier',
    'collusion_game': 'ai_safety.collusion_game',
    'seventh_validator': 'ai_safety.seventh_validator',

    # Communication
    'message_codec': 'communication.message_codec',
    'translator': 'communication.translator',
    'translator_alt': 'communication.translator_alt',
    'aura_compressor': 'communication.aura_compressor',
    'aura_secure_transport': 'communication.aura_secure_transport',
    'aura_strategy_profile': 'communication.aura_strategy_profile',
    'aura_bitpacked_extension': 'communication.aura_bitpacked_extension',
    'generate_aura_templates': 'communication.generate_aura_templates',
    'generate_all_aura_templates': 'communication.generate_all_aura_templates',
    'bench_compression': 'communication.bench_compression',

    # Infrastructure
    'memory_auditor': 'infrastructure.memory_auditor',
    'memory_auditor_optimized': 'infrastructure.memory_auditor_optimized',
    'memory_merkle': 'infrastructure.memory_merkle',
    'memory_storage': 'infrastructure.memory_storage',
    'workflow_state_machine': 'infrastructure.workflow_state_machine',
    'workflow_types': 'infrastructure.workflow_types',
    'reputation_system': 'infrastructure.reputation_system',
    'validation_pipeline': 'infrastructure.validation_pipeline',
    'reward_engine': 'infrastructure.reward_engine',
    'incentive_calibration': 'infrastructure.incentive_calibration',
    'resource_guard': 'infrastructure.resource_guard',
    'offline_bundle': 'infrastructure.offline_bundle',
    'production_control_hooks': 'infrastructure.production_control_hooks',
    'file_export_validator': 'infrastructure.file_export_validator',

    # Utilities
    'config_loader': 'utilities.config_loader',
    'logging_config': 'utilities.logging_config',
    'log_schema': 'utilities.log_schema',
    'hardware_adapter': 'utilities.hardware_adapter',
    'hardware_translator': 'utilities.hardware_translator',
    'core_values': 'utilities.core_values',
    'control_actions': 'utilities.control_actions',
    'ui_integration': 'utilities.ui_integration',
    'val_bridge': 'utilities.val_bridge',
    'semantic_consensus': 'utilities.semantic_consensus',

    # Models
    'cube_model': 'models.cube_model',
    'vrf_ed25519': 'models.vrf_ed25519',
    'vrf_random': 'models.vrf_random',
    'orka_counterpoint': 'models.orka_counterpoint',
    'orka_penalty_tracker': 'models.orka_penalty_tracker',
    'key_rotation': 'models.key_rotation',
}

def fix_imports_in_file(file_path: Path) -> bool:
    """Fix imports in a single file. Returns True if file was modified."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix import statements
        for old_module, new_module in IMPORT_MAPPING.items():
            # Match "from old_module import ..." or "import old_module"
            patterns = [
                rf'\bfrom {re.escape(old_module)}\b',
                rf'\bimport {re.escape(old_module)}\b'
            ]

            for pattern in patterns:
                # Replace the module name but keep the rest of the import
                content = re.sub(
                    rf'({pattern})',
                    lambda m: m.group(1).replace(old_module, new_module),
                    content
                )

        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    return False

def main():
    """Fix imports in all Python files."""
    repo_root = Path(__file__).parent

    # Find all Python files excluding archived, venv, and special directories
    exclude_patterns = [
        'Archive Files',
        'venv',
        '__pycache__',
        '.git',
        'node_modules'
    ]

    modified_files = []

    for py_file in repo_root.rglob('*.py'):
        # Skip excluded directories
        if any(excl in str(py_file) for excl in exclude_patterns):
            continue

        if fix_imports_in_file(py_file):
            modified_files.append(py_file)
            print(f"Fixed imports in: {py_file}")

    print(f"\nImport fixes completed. Modified {len(modified_files)} files:")
    for f in modified_files[:10]:  # Show first 10
        print(f"  {f}")
    if len(modified_files) > 10:
        print(f"  ... and {len(modified_files) - 10} more")

if __name__ == '__main__':
    main()
