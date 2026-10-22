#!/usr/bin/env python3
"""Fill the «KEY» values of the embedded-inclusion drafts from the records.

Reads docs/reports/embedded_field.json (MD), embedded_gates.json,
embedded_continuum.json, embedded_creep.json and, if present,
embedded_sweep.json, prints every value with its source, and writes the filled
sources to docs/paper (main.tex, main_ru.tex, supplementary.tex,
supplementary_ru.tex, highlights.tex). Russian copies use the decimal comma.
Text blocks (S2_TEXT, S6_TEXT, DISL_TEXT) are read from s2_, s6_ and disl_{en,ru}.tex
next to this script.

    python docs/paper/_drafts/fill_embedded.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
REPORTS = PAPER.parents[1] / "docs" / "reports"
sys.path.insert(0, str(PAPER.parents[1] / "analysis" / "python"))
from embedded_gates import agreement  # noqa: E402


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def rows(md, name):
    return (md.get("linear") or md["profiles"])[name]


def nearest(rs, d):
    return min(rs, key=lambda r: abs(r["d_A"] - d))


def values() -> dict:
    md, gates, cont, creep = (load("embedded_field.json"), load("embedded_gates.json"),
                              load("embedded_continuum.json"), load("embedded_creep.json"))
    v = {}
    # near-surface MD values: shells 5-10 A from the surface; closer in, the cones
    # along the field hold 15-20 atoms per shell and scatter by up to 25 MPa
    def near(name):
        return [r for r in rows(md, name) if 5.0 <= r["d_A"] <= 10.0]
    v["MD_POLE_PEAK"] = max(abs(r["srr"]) for r in near("pole"))
    v["MD_EQ_PEAK"] = max(r["srr"] for r in near("equator"))
    v["MD_EQ_SXX"] = max(r["stt"] for r in rows(md, "equator") if r["d_A"] <= 4)
    v["MD_SHEAR_PEAK"] = max(abs(r["s_axial_shear"]) for r in near("lobe25") + near("lobe67"))
    # the MD field against the same-cell continuum (rule in embedded_gates.agreement)
    ag = agreement(md, cont)
    v["A_FIT"] = ag["amplitude"]
    v["A_PCT"] = 100 * ag["amplitude"]
    per = ag["amplitude_by_direction"]
    v["A_POLE"], v["A_EQ"], v["A_L25"], v["A_L67"] = per["pole"], per["equator"], per["lobe25"], per["lobe67"]
    v["FIT_D"] = ag["fit_from_d_A"]
    v["MED_PCT"] = 100 * ag["median_deviation_after_scaling"]
    v["LAYER"] = ag["interface_layer_A"]
    # supplement S2: convergence, linearity, events, defects, mean stress
    v["G1_MAX"] = gates["G1_convergence"]["max_shell_change_MPa"]
    v["G3_MAX"] = max(abs(r["symmetric_MPa"]) for rr in gates["G3_linearity"].values() for r in rr)
    ev = gates["events"]
    v["EV_PLUS"] = ev["n_matrix_atoms_departing_by_more_than_0.1_A"]
    v["EV_MINUS"] = ev["minus_n_matrix_atoms_departing_by_more_than_0.1_A"]
    v["EV_MINUS_D"] = max(ev["their_distance_from_surface_A"] + ev["minus_distance_from_surface_A"])
    v["EV_MINUS_MAX"] = max(ev["max_departure_plus_A"], ev["max_departure_minus_A"])
    dxa = load("embedded_dxa.json")["cases"]
    far = sorted({r[0]["matrix_shells"]["d>=6"]["n_atoms"] - r[0]["matrix_shells"]["d>=6"]["by_structure"].get("FCC", 0)
                  for r in dxa.values()})
    if any(r[k]["n_segments"] for r in dxa.values() for k in (0, 1)):
        raise SystemExit("DXA found dislocation segments: the S2 text says none")
    v["NONFCC_FAR"] = "%d" % far[0] if len(far) == 1 else "%d--%d" % (far[0], far[-1])
    g4 = gates["G4_mean_stress"]
    v["G4_MD"] = "(%.1f; %.1f; %.1f)" % tuple(g4["md"][k] for k in ("xx", "yy", "zz"))
    v["G4_CT"] = "(%.1f; %.1f; %.1f)" % tuple(g4["continuum"][k] for k in ("xx", "yy", "zz"))
    v["G4_RATIO"] = float(np.mean([g4["md"][k] / g4["continuum"][k] for k in ("xx", "yy", "zz")]))
    # why the field is weaker: displacement transfer by shell, stress per strain,
    # density and cavity (embedded_gates displacement_vs_continuum, embedded_interface)
    shell = {r["d_from_A"]: r for r in gates["displacement_vs_continuum"]}
    v["D46R"], v["D46T"] = (100 * shell[4.0]["radial_md_over_continuum"], 100 * shell[4.0]["tangential_md_over_continuum"])
    v["D1214R"], v["D1214T"] = (100 * shell[12.0]["radial_md_over_continuum"],
                                100 * shell[12.0]["tangential_md_over_continuum"])
    itf = load("embedded_interface.json")
    far_rows = [q for q in itf["stress_vs_atomic_strain"] if q["d_from_A"] >= 8.0]
    near_rows = [q for q in itf["stress_vs_atomic_strain"] if q["d_from_A"] < 3.0]
    v["VIR_FAR"] = "%.2f--%.2f" % (min(q["virial_over_C_eps"] for q in far_rows),
                                   max(q["virial_over_C_eps"] for q in far_rows))
    v["VIR_CORR"] = min(q["correlation"] for q in far_rows)
    v["VIR_NEAR"] = "%.2f--%.2f" % (min(q["virial_over_C_eps"] for q in near_rows),
                                    max(q["virial_over_C_eps"] for q in near_rows))
    v["DENS_FIRST"] = next(q["relative_density"] for q in itf["density"] if abs(q["r_from_A"] - 25.0) < 1e-6)
    v["CAV_PCT"] = 100 * (itf["cavity_over_inclusion_volume"] - 1)
    v["R_EQ"] = itf["radius_A"] * ag["amplitude"] ** (1.0 / 3.0)
    v["LOSS_UM"] = 100 * (1 - ag["amplitude"]) * itf["radius_A"] / 25000.0
    # the dislocation above the inclusion (embedded_disl_states) and the 4x/10x cells (embedded_margin)
    ds = load("embedded_disl_states.json")
    v["DISL_D"] = abs(ds["ctl_core_minus_sphere_x_A"])
    v["DISL_SHIFT"] = abs(ds["core_shift_fld_minus_ctl_A"])
    v["DISL_REV"] = abs(ds["core_shift_rev_minus_ctl_A"])
    v["DISL_RELAX"] = abs(ds["ctl_core_shift_from_built_A"])
    v["DISL_SPLIT"] = float(np.mean([s["splitting_A"] for s in ds["states"].values()]))
    v["BLOCK_TOP"] = ds["ctl_block_stress_at_zero_load_MPa"]["top"]
    v["BLOCK_BOT"] = ds["ctl_block_stress_at_zero_load_MPa"]["bottom"]
    gp = md["glide_planes"]
    at = []
    for h in ("10", "15"):
        x = np.array(gp[h]["x_A"])
        y = np.array([np.nan if q is None else q for q in gp[h]["line_average_MPa"]])
        o = np.argsort(x)
        at.append(np.interp(ds["ctl_core_minus_sphere_x_A"], x[o], y[o]))
    h_line = ds["glide_plane_above_sphere_top_A"]
    v["DISL_TAU"] = abs(at[0] + (at[1] - at[0]) * (h_line - 10.0) / 5.0)
    mg = load("embedded_margin.json")["cases"]
    for c in ("x4", "x10"):
        if any(mg[c]["dxa_segments"]):
            raise SystemExit("DXA found dislocations in the %s cell: the S2 text says none" % c)
    v["X4_LIN"] = mg["x4"]["field_over_multiple_of_1x"]["median"]
    v["X10_LIN"] = mg["x10"]["field_over_multiple_of_1x"]["median"]
    v["X10_SHEAR"] = mg["x10"]["max_lobe_shear_MPa_any"]
    first = gates["displacement_vs_continuum"][0]
    v["KIN_RAD"] = 100 * first["radial_md_over_continuum"]
    v["KIN_TAN"] = 100 * first["tangential_md_over_continuum"]
    ctl = gates["control_relaxation"]
    v["CTL_FAR_MEAN"] = ctl["far_mean_stress_before_MPa"]
    v["CTL_BOX_SCALE"] = ctl["box_scale"]
    v["CTL_FAR_AFTER"] = ctl["far_mean_stress_after_MPa"]
    # glide planes
    best = (0.0, None, 0.0)
    for h, g in md["glide_planes"].items():
        la = max(abs(x) for x in g["line_average_MPa"] if x is not None)
        if la > best[0]:
            best = (la, h, g["local_max_abs_MPa"])
    v["LINE_PEAK"], v["LINE_H"], v["LOCAL_PEAK"] = best
    v["MEAN_PRED"] = "(%.1f; %.1f; %.1f)" % tuple(cont["periodic_mean_matrix_MPa"][k] for k in ("xx", "yy", "zz"))
    v["VSTAR_GRAINS"] = creep["vstar_for_target_b3"]["grains"]
    v["VSTAR_CRYSTAL"] = creep["vstar_for_target_b3"]["crystal"]
    v["VSTAR_MAX"] = creep["vstar_for_target_b3"]["max"]
    v["EPS_AT_70"] = 0.194 * v["VSTAR_GRAINS"] / 70
    yld = load("embedded_yield.json")["threshold_strain_percent"]
    v["EPS_SLIP_LO"], v["EPS_SLIP_HI"] = yld["rss_crystal"]
    v["EPS_VM_LO"], v["EPS_VM_HI"] = yld["von_mises"]
    # shells above the yield criteria at the given strain (single sphere): outer radius
    # r/R between the high and the low limit, and the thickness for a 5 um particle
    shells = load("embedded_yield.json")["shell_outer_r_over_R"]
    def at_eps(k):
        q = next(q for q in shells[k] if abs(q["eps_percent"] - 0.194) < 1e-9)
        return q["r_over_R_at_high_limit"], q["r_over_R_at_low_limit"]
    vm, sl = at_eps("von_mises"), at_eps("rss_crystal")
    v["SHELL_VM"] = "%.1f--%.1f" % vm
    v["SHELL_SLIP"] = "%.1f--%.1f" % sl
    v["THICK_SLIP"] = "%.1f--%.1f" % (sl[0] - 1, sl[1] - 1)
    v["THICK_VM_UM"] = "%.1f--%.1f" % ((vm[0] - 1) * 2.5, (vm[1] - 1) * 2.5)
    for k in ("POLE_PEAK", "EQ_PEAK", "SHEAR_PEAK"):
        v[k] = v["MD_" + k]
    return v


def fmt(key: str, val, ru: bool) -> str:
    if isinstance(val, str):
        s = val
    elif key in ("DISL_SHIFT", "DISL_REV", "X4_LIN", "X10_LIN"):
        s = "%.2f" % val
    elif key in ("DISL_D", "DISL_RELAX", "DISL_SPLIT", "DISL_TAU"):
        s = "%.1f" % val
    elif key in ("BLOCK_TOP", "BLOCK_BOT", "X10_SHEAR"):
        s = "%.0f" % val
    elif key in ("VIR_CORR", "DENS_FIRST", "LOSS_UM"):
        s = "%.2f" % val
    elif key == "R_EQ":
        s = "%.1f" % val
    elif key in ("D46R", "D46T", "D1214R", "D1214T", "CAV_PCT"):
        s = "%d" % round(float(val))
    elif key in ("G1_MAX", "G3_MAX", "EV_MINUS_D"):
        s = "%.1f" % val
    elif key == "EV_MINUS_MAX" or key == "G4_RATIO":
        s = "%.2f" % val
    elif key == "MED_PCT":
        s = "%.1f" % val
    elif key in ("LINE_H", "FIT_D", "LAYER", "A_PCT", "KIN_RAD", "KIN_TAN", "EV_PLUS", "EV_MINUS"):
        s = "%d" % round(float(val))
    elif key.startswith("A_"):
        s = "%.2f" % val
    elif key.startswith("VSTAR"):
        s = "%.0f" % val
    elif key == "EPS_AT_70" or key.startswith(("EPS_SLIP", "EPS_VM")):
        s = "%.3f" % val
    elif key == "CTL_BOX_SCALE":
        s = "%.5f" % val
    elif key in ("LINE_PEAK", "LOCAL_PEAK", "CTL_FAR_MEAN", "CTL_FAR_AFTER"):
        s = "%.1f" % val
    else:
        s = "%.0f" % val
    return s.replace(".", "{,}") if ru else s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    v = values()
    for k in sorted(v):
        print("%-14s %s" % (k, v[k]))
    if a.dry_run:
        return 0
    jobs = [("main_en_embedded.tex", "main.tex", False), ("main_ru_embedded.tex", "main_ru.tex", True),
            ("supp_en_embedded.tex", "supplementary.tex", False),
            ("supp_ru_embedded.tex", "supplementary_ru.tex", True),
            ("highlights_embedded.tex", "highlights.tex", False)]
    for src, dst, ru in jobs:
        t = (HERE / src).read_text(encoding="utf-8")
        for block, stem in (("S2_TEXT", "s2"), ("S6_TEXT", "s6"), ("DISL_TEXT", "disl")):
            f = HERE / ("%s_%s.tex" % (stem, "ru" if ru else "en"))
            if "«%s»" % block in t:
                if not f.exists():
                    raise SystemExit("text block %s missing for %s" % (f.name, src))
                t = t.replace("«%s»" % block, f.read_text(encoding="utf-8").strip())
        def sub(m):
            key = m.group(1)
            if key not in v:
                raise KeyError("no value for %s in %s" % (key, src))
            return fmt(key, v[key], ru)
        t = re.sub(r"«([A-Z0-9_]+)»", sub, t)
        if "«" in t:
            raise SystemExit("unfilled placeholder left in %s" % src)
        (PAPER / dst).write_text(t, encoding="utf-8", newline="\n")
        print("written", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
