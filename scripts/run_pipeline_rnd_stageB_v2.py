#!/usr/bin/env python
"""CLI for the Stage B-aware R&D planner v2.

Planner only. This script never launches LAMMPS, never spawns subprocesses,
and never touches active run roots. It reads the Stage B v2 policy template and
exports proposal data under runs/pipeline_rnd_stageB/dry_run_<timestamp>/.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from science_optimizer.pipeline_rnd_stageB_v2 import (  # noqa: E402
    StageBPolicyError,
    estimate_wave_cost,
    export_dry_run_outputs,
    generate_mock_decision_scenarios,
    generate_stageB_queue,
    generate_stageB_waves,
    load_policy,
    make_strategy_summary,
)


DEFAULT_POLICY = REPO_ROOT / "configs" / "pipeline_rnd_stageB_v2_policy.template.yaml"


def _print_header(policy: Mapping[str, Any]) -> None:
    print("=== pipeline_rnd_stageB_v2 ===")
    print("mode: planner_only | no MD execution | no subprocess launch")
    print(f"policy: {policy['_policy_path']}")
    print("active run roots: untouched")
    print()


def _print_plan(policy: Mapping[str, Any]) -> None:
    summary = make_strategy_summary(policy)
    waves = generate_stageB_waves(policy)
    _print_header(policy)
    print("-- Stage A gate --")
    gate = summary["stage_A_gate"]
    print(f"  current target: {gate['current_next_target']}")
    print(f"  priority eps: {gate['priority_eps']}")
    print(f"  short enabled: {gate['short_enabled']}")
    print()
    print("-- Stage B axes --")
    for key, values in summary["stage_B_axes"].items():
        print(f"  {key}: {values}")
    print()
    print("-- Staged waves --")
    for wave in waves:
        print(
            f"  {wave['name']:<25} candidates={wave['candidate_count']:<3} "
            f"smoke_all={wave['smoke_all']} production_slots={wave['production_slots']}"
        )
        print(f"    depends_on: {wave['depends_on']}")
        print(f"    purpose: {wave['purpose']}")
    print()
    print("-- Disabled/gated --")
    for item in summary["disabled_or_gated"]:
        print(f"  - {item}")
    print()
    print("plan-only: no files written.")


def _print_cost_model(policy: Mapping[str, Any]) -> None:
    costs = estimate_wave_cost(policy)
    _print_header(policy)
    print("-- Single run estimates --")
    for key, rec in costs["single_runs"].items():
        print(f"  {key:<36} ~{rec['estimated_hours']} h")
    print()
    print("-- Stage B wave estimates --")
    for key, rec in costs["stage_B_waves"].items():
        print(
            f"  {key:<28} smoke={rec['smoke_only_hours']} h | "
            f"smoke+early={rec['smoke_plus_early_gate_hours']} h | "
            f"smoke+selected production={rec['smoke_plus_selected_production_hours']} h"
        )
    print()
    full = costs["full_factorial_rejected"]
    comp = costs["comparison"]
    print("-- Rejected full factorial --")
    print(f"  cases: {full['case_count']} ({full['axis_counts']})")
    print(f"  smoke+production: ~{full['smoke_plus_production_hours']} h")
    print(f"  staged B1-B4 alternative: ~{comp['B1_to_B4_staged_smoke_plus_winners_hours']} h")
    print(f"  rejected/staged ratio: ~{comp['factorial_to_staged_ratio']}x")
    print()
    print("cost-model: no files written.")


def _print_mock_decisions(policy: Mapping[str, Any]) -> None:
    scenarios = generate_mock_decision_scenarios(policy)
    _print_header(policy)
    print("-- Mock decision scenarios --")
    for scenario in scenarios:
        rec = scenario["recommendation"]
        scores = rec["scores"]
        print()
        print(scenario["name"])
        print(f"  expected: {scenario['expected']}")
        print(
            f"  utility={scores['science_utility']} "
            f"signal={scores['has_defect_signal']} "
            f"stability={scores['stability_score']}"
        )
        print(
            f"  label={rec['promotion_label']} "
            f"approval={'YES' if rec['requires_manual_approval'] else 'no'} "
            f"next_waves={rec['next_waves']}"
        )
        for action in rec["actions"]:
            print(f"  - {action}")
    print()
    print("mock-decisions: no files written.")


def _new_output_dir(policy: Mapping[str, Any],
                    output_root: str | None = None) -> Path:
    if output_root:
        root = Path(output_root)
    else:
        root = Path(policy.get("output", {}).get("root", "runs/pipeline_rnd_stageB"))
    if not root.is_absolute():
        root = REPO_ROOT / root
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = root / f"dry_run_{ts}"
    n = 1
    while out.exists():
        n += 1
        out = root / f"dry_run_{ts}-{n}"
    return out


def _export(policy: Mapping[str, Any],
            output_root: str | None = None) -> dict[str, Path]:
    out = _new_output_dir(policy, output_root)
    return export_dry_run_outputs(policy, out)


def _print_export_result(paths: Mapping[str, Path]) -> None:
    print("-- Dry-run artifacts written (NO execution) --")
    for name, path in paths.items():
        try:
            shown: Path = path.relative_to(REPO_ROOT)
        except ValueError:
            shown = path
        print(f"  {name}: {shown}")
    print()


def _print_queue_preview(policy: Mapping[str, Any]) -> None:
    queue = generate_stageB_queue(policy)
    print("-- Stage B queue preview --")
    print(f"  items: {len(queue)}")
    for item in queue[:12]:
        print(
            f"  {item['queue_id']:<42} {item['wave']:<25} "
            f"{item['fidelity']:<22} steps={item['steps']}"
        )
    if len(queue) > 12:
        print(f"  ... {len(queue) - 12} more items in stageB_queue.jsonl")
    print()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="run_pipeline_rnd_stageB_v2",
        description="Stage B-aware R&D planner v2 - planner only, no MD.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_POLICY),
        help="Stage B v2 policy template path",
    )
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--cost-model", action="store_true")
    parser.add_argument("--mock-decisions", action="store_true")
    parser.add_argument("--export-policy", action="store_true")
    parser.add_argument("--generate-stageB-queue", action="store_true")
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            "override dry-run output root (default: policy output.root under "
            "the repo). Only affects --export-policy / --generate-stageB-queue."
        ),
    )
    args = parser.parse_args(argv)

    if not any((
        args.plan_only,
        args.cost_model,
        args.mock_decisions,
        args.export_policy,
        args.generate_stageB_queue,
    )):
        parser.error(
            "choose at least one of --plan-only / --cost-model / "
            "--mock-decisions / --export-policy / --generate-stageB-queue"
        )

    try:
        policy = load_policy(args.config)
    except StageBPolicyError as exc:
        print(f"POLICY ERROR: {exc}", file=sys.stderr)
        return 2

    if args.plan_only:
        _print_plan(policy)
    if args.cost_model:
        _print_cost_model(policy)
    if args.mock_decisions:
        _print_mock_decisions(policy)
    if args.export_policy:
        _print_header(policy)
        paths = _export(policy, args.output_root)
        _print_export_result(paths)
    if args.generate_stageB_queue:
        _print_header(policy)
        _print_queue_preview(policy)
        paths = _export(policy, args.output_root)
        _print_export_result(paths)

    print("DONE: planner_only, no LAMMPS/MD was launched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
