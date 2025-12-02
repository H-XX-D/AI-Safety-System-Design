"""
Utilities for building WORM-style USB audit packages.

This module is purposely lightweight so the test suite can exercise the core
behaviour without needing the actual hardware workflow.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.memory_storage import MemoryStorage, MemoryType


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize_timestamp(value: str) -> str:
    return value.replace(":", "-").replace(" ", "_")


@dataclass
class AuditPackage:
    timestamp: str
    merkle_roots: Dict[str, Optional[str]]
    proposals: List[Dict[str, Any]]
    human_decisions: List[Dict[str, Any]]
    safety_incidents: List[Dict[str, Any]]
    metadata: Dict[str, Any]


@dataclass
class WORMManifest:
    created: str
    audit_dir: str
    total_files: int
    total_size_bytes: int
    filler_size_bytes: int
    file_hashes: Dict[str, str]
    root_hash: str
    read_only_verified: bool


class WORMUSBBuilder:
    SYSTEM_PATH_PREFIXES = ("/usr", "/System")

    def __init__(self, usb_path: str) -> None:
        path = Path(usb_path)
        if not path.exists():
            raise ValueError(f"USB path {usb_path} does not exist")
        if not path.is_dir():
            raise ValueError("USB path must be a directory")
        if any(str(path).startswith(prefix) for prefix in self.SYSTEM_PATH_PREFIXES):
            raise ValueError("Refusing to operate on system directory")
        self.usb_path = path

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------
    def collect_audit_data(self, storage: MemoryStorage) -> AuditPackage:
        timestamp = datetime.now().isoformat()
        merkle_roots: Dict[str, Optional[str]] = {}
        if hasattr(storage, "trees"):
            for mtype, tree in storage.trees.items():
                merkle_roots[mtype.value] = tree.get_root_hash()
        proposals = self._extract_proposals(storage)
        decisions = self._extract_decisions(storage)
        incidents = self._extract_incidents(storage)
        metadata = {
            "collection_timestamp": timestamp,
            "total_proposals": len(proposals),
            "total_decisions": len(decisions),
            "total_incidents": len(incidents),
            "merkle_roots_count": len(merkle_roots),
        }
        return AuditPackage(
            timestamp=timestamp,
            merkle_roots=merkle_roots,
            proposals=proposals,
            human_decisions=decisions,
            safety_incidents=incidents,
            metadata=metadata,
        )

    def _extract_proposals(self, storage: MemoryStorage) -> List[Dict[str, Any]]:
        if hasattr(storage, "memories"):
            episodic = storage.memories.get(MemoryType.EPISODIC, [])
            return [dict(item) for item in episodic]
        return []

    def _extract_decisions(self, storage: MemoryStorage) -> List[Dict[str, Any]]:
        if hasattr(storage, "human_decisions"):
            decisions = storage.human_decisions
            if isinstance(decisions, dict):
                return [dict(v) for v in decisions.values()]
            return [dict(v) for v in decisions]
        return []

    def _extract_incidents(self, storage: MemoryStorage) -> List[Dict[str, Any]]:
        if hasattr(storage, "safety_incidents"):
            return [dict(v) for v in storage.safety_incidents]
        return []

    # ------------------------------------------------------------------
    # Audit package handling
    # ------------------------------------------------------------------
    def write_audit_package(self, package: AuditPackage) -> Path:
        folder_name = f"audit_{_sanitize_timestamp(package.timestamp)}"
        audit_dir = self.usb_path / folder_name
        _ensure_dir(audit_dir)

        payloads = {
            "audit_package.json": asdict(package),
            "merkle_roots.json": package.merkle_roots,
            "proposals.json": package.proposals,
            "human_decisions.json": package.human_decisions,
            "safety_incidents.json": package.safety_incidents,
            "metadata.json": package.metadata,
        }
        for name, data in payloads.items():
            with open(audit_dir / name, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, default=str)

        readme = (
            "AI Safety System Audit Package (WORM Snapshot)\n"
            "================================\n\n"
            f"Collection Timestamp: {package.timestamp}\n"
            f"Total Proposals: {package.metadata['total_proposals']}\n"
            f"Total Decisions: {package.metadata['total_decisions']}\n"
            f"Total Incidents: {package.metadata['total_incidents']}\n"
            f"Merkle Roots: {package.metadata['merkle_roots_count']}\n"
            f"USB Path: {self.usb_path}\n"
        )
        with open(audit_dir / "README.txt", "w", encoding="utf-8") as handle:
            handle.write(readme)

        return audit_dir

    def make_read_only(self, path: Path) -> None:
        if not path.exists():
            return
        for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if item.is_file():
                item.chmod(0o444)
            elif item.is_dir():
                item.chmod(0o555)
        if path.is_dir():
            path.chmod(0o555)

    def make_read_write(self, path: Path) -> None:
        for item in path.rglob("*"):
            if item.is_file():
                item.chmod(0o644)
            elif item.is_dir():
                item.chmod(0o755)
        if path.is_dir():
            path.chmod(0o755)

    def verify_immutability(self, path: Path) -> bool:
        if not path.exists():
            return False
        for item in path.rglob("*"):
            mode = item.stat().st_mode & 0o777
            if item.is_file() and mode != 0o444:
                return False
            if item.is_dir() and mode != 0o555:
                return False
        mode = path.stat().st_mode & 0o777
        return mode == 0o555

    # ------------------------------------------------------------------
    # Filler + space operations
    # ------------------------------------------------------------------
    def fill_remaining_space(self, chunk_size: int = 10 * 1024 * 1024) -> int:
        filler_dir = self.usb_path / ".worm_filler"
        _ensure_dir(filler_dir)
        idx = len(list(filler_dir.glob("filler_*.bin")))
        filler_path = filler_dir / f"filler_{idx:04d}.bin"
        with open(filler_path, "wb") as handle:
            handle.write(b"\0" * chunk_size)
        filler_path.chmod(0o444)
        return chunk_size

    def get_free_space(self) -> int:
        usage = shutil.disk_usage(self.usb_path)
        return usage.free

    # ------------------------------------------------------------------
    # Manifest + drive creation
    # ------------------------------------------------------------------
    def create_manifest(self, audit_dir: Path, filler_bytes: int = 0) -> WORMManifest:
        hashes = self._compute_file_hashes(audit_dir)
        root_hash = self._calculate_root_hash(hashes)
        total_size = sum((audit_dir / rel).stat().st_size for rel in hashes)
        manifest = WORMManifest(
            created=datetime.now().isoformat(),
            audit_dir=str(audit_dir),
            total_files=len(hashes),
            total_size_bytes=total_size,
            filler_size_bytes=filler_bytes,
            file_hashes=hashes,
            root_hash=root_hash,
            read_only_verified=self.verify_immutability(audit_dir),
        )
        manifest_path = audit_dir / "WORM_MANIFEST.json"
        reset_permissions = False
        if not os.access(audit_dir, os.W_OK):
            self.make_read_write(audit_dir)
            reset_permissions = True
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(asdict(manifest), handle, indent=2)
        manifest_path.chmod(0o444)
        if reset_permissions:
            self.make_read_only(audit_dir)
        return manifest

    def _compute_file_hashes(self, audit_dir: Path) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        for file in sorted(audit_dir.rglob("*")):
            if file.is_file():
                rel = str(file.relative_to(audit_dir))
                hashes[rel] = self._hash_file(file)
        return hashes

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _calculate_root_hash(hashes: Dict[str, str]) -> str:
        digest = hashlib.sha256()
        for rel, value in sorted(hashes.items()):
            digest.update(rel.encode())
            digest.update(value.encode())
        return digest.hexdigest()

    def create_worm_drive(
        self,
        storage: MemoryStorage,
        *,
        fill_space: bool = False,
        filler_chunk_size: int = 4 * 1024 * 1024,
    ) -> Path:
        package = self.collect_audit_data(storage)
        audit_dir = self.write_audit_package(package)
        self.make_read_only(audit_dir)
        filler_bytes = self.fill_remaining_space(chunk_size=filler_chunk_size) if fill_space else 0
        self.create_manifest(audit_dir, filler_bytes=filler_bytes)
        return audit_dir

    # ------------------------------------------------------------------
    # USB info
    # ------------------------------------------------------------------
    def get_usb_info(self) -> Dict[str, Any]:
        total, used, free = shutil.disk_usage(self.usb_path)
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        info = {
            "path": str(self.usb_path),
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "hardware_info": platform.platform(),
        }
        return info
