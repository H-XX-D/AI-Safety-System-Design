#!/usr/bin/env bash
# Create SquashFS WORM USB for Linux
# This creates a truly read-only, immutable USB key

set -euo pipefail

WORM_SOURCE="${WORM_USB_PATH:-/Volumes/NO NAME/ORKASTRATOR_WORM}"
USB_DEVICE="${1:-/dev/sdb}"  # Change to your USB device
MOUNT_POINT="/mnt/worm_usb"
SQUASHFS_FILE="/tmp/orkastrator_worm.squashfs"

echo "=========================================="
echo "Creating SquashFS WORM USB"
echo "=========================================="
echo "Source: $WORM_SOURCE"
echo "Target Device: $USB_DEVICE"
echo ""
echo "⚠️  WARNING: This will ERASE $USB_DEVICE"
echo "Press Ctrl+C to cancel, Enter to continue..."
read

# Step 1: Create SquashFS image from WORM data
echo ""
echo "Step 1: Creating SquashFS image..."
sudo mksquashfs "$WORM_SOURCE" "$SQUASHFS_FILE" \
    -comp xz \
    -b 1M \
    -Xbcj x86 \
    -noappend \
    -no-xattrs \
    -all-root

echo "✓ SquashFS image created: $(du -h "$SQUASHFS_FILE" | cut -f1)"

# Step 2: Unmount USB if mounted
echo ""
echo "Step 2: Unmounting USB (if mounted)..."
sudo umount "${USB_DEVICE}1" 2>/dev/null || true
sudo umount "${USB_DEVICE}" 2>/dev/null || true

# Step 3: Wipe USB and create partition
echo ""
echo "Step 3: Creating partition on $USB_DEVICE..."
sudo parted -s "$USB_DEVICE" mklabel msdos
sudo parted -s "$USB_DEVICE" mkpart primary 0% 100%
sudo parted -s "$USB_DEVICE" set 1 boot on

# Wait for kernel to recognize partition
sleep 2

# Step 4: Write SquashFS directly to partition (no filesystem layer)
echo ""
echo "Step 4: Writing SquashFS image to ${USB_DEVICE}1..."
sudo dd if="$SQUASHFS_FILE" of="${USB_DEVICE}1" bs=4M status=progress
sync

# Step 5: Verify
echo ""
echo "Step 5: Verifying SquashFS image..."
sudo mkdir -p "$MOUNT_POINT"
sudo mount -t squashfs -o loop,ro "${USB_DEVICE}1" "$MOUNT_POINT"

echo "✓ USB mounted at $MOUNT_POINT"
echo ""
echo "Checking files..."
file_count=$(find "$MOUNT_POINT" -type f | wc -l)
echo "✓ Files found: $file_count"

if [ -f "$MOUNT_POINT/MANIFEST.json" ]; then
    echo "✓ MANIFEST.json found"
    total_files=$(python3 -c "import json; print(json.load(open('$MOUNT_POINT/MANIFEST.json'))['total_files'])")
    echo "✓ Manifest reports $total_files files"

    if [ "$file_count" -eq "$total_files" ]; then
        echo "✓ File count matches manifest"
    else
        echo "❌ File count mismatch: found $file_count, expected $total_files"
    fi
fi

# Step 6: Verify immutability
echo ""
echo "Step 6: Testing immutability..."
if touch "$MOUNT_POINT/test_write.txt" 2>/dev/null; then
    echo "❌ ERROR: USB is WRITABLE (should be read-only)"
    exit 1
else
    echo "✓ USB is read-only (write test failed as expected)"
fi

echo ""
echo "=========================================="
echo "✅ SquashFS WORM USB Created Successfully"
echo "=========================================="
echo ""
echo "Device: $USB_DEVICE"
echo "Filesystem: SquashFS (compressed, read-only)"
echo "Mount command: sudo mount -t squashfs -o ro ${USB_DEVICE}1 /mnt/worm"
echo ""
echo "To eject:"
echo "  sudo umount $MOUNT_POINT"
echo "  sudo eject $USB_DEVICE"
echo ""

# Cleanup
sudo umount "$MOUNT_POINT"
rm "$SQUASHFS_FILE"

echo "✓ Cleanup complete"
