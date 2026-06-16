"""Config loading / validation / effective-config dump for the stage sweep."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

REQUIRED_TOP_KEYS = ("A0", "A1_small", "A1_medium", "A2_optional", "resources")

REQUIRED_A0_KEYS = (
    "atoms_target",
    "structure_source",
    "eps_z",
    "temperatures_K",
    "smoke_steps",
    "production_steps",
    "run_smoke",
    "run_production_after_smoke_pass",
)

REQUIRED_A1_KEYS = (
    "atoms_target_candidates",
    "select_first_buildable_under_memory_limit",
    "inclusion_axis_ratio",
    "eps_z",
    "temperatures_K",
    "smoke_steps",
    "production_steps",
    "run_smoke_after_A0_production_pass",
    "run_production_after_gate_pass",
)

REQUIRED_RESOURCE_KEYS = (
    "cpu_mpi_ranks",
    "openmp_threads",
    "max_memory_gb",
    "min_free_disk_gb_before_start",
    "min_free_disk_gb_before_production",
    "dump_every_smoke",
    "dump_every_production",
    "restart_every",
    "max_walltime_smoke_minutes",
    "max_walltime_A0_production_hours",
    "max_walltime_A1_production_hours",
    "gpu_mode",
    "lammps_executable",
    "python_executable",
)


class ConfigError(RuntimeError):
    pass


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"config file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ConfigError("config root must be a YAML mapping")
    validate_config(cfg)
    cfg = copy.deepcopy(cfg)
    cfg["_config_path"] = str(p.resolve())
    return cfg


def _require(section: dict, keys, where: str) -> None:
    missing = [k for k in keys if k not in section]
    if missing:
        raise ConfigError(f"missing keys in {where}: {missing}")


def validate_config(cfg: dict) -> None:
    _require(cfg, REQUIRED_TOP_KEYS, "config root")
    _require(cfg["A0"], REQUIRED_A0_KEYS, "A0")
    _require(cfg["A1_small"], REQUIRED_A1_KEYS, "A1_small")
    _require(cfg["resources"], REQUIRED_RESOURCE_KEYS, "resources")

    # Hard safety rails: bigger stages must stay off in this run.
    if cfg["A1_medium"].get("enabled", False):
        raise ConfigError("A1_medium.enabled must be false in this run (safety rule)")
    if cfg["A2_optional"].get("enabled", False):
        raise ConfigError("A2_optional.enabled must be false in this run (safety rule)")

    for stage in ("A0", "A1_small"):
        eps = cfg[stage]["eps_z"]
        if not isinstance(eps, list) or not eps:
            raise ConfigError(f"{stage}.eps_z must be a non-empty list")
        for e in eps:
            if not isinstance(e, (int, float)) or e < 0.0 or e > 0.02:
                raise ConfigError(f"{stage}.eps_z value out of sane range [0, 0.02]: {e}")
        # The committed templates hardcode 300 K; anything else needs a template change.
        if [float(t) for t in cfg[stage]["temperatures_K"]] != [300.0]:
            raise ConfigError(f"{stage}.temperatures_K: only [300] is supported")
        for key in ("smoke_steps", "production_steps"):
            v = cfg[stage][key]
            if not isinstance(v, int) or v <= 0 or v > 2_000_000:
                raise ConfigError(f"{stage}.{key} must be a positive int <= 2e6, got {v}")

    res = cfg["resources"]
    for key in ("cpu_mpi_ranks", "openmp_threads", "dump_every_smoke",
                "dump_every_production", "restart_every"):
        v = res[key]
        if not isinstance(v, int) or v <= 0:
            raise ConfigError(f"resources.{key} must be a positive int, got {v}")

    targets = cfg["A1_small"]["atoms_target_candidates"]
    if not isinstance(targets, list) or not targets:
        raise ConfigError("A1_small.atoms_target_candidates must be a non-empty list")
    if max(targets) > 150_000:
        raise ConfigError(
            "A1_small targets above 150k are not allowed in this run "
            f"(got {max(targets)}); A1_medium/A2 are separate, disabled stages"
        )
    ratio = [float(x) for x in cfg["A1_small"]["inclusion_axis_ratio"]]
    if ratio != [1.0, 1.0, 2.0]:
        raise ConfigError(f"A1_small.inclusion_axis_ratio must be [1, 1, 2], got {ratio}")


def effective_config_text(cfg: dict) -> str:
    public = {k: v for k, v in cfg.items() if not str(k).startswith("_")}
    header = (
        f"# Effective config (source: {cfg.get('_config_path', 'unknown')})\n"
        "# Written by stage_runner; do not edit, edit configs/ instead.\n"
    )
    return header + yaml.safe_dump(public, sort_keys=False, allow_unicode=True)


def dump_effective(cfg: dict, out_path: Path) -> None:
    Path(out_path).write_text(effective_config_text(cfg), encoding="utf-8")
