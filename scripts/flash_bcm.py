#!/usr/bin/env python3
"""Build, flash, and verify the BCM firmware on the connected STM32 board.

Replaces the old deploy_bcm.sh (still the entry point Jenkins/devs call —
it just execs this script now) with a version that:
  - Logs every stage (compile/probe/flash/reset/verify) with clear
    start/end banners, using the same Log formatting as the test suite.
  - Writes the full build/flash output to a log file always, and only
    prints it to the console if a stage actually fails.
  - Verifies the board is actually alive over UART after resetting it.
    st-flash's SWD-based reset does not reliably restart the target's
    peripherals on all ST-Link + STM32 combinations, so the old script
    could report "DEPLOYMENT SUCCESSFUL" while the board stayed silent
    until someone noticed a test hanging and manually power-cycled it.
"""
import hashlib
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.bridge.hardware_bridge import Log, HardwareBridge  # noqa: E402

FIRMWARE_DIR = REPO_ROOT / "firmware" / "BCM_Firmware"
BINARY_PATH = FIRMWARE_DIR / "build" / "BCM_Firmware.bin"
ELF_PATH = FIRMWARE_DIR / "build" / "BCM_Firmware.elf"
VERSION_PATH = FIRMWARE_DIR / "VERSION"
CHANGELOG_PATH = FIRMWARE_DIR / "CHANGELOG.md"
FLASH_ADDRESS = "0x08000000"
REQUIRED_TOOLS = ("arm-none-eabi-gcc", "st-flash", "st-info")
POST_RESET_SETTLE_S = 1.0  # give the board a moment before checking UART


def _run(cmd, cwd=None):
    """Runs a command and returns its stripped stdout, or "" if it fails."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _md5sum(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_stage(name, cmd, cwd=None):
    """Runs a subprocess as one logged stage: verbose output always goes to
    the log file; it's only replayed to the console if the stage fails."""
    Log.stage_start(name)
    start = time.time()

    process = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    captured = []
    for line in process.stdout:
        line = line.rstrip()
        if line:
            captured.append(line)
            Log.verbose(line)
    process.wait()
    elapsed = time.time() - start

    if process.returncode != 0:
        Log.error(f"Stage '{name}' failed (exit {process.returncode}) after {elapsed:.1f}s. Output:")
        for line in captured:
            Log.error(line)
        Log.stage_end(name, ok=False)
        raise SystemExit(1)

    Log.info(f"{name} completed in {elapsed:.1f}s ({len(captured)} lines logged)")
    Log.stage_end(name, ok=True)


def check_toolchain():
    Log.stage_start("Checking toolchain")
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    if missing:
        Log.error(f"Missing required tools: {', '.join(missing)}")
        Log.error("Install the ARM GCC toolchain and stlink-tools (e.g. `brew install open-ocd stlink`).")
        Log.stage_end("Checking toolchain", ok=False)
        raise SystemExit(1)
    Log.info(f"Found: {', '.join(REQUIRED_TOOLS)}")
    Log.stage_end("Checking toolchain", ok=True)


def _fw_version():
    """The MAJOR.MINOR.PATCH release number from VERSION — bumped by hand,
    alongside a CHANGELOG.md entry (see check_changelog_entry)."""
    return VERSION_PATH.read_text().strip() if VERSION_PATH.exists() else "0.0.0"


def _sw_version():
    """Matches the Makefile's GIT_VERSION exactly: FW_VERSION plus a
    +<git-hash>[-dirty] build-metadata suffix pinning the exact commit —
    this is the string baked into the binary via BCM_SW_VERSION and reported
    live over UART by CMD_GET_VERSION."""
    git_hash = _run(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO_ROOT)) or "unknown"
    dirty = bool(_run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT)))
    return f"{_fw_version()}+{git_hash}{'-dirty' if dirty else ''}"


def _changelog_entry(fw_version):
    """Returns the bullet lines under `## <fw_version>` in CHANGELOG.md, or
    None if there's no such heading yet."""
    if not CHANGELOG_PATH.exists():
        return None
    lines = CHANGELOG_PATH.read_text().splitlines()
    try:
        start = lines.index(f"## {fw_version}") + 1
    except ValueError:
        return None
    entry = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            entry.append(line.strip())
    return entry or None


def check_changelog_entry():
    """Refuses to flash a version with no matching CHANGELOG.md entry, so
    every build that reaches hardware has a recorded, human-readable reason
    for existing — not just a bumped number."""
    Log.stage_start("Checking changelog entry")
    fw_version = _fw_version()
    entry = _changelog_entry(fw_version)

    if entry is None:
        Log.error(f"No CHANGELOG.md entry for version {fw_version} (VERSION file: {VERSION_PATH}).")
        Log.error(f"Add a `## {fw_version}` section to {CHANGELOG_PATH} describing this release, then re-run.")
        Log.stage_end("Checking changelog entry", ok=False)
        raise SystemExit(1)

    Log.info(f"Version {fw_version}:")
    for line in entry:  # pylint: disable=not-an-iterable  # unreachable with entry=None, see raise above
        Log.info(f"  {line}")
    Log.stage_end("Checking changelog entry", ok=True)


def check_currently_flashed_version():
    """Reads the version the board reports RIGHT NOW, before this run
    overwrites it — the 'what was on it before' half of flash traceability.
    Best-effort: a blank/bricked board, or older firmware predating
    CMD_GET_VERSION, just reports as unknown rather than failing the run —
    there's nothing actionable to do about either case before flashing."""
    Log.stage_start("Checking currently-flashed version")

    try:
        bridge = HardwareBridge()
    except Exception as e:
        Log.info(f"Could not open the serial port to check the current version: {e}")
        Log.stage_end("Checking currently-flashed version", ok=True)
        return None

    version = bridge.get_version()
    bridge.close()

    if version:
        Log.info(f"Board currently reports: {version}")
    else:
        Log.info("Board did not respond to CMD_GET_VERSION (blank, or firmware predating this command).")
    Log.stage_end("Checking currently-flashed version", ok=True)
    return version


def log_binary_details():
    """Logs everything needed to know exactly what's about to be flashed:
    which binary, built from which git commit, with what checksum, and how
    much flash/RAM it uses — the kind of traceability you'd want before
    putting firmware on a safety-critical ECU."""
    Log.stage_start("Inspecting binary")

    size_bytes = BINARY_PATH.stat().st_size
    Log.info(f"Binary:       {BINARY_PATH} ({size_bytes} bytes / {size_bytes / 1024:.1f} KB)")
    Log.info(f"MD5:          {_md5sum(BINARY_PATH)}")
    Log.info(f"Flash target: {FLASH_ADDRESS}")
    Log.info(f"SW version:   {_sw_version()}")

    gcc_version = _run(["arm-none-eabi-gcc", "-dumpversion"]) or "unknown"
    Log.info(f"Toolchain:    arm-none-eabi-gcc {gcc_version}")

    if ELF_PATH.exists():
        size_output = _run(["arm-none-eabi-size", str(ELF_PATH)])
        lines = size_output.splitlines()
        if len(lines) >= 2:
            Log.info(f"Memory usage: {lines[0]}")
            Log.info(f"              {lines[1]}")

    Log.stage_end("Inspecting binary", ok=True)


def probe_hardware():
    Log.stage_start("Probing ST-Link / target")
    result = subprocess.run(["st-info", "--probe"], capture_output=True, text=True)
    for line in result.stdout.strip().splitlines():
        Log.info(line.strip())

    if result.returncode != 0 or "Found 0 stlink" in result.stdout:
        Log.error("No ST-Link programmer detected. Check the USB connection.")
        Log.stage_end("Probing ST-Link / target", ok=False)
        raise SystemExit(1)
    Log.stage_end("Probing ST-Link / target", ok=True)


def verify_uart_link(expected_version):
    """Opens the serial port, checks whether the board is actually streaming
    telemetry after the reset, and asks it for its firmware version (see
    CMD_GET_VERSION in main.c) to confirm the running board matches what was
    just built - not just that *something* got written to flash."""
    Log.stage_start("Verifying UART link")
    time.sleep(POST_RESET_SETTLE_S)

    try:
        bridge = HardwareBridge()
    except Exception as e:
        Log.error(f"Could not open the serial port: {e}")
        Log.stage_end("Verifying UART link", ok=False)
        return False

    alive = bool(bridge.protocol.latest_telemetry)
    reported_version = bridge.get_version() if alive else None
    bridge.close()

    if not alive:
        Log.error(
            "No telemetry received after reset. This is a known ST-Link "
            "SWD-reset quirk (the reset doesn't always restart peripheral "
            "clocks the way a real power-on reset does)."
        )
        Log.error("Fix: unplug/replug the board's USB cable, or press its reset button, then re-run this script.")
        Log.stage_end("Verifying UART link", ok=False)
        return False

    Log.info("Board is streaming telemetry — UART link confirmed alive.")
    if reported_version is None:
        Log.error("Board did not respond to CMD_GET_VERSION (old firmware without this command?).")
        Log.stage_end("Verifying UART link", ok=False)
        return False
    if reported_version != expected_version:
        Log.error(f"Version mismatch: board reports '{reported_version}', expected '{expected_version}'.")
        Log.error("The board may be running stale firmware from a previous flash — re-run this script.")
        Log.stage_end("Verifying UART link", ok=False)
        return False

    Log.info(f"Board firmware version confirmed: {reported_version}")
    Log.stage_end("Verifying UART link", ok=True)
    return True


def main():
    log_dir = REPO_ROOT / "test_results" / f"flash_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_dir.mkdir(parents=True, exist_ok=True)
    Log.attach_file_handler(str(log_dir), filename="flash.log")

    Log.info("=== BCM Firmware Deployment ===")
    overall_start = time.time()

    check_toolchain()
    check_changelog_entry()
    previous_version = check_currently_flashed_version()

    run_stage("Compiling firmware", ["make", "clean", "all"], cwd=str(FIRMWARE_DIR))

    if not BINARY_PATH.exists():
        Log.error(f"Expected binary not found: {BINARY_PATH}")
        raise SystemExit(1)

    log_binary_details()
    new_version = _sw_version()
    probe_hardware()
    run_stage(
        "Flashing firmware",
        ["st-flash", "--connect-under-reset", "write", str(BINARY_PATH), FLASH_ADDRESS],
    )
    run_stage("Resetting board", ["st-flash", "reset"])

    uart_ok = verify_uart_link(new_version)
    elapsed = time.time() - overall_start

    Log.info(f"=== FLASH TRACEABILITY: {previous_version or 'unknown'} -> {new_version} ===")
    if uart_ok:
        Log.info(f"=== Deployment successful in {elapsed:.1f}s — firmware flashed and verified live ===")
    else:
        Log.info(f"=== Deployment completed in {elapsed:.1f}s, but UART verification FAILED (see above) ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
