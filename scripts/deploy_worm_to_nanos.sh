#!/bin/bash
# Deploy WORM USB to all Nano nodes
# Each nano has a 960MB USB key mounted at /media/{user}/6745-2301

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==============================================="
echo "🔒 ORKASTRATOR WORM USB Deployment to Nanos"
echo "==============================================="
echo ""

# Define nodes: NAME:USER@IP
declare -A NODES
NODES=(
    ["GIN"]="gin@192.168.0.242"
    ["ORIN"]="orin@192.168.0.160"
    ["TIF"]="tif@192.168.0.213"
    ["TORI"]="tori@192.168.0.235"
    ["PAGEQA"]="page@192.168.0.168"
    ["ARCHI"]="archi@192.168.0.232"
    ["GUARD"]="guard@192.168.0.146"
)

# USB device label
USB_LABEL="6745-2301"

# Create local WORM package first
echo "📦 Creating WORM package locally..."
TEMP_WORM_DIR="/tmp/orkastrator_worm_deploy"
rm -rf "$TEMP_WORM_DIR"
mkdir -p "$TEMP_WORM_DIR"

cd "$PROJECT_ROOT"

# Run the WORM creator in a lightweight mode (no random filler for faster deployment)
python3 << 'PYTHON_SCRIPT'
import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, '/home/xx/AI-Safety-System-Design')

WORM_DIR = Path("/tmp/orkastrator_worm_deploy/ORKASTRATOR_WORM")
DATA_DIR = WORM_DIR / "data"
TEMPLATES_DIR = DATA_DIR / "compression_templates"
SYSTEM_DIR = DATA_DIR / "system"
ARTIFACTS_DIR = WORM_DIR / "artifacts"

# Create directories
for d in [WORM_DIR, DATA_DIR, TEMPLATES_DIR, SYSTEM_DIR, ARTIFACTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print("📁 Created directory structure")

# Write compression templates
COMPRESSION_TEMPLATES = {
    "common_patterns.json": {
        "version": "1.0",
        "patterns": [
            {"id": "http_req", "pattern": "GET /api/", "freq": 0.85},
            {"id": "http_res", "pattern": '{"status":"success"', "freq": 0.92},
            {"id": "timestamp", "pattern": "2025-", "freq": 0.78},
            {"id": "json_obj", "pattern": '{"', "freq": 0.95},
            {"id": "ai_model", "pattern": "GIN|ORIN|TIF|TORI|PAGEQA|ARCHI|GUARD|ORKA", "freq": 0.88}
        ]
    },
    "dictionary.json": {
        "version": "1.0",
        "words": [
            "proposal", "debate", "consensus", "detection", "deception",
            "agent", "orchestrator", "validator", "penalty", "reputation",
            "claim", "verification", "sandbox", "safety", "alignment",
            "memory", "merkle", "audit", "incident", "threshold"
        ],
        "tokens": {
            "models": ["GIN", "ORIN", "TIF", "TORI", "PAGEQA", "ARCHI", "GUARD", "ORKA"],
            "statuses": ["approved", "rejected", "in_review", "pending"],
            "severities": ["low", "medium", "high", "critical"]
        }
    }
}

for filename, content in COMPRESSION_TEMPLATES.items():
    with open(TEMPLATES_DIR / filename, 'w') as f:
        json.dump(content, f, indent=2)
print("📦 Written compression templates")

# Compute hashes of critical files
def hash_file(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None

PROJECT = Path("/home/xx/AI-Safety-System-Design")
CRITICAL_FILES = {
    "core_values": PROJECT / "config/core_values.json",
    "alignment_filter": PROJECT / "ai_safety/bulletproof_alignment_filter.py",
    "seventh_validator": PROJECT / "ai_safety/seventh_validator.py",
    "deception_detector": PROJECT / "ai_safety/deception_detector.py",
    "worm_usb_verifier": PROJECT / "security/worm_usb_verifier.py",
    "worm_manifest": PROJECT / "security/worm_manifest.py",
    "orchestrator": PROJECT / "core/orchestrator_v2.py",
    "translator": PROJECT / "communication/translator.py",
}

core_hashes = {}
for name, path in CRITICAL_FILES.items():
    h = hash_file(path)
    if h:
        core_hashes[name] = h
        print(f"   ✓ {name}: {h[:16]}...")

# Write core hashes
with open(SYSTEM_DIR / "core_hashes.json", 'w') as f:
    json.dump(core_hashes, f, indent=2)
print("🔐 Written core hashes")

# Copy critical safety files to artifacts
import shutil
for name, path in CRITICAL_FILES.items():
    if path.exists():
        dest = ARTIFACTS_DIR / path.name
        shutil.copy2(path, dest)
print("📄 Copied critical artifacts")

# Write system info
system_info = {
    "system_name": "ORKASTRATOR",
    "version": "0.4.1-dev",
    "created": datetime.now().isoformat(),
    "node_type": "nano_agent",
    "cluster_config": {
        "orchestrator": {"name": "ORKA", "ip": "192.168.0.249", "model": "qwen2.5:14b"},
        "agents": {
            "GIN": {"ip": "192.168.0.242", "model": "deepseek-r1:1.5b", "role": "code_gen"},
            "ORIN": {"ip": "192.168.0.160", "model": "deepseek-r1:1.5b", "role": "nvidia_expert"},
            "TIF": {"ip": "192.168.0.213", "model": "deepseek-r1:1.5b", "role": "technical"},
            "TORI": {"ip": "192.168.0.235", "model": "gemma3:4b", "role": "code_review"},
            "PAGEQA": {"ip": "192.168.0.168", "model": "qwen2.5:3b", "role": "research"},
            "ARCHI": {"ip": "192.168.0.232", "model": "qwen2.5:3b", "role": "architecture"},
            "GUARD": {"ip": "192.168.0.146", "model": "llama-guard3:1b", "role": "safety"},
        }
    }
}
with open(SYSTEM_DIR / "system_info.json", 'w') as f:
    json.dump(system_info, f, indent=2)
print("📋 Written system info")

# Write README
README = """
===============================================
ORKASTRATOR AI Safety System - WORM USB
===============================================

This USB key contains Write-Once-Read-Many (WORM) data
for the ORKASTRATOR AI Safety System nano node cluster.

IMPORTANT: Do NOT modify any files on this drive.
Any modifications will break cryptographic verification.

Contents:
---------
/data/compression_templates/  - AURA compression dictionaries
/data/system/                 - Core system hashes and config
/artifacts/                   - Critical safety system files

Verification:
-------------
The MANIFEST.json contains SHA-256 hashes of all files.
Run verify_worm_integrity.py to verify this drive.

Created: """ + datetime.now().isoformat() + """
Version: 0.4.1-dev
System: ORKASTRATOR
"""
with open(WORM_DIR / "README.txt", 'w') as f:
    f.write(README)
print("📄 Written README")

# Compute all file hashes for manifest
all_hashes = {}
for root, dirs, files in os.walk(WORM_DIR):
    for fn in files:
        if fn == "MANIFEST.json":
            continue
        full = Path(root) / fn
        rel = full.relative_to(WORM_DIR)
        h = hash_file(full)
        if h:
            all_hashes[str(rel)] = h

# Calculate root hash
root_hasher = hashlib.sha256()
for path in sorted(all_hashes.keys()):
    root_hasher.update(path.encode())
    root_hasher.update(b'::')
    root_hasher.update(all_hashes[path].encode())
root_hash = root_hasher.hexdigest()

# Write manifest
manifest = {
    "created": datetime.now().isoformat(),
    "version": "0.4.1-dev",
    "system_name": "ORKASTRATOR",
    "root_hash": root_hash,
    "file_count": len(all_hashes),
    "core_hashes": core_hashes,
    "file_hashes": all_hashes,
}
with open(WORM_DIR / "MANIFEST.json", 'w') as f:
    json.dump(manifest, f, indent=2)

print(f"✅ WORM package created")
print(f"   Root hash: {root_hash[:32]}...")
print(f"   Files: {len(all_hashes)}")
PYTHON_SCRIPT

echo ""
echo "📤 Deploying to each nano node..."
echo ""

# Deploy to each node
for NODE_NAME in "${!NODES[@]}"; do
    NODE_CONN="${NODES[$NODE_NAME]}"
    USER=$(echo "$NODE_CONN" | cut -d@ -f1)
    IP=$(echo "$NODE_CONN" | cut -d@ -f2)
    USB_PATH="/media/$USER/$USB_LABEL"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📡 Deploying to $NODE_NAME ($IP)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check if USB is mounted
    if ! ssh "$NODE_CONN" "test -d '$USB_PATH'" 2>/dev/null; then
        echo "   ❌ USB not mounted at $USB_PATH"
        continue
    fi
    
    # Check available space
    AVAIL=$(ssh "$NODE_CONN" "df '$USB_PATH' --output=avail | tail -1" 2>/dev/null | tr -d ' ')
    echo "   📊 Available space: ${AVAIL}K"
    
    # Clear existing WORM data if present
    echo "   🧹 Clearing existing WORM data..."
    ssh "$NODE_CONN" "rm -rf '$USB_PATH/ORKASTRATOR_WORM'" 2>/dev/null || true
    
    # Copy WORM package
    echo "   📦 Copying WORM package..."
    scp -r /tmp/orkastrator_worm_deploy/ORKASTRATOR_WORM "$NODE_CONN:$USB_PATH/" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        # Make read-only
        echo "   🔒 Setting read-only..."
        ssh "$NODE_CONN" "chmod -R a-w '$USB_PATH/ORKASTRATOR_WORM'" 2>/dev/null
        
        # Verify
        ROOT_HASH=$(ssh "$NODE_CONN" "cat '$USB_PATH/ORKASTRATOR_WORM/MANIFEST.json' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"root_hash\"][:32])'" 2>/dev/null)
        echo "   ✅ Deployed successfully!"
        echo "   🔑 Root hash: ${ROOT_HASH}..."
    else
        echo "   ❌ Failed to copy WORM package"
    fi
    echo ""
done

echo "==============================================="
echo "✨ WORM USB Deployment Complete!"
echo "==============================================="
echo ""
echo "To verify on any node, run:"
echo "  ssh user@node 'cat /media/user/6745-2301/ORKASTRATOR_WORM/MANIFEST.json'"
echo ""
