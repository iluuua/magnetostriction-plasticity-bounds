#!/usr/bin/env python3
"""Summarize LAMMPS thermo output and basic failure markers."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


NUMERIC_START = re.compile(r"^\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
THERMO_COLUMNS = {
    "Step",
    "Temp",
    "PotEng",
    "KinEng",
    "TotEng",
    "Press",
    "Volume",
    "Lx",
    "Ly",
    "Lz",
}


def _is_number(value: str) -> bool:
    try:
        number = float(value)
    except ValueError:
        return False
    return math.isfinite(number) or math.isnan(number)


def parse_thermo_tables(text: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] == "Step" and THERMO_COLUMNS.intersection(parts):
            current = {"columns": parts, "rows": []}
            tables.append(current)
            continue

        if current is None:
            continue

        if not NUMERIC_START.match(line):
            current = None
            continue

        values = line.split()
        if len(values) != len(current["columns"]) or not all(_is_number(v) for v in values):
            current = None
            continue

        row = {col: float(value) for col, value in zip(current["columns"], values)}
        if "Step" in row:
            row["Step"] = int(row["Step"])
        current["rows"].append(row)

    return tables


def summarize_log(log_path: Path) -> dict[str, Any]:
    text = log_path.read_text(errors="replace")
    lower = text.lower()
    tables = parse_thermo_tables(text)
    last_rows = [table["rows"][-1] for table in tables if table["rows"]]
    dangerous = [int(match.group(1)) for match in re.finditer(r"Dangerous builds\s*=\s*(\d+)", text)]
    loop_times = [
        {
            "seconds": float(match.group(1)),
            "steps": int(match.group(2)),
            "atoms": int(match.group(3)),
        }
        for match in re.finditer(
            r"Loop time of\s+([0-9.eE+-]+).*?for\s+(\d+)\s+steps\s+with\s+(\d+)\s+atoms",
            text,
        )
    ]
    total_wall = None
    wall_matches = re.findall(r"Total wall time:\s*(.+)", text)
    if wall_matches:
        total_wall = wall_matches[-1].strip()

    table_summaries = []
    for table in tables:
        rows = table["rows"]
        first = rows[0] if rows else None
        last = rows[-1] if rows else None
        last_20 = rows[-20:]
        numeric_columns = [col for col in table["columns"] if rows and isinstance(rows[0].get(col), (int, float))]
        last_20_mean = {
            col: statistics.fmean(float(row[col]) for row in last_20)
            for col in numeric_columns
            if last_20
        }
        last_20_min = {
            col: min(float(row[col]) for row in last_20)
            for col in numeric_columns
            if last_20
        }
        last_20_max = {
            col: max(float(row[col]) for row in last_20)
            for col in numeric_columns
            if last_20
        }
        drift_first_to_last = {
            col: float(last[col]) - float(first[col])
            for col in numeric_columns
            if first is not None and last is not None
        }
        overall_mean = {
            col: statistics.fmean(float(row[col]) for row in rows)
            for col in numeric_columns
            if rows
        }
        overall_min = {
            col: min(float(row[col]) for row in rows)
            for col in numeric_columns
            if rows
        }
        overall_max = {
            col: max(float(row[col]) for row in rows)
            for col in numeric_columns
            if rows
        }
        table_summaries.append(
            {
                "columns": table["columns"],
                "n_rows": len(rows),
                "first": first,
                "last": last,
                "overall_mean": overall_mean,
                "overall_min": overall_min,
                "overall_max": overall_max,
                "last_20_mean": last_20_mean,
                "last_20_min": last_20_min,
                "last_20_max": last_20_max,
                "drift_first_to_last": drift_first_to_last,
            }
        )

    summary = {
        "log_path": str(log_path),
        "has_error": "error" in lower,
        "has_nan": bool(re.search(r"(^|[^a-zA-Z])nan([^a-zA-Z]|$)", lower)),
        "has_lost_atoms": "lost atoms" in lower,
        "dangerous_builds": dangerous,
        "dangerous_builds_max": max(dangerous) if dangerous else None,
        "loop_times": loop_times,
        "total_wall_time": total_wall,
        "n_thermo_tables": len(tables),
        "thermo_tables": table_summaries,
        "last_thermo": last_rows[-1] if last_rows else None,
    }
    if table_summaries:
        last_table = table_summaries[-1]
        summary["last_20_mean"] = last_table["last_20_mean"]
        summary["last_20_min"] = last_table["last_20_min"]
        summary["last_20_max"] = last_table["last_20_max"]
        summary["overall_mean"] = last_table["overall_mean"]
        summary["overall_min"] = last_table["overall_min"]
        summary["overall_max"] = last_table["overall_max"]
        summary["drift_first_to_last"] = last_table["drift_first_to_last"]
    summary["ok_basic"] = not summary["has_error"] and not summary["has_nan"] and not summary["has_lost_atoms"]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_path", type=Path)
    parser.add_argument("--output", type=Path, help="JSON output path. Defaults to log_summary.json next to the log.")
    args = parser.parse_args()

    summary = summarize_log(args.log_path)
    output = args.output or args.log_path.with_name("log_summary.json")
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    last = summary["last_thermo"] or {}
    print(f"log: {args.log_path}")
    print(f"ok_basic: {summary['ok_basic']}")
    print(f"ERROR: {summary['has_error']}  nan: {summary['has_nan']}  lost_atoms: {summary['has_lost_atoms']}")
    print(f"Dangerous builds: {summary['dangerous_builds']}")
    if last:
        fields = ["Step", "Temp", "PotEng", "KinEng", "TotEng", "Press", "Volume", "Lx", "Ly", "Lz"]
        print("last thermo:")
        for field in fields:
            if field in last:
                print(f"  {field}: {last[field]}")
    if summary.get("last_20_mean"):
        print("last 20 thermo mean:")
        for field in ["Temp", "PotEng", "TotEng", "Press"]:
            if field in summary["last_20_mean"]:
                print(f"  {field}: {summary['last_20_mean'][field]}")
    if summary.get("overall_mean"):
        print("overall thermo mean/range:")
        for field in ["Temp", "PotEng", "TotEng", "Press"]:
            if field in summary["overall_mean"]:
                print(
                    f"  {field}: mean={summary['overall_mean'][field]} "
                    f"min={summary['overall_min'][field]} max={summary['overall_max'][field]}"
                )
    if summary.get("drift_first_to_last"):
        print("drift first->last:")
        for field in ["Temp", "PotEng", "TotEng", "Press"]:
            if field in summary["drift_first_to_last"]:
                print(f"  {field}: {summary['drift_first_to_last'][field]}")
    print(f"json: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
