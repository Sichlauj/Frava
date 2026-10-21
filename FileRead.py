import os
import shutil
import subprocess
import sys
import argparse

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import fitdecode

# CSV_KEYS defines the fields to be included in the output csv. ig the ebike stuff can stay...
CSV_KEYS = [ "timestamp", "latitude", "longitude", "enhanced_altitude",
             "distance", "enhanced_speed", "power", "cadence",
             "motor_power", "ebike_assist_mode", "ebike_battery_level",
             "grade", "gps elevation", "smoothed elevation"
            ]

# Ensure GPSBabel is available for use
def find_gpsbabel():
    """Return the path to the gpsbabel executable if it is available."""
    candidates = []

    env_path = os.environ.get("GPSBABEL")
    if env_path:
        candidates.append(env_path)

    candidates.extend([
        shutil.which("gpsbabel"),
        os.path.join(sys.prefix, "Scripts", "gpsbabel.exe"),
        os.path.join(sys.prefix, "Scripts", "gpsbabel"),
        os.path.join(sys.prefix, "bin", "gpsbabel"),
        os.path.join(os.getcwd(), "gpsbabel.exe"),
        os.path.join(os.getcwd(), "gpsbabel"),
    ])

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return None

# This function reads a .fit file and exports the data to GPX and CSV files for processing, analysis and visualization.
def read_fit_file(filename, outgpxname=None, outcsvname=None):
    """Read a .fit file. Export to GPX and/or CSV files.
    """

    if outcsvname:
        outcsv = open(outcsvname, 'w')
        print(','.join(CSV_KEYS), file=outcsv)
    else:
        outcsv = None

    if outgpxname:
        gpsbabel = find_gpsbabel()
        if gpsbabel is None:
            print("Can't export GPX: gpsbabel is not installed or not reachable from this environment",
                  file=sys.stderr)
            outgpxname = None
        else:
            try:
                subprocess.run([gpsbabel,
                                "-i", "garmin_fit",
                                "-f", filename,
                                "-o", "gpx",
                                "-F", outgpxname],
                               check=True,
                               capture_output=True,
                               text=True)
            except subprocess.CalledProcessError as exc:
                print(f"gpsbabel failed to export GPX: {exc.stderr or exc}",
                      file=sys.stderr)
                outgpxname = None

    with fitdecode.FitReader(filename) as fit:
        for frame in fit:
            if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                if frame.name != 'record':
                    continue

                fields = {}
                for f in frame.fields:
                    fields[f.name] = f.value

                if outcsv:
                    print(','.join([ str(fields[key])
                                     if key in fields
                                     else ''
                                     for key in CSV_KEYS
                                    ]),
                          file=outcsv)

    if outcsv:
        outcsv.close()
        if os.path.exists(outcsvname):
            print("Saved CSV to", outcsvname)
        else:
            print("CSV not saved, womp womp")

    if outgpxname:
        if os.path.exists(outgpxname):
            print("Saved GPX to", outgpxname)
        else:
            print("GPX not saved, womp womp")
    else:
        print("Can't get to GPSBabel - no GPX")

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a .fit file and export to GPX and/or CSV files.")
    parser.add_argument("filename", help="Path to the .fit file to read.")
    parser.add_argument("--outcsv", help="Path to the output CSV file.", default=None)
    parser.add_argument("--outgpx", help="Path to the output GPX file.", default=None)
    return parser.parse_args()

if __name__ == '__main__':

    args = _parse_args()
    read_fit_file(args.filename, outcsvname=args.outcsv, outgpxname=args.outgpx)