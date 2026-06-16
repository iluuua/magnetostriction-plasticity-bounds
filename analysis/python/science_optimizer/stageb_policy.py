"""Foundation for the Stage B v2 planner: constants, policy loading, accessors.

Pure helper module (stdlib + PyYAML only). Holds the shared constants, the
``StageBPolicyError``, the validated ``load_policy``, and the small policy
accessors used by the cost / wave / decision / export modules. Kept separate so
those modules share one source of truth without importing the public facade,
which keeps the import graph acyclic.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml


REF_ATOMS = 24259
REF_STEPS_PER_S = 9.46
DEFAULT_ATOM_TARGET = 100000
ACTIVE_RUN_ROOTS = (
    "runs/stage_sweep_gpu_grid/20260611-175339",
    "runs/stage_sweep_gpu_A1_100k/20260612-173748",
    "runs/stage_sweep_gpu_A1_100k_*",
)

# Waves whose smoke + selected-production cost is the staged alternative to the
# rejected full factorial (B5 is conditional and excluded from the baseline).
STAGED_BASELINE_WAVES = (
    "B1_size",
    "B2_shape",
    "B3_position_predefects",
    "B4_concentration",
)


class StageBPolicyError(RuntimeError):
    """Invalid policy or unsafe planner request."""


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load and validate the Stage B v2 planner policy."""
    p = Path(path)
    if not p.is_file():
        raise StageBPolicyError(f"policy file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    if not isinstance(policy, dict):
        raise StageBPolicyError("policy root must be a YAML mapping")

    experiment = policy.get("experiment", {})
    if experiment.get("no_md_execution") is not True:
        raise StageBPolicyError("experiment.no_md_execution must be true")
    if experiment.get("mode") != "template_only":
        raise StageBPolicyError("experiment.mode must remain template_only")
    if "stage_B_waves" not in policy:
        raise StageBPolicyError("missing stage_B_waves")
    if "stage_B0_baseline_lock" not in policy:
        raise StageBPolicyError("missing stage_B0_baseline_lock")

    policy_axes = axes(policy)
    required_axes = (
        "inclusion_size_nm",
        "shapes",
        "positions",
        "predefects",
        "inclusion_counts",
        "compositions_enabled",
    )
    missing = [axis for axis in required_axes if axis not in policy_axes]
    if missing:
        raise StageBPolicyError(f"missing Stage B axes: {missing}")
    if policy_axes["compositions_enabled"] != ["Fe4Al13"]:
        raise StageBPolicyError("only Fe4Al13 may be enabled in v2")

    policy = deepcopy(policy)
    policy["_policy_path"] = str(p.resolve())
    return policy


# --- accessors (named to avoid clashing with the fidelity/objectives modules) ---


def stage_b(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["policy"]["stage_B"]


def axes(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return stage_b(policy)["axes"]


def fidelity_cfg(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["fidelity"]


def baseline(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["stage_B0_baseline_lock"]


def cost_model(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["costs"]["runtime_model"]


def overheads(policy: Mapping[str, Any]) -> Mapping[str, float]:
    raw = policy["costs"]["overhead_factors"]
    return {
        "atoms_100k": float(raw["atoms_100k"]),
        "atoms_250k": float(raw["atoms_250k"]),
        "atoms_500k_700k": float(raw["atoms_500k_700k"]),
        "stage_B_small_variant": float(raw["stage_B_small_variant"]),
    }
