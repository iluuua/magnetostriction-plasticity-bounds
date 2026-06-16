"""Stage B post-run decision and launch-gate helpers.

This module is intentionally file/JSON oriented. It reads completed runner
state and small analysis artifacts, but it never starts LAMMPS by itself.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from . import paths


STAGEB_STRUCTURE_MODE = "build_stageB_realism_100k"
POSTRUN_DECISION_JSON = "postrun_decision.json"
POSTRUN_DECISION_MD = "postrun_decision.md"
POSTRUN_AGENT_REPORT = "agent_report_stageB_realism_100k_postrun_decision.md"
CONFIRMATION_APPROVAL_FILE = "APPROVE_500K_CONFIRMATION.txt"
CONFIRMATION_APPROVAL_TEXT = "APPROVE_500K_CONFIRMATION"
NEIGHBOR_WORKAROUND = "neigh_modify    delay 0 every 10 check no"
FORBIDDEN_INPUT_PATTERNS = {
    "minimize": r"(?mi)^\s*minimize\b",
    "min_style": r"(?mi)^\s*min_style\b",
    "thermo 1": r"(?mi)^\s*thermo\s+1\s*$",
}
FORBIDDEN_INPUT_LITERALS = ("CUDA_LAUNCH_BLOCKING", "compute-sanitizer")
DEFAULT_500K_ATOM_TARGET = 500000
DEFAULT_500K_DISK_GB = 60.0


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp_dir() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, headers: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_yaml(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def first_number(data: dict[str, Any], keys: Iterable[str], default: float = 0.0) -> float:
    for key in keys:
        cur: Any = data
        found = True
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                found = False
                break
            cur = cur[part]
        if found:
            return as_float(cur, default)
    return default


def normalize_run_root(run_root: str | Path) -> Path:
    root = Path(run_root)
    if not root.is_absolute():
        root = paths.REPO_ROOT / root
    return root.resolve()


def is_stageb_production_record(rec: dict[str, Any]) -> bool:
    if rec.get("phase") != "production":
        return False
    structure = rec.get("structure") or {}
    if structure.get("stageB_case"):
        return True
    if structure.get("structure_mode") == STAGEB_STRUCTURE_MODE:
        return True
    return str(rec.get("stage", "")).startswith("B3")


def stageb_case_name(rec: dict[str, Any]) -> str:
    structure = rec.get("structure") or {}
    return str(structure.get("stageB_case") or rec.get("case_id") or "")


def case_status_is_running(rec: dict[str, Any]) -> bool:
    status = str(rec.get("status") or "").lower()
    if status.startswith("running"):
        return True
    if rec.get("success") is True:
        return False
    steps_target = as_int(rec.get("steps_target"), 0)
    steps_done = as_int(rec.get("steps_completed") or rec.get("current_step"), 0)
    return steps_target > 0 and 0 <= steps_done < steps_target and not case_has_unstable_failure(rec)


def case_has_unstable_failure(rec: dict[str, Any]) -> bool:
    if rec.get("success") is True:
        return False
    status = str(rec.get("status") or "").lower()
    if "failed" in status or rec.get("hung") or rec.get("timed_out"):
        return True
    markers = json.dumps(rec.get("error_markers") or {}, ensure_ascii=False).lower()
    reasons = json.dumps(rec.get("failure_reasons") or [], ensure_ascii=False).lower()
    text = f"{markers} {reasons}"
    return any(token in text for token in ("cuda", "illegal", "nan", "lost atoms", "hang", "error"))


def case_log_clean(rec: dict[str, Any]) -> bool:
    summary = rec.get("log_summary") or {}
    if summary.get("has_error") or summary.get("nan_found") or summary.get("lost_atoms"):
        return False
    text = json.dumps(rec.get("error_markers") or {}, ensure_ascii=False).lower()
    return not any(token in text for token in ("cuda", "illegal", "nan", "lost"))


def load_effective_config(run_root: Path) -> dict[str, Any]:
    return load_yaml(run_root / "effective_config.yaml", {}) or {}


def stageb_stage_config(cfg: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    for name, stage in (cfg.get("stages") or {}).items():
        if isinstance(stage, dict) and stage.get("structure_mode") == STAGEB_STRUCTURE_MODE:
            return str(name), stage
    return None, {}


def expected_production_case_ids(run_root: Path, state: dict[str, Any]) -> list[str]:
    cfg = load_effective_config(run_root)
    _stage_name, stage = stageb_stage_config(cfg)
    ids = [str(x) for x in stage.get("production_case_ids") or []]
    if ids:
        return ids
    cases = []
    for rec in (state.get("cases") or {}).values():
        if is_stageb_production_record(rec):
            name = stageb_case_name(rec)
            if name and name not in cases:
                cases.append(name)
    return cases


def find_analysis_paths(run_root: Path, state: dict[str, Any]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for rec in (state.get("cases") or {}).values():
        if not is_stageb_production_record(rec):
            continue
        case = stageb_case_name(rec)
        raw = rec.get("analysis")
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = (paths.REPO_ROOT / p).resolve()
            if p.is_file() and case:
                found[case] = p
    for p in run_root.glob("cases/**/production/analysis.json"):
        # Runner analysis JSON stores the runtime case id
        # (<stageB_case>_production). The directory name is the stable Stage B
        # design id used by configs and branch decisions.
        case = str(p.parent.parent.name)
        found.setdefault(case, p)
    return found


def strong_signal_reasons(analysis: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if as_int(analysis.get("dislocation_segments"), 0) > 0:
        reasons.append("dislocation_segments_gt_0")
    if as_float(analysis.get("dislocation_length_A"), 0.0) > 0.0:
        reasons.append("dislocation_length_A_gt_0")
    if as_float(analysis.get("dislocation_density_per_m2"), 0.0) > 0.0:
        reasons.append("dislocation_density_per_m2_gt_0")
    return reasons


def weak_signal_reasons(analysis: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    pz = analysis.get("plastic_zone") or {}
    hcp_beyond = as_int(pz.get("hcp_atoms_beyond_1p3_shell"), 0)
    defect_beyond = as_int(pz.get("defect_atoms_beyond_1p3_shell"), 0)
    max_dist = as_float(pz.get("max_normalized_ellipsoid_distance"), 0.0)
    if hcp_beyond >= 5:
        reasons.append("hcp_atoms_beyond_shell_material")
    if defect_beyond > 3 and max_dist >= 1.35:
        reasons.append("plastic_zone_beyond_boundary_noise")
    if bool(analysis.get("plastic_zone_detected")):
        reasons.append("plastic_zone_detected")
    if bool(first_number(analysis, ("atomic_strain.localized_near_inclusion",), 0.0)):
        reasons.append("atomic_strain_localized_near_inclusion")
    if bool(first_number(analysis, ("non_affine.localized_near_gb",), 0.0)):
        reasons.append("non_affine_localized_near_gb")
    return reasons


def deformation_only_reasons(analysis: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    p99 = first_number(
        analysis,
        (
            "matrix_displacement_p99_A",
            "displacement.matrix.p99_A",
            "deformation_proxy.matrix_p99_A",
        ),
        0.0,
    )
    max_disp = first_number(
        analysis,
        (
            "matrix_displacement_max_A",
            "displacement.matrix.max_A",
            "deformation_proxy.matrix_max_A",
        ),
        0.0,
    )
    if p99 >= 0.75:
        reasons.append("matrix_displacement_p99_high")
    if max_disp >= 2.0:
        reasons.append("matrix_displacement_max_high")
    localization = analysis.get("localization") or {}
    if localization.get("interface_shell") or localization.get("gb_band"):
        reasons.append("displacement_localized_interface_or_gb")
    return reasons


def score_analysis(analysis: dict[str, Any]) -> float:
    return (
        1000.0 * len(strong_signal_reasons(analysis))
        + 10.0 * len(weak_signal_reasons(analysis))
        + as_float(analysis.get("dislocation_length_A"), 0.0)
        + 0.001 * as_float(analysis.get("dislocation_density_per_m2"), 0.0)
    )


@dataclass
class PostrunSummary:
    run_root: Path
    state: dict[str, Any]
    expected_cases: list[str]
    completed_cases: list[str]
    failed_cases: list[str]
    running_cases: list[str]
    missing_cases: list[str]
    analysis_by_case: dict[str, dict[str, Any]]
    analysis_paths: dict[str, Path]
    production_logs_clean: bool
    status: str
    branch: str
    signal_cases: list[dict[str, Any]] = field(default_factory=list)
    winner_case: str | None = None
    winner_reason: str = ""


def collect_postrun_summary(run_root: str | Path) -> PostrunSummary:
    root = normalize_run_root(run_root)
    state = read_json(root / "state.json", {}) or {}
    expected = expected_production_case_ids(root, state)
    completed: list[str] = []
    failed: list[str] = []
    running: list[str] = []
    production_records: dict[str, dict[str, Any]] = {}
    logs_clean = True
    for rec in (state.get("cases") or {}).values():
        if not is_stageb_production_record(rec):
            continue
        case = stageb_case_name(rec)
        if not case:
            continue
        production_records[case] = rec
        if case_status_is_running(rec):
            running.append(case)
        elif case_has_unstable_failure(rec):
            failed.append(case)
        elif rec.get("success") is True:
            completed.append(case)
            logs_clean = logs_clean and case_log_clean(rec)
    missing = [case for case in expected if case not in completed and case not in failed and case not in running]

    analysis_paths = find_analysis_paths(root, state)
    analysis_by_case: dict[str, dict[str, Any]] = {}
    for case, path in analysis_paths.items():
        data = read_json(path, {}) or {}
        if data:
            analysis_by_case[case] = data

    signal_cases: list[dict[str, Any]] = []
    weak_cases: list[dict[str, Any]] = []
    deformation_cases: list[dict[str, Any]] = []
    for case, data in analysis_by_case.items():
        strong = strong_signal_reasons(data)
        weak = weak_signal_reasons(data)
        deform = deformation_only_reasons(data)
        if strong:
            signal_cases.append({"case": case, "strength": "confirmed", "reasons": strong, "score": score_analysis(data)})
        elif weak:
            weak_cases.append({"case": case, "strength": "weak", "reasons": weak, "score": score_analysis(data)})
        elif deform:
            deformation_cases.append({"case": case, "strength": "deformation_only", "reasons": deform, "score": 1.0})

    if running or (missing and not failed):
        status = "incomplete"
        branch = "wait"
    elif failed or not logs_clean:
        status = "unstable"
        branch = "C_fix_geometry_or_protocol"
    elif signal_cases:
        status = "confirmed_dislocation_signal"
        branch = "A_500k_confirmation"
    elif weak_cases:
        status = "weak_plasticity_candidate"
        branch = "A1_repeat_100k_then_250k_or_500k_manual"
        signal_cases = weak_cases
    elif deformation_cases:
        status = "deformation_only_no_dxa"
        branch = "B_no_dislocation_validation"
        signal_cases = deformation_cases
    else:
        status = "no_dislocation_no_plasticity"
        branch = "B_no_dislocation_validation"

    winner_case = None
    winner_reason = ""
    if signal_cases:
        best = sorted(signal_cases, key=lambda row: float(row.get("score") or 0.0), reverse=True)[0]
        winner_case = str(best["case"])
        winner_reason = ", ".join(str(x) for x in best.get("reasons") or [])

    return PostrunSummary(
        run_root=root,
        state=state,
        expected_cases=expected,
        completed_cases=sorted(set(completed)),
        failed_cases=sorted(set(failed)),
        running_cases=sorted(set(running)),
        missing_cases=sorted(set(missing)),
        analysis_by_case=analysis_by_case,
        analysis_paths=analysis_paths,
        production_logs_clean=logs_clean,
        status=status,
        branch=branch,
        signal_cases=signal_cases,
        winner_case=winner_case,
        winner_reason=winner_reason,
    )


def allowed_for_branch(branch: str) -> list[str]:
    if branch == "A_500k_confirmation":
        return ["configs/stageB_500k_confirmation.template.yaml"]
    if branch == "B_no_dislocation_validation":
        return ["configs/stageB_no_dislocation_branch.template.yaml"]
    if branch == "C_fix_geometry_or_protocol":
        return ["scripts/extract_stageB_failed_case.py"]
    if branch == "A1_repeat_100k_then_250k_or_500k_manual":
        return ["manual Stage B 100k repeat/250k/500k review only"]
    return []


def forbidden_for_branch(branch: str) -> list[str]:
    common = ["full_factorial", "A2", "250k_unapproved", "700k", "parallel_lammps"]
    if branch != "A_500k_confirmation":
        return ["500k_confirmation"] + common
    return common


def build_decision(summary: PostrunSummary) -> dict[str, Any]:
    return {
        "generated_at": now_stamp(),
        "run_root": str(summary.run_root),
        "status": summary.status,
        "branch": summary.branch,
        "completed_cases": summary.completed_cases,
        "failed_cases": summary.failed_cases,
        "running_cases": summary.running_cases,
        "missing_cases": summary.missing_cases,
        "missing_analysis_cases": [
            case for case in summary.completed_cases if case not in summary.analysis_by_case
        ],
        "expected_cases": summary.expected_cases,
        "signal_cases": summary.signal_cases,
        "winner_case": summary.winner_case,
        "winner_reason": summary.winner_reason,
        "production_logs_clean": bool(summary.production_logs_clean),
        "allowed_next_configs": allowed_for_branch(summary.branch),
        "forbidden_next_configs": forbidden_for_branch(summary.branch),
        "manual_approval_required": True,
        "analysis_paths": {k: str(v) for k, v in sorted(summary.analysis_paths.items())},
        "summary_inputs": {
            "state_json": str(summary.run_root / "state.json"),
            "production_summary_csv": str(summary.run_root / "production_summary.csv"),
            "runtime_summary_csv": str(summary.run_root / "tables" / "runtime_summary.csv"),
            "defect_summary_csv": str(summary.run_root / "tables" / "defect_summary.csv"),
        },
    }


def dxa_summary_rows(summary: PostrunSummary) -> list[dict[str, Any]]:
    rows = []
    for case, data in sorted(summary.analysis_by_case.items()):
        rows.append(
            {
                "case": case,
                "dislocation_segments": as_int(data.get("dislocation_segments"), 0),
                "dislocation_length_A": as_float(data.get("dislocation_length_A"), 0.0),
                "dislocation_density_per_m2": as_float(data.get("dislocation_density_per_m2"), 0.0),
                "burgers_types": json.dumps(data.get("burgers_types") or data.get("dislocation_types") or []),
                "analysis": str(summary.analysis_paths.get(case, "")),
            }
        )
    return rows


def deformation_summary_rows(summary: PostrunSummary) -> list[dict[str, Any]]:
    rows = []
    for case, data in sorted(summary.analysis_by_case.items()):
        rows.append(
            {
                "case": case,
                "matrix_displacement_p50_A": first_number(data, ("matrix_displacement_p50_A", "displacement.matrix.p50_A"), 0.0),
                "matrix_displacement_p95_A": first_number(data, ("matrix_displacement_p95_A", "displacement.matrix.p95_A"), 0.0),
                "matrix_displacement_p99_A": first_number(data, ("matrix_displacement_p99_A", "displacement.matrix.p99_A"), 0.0),
                "matrix_displacement_max_A": first_number(data, ("matrix_displacement_max_A", "displacement.matrix.max_A"), 0.0),
                "inclusion_displacement_max_A": first_number(data, ("inclusion_displacement_max_A", "displacement.inclusion.max_A"), 0.0),
            }
        )
    return rows


def localization_summary_rows(summary: PostrunSummary) -> list[dict[str, Any]]:
    rows = []
    for case, data in sorted(summary.analysis_by_case.items()):
        pz = data.get("plastic_zone") or {}
        loc = data.get("localization") or {}
        rows.append(
            {
                "case": case,
                "hcp_atoms_beyond_1p3_shell": as_int(pz.get("hcp_atoms_beyond_1p3_shell"), 0),
                "defect_atoms_beyond_1p3_shell": as_int(pz.get("defect_atoms_beyond_1p3_shell"), 0),
                "max_normalized_ellipsoid_distance": as_float(pz.get("max_normalized_ellipsoid_distance"), 0.0),
                "interface_shell_signal": loc.get("interface_shell"),
                "near_matrix_signal": loc.get("near_matrix"),
                "mid_matrix_signal": loc.get("mid_matrix"),
                "gb_band_signal": loc.get("gb_band"),
            }
        )
    return rows


def decision_markdown(decision: dict[str, Any]) -> str:
    lines = [
        "# Stage B Realism 100k Post-Run Decision",
        "",
        f"Generated: {decision['generated_at']}",
        f"Run root: `{decision['run_root']}`",
        "",
        f"- status: `{decision['status']}`",
        f"- branch: `{decision['branch']}`",
        f"- winner_case: `{decision.get('winner_case')}`",
        f"- winner_reason: `{decision.get('winner_reason')}`",
        f"- production_logs_clean: `{decision.get('production_logs_clean')}`",
        f"- manual_approval_required: `{decision.get('manual_approval_required')}`",
        "",
        "## Cases",
        "",
        f"- completed: {', '.join(decision['completed_cases']) or 'none'}",
        f"- failed: {', '.join(decision['failed_cases']) or 'none'}",
        f"- running: {', '.join(decision['running_cases']) or 'none'}",
        f"- missing: {', '.join(decision['missing_cases']) or 'none'}",
        f"- missing analysis: {', '.join(decision['missing_analysis_cases']) or 'none'}",
        "",
        "## Signal Cases",
        "",
    ]
    if decision["signal_cases"]:
        for row in decision["signal_cases"]:
            lines.append(f"- {row['case']}: {row['strength']} ({', '.join(row['reasons'])})")
    else:
        lines.append("- none")
    lines += [
        "",
        "## Allowed Next Configs",
        "",
        *[f"- `{x}`" for x in decision["allowed_next_configs"]],
        "",
        "## Forbidden Next Configs",
        "",
        *[f"- `{x}`" for x in decision["forbidden_next_configs"]],
    ]
    return "\n".join(lines).rstrip() + "\n"


def baseline_comparison_markdown(decision: dict[str, Any]) -> str:
    return (
        "# Stage B vs A1 Negative Baseline\n\n"
        f"Generated: {decision['generated_at']}\n\n"
        "A1_custom_100k baseline remained a stable negative: zero DXA "
        "dislocation segments, zero line length, and no material matrix HCP/plastic-zone "
        "signal beyond the inclusion shell.\n\n"
        f"Current Stage B decision status: `{decision['status']}`.\n"
        f"Recommended branch: `{decision['branch']}`.\n\n"
        "Interpretation rule: displacement maxima alone do not justify a 500k "
        "confirmation. 500k is only opened by confirmed DXA line signal.\n"
    )


def write_postrun_outputs(summary: PostrunSummary, decision: dict[str, Any]) -> list[Path]:
    root = summary.run_root
    written: list[Path] = []
    write_json(root / POSTRUN_DECISION_JSON, decision)
    written.append(root / POSTRUN_DECISION_JSON)
    (root / POSTRUN_DECISION_MD).write_text(decision_markdown(decision), encoding="utf-8")
    written.append(root / POSTRUN_DECISION_MD)
    (paths.REPO_ROOT / POSTRUN_AGENT_REPORT).write_text(decision_markdown(decision), encoding="utf-8")
    written.append(paths.REPO_ROOT / POSTRUN_AGENT_REPORT)
    write_csv_rows(
        root / "tables" / "dxa_summary.csv",
        ["case", "dislocation_segments", "dislocation_length_A", "dislocation_density_per_m2", "burgers_types", "analysis"],
        dxa_summary_rows(summary),
    )
    write_csv_rows(
        root / "tables" / "deformation_summary.csv",
        [
            "case",
            "matrix_displacement_p50_A",
            "matrix_displacement_p95_A",
            "matrix_displacement_p99_A",
            "matrix_displacement_max_A",
            "inclusion_displacement_max_A",
        ],
        deformation_summary_rows(summary),
    )
    write_csv_rows(
        root / "tables" / "localization_summary.csv",
        [
            "case",
            "hcp_atoms_beyond_1p3_shell",
            "defect_atoms_beyond_1p3_shell",
            "max_normalized_ellipsoid_distance",
            "interface_shell_signal",
            "near_matrix_signal",
            "mid_matrix_signal",
            "gb_band_signal",
        ],
        localization_summary_rows(summary),
    )
    for name in ("dxa_summary.csv", "deformation_summary.csv", "localization_summary.csv"):
        written.append(root / "tables" / name)
    (root / "baseline_comparison.md").write_text(baseline_comparison_markdown(decision), encoding="utf-8")
    written.append(root / "baseline_comparison.md")
    return written


def analyze_run_root(run_root: str | Path, *, dry_run: bool = False, write_incomplete: bool = False) -> dict[str, Any]:
    summary = collect_postrun_summary(run_root)
    decision = build_decision(summary)
    decision["dry_run"] = bool(dry_run)
    decision["writes"] = []
    if not dry_run:
        if summary.status == "incomplete" and not write_incomplete:
            decision["write_skipped_reason"] = "run incomplete; post-run files are not written until completion"
        else:
            decision["writes"] = [str(p) for p in write_postrun_outputs(summary, decision)]
    return decision


def load_postrun_decision(run_root: str | Path, decision_path: str | Path | None = None) -> tuple[dict[str, Any] | None, Path]:
    root = normalize_run_root(run_root)
    path = Path(decision_path) if decision_path else root / POSTRUN_DECISION_JSON
    if not path.is_absolute():
        path = (paths.REPO_ROOT / path).resolve()
    return read_json(path, None), path


def active_lammps_processes() -> list[str]:
    if os.environ.get("STAGEB_ASSUME_NO_ACTIVE_LAMMPS_FOR_TESTS") == "1":
        return []
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq lmp_kokkos_cuda.exe"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            return [line.strip() for line in proc.stdout.splitlines() if "lmp_kokkos_cuda.exe" in line.lower()]
        except Exception as exc:
            return [f"process check failed: {exc}"]
    try:
        proc = subprocess.run(
            ["pgrep", "-af", "lmp_kokkos_cuda|lmp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def disk_free_gb(path: Path) -> float:
    p = path.resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free / (1024**3)


def approval_file_ok(run_root: Path) -> bool:
    p = run_root / CONFIRMATION_APPROVAL_FILE
    return p.is_file() and p.read_text(encoding="utf-8", errors="replace").strip() == CONFIRMATION_APPROVAL_TEXT


def decision_signal_entry(decision: dict[str, Any], case: str) -> dict[str, Any] | None:
    for row in decision.get("signal_cases") or []:
        if row.get("case") == case:
            return row
    return None


def original_stageb_case_config(run_root: Path, case_id: str) -> dict[str, Any]:
    _stage_name, stage = stageb_stage_config(load_effective_config(run_root))
    for case in stage.get("cases") or []:
        if str(case.get("case_id")) == str(case_id):
            return dict(case)
    return {}


def make_500k_confirmation_config(run_root: str | Path, decision: dict[str, Any]) -> dict[str, Any]:
    root = normalize_run_root(run_root)
    winner = decision.get("winner_case")
    if not winner:
        raise ValueError("winner_case is required")
    original = original_stageb_case_config(root, str(winner))
    signal = decision_signal_entry(decision, str(winner)) or {}
    eps_z = as_float(original.get("eps_z", signal.get("eps_z", 0.0100)), 0.0100)
    seed = as_int(original.get("deterministic_seed"), 73002) + 500000
    case: dict[str, Any] = {
        "case_id": f"{winner}_500k_confirmation",
        "atom_target": DEFAULT_500K_ATOM_TARGET,
        "position": original.get("position", "near_grain_boundary"),
        "predefect": original.get("predefect", "perfect"),
        "eps_z": eps_z,
        "deterministic_seed": seed,
        "source_winner_case": winner,
    }
    if case["predefect"] == "vacancies_medium":
        if "vacancy_fraction" in original:
            case["vacancy_fraction"] = original["vacancy_fraction"]
        elif "vacancy_count" in original:
            case["vacancy_count"] = max(1, as_int(original["vacancy_count"], 200) * 5)
    return {
        "experiment": {
            "name": "stageB_realism_100k_smoke_production",
            "mode": "stageB_500k_confirmation",
            "description": "Single winner-case 500k confirmation gated by Stage B post-run decision",
            "output_root": "runs/stageB_500k_confirmation",
            "temperature_K": 300,
            "potential_track": "MEAM_Jelinek_2012",
            "magnetic_surrogate": "inclusion_eigenstrain",
            "source_stageB_run_root": str(root),
            "source_postrun_decision": str(root / POSTRUN_DECISION_JSON),
        },
        "production_reliability": {
            "production_chunk_steps": 10000,
            "max_no_progress_minutes": 25,
            "watchdog_poll_seconds": 30,
            "resume_from_latest_restart": True,
            "retry_hung_chunk_once": True,
            "update_state_after_each_chunk": True,
            "write_restart_after_each_chunk": True,
        },
        "gpu_profile": {
            "name": "kokkos_cuda_meam_neighbor_check_no",
            "enabled": True,
            "lammps_executable": r"B:\builds\lammps-kokkos-cuda-cuda124-msvc1439\build\lmp_kokkos_cuda.exe",
            "command_args": ["-k", "on", "g", "1", "-sf", "kk", "-pk", "kokkos", "newton", "on", "neigh", "half", "gpu/aware", "off"],
            "required_input_rewrites": {"neighbor_policy": NEIGHBOR_WORKAROUND},
            "forbidden_environment": ["CUDA_LAUNCH_BLOCKING"],
        },
        "io_policy": {
            "thermo_every": {"smoke": 100, "short": 500, "production": 1000},
            "dump_every": {"smoke": 1000, "short": 5000, "production": 10000},
            "restart_every": 10000,
            "write_final_data": True,
            "write_final_dump": True,
            "compress_large_dumps": False,
        },
        "resources": {
            "gpu_count": 1,
            "gpu_memory_gb": 12,
            "cpu_helper_threads": 6,
            "min_free_disk_gb_before_stage": DEFAULT_500K_DISK_GB,
            "min_free_disk_gb_before_large_stage": DEFAULT_500K_DISK_GB,
            "max_run_hours": {"smoke": 10, "short": 20, "production_B3_500k_confirmation": 120},
            "stop_if_gpu_memory_error": True,
            "stop_if_disk_below_threshold": True,
        },
        "stages": {
            "B3_500k_confirmation": {
                "enabled": True,
                "structure_mode": STAGEB_STRUCTURE_MODE,
                "atom_targets": [DEFAULT_500K_ATOM_TARGET],
                "eps_z": [eps_z],
                "smoke_steps": 2000,
                "short_steps": 0,
                "production_steps": 100000,
                "prep_t_start_K": 50.0,
                "prep_ramp_steps": 3000,
                "prep_steps": 5000,
                "run_short_after_smoke_pass": False,
                "run_production_after_smoke_pass": True,
                "gate_required_before_each_production": False,
                "analyze_after_production": True,
                "max_smoke_cases": 1,
                "max_production_cases": 1,
                "production_case_ids": [case["case_id"]],
                "cases": [case],
            }
        },
        "analysis": {"enabled": True, "tools": ["ovito_dxa"], "compare_to_stage_baseline": True},
        "science_gates": {
            "stability_pass": {
                "require_exit_code_zero": True,
                "forbid_patterns": ["ERROR", "nan", "lost atoms", "cudaError", "illegal memory"],
            },
            "production_signal": {"interesting_if_any": ["dislocation_count_gt_0"]},
            "escalation_rules": ["single winner-case confirmation only; no full factorial"],
        },
    }


def render_500k_input_safety_preview(config: dict[str, Any]) -> str:
    stage = config["stages"]["B3_500k_confirmation"]
    case = stage["cases"][0]
    return (
        f"# Safety preview for {case['case_id']}\n"
        "units           metal\n"
        "atom_style      atomic\n"
        "read_data       <generated_winner_case_data>\n"
        "pair_style      meam\n"
        "neighbor        2.0 bin\n"
        f"{NEIGHBOR_WORKAROUND}\n"
        "thermo          1000\n"
        "restart         10000 restart.<case>.*\n"
        "run             100000\n"
        "write_dump      all custom dump.<case>_final.lammpstrj id type x y z modify sort id\n"
    )


def input_preview_is_safe(text: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if NEIGHBOR_WORKAROUND not in text:
        reasons.append("missing neighbor workaround")
    for label, pattern in FORBIDDEN_INPUT_PATTERNS.items():
        if re.search(pattern, text):
            reasons.append(f"forbidden {label}")
    for literal in FORBIDDEN_INPUT_LITERALS:
        if literal in text:
            reasons.append(f"forbidden {literal}")
    return not reasons, reasons


@dataclass
class GateResult:
    allowed: bool
    reasons: list[str]
    decision_path: Path | None = None
    decision: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    active_processes: list[str] = field(default_factory=list)
    disk_free_gb: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "decision_path": str(self.decision_path) if self.decision_path else None,
            "active_processes": self.active_processes,
            "disk_free_gb": self.disk_free_gb,
            "branch": (self.decision or {}).get("branch"),
            "status": (self.decision or {}).get("status"),
            "winner_case": (self.decision or {}).get("winner_case"),
        }


def validate_500k_gate(
    run_root: str | Path,
    *,
    mode: str,
    decision_path: str | Path | None = None,
    approve_cli: bool = False,
    active_process_checker: Callable[[], list[str]] = active_lammps_processes,
    disk_free_checker: Callable[[Path], float] = disk_free_gb,
) -> GateResult:
    root = normalize_run_root(run_root)
    decision, path = load_postrun_decision(root, decision_path)
    reasons: list[str] = []
    if decision is None:
        return GateResult(False, [f"postrun_decision.json not found: {path}"], path)
    if decision.get("status") == "incomplete":
        reasons.append("current Stage B 100k is incomplete")
    if decision.get("branch") != "A_500k_confirmation":
        reasons.append(f"postrun branch is {decision.get('branch')!r}, not A_500k_confirmation")
    winner = str(decision.get("winner_case") or "")
    if not winner:
        reasons.append("winner_case is not set")
    signal = decision_signal_entry(decision, winner) if winner else None
    if not signal or signal.get("strength") != "confirmed":
        reasons.append("winner_case has no confirmed DXA signal")
    if not decision.get("production_logs_clean", False):
        reasons.append("100k production logs are not clean")
    active = active_process_checker()
    if active:
        reasons.append("active LAMMPS process detected")
    free = disk_free_checker(root)
    if free < DEFAULT_500K_DISK_GB:
        reasons.append(f"disk_free_gb {free:.1f} below threshold {DEFAULT_500K_DISK_GB:.1f}")
    if mode == "launch" and not (approve_cli or approval_file_ok(root)):
        reasons.append("manual approval missing for 500k launch")

    config = None
    if not reasons:
        config = make_500k_confirmation_config(root, decision)
        cases = config["stages"]["B3_500k_confirmation"]["cases"]
        if len(cases) != 1:
            reasons.append("generated config does not contain exactly one winner case")
        atom_target = as_int(cases[0].get("atom_target"), 0)
        if atom_target < 450000 or atom_target > 600000:
            reasons.append(f"atom target outside 450k-600k: {atom_target}")
        ok, input_reasons = input_preview_is_safe(render_500k_input_safety_preview(config))
        if not ok:
            reasons.extend(input_reasons)
    return GateResult(not reasons, reasons, path, decision, config, active, free)


def write_500k_preflight_artifacts(output_run_root: Path, gate: GateResult) -> list[Path]:
    output_run_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    write_json(output_run_root / "state.json", {"status": "launch_ready" if gate.allowed else "blocked", **gate.as_dict()})
    written.append(output_run_root / "state.json")
    if gate.config:
        text = yaml.safe_dump(gate.config, sort_keys=False, allow_unicode=False)
        (output_run_root / "effective_config.yaml").write_text(text, encoding="utf-8")
        written.append(output_run_root / "effective_config.yaml")
        preview = render_500k_input_safety_preview(gate.config)
        (output_run_root / "input_safety_preview.in").write_text(preview, encoding="utf-8")
        written.append(output_run_root / "input_safety_preview.in")
        cmd = [
            str(paths.REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            "scripts\\run_stage_sweep.py",
            "--config",
            str(output_run_root / "effective_config.yaml"),
            "--run-dir",
            str(output_run_root),
            "--run-stage",
            "B3_500k_confirmation",
            "--gpu",
        ]
        (output_run_root / "command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
        written.append(output_run_root / "command.txt")
    lines = [
        "# Stage B 500k Confirmation Preflight",
        "",
        f"Generated: {now_stamp()}",
        f"allowed: `{gate.allowed}`",
        f"branch: `{(gate.decision or {}).get('branch')}`",
        f"winner_case: `{(gate.decision or {}).get('winner_case')}`",
        f"disk_free_gb: `{gate.disk_free_gb}`",
        "",
        "## Reasons",
        "",
    ]
    lines += [f"- {x}" for x in gate.reasons] if gate.reasons else ["- preflight passed"]
    (output_run_root / "launch_preflight_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(output_run_root / "launch_preflight_report.md")
    return written


def no_dislocation_proposals() -> list[dict[str, Any]]:
    return [
        {
            "id": "B6_positive_control_shear_30k",
            "priority": 1,
            "launch_mode": "launch-positive-control",
            "status": "proposal_ready_blocked_until_runner_support",
            "purpose": "prove DXA/analysis detects dislocations under a known positive-control load",
            "blocker": "no pure-Al/GB shear runner is implemented in stage_runner.gpu_grid.py",
        },
        {
            "id": "B6_seed_dislocation_nearGB_100k",
            "priority": 2,
            "launch_mode": "launch-seeded",
            "status": "disabled",
            "purpose": "test whether eigenstrain moves existing defects",
            "blocker": "seed_dislocation_if_available is explicitly unsupported until a real seeding tool exists",
        },
        {
            "id": "B6_cyclic_eigenstrain_100k",
            "priority": 3,
            "launch_mode": "launch-cyclic",
            "status": "proposal_ready_blocked_until_runner_support",
            "purpose": "dynamic 0 -> 0.010 -> 0 loading instead of static hold",
            "blocker": "cyclic eigenstrain schedule is not implemented in the current LAMMPS input generator",
        },
        {
            "id": "B6_platelet_or_faceted_inclusion_nearGB_100k",
            "priority": 4,
            "launch_mode": "launch-platelet",
            "status": "proposal_ready_blocked_until_builder_support",
            "purpose": "stress concentration from sharper inclusion geometry near GB",
            "blocker": "Stage B runtime builder currently supports ellipsoid_1_1_2 only",
        },
        {
            "id": "B6_high_temperature_assist_100k",
            "priority": 5,
            "launch_mode": "manual-only",
            "status": "disabled",
            "purpose": "400-600 K barrier-lowering check after physics and stability review",
            "blocker": "temperature branch requires separate approval and preflight",
        },
    ]


def validate_no_dislocation_gate(
    run_root: str | Path,
    *,
    mode: str,
    decision_path: str | Path | None = None,
    active_process_checker: Callable[[], list[str]] = active_lammps_processes,
) -> GateResult:
    root = normalize_run_root(run_root)
    decision, path = load_postrun_decision(root, decision_path)
    reasons: list[str] = []
    if decision is None:
        return GateResult(False, [f"postrun_decision.json not found: {path}"], path)
    branch = decision.get("branch")
    status = decision.get("status")
    if branch != "B_no_dislocation_validation" and status != "deformation_only_no_dxa":
        reasons.append(f"postrun branch/status does not allow no-dislocation branch: {branch!r}/{status!r}")
    if decision.get("status") in ("incomplete", "unstable"):
        reasons.append(f"postrun status blocks no-dislocation physics branch: {decision.get('status')}")
    if mode.startswith("launch"):
        active = active_process_checker()
        if active:
            reasons.append("active LAMMPS process detected")
        else:
            active = []
        selected = mode.replace("launch-", "B6_", 1)
        proposals = no_dislocation_proposals()
        match = [p for p in proposals if selected in p["id"] or p["launch_mode"] == mode]
        if match and match[0].get("status") != "supported":
            reasons.append(match[0]["blocker"])
        return GateResult(not reasons, reasons, path, decision, None, active)
    return GateResult(not reasons, reasons, path, decision, None, [])


def no_dislocation_plan_markdown(decision: dict[str, Any] | None = None) -> str:
    lines = [
        "# Stage B No-Dislocation Branch Plan",
        "",
        f"Generated: {now_stamp()}",
        "",
        "This branch is used only when Stage B 100k has no confirmed DXA line signal.",
        "It prevents a blind 500k escalation and orders lower-cost validation first.",
        "",
    ]
    if decision:
        lines += [
            f"- source status: `{decision.get('status')}`",
            f"- source branch: `{decision.get('branch')}`",
            "",
        ]
    lines += [
        "## Proposal Order",
        "",
        "| priority | experiment | status | blocker |",
        "| ---: | --- | --- | --- |",
    ]
    for p in no_dislocation_proposals():
        lines.append(f"| {p['priority']} | `{p['id']}` | {p['status']} | {p['blocker']} |")
    lines += [
        "",
        "No 500k, 250k, 700k, full factorial, or parallel LAMMPS launch is allowed from this branch.",
    ]
    return "\n".join(lines) + "\n"
