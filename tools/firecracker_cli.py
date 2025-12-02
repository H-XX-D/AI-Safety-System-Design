#!/usr/bin/env python3
"""
Utility CLI for downloading and staging Firecracker + jailer binaries and demo
kernel/rootfs artifacts. Intended as a convenience wrapper so contributors
don't have to manually copy/paste curl commands.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import textwrap
import urllib.request
from pathlib import Path
from typing import Tuple

DEFAULT_VERSION = "v1.7.0"
DEFAULT_KERNEL_URL = "https://s3.amazonaws.com/spec.ccfc.min/img/firecracker/kernel/vmlinux-5.10.225"
DEFAULT_ROOTFS_URL = "https://s3.amazonaws.com/spec.ccfc.min/img/firecracker/rootfs/bionic.rootfs.ext4"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, open(dest, "wb") as handle:
        chunk = response.read(8192)
        while chunk:
            handle.write(chunk)
            chunk = response.read(8192)


def _mark_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def download_binaries(version: str, bin_dir: Path) -> Tuple[Path, Path]:
    base_url = f"https://github.com/firecracker-microvm/firecracker/releases/download/{version}"
    firecracker_path = bin_dir / f"firecracker-{version}"
    jailer_path = bin_dir / f"jailer-{version}"

    print(f"Downloading Firecracker {version} -> {firecracker_path}")
    _download(f"{base_url}/firecracker-{version}", firecracker_path)
    print(f"Downloading jailer {version} -> {jailer_path}")
    _download(f"{base_url}/jailer-{version}", jailer_path)

    _mark_executable(firecracker_path)
    _mark_executable(jailer_path)
    return firecracker_path, jailer_path


def download_artifacts(kernel_url: str, rootfs_url: str, artifact_dir: Path) -> Tuple[Path, Path]:
    kernel_path = artifact_dir / Path(kernel_url).name
    rootfs_path = artifact_dir / Path(rootfs_url).name

    print(f"Downloading kernel -> {kernel_path}")
    _download(kernel_url, kernel_path)
    print(f"Downloading rootfs -> {rootfs_path}")
    _download(rootfs_url, rootfs_path)
    return kernel_path, rootfs_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Firecracker binaries + demo kernel/rootfs artifacts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Firecracker release tag")
    parser.add_argument(
        "--bin-dir",
        default="firecracker/bin",
        type=Path,
        help="Directory to place firecracker and jailer binaries",
    )
    parser.add_argument(
        "--artifact-dir",
        default="firecracker/artifacts",
        type=Path,
        help="Directory to place kernel/rootfs artifacts",
    )
    parser.add_argument("--kernel-url", default=DEFAULT_KERNEL_URL, help="Kernel image URL")
    parser.add_argument("--rootfs-url", default=DEFAULT_ROOTFS_URL, help="Rootfs image URL")
    parser.add_argument(
        "--skip-artifacts",
        action="store_true",
        help="Skip kernel/rootfs download (only binaries will be fetched)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if sys.platform != "linux":
        print("WARNING: Firecracker only runs on Linux with KVM; downloads will continue, but execution will fail on this platform.", file=sys.stderr)

    bin_dir: Path = args.bin_dir
    artifact_dir: Path = args.artifact_dir

    bin_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    firecracker_path, jailer_path = download_binaries(args.version, bin_dir)
    kernel_path = rootfs_path = None
    if not args.skip_artifacts:
        kernel_path, rootfs_path = download_artifacts(args.kernel_url, args.rootfs_url, artifact_dir)

    summary = textwrap.dedent(
        f"""
        Firecracker bundle ready.

        Firecracker binary : {firecracker_path}
        Jailer binary      : {jailer_path}
        Kernel image       : {kernel_path or '(skipped)'}
        Rootfs image       : {rootfs_path or '(skipped)'}

        Next steps:
          1. Copy binaries into your PATH (e.g., sudo cp {firecracker_path} /usr/local/bin/firecracker)
          2. Set executable bits if needed (already applied, but double-check after copying)
          3. Update config/default.yaml sandbox.firecracker_kernel / sandbox.firecracker_rootfs
          4. Ensure your user is in the 'kvm' group: sudo usermod -aG kvm $USER
          5. Run the orchestrator with sandbox.engine=firecracker to verify.
        """
    ).strip()
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
