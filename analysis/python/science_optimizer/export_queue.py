"""Planned-queue generation and dry-run export (NO execution).

Generates the recommended next trials as data only:

    runs/science_optimizer/dry_run_{timestamp}/planned_queue.yaml
    runs/science_optimizer/dry_run_{timestamp}/planned_trials.jsonl
    runs/science_optimizer/dry_run_{timestamp}/decision_report.md

The queue intentionally does NOT duplicate the in-flight A0 sweep
(runs/stage_sweep_gpu_grid/20260611-175339): A0 is treated as covered.
Waves:

    P1 A1_small        gated on the A0 production review
    P2 A1_medium       gated on A1_small; productions need per-case gates
    P3a signal branch  IF A1_medium shows signal: A2 confirmation + Stage B B1/B2
    P3b pivot branch   IF A1_medium shows NO signal: Stage B B3/B4 realism pivot

No full factorial: each wave changes one high-value axis at a time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from . import __version__, PLANNER_NAME
from . import fidelity as fid
from .decision_policy import run_mock_scenarios, STANDARD_STOP_CONDITIONS

# gpu_grid A2_large uses a shorter "short" rung than the global ladder
# (configs/stage_sweep_gpu_grid.yaml: A2_large.short_steps: 10000).
A2_SHORT_STEPS = 10000

ACTIVE_RUN_ROOT = "runs/stage_sweep_gpu_grid/20260611-175339"
GPU_GRID_CONFIG = "configs/stage_sweep_gpu_grid.yaml"
STAGE_B_TEMPLATE = "configs/stage_sweep_inclusion_design.template.yaml"


@dataclass
class QueueItem:
    trial_id: str
    reason: str
    stage: str
    atom_target: int
    eps_z: float
    inclusion_size_nm: float | None
    shape: str | None
    position: str | None
    predefect_variant: str | None
    composition: str | None
    fidelity: str
    steps: int
    expected_runtime_class: str
    requires_manual_approval: bool
    runner_config_patch: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _eps_tag(eps: float) -> str:
    return f"eps{int(round(eps * 10000)):04d}"


def _steps_for(cfg: Mapping[str, Any], fidelity: str, stage: str) -> int:
    ladder = fid.build_fidelity_ladder(cfg)
    if fidelity == "short" and stage.startswith("A2"):
        return A2_SHORT_STEPS
    return ladder[fidelity].steps


class QueueBuilder:
    def __init__(self, cfg: Mapping[str, Any]):
        self.cfg = cfg
        self.items: list[QueueItem] = []
        self._n = 0
        self.size_ladder = fid.build_size_ladder(cfg)

    def _add(self, *, stage: str, size_stage: str, atom_target: int,
             eps_z: float, fidelity: str, reason: str,
             requires_manual_approval: bool,
             inclusion_size_nm: float | None = None,
             shape: str | None = "ellipsoid_1_1_2",
             position: str | None = "grain_interior",
             predefect_variant: str | None = "perfect",
             composition: str | None = "Fe4Al13",
             patch: dict[str, Any] | None = None,
             id_suffix: str = "") -> QueueItem:
        self._n += 1
        steps = _steps_for(self.cfg, fidelity, size_stage)
        cost = fid.expected_cost(self.cfg, atom_target, steps, fidelity,
                                 size_stage)
        if cost["over_budget"]:
            reason += (f" NOTE: est ~{cost['estimated_hours']}h exceeds the "
                       f"{cost['session_budget_hours']:.0f}h session budget -> "
                       "chunked multi-session run via restart/resume.")
        trial_id = (f"T{self._n:03d}_{stage}_n{atom_target // 1000}k_"
                    f"{_eps_tag(eps_z)}_{fidelity}{id_suffix}")
        item = QueueItem(
            trial_id=trial_id, reason=reason, stage=stage,
            atom_target=atom_target, eps_z=eps_z,
            inclusion_size_nm=inclusion_size_nm, shape=shape,
            position=position, predefect_variant=predefect_variant,
            composition=composition, fidelity=fidelity, steps=steps,
            expected_runtime_class=cost["runtime_class"],
            requires_manual_approval=requires_manual_approval,
            runner_config_patch=patch or {})
        self.items.append(item)
        return item

    # -- waves -------------------------------------------------------------

    def wave_p1_a1_small(self) -> None:
        eps_pair = [float(self.cfg["layers"]["eps"]["physical_main"]),
                    float(self.cfg["layers"]["eps"]["overload"][-1])]
        gate = "P1 gate: A0 production reviewed (covered by active sweep)."
        sizes = self.size_ladder["A1_small"].atom_targets
        for fidelity in ("smoke", "short"):
            for atoms in sizes:
                for eps in eps_pair:
                    prereq = ("" if fidelity == "smoke"
                              else " Runs only after the matching smoke passes.")
                    self._add(
                        stage="A1_small", size_stage="A1_small",
                        atom_target=atoms, eps_z=eps, fidelity=fidelity,
                        reason=f"{gate} First size-effect rung at {atoms} "
                               f"atoms, eps_z={eps}.{prereq}",
                        requires_manual_approval=False,
                        patch={"target_config": GPU_GRID_CONFIG,
                               "stages": {"A1_small": {
                                   "atom_targets": [atoms],
                                   "eps_z": [eps]}}})
        prod_atoms = sizes[0]
        for eps in eps_pair:
            self._add(
                stage="A1_small", size_stage="A1_small",
                atom_target=prod_atoms, eps_z=eps, fidelity="production",
                reason=f"{gate} select_first_stable_for_full_production: "
                       f"production at the first stable size ({prod_atoms}); "
                       f"switch to {sizes[-1]} only if {prod_atoms} is "
                       "unstable. Requires smoke+short pass.",
                requires_manual_approval=False,
                patch={"target_config": GPU_GRID_CONFIG,
                       "stages": {"A1_small": {
                           "atom_targets": [prod_atoms], "eps_z": [eps]}}})

    def wave_p2_a1_medium(self) -> None:
        eps_pair = [float(self.cfg["layers"]["eps"]["physical_main"]),
                    float(self.cfg["layers"]["eps"]["overload"][-1])]
        gate = "P2 gate: A1_small production stable and reviewed."
        sizes = self.size_ladder["A1_medium"].atom_targets
        for fidelity in ("smoke", "short", "production"):
            for atoms in sizes:
                for eps in eps_pair:
                    manual = fidelity == "production"
                    extra = (" gate_required_before_each_production: each "
                             "A1_medium production needs an explicit gate "
                             "review (main scientific gate)."
                             if manual else "")
                    self._add(
                        stage="A1_medium", size_stage="A1_medium",
                        atom_target=atoms, eps_z=eps, fidelity=fidelity,
                        reason=f"{gate} Main scientific gate at {atoms} "
                               f"atoms, eps_z={eps}.{extra}",
                        requires_manual_approval=manual,
                        patch={"target_config": GPU_GRID_CONFIG,
                               "stages": {"A1_medium": {
                                   "atom_targets": [atoms],
                                   "eps_z": [eps]}}})

    def wave_p3a_signal(self) -> None:
        eps_main = float(self.cfg["layers"]["eps"]["physical_main"])
        gate = ("P3a CONDITIONAL wave: only IF A1_medium production shows a "
                "defect signal (science_utility >= "
                f"{self.cfg['thresholds']['min_science_utility_for_large_confirmation']}).")
        a2 = self.size_ladder["A2_large"].atom_targets
        atoms_500k = a2[0]
        for fidelity, why in (
                ("smoke", "stability check before any large run"),
                ("short", "medium confirmation before committing ~60h"),
                ("large_confirmation", "size-effect confirmation ONLY")):
            self._add(
                stage="A2_large", size_stage="A2_large",
                atom_target=atoms_500k, eps_z=eps_main, fidelity=fidelity,
                reason=f"{gate} 500k {why}.",
                requires_manual_approval=True,
                patch={"target_config": GPU_GRID_CONFIG,
                       "stages": {"A2_large": {
                           "atom_targets": [atoms_500k],
                           "eps_z": [eps_main]}}})
        atoms_700k = a2[-1]
        self._add(
            stage="A2_large", size_stage="A2_large",
            atom_target=atoms_700k, eps_z=eps_main, fidelity="smoke",
            reason=f"{gate} 700k smoke ONLY after 500k is stable AND remains "
                   "informative; never a blind default.",
            requires_manual_approval=True,
            patch={"target_config": GPU_GRID_CONFIG,
                   "stages": {"A2_large": {
                       "atom_targets": [atoms_700k], "eps_z": [eps_main]}}})
        # Stage B, one axis at a time: B1 inclusion size first, at the cheap
        # informative size (120k), physical-main eps only.
        b_atoms = self.size_ladder["A1_small"].atom_targets[-1]
        for size_nm in self.cfg["layers"]["inclusion_design"]["sizes_nm"]:
            self._add(
                stage="B1_size", size_stage="A1_small",
                atom_target=b_atoms, eps_z=eps_main, fidelity="smoke",
                inclusion_size_nm=float(size_nm),
                reason=f"{gate} Stage B axis 1 (inclusion size {size_nm} nm) "
                       "at the cheap informative size; one axis at a time.",
                requires_manual_approval=True,
                patch={"target_config": f"copy of {STAGE_B_TEMPLATE}",
                       "stages": {"B1_size": {
                           "enabled": True,
                           "atom_targets": [b_atoms],
                           "inclusion_sizes_nm": [size_nm],
                           "eps_z": [eps_main]}}},
                id_suffix=f"_inc{size_nm}nm")
        for shape in ("sphere", "platelet"):
            self._add(
                stage="B2_shape", size_stage="A1_small",
                atom_target=b_atoms, eps_z=eps_main, fidelity="smoke",
                inclusion_size_nm=None, shape=shape,
                reason=f"{gate} Stage B axis 2 (shape={shape}) using the best "
                       "B1 inclusion size (inclusion_size_nm decided after "
                       "B1); ellipsoid_1_1_2 is the existing baseline.",
                requires_manual_approval=True,
                patch={"target_config": f"copy of {STAGE_B_TEMPLATE}",
                       "stages": {"B2_shape": {
                           "enabled": True,
                           "shapes": [shape],
                           "inclusion_sizes_nm": ["from_B1_best_or_signal"],
                           "eps_z": [eps_main]}}},
                id_suffix=f"_{shape}")

    def wave_p3b_pivot(self) -> None:
        eps_main = float(self.cfg["layers"]["eps"]["physical_main"])
        eps_over = float(self.cfg["layers"]["eps"]["overload"][-1])
        gate = ("P3b CONDITIONAL wave: only IF A1_medium production is "
                "stable with NO defect signal (pivot_to_realism). Takes "
                "priority over any 700k ideal-monocrystal escalation.")
        atoms = 250000  # representative A1_medium size where the null result came from
        for eps in (eps_main, eps_over):
            self._add(
                stage="B3_position", size_stage="A1_medium",
                atom_target=atoms, eps_z=eps, fidelity="smoke",
                position="near_grain_boundary",
                reason=f"{gate} Realism axis: same inclusion near a grain "
                       f"boundary, eps_z={eps}.",
                requires_manual_approval=True,
                patch={"target_config": f"copy of {STAGE_B_TEMPLATE}",
                       "stages": {"B3_position": {
                           "enabled": True,
                           "positions": ["near_grain_boundary"],
                           "eps_z": [eps]}}},
                id_suffix="_near_gb")
        for variant in ("vacancies_medium", "seed_dislocation_if_available"):
            self._add(
                stage="B4_predefects", size_stage="A1_medium",
                atom_target=atoms, eps_z=eps_main, fidelity="smoke",
                predefect_variant=variant,
                reason=f"{gate} Realism axis: predefects ({variant}) lower "
                       "the nucleation threshold in real material.",
                requires_manual_approval=True,
                patch={"target_config": f"copy of {STAGE_B_TEMPLATE}",
                       "stages": {"B4_predefects": {
                           "enabled": True,
                           "variants": [variant],
                           "eps_z": [eps_main]}}},
                id_suffix=f"_{variant.split('_')[0]}")


def build_planned_queue(cfg: Mapping[str, Any]) -> tuple[list[QueueItem], dict[str, Any]]:
    b = QueueBuilder(cfg)
    b.wave_p1_a1_small()
    b.wave_p2_a1_medium()
    b.wave_p3a_signal()
    b.wave_p3b_pivot()

    by_stage: dict[str, int] = {}
    by_fidelity: dict[str, int] = {}
    manual = 0
    est_hours_total = 0.0
    for it in b.items:
        by_stage[it.stage] = by_stage.get(it.stage, 0) + 1
        by_fidelity[it.fidelity] = by_fidelity.get(it.fidelity, 0) + 1
        if it.requires_manual_approval:
            manual += 1
        est_hours_total += fid.estimate_runtime_hours(cfg, it.atom_target, it.steps)
    notes = {
        "item_count": len(b.items),
        "by_stage": by_stage,
        "by_fidelity": by_fidelity,
        "manual_approval_items": manual,
        "estimated_gpu_hours_if_everything_ran": round(est_hours_total, 1),
        "a0_note": ("A0_24k items are intentionally absent: the active sweep "
                    f"({ACTIVE_RUN_ROOT}) already runs A0 production for all "
                    "five eps values."),
        "conditional_note": ("P3a and P3b are mutually exclusive conditional "
                             "waves keyed to the A1_medium gate outcome; the "
                             "estimated total above is therefore an upper bound."),
    }
    return b.items, notes


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _output_dir(cfg: Mapping[str, Any], repo_root: Path,
                timestamp: str | None = None) -> Path:
    root = Path(cfg.get("output", {}).get("root", "runs/science_optimizer"))
    if not root.is_absolute():
        root = repo_root / root
    ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    out = root / f"dry_run_{ts}"
    n = 1
    while out.exists():
        n += 1
        out = root / f"dry_run_{ts}-{n}"
    return out


def write_planned_queue_yaml(path: Path, cfg: Mapping[str, Any],
                             items: list[QueueItem],
                             notes: Mapping[str, Any]) -> None:
    doc = {
        "planner": f"{PLANNER_NAME} v{__version__}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "planner_only",
        "no_md_execution": True,
        "policy": cfg["optimizer"]["method"],
        "seed": cfg["optimizer"]["seed"],
        "source_config": cfg.get("_config_path", "configs/layered_optimizer_policy.yaml"),
        "active_run_root_untouched": ACTIVE_RUN_ROOT,
        "summary": dict(notes),
        "items": [it.as_dict() for it in items],
    }
    header = ("# Planned runner queue (DRY RUN - nothing here was executed).\n"
              "# Generated by the layered multi-fidelity optimizer planner.\n"
              "# P3a/P3b are conditional waves; see summary.conditional_note.\n")
    path.write_text(header + yaml.safe_dump(doc, sort_keys=False,
                                            allow_unicode=True),
                    encoding="utf-8")


def write_planned_trials_jsonl(path: Path, items: list[QueueItem]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it.as_dict(), ensure_ascii=False) + "\n")


def _fmt_scenario(rec: Mapping[str, Any]) -> str:
    d = rec["decision"]
    lines = [f"### {rec['title']}", ""]
    ctx = rec["context"]
    r = rec["result"]
    interesting = {k: v for k, v in r.items()
                   if v not in (0, 0.0, False, None, "") or k in
                   ("stable", "runtime_hours", "dislocation_count")}
    lines += [
        "Input (mock):",
        "",
        f"- context: stage={ctx['size_stage']}, atoms={ctx['atom_target']}, "
        f"eps_z={ctx['eps_z']}, fidelity={ctx['fidelity']}",
        f"- result: `{interesting}`",
        "",
        f"Scores: defect_signal={d['scores']['defect_signal_score']}, "
        f"penalty={d['scores']['penalty']}, "
        f"science_utility={d['scores']['science_utility']}, "
        f"signal_detected={d['scores']['has_defect_signal']}",
        "",
        f"Decision: **{d['action']}** (label `{d['promotion_label']}`, "
        f"human approval: {'YES' if d['requires_human_approval'] else 'no'})",
        "",
        f"- why: {d['reason']}",
    ]
    if d.get("required_fidelity"):
        lines.append(f"- required fidelity: {d['required_fidelity']}")
    if d.get("expected_cost"):
        lines.append(f"- expected cost: {d['expected_cost']}")
    for nt in d.get("next_trials", []):
        cost = nt.get("expected_cost", {})
        lines.append(
            f"- next: {nt['fidelity']} @ {nt['atom_target']} atoms, "
            f"eps_z={nt['eps_z']}, variant={nt.get('realism_variant')}, "
            f"design={nt.get('design', {})}, est ~{cost.get('estimated_hours')}h")
    if "second_event_decision" in rec:
        d2 = rec["second_event_decision"]
        lines += [
            "",
            f"Second identical event in the same branch -> **{d2['action']}** "
            f"(label `{d2['promotion_label']}`): {d2['reason']}",
        ]
    lines += ["", f"Expected (spec): {rec['expected']}", ""]
    return "\n".join(lines)


def write_decision_report(path: Path, cfg: Mapping[str, Any],
                          items: list[QueueItem], notes: Mapping[str, Any],
                          scenario_records: list[Mapping[str, Any]]) -> None:
    n_prev = 12
    lines: list[str] = []
    lines += [
        "# Layered optimizer dry-run decision report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Planner: {PLANNER_NAME} v{__version__} "
        f"(policy: {cfg['optimizer']['method']}, seed {cfg['optimizer']['seed']})",
        "",
        "Mode: `planner_only`. **No MD was executed.** The active run root "
        f"`{ACTIVE_RUN_ROOT}` was not touched.",
        "",
        "## Planning assumptions",
        "",
        f"- {notes['a0_note']}",
        "- Production never runs before its smoke+short rungs pass "
        "(fidelity ladder rule).",
        "- A1_medium productions each require an explicit human gate "
        "(`gate_required_before_each_production`).",
        f"- {notes['conditional_note']}",
        "- Failed / hung / nan / lost-atoms / cuda-error trials are rejected; "
        "a single recovered hang earns exactly one same-fidelity retry.",
        "",
        "## Queue summary",
        "",
        f"- planned items: **{notes['item_count']}**",
        f"- by stage: {notes['by_stage']}",
        f"- by fidelity: {notes['by_fidelity']}",
        f"- items requiring manual approval: {notes['manual_approval_items']}",
        f"- estimated GPU hours if every item ran (upper bound, both "
        f"conditional waves counted): ~{notes['estimated_gpu_hours_if_everything_ran']}h",
        "",
        f"First {n_prev} items:",
        "",
        "| trial_id | stage | fidelity | atoms | eps_z | runtime class | manual |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for it in items[:n_prev]:
        lines.append(
            f"| {it.trial_id} | {it.stage} | {it.fidelity} | {it.atom_target} "
            f"| {it.eps_z} | {it.expected_runtime_class} "
            f"| {'YES' if it.requires_manual_approval else ''} |")
    lines += [
        "",
        "Full list: `planned_queue.yaml` / `planned_trials.jsonl`.",
        "",
        "## Decision scenarios (mock results through rule_based_policy_v1)",
        "",
    ]
    for rec in scenario_records:
        lines.append(_fmt_scenario(rec))
    lines += [
        "## Standard branch stop conditions",
        "",
    ]
    lines += [f"- {c}" for c in STANDARD_STOP_CONDITIONS]
    lines += [
        "",
        "## Why this is not Bayesian optimization yet",
        "",
        "- v1 is a deterministic **rule-based layered planner**: the search "
        "space is still tiny and gate-driven, and almost every decision is "
        "dominated by stability and cost constraints, not by a smooth "
        "objective a surrogate model could exploit.",
        "- There are not yet enough completed production trials with "
        "`science_utility` values to fit any surrogate (GP/TPE) without it "
        "just reproducing the priors; rule-of-thumb: ~15-20 completed "
        "production-fidelity trials across eps/size/design axes first.",
        "- v2 can plug in behind the same `Decision` interface: "
        "`bayesian_optimizer_v2` (GP/TPE expected-improvement proposals) or "
        "`hyperband_v2` (successive halving over the existing "
        "smoke/short/production budget ladder). Both placeholders exist in "
        "`decision_policy.py` and intentionally raise `NotImplementedError`.",
        "- No Optuna/BoTorch/Ax dependency is added in this task; the "
        "implementation stays dependency-light (stdlib + PyYAML).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def export_dry_run(cfg: Mapping[str, Any], repo_root: Path,
                   timestamp: str | None = None) -> dict[str, Path]:
    """Build the queue + scenarios and write the three dry-run artifacts."""
    items, notes = build_planned_queue(cfg)
    scenarios = run_mock_scenarios(cfg)
    out_dir = _output_dir(cfg, repo_root, timestamp)
    out_dir.mkdir(parents=True, exist_ok=False)
    paths = {
        "planned_queue": out_dir / "planned_queue.yaml",
        "planned_trials": out_dir / "planned_trials.jsonl",
        "decision_report": out_dir / "decision_report.md",
    }
    write_planned_queue_yaml(paths["planned_queue"], cfg, items, notes)
    write_planned_trials_jsonl(paths["planned_trials"], items)
    write_decision_report(paths["decision_report"], cfg, items, notes, scenarios)
    return paths
