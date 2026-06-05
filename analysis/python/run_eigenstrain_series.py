#!/usr/bin/env python3

from pathlib import Path
import subprocess
import json
import re
import csv
import shutil

ROOT = Path(__file__).resolve().parents[2]

STRAINS = [
    ("epsz_p0p00100", "0.0010"),
    ("epsz_p0p00500", "0.0050"),
    ("epsz_p0p01000", "0.0100"),
]

POT_MEAMF = "../../../../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf"
POT_PARAM = "../../../../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe"

RUN_ROOT = ROOT / "lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax"
TABLE_DIR = ROOT / "results/tables/ellipsoid_inclusion"
TABLE_DIR.mkdir(parents=True, exist_ok=True)

def run(cmd, cwd=None):
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)

def make_input(tag):
    run_dir = RUN_ROOT / f"{tag}_minimize"
    run_dir.mkdir(parents=True, exist_ok=True)

    input_path = run_dir / f"in.ellipsoid_eigenstrain_{tag}_minimize"

    input_path.write_text(f"""units           metal
dimension       3
boundary        p p p
atom_style      atomic

read_data       ../../../../../structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/{tag}/data.ellipsoid_eigenstrain_{tag}

mass            1 26.9815385
mass            2 55.845

pair_style      meam
pair_coeff      * * {POT_MEAMF} AlS SiS MgS CuS FeS {POT_PARAM} AlS FeS

neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes

compute         pe_atom all pe/atom
compute         stress_atom all stress/atom NULL

thermo          100
thermo_style    custom step atoms temp pe etotal press pxx pyy pzz lx ly lz
thermo_modify   lost warn flush yes

dump            d0 all custom 100 dump.ellipsoid_eigenstrain_{tag}_minimize.lammpstrj id type x y z c_pe_atom c_stress_atom[1] c_stress_atom[2] c_stress_atom[3]
dump_modify     d0 sort id

run             0

min_style       cg
minimize        1.0e-8 1.0e-10 10000 100000

write_data      data.ellipsoid_eigenstrain_{tag}_minimized
write_dump      all custom dump.ellipsoid_eigenstrain_{tag}_minimized_final.lammpstrj id type x y z modify sort id

undump          d0
""")

    return run_dir, input_path

def parse_log(tag, run_dir):
    log_path = run_dir / f"log.ellipsoid_eigenstrain_{tag}_minimize.lammps"
    text = log_path.read_text(errors="replace")

    if re.search(r"ERROR|nan|lost atoms|Fatal error", text, re.IGNORECASE):
        status = "failed"
    else:
        status = "completed"

    danger = re.findall(r"Dangerous builds =\s+(\d+)", text)
    dangerous_builds = int(danger[-1]) if danger else None

    energy_final = None
    m = re.search(r"Energy initial, next-to-last, final =\s*\n\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)\s+([-\d.Ee+]+)", text)
    if m:
        energy_final = float(m.group(3))

    force_two_norm_final = None
    force_max_final = None

    m2 = re.search(r"Force two-norm initial, final =\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)", text)
    if m2:
        force_two_norm_final = float(m2.group(2))

    m3 = re.search(r"Force max component initial, final =\s*([-\d.Ee+]+)\s+([-\d.Ee+]+)", text)
    if m3:
        force_max_final = float(m3.group(2))

    return {
        "status": status,
        "dangerous_builds": dangerous_builds,
        "energy_final_eV": energy_final,
        "force_two_norm_final": force_two_norm_final,
        "force_max_component_final": force_max_final,
    }

def main():
    rows = []

    for tag, eps in STRAINS:
        print(f"\n=== {tag} / eps_z={eps} ===")

        run(["python", "analysis/python/apply_ellipsoid_eigenstrain.py", eps], cwd=ROOT)

        build_report = ROOT / f"structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/{tag}/ellipsoid_eigenstrain_{tag}_build_report.json"
        build = json.loads(build_report.read_text())

        if not build.get("safe_basic"):
            raise RuntimeError(f"{tag}: build safe_basic=false, stop before LAMMPS")

        run_dir, input_path = make_input(tag)

        for pattern in [
            "log.lammps",
            f"log.ellipsoid_eigenstrain_{tag}_minimize.lammps",
            f"dump.ellipsoid_eigenstrain_{tag}_minimize.lammpstrj",
            f"dump.ellipsoid_eigenstrain_{tag}_minimized_final.lammpstrj",
            f"data.ellipsoid_eigenstrain_{tag}_minimized",
        ]:
            p = run_dir / pattern
            if p.exists():
                p.unlink()

        run([
            "lmp",
            "-log", f"log.ellipsoid_eigenstrain_{tag}_minimize.lammps",
            "-in", input_path.name,
        ], cwd=run_dir)

        run(["python", "analysis/python/check_eigenstrain_minimized_sanity.py", tag], cwd=ROOT)
        run(["python", "analysis/python/make_eigenstrain_visual_debug.py", tag], cwd=ROOT)

        sanity_path = TABLE_DIR / f"ellipsoid_trial_001_eigenstrain_{tag}_minimized_distance_report.json"
        sanity = json.loads(sanity_path.read_text())
        parsed = parse_log(tag, run_dir)

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
            **parsed,
        })

    out_csv = TABLE_DIR / "ellipsoid_trial_001_eigenstrain_series_summary.csv"
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved summary: {out_csv}")
    print(json.dumps(rows, indent=2))

if __name__ == "__main__":
    main()
