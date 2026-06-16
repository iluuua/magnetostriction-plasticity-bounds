"""Safe Stage B focus-run transition helpers.

This module writes small handoff and preflight artifacts only. It never starts
LAMMPS, OVITO, or ffmpeg.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
OLD_RUN_ROOT_DEFAULT = Path("runs/stageB_realism_100k/20260613-222836")
SNAPSHOT_DIRNAME = "handoff_completed_cases_snapshot"
FOCUS_STAGE = "B3_nearGB_vacancies_focus_100k"
FOCUS_OUTPUT_ROOT = "stageB_nearGB_vacancies_focus_100k"
FOCUS_CASE_IDS = [
    "B3_nearGB_vacancies_medium_eps0025",
    "B3_nearGB_vacancies_medium_eps0100",
]
CURRENT_CASE4 = "B3_interior_vacancies_medium_eps0100"
NEIGHBOR_WORKAROUND = "neigh_modify    delay 0 every 10 check no"
SMALL_HASH_BYTES = 2 * 1024 * 1024
COPY_SMALL_BYTES = 2 * 1024 * 1024


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp_dir() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def normalize_repo_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or default


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_large_run_payload(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith("dump.")
        or name.startswith("restart.")
        or name.startswith("data.")
        or name.endswith(".lammpstrj")
    )


def file_manifest_entry(
    path: Path,
    *,
    run_root: Path,
    snapshot_dir: Path | None = None,
    category: str,
    case_id: str | None = None,
) -> dict[str, Any]:
    st = path.stat()
    entry: dict[str, Any] = {
        "category": category,
        "case_id": case_id or "",
        "name": path.name,
        "absolute_path": str(path.resolve()),
        "relative_path": repo_relative(path),
        "run_root_relative_path": path.resolve().relative_to(run_root).as_posix()
        if path.resolve().is_relative_to(run_root.resolve())
        else "",
        "size_bytes": int(st.st_size),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        "sha256": "",
        "copied_to": "",
        "copy_policy": "manifest_reference",
    }
    if st.st_size <= SMALL_HASH_BYTES:
        entry["sha256"] = sha256_file(path)
    if snapshot_dir and st.st_size <= COPY_SMALL_BYTES and not is_large_run_payload(path):
        dest = snapshot_dir / "files" / entry["run_root_relative_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        entry["copied_to"] = repo_relative(dest)
        entry["copy_policy"] = "copied_small_file"
    return entry


def stageb_case_from_record(rec: dict[str, Any]) -> str:
    structure = rec.get("structure") or {}
    raw = str(structure.get("stageB_case") or rec.get("case_id") or "")
    return raw.removesuffix("_production")


def production_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rec in (state.get("cases") or {}).values():
        if rec.get("phase") == "production" and str(rec.get("stage", "")).startswith("B3"):
            records.append(rec)
    return sorted(records, key=lambda r: str(r.get("started_at") or ""))


def completed_production_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in production_records(state) if r.get("success") is True and str(r.get("status")) == "success"]


def running_production_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in production_records(state) if str(r.get("status", "")).startswith("running")]


def case_production_dir(run_root: Path, case_id: str) -> Path:
    return run_root / "cases" / "B3_realism_100k" / case_id / "production"


def gather_case_files(run_root: Path, case_id: str, *, include_in_progress: bool = False) -> list[Path]:
    prod = case_production_dir(run_root, case_id)
    if not prod.is_dir():
        return []
    files: list[Path] = []
    patterns = [
        "analysis.json",
        "case_metadata.json",
        "geometry_metadata.json",
        "command*.txt",
        "log*.lammps",
        "stdout*.txt",
        "stderr*.txt",
        "data.*_final",
        "dump.*_final.lammpstrj",
        "restart.*",
    ]
    if include_in_progress:
        patterns.extend(["in.*chunk*.txt", "in.*chunk*", "dump.*chunk*.lammpstrj"])
    for pattern in patterns:
        files.extend(p for p in prod.glob(pattern) if p.is_file())
    return sorted(set(files), key=lambda p: p.as_posix())


def top_level_snapshot_files(run_root: Path) -> list[Path]:
    names = [
        "state.json",
        "production_summary.csv",
        "smoke_summary.csv",
        "effective_config.yaml",
        "run_plan.md",
        "preflight_report.md",
        "active_run_report.md",
        "final_report.md",
        "hang_recovery_report.md",
        "production_launched_after_smoke.txt",
        "queue_production_after_smoke.ps1",
        "queue_production_after_smoke_v2.ps1",
    ]
    return [run_root / name for name in names if (run_root / name).is_file()]


def git_snapshot_text() -> str:
    commands = [
        ["git", "rev-parse", "--show-toplevel"],
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--short"],
    ]
    blocks: list[str] = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
        blocks.append(f"$ {' '.join(cmd)}\n{proc.stdout}{proc.stderr}".rstrip())
    return "\n\n".join(blocks) + "\n"


def write_completed_cases_snapshot(
    run_root: str | Path,
    snapshot_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = normalize_repo_path(run_root)
    out = normalize_repo_path(snapshot_dir) if snapshot_dir else root / SNAPSHOT_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    state = read_json(root / "state.json", {}) or {}
    completed = completed_production_records(state)
    running = running_production_records(state)
    entries: list[dict[str, Any]] = []

    for path in top_level_snapshot_files(root):
        entries.append(file_manifest_entry(path, run_root=root, snapshot_dir=out, category="run_root"))

    for rec in completed:
        case_id = stageb_case_from_record(rec)
        for path in gather_case_files(root, case_id):
            entries.append(
                file_manifest_entry(
                    path,
                    run_root=root,
                    snapshot_dir=out,
                    category="completed_case",
                    case_id=case_id,
                )
            )

    for rec in running:
        case_id = stageb_case_from_record(rec)
        for path in gather_case_files(root, case_id, include_in_progress=True):
            entries.append(
                file_manifest_entry(
                    path,
                    run_root=root,
                    snapshot_dir=out,
                    category="in_progress_case",
                    case_id=case_id,
                )
            )

    git_path = out / "git_snapshot.txt"
    git_path.write_text(git_snapshot_text(), encoding="utf-8")
    entries.append(file_manifest_entry(git_path, run_root=out, snapshot_dir=None, category="git_snapshot"))

    manifest = {
        "generated_at": now_stamp(),
        "run_root": str(root),
        "snapshot_dir": str(out),
        "completed_cases": [stageb_case_from_record(r) for r in completed],
        "running_cases": [stageb_case_from_record(r) for r in running],
        "copy_policy": {
            "small_files_copied_under": "files/",
            "small_copy_threshold_bytes": COPY_SMALL_BYTES,
            "small_hash_threshold_bytes": SMALL_HASH_BYTES,
            "large_payload_policy": "path_size_mtime_only_for_dump_restart_data_files",
        },
        "files": entries,
    }
    write_json(out / "completed_cases_manifest.json", manifest)
    (out / "completed_cases_summary.md").write_text(snapshot_summary_markdown(manifest), encoding="utf-8")
    return manifest


def snapshot_summary_markdown(manifest: dict[str, Any]) -> str:
    copied = sum(1 for f in manifest["files"] if f.get("copy_policy") == "copied_small_file")
    referenced = len(manifest["files"]) - copied
    lines = [
        "# Completed Cases Snapshot",
        "",
        f"Generated: {manifest['generated_at']}",
        f"Run root: `{manifest['run_root']}`",
        f"Snapshot dir: `{manifest['snapshot_dir']}`",
        "",
        "## Completed Production Cases",
        "",
    ]
    lines += [f"- `{case}`" for case in manifest["completed_cases"]] or ["- none"]
    lines += ["", "## Running Production Cases", ""]
    lines += [f"- `{case}`" for case in manifest["running_cases"]] or ["- none"]
    lines += [
        "",
        "## File Policy",
        "",
        f"- copied small files: {copied}",
        f"- manifest references only: {referenced}",
        "- dump/restart/data payloads are referenced by path, size, and mtime to avoid unnecessary disk load.",
        "- small files include SHA-256 hashes where they are below the configured hash threshold.",
    ]
    return "\n".join(lines) + "\n"


def powershell_process_snapshot() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'lmp|python|ovito|ffmpeg' -or "
        "$_.CommandLine -match 'run_stage_sweep|lmp_kokkos|ovito|ffmpeg' } | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 4"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    return data if isinstance(data, list) else [data]


def active_lammps(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        p
        for p in processes
        if "lmp_kokkos_cuda" in str(p.get("Name", "")).lower()
        or "lmp_kokkos_cuda" in str(p.get("CommandLine", "")).lower()
    ]


def process_has_name_or_command(processes: list[dict[str, Any]], token: str) -> bool:
    token = token.lower()
    return any(token in str(p.get("Name", "")).lower() or token in str(p.get("CommandLine", "")).lower() for p in processes)


def process_name_contains(processes: list[dict[str, Any]], token: str) -> bool:
    token = token.lower()
    return any(token in str(p.get("Name", "")).lower() for p in processes)


def parse_chunk_tag(text: str) -> str:
    match = re.search(r"(chunk\d{7}_\d{7})", text)
    return match.group(1) if match else ""


def latest_restart(run_root: Path, case_id: str) -> dict[str, Any] | None:
    prod = case_production_dir(run_root, case_id)
    rows: list[dict[str, Any]] = []
    for path in prod.glob(f"restart.{case_id}_production.*"):
        step_match = re.search(r"\.(\d+)$", path.name)
        rows.append(
            {
                "path": str(path.resolve()),
                "step": int(step_match.group(1)) if step_match else None,
                "size_bytes": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
    rows = sorted(rows, key=lambda r: (r["step"] or -1, r["path"]))
    return rows[-1] if rows else None


def old_queue_case5_started(state: dict[str, Any]) -> bool:
    return any(stageb_case_from_record(rec) in FOCUS_CASE_IDS for rec in production_records(state))


def write_safe_stop_plan(
    run_root: str | Path,
    snapshot_dir: str | Path,
    *,
    process_checker: Callable[[], list[dict[str, Any]]] = powershell_process_snapshot,
) -> Path:
    root = normalize_repo_path(run_root)
    snapshot = normalize_repo_path(snapshot_dir)
    state = read_json(root / "state.json", {}) or {}
    processes = process_checker()
    lammps = active_lammps(processes)
    running = running_production_records(state)
    current_case = stageb_case_from_record(running[0]) if running else CURRENT_CASE4
    active_command = str(lammps[0].get("CommandLine", "")) if lammps else ""
    active_chunk = parse_chunk_tag(active_command)
    last_restart = latest_restart(root, current_case)
    runner_pids = [
        p.get("ProcessId")
        for p in processes
        if "run_stage_sweep.py" in str(p.get("CommandLine", ""))
        and (
            str(root) in str(p.get("CommandLine", ""))
            or "stageB_realism_100k_smoke_production.yaml" in str(p.get("CommandLine", ""))
            or "stageB_realism_100k" in str(p.get("CommandLine", ""))
        )
    ]
    case5_started = old_queue_case5_started(state)
    can_stop_now = not lammps and not case5_started and bool(runner_pids)
    stop_command = (
        f"Stop-Process -Id {','.join(str(x) for x in runner_pids)} -ErrorAction Stop"
        if can_stop_now
        else "blocked: active_lammps_detected or unsafe queue state"
    )
    lines = [
        "# Safe Stop Old Queue Plan",
        "",
        f"Generated: {now_stamp()}",
        f"Old run root: `{root}`",
        f"Snapshot dir: `{snapshot}`",
        "",
        "## Current Activity",
        "",
        f"- active_lammps: `{bool(lammps)}`",
        f"- active_lammps_pids: `{', '.join(str(p.get('ProcessId')) for p in lammps) if lammps else ''}`",
        f"- runner_pids: `{', '.join(str(x) for x in runner_pids)}`",
        f"- current_case: `{current_case}`",
        f"- active_chunk_from_process: `{active_chunk}`",
        f"- case5_started_in_state: `{case5_started}`",
        "",
        "## Last Restart",
        "",
        f"- restart: `{last_restart.get('path') if last_restart else ''}`",
        f"- restart_step: `{last_restart.get('step') if last_restart else ''}`",
        f"- restart_mtime: `{last_restart.get('mtime') if last_restart else ''}`",
        "",
        "## Stop Decision",
        "",
        f"- can_stop_now: `{can_stop_now}`",
        f"- safe_stop_command: `{stop_command}`",
        "",
        "Only run the stop command if `active_lammps` is false and case 5 has not started.",
        "With an active LAMMPS chunk, wait for the chunk/case to finish and re-run preflight.",
        "",
        "## Preserved Files",
        "",
        f"- completed manifest: `{snapshot / 'completed_cases_manifest.json'}`",
        f"- completed summary: `{snapshot / 'completed_cases_summary.md'}`",
        "",
        "## Forbidden Commands",
        "",
        "- `taskkill /F` against active LAMMPS",
        "- deleting the old run root",
        "- restarting over the old run root",
        "- launching a second MD run while old LAMMPS is active",
    ]
    path = root / "safe_stop_old_queue_plan.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def focus_case_ids(config: dict[str, Any]) -> list[str]:
    stage = (config.get("stages") or {}).get(FOCUS_STAGE) or {}
    return [str(x) for x in stage.get("production_case_ids") or []]


def validate_focus_config(config: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    stage = (config.get("stages") or {}).get(FOCUS_STAGE)
    if not isinstance(stage, dict):
        return [f"missing stage {FOCUS_STAGE}"]
    ids = focus_case_ids(config)
    if ids != FOCUS_CASE_IDS:
        reasons.append(f"production_case_ids must be exactly {FOCUS_CASE_IDS}, got {ids}")
    if int(stage.get("max_production_cases", 0)) != 2:
        reasons.append("max_production_cases must be 2")
    if len(stage.get("cases") or []) != 2:
        reasons.append("stage cases must contain exactly 2 cases")
    dump_every = int((config.get("io_policy") or {}).get("dump_every", {}).get("production", 0))
    if dump_every <= 0 or dump_every > 2000:
        reasons.append("io_policy.dump_every.production must be in 1..2000")
    if int((config.get("io_policy") or {}).get("restart_every", 0)) != 10000:
        reasons.append("io_policy.restart_every must be 10000")
    if int((config.get("io_policy") or {}).get("thermo_every", {}).get("production", 0)) != 1000:
        reasons.append("io_policy.thermo_every.production must be 1000")
    neighbor = ((config.get("gpu_profile") or {}).get("required_input_rewrites") or {}).get("neighbor_policy")
    if neighbor != NEIGHBOR_WORKAROUND:
        reasons.append("neighbor workaround is missing or changed")
    if "500k" in json.dumps(config).lower():
        reasons.append("focus config must not contain 500k scope")
    return reasons


def write_effective_focus_config(config_template: str | Path, focus_run_root: str | Path) -> Path:
    cfg_path = normalize_repo_path(config_template)
    root = normalize_repo_path(focus_run_root)
    root.mkdir(parents=True, exist_ok=True)
    cfg = read_yaml(cfg_path, {})
    reasons = validate_focus_config(cfg)
    if reasons:
        raise ValueError("; ".join(reasons))
    out = root / "effective_config.yaml"
    shutil.copy2(cfg_path, out)
    return out


def focus_run_command(config_path: str | Path, focus_run_root: str | Path) -> str:
    return (
        ".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py "
        f"--config {repo_relative(normalize_repo_path(config_path))} "
        f"--run-dir {repo_relative(normalize_repo_path(focus_run_root))} "
        f"--run-stage {FOCUS_STAGE} --gpu"
    )


def disk_free_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return round(usage.free / (1024**3), 3)


def default_disk_checker(root: str) -> float:
    path = Path(root)
    return disk_free_gb(path if path.exists() else path.anchor)


def default_gpu_checker() -> dict[str, Any]:
    proc = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"available": False, "free": False, "reason": "nvidia-smi unavailable"}
    row = [x.strip() for x in proc.stdout.splitlines()[0].split(",")]
    used = float(row[2])
    util = float(row[3])
    return {
        "available": True,
        "name": row[0],
        "memory_total_mib": float(row[1]),
        "memory_used_mib": used,
        "utilization_gpu_percent": util,
        "temperature_c": float(row[4]),
        "free": used <= 2048 and util <= 20,
    }


@dataclass
class PreflightInputs:
    old_run_root: Path
    focus_run_root: Path
    focus_config_path: Path
    snapshot_dir: Path
    command: str


def validate_focus_preflight(
    inputs: PreflightInputs,
    *,
    process_checker: Callable[[], list[dict[str, Any]]] = powershell_process_snapshot,
    disk_checker: Callable[[str], float] = default_disk_checker,
    gpu_checker: Callable[[], dict[str, Any]] = default_gpu_checker,
) -> dict[str, Any]:
    processes = process_checker()
    cfg = read_yaml(inputs.focus_config_path, {}) or {}
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    checks["active_lammps"] = active_lammps(processes)
    if checks["active_lammps"]:
        blockers.append("active_lammps_detected")

    manifest = inputs.snapshot_dir / "completed_cases_manifest.json"
    checks["completed_cases_manifest_exists"] = manifest.is_file()
    if not manifest.is_file():
        blockers.append("completed_cases_snapshot_missing")

    checks["run_roots_differ"] = inputs.old_run_root.resolve() != inputs.focus_run_root.resolve()
    if not checks["run_roots_differ"]:
        blockers.append("focus_run_root_matches_old_run_root")

    config_reasons = validate_focus_config(cfg)
    checks["focus_config_reasons"] = config_reasons
    if config_reasons:
        blockers.append("focus_config_invalid")

    c_free = disk_checker("C:/")
    b_free = disk_checker("B:/")
    checks["disk_free_gb"] = {"C": c_free, "B": b_free}
    if c_free <= 20:
        blockers.append("c_disk_below_20gb")
    if b_free <= 100:
        blockers.append("b_disk_below_100gb")

    gpu = gpu_checker()
    checks["gpu"] = gpu
    if not gpu.get("free", False):
        blockers.append("gpu_not_free")

    checks["external_render_processes"] = {
        "ovito": process_name_contains(processes, "ovito"),
        "ffmpeg": process_name_contains(processes, "ffmpeg"),
    }
    if checks["external_render_processes"]["ovito"]:
        blockers.append("ovito_process_active")
    if checks["external_render_processes"]["ffmpeg"]:
        blockers.append("ffmpeg_process_active")

    lowered_command = inputs.command.lower()
    forbidden_command_tokens = [
        token
        for token in ("ovito", "ffmpeg", "compute-sanitizer", "cuda_launch_blocking")
        if token in lowered_command
    ]
    if re.search(r"(?mi)^\s*(minimize|min_style)\b", inputs.command) or re.search(
        r"(?mi)^\s*thermo\s+1\s*$", inputs.command
    ):
        forbidden_command_tokens.append("forbidden_lammps_input")
    checks["focus_launcher_forbidden_tokens"] = forbidden_command_tokens
    if forbidden_command_tokens:
        blockers.append("focus_launcher_contains_forbidden_external_or_debug_token")

    return {
        "generated_at": now_stamp(),
        "old_run_root": str(inputs.old_run_root),
        "focus_run_root": str(inputs.focus_run_root),
        "focus_config": str(inputs.focus_config_path),
        "snapshot_dir": str(inputs.snapshot_dir),
        "allowed_to_launch": not blockers,
        "blocked": bool(blockers),
        "blockers": blockers,
        "checks": checks,
        "command": inputs.command,
    }


def preflight_markdown(preflight: dict[str, Any]) -> str:
    lines = [
        "# Focus Run Preflight",
        "",
        f"Generated: {preflight['generated_at']}",
        f"Old run root: `{preflight['old_run_root']}`",
        f"Focus run root: `{preflight['focus_run_root']}`",
        f"Focus config: `{preflight['focus_config']}`",
        "",
        f"- allowed_to_launch: `{preflight['allowed_to_launch']}`",
        f"- blocked: `{preflight['blocked']}`",
        "",
        "## Blockers",
        "",
    ]
    lines += [f"- `{b}`" for b in preflight["blockers"]] or ["- none"]
    lines += [
        "",
        "## Command",
        "",
        "```powershell",
        preflight["command"],
        "```",
        "",
        "Do not run this command while any blocker is present.",
        "",
        "## Checks",
        "",
        f"- completed manifest exists: `{preflight['checks'].get('completed_cases_manifest_exists')}`",
        f"- run roots differ: `{preflight['checks'].get('run_roots_differ')}`",
        f"- disk free GB: `{preflight['checks'].get('disk_free_gb')}`",
        f"- gpu: `{preflight['checks'].get('gpu')}`",
        f"- external render processes: `{preflight['checks'].get('external_render_processes')}`",
        f"- focus config reasons: `{preflight['checks'].get('focus_config_reasons')}`",
    ]
    return "\n".join(lines) + "\n"


def write_focus_preflight_artifacts(preflight: dict[str, Any], focus_run_root: str | Path) -> list[Path]:
    root = normalize_repo_path(focus_run_root)
    json_path = root / "focus_run_preflight.json"
    md_path = root / "focus_run_preflight.md"
    write_json(json_path, preflight)
    md_path.write_text(preflight_markdown(preflight), encoding="utf-8")
    return [json_path, md_path]


def estimate_focus_dump_volume_gb(config: dict[str, Any]) -> dict[str, Any]:
    dump_every = int((config.get("io_policy") or {}).get("dump_every", {}).get("production", 1000))
    cases = len(focus_case_ids(config))
    steps = int(((config.get("stages") or {}).get(FOCUS_STAGE) or {}).get("production_steps", 100000))
    chunks_per_case = max(1, steps // 10000)
    current_dump_per_chunk_mb = 13.6
    scale = 10000 / dump_every
    total_gb = cases * chunks_per_case * current_dump_per_chunk_mb * scale / 1024
    return {
        "dump_every": dump_every,
        "cases": cases,
        "steps_per_case": steps,
        "estimated_dump_gb": round(total_gb, 3),
        "basis": "observed Stage B chunk dump about 13.6 MB at dump_every=10000",
    }


def write_focus_run_setup(
    config_template: str | Path,
    focus_run_root: str | Path,
    *,
    old_run_root: str | Path,
    snapshot_dir: str | Path,
    process_checker: Callable[[], list[dict[str, Any]]] = powershell_process_snapshot,
    disk_checker: Callable[[str], float] = default_disk_checker,
    gpu_checker: Callable[[], dict[str, Any]] = default_gpu_checker,
) -> dict[str, Any]:
    focus_root = normalize_repo_path(focus_run_root)
    effective = write_effective_focus_config(config_template, focus_root)
    command = focus_run_command(effective, focus_root)
    (focus_root / "focus_run_command.txt").write_text(command + "\n", encoding="utf-8")
    cfg = read_yaml(effective, {}) or {}
    write_json(focus_root / "focus_run_volume_estimate.json", estimate_focus_dump_volume_gb(cfg))
    preflight = validate_focus_preflight(
        PreflightInputs(
            old_run_root=normalize_repo_path(old_run_root),
            focus_run_root=focus_root,
            focus_config_path=effective,
            snapshot_dir=normalize_repo_path(snapshot_dir),
            command=command,
        ),
        process_checker=process_checker,
        disk_checker=disk_checker,
        gpu_checker=gpu_checker,
    )
    write_focus_preflight_artifacts(preflight, focus_root)
    return {
        "focus_run_root": str(focus_root),
        "effective_config": str(effective),
        "command": command,
        "preflight": preflight,
    }


def copy_partial_event_outputs_to_completed_aliases(output_dir: str | Path) -> list[Path]:
    out = normalize_repo_path(output_dir)
    mapping = {
        "event_timeline.csv": "event_timeline_completed_cases.csv",
        "event_timeline.json": "event_timeline_completed_cases.json",
        "event_detection_report.md": "completed_cases_detection_report.md",
    }
    written: list[Path] = []
    for src_name, dst_name in mapping.items():
        src = out / src_name
        if src.is_file():
            dst = out / dst_name
            shutil.copy2(src, dst)
            written.append(dst)
    return written
