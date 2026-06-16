#!/usr/bin/env python3
"""OVITO CNA + DXA analysis of one final dump (standalone, subprocess-friendly).

Deliberately self-contained (no package-relative imports) so the orchestrator can
run it as an isolated subprocess with the OVITO venv python:

    .venv/Scripts/python.exe analysis/python/stage_runner/analysis_runner.py
        --dump <dump file> --matrix-max-id N
        [--center x,y,z --axes a,b,c] --out result.json

Metrics: FCC/HCP/OTHER fractions of the Al matrix, dislocation segment count,
total line length, dislocation density, all DXA attributes (per-Burgers-family
lengths when present), stacking-fault indicator (HCP in fcc matrix), and a
plastic-zone note (matrix defect atoms outside the inclusion interface shell).
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import numpy as np


def analyze_dump(
    dump_path: str,
    matrix_max_id: int,
    center: tuple[float, float, float] | None = None,
    inclusion_axes: tuple[float, float, float] | None = None,
    clearance: float = 2.2,
) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier

    pipe = import_file(str(dump_path))
    pipe.modifiers.append(CommonNeighborAnalysisModifier())
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute()

    st = np.asarray(data.particles["Structure Type"])
    if "Particle Identifier" in data.particles:
        ids = np.asarray(data.particles["Particle Identifier"])
        mask = ids <= int(matrix_max_id)
    else:
        mask = np.asarray(data.particles["Particle Type"]) == 1
    nm = int(mask.sum())
    if nm == 0:
        raise RuntimeError("matrix selection is empty; wrong --matrix-max-id?")

    fcc = int(np.count_nonzero(st[mask] == 1))
    hcp = int(np.count_nonzero(st[mask] == 2))
    other = int(np.count_nonzero(st[mask] == 0))

    n_segments = len(data.dislocations.segments)
    total_len = float(data.attributes.get("DislocationAnalysis.total_line_length", 0.0))
    if total_len == 0.0 and n_segments:
        total_len = float(sum(s.length for s in data.dislocations.segments))
    vol = float(data.cell.volume)
    rho = total_len / vol * 1e20 if vol else 0.0

    dxa_attrs = {}
    for key, value in data.attributes.items():
        skey = str(key)
        if skey.startswith("DislocationAnalysis"):
            try:
                dxa_attrs[skey] = float(value)
            except (TypeError, ValueError):
                dxa_attrs[skey] = str(value)

    result = {
        "dump": str(dump_path),
        "matrix_max_id": int(matrix_max_id),
        "matrix_atoms": nm,
        "fcc_atoms": fcc,
        "hcp_atoms": hcp,
        "other_atoms": other,
        "fcc_pct": round(100.0 * fcc / nm, 3),
        "hcp_pct": round(100.0 * hcp / nm, 4),
        "other_pct": round(100.0 * other / nm, 3),
        "dislocation_segments": n_segments,
        "dislocation_length_A": round(total_len, 2),
        "dislocation_density_per_m2": rho,
        "cell_volume_A3": vol,
        "dxa_attributes": dxa_attrs,
        "stacking_fault_indicator": {
            "hcp_atoms_in_matrix": hcp,
            "note": "HCP-classified atoms inside the fcc Al matrix indicate "
            "stacking faults / partial dislocation traces",
        },
    }

    if center is not None and inclusion_axes is not None:
        pos = np.asarray(data.particles.positions)
        cell = np.asarray(data.cell)[:3, :3]
        box_len = np.array([cell[0][0], cell[1][1], cell[2][2]], dtype=float)
        ctr = np.array(center, dtype=float)
        shell_axes = np.array(inclusion_axes, dtype=float) + float(clearance)

        defect_mask = mask & (st != 1)
        rel = pos[defect_mask] - ctr
        rel -= box_len * np.round(rel / box_len)
        e_val = np.sqrt(np.sum((rel / shell_axes) ** 2, axis=1))

        n_defect = int(defect_mask.sum())
        beyond = e_val > 1.3  # outside the immediate inclusion interface shell
        hcp_defect = st[defect_mask] == 2
        result["plastic_zone"] = {
            "matrix_defect_atoms_total": n_defect,
            "defect_atoms_beyond_1p3_shell": int(np.count_nonzero(beyond)),
            "hcp_atoms_beyond_1p3_shell": int(np.count_nonzero(beyond & hcp_defect)),
            "max_normalized_ellipsoid_distance": float(e_val.max()) if n_defect else None,
            "median_normalized_ellipsoid_distance": float(np.median(e_val)) if n_defect else None,
            "note": "normalized distance 1.0 = inclusion interface shell "
            "(axes + clearance); defects at <=1.3 are interface atoms, "
            "defects well beyond 1.3 suggest a plastic zone in the matrix",
        }

    return result


def _parse_triplet(text: str) -> tuple[float, float, float]:
    parts = [float(x) for x in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected 'x,y,z'")
    return parts[0], parts[1], parts[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--matrix-max-id", type=int, required=True)
    ap.add_argument("--center", type=_parse_triplet, default=None)
    ap.add_argument("--axes", type=_parse_triplet, default=None)
    ap.add_argument("--clearance", type=float, default=2.2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if not Path(args.dump).is_file():
        print(f"ERROR: dump not found: {args.dump}", file=sys.stderr)
        return 2
    try:
        result = analyze_dump(
            args.dump,
            args.matrix_max_id,
            center=args.center,
            inclusion_axes=args.axes,
            clearance=args.clearance,
        )
    except Exception:
        traceback.print_exc()
        return 2

    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
