#!/usr/bin/env python3
"""Stage G2 common-origin preparation.

Adversarial review (g2-shear-protocol-verify) fatal flaw #1: the G1 control and
physical smoke finals have dislocations at different positions (the drift IS the
G1 signal), so a raw tau_c difference between them is not attributable to the
eigenstrain. Fix: take ONE relaxed snapshot (the G1 CONTROL smoke final, with
velocities) and derive both G2 starts from it:
  - control:  the snapshot unchanged;
  - physical: the same snapshot with the Fe-block z scaled by (1+eps) about z=0
    (max atom displacement ~0.09 A; both cases then share a 5 ps tau=0 hold in
    the ramp input for re-thermalization).
Atom IDs: matrix Al = 1..N_AL, Fe block = N_AL+1..N (generator writes Al first).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
N_AL_MATRIX = 268488          # from G1 metadata: counts.al_matrix
EPS = 0.00194
CASES = {"G2_shear_eps0000": 0.0, "G2_shear_eps00194": EPS}
OUT_ROOT = REPO_ROOT / "structures" / "stageG2_common_origin"


def transform_data(src: Path, dst: Path, eps: float) -> dict:
    lines = src.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    section = None
    n_scaled = 0
    zmax_fe = 0.0
    for ln in lines:
        stripped = ln.strip()
        if re.match(r"^(Atoms|Velocities|Masses)\b", stripped):
            section = stripped.split()[0]
            out.append(ln)
            continue
        if section == "Atoms" and stripped and not stripped.startswith("#"):
            parts = ln.split()
            if len(parts) >= 5:
                atom_id = int(parts[0])
                if eps != 0.0 and atom_id > N_AL_MATRIX:
                    z = float(parts[4]) * (1.0 + eps)
                    parts[4] = f"{z:.10g}"
                    n_scaled += 1
                    zmax_fe = max(zmax_fe, z)
                out.append(" ".join(parts))
                continue
        out.append(ln)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"scaled_atoms": n_scaled, "zmax_fe_A": zmax_fe}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True,
                        help="G1 CONTROL smoke final data (with velocities)")
    args = parser.parse_args()

    manifest = {"source_snapshot": str(args.source), "n_al_matrix": N_AL_MATRIX,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "cases": {}}
    for case, eps in CASES.items():
        dst = OUT_ROOT / case / f"{case}.start.data"
        info = transform_data(args.source, dst, eps)
        manifest["cases"][case] = {"eps_z": eps, "data_file": str(dst), **info}
    (OUT_ROOT / "stageG2_common_origin_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
