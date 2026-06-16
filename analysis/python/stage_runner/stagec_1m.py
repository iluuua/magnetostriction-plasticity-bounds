"""Stage C 1M-class queue/preflight helpers.

The helpers in this module prepare launch artifacts only. They do not start MD.
Actual launch is handled by scripts/launch_stageC_1M_after_focus.py after a
fresh no-active-LAMMPS preflight.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from . import builder, paths
from .gpu_grid import GridConfigError, load_grid_config, validation_plan_lines


REPO_ROOT = paths.REPO_ROOT
STAGEC_STAGE = "C1_1M_scaleup_100k"
STAGEC_CASE = "C1_1M_nearGB_vacancies_medium_eps0100"
STAGEC_CONFIG_TEMPLATE = REPO_ROOT / "configs" / "stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml"
STAGEC_OUTPUT_ROOT = REPO_ROOT / "runs" / "stageC_1M_nearGB_vacancies_eps0100_100k"
FOCUS_RUN_ROOT_DEFAULT = REPO_ROOT / "runs" / "stageB_nearGB_vacancies_focus_100k" / "20260615-215533"

BLOCKER_ACTIVE_FOCUS = "active_focused_100k_lammps"
FORBIDDEN_LAUNCH_TOKENS = ("ovito", "ffmpeg", "compute-sanitizer", "cuda_launch_blocking")
REQUIRED_DUMP_FIELDS = ("id", "type", "x", "y", "z", "c_pe_atom", "c_st[1]", "c_st[2]", "c_st[3]")
EXPECTED_LAMMPS_ARGS = (
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
)


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp_dir() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def normalize_repo_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.resolve()


def repo_relative(path: str | Path) -> str:
    p = normalize_repo_path(path)
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def read_yaml(path: str | Path) -> dict[str, Any]:
    with normalize_repo_path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_json(path: str | Path, data: dict[str, Any] | list[Any]) -> Path:
    p = normalize_repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def write_text(path: str | Path, text: str) -> Path:
    p = normalize_repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    return p


def stagec_run_root(path: str | Path | None = None) -> Path:
    if path:
        return normalize_repo_path(path)
    return (STAGEC_OUTPUT_ROOT / timestamp_dir()).resolve()


def stagec_launch_args(config_path: str | Path, run_root: str | Path) -> list[str]:
    return [
        ".venv\\Scripts\\python.exe",
        "scripts\\run_stage_sweep.py",
        "--config",
        repo_relative(config_path),
        "--run-dir",
        repo_relative(run_root),
        "--run-stage",
        STAGEC_STAGE,
        "--gpu",
    ]


def command_text(args: list[str]) -> str:
    return " ".join(args)


def stagec_launch_command(config_path: str | Path, run_root: str | Path) -> str:
    return command_text(stagec_launch_args(config_path, run_root))


def launch_after_focus_command(focus_root: str | Path, run_root: str | Path) -> str:
    return (
        ".venv\\Scripts\\python.exe scripts\\launch_stageC_1M_after_focus.py "
        f"--focus-run-root {repo_relative(focus_root)} "
        f"--stageC-run-root {repo_relative(run_root)}"
    )


def continuation_command(run_root: str | Path, target_step: int) -> str:
    suffix = f"continue_to_{target_step // 1000}k"
    case_id = f"{STAGEC_CASE}_production"
    return (
        "# TEMPLATE ONLY - do not run until the 100k decision report approves continuation.\n"
        "# Create/review the referenced continuation config first; it must preserve the same one case.\n"
        ".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py "
        f"--config {repo_relative(run_root)}\\effective_config.{suffix}.yaml "
        f"--run-dir {repo_relative(run_root)} "
        f"--run-stage {STAGEC_STAGE} --gpu --force-rerun {case_id}"
    )


def powershell_process_snapshot() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and "
        "($_.CommandLine -match 'run_stage_sweep|stageB_nearGB_vacancies_focus_100k|lmp_kokkos_cuda|ovito|ffmpeg') } | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 4"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    return data if isinstance(data, list) else [data]


def _is_self_scan_process(process: dict[str, Any]) -> bool:
    cmd = str(process.get("CommandLine", ""))
    name = str(process.get("Name", "")).lower()
    if name in {"powershell.exe", "pwsh.exe"} and "Get-CimInstance Win32_Process" in cmd:
        return True
    return any(
        token in cmd
        for token in ("prepare_stageC_1M_queue_plan.py", "launch_stageC_1M_after_focus.py")
    )


def active_lammps_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        p
        for p in processes
        if not _is_self_scan_process(p)
        and "lmp_kokkos_cuda" in str(p.get("Name", "")).lower()
    ]


def active_focus_processes(processes: list[dict[str, Any]], focus_root: str | Path) -> list[dict[str, Any]]:
    root = normalize_repo_path(focus_root)
    rel = repo_relative(root)
    tokens = {
        str(root),
        str(root).replace("/", "\\"),
        str(root).replace("\\", "/"),
        rel,
        rel.replace("/", "\\"),
        rel.replace("\\", "/"),
    }
    rows: list[dict[str, Any]] = []
    for process in processes:
        if _is_self_scan_process(process):
            continue
        cmd = str(process.get("CommandLine", ""))
        if any(token and token in cmd for token in tokens):
            rows.append(process)
    return rows


def external_render_processes(processes: list[dict[str, Any]]) -> dict[str, bool]:
    rows = [p for p in processes if not _is_self_scan_process(p)]
    return {
        "ovito": any("ovito" in str(p.get("Name", "")).lower() for p in rows),
        "ffmpeg": any("ffmpeg" in str(p.get("Name", "")).lower() for p in rows),
    }


def disk_free_gb(path: str | Path) -> float:
    p = Path(path)
    usage = shutil.disk_usage(p if p.exists() else Path(p.anchor or "."))
    return round(usage.free / (1024**3), 3)


def default_disk_checker(root: str) -> float:
    return disk_free_gb(root)


def _first_dump_atom_count(path: Path) -> int | None:
    want_next = False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if want_next:
                    try:
                        return int(line.strip())
                    except ValueError:
                        return None
                if line.startswith("ITEM: NUMBER OF ATOMS"):
                    want_next = True
    except OSError:
        return None
    return None


def _dump_frame_count(path: Path) -> int:
    frames = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("ITEM: TIMESTEP"):
                    frames += 1
    except OSError:
        return 0
    return frames


def inspect_dump_sample(path: Path) -> dict[str, Any] | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None
    atoms = _first_dump_atom_count(path)
    frames = _dump_frame_count(path)
    if not atoms or not frames:
        return {
            "path": str(path),
            "size_bytes": size,
            "atoms": atoms,
            "frames": frames,
            "bytes_per_atom_frame": None,
        }
    return {
        "path": str(path),
        "size_bytes": size,
        "atoms": atoms,
        "frames": frames,
        "bytes_per_atom_frame": round(size / (atoms * frames), 3),
    }


def dump_samples(focus_root: str | Path, limit: int = 5) -> list[dict[str, Any]]:
    root = normalize_repo_path(focus_root)
    if not root.exists():
        return []
    candidates = sorted(
        (p for p in root.rglob("dump*.lammpstrj") if p.is_file()),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    rows: list[dict[str, Any]] = []
    for path in candidates[:limit]:
        sample = inspect_dump_sample(path)
        if sample:
            rows.append(sample)
    return rows


def restart_samples(focus_root: str | Path, atom_count_hint: int | None) -> list[dict[str, Any]]:
    root = normalize_repo_path(focus_root)
    if not root.exists() or not atom_count_hint:
        return []
    rows = []
    for path in sorted(root.rglob("restart.*"), key=lambda p: p.stat().st_size, reverse=True)[:5]:
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size <= 0:
            continue
        rows.append(
            {
                "path": str(path),
                "size_bytes": size,
                "bytes_per_atom": round(size / atom_count_hint, 3),
            }
        )
    return rows


def stagec_plan(config: dict[str, Any]) -> dict[str, Any]:
    case = ((config.get("stages") or {}).get(STAGEC_STAGE) or {}).get("cases", [{}])[0]
    resources = config.get("resources") or {}
    return builder.plan_for_target(
        int(case.get("atom_target", config.get("target_atoms", 1000000))),
        ranks=1,
        max_memory_gb=float(resources.get("gpu_memory_gb", 12)),
    )


def build_volume_estimate(config: dict[str, Any], focus_root: str | Path) -> dict[str, Any]:
    plan = stagec_plan(config)
    stage = (config.get("stages") or {}).get(STAGEC_STAGE) or {}
    io = config.get("io_policy") or {}
    production_steps = int(stage.get("production_steps", config.get("production_steps", 100000)))
    dump_every = int((io.get("dump_every") or {}).get("production", config.get("dump_every", {}).get("production", 5000)))
    restart_every = int(io.get("restart_every", config.get("restart_every", 10000)))
    planned_dump_frames = production_steps // dump_every
    planned_final_dump_frames = 1 if io.get("write_final_dump", True) else 0
    samples = dump_samples(focus_root)
    usable = [s for s in samples if s.get("bytes_per_atom_frame")]
    if usable:
        bytes_per_atom_frame = sum(float(s["bytes_per_atom_frame"]) for s in usable) / len(usable)
        dump_basis = "observed focused Stage B dump byte density"
        atom_hint = int(usable[0].get("atoms") or 0) or None
    else:
        bytes_per_atom_frame = 130.0
        dump_basis = "fallback text dump estimate: 130 bytes/atom/frame"
        atom_hint = None
    restarts = restart_samples(focus_root, atom_hint)
    if restarts:
        bytes_per_atom_restart = sum(float(r["bytes_per_atom"]) for r in restarts) / len(restarts)
        restart_basis = "observed focused Stage B restart byte density"
    else:
        bytes_per_atom_restart = 120.0
        restart_basis = "fallback restart estimate: 120 bytes/atom/restart"
    restart_files = production_steps // restart_every
    atoms = int(plan["estimated_atoms"])
    dump_gb = bytes_per_atom_frame * atoms * (planned_dump_frames + planned_final_dump_frames) / (1024**3)
    restart_gb = bytes_per_atom_restart * atoms * restart_files / (1024**3)
    overhead_gb = 2.0
    total_gb = dump_gb + restart_gb + overhead_gb
    return {
        "generated_at": now_stamp(),
        "target_atoms_requested": int(config.get("target_atoms", 1000000)),
        "case_atom_target": int(((config.get("stages") or {}).get(STAGEC_STAGE) or {}).get("atom_targets", [0])[0]),
        "estimated_atoms": atoms,
        "estimated_memory_gb": plan["estimated_memory_gb"],
        "feasible_under_configured_memory_limit": plan["feasible_under_memory_limit"],
        "production_steps": production_steps,
        "dump_every": dump_every,
        "planned_dump_frames": planned_dump_frames,
        "planned_final_dump_frames": planned_final_dump_frames,
        "restart_every": restart_every,
        "planned_restart_files": restart_files,
        "estimated_dump_gb": round(dump_gb, 2),
        "estimated_restart_gb": round(restart_gb, 2),
        "estimated_overhead_gb": overhead_gb,
        "estimated_total_storage_gb": round(total_gb, 2),
        "dump_basis": dump_basis,
        "restart_basis": restart_basis,
        "dump_samples": samples,
        "restart_samples": restarts,
    }


def stagec_case_ids(config: dict[str, Any]) -> list[str]:
    stage = (config.get("stages") or {}).get(STAGEC_STAGE) or {}
    return [str(x) for x in stage.get("production_case_ids") or []]


def validate_stagec_config(config: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if config.get("run_stage") != STAGEC_STAGE:
        reasons.append(f"run_stage must be {STAGEC_STAGE}")
    if [str(x) for x in config.get("case_ids", [])] != [STAGEC_CASE]:
        reasons.append(f"top-level case_ids must be exactly [{STAGEC_CASE}]")
    if int(config.get("target_atoms", 0) or 0) != 1000000:
        reasons.append("top-level target_atoms must be 1000000")
    stage = (config.get("stages") or {}).get(STAGEC_STAGE)
    if not isinstance(stage, dict):
        return reasons + [f"missing stage {STAGEC_STAGE}"]
    cases = stage.get("cases") or []
    if len(cases) != 1:
        reasons.append("stage must contain exactly one case")
    if stagec_case_ids(config) != [STAGEC_CASE]:
        reasons.append(f"production_case_ids must be exactly [{STAGEC_CASE}]")
    if cases and str(cases[0].get("case_id")) != STAGEC_CASE:
        reasons.append(f"case_id must be {STAGEC_CASE}")
    if int(stage.get("production_steps", 0) or 0) != 100000:
        reasons.append("production_steps must be 100000")
    rel = config.get("production_reliability") or {}
    if int(rel.get("production_chunk_steps", 0) or 0) != 10000:
        reasons.append("production_reliability.production_chunk_steps must be 10000")
    io = config.get("io_policy") or {}
    if int((io.get("dump_every") or {}).get("production", 0) or 0) < 5000:
        reasons.append("io_policy.dump_every.production must be >= 5000")
    if int(io.get("restart_every", 0) or 0) != 10000:
        reasons.append("io_policy.restart_every must be 10000")
    if int((io.get("thermo_every") or {}).get("production", 0) or 0) != 1000:
        reasons.append("io_policy.thermo_every.production must be 1000")
    fields = tuple(str(x) for x in io.get("dump_fields", ()))
    missing_fields = [f for f in REQUIRED_DUMP_FIELDS if f not in fields]
    if missing_fields:
        reasons.append(f"io_policy.dump_fields missing {missing_fields}")
    gp = config.get("gpu_profile") or {}
    if tuple(str(x) for x in gp.get("command_args", ())) != EXPECTED_LAMMPS_ARGS:
        reasons.append("gpu_profile.command_args must preserve the KOKKOS CUDA args")
    if not ((config.get("event_pipeline") or {}).get("enabled")):
        reasons.append("event_pipeline.enabled must be true")
    plan = stagec_plan(config)
    if not (900000 <= int(plan["estimated_atoms"]) <= 1100000):
        reasons.append(f"estimated atom count outside 900k..1.1M: {plan['estimated_atoms']}")
    if not plan["feasible_under_memory_limit"]:
        reasons.append(f"estimated GPU memory exceeds configured limit: {plan['estimated_memory_gb']} GB")
    return reasons


def forbidden_tokens_in_command(command: str) -> list[str]:
    low = command.lower()
    tokens = [token for token in FORBIDDEN_LAUNCH_TOKENS if token in low]
    if re.search(r"(?mi)^\s*(minimize|min_style)\b", command):
        tokens.append("minimize")
    if re.search(r"(?mi)^\s*thermo\s+1\s*$", command):
        tokens.append("thermo 1")
    return sorted(set(tokens))


def build_preflight(
    config_path: str | Path,
    run_root: str | Path,
    focus_root: str | Path = FOCUS_RUN_ROOT_DEFAULT,
    *,
    process_checker: Callable[[], list[dict[str, Any]]] = powershell_process_snapshot,
    disk_checker: Callable[[str], float] = default_disk_checker,
) -> dict[str, Any]:
    config_path = normalize_repo_path(config_path)
    run_root = normalize_repo_path(run_root)
    focus_root = normalize_repo_path(focus_root)
    config = read_yaml(config_path)
    volume = build_volume_estimate(config, focus_root)
    command = stagec_launch_command(config_path, run_root)
    processes = process_checker()
    lammps = active_lammps_processes(processes)
    focus = active_focus_processes(processes, focus_root)
    render = external_render_processes(processes)
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    if focus or lammps:
        if focus or any(str(focus_root) in str(p.get("CommandLine", "")) for p in lammps):
            blockers.append(BLOCKER_ACTIVE_FOCUS)
        else:
            blockers.append("active_lammps_detected")
    checks["active_lammps_processes"] = lammps
    checks["active_focus_processes"] = focus

    output_root = STAGEC_OUTPUT_ROOT.resolve()
    checks["stagec_run_root_under_output_root"] = run_root == output_root or run_root.is_relative_to(output_root)
    if not checks["stagec_run_root_under_output_root"]:
        blockers.append("stagec_run_root_outside_stagec_output_root")
    checks["stagec_run_root_differs_from_focus_root"] = run_root != focus_root
    if not checks["stagec_run_root_differs_from_focus_root"]:
        blockers.append("stagec_run_root_matches_focus_run_root")

    config_reasons = validate_stagec_config(config)
    checks["stagec_config_reasons"] = config_reasons
    if config_reasons:
        blockers.append("stagec_config_invalid")

    try:
        grid_cfg = load_grid_config(config_path)
        plan_ok, plan_lines = validation_plan_lines(grid_cfg)
        checks["plan_only_validates"] = plan_ok
        checks["plan_only_lines"] = plan_lines
        if not plan_ok:
            blockers.append("grid_plan_only_failed")
    except (GridConfigError, Exception) as exc:
        checks["plan_only_validates"] = False
        checks["plan_only_error"] = str(exc)
        blockers.append("grid_plan_only_failed")

    forbidden = forbidden_tokens_in_command(command)
    checks["forbidden_tokens_in_launch_command"] = forbidden
    if forbidden:
        blockers.append("launch_command_contains_forbidden_token")

    c_free = disk_checker("C:/")
    b_free = disk_checker("B:/")
    checks["disk_free_gb"] = {"C": c_free, "B": b_free}
    if c_free <= 20:
        blockers.append("c_disk_below_20gb")
    if b_free <= 100:
        blockers.append("b_disk_below_100gb")
    checks["estimated_total_storage_gb"] = volume["estimated_total_storage_gb"]
    checks["b_disk_post_estimate_free_gb"] = round(b_free - float(volume["estimated_total_storage_gb"]), 2)
    if checks["b_disk_post_estimate_free_gb"] <= 100:
        blockers.append("b_disk_below_safe_threshold_after_estimate")

    checks["external_render_processes"] = render
    if render["ovito"]:
        blockers.append("ovito_process_active")
    if render["ffmpeg"]:
        blockers.append("ffmpeg_process_active")

    queue_blockers = [b for b in blockers if b != BLOCKER_ACTIVE_FOCUS]
    allowed = not blockers
    queue_ready = not queue_blockers
    return {
        "generated_at": now_stamp(),
        "run_stage": STAGEC_STAGE,
        "selected_case": STAGEC_CASE,
        "focus_run_root": str(focus_root),
        "stageC_run_root": str(run_root),
        "config": str(config_path),
        "allowed_to_launch_now": allowed,
        "queue_ready": queue_ready,
        "blocked_by": blockers,
        "can_launch_after_current_focus_finishes": queue_ready and blockers == [BLOCKER_ACTIVE_FOCUS],
        "launch_policy": "manual_after_focused_run_only",
        "launch_command": command,
        "launch_after_focus_command": launch_after_focus_command(focus_root, run_root),
        "checks": checks,
        "volume_estimate": volume,
    }


def preflight_markdown(preflight: dict[str, Any]) -> str:
    volume = preflight["volume_estimate"]
    lines = [
        "# Stage C 1M Preflight",
        "",
        f"Generated: {preflight['generated_at']}",
        f"Stage C root: `{preflight['stageC_run_root']}`",
        f"Selected case: `{preflight['selected_case']}`",
        "",
        f"- allowed_to_launch_now: `{preflight['allowed_to_launch_now']}`",
        f"- queue_ready: `{preflight['queue_ready']}`",
        f"- blocked_by: `{preflight['blocked_by']}`",
        f"- can_launch_after_current_focus_finishes: `{preflight['can_launch_after_current_focus_finishes']}`",
        "",
        "## Runtime And Storage",
        "",
        f"- estimated_atoms: `{volume['estimated_atoms']}`",
        f"- estimated_memory_gb: `{volume['estimated_memory_gb']}`",
        f"- expected_runtime: `optimistic ~4 days; expected ~5 days; pessimistic ~6.5 days`",
        f"- estimated_dump_gb: `{volume['estimated_dump_gb']}`",
        f"- estimated_restart_gb: `{volume['estimated_restart_gb']}`",
        f"- estimated_total_storage_gb: `{volume['estimated_total_storage_gb']}`",
        f"- disk_free_gb: `{preflight['checks']['disk_free_gb']}`",
        "",
        "## Launch Command",
        "",
        "```powershell",
        preflight["launch_command"],
        "```",
        "",
        "Do not run the launch command while `blocked_by` is non-empty.",
        "",
        "## Launch-After-Focus Command",
        "",
        "```powershell",
        preflight["launch_after_focus_command"],
        "```",
    ]
    return "\n".join(lines) + "\n"


def readme_text(preflight: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Stage C 1M Queue Root",
            "",
            f"Selected case: `{STAGEC_CASE}`.",
            "This root is prepared for a single 100k-step Stage C checkpoint.",
            "",
            "## Launch Policy",
            "",
            "- Do not launch while any LAMMPS process is active.",
            "- Do not launch while the focused Stage B run is active.",
            "- Use `launch_after_focus_command.txt` after the focused run completes or stops.",
            "- Continuation to 200k/250k is manual-only after the 100k decision report.",
            "",
            "## Expected Runtime",
            "",
            "- optimistic: about 4 days",
            "- expected: about 5 days",
            "- pessimistic: about 6.5 days",
            "",
            "## Event Pipeline",
            "",
            "After the 100k checkpoint completes, run:",
            "",
            "```powershell",
            f".venv\\Scripts\\python.exe scripts\\run_event_pipeline_dry_run.py --run-root {repo_relative(preflight['stageC_run_root'])} --allow-incomplete",
            "```",
        ]
    ) + "\n"


def report_text(preflight: dict[str, Any]) -> str:
    volume = preflight["volume_estimate"]
    monitor = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
        "(($_.Name -like 'lmp_kokkos_cuda*') -or ($_.Name -match 'python' -and "
        "$_.CommandLine -like '*run_stage_sweep.py*')) } | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine"
    )
    return "\n".join(
        [
            "# Stage C 1M Queue Plan",
            "",
            f"Generated: {preflight['generated_at']}",
            "",
            "## Selection",
            "",
            f"- case: `{STAGEC_CASE}`",
            "- reason: nearGB placement plus vacancies_medium and eps0100 overload is the strongest current DXA candidate.",
            f"- Stage C root: `{preflight['stageC_run_root']}`",
            f"- estimated atom count: `{volume['estimated_atoms']}`",
            "",
            "## Runtime And IO",
            "",
            "- expected runtime: optimistic ~4 days; expected ~5 days; pessimistic ~6.5 days",
            "- production checkpoint: `0 -> 100000 steps`",
            "- dump policy: production dump every `5000` steps, final dump at 100000",
            "- restart policy: restart every `10000` steps, final restart at 100000",
            f"- estimated dump GB: `{volume['estimated_dump_gb']}`",
            f"- estimated restart GB: `{volume['estimated_restart_gb']}`",
            f"- estimated total storage GB: `{volume['estimated_total_storage_gb']}`",
            f"- disk free GB: `{preflight['checks']['disk_free_gb']}`",
            "",
            "## Launch Status",
            "",
            f"- allowed_to_launch_now: `{preflight['allowed_to_launch_now']}`",
            f"- queue_ready: `{preflight['queue_ready']}`",
            f"- blockers: `{preflight['blocked_by']}`",
            "",
            "## Launch After Focus",
            "",
            "```powershell",
            preflight["launch_after_focus_command"],
            "```",
            "",
            "## Monitor Command",
            "",
            "```powershell",
            monitor,
            "```",
            "",
            "## Continuation Plan",
            "",
            "- if confirmed_DXA: event-window high-frequency rerun, not blind continuation",
            "- if no DXA but strong precursor: continue from restart.100000 to 200k or 250k after manual approval",
            "- if no DXA and no precursor: stop scaling and prepare positive-control/seeded/cyclic branch",
            "",
            "## Event Pipeline After Completion",
            "",
            "```powershell",
            f".venv\\Scripts\\python.exe scripts\\run_event_pipeline_dry_run.py --run-root {repo_relative(preflight['stageC_run_root'])} --allow-incomplete",
            "```",
        ]
    ) + "\n"


def prepare_stagec_queue(
    *,
    config_template: str | Path = STAGEC_CONFIG_TEMPLATE,
    run_root: str | Path | None = None,
    focus_root: str | Path = FOCUS_RUN_ROOT_DEFAULT,
    process_checker: Callable[[], list[dict[str, Any]]] = powershell_process_snapshot,
    disk_checker: Callable[[str], float] = default_disk_checker,
) -> dict[str, Any]:
    root = stagec_run_root(run_root)
    root.mkdir(parents=True, exist_ok=False)
    for subdir in ("cases", "logs", "summaries", "tables"):
        (root / subdir).mkdir(exist_ok=True)
    effective = root / "effective_config.yaml"
    shutil.copy2(normalize_repo_path(config_template), effective)
    preflight = build_preflight(
        effective,
        root,
        focus_root,
        process_checker=process_checker,
        disk_checker=disk_checker,
    )
    write_json(root / "stageC_1M_preflight.json", preflight)
    write_text(root / "stageC_1M_preflight.md", preflight_markdown(preflight))
    write_json(root / "stageC_1M_volume_estimate.json", preflight["volume_estimate"])
    write_text(root / "stageC_1M_launch_command.txt", preflight["launch_command"])
    write_text(root / "launch_after_focus_command.txt", preflight["launch_after_focus_command"])
    write_text(root / "continue_to_200k_command.txt", continuation_command(root, 200000))
    write_text(root / "continue_to_250k_command.txt", continuation_command(root, 250000))
    write_text(root / "README_STAGEC_1M.md", readme_text(preflight))
    report = report_text(preflight)
    write_text(REPO_ROOT / "agent_report_stageC_1M_queue_plan.md", report)
    return {
        "stageC_run_root": str(root),
        "effective_config": str(effective),
        "preflight_json": str(root / "stageC_1M_preflight.json"),
        "preflight_md": str(root / "stageC_1M_preflight.md"),
        "volume_estimate": str(root / "stageC_1M_volume_estimate.json"),
        "launch_command": str(root / "stageC_1M_launch_command.txt"),
        "launch_after_focus_command": str(root / "launch_after_focus_command.txt"),
        "report": str(REPO_ROOT / "agent_report_stageC_1M_queue_plan.md"),
        "preflight": preflight,
    }
