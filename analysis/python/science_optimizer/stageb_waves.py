"""Stage B v2 staged-wave and candidate generation (proposal data only)."""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping

from . import stageb_policy as sp
from .stageb_models import StageBCandidate, StageBWave


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
    axes = sp.axes(policy)
    baseline = sp.baseline(policy)
    eps_priority = list(sp.stage_b(policy)["eps"]["priority"])
    atom_target = int(sp.stage_b(policy)["atom_targets"]["default"][0])

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
        for eps in sp.stage_b(policy)["eps"]["threshold_refinement"]
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
