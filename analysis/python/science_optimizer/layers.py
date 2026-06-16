"""Layer model for the layered multi-fidelity optimizer.

Eight layers, L0..L7, map the physical/computational search space:

    L0 infrastructure      existing GPU runner, chunked production, restart
    L1 fidelity            smoke -> short -> production -> large_confirmation
    L2 size_scale          24k -> 80k/120k -> 200k/250k/300k -> 500k/700k
    L3 physics_surrogate   eigenstrain eps_z scalar (future: direction/tensor/cyclic)
    L4 inclusion_design    size / shape / position / predefects / count / composition
    L5 realism             monocrystal -> GB -> vacancies -> dislocation -> polycrystal
    L6 objective           defect signal / stability / cost / interpretability
    L7 decision_policy     promote / stop / retry / pivot / confirm / manual review

Each layer exposes: allowed_values, prerequisites, cost_level, risk_level,
scientific_value, promotion_rules, stop_rules. Layers are static metadata;
the dynamic logic lives in fidelity.py / objectives.py / decision_policy.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class LayerError(RuntimeError):
    pass


# Coarse ordinal levels used for cost_level / risk_level / scientific_value.
LEVELS = ("none", "low", "medium", "high", "extreme")


@dataclass(frozen=True)
class Layer:
    """One layer of the search space (static metadata)."""

    name: str
    index: int
    description: str
    # axis name -> tuple of allowed values (or descriptive strings)
    allowed_values: Mapping[str, tuple]
    # names of layers / gates that must be satisfied before this layer moves
    prerequisites: tuple[str, ...]
    cost_level: str
    risk_level: str
    scientific_value: str
    promotion_rules: tuple[str, ...]
    stop_rules: tuple[str, ...]

    def __post_init__(self) -> None:
        for lvl_name in ("cost_level", "risk_level", "scientific_value"):
            lvl = getattr(self, lvl_name)
            if lvl not in LEVELS:
                raise LayerError(f"layer {self.name}: {lvl_name}={lvl!r} not in {LEVELS}")

    def summary_line(self) -> str:
        axes = ", ".join(self.allowed_values.keys()) or "-"
        return (f"L{self.index} {self.name:<18} cost={self.cost_level:<7} "
                f"risk={self.risk_level:<7} value={self.scientific_value:<7} axes: {axes}")


@dataclass
class LayerStack:
    """Ordered, validated collection of the eight layers."""

    layers: dict[str, Layer] = field(default_factory=dict)

    def add(self, layer: Layer) -> None:
        if layer.name in self.layers:
            raise LayerError(f"duplicate layer name: {layer.name}")
        self.layers[layer.name] = layer

    def get(self, name: str) -> Layer:
        try:
            return self.layers[name]
        except KeyError:
            raise LayerError(f"unknown layer: {name}") from None

    def ordered(self) -> list[Layer]:
        return sorted(self.layers.values(), key=lambda l: l.index)

    def validate(self) -> None:
        names = set(self.layers)
        if len(self.layers) != 8:
            raise LayerError(f"expected 8 layers, got {len(self.layers)}")
        indices = sorted(l.index for l in self.layers.values())
        if indices != list(range(8)):
            raise LayerError(f"layer indices must be 0..7, got {indices}")
        for layer in self.layers.values():
            for prereq in layer.prerequisites:
                # prerequisites may name another layer or a named gate
                # ("gate:..."); layer references must resolve.
                if prereq.startswith("gate:"):
                    continue
                if prereq not in names:
                    raise LayerError(
                        f"layer {layer.name}: unresolved prerequisite {prereq!r}")

    def summary(self) -> str:
        return "\n".join(l.summary_line() for l in self.ordered())


def build_layer_stack(cfg: Mapping[str, Any]) -> LayerStack:
    """Build the eight-layer stack from configs/layered_optimizer_policy.yaml."""
    lcfg = cfg["layers"]
    fid = lcfg["fidelity"]
    size = lcfg["size_scale"]
    eps = lcfg["eps"]
    inc = lcfg["inclusion_design"]

    stack = LayerStack()

    stack.add(Layer(
        name="infrastructure",
        index=0,
        description=("Existing GPU stage_runner: chunked production, "
                     "restart/resume, watchdog, state.json. Reused as-is."),
        allowed_values={
            "runner": ("stage_runner.gpu_grid (chunked + watchdog + resume)",),
            "execution_here": ("forbidden: planner_only, no_md_execution",),
        },
        prerequisites=(),
        cost_level="none",
        risk_level="low",
        scientific_value="none",
        promotion_rules=(
            "Planner emits queue items + runner_config_patch; humans/runner execute.",
        ),
        stop_rules=(
            "Stop planning against a run root that is active (hard rule).",
        ),
    ))

    stack.add(Layer(
        name="fidelity",
        index=1,
        description="Cheap-to-expensive simulation ladder per trial.",
        allowed_values={
            "fidelity": ("smoke", "short", "production", "large_confirmation"),
            "steps": (fid["smoke_steps"], fid["short_steps"], fid["production_steps"]),
            "large_confirmation_atom_targets":
                tuple(fid["large_confirmation_atom_targets"]),
        },
        prerequisites=("infrastructure",),
        cost_level="medium",
        risk_level="low",
        scientific_value="medium",
        promotion_rules=(
            "smoke pass -> short; short pass -> production.",
            "production only after smoke AND short pass.",
            "large_confirmation only after production signal or an explicit "
            "unresolved size-effect gate.",
        ),
        stop_rules=(
            "failed/hung/nan/lost_atoms/cuda_error trials are rejected.",
        ),
    ))

    stack.add(Layer(
        name="size_scale",
        index=2,
        description="Atom-count ladder A0 -> A1_small -> A1_medium -> A2_large.",
        allowed_values={
            "A0_24k": tuple(size["A0"]),
            "A1_small": tuple(size["A1_small"]),
            "A1_medium": tuple(size["A1_medium"]),
            "A2_large": tuple(size["A2_large"]),
        },
        prerequisites=("fidelity",),
        cost_level="high",
        risk_level="medium",
        scientific_value="high",
        promotion_rules=(
            "Promote one size stage at a time after the previous stage gate.",
            "A2_large (500k/700k) only to confirm an existing size effect.",
            "700k only after 500k is stable and informative.",
        ),
        stop_rules=(
            "If A1_medium shows no defect signal: do NOT escalate ideal "
            "monocrystal to 700k; pivot to realism instead.",
            "Stop escalation if disk below threshold or runtime budget exceeded.",
        ),
    ))

    stack.add(Layer(
        name="physics_surrogate",
        index=3,
        description=("Magnetic loading surrogate: scalar eigenstrain eps_z "
                     "inside the Fe-Al inclusion. Direct field is future work."),
        allowed_values={
            "eps_z": tuple(eps["values"]),
            "physical_main": (eps["physical_main"],),
            "overload": tuple(eps["overload"]),
            "future": ("eigenstrain_direction", "anisotropic_tensor_eigenstrain",
                       "cyclic_eigenstrain", "direct_spin_lattice_after_parameters"),
        },
        prerequisites=("size_scale",),
        cost_level="low",
        risk_level="low",
        scientific_value="high",
        promotion_rules=(
            "0.0025 is the physical main case; 0.0050/0.0100 are overload probes.",
            "Direct magnetic field requires: moments, exchange constants, "
            "spin-lattice coupling, magnetostriction tensor, anisotropy, field "
            "orientation, domain structure, validated spin-lattice Al-Fe potential.",
        ),
        stop_rules=(
            "Do not add new eps values mid-branch; finish the ladder first.",
        ),
    ))

    stack.add(Layer(
        name="inclusion_design",
        index=4,
        description="Stage B design axes for the inclusion itself.",
        allowed_values={
            "inclusion_size_nm": tuple(inc["sizes_nm"]),
            "shape": tuple(inc["shapes"]),
            "position": tuple(inc["positions"]),
            "predefects": tuple(inc["predefects"]),
            "inclusion_count": tuple(inc["inclusion_counts"]),
            "composition": tuple(inc["compositions"]),
        },
        prerequisites=("physics_surrogate", "gate:A1_medium_reviewed"),
        cost_level="high",
        risk_level="medium",
        scientific_value="high",
        promotion_rules=(
            "No full factorial: change one high-value design axis at a time.",
            "Multi-inclusion only after a single-inclusion signal exists.",
            "Composition sweep requires validated structure + potential + "
            "interface orientation search.",
        ),
        stop_rules=(
            "Stop a design axis when metrics are indistinguishable from "
            "baseline after the axis question is answered.",
        ),
    ))

    stack.add(Layer(
        name="realism",
        index=5,
        description="Material realism ladder around the inclusion.",
        allowed_values={
            "variant": ("perfect_monocrystal", "grain_boundary",
                        "predefects_vacancies", "seeded_dislocation",
                        "polycrystal", "multi_inclusion"),
        },
        prerequisites=("physics_surrogate",),
        cost_level="medium",
        risk_level="medium",
        scientific_value="high",
        promotion_rules=(
            "Becomes the PRIORITY branch when ideal monocrystal has no signal "
            "at A1_medium (grain_boundary, vacancies, seeded dislocation).",
            "Polycrystal needs a builder + orientation control (future).",
        ),
        stop_rules=(
            "Stop realism variants that repeatedly fail stability checks.",
        ),
    ))

    stack.add(Layer(
        name="objective",
        index=6,
        description="What 'good' means: scores computed in objectives.py.",
        allowed_values={
            "scores": ("defect_signal_score", "penalty", "science_utility",
                       "stability_score", "cost_efficiency",
                       "interpretability_score"),
            "signal_inputs": ("dislocation_count", "total_line_length",
                              "hcp_fraction", "other_fraction",
                              "plastic_zone_detected", "stacking_fault_indicator"),
        },
        prerequisites=("fidelity",),
        cost_level="none",
        risk_level="low",
        scientific_value="high",
        promotion_rules=(
            "science_utility >= min_science_utility_for_production gates "
            "design-branch escalation.",
            "science_utility >= min_science_utility_for_large_confirmation "
            "gates A2 confirmation.",
        ),
        stop_rules=(
            "Penalty terms (instability, hang, cuda_error, nan, lost atoms, "
            "runtime) can never be traded away by a strong signal alone.",
        ),
    ))

    stack.add(Layer(
        name="decision_policy",
        index=7,
        description="Rule-based policy v1 (decision_policy.py); v2 hooks for "
                    "Bayesian/Hyperband exist as placeholders.",
        allowed_values={
            "action": ("promote", "stop", "retry", "pivot",
                       "confirm_on_larger_scale", "require_manual_review"),
            "promotion_label": ("reject", "retry", "promote_to_short",
                                "promote_to_production", "confirm_large",
                                "pivot_to_realism", "manual_review"),
        },
        prerequisites=("objective",),
        cost_level="none",
        risk_level="low",
        scientific_value="medium",
        promotion_rules=(
            "Every decision must state: what next, why, fidelity, expected "
            "cost, stop conditions, and whether human approval is required.",
        ),
        stop_rules=(
            "Repeated hangs (> max_hangs_per_branch) stop the branch.",
            "Branch failure rate > max_failure_rate_per_branch stops the branch.",
            "Disk/runtime over budget requires manual review or stops the branch.",
        ),
    ))

    stack.validate()
    return stack
