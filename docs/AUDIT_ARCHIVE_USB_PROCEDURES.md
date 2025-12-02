# AI Safety System - WORM USB Procedures

**Write-Once, Read-Many USB Drive Creation and Verification**

---

## Executive Summary

The AI Safety System WORM USB Builder creates immutable USB drives containing complete audit trails for air-gapped review and long-term archival. This ensures:

- **Immutability**: Files cannot be modified after creation
- **Verification**: Cryptographic hashes prove data integrity
- **Completeness**: All audit data (Merkle roots, proposals, decisions, incidents)
- **Tamper-Resistance**: Space exhaustion prevents future writes

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Detailed Procedures](#detailed-procedures)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Security Considerations](#security-considerations)
8. [FAQ](#faq)

---

## Overview

### What is WORM?

**WORM (Write-Once, Read-Many)** is a data storage paradigm where:
- Data can be written **once**
- Data can be read **many** times
- Data **cannot be modified** or deleted

### Why WORM for AI Safety?

AI Safety Systems require immutable audit trails to:
- Prevent tampering with safety records
- Provide verifiable evidence for investigations
- Enable offline review by security auditors
- Meet compliance requirements (SOC 2, ISO 27001)

### How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    WORM USB Creation                     │
├─────────────────────────────────────────────────────────┤
│  1. Collect Audit Data                                   │
│     - Merkle roots from MemoryStorage                    │
│     - AI-generated proposals                             │
│     - Human oversight decisions                          │
│     - Safety incident reports                            │
│                                                           │
│  2. Write to USB                                         │
│     - Structured JSON files                              │
│     - README with statistics                             │
│                                                           │
│  3. Make Read-Only                                       │
│     - Files: chmod 444 (r--r--r--)                       │
│     - Directories: chmod 555 (r-xr-xr-x)                 │
│                                                           │
│  4. Fill Remaining Space                                 │
│     - Cryptographically random data                      │
│     - Prevents future writes                             │
│                                                           │
│  5. Create Verification Manifest                         │
│     - SHA-256 hashes for all files                       │
│     - Root hash for verification                         │
│     - Immutability confirmation                          │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Hardware Requirements

- **USB Drive**:
  - Minimum size: 2 GB
  - Recommended: 8 GB or larger
  - Type: USB 2.0 or higher
  - Format: exFAT, FAT32, or ext4

### Software Requirements

```bash
# Python 3.8+
python --version

# Required packages
pip install -r requirements.txt
```

### Permissions

- **Read/Write access** to USB drive
- **sudo** not required (uses file permissions)

### USB Drive Preparation

```bash
# macOS: Format as exFAT
diskutil eraseDisk exFAT USB_AUDIT /dev/disk2

# Linux: Format as ext4
sudo mkfs.ext4 -L USB_AUDIT /dev/sdb1

# Windows: Format as exFAT via GUI
# Right-click drive → Format → exFAT
```

---

## Quick Start

### 1. Create WORM USB

```bash
# Full workflow (with space filling)
python ai_safety_worm_usb.py create /Volumes/USB_AUDIT

# Without space filling (faster, for testing)
python ai_safety_worm_usb.py create /Volumes/USB_AUDIT --no-fill
```

### 2. Verify Immutability

```bash
# Verify audit directory is read-only
python ai_safety_worm_usb.py verify /Volumes/USB_AUDIT/audit_20250110_143022
```

### 3. Get USB Information

```bash
# Show USB drive stats
python ai_safety_worm_usb.py info /Volumes/USB_AUDIT
```

### Example Output

```
================================================================================
Creating WORM USB Drive
================================================================================
USB Path: /Volumes/USB_AUDIT

[1/5] Collecting audit data...
✓ Wrote audit package to: /Volumes/USB_AUDIT/audit_20250110_143022
  - 15 proposals
  - 12 human decisions
  - 3 safety incidents
  - 4 Merkle roots

[2/5] Writing audit package...
✓ Wrote audit package to: /Volumes/USB_AUDIT/audit_20250110_143022

[3/5] Making files read-only...
✓ Made all files read-only in: /Volumes/USB_AUDIT/audit_20250110_143022

[4/5] Filling remaining space...
Free space on USB: 7.45 GB
Filling 7.44 GB with random data...
  Progress: 100.0% (7.44 GB)
✓ Filled 7.44 GB with random data (763 files)

[5/5] Creating verification manifest...
✓ All files have correct read-only permissions (444)
✓ All directories have correct read-only permissions (555)
✓ Write test failed (directory is immutable)
✓ Created manifest: /Volumes/USB_AUDIT/audit_20250110_143022/WORM_MANIFEST.json
  - 7 files
  - 1.23 MB audit data
  - 7.44 GB filler data
  - Root hash: a3f5c9e7b2d4f1a8...

================================================================================
✓ WORM USB Drive Created Successfully
================================================================================
Audit Directory: /Volumes/USB_AUDIT/audit_20250110_143022
Immutable: True
Root Hash: a3f5c9e7b2d4f1a8c3e6f9d2b5a8e1f4c7d0a3b6e9f2c5a8d1b4e7f0a3c6
```

---

## Detailed Procedures

### Procedure 1: Creating WORM USB (Python API)

```python
from ai_safety_worm_usb import WORMUSBBuilder
from memory_storage import MemoryStorage

# Initialize
storage = MemoryStorage()
builder = WORMUSBBuilder("/Volumes/USB_AUDIT")

# Create WORM drive
audit_dir = builder.create_worm_drive(storage, fill_space=True)

# Result
print(f"Audit directory: {audit_dir}")
# /Volumes/USB_AUDIT/audit_20250110_143022
```

### Procedure 2: Creating WORM USB (Step-by-Step)

```python
from ai_safety_worm_usb import WORMUSBBuilder
from memory_storage import MemoryStorage

# Step 1: Initialize
builder = WORMUSBBuilder("/Volumes/USB_AUDIT")
storage = MemoryStorage()

# Step 2: Collect audit data
package = builder.collect_audit_data(storage)
print(f"Collected: {package.metadata['total_proposals']} proposals")

# Step 3: Write to USB
audit_dir = builder.write_audit_package(package)
print(f"Wrote to: {audit_dir}")

# Step 4: Make read-only
builder.make_read_only(audit_dir)
print("Made read-only")

# Step 5: Fill space (optional)
filler_bytes = builder.fill_remaining_space()
print(f"Filled: {filler_bytes / (1024**3):.2f} GB")

# Step 6: Create manifest
manifest = builder.create_manifest(audit_dir, filler_bytes)
print(f"Root hash: {manifest.root_hash}")
```

### Procedure 3: Verifying WORM USB

```python
from ai_safety_worm_usb import WORMUSBBuilder
from pathlib import Path

# Load builder
audit_dir = Path("/Volumes/USB_AUDIT/audit_20250110_143022")
builder = WORMUSBBuilder(str(audit_dir.parent))

# Verify immutability
is_immutable = builder.verify_immutability(audit_dir)

if is_immutable:
    print("✓ Audit directory is immutable")
else:
    print("✗ Audit directory is NOT immutable")

# Load and verify manifest
import json
manifest_path = audit_dir / "WORM_MANIFEST.json"
with open(manifest_path, 'r') as f:
    manifest = json.load(f)

print(f"Files: {manifest['total_files']}")
print(f"Root hash: {manifest['root_hash']}")
print(f"Verified: {manifest['read_only_verified']}")
```

### Procedure 4: Extracting Data from WORM USB

```python
import json
from pathlib import Path

audit_dir = Path("/Volumes/USB_AUDIT/audit_20250110_143022")

# Load complete package
with open(audit_dir / "audit_package.json", 'r') as f:
    package = json.load(f)

# Access proposals
proposals = package['proposals']
for proposal in proposals:
    print(f"Proposal {proposal['id']}: {proposal['motivation']}")

# Access human decisions
decisions = package['human_decisions']
for decision in decisions:
    print(f"Decision: {decision['decision']} - {decision['reasoning']}")

# Access safety incidents
incidents = package['safety_incidents']
for incident in incidents:
    print(f"Incident {incident['incident_id']}: {incident['description']}")

# Verify Merkle roots
merkle_roots = package['merkle_roots']
for mem_type, root_hash in merkle_roots.items():
    print(f"{mem_type}: {root_hash}")
```

---

## Verification

### Manual Verification Checklist

#### File Permissions

```bash
# Check file permissions (should be 444)
ls -l /Volumes/USB_AUDIT/audit_*/

# Example output:
# -r--r--r--  1 user  staff  1234 Jan 10 14:30 audit_package.json
# -r--r--r--  1 user  staff   567 Jan 10 14:30 merkle_roots.json
```

#### Directory Permissions

```bash
# Check directory permissions (should be 555)
ls -ld /Volumes/USB_AUDIT/audit_*/

# Example output:
# dr-xr-xr-x  9 user  staff  288 Jan 10 14:30 audit_20250110_143022
```

#### Write Test

```bash
# Attempt to write (should fail)
echo "test" > /Volumes/USB_AUDIT/audit_*/test.txt
# Expected: Permission denied

# Attempt to modify existing file (should fail)
echo "test" >> /Volumes/USB_AUDIT/audit_*/README.txt
# Expected: Permission denied
```

### Cryptographic Verification

```python
import hashlib
import json
from pathlib import Path

audit_dir = Path("/Volumes/USB_AUDIT/audit_20250110_143022")

# Load manifest
with open(audit_dir / "WORM_MANIFEST.json", 'r') as f:
    manifest = json.load(f)

# Verify each file hash
for rel_path, expected_hash in manifest['file_hashes'].items():
    file_path = audit_dir / rel_path

    # Calculate actual hash
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()

    if actual_hash == expected_hash:
        print(f"✓ {rel_path}")
    else:
        print(f"✗ {rel_path} - HASH MISMATCH")

# Verify root hash
root_hasher = hashlib.sha256()
for path in sorted(manifest['file_hashes'].keys()):
    root_hasher.update(path.encode('utf-8'))
    root_hasher.update(manifest['file_hashes'][path].encode('utf-8'))
expected_root = manifest['root_hash']
actual_root = root_hasher.hexdigest()

if actual_root == expected_root:
    print(f"✓ Root hash verified: {actual_root[:16]}...")
else:
    print(f"✗ Root hash mismatch!")
```

---

## Troubleshooting

### Issue: Permission Denied (Not Enough Space)

**Symptom:**
```
OSError: [Errno 28] No space left on device
```

**Solution:**
```bash
# Check free space
df -h /Volumes/USB_AUDIT

# Use smaller chunk size
python -c "
from ai_safety_worm_usb import WORMUSBBuilder
builder = WORMUSBBuilder('/Volumes/USB_AUDIT')
builder.fill_remaining_space(chunk_size=1024*1024)  # 1MB chunks
"
```

### Issue: Cannot Make Files Read-Only

**Symptom:**
```
PermissionError: [Errno 1] Operation not permitted
```

**Solution:**
```bash
# Check USB is not write-protected
# Check filesystem supports chmod (FAT32 may not)

# macOS: Use exFAT instead of FAT32
diskutil eraseDisk exFAT USB_AUDIT /dev/disk2

# Linux: Use ext4
sudo mkfs.ext4 -L USB_AUDIT /dev/sdb1
```

### Issue: USB Path Not Found

**Symptom:**
```
ValueError: USB path does not exist: /Volumes/USB_AUDIT
```

**Solution:**
```bash
# macOS: Check mount point
ls /Volumes/

# Linux: Check mount point
ls /media/$USER/

# Windows: Check drive letter
dir E:\
```

### Issue: Out of Memory (Large Filler)

**Symptom:**
```
MemoryError: Unable to allocate array
```

**Solution:**
```python
# Use smaller chunk size
builder.fill_remaining_space(chunk_size=1*1024*1024)  # 1MB instead of 10MB
```

### Issue: Verification Fails

**Symptom:**
```
✗ File not read-only: README.txt (mode: 0o644)
```

**Solution:**
```bash
# Re-run make_read_only
python -c "
from ai_safety_worm_usb import WORMUSBBuilder
from pathlib import Path
builder = WORMUSBBuilder('/Volumes/USB_AUDIT')
audit_dir = Path('/Volumes/USB_AUDIT/audit_20250110_143022')
builder.make_read_only(audit_dir)
"
```

---

## Security Considerations

### Threat Model

The WORM USB Builder defends against:

1. **Accidental Modification**: File permissions prevent unintentional edits
2. **Malicious Tampering**: Read-only + space exhaustion prevents writes
3. **Data Corruption**: SHA-256 hashes detect corruption
4. **Replay Attacks**: Timestamps and Merkle roots prove freshness

### Limitations

The WORM USB Builder **does not** defend against:

1. **Physical Destruction**: USB can be physically destroyed
2. **Root/Admin Tampering**: Root user can override permissions
3. **Filesystem Format**: User can reformat the entire USB
4. **Hardware Backdoors**: Malicious USB firmware

### Best Practices

#### For Maximum Security

```bash
# 1. Use hardware write-protect switch (if available)
# 2. Create multiple copies on different USB drives
# 3. Store in secure location (safe, vault)
# 4. Use cryptographic signing (see worm_usb_builder.py)
# 5. Enable USB access logging

# Example: Create 3 copies
for i in {1..3}; do
    python ai_safety_worm_usb.py create /Volumes/USB_AUDIT_$i
done
```

#### For Chain of Custody

```python
# Add cryptographic signature
from ai_safety_worm_usb import WORMUSBBuilder
import hashlib
import hmac

audit_dir = Path("/Volumes/USB_AUDIT/audit_20250110_143022")
manifest_path = audit_dir / "WORM_MANIFEST.json"

# Calculate signature
secret = "your-secret-key"
with open(manifest_path, 'rb') as f:
    manifest_data = f.read()

signature = hmac.new(
    secret.encode('utf-8'),
    manifest_data,
    hashlib.sha256
).hexdigest()

print(f"Signature: {signature}")

# Store signature separately (not on USB)
with open("usb_signature.txt", 'w') as f:
    f.write(f"{audit_dir.name}\n")
    f.write(f"{signature}\n")
```

---

## FAQ

### Q: Can I add more data after creation?

**A:** No. The WORM design prevents writes after creation. To add more data, create a new audit directory.

### Q: How do I update a file?

**A:** You cannot update files in a WORM drive. This is intentional. Create a new audit directory with updated data.

### Q: What if I need to delete sensitive data?

**A:** WORM prevents deletion. If you need to remove data:
1. Physically destroy the USB drive
2. Or reformat the entire drive (loses all data)

### Q: How long does space filling take?

**A:** Approximately:
- 2 GB USB: 2-5 minutes
- 8 GB USB: 8-15 minutes
- 32 GB USB: 30-60 minutes
- 128 GB USB: 2-4 hours

### Q: Can I use the USB for other files?

**A:** Not recommended. The WORM builder fills all free space to prevent future writes. If you skip space filling (`--no-fill`), you could technically add more files, but this defeats the WORM purpose.

### Q: What filesystems are supported?

**A:**
- **exFAT**: ✓ Recommended (cross-platform, large files)
- **FAT32**: ⚠️ Limited (no chmod support on some systems)
- **ext4**: ✓ Good (Linux-only)
- **NTFS**: ⚠️ Limited (requires ntfs-3g on macOS/Linux)
- **HFS+**: ✓ Good (macOS-only)
- **APFS**: ✓ Good (macOS-only)

### Q: How do I verify data integrity?

**A:** Use the verification procedure:

```bash
python ai_safety_worm_usb.py verify /Volumes/USB_AUDIT/audit_20250110_143022
```

Or manually verify SHA-256 hashes in `WORM_MANIFEST.json`.

### Q: Can I create WORM drives programmatically?

**A:** Yes:

```python
from ai_safety_worm_usb import WORMUSBBuilder
from memory_storage import MemoryStorage

storage = MemoryStorage()
builder = WORMUSBBuilder("/Volumes/USB_AUDIT")
audit_dir = builder.create_worm_drive(storage)
```

### Q: What happens if the USB is unplugged during creation?

**A:**
- **During data write**: Incomplete audit directory. Re-run creation.
- **During space fill**: Partial filler data. Re-run `fill_remaining_space()`.
- **After completion**: No issue. USB is already immutable.

### Q: How do I transfer WORM USB to another system?

**A:** Simply plug the USB into the target system. All files are read-only and portable.

```bash
# macOS
ls /Volumes/USB_AUDIT/audit_*/

# Linux
ls /media/$USER/USB_AUDIT/audit_*/

# Windows
dir E:\audit_*
```

---

## Appendix: File Structure

### Audit Directory Layout

```
audit_20250110_143022/
├── audit_package.json       # Complete audit package
├── merkle_roots.json         # Merkle tree root hashes
├── proposals.json            # AI-generated proposals
├── human_decisions.json      # Human oversight decisions
├── safety_incidents.json     # Safety incident reports
├── metadata.json             # Package metadata
├── README.txt                # Human-readable summary
└── WORM_MANIFEST.json        # Verification manifest

.worm_filler/                 # Random filler data
├── filler_0000.bin
├── filler_0001.bin
├── filler_0002.bin
└── ...
```

### Example audit_package.json

```json
{
  "timestamp": "2025-01-10T14:30:22.123456",
  "merkle_roots": {
    "episodic": "a3f5c9e7b2d4f1a8c3e6f9d2b5a8e1f4c7d0a3b6e9f2c5a8d1b4e7f0a3c6",
    "procedural": "b4e6d0f8c3a5e2b7d1f4a9c6e3b0f5d8a2c7e1b5d9f3a6c0e4b8d2f6a1c5",
    "semantic": "c5f7e1a9d4b6f2c8e3a0d5b9f4c7e2a6d1b5f0c8e3a7d2b6f1c5e0a4d8b3"
  },
  "proposals": [
    {
      "id": "prop_001",
      "system_id": 1,
      "timestamp": "2025-01-10T14:25:00.000000",
      "motivation": "Improve deception detection using attention patterns",
      "changes": {"add": "deception_detector_v2.py"},
      "status": "approved"
    }
  ],
  "human_decisions": [
    {
      "decision_id": "dec_001",
      "proposal_id": "prop_001",
      "decision": "approved_with_conditions",
      "reasoning": "Good proposal, requires additional testing",
      "timestamp": "2025-01-10T14:26:00.000000",
      "conditions": ["Add unit tests", "Security review"]
    }
  ],
  "safety_incidents": [
    {
      "incident_id": "inc_001",
      "type": "deception_detected",
      "severity": "HIGH",
      "systems_involved": [1, 3],
      "description": "Overconfident proposal with missing uncertainties",
      "timestamp": "2025-01-10T14:20:00.000000"
    }
  ],
  "metadata": {
    "collection_timestamp": "2025-01-10T14:30:22.123456",
    "total_proposals": 15,
    "total_decisions": 12,
    "total_incidents": 3,
    "merkle_roots_count": 3
  }
}
```

### Example WORM_MANIFEST.json

```json
{
  "created": "2025-01-10T14:35:00.123456",
  "audit_dir": "/Volumes/USB_AUDIT/audit_20250110_143022",
  "total_files": 7,
  "total_size_bytes": 1289456,
  "filler_size_bytes": 7987654321,
  "file_hashes": {
    "audit_package.json": "a3f5c9e7b2d4f1a8c3e6f9d2b5a8e1f4c7d0a3b6e9f2c5a8d1b4e7f0a3c6",
    "merkle_roots.json": "b4e6d0f8c3a5e2b7d1f4a9c6e3b0f5d8a2c7e1b5d9f3a6c0e4b8d2f6a1c5",
    "proposals.json": "c5f7e1a9d4b6f2c8e3a0d5b9f4c7e2a6d1b5f0c8e3a7d2b6f1c5e0a4d8b3",
    "human_decisions.json": "d6a8f2b0c5e3d7f1a4c9e6b3d0f5a8c2e7b1d5f9a3c6e0b4d8f2a6c1e5b9",
    "safety_incidents.json": "e7b9f3c1d6a4e8f2b5d0a9c7e4b2f6d1a5c8e3b7d1f5a0c4e9b6d3f8a2c6",
    "metadata.json": "f8c0a4d2b7e5f9c3a6d1b8e5c2f7a0d4b9e6c3f1a5d8b2e7c4f0a9d6b3e8",
    "README.txt": "a9d1b5c3e8f4a7d2b6e0c5f9a3d7b1e6c4f8a2d5b9e3c7f1a6d0b4e8c2f6"
  },
  "root_hash": "b0e2c4f6a8d1b3e5c7f9a2d4b6e8c0f2a5d7b9e1c3f5a8d0b2e4c6f8a1d3",
  "read_only_verified": true
}
```

---

## Support

For issues or questions:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review [START_HERE.md](../START_HERE.md)
3. Open an issue on GitHub

---

**Status:** Production Ready
**Last Updated:** 2025-01-10
**Version:** 1.0.0
