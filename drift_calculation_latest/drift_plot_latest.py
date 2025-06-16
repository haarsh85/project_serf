import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

def parse_log_file(log_path):
    """Parse Serf drift log file into structured data"""
    data = []
    valid_count = 0
    invalid_count = 0

    with open(log_path, "r") as f:
        for line_number, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            
            # Skip empty lines and non-NODE_DRIFT entries
            if not line.startswith("NODE_DRIFT"):
                invalid_count += 1
                continue

            parts = line.split(",")
            
            # Validate line structure
            if len(parts) != 7:
                invalid_count += 1
                continue

            try:
                # Parse timestamp
                time_str = parts[1].split("=")[1].replace("Z", "+0000")
                parsed_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S%z")

                # Parse metrics
                entry = {
                    "time": parsed_time,
                    "node": parts[2].split("=")[1],
                    "vec_distance_ms": float(parts[3].split("=")[1]),
                    "total_drift_ms": float(parts[4].split("=")[1]),
                    "height": float(parts[5].split("=")[1]),
                    "adjustment": float(parts[6].split("=")[1]),
                }
                data.append(entry)
                valid_count += 1

            except Exception as e:
                invalid_count += 1
                continue

    print(f"Parsing complete - Valid: {valid_count}, Invalid: {invalid_count}")
    return pd.DataFrame(data)

def plot_drift_data(df):
    """Generate drift analysis plots"""
    # Aggregate data by time
    agg_df = df.groupby("time").agg({
        "vec_distance_ms": ["mean", "min", "max", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)],
        "total_drift_ms": ["mean", "min", "max", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
    })
    
    # Format column names
    agg_df.columns = [
        "vec_mean", "vec_min", "vec_max", "vec_p25", "vec_p75",
        "total_mean", "total_min", "total_max", "total_p25", "total_p75"
    ]

    # Create figure
    plt.figure(figsize=(14, 10))
    plt.suptitle("Serf Network Coordinate Drift Analysis", y=0.95)

    # Positional Drift Plot (Vec component)
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(agg_df.index, agg_df["vec_mean"], label="Average", color="blue")
    ax1.fill_between(agg_df.index, agg_df["vec_p25"], agg_df["vec_p75"], 
                    color="blue", alpha=0.15, label="IQR (25th-75th %)")
    ax1.plot(agg_df.index, agg_df["vec_max"], "--", color="blue", alpha=0.4, label="Max")
    ax1.plot(agg_df.index, agg_df["vec_min"], "--", color="blue", alpha=0.4, label="Min")
    ax1.set_ylabel("Positional Drift (ms)\n(Euclidean Norm of Vec)")
    ax1.legend()
    ax1.grid(True)

    # Total Drift Plot (Vec + Height + Adjustment)
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.plot(agg_df.index, agg_df["total_mean"], label="Average", color="orange")
    ax2.fill_between(agg_df.index, agg_df["total_p25"], agg_df["total_p75"],
                    color="orange", alpha=0.15, label="IQR (25th-75th %)")
    ax2.plot(agg_df.index, agg_df["total_max"], "--", color="orange", alpha=0.4, label="Max")
    ax2.plot(agg_df.index, agg_df["total_min"], "--", color="orange", alpha=0.4, label="Min")
    ax2.set_xlabel("Time (UTC)")
    ax2.set_ylabel("Total Drift (ms)\n(Vec + Height + Adjustment)")
    ax2.legend()
    ax2.grid(True)

    # Format x-axis
    for ax in [ax1, ax2]:
        # Major ticks: Midnight with date
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0]))  # Midnight
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%Y-%m-%d"))  

        # Minor ticks: Every 3 hours (time only)
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 3)))  
        ax.xaxis.set_minor_formatter(mdates.DateFormatter("%H:%M"))  

        # Rotate and align labels
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")  # Centered and horizontal
        plt.setp(ax.xaxis.get_minorticklabels(), rotation=0, ha="center")  

        # Adjust label positions
        ax.xaxis.set_tick_params(which="major", pad=15)  # Spacing for two-line labels

    plt.tight_layout()
    plt.savefig("drift_analysis.png", dpi=300, bbox_inches="tight")
    print("Plot saved as drift_analysis.png")


if __name__ == "__main__":
    # Configuration
    LOG_FILE = "drift.log"
    
    # Parse and validate log data
    df = parse_log_file(LOG_FILE)
    
    if df.empty:
        print(f"No valid data found in {LOG_FILE}")
        exit(1)
        
    print("\nFirst 3 entries:")
    print(df.head(3))
    
    # Generate plots
    plot_drift_data(df)