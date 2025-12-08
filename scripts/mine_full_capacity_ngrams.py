#!/usr/bin/env python3
"""
Mine frequent n-grams from full_capacity_tests logs and package them
into contiguous NumPy buffers suitable for binary-semantic dictionaries.

Default input: data/full_capacity_tests
Default output: worm_usb_dir/aura_templates/mined_ngrams.npz

Buffers saved:
  - phrases: utf-8 bytes for all n-grams concatenated
  - offsets: uint32 offsets into phrases buffer
  - lengths: uint16 lengths (up to 65535 bytes)
  - counts: uint32 occurrence counts aligned with offsets/lengths
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np


WORD_RE = re.compile(r"[A-Za-z0-9']+")


def tokenize(text: str) -> List[str]:
    """Simple alnum/apostrophe tokenizer."""
    return [w.lower() for w in WORD_RE.findall(text)]


def iter_texts(paths: Iterable[Path]) -> Iterable[str]:
    """Yield text from .log and .json files."""
    for path in paths:
        if path.suffix.lower() == ".log":
            try:
                yield path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
        elif path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                yield json.dumps(data, ensure_ascii=False)
            except Exception:
                continue


def mine_ngrams(texts: Iterable[str], n_range: Tuple[int, int]) -> Counter:
    """Count n-grams in the given texts."""
    counts: Counter = Counter()
    n_min, n_max = n_range
    for text in texts:
        tokens = tokenize(text)
        for n in range(n_min, n_max + 1):
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i : i + n])
                counts[gram] += 1
    return counts


def build_buffers(phrases: List[str], counts: List[int]) -> dict:
    """Build contiguous buffers for phrases and metadata."""
    encoded = [p.encode("utf-8") for p in phrases]
    offsets = []
    lengths = []
    pos = 0
    for b in encoded:
        offsets.append(pos)
        lengths.append(len(b))
        pos += len(b)
    buffer = b"".join(encoded)
    return {
        "phrases": np.frombuffer(buffer, dtype=np.uint8),
        "offsets": np.array(offsets, dtype=np.uint32),
        "lengths": np.array(lengths, dtype=np.uint16),
        "counts": np.array(counts, dtype=np.uint32),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine n-grams from full_capacity_tests logs.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/full_capacity_tests"),
        help="Directory to scan for .log/.json files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("worm_usb_dir/aura_templates/mined_ngrams.npz"),
        help="Output NPZ path",
    )
    parser.add_argument(
        "--n-min",
        type=int,
        default=3,
        help="Minimum n-gram size",
    )
    parser.add_argument(
        "--n-max",
        type=int,
        default=5,
        help="Maximum n-gram size",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=64000,
        help="Keep top K n-grams",
    )
    args = parser.parse_args()

    files = list(args.input_dir.glob("**/*"))
    texts = list(iter_texts(files))
    if not texts:
        print("No input texts found.")
        return

    counts = mine_ngrams(texts, (args.n_min, args.n_max))
    most_common = counts.most_common(args.top)
    phrases = [p for p, _ in most_common]
    freq = [c for _, c in most_common]

    buffers = build_buffers(phrases, freq)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **buffers)

    print(f"Saved {len(phrases)} n-grams to {args.output}")
    total = sum(freq)
    if total:
        print(f"Coverage: top {len(phrases)} n-grams account for {total} occurrences")


if __name__ == "__main__":
    main()
