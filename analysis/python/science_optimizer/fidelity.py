"""Fidelity ladder, size-scale ladder and runtime/cost model.

Fidelity ladder (steps from configs/layered_optimizer_policy.yaml):

    smoke               2 000 steps    stability and early signal
    short              20 000 steps    medium confirmation
    production        100 000 steps    final metrics
    large_confirmation  production steps at 250k/500k/700k atoms,
                        size-effect confirmation only

Size ladder:

    A0_24k      [24259]                  pipeline validation and baseline
    A1_small    [80000, 120000]          first size effect
    A1_medium   [200000, 250000, 300000] main scientific gate
    A2_large    [500000, 700000]         expensive confirmation only

The runtime model is a deliberately rough linear-in-atoms scaling anchored
to the observed A0 GPU rate (~9.4 steps/s at 24 259 atoms, RTX 3060,
runs/stage_sweep_gpu_grid/20260611-175339). It exists to label queue items
with an expected_runtime_class and to flag budget overruns, not to predict
wall time precisely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class FidelityError(RuntimeError):
    pass


FIDELITY_ORDER = ("smoke", "short", "production", "large_confirmation")

# Hard reject flags: any of these makes a trial rejected regardless of signal.
HARD_FAILURE_FLAGS = ("failed", "hung", "cuda_error", "lost_atoms", "nan_found")


@dataclass(frozen=True)
class FidelityLevel:
    name: str
    order: int
    steps: int
    purpose: str
    # only meaningful for large_confirmation
    atom_targets: tuple[int, ...] = ()


@dataclass(frozen=True)
class SizeStage:
    name: str
    order: int
    atom_targets: tuple[int, ...]
    role: str


def build_fidelity_ladder(cfg: Mapping[str, Any]) -> dict[str, FidelityLevel]:
    fid = cfg["layers"]["fidelity"]
    return {
        "smoke": FidelityLevel(
            "smoke", 0, int(fid["smoke_steps"]),
            "stability and early signal"),
        "short": FidelityLevel(
            "short", 1, int(fid["short_steps"]),
            "medium confirmation"),
        "production": FidelityLevel(
            "production", 2, int(fid["production_steps"]),
            "final metrics"),
        "large_confirmation": FidelityLevel(
            "large_confirmation", 3, int(fid["production_steps"]),
            "size-effect confirmation only",
            atom_targets=tuple(fid["large_confirmation_atom_targets"])),
    }


def build_size_ladder(cfg: Mapping[str, Any]) -> dict[str, SizeStage]:
    size = cfg["layers"]["size_scale"]
    return {
        "A0_24k": SizeStage("A0_24k", 0, tuple(size["A0"]),
                            "pipeline validation and baseline"),
        "A1_small": SizeStage("A1_small", 1, tuple(size["A1_small"]),
                              "first size effect"),
        "A1_medium": SizeStage("A1_medium", 2, tuple(size["A1_medium"]),
                               "main scientific gate"),
        "A2_large": SizeStage("A2_large", 3, tuple(size["A2_large"]),
                              "expensive confirmation only"),
    }


def stage_for_atom_target(size_ladder: Mapping[str, SizeStage],
                          atom_target: int) -> SizeStage:
    for stage in size_ladder.values():
        if atom_target in stage.atom_targets:
            return stage
    raise FidelityError(f"atom_target {atom_target} not in any size stage")


def next_fidelity(name: str) -> str | None:
    """Next rung of the ladder, or None at the top."""
    if name not in FIDELITY_ORDER:
        raise FidelityError(f"unknown fidelity: {name}")
    i = FIDELITY_ORDER.index(name)
    return FIDELITY_ORDER[i + 1] if i + 1 < len(FIDELITY_ORDER) else None


def has_hard_failure(result: Any) -> bool:
    """failed/hung/nan/lost/cuda_error trials are rejected (ladder rule)."""
    return any(bool(getattr(result, flag, False)) for flag in HARD_FAILURE_FLAGS)


def fidelity_pass(result: Any) -> bool:
    """A trial passes its fidelity rung iff stable and no hard-failure flag."""
    return bool(getattr(result, "stable", False)) and not has_hard_failure(result)


# ---------------------------------------------------------------------------
# Runtime / cost model
# ---------------------------------------------------------------------------

RUNTIME_CLASSES = (
    (0.5, "under_30min"),
    (2.0, "under_2h"),
    (6.0, "h2_6"),
    (12.0, "h6_12"),
    (24.0, "h12_24"),
    (48.0, "h24_48"),
    (float("inf"), "over_48h"),
)


def estimate_runtime_hours(cfg: Mapping[str, Any], atom_target: int,
                           steps: int) -> float:
    """Rough wall-time estimate: rate scales inversely with atom count."""
    model = cfg["costs"]["runtime_model"]
    ref_rate = float(model["ref_steps_per_s"])
    ref_atoms = float(model["ref_atoms"])
    rate = ref_rate * ref_atoms / float(atom_target)  # steps/s at this size
    return steps / rate / 3600.0


def runtime_class(hours: float) -> str:
    for limit, label in RUNTIME_CLASSES:
        if hours <= limit:
            return label
    return "over_48h"


def runtime_budget_hours(cfg: Mapping[str, Any], fidelity: str,
                         size_stage_name: str) -> float:
    """Per-session budget mirroring stage_sweep_gpu_grid resources.max_run_hours."""
    budgets = cfg["costs"]["max_run_hours"]
    if fidelity == "smoke":
        return float(budgets["smoke"])
    if fidelity == "short":
        return float(budgets["short"])
    key = {
        "A0_24k": "production_A0_24k",
        "A1_small": "production_A1_small",
        "A1_medium": "production_A1_medium",
        "A2_large": "production_A2_large",
    }.get(size_stage_name, "production_A2_large")
    return float(budgets[key])


def expected_cost(cfg: Mapping[str, Any], atom_target: int, steps: int,
                  fidelity: str, size_stage_name: str) -> dict[str, Any]:
    """Cost record for queue items and decisions.

    over_budget means the single-session budget would be exceeded; with the
    chunked runner this implies a multi-session run, not an impossible one.
    """
    hours = estimate_runtime_hours(cfg, atom_target, steps)
    budget = runtime_budget_hours(cfg, fidelity, size_stage_name)
    return {
        "estimated_hours": round(hours, 2),
        "runtime_class": runtime_class(hours),
        "session_budget_hours": budget,
        "over_budget": hours > budget,
    }


# ---------------------------------------------------------------------------
# Ladder gates
# ---------------------------------------------------------------------------

def production_allowed(smoke_passed: bool, short_passed: bool) -> bool:
    """Production only after smoke AND short pass."""
    return smoke_passed and short_passed


def large_confirmation_allowed(production_passed: bool,
                               production_has_signal: bool,
                               size_effect_gate_open: bool) -> bool:
    """500k/700k only after production signal, or an explicit, documented,
    still-unresolved size-effect question (manual gate)."""
    if not production_passed:
        return False
    return production_has_signal or size_effect_gate_open
