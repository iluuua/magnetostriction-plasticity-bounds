#!/usr/bin/env python3
"""Elastic constants of Al and Al13Fe4 for the MEAM potential of the calculations.

Each crystal is relaxed to zero stress, then strained by +-DELTA in each of the
six Voigt components; the atoms relax at the strained box and the stress is
read back. C_ij = -(dP_i/dE_j) from central differences (LAMMPS pressure is
minus the stress). Runs on the CPU with the plain meam pair style.

Al: cubic cell with cube axes, 4x4x4 conventional cells; reports C11 C12 C44,
the Zener ratio and the isotropic (Voigt-Reuss-Hill) shear modulus and Poisson
ratio. Al13Fe4: the 102-atom monoclinic cell replicated 2x3x2; reports the full
6x6 matrix and the Voigt-Reuss-Hill bulk and shear moduli.

    python analysis/python/meam_elastic_constants.py --out docs/reports/meam_elastic_constants.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LMP = "B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe"
POT = ROOT / "potentials/meam/Jelinek_2012"
DELTA = 1.0e-3
VOIGT = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]

HEAD = """units metal
atom_style atomic
boundary p p p
{create}
mass 1 26.9815385
mass 2 55.845
mass 3 24.305
mass 4 28.0855
pair_style meam
pair_coeff * * {pot}/Jelinek_2012_meamf AlS SiS MgS CuS FeS {pot}/Jelinek_2012_meam.alsimgcufe AlS FeS MgS SiS
neighbor 2.0 bin
neigh_modify delay 0 every 1 check yes
thermo_style custom step pe pxx pyy pzz pyz pxz pxy
"""


def run(script: str, wd: Path) -> str:
    (wd / "in.el").write_text(script, encoding="utf-8")
    out = subprocess.run([LMP, "-in", "in.el", "-log", "log.el", "-echo", "none", "-screen", "none"],
                         cwd=wd, capture_output=True, text=True)
    log = (wd / "log.el").read_text(encoding="utf-8", errors="replace")
    if out.returncode or "ERROR" in log:
        raise RuntimeError(log[-2000:])
    return log


def last_stress(log: str) -> np.ndarray:
    m = re.findall(r"^STRESS (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)", log, re.M)
    return np.array([float(v) for v in m[-1]])          # bar: pxx pyy pzz pyz pxz pxy


def relaxed(create: str, wd: Path, tri: bool) -> None:
    s = HEAD.format(create=create, pot=POT.as_posix())
    s += ("fix br all box/relax %s 0.0 vmax 0.001\n" % ("tri" if tri else "aniso")
          + "min_style cg\nminimize 0.0 1e-8 20000 200000\nunfix br\nminimize 0.0 1e-8 20000 200000\n"
          + "write_data ref.data\n")
    run(s, wd)


def strained_stress(wd: Path, k: int, sgn: float) -> np.ndarray:
    """Stress after a strain sgn*DELTA in Voigt component k (engineering shear),
    applied to the restricted triclinic box as in the LAMMPS ELASTIC example;
    the atoms relax at the strained box."""
    d = sgn * DELTA
    lines = [HEAD.format(create="read_data ref.data", pot=POT.as_posix()),
             "change_box all triclinic",
             "variable lx0 equal $(lx)", "variable ly0 equal $(ly)", "variable lz0 equal $(lz)",
             "variable xy0 equal $(xy)", "variable xz0 equal $(xz)", "variable yz0 equal $(yz)"]
    cmd = {
        0: "x scale %r xy final $(v_xy0*%r) xz final $(v_xz0*%r)" % (1 + d, 1 + d, 1 + d),
        1: "y scale %r yz final $(v_yz0*%r)" % (1 + d, 1 + d),
        2: "z scale %r" % (1 + d),
        3: "yz final $(v_yz0+%r*v_lz0)" % d,
        4: "xz final $(v_xz0+%r*v_lz0)" % d,
        5: "xy final $(v_xy0+%r*v_ly0) xz final $(v_xz0+%r*v_yz0)" % (d, d),
    }[k]
    lines += ["change_box all %s remap units box" % cmd,
              "min_style cg", "minimize 0.0 1e-8 20000 200000",
              'print "STRESS $(pxx) $(pyy) $(pzz) $(pyz) $(pxz) $(pxy)"']
    return last_stress(run("\n".join(lines) + "\n", wd))


def stiffness(create: str, tri: bool) -> np.ndarray:
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        relaxed(create, wd, tri)
        C = np.zeros((6, 6))
        for k in range(6):
            sp, sm = strained_stress(wd, k, +1), strained_stress(wd, k, -1)
            # stress = -pressure; bar -> GPa; engineering shear strain 2 e_ij = DELTA
            C[:, k] = -(sp - sm) / (2 * DELTA) * 1e-4
        return 0.5 * (C + C.T)


def vrh(C: np.ndarray) -> dict:
    S = np.linalg.inv(C)
    kv = (C[0, 0] + C[1, 1] + C[2, 2] + 2 * (C[0, 1] + C[1, 2] + C[0, 2])) / 9
    gv = (C[0, 0] + C[1, 1] + C[2, 2] - C[0, 1] - C[1, 2] - C[0, 2] + 3 * (C[3, 3] + C[4, 4] + C[5, 5])) / 15
    kr = 1 / (S[0, 0] + S[1, 1] + S[2, 2] + 2 * (S[0, 1] + S[1, 2] + S[0, 2]))
    gr = 15 / (4 * (S[0, 0] + S[1, 1] + S[2, 2]) - 4 * (S[0, 1] + S[1, 2] + S[0, 2]) + 3 * (S[3, 3] + S[4, 4] + S[5, 5]))
    k, g = (kv + kr) / 2, (gv + gr) / 2
    return {"K_voigt": kv, "K_reuss": kr, "G_voigt": gv, "G_reuss": gr, "K_hill": k, "G_hill": g,
            "nu_hill": (3 * k - 2 * g) / (2 * (3 * k + g)), "E_hill": 9 * k * g / (3 * k + g)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    al = stiffness("lattice fcc 4.05\nregion b block 0 4 0 4 0 4\ncreate_box 4 b\ncreate_atoms 1 box", tri=False)
    fe_cell = (ROOT / "structures/converted/Al13Fe4/al13fe4.data").as_posix()
    fe = stiffness("read_data %s extra/atom/types 2\nreplicate 2 3 2" % fe_cell, tri=True)
    res = {"potential": "MEAM Jelinek 2012", "strain_step": DELTA,
           "Al": {"C11": al[0, 0], "C12": al[0, 1], "C44": al[3, 3],
                  "zener": 2 * al[3, 3] / (al[0, 0] - al[0, 1]), "C_GPa": al.round(3).tolist(), **vrh(al)},
           "Al13Fe4": {"C_GPa": fe.round(3).tolist(), **vrh(fe)}}
    res["shear_modulus_ratio_inclusion_to_matrix"] = res["Al13Fe4"]["G_hill"] / res["Al"]["G_hill"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print("Al: C11 %.1f C12 %.1f C44 %.1f GPa, Zener %.2f, G %.1f, nu %.3f, E %.1f" % (
        al[0, 0], al[0, 1], al[3, 3], res["Al"]["zener"], res["Al"]["G_hill"], res["Al"]["nu_hill"], res["Al"]["E_hill"]))
    print("Al13Fe4: K %.1f G %.1f GPa (Voigt %.1f, Reuss %.1f); G ratio %.2f" % (
        res["Al13Fe4"]["K_hill"], res["Al13Fe4"]["G_hill"], res["Al13Fe4"]["G_voigt"],
        res["Al13Fe4"]["G_reuss"], res["shear_modulus_ratio_inclusion_to_matrix"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
