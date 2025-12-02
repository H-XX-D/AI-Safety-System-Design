"""Microbenchmark: Bit-packed vs AURA encode/decode overhead.

This is a rough, single-threaded benchmark to illustrate per-operation
costs for tiny control messages vs larger semantic messages.
"""
from __future__ import annotations
import time
from typing import Dict, Any
from message_codec import MessageCodec


def bench_once(codec: MessageCodec, msg: str, n: int = 5000) -> Dict[str, Any]:
    t0 = time.perf_counter()
    for _ in range(n):
        p, _m, _meta = codec.encode(msg)
        _d, _i = codec.decode(p)
    dt = time.perf_counter() - t0
    return {"iterations": n, "seconds": dt, "per_op_us": (dt / n) * 1e6}


def main():
    codec = MessageCodec()
    small = "System 1 approves proposal 042"
    large = "I recommend testing the quantization routine before deployment; ensure clarity and risk noted."

    res_small = bench_once(codec, small, n=10000)
    res_large = bench_once(codec, large, n=5000)

    print("\n=== MICROBENCH RESULTS ===")
    print(f"small/bitpacked: {res_small['per_op_us']:.2f} µs/op ({res_small['iterations']} iters)")
    print(f"large/aura:      {res_large['per_op_us']:.2f} µs/op ({res_large['iterations']} iters)")


if __name__ == "__main__":
    main()
