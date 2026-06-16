"""Stage B v2 cost model.

The base (overhead-free) runtime formula is reused from ``fidelity.py`` so v1
and v2 share one implementation:
``estimated_steps_per_s = ref_steps_per_s * ref_atoms / atom_count`` and
``base_hours = steps / estimated_steps_per_s / 3600``. This module layers the
Stage B overhead factor on top and assembles the wave / full-factorial records.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from . import fidelity as fid
from . import stageb_policy as sp
from .stageb_models import RuntimeEstimate


def estimate_runtime_hours(
    atom_count: int,
    steps: int,
    overhead_factor: float,
    ref_atoms: int = sp.REF_ATOMS,
    ref_steps_per_s: float = sp.REF_STEPS_PER_S,
) -> float:
    """Estimate wall hours with linear-in-atom-count scaling + overhead.

    Delegates the base rate/hours to ``fidelity.estimate_runtime_hours`` and
    multiplies by the Stage B ``overhead_factor``.
    """
    if atom_count <= 0:
        raise ValueError("atom_count must be positive")
    if steps < 0:
        raise ValueError("steps must be non-negative")
    rate_cfg = {
        "costs": {
            "runtime_model": {
                "ref_steps_per_s": ref_steps_per_s,
                "ref_atoms": ref_atoms,
            }
        }
    }
    base_hours = fid.estimate_runtime_hours(rate_cfg, atom_count, steps)
    return base_hours * float(overhead_factor)


def _steps_per_s(atom_count: int) -> float:
    """Reference steps/s at this atom count (mirrors fidelity's internal rate)."""
    return sp.REF_STEPS_PER_S * sp.REF_ATOMS / float(atom_count)


def _runtime_record(
    name: str,
    atom_count: int,
    steps: int,
    overhead_factor: float,
) -> dict[str, Any]:
    return RuntimeEstimate(
        name=name,
        atom_count=atom_count,
        steps=steps,
        overhead_factor=overhead_factor,
        estimated_steps_per_s=round(_steps_per_s(atom_count), 4),
        estimated_hours=round(
            estimate_runtime_hours(atom_count, steps, overhead_factor), 3),
    ).as_dict()


def _sum_record(name: str, records: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "name": name,
        "parts": [r["name"] for r in records],
        "estimated_hours": round(sum(float(r["estimated_hours"]) for r in records), 3),
    }


def _wave_count_record(
    wave: str,
    smoke_cases: int,
    early_gate_cases: int,
    production_cases: int,
    atom_count: int,
    smoke_steps: int,
    early_steps: int,
    prod_steps: int,
    overhead: float,
) -> dict[str, Any]:
    smoke = smoke_cases * estimate_runtime_hours(atom_count, smoke_steps, overhead)
    early = early_gate_cases * estimate_runtime_hours(atom_count, early_steps, overhead)
    prod = production_cases * estimate_runtime_hours(atom_count, prod_steps, overhead)
    return {
        "wave": wave,
        "smoke_cases": smoke_cases,
        "early_production_gate_cases": early_gate_cases,
        "selected_production_cases": production_cases,
        "smoke_only_hours": round(smoke, 3),
        "smoke_plus_early_gate_hours": round(smoke + early, 3),
        "smoke_plus_selected_production_hours": round(smoke + prod, 3),
        "note": (
            "early_production_gate is the first two production chunks; it is "
            "a decision checkpoint, not a separate throwaway run"
        ),
    }


def _staged_baseline_hours(waves: Mapping[str, Mapping[str, Any]]) -> float:
    """Sum smoke + selected-production hours over the staged baseline waves."""
    return sum(
        w["smoke_plus_selected_production_hours"]
        for w in waves.values()
        if w["wave"] in sp.STAGED_BASELINE_WAVES
    )


def estimate_full_factorial_cost(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate the rejected naive grid cost at 100k for smoke + production."""
    axes = sp.axes(policy)
    eps_count = len(sp.stage_b(policy)["eps"]["priority"])
    axis_counts = {
        "inclusion_size_nm": len(axes["inclusion_size_nm"]),
        "shape": len(axes["shapes"]),
        "position": len(axes["positions"]),
        "predefects": len(axes["predefects"]),
        "inclusion_count": len(axes["inclusion_counts"]),
        "eps": eps_count,
    }
    case_count = math.prod(axis_counts.values())
    fidcfg = sp.fidelity_cfg(policy)
    overhead = sp.overheads(policy)["stage_B_small_variant"]
    smoke_hours = case_count * estimate_runtime_hours(
        sp.DEFAULT_ATOM_TARGET, int(fidcfg["smoke"]["steps"]), overhead)
    production_hours = case_count * estimate_runtime_hours(
        sp.DEFAULT_ATOM_TARGET, int(fidcfg["production"]["steps"]), overhead)
    return {
        "axis_counts": axis_counts,
        "case_count": case_count,
        "assumed_atom_target": sp.DEFAULT_ATOM_TARGET,
        "smoke_all_hours": round(smoke_hours, 3),
        "production_all_hours": round(production_hours, 3),
        "smoke_plus_production_hours": round(smoke_hours + production_hours, 3),
        "rejected_reason": (
            "432 cases before atom-count repeats, early gates, large "
            "confirmation, analysis cost, or replicate seeds."
        ),
    }


def estimate_wave_cost(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate single-run cost lines and staged-wave alternatives."""
    fidcfg = sp.fidelity_cfg(policy)
    overhead = sp.overheads(policy)
    smoke_steps = int(fidcfg["smoke"]["steps"])
    prod_steps = int(fidcfg["production"]["steps"])
    early_steps = int(fidcfg["early_production_gate"]["total_steps"])

    one_100k = _runtime_record(
        "100k production, 1 eps", sp.DEFAULT_ATOM_TARGET, prod_steps,
        overhead["atoms_100k"])
    two_100k = _sum_record("100k production, 2 eps strategy", [one_100k, one_100k])
    one_250k = _runtime_record(
        "250k production, 1 eps", 250000, prod_steps, overhead["atoms_250k"])
    one_500k = _runtime_record(
        "500k production, 1 eps", 500000, prod_steps,
        overhead["atoms_500k_700k"])
    one_700k = _runtime_record(
        "700k production, 1 eps", 700000, prod_steps,
        overhead["atoms_500k_700k"])

    variant_overhead = overhead["stage_B_small_variant"]
    waves = {
        "B1_size": _wave_count_record(
            "B1_size", smoke_cases=6, production_cases=2,
            early_gate_cases=2, atom_count=sp.DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B2_shape": _wave_count_record(
            "B2_shape", smoke_cases=6, production_cases=2,
            early_gate_cases=2, atom_count=sp.DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B3_position_predefects": _wave_count_record(
            "B3_position_predefects", smoke_cases=12, production_cases=2,
            early_gate_cases=2, atom_count=sp.DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B4_concentration": _wave_count_record(
            "B4_concentration", smoke_cases=6, production_cases=1,
            early_gate_cases=1, atom_count=sp.DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B5_eps_threshold": _wave_count_record(
            "B5_eps_threshold", smoke_cases=0, production_cases=2,
            early_gate_cases=2, atom_count=sp.DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
    }

    full_factorial = estimate_full_factorial_cost(policy)
    staged = _staged_baseline_hours(waves)
    return {
        "runtime_model": {
            "ref_atoms": sp.cost_model(policy)["ref_atoms"],
            "ref_steps_per_s": sp.cost_model(policy)["ref_steps_per_s"],
            "formula": (
                "steps / (ref_steps_per_s * ref_atoms / atom_count) / "
                "3600 * overhead_factor"
            ),
        },
        "single_runs": {
            "production_100k_1eps": one_100k,
            "production_100k_two_eps_strategy": two_100k,
            "production_250k_1eps": one_250k,
            "production_500k_1eps": one_500k,
            "production_700k_1eps": one_700k,
        },
        "stage_B_waves": waves,
        "full_factorial_rejected": full_factorial,
        "comparison": {
            "B1_to_B4_staged_smoke_plus_winners_hours": round(staged, 3),
            "full_factorial_hours": full_factorial["smoke_plus_production_hours"],
            "factorial_to_staged_ratio": round(
                full_factorial["smoke_plus_production_hours"] / max(0.001, staged),
                1,
            ),
        },
    }
