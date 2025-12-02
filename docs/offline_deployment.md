Offline Deployment & Certified USB Bundle
========================================

Goal
----
Enable provisioning in fully air‑gapped environments: all Python packages, integrity manifests, and source code supplied via a certified USB stick. The target system installs without contacting external networks, and operators can independently verify contents.

High‑Level Steps
----------------
1. Prepare staging machine (online) with clean virtualenv.
2. Download all required wheels (incl. AURA compressor) into a folder named offline_bundle/.
3. Generate a manifest (offline_manifest.json) with SHA256 + file size + package name.
4. (Optional) Sign manifest (offline_manifest.sig) using HMAC or PGP.
5. Copy repository + offline_bundle/ + manifest (+ signature) to certified USB.
6. On air‑gapped system verify manifest hashes, then install from local bundle.

Bundle Creation Commands (Staging)
----------------------------------
1) Create virtualenv and upgrade pip
2) pip download -r requirements.txt -d offline_bundle
3) pip download aura-compression==<PINNED_VERSION> -d offline_bundle
4) python offline_bundle.py generate offline_bundle offline_manifest.json
5) python offline_bundle.py sign offline_manifest.json offline_manifest.sig --secret $HUMAN_SIGNING_SECRET

Verification & Install (Air‑Gapped)
-----------------------------------
1) python3 offline_bundle.py verify offline_bundle offline_manifest.json
2) python3 offline_bundle.py verify-signature offline_manifest.json offline_manifest.sig --secret $HUMAN_SIGNING_SECRET
3) pip install --no-index --find-links offline_bundle -r requirements.txt aura-compression==<PINNED_VERSION>

Manifest Format (offline_manifest.json)
---------------------------------------
Fields: created (ISO8601), packages (list of objects with filename, sha256, size_bytes, name)

Security Considerations
-----------------------
* Reproducibility: pin exact versions (including AURA) in requirements or a lock file.
* Integrity: SHA256 over wheel bytes validated before install.
* Authenticity: Optional signature; rotate secret or migrate to PGP public key model.
* Audit Trail: Anchor manifest hash in Merkle memory for immutable trace.

Post‑Training Distribution (Compression Artifacts)
-------------------------------------------------
To keep WORM minimal and stable, we do not store compression library baselines or templates there.
Instead, distribute the vetted compression wheels and templates via the project website alongside
the deception database snapshots. Bundle these into the certified USB for air‑gapped installs.
This aligns provenance with regular releases while keeping WORM focused on fundamentals only.

Recommended Pins
----------------
Add AURA to requirements.txt with explicit version, e.g.: aura-compression==1.2.3
Then re-run the download + manifest generation.

Anchoring Manifest
------------------
After verifying manifest on target system, compute SHA256 of offline_manifest.json and store in MemoryStorage under METACOGNITIVE to create a tamper-evident audit entry.

Multi‑Sig Extension (Future)
----------------------------
Provide multiple human signatures over the same manifest file; store an array of signature objects in offline_manifest_multisig.json.

Graceful Failure Mode
---------------------
If any wheel fails hash verification: abort installation, log offending filename, and require new USB bundle.

See Also
--------
offline_bundle.py (manifest tooling)
human_review.py (HMAC signing mechanics)
orchestrator.py (trust layer config gating / anchoring)
worm_manifest.py (note re: no compression baselines in WORM)
