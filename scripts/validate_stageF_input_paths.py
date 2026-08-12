#!/usr/bin/env python
"""PART D path validation: verify every file path in the Stage F commensurate inputs is well-formed.

For each read_data/dump/restart/write_data/write_restart path: absolute, no corrupt substring, parent
directory exists, and (for read_data) the file exists. Emits JSON + a pass/fail summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe")
RUN = ROOT / "runs/stageF_F0_planar_100A_ppf_commensurate/20260630-010748"
INPUTS = [
    RUN / "F0_planar_100A_comm_eps0000/smoke/in.smoke",
    RUN / "F0_planar_100A_comm_eps00194/smoke/in.smoke",
    RUN / "F0_planar_100A_comm_eps00194/equil/in.common_cell_min",
]
# path-token index per command (0-based on the whitespace-split line)
PATH_TOKEN = {"read_data": 1, "write_data": 1, "write_restart": 1, "restart": 2, "dump": 5}
MUST_EXIST = {"read_data"}  # output paths: only the parent must exist
BAD_SUBSTRINGS = ["Documsics", "F0uil", "20260630-01000", "\\\\", "//C", "..", " "]


def check_path(cmd: str, raw: str) -> dict:
    p = raw.strip()
    rec: dict = {"command": cmd, "path": p, "issues": []}
    # strip a trailing restart wildcard / glob for existence checks
    probe = p.replace("*", "X")
    pp = Path(probe)
    if not pp.is_absolute():
        rec["issues"].append("not absolute")
    for bad in BAD_SUBSTRINGS:
        if bad == " ":
            continue  # spaces are legal inside the LAMMPS path here (none expected); checked via token count
        if bad in p:
            rec["issues"].append(f"corrupt substring '{bad}'")
    parent = pp.parent
    rec["parent_exists"] = parent.exists()
    if not parent.exists():
        rec["issues"].append(f"parent missing: {parent}")
    if cmd in MUST_EXIST:
        rec["file_exists"] = pp.exists()
        if not pp.exists():
            rec["issues"].append("read_data file missing")
    rec["ok"] = not rec["issues"]
    return rec


def main() -> None:
    report: dict = {"inputs": [], "all_ok": True}
    for inp in INPUTS:
        entry: dict = {"input": str(inp), "exists": inp.exists(), "paths": []}
        if not inp.exists():
            entry["error"] = "input file missing"
            report["all_ok"] = False
            report["inputs"].append(entry)
            continue
        for line in inp.read_text().splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            tok = s.split()
            cmd = tok[0]
            if cmd in PATH_TOKEN and len(tok) > PATH_TOKEN[cmd]:
                rec = check_path(cmd, tok[PATH_TOKEN[cmd]])
                entry["paths"].append(rec)
                if not rec["ok"]:
                    report["all_ok"] = False
        report["inputs"].append(entry)

    out = ROOT / "docs/reports/stageF_F0_commensurate_ppf_input_path_validation.json"
    out.write_text(json.dumps(report, indent=2))
    for e in report["inputs"]:
        tag = "MISSING" if not e.get("exists") else ("OK" if all(p["ok"] for p in e["paths"]) else "FAIL")
        print(f"[{tag}] {Path(e['input']).parent.parent.name}/{Path(e['input']).parent.name}/{Path(e['input']).name}  ({len(e.get('paths', []))} paths)")
        for p in e.get("paths", []):
            if not p["ok"]:
                print(f"    !! {p['command']}: {p['issues']}  {p['path']}")
    print(f"ALL_OK={report['all_ok']}  -> {out}")
    sys.exit(0 if report["all_ok"] else 2)


if __name__ == "__main__":
    main()
