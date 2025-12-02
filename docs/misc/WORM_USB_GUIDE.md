# 🔒 ORKASTRATOR WORM USB Key Creation Guide

Complete guide for creating Write-Once-Read-Many (WORM) USB keys for the ORKASTRATOR AI Safety System.

---

## 📋 Overview

This system creates tamper-proof USB keys containing:

1. **AURA Compression Templates** - Pattern dictionaries for efficient data compression
2. **System Configuration** - Core hashes, model definitions, debate parameters
3. **Cryptographic Filler** - Random data filling remaining space for immutability

**Purpose**: Create audit-proof, tamper-evident storage media for AI safety critical data.

---

## 🎯 Requirements

### Hardware
- **USB Flash Drives**: 1GB capacity (minimum)
- **Recommended**: SanDisk, Kingston, or Samsung brand
- **Quantity**: As many as needed (script processes one at a time)

### Software
- **Python 3.8+**
- **Operating System**: macOS, Linux, or Windows
- **Permissions**: Write access to USB drive

### Dependencies
All dependencies are Python standard library:
- `hashlib` - Cryptographic hashing
- `secrets` - Cryptographically secure random generation
- `json` - Data serialization
- `pathlib` - File system operations

---

## 🚀 Quick Start

### Step 1: Prepare USB Drive

1. Insert blank 1GB USB flash drive
2. **Optional**: Format as FAT32 or exFAT for cross-platform compatibility
3. Note the mount path:
   - **macOS**: `/Volumes/USB_DRIVE`
   - **Linux**: `/media/username/USB_DRIVE`
   - **Windows**: `D:\` or `E:\` etc.

### Step 2: Run Creation Script

```bash
# Navigate to repository
cd /Users/hendrixx./AI-Safety-System-Design

# Run WORM USB creator
python create_worm_usb.py /Volumes/USB_DRIVE
```

### Step 3: Verify

```bash
# Verify integrity
python verify_worm_integrity.py /Volumes/USB_DRIVE/ORKASTRATOR_WORM
```

### Step 4: Eject Safely

```bash
# macOS
diskutil eject /Volumes/USB_DRIVE

# Linux
umount /media/username/USB_DRIVE

# Windows - Use "Safely Remove Hardware"
```

---

## 📊 What Gets Created

### Directory Structure

```
/Volumes/USB_DRIVE/
└── ORKASTRATOR_WORM/
    ├── MANIFEST.json              # Complete integrity manifest
    ├── README.txt                 # Human-readable information
    ├── data/
    │   ├── compression_templates/
    │   │   ├── common_patterns.json    # AURA pattern dictionary
    │   │   └── dictionary.json         # Token compression dictionary
    │   └── system/
    │       ├── core_hashes.json        # Core component hashes
    │       ├── system_info.json        # Model definitions
    │       └── config.json             # System configuration
    └── .filler/
        ├── random_0000.bin        # Cryptographic random data
        ├── random_0001.bin        # (Fills remaining space)
        └── ...
```

### File Contents

#### `compression_templates/common_patterns.json`
```json
{
  "version": "1.0",
  "patterns": [
    {"id": "http_req", "pattern": "GET /api/", "freq": 0.85},
    {"id": "http_res", "pattern": "{\"status\":\"success\"", "freq": 0.92},
    {"id": "ai_model", "pattern": "TIF|GIN|TORI|THEO|NOVEL|VAL|ORKA", "freq": 0.88}
  ]
}
```

#### `compression_templates/dictionary.json`
```json
{
  "version": "1.0",
  "words": [
    "proposal", "debate", "consensus", "detection", "deception",
    "agent", "orchestrator", "validator", "penalty", "reputation"
  ],
  "tokens": {
    "models": ["TIF", "GIN", "TORI", "THEO", "NOVEL", "VAL", "ORKA"],
    "statuses": ["approved", "rejected", "in_review", "pending"]
  }
}
```

#### `system/core_hashes.json`
```json
{
  "core_values_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "alignment_filter_hash": "5bdb62947a9cee2fa77d038483e0b4894e9735c7b690d8062a1b48266aaf5639",
  "debate_engine_hash": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a"
}
```

#### `system/system_info.json`
```json
{
  "system_name": "ORKASTRATOR",
  "version": "0.4.1-dev",
  "models": {
    "TIF": "Scientific Research Model",
    "GIN": "Engineering Model",
    "TORI": "Historical Analysis Model",
    "THEO": "Theoretical Model",
    "NOVEL": "Creative Model",
    "ORKA": "Orchestrator (System Coordinator)",
    "VAL": "Validator Model"
  },
  "features": [
    "Multi-round debate engine",
    "Claim verification system",
    "Deception detection",
    "Reputation tracking"
  ]
}
```

#### `MANIFEST.json` (Excerpt)
```json
{
  "created": "2025-11-12T10:30:45.123456",
  "version": "0.4.1-dev",
  "system_name": "ORKASTRATOR",
  "usb_capacity_gb": 1.0,
  "data_size_bytes": 12582912,
  "filler_size_bytes": 1060372480,
  "total_files": 187,
  "root_hash": "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a",
  "file_hashes": {
    "data/compression_templates/common_patterns.json": "e3b0c442...",
    "data/compression_templates/dictionary.json": "5bdb6294...",
    ...
  },
  "core_hashes": { ... }
}
```

---

## 🔐 Security Features

### 1. Write-Once-Read-Many (WORM)
- All files set to **read-only** permissions (`0o444`)
- Directories set to **read-execute only** (`0o555`)
- **Cannot be modified** without root/admin access
- Filesystem-level immutability

### 2. Cryptographic Integrity
- **SHA-256 hashes** for every file
- **Root hash** computed from all file hashes (Merkle tree concept)
- Tamper detection via hash verification
- Cryptographically secure random filler

### 3. Random Filler
- Uses Python's `secrets` module (cryptographically secure)
- Fills **remaining space** on USB drive
- Prevents selective file replacement attacks
- Makes capacity analysis attacks harder

### 4. Verification
- Multi-level integrity checking
- Read-only permission verification
- File existence validation
- Hash mismatch detection
- Unexpected file detection

---

## 📐 Technical Details

### Space Allocation

For a 1GB USB drive:
- **~12 MB**: System data (templates, config, manifest)
- **~50 MB**: Safety margin (reserved)
- **~960 MB**: Cryptographic random filler

### Random Data Generation

```python
# Cryptographically secure random generation
random_data = secrets.token_bytes(chunk_size)

# Not using os.urandom() or random module
# secrets module uses OS-provided CSPRNG
```

### Hash Calculation

```python
# File hash (SHA-256)
h = hashlib.sha256()
with open(file_path, 'rb') as f:
    while chunk := f.read(8192):
        h.update(chunk)
file_hash = h.hexdigest()

# Root hash (all files)
h = hashlib.sha256()
for path in sorted(file_hashes.keys()):
    h.update(path.encode())
    h.update(file_hashes[path].encode())
root_hash = h.hexdigest()
```

### Permissions

```python
# Files: r--r--r-- (0o444)
path.chmod(0o444)

# Directories: r-xr-xr-x (0o555)
path.chmod(0o555)
```

---

## 🔍 Verification Process

### Automated Verification

Run the verification script:

```bash
python verify_worm_integrity.py /Volumes/USB_DRIVE/ORKASTRATOR_WORM
```

**Checks performed:**
1. ✅ **Manifest Load** - MANIFEST.json exists and is valid JSON
2. ✅ **Read-Only** - All files have correct permissions
3. ✅ **File Existence** - All manifest files are present
4. ✅ **File Hashes** - Each file hash matches manifest
5. ✅ **Root Hash** - Overall integrity hash is correct
6. ✅ **Unexpected Files** - No unauthorized files added

### Manual Verification

**Check read-only permissions:**
```bash
find ORKASTRATOR_WORM -type f -not -perm 444 | wc -l
# Should output: 0
```

**Check root hash:**
```bash
python -c "import json; print(json.load(open('ORKASTRATOR_WORM/MANIFEST.json'))['root_hash'])"
```

**Count files:**
```bash
find ORKASTRATOR_WORM -type f | wc -l
```

---

## 🎨 Customization

### Add Custom Templates

Edit the `COMPRESSION_TEMPLATES` dictionary in `create_worm_usb.py`:

```python
COMPRESSION_TEMPLATES = {
    "common_patterns.json": { ... },
    "dictionary.json": { ... },
    "custom_patterns.json": {  # Add your own
        "version": "1.0",
        "patterns": [
            {"id": "custom_1", "pattern": "your_pattern", "freq": 0.9}
        ]
    }
}
```

### Adjust USB Size

```python
# For 2GB USB
creator = WORMUSBCreator(usb_path, target_size_gb=2.0)

# For 512MB USB
creator = WORMUSBCreator(usb_path, target_size_gb=0.5)
```

### Disable Random Filler

```python
# Skip random filler (NOT RECOMMENDED for production)
package = creator.create_worm_drive(fill_with_random=False)
```

### Change Safety Margin

```python
# In _fill_remaining_space method
safety_margin = 100 * 1024 * 1024  # 100MB instead of 50MB
```

---

## ⚠️ Security Considerations

### ✅ DO
- ✅ **Verify integrity** before distributing
- ✅ **Use brand-name** USB drives
- ✅ **Test on multiple computers** before mass production
- ✅ **Store master copy** in secure location
- ✅ **Document serial numbers** for tracking
- ✅ **Use fresh, blank** USB drives

### ❌ DON'T
- ❌ **Modify files** after creation (defeats WORM purpose)
- ❌ **Reuse USB drives** that held other data
- ❌ **Skip verification** step
- ❌ **Use system directories** as USB path
- ❌ **Share before verification** completes
- ❌ **Disable random filler** in production

---

## 🐛 Troubleshooting

### Issue: "USB path does not exist"
**Solution**: Verify USB is mounted and path is correct
```bash
# macOS - list mounted volumes
ls /Volumes/

# Linux - list mounted media
ls /media/$USER/
```

### Issue: "Insufficient space for filler"
**Solution**: USB drive is too small or has existing data
```bash
# Check available space
df -h /Volumes/USB_DRIVE

# Solution: Use larger USB or format to reclaim space
```

### Issue: "Permission denied" when setting read-only
**Solution**: Run with appropriate permissions
```bash
# macOS/Linux
sudo python create_worm_usb.py /Volumes/USB_DRIVE

# Or change USB ownership first
sudo chown -R $USER /Volumes/USB_DRIVE
```

### Issue: Verification fails with hash mismatches
**Causes**:
1. USB drive has bad sectors (hardware issue)
2. Files were modified after creation
3. Filesystem corruption

**Solution**:
```bash
# Try different USB drive
# Check USB health with disk utility
# Recreate WORM USB from scratch
```

### Issue: Random filler takes too long
**Solution**: Reduce chunk size for progress feedback
```python
# In create_worm_usb.py
chunk_size = 5 * 1024 * 1024  # 5MB instead of 10MB
```

---

## 📚 Advanced Usage

### Batch Creation (Multiple USB Drives)

```bash
#!/bin/bash
# batch_create_worm.sh

for usb in /Volumes/USB_DRIVE_*; do
    echo "Creating WORM on $usb"
    python create_worm_usb.py "$usb"
    python verify_worm_integrity.py "$usb/ORKASTRATOR_WORM"
done
```

### JSON Export of Verification

```python
import json

verifier = WORMVerifier(worm_path)
success, results = verifier.verify()

# Export to JSON
with open('verification_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

### Integration with CI/CD

```yaml
# .github/workflows/worm_verification.yml
name: WORM Integrity Check

on: [push]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Verify WORM Templates
        run: |
          python verify_worm_integrity.py ./test_worm_usb
```

---

## 📖 Related Documentation

- [DEBATE_ENGINE_ANALYSIS.md](DEBATE_ENGINE_ANALYSIS.md) - Debate engine architecture
- [ui/README.md](ui/README.md) - ORKASTRATOR GUI documentation
- [ui/STANDALONE.md](ui/STANDALONE.md) - Standalone mode guide
- [worm_manifest.py](worm_manifest.py) - WORM manifest implementation

---

## 🎯 Use Cases

### 1. Audit Trail
Create tamper-proof records of AI decisions and debates for regulatory compliance.

### 2. Distribution
Ship compression templates and system configuration on immutable media.

### 3. Backup
Create verified backups of critical AI safety parameters.

### 4. Air-Gapped Systems
Provide system data to isolated environments without network dependency.

### 5. Forensics
Maintain chain-of-custody for AI incident investigation.

---

## ✅ Checklist for Production

Before distributing WORM USB keys:

- [ ] Run creation script on test USB
- [ ] Verify integrity passes all checks
- [ ] Test read-only enforcement (try to modify file)
- [ ] Verify cross-platform compatibility (test on multiple OS)
- [ ] Document USB serial numbers
- [ ] Store master template
- [ ] Create verification logs
- [ ] Test on target deployment environment
- [ ] Validate compression templates are correct
- [ ] Review README.txt on USB for accuracy

---

## 🌟 Summary

The ORKASTRATOR WORM USB system provides:

✅ **Tamper-Proof Storage** - Cryptographic integrity verification
✅ **Immutable Data** - Read-only enforcement at filesystem level
✅ **Random Filler** - Prevents capacity-based attacks
✅ **Easy Verification** - Automated integrity checking
✅ **Cross-Platform** - Works on macOS, Linux, Windows
✅ **Zero Dependencies** - Uses Python standard library only
✅ **Production Ready** - Comprehensive error handling and validation

Perfect for distributing AI safety critical data on physically secure media.
