#!/usr/bin/env python3
"""Generates a long, multi-phase synthetic drive-cycle CSV that deliberately
drives the BCM's system-status machine (see hardware_bridge.derive_system_state)
through every state AND every transition between states at least once:

    NORMAL, ACTIVE (ABS/HSA), WARNING (brake wear), FAULT (thermal/plausibility)

Timing note (SWE6-Test/firmware/BCM_Firmware/Core/Src/main.c): BCM_Step() -
where the plausibility latch counter lives - runs at 100Hz (every 10ms), and
that latch needs only 5 consecutive cycles (50ms) of "pedal>50% & speed not
decreasing" to trip. ABS requires pedal>80%, which always satisfies the
plausibility precondition too, so a *reliably* clean ABS-only demonstration
would need sub-50ms command cadence - not practical from a Python/UART
command loop. HSA requires pedal<5% while holding, which is always safely
under the plausibility threshold regardless of timing, so HSA is used for
every combo phase that needs to be reproducible. The one ABS phase here is
a best-effort bonus: it may legitimately show FAULT and ACTIVE together,
which is itself an accurate demonstration of how the two safety checks
interact, not a bug.

Phase -> expected system state (see bcm_safety.c / bcm_abs.c / bcm_hsa.c):

    cold_start_idle          NORMAL
    hsa_arm_1 / hsa_hold_1   NORMAL -> ACTIVE (HSA) -> NORMAL (hold times out)
    city_stop_and_go         NORMAL
    highway_cruise           NORMAL
    hard_brake_abs_event     ACTIVE (ABS) and/or FAULT (plausibility) - best effort
    post_brake_recovery      NORMAL
    sustained_hard_pedal     FAULT (plausibility)
    pedal_release            NORMAL
    long_highway_heat_soak   NORMAL
    overheat_event           FAULT (thermal)
    cooldown                 NORMAL
    wear_accumulation        NORMAL -> WARNING (wear crosses 90%)
    warning_to_fault_thermal WARNING -> FAULT (temp also crosses 200C)
    fault_to_warning_thermal FAULT -> WARNING (temp recovers, wear still high)
    warning_to_normal        WARNING -> NORMAL (wear recovers)
    normal_to_warning_again  NORMAL -> WARNING (wear re-elevated for the next demo)
    hsa_arm_2 / hsa_hold_2   WARNING -> ACTIVE (wear drops <=90% mid-hold) -> NORMAL
    settle_wear              NORMAL
    hsa_arm_3 / hsa_hold_3   NORMAL -> ACTIVE -> FAULT (thermal spike mid-hold)
                             -> ACTIVE (thermal clears, HSA still holding) -> NORMAL
    end_of_session_idle      NORMAL

Usage:
    python3 scripts/generate_drive_cycle.py
    python3 scripts/generate_drive_cycle.py --out scripts/my_cycle.csv
"""
import argparse
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "scripts" / "drive_cycle_long.csv"

# name, duration_s, step_s, pedal(start,end), speed(start,end), temp(start,end), wear(start,end)
PHASES = [
    dict(name="cold_start_idle",          duration=60,  step=10,   pedal=(0, 0),   speed=(0, 0),    temp=(25, 25),   wear=(5, 5)),

    # HSA #1: arm (speed<0.1 & pedal>80) then hold (pedal<5%) until the 2.0s
    # timer expires on its own -> clean NORMAL -> ACTIVE -> NORMAL.
    dict(name="hsa_arm_1",                duration=0.3, step=0.3,  pedal=(90, 90), speed=(0, 0),    temp=(25, 25),   wear=(5, 5)),
    dict(name="hsa_hold_1",               duration=2.5, step=2.5,  pedal=(0, 0),   speed=(0, 0),    temp=(25, 25),   wear=(5, 5)),

    dict(name="city_stop_and_go",         duration=180, step=5,    pedal=(10, 40), speed=(5, 45),   temp=(25, 60),   wear=(5, 15)),
    dict(name="highway_cruise",           duration=120, step=5,    pedal=(30, 35), speed=(60, 110), temp=(60, 70),   wear=(15, 20)),

    # Best-effort ABS demo: fine cadence (30ms, under the 50ms plausibility
    # window) with continuously decreasing speed. May still show FAULT
    # alongside ACTIVE - see module docstring.
    dict(name="hard_brake_abs_event",     duration=5,   step=0.03, pedal=(90, 85), speed=(130, 30), temp=(70, 68),   wear=(20, 21)),

    dict(name="post_brake_recovery",      duration=60,  step=5,    pedal=(15, 20), speed=(25, 40),  temp=(65, 60),   wear=(21, 22)),
    dict(name="sustained_hard_pedal",     duration=20,  step=2,    pedal=(70, 70), speed=(30, 32),  temp=(55, 55),   wear=(22, 22)),
    dict(name="pedal_release",            duration=20,  step=4,    pedal=(10, 5),  speed=(25, 15),  temp=(50, 45),   wear=(22, 23)),
    dict(name="long_highway_heat_soak",   duration=180, step=10,   pedal=(30, 35), speed=(85, 95),  temp=(80, 190),  wear=(23, 40)),
    dict(name="overheat_event",           duration=30,  step=5,    pedal=(15, 20), speed=(55, 60),  temp=(205, 230), wear=(40, 41)),
    dict(name="cooldown",                 duration=60,  step=10,   pedal=(0, 0),   speed=(30, 0),   temp=(200, 40),  wear=(41, 42)),
    dict(name="wear_accumulation",        duration=240, step=15,   pedal=(15, 20), speed=(40, 50),  temp=(40, 50),   wear=(42, 95)),

    # WARNING <-> FAULT: thermal fault trips and clears while wear stays >90%.
    dict(name="warning_to_fault_thermal", duration=20,  step=5,    pedal=(0, 0),   speed=(0, 0),    temp=(190, 210), wear=(95, 95)),
    dict(name="fault_to_warning_thermal", duration=15,  step=5,    pedal=(0, 0),   speed=(0, 0),    temp=(210, 185), wear=(95, 95)),

    # WARNING -> NORMAL (direct), then back to WARNING for the next demo.
    dict(name="warning_to_normal",        duration=20,  step=5,    pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(95, 60)),
    dict(name="normal_to_warning_again",  duration=20,  step=5,    pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(60, 95)),

    # HSA #2: arm+hold while wear is still >90% (WARNING outranks ACTIVE, so
    # HSA_ACTIVE is silently set here without changing the reported state),
    # then wear drops <=90% mid-hold -> WARNING flips straight to ACTIVE
    # (HSA_ACTIVE was there the whole time), then the hold times out -> NORMAL.
    dict(name="hsa_arm_2",                duration=0.3, step=0.3,  pedal=(90, 90), speed=(0, 0),    temp=(40, 40),   wear=(95, 95)),
    dict(name="hsa_hold_2a_hidden",       duration=0.5, step=0.5,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(95, 95)),
    dict(name="hsa_hold_2b_reveal",       duration=0.4, step=0.4,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(80, 80)),
    dict(name="hsa_hold_2c_timeout",      duration=1.3, step=1.3,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(80, 80)),

    dict(name="settle_wear",              duration=30,  step=10,   pedal=(0, 0),   speed=(0, 0),    temp=(30, 30),   wear=(80, 20)),

    # HSA #3: arm+hold at rest, then a thermal spike trips FAULT mid-hold
    # (FAULT outranks ACTIVE), then temp recovers -> back to ACTIVE (HSA is
    # still literally holding), then the hold times out -> NORMAL.
    dict(name="hsa_arm_3",                duration=0.3, step=0.3,  pedal=(90, 90), speed=(0, 0),    temp=(40, 40),   wear=(20, 20)),
    dict(name="hsa_hold_3a_active",       duration=0.5, step=0.5,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(20, 20)),
    dict(name="hsa_hold_3b_fault",        duration=0.4, step=0.4,  pedal=(0, 0),   speed=(0, 0),    temp=(210, 210), wear=(20, 20)),
    dict(name="hsa_hold_3c_active_again", duration=0.3, step=0.3,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(20, 20)),
    dict(name="hsa_hold_3d_timeout",      duration=1.0, step=1.0,  pedal=(0, 0),   speed=(0, 0),    temp=(40, 40),   wear=(20, 20)),

    dict(name="end_of_session_idle",      duration=60,  step=15,   pedal=(0, 0),   speed=(0, 0),    temp=(30, 30),   wear=(20, 20)),
]


def _interp(start, end, frac):
    return start + (end - start) * frac


def generate_rows():
    rows = []
    t = 0.0
    for phase in PHASES:
        n_steps = max(1, round(phase["duration"] / phase["step"]))
        for i in range(n_steps + 1):
            frac = i / n_steps
            rows.append({
                "time_s": round(t + frac * phase["duration"], 3),
                "pedal": round(_interp(*phase["pedal"], frac), 1),
                "speed": round(_interp(*phase["speed"], frac), 1),
                "temp": round(_interp(*phase["temp"], frac), 1),
                "wear": round(_interp(*phase["wear"], frac), 1),
            })
        t += phase["duration"]
    return rows


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output CSV path (default: {DEFAULT_OUT})")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = generate_rows()

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time_s", "pedal", "speed", "temp", "wear"])
        writer.writeheader()
        writer.writerows(rows)

    total_duration = sum(p["duration"] for p in PHASES)
    print(f"Wrote {len(rows)} rows ({total_duration:.0f}s / {total_duration / 60:.1f} min) to {args.out}")
    print("Phases:")
    for phase in PHASES:
        print(f"  {phase['name']:<24} {phase['duration']:>6.1f}s")


if __name__ == "__main__":
    main()
