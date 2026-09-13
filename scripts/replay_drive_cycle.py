#!/usr/bin/env python3
"""Streams a drive-cycle CSV to the board over time, while the board's
response is processed and stored exactly the way the test suite already
does it: HardwareBridge's reader thread parses each telemetry frame and
writes it to test_results/session_<ts>/telemetry_<ts>.csv and session.log.

Input CSV columns: `time_s` (elapsed seconds from the start of the replay,
required) plus any of `pedal`, `speed`, `temp`, `wear` (optional — only the
columns present in the header are sent as commands, and only for rows where
that cell isn't blank). Example:

    time_s,pedal,speed,temp
    0,0,0,25
    1,20,10,25
    5,80,60,210

Usage:
    python3 scripts/replay_drive_cycle.py scripts/sample_drive_cycle.csv
    python3 scripts/replay_drive_cycle.py my_cycle.csv --no-reset
"""
import argparse
import csv
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.bridge.hardware_bridge import Log, HardwareBridge, SerialLinkLost, derive_system_state  # noqa: E402

COMMAND_SENDERS = {
    "pedal": lambda bridge, v: bridge.set_pedal(v),
    "speed": lambda bridge, v: bridge.set_speed(v),
    "temp": lambda bridge, v: bridge.set_temp(v),
    "wear": lambda bridge, v: bridge.set_wear(v),
}

DEFAULT_HEARTBEAT_INTERVAL_S = 20.0
POLL_INTERVAL_S = 0.5  # granularity of the wait between rows/heartbeats


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path, help="Drive-cycle CSV file to replay")
    parser.add_argument("--no-reset", action="store_true", help="Don't send a RESET command before replaying")
    parser.add_argument(
        "--heartbeat-interval", type=float, default=DEFAULT_HEARTBEAT_INTERVAL_S,
        help=f"Max seconds of silence before a status heartbeat is logged, "
             f"independent of row spacing (default: {DEFAULT_HEARTBEAT_INTERVAL_S})",
    )
    return parser.parse_args()


def load_cycle(csv_path):
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if "time_s" not in reader.fieldnames:
            raise ValueError("CSV must have a 'time_s' column")
        columns = [c for c in COMMAND_SENDERS if c in reader.fieldnames]
        if not columns:
            raise ValueError(f"CSV must have at least one of: {', '.join(COMMAND_SENDERS)}")

        rows = []
        for row in reader:
            step = {"time_s": float(row["time_s"])}
            for col in columns:
                if row.get(col, "") != "":
                    step[col] = float(row[col])
            rows.append(step)
    return rows, columns


def main():
    args = parse_args()
    rows, columns = load_cycle(args.csv_path)
    Log.info(f"Loaded {len(rows)} steps from {args.csv_path} (driving: {', '.join(columns)})")

    try:
        bridge = HardwareBridge()
    except Exception as e:
        Log.error(f"Could not connect to the board: {e}")
        sys.exit(1)

    exit_code = 0
    start = time.time()
    last_heartbeat = start
    try:
        if not args.no_reset:
            bridge.reset()

        for i, row in enumerate(rows):
            target_time = start + row["time_s"]

            # Wait for this row's scheduled time, but never sleep longer than
            # heartbeat-interval at a stretch, so a status line always gets
            # logged at least that often even if rows are spaced further
            # apart than that (e.g. a hand-written, sparsely-sampled CSV).
            while True:
                now = time.time()
                remaining = target_time - now
                if remaining <= 0:
                    break
                if now - last_heartbeat >= args.heartbeat_interval:
                    last_heartbeat = now
                    telem = bridge.get_status()
                    flag = int(telem.get("flag", 0))
                    Log.info(
                        f"Still replaying... {now - start:.0f}s elapsed, step {i + 1}/{len(rows)} "
                        f"pending @ t={row['time_s']:.1f}s, state={derive_system_state(flag)}"
                    )
                time.sleep(min(POLL_INTERVAL_S, remaining))

            for col in columns:
                if col in row:
                    COMMAND_SENDERS[col](bridge, row[col])

            telem = bridge.get_status()
            flag = int(telem.get("flag", 0))
            Log.info(
                f"Step {i + 1}/{len(rows)} @ t={row['time_s']:.1f}s -> "
                f"pedal={telem.get('p')} speed={telem.get('s')} chip_c={telem.get('chip_c')} "
                f"state={derive_system_state(flag)}"
            )
            last_heartbeat = time.time()
    except KeyboardInterrupt:
        Log.info("Replay interrupted by user.")
    except SerialLinkLost as e:
        Log.error(f"Lost the serial connection mid-replay: {e}")
        exit_code = 1
    finally:
        csv_filename = bridge.csv_filename
        state_log_filename = bridge.state_log_filename
        try:
            bridge.close()
        except Exception as e:
            Log.error(f"Error while closing the hardware link (ignored): {e}")
        Log.info(f"=== Drive-cycle replay finished. Telemetry: {csv_filename} | State transitions: {state_log_filename} ===")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
