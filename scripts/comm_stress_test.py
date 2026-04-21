import serial
import time

SERIAL_PORT = "/dev/tty.usbmodem103"
BAUD_RATE = 115200

def run_performance_test():
    print(f"PERFORMANCE & STRESS TEST on {SERIAL_PORT}")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    
    # 1. Latency Baseline
    print("\nSTAGE 1: MEASURING ROUND-TRIP LATENCY...")
    latencies = []
    for i in range(20):
        start = time.time()
        ser.write(f"P{i}\n".encode())
        
        # Pull until ACK
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if "[ACK]" in line:
                end = time.time()
                latencies.append((end - start) * 1000)
                break
            if time.time() - start > 1.0:
                print(" [FAIL] Latency timeout!")
                break
    
    avg_lat = sum(latencies) / len(latencies)
    print(f" [INFO] Average Latency: {avg_lat:.2f} ms")

    # 2. High-Frequency Stress
    print("\nSTAGE 2: HIGH-FREQUENCY BURST (50 Cmds/sec)...")
    success = 0
    start_burst = time.time()
    for i in range(50):
        ser.write(f"S{i}\n".encode())
        # No delay - just pure flooding
    
    # Try to collect 50 ACKs
    timeout = time.time() + 2.0
    while success < 50 and time.time() < timeout:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if "[ACK]" in line:
            success += 1

    print(f" [RESULT] Processed {success}/50 commands under heavy load.")
    if success == 50:
        print(" [PASS] UART Tunnel is 100% stable under burst pressure.")
    else:
        print(" [FAIL] Tunnel dropped commands!")

    ser.close()

if __name__ == "__main__":
    run_performance_test()
