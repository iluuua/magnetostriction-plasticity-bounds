"""Explicit data models for the Stage B v2 planner.

Pure dataclasses: no logic, no I/O, no dependencies beyond the stdlib. Each
model exposes ``as_dict()`` so the planner keeps emitting plain,
JSON/YAML-serializable structures (dry-run output semantics unchanged). Field
order matches the historical dict key order so exported artifacts stay
byte-stable apart from timestamps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RuntimeEstimate:
    """One runtime/cost line for a single run or a wave rung."""

    name: str
    atom_count: int
    steps: int
    overhead_factor: float
    estimated_steps_per_s: float
    estimated_hours: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageBCandidate:
    """One proposed Stage B design point (proposal-only; never executed)."""

    candidate_id: str
    wave: str
    varied_axis: str
    atom_target: int
    eps: float
    inclusion_size_nm: Any
    shape: Any
    position: Any
    predefect: Any
    inclusion_count: Any
    composition: str
    manual_approval_required: bool = True
    no_md_execution: bool = True
    status: str = "proposal_only"
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageBWave:
    """A staged wave (varies one axis) holding its candidate proposals."""

    name: str
    purpose: str
    depends_on: str
    priority_if: str | None
    smoke_all: bool
    production_slots: int
    candidate_count: int
    candidates: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScienceUtilityScore:
    """Science-utility scoring result for one (mock or real) trial."""

    defect_signal_score: float
    penalty: float
    science_utility: float
    stability_score: float
    cost_efficiency: float
    interpretability_score: float
    has_defect_signal: bool
    promotion_label: str
    components: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    """A Stage B-aware recommendation derived from a trial result."""

    promotion_label: str
    requires_manual_approval: bool
    actions: list[str]
    next_waves: list[str]
    scores: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
