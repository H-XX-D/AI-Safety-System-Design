#!/usr/bin/env bash
set -euo pipefail
# Auto-mount WORM USB for ORKA system
# Works with SquashFS or ISO 9660

MOUNT_POINT="/mnt/orkastrator_worm"
USB_DEVICE="${1:-/dev/sdb1}"

echo "Mounting WORM USB..."

# Create mount point
sudo mkdir -p "$MOUNT_POINT"

# Detect filesystem type
FS_TYPE=$(sudo blkid -o value -s TYPE "$USB_DEVICE" 2>/dev/null)

if [ -z "$FS_TYPE" ]; then
    # Try to detect SquashFS magic bytes
    if sudo dd if="$USB_DEVICE" bs=4 count=1 2>/dev/null | grep -q "hsqs"; then
        FS_TYPE="squashfs"
    fi
fi

echo "Detected filesystem: ${FS_TYPE:-unknown}"

# Mount read-only
case "$FS_TYPE" in
    squashfs)
        sudo mount -t squashfs -o ro "$USB_DEVICE" "$MOUNT_POINT"
        ;;
    iso9660)
        sudo mount -t iso9660 -o ro "$USB_DEVICE" "$MOUNT_POINT"
        ;;
    ext4)
        sudo mount -o ro "$USB_DEVICE" "$MOUNT_POINT"
        ;;
    erofs)
        sudo mount -t erofs "$USB_DEVICE" "$MOUNT_POINT"
        ;;
    *)
        echo "Error: Unsupported filesystem type: $FS_TYPE"
        exit 1
        ;;
esac

# Verify mount
if mountpoint -q "$MOUNT_POINT"; then
    echo "✓ WORM USB mounted at $MOUNT_POINT"

    # Verify immutability
    if touch "$MOUNT_POINT/test_write.txt" 2>/dev/null; then
        echo "❌ WARNING: USB is writable (should be read-only)"
        sudo umount "$MOUNT_POINT"
        exit 1
    else
        echo "✓ USB is read-only (verified)"
    fi

    # Add to Python path
    export PYTHONPATH="$MOUNT_POINT/programs:$PYTHONPATH"
    echo "✓ Added to PYTHONPATH: $MOUNT_POINT/programs"

    # Verify WORM manifest
    if [ -f "$MOUNT_POINT/programs/3bc169ec_worm_manifest.py" ]; then
        echo "✓ WORM manifest found"
    else
        echo "❌ ERROR: WORM manifest not found"
        sudo umount "$MOUNT_POINT"
        exit 1
    fi

    echo ""
    echo "WORM USB ready for ORKA system"
    echo "Import with: sys.path.insert(0, '$MOUNT_POINT/programs')"
else
    echo "❌ Failed to mount USB"
    exit 1
fi
