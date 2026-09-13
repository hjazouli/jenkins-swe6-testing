#!/usr/bin/env python3
"""Continuously logs BCM telemetry for as long as this script runs.

Reuses HardwareBridge exactly as the test suite does, so output lands in
the same place tests already use: test_results/session_<ts>/telemetry_<ts>.csv
(raw per-sample data) and session.log (human-readable [TELEM] lines, same
tagged format as everywhere else). Meant for soak/endurance monitoring —
run it for hours unattended, or until you Ctrl+C it.

Usage:
    python3 scripts/monitor_bcm.py                    # run until Ctrl+C
    python3 scripts/monitor_bcm.py --duration 3600     # run for 1 hour
    python3 scripts/monitor_bcm.py --no-reset          # don't reset the board first
    python3 scripts/monitor_bcm.py --status-interval 5 # more frequent console heartbeats
"""
import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.bridge.hardware_bridge import Log, HardwareBridge, SerialLinkLost, derive_system_state  # noqa: E402

DEFAULT_STATUS_INTERVAL_S = 30.0
POLL_INTERVAL_S = 0.1  # faster than the board's 100ms telemetry rate, avoids missing samples


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--duration", type=float, default=None,
        help="Stop automatically after this many seconds (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--no-reset", action="store_true",
        help="Don't send a RESET command before monitoring (default: reset for a clean baseline)",
    )
    parser.add_argument(
        "--status-interval", type=float, default=DEFAULT_STATUS_INTERVAL_S,
        help=f"Seconds between console heartbeat updates (default: {DEFAULT_STATUS_INTERVAL_S})",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        bridge = HardwareBridge()
    except Exception as e:
        Log.error(f"Could not connect to the board: {e}")
        Log.error("Check that it's plugged in and the port in hardware_bridge.SERIAL_PORT is correct.")
        sys.exit(1)

    try:
        if not args.no_reset:
            bridge.reset()
    except SerialLinkLost as e:
        Log.error(f"Lost the serial connection before monitoring could start: {e}")
        bridge.close()
        sys.exit(1)

    duration_desc = f"for {args.duration:.0f}s" if args.duration else "until Ctrl+C"
    Log.info(f"Monitoring started, running {duration_desc}. Logging to {bridge.csv_filename}")

    sample_count = 0
    last_seen_tick = None
    chip_c_min = chip_c_max = None
    chip_c_sum = 0.0

    start = time.time()
    last_status = start

    try:
        while args.duration is None or (time.time() - start) < args.duration:
            time.sleep(POLL_INTERVAL_S)
            telem = bridge.get_status()

            tick = telem.get("t")
            if tick is not None and tick != last_seen_tick:
                last_seen_tick = tick
                sample_count += 1
                chip_c = telem.get("chip_c")
                if chip_c is not None:
                    chip_c_min = chip_c if chip_c_min is None else min(chip_c_min, chip_c)
                    chip_c_max = chip_c if chip_c_max is None else max(chip_c_max, chip_c)
                    chip_c_sum += chip_c

            now = time.time()
            if now - last_status >= args.status_interval:
                last_status = now
                state = derive_system_state(int(telem.get("flag", 0)))
                Log.info(
                    f"Still monitoring... {now - start:.0f}s elapsed, {sample_count} samples, "
                    f"latest: pedal={telem.get('p')} speed={telem.get('s')} "
                    f"state={state} chip_c={telem.get('chip_c')}"
                )
    except KeyboardInterrupt:
        Log.info("Interrupted by user.")
    finally:
        elapsed = time.time() - start
        csv_filename = bridge.csv_filename
        bridge.close()

        Log.info(f"=== Monitoring stopped after {elapsed:.1f}s, {sample_count} samples logged ===")
        if sample_count > 0 and chip_c_min is not None:
            Log.info(
                f"Chip temperature over the run: min={chip_c_min}C max={chip_c_max}C "
                f"avg={chip_c_sum / sample_count:.1f}C"
            )
        Log.info(f"CSV: {csv_filename}")


if __name__ == "__main__":
    main()
