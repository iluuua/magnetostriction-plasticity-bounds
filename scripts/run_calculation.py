#!/usr/bin/env python3
"""Reproduce a published calculation from its archived initial configuration.

The default mode only prints the command. Pass --execute to start LAMMPS.
The alloy initial file is a candidate state without a launch-time hash;
exact replay of its original mobile coordinates is not established.
The three ramp cases preserve the original loading rates, thermostat seed and
monitor volumes. Metal units are used throughout. CPU and Kokkos runs can
differ numerically; matching the protocol does not establish convergence.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POTENTIAL = ROOT / "potentials/meam/Jelinek_2012"
RAMP_VARIABLES = {
    "N_AL": 72532,
    "TOPZ": 144.94,
    "XL0": 114.32,
    "XL1": 154.64,
    "ZL0": 38.23,
    "ZL1": 60.23,
    "XU0": 90.92,
    "XU1": 140.92,
    "ZU0": 61.61,
    "ZU1": 83.61,
}


def specification(case: str) -> tuple[Path, Path, dict]:
    """Return the input state, LAMMPS script and original run parameters."""
    if case.startswith("interface_"):
        suffix = "ctl" if case.endswith("control") else "fld"
        return (
            ROOT / f"data/publication/interface/initial_{suffix}.data.gz",
            ROOT / "lammps/stageG4_tilted_solute/in.fieldgate_pert",
            {"N_AL": 72532, "HOLD_INCL": 1, "KSPRING": 20.0, "CG_MAX": 6000, "CG_FTOL": 0.02},
        )
    if case == "alloy":
        return (
            ROOT / "data/publication/alloy/initial.data.gz",
            ROOT / "lammps/stageG3_solute_mobility/in.vstar",
            {"SEED": 88004},
        )
    held = case != "g15_free_control"
    variables = {
        **RAMP_VARIABLES,
        "NSTEPS": 45000 if held else 101000,
        "TAUMAX_MPA": 145.45 if held else 400.0,
        "HOLD_INCL": int(held),
    }
    return (
        ROOT / f"data/publication/{case}/initial.data.gz",
        ROOT / "lammps/stageG4_tilted_solute/in.ramp",
        variables,
    )


def command(case: str, executable: str, output: Path, kokkos: bool) -> tuple[list[str], Path]:
    """Construct an argument list without shell expansion or side effects."""
    initial, script, variables = specification(case)
    for required in (
        initial,
        script,
        POTENTIAL / "Jelinek_2012_meamf",
        POTENTIAL / "Jelinek_2012_meam.alsimgcufe",
    ):
        if not required.is_file():
            raise FileNotFoundError(required)
    args = [executable]
    if kokkos:
        args += [
            "-k",
            "on",
            "g",
            "1",
            "-sf",
            "kk",
            "-pk",
            "kokkos",
            "newton",
            "on",
            "neigh",
            "half",
            "gpu/aware",
            "off",
        ]
    args += ["-in", script.as_posix(), "-log", (output / "log.lammps").as_posix()]
    variables = {
        "DATA_FILE": (output / "initial.data").as_posix(),
        "POT_DIR": POTENTIAL.as_posix(),
        "OUT_PREFIX": (output / case).as_posix(),
        **variables,
    }
    for key, value in variables.items():
        args += ["-var", key, str(value)]
    return args, initial


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case",
        choices=(
            "interface_control",
            "interface_strained",
            "g15_free_control",
            "g15_held_control",
            "g15_held_strained",
            "alloy",
        ),
    )
    parser.add_argument("--executable", default=os.environ.get("LAMMPS_EXECUTABLE", "lmp"))
    parser.add_argument(
        "--kokkos", action="store_true", help="use one CUDA GPU with the tested neighbour settings"
    )
    parser.add_argument(
        "--output", type=Path, help="new output directory; existing results are never overwritten"
    )
    parser.add_argument(
        "--execute", action="store_true", help="start the calculation after printing its command"
    )
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = (args.output or ROOT / "runs/reproduced" / args.case / stamp).resolve()
    invocation, initial = command(args.case, args.executable, output, args.kokkos)
    print(
        json.dumps(
            {
                "case": args.case,
                "initial": initial.relative_to(ROOT).as_posix(),
                "command": invocation,
                "execute": args.execute,
            },
            indent=2,
        )
    )
    if not args.execute:
        return 0
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    with gzip.open(initial, "rb") as src, (output / "initial.data").open("wb") as dst:
        shutil.copyfileobj(src, dst)
    (output / "command.json").write_text(json.dumps(invocation, indent=2) + "\n", encoding="utf-8")
    with (output / "stdout.txt").open("w", encoding="utf-8") as stdout:
        result = subprocess.run(
            invocation, cwd=output, stdout=stdout, stderr=subprocess.STDOUT, check=False
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
