#!/usr/bin/env python3
"""Records of the runs that answer "elastic or plastic", for docs/reports.

  embedded_peierls.json      straight edge dislocation without an inclusion:
                             sweep.json of embedded_sweep.py -> stress peaks before
                             each jump (the lattice resistance), valley spacing, DXA
  embedded_disl_states.json  dislocation above the inclusion: states.json of
                             embedded_disl_states.py plus the slab geometry, the
                             relaxation logs and the block stresses at zero load
  embedded_margin.json       cells with 4 and 10 times the strain: dxa.json of
                             embedded_dxa.py and the fields field_x4/x10.json of
                             embedded_inclusion_field.py against the field at eps

    python analysis/python/embedded_records.py --peierls runs/.../peierls \
        --disl runs/.../disl_dx15 --margin runs/.../margin --out-dir docs/reports
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPORTS = Path(__file__).resolve().parents[2] / "docs" / "reports"


def rel(p: Path) -> str:
    return p.as_posix().split("physics_md_al_fe/")[-1]


def peierls(run: Path) -> dict:
    d = json.loads((run / "sweep.json").read_text(encoding="utf-8"))
    c = d["control"]
    t, x = np.array(c["tau_MPa"]), np.array(c["x_line_A"])
    pk = [i for i in range(2, len(t) - 1) if t[i] > t[i - 1] and t[i] > t[i + 1]]
    after = [i + 1 for i in pk]
    return {"what": "straight edge dislocation, MEAM (Jelinek 2012) Al slab, T = 0, strain-controlled quasi-static sweep",
            "run_dir": rel(run), "delta_A": d["delta_A"],
            "sign_convention": "tau is the applied sigma_xz = -(top + bottom block reactions)/2",
            "peak_steps": pk, "peak_tau_MPa": t[pk].round(2).tolist(),
            "peierls_stress_MPa": round(float(t[pk].mean()), 2),
            "valley_positions_after_jumps_A": x[after].round(2).tolist(),
            "valley_spacing_A": np.diff(x[[1] + after]).round(2).tolist(),
            "valley_spacing_expected_A": round(d["burgers_A"] / 2, 3),
            "top_bottom_difference_max_MPa": round(c["top_bottom_difference_max_MPa"], 2),
            "dxa_mean_core_x_A": {k: round(float(np.mean(v)), 2) for k, v in d.get("dxa_line_x_A", {}).items()},
            "inferred_x_A_at_dxa_steps": {k: round(float(x[int(k)]), 2) for k in d.get("dxa_line_x_A", {})},
            "dxa_partials_per_dump": {k: len(v) for k, v in d.get("dxa_line_x_A", {}).items()}}


def disl_states(run: Path) -> dict:
    st = json.loads((run / "states.json").read_text(encoding="utf-8"))
    meta = json.loads(next(run.glob("*_metadata.json")).read_text(encoding="utf-8"))
    sph = meta["sphere"]
    st["run_dir"] = rel(run)
    st["x_core_built_A"] = meta["x_core_initial_A"]
    st["sphere_centre_x_A"] = sph["centre_A"][0]
    st["glide_plane_above_sphere_top_A"] = meta["z_glide_A"] - (sph["centre_A"][2] + sph["radius_A"])
    st["ctl_core_shift_from_built_A"] = st["states"]["ctl"]["core_x_A"] - meta["x_core_initial_A"]
    st["relaxation_log_lines"] = {
        c: [l for l in (run / f"log.{c}_relax").read_text(encoding="utf-8", errors="replace").splitlines()
            if l.startswith(("CHUNK", "ZFIX"))] for c in ("ctl", "fld", "rev")}
    step0 = [l.split() for l in (run / "log.ctl.sweep").read_text(encoding="utf-8", errors="replace").splitlines()
             if l.startswith("STEP 0 ")]
    if step0:
        st["ctl_block_stress_at_zero_load_MPa"] = {"top": -float(step0[0][3]), "bottom": -float(step0[0][5])}
    return st


def margin(run: Path, field_1x: Path) -> dict:
    f1 = json.loads(field_1x.read_text(encoding="utf-8"))["linear"]
    dx = json.loads((run / "dxa.json").read_text(encoding="utf-8"))["cases"]
    out = {"run_dir": rel(run), "cases": {}}
    for c, mult in (("x4", 4), ("x10", 10)):
        f = json.loads((run / f"field_{c}.json").read_text(encoding="utf-8"))["profiles"]
        rat = []
        for name, key in (("pole", "srr"), ("equator", "srr"), ("lobe25", "s_axial_shear"),
                          ("lobe67", "s_axial_shear")):
            for r1, rx in zip(f1[name], f[name]):
                if 5 <= r1["d_A"] <= 30 and abs(r1[key]) >= 5:
                    rat.append(rx[key] / mult / r1[key])
        lobes = f["lobe25"] + f["lobe67"]
        far = dx[c][0]["matrix_shells"]["d>=6"]
        case = {"strain_percent": 0.194 * mult,
                "dxa_segments": [r["n_segments"] for r in dx[c]],
                "matrix_nonfcc_beyond_6A": far["n_atoms"] - far["by_structure"].get("FCC", 0),
                "field_over_multiple_of_1x": {"median": float(np.median(rat)), "min": float(min(rat)),
                                              "max": float(max(rat))},
                "max_lobe_shear_MPa_d5_10": max(abs(r["s_axial_shear"]) for r in lobes if 5 <= r["d_A"] <= 10),
                "max_lobe_shear_MPa_any": max(abs(r["s_axial_shear"]) for r in lobes),
                "max_von_mises_MPa_any": max(r["von_mises"] for n in f for r in f[n])}
        for line in (run / f"log.{c}").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("CHUNK B"):
                case["final_fnorm"] = float(line.split()[-1])
        out["cases"][c] = case
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--peierls", type=Path)
    ap.add_argument("--disl", type=Path)
    ap.add_argument("--margin", type=Path)
    ap.add_argument("--field", type=Path, default=REPORTS / "embedded_field.json")
    ap.add_argument("--out-dir", type=Path, default=REPORTS)
    a = ap.parse_args()
    jobs = []
    if a.peierls:
        jobs.append(("embedded_peierls.json", peierls(a.peierls.resolve())))
    if a.disl:
        jobs.append(("embedded_disl_states.json", disl_states(a.disl.resolve())))
    if a.margin:
        jobs.append(("embedded_margin.json", margin(a.margin.resolve(), a.field)))
    for name, rec in jobs:
        (a.out_dir / name).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
        print("written", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
