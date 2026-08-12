#!/usr/bin/env python3
"""OVITO CNA + DXA + PTM analysis of one final dump (standalone, subprocess-friendly).

Deliberately self-contained (no package-relative imports) so the orchestrator can
run it as an isolated subprocess with the OVITO venv python:

    .venv/Scripts/python.exe analysis/python/stage_runner/analysis_runner.py
        --dump <dump file> --matrix-max-id N
        [--center x,y,z --axes a,b,c] --out result.json

Metrics: CNA FCC/HCP/OTHER fractions of the Al matrix, PTM structure counts,
dislocation segment count,
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


STRUCTURE_LABELS = {
    0: "other",
    1: "fcc",
    2: "hcp",
    3: "bcc",
    4: "ico",
    5: "sc",
    6: "cubic_diamond",
    7: "hexagonal_diamond",
    8: "graphene",
}


def _matrix_mask(data, matrix_max_id: int) -> np.ndarray:
    if "Particle Identifier" in data.particles:
        ids = np.asarray(data.particles["Particle Identifier"])
        return ids <= int(matrix_max_id)
    return np.asarray(data.particles["Particle Type"]) == 1


def _structure_summary(st: np.ndarray, mask: np.ndarray) -> dict:
    nm = int(mask.sum())
    if nm == 0:
        raise RuntimeError("matrix selection is empty; wrong --matrix-max-id?")
    summary = {"matrix_atoms": nm}
    for code, label in STRUCTURE_LABELS.items():
        count = int(np.count_nonzero(st[mask] == code))
        summary[f"{label}_atoms"] = count
        summary[f"{label}_pct"] = round(100.0 * count / nm, 4)
    return summary


def _von_mises_from_pressure_bar(p: np.ndarray) -> float:
    xx, yy, zz, xy, xz, yz = [float(x) for x in p]
    return float(
        np.sqrt(
            0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2)
            + 3.0 * (xy**2 + xz**2 + yz**2)
        )
    )


def _signed_ellipsoid_distance(
    positions: np.ndarray,
    center: tuple[float, float, float],
    axes: tuple[float, float, float],
    box_len: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rel = positions - np.array(center, dtype=float)
    rel -= box_len * np.round(rel / box_len)
    radius = np.linalg.norm(rel, axis=1)
    direction = np.zeros_like(rel)
    nz = radius > 0.0
    direction[nz] = rel[nz] / radius[nz, None]
    denom = np.sqrt(np.sum((direction / np.array(axes, dtype=float)) ** 2, axis=1))
    surface_radius = np.divide(1.0, denom, out=np.zeros_like(radius), where=denom > 0.0)
    signed_distance = radius - surface_radius
    normalized = np.sqrt(np.sum((rel / np.array(axes, dtype=float)) ** 2, axis=1))
    return signed_distance, normalized


def _stress_summary_for_mask(stress: np.ndarray, mask: np.ndarray, atom_volume: float) -> dict:
    count = int(np.count_nonzero(mask))
    if count == 0:
        return {"atom_count": 0}
    volume = count * atom_volume
    pressure_bar = -np.sum(stress[mask], axis=0) / volume
    pressure_mpa = pressure_bar * 0.1
    return {
        "atom_count": count,
        "estimated_volume_A3": float(volume),
        "pxx_MPa": float(pressure_mpa[0]),
        "pyy_MPa": float(pressure_mpa[1]),
        "pzz_MPa": float(pressure_mpa[2]),
        "pxy_MPa": float(pressure_mpa[3]),
        "pxz_MPa": float(pressure_mpa[4]),
        "pyz_MPa": float(pressure_mpa[5]),
        "hydrostatic_pressure_MPa": float(np.mean(pressure_mpa[:3])),
        "von_mises_MPa": float(_von_mises_from_pressure_bar(pressure_bar) * 0.1),
        "max_abs_shear_MPa": float(np.max(np.abs(pressure_mpa[3:]))),
    }


def _profile_rows(
    *,
    stress: np.ndarray,
    structure_type: np.ndarray,
    matrix_mask: np.ndarray,
    distances: np.ndarray,
    atom_volume: float,
    bins: list[tuple[float, float | None]],
) -> list[dict]:
    rows = []
    for lo, hi in bins:
        mask = matrix_mask & (distances >= lo)
        if hi is not None:
            mask &= distances < hi
        summary = _stress_summary_for_mask(stress, mask, atom_volume)
        count = int(summary.get("atom_count", 0) or 0)
        hcp = int(np.count_nonzero(mask & (structure_type == 2)))
        other = int(np.count_nonzero(mask & (structure_type == 0)))
        rows.append(
            {
                "distance_from_interface_min_A": lo,
                "distance_from_interface_max_A": hi,
                "atom_count": count,
                "hcp_atoms": hcp,
                "other_atoms": other,
                "hcp_pct": round(100.0 * hcp / count, 4) if count else 0.0,
                "other_pct": round(100.0 * other / count, 4) if count else 0.0,
                **summary,
            }
        )
    return rows


def _cluster_summary(
    *,
    positions: np.ndarray,
    mask: np.ndarray,
    box_len: np.ndarray,
    cutoff_A: float = 4.2,
) -> dict:
    indices = np.flatnonzero(mask)
    count = int(len(indices))
    if count == 0:
        return {"atom_count": 0, "cluster_count": 0, "largest_cluster_atoms": 0, "cluster_sizes": [], "cutoff_A": cutoff_A}
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    pts = positions[indices]
    cutoff2 = cutoff_A * cutoff_A
    for i in range(count):
        delta = pts[i + 1 :] - pts[i]
        if len(delta) == 0:
            continue
        delta -= box_len * np.round(delta / box_len)
        distances2 = np.einsum("ij,ij->i", delta, delta)
        for rel_j in np.flatnonzero(distances2 <= cutoff2):
            union(i, int(rel_j) + i + 1)

    sizes: dict[int, int] = {}
    for i in range(count):
        root = find(i)
        sizes[root] = sizes.get(root, 0) + 1
    cluster_sizes = sorted(sizes.values(), reverse=True)
    return {
        "atom_count": count,
        "cluster_count": len(cluster_sizes),
        "largest_cluster_atoms": int(cluster_sizes[0]) if cluster_sizes else 0,
        "cluster_sizes": cluster_sizes,
        "cutoff_A": cutoff_A,
    }


def _z_profile_rows(
    *,
    stress: np.ndarray,
    structure_type: np.ndarray,
    matrix_mask: np.ndarray,
    positions: np.ndarray,
    center: tuple[float, float, float],
    box_len: np.ndarray,
    atom_volume: float,
    radius_A: float,
    bin_width_A: float = 10.0,
) -> list[dict]:
    rel = positions - np.array(center, dtype=float)
    rel -= box_len * np.round(rel / box_len)
    radial_xy = np.sqrt(rel[:, 0] ** 2 + rel[:, 1] ** 2)
    z = rel[:, 2]
    z_min = float(np.floor(z.min() / bin_width_A) * bin_width_A)
    z_max = float(np.ceil(z.max() / bin_width_A) * bin_width_A)
    rows = []
    edge = z_min
    while edge < z_max:
        hi = edge + bin_width_A
        mask = matrix_mask & (radial_xy <= radius_A) & (z >= edge) & (z < hi)
        summary = _stress_summary_for_mask(stress, mask, atom_volume)
        count = int(summary.get("atom_count", 0) or 0)
        hcp = int(np.count_nonzero(mask & (structure_type == 2)))
        other = int(np.count_nonzero(mask & (structure_type == 0)))
        rows.append(
            {
                "z_rel_min_A": edge,
                "z_rel_max_A": hi,
                "cylinder_radius_A": radius_A,
                "atom_count": count,
                "hcp_atoms": hcp,
                "other_atoms": other,
                "hcp_pct": round(100.0 * hcp / count, 4) if count else 0.0,
                "other_pct": round(100.0 * other / count, 4) if count else 0.0,
                **summary,
            }
        )
        edge = hi
    return rows


def analyze_stress_profiles(
    data,
    structure_type: np.ndarray,
    matrix_mask: np.ndarray,
    center: tuple[float, float, float] | None,
    axes: tuple[float, float, float] | None,
) -> dict:
    stress_keys = [f"c_st[{i}]" for i in range(1, 7)]
    if center is None or axes is None:
        return {"available": False, "reason": "center/axes not supplied"}
    missing = [key for key in stress_keys if key not in data.particles]
    if missing:
        return {"available": False, "reason": f"stress columns missing: {missing}"}

    stress = np.vstack([np.asarray(data.particles[key], dtype=float) for key in stress_keys]).T
    positions = np.asarray(data.particles.positions, dtype=float)
    cell = np.asarray(data.cell)[:3, :3]
    box_len = np.array([cell[0][0], cell[1][1], cell[2][2]], dtype=float)
    atom_volume = float(data.cell.volume) / int(len(positions))
    signed_distance, normalized_distance = _signed_ellipsoid_distance(positions, center, axes, box_len)

    inclusion_mask = ~matrix_mask
    interface_shell = matrix_mask & (signed_distance >= 0.0) & (signed_distance < 5.0)
    near_matrix = matrix_mask & (signed_distance >= 5.0) & (signed_distance < 15.0)
    mid_matrix = matrix_mask & (signed_distance >= 15.0) & (signed_distance < 30.0)
    far_gt_15_matrix = matrix_mask & (signed_distance >= 15.0)
    far_gt_30_matrix = matrix_mask & (signed_distance >= 30.0)

    radial_bins = [(0.0, 5.0), (5.0, 15.0), (15.0, 30.0), (30.0, None)]
    radial = _profile_rows(
        stress=stress,
        structure_type=structure_type,
        matrix_mask=matrix_mask,
        distances=signed_distance,
        atom_volume=atom_volume,
        bins=radial_bins,
    )
    z_axis = _z_profile_rows(
        stress=stress,
        structure_type=structure_type,
        matrix_mask=matrix_mask,
        positions=positions,
        center=center,
        box_len=box_len,
        atom_volume=atom_volume,
        radius_A=max(5.0, min(float(axes[0]), float(axes[1])) * 0.5),
    )

    nonempty_radial = [r for r in radial if int(r.get("atom_count", 0) or 0) > 0]
    nonempty_z = [r for r in z_axis if int(r.get("atom_count", 0) or 0) > 0]
    above = [r for r in nonempty_z if float(r["z_rel_min_A"]) >= 0.0]
    below = [r for r in nonempty_z if float(r["z_rel_max_A"]) <= 0.0]
    extrema = {
        "max_radial_von_mises": max(nonempty_radial, key=lambda r: float(r.get("von_mises_MPa", 0.0)), default=None),
        "max_z_above_von_mises": max(above, key=lambda r: float(r.get("von_mises_MPa", 0.0)), default=None),
        "max_z_below_von_mises": max(below, key=lambda r: float(r.get("von_mises_MPa", 0.0)), default=None),
        "max_normalized_distance_seen": float(normalized_distance[matrix_mask].max()) if int(matrix_mask.sum()) else None,
    }

    return {
        "available": True,
        "method": (
            "Virial stress proxy from LAMMPS c_st[1..6]; pressure tensor is "
            "-sum(c_st)/estimated_zone_volume. 1 bar = 0.1 MPa. Zone volume "
            "uses the mean atomic volume, so absolute local stresses are approximate."
        ),
        "cell_volume_A3": float(data.cell.volume),
        "mean_atomic_volume_A3": atom_volume,
        "zones": {
            "inclusion": _stress_summary_for_mask(stress, inclusion_mask, atom_volume),
            "interface_matrix_0_5A": _stress_summary_for_mask(stress, interface_shell, atom_volume),
            "matrix_near_5_15A": _stress_summary_for_mask(stress, near_matrix, atom_volume),
            "matrix_mid_15_30A": _stress_summary_for_mask(stress, mid_matrix, atom_volume),
            "matrix_far_gt_30A": _stress_summary_for_mask(stress, far_gt_30_matrix, atom_volume),
            "matrix_far_gt_15A": _stress_summary_for_mask(stress, far_gt_15_matrix, atom_volume),
        },
        "radial_profile": radial,
        "z_axis_profile": z_axis,
        "hcp_cluster_summary": _cluster_summary(
            positions=positions,
            mask=matrix_mask & (structure_type == 2),
            box_len=box_len,
        ),
        "other_cluster_summary": _cluster_summary(
            positions=positions,
            mask=matrix_mask & (structure_type == 0),
            box_len=box_len,
        ),
        "hotspots": extrema,
        "extrema": extrema,
    }


def analyze_ptm_dump(dump_path: str, matrix_max_id: int) -> dict:
    from ovito.io import import_file
    from ovito.modifiers import PolyhedralTemplateMatchingModifier

    pipe = import_file(str(dump_path))
    pipe.modifiers.append(PolyhedralTemplateMatchingModifier())
    data = pipe.compute()
    st = np.asarray(data.particles["Structure Type"])
    mask = _matrix_mask(data, matrix_max_id)
    summary = _structure_summary(st, mask)
    attrs = {}
    for key, value in data.attributes.items():
        skey = str(key)
        if skey.startswith("PolyhedralTemplateMatching"):
            try:
                attrs[skey] = float(value)
            except (TypeError, ValueError):
                attrs[skey] = str(value)
    summary["attributes"] = attrs
    return summary


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
    mask = _matrix_mask(data, matrix_max_id)
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
        "ptm": analyze_ptm_dump(dump_path, matrix_max_id),
        "stress_profiles": analyze_stress_profiles(data, st, mask, center, inclusion_axes),
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
