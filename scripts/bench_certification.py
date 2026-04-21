import serial
import time
import sys

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200

def run_certification():
    print("\n" + "="*50)
    print("🚀 BCM INFRASTRUCTURE CERTIFICATION (INTERRUPT-ARCH)")
    print("="*50)
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        ser.reset_input_buffer()
        time.sleep(1) # Wait for port to stabilize
    except Exception as e:
        print(f"❌ [FAIL] Could not open {SERIAL_PORT}: {e}")
        return

    # --- PHASE 1: HEARTBEAT STABILITY ---
    print("\n📡 PHASE 1: Timing Integrity (1Hz Heartbeat)...")
    samples = []
    timeout_start = time.time()
    while len(samples) < 3 and (time.time() - timeout_start < 5):
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "[BCM" in line:
            samples.append(time.time())
            print(f"   ↳ Sample {len(samples)}: Received at {time.strftime('%H:%M:%S')}")

    if len(samples) >= 2:
        diff = samples[1] - samples[0]
        print(f"   ✅ Interval: {diff:.3f}s (Target: 1.000s)")
        if 0.9 <= diff <= 1.1:
            print("   🎖️ [PASS] Timing is stable.")
        else:
            print("   ⚠️ [WARN] Timing jitter detected.")
    else:
        print("   ❌ [FAIL] Not enough heartbeats received.")

    # --- PHASE 2: COMMAND STRESS TEST ---
    print("\n📤 PHASE 2: Command Throughput (Interrupt-RX Stress)...")
    success_count = 0
    total_cmds = 20
    for i in range(total_cmds):
        cmd = f"P{i}\n"
        ser.write(cmd.encode())
        # Brief pause to mimic rapid successive commands
        time.sleep(0.1) 
        
        # Look for ACK
        ack_found = False
        timeout_inner = time.time()
        while time.time() - timeout_inner < 0.5:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if "[ACK] RECEIVED" in line or "[BCM" in line: # ACK search
                if "[ACK]" in line:
                    ack_found = True
                    break
        
        if ack_found:
            success_count += 1
            sys.stdout.write(".")
            sys.stdout.flush()
        else:
            sys.stdout.write("F")
            sys.stdout.flush()

    print(f"\n   ✅ Results: {success_count}/{total_cmds} commands acknowledged.")
    if success_count == total_cmds:
        print("   🎖️ [PASS] UART RX Interrupt is solid.")
    else:
        print("   ❌ [FAIL] Command loss detected!")

    # --- PHASE 3: RESET INTEGRITY ---
    print("\n🔄 PHASE 3: System Recovery (Memory Reset)...")
    ser.write(b"R\n")
    time.sleep(0.5)
    found_reset = False
    timeout_reset = time.time()
    while time.time() - timeout_reset < 2:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if "[SYS] RESET PERFORMED" in line:
            found_reset = True
            print("   ✅ Reset message received.")
            break
            
    if found_reset:
        print("   🎖️ [PASS] Soft-Reset logic verified.")
    else:
        print("   ❌ [FAIL] Board did not acknowledge reset.")

    print("\n" + "="*50)
    if success_count == total_cmds and found_reset:
        print("🏆 INFRASTRUCTURE CERTIFIED: BCM IS READY FOR LOGIC VALIDATION")
    else:
        print("🚨 CERTIFICATION FAILED: CHECK HARDWARE CONNECTIONS")
    print("="*50 + "\n")

    ser.close()

if __name__ == "__main__":
    run_certification()
