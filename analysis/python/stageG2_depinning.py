#!/usr/bin/env python3
"""Track DXA Burgers families and departure candidates during a shear ramp.

Input is an original run directory or a plain/gzip trajectory (including a
quoted shard glob). OVITO supplies DXA geometry. Coordinates and line lengths
are in angstroms, time steps use a 1 fs default, and stresses are in MPa.
JSON and per-frame CSV retain nominal-ramp provenance and sampling coverage.
Reappearing families after a missing frame have untrusted lineage; their
departure candidates are diagnostics, not onsets of the original line.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from _g4clean import file_provenance, open_text, trajectory_paths

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = ["G2_shear_eps0000", "G2_shear_eps00194"]
LX = 186.1458
PRE, TS, NTOT = 5000, 16000, 101000
TAUMAX = 400.0


@dataclass(frozen=True)
class Ramp:
    """Raised-cosine rate onset followed by linear loading, as in in.ramp."""

    pre_steps: int = PRE
    smooth_steps: int = TS
    total_steps: int = NTOT
    tau_max_mpa: float = TAUMAX
    timestep_ps: float = 0.001

    def __post_init__(self):
        if (
            self.pre_steps < 0
            or self.smooth_steps <= 0
            or self.total_steps < self.pre_steps + self.smooth_steps
            or not math.isfinite(self.tau_max_mpa)
            or self.tau_max_mpa <= 0
            or not math.isfinite(self.timestep_ps)
            or self.timestep_ps <= 0
        ):
            raise ValueError("Invalid nominal ramp parameters")


def tau_nominal_mpa(step: float, ramp: Ramp | None = None) -> float:
    """Evaluate nominal shear in MPa without inferring a run's completion."""
    ramp = ramp or Ramp(PRE, TS, NTOT, TAUMAX)
    n_ramp = ramp.total_steps - ramp.pre_steps
    r = ramp.tau_max_mpa / (n_ramp - 0.5 * ramp.smooth_steps)
    sp = step - ramp.pre_steps
    if sp <= 0:
        return 0.0
    if sp < ramp.smooth_steps:
        return r * (
            0.5 * sp
            - (ramp.smooth_steps / (2 * math.pi)) * math.sin(math.pi * sp / ramp.smooth_steps)
        )
    return r * (sp - 0.5 * ramp.smooth_steps)


def parse_log(log_path: Path) -> dict[str, np.ndarray]:
    """Read production thermo columns by header; taubar remains in bar."""
    names = {
        "step": "Step",
        "temp": "Temp",
        "taubar": "v_taubar",
        "tauLow": "v_tauLowMPa",
        "tauUpp": "v_tauUppMPa",
    }
    rows, columns = {}, None
    with open_text(log_path) as stream:
        for line in stream:
            parts = line.split()
            if parts[:1] == ["Step"]:
                columns = parts if set(names.values()).issubset(parts) else None
                continue
            if columns is None or len(parts) != len(columns):
                continue
            try:
                values = [float(parts[columns.index(key)]) for key in names.values()]
            except ValueError:
                continue
            rows[values[0]] = values
    arr = np.array([rows[key] for key in sorted(rows)], dtype=float).reshape(-1, len(names))
    return {name: arr[:, i] for i, name in enumerate(names)}


def circ_mean(xs: np.ndarray) -> float:
    """Circular mean position in [0, LX), in angstroms."""
    ang = xs / LX * 2 * math.pi
    return float(
        (math.atan2(np.sin(ang).mean(), np.cos(ang).mean()) % (2 * math.pi)) / (2 * math.pi) * LX
    )


FLAT = False


def case_dir(run_dir: Path, case: str) -> Path:
    """Resolve original nested and flat run layouts."""
    return run_dir / case if FLAT else run_dir / case / "production"


def analyze_case(
    case: str,
    run_dir: Path | None = None,
    *,
    dump: str | None = None,
    log_path: Path | None = None,
    ramp: Ramp | None = None,
    max_frames: int | None = None,
    lx: float | None = None,
) -> dict:
    """Run DXA on saved frames; missing family observations break lineage."""
    global LX
    from ovito.io import import_file
    from ovito.modifiers import DislocationAnalysisModifier

    if dump is None:
        if run_dir is None:
            raise ValueError("Supply a run directory or a trajectory")
        directory = case_dir(run_dir, case)
        dump = str(directory / f"{case}.production.lammpstrj")
        if log_path is None and (directory / "log.lammps").is_file():
            log_path = directory / "log.lammps"
    paths = trajectory_paths(dump)
    pipe = import_file([str(path) for path in paths])
    ramp = ramp or Ramp(PRE, TS, NTOT, TAUMAX)
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)

    frames = []
    count = pipe.source.num_frames
    if max_frames is not None:
        if max_frames <= 0:
            raise ValueError("max_frames must be positive")
        count = min(count, max_frames)
    for fi in range(count):
        data = pipe.compute(fi)
        if "Timestep" not in data.attributes:
            raise ValueError("Trajectory must retain the original LAMMPS timesteps")
        step = int(data.attributes["Timestep"])
        if frames and step <= frames[-1]["step"]:
            raise ValueError("Shard timesteps must be strictly increasing without overlap")
        box_lx = float(np.linalg.norm(np.asarray(data.cell)[:, 0]))
        if fi == 0:
            LX = box_lx if lx is None else lx
            if not np.isclose(LX, box_lx, atol=1e-3, rtol=0):
                raise ValueError("--lx disagrees with the trajectory cell")
        elif not np.isclose(LX, box_lx, atol=1e-3, rtol=0):
            raise ValueError("Tracking requires constant Lx")
        fam: dict[str, list] = {"plus": [], "minus": [], "other": [], "interface": []}
        total_len = 0.0
        for seg in data.dislocations.segments:
            pts = np.asarray(seg.points)
            bx = float(seg.spatial_burgers_vector[0])
            zc = float(pts[:, 2].mean())
            xc = circ_mean(pts[:, 0])
            total_len += float(seg.length)
            entry = (xc, zc, float(seg.length), bx)
            if zc < 40.0:
                fam["interface"].append(entry)
            elif bx > 0.5:
                fam["plus"].append(entry)
            elif bx < -0.5:
                fam["minus"].append(entry)
            else:
                fam["other"].append(entry)
        row = {
            "frame": fi,
            "step": step,
            "tau_nominal_MPa": tau_nominal_mpa(step, ramp),
            "n_segments": len(data.dislocations.segments),
            "dxa_total_len_A": total_len,
            "n_interface_segments": len(fam["interface"]),
            "n_other_segments": len(fam["other"]),
        }
        for name in ("plus", "minus"):
            entries = fam[name]
            if entries:
                xs = np.array([e[0] for e in entries])
                w = np.array([e[2] for e in entries])
                row[f"x_{name}"] = circ_mean(np.repeat(xs, np.maximum(1, (w / 10).astype(int))))
                row[f"z_{name}"] = float(np.mean([e[1] for e in entries]))
                row[f"len_{name}"] = float(w.sum())
                row[f"xmin_{name}"] = float(xs.min())
                row[f"xmax_{name}"] = float(xs.max())
            else:
                row[f"x_{name}"] = None
        frames.append(row)

    result = analyze_frames(frames, timestep_ps=ramp.timestep_ps)
    result.update(
        {
            "case": case,
            "inputs": [file_provenance(path, checksum=False) for path in paths],
            "nominal_ramp": asdict(ramp),
            "cell_length_x_A": LX,
            "coverage": {
                "available_frames": pipe.source.num_frames,
                "analyzed_frames": len(frames),
                "last_analyzed_step": frames[-1]["step"],
                "last_nominal_MPa": frames[-1]["tau_nominal_MPa"],
                "subset_only": count < pipe.source.num_frames,
            },
        }
    )
    if result["onset"] is not None:
        onset = result["onset"]
        onset["tau_local_low_MPa"] = None
        onset["tau_local_upp_MPa"] = None
        if log_path is not None:
            log = parse_log(log_path)
            mask = (log["step"] > onset["step"] - 1000) & (log["step"] < onset["step"] + 1000)
            if np.any(mask):
                onset["tau_local_low_MPa"] = float(log["tauLow"][mask].mean())
                onset["tau_local_upp_MPa"] = float(log["tauUpp"][mask].mean())
    if log_path is not None:
        result["log_input"] = file_provenance(log_path)
    return result


def analyze_frames(frames: list[dict], *, timestep_ps: float = 0.001) -> dict:
    """Apply departure criteria to saved family means without rerunning DXA.

    A candidate needs two subsequent observations. A missing observation can
    sustain a departure, but does not distinguish exit from annihilation or
    failure of DXA. A family seen again after a gap is not the original line.
    """
    if not frames:
        raise ValueError("No frames to analyze")
    for name in ("plus", "minus"):
        prev = None
        acc = 0.0
        gap = False
        for row in frames:
            x = row.get(f"x_{name}")
            if x is None:
                row[f"xu_{name}"] = None
                row[f"lineage_{name}"] = "missing"
                gap = gap or prev is not None
                continue
            row[f"lineage_{name}"] = "reacquired_untrusted" if gap else "continuous_family"
            if prev is not None:
                d = x - prev
                d -= round(d / LX) * LX
                acc += d
            else:
                acc = x
            prev = x
            row[f"xu_{name}"] = acc

    for row in frames:
        xp, xm = row.get("xu_plus"), row.get("xu_minus")
        row["s_A"] = (xp - xm) if (xp is not None and xm is not None) else None

    # Separation is a family-level diagnostic, not a dislocation identity.
    base = [
        (r["step"], r["s_A"])
        for r in frames
        if r["tau_nominal_MPa"] < 40.0 and r["s_A"] is not None
    ]
    bs = np.array(base)
    coef = np.polyfit(bs[:, 0], bs[:, 1], 1) if len(base) >= 3 else None
    sigma_s = float(np.std(bs[:, 1] - np.polyval(coef, bs[:, 0]))) if coef is not None else None
    thresh = max(6 * sigma_s, 8.0) if sigma_s is not None else None
    onset = None
    for i, r in enumerate(frames):
        if r["s_A"] is None or coef is None:
            continue
        dev = r["s_A"] - float(np.polyval(coef, r["step"]))
        r["s_dev_A"] = dev
        if onset is None and dev > thresh:
            later = frames[i + 1 : i + 3]
            if len(later) == 2 and all(
                f["s_A"] is None or (f["s_A"] - np.polyval(coef, f["step"])) > dev - 2.0
                for f in later
            ):
                onset = r
                gone = [f for f in frames[i + 1 :] if f["s_A"] is None]
                onset["line_gone_at_step"] = gone[0]["step"] if gone else None
    result = {
        "frames": frames,
        "sigma_s_A": sigma_s,
        "threshold_A": thresh,
        "baseline_fit": (
            {"slope_A_per_step": float(coef[0]), "intercept_A": float(coef[1])}
            if coef is not None
            else None
        ),
    }

    result["per_line"] = {}
    for key, lab in (("xu_plus", "plus"), ("xu_minus", "minus")):
        pts = [(r["step"], r[key], r["tau_nominal_MPa"]) for r in frames if r.get(key) is not None]
        if len(pts) < 4:
            continue
        x0 = pts[0][1]
        early = [(s, x - x0) for s, x, tau in pts if s * timestep_ps <= 6.0]
        base = np.array([(s, x) for s, x, tau in pts if tau < 40.0 and s * timestep_ps >= 4.0])
        if len(base) < 3:
            continue
        cb = np.polyfit(base[:, 0], base[:, 1], 1)
        sig = float(np.std(base[:, 1] - np.polyval(cb, base[:, 0])))
        thr = max(6 * sig, 8.0)
        line_onset = None
        for s, x, tau in pts:
            dev = x - float(np.polyval(cb, s))
            if abs(dev) > thr and tau >= 40.0:
                steps_present = {r["step"] for r in frames if r.get(key) is not None}
                nxt = [r["step"] for r in frames if r["step"] > s][:2]
                ok = len(nxt) == 2 and all(
                    (st not in steps_present)
                    or abs(
                        float(dict((q[0], q[1]) for q in pts).get(st, 0.0))
                        - float(np.polyval(cb, st))
                    )
                    > thr - 2.0
                    for st in nxt
                )
                if ok:
                    line_onset = {"step": s, "tau_nominal_MPa": tau, "x_A": x, "dev_A": dev}
                    break
        gone = [r["step"] for r in frames if r.get(key) is None and r["step"] > pts[0][0]]
        reacquired = [r["step"] for r in frames if r[f"lineage_{lab}"] == "reacquired_untrusted"]
        baseline_reacquired = any(
            r[f"lineage_{lab}"] == "reacquired_untrusted"
            and r["tau_nominal_MPa"] < 40
            and r["step"] * timestep_ps >= 4.0
            for r in frames
        )
        trusted = not baseline_reacquired and not (
            line_onset and gone and gone[0] <= line_onset["step"]
        )
        result["per_line"][lab] = {
            "x_at_start_A": x0,
            "displacement_in_first_6ps_A": early[-1][1] if early else None,
            "baseline_sigma_A": sig,
            "threshold_A": thr,
            "baseline_slope_A_per_step": float(cb[0]),
            "onset": line_onset if trusted else None,
            "candidate_onset": line_onset,
            "lineage_status": "untrusted_after_gap"
            if reacquired
            else "continuous_until_disappearance",
            "first_reacquired_step": reacquired[0] if reacquired else None,
            "onset_trusted": bool(trusted and line_onset),
            "line_gone_at_step": gone[0] if gone else None,
        }
    if onset is not None:
        result["onset"] = {
            "step": onset["step"],
            "frame": onset["frame"],
            "tau_c_nominal_MPa": onset["tau_nominal_MPa"],
            "s_at_onset_A": onset["s_A"],
            "s_dev_at_onset_A": onset["s_dev_A"],
            "line_gone_at_step": onset.get("line_gone_at_step"),
        }
    else:
        result["onset"] = None
    result["candidate_onset"] = result["onset"]
    if onset and any(
        r[f"lineage_{name}"] == "reacquired_untrusted"
        for r in frames
        if r["step"] <= onset["step"] or r["tau_nominal_MPa"] < 40
        for name in ("plus", "minus")
    ):
        result["onset"] = None
    result["interpretation"] = (
        "Burgers-family departure candidates. Family continuity "
        "does not establish segment identity or confirm nucleation."
    )
    return result


def ramp_parameters(command_path: Path | None = None, **overrides) -> tuple[Ramp, dict]:
    """Read actual -var overrides from cmd.json, then apply explicit CLI values.

    LAMMPS echoes default ``variable ... index`` lines even when the command
    overrides them. Those echoed defaults are not evidence of the run values.
    """
    values = asdict(Ramp())
    sources = {key: "in.ramp default; not independently verified" for key in values}
    names = {
        "NSTEPS": "total_steps",
        "TAUMAX_MPA": "tau_max_mpa",
        "PRE_STEPS": "pre_steps",
        "TS": "smooth_steps",
    }
    if command_path is not None:
        command = json.loads(command_path.read_text(encoding="utf-8"))
        if not isinstance(command, list):
            raise ValueError("Command provenance must be a JSON argument list")
        for i, value in enumerate(command[:-2]):
            if value == "-var" and command[i + 1] in names:
                key = names[command[i + 1]]
                values[key] = type(values[key])(command[i + 2])
                sources[key] = file_provenance(command_path)["path"]
    for key, value in overrides.items():
        if value is not None:
            values[key] = value
            sources[key] = "explicit CLI parameter"
    return Ramp(**values), sources


def main() -> int:
    global FLAT, LX
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-dir", type=Path)
    source.add_argument("--dump", help="single trajectory or quoted gzip shard glob")
    parser.add_argument("--case", default="trajectory", help="case name for --dump")
    parser.add_argument("--cases", default=None, help="comma-separated case names")
    parser.add_argument("--tag", default="", help="suffix for output file names")
    parser.add_argument(
        "--flat",
        action="store_true",
        help="stage G15 layout: run_dir/<case>/<case>.production.lammpstrj",
    )
    parser.add_argument("--lx", type=float, help="optional Lx check against the dump, in A")
    parser.add_argument("--log", type=Path, help="optional production log for local stresses")
    parser.add_argument(
        "--command-file", type=Path, help="original cmd.json containing -var overrides"
    )
    parser.add_argument("--total-steps", type=int, help="original NSTEPS, not the last saved frame")
    parser.add_argument("--tau-max-mpa", type=float, help="original TAUMAX_MPA")
    parser.add_argument("--pre-steps", type=int)
    parser.add_argument("--smooth-steps", type=int)
    parser.add_argument("--timestep-ps", type=float)
    parser.add_argument(
        "--max-frames", type=int, help="analyze a prefix for a labelled smoke check"
    )
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "docs" / "reports")
    args = parser.parse_args()

    FLAT = args.flat
    if args.dump and args.cases:
        parser.error("Use --case with --dump; --cases belongs to --run-dir")
    cases = [args.case] if args.dump else (args.cases.split(",") if args.cases else CASES)
    if len(cases) > 1 and (args.log or args.command_file):
        parser.error("Explicit --log and --command-file require a single case")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    summary = {
        "run_dir": str(args.run_dir) if args.run_dir else None,
        "cases_analyzed": cases,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol": "oriented Burgers families; baseline tau<40 MPa; "
        "departure >6*sigma (minimum 8 A), checked in two subsequent frames; "
        "reacquisition after a gap invalidates original-line onset",
        "cases": {},
    }
    for case in cases:
        directory = (
            trajectory_paths(args.dump)[0].parent if args.dump else case_dir(args.run_dir, case)
        )
        command_path = args.command_file
        if command_path is None and (directory / "cmd.json").is_file():
            command_path = directory / "cmd.json"
        ramp, sources = ramp_parameters(
            command_path,
            total_steps=args.total_steps,
            tau_max_mpa=args.tau_max_mpa,
            pre_steps=args.pre_steps,
            smooth_steps=args.smooth_steps,
            timestep_ps=args.timestep_ps,
        )
        res = analyze_case(
            case,
            args.run_dir,
            dump=args.dump,
            log_path=args.log,
            ramp=ramp,
            max_frames=args.max_frames,
            lx=args.lx,
        )
        res["ramp_parameter_sources"] = sources
        keys = list(dict.fromkeys(key for row in res["frames"] for key in row))
        csv_path = args.out_dir / f"stageG2_depinning_{case}{tag}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(res["frames"])
        summary["cases"][case] = {k: v for k, v in res.items() if k != "frames"}
        summary["cases"][case]["csv"] = str(csv_path)

    if len(cases) >= 2:
        o0 = summary["cases"][cases[0]]["onset"]
        o1 = summary["cases"][cases[1]]["onset"]
        if o0 and o1:
            summary["delta_tau_c_nominal_MPa"] = o1["tau_c_nominal_MPa"] - o0["tau_c_nominal_MPa"]
    out = args.out_dir / f"stageG2_depinning_summary{tag}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
    for c, v in summary["cases"].items():
        print(c, "onset:", json.dumps(v["onset"]))
        for lab, pl in v.get("per_line", {}).items():
            print("   ", lab, json.dumps(pl))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
