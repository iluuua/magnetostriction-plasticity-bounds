"""Objective / score computation for the layered optimizer.

Implements the agreed scoring contract:

    defect_signal_score =
          3.0 * I(dislocation_count > 0)
        + 1.5 * log1p(total_line_length)
        + 1.0 * max(0, hcp_fraction   - baseline_hcp_fraction)
        + 0.8 * max(0, other_fraction - baseline_other_fraction)
        + 1.0 * I(plastic_zone_detected)
        + 0.5 * I(stacking_fault_indicator)

    penalty =
          4.0 * I(not stable)
        + 3.0 * I(failed) + 3.0 * I(hung) + 3.0 * I(cuda_error)
        + 2.0 * I(lost_atoms) + 2.0 * I(nan_found)
        + 0.1 * runtime_hours

    science_utility = defect_signal_score - penalty

Signal detection thresholds mirror science_gates.production_signal in
configs/stage_sweep_gpu_grid.yaml (0.05 % HCP growth, 0.5 % OTHER growth,
expressed here as absolute fractions).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping


# science_gates: hcp_fraction_increase_gt_0.05_percent -> 0.0005 as a fraction
HCP_SIGNAL_DELTA = 0.0005
# science_gates: other_fraction_increase_gt_0.5_percent -> 0.005 as a fraction
OTHER_SIGNAL_DELTA = 0.005


class PromotionLabel:
    REJECT = "reject"
    RETRY = "retry"
    PROMOTE_TO_SHORT = "promote_to_short"
    PROMOTE_TO_PRODUCTION = "promote_to_production"
    CONFIRM_LARGE = "confirm_large"
    PIVOT_TO_REALISM = "pivot_to_realism"
    MANUAL_REVIEW = "manual_review"

    ALL = (REJECT, RETRY, PROMOTE_TO_SHORT, PROMOTE_TO_PRODUCTION,
           CONFIRM_LARGE, PIVOT_TO_REALISM, MANUAL_REVIEW)


@dataclass
class TrialResult:
    """Measured/parsed outcome of one trial (one fidelity rung of one case)."""

    # defect / structure metrics
    dislocation_count: int = 0
    total_line_length: float = 0.0      # Angstrom, from OVITO DXA
    dislocation_density: float = 0.0
    hcp_fraction: float = 0.0
    other_fraction: float = 0.0
    baseline_hcp_fraction: float = 0.0
    baseline_other_fraction: float = 0.0
    plastic_zone_detected: bool = False
    stacking_fault_indicator: bool = False
    # cost
    runtime_hours: float = 0.0
    # stability / infrastructure flags
    stable: bool = True
    failed: bool = False
    hung: bool = False
    cuda_error: bool = False
    lost_atoms: bool = False
    nan_found: bool = False
    # analysis quality
    interpretability_flag: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ObjectiveScores:
    defect_signal_score: float
    penalty: float
    science_utility: float
    stability_score: float
    cost_efficiency: float
    interpretability_score: float
    has_defect_signal: bool
    promotion_label: str = PromotionLabel.MANUAL_REVIEW
    components: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ind(flag: bool) -> float:
    return 1.0 if flag else 0.0


def has_defect_signal(r: TrialResult) -> bool:
    """Production-signal definition shared with the gpu_grid science gates."""
    return (
        r.dislocation_count > 0
        or (r.hcp_fraction - r.baseline_hcp_fraction) > HCP_SIGNAL_DELTA
        or (r.other_fraction - r.baseline_other_fraction) > OTHER_SIGNAL_DELTA
        or r.plastic_zone_detected
    )


def defect_signal_score(r: TrialResult) -> tuple[float, dict[str, float]]:
    comp = {
        "dislocations_present": 3.0 * _ind(r.dislocation_count > 0),
        "line_length_log1p": 1.5 * math.log1p(max(0.0, r.total_line_length)),
        "hcp_growth": 1.0 * max(0.0, r.hcp_fraction - r.baseline_hcp_fraction),
        "other_growth": 0.8 * max(0.0, r.other_fraction - r.baseline_other_fraction),
        "plastic_zone": 1.0 * _ind(r.plastic_zone_detected),
        "stacking_fault": 0.5 * _ind(r.stacking_fault_indicator),
    }
    return sum(comp.values()), comp


def penalty(r: TrialResult) -> tuple[float, dict[str, float]]:
    comp = {
        "unstable": 4.0 * _ind(not r.stable),
        "failed": 3.0 * _ind(r.failed),
        "hung": 3.0 * _ind(r.hung),
        "cuda_error": 3.0 * _ind(r.cuda_error),
        "lost_atoms": 2.0 * _ind(r.lost_atoms),
        "nan_found": 2.0 * _ind(r.nan_found),
        "runtime": 0.1 * max(0.0, r.runtime_hours),
    }
    return sum(comp.values()), comp


def stability_score(r: TrialResult) -> float:
    """1.0 = clean run; deductions per failure mode; clamped to [0, 1]."""
    s = 1.0
    if not r.stable:
        s -= 0.5
    for flag in (r.failed, r.hung, r.cuda_error):
        if flag:
            s -= 0.3
    for flag in (r.lost_atoms, r.nan_found):
        if flag:
            s -= 0.2
    return max(0.0, min(1.0, s))


def cost_efficiency(utility: float, runtime_hours: float) -> float:
    """Science utility per wall-clock hour (floored at 0.1 h to avoid blowup)."""
    return utility / max(0.1, runtime_hours)


def interpretability_score(r: TrialResult) -> float:
    return 1.0 if r.interpretability_flag else 0.4


def base_promotion_label(r: TrialResult, scores: "ObjectiveScores",
                         fidelity: str, size_stage: str,
                         thresholds: Mapping[str, Any]) -> str:
    """Per-trial label from scores alone (no branch history).

    decision_policy.RuleBasedPolicyV1 refines this with branch state
    (hang counts, retry budget, failure rate, cost guards).
    """
    # hard failures first
    if r.hung:
        # single hang is retryable at the same fidelity; repetition is
        # handled at branch level by the policy
        return PromotionLabel.RETRY
    if r.failed or r.cuda_error or r.nan_found or r.lost_atoms or not r.stable:
        return PromotionLabel.REJECT

    if fidelity == "smoke":
        return PromotionLabel.PROMOTE_TO_SHORT
    if fidelity == "short":
        return PromotionLabel.PROMOTE_TO_PRODUCTION

    if fidelity == "production":
        large_thr = float(thresholds["min_science_utility_for_large_confirmation"])
        if scores.has_defect_signal and scores.science_utility >= large_thr:
            return PromotionLabel.CONFIRM_LARGE
        if size_stage == "A1_medium" and not scores.has_defect_signal:
            # main scientific gate came back null -> realism pivot
            return PromotionLabel.PIVOT_TO_REALISM
        # weak/ambiguous signal, or baseline stages: human gate review
        return PromotionLabel.MANUAL_REVIEW

    # large_confirmation: size-effect assessment is always a human decision
    return PromotionLabel.MANUAL_REVIEW


def score_trial(r: TrialResult, thresholds: Mapping[str, Any],
                fidelity: str = "production",
                size_stage: str = "A1_medium") -> ObjectiveScores:
    """Compute all scores + the base promotion label for one trial result."""
    signal, signal_comp = defect_signal_score(r)
    pen, pen_comp = penalty(r)
    utility = signal - pen
    scores = ObjectiveScores(
        defect_signal_score=round(signal, 4),
        penalty=round(pen, 4),
        science_utility=round(utility, 4),
        stability_score=round(stability_score(r), 4),
        cost_efficiency=round(cost_efficiency(utility, r.runtime_hours), 4),
        interpretability_score=interpretability_score(r),
        has_defect_signal=has_defect_signal(r),
        components={**{f"signal.{k}": round(v, 4) for k, v in signal_comp.items()},
                    **{f"penalty.{k}": round(v, 4) for k, v in pen_comp.items()}},
    )
    scores.promotion_label = base_promotion_label(
        r, scores, fidelity, size_stage, thresholds)
    return scores
