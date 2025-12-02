#!/usr/bin/env python3
"""Simple helper to capture ESP32 serial output for a limited duration."""

from __future__ import annotations

import argparse
import sys
import time

try:
    import serial  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - runtime import guard
    print("pyserial is required to capture serial output", file=sys.stderr)
    sys.exit(1)


def pulse_reset(ser: "serial.Serial", *, enter_bootloader: bool) -> None:
    # Pulse the EN line; only keep IO0 asserted when staying in the ROM loader.
    ser.dtr = True
    time.sleep(0.05)
    ser.dtr = False
    time.sleep(0.05)
    if not enter_bootloader:
        ser.rts = False


def capture(
    port: str,
    baud: int,
    duration: float,
    encoding: str,
    auto_reset: bool,
    enter_bootloader: bool,
) -> int:
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.2)
    except serial.SerialException as exc:  # pragma: no cover - runtime failure path
        print(f"Failed to open {port}: {exc}", file=sys.stderr)
        return 1

    ser.dtr = False
    ser.rts = enter_bootloader
    time.sleep(0.02)

    if auto_reset:
        pulse_reset(ser, enter_bootloader=enter_bootloader)
    elif not enter_bootloader:
        ser.rts = False

    deadline = time.time() + duration
    try:
        while time.time() < deadline:
            chunk = ser.readline()
            if not chunk:
                continue
            text = chunk.decode(encoding, errors="replace")
            sys.stdout.write(text)
            sys.stdout.flush()
    finally:
        ser.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture serial output for a fixed duration")
    parser.add_argument("port", help="Serial port path, e.g. /dev/cu.usbserial-0001")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Baud rate to use (default: 115200)")
    parser.add_argument("-d", "--duration", type=float, default=7.0, help="Duration to capture, in seconds")
    parser.add_argument("-e", "--encoding", default="utf-8", help="Text encoding for output (default: utf-8)")
    parser.add_argument("--no-reset", action="store_true", help="Skip toggling DTR/RTS before capture")
    parser.add_argument(
        "--enter-bootloader",
        action="store_true",
        help="Hold IO0 low so the ROM stays in download mode",
    )
    args = parser.parse_args(argv)
    return capture(
        args.port,
        args.baud,
        args.duration,
        args.encoding,
        not args.no_reset,
        args.enter_bootloader,
    )


if __name__ == "__main__":
    sys.exit(main())
