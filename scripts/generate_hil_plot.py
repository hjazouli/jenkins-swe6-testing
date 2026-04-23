import sys
import os
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def parse_hil_log(filepath):
    data = []
    
    # Pattern to match telemetry: [BCM-V101] T:1657000 P:0 S:0 W:0 F:0 R:0 Lights:OFF FLAG:96
    pattern = re.compile(r"T:(?P<tick>\d+)\s+P:(?P<pedal>\d+)\s+S:(?P<speed>\d+)\s+W:(?P<wear>\d+)\s+F:(?P<front>\d+)\s+R:(?P<rear>\d+)\s+(?:L|Lights):(?P<lights>\w+)\s+FLAG:(?P<flag>\d+)")

    with open(filepath, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                entry = match.groupdict()
                # Convert numeric values
                entry['tick'] = int(entry['tick'])
                entry['pedal'] = int(entry['pedal'])
                entry['speed'] = int(entry['speed'])
                entry['wear'] = int(entry['wear'])
                entry['front'] = int(entry['front'])
                entry['rear'] = int(entry['rear'])
                entry['flag'] = int(entry['flag'])
                
                # Relative time in seconds (T: is usually in ms or 10ms units based on SysTick)
                # Assuming 1ms SysTick based on BCM_Periodic_Task
                entry['time_sec'] = entry['tick'] / 1000.0
                
                data.append(entry)
                
    print(f"DEBUG: Found {len(data)} telemetry entries.")
    return pd.DataFrame(data)

def generate_plots(df, output_name):
    if df.empty:
        print("No telemetry data found in log.")
        return

    # Normalize time to start at 0
    df['time_sec'] = df['time_sec'] - df['time_sec'].iloc[0]

    # Create Figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"BCM HIL Validation Report - {output_name}", fontsize=16, fontweight='bold')

    # Subplot 1: Inputs & Speed
    ax1.plot(df['time_sec'], df['pedal'], label='Pedal Force (%)', color='#2ecc71', linewidth=2)
    ax1.plot(df['time_sec'], df['speed'], label='Vehicle Speed (km/h)', color='#3498db', linestyle='--')
    ax1.plot(df['time_sec'], df['wear'], label='Brake Wear (%)', color='#e67e22')
    ax1.set_ylabel("Input Values")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    ax1.set_title("System Stimulus")

    # Subplot 2: Hydraulic Output & Flags
    ax2.plot(df['time_sec'], df['front'], label='Front Pressure (Bar)', color='#e74c3c', linewidth=2)
    ax2.plot(df['time_sec'], df['rear'], label='Rear Pressure (Bar)', color='#c0392b', linestyle='-.')
    ax2.set_ylabel("Hydraulic Output")
    ax2.set_xlabel("Time (Seconds - ECU Relative)")
    
    # Twin axis for Status Flags
    ax3 = ax2.twinx()
    ax3.step(df['time_sec'], df['flag'], label='Status Flag (Raw)', color='#9b59b6', where='post', alpha=0.5)
    ax3.set_ylabel("Binary Flags (Bitmask)")
    
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left')
    ax3.legend(loc='upper right')
    ax2.set_title("System Response & Safety Flags")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    report_path = f"{output_name}_report.png"
    plt.savefig(report_path, dpi=300)
    print(f"Visualization saved to: {report_path}")
    return report_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_hil_plot.py <trace_file.log>")
        sys.exit(1)
        
    log_file = sys.argv[1]
    name = os.path.splitext(os.path.basename(log_file))[0]
    
    df = parse_hil_log(log_file)
    generate_plots(df, name)
