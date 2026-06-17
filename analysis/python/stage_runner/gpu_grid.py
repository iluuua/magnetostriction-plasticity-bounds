"""Config-driven GPU grid runner for the Al/Fe4Al13 staged sweep.

This module is intentionally separate from the older A0/A1-small autopilot so
the production GPU path can be hardened without rewriting the existing runner in
place. All generated inputs and outputs are kept under the configured run root.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from . import builder, eigenstrain, paths
from .analysis_runner import analyze_dump
from .lammps_detect import get_help_text, parse_capabilities
from .log_parser import parse_log


REPO_ROOT = paths.REPO_ROOT
GRID_EXPERIMENT_NAME = "al_fe4al13_gpu_grid_sweep"
# Trimmed A1_custom_100k experiment shares the same runner/config shape.
STAGEB_REALISM_EXPERIMENT_NAME = "stageB_realism_100k_smoke_production"
STAGEB_REALISM_MODE = "build_stageB_realism_100k"
GRID_EXPERIMENT_NAMES = (
    GRID_EXPERIMENT_NAME,
    "stage_sweep_gpu_A1_100k_smoke_production",
    STAGEB_REALISM_EXPERIMENT_NAME,
    "stageB_nearGB_vacancies_focus_100k",
    "stageC_1M_nearGB_vacancies_eps0100_100k",
)
PRODUCTION_NEIGHBOR_POLICY = "neigh_modify    delay 0 every 10 check no"
LARGE_STAGE_PREFIXES = ("A2",)
STAGEB_ALLOWED_POSITIONS = ("grain_interior", "near_grain_boundary")
STAGEB_ALLOWED_PREDEFECTS = ("perfect", "vacancies_medium", "seed_dislocation_if_available")
DEFECT_ATOMS_BOUNDARY_NOISE_MAX = 3
HCP_ATOMS_BEYOND_SHELL_SIGNAL_MIN = 1
PLASTIC_ZONE_DISTANCE_SIGNAL_MIN = 1.35
HCP_PCT_SIGNAL_DELTA = 0.05
OTHER_PCT_SIGNAL_DELTA = 0.5


class GridConfigError(RuntimeError):
    pass


class GridStop(RuntimeError):
    pass


def load_grid_config(config_path: Path | str) -> dict[str, Any]:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise GridConfigError("config root must be a mapping")
    if cfg.get("experiment", {}).get("name") not in GRID_EXPERIMENT_NAMES:
        raise GridConfigError(
            f"not a GPU grid config: experiment.name={cfg.get('experiment', {}).get('name')!r}"
        )
    validate_config_shape(cfg)
    return cfg


def is_grid_config_file(config_path: Path | str) -> bool:
    try:
        with Path(config_path).open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return False
    return isinstance(cfg, dict) and cfg.get("experiment", {}).get("name") in GRID_EXPERIMENT_NAMES


def validate_config_shape(cfg: dict[str, Any]) -> None:
    required_top = ["experiment", "gpu_profile", "io_policy", "resources", "stages", "analysis", "science_gates"]
    missing = [k for k in required_top if k not in cfg]
    if missing:
        raise GridConfigError(f"missing top-level sections: {missing}")
    gp = cfg["gpu_profile"]
    if not gp.get("enabled"):
        raise GridConfigError("gpu_profile.enabled must be true")
    if not gp.get("lammps_executable"):
        raise GridConfigError("gpu_profile.lammps_executable is required")
    if not isinstance(gp.get("command_args"), list) or not gp["command_args"]:
        raise GridConfigError("gpu_profile.command_args must be a non-empty list")
    rewrites = gp.get("required_input_rewrites") or {}
    if rewrites.get("neighbor_policy") != PRODUCTION_NEIGHBOR_POLICY:
        raise GridConfigError(
            "gpu_profile.required_input_rewrites.neighbor_policy must be "
            f"{PRODUCTION_NEIGHBOR_POLICY!r}"
        )
    if "CUDA_LAUNCH_BLOCKING" not in (gp.get("forbidden_environment") or []):
        raise GridConfigError("gpu_profile.forbidden_environment must include CUDA_LAUNCH_BLOCKING")

    io = cfg["io_policy"]
    for phase in ("smoke", "short", "production"):
        if int(io.get("thermo_every", {}).get(phase, 0)) <= 1:
            raise GridConfigError(f"io_policy.thermo_every.{phase} must be > 1")
        if int(io.get("dump_every", {}).get(phase, 0)) <= 1:
            raise GridConfigError(f"io_policy.dump_every.{phase} must be > 1")

    rel = cfg.get("production_reliability")
    if not isinstance(rel, dict):
        raise GridConfigError("production_reliability section is required")
    if int(rel.get("production_chunk_steps", 0)) <= 0:
        raise GridConfigError("production_reliability.production_chunk_steps must be positive")
    if float(rel.get("max_no_progress_minutes", 0)) <= 0:
        raise GridConfigError("production_reliability.max_no_progress_minutes must be positive")
    for key in ("resume_from_latest_restart", "retry_hung_chunk_once"):
        if key not in rel:
            raise GridConfigError(f"production_reliability.{key} is required")

    stages = cfg["stages"]
    if not isinstance(stages, dict) or not stages:
        raise GridConfigError("stages must be a non-empty mapping")
    for name, stage in stages.items():
        if not stage.get("enabled", False):
            continue
        mode = stage.get("structure_mode")
        if not stage.get("atom_targets"):
            raise GridConfigError(f"{name}.atom_targets must be non-empty")
        if not stage.get("eps_z"):
            raise GridConfigError(f"{name}.eps_z must be non-empty")
        for key in ("smoke_steps", "production_steps"):
            if int(stage.get(key, 0)) <= 0:
                raise GridConfigError(f"{name}.{key} must be positive")
        uses_short = bool(stage.get("run_short") or stage.get("run_short_after_smoke_pass"))
        if uses_short and int(stage.get("short_steps", 0)) <= 0:
            raise GridConfigError(
                f"{name}.short_steps must be positive when a short phase is enabled"
            )
        if mode == STAGEB_REALISM_MODE:
            validate_stageb_realism_stage(name, stage)


def validate_stageb_realism_stage(name: str, stage: dict[str, Any]) -> None:
    cases = stage.get("cases")
    if not isinstance(cases, list) or not cases:
        raise GridConfigError(f"{name}.cases must be a non-empty list for {STAGEB_REALISM_MODE}")
    max_prod = int(stage.get("max_production_cases", 0))
    if max_prod <= 0 or max_prod > 6:
        raise GridConfigError(f"{name}.max_production_cases must be in 1..6")
    if len(cases) > int(stage.get("max_smoke_cases", 6)):
        raise GridConfigError(f"{name}.cases exceeds max_smoke_cases")
    seen: set[str] = set()
    for idx, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise GridConfigError(f"{name}.cases[{idx}] must be a mapping")
        cid = str(case.get("case_id", "")).strip()
        if not cid:
            raise GridConfigError(f"{name}.cases[{idx}].case_id is required")
        if cid in seen:
            raise GridConfigError(f"{name}.cases duplicate case_id: {cid}")
        seen.add(cid)
        if int(case.get("atom_target", 0)) <= 0:
            raise GridConfigError(f"{cid}.atom_target must be positive")
        if float(case.get("eps_z", -999.0)) not in [float(x) for x in stage["eps_z"]]:
            raise GridConfigError(f"{cid}.eps_z must be listed in {name}.eps_z")
        position = case.get("position")
        if position not in STAGEB_ALLOWED_POSITIONS:
            raise GridConfigError(
                f"{cid}.position must be one of {STAGEB_ALLOWED_POSITIONS}"
            )
        predefect = case.get("predefect")
        if predefect not in STAGEB_ALLOWED_PREDEFECTS:
            raise GridConfigError(
                f"{cid}.predefect must be one of {STAGEB_ALLOWED_PREDEFECTS}"
            )
        if predefect == "seed_dislocation_if_available":
            raise GridConfigError(
                f"{cid}.predefect=seed_dislocation_if_available is unsupported until a real seeding tool exists"
            )
        if case.get("deterministic_seed") is None:
            raise GridConfigError(f"{cid}.deterministic_seed is required")
        if predefect == "vacancies_medium":
            if case.get("vacancy_count") is None and case.get("vacancy_fraction") is None:
                raise GridConfigError(
                    f"{cid}.vacancies_medium requires vacancy_count or vacancy_fraction"
                )
    prod_ids = stage.get("production_case_ids")
    if prod_ids:
        unknown = [cid for cid in prod_ids if cid not in seen]
        if unknown:
            raise GridConfigError(f"{name}.production_case_ids unknown cases: {unknown}")
        if len(prod_ids) > max_prod:
            raise GridConfigError(f"{name}.production_case_ids exceeds max_production_cases")


def output_root(cfg: dict[str, Any]) -> Path:
    raw = cfg["experiment"]["output_root"]
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def latest_run_dir(cfg: dict[str, Any]) -> Path | None:
    root = output_root(cfg)
    if not root.is_dir():
        return None
    candidates = sorted(d for d in root.iterdir() if d.is_dir())
    return candidates[-1] if candidates else None


def make_run_dir(cfg: dict[str, Any], explicit_run_dir: Path | str | None = None) -> Path:
    root = output_root(cfg).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if explicit_run_dir is None:
        run_dir = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    else:
        run_dir = Path(explicit_run_dir)
        if not run_dir.is_absolute():
            run_dir = REPO_ROOT / run_dir
        run_dir = run_dir.resolve()
    if not run_dir.is_relative_to(root):
        raise GridConfigError(f"run_dir escapes output_root: {run_dir} not under {root}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("cases", "logs", "structures", "summaries", "tables"):
        (run_dir / sub).mkdir(exist_ok=True)
    return run_dir


def safe_child(root: Path, *parts: str | int) -> Path:
    p = root.joinpath(*(str(x) for x in parts)).resolve()
    if not p.is_relative_to(root.resolve()):
        raise GridConfigError(f"generated path escapes run root: {p}")
    return p


def eps_tag(eps_z: float) -> str:
    return paths.eps_tag(float(eps_z))


def case_id(stage: str, atom_target: int, eps_z: float | None, phase: str) -> str:
    if eps_z is None:
        return f"{stage}_{int(atom_target)}_{phase}"
    return f"{stage}_{int(atom_target)}_eps_{eps_tag(float(eps_z))}_{phase}"


def deterministic_seed(text: str) -> int:
    return 10000 + (sum((i + 1) * ord(c) for i, c in enumerate(text)) % 80000)


def path_for_lammps(path: Path | str) -> str:
    return Path(path).resolve().as_posix()


def existing_parent_for_usage(path: Path) -> Path:
    p = Path(path).resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    return p


def free_disk_gb(path: Path) -> float:
    usage = shutil.disk_usage(existing_parent_for_usage(path))
    return usage.free / (1024**3)


def command_text(cmd: list[str]) -> str:
    return " ".join(str(x) for x in cmd)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def short_git_status() -> str:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return f"<git status failed: {exc}>"
    text = proc.stdout.strip()
    return text if text else "<clean>"


def git_changed_files() -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return [line for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def process_cpu_seconds(proc: subprocess.Popen) -> float | None:
    """Total kernel+user CPU seconds consumed by a child process (Windows), or None."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        handle = wintypes.HANDLE(int(proc._handle))  # type: ignore[attr-defined]
        times = [wintypes.FILETIME() for _ in range(4)]
        ok = ctypes.WinDLL("kernel32").GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
        if not ok:
            return None

        def _seconds(ft: Any) -> float:
            return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 1.0e7

        return _seconds(times[2]) + _seconds(times[3])
    except Exception:
        return None


def nvidia_smi_snapshot() -> dict[str, Any]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"available": False, "reason": "nvidia-smi not found"}
    cmd = [
        exe,
        "--query-gpu=name,memory.total,memory.used,driver_version,temperature.gpu,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception as exc:
        return {"available": False, "reason": str(exc)}
    rows = []
    for line in proc.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            rows.append(
                {
                    "name": parts[0],
                    "memory_total_mib": parts[1],
                    "memory_used_mib": parts[2],
                    "driver_version": parts[3],
                    "temperature_c": parts[4],
                    "utilization_gpu_percent": parts[5],
                }
            )
    return {"available": proc.returncode == 0, "returncode": proc.returncode, "gpus": rows, "stderr": proc.stderr.strip()}


def active_process_snapshot() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for image in ("lmp.exe", "lmp_kokkos_cuda.exe", "mpiexec.exe", "compute-sanitizer.exe"):
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            lines = [ln.strip() for ln in proc.stdout.splitlines() if image.lower() in ln.lower()]
            result[image] = lines
        except Exception as exc:
            result[image] = [f"tasklist failed: {exc}"]
    return result


def validation_plan_lines(cfg: dict[str, Any]) -> tuple[bool, list[str]]:
    lines: list[str] = []
    ok = True
    lines.append(f"experiment: {cfg['experiment']['name']}")
    lines.append(f"output_root: {output_root(cfg)}")
    lmp = Path(cfg["gpu_profile"]["lammps_executable"])
    if not lmp.is_file():
        ok = False
        lines.append(f"FAIL lammps_executable missing: {lmp}")
    else:
        lines.append(f"OK lammps_executable: {lmp}")
    if cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"] == PRODUCTION_NEIGHBOR_POLICY:
        lines.append(f"OK neighbor rewrite: {PRODUCTION_NEIGHBOR_POLICY}")
    else:
        ok = False
        lines.append("FAIL neighbor rewrite does not match validated policy")
    if "CUDA_LAUNCH_BLOCKING" in cfg["gpu_profile"].get("forbidden_environment", []):
        lines.append("OK production child env will remove CUDA_LAUNCH_BLOCKING")
    else:
        ok = False
        lines.append("FAIL CUDA_LAUNCH_BLOCKING missing from forbidden_environment")
    for path, label in (
        (paths.A0_BASELINE_DATA, "A0 baseline data"),
        (paths.MEAM_LIBRARY, "MEAM library"),
        (paths.MEAM_PARAMS, "MEAM params"),
        (paths.AL13FE4_DATA, "Fe4Al13 source data"),
    ):
        if Path(path).is_file():
            lines.append(f"OK {label}: {path}")
        else:
            ok = False
            lines.append(f"FAIL {label} missing: {path}")

    lines.append("")
    lines.append("Configured stages and cases:")
    resources = cfg["resources"]
    for stage_name, stage in cfg["stages"].items():
        if not stage.get("enabled", False):
            lines.append(f"- {stage_name}: disabled")
            continue
        atom_targets = [int(x) for x in stage["atom_targets"]]
        eps_values = [float(x) for x in stage["eps_z"]]
        optional = [float(x) for x in stage.get("optional_eps_after_stable", [])]
        overload = [float(x) for x in stage.get("overload_eps_only_if_previous_signal", [])]
        lines.append(
            f"- {stage_name}: mode={stage['structure_mode']} targets={atom_targets} "
            f"eps={eps_values} optional={optional or overload}"
        )
        lines.append(
            f"  steps smoke/short/production="
            f"{stage['smoke_steps']}/{stage['short_steps']}/{stage['production_steps']}"
        )
        if stage["structure_mode"] == "existing_A0":
            for eps in eps_values:
                tmpl = paths.a0_template_for_tag(eps_tag(eps))
                if tmpl.is_file():
                    lines.append(f"  OK A0 template eps_{eps_tag(eps)}: {tmpl}")
                else:
                    ok = False
                    lines.append(f"  FAIL A0 template missing eps_{eps_tag(eps)}: {tmpl}")
        else:
            try:
                if stage["structure_mode"] == STAGEB_REALISM_MODE:
                    cases = stage.get("cases", [])
                    lines.append(f"  Stage B realism cases: {len(cases)}")
                    for case in cases:
                        plan = builder.plan_for_target(
                            int(case["atom_target"]),
                            ranks=1,
                            max_memory_gb=resources["gpu_memory_gb"],
                        )
                        lines.append(
                            "  case {case_id}: position={position} predefect={predefect} "
                            "eps={eps_z} target={target_atoms} est_atoms={estimated_atoms} "
                            "est_gpu_mem_gb={estimated_memory_gb} feasible={feasible_under_memory_limit}".format(
                                **case, **plan
                            )
                        )
                else:
                    for target in atom_targets:
                        plan = builder.plan_for_target(target, ranks=1, max_memory_gb=resources["gpu_memory_gb"])
                        lines.append(
                            "  plan target={target_atoms} est_atoms={estimated_atoms} "
                            "est_gpu_mem_gb={estimated_memory_gb} feasible={feasible_under_memory_limit}".format(**plan)
                        )
            except Exception as exc:
                ok = False
                lines.append(f"  FAIL structure planning failed: {exc}")
    return ok, lines


def check_environment(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any], list[str]]:
    ok = True
    lines: list[str] = []
    env_report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(REPO_ROOT),
        "output_root": str(output_root(cfg)),
    }

    lmp = Path(cfg["gpu_profile"]["lammps_executable"])
    if not lmp.is_file():
        ok = False
        lines.append(f"FAIL LAMMPS GPU binary missing: {lmp}")
    else:
        lines.append(f"OK LAMMPS GPU binary exists: {lmp}")
        try:
            help_text = get_help_text(lmp, REPO_ROOT)
            caps = parse_capabilities(help_text)
            env_report["lammps_capabilities"] = caps
            for key in ("has_meam", "has_meam_kk", "has_kokkos", "has_kokkos_cuda"):
                if caps.get(key):
                    lines.append(f"OK {key}: {caps.get(key)}")
                else:
                    ok = False
                    lines.append(f"FAIL {key}: {caps.get(key)}")
            lines.append(f"KOKKOS API: {caps.get('kokkos_api')}")
        except Exception as exc:
            ok = False
            lines.append(f"FAIL lmp -h capability check: {exc}")

    imports = {}
    for mod in ("yaml", "numpy", "pandas", "matplotlib", "ovito", "scipy"):
        try:
            m = importlib.import_module(mod)
            imports[mod] = getattr(m, "__version__", "imported")
            lines.append(f"OK python import {mod}: {imports[mod]}")
        except Exception as exc:
            imports[mod] = f"FAILED: {exc}"
            if mod in ("yaml", "numpy", "scipy"):
                ok = False
                lines.append(f"FAIL python import {mod}: {exc}")
            else:
                lines.append(f"WARN python import {mod}: {exc}")
    env_report["python_imports"] = imports

    forbidden = cfg["gpu_profile"].get("forbidden_environment", [])
    forbidden_present = [name for name in forbidden if name in os.environ]
    env_report["forbidden_environment_present_in_parent"] = forbidden_present
    if forbidden_present:
        lines.append(
            "WARN parent environment contains forbidden production keys; child LAMMPS env will remove: "
            + ", ".join(forbidden_present)
        )
    else:
        lines.append("OK parent environment has no forbidden production keys")

    disks = {}
    for drive in ("C:\\", "B:\\"):
        p = Path(drive)
        if p.exists():
            disks[drive] = round(free_disk_gb(p), 2)
            lines.append(f"disk free {drive}: {disks[drive]} GB")
    disks[str(output_root(cfg))] = round(free_disk_gb(output_root(cfg)), 2)
    env_report["disk_free_gb"] = disks

    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        env_report["ram_gb"] = round(vm.total / (1024**3), 2)
        lines.append(f"RAM total: {env_report['ram_gb']} GB")
    except Exception:
        env_report["ram_gb"] = None
        lines.append("WARN psutil unavailable; RAM total not recorded")

    env_report["nvidia_smi"] = nvidia_smi_snapshot()
    if env_report["nvidia_smi"].get("available"):
        lines.append(f"OK nvidia-smi: {env_report['nvidia_smi'].get('gpus')}")
    else:
        ok = False
        lines.append(f"FAIL nvidia-smi unavailable: {env_report['nvidia_smi'].get('reason')}")

    env_report["active_processes"] = active_process_snapshot()
    for image, rows in env_report["active_processes"].items():
        if rows:
            lines.append(f"WARN active {image}: {rows}")
        else:
            lines.append(f"OK no active {image}")

    return ok, env_report, lines


class StateStore:
    def __init__(self, run_dir: Path):
        self.path = run_dir / "state.json"
        self.data = read_json(
            self.path,
            {
                "run_dir": str(run_dir),
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at": None,
                "cases": {},
                "stages": {},
                "gates": {},
                "stop_reason": None,
            },
        )

    def save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def case(self, cid: str) -> dict[str, Any] | None:
        return self.data.get("cases", {}).get(cid)

    def case_success(self, cid: str) -> bool:
        return bool((self.case(cid) or {}).get("success"))

    def mark_case(self, cid: str, record: dict[str, Any]) -> None:
        self.data.setdefault("cases", {})[cid] = record
        self.save()

    def mark_stage(self, stage: str, record: dict[str, Any]) -> None:
        self.data.setdefault("stages", {})[stage] = record
        self.save()

    def mark_gate(self, stage: str, record: dict[str, Any]) -> None:
        self.data.setdefault("gates", {})[stage] = record
        self.save()

    def stop(self, reason: str) -> None:
        self.data["stop_reason"] = reason
        self.save()


class GpuGridRunner:
    def __init__(
        self,
        cfg: dict[str, Any],
        *,
        run_dir: Path | str | None = None,
        resume: bool = False,
        force_rerun: str | None = None,
        smoke_only: bool = False,
    ):
        self.cfg = cfg
        if resume and run_dir is None:
            run_dir = latest_run_dir(cfg)
            if run_dir is None:
                raise GridStop("no existing GPU grid run found to resume")
        self.run_dir = make_run_dir(cfg, explicit_run_dir=run_dir)
        self.force_rerun = force_rerun
        self.smoke_only = smoke_only
        self.state = StateStore(self.run_dir)
        self.write_effective_config()
        self.env_report: dict[str, Any] | None = None

    @property
    def summaries_dir(self) -> Path:
        return self.run_dir / "summaries"

    @property
    def tables_dir(self) -> Path:
        return self.run_dir / "tables"

    def write_effective_config(self) -> None:
        (self.run_dir / "effective_config.yaml").write_text(
            yaml.safe_dump(self.cfg, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )

    def child_env(self) -> dict[str, str]:
        env = dict(os.environ)
        for name in self.cfg["gpu_profile"].get("forbidden_environment", []):
            env.pop(name, None)
        env["OMP_NUM_THREADS"] = str(int(self.cfg["resources"].get("cpu_helper_threads", 1)))
        return env

    def lammps_cmd(self, input_path: Path, log_path: Path) -> list[str]:
        gp = self.cfg["gpu_profile"]
        return [gp["lammps_executable"], *[str(x) for x in gp["command_args"]], "-in", input_path.name, "-log", log_path.name]

    @staticmethod
    def chunk_input_name(chunk_tag: str) -> str:
        return f"in.{chunk_tag}"

    @staticmethod
    def chunk_log_name(chunk_tag: str) -> str:
        return f"log.{chunk_tag}.lammps"

    @staticmethod
    def chunk_dump_name(chunk_tag: str) -> str:
        return f"dump.{chunk_tag}.lammpstrj"

    @staticmethod
    def chunk_restart_name(step: int) -> str:
        return f"restart.{int(step)}"

    @staticmethod
    def chunk_restart_glob() -> str:
        return "restart.*"

    @staticmethod
    def chunk_final_data_name() -> str:
        return "data.final"

    @staticmethod
    def chunk_final_dump_name() -> str:
        return "dump.final.lammpstrj"

    def production_reliability(self) -> dict[str, Any]:
        raw = self.cfg.get("production_reliability") or {}
        return {
            "production_chunk_steps": int(raw.get("production_chunk_steps", 10000)),
            "max_no_progress_minutes": float(raw.get("max_no_progress_minutes", 25)),
            "resume_from_latest_restart": bool(raw.get("resume_from_latest_restart", True)),
            "retry_hung_chunk_once": bool(raw.get("retry_hung_chunk_once", True)),
            "watchdog_poll_seconds": float(raw.get("watchdog_poll_seconds", 30)),
        }

    def _watchdog_event(self, msg: str) -> str:
        return f"{datetime.now().isoformat(timespec='seconds')} {msg}"

    def _progress_signature(self, work_dir: Path, proc: subprocess.Popen) -> dict[str, Any]:
        """Snapshot of everything that should change while LAMMPS makes progress."""
        sig: dict[str, Any] = {}
        try:
            for p in work_dir.iterdir():
                if not p.is_file():
                    continue
                if p.name.startswith(("log.", "dump.", "restart.", "data.", "stdout", "stderr")):
                    st = p.stat()
                    sig[p.name] = (st.st_size, st.st_mtime_ns)
        except OSError:
            pass
        cpu = process_cpu_seconds(proc)
        if cpu is not None:
            sig["__cpu_seconds__"] = round(cpu, 1)
        return sig

    def _wait_after_kill(self, proc: subprocess.Popen) -> int | None:
        try:
            return proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            return None

    def _wait_with_watchdog(
        self, proc: subprocess.Popen, work_dir: Path, *, timeout_s: int
    ) -> tuple[int | None, bool, bool, list[str]]:
        """Wait for LAMMPS while watching CPU time and log/dump/restart growth.

        Hung means: process alive but CPU delta is zero and no watched file grows
        for max_no_progress_minutes. Returns (exit_code, timed_out, hung, events).
        """
        rel = self.production_reliability()
        no_progress_s = rel["max_no_progress_minutes"] * 60.0
        poll_s = max(5.0, rel["watchdog_poll_seconds"])
        start = time.time()
        last_change = start
        last_sig = self._progress_signature(work_dir, proc)
        events: list[str] = []
        while True:
            elapsed = time.time() - start
            if elapsed >= timeout_s:
                events.append(self._watchdog_event(f"timeout after {elapsed / 3600.0:.2f} h -> kill PID {proc.pid}"))
                self.kill_process_tree(proc.pid)
                return self._wait_after_kill(proc), True, False, events
            try:
                exit_code = proc.wait(timeout=max(1.0, min(poll_s, timeout_s - elapsed)))
                return exit_code, False, False, events
            except subprocess.TimeoutExpired:
                pass
            sig = self._progress_signature(work_dir, proc)
            now = time.time()
            if sig != last_sig:
                last_sig = sig
                last_change = now
            elif now - last_change >= no_progress_s:
                events.append(
                    self._watchdog_event(
                        f"no CPU/log/dump/restart progress for {(now - last_change) / 60.0:.1f} min "
                        f"(limit {no_progress_s / 60.0:.0f} min) -> kill PID {proc.pid}"
                    )
                )
                self.kill_process_tree(proc.pid)
                return self._wait_after_kill(proc), False, True, events

    def phase_timeout_s(self, stage: str, phase: str) -> int:
        hours = self.cfg["resources"]["max_run_hours"]
        if phase == "production":
            key = f"production_{stage}"
            return int(float(hours.get(key, hours.get("production_A0", 5))) * 3600)
        if phase == "prep":
            return int(float(hours.get("smoke", 2)) * 3600)
        return int(float(hours.get(phase, 2)) * 3600)

    def check_disk_for_stage(self, stage: str) -> tuple[bool, str]:
        threshold = float(self.cfg["resources"]["min_free_disk_gb_before_stage"])
        if stage.startswith(LARGE_STAGE_PREFIXES):
            threshold = float(self.cfg["resources"]["min_free_disk_gb_before_large_stage"])
        free = free_disk_gb(self.run_dir)
        if free < threshold:
            return False, f"free disk below threshold before {stage}: {free:.1f} GB < {threshold:.1f} GB"
        return True, f"free disk OK before {stage}: {free:.1f} GB >= {threshold:.1f} GB"

    def case_dir(self, stage: str, atom_target: int, eps_z: float | None, phase: str) -> Path:
        eps_part = "no_eps" if eps_z is None else f"eps_{eps_tag(float(eps_z))}"
        d = safe_child(self.run_dir, "cases", stage, f"atoms_{int(atom_target)}", eps_part, phase)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def structure_dir(self, stage: str, atom_target: int, eps_z: float | None = None) -> Path:
        parts: list[str | int] = ["structures", stage, int(atom_target)]
        if eps_z is not None:
            parts.append(f"eps_{eps_tag(float(eps_z))}")
        d = safe_child(self.run_dir, *parts)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def stageb_case_dir(self, stage: str, case_name: str, phase: str) -> Path:
        d = safe_child(self.run_dir, "cases", stage, case_name, phase)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def stageb_structure_dir(self, stage: str, case_name: str, eps_z: float | None = None) -> Path:
        parts: list[str | int] = ["structures", stage, case_name]
        if eps_z is not None:
            parts.append(f"eps_{eps_tag(float(eps_z))}")
        d = safe_child(self.run_dir, *parts)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _stageb_runtime_case_id(case_cfg: Mapping[str, Any], phase: str) -> str:
        return f"{case_cfg['case_id']}_{phase}"

    def stageb_cases(self, stage: str) -> list[dict[str, Any]]:
        return list(self.cfg["stages"][stage].get("cases", []))

    def input_for_phase(
        self,
        *,
        template_text: str,
        data_path: Path,
        stage: str,
        atom_target: int,
        eps_z: float | None,
        phase: str,
        steps: int,
        inclusion_id_min: int | None,
        inclusion_id_max: int | None,
        case_name: str,
    ) -> str:
        io = self.cfg["io_policy"]
        temp = float(self.cfg["experiment"]["temperature_K"])
        neighbor_policy = self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"]
        thermo_every = int(io["thermo_every"].get(phase, io["thermo_every"]["smoke"]))
        dump_every = int(io["dump_every"].get(phase, io["dump_every"]["smoke"]))
        configured_dump_fields = io.get("dump_fields")
        if isinstance(configured_dump_fields, list):
            configured_dump_fields = " ".join(str(x) for x in configured_dump_fields)
        elif configured_dump_fields is not None:
            configured_dump_fields = str(configured_dump_fields)
        restart_every = int(io.get("restart_every", 0))
        seed = deterministic_seed(case_name)
        final_data = f"data.{case_name}_final"
        final_dump = f"dump.{case_name}_final.lammpstrj"
        trajectory_dump = f"dump.{case_name}.lammpstrj"
        out: list[str] = [
            f"# Run-local GPU grid input for {case_name}",
            "# Generated from project template; tracked templates and baseline data are not modified.",
        ]
        found_neigh = False
        inserted_restart = False
        for raw in template_text.splitlines():
            stripped = raw.strip()
            if not stripped:
                out.append(raw)
                continue
            if stripped.startswith("#"):
                out.append(raw)
                continue
            if re.match(r"^read_data\s+", stripped):
                out.append(f"read_data       {path_for_lammps(data_path)}")
            elif re.match(r"^pair_coeff\s+", stripped):
                out.append(
                    "pair_coeff      * * "
                    f"{path_for_lammps(paths.MEAM_LIBRARY)} AlS SiS MgS CuS FeS "
                    f"{path_for_lammps(paths.MEAM_PARAMS)} AlS FeS"
                )
            elif re.match(r"^neigh_modify\s+", stripped):
                out.append(neighbor_policy)
                found_neigh = True
            elif re.match(r"^thermo\s+\d+", stripped):
                out.append(f"thermo          {thermo_every}")
            elif stripped.startswith("group") and "inclusion id" in stripped and inclusion_id_min and inclusion_id_max:
                out.append(f"group           inclusion id {int(inclusion_id_min)}:{int(inclusion_id_max)}")
            elif stripped.startswith("velocity") and "create" in stripped:
                parts = stripped.split()
                group = parts[1] if len(parts) > 1 else "all"
                suffix = " ".join(parts[5:]) if len(parts) > 5 else "mom yes rot no dist gaussian"
                out.append(f"velocity        {group} create {temp:.1f} {seed} {suffix}")
            elif stripped.startswith("fix") and " nvt " in f" {stripped} " and " temp " in f" {stripped} ":
                parts = stripped.split()
                fix_id = parts[1] if len(parts) > 1 else "nvt_all"
                group = parts[2] if len(parts) > 2 else "all"
                out.append(f"fix             {fix_id} {group} nvt temp {temp:.1f} {temp:.1f} 0.1")
            elif stripped.startswith("dump ") and " custom " in stripped:
                # Keep the same fields as the source trajectory dump, but make frequency and filename config-driven.
                parts = stripped.split()
                fields = configured_dump_fields or (" ".join(parts[6:]) if len(parts) > 6 else "id type x y z")
                dump_id = parts[1] if len(parts) > 1 else "d1"
                group = parts[2] if len(parts) > 2 else "all"
                out.append(f"dump            {dump_id} {group} custom {dump_every} {trajectory_dump} {fields}")
            elif re.match(r"^run\s+\d+", stripped):
                if restart_every > 0 and not inserted_restart:
                    out.append(f"restart         {restart_every} restart.{case_name}.*")
                    inserted_restart = True
                out.append(f"run             {int(steps)}")
            elif re.match(r"^write_data\s+", stripped):
                if io.get("write_final_data", True):
                    out.append(f"write_data      {final_data}")
            elif re.match(r"^write_dump\s+", stripped):
                if io.get("write_final_dump", True):
                    fields = configured_dump_fields or "id type x y z"
                    out.append(f"write_dump      all custom {final_dump} {fields} modify sort id")
            else:
                out.append(raw)
        if not found_neigh:
            for i, line in enumerate(out):
                if line.strip().startswith("neighbor"):
                    out.insert(i + 1, neighbor_policy)
                    found_neigh = True
                    break
        if not found_neigh:
            out.append("neighbor        2.0 bin")
            out.append(neighbor_policy)
        text = "\n".join(out).rstrip() + "\n"
        if neighbor_policy not in text:
            raise GridStop(f"input for {case_name} is missing required neighbor policy")
        if (
            re.search(r"(?mi)^\s*(minimize|min_style)\b", text)
            or
            re.search(r"(?m)^\s*thermo\s+1\s*$", text)
            or "CUDA_LAUNCH_BLOCKING" in text
            or "compute-sanitizer" in text
        ):
            raise GridStop(f"forbidden debug setting leaked into input for {case_name}")
        return text

    def a0_structure(self, eps_z: float) -> dict[str, Any]:
        atom_target = int(self.cfg["stages"]["A0_24k"]["atom_targets"][0])
        if abs(float(eps_z)) < 1.0e-12:
            return {
                "data_path": paths.A0_BASELINE_DATA,
                "matrix_max_id": paths.A0_MATRIX_MAX_ID,
                "inclusion_id_min": paths.A0_INCLUSION_ID_MIN,
                "inclusion_id_max": paths.A0_INCLUSION_ID_MAX,
                "inclusion_atoms": paths.A0_INCLUSION_ATOMS,
                "center_A": list(paths.A0_CENTER),
                "inclusion_axes_A": list(paths.A0_INCLUSION_AXES),
                "atom_count": atom_target,
            }
        out_dir = self.structure_dir("A0_24k", atom_target, eps_z)
        tag = paths.epsz_dirtag(float(eps_z))
        data_path = out_dir / f"data.ellipsoid_eigenstrain_{tag}"
        report_path = out_dir / f"ellipsoid_eigenstrain_{tag}_build_report.json"
        if not data_path.is_file():
            eigenstrain.regenerate(
                paths.A0_BASELINE_DATA,
                out_dir,
                float(eps_z),
                inclusion_id_min=paths.A0_INCLUSION_ID_MIN,
                inclusion_id_max=paths.A0_INCLUSION_ID_MAX,
                expected_inclusion_atoms=paths.A0_INCLUSION_ATOMS,
                center=paths.A0_CENTER,
            )
        report = read_json(report_path, {})
        return {
            "data_path": data_path,
            "matrix_max_id": paths.A0_MATRIX_MAX_ID,
            "inclusion_id_min": paths.A0_INCLUSION_ID_MIN,
            "inclusion_id_max": paths.A0_INCLUSION_ID_MAX,
            "inclusion_atoms": paths.A0_INCLUSION_ATOMS,
            "center_A": report.get("center_A", list(paths.A0_CENTER)),
            "inclusion_axes_A": list(paths.A0_INCLUSION_AXES),
            "atom_count": atom_target,
        }

    def ensure_scaled_baseline(self, stage: str, atom_target: int) -> dict[str, Any]:
        build_dir = self.structure_dir(stage, atom_target)
        meta_path = build_dir / "a1_small_metadata.json"
        if meta_path.is_file():
            meta = read_json(meta_path, {})
        else:
            plan = builder.plan_for_target(
                int(atom_target),
                ranks=1,
                max_memory_gb=float(self.cfg["resources"]["gpu_memory_gb"]),
            )
            if not plan["feasible_under_memory_limit"]:
                raise GridStop(
                    f"{stage} target {atom_target} estimated GPU memory "
                    f"{plan['estimated_memory_gb']} GB exceeds configured "
                    f"{self.cfg['resources']['gpu_memory_gb']} GB"
                )
            meta = builder.build_structure(plan, build_dir)

        prep_dir = self.case_dir(stage, int(atom_target), None, "prep")
        baseline_data = prep_dir / "data.a1_baseline_equil"
        if baseline_data.is_file() and self.state.case_success(case_id(stage, atom_target, None, "prep")):
            meta["baseline_data"] = str(baseline_data)
            return meta

        prep_case = case_id(stage, atom_target, None, "prep")
        if self.state.case_success(prep_case) and self.force_rerun != prep_case:
            meta["baseline_data"] = str(baseline_data)
            return meta

        stage_cfg = self.cfg["stages"][stage]
        prep_equil_steps = int(stage_cfg.get("prep_steps", stage_cfg["smoke_steps"]))
        prep_ramp_steps = int(stage_cfg.get("prep_ramp_steps", 3000))
        prep_segments = stage_cfg.get("prep_segments")
        if prep_segments is not None:
            prep_total_steps = sum(int(seg["steps"]) for seg in prep_segments)
        else:
            prep_total_steps = prep_ramp_steps + prep_equil_steps
        prep_restart_every = int(stage_cfg.get("prep_restart_every", self.cfg["io_policy"].get("restart_every", 10000)))
        # GPU-safe prep: no minimize (LAMMPS would override neigh_modify to
        # 'every 1 delay 0 check yes' during minimization and crash meam/kk CUDA
        # with cudaErrorIllegalAddress; see A1_prep_failure_diagnosis.md). The
        # input is final as generated: the generic input_for_phase rewrites
        # would clobber the temperature ramp and the two run sections.
        prep_input = builder.make_prep_input_gpu_safe(
            meta,
            t_start_K=float(stage_cfg.get("prep_t_start_K", 50.0)),
            t_target_K=float(self.cfg["experiment"]["temperature_K"]),
            ramp_steps=prep_ramp_steps,
            equil_steps=prep_equil_steps,
            seed=deterministic_seed(prep_case),
            thermo_every=int(self.cfg["io_policy"]["thermo_every"]["smoke"]),
            neighbor_policy=self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"],
            restart_every=prep_restart_every,
            restart_prefix=prep_case,
            segments=prep_segments,
            dump_every=stage_cfg.get("prep_dump_every"),
            dump_fields=stage_cfg.get("prep_dump_fields"),
        )
        self._assert_prep_input_safe(prep_input, prep_case)
        meta.setdefault("atom_count", int(meta["total_atoms"]))
        rec = self.execute_case(
            case_name=prep_case,
            stage=stage,
            atom_target=int(atom_target),
            eps_z=None,
            phase="prep",
            steps=prep_total_steps,
            input_text=prep_input,
            work_dir=prep_dir,
            structure_meta=meta,
            expected_outputs=["data.a1_baseline_equil"],
        )
        if not rec["success"]:
            raise GridStop(f"prep failed for {stage} target {atom_target}: {rec.get('failure_reasons')}")
        meta["baseline_data"] = str(baseline_data)
        self.write_structure_prep_report(stage, int(atom_target))
        return meta

    def _assert_prep_input_safe(self, text: str, case_name: str) -> None:
        policy = self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"]
        if policy not in text:
            raise GridStop(f"prep input for {case_name} is missing the required neighbor policy line")
        if re.search(r"(?mi)^\s*(minimize|min_style)\b", text):
            raise GridStop(
                f"prep input for {case_name} contains minimize, forbidden on meam/kk KOKKOS CUDA "
                "(LAMMPS overrides neigh_modify to 'every 1 check yes' during minimization)"
            )
        if (
            re.search(r"(?m)^\s*thermo\s+1\s*$", text)
            or "CUDA_LAUNCH_BLOCKING" in text
            or "compute-sanitizer" in text
        ):
            raise GridStop(f"forbidden debug setting leaked into prep input for {case_name}")

    def write_structure_prep_report(self, stage: str, atom_target: int) -> None:
        """structure_prep_report.md in the run root: build + prep + eps coverage."""
        build_dir = self.structure_dir(stage, atom_target)
        meta = read_json(build_dir / "a1_small_metadata.json", {})
        build_report = read_json(build_dir / "a1_small_build_report.json", {})
        if not meta:
            return
        prep_case = case_id(stage, atom_target, None, "prep")
        prep_rec = self.state.case(prep_case) or {}
        prep_final = prep_rec.get("log_summary", {}).get("final_thermo") or {}
        eps_files = sorted(build_dir.glob("eps_*/data.ellipsoid_eigenstrain_*"))
        eps_reports = sorted(build_dir.glob("eps_*/ellipsoid_eigenstrain_*_build_report.json"))
        box = meta.get("box_A", [])
        # baseline_data is only set on the in-memory meta, never persisted to the
        # metadata json; derive the canonical path and report its real presence.
        baseline_path = Path(
            meta.get("baseline_data")
            or self.case_dir(stage, atom_target, None, "prep") / "data.a1_baseline_equil"
        )
        baseline_note = "" if baseline_path.is_file() else " (not written yet)"
        min_pair = build_report.get("min_pair_distance_A")
        min_pair_note = min_pair if min_pair is not None else "no pairs within 2.1 A"
        lines = [
            f"# Structure prep report: {stage} target {atom_target}",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run root: `{self.run_dir}`",
            "",
            "## Atom counts",
            "",
            f"- target_atom_count: {atom_target}",
            f"- actual_atom_count: {meta.get('total_atoms')}",
            f"- matrix_atoms: {meta.get('matrix_atoms')} (ids 1..{meta.get('matrix_max_id')})",
            f"- inclusion_atoms: {meta.get('inclusion_atoms')} "
            f"(ids {meta.get('inclusion_id_min')}..{meta.get('inclusion_id_max')})",
            "",
            "## Geometry",
            "",
            f"- box_A: {[round(float(b), 3) for b in box] if box else 'n/a'}",
            f"- center_A: {[round(float(c), 3) for c in meta.get('center_A', [])]}",
            f"- inclusion_axes_A: {[round(float(a), 3) for a in meta.get('inclusion_axes_A', [])]}",
            f"- al_lattice_A: {meta.get('al_lattice_A')}",
            f"- type_mapping: {meta.get('type_mapping')}",
            "",
            "## Clearance / sanity checks (builder)",
            "",
            f"- pairs_below_1p8_A (hard): {build_report.get('pairs_below_1p8_A')}",
            f"- cross_source_pairs_below_2p1_A: {build_report.get('cross_source_pairs_below_2p1_A')}",
            f"- pairs_below_2p1_A (warn): {build_report.get('pairs_below_2p1_A')}",
            f"- min_pair_distance_A: {min_pair_note}",
            f"- removed_matrix_atoms_near_inclusion: {build_report.get('removed_matrix_atoms_near_inclusion')}",
            f"- clearance_A: {build_report.get('clearance_A')}",
            f"- safe_basic: {build_report.get('safe_basic')}",
            "",
            "## Prep run (GPU-safe, no minimize)",
            "",
            f"- case: {prep_case}",
            f"- status: {prep_rec.get('status', 'not_run')}",
            f"- protocol: settle ramp ({self.cfg['stages'][stage].get('prep_t_start_K', 50.0)} K -> "
            f"{self.cfg['experiment']['temperature_K']} K, timestep 0.0005) + NVT equilibration (timestep 0.001)",
            f"- steps_target: {prep_rec.get('steps_target')}",
            f"- wall_time_s: {prep_rec.get('wall_time_s')}",
            f"- final_temp_K: {prep_final.get('Temp')}",
            f"- final_pe_eV: {prep_final.get('PotEng')}",
            f"- final_press_bar: {prep_final.get('Press')}",
            "",
            "## Generated data paths",
            "",
            f"- as_built: `{meta.get('data_file')}`",
            f"- baseline_equil: `{baseline_path}`{baseline_note}",
            f"- build_report: `{build_dir / 'a1_small_build_report.json'}`",
            f"- metadata: `{build_dir / 'a1_small_metadata.json'}`",
            "",
            "## Eigenstrain data paths",
            "",
        ]
        if eps_files:
            lines += [f"- `{p}`" for p in eps_files]
            lines += [f"- report: `{p}`" for p in eps_reports]
        else:
            lines.append("- none generated yet (created lazily per eps case)")
        lines += [
            "",
            "## Warnings / limitations",
            "",
            f"- exact {atom_target} atoms is impossible with integer fcc replication; "
            f"the nearest lattice-commensurate build ({meta.get('total_atoms')} atoms) is used.",
            "- the baseline is thermally settled (no energy minimization): minimize is "
            "forbidden on meam/kk KOKKOS CUDA (neighbor-policy override crash; see "
            "A1_prep_failure_diagnosis.md). A small systematic offset in interface "
            "CNA counts vs the minimized A0 baseline is possible; compare eps cases "
            "against this stage's own baseline first.",
            "- dangerous neighbor builds are not checked (`check no` workaround).",
        ]
        (self.run_dir / "structure_prep_report.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def scaled_structure(self, stage: str, atom_target: int, eps_z: float) -> dict[str, Any]:
        meta = self.ensure_scaled_baseline(stage, atom_target)
        if abs(float(eps_z)) < 1.0e-12:
            return {
                "data_path": Path(meta["baseline_data"]),
                "matrix_max_id": int(meta["matrix_max_id"]),
                "inclusion_id_min": int(meta["inclusion_id_min"]),
                "inclusion_id_max": int(meta["inclusion_id_max"]),
                "inclusion_atoms": int(meta["inclusion_atoms"]),
                "center_A": meta["center_A"],
                "inclusion_axes_A": meta["inclusion_axes_A"],
                "atom_count": int(meta["total_atoms"]),
            }
        out_dir = self.structure_dir(stage, int(atom_target), eps_z)
        tag = paths.epsz_dirtag(float(eps_z))
        data_path = out_dir / f"data.ellipsoid_eigenstrain_{tag}"
        report_path = out_dir / f"ellipsoid_eigenstrain_{tag}_build_report.json"
        if not data_path.is_file():
            eigenstrain.regenerate(
                Path(meta["baseline_data"]),
                out_dir,
                float(eps_z),
                inclusion_id_min=int(meta["inclusion_id_min"]),
                inclusion_id_max=int(meta["inclusion_id_max"]),
                expected_inclusion_atoms=int(meta["inclusion_atoms"]),
                center=tuple(float(x) for x in meta["center_A"]),
            )
            self.write_structure_prep_report(stage, int(atom_target))
        report = read_json(report_path, {})
        return {
            "data_path": data_path,
            "matrix_max_id": int(meta["matrix_max_id"]),
            "inclusion_id_min": int(meta["inclusion_id_min"]),
            "inclusion_id_max": int(meta["inclusion_id_max"]),
            "inclusion_atoms": int(meta["inclusion_atoms"]),
            "center_A": report.get("center_A", meta["center_A"]),
            "inclusion_axes_A": meta["inclusion_axes_A"],
            "atom_count": int(meta["total_atoms"]),
        }

    def ensure_stageb_geometry(self, stage: str, case_cfg: Mapping[str, Any]) -> dict[str, Any]:
        case_name = str(case_cfg["case_id"])
        build_dir = self.stageb_structure_dir(stage, case_name)
        meta_path = build_dir / "stageB_realism_metadata.json"
        if meta_path.is_file():
            meta = read_json(meta_path, {})
        else:
            plan = builder.plan_for_target(
                int(case_cfg["atom_target"]),
                ranks=1,
                max_memory_gb=float(self.cfg["resources"]["gpu_memory_gb"]),
            )
            if not plan["feasible_under_memory_limit"]:
                raise GridStop(
                    f"{case_name} estimated GPU memory {plan['estimated_memory_gb']} GB exceeds "
                    f"{self.cfg['resources']['gpu_memory_gb']} GB"
                )
            meta = builder.build_stageb_realism_structure(
                plan,
                build_dir,
                case_id=case_name,
                position=str(case_cfg["position"]),
                predefect=str(case_cfg["predefect"]),
                deterministic_seed=int(case_cfg["deterministic_seed"]),
                vacancy_fraction=(
                    float(case_cfg["vacancy_fraction"])
                    if case_cfg.get("vacancy_fraction") is not None else None
                ),
                vacancy_count=(
                    int(case_cfg["vacancy_count"])
                    if case_cfg.get("vacancy_count") is not None else None
                ),
                boundary_surface_gap_A=float(case_cfg.get("boundary_surface_gap_A", 5.0)),
            )
        self.validate_stageb_geometry(case_cfg, meta)
        return meta

    def validate_stageb_geometry(self, case_cfg: Mapping[str, Any], meta: Mapping[str, Any]) -> None:
        cid = str(case_cfg["case_id"])
        atoms = int(meta.get("actual_atom_count") or meta.get("total_atoms") or 0)
        target = int(case_cfg.get("atom_target", 100000) or 100000)
        lower = max(1, int(round(target * 0.85)))
        upper = int(round(target * 1.15))
        if atoms < lower or atoms > upper:
            raise GridStop(
                f"{cid} actual atom count outside target-relative range "
                f"{lower}..{upper}: {atoms}"
            )
        if int(meta.get("matrix_atoms", 0) or 0) <= 0:
            raise GridStop(f"{cid} has no matrix atoms")
        if int(meta.get("inclusion_atoms", 0) or 0) <= 0:
            raise GridStop(f"{cid} has no inclusion atoms")
        if not bool(meta.get("no_inclusion_atoms_deleted", False)):
            raise GridStop(f"{cid} deleted inclusion atoms")
        if not bool(meta.get("safe_basic", False)):
            raise GridStop(f"{cid} geometry safety check failed")
        center = [float(x) for x in meta.get("center_A", [])]
        box = [float(x) for x in meta.get("box_A", [])]
        axes = [float(x) for x in meta.get("inclusion_axes_A", [])]
        if len(center) != 3 or len(box) != 3 or len(axes) != 3:
            raise GridStop(f"{cid} missing center/box/axes metadata")
        for c, b, a in zip(center, box, axes):
            if c - a <= 0.0 or c + a >= b:
                raise GridStop(f"{cid} inclusion is clipped or outside the box")
        if case_cfg["position"] == "near_grain_boundary":
            boundary = meta.get("boundary") or {}
            if not boundary.get("boundary_plane") or not boundary.get("grain2_orientation"):
                raise GridStop(f"{cid} near_grain_boundary metadata missing")
            if float(boundary.get("inclusion_surface_gap_to_boundary_A", -1.0)) <= 0.0:
                raise GridStop(f"{cid} inclusion overlaps the grain-boundary plane")
        if case_cfg["predefect"] == "vacancies_medium":
            vacancy = meta.get("vacancy") or {}
            if int(vacancy.get("vacancy_count_actual", 0) or 0) <= 0:
                raise GridStop(f"{cid} vacancies_medium created no vacancies")
            if not bool(vacancy.get("no_inclusion_atoms_deleted", False)):
                raise GridStop(f"{cid} vacancy deletion touched inclusion atoms")

    def ensure_stageb_baseline(self, stage: str, case_cfg: Mapping[str, Any]) -> dict[str, Any]:
        meta = self.ensure_stageb_geometry(stage, case_cfg)
        case_name = str(case_cfg["case_id"])
        prep_dir = self.stageb_case_dir(stage, case_name, "prep")
        baseline_data = prep_dir / "data.a1_baseline_equil"
        prep_case = self._stageb_runtime_case_id(case_cfg, "prep")
        if baseline_data.is_file() and self.state.case_success(prep_case):
            meta["baseline_data"] = str(baseline_data)
            return meta
        if self.state.case_success(prep_case) and self.force_rerun != prep_case:
            meta["baseline_data"] = str(baseline_data)
            return meta

        stage_cfg = self.cfg["stages"][stage]
        prep_equil_steps = int(case_cfg.get("prep_steps", stage_cfg.get("prep_steps", stage_cfg["smoke_steps"])))
        prep_ramp_steps = int(case_cfg.get("prep_ramp_steps", stage_cfg.get("prep_ramp_steps", 3000)))
        prep_segments = case_cfg.get("prep_segments", stage_cfg.get("prep_segments"))
        if prep_segments is not None:
            prep_total_steps = sum(int(seg["steps"]) for seg in prep_segments)
        else:
            prep_total_steps = prep_ramp_steps + prep_equil_steps
        prep_restart_every = int(case_cfg.get(
            "prep_restart_every",
            stage_cfg.get("prep_restart_every", self.cfg["io_policy"].get("restart_every", 10000)),
        ))
        prep_input = builder.make_prep_input_gpu_safe(
            meta,
            t_start_K=float(stage_cfg.get("prep_t_start_K", 50.0)),
            t_target_K=float(self.cfg["experiment"]["temperature_K"]),
            ramp_steps=prep_ramp_steps,
            equil_steps=prep_equil_steps,
            seed=int(case_cfg["deterministic_seed"]),
            thermo_every=int(self.cfg["io_policy"]["thermo_every"]["smoke"]),
            neighbor_policy=self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"],
            restart_every=prep_restart_every,
            restart_prefix=prep_case,
            segments=prep_segments,
            dump_every=case_cfg.get("prep_dump_every", stage_cfg.get("prep_dump_every")),
            dump_fields=case_cfg.get("prep_dump_fields", stage_cfg.get("prep_dump_fields")),
        )
        self._assert_prep_input_safe(prep_input, prep_case)
        self.assert_generated_input_safe(prep_input, prep_case)
        rec = self.execute_case(
            case_name=prep_case,
            stage=stage,
            atom_target=int(case_cfg["atom_target"]),
            eps_z=None,
            phase="prep",
            steps=prep_total_steps,
            input_text=prep_input,
            work_dir=prep_dir,
            structure_meta=meta,
            expected_outputs=["data.a1_baseline_equil"],
        )
        if not rec["success"]:
            raise GridStop(f"prep failed for {case_name}: {rec.get('failure_reasons')}")
        meta["baseline_data"] = str(baseline_data)
        write_json(prep_dir / "geometry_metadata.json", meta)
        self.write_stageb_geometry_summary(stage)
        return meta

    def stageb_structure_for_case(self, stage: str, case_cfg: Mapping[str, Any]) -> dict[str, Any]:
        meta = self.ensure_stageb_baseline(stage, case_cfg)
        eps_z = float(case_cfg["eps_z"])
        if abs(eps_z) < 1.0e-12:
            data_path = Path(meta["baseline_data"])
            center = meta["center_A"]
        else:
            out_dir = self.stageb_structure_dir(stage, str(case_cfg["case_id"]), eps_z)
            tag = paths.epsz_dirtag(eps_z)
            data_path = out_dir / f"data.ellipsoid_eigenstrain_{tag}"
            report_path = out_dir / f"ellipsoid_eigenstrain_{tag}_build_report.json"
            if not data_path.is_file():
                eigenstrain.regenerate(
                    Path(meta["baseline_data"]),
                    out_dir,
                    eps_z,
                    inclusion_id_min=int(meta["inclusion_id_min"]),
                    inclusion_id_max=int(meta["inclusion_id_max"]),
                    expected_inclusion_atoms=int(meta["inclusion_atoms"]),
                    center=tuple(float(x) for x in meta["center_A"]),
                )
            report = read_json(report_path, {})
            center = report.get("center_A", meta["center_A"])
        return {
            "data_path": data_path,
            "matrix_max_id": int(meta["matrix_max_id"]),
            "inclusion_id_min": int(meta["inclusion_id_min"]),
            "inclusion_id_max": int(meta["inclusion_id_max"]),
            "inclusion_atoms": int(meta["inclusion_atoms"]),
            "center_A": center,
            "inclusion_axes_A": meta["inclusion_axes_A"],
            "atom_count": int(meta["actual_atom_count"]),
            "stageB_case": str(case_cfg["case_id"]),
            "position": str(case_cfg["position"]),
            "predefect": str(case_cfg["predefect"]),
            "geometry_metadata": meta,
        }

    def assert_generated_input_safe(self, text: str, case_name: str) -> None:
        policy = self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"]
        if policy not in text:
            raise GridStop(f"input for {case_name} missing required neighbor workaround")
        forbidden = {
            "minimize": r"(?mi)^\s*minimize\b",
            "min_style": r"(?mi)^\s*min_style\b",
            "thermo 1": r"(?mi)^\s*thermo\s+1\s*$",
        }
        for label, pattern in forbidden.items():
            if re.search(pattern, text):
                raise GridStop(f"forbidden command {label!r} in generated input for {case_name}")
        for literal in ("CUDA_LAUNCH_BLOCKING", "compute-sanitizer"):
            if literal in text:
                raise GridStop(f"forbidden text {literal!r} in generated input for {case_name}")

    def run_stageb_lammps_case(
        self,
        stage: str,
        case_cfg: Mapping[str, Any],
        phase: str,
    ) -> dict[str, Any]:
        cid = self._stageb_runtime_case_id(case_cfg, phase)
        if self.state.case_success(cid) and self.force_rerun != cid:
            return self.state.case(cid) or {}
        structure = self.stageb_structure_for_case(stage, case_cfg)
        template = self.template_text_for_case(float(case_cfg["eps_z"]))
        work_dir = self.stageb_case_dir(stage, str(case_cfg["case_id"]), phase)
        input_text = self.input_for_phase(
            template_text=template,
            data_path=Path(structure["data_path"]),
            stage=stage,
            atom_target=int(case_cfg["atom_target"]),
            eps_z=float(case_cfg["eps_z"]),
            phase=phase,
            steps=int(self.cfg["stages"][stage][f"{phase}_steps"]),
            inclusion_id_min=int(structure["inclusion_id_min"]),
            inclusion_id_max=int(structure["inclusion_id_max"]),
            case_name=cid,
        )
        self.assert_generated_input_safe(input_text, cid)
        write_json(work_dir / "geometry_metadata.json", structure["geometry_metadata"])
        expected = []
        if self.cfg["io_policy"].get("write_final_data", True):
            expected.append(f"data.{cid}_final")
        if self.cfg["io_policy"].get("write_final_dump", True):
            expected.append(f"dump.{cid}_final.lammpstrj")
        if phase == "production" and self.production_reliability()["production_chunk_steps"] > 0:
            return self.run_production_case_chunked(
                cid=cid,
                stage=stage,
                atom_target=int(case_cfg["atom_target"]),
                eps_z=float(case_cfg["eps_z"]),
                steps=int(self.cfg["stages"][stage]["production_steps"]),
                base_input_text=input_text,
                work_dir=work_dir,
                structure_meta=structure,
                expected_final_outputs=expected,
            )
        return self.execute_case(
            case_name=cid,
            stage=stage,
            atom_target=int(case_cfg["atom_target"]),
            eps_z=float(case_cfg["eps_z"]),
            phase=phase,
            steps=int(self.cfg["stages"][stage][f"{phase}_steps"]),
            input_text=input_text,
            work_dir=work_dir,
            structure_meta=structure,
            expected_outputs=expected,
        )

    def structure_for_case(self, stage: str, atom_target: int, eps_z: float) -> dict[str, Any]:
        mode = self.cfg["stages"][stage]["structure_mode"]
        if mode == "existing_A0":
            return self.a0_structure(float(eps_z))
        if mode == "build_scaled_ellipsoid":
            return self.scaled_structure(stage, int(atom_target), float(eps_z))
        raise GridStop(f"unknown structure_mode for {stage}: {mode}")

    def template_text_for_case(self, eps_z: float) -> str:
        tag = eps_tag(float(eps_z))
        template = paths.a0_template_for_tag(tag)
        if not template.is_file():
            # Larger stages can still use the eps_0000 template with run-local data
            # when a new optional eps value has no dedicated tracked template.
            template = paths.a0_template_for_tag("0000")
        return template.read_text(encoding="utf-8", errors="replace")

    def execute_case(
        self,
        *,
        case_name: str,
        stage: str,
        atom_target: int,
        eps_z: float | None,
        phase: str,
        steps: int,
        input_text: str,
        work_dir: Path,
        structure_meta: dict[str, Any],
        expected_outputs: list[str],
    ) -> dict[str, Any]:
        existing = self.state.case(case_name)
        if existing and existing.get("success") and self.force_rerun != case_name:
            return existing

        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / f"in.{case_name}"
        log_path = work_dir / f"log.{case_name}.lammps"
        stdout_path = work_dir / "stdout.txt"
        stderr_path = work_dir / "stderr.txt"
        input_path.write_text(input_text, encoding="utf-8", newline="\n")
        cmd = self.lammps_cmd(input_path, log_path)
        (work_dir / "command.txt").write_text(command_text(cmd) + "\n", encoding="utf-8")

        if any("CUDA_LAUNCH_BLOCKING" in str(x) for x in cmd):
            raise GridStop(f"forbidden CUDA_LAUNCH_BLOCKING leaked into command for {case_name}")

        running = {
            "case_id": case_name,
            "status": "running",
            "success": False,
            "stage": stage,
            "atom_count": int(structure_meta.get("atom_count", atom_target)),
            "atom_target": int(atom_target),
            "eps_z": eps_z,
            "temperature_K": float(self.cfg["experiment"]["temperature_K"]),
            "mode": "kokkos_cuda_meam_neighbor_check_no" if phase != "prep" else "prep_kokkos_cuda_meam_neighbor_check_no",
            "phase": phase,
            "steps_target": int(steps),
            "input": str(input_path),
            "log": str(log_path),
            "command": cmd,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "structure": {k: str(v) if isinstance(v, Path) else v for k, v in structure_meta.items()},
            "gpu_snapshot_before": nvidia_smi_snapshot(),
        }
        self.state.mark_case(case_name, running)

        timeout_s = self.phase_timeout_s(stage, phase)
        disk_before = free_disk_gb(self.run_dir)
        start = time.time()
        with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as err:
            proc = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                stdout=out,
                stderr=err,
                env=self.child_env(),
                text=True,
            )
            exit_code, timed_out, hung, watchdog_events = self._wait_with_watchdog(
                proc, work_dir, timeout_s=timeout_s
            )
        duration_s = time.time() - start
        disk_after = free_disk_gb(self.run_dir)
        log = parse_log(log_path)
        outputs = self.collect_outputs(work_dir)
        error_markers = self.find_error_markers([log_path, stdout_path, stderr_path])
        final = log.get("final_thermo") or {}
        loop = log.get("loop") or {}
        # Prefer the cumulative thermo Step: multi-run inputs (prep settle+equil)
        # report only the last run's steps in the Loop line.
        steps_completed = int(final.get("Step") or loop.get("steps") or 0)
        atom_count = int(loop.get("atoms") or structure_meta.get("atom_count") or atom_target)
        rate = log.get("timesteps_per_s")
        failure_reasons = self.failure_reasons(
            exit_code=exit_code,
            timed_out=timed_out,
            hung=hung,
            log=log,
            error_markers=error_markers,
            expected_outputs=expected_outputs,
            output_names={o["name"] for o in outputs},
        )
        dangerous_status = "not_checked_check_no"
        if "check no" not in self.cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"]:
            dangerous_status = str(log.get("dangerous_builds", 0))
        record = {
            **running,
            "status": "success" if not failure_reasons else "failed",
            "success": not failure_reasons,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "hung": hung,
            "watchdog_events": watchdog_events,
            "timeout_s": timeout_s,
            "wall_time_s": round(duration_s, 3),
            "steps_completed": steps_completed,
            "timesteps_per_s": rate,
            "katom_step_per_s": round(atom_count * float(rate) / 1000.0, 3) if rate else None,
            "neighbor_builds": self.neighbor_builds(log_path),
            "dangerous_builds_status": dangerous_status,
            "final_temp": final.get("Temp"),
            "final_pe": final.get("PotEng") if "PotEng" in final else final.get("PE") if "PE" in final else final.get("Pe"),
            "final_ke": final.get("KinEng") if "KinEng" in final else final.get("KE") if "KE" in final else final.get("Ke"),
            "final_etotal": final.get("TotEng") if "TotEng" in final else final.get("E_total") if "E_total" in final else final.get("Etot"),
            "final_press": final.get("Press"),
            "log_summary": log,
            "outputs": outputs,
            "disk_free_before_gb": round(disk_before, 3),
            "disk_free_after_gb": round(disk_after, 3),
            "error_markers": error_markers,
            "failure_reasons": failure_reasons,
            "gpu_snapshot_after": nvidia_smi_snapshot(),
        }
        write_json(work_dir / "case_metadata.json", record)
        self.state.mark_case(case_name, record)
        self.write_runtime_tables()
        self.write_final_report()
        return record

    def kill_process_tree(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=60)
        else:
            try:
                os.kill(pid, 9)
            except OSError:
                pass

    def collect_outputs(self, work_dir: Path) -> list[dict[str, Any]]:
        rows = []
        for p in sorted(work_dir.iterdir()):
            if p.is_file() and not p.name.startswith(("stdout", "stderr")):
                rows.append({"name": p.name, "path": str(p), "size_bytes": p.stat().st_size})
        return rows

    def find_error_markers(self, files: list[Path]) -> dict[str, list[str]]:
        patterns = [str(x) for x in self.cfg["science_gates"]["stability_pass"].get("forbid_patterns", [])]
        if "cudaError" not in patterns:
            patterns.append("cudaError")
        if "illegal memory" not in patterns:
            patterns.append("illegal memory")
        found: dict[str, list[str]] = {p: [] for p in patterns}
        for file in files:
            if not file.is_file():
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                low = line.lower()
                for pat in patterns:
                    if pat.lower() in low:
                        found[pat].append(line.strip())
        return {k: v[:20] for k, v in found.items() if v}

    def failure_reasons(
        self,
        *,
        exit_code: int | None,
        timed_out: bool,
        log: dict[str, Any],
        error_markers: dict[str, list[str]],
        expected_outputs: list[str],
        output_names: set[str],
        hung: bool = False,
    ) -> list[str]:
        reasons = []
        if hung:
            reasons.append(
                "watchdog hang: process alive but no CPU/log/dump/restart progress within max_no_progress_minutes"
            )
        if timed_out:
            reasons.append("timed out")
        if exit_code != 0:
            reasons.append(f"nonzero exit code: {exit_code}")
        if not log.get("exists"):
            reasons.append("LAMMPS log missing")
        if log.get("has_error"):
            reasons.append("ERROR found in LAMMPS log")
        if log.get("nan_found"):
            reasons.append("nan found")
        if log.get("lost_atoms"):
            reasons.append("lost atoms found")
        if error_markers:
            reasons.append("forbidden error markers: " + ", ".join(error_markers))
        if not log.get("completed_normally"):
            reasons.append("no Total wall time line")
        for output in expected_outputs:
            if output not in output_names:
                reasons.append(f"expected output missing: {output}")
        return reasons

    def neighbor_builds(self, log_path: Path) -> int | None:
        if not log_path.is_file():
            return None
        text = log_path.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(r"Neighbor list builds\s*=\s*(\d+)", text)
        if matches:
            return int(matches[-1])
        matches = re.findall(r"Nbuild\s+(\d+)", text)
        return int(matches[-1]) if matches else None

    def run_lammps_case(self, stage: str, atom_target: int, eps_z: float, phase: str, steps: int) -> dict[str, Any]:
        cid = case_id(stage, atom_target, eps_z, phase)
        if self.state.case_success(cid) and self.force_rerun != cid:
            return self.state.case(cid) or {}
        structure = self.structure_for_case(stage, int(atom_target), float(eps_z))
        template = self.template_text_for_case(float(eps_z))
        case_dir = self.case_dir(stage, int(atom_target), float(eps_z), phase)
        input_text = self.input_for_phase(
            template_text=template,
            data_path=Path(structure["data_path"]),
            stage=stage,
            atom_target=int(atom_target),
            eps_z=float(eps_z),
            phase=phase,
            steps=int(steps),
            inclusion_id_min=int(structure["inclusion_id_min"]),
            inclusion_id_max=int(structure["inclusion_id_max"]),
            case_name=cid,
        )
        expected = []
        if self.cfg["io_policy"].get("write_final_data", True):
            expected.append(f"data.{cid}_final")
        if self.cfg["io_policy"].get("write_final_dump", True):
            expected.append(f"dump.{cid}_final.lammpstrj")
        if phase == "production" and self.production_reliability()["production_chunk_steps"] > 0:
            return self.run_production_case_chunked(
                cid=cid,
                stage=stage,
                atom_target=int(atom_target),
                eps_z=float(eps_z),
                steps=int(steps),
                base_input_text=input_text,
                work_dir=case_dir,
                structure_meta=structure,
                expected_final_outputs=expected,
            )
        return self.execute_case(
            case_name=cid,
            stage=stage,
            atom_target=int(atom_target),
            eps_z=float(eps_z),
            phase=phase,
            steps=int(steps),
            input_text=input_text,
            work_dir=case_dir,
            structure_meta=structure,
            expected_outputs=expected,
        )

    def _latest_restart_step(
        self, work_dir: Path, case_name: str, *, max_step: int | None = None, skip: set[int] | None = None
    ) -> int | None:
        best: int | None = None
        prefixes = (f"restart.{case_name}.", "restart.")
        patterns = (f"restart.{case_name}.*", "restart.*")
        for prefix, pattern in zip(prefixes, patterns):
            for p in work_dir.glob(pattern):
                suffix = p.name[len(prefix):]
                if not suffix.isdigit():
                    continue
                step = int(suffix)
                if max_step is not None and step > max_step:
                    continue
                if skip and step in skip:
                    continue
                try:
                    if p.stat().st_size <= 0:
                        continue
                except OSError:
                    continue
                if best is None or step > best:
                    best = step
        return best

    def _chunk_input_text(
        self,
        base_input_text: str,
        *,
        case_name: str,
        start_step: int,
        end_step: int,
        final_chunk: bool,
        chunk_tag: str,
    ) -> str:
        """Rewrite the monolithic case input into one chunk of the production run.

        For resume chunks the structure comes from read_restart (velocities, groups
        and fix nvt state restore from the restart file; MEAM pair_coeff must be
        re-specified and is kept). Trajectory dumps are per-chunk so an existing
        dump from an earlier attempt is never overwritten.
        """
        resume = start_step > 0
        restart_in = self.chunk_restart_name(start_step)
        traj_name = f"dump.{case_name}.lammpstrj"
        chunk_traj = self.chunk_dump_name(chunk_tag)
        final_data = f"data.{case_name}_final"
        final_dump = f"dump.{case_name}_final.lammpstrj"
        out: list[str] = [
            f"# Chunk {chunk_tag} ({start_step} -> {end_step}) of {case_name}: "
            + (f"resumes from {restart_in}" if resume else "fresh start from data file"),
        ]
        for raw in base_input_text.splitlines():
            stripped = raw.strip()
            if resume and re.match(r"^read_data\s+", stripped):
                out.append(f"read_restart    {restart_in}")
                continue
            if resume and stripped.startswith("velocity") and " create " in f" {stripped} ":
                out.append(f"# chunk resume: velocities restored from {restart_in}; dropped: {stripped}")
                continue
            if traj_name in raw:
                out.append(raw.replace(traj_name, chunk_traj))
                continue
            if re.match(r"^restart\s+\d+", stripped):
                parts = stripped.split()
                interval = parts[1] if len(parts) > 1 else str(end_step - start_step)
                out.append(f"restart         {interval} {self.chunk_restart_glob()}")
                continue
            if re.match(r"^run\s+\d+", stripped):
                if resume:
                    out.append(f"run             {int(end_step)} upto")
                else:
                    out.append(f"run             {int(end_step)}")
                out.append(f"write_restart   {self.chunk_restart_name(end_step)}")
                continue
            if re.match(r"^write_data\s+", stripped):
                if final_chunk:
                    out.append(raw.replace(final_data, self.chunk_final_data_name()))
                continue
            if re.match(r"^write_dump\s+", stripped):
                if final_chunk:
                    out.append(raw.replace(final_dump, self.chunk_final_dump_name()))
                continue
            out.append(raw)
        text = "\n".join(out).rstrip() + "\n"
        if (
            re.search(r"(?m)^\s*thermo\s+1\s*$", text)
            or "CUDA_LAUNCH_BLOCKING" in text
            or "compute-sanitizer" in text
        ):
            raise GridStop(f"forbidden debug setting leaked into chunk input for {case_name} {chunk_tag}")
        return text

    def execute_chunk(
        self,
        *,
        case_name: str,
        stage: str,
        work_dir: Path,
        chunk_tag: str,
        start_step: int,
        end_step: int,
        attempt: int,
        input_text: str,
        expected_outputs: list[str],
    ) -> dict[str, Any]:
        input_path = work_dir / self.chunk_input_name(chunk_tag)
        log_path = work_dir / self.chunk_log_name(chunk_tag)
        stdout_path = work_dir / f"stdout.{chunk_tag}.txt"
        stderr_path = work_dir / f"stderr.{chunk_tag}.txt"
        input_path.write_text(input_text, encoding="utf-8", newline="\n")
        cmd = self.lammps_cmd(input_path, log_path)
        (work_dir / f"command.{chunk_tag}.txt").write_text(command_text(cmd) + "\n", encoding="utf-8")
        if any("CUDA_LAUNCH_BLOCKING" in str(x) for x in cmd):
            raise GridStop(f"forbidden CUDA_LAUNCH_BLOCKING leaked into command for {case_name} {chunk_tag}")
        timeout_s = self.phase_timeout_s(stage, "production")
        started_at = datetime.now().isoformat(timespec="seconds")
        start = time.time()
        with stdout_path.open("w", encoding="utf-8", errors="replace") as out, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as err:
            proc = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                stdout=out,
                stderr=err,
                env=self.child_env(),
                text=True,
            )
            exit_code, timed_out, hung, watchdog_events = self._wait_with_watchdog(
                proc, work_dir, timeout_s=timeout_s
            )
        duration_s = time.time() - start
        log = parse_log(log_path)
        error_markers = self.find_error_markers([log_path, stdout_path, stderr_path])
        output_names = {o["name"] for o in self.collect_outputs(work_dir)}
        failure_reasons = self.failure_reasons(
            exit_code=exit_code,
            timed_out=timed_out,
            hung=hung,
            log=log,
            error_markers=error_markers,
            expected_outputs=expected_outputs,
            output_names=output_names,
        )
        final = log.get("final_thermo") or {}
        rate = log.get("timesteps_per_s")
        return {
            "chunk_tag": chunk_tag,
            "start_step": int(start_step),
            "end_step": int(end_step),
            "attempt": int(attempt),
            "status": "success" if not failure_reasons else ("hung" if hung else "failed"),
            "success": not failure_reasons,
            "hung": hung,
            "timed_out": timed_out,
            "exit_code": exit_code,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "wall_time_s": round(duration_s, 3),
            "steps_completed": int(final.get("Step") or 0),
            "timesteps_per_s": rate,
            "command": cmd,
            "input": str(input_path),
            "log": str(log_path),
            "restart_expected": self.chunk_restart_name(end_step),
            "restart_written": (work_dir / self.chunk_restart_name(end_step)).is_file(),
            "final_thermo": final,
            "failure_reasons": failure_reasons,
            "error_markers": error_markers,
            "watchdog_events": watchdog_events,
        }

    def _chunk_failed_on_restart_read(self, chunk: dict[str, Any], work_dir: Path) -> bool:
        texts: list[str] = []
        for candidate in (
            Path(chunk.get("log") or ""),
            work_dir / f"stdout.{chunk['chunk_tag']}.txt",
            work_dir / f"stderr.{chunk['chunk_tag']}.txt",
        ):
            if candidate.is_file():
                texts.append(candidate.read_text(encoding="utf-8", errors="replace"))
        joined = "\n".join(texts).lower()
        return "error" in joined and ("read_restart" in joined or "restart file" in joined)

    def run_production_case_chunked(
        self,
        *,
        cid: str,
        stage: str,
        atom_target: int,
        eps_z: float,
        steps: int,
        base_input_text: str,
        work_dir: Path,
        structure_meta: dict[str, Any],
        expected_final_outputs: list[str],
    ) -> dict[str, Any]:
        rel = self.production_reliability()
        chunk_steps = int(rel["production_chunk_steps"])
        retry_once = bool(rel["retry_hung_chunk_once"])
        resume_latest = bool(rel["resume_from_latest_restart"])

        previous = self.state.case(cid)
        bad_restarts: set[int] = set()
        current = 0
        resumed_from: int | None = None
        if resume_latest:
            latest = self._latest_restart_step(work_dir, cid, max_step=steps, skip=bad_restarts)
            if latest:
                current = latest
                resumed_from = latest

        record: dict[str, Any] = {
            "case_id": cid,
            "status": "running_chunked",
            "success": False,
            "stage": stage,
            "atom_count": int(structure_meta.get("atom_count", atom_target)),
            "atom_target": int(atom_target),
            "eps_z": float(eps_z),
            "temperature_K": float(self.cfg["experiment"]["temperature_K"]),
            "mode": "kokkos_cuda_meam_neighbor_check_no",
            "phase": "production",
            "chunked": True,
            "production_chunk_steps": chunk_steps,
            "steps_target": int(steps),
            "current_step": int(current),
            "resumed_from_restart_step": resumed_from,
            "input": str(work_dir / f"in.{cid}"),
            "log": str(work_dir / f"log.{cid}.lammps"),
            "command": None,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "structure": {k: str(v) if isinstance(v, Path) else v for k, v in structure_meta.items()},
            "gpu_snapshot_before": nvidia_smi_snapshot(),
            "chunks": [],
            "hang_events": [],
        }
        if previous:
            record["previous_attempt"] = {
                k: previous.get(k)
                for k in (
                    "status",
                    "chunked",
                    "exit_code",
                    "steps_completed",
                    "started_at",
                    "finished_at",
                    "timed_out",
                    "failure_reasons",
                )
            }
        self.state.mark_case(cid, record)
        self.write_hang_recovery_report()

        hang_counts: dict[int, int] = {}
        fallback_count = 0
        overall_start = time.time()
        while current < steps:
            end = min(current + chunk_steps, steps)
            final_chunk = end >= steps
            chunk_tag = f"chunk{current:07d}_{end:07d}"
            attempt = hang_counts.get(current, 0) + 1
            expected_final = []
            if final_chunk:
                for name in expected_final_outputs:
                    if name == f"data.{cid}_final":
                        expected_final.append(self.chunk_final_data_name())
                    elif name == f"dump.{cid}_final.lammpstrj":
                        expected_final.append(self.chunk_final_dump_name())
                    else:
                        expected_final.append(name)
            expected = [self.chunk_restart_name(end)] + expected_final
            input_text = self._chunk_input_text(
                base_input_text,
                case_name=cid,
                start_step=current,
                end_step=end,
                final_chunk=final_chunk,
                chunk_tag=chunk_tag,
            )
            chunk = self.execute_chunk(
                case_name=cid,
                stage=stage,
                work_dir=work_dir,
                chunk_tag=chunk_tag,
                start_step=current,
                end_step=end,
                attempt=attempt,
                input_text=input_text,
                expected_outputs=expected,
            )
            record["chunks"].append(chunk)
            record["input"] = chunk["input"]
            record["log"] = chunk["log"]
            record["command"] = chunk["command"]

            if chunk["success"]:
                current = end
                record["current_step"] = current
                self.state.mark_case(cid, record)
                self.write_hang_recovery_report()
                continue

            if chunk["hung"]:
                record["hang_events"].extend(chunk.get("watchdog_events", []))
                hang_counts[chunk["start_step"]] = hang_counts.get(chunk["start_step"], 0) + 1
                if retry_once and hang_counts[chunk["start_step"]] <= 1:
                    latest = self._latest_restart_step(work_dir, cid, max_step=steps, skip=bad_restarts)
                    retry_from = int(latest if latest is not None else 0)
                    record["hang_events"].append(
                        self._watchdog_event(
                            f"chunk {chunk_tag} hung (attempt {attempt}); killed process, resuming from "
                            f"latest restart step {retry_from} and retrying once"
                        )
                    )
                    current = retry_from
                    record["current_step"] = current
                    self.state.mark_case(cid, record)
                    self.write_hang_recovery_report()
                    continue
                record["hang_events"].append(
                    self._watchdog_event(f"chunk {chunk_tag} hung twice; case failed, escalation stopped")
                )
                return self._finish_chunked_case(
                    record,
                    work_dir=work_dir,
                    steps=steps,
                    overall_start=overall_start,
                    failure_reasons=[f"chunk {chunk_tag} hung twice; escalation stopped"],
                )

            if (
                chunk["start_step"] > 0
                and fallback_count < 2
                and self._chunk_failed_on_restart_read(chunk, work_dir)
            ):
                bad_restarts.add(chunk["start_step"])
                fallback_count += 1
                older = self._latest_restart_step(work_dir, cid, max_step=steps, skip=bad_restarts)
                if older is None:
                    return self._finish_chunked_case(
                        record,
                        work_dir=work_dir,
                        steps=steps,
                        overall_start=overall_start,
                        failure_reasons=[
                            f"restart.{cid}.{chunk['start_step']} unreadable and no older restart available"
                        ],
                    )
                record["hang_events"].append(
                    self._watchdog_event(
                        f"restart.{cid}.{chunk['start_step']} failed to read; falling back to restart step {older}"
                    )
                )
                current = int(older)
                record["current_step"] = current
                self.state.mark_case(cid, record)
                continue

            return self._finish_chunked_case(
                record,
                work_dir=work_dir,
                steps=steps,
                overall_start=overall_start,
                failure_reasons=[f"chunk {chunk_tag} failed: {chunk['failure_reasons']}"],
            )

        return self._finish_chunked_case(
            record, work_dir=work_dir, steps=steps, overall_start=overall_start, failure_reasons=[]
        )

    def _finish_chunked_case(
        self,
        record: dict[str, Any],
        *,
        work_dir: Path,
        steps: int,
        overall_start: float,
        failure_reasons: list[str],
    ) -> dict[str, Any]:
        chunks = record.get("chunks") or []
        ok_chunks = [c for c in chunks if c.get("success")]
        success = not failure_reasons and int(record.get("current_step") or 0) >= int(steps)
        last_log_path: Path | None = None
        if ok_chunks:
            last_log_path = Path(ok_chunks[-1]["log"])
        elif chunks:
            last_log_path = Path(chunks[-1]["log"])
        log = parse_log(last_log_path) if last_log_path else {"exists": False}
        weighted = [
            (float(c["timesteps_per_s"]), int(c["end_step"]) - int(c["start_step"]))
            for c in ok_chunks
            if c.get("timesteps_per_s")
        ]
        steps_rated = sum(w for _, w in weighted)
        rate = round(sum(r * w for r, w in weighted) / steps_rated, 3) if steps_rated else None
        atom_count = int(record.get("atom_count") or 0)
        final = log.get("final_thermo") or {}
        record.update(
            {
                "status": "success" if success else "failed",
                "success": success,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "exit_code": 0 if success else (chunks[-1].get("exit_code") if chunks else None),
                "timed_out": any(c.get("timed_out") for c in chunks),
                "hung": any(c.get("hung") for c in chunks),
                "timeout_s": self.phase_timeout_s(record["stage"], "production"),
                "wall_time_s": round(time.time() - overall_start, 3),
                "chunk_wall_time_s": round(sum(float(c.get("wall_time_s") or 0) for c in chunks), 3),
                "steps_completed": int(record.get("current_step") or 0),
                "timesteps_per_s": rate,
                "katom_step_per_s": round(atom_count * rate / 1000.0, 3) if rate else None,
                "neighbor_builds": self.neighbor_builds(last_log_path) if last_log_path else None,
                "dangerous_builds_status": "not_checked_check_no",
                "final_temp": final.get("Temp"),
                "final_pe": final.get("PotEng"),
                "final_ke": final.get("KinEng"),
                "final_etotal": final.get("TotEng"),
                "final_press": final.get("Press"),
                "log_summary": log,
                "outputs": self.collect_outputs(work_dir),
                "failure_reasons": failure_reasons,
                "error_markers": chunks[-1].get("error_markers", {}) if chunks else {},
                "gpu_snapshot_after": nvidia_smi_snapshot(),
            }
        )
        write_json(work_dir / "case_metadata.json", record)
        self.state.mark_case(record["case_id"], record)
        self.write_runtime_tables()
        self.write_final_report()
        self.write_hang_recovery_report()
        return record

    def write_hang_recovery_report(self) -> None:
        rel = self.production_reliability()
        rows = [
            r
            for r in self.state.data.get("cases", {}).values()
            if r.get("chunked") or r.get("hang_events") or r.get("hung") or r.get("previous_attempt")
        ]
        lines = [
            "# Hang recovery report",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run root: `{self.run_dir}`",
            "",
            "Watchdog policy: a production chunk is declared hung when the LAMMPS process is alive but",
            f"CPU time and log/dump/restart files all stop changing for {rel['max_no_progress_minutes']:.0f} minutes.",
            "A hung chunk is killed, the case resumes from the latest valid restart, and the chunk is retried once.",
            "If the same chunk hangs twice the case is marked failed and escalation stops.",
            f"Production runs in chunks of {rel['production_chunk_steps']} steps with write_restart + state.json",
            "update + log verification (ERROR/nan/lost atoms/cudaError) after every chunk.",
            "",
        ]
        if not rows:
            lines.append("No chunked production cases or hang events recorded yet.")
        for rec in rows:
            lines += [
                f"## {rec.get('case_id')}",
                "",
                f"- status: `{rec.get('status')}` (success={rec.get('success')})",
                f"- current_step: {rec.get('current_step', rec.get('steps_completed'))}/{rec.get('steps_target')}",
                f"- resumed_from_restart_step: {rec.get('resumed_from_restart_step')}",
            ]
            prev = rec.get("previous_attempt")
            if prev:
                lines.append(
                    f"- previous attempt: status=`{prev.get('status')}` chunked={prev.get('chunked')} "
                    f"exit_code={prev.get('exit_code')} steps_completed={prev.get('steps_completed')} "
                    f"failure_reasons={prev.get('failure_reasons')}"
                )
            chunks = rec.get("chunks") or []
            if chunks:
                lines += [
                    "",
                    "| chunk | attempt | status | exit | steps | wall_s | t/s | restart_written |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- |",
                ]
                for c in chunks:
                    lines.append(
                        f"| {c.get('chunk_tag')} | {c.get('attempt')} | {c.get('status')} | {c.get('exit_code')} | "
                        f"{c.get('steps_completed')} | {c.get('wall_time_s')} | {c.get('timesteps_per_s')} | "
                        f"{c.get('restart_written')} |"
                    )
            events = list(rec.get("hang_events") or [])
            for c in chunks:
                for e in c.get("watchdog_events") or []:
                    if e not in events:
                        events.append(e)
            lines += ["", "### Watchdog / recovery events", ""]
            lines += [f"- {e}" for e in events] if events else ["- none"]
            lines.append("")
        (self.run_dir / "hang_recovery_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_stage(self, stage_name: str) -> bool:
        if stage_name not in self.cfg["stages"]:
            raise GridStop(f"unknown stage: {stage_name}")
        stage = self.cfg["stages"][stage_name]
        if not stage.get("enabled", False):
            self.state.mark_stage(stage_name, {"status": "disabled"})
            return True
        disk_ok, disk_msg = self.check_disk_for_stage(stage_name)
        if not disk_ok and self.cfg["resources"].get("stop_if_disk_below_threshold", True):
            self.write_gate_report(stage_name, "blocked", [disk_msg])
            self.state.stop(disk_msg)
            return False

        if stage_name != "A0_24k" and not self.previous_stage_stable(stage_name):
            msg = f"{stage_name} blocked because previous stage is not stable"
            self.write_gate_report(stage_name, "blocked", [msg])
            self.state.stop(msg)
            return False
        if stage_name == "A2_large" and self.cfg["stages"][stage_name].get("manual_override_required_if_no_signal_at_300k"):
            if not self.stage_has_science_signal("A1_medium"):
                msg = "A2_large requires manual review because A1_medium has no recorded science signal"
                self.write_gate_report(stage_name, "requires_manual_review", [msg])
                self.state.stop(msg)
                return False

        mode = stage["structure_mode"]
        if mode == "existing_A0":
            ok = self.run_existing_a0_stage(stage_name, stage)
        elif mode == "build_scaled_ellipsoid":
            ok = self.run_scaled_stage(stage_name, stage)
        elif mode == STAGEB_REALISM_MODE:
            ok = self.run_stageb_realism_stage(stage_name, stage)
        else:
            raise GridStop(f"unsupported structure_mode for {stage_name}: {mode}")

        self.write_stage_report(stage_name)
        self.write_final_report()
        return ok

    def run_stageb_realism_stage(self, stage_name: str, stage: dict[str, Any]) -> bool:
        cases = self.stageb_cases(stage_name)
        failures: list[str] = []
        selected_production: list[str] = []
        target_label = str(max(int(case["atom_target"]) for case in cases)) if cases else "unknown"
        try:
            for case in cases:
                self.ensure_stageb_geometry(stage_name, case)
            self.write_stageb_geometry_summary(stage_name)

            for case in cases:
                rec = self.run_stageb_lammps_case(stage_name, case, "smoke")
                if not rec.get("success"):
                    failures.append(f"{case['case_id']}: smoke failed {rec.get('failure_reasons')}")
            self.write_stageb_phase_summary(stage_name, "smoke")
            if failures:
                self.state.mark_stage(stage_name, {"status": "failed_smoke", "failures": failures})
                self.write_gate_report(stage_name, "blocked", failures)
                return False

            if self.smoke_only:
                self.state.mark_stage(
                    stage_name,
                    {
                        "status": "success_smoke_only",
                        "selected_target": target_label,
                        "smoke_case_ids": [case["case_id"] for case in cases],
                    },
                )
                self.write_gate_report(
                    stage_name,
                    "requires_manual_review",
                    ["smoke-only run completed; production not launched in this invocation"],
                )
                return True

            if not (stage.get("run_production_after_smoke_pass", False) or stage.get("run_production_after_gate_pass", False)):
                self.state.mark_stage(stage_name, {"status": "success_smoke_only", "selected_target": target_label})
                self.write_gate_report(stage_name, "requires_manual_review", ["smoke passed; production disabled in config"])
                return True

            prod_ids = list(stage.get("production_case_ids") or [case["case_id"] for case in cases])
            max_prod = int(stage.get("max_production_cases", 6))
            prod_ids = prod_ids[:max_prod]
            case_by_id = {case["case_id"]: case for case in cases}
            for cid in prod_ids:
                selected_production.append(str(cid))
                rec = self.run_stageb_lammps_case(stage_name, case_by_id[cid], "production")
                if not rec.get("success"):
                    failures.append(f"{cid}: production failed {rec.get('failure_reasons')}")
                    break
                if stage.get("analyze_after_production", False):
                    self.analyze_case(rec)
                self.write_stageb_phase_summary(stage_name, "production")
            self.write_stageb_phase_summary(stage_name, "production")
        except Exception as exc:
            failures.append(str(exc))

        if failures:
            self.state.mark_stage(
                stage_name,
                {
                    "status": "failed_production" if selected_production else "failed",
                    "selected_target": target_label,
                    "production_case_ids": selected_production,
                    "failures": failures,
                },
            )
            self.write_gate_report(stage_name, "blocked", failures)
            return False

        self.state.mark_stage(
            stage_name,
            {
                "status": "success",
                "selected_target": target_label,
                "smoke_case_ids": [case["case_id"] for case in cases],
                "production_case_ids": selected_production,
                "failures": [],
            },
        )
        self.write_gate_report(
            stage_name,
            "requires_manual_review",
            [
                "B3 realism 100k sprint completed; review defect_summary/gate logic before any larger confirmation",
                "250k/500k/700k remain disabled and require explicit user approval",
            ],
        )
        return True

    def run_existing_a0_stage(self, stage_name: str, stage: dict[str, Any]) -> bool:
        target = int(stage["atom_targets"][0])
        eps_values = [float(x) for x in stage["eps_z"]]
        smoke_ok = True
        if stage.get("run_smoke", False):
            for eps in eps_values:
                rec = self.run_lammps_case(stage_name, target, eps, "smoke", int(stage["smoke_steps"]))
                smoke_ok = smoke_ok and bool(rec.get("success"))
        if not smoke_ok:
            self.state.mark_stage(stage_name, {"status": "failed_smoke"})
            return False
        if stage.get("run_short", False):
            for eps in eps_values:
                rec = self.run_lammps_case(stage_name, target, eps, "short", int(stage["short_steps"]))
                if not rec.get("success"):
                    self.state.mark_stage(stage_name, {"status": "failed_short"})
                    return False
        if stage.get("run_production_after_smoke_pass", False):
            for eps in eps_values:
                rec = self.run_lammps_case(stage_name, target, eps, "production", int(stage["production_steps"]))
                if not rec.get("success"):
                    self.state.mark_stage(stage_name, {"status": "failed_production"})
                    return False
                if stage.get("analyze_after_production", False):
                    self.analyze_case(rec)
        self.state.mark_stage(stage_name, {"status": "success", "selected_target": target})
        return True

    def run_scaled_stage(self, stage_name: str, stage: dict[str, Any]) -> bool:
        selected_target: int | None = None
        failures: list[str] = []
        primary_eps = [float(x) for x in stage["eps_z"]]
        optional_eps = [float(x) for x in stage.get("optional_eps_after_stable", stage.get("overload_eps_only_if_previous_signal", []))]
        for target in [int(x) for x in stage["atom_targets"]]:
            try:
                self.ensure_scaled_baseline(stage_name, target)
                if not self.run_phase_group(stage_name, stage, target, primary_eps, "smoke"):
                    failures.append(f"target {target}: smoke failed")
                    continue
                if stage.get("run_short_after_smoke_pass", False):
                    if not self.run_phase_group(stage_name, stage, target, primary_eps, "short"):
                        failures.append(f"target {target}: short failed")
                        continue
                if stage.get("gate_required_before_each_production", False):
                    gate = self.write_gate_report(stage_name, "approved_to_escalate", [f"target {target} smoke/short passed"])
                    if gate["decision"] != "approved_to_escalate":
                        self.state.mark_stage(stage_name, {"status": gate["decision"], "selected_target": target})
                        return False
                if stage.get("run_production_after_short_pass", False) or stage.get("run_production_after_gate_pass", False):
                    if not self.run_phase_group(stage_name, stage, target, primary_eps, "production"):
                        failures.append(f"target {target}: production failed")
                        continue
                    for rec in self.production_records(stage_name, target):
                        if stage.get("analyze_after_production", False):
                            self.analyze_case(rec)
                if optional_eps and self.stage_has_science_signal(stage_name):
                    self.run_phase_group(stage_name, stage, target, optional_eps, "smoke")
                    if stage.get("run_short_after_smoke_pass", False):
                        self.run_phase_group(stage_name, stage, target, optional_eps, "short")
                    if stage.get("run_production_after_short_pass", False) or stage.get("run_production_after_gate_pass", False):
                        self.run_phase_group(stage_name, stage, target, optional_eps, "production")
                selected_target = target
                break
            except Exception as exc:
                failures.append(f"target {target}: {exc}")
                if "cuda" in str(exc).lower() and self.cfg["resources"].get("stop_if_gpu_memory_error", True):
                    break
        if selected_target is None:
            self.state.mark_stage(stage_name, {"status": "failed", "failures": failures})
            self.write_gate_report(stage_name, "blocked", failures)
            return False
        self.state.mark_stage(stage_name, {"status": "success", "selected_target": selected_target, "failures": failures})
        return True

    def run_phase_group(self, stage: str, stage_cfg: dict[str, Any], target: int, eps_values: list[float], phase: str) -> bool:
        steps = int(stage_cfg[f"{phase}_steps"])
        ok = True
        for eps in eps_values:
            rec = self.run_lammps_case(stage, target, eps, phase, steps)
            ok = ok and bool(rec.get("success"))
            if not rec.get("success"):
                return False
        return ok

    def stage_order(self) -> list[str]:
        return [name for name, stage in self.cfg["stages"].items() if stage.get("enabled", False)]

    def previous_stage_stable(self, stage: str) -> bool:
        order = self.stage_order()
        idx = order.index(stage)
        if idx == 0:
            return True
        prev = order[idx - 1]
        return self.state.data.get("stages", {}).get(prev, {}).get("status") == "success"

    def autopilot(self) -> bool:
        for stage_name in self.stage_order():
            already = self.state.data.get("stages", {}).get(stage_name, {})
            if already.get("status") == "success" and not self.force_rerun:
                continue
            ok = self.run_stage(stage_name)
            if not ok:
                self.write_final_report()
                return False
        self.write_gate_report("A2_large", "approved_to_escalate", ["all configured stages completed"], allow_missing=True)
        self.write_final_report()
        return True

    def force_rerun_case(self, cid: str) -> bool:
        rec = self.state.case(cid)
        if not rec:
            raise GridStop(f"case not found in state: {cid}")
        phase = rec["phase"]
        if phase == "prep":
            stage = rec["stage"]
            target = int(rec["atom_target"])
            self.force_rerun = cid
            self.ensure_scaled_baseline(stage, target)
            return bool(self.state.case(cid).get("success"))
        self.force_rerun = cid
        rec2 = self.run_lammps_case(
            rec["stage"],
            int(rec["atom_target"]),
            float(rec["eps_z"]),
            phase,
            int(rec["steps_target"]),
        )
        return bool(rec2.get("success"))

    def analyze_only(self) -> bool:
        ok = True
        for rec in list(self.state.data.get("cases", {}).values()):
            if rec.get("phase") == "production" and rec.get("success"):
                ok = self.analyze_case(rec) and ok
        self.write_defect_summary()
        self.write_final_report()
        return ok

    def production_records(self, stage: str, target: int | None = None) -> list[dict[str, Any]]:
        rows = []
        for rec in self.state.data.get("cases", {}).values():
            if rec.get("stage") != stage or rec.get("phase") != "production" or not rec.get("success"):
                continue
            if target is not None and int(rec.get("atom_target")) != int(target):
                continue
            rows.append(rec)
        return rows

    def stageb_records(self, stage: str, phase: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for rec in self.state.data.get("cases", {}).values():
            if rec.get("stage") != stage:
                continue
            if phase is not None and rec.get("phase") != phase:
                continue
            if not rec.get("structure", {}).get("stageB_case"):
                continue
            rows.append(rec)
        return sorted(rows, key=lambda r: str(r.get("case_id", "")))

    def write_stageb_geometry_summary(self, stage: str) -> None:
        headers = [
            "case_id",
            "position",
            "predefect",
            "eps_z",
            "atom_target",
            "actual_atom_count",
            "matrix_atoms",
            "inclusion_atoms",
            "safe_basic",
            "min_pair_distance_A",
            "pairs_below_1p8_A",
            "cross_source_pairs_below_2p1_A",
            "boundary_plane",
            "boundary_location",
            "inclusion_distance_to_boundary",
            "vacancy_count_actual",
            "no_inclusion_atoms_deleted",
            "geometry_metadata",
        ]
        rows = []
        for case in self.stageb_cases(stage):
            meta_path = self.stageb_structure_dir(stage, str(case["case_id"])) / "geometry_metadata.json"
            if not meta_path.is_file():
                continue
            meta = read_json(meta_path, {})
            boundary = meta.get("boundary") or {}
            vacancy = meta.get("vacancy") or {}
            rows.append({
                "case_id": case["case_id"],
                "position": case["position"],
                "predefect": case["predefect"],
                "eps_z": case["eps_z"],
                "atom_target": case["atom_target"],
                "actual_atom_count": meta.get("actual_atom_count"),
                "matrix_atoms": meta.get("matrix_atoms"),
                "inclusion_atoms": meta.get("inclusion_atoms"),
                "safe_basic": meta.get("safe_basic"),
                "min_pair_distance_A": meta.get("min_pair_distance_A"),
                "pairs_below_1p8_A": meta.get("pairs_below_1p8_A"),
                "cross_source_pairs_below_2p1_A": meta.get("cross_source_pairs_below_2p1_A"),
                "boundary_plane": boundary.get("boundary_plane"),
                "boundary_location": boundary.get("boundary_location"),
                "inclusion_distance_to_boundary": boundary.get("inclusion_distance_to_boundary"),
                "vacancy_count_actual": vacancy.get("vacancy_count_actual"),
                "no_inclusion_atoms_deleted": meta.get("no_inclusion_atoms_deleted"),
                "geometry_metadata": str(meta_path),
            })
        self.write_csv(self.run_dir / "geometry_summary.csv", headers, rows)
        self.write_csv(self.tables_dir / "geometry_summary.csv", headers, rows)

    def write_stageb_phase_summary(self, stage: str, phase: str) -> None:
        headers = [
            "case_id",
            "stageB_case",
            "position",
            "predefect",
            "eps_z",
            "phase",
            "steps_target",
            "steps_completed",
            "exit_code",
            "success",
            "wall_time_s",
            "timesteps_per_s",
            "final_temp",
            "final_press",
            "failure_reasons",
            "log",
        ]
        rows = []
        for rec in self.stageb_records(stage, phase):
            st = rec.get("structure") or {}
            rows.append({
                "case_id": rec.get("case_id"),
                "stageB_case": st.get("stageB_case"),
                "position": st.get("position"),
                "predefect": st.get("predefect"),
                "eps_z": rec.get("eps_z"),
                "phase": rec.get("phase"),
                "steps_target": rec.get("steps_target"),
                "steps_completed": rec.get("steps_completed"),
                "exit_code": rec.get("exit_code"),
                "success": rec.get("success"),
                "wall_time_s": rec.get("wall_time_s"),
                "timesteps_per_s": rec.get("timesteps_per_s"),
                "final_temp": rec.get("final_temp"),
                "final_press": rec.get("final_press"),
                "failure_reasons": rec.get("failure_reasons"),
                "log": rec.get("log"),
            })
        filename = "smoke_summary.csv" if phase == "smoke" else f"{phase}_summary.csv"
        self.write_csv(self.run_dir / filename, headers, rows)
        self.write_csv(self.tables_dir / filename, headers, rows)

    def analyze_case(self, rec: dict[str, Any]) -> bool:
        if not self.cfg.get("analysis", {}).get("enabled", False):
            return True
        final_dump = None
        final_dump_names = {f"dump.{rec['case_id']}_final.lammpstrj", self.chunk_final_dump_name()}
        for output in rec.get("outputs", []):
            if output["name"] in final_dump_names:
                final_dump = Path(output["path"])
                break
        if final_dump is None or not final_dump.is_file():
            return False
        out_path = Path(rec["input"]).parent / "analysis.json"
        structure = rec.get("structure", {})
        center = structure.get("center_A")
        axes = structure.get("inclusion_axes_A")
        try:
            result = analyze_dump(
                str(final_dump),
                int(structure["matrix_max_id"]),
                center=tuple(float(x) for x in center) if center else None,
                inclusion_axes=tuple(float(x) for x in axes) if axes else None,
            )
            result.update(
                {
                    "case": rec["case_id"],
                    "stage": rec["stage"],
                    "atom_target": rec["atom_target"],
                    "eps_z": rec["eps_z"],
                }
            )
            write_json(out_path, result)
            rec["analysis"] = str(out_path)
            rec["science_signal"] = self.analysis_has_signal(result)
            self.state.mark_case(rec["case_id"], rec)
            self.write_defect_summary()
            return True
        except Exception as exc:
            rec["analysis_error"] = str(exc)
            rec["science_signal"] = False
            self.state.mark_case(rec["case_id"], rec)
            return False

    @staticmethod
    def _analysis_pct(result: dict[str, Any], pct_key: str, fraction_key: str) -> float | None:
        if pct_key in result:
            return float(result.get(pct_key) or 0.0)
        if fraction_key in result:
            return 100.0 * float(result.get(fraction_key) or 0.0)
        return None

    @staticmethod
    def analysis_signal_reasons(result: dict[str, Any]) -> list[str]:
        """Return robust science-signal reasons for a production analysis.

        Tiny matrix defects just outside the interface shell are boundary noise.
        A1_custom_100k has exactly this pattern: no dislocations, no HCP beyond
        the 1.3 shell, and only three OTHER atoms at normalized distance ~1.31.
        """
        reasons: list[str] = []

        if int(result.get("dislocation_segments", 0) or 0) > 0:
            reasons.append("dislocation_segments_gt_0")
        if float(result.get("dislocation_length_A", 0.0) or 0.0) > 0.0:
            reasons.append("dislocation_length_gt_0")
        if float(result.get("dislocation_density_per_m2", 0.0) or 0.0) > 0.0:
            reasons.append("dislocation_density_gt_0")

        hcp_pct = GpuGridRunner._analysis_pct(result, "hcp_pct", "hcp_fraction")
        baseline_hcp_pct = GpuGridRunner._analysis_pct(
            result, "baseline_hcp_pct", "baseline_hcp_fraction")
        if (
            hcp_pct is not None
            and baseline_hcp_pct is not None
            and (hcp_pct - baseline_hcp_pct) > HCP_PCT_SIGNAL_DELTA
        ):
            reasons.append("hcp_pct_growth_vs_baseline")

        other_pct = GpuGridRunner._analysis_pct(result, "other_pct", "other_fraction")
        baseline_other_pct = GpuGridRunner._analysis_pct(
            result, "baseline_other_pct", "baseline_other_fraction")
        if (
            other_pct is not None
            and baseline_other_pct is not None
            and (other_pct - baseline_other_pct) > OTHER_PCT_SIGNAL_DELTA
        ):
            reasons.append("other_pct_growth_vs_baseline")

        pz = result.get("plastic_zone") or {}
        hcp_beyond = int(pz.get("hcp_atoms_beyond_1p3_shell", 0) or 0)
        if hcp_beyond >= HCP_ATOMS_BEYOND_SHELL_SIGNAL_MIN:
            reasons.append("hcp_atoms_beyond_shell")

        defect_beyond = int(pz.get("defect_atoms_beyond_1p3_shell", 0) or 0)
        max_distance = pz.get("max_normalized_ellipsoid_distance")
        if (
            defect_beyond > DEFECT_ATOMS_BOUNDARY_NOISE_MAX
            and max_distance is not None
            and float(max_distance) >= PLASTIC_ZONE_DISTANCE_SIGNAL_MIN
        ):
            reasons.append("plastic_zone_defects_beyond_noise")

        if bool(result.get("plastic_zone_detected")):
            reasons.append("plastic_zone_detected")

        return reasons

    def analysis_has_signal(self, result: dict[str, Any]) -> bool:
        return bool(GpuGridRunner.analysis_signal_reasons(result))

    def stage_has_science_signal(self, stage: str) -> bool:
        for rec in self.production_records(stage):
            analysis_path = rec.get("analysis")
            if analysis_path and Path(analysis_path).is_file():
                if self.analysis_has_signal(read_json(Path(analysis_path), {})):
                    return True
                continue
            if rec.get("science_signal"):
                return True
        return False

    def write_runtime_tables(self) -> None:
        headers = [
            "case_id",
            "stage",
            "atom_count",
            "eps_z",
            "phase",
            "steps_target",
            "steps_completed",
            "exit_code",
            "success",
            "wall_time_s",
            "timesteps_per_s",
            "katom_step_per_s",
            "neighbor_builds",
            "dangerous_builds_status",
            "final_temp",
            "final_pe",
            "final_ke",
            "final_etotal",
            "final_press",
            "disk_free_after_gb",
        ]
        rows = sorted(self.state.data.get("cases", {}).values(), key=lambda r: r.get("started_at") or "")
        self.write_csv(self.tables_dir / "runtime_summary.csv", headers, rows)
        for stage in self.stage_order():
            self.write_csv(
                self.tables_dir / f"{stage}_summary.csv",
                headers,
                [r for r in rows if r.get("stage") == stage],
            )

    def write_defect_summary(self) -> None:
        headers = [
            "case",
            "stage",
            "atom_target",
            "eps_z",
            "matrix_atoms",
            "fcc_pct",
            "hcp_pct",
            "other_pct",
            "dislocation_segments",
            "dislocation_length_A",
            "dislocation_density_per_m2",
            "defect_atoms_beyond_1p3_shell",
            "science_signal",
            "dump",
        ]
        rows = []
        for rec in self.state.data.get("cases", {}).values():
            analysis_path = rec.get("analysis")
            if not analysis_path or not Path(analysis_path).is_file():
                continue
            data = read_json(Path(analysis_path), {})
            pz = data.get("plastic_zone") or {}
            rows.append(
                {
                    "case": rec["case_id"],
                    "stage": rec["stage"],
                    "atom_target": rec["atom_target"],
                    "eps_z": rec["eps_z"],
                    "matrix_atoms": data.get("matrix_atoms"),
                    "fcc_pct": data.get("fcc_pct"),
                    "hcp_pct": data.get("hcp_pct"),
                    "other_pct": data.get("other_pct"),
                    "dislocation_segments": data.get("dislocation_segments"),
                    "dislocation_length_A": data.get("dislocation_length_A"),
                    "dislocation_density_per_m2": data.get("dislocation_density_per_m2"),
                    "defect_atoms_beyond_1p3_shell": pz.get("defect_atoms_beyond_1p3_shell"),
                    "science_signal": self.analysis_has_signal(data),
                    "dump": data.get("dump"),
                }
            )
        self.write_csv(self.tables_dir / "defect_summary.csv", headers, rows)

    def write_csv(self, path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def write_stage_report(self, stage: str) -> None:
        cases = [r for r in self.state.data.get("cases", {}).values() if r.get("stage") == stage]
        lines = [
            f"# {stage} report",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Stage state: `{self.state.data.get('stages', {}).get(stage, {}).get('status', 'unknown')}`",
            f"Cases completed: {sum(1 for r in cases if r.get('success'))}/{len(cases)}",
            "",
            "| case | phase | eps_z | atoms | exit | success | steps | t/s | wall_s |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for rec in cases:
            lines.append(
                f"| {rec.get('case_id')} | {rec.get('phase')} | {rec.get('eps_z')} | "
                f"{rec.get('atom_count')} | {rec.get('exit_code')} | {rec.get('success')} | "
                f"{rec.get('steps_completed')}/{rec.get('steps_target')} | "
                f"{rec.get('timesteps_per_s')} | {rec.get('wall_time_s')} |"
            )
        lines += [
            "",
            "Neighbor workaround: `neigh_modify    delay 0 every 10 check no`.",
            "Dangerous builds are not checked with `check no`; this risk is reported explicitly.",
        ]
        (self.summaries_dir / f"{stage}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_gate_report(self, stage: str, decision: str, reasons: list[str], allow_missing: bool = False) -> dict[str, Any]:
        cases = [r for r in self.state.data.get("cases", {}).values() if r.get("stage") == stage]
        if not cases and not allow_missing:
            reasons = reasons + ["no cases recorded for this stage yet"]
        rec = {
            "stage": stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": decision,
            "approved_to_escalate": decision == "approved_to_escalate",
            "blocked": decision == "blocked",
            "requires_manual_review": decision == "requires_manual_review",
            "reasons": reasons,
            "completed_cases": [r.get("case_id") for r in cases if r.get("success")],
            "failures": {r.get("case_id"): r.get("failure_reasons") for r in cases if not r.get("success")},
            "nvidia_smi": nvidia_smi_snapshot(),
            "disk_free_gb": round(free_disk_gb(self.run_dir), 2),
            "science_signal": self.stage_has_science_signal(stage),
        }
        self.state.mark_gate(stage, rec)
        lines = [
            f"# {stage} gate report",
            "",
            f"Generated: {rec['generated_at']}",
            "",
            f"decision: `{decision}`",
            f"approved_to_escalate: `{rec['approved_to_escalate']}`",
            f"blocked: `{rec['blocked']}`",
            f"requires_manual_review: `{rec['requires_manual_review']}`",
            f"science_signal: `{rec['science_signal']}`",
            f"disk_free_gb: `{rec['disk_free_gb']}`",
            "",
            "## Reasons",
            "",
        ]
        lines += [f"- {r}" for r in reasons] if reasons else ["- none"]
        lines += [
            "",
            "## Completed Cases",
            "",
        ]
        lines += [f"- {c}" for c in rec["completed_cases"]] if rec["completed_cases"] else ["- none"]
        lines += ["", "## Failures", ""]
        if rec["failures"]:
            for cid, failures in rec["failures"].items():
                lines.append(f"- {cid}: {failures}")
        else:
            lines.append("- none")
        lines += ["", "## VRAM Notes", "", f"```json\n{json.dumps(rec['nvidia_smi'], indent=2)}\n```"]
        (self.summaries_dir / f"{stage}_gate_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return rec

    def write_final_report(self) -> None:
        stages = self.state.data.get("stages", {})
        cases = self.state.data.get("cases", {})
        lines = [
            "# GPU grid sweep final report",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Run root: `{self.run_dir}`",
            "",
            "## Git Status",
            "",
            "```text",
            short_git_status(),
            "```",
            "",
            "## Changed Files",
            "",
        ]
        changed = git_changed_files()
        lines += [f"- `{x}`" for x in changed] if changed else ["- none"]
        gp = self.cfg["gpu_profile"]
        lines += [
            "",
            "## Config-Driven Proof",
            "",
            "- Sweep stages, atom targets, eps values, steps, GPU args, rewrites, gates, resource thresholds, and analysis settings come from `effective_config.yaml`.",
            "- Python iterates `stages` from YAML and does not carry hardcoded eps or atom-target sweep lists.",
            "",
            "## Effective GPU Profile",
            "",
            f"- executable: `{gp['lammps_executable']}`",
            f"- args: `{' '.join(str(x) for x in gp['command_args'])}`",
            f"- forbidden env removed from child process: `{', '.join(gp.get('forbidden_environment', []))}`",
            "- production confirmation: `CUDA_LAUNCH_BLOCKING` is not placed in command lines and is removed from the LAMMPS child environment.",
            f"- neighbor workaround: `{gp['required_input_rewrites']['neighbor_policy']}`",
            "- risk: Dangerous builds are not checked with `check no`; this is a validated run-local workaround, not an upstream source fix.",
            "",
            "## Stage Status",
            "",
            "| stage | status | selected_target | science_signal |",
            "| --- | --- | --- | --- |",
        ]
        for stage in self.stage_order():
            sr = stages.get(stage, {})
            lines.append(
                f"| {stage} | {sr.get('status', 'not_started')} | "
                f"{sr.get('selected_target', '')} | {self.stage_has_science_signal(stage)} |"
            )
        lines += [
            "",
            "## Runtime Summary",
            "",
            f"- recorded cases: {len(cases)}",
            f"- successful cases: {sum(1 for r in cases.values() if r.get('success'))}",
            f"- stopped reason: `{self.state.data.get('stop_reason')}`",
            "",
            "## Escalation Decision",
            "",
        ]
        stop_reason = self.state.data.get("stop_reason")
        if stop_reason:
            lines.append(f"Escalation stopped: {stop_reason}")
        elif all(stages.get(stage, {}).get("status") == "success" for stage in self.stage_order()):
            lines.append("All enabled configured stages completed.")
        else:
            lines.append("Run is in progress or awaiting the next gate.")
        lines += [
            "",
            "## Next Recommended Scientific Action",
            "",
        ]
        if self.stage_has_science_signal("A1_medium"):
            lines.append("- Continue size scaling through the configured A2 gate if resources remain stable.")
        elif stages.get("A1_medium", {}).get("status") == "success":
            lines.append("- If A1_medium shows zero dislocations and no HCP/OTHER/plastic-zone growth, do not blindly scale to 700k; consider grain boundaries, predefects, or polycrystal pivots.")
        else:
            lines.append("- Continue the gated run until A1_medium production and analysis determine whether A2 is justified.")
        lines.append("- Report the KOKKOS neighbor-check CUDA bug upstream with the sanitizer root cause and validated workaround.")
        (self.run_dir / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_plan(cfg: dict[str, Any]) -> int:
    ok, lines = validation_plan_lines(cfg)
    print("\n".join(lines))
    print(f"\nplan-only result: {'OK' if ok else 'FAIL'}")
    print(f"(a new run would be created under {output_root(cfg)})")
    return 0 if ok else 1


def print_check_env(cfg: dict[str, Any], run_dir: Path | None = None) -> int:
    ok, env, lines = check_environment(cfg)
    print("\n".join(lines))
    print(f"\ncheck-env result: {'OK' if ok else 'FAIL'}")
    if run_dir is not None:
        write_json(run_dir / "logs" / "check_env.json", env)
    return 0 if ok else 1


def main_from_args(args: Any) -> int:
    try:
        cfg = load_grid_config(args.config)
    except GridConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 1

    if args.plan_only:
        return print_plan(cfg)
    if args.check_env:
        return print_check_env(cfg)

    resume = bool(getattr(args, "resume", False))
    run_dir = Path(args.run_dir) if args.run_dir else None
    if getattr(args, "analyze_only", False) and run_dir is None:
        run_dir = latest_run_dir(cfg)
        if run_dir is None:
            print("ERROR: --analyze-only needs --run-dir (no runs found)", file=sys.stderr)
            return 1
    if getattr(args, "force_rerun", None) and not (getattr(args, "run_stage", None) or getattr(args, "autopilot_gpu_grid", False)):
        resume = True

    try:
        runner = GpuGridRunner(
            cfg,
            run_dir=run_dir,
            resume=resume,
            force_rerun=args.force_rerun,
            smoke_only=bool(getattr(args, "smoke_only", False)),
        )
        if args.force_rerun and not (args.run_stage or args.autopilot_gpu_grid):
            ok = runner.force_rerun_case(args.force_rerun)
        elif args.analyze_only:
            ok = runner.analyze_only()
        elif args.run_stage:
            if not args.gpu:
                raise GridStop("--run-stage for GPU grid requires --gpu")
            ok = runner.run_stage(args.run_stage)
        elif args.autopilot_gpu_grid or resume:
            ok = runner.autopilot()
        else:
            print("ERROR: no GPU grid execution flag selected", file=sys.stderr)
            return 1
    except GridStop as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        return 1

    print(f"\nrun directory: {runner.run_dir}")
    print(f"result: {'OK' if ok else 'STOPPED (see summaries/*_gate_report.md and final_report.md)'}")
    return 0 if ok else 1
