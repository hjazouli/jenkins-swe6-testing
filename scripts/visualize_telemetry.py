import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import sys

def get_latest_session():
    sessions = glob.glob("test_results/session_*")
    if not sessions:
        return None
    return max(sessions, key=os.path.getmtime)

def plot_csv(csv_path, output_dir):
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    filename = os.path.basename(csv_path).replace(".csv", ".png")
    
    # Create the Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    
    # Subplot 1: Pressures and Pedal
    ax1.plot(df.index, df['Pedal_pct'], label='Pedal (%)', color='gray', linestyle='--')
    ax1.plot(df.index, df['Front_bar'], label='Front (Bar)', color='blue', linewidth=2)
    ax1.plot(df.index, df['Rear_bar'], label='Rear (Bar)', color='red', linewidth=2)
    ax1.set_ylabel("Pressure / Force")
    ax1.set_title(f"Test Case: {filename}")
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Speed and Status
    ax2.plot(df.index, df['Speed_kmh'], label='Speed (km/h)', color='green', linewidth=2)
    ax2.set_ylabel("Speed")
    ax2.set_xlabel("Time (Frames)")
    
    # Overlay Brake Light status
    ax2_twin = ax2.twinx()
    ax2_twin.fill_between(df.index, 0, df['Lights'], alpha=0.2, color='orange', label='Brake Lights')
    ax2_twin.set_yticks([])
    
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename))
    plt.close(fig)

def plot_session(session_path):
    csv_files = glob.glob(os.path.join(session_path, "*.csv"))
    if not csv_files:
        print(f"No CSV files found in {session_path}")
        return

    # Create a subfolder for plots to keep things tidy
    plot_dir = os.path.join(session_path, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    print(f"Generating {len(csv_files)} individual plots...")
    for f in sorted(csv_files):
        plot_csv(f, plot_dir)
    
    print(f"\nSUCCESS: All individual graphs generated in {plot_dir}")

if __name__ == "__main__":
    latest = get_latest_session()
    if latest:
        print(f"Analyzing latest session: {latest}")
        plot_session(latest)
    else:
        print("No test sessions found in test_results/")
