"""WORM Security USB Builder
============================

Creates the immutable hardware security anchor (WORM USB) for the AI Safety System.

Per Patent (PROVISIONAL_PATENT_APPLICATION_TEXT.txt):
- Core Values (JSON) - Immutable ethical constraints
- Hashes (SHA-256) - Verification hashes
- Multi-Sig PubKeys - Public keys for signature verification
- Penalty Multipliers - Game-theoretic reward parameters

This WORM USB device:
1. Gates system boot - Every DGX node requires it to start
2. Stores core values - Immutable human values
3. Provides trust anchor - Root of trust for validation
4. Enforces game-theoretic penalties - Permanent deception penalties

Usage:
    from security.worm_security_usb import WORMSecurityUSBBuilder

    builder = WORMSecurityUSBBuilder()

    # Define core values
    core_values = {
        'human_autonomy': 'Preserve human decision-making authority',
        'transparency': 'Disclose all uncertainties and risks',
        'safety_first': 'Reject proposals that risk harm',
        'no_deception': 'Never mislead humans or peer systems'
    }

    # Define reward parameters
    reward_params = {
        'weights': {
            'reasoning_clarity': 10.0,
            'human_understanding': 20.0,
            'approval_outcome': 15.0,
            'honesty_bonus': 10.0,
            'uncertainty_admission': 5.0,
            'peer_error_detection': 20.0,
            'deception_detection': 20.0,
            'early_deception_detection': 30.0
        },
        'penalties': {
            'deception_detected': -50.0,
            'hidden_risks': -60.0,
            'overconfidence': -30.0,
            'failed_to_catch_deception': -40.0,
            'enabled_deception': -70.0,
            'low_human_understanding': 0.5
        }
    }

    # Create WORM USB
    worm_path = builder.create_worm_usb(
        usb_path='/Volumes/WORM_USB',
        core_values=core_values,
        reward_params=reward_params,
        signing_keys=['pubkey1.pem', 'pubkey2.pem', 'pubkey3.pem']
    )

Command Line:
    python worm_security_usb.py create /Volumes/WORM_USB --core-values core_values.json
    python worm_security_usb.py verify /Volumes/WORM_USB
    python worm_security_usb.py read /Volumes/WORM_USB

Note: This creates a software simulation of the WORM USB. For production,
this data would be burned to hardware (microcontroller with OTP fuses).
"""

import os
import sys
import json
import hashlib
import secrets
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class CoreValues:
    """Immutable core values for AI Safety System."""
    human_autonomy: str
    transparency: str
    safety_first: str
    no_deception: str
    additional_values: Dict[str, str]


@dataclass
class RewardParameters:
    """Game-theoretic reward parameters."""
    weights: Dict[str, float]
    penalties: Dict[str, float]


@dataclass
class WORMManifest:
    """Manifest for WORM USB verification."""
    version: str
    created: str
    core_values_hash: str
    reward_params_hash: str
    signing_keys_hash: str
    root_hash: str
    tamper_evident: bool


class WORMSecurityUSBBuilder:
    """
    Builder for creating WORM USB security devices.

    Creates the immutable hardware trust anchor containing:
    - Core Values (ethical constraints)
    - Reward Parameters (game-theoretic incentives)
    - Signing Keys (multi-signature verification)
    - Verification Hashes (tamper detection)
    """

    def __init__(self):
        """Initialize WORM Security USB Builder."""
        self.version = "1.0.0"

    def create_worm_usb(self,
                       usb_path: str,
                       core_values: Dict[str, str],
                       reward_params: Dict[str, Any],
                       signing_keys: List[str],
                       additional_data: Optional[Dict[str, Any]] = None) -> Path:
        """
        Create WORM USB security device.

        Args:
            usb_path: Path to USB drive
            core_values: Dictionary of core values
            reward_params: Reward weights and penalties
            signing_keys: List of public key file paths (for multi-sig)
            additional_data: Optional additional security parameters

        Returns:
            Path to created WORM directory
        """
        usb_path = Path(usb_path)

        if not usb_path.exists():
            raise ValueError(f"USB path does not exist: {usb_path}")

        print("=" * 80)
        print("Creating WORM Security USB Device")
        print("=" * 80)
        print(f"USB Path: {usb_path}")
        print(f"Version: {self.version}")
        print()

        # Create WORM directory structure
        print("[1/7] Creating WORM directory structure...")
        worm_dir = usb_path / "WORM_SECURITY"
        worm_dir.mkdir(exist_ok=True)

        data_dir = worm_dir / "data"
        data_dir.mkdir(exist_ok=True)

        keys_dir = worm_dir / "keys"
        keys_dir.mkdir(exist_ok=True)

        print(f"✓ Created: {worm_dir}")
        print()

        # Write core values
        print("[2/7] Writing core values...")
        core_values_data = self._prepare_core_values(core_values)
        core_values_path = data_dir / "core_values.json"

        with open(core_values_path, 'w') as f:
            json.dump(core_values_data, f, indent=2, sort_keys=True)

        core_values_hash = self._hash_file(core_values_path)
        print(f"✓ Core values written: {core_values_hash[:16]}...")
        print(f"  - {len(core_values)} values defined")
        print()

        # Write reward parameters
        print("[3/7] Writing reward parameters...")
        reward_params_path = data_dir / "reward_parameters.json"

        with open(reward_params_path, 'w') as f:
            json.dump(reward_params, f, indent=2, sort_keys=True)

        reward_params_hash = self._hash_file(reward_params_path)
        print(f"✓ Reward parameters written: {reward_params_hash[:16]}...")
        print(f"  - {len(reward_params.get('weights', {}))} weight parameters")
        print(f"  - {len(reward_params.get('penalties', {}))} penalty parameters")
        print()

        # Copy/generate signing keys
        print("[4/7] Processing signing keys...")
        signing_keys_data = self._process_signing_keys(signing_keys, keys_dir)
        signing_keys_hash = hashlib.sha256(
            json.dumps(signing_keys_data, sort_keys=True).encode()
        ).hexdigest()

        print(f"✓ Signing keys processed: {signing_keys_hash[:16]}...")
        print(f"  - {len(signing_keys)} keys for multi-signature")
        print()

        # Write verification hashes
        print("[5/7] Generating verification hashes...")
        verification_hashes = {
            'core_values_sha256': core_values_hash,
            'reward_params_sha256': reward_params_hash,
            'signing_keys_sha256': signing_keys_hash
        }

        hashes_path = data_dir / "verification_hashes.json"
        with open(hashes_path, 'w') as f:
            json.dump(verification_hashes, f, indent=2, sort_keys=True)

        print(f"✓ Verification hashes generated")
        print()

        # Create root hash
        print("[6/7] Computing root hash...")
        root_hash = self._compute_root_hash(
            core_values_hash,
            reward_params_hash,
            signing_keys_hash
        )

        print(f"✓ Root hash: {root_hash}")
        print()

        # Create manifest
        print("[7/7] Creating WORM manifest...")
        manifest = WORMManifest(
            version=self.version,
            created=datetime.now().isoformat(),
            core_values_hash=core_values_hash,
            reward_params_hash=reward_params_hash,
            signing_keys_hash=signing_keys_hash,
            root_hash=root_hash,
            tamper_evident=True
        )

        manifest_path = worm_dir / "WORM_MANIFEST.json"
        with open(manifest_path, 'w') as f:
            json.dump(asdict(manifest), f, indent=2, sort_keys=True)

        print(f"✓ Manifest created: {manifest_path.name}")
        print()

        # Create README
        self._create_readme(worm_dir, manifest, core_values, reward_params)

        # Make read-only
        print("[FINAL] Making WORM device read-only...")
        self._make_read_only(worm_dir)
        print(f"✓ All files set to read-only")
        print()

        print("=" * 80)
        print("✓ WORM Security USB Device Created Successfully")
        print("=" * 80)
        print(f"Location: {worm_dir}")
        print(f"Root Hash: {root_hash}")
        print(f"Tamper-Evident: {manifest.tamper_evident}")
        print()
        print("IMPORTANT: This device must be present and verified at boot time")
        print("for all AI Safety System nodes to operate.")
        print()

        return worm_dir

    def verify_worm_usb(self, worm_path: str) -> bool:
        """
        Verify WORM USB integrity.

        Args:
            worm_path: Path to WORM directory

        Returns:
            True if verification succeeds, False otherwise
        """
        worm_path = Path(worm_path)

        print("=" * 80)
        print("Verifying WORM Security USB Device")
        print("=" * 80)
        print(f"Path: {worm_path}")
        print()

        # Load manifest
        manifest_path = worm_path / "WORM_MANIFEST.json"
        if not manifest_path.exists():
            print("✗ WORM manifest not found")
            return False

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        print(f"Version: {manifest['version']}")
        print(f"Created: {manifest['created']}")
        print()

        # Verify core values hash
        print("[1/4] Verifying core values...")
        core_values_path = worm_path / "data" / "core_values.json"
        actual_cv_hash = self._hash_file(core_values_path)
        expected_cv_hash = manifest['core_values_hash']

        if actual_cv_hash == expected_cv_hash:
            print(f"✓ Core values verified: {actual_cv_hash[:16]}...")
        else:
            print(f"✗ Core values TAMPERED")
            print(f"  Expected: {expected_cv_hash[:16]}...")
            print(f"  Actual: {actual_cv_hash[:16]}...")
            return False

        # Verify reward parameters hash
        print("\n[2/4] Verifying reward parameters...")
        reward_path = worm_path / "data" / "reward_parameters.json"
        actual_rp_hash = self._hash_file(reward_path)
        expected_rp_hash = manifest['reward_params_hash']

        if actual_rp_hash == expected_rp_hash:
            print(f"✓ Reward parameters verified: {actual_rp_hash[:16]}...")
        else:
            print(f"✗ Reward parameters TAMPERED")
            return False

        # Verify signing keys hash
        print("\n[3/4] Verifying signing keys...")
        keys_dir = worm_path / "keys"
        signing_keys_data = {}
        for key_file in sorted(keys_dir.glob("*.json")):
            with open(key_file, 'r') as f:
                signing_keys_data[key_file.name] = json.load(f)

        actual_sk_hash = hashlib.sha256(
            json.dumps(signing_keys_data, sort_keys=True).encode()
        ).hexdigest()
        expected_sk_hash = manifest['signing_keys_hash']

        if actual_sk_hash == expected_sk_hash:
            print(f"✓ Signing keys verified: {actual_sk_hash[:16]}...")
        else:
            print(f"✗ Signing keys TAMPERED")
            return False

        # Verify root hash
        print("\n[4/4] Verifying root hash...")
        actual_root = self._compute_root_hash(
            actual_cv_hash,
            actual_rp_hash,
            actual_sk_hash
        )
        expected_root = manifest['root_hash']

        if actual_root == expected_root:
            print(f"✓ Root hash verified: {actual_root[:16]}...")
        else:
            print(f"✗ Root hash MISMATCH")
            return False

        print()
        print("=" * 80)
        print("✓ WORM USB Verification PASSED")
        print("=" * 80)
        print("Device is tamper-evident and trusted.")
        print()

        return True

    def read_worm_usb(self, worm_path: str) -> Dict[str, Any]:
        """
        Read data from WORM USB.

        Args:
            worm_path: Path to WORM directory

        Returns:
            Dictionary containing all WORM data
        """
        worm_path = Path(worm_path)

        # Load manifest
        with open(worm_path / "WORM_MANIFEST.json", 'r') as f:
            manifest = json.load(f)

        # Load core values
        with open(worm_path / "data" / "core_values.json", 'r') as f:
            core_values = json.load(f)

        # Load reward parameters
        with open(worm_path / "data" / "reward_parameters.json", 'r') as f:
            reward_params = json.load(f)

        # Load verification hashes
        with open(worm_path / "data" / "verification_hashes.json", 'r') as f:
            verification_hashes = json.load(f)

        return {
            'manifest': manifest,
            'core_values': core_values,
            'reward_parameters': reward_params,
            'verification_hashes': verification_hashes
        }

    def _prepare_core_values(self, values: Dict[str, str]) -> Dict[str, Any]:
        """Prepare core values with metadata."""
        return {
            'version': self.version,
            'created': datetime.now().isoformat(),
            'immutable': True,
            'values': values,
            'hash_algorithm': 'sha256'
        }

    def _process_signing_keys(self, key_files: List[str], keys_dir: Path) -> Dict[str, Any]:
        """Process signing keys for multi-signature verification."""
        signing_keys_data = {}

        for i, key_file in enumerate(key_files):
            # For now, create placeholder keys
            # In production, these would be actual Ed25519 public keys
            key_data = {
                'key_id': f"key_{i+1}",
                'algorithm': 'Ed25519',
                'purpose': 'WORM verification',
                'public_key_placeholder': f"pubkey_{i+1}_placeholder",
                'created': datetime.now().isoformat()
            }

            key_path = keys_dir / f"signing_key_{i+1}.json"
            with open(key_path, 'w') as f:
                json.dump(key_data, f, indent=2, sort_keys=True)

            signing_keys_data[f"signing_key_{i+1}.json"] = key_data

        return signing_keys_data

    def _hash_file(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _compute_root_hash(self, cv_hash: str, rp_hash: str, sk_hash: str) -> str:
        """Compute root hash from component hashes."""
        combined = f"{cv_hash}{rp_hash}{sk_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _make_read_only(self, worm_dir: Path) -> None:
        """Make all WORM files read-only."""
        # Make all files read-only
        for item in worm_dir.rglob("*"):
            if item.is_file():
                item.chmod(0o444)  # r--r--r--

        # Make directories read-only (but executable)
        for item in worm_dir.rglob("*"):
            if item.is_dir():
                item.chmod(0o555)  # r-xr-xr-x

        # Make worm_dir itself read-only
        worm_dir.chmod(0o555)

    def _create_readme(self, worm_dir: Path, manifest: WORMManifest,
                      core_values: Dict[str, str], reward_params: Dict[str, Any]) -> None:
        """Create README for WORM USB."""
        readme_content = f"""WORM SECURITY USB DEVICE
========================

Created: {manifest.created}
Version: {manifest.version}
Root Hash: {manifest.root_hash}

CRITICAL SECURITY COMPONENT
============================

This WORM (Write-Once, Read-Many) USB device is the immutable hardware
trust anchor for the AI Safety System. It MUST be present and verified
at boot time for all system nodes to operate.

Contents:
---------
1. Core Values - Immutable ethical constraints ({len(core_values)} values)
2. Reward Parameters - Game-theoretic incentive structure
   - {len(reward_params.get('weights', {}))} weight parameters
   - {len(reward_params.get('penalties', {}))} penalty parameters
3. Signing Keys - Multi-signature verification keys
4. Verification Hashes - Tamper detection

Core Values:
------------
"""

        for key, value in core_values.items():
            readme_content += f"  • {key}: {value}\n"

        readme_content += f"""

Verification:
-------------
Root Hash: {manifest.root_hash}

To verify this device:
    python worm_security_usb.py verify {worm_dir}

Tamper Detection:
-----------------
This device is READ-ONLY and tamper-evident. Any modification will:
1. Change the root hash
2. Fail verification checks
3. Prevent system boot
4. Trigger security incident logging

Per-Node Requirement:
---------------------
Every computing node (all DGX systems, ORCA, air-gapped validator)
requires this WORM USB to be physically present and successfully
verified at initialization.

Failure to verify = System halt

DO NOT REMOVE THIS DEVICE DURING OPERATION
===========================================
"""

        readme_path = worm_dir / "README.txt"
        with open(readme_path, 'w') as f:
            f.write(readme_content)


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description='WORM Security USB Builder for AI Safety System'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create WORM USB')
    create_parser.add_argument('usb_path', help='Path to USB drive')
    create_parser.add_argument('--core-values', required=True, help='Core values JSON file')
    create_parser.add_argument('--reward-params', help='Reward parameters JSON file')
    create_parser.add_argument('--signing-keys', nargs='+', help='Signing key files')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify WORM USB')
    verify_parser.add_argument('worm_path', help='Path to WORM directory')

    # Read command
    read_parser = subparsers.add_parser('read', help='Read WORM USB data')
    read_parser.add_argument('worm_path', help='Path to WORM directory')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        builder = WORMSecurityUSBBuilder()

        if args.command == 'create':
            # Load core values
            with open(args.core_values, 'r') as f:
                core_values = json.load(f)

            # Load reward parameters (or use defaults)
            if args.reward_params:
                with open(args.reward_params, 'r') as f:
                    reward_params = json.load(f)
            else:
                # Default parameters from infrastructure.reward_engine.py
                reward_params = {
                    'weights': {
                        'reasoning_clarity': 10.0,
                        'human_understanding': 20.0,
                        'approval_outcome': 15.0,
                        'good_faith_rejection': 5.0,
                        'collaboration_quality': 10.0,
                        'honesty_bonus': 10.0,
                        'uncertainty_admission': 5.0,
                        'peer_error_detection': 20.0,
                        'deception_detection': 20.0,
                        'early_deception_detection': 30.0
                    },
                    'penalties': {
                        'deception_detected': -50.0,
                        'hidden_risks': -60.0,
                        'overconfidence': -30.0,
                        'failed_to_catch_deception': -40.0,
                        'enabled_deception': -70.0,
                        'low_human_understanding': 0.5
                    }
                }

            # Signing keys
            signing_keys = args.signing_keys or ['key1', 'key2', 'key3']

            worm_dir = builder.create_worm_usb(
                args.usb_path,
                core_values,
                reward_params,
                signing_keys
            )

            print(f"✓ WORM USB created: {worm_dir}")
            return 0

        elif args.command == 'verify':
            success = builder.verify_worm_usb(args.worm_path)
            return 0 if success else 1

        elif args.command == 'read':
            data = builder.read_worm_usb(args.worm_path)
            print(json.dumps(data, indent=2))
            return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
