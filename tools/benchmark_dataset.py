
import os
import glob
import sys
from collections import defaultdict
from communication.message_codec import MessageCodec

def benchmark_dataset(input_dir):
    print(f"Benchmarking compression on {input_dir}...")
    
    files = glob.glob(os.path.join(input_dir, "*.md"))
    if not files:
        print("No .md files found.")
        return

    codec = MessageCodec()
    
    total_orig = 0
    total_comp = 0
    method_counts = defaultdict(int)
    
    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        payload, method, meta = codec.encode(content)
        
        orig_size = len(content.encode('utf-8'))
        comp_size = len(payload) + 1 # +1 for method byte
        
        total_orig += orig_size
        total_comp += comp_size
        method_counts[method] += 1
        
    print("-" * 40)
    print(f"Total Original:   {total_orig} bytes")
    print(f"Total Compressed: {total_comp} bytes")
    if total_comp > 0:
        print(f"Compression Ratio: {total_orig / total_comp:.2f}x")
    else:
        print("Compression Ratio: N/A")
        
    print("\nMethod Usage:")
    for m, count in method_counts.items():
        print(f"  {m}: {count}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 benchmark_dataset.py <input_dir>")
        sys.exit(1)
    
    benchmark_dataset(sys.argv[1])
