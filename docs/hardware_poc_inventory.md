# Proof-of-Concept Hardware Inventory

Working inventory for the proof-of-concept (POC) lab. Treat this document as the authoritative ledger for what exists, where it lives, and what still needs attention.

## Equipment Summary

| Item | Qty | Role in POC | Current Status | Notes |
| --- | --- | --- | --- | --- |
| NVIDIA “Super Nano” developer boards (Jetson form factor, 8 GB RAM) | 6 | Distributed accelerator swarm for sandbox + translator workloads | Awaiting shipment ETA | Confirm carrier insurance; PoE splitters required if lab power bricks are constrained |
| HP Z6 workstation (24-core Xeon Gold + NVIDIA 5060 Ti 16 GB) | 1 | Orchestrator host, model compilation, heavy simulation runs | On-site, burn-in scheduled | Install dual NVMe mirror before staging sensitive data |
| 2.5 GbE managed switch (8-port) | 1 | Low-latency backplane between workstation and Jetsons | Received, pending rack mount | Label ports 1-6 (Jetsons), 7 (workstation), 8 (uplink); interconnect with 1 ft Cat8 patch cables |
| ESP32-S3 + 7" touch display kit | 1 | Human-in-the-loop translator UI and safety interlock prototyping | In transit | Needs 5V/3A PSU and resin enclosure before lab use |
| Read-only USB media (macOS-certified WORM) | 2 | Immutable audit bundles + deployment manifests | Received, sealing hash outstanding | Store in fireproof safe; log SHA-256 + custody chain |

## Receiving & Provisioning Checklist

1. **Receiving log** – Capture delivery date, carrier, condition, and tamper indicators. Photograph packaging for audit evidence.
2. **Serial capture** – Record serials/MACs (and TPM/secure-element IDs if present) in the table below.
3. **Power-on verification** – Complete POST/power checks within 24 hours to keep the RMA window open.
4. **Firmware baseline** – Document firmware/BIOS versions prior to any updates. Prefer write-protected images when available.
5. **Provisioning** – Apply hardened OS images, install monitoring agents, and register assets in the CMDB after burn-in passes. Use the new `docs/hp_z6_ubuntu_autoinstall.yaml` profile for the HP Z6 node so the mirrored NVMe + baseline packages are installed consistently.
6. **Custody update** – Note the responsible engineer and storage location. Transfers require dual-signature acknowledgment.

## Serial / Asset Log

| Item | Serial / MAC | Secure Element ID | Received By | Date | Notes |
| --- | --- | --- | --- | --- | --- |
| Super Nano #1 | | | | | |
| Super Nano #2 | | | | | |
| Super Nano #3 | | | | | |
| Super Nano #4 | | | | | |
| Super Nano #5 | | | | | |
| Super Nano #6 | | | | | |
| HP Z6 Workstation | | | | | |
| 2.5 GbE Switch | | | | | |
| ESP32-S3 Kit | | | | | |
| WORM USB #1 | | | | | |
| WORM USB #2 | | | | | |

> Tip: Export this table to PDF and attach it to the physical custody paperwork so auditors can trace asset lineage without needing repository access.

## macOS Manual Imaging Procedure

When preparing the seven 1 GB WORM USB drives, perform the process manually (no automation scripts) so every destructive action is double-checked:

1. `diskutil list` → identify the removable disk (e.g., `/dev/disk4`). Triple-verify size before proceeding.
2. `diskutil unmountDisk /dev/disk4` to ensure nothing is mounted.
3. `diskutil eraseDisk FAT32 WORMKEY01 MBRFormat /dev/disk4`
4. Copy payload: `rsync -a --delete ./worm_usb_dir/ /Volumes/WORMKEY01/`
5. Create manifest: `(cd /Volumes/WORMKEY01 && find . -type f -print0 | sort -z | xargs -0 shasum -a 256 > manifest.sha256)`
6. Fill remaining space so the volume is write-blocked by capacity:  
   ```
   df -k /Volumes/WORMKEY01
   # note Available column (K). subtract 4 KB as buffer, use that value below
   dd if=/dev/zero of=/Volumes/WORMKEY01/.worm_filler.bin bs=1024 count=<available minus 4>
   ```
7. `sync` then optionally compute whole-device hash: `shasum -a 256 /dev/rdisk4 > device.sha256`
8. `diskutil unmount /Volumes/WORMKEY01 && diskutil eject /dev/disk4`
9. Record serial, manifest hash, device hash, operator initials, and store the USB in tamper-evident packaging.

All commands must be run while watching the terminal; stop immediately if output deviates from plan. Destructive steps (erase/fill) require a second engineer to observe per lab policy.

## Outstanding Actions

- Confirm arrival dates for the ESP32 kit and Super Nanos; attach shipping numbers once procurement publishes them.
- Order PoE-capable injectors or wall adapters if the managed switch cannot supply enough power budget.
- Schedule a 48-hour burn-in for the workstation and document thermal readings before installing orchestration software.
- Generate initial WORM manifest hashes and store them alongside the USB serial entries above.

Keep this document synchronized with shipping manifests and procurement tickets. Every update should be referenced in the audit log to maintain a clean hardware provenance trail.
