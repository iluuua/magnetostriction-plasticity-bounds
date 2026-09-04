#!/usr/bin/env python3
"""Collect the numbers that patch_round2.py substitutes, from the records of
the held (and free) stage G13 v2 pairs.

Inputs (defaults are the repo's report files):
  --g10   stageG10 profile record of the HELD pair
  --g12h  stageG12 retention record of the HELD pair
  --g12f  stageG12 retention record of the FREE pair
  --g17   stageG17 continuum record for the ridge
Output: numbers_round2.json (EN and RU formatting side by side) and a printed
summary, including the checks a reader of the paper will make.
"""
from __future__ import annotations
import argparse, io, json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "analysis" / "python"))
from stageG5_two_scale_bridge import enhancement  # noqa: E402

MU, B = 26.5e9, 2.8638e-10
SPHERE_MPA = 41.45
RIDGE_CREST_R = 20.0


def ru(s: str) -> str:
    return s.replace(".", "{,}")


def solve_vstar(tau_mpa: float, target=0.25) -> float:
    lo, hi = 5.0, 400.0
    if enhancement(tau_mpa * 1e6, lo) > target:
        return lo
    if enhancement(tau_mpa * 1e6, hi) < target:
        return hi
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if enhancement(tau_mpa * 1e6, mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def fmt_enh(x: float) -> str:
    if x >= 100:
        e = int(math.floor(math.log10(x)))
        return r"$%.1f\times10^{%d}$" % (x / 10 ** e, e)
    if x >= 10:
        return "%.0f" % x
    if x >= 1:
        return "%.1f" % x
    return "%.2f" % x if x >= 0.1 else "%.3f" % x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--g10", type=Path, default=REPO / "docs/reports/stageG10_field_profile.json")
    ap.add_argument("--g12h", type=Path, default=REPO / "docs/reports/stageG12_eigenstrain_retention.json")
    ap.add_argument("--g12f", type=Path, default=REPO / "docs/reports/stageG12_eigenstrain_retention_free.json")
    ap.add_argument("--g17", type=Path, default=REPO / "docs/reports/stageG17_ridge_continuum.json")
    ap.add_argument("--out", type=Path, default=HERE / "numbers_round2.json")
    a = ap.parse_args()

    g10 = json.loads(a.g10.read_text(encoding="utf-8"))
    rows = [r for r in g10["profile"] if r.get("above_apex")]
    axis = [(r["r_A"], abs(r["d_sigma_xz_axis_MPa"])) for r in rows if r.get("d_sigma_xz_axis_MPa") is not None]
    if not axis:
        raise SystemExit("the profile record has no on-axis window (rerun stageG10 with the current script)")
    r_pk, pk = max(axis, key=lambda t: t[1])
    width_pk = max(r["max_RSS_MPa"] for r in rows)
    nf = g10["noise_floor_beyond_60A"]
    far_mean, far_sd = nf["mean_max_RSS_MPa"], nf["std_MPa"]
    # decay: first bin beyond the peak whose on-axis |d sigma_xz| is within the far-field band
    decay_r = None
    for r_, v in axis:
        if r_ > r_pk and v <= far_mean + far_sd:
            decay_r = r_
            break
    decay_d = (decay_r - RIDGE_CREST_R) if decay_r else None

    def eta(path: Path):
        d = json.loads(path.read_text(encoding="utf-8"))
        return float(d["eta_used_for_rescaling"]), float(d["eta_used_for_rescaling_se"])
    eh, eh_se = eta(a.g12h)
    ef, ef_se = eta(a.g12f) if a.g12f.exists() else (float("nan"), float("nan"))

    g17 = json.loads(a.g17.read_text(encoding="utf-8"))
    d_md = r_pk - RIDGE_CREST_R
    cont = min(g17["profile"], key=lambda p: abs(p["d_A"] - d_md))
    # the MD on-axis window is |x - x_ridge| < 10 A: compare with the continuum
    # value averaged over the same 20 A window
    cont_val = abs(cont["axis_window_20A"]["sxz_MPa"])
    cont_axis = abs(cont["on_axis"]["sxz_MPa"])
    rigid = g17["validation"].get("rigid_inclusion_factor_for_shear")

    e50, e70 = enhancement(pk * 1e6, 50), enhancement(pk * 1e6, 70)
    v_sphere, v_ridge = solve_vstar(SPHERE_MPA), solve_vstar(pk)
    vlo, vhi = sorted([v_sphere, v_ridge])
    vlo, vhi = int(5 * round(vlo / 5)), int(5 * round(vhi / 5))
    bow = MU * B / (pk * 1e6) * 1e6
    ratio = SPHERE_MPA / pk

    num = {
        "RIDGE_PEAK": "%.0f" % pk if pk >= 10 else "%.1f" % pk,
        "RIDGE_WIDTHAVG": "%.1f" % width_pk,
        "FAR": r"$%.1f\pm%.1f$" % (far_mean, far_sd),
        "DECAY": "%.0f" % decay_d if decay_d is not None else "??",
        "ETA_HELD": r"$%.2f\pm%.2f$" % (eh, eh_se),
        "ETA_FREE": r"$%.2f\pm%.2f$" % (ef, ef_se),
        "ENH_RIDGE_50": fmt_enh(e50), "ENH_RIDGE_70": fmt_enh(e70),
        "VSTAR_LO": str(vlo), "VSTAR_HI": str(vhi),
        "BOW_RIDGE": "%.1f" % bow if bow >= 1 else "%.2f" % bow,
        "RATIO_SPHERE_RIDGE": "%.1f" % ratio,
        "CONT_RIDGE": "%.0f" % cont_val if cont_val >= 10 else "%.1f" % cont_val,
    }
    for k in list(num):
        if k in ("DECAY", "VSTAR_LO", "VSTAR_HI"):
            continue
        num[k + "_RU"] = ru(num[k])
    num["_meta"] = {
        "peak_r_A": r_pk, "peak_on_axis_MPa": pk, "peak_width_avg_MPa": width_pk,
        "far_field": [far_mean, far_sd], "decay_r_A": decay_r,
        "eta_held": [eh, eh_se], "eta_free": [ef, ef_se],
        "enh_ridge": {"19": enhancement(pk * 1e6, 19), "30": enhancement(pk * 1e6, 30), "50": e50, "70": e70,
                      "100": enhancement(pk * 1e6, 100), "142": enhancement(pk * 1e6, 142)},
        "vstar_for_0.25": {"sphere_41MPa": v_sphere, "ridge": v_ridge},
        "bow_out_um": bow, "continuum_ridge_at_same_d": {"d_A": cont["d_A"], "window_20A_MPa": cont_val, "on_axis_MPa": cont_axis,
                                                        "rigid_factor": rigid, "window_20A_rigid_MPa": cont_val * rigid if rigid else None},
        "g10_label": g10.get("label"), "g10_cell": g10.get("cell"),
    }
    a.out.write_text(json.dumps(num, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(num, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
