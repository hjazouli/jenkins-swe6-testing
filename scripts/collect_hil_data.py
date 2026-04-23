import time
from tests.bridge.hardware_bridge import HardwareBridge

def collect_data():
    hb = HardwareBridge()
    try:
        print("Starting 10-second Data Collection...")
        # Simulate a drive cycle
        for i in range(10):
            speed = i * 15
            pedal = 100 - (i * 10)
            hb.set_speed(float(speed))
            hb.set_pedal(float(pedal))
            hb.set_wear(float(i * 5))
            
            print(f"Cycle {i+1}/10: Speed={speed}, Pedal={pedal}")
            time.sleep(1.0) # Wait for heartbeat
            
        print(f"Done! Trace saved to: {hb.trace_filename}")
        return hb.trace_filename
    finally:
        hb.close()

if __name__ == "__main__":
    trace_file = collect_data()
    print(f"\nNow run: ./.venv/bin/python3 scripts/generate_hil_plot.py {trace_file}")
