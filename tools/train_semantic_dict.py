
import sys
import os
import glob
import numpy as np
from collections import defaultdict
from pathlib import Path

def train_dictionary(input_dir, output_path, max_entries=60000, min_freq=2, min_len=4, max_len=64):
    print("=" * 80)
    print(f"TRAINING SEMANTIC DICTIONARY")
    print(f"Input: {input_dir}")
    print(f"Output: {output_path}")
    print("=" * 80)

    # 1. Read all files
    files = glob.glob(os.path.join(input_dir, "*.md"))
    if not files:
        print("No .md files found.")
        return

    all_text = ""
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            all_text += f.read() + "\n"  # Add newline separator
    
    print(f"Total corpus size: {len(all_text)} bytes")

    # 2. Mine N-grams
    # We use a simple approach: count all substrings of length min_len to max_len
    # For 20KB corpus, this is fast enough.
    
    print("Mining n-grams...")
    counts = defaultdict(int)
    
    # Optimization: Don't iterate every single length if corpus is large, 
    # but for 20KB we can do it.
    
    corpus_len = len(all_text)
    
    # To speed up, we can just look for repeated words/phrases
    # But let's stick to the brute force substring counting for maximum quality on small data
    for length in range(min_len, max_len + 1):
        for i in range(corpus_len - length):
            sub = all_text[i : i + length]
            # Heuristic: skip if starts/ends with space to avoid partial words?
            # Actually, we want " word " to be captured.
            # But we don't want "ord " from "word ".
            # Let's just count everything and let the savings metric sort it out.
            counts[sub] += 1

    print(f"Found {len(counts)} unique n-grams.")

    # 3. Score and Select
    # Score = (length - 2) * frequency
    # We subtract 2 because the token overhead is 2 bytes (0x80 + index)
    # Actually overhead is 2 bytes for token vs length bytes for literal.
    # Savings = length - 2.
    
    candidates = []
    for pattern, freq in counts.items():
        if freq < min_freq:
            continue
        
        savings = (len(pattern) - 2) * freq
        if savings > 0:
            candidates.append((pattern, savings, freq))
    
    # Sort by savings descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # 4. Filter overlaps (Greedy)
    # If we select "hello world", we shouldn't also select "hello" if it mostly appears in "hello world"
    # But for a simple dictionary, we can just take the top N.
    # The compressor (greedy) will match longest first.
    # So having "hello world" and "hello" is fine.
    
    selected = candidates[:max_entries]
    print(f"Selected top {len(selected)} patterns.")
    
    if selected:
        print(f"Top pattern: '{selected[0][0]}' (Savings: {selected[0][1]})")

    # 5. Build Arrays
    phrases_bytes = bytearray()
    offsets = []
    lengths = []
    
    current_offset = 0
    
    for pattern, savings, freq in selected:
        p_bytes = pattern.encode('utf-8')
        phrases_bytes.extend(p_bytes)
        offsets.append(current_offset)
        lengths.append(len(p_bytes))
        current_offset += len(p_bytes)
        
    # 6. Save to NPZ
    np.savez_compressed(
        output_path,
        phrases=np.array(phrases_bytes, dtype=np.uint8),
        offsets=np.array(offsets, dtype=np.uint32),
        lengths=np.array(lengths, dtype=np.uint16)
    )
    
    print(f"Saved dictionary to {output_path}")
    print(f"Dictionary size: {len(phrases_bytes)} bytes (raw text)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 train_semantic_dict.py <input_dir> <output_npz>")
        sys.exit(1)
    
    train_dictionary(sys.argv[1], sys.argv[2])
