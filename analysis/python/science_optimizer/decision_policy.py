"""Decision policy layer (L7): rule_based_policy_v1 + v2 placeholders.

Every decision answers: what to run next, why, at which fidelity, at what
expected cost, under which stop conditions, and whether a human must
approve it first.

Rule order of rule_based_policy_v1 (first match wins):

    R1  hung trial            -> retry once at same fidelity; repeated hang
                                 stops the branch; no size escalation
    R2  hard failure/unstable -> reject (short rung: one retry allowed if
                                 it was an infrastructure failure)
    R3  branch failure rate   -> stop branch
    R4  runtime over budget   -> manual review if utility is promising,
                                 stop branch (suggest cheaper targeted
                                 Stage B cases) if utility is below threshold
    R5  smoke pass            -> promote to short
    R6  short pass            -> promote to production (gated)
    R7  production pass       -> confirm_large | pivot_to_realism | manual_review
    R8  large_confirmation    -> manual review (size-effect assessment)

v2 (BayesianOptimizerV2 / HyperbandV2) are intentionally only placeholders:
no Optuna/BoTorch/Ax dependency is added in this task.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Mapping

from . import fidelity as fid
from . import objectives as obj


class PolicyError(RuntimeError):
    pass


class DecisionAction:
    """Allowed actions: mirrors layers.py L7 decision_policy.allowed_values."""

    PROMOTE = "promote"
    STOP = "stop"
    RETRY = "retry"
    PIVOT = "pivot"
    CONFIRM_LARGE = "confirm_on_larger_scale"
    MANUAL_REVIEW = "require_manual_review"

    ALL = (PROMOTE, STOP, RETRY, PIVOT, CONFIRM_LARGE, MANUAL_REVIEW)


# Standing stop conditions attached to every branch decision.
STANDARD_STOP_CONDITIONS = (
    "repeated hangs in branch (> max_hangs_per_branch)",
    "branch failure rate > max_failure_rate_per_branch",
    "free disk below configured threshold before stage",
    "metrics indistinguishable from baseline after the branch question is answered",
    "a cheaper branch can answer the next question more directly",
)


@dataclass
class TrialContext:
    """Where in the layer space a trial result came from."""

    trial_id: str
    fidelity: str                       # smoke | short | production | large_confirmation
    size_stage: str                     # A0_24k | A1_small | A1_medium | A2_large
    atom_target: int
    eps_z: float
    realism_variant: str = "perfect_monocrystal"
    design: dict[str, Any] = field(default_factory=dict)
    # set by the runner/watchdog when the failure was infrastructural
    # (hang, smpd loss, cuda driver issue) rather than physical
    infrastructure_failure: bool = False
    recovery_succeeded: bool = False

    def branch_id(self) -> str:
        return f"{self.size_stage}/{self.realism_variant}/eps_{self.eps_z:.4f}"


@dataclass
class BranchState:
    """Mutable per-branch history the policy needs for stop/retry rules."""

    branch_id: str
    trials_total: int = 0
    failures: int = 0
    hangs: int = 0
    retries_used: int = 0

    def failure_rate(self) -> float:
        if self.trials_total <= 0:
            return 0.0
        return self.failures / self.trials_total

    def record(self, result: obj.TrialResult) -> None:
        self.trials_total += 1
        if result.hung:
            self.hangs += 1
        if fid.has_hard_failure(result) or not result.stable:
            self.failures += 1


@dataclass
class Decision:
    action: str
    promotion_label: str
    reason: str
    next_trials: list[dict[str, Any]] = field(default_factory=list)
    required_fidelity: str | None = None
    expected_cost: dict[str, Any] = field(default_factory=dict)
    stop_conditions: list[str] = field(default_factory=list)
    requires_human_approval: bool = False
    policy_name: str = "rule_based_policy_v1"
    scores: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary_line(self) -> str:
        approval = "HUMAN-APPROVAL" if self.requires_human_approval else "auto"
        return (f"{self.action:<26} label={self.promotion_label:<22} "
                f"[{approval}] {self.reason}")


class RuleBasedPolicyV1:
    """Deterministic layered rule policy (no surrogate model, no sampling)."""

    name = "rule_based_layered_multifidelity_v1"

    def __init__(self, cfg: Mapping[str, Any]):
        self.cfg = cfg
        self.thresholds = cfg["thresholds"]
        self.policy_cfg = cfg["policy"]
        self.size_ladder = fid.build_size_ladder(cfg)
        self.fidelity_ladder = fid.build_fidelity_ladder(cfg)

    # -- helpers ----------------------------------------------------------

    def _cost(self, atom_target: int, steps: int, fidelity: str,
              size_stage: str) -> dict[str, Any]:
        return fid.expected_cost(self.cfg, atom_target, steps, fidelity, size_stage)

    def _next_trial_spec(self, ctx: TrialContext, fidelity: str,
                         **overrides: Any) -> dict[str, Any]:
        steps = self.fidelity_ladder[fidelity].steps
        spec = {
            "size_stage": ctx.size_stage,
            "atom_target": ctx.atom_target,
            "eps_z": ctx.eps_z,
            "realism_variant": ctx.realism_variant,
            "fidelity": fidelity,
            "steps": steps,
        }
        spec.update(overrides)
        spec["expected_cost"] = self._cost(
            spec["atom_target"], spec["steps"], spec["fidelity"],
            spec["size_stage"])
        return spec

    def _pivot_targets(self, ctx: TrialContext) -> list[dict[str, Any]]:
        """Realism-pivot candidates from policy.if_A1_medium_no_signal."""
        prioritized = self.policy_cfg["if_A1_medium_no_signal"]["prioritize"]
        specs: list[dict[str, Any]] = []
        for variant in prioritized:
            if variant == "polycrystal_future":
                continue  # documented as future work; no builder yet
            if variant == "near_grain_boundary":
                spec = self._next_trial_spec(
                    ctx, "smoke", realism_variant="grain_boundary",
                    design={"position": "near_grain_boundary"})
            else:
                spec = self._next_trial_spec(
                    ctx, "smoke", realism_variant="predefects_vacancies"
                    if variant.startswith("vacancies") else "seeded_dislocation",
                    design={"predefect_variant": variant})
            specs.append(spec)
        return specs

    def _cheaper_stageb_targets(self, ctx: TrialContext) -> list[dict[str, Any]]:
        """Targeted Stage B smoke cases at the cheapest informative size."""
        cheap_atoms = min(self.size_ladder["A1_small"].atom_targets,
                          key=lambda n: abs(n - 120000))
        eps_main = float(self.cfg["layers"]["eps"]["physical_main"])
        return [
            self._next_trial_spec(
                ctx, "smoke", size_stage="A1_small", atom_target=cheap_atoms,
                eps_z=eps_main, realism_variant="grain_boundary",
                design={"position": "near_grain_boundary"}),
            self._next_trial_spec(
                ctx, "smoke", size_stage="A1_small", atom_target=cheap_atoms,
                eps_z=eps_main, realism_variant="predefects_vacancies",
                design={"predefect_variant": "vacancies_medium"}),
        ]

    # -- main entry point --------------------------------------------------

    def decide(self, ctx: TrialContext, result: obj.TrialResult,
               branch: BranchState | None = None) -> Decision:
        if ctx.fidelity not in fid.FIDELITY_ORDER:
            raise PolicyError(f"unknown fidelity: {ctx.fidelity}")
        branch = branch or BranchState(ctx.branch_id())
        branch.record(result)

        scores = obj.score_trial(result, self.thresholds,
                                 fidelity=ctx.fidelity,
                                 size_stage=ctx.size_stage)
        max_hangs = int(self.thresholds["max_hangs_per_branch"])
        max_fail_rate = float(self.thresholds["max_failure_rate_per_branch"])
        prod_thr = float(self.thresholds["min_science_utility_for_production"])
        large_thr = float(self.thresholds["min_science_utility_for_large_confirmation"])

        def mk(action: str, label: str, reason: str, **kw: Any) -> Decision:
            d = Decision(action=action, promotion_label=label, reason=reason,
                         scores=scores.as_dict(), **kw)
            d.stop_conditions = list(d.stop_conditions) + list(STANDARD_STOP_CONDITIONS)
            return d

        # R1: hang handling -------------------------------------------------
        if result.hung:
            if branch.hangs > max_hangs:
                return mk(
                    DecisionAction.STOP, obj.PromotionLabel.REJECT,
                    f"repeated hang in branch {branch.branch_id} "
                    f"({branch.hangs} > max_hangs_per_branch={max_hangs}); "
                    "stop branch; no escalation to larger atom_count until "
                    "the branch is stable",
                    requires_human_approval=True,
                    stop_conditions=["branch frozen until infrastructure cause "
                                     "is reviewed"])
            if ctx.recovery_succeeded and branch.retries_used == 0:
                branch.retries_used += 1
                return mk(
                    DecisionAction.RETRY, obj.PromotionLabel.RETRY,
                    "single hang with successful restart recovery: retry once "
                    "at the SAME fidelity; a second hang stops the branch",
                    next_trials=[self._next_trial_spec(ctx, ctx.fidelity)],
                    required_fidelity=ctx.fidelity,
                    expected_cost=self._cost(ctx.atom_target,
                                             self.fidelity_ladder[ctx.fidelity].steps,
                                             ctx.fidelity, ctx.size_stage),
                    stop_conditions=["second hang in this branch -> stop"])
            return mk(
                DecisionAction.STOP, obj.PromotionLabel.REJECT,
                "hang without successful recovery or retry budget exhausted; "
                "stop branch pending manual infrastructure review",
                requires_human_approval=True)

        # R2: hard failures / instability -----------------------------------
        if fid.has_hard_failure(result) or not result.stable:
            if (ctx.fidelity == "short" and ctx.infrastructure_failure
                    and branch.retries_used == 0):
                branch.retries_used += 1
                return mk(
                    DecisionAction.RETRY, obj.PromotionLabel.RETRY,
                    "short-fidelity infrastructure failure: one retry allowed",
                    next_trials=[self._next_trial_spec(ctx, "short")],
                    required_fidelity="short")
            return mk(
                DecisionAction.STOP, obj.PromotionLabel.REJECT,
                f"{ctx.fidelity} failed "
                f"(stable={result.stable}, flags="
                f"{[f for f in fid.HARD_FAILURE_FLAGS if getattr(result, f)]}); "
                "rejected by fidelity ladder rule")

        # R3: branch failure rate -------------------------------------------
        if branch.trials_total >= 4 and branch.failure_rate() > max_fail_rate:
            return mk(
                DecisionAction.STOP, obj.PromotionLabel.REJECT,
                f"branch failure rate {branch.failure_rate():.2f} > "
                f"{max_fail_rate}; stop branch",
                requires_human_approval=True)

        # R4: cost guard ------------------------------------------------------
        budget = fid.runtime_budget_hours(self.cfg, ctx.fidelity, ctx.size_stage)
        if result.runtime_hours > budget:
            if scores.science_utility >= prod_thr:
                return mk(
                    DecisionAction.MANUAL_REVIEW, obj.PromotionLabel.MANUAL_REVIEW,
                    f"runtime {result.runtime_hours:.1f}h exceeded session budget "
                    f"{budget:.0f}h but utility {scores.science_utility:.2f} is "
                    "promising: manual review of disk/runtime before continuing",
                    requires_human_approval=True)
            return mk(
                DecisionAction.STOP, obj.PromotionLabel.REJECT,
                f"expensive low-value branch: runtime {result.runtime_hours:.1f}h "
                f"> budget {budget:.0f}h and science_utility "
                f"{scores.science_utility:.2f} < {prod_thr}; stop branch and "
                "prefer cheaper targeted Stage B cases over large confirmation",
                next_trials=self._cheaper_stageb_targets(ctx),
                required_fidelity="smoke",
                requires_human_approval=True)

        # R5/R6: smoke and short promotion -----------------------------------
        if ctx.fidelity == "smoke":
            return mk(
                DecisionAction.PROMOTE, obj.PromotionLabel.PROMOTE_TO_SHORT,
                "smoke passed (stable, no failure flags): promote to short",
                next_trials=[self._next_trial_spec(ctx, "short")],
                required_fidelity="short",
                expected_cost=self._cost(ctx.atom_target,
                                         self.fidelity_ladder["short"].steps,
                                         "short", ctx.size_stage))
        if ctx.fidelity == "short":
            gated = ctx.size_stage in ("A1_medium", "A2_large")
            return mk(
                DecisionAction.PROMOTE, obj.PromotionLabel.PROMOTE_TO_PRODUCTION,
                "short passed: promote to production (smoke+short gate satisfied)"
                + ("; production at this stage requires a gate review first"
                   if gated else ""),
                next_trials=[self._next_trial_spec(ctx, "production")],
                required_fidelity="production",
                requires_human_approval=gated,
                expected_cost=self._cost(ctx.atom_target,
                                         self.fidelity_ladder["production"].steps,
                                         "production", ctx.size_stage))

        # R7: production outcomes ---------------------------------------------
        if ctx.fidelity == "production":
            if scores.has_defect_signal and scores.science_utility >= large_thr:
                confirm_atoms = min(self.size_ladder["A2_large"].atom_targets)
                steps = self.fidelity_ladder["large_confirmation"].steps
                next_specs = [
                    self._next_trial_spec(ctx, "smoke", size_stage="A2_large",
                                          atom_target=confirm_atoms),
                    self._next_trial_spec(ctx, "short", size_stage="A2_large",
                                          atom_target=confirm_atoms),
                    self._next_trial_spec(ctx, "large_confirmation",
                                          size_stage="A2_large",
                                          atom_target=confirm_atoms),
                ]
                return mk(
                    DecisionAction.CONFIRM_LARGE, obj.PromotionLabel.CONFIRM_LARGE,
                    f"production stable with signal (utility "
                    f"{scores.science_utility:.2f} >= {large_thr}): confirm size "
                    f"effect at {confirm_atoms} atoms; 700k only after 500k is "
                    "stable AND remains informative; inclusion size/shape sweep "
                    "(Stage B B1/B2) is the parallel cheaper option",
                    next_trials=next_specs,
                    required_fidelity="smoke",
                    requires_human_approval=True,
                    expected_cost=self._cost(confirm_atoms, steps,
                                             "large_confirmation", "A2_large"),
                    stop_conditions=["stop confirmation if 500k adds no "
                                     "information beyond 250k/300k"])
            if ctx.size_stage == "A1_medium" and not scores.has_defect_signal:
                pivot_cfg = self.policy_cfg["if_A1_medium_no_signal"]
                return mk(
                    DecisionAction.PIVOT, obj.PromotionLabel.PIVOT_TO_REALISM,
                    "A1_medium production stable but NO defect signal: pivot to "
                    f"realism (prioritize {', '.join(pivot_cfg['prioritize'])}); "
                    f"deprioritize {', '.join(pivot_cfg['deprioritize'])}; do "
                    "not blindly escalate the ideal monocrystal to 700k",
                    next_trials=self._pivot_targets(ctx),
                    required_fidelity="smoke",
                    requires_human_approval=True,
                    stop_conditions=["pivot branch also null at production -> "
                                     "stop the eigenstrain amplitude question"])
            return mk(
                DecisionAction.MANUAL_REVIEW, obj.PromotionLabel.MANUAL_REVIEW,
                f"production stable, utility {scores.science_utility:.2f} below "
                f"large-confirmation threshold {large_thr} "
                f"(signal={scores.has_defect_signal}): write gate report and "
                "review before spending more compute",
                requires_human_approval=True)

        # R8: large_confirmation ----------------------------------------------
        return mk(
            DecisionAction.MANUAL_REVIEW, obj.PromotionLabel.MANUAL_REVIEW,
            "large_confirmation finished: size-effect assessment is always a "
            "human decision (compare against A1_medium metrics)",
            requires_human_approval=True)


# ---------------------------------------------------------------------------
# v2 placeholders (no new dependencies in this task)
# ---------------------------------------------------------------------------

class BayesianOptimizerV2:
    """Placeholder. Not implemented in v1 — see decision_report.md section
    'Why this is not Bayesian optimization yet'.

    Plan: once enough completed production trials with science_utility exist
    (rule of thumb: > ~15-20 across the eps/size/design axes), fit a cheap
    surrogate (GP or TPE) over (eps_z, atom_target, design axes) and propose
    candidates by expected improvement, still subject to the same fidelity
    ladder and L7 stop rules. Requires Optuna or BoTorch — deliberately NOT
    added as a dependency in this task.
    """

    name = "bayesian_optimizer_v2"

    def __init__(self, *_a: Any, **_kw: Any):
        raise NotImplementedError(
            "bayesian_optimizer_v2 is a placeholder; use "
            "rule_based_layered_multifidelity_v1")


class HyperbandV2:
    """Placeholder. Successive-halving over the existing fidelity ladder:
    many smoke trials -> keep top fraction by early defect_signal_score ->
    short -> production. Maps naturally onto smoke/short/production budgets
    (2k/20k/100k steps) but needs reliable early-signal metrics at smoke
    fidelity before it is scientifically safe.
    """

    name = "hyperband_v2"

    def __init__(self, *_a: Any, **_kw: Any):
        raise NotImplementedError(
            "hyperband_v2 is a placeholder; use "
            "rule_based_layered_multifidelity_v1")


def get_policy(name: str, cfg: Mapping[str, Any]) -> RuleBasedPolicyV1:
    if name in ("rule_based_layered_multifidelity_v1", "rule_based_policy_v1"):
        return RuleBasedPolicyV1(cfg)
    if name == "bayesian_optimizer_v2":
        raise NotImplementedError(BayesianOptimizerV2.__doc__ or "")
    if name == "hyperband_v2":
        raise NotImplementedError(HyperbandV2.__doc__ or "")
    raise PolicyError(f"unknown policy: {name}")


# ---------------------------------------------------------------------------
# Mock decision scenarios (used by --score-mock / --dry-run / decision report)
# ---------------------------------------------------------------------------

def build_mock_scenarios(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Four canonical situations the planner must handle correctly.

    Runtime values are chosen relative to costs.max_run_hours so that each
    scenario exercises the intended rule (S1/S2 inside budget, S4 over).
    """
    eps_main = float(cfg["layers"]["eps"]["physical_main"])
    eps_over = float(cfg["layers"]["eps"]["overload"][-1])

    s1 = {
        "name": "S1_A1_medium_no_signal",
        "title": "Scenario 1 - A1_medium production stable, no defect signal",
        "context": TrialContext(
            trial_id="mock-S1", fidelity="production", size_stage="A1_medium",
            atom_target=250000, eps_z=eps_main),
        "result": obj.TrialResult(
            stable=True, dislocation_count=0, total_line_length=0.0,
            hcp_fraction=0.0301, baseline_hcp_fraction=0.0300,
            other_fraction=0.0042, baseline_other_fraction=0.0040,
            plastic_zone_detected=False, runtime_hours=20.0),
        "expected": "pivot_to_realism; prioritize near_grain_boundary / "
                    "vacancies_medium / seed_dislocation_if_available; "
                    "no blind 700k ideal monocrystal",
    }
    s2 = {
        "name": "S2_A1_medium_signal",
        "title": "Scenario 2 - A1_medium production stable WITH defect signal",
        "context": TrialContext(
            trial_id="mock-S2", fidelity="production", size_stage="A1_medium",
            atom_target=250000, eps_z=eps_over),
        "result": obj.TrialResult(
            stable=True, dislocation_count=14, total_line_length=420.0,
            hcp_fraction=0.0345, baseline_hcp_fraction=0.0300,
            other_fraction=0.0058, baseline_other_fraction=0.0040,
            plastic_zone_detected=True, stacking_fault_indicator=True,
            runtime_hours=20.0),
        "expected": "confirm_large at 500k (manual approval); 700k only after "
                    "500k remains informative; Stage B size/shape sweep allowed",
    }
    s3 = {
        "name": "S3_infrastructure_hang",
        "title": "Scenario 3 - infrastructure instability (hang, recovery ok)",
        "context": TrialContext(
            trial_id="mock-S3", fidelity="production", size_stage="A1_small",
            atom_target=80000, eps_z=eps_main,
            infrastructure_failure=True, recovery_succeeded=True),
        "result": obj.TrialResult(
            stable=False, hung=True, cuda_error=False, runtime_hours=6.0),
        "expected": "retry once at same fidelity; second hang stops the "
                    "branch; no escalation to larger atom counts until stable",
        "repeat_to_show_branch_stop": True,
    }
    s4 = {
        "name": "S4_expensive_low_value",
        "title": "Scenario 4 - stable but expensive, low-value branch",
        "context": TrialContext(
            trial_id="mock-S4", fidelity="production", size_stage="A1_medium",
            atom_target=300000, eps_z=eps_main),
        "result": obj.TrialResult(
            stable=True, dislocation_count=0, total_line_length=0.0,
            hcp_fraction=0.0302, baseline_hcp_fraction=0.0300,
            other_fraction=0.0041, baseline_other_fraction=0.0040,
            runtime_hours=30.0),
        "expected": "stop branch (runtime over budget, utility below "
                    "threshold); suggest cheaper targeted Stage B cases "
                    "instead of large confirmation",
    }
    return [s1, s2, s3, s4]


def run_mock_scenarios(cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Run the canonical scenarios through the v1 policy; return records."""
    policy = RuleBasedPolicyV1(cfg)
    records: list[dict[str, Any]] = []
    for sc in build_mock_scenarios(cfg):
        ctx: TrialContext = sc["context"]
        result: obj.TrialResult = sc["result"]
        branch = BranchState(ctx.branch_id())
        decision = policy.decide(ctx, result, branch)
        record = {
            "name": sc["name"],
            "title": sc["title"],
            "expected": sc["expected"],
            "context": asdict(ctx),
            "result": result.as_dict(),
            "decision": decision.as_dict(),
        }
        if sc.get("repeat_to_show_branch_stop"):
            second = policy.decide(ctx, result, branch)
            record["second_event_decision"] = second.as_dict()
        records.append(record)
    return records
