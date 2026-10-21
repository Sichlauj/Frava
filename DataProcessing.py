import os
import shutil
import subprocess
import sys
import argparse

import folium
import seaborn as sns
import matplotlib.dates as mdates
import webbrowser

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gpxplotter import read_gpx_file, create_folium_map, add_segment_to_map

from FileRead import read_fit_file

def Summary_Data():
    # Extract key data from CSV for summary stats
    fish = 1

def smooth(signal, points):
    # Smooth the given signal using a rectangular window."""
    window = np.ones(points) / points
    return np.convolve(signal, window, mode="same")

def GPX_map(gpx_path):
    # Simple plot of GPX activity on map
    route_points = []

    for track in read_gpx_file(gpx_path):
        for segment in track.get("segments", []):
            if not isinstance(segment, dict):
                continue

            lats = segment.get("lat", [])
            lons = segment.get("lon", [])
            if (len(lats) == 0) and (len(lons) == 0):
                continue

            for lat, lon in zip(lats, lons):
                if lat is not None and lon is not None:
                    route_points.append([float(lat), float(lon)])

    if not route_points:
        raise ValueError(f"No coordinate data found in {gpx_path}")

    center_lat = sum(point[0] for point in route_points) / len(route_points)
    center_lon = sum(point[1] for point in route_points) / len(route_points)

    activity_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri",
        control_scale=True,
    )

    folium.PolyLine(
        route_points,
        color="blue",
        weight=4,
        opacity=0.9,
    ).add_to(activity_map)

    if len(route_points) > 1:
        activity_map.fit_bounds([route_points[0], route_points[-1]])

    out_html = os.path.splitext(gpx_path)[0] + "_map.html"
    activity_map.save(out_html)
    print(f"Saved map to {out_html}")
    return activity_map

def plot_GPX_basic(gpx_path):
    sns.set_context("notebook")
    colors = sns.color_palette()

    merged_x = []
    merged_y = []
    merged_hr = []
    merged_power = []
    merged_vel = []
    cumulative_distance_m = 0.0

    for track in read_gpx_file(gpx_path):
        for segment in track.get("segments", []):
            if not isinstance(segment, dict):
                continue

            distance = np.asarray(segment.get("distance", segment.get("Distance / km", [])), dtype=float)
            elevation = np.asarray(segment.get("elevation", segment.get("ele", [])), dtype=float)
            heart = np.asarray(segment.get("hr", []), dtype=float)
            power = np.asarray(segment.get("power", []), dtype=float)
            velocity = np.asarray(segment.get("velocity", []), dtype=float)

            if distance.size == 0 and elevation.size == 0:
                continue

            if distance.size and distance[0] <= cumulative_distance_m:
                distance = distance + cumulative_distance_m

            if distance.size:
                merged_x.extend((distance / 1000.0).tolist())
                cumulative_distance_m = float(distance[-1])
            elif elevation.size:
                merged_x.extend(np.arange(elevation.size, dtype=float).tolist())

            if elevation.size:
                merged_y.extend(elevation.tolist())

            if heart.size:
                merged_hr.extend(heart.tolist())

            if power.size:
                merged_power.extend(power.tolist())

            if velocity.size:
                merged_vel.extend(velocity.tolist())

    if not merged_x:
        print(f"No GPX track data found in {gpx_path}")
        return

    fig, ax1 = plt.subplots(constrained_layout=True, figsize=(8, 4))
    (line1,) = ax1.plot(merged_x, merged_y, lw=3, color=colors[0])
    ax1.fill_between(merged_x, merged_y, y2=min(merged_y), alpha=0.1)
    ax1.set(xlabel="Distance / km", ylabel="Elevation")

    ax2 = None
    line2 = None
    if merged_hr:
        ax2 = ax1.twinx()
        heart = smooth(np.asarray(merged_hr, dtype=float), 51)
        (line2,) = ax2.plot(merged_x, heart, color=colors[1], alpha=0.8, lw=3)
        ax2.set_ylim(0, 200)
        ax2.set(ylabel="Heart rate / bpm")

    ax3 = None
    line3 = None
    if merged_power:
        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("axes", 1.2))
        power = smooth(np.asarray(merged_power, dtype=float), 51)
        (line3,) = ax3.plot(merged_x, power, color=colors[2], alpha=0.8, lw=3)
        ax3.set(ylabel="Power / W")

    ax4 = None
    line4 = None
    if merged_vel:
        ax4 = ax1.twinx()
        ax4.spines["right"].set_position(("axes", 1.8))
        vel = 3.6 * smooth(np.asarray(merged_vel, dtype=float), 51)
        (line4,) = ax4.plot(merged_x, vel, alpha=0.8, color=colors[3], lw=3)
        ax4.set(ylabel="Velocity / km/h")
        ax4.set_ylim(0, 20)

    axes = [ax1]
    lines = [line1]
    if ax2 is not None and line2 is not None:
        axes.append(ax2)
        lines.append(line2)
    if ax3 is not None and line3 is not None:
        axes.append(ax3)
        lines.append(line3)
    if ax4 is not None and line4 is not None:
        axes.append(ax4)
        lines.append(line4)

    for axi, linei in zip(axes, lines):
        axi.yaxis.label.set_color(linei.get_color())
        axi.tick_params(axis="y", colors=linei.get_color())
        key = "right" if axi != ax1 else "left"
        axi.spines[key].set_edgecolor(linei.get_color())
        axi.spines[key].set_linewidth(2)

    ax1.spines["top"].set_visible(False)

    for axi in (ax2, ax3, ax4):
        if axi is None:
            continue
        for key in axi.spines:
            axi.spines[key].set_visible(False)
        axi.spines["right"].set_visible(True)

    handles = [line1]
    labels = ["Elevation"]
    if line2 is not None:
        handles.append(line2)
        labels.append("Heart rate")
    if line3 is not None:
        handles.append(line3)
        labels.append("Power")
    if line4 is not None:
        handles.append(line4)
        labels.append("Velocity")

    if len(handles) > 1:
        ax1.legend(handles, labels, loc="upper left", frameon=True)

    # plt.show()

def clean_activity_data(csv_file_path):
    # Clean up activity data by binning into 10-second intervals and reducing number of fields

    df = pd.read_csv(csv_file_path)
    if "timestamp" not in df.columns:
        raise ValueError(f"CSV {csv_file_path} does not contain a 'timestamp' column")

    time_col = "timestamp"
    speed_col = "enhanced_speed" if "enhanced_speed" in df.columns else "speed" if "speed" in df.columns else None
    distance_col = "distance" if "distance" in df.columns else None
    elevation_col = (
        "enhanced_altitude"
        if "enhanced_altitude" in df.columns
        else "gps elevation"
        if "gps elevation" in df.columns
        else "smoothed elevation"
        if "smoothed elevation" in df.columns
        else "elevation"
        if "elevation" in df.columns
        else None
    )

    if speed_col is None or distance_col is None or elevation_col is None:
        missing = []
        if speed_col is None:
            missing.append("speed")
        if distance_col is None:
            missing.append("distance")
        if elevation_col is None:
            missing.append("elevation")
        raise ValueError(f"CSV does not contain the required analysis columns: {missing}")

    df = df[[time_col, speed_col, distance_col, elevation_col]].copy()
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)

    if df.empty:
        return pd.DataFrame(columns=["speed", "distance", "elevation"]) 

    df[speed_col] = pd.to_numeric(df[speed_col], errors="coerce")
    df[distance_col] = pd.to_numeric(df[distance_col], errors="coerce")
    df[elevation_col] = pd.to_numeric(df[elevation_col], errors="coerce")

    df["bucket"] = df[time_col].dt.floor("10s")

    bucket_summary = (
        df.groupby("bucket", as_index=False)
        .agg(
            speed=(speed_col, "mean"),
            distance=(distance_col, "last"),
            elevation=(elevation_col, "mean"),
        )
    )

    full_range = pd.date_range(
        start=bucket_summary["bucket"].min(),
        end=bucket_summary["bucket"].max(),
        freq="10s",
        tz="UTC",
    )
    clean_df = bucket_summary.set_index("bucket").reindex(full_range).reset_index(drop=True)
    clean_df = clean_df.rename_axis(None)

    clean_df["speed"] = pd.to_numeric(clean_df["speed"], errors="coerce").fillna(0.0)
    clean_df["distance"] = pd.to_numeric(clean_df["distance"], errors="coerce").ffill().fillna(0.0)
    clean_df["elevation"] = pd.to_numeric(clean_df["elevation"], errors="coerce").ffill().bfill()

    return clean_df[["speed", "distance", "elevation"]].reset_index(drop=True)


def build_dashboard(activity_stats, gpx_path):
    # Brief summary of some of the stats strava won't tell you
    if isinstance(activity_stats, str):
        activity_stats = pd.read_csv(activity_stats)

    activity_stats = activity_stats.copy()
    if "speed" not in activity_stats.columns:
        raise ValueError("activity_stats must include a 'speed' column")
    if "elevation" not in activity_stats.columns:
        raise ValueError("activity_stats must include an 'elevation' column")
    if "distance" not in activity_stats.columns:
        raise ValueError("activity_stats must include a 'distance' column")

    distance_series = pd.to_numeric(activity_stats["distance"], errors="coerce").fillna(0.0)
    total_distance_m = float(distance_series.max() - distance_series.min()) if len(distance_series) > 0 else 0.0
    avg_speed_mps = float(activity_stats["speed"].mean())
    max_speed_mps = float(activity_stats["speed"].max())
    avg_speed_kmh = 3.6 * avg_speed_mps
    max_speed_kmh = 3.6 * max_speed_mps

    elevation = pd.to_numeric(activity_stats["elevation"], errors="coerce").ffill().fillna(0.0)
    gain = elevation.diff().fillna(0.0).clip(lower=0).sum()
    avg_grade = 100.0 * (gain / max(total_distance_m, 1.0)) if total_distance_m > 0 else 0.0

    speeds = pd.to_numeric(activity_stats["speed"], errors="coerce").fillna(0.0)
    speed_change = speeds.diff().abs()
    relative_change = speed_change / speeds.shift(1).abs().replace(0, np.nan)
    relative_change = relative_change.fillna(0.0)
    accel_events = int((relative_change > 0.10).sum())

    elevation_delta = elevation.diff().fillna(0.0)
    rise_mask = elevation_delta > 0
    climb_starts = []
    for i in range(len(elevation_delta) - 5):
        window = elevation_delta.iloc[i:i+6]
        total_gain = float(window.sum())
        gain_count = int((window > 0).sum())
        if gain_count >= 6 and total_gain >= 24.384:
            climb_starts.append(i)
    for i in range(len(elevation_delta) - 9):
        window = elevation_delta.iloc[i:i+10]
        total_gain = float(window.sum())
        gain_count = int((window > 0).sum())
        if gain_count >= 9 and total_gain >= 24.384:
            climb_starts.append(i)

    if climb_starts:
        unique_starts = sorted(set(climb_starts))
        valid_ranges = []
        last = -10
        for start in unique_starts:
            if start > last + 5:
                valid_ranges.append(start)
                last = start
        climb_count = len(valid_ranges)
    else:
        climb_count = 0
        valid_ranges = []

    if os.path.exists(gpx_path):
        map_obj = GPX_map(gpx_path)
        map_name = os.path.splitext(gpx_path)[0] + "_map.html"
    else:
        map_obj = None
        map_name = ""

    plot_png = os.path.splitext(gpx_path)[0] + "_summary.png"
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    x = np.arange(len(activity_stats))
    axes[0].plot(x, activity_stats["speed"], color="tab:blue", lw=2)
    axes[0].set_ylabel("Speed (m/s)")
    axes[0].set_title("Speed / Elevation")
    ax2 = axes[0].twinx()
    ax2.plot(x, elevation, color="tab:green", lw=2)
    ax2.set_ylabel("Elevation (m)")

    if "hr" in activity_stats.columns:
        axes[1].plot(x, activity_stats["hr"], color="tab:orange", lw=2, label="HR")
        axes[1].set_ylabel("Heart rate")
    if "power" in activity_stats.columns:
        axp = axes[1].twinx()
        axp.plot(x, activity_stats["power"], color="tab:red", lw=2, label="Power")
        axp.set_ylabel("Power")
    if "hr" not in activity_stats.columns and "power" not in activity_stats.columns:
        axes[1].plot(x, activity_stats["speed"], color="tab:purple", lw=2)
        axes[1].set_ylabel("Speed (m/s)")
    axes[1].set_xlabel("10-second blocks")
    fig.savefig(plot_png, dpi=150)
    plt.close(fig)

    raw_csv = os.path.splitext(gpx_path)[0] + ".csv"
    hr_series = None
    if os.path.exists(raw_csv):
        try:
            raw_df = pd.read_csv(raw_csv)
            for key in ("heart_rate", "hr", "Heart Rate", "average_heart_rate"):
                if key in raw_df.columns:
                    hr_series = pd.to_numeric(raw_df[key], errors="coerce")
                    break
        except Exception:
            hr_series = None

    climb_hr = np.nan
    if hr_series is not None and valid_ranges:
        idxs = []
        for start in valid_ranges:
            idxs.extend(range(start, min(start + 6, len(elevation_delta))))
        if idxs:
            climb_hr = float(np.nanmean(hr_series.iloc[idxs])) if len(idxs) else np.nan

    summary_rows = [
        ("Average speed", f"{avg_speed_kmh:.2f} km/h"),
        ("Max speed", f"{max_speed_kmh:.2f} km/h"),
        ("Distance", f"{total_distance_m / 1000.0:.2f} km"),
        ("Elevation gain", f"{gain * 3.28084:.1f} ft"),
        ("Average grade", f"{avg_grade:.2f}%"),
    ]

    detail_rows = [
        ("Acceleration events (>10% step)", f"{accel_events}"),
        ("Climbs", f"{climb_count}"),
        ("Climbing HR", f"{climb_hr:.1f} bpm" if pd.notna(climb_hr) else "n/a"),
    ]

    summary_html = "<table><tr><th>Metric</th><th>Value</th></tr>" + "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in summary_rows
    ) + "</table>"
    detail_html = "<table><tr><th>Metric</th><th>Value</th></tr>" + "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in detail_rows
    ) + "</table>"

    if map_name:
        map_html = f'<iframe src="{os.path.basename(map_name)}" width="100%" height="420" style="border:none"></iframe>'
    else:
        map_html = "<p>No map data available.</p>"

    plot_html = f'<img src="{os.path.basename(plot_png)}" style="width:100%; max-height:420px; object-fit:contain;" />'

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Activity Dashboard</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; background: #f4f6f8; color: #1f2937; }}
          h1 {{ margin-bottom: 8px; }}
          .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
          .panel {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
          table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
          th, td {{ border: 1px solid #dfe4ea; padding: 8px 10px; text-align: left; }}
          th {{ background: #eef2ff; }}
          iframe {{ width: 100%; border: 0; border-radius: 8px; }}
          img {{ width: 100%; border-radius: 8px; }}
        </style>
      </head>
      <body>
        <h1>Activity Dashboard</h1>
        <div class="grid">
          <div class="panel">
            <h2>1. Map of the activity</h2>
            {map_html}
          </div>
          <div class="panel">
            <h2>2. Speed / Elevation / HR / Power plot</h2>
            {plot_html}
          </div>
          <div class="panel">
            <h2>3. Summary metrics</h2>
            {summary_html}
          </div>
          <div class="panel">
            <h2>4. Detailed stats</h2>
            {detail_html}
          </div>
        </div>
      </body>
    </html>
    """

    dashboard_path = os.path.splitext(gpx_path)[0] + "_dashboard.html"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)

    webbrowser.open_new_tab(dashboard_path)

    print(f"Saved dashboard to {dashboard_path}")
    return dashboard_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read fit file breakdown outputs and prepare data for analysis")
    parser.add_argument("--fit", help="Path to the input .fit file. If provided, CSV and GPX are generated automatically from this file.", default=None)
    parser.add_argument("--incsv", help="Path to the input CSV file. Used only when --fit is not provided.", default=None)
    parser.add_argument("--ingpx", help="Path to the input GPX file. Used only when --fit is not provided.", default=None)
    return parser.parse_args()

if __name__ == '__main__':
    args = _parse_args()

    if args.fit is not None:
        fit_path = os.path.abspath(args.fit)
        if not os.path.exists(fit_path):
            raise FileNotFoundError(f"FIT file not found: {fit_path}")

        base_dir = os.path.dirname(fit_path)
        base_name = os.path.splitext(os.path.basename(fit_path))[0]
        csv_path = os.path.join(base_dir, f"{base_name}.csv")
        gpx_path = os.path.join(base_dir, f"{base_name}.gpx")

        file_read_script = os.path.join(os.path.dirname(__file__), "FileRead.py")
        subprocess.run(
            [sys.executable, file_read_script, fit_path, "--outcsv", csv_path, "--outgpx", gpx_path],
            check=True,
        )
        in_csv = csv_path
        in_gpx = gpx_path
    else:
        in_csv = args.incsv
        in_gpx = args.ingpx

        if not in_csv or not os.path.exists(in_csv):
            raise FileNotFoundError(f"CSV file not found: {in_csv}")
        if not in_gpx or not os.path.exists(in_gpx):
            raise FileNotFoundError(f"GPX file not found: {in_gpx}")

    activity_stats = clean_activity_data(in_csv)
    activity_stats.to_csv("simplified_activity_data.csv", index=False)

    plot_GPX_basic(in_gpx)
    build_dashboard(activity_stats, in_gpx)
