"""Build event timelines from existing Stage B analysis artifacts."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .schema import EventThresholds, TIMELINE_EXTRA_FIELDS, manifest_headers


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = repo_root() / p
    return p.resolve()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def as_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def first_value(data: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        cur: Any = data
        found = True
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                found = False
                break
            cur = cur[part]
        if found and cur is not None:
            return cur
    return default


def first_number(data: dict[str, Any], keys: Iterable[str], default: float | None = None) -> float | None:
    return as_float(first_value(data, keys, default), default)


def extract_step_from_text(text: str | None) -> int | None:
    if not text:
        return None
    matches = re.findall(r"(?:chunk|\.)(\d{4,})(?:_|\.|$)", str(text))
    if matches:
        return int(matches[-1])
    numbers = re.findall(r"(\d{4,})", str(text))
    if numbers:
        return int(numbers[-1])
    return None


def stable_frame_id(case_id: str, timestep: int | None, index: int) -> str:
    safe_case = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id).strip("_") or "case"
    if timestep is None:
        return f"{safe_case}__frame_{index:05d}"
    return f"{safe_case}__step_{timestep:010d}"


def _count_from_pct(analysis: dict[str, Any], pct_key: str, count_base_keys: tuple[str, ...]) -> int | None:
    pct = as_float(analysis.get(pct_key), None)
    if pct is None:
        return None
    base = first_number(analysis, count_base_keys, None)
    if base is None:
        return None
    return int(round(float(base) * pct / 100.0))


def event_metrics(analysis: dict[str, Any]) -> dict[str, Any]:
    plastic = analysis.get("plastic_zone") or {}
    matrix_count_keys = ("matrix_atoms", "matrix_atom_count", "atoms.matrix")
    hcp_atoms = as_int(first_value(analysis, ("hcp_atoms", "matrix_hcp_atoms"), None), None)
    if hcp_atoms is None:
        hcp_atoms = _count_from_pct(analysis, "hcp_pct", matrix_count_keys)
    other_atoms = as_int(first_value(analysis, ("other_atoms", "matrix_other_atoms"), None), None)
    if other_atoms is None:
        other_atoms = _count_from_pct(analysis, "other_pct", matrix_count_keys)
    hcp_beyond = as_int(plastic.get("hcp_atoms_beyond_1p3_shell"), 0) or 0
    defect_beyond = as_int(plastic.get("defect_atoms_beyond_1p3_shell"), 0) or 0
    return {
        "dislocation_segments": as_int(
            first_value(analysis, ("dislocation_segments", "dislocation_count"), 0),
            0,
        )
        or 0,
        "dislocation_line_length_A": first_number(
            analysis,
            ("dislocation_line_length_A", "dislocation_length_A", "total_line_length"),
            0.0,
        )
        or 0.0,
        "dislocation_density_per_m2": first_number(
            analysis,
            ("dislocation_density_per_m2", "dislocation_density"),
            0.0,
        )
        or 0.0,
        "hcp_atoms": max(hcp_atoms or 0, hcp_beyond),
        "other_atoms": max(other_atoms or 0, defect_beyond),
        "hcp_pct": first_number(analysis, ("hcp_pct", "hcp_fraction"), 0.0) or 0.0,
        "other_pct": first_number(analysis, ("other_pct", "other_fraction"), 0.0) or 0.0,
        "atomic_strain_p95": first_number(
            analysis,
            ("atomic_strain_p95", "atomic_strain.p95", "atomic_strain.matrix.p95"),
            None,
        ),
        "atomic_strain_p99": first_number(
            analysis,
            ("atomic_strain_p99", "atomic_strain.p99", "atomic_strain.matrix.p99"),
            None,
        ),
        "Dmin2_p95": first_number(
            analysis,
            ("Dmin2_p95", "dmin2_p95", "non_affine.p95", "non_affine.matrix.p95"),
            None,
        ),
        "Dmin2_p99": first_number(
            analysis,
            ("Dmin2_p99", "dmin2_p99", "non_affine.p99", "non_affine.matrix.p99"),
            None,
        ),
        "max_displacement": first_number(
            analysis,
            (
                "max_displacement",
                "matrix_displacement_max_A",
                "displacement.matrix.max_A",
                "deformation_proxy.matrix_max_A",
            ),
            None,
        ),
        "p95_displacement": first_number(
            analysis,
            ("matrix_displacement_p95_A", "displacement.matrix.p95_A"),
            None,
        ),
        "plastic_zone_detected": bool(analysis.get("plastic_zone_detected")),
    }


def classify_event(
    analysis: dict[str, Any],
    thresholds: EventThresholds | None = None,
) -> tuple[str, list[str], float, dict[str, Any]]:
    """Classify one frame/case analysis into the four required event classes."""

    t = thresholds or EventThresholds()
    m = event_metrics(analysis)
    reasons: list[str] = []
    if m["dislocation_segments"] >= t.confirmed_dxa_min_segments:
        reasons.append("dislocation_segments_gt_0")
    if m["dislocation_line_length_A"] >= t.confirmed_dxa_min_line_length_A:
        reasons.append("dislocation_line_length_A_gt_0")
    if m["dislocation_density_per_m2"] > 0.0:
        reasons.append("dislocation_density_per_m2_gt_0")
    if reasons:
        score = 1000.0 + 100.0 * m["dislocation_segments"] + float(m["dislocation_line_length_A"])
        return "confirmed_DXA", reasons, score, m

    weak_reasons: list[str] = []
    if m["hcp_atoms"] >= t.weak_hcp_min_atoms:
        weak_reasons.append("hcp_atoms_threshold")
    if float(m["hcp_pct"]) >= t.weak_hcp_min_pct:
        weak_reasons.append("hcp_pct_threshold")
    if m["other_atoms"] >= t.weak_other_min_atoms:
        weak_reasons.append("other_atoms_threshold")
    if m["plastic_zone_detected"]:
        weak_reasons.append("plastic_zone_detected")
    if weak_reasons:
        score = 100.0 + float(m["hcp_atoms"]) + 0.1 * float(m["other_atoms"])
        return "weak_hcp", weak_reasons, score, m

    deform_reasons: list[str] = []
    if (m["atomic_strain_p95"] or 0.0) >= t.deformation_strain_p95_min:
        deform_reasons.append("atomic_strain_p95_threshold")
    if (m["atomic_strain_p99"] or 0.0) >= t.deformation_strain_p99_min:
        deform_reasons.append("atomic_strain_p99_threshold")
    if (m["Dmin2_p95"] or 0.0) >= t.deformation_dmin2_p95_min:
        deform_reasons.append("Dmin2_p95_threshold")
    if (m["Dmin2_p99"] or 0.0) >= t.deformation_dmin2_p99_min:
        deform_reasons.append("Dmin2_p99_threshold")
    if (m["p95_displacement"] or 0.0) >= t.deformation_displacement_p95_min_A:
        deform_reasons.append("matrix_displacement_p95_threshold")
    if (m["max_displacement"] or 0.0) >= t.deformation_displacement_max_min_A:
        deform_reasons.append("max_displacement_threshold")
    if deform_reasons:
        score = 10.0 + (m["max_displacement"] or 0.0) + 10.0 * (m["atomic_strain_p99"] or 0.0)
        return "deformation_only", deform_reasons, score, m

    return "no_event", ["no_threshold_crossed"], 0.0, m


def iter_analysis_records(run_root: str | Path) -> list[dict[str, Any]]:
    root = normalize_path(run_root)
    state = read_json(root / "state.json", {}) or {}
    records: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for rec in (state.get("cases") or {}).values():
        analysis_path = rec.get("analysis")
        if not analysis_path:
            continue
        p = normalize_path(analysis_path)
        if not p.is_file():
            continue
        seen_paths.add(p)
        records.append({"record": rec, "analysis_path": p, "analysis": read_json(p, {}) or {}})
    for p in root.glob("cases/**/production/analysis.json"):
        rp = p.resolve()
        if rp in seen_paths:
            continue
        records.append({"record": {}, "analysis_path": rp, "analysis": read_json(rp, {}) or {}})
    return records


def output_path_from_record(rec: dict[str, Any], analysis: dict[str, Any]) -> str:
    dump = analysis.get("dump") or analysis.get("dump_file")
    if dump:
        return str(dump)
    for output in rec.get("outputs") or []:
        if str(output.get("name", "")).endswith("_final.lammpstrj"):
            return str(output.get("path"))
    return ""


def build_event_timeline(
    run_root: str | Path,
    thresholds: EventThresholds | None = None,
    *,
    default_camera_id: str = "stageB_overview_v1",
    default_coloring_mode: str = "structure_type",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(iter_analysis_records(run_root), start=1):
        rec = item["record"]
        analysis = item["analysis"]
        event_class, reasons, score, metrics = classify_event(analysis, thresholds)
        structure = rec.get("structure") or {}
        case_id = str(
            structure.get("stageB_case")
            or analysis.get("stageB_case")
            or analysis.get("case")
            or rec.get("case_id")
            or item["analysis_path"].parent.parent.name
        )
        dump_file = output_path_from_record(rec, analysis)
        timestep = as_int(
            first_value(analysis, ("timestep", "step", "current_step"), None),
            None,
        )
        if timestep is None:
            timestep = as_int(rec.get("steps_completed") or rec.get("current_step"), None)
        if timestep is None:
            timestep = extract_step_from_text(dump_file) or extract_step_from_text(rec.get("case_id"))
        row = {
            "frame_id": stable_frame_id(case_id, timestep, idx),
            "case_id": case_id,
            "timestep": timestep if timestep is not None else "",
            "time_ps": first_value(analysis, ("time_ps",), ""),
            "dump_file": dump_file,
            "restart_file": "",
            "camera_id": default_camera_id,
            "coloring_mode": default_coloring_mode,
            "visible_layers": "atoms,inclusion,gb,legend,scalebar,timestep_label",
            "temperature": first_value(analysis, ("temperature", "temp"), rec.get("final_temp", "")),
            "pressure": first_value(analysis, ("pressure", "press"), rec.get("final_press", "")),
            "pe": first_value(analysis, ("pe", "potential_energy"), rec.get("final_pe", "")),
            "ke": first_value(analysis, ("ke", "kinetic_energy"), rec.get("final_ke", "")),
            "etotal": first_value(analysis, ("etotal", "total_energy"), rec.get("final_etotal", "")),
            "pxx": first_value(analysis, ("pxx", "stress.pxx"), ""),
            "pyy": first_value(analysis, ("pyy", "stress.pyy"), ""),
            "pzz": first_value(analysis, ("pzz", "stress.pzz"), ""),
            "eps_z": first_value(analysis, ("eps_z",), rec.get("eps_z", "")),
            "dislocation_segments": metrics["dislocation_segments"],
            "dislocation_line_length_A": metrics["dislocation_line_length_A"],
            "hcp_atoms": metrics["hcp_atoms"],
            "other_atoms": metrics["other_atoms"],
            "atomic_strain_p95": metrics["atomic_strain_p95"] if metrics["atomic_strain_p95"] is not None else "",
            "atomic_strain_p99": metrics["atomic_strain_p99"] if metrics["atomic_strain_p99"] is not None else "",
            "Dmin2_p95": metrics["Dmin2_p95"] if metrics["Dmin2_p95"] is not None else "",
            "Dmin2_p99": metrics["Dmin2_p99"] if metrics["Dmin2_p99"] is not None else "",
            "max_displacement": metrics["max_displacement"] if metrics["max_displacement"] is not None else "",
            "event_class": event_class,
            "stage": rec.get("stage", ""),
            "phase": rec.get("phase", ""),
            "analysis_file": str(item["analysis_path"]),
            "event_score": round(float(score), 6),
            "event_reasons": ";".join(reasons),
        }
        rows.append(row)
    return sorted(rows, key=lambda r: (str(r["case_id"]), as_int(r["timestep"], -1) or -1, str(r["frame_id"])))


def write_csv_rows(path: Path, headers: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def event_report_markdown(run_root: Path, rows: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row["event_class"])] = counts.get(str(row["event_class"]), 0) + 1
    lines = [
        "# Event Detection Report",
        "",
        f"Generated: {now_stamp()}",
        f"Run root: `{run_root}`",
        "",
        "## Summary",
        "",
    ]
    if rows:
        for event_class in ("confirmed_DXA", "weak_hcp", "deformation_only", "no_event"):
            lines.append(f"- {event_class}: {counts.get(event_class, 0)}")
    else:
        lines.append("- no analysis frames were available")
    lines += ["", "## Frames", "", "| frame | case | step | event_class | reasons |", "| --- | --- | ---: | --- | --- |"]
    for row in rows:
        lines.append(
            f"| `{row['frame_id']}` | `{row['case_id']}` | {row['timestep'] or ''} | "
            f"`{row['event_class']}` | {row['event_reasons']} |"
        )
    lines += [
        "",
        "Notes:",
        "",
        "- This is a post-processing artifact built from existing analysis JSON files.",
        "- It does not prove a high-frequency event onset unless frame cadence is fine enough.",
        "- Rerun windows are generated separately as dry-run plans and require operator approval before launch.",
    ]
    return "\n".join(lines) + "\n"


def write_event_timeline_outputs(
    run_root: str | Path,
    output_dir: str | Path | None = None,
    thresholds: EventThresholds | None = None,
) -> dict[str, Any]:
    root = normalize_path(run_root)
    out = normalize_path(output_dir) if output_dir else root / "event_pipeline"
    rows = build_event_timeline(root, thresholds)
    headers = manifest_headers(extra=True)
    csv_path = out / "event_timeline.csv"
    json_path = out / "event_timeline.json"
    report_path = out / "event_detection_report.md"
    write_csv_rows(csv_path, headers, rows)
    write_json(
        json_path,
        {
            "generated_at": now_stamp(),
            "run_root": str(root),
            "schema": headers,
            "event_classes": ["no_event", "deformation_only", "weak_hcp", "confirmed_DXA"],
            "frames": rows,
        },
    )
    report_path.write_text(event_report_markdown(root, rows), encoding="utf-8")
    return {
        "run_root": str(root),
        "output_dir": str(out),
        "frame_count": len(rows),
        "writes": [str(csv_path), str(json_path), str(report_path)],
        "event_classes": sorted({str(r["event_class"]) for r in rows}),
    }
