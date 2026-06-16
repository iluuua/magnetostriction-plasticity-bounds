"""Stage B-aware R&D planner v2 (planner only).

This module turns the Stage B policy template into staged waves B0..B5, a rough
cost model, science-utility scoring, and dry-run policy/queue/decision
artifacts. It is a *decision layer*: it never launches LAMMPS, never spawns
subprocesses, never imports the execution runner, and never touches active run
roots (those appear only as text metadata in the exported files).

Production-ready notes:

- Scoring reuses ``objectives.py`` (single source of truth for the
  defect_signal / penalty / stability math); this module only adapts a metrics
  dict into the shared ``TrialResult`` and adds the Stage B promotion
  vocabulary and the (broader) Stage B signal definition.
- The runtime cost formula reuses ``fidelity.estimate_runtime_hours`` and layers
  the Stage B overhead factor on top, so the base rate lives in one place.
- Explicit models live in ``stageb_models.py``; builders return ``as_dict()`` so
  dry-run outputs stay plain dict/JSON/YAML and deterministic (apart from the
  timestamped output directory and embedded generation timestamps).

Public API (stable): ``load_policy``, ``estimate_runtime_hours``,
``estimate_wave_cost``, ``generate_stageB_waves``, ``estimate_full_factorial_cost``,
``score_science_utility``, ``recommend_from_mock_result``,
``generate_mock_decision_scenarios``, ``export_dry_run_outputs``,
``make_strategy_summary``, ``generate_stageB_queue``.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any, Mapping

import yaml

from . import fidelity as fid
from . import objectives as obj
from .stageb_models import (
    Recommendation,
    RuntimeEstimate,
    ScienceUtilityScore,
    StageBCandidate,
    StageBWave,
)


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
_STAGED_BASELINE_WAVES = (
    "B1_size",
    "B2_shape",
    "B3_position_predefects",
    "B4_concentration",
)


class StageBPolicyError(RuntimeError):
    """Invalid policy or unsafe planner request."""


# ---------------------------------------------------------------------------
# Policy loading and accessors
# ---------------------------------------------------------------------------


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

    axes = _axes(policy)
    required_axes = (
        "inclusion_size_nm",
        "shapes",
        "positions",
        "predefects",
        "inclusion_counts",
        "compositions_enabled",
    )
    missing = [axis for axis in required_axes if axis not in axes]
    if missing:
        raise StageBPolicyError(f"missing Stage B axes: {missing}")
    if axes["compositions_enabled"] != ["Fe4Al13"]:
        raise StageBPolicyError("only Fe4Al13 may be enabled in v2")

    policy = deepcopy(policy)
    policy["_policy_path"] = str(p.resolve())
    return policy


def _stage_b(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["policy"]["stage_B"]


def _axes(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return _stage_b(policy)["axes"]


def _fidelity(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["fidelity"]


def _baseline(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["stage_B0_baseline_lock"]


def _cost_model(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    return policy["costs"]["runtime_model"]


def _overheads(policy: Mapping[str, Any]) -> Mapping[str, float]:
    raw = policy["costs"]["overhead_factors"]
    return {
        "atoms_100k": float(raw["atoms_100k"]),
        "atoms_250k": float(raw["atoms_250k"]),
        "atoms_500k_700k": float(raw["atoms_500k_700k"]),
        "stage_B_small_variant": float(raw["stage_B_small_variant"]),
    }


# ---------------------------------------------------------------------------
# Cost model (base rate reused from fidelity.py; overhead layered on top)
# ---------------------------------------------------------------------------


def estimate_runtime_hours(
    atom_count: int,
    steps: int,
    overhead_factor: float,
    ref_atoms: int = REF_ATOMS,
    ref_steps_per_s: float = REF_STEPS_PER_S,
) -> float:
    """Estimate wall hours with linear-in-atom-count scaling + overhead.

    The base (overhead-free) formula is delegated to
    ``fidelity.estimate_runtime_hours`` so v1 and v2 share one implementation:
    ``estimated_steps_per_s = ref_steps_per_s * ref_atoms / atom_count`` and
    ``base_hours = steps / estimated_steps_per_s / 3600``. v2 multiplies by the
    Stage B ``overhead_factor``.
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
    return REF_STEPS_PER_S * REF_ATOMS / float(atom_count)


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
        if w["wave"] in _STAGED_BASELINE_WAVES
    )


def estimate_wave_cost(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate single-run cost lines and staged-wave alternatives."""
    fidelity = _fidelity(policy)
    overhead = _overheads(policy)
    smoke_steps = int(fidelity["smoke"]["steps"])
    prod_steps = int(fidelity["production"]["steps"])
    early_steps = int(fidelity["early_production_gate"]["total_steps"])

    one_100k = _runtime_record(
        "100k production, 1 eps", DEFAULT_ATOM_TARGET, prod_steps,
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
            early_gate_cases=2, atom_count=DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B2_shape": _wave_count_record(
            "B2_shape", smoke_cases=6, production_cases=2,
            early_gate_cases=2, atom_count=DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B3_position_predefects": _wave_count_record(
            "B3_position_predefects", smoke_cases=12, production_cases=2,
            early_gate_cases=2, atom_count=DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B4_concentration": _wave_count_record(
            "B4_concentration", smoke_cases=6, production_cases=1,
            early_gate_cases=1, atom_count=DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
        "B5_eps_threshold": _wave_count_record(
            "B5_eps_threshold", smoke_cases=0, production_cases=2,
            early_gate_cases=2, atom_count=DEFAULT_ATOM_TARGET,
            smoke_steps=smoke_steps, early_steps=early_steps,
            prod_steps=prod_steps, overhead=variant_overhead),
    }

    full_factorial = estimate_full_factorial_cost(policy)
    staged = _staged_baseline_hours(waves)
    return {
        "runtime_model": {
            "ref_atoms": _cost_model(policy)["ref_atoms"],
            "ref_steps_per_s": _cost_model(policy)["ref_steps_per_s"],
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


def estimate_full_factorial_cost(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate the rejected naive grid cost at 100k for smoke + production."""
    axes = _axes(policy)
    eps_count = len(_stage_b(policy)["eps"]["priority"])
    axis_counts = {
        "inclusion_size_nm": len(axes["inclusion_size_nm"]),
        "shape": len(axes["shapes"]),
        "position": len(axes["positions"]),
        "predefects": len(axes["predefects"]),
        "inclusion_count": len(axes["inclusion_counts"]),
        "eps": eps_count,
    }
    case_count = math.prod(axis_counts.values())
    fidelity = _fidelity(policy)
    overhead = _overheads(policy)["stage_B_small_variant"]
    smoke_hours = case_count * estimate_runtime_hours(
        DEFAULT_ATOM_TARGET, int(fidelity["smoke"]["steps"]), overhead)
    production_hours = case_count * estimate_runtime_hours(
        DEFAULT_ATOM_TARGET, int(fidelity["production"]["steps"]), overhead)
    return {
        "axis_counts": axis_counts,
        "case_count": case_count,
        "assumed_atom_target": DEFAULT_ATOM_TARGET,
        "smoke_all_hours": round(smoke_hours, 3),
        "production_all_hours": round(production_hours, 3),
        "smoke_plus_production_hours": round(smoke_hours + production_hours, 3),
        "rejected_reason": (
            "432 cases before atom-count repeats, early gates, large "
            "confirmation, analysis cost, or replicate seeds."
        ),
    }


# ---------------------------------------------------------------------------
# Staged wave and candidate generation
# ---------------------------------------------------------------------------


def _candidate(
    *,
    wave: str,
    axis: str,
    atom_target: int,
    eps: float,
    inclusion_size_nm: Any,
    shape: Any,
    position: Any,
    predefect: Any,
    inclusion_count: Any,
    composition: str,
    note: str = "",
) -> dict[str, Any]:
    candidate_id = (
        f"{wave}_{axis}_{str(inclusion_size_nm).replace('.', 'p')}_"
        f"{shape}_{position}_{predefect}_count{inclusion_count}_"
        f"eps{int(round(float(eps) * 10000)):04d}"
    )
    return StageBCandidate(
        candidate_id=candidate_id,
        wave=wave,
        varied_axis=axis,
        atom_target=atom_target,
        eps=float(eps),
        inclusion_size_nm=inclusion_size_nm,
        shape=shape,
        position=position,
        predefect=predefect,
        inclusion_count=inclusion_count,
        composition=composition,
        note=note,
    ).as_dict()


def _wave(
    name: str,
    purpose: str,
    candidates: list[dict[str, Any]],
    *,
    smoke_all: bool,
    production_slots: int,
    depends_on: str,
    priority_if: str | None = None,
) -> dict[str, Any]:
    return StageBWave(
        name=name,
        purpose=purpose,
        depends_on=depends_on,
        priority_if=priority_if,
        smoke_all=smoke_all,
        production_slots=production_slots,
        candidate_count=len(candidates),
        candidates=candidates,
    ).as_dict()


def generate_stageB_waves(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Generate staged Stage B waves B0..B5 as dry proposal data."""
    axes = _axes(policy)
    baseline = _baseline(policy)
    eps_priority = list(_stage_b(policy)["eps"]["priority"])
    atom_target = int(_stage_b(policy)["atom_targets"]["default"][0])

    b0_candidates = [
        _candidate(
            wave="B0_baseline_lock",
            axis="baseline_lock",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm=baseline["inclusion_size_nm"],
            shape=baseline["shape"],
            position=baseline["position"],
            predefect=baseline["predefect"],
            inclusion_count=baseline["inclusion_count"],
            composition=baseline["composition"],
            note="VERIFY_BUILDER: baseline/current inclusion_size_nm assumed 4 nm",
        )
        for eps in eps_priority
    ]

    b1_candidates = [
        _candidate(
            wave="B1_size",
            axis="inclusion_size_nm",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm=size,
            shape="ellipsoid_1_1_2",
            position="grain_interior",
            predefect="perfect",
            inclusion_count=1,
            composition="Fe4Al13",
        )
        for size, eps in product(axes["inclusion_size_nm"], eps_priority)
    ]

    b2_candidates = [
        _candidate(
            wave="B2_shape",
            axis="shape",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm="from_B1_best_or_informative",
            shape=shape,
            position="grain_interior",
            predefect="perfect",
            inclusion_count=1,
            composition="Fe4Al13",
        )
        for shape, eps in product(axes["shapes"], eps_priority)
    ]

    b3_predefects = policy["stage_B_waves"]["B3_position_predefects"][
        "predefect_subset"
    ]
    b3_candidates = [
        _candidate(
            wave="B3_position_predefects",
            axis="position_predefect",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm="from_B1_B2_best_or_baseline",
            shape="from_B2_best_or_ellipsoid_1_1_2",
            position=position,
            predefect=predefect,
            inclusion_count=1,
            composition="Fe4Al13",
        )
        for position, predefect, eps in product(
            axes["positions"], b3_predefects, eps_priority
        )
    ]

    b4_candidates = [
        _candidate(
            wave="B4_concentration",
            axis="inclusion_count",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm="from_best_single_inclusion",
            shape="from_best_single_inclusion",
            position="from_best_single_inclusion",
            predefect="from_best_single_inclusion",
            inclusion_count=count,
            composition="Fe4Al13",
            note="builder_gate: reject unless clearance/non-overlap is safe",
        )
        for count, eps in product(axes["inclusion_counts"], eps_priority)
    ]

    b5_candidates = [
        _candidate(
            wave="B5_eps_threshold",
            axis="eps",
            atom_target=atom_target,
            eps=eps,
            inclusion_size_nm="from_signal_case",
            shape="from_signal_case",
            position="from_signal_case",
            predefect="from_signal_case",
            inclusion_count="from_signal_case",
            composition="Fe4Al13",
            note="only if eps=0.0100 has signal and eps=0.0025 does not",
        )
        for eps in _stage_b(policy)["eps"]["threshold_refinement"]
    ]

    return [
        _wave(
            "B0_baseline_lock",
            "Freeze the baseline design before any Stage B wave.",
            b0_candidates,
            smoke_all=False,
            production_slots=0,
            depends_on="A1_custom_100k gate reviewed",
        ),
        _wave(
            "B1_size",
            "Vary only inclusion_size_nm; fixed ellipsoid/interior/perfect/count=1.",
            b1_candidates,
            smoke_all=True,
            production_slots=2,
            depends_on="B0_baseline_lock",
        ),
        _wave(
            "B2_shape",
            "Use best/informative size from B1; vary only shape.",
            b2_candidates,
            smoke_all=True,
            production_slots=2,
            depends_on="B1_size smoke ranking",
        ),
        _wave(
            "B3_position_predefects",
            "Use best size/shape or pivot on no signal; vary position and realism defects.",
            b3_candidates,
            smoke_all=True,
            production_slots=2,
            depends_on="B1/B2 best OR A1_100k no-signal pivot",
            priority_if="A1_100k or A1_medium ideal monocrystal has no signal",
        ),
        _wave(
            "B4_concentration",
            "Only after a single-inclusion signal or manual approval; vary count.",
            b4_candidates,
            smoke_all=True,
            production_slots=1,
            depends_on="single_inclusion_signal_or_manual_approval",
        ),
        _wave(
            "B5_eps_threshold",
            "Refine threshold when overload has signal but physical eps does not.",
            b5_candidates,
            smoke_all=False,
            production_slots=2,
            depends_on="eps0.0100_signal_and_eps0.0025_no_signal",
        ),
    ]


# ---------------------------------------------------------------------------
# Science-utility scoring (math reused from objectives.py)
# ---------------------------------------------------------------------------


def _trial_result_from_metrics(metrics: Mapping[str, Any]) -> obj.TrialResult:
    """Adapt a Stage B metrics dict into the shared objectives.TrialResult."""
    return obj.TrialResult(
        dislocation_count=int(metrics.get("dislocation_count", 0) or 0),
        total_line_length=float(metrics.get("total_line_length", 0.0) or 0.0),
        hcp_fraction=float(metrics.get("hcp_fraction", 0.0) or 0.0),
        other_fraction=float(metrics.get("other_fraction", 0.0) or 0.0),
        baseline_hcp_fraction=float(metrics.get("baseline_hcp_fraction", 0.0) or 0.0),
        baseline_other_fraction=float(
            metrics.get("baseline_other_fraction", 0.0) or 0.0),
        plastic_zone_detected=bool(metrics.get("plastic_zone_detected")),
        stacking_fault_indicator=bool(metrics.get("stacking_fault_indicator")),
        runtime_hours=float(metrics.get("runtime_hours", 0.0) or 0.0),
        stable=bool(metrics.get("stable", True)),
        failed=bool(metrics.get("failed")),
        hung=bool(metrics.get("hung")),
        cuda_error=bool(metrics.get("cuda_error")),
        lost_atoms=bool(metrics.get("lost_atoms")),
        nan_found=bool(metrics.get("nan_found")),
        interpretability_flag=bool(metrics.get("interpretability_flag", True)),
    )


def _has_stageb_signal(r: obj.TrialResult) -> bool:
    """Stage B signal = shared defect signal, plus line length / stacking fault."""
    return (
        obj.has_defect_signal(r)
        or r.total_line_length > 0
        or r.stacking_fault_indicator
    )


def score_science_utility(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Compute defect_signal_score, penalty, utility, and a coarse label.

    The component math is delegated to objectives.py so v1 and v2 cannot drift;
    only the Stage B signal definition and promotion vocabulary are local.
    """
    r = _trial_result_from_metrics(metrics)
    signal, signal_comp = obj.defect_signal_score(r)
    pen, pen_comp = obj.penalty(r)
    utility = signal - pen
    stability = obj.stability_score(r)
    has_signal = _has_stageb_signal(r)
    label = _promotion_label(metrics, utility, has_signal, stability)
    return ScienceUtilityScore(
        defect_signal_score=round(signal, 4),
        penalty=round(pen, 4),
        science_utility=round(utility, 4),
        stability_score=round(stability, 4),
        cost_efficiency=round(obj.cost_efficiency(utility, r.runtime_hours), 4),
        interpretability_score=obj.interpretability_score(r),
        has_defect_signal=has_signal,
        promotion_label=label,
        components={
            **{f"signal.{k}": round(v, 4) for k, v in signal_comp.items()},
            **{f"penalty.{k}": round(v, 4) for k, v in pen_comp.items()},
        },
    ).as_dict()


def _promotion_label(
    metrics: Mapping[str, Any],
    utility: float,
    has_signal: bool,
    stability: float,
) -> str:
    if bool(metrics.get("hung")) and not bool(metrics.get("failed")):
        return "retry_once"
    if (
        stability <= 0.0
        or bool(metrics.get("failed"))
        or bool(metrics.get("cuda_error"))
        or bool(metrics.get("lost_atoms"))
        or bool(metrics.get("nan_found"))
    ):
        return "reject"
    if not bool(metrics.get("stable", True)):
        return "reject"
    if has_signal and utility >= 6.0:
        return "confirm_500k_manual"
    if has_signal and utility >= 4.0:
        return "confirm_250k"
    if has_signal and utility >= 1.0:
        return "promote_to_production"
    if (not has_signal) and float(metrics.get("runtime_hours", 0.0) or 0.0) >= 8.0:
        return "pivot_to_realism"
    if utility < 0:
        return "stop_branch"
    return "manual_review"


# ---------------------------------------------------------------------------
# Recommendations and mock decision scenarios
# ---------------------------------------------------------------------------


def _recommendation(
    scores: Mapping[str, Any],
    label: str,
    actions: list[str],
    *,
    next_waves: list[str],
    manual_approval: bool,
) -> dict[str, Any]:
    return Recommendation(
        promotion_label=label,
        requires_manual_approval=manual_approval,
        actions=actions,
        next_waves=next_waves,
        scores=dict(scores),
    ).as_dict()


def recommend_from_mock_result(
    mock_result: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Turn one mock result into a Stage B-aware recommendation."""
    scores = score_science_utility(mock_result)
    scenario = str(mock_result.get("scenario", "generic"))
    eps_threshold = list(_stage_b(policy)["eps"]["threshold_refinement"])

    if scenario == "A1_100k_eps_0025_signal":
        return _recommendation(
            scores,
            "confirm_250k",
            [
                "Open 250k confirmation only after manual approval.",
                "Start B1_size as the first Stage B design wave.",
                "Keep B2_shape gated on B1 smoke ranking.",
            ],
            next_waves=["B1_size"],
            manual_approval=True,
        )
    if scenario == "A1_100k_only_eps_0100_signal":
        return _recommendation(
            scores,
            "manual_review",
            [
                f"Run B5_eps_threshold at eps={eps_threshold}.",
                "If threshold remains high, prioritize B3_position_predefects.",
                "Do not spend 700k ideal-monocrystal time before the realism check.",
            ],
            next_waves=["B5_eps_threshold", "B3_position_predefects"],
            manual_approval=True,
        )
    if scenario == "A1_100k_no_signal":
        return _recommendation(
            scores,
            "pivot_to_realism",
            [
                "Run B3_position_predefects before blind 700k escalation.",
                "Prioritize near_grain_boundary and vacancies_medium.",
                "Keep 500k/700k ideal monocrystal gated off.",
            ],
            next_waves=["B3_position_predefects"],
            manual_approval=True,
        )
    if scenario == "B1_size_6nm_signal":
        return _recommendation(
            scores,
            "confirm_250k" if scores["science_utility"] >= 4.0
            else "promote_to_production",
            [
                "Use inclusion_size_nm=6 as B2_shape input.",
                "Optionally open 250k confirmation if utility remains high.",
            ],
            next_waves=["B2_shape"],
            manual_approval=True,
        )
    if scenario == "B3_near_grain_boundary_signal":
        return _recommendation(
            scores,
            "confirm_250k",
            [
                "Confirm the near-boundary case at 250k.",
                "Do not prioritize larger ideal-monocrystal scaling.",
                "Keep position/predefect interpretation ahead of B4 concentration.",
            ],
            next_waves=["B3_position_predefects"],
            manual_approval=True,
        )
    if scenario == "B4_concentration_unstable":
        return _recommendation(
            scores,
            "stop_branch",
            [
                "Stop concentration branch after instability/chaos.",
                "Keep single-inclusion interpretation as the scientific baseline.",
                "Report multi-inclusion as unstable or too chaotic until placement improves.",
            ],
            next_waves=[],
            manual_approval=True,
        )

    return _recommendation(
        scores,
        scores["promotion_label"],
        ["Manual review: scenario was not one of the canonical decisions."],
        next_waves=[],
        manual_approval=True,
    )


def generate_mock_decision_scenarios(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Six canonical mock decisions required by the task prompt."""
    scenarios = [
        {
            "name": "A1_100k eps=0.0025 signal",
            "mock_result": {
                "scenario": "A1_100k_eps_0025_signal",
                "stable": True,
                "dislocation_count": 3,
                "total_line_length": 125.0,
                "hcp_fraction": 0.0310,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0045,
                "baseline_other_fraction": 0.0040,
                "plastic_zone_detected": True,
                "runtime_hours": 11.5,
            },
            "expected": "recommend 250k confirmation + B1_size",
        },
        {
            "name": "A1_100k only eps=0.0100 signal",
            "mock_result": {
                "scenario": "A1_100k_only_eps_0100_signal",
                "stable": True,
                "dislocation_count": 2,
                "total_line_length": 80.0,
                "hcp_fraction": 0.0302,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0041,
                "baseline_other_fraction": 0.0040,
                "plastic_zone_detected": True,
                "runtime_hours": 11.5,
                "physical_eps_signal": False,
                "overload_eps_signal": True,
            },
            "expected": "recommend B5 eps [0.0050, 0.0075] + B3 realism if high",
        },
        {
            "name": "A1_100k no signal",
            "mock_result": {
                "scenario": "A1_100k_no_signal",
                "stable": True,
                "dislocation_count": 0,
                "total_line_length": 0.0,
                "hcp_fraction": 0.0301,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0041,
                "baseline_other_fraction": 0.0040,
                "runtime_hours": 11.5,
            },
            "expected": "recommend B3 position/predefects; avoid blind 700k",
        },
        {
            "name": "B1_size finds 6 nm signal",
            "mock_result": {
                "scenario": "B1_size_6nm_signal",
                "stable": True,
                "dislocation_count": 4,
                "total_line_length": 180.0,
                "hcp_fraction": 0.0314,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0048,
                "baseline_other_fraction": 0.0040,
                "plastic_zone_detected": True,
                "runtime_hours": 11.5,
                "inclusion_size_nm": 6,
            },
            "expected": "recommend B2_shape at size=6; optional 250k confirmation",
        },
        {
            "name": "B3 near_grain_boundary signal",
            "mock_result": {
                "scenario": "B3_near_grain_boundary_signal",
                "stable": True,
                "dislocation_count": 5,
                "total_line_length": 220.0,
                "hcp_fraction": 0.0320,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0055,
                "baseline_other_fraction": 0.0040,
                "plastic_zone_detected": True,
                "runtime_hours": 12.0,
                "position": "near_grain_boundary",
            },
            "expected": "recommend 250k near-boundary confirmation",
        },
        {
            "name": "B4 concentration increases chaos/instability",
            "mock_result": {
                "scenario": "B4_concentration_unstable",
                "stable": False,
                "failed": True,
                "lost_atoms": True,
                "dislocation_count": 0,
                "total_line_length": 0.0,
                "runtime_hours": 4.0,
                "inclusion_count": 4,
                "interpretability_flag": False,
            },
            "expected": "stop concentration branch; keep single-inclusion interpretation",
        },
    ]
    for scenario in scenarios:
        scenario["recommendation"] = recommend_from_mock_result(
            scenario["mock_result"], policy)
    return scenarios


# ---------------------------------------------------------------------------
# Queue generation
# ---------------------------------------------------------------------------


def _queue_item(
    sequence: int,
    candidate: Mapping[str, Any],
    fidelity: str,
    steps: int,
    reason: str,
    *,
    selection_rule: str | None = None,
) -> dict[str, Any]:
    item = dict(candidate)
    item.update({
        "queue_id": f"Q{sequence:03d}_{candidate.get('wave', 'unknown')}_{fidelity}",
        "fidelity": fidelity,
        "steps": steps,
        "reason": reason,
        "selection_rule": selection_rule,
        "runner_config": "future copied Stage B runtime config only",
        "will_launch_md": False,
    })
    return item


def generate_stageB_queue(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Generate dry proposal queue items from the staged waves."""
    fidelity = _fidelity(policy)
    queue: list[dict[str, Any]] = []
    n = 0
    for wave in generate_stageB_waves(policy):
        for candidate in wave["candidates"]:
            if wave["smoke_all"]:
                n += 1
                queue.append(_queue_item(
                    n, candidate, "smoke", int(fidelity["smoke"]["steps"]),
                    "proposal_only: smoke all candidates before ranking"))
        for rank in range(1, wave["production_slots"] + 1):
            representative = wave["candidates"][0] if wave["candidates"] else {}
            n += 1
            queue.append(_queue_item(
                n, representative, "early_production_gate",
                int(fidelity["early_production_gate"]["total_steps"]),
                f"gated slot {rank}: first two production chunks for a top-ranked candidate",
                selection_rule=f"rank {rank} after {wave['name']} smoke review",
            ))
            n += 1
            queue.append(_queue_item(
                n, representative, "production",
                int(fidelity["production"]["steps"]),
                f"gated slot {rank}: resumable continuation to 100k only if early gate wins",
                selection_rule=f"rank {rank} after early_production_gate review",
            ))
    return queue


# ---------------------------------------------------------------------------
# Strategy summary and dry-run export
# ---------------------------------------------------------------------------


def make_strategy_summary(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize the R&D strategy in machine-friendly form."""
    stage_b = _stage_b(policy)
    return {
        "planner": "pipeline_rnd_stageB_v2",
        "mode": "planner_only",
        "no_md_execution": True,
        "stage_A_gate": {
            "current_next_target": policy["policy"]["stage_A"]["current_next_target"],
            "priority_eps": policy["policy"]["stage_A"]["priority_eps"],
            "short_enabled": policy["policy"]["stage_A"]["short_enabled"],
            "active_execution_lane": "external execution-agent; this tool does not touch it",
        },
        "stage_B_axes": {
            "inclusion_size_nm": stage_b["axes"]["inclusion_size_nm"],
            "shapes": stage_b["axes"]["shapes"],
            "positions": stage_b["axes"]["positions"],
            "predefects": stage_b["axes"]["predefects"],
            "inclusion_counts": stage_b["axes"]["inclusion_counts"],
            "compositions_enabled": stage_b["axes"]["compositions_enabled"],
            "compositions_disabled_until_validated": stage_b["axes"][
                "compositions_disabled_until_validated"
            ],
        },
        "adaptive_design": [
            "B0 lock baseline before changing axes",
            "B1 size: smoke all, top-2 production",
            "B2 shape: use best/informative B1 size, smoke all, top-2 production",
            "B3 position/predefects: priority realism pivot on no signal",
            "B4 concentration: only after single-inclusion signal or manual approval",
            "B5 eps threshold: only if eps=0.0100 signal but eps=0.0025 no signal",
        ],
        "disabled_or_gated": [
            "full factorial",
            "composition FeAl/Fe3Al until structure/potential/interface validation",
            "500k/700k except manual large confirmation",
            "direct magnetic field / SPIN future track",
            "Optuna/BoTorch until enough completed production observations exist",
        ],
        "active_run_roots_untouched": list(ACTIVE_RUN_ROOTS),
    }


def _strategy_summary_markdown(
    summary: Mapping[str, Any],
    costs: Mapping[str, Any],
) -> str:
    lines = [
        "# Stage B v2 dry-run strategy summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Mode: planner_only. No MD was launched. Active run roots were not touched.",
        "",
        "## Stage A gate",
        "",
        f"- current target: {summary['stage_A_gate']['current_next_target']}",
        f"- priority eps: {summary['stage_A_gate']['priority_eps']}",
        f"- short enabled: {summary['stage_A_gate']['short_enabled']}",
        "",
        "## Stage B axes",
        "",
    ]
    for key, value in summary["stage_B_axes"].items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Adaptive design",
        "",
    ]
    lines += [f"- {item}" for item in summary["adaptive_design"]]
    lines += [
        "",
        "## Disabled or gated",
        "",
    ]
    lines += [f"- {item}" for item in summary["disabled_or_gated"]]
    comp = costs["comparison"]
    lines += [
        "",
        "## Cost comparison",
        "",
        f"- staged B1-B4 smoke + winners: ~{comp['B1_to_B4_staged_smoke_plus_winners_hours']} GPU-hours",
        f"- rejected full factorial: ~{comp['full_factorial_hours']} GPU-hours",
        f"- rejected/staged ratio: ~{comp['factorial_to_staged_ratio']}x",
        "",
    ]
    return "\n".join(lines)


def export_dry_run_outputs(
    policy: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write dry-run artifacts under runs/pipeline_rnd_stageB/dry_run_*."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    waves = generate_stageB_waves(policy)
    queue = generate_stageB_queue(policy)
    costs = estimate_wave_cost(policy)
    scenarios = generate_mock_decision_scenarios(policy)
    summary = make_strategy_summary(policy)

    paths = {
        "policy_export": out / "policy_export.yaml",
        "strategy_summary": out / "strategy_summary.md",
        "cost_model": out / "cost_model.json",
        "stageB_waves": out / "stageB_waves.yaml",
        "stageB_queue": out / "stageB_queue.jsonl",
        "mock_decisions": out / "mock_decisions.json",
    }
    policy_doc = deepcopy(dict(policy))
    policy_doc["_exported_at"] = datetime.now().isoformat(timespec="seconds")
    policy_doc["_planner_only"] = True
    policy_doc["_active_run_roots_untouched"] = list(ACTIVE_RUN_ROOTS)
    paths["policy_export"].write_text(
        yaml.safe_dump(policy_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    paths["strategy_summary"].write_text(
        _strategy_summary_markdown(summary, costs), encoding="utf-8")
    paths["cost_model"].write_text(
        json.dumps(costs, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["stageB_waves"].write_text(
        yaml.safe_dump({"waves": waves}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    with paths["stageB_queue"].open("w", encoding="utf-8") as f:
        for item in queue:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    paths["mock_decisions"].write_text(
        json.dumps(scenarios, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths
