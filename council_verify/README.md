# Council Offline Verifier

This folder contains a single-entry verification script intended for an offline (air-gapped) council machine.

## What it verifies
- WORM source/spec artifacts: Hash manifest integrity and HMAC signature
- Offline package bundle: Hash manifest integrity and HMAC signature

## Requirements
- Python 3 available on the offline machine
- The following files/directories copied from the USB:
  - `worm_usb_dir/` with `manifest.json` and `manifest.sig` (and optionally `files/` if materialized)
  - `offline_bundle/` with packages
  - `offline_manifest.json` and `offline_manifest.sig`
  - `worm_usb_builder.py` and `offline_bundle.py` (placed in the same directory as this script or on `PYTHONPATH`)

## Usage

```bash
python verify_all.py \
  --worm-dir worm_usb_dir \
  --worm-manifest worm_usb_dir/manifest.json \
  --worm-sig worm_usb_dir/manifest.sig \
  --offline-dir offline_bundle \
  --offline-manifest offline_manifest.json \
  --offline-sig offline_manifest.sig \
  --secret "$WORM_SECRET"
```

The script prints a PASS/FAIL summary for both hash verification and signature verification.

Notes:
- HMAC-based signatures are intended for test and lab scenarios. For production, use asymmetric signatures managed by the council.
- If the WORM manifest was generated with `--materialize`, all files needed for verification are under `worm_usb_dir/files/`.
