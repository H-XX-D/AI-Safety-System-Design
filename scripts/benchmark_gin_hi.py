#!/usr/bin/env python3
"""Quick one-shot benchmark for running directly on the GIN nano.

Sends the prompt "hi" (or a custom prompt) to the local Ollama endpoint and
reports end-to-end latency plus the raw response payload. Run this *on the
nano itself* (no network hop) to verify the 3DLM/ThirdLM model is loaded.
"""

import argparse
import json
import time
import urllib.error
import urllib.request


def run_benchmark(host: str, port: int, model: str, prompt: str) -> None:
    url = f"http://{host}:{port}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        raise SystemExit(f"Request failed: {e}")
    elapsed_ms = (time.monotonic() - start) * 1000

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"raw": raw.decode("utf-8", errors="replace")}

    print("=== GIN nano benchmark ===")
    print(f"Endpoint : {url}")
    print(f"Model    : {model}")
    print(f"Prompt   : {prompt!r}")
    print(f"Latency  : {elapsed_ms:.2f} ms")
    print("Response :")
    print(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Benchmark a single prompt on the GIN nano")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Nano IP/hostname (default: 127.0.0.1 for local, change if needed)",
    )
    parser.add_argument("--port", type=int, default=11434, help="Ollama port (default: 11434)")
    parser.add_argument("--model", default="deepseek-r1:1.5b", help="Model name loaded on the nano")
    parser.add_argument("--prompt", default="hi", help="Prompt to send (default: 'hi')")

    args = parser.parse_args()
    run_benchmark(args.host, args.port, args.model, args.prompt)


if __name__ == "__main__":
    main()
