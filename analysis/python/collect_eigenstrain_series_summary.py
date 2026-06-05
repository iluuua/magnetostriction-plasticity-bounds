#!/usr/bin/env python3

from pathlib import Path
import json
import re
import csv

ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = ROOT / "results/tables/ellipsoid_inclusion"

CASES = [
    ("epsz_p0p00100", 0.0010),
    ("epsz_p0p00250", 0.0025),
    ("epsz_p0p00500", 0.0050),
    ("epsz_p0p01000", 0.0100),
]

def read_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def parse_log(tag: str):
    log_path = ROOT / (
        f"lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/"
        f"{tag}_minimize/log.ellipsoid_eigenstrain_{tag}_minimize.lammps"
    )

    if not log_path.exists():
        return {
            "log_exists": False,
            "has_error_nan_lost_fatal": None,
            "has_total_wall_time": False,
            "dangerous_builds": None,
            "energy_initial_eV": None,
            "energy_final_eV": None,
            "force_two_norm_initial": None,
            "force_two_norm_final": None,
            "force_max_component_initial": None,
            "force_max_component_final": None,
            "iterations": None,
            "force_evaluations": None,
        }

    text = log_path.read_text(errors="replace")

    dangerous = re.findall(r"Dangerous builds =\s+(\d+)", text)

    energy = re.search(
        r"Energy initial, next-to-last, final =\s*\n\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)",
        text,
    )

    force_two = re.search(
        r"Force two-norm initial, final =\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)",
        text,
    )

    force_max = re.search(
        r"Force max component initial, final =\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)",
        text,
    )

    iters = re.search(
        r"Iterations, force evaluations =\s*(\d+)\s+(\d+)",
        text,
    )

    return {
        "log_exists": True,
        "has_error_nan_lost_fatal": bool(re.search(r"ERROR|nan|lost atoms|Fatal error", text, re.I)),
        "has_total_wall_time": "Total wall time" in text,
        "dangerous_builds": int(dangerous[-1]) if dangerous else None,
        "energy_initial_eV": float(energy.group(1)) if energy else None,
        "energy_final_eV": float(energy.group(3)) if energy else None,
        "force_two_norm_initial": float(force_two.group(1)) if force_two else None,
        "force_two_norm_final": float(force_two.group(2)) if force_two else None,
        "force_max_component_initial": float(force_max.group(1)) if force_max else None,
        "force_max_component_final": float(force_max.group(2)) if force_max else None,
        "iterations": int(iters.group(1)) if iters else None,
        "force_evaluations": int(iters.group(2)) if iters else None,
    }

rows = []

for tag, eps in CASES:
    build_report = ROOT / (
        f"structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/"
        f"{tag}/ellipsoid_eigenstrain_{tag}_build_report.json"
    )

    sanity_report = TABLE_DIR / (
        f"ellipsoid_trial_001_eigenstrain_{tag}_minimized_distance_report.json"
    )

    run_dir = ROOT / (
        f"lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/"
        f"{tag}_minimize"
    )

    data_file = run_dir / f"data.ellipsoid_eigenstrain_{tag}_minimized"
    final_dump = run_dir / f"dump.ellipsoid_eigenstrain_{tag}_minimized_final.lammpstrj"

    build = read_json(build_report)
    sanity = read_json(sanity_report)
    parsed_log = parse_log(tag)

    hard_pairs = sanity.get("pairs_below_1p8_A")
    has_error = parsed_log.get("has_error_nan_lost_fatal")
    has_wall_time = parsed_log.get("has_total_wall_time")
    data_ok = data_file.exists() and data_file.stat().st_size > 0
    dump_ok = final_dump.exists() and final_dump.stat().st_size > 0

    accepted_sanity = (
        hard_pairs == 0
        and has_error is False
        and has_wall_time is True
        and data_ok
        and dump_ok
    )

    rows.append({
        "tag": tag,
        "eps_z": eps,
        "build_min_pair_A": build.get("min_pair_distance_A"),
        "build_pairs_below_1p8": build.get("pairs_below_1p8_A"),
        "build_Al_Fe_below_2p1": build.get("Al_Fe_pairs_below_2p1_A"),
        "minimized_min_pair_A": sanity.get("min_pair_distance_A"),
        "minimized_pairs_below_1p8": sanity.get("pairs_below_1p8_A"),
        "minimized_Al_Fe_below_2p1": sanity.get("Al_Fe_pairs_below_2p1_A"),
        "safe_basic": sanity.get("safe_basic"),
        "data_exists": data_ok,
        "final_dump_exists": dump_ok,
        "accepted_script_sanity": accepted_sanity,
        **parsed_log,
    })

TABLE_DIR.mkdir(parents=True, exist_ok=True)

out_csv = TABLE_DIR / "ellipsoid_trial_001_eigenstrain_series_summary.csv"
with out_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved: {out_csv}")
print(json.dumps(rows, indent=2))
