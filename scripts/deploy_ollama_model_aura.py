#!/usr/bin/env python3
"""Smart deploy: use zstd for model tarball transfer + AURA-compressed metadata.

This script is a safer, more efficient alternative to the existing
`deploy_ollama_model.sh` for deploying large models (GGUF/safetensors).

Workflow:
  - Create a tarball of the model directory and compress with zstd (if available)
  - Generate metadata (file list, sizes, sha256) and compress with AURA
  - Transfer the tar.zst and metadata.aura to remote host via scp/rsync
  - On remote host try to extract tar.zst (uses zstd/tar). If that fails we
    fall back to rsync-the-directory

Usage:
  python3 scripts/deploy_ollama_model_aura.py --hosts "user@host" --model-path /abs/path --model-name HELVETE-3B --key ~/.ssh/id_ed25519 --dry-run
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

try:
    # Use the repo's AURA helper (ML selection disabled wrapper)
    from communication.aura_compressor import create_compressor
except Exception:
    create_compressor = None


def sh(cmd: List[str], dry_run: bool = False, capture: bool = False, timeout: int = 60) -> subprocess.CompletedProcess:
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")
    return subprocess.run(cmd, capture_output=capture, timeout=timeout, check=False)


def find_exe(name: str) -> bool:
    return shutil.which(name) is not None


def calc_dir_metadata(path: Path) -> dict:
    files = []
    total = 0
    for root, _, filenames in os.walk(path):
        for fn in filenames:
            fp = Path(root) / fn
            try:
                size = fp.stat().st_size
                total += size
                h = hashlib.sha256()
                with fp.open('rb') as fh:
                    while True:
                        chunk = fh.read(8192)
                        if not chunk:
                            break
                        h.update(chunk)
                files.append({"path": str(fp.relative_to(path)), "size": size, "sha256": h.hexdigest()})
            except Exception as e:
                files.append({"path": str(fp.relative_to(path)), "size": None, "sha256": None, "error": str(e)})
    return {"model": path.name, "total_bytes": total, "file_count": len(files), "files": files}


def make_tar_zstd(src: Path, dst: Path, level: int = 19, threads: int = 0, dry_run: bool = False) -> Tuple[bool, str]:
    """NO-OP helper preserved for compatibility.

    Per policy: do NOT compress model weights using external tar/zstd.
    This function intentionally does nothing and signals that tarballing
    is disabled so caller falls back to rsync directory copy.
    """
    return False, "external compression disabled"


def compress_metadata_aura(metadata: dict):
    text = json.dumps(metadata, indent=2)
    if create_compressor is None:
        return text.encode('utf-8'), {'method': 'RAW'}

    comp = create_compressor()
    payload, method, meta = comp.compress(text)
    # Ensure metadata includes method name for remote auditing
    meta = dict(meta)
    meta['method'] = method.name if hasattr(method, 'name') else str(method)
    return payload, meta


def deploy_to_host(target: str, model_src: Path, model_name: str, key: str | None, dry_run=False, no_restart=False):
    user_at_host = target
    remote_model_dir = f"~/.ollama/models/{model_name}"

    # Prepare tar.zst
    tmp_dir = Path(tempfile.mkdtemp(prefix='deploy_model_'))
    tar_dest = tmp_dir / f"{model_name}.tar.zst"

    ok, reason = make_tar_zstd(model_src, tar_dest, dry_run=dry_run)
    if not ok:
        print(f"Warning: creating tar.zst failed ({reason}) — will fallback to rsync directory copy")

    # Metadata
    meta = calc_dir_metadata(model_src)
    aura_payload, aura_meta = compress_metadata_aura(meta)
    aura_b64 = base64.b64encode(aura_payload).decode('ascii')

    # Transfer tarball first (if exists)
    if tar_dest.exists() and not dry_run:
        print(f"Copying tarball to {user_at_host}:/tmp/")
        scp_cmd = ['scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null']
        if key:
            scp_cmd += ['-i', key]
        scp_cmd += [str(tar_dest), f"{user_at_host}:/tmp/{tar_dest.name}"]
        res = sh(scp_cmd, dry_run=dry_run, capture=True)
        if res.returncode != 0:
            print("Tarball scp failed, falling back to rsync directory copy")
            tar_exists_remote = False
        else:
            tar_exists_remote = True
    else:
        tar_exists_remote = False

    # Place metadata (AURA) on remote
    meta_remote = f"{remote_model_dir}/{model_name}.metadata.aura"
    meta_cmd = (
        f"echo '{aura_b64}' | base64 -d > {meta_remote} && echo '{json.dumps(aura_meta)}' > {remote_model_dir}/{model_name}.metadata.aura.meta.json"
    )
    ssh_prefix = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null']
    if key:
        ssh_prefix.insert(1, '-i'); ssh_prefix.insert(2, key)

    # Ensure remote model dir
    run_dir_cmd = ssh_prefix + [user_at_host, f"mkdir -p {remote_model_dir}"]
    sh(run_dir_cmd, dry_run=dry_run)

    # Put metadata
    run_meta_cmd = ssh_prefix + [user_at_host, meta_cmd]
    sh(run_meta_cmd, dry_run=dry_run)

    # If tar exists remote — try to extract it using zstd+tar
    extracted = False
    if tar_exists_remote:
        extract_cmd = f"mkdir -p {remote_model_dir} && tar -I zstd -xf /tmp/{tar_dest.name} -C {remote_model_dir} || (zstd -d /tmp/{tar_dest.name} -c | tar -xf - -C {remote_model_dir})"
        res = sh(ssh_prefix + [user_at_host, extract_cmd], dry_run=dry_run, capture=True)
        if res.returncode == 0:
            extracted = True
            print(f"Extracted tar.zst on {user_at_host}")
        else:
            print(f"Remote extract failed on {user_at_host}. Falling back to rsync directory copy")

    # If extraction didn't happen, fallback to rsync directory copy
    if not extracted:
        # Intentionally DO NOT use rsync -z for model transfers — models/weights are not compressed.
        rsync_base = ['rsync', '-a', '--delete', '-e', ' '.join(["ssh", "-o StrictHostKeyChecking=no", "-o UserKnownHostsFile=/dev/null"])]
        if key:
            rsync_base[-1] = f"ssh -i {key} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        rsync_cmd = rsync_base + [str(model_src.resolve()) + '/', f"{user_at_host}:{remote_model_dir}/"]
        res = sh(rsync_cmd, dry_run=dry_run, capture=True)
        if res.returncode != 0:
            print(f"ERROR: rsync failed to {user_at_host}: {res.stderr.decode(errors='ignore')}")
            return False

    # Optionally restart Ollama
    if not no_restart:
        restart_cmd = ssh_prefix + [user_at_host, "if command -v systemctl >/dev/null 2>&1; then sudo -n systemctl restart ollama 2>/dev/null || true; fi"]
        sh(restart_cmd, dry_run=dry_run)

    # Validate with 'ollama list' if available
    validate_cmd = ssh_prefix + [user_at_host, "ollama list || true"]
    sh(validate_cmd, dry_run=dry_run, capture=True)

    return True


def main():
    parser = argparse.ArgumentParser(description="Deploy model dir with zstd + AURA metadata")
    parser.add_argument('--hosts', required=True, help='Space separated user@host targets')
    parser.add_argument('--model-path', required=True, help='Absolute path to local model directory')
    parser.add_argument('--model-name', required=True, help='Target model name under ~/.ollama/models')
    parser.add_argument('--key', default=None, help='SSH private key')
    parser.add_argument('--no-restart', action='store_true', help='Do not restart ollama service on remote host')
    parser.add_argument('--dry-run', action='store_true', help='Print actions but do not execute')

    args = parser.parse_args()

    hosts = args.hosts.split()
    model_path = Path(args.model_path)
    if not model_path.exists() or not model_path.is_dir():
        print(f"Model path not found: {model_path}")
        sys.exit(1)

    success_hosts = []
    failed_hosts = []

    for h in hosts:
        print(f"--- Deploy to {h} ---")
        ok = deploy_to_host(h, model_path, args.model_name, args.key, dry_run=args.dry_run, no_restart=args.no_restart)
        if ok:
            success_hosts.append(h)
        else:
            failed_hosts.append(h)

    print("\nDeployment summary:")
    print("  Success:", success_hosts)
    print("  Failed:", failed_hosts)


if __name__ == '__main__':
    main()
