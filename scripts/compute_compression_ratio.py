#!/usr/bin/env python3
"""
Compute compression ratios across saved run artifacts.

Scans one or more directories (default: data/improvements) for text files,
compresses their contents with the AURA classifier, and reports per-method
and overall ratios. Useful for validating real-world effectiveness on Orin.
"""

import argparse
import pathlib
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

# Add repo root to import path for local modules
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def find_text_files(paths: Iterable[pathlib.Path], suffixes: Tuple[str, ...]) -> List[pathlib.Path]:
    """Recursively find candidate text files under the provided paths."""
    files: List[pathlib.Path] = []
    for base in paths:
        if not base.exists():
            continue
        if base.is_file():
            if base.suffix.lower() in suffixes:
                files.append(base)
            continue
        files.extend(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in suffixes)
    return files


def load_text(path: pathlib.Path) -> str:
    """Load text with a forgiving decoder to avoid aborting on bad files."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def compute_ratios(file_paths: List[pathlib.Path]) -> Dict[str, Dict[str, float]]:
    """Compress files and accumulate stats."""
    try:
        from communication.aura_compressor import classify_and_compress  # type: ignore
    except Exception as exc:  # pragma: no cover
        print(f"Failed to import AURA compressor: {exc}", file=sys.stderr)
        sys.exit(1)

    totals = {
        "original_bytes": 0,
        "compressed_bytes": 0,
    }
    by_method: Dict[str, Dict[str, float]] = defaultdict(lambda: {"original_bytes": 0, "compressed_bytes": 0, "files": 0})
    skipped = Counter()

    for path in file_paths:
        text = load_text(path).strip()
        if not text:
            skipped["empty"] += 1
            continue
        try:
            compressed, method, _meta = classify_and_compress(text)
        except Exception as exc:
            skipped["errors"] += 1
            print(f"[warn] Failed to compress {path}: {exc}", file=sys.stderr)
            continue

        original_size = len(text.encode("utf-8"))
        compressed_size = len(compressed)

        totals["original_bytes"] += original_size
        totals["compressed_bytes"] += compressed_size

        stats = by_method[method]
        stats["original_bytes"] += original_size
        stats["compressed_bytes"] += compressed_size
        stats["files"] += 1

    return {
        "totals": totals,
        "by_method": by_method,
        "skipped_empty": skipped.get("empty", 0),
        "skipped_errors": skipped.get("errors", 0),
        "files_processed": sum(m["files"] for m in by_method.values()),
    }  # type: ignore[return-value]


def format_ratio(original: float, compressed: float) -> str:
    if compressed == 0:
        return "n/a"
    return f"{original / compressed:.2f}x"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute AURA compression ratios on saved runs.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=pathlib.Path,
        default=[pathlib.Path("data/improvements")],
        help="Paths to scan for text files (default: data/improvements)",
    )
    parser.add_argument(
        "--suffixes",
        nargs="+",
        default=[".md", ".txt"],
        help="File suffixes to include (default: .md .txt)",
    )
    args = parser.parse_args()

    files = find_text_files(args.paths, tuple(s.lower() for s in args.suffixes))
    if not files:
        print("No files found with the given suffixes.")
        return

    result = compute_ratios(files)
    totals = result["totals"]
    overall_ratio = format_ratio(totals["original_bytes"], totals["compressed_bytes"])

    print(f"Files processed: {result['files_processed']}")
    print(f"Skipped empty: {result['skipped_empty']}, errors: {result['skipped_errors']}")
    print(f"Overall ratio: {overall_ratio} ({totals['original_bytes']} → {totals['compressed_bytes']} bytes)")
    print("\nBy method:")
    for method, stats in sorted(result["by_method"].items(), key=lambda kv: kv[1]["original_bytes"], reverse=True):
        ratio = format_ratio(stats["original_bytes"], stats["compressed_bytes"])
        print(f"  {method:20s} {ratio:>8}  files={int(stats['files'])}  "
              f"{int(stats['original_bytes'])} → {int(stats['compressed_bytes'])} bytes")


if __name__ == "__main__":
    main()
