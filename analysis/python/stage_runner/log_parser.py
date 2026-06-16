"""LAMMPS log parsing: errors, nan, lost atoms, performance, final thermo state."""

from __future__ import annotations

import math
import re
from pathlib import Path

NAN_RE = re.compile(r"(?i)\bnan\b")
LOOP_RE = re.compile(
    r"Loop time of ([\d.eE+-]+) on (\d+) procs for (\d+) steps with (\d+) atoms"
)
NSDAY_RE = re.compile(r"([\d.eE+-]+)\s*ns/day")
TSTEPS_RE = re.compile(r"([\d.eE+-]+)\s*timesteps/s")
DANGER_RE = re.compile(r"Dangerous builds = (\d+)")
WALL_RE = re.compile(r"Total wall time:\s*([\d:]+)")


def _try_float(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def _parse_thermo_blocks(lines: list[str]) -> list[dict]:
    """Each block: {'columns': [...], 'rows': [[float|None,...], ...]}."""
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if parts and parts[0] == "Step":
            columns = parts
            rows: list[list[float | None]] = []
            i += 1
            while i < len(lines):
                rparts = lines[i].split()
                if not rparts:
                    i += 1
                    continue
                if rparts[0] == "Loop" or rparts[0] == "Step":
                    break
                if _try_float(rparts[0]) is not None and len(rparts) == len(columns):
                    rows.append([_try_float(t) for t in rparts])
                    i += 1
                    continue
                # WARNING or other interleaved output inside the thermo table.
                i += 1
            blocks.append({"columns": columns, "rows": rows})
            continue
        i += 1
    return blocks


def parse_log(log_path: Path | str) -> dict:
    p = Path(log_path)
    result: dict = {
        "log_path": str(p),
        "exists": p.is_file(),
        "size_bytes": p.stat().st_size if p.is_file() else 0,
        "has_error": False,
        "error_lines": [],
        "nan_found": False,
        "lost_atoms": False,
        "lost_atoms_lines": [],
        "dangerous_builds": 0,
        "loop": None,
        "ns_per_day": None,
        "timesteps_per_s": None,
        "final_thermo": None,
        "atoms_first": None,
        "atoms_last": None,
        "total_wall_time": None,
        "completed_normally": False,
    }
    if not p.is_file():
        return result

    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for line in lines:
        if "ERROR" in line:
            result["has_error"] = True
            if len(result["error_lines"]) < 20:
                result["error_lines"].append(line.strip())
        if "Lost atoms" in line:
            result["lost_atoms"] = True
            if len(result["lost_atoms_lines"]) < 10:
                result["lost_atoms_lines"].append(line.strip())

    if NAN_RE.search(text):
        result["nan_found"] = True

    for m in DANGER_RE.finditer(text):
        result["dangerous_builds"] += int(m.group(1))

    # Use the LAST occurrence: multi-run inputs (e.g. prep settle+equil) emit one
    # Loop/performance block per run section; the last one reflects the final
    # production-relevant segment. Single-run logs are unaffected.
    loop_matches = list(LOOP_RE.finditer(text))
    if loop_matches:
        m = loop_matches[-1]
        result["loop"] = {
            "loop_time_s": float(m.group(1)),
            "procs": int(m.group(2)),
            "steps": int(m.group(3)),
            "atoms": int(m.group(4)),
        }
    nsday_matches = NSDAY_RE.findall(text)
    if nsday_matches:
        result["ns_per_day"] = float(nsday_matches[-1])
    tsteps_matches = TSTEPS_RE.findall(text)
    if tsteps_matches:
        result["timesteps_per_s"] = float(tsteps_matches[-1])
    m = WALL_RE.search(text)
    if m:
        result["total_wall_time"] = m.group(1)
        result["completed_normally"] = True

    blocks = _parse_thermo_blocks(lines)
    if blocks:
        last_rows = blocks[-1]["rows"]
        if last_rows:
            cols = blocks[-1]["columns"]
            final = dict(zip(cols, last_rows[-1]))
            # NaN values parse as float('nan'): flag them explicitly.
            for v in final.values():
                if isinstance(v, float) and math.isnan(v):
                    result["nan_found"] = True
            result["final_thermo"] = final
        first_rows = blocks[0]["rows"]
        if first_rows and "Atoms" in blocks[0]["columns"]:
            idx = blocks[0]["columns"].index("Atoms")
            v = first_rows[0][idx]
            result["atoms_first"] = int(v) if v is not None else None
        if last_rows and "Atoms" in blocks[-1]["columns"]:
            idx = blocks[-1]["columns"].index("Atoms")
            v = last_rows[-1][idx]
            result["atoms_last"] = int(v) if v is not None else None

    if (
        result["atoms_first"] is not None
        and result["atoms_last"] is not None
        and result["atoms_first"] != result["atoms_last"]
    ):
        result["lost_atoms"] = True
        result["lost_atoms_lines"].append(
            f"atom count drifted in thermo table: {result['atoms_first']} -> {result['atoms_last']}"
        )

    return result
