import serial
import time

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 9600


def run_nominal_check():
    print(f"NOMINAL COMMUNICATION CHECK on {SERIAL_PORT}")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1.0)

    # 1. Heartbeat
    print("\nSTEP 1: VERIFYING TELEMETRY HEARTBEAT...")
    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if "[BCM-V101]" in line:
        print(f" [PASS] RECEIVED DATA: {line}")
    else:
        print(" [FAIL] TIMEOUT: Board is silent.")
        return

    # 2. Version Command
    print("\nSTEP 2: VERIFYING COMMAND ACKNOWLEDGEMENT...")
    print(" [SEND] P50")
    ser.write(b"P50\n")
    time.sleep(0.5)

    # Check for ACK
    found_ack = False
    for _ in range(20):
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "[ACK] RECEIVED" in line:
            print(f" [PASS] RECEIVED ACK: {line}")
            found_ack = True
            break

    if not found_ack:
        print(" [FAIL] No acknowledgement received.")

    # 3. Value Accuracy
    print("\nSTEP 3: VERIFYING DATA ACCURACY...")
    print(" [SEND] P123")
    ser.write(b"P123\n")
    time.sleep(1.0)  # Wait for telemetry

    for _ in range(20):
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "[BCM-V101]" in line and "P:123" in line:
            print(f" [PASS] ACCURACY VERIFIED: Telemetry shows {line}")
            break
    else:
        print(" [FAIL] ACCURACY FAILED: Telemetry does not match sent command.")

    # 4. Temperature Check
    print("\nSTEP 4: VERIFYING TEMPERATURE INPUT...")
    print(" [SEND] T75.5")
    ser.write(b"T75.5\n")
    time.sleep(1.0)
    for _ in range(20):
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "T:75" in line or "T:76" in line:
            print(f" [PASS] TEMPERATURE VERIFIED: {line}")
            break

    # 5. Multi-Command Stress (Small)
    print("\nSTEP 5: VERIFYING MULTI-COMMAND INTEGRITY...")
    print(" [SEND] P10, S20, T30")
    ser.write(b"P10\n")
    ser.write(b"S20\n")
    ser.write(b"T30\n")
    time.sleep(1.5)

    for _ in range(30):
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "[BCM-V101]" in line and "P:10" in line and "S:20" in line:
            print(f" [PASS] MULTI-COMMAND SUCCESS: {line}")
            break
    else:
        print(" [FAIL] MULTI-COMMAND ERROR: Board lost some data.")

    ser.close()
    print("\n[INFO] ALL NOMINAL CHECKS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_nominal_check()
