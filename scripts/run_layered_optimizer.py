#!/usr/bin/env python
"""CLI for the layered multi-fidelity optimizer (planner/scheduler layer).

PLANNER ONLY. This script never launches LAMMPS, never spawns subprocesses,
and never touches active run roots. It reads the policy config, builds the
layer model, scores mock results, and exports a planned queue as data.

Usage:
    .venv\\Scripts\\python.exe scripts\\run_layered_optimizer.py \
        --config configs\\layered_optimizer_policy.yaml --plan-only
    ... --dry-run        plan + mock scenarios + write dry-run artifacts
    ... --score-mock     run the 4 canonical mock scenarios, print decisions
    ... --export-queue   write planned_queue.yaml / planned_trials.jsonl /
                         decision_report.md (no execution)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

import yaml  # noqa: E402

from science_optimizer import PLANNER_NAME, __version__  # noqa: E402
from science_optimizer import fidelity as fid  # noqa: E402
from science_optimizer.layers import build_layer_stack  # noqa: E402
from science_optimizer.decision_policy import run_mock_scenarios  # noqa: E402
from science_optimizer.export_queue import (  # noqa: E402
    ACTIVE_RUN_ROOT, build_planned_queue, export_dry_run)


class PolicyConfigError(RuntimeError):
    pass


REQUIRED_SECTIONS = ("experiment", "optimizer", "layers", "thresholds",
                     "policy", "costs")
REQUIRED_THRESHOLDS = ("min_science_utility_for_production",
                       "min_science_utility_for_large_confirmation",
                       "max_failure_rate_per_branch", "max_hangs_per_branch")


def load_policy_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise PolicyConfigError(f"config file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise PolicyConfigError("config root must be a YAML mapping")

    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise PolicyConfigError(f"missing config sections: {missing}")
    missing_thr = [k for k in REQUIRED_THRESHOLDS if k not in cfg["thresholds"]]
    if missing_thr:
        raise PolicyConfigError(f"missing thresholds: {missing_thr}")

    # Hard safety rails: this layer must stay a planner.
    if cfg["experiment"].get("mode") != "planner_only":
        raise PolicyConfigError(
            "experiment.mode must be 'planner_only'; this tool never runs MD")
    if cfg["optimizer"].get("no_md_execution") is not True:
        raise PolicyConfigError(
            "optimizer.no_md_execution must be true; this tool never runs MD")

    # Same eps sanity range the stage_runner enforces.
    for e in cfg["layers"]["eps"]["values"]:
        if not isinstance(e, (int, float)) or e < 0.0 or e > 0.02:
            raise PolicyConfigError(f"eps value out of sane range [0, 0.02]: {e}")

    cfg["_config_path"] = str(p.resolve())
    return cfg


def print_plan(cfg: dict) -> None:
    stack = build_layer_stack(cfg)
    fladder = fid.build_fidelity_ladder(cfg)
    sladder = fid.build_size_ladder(cfg)
    items, notes = build_planned_queue(cfg)

    print(f"=== {PLANNER_NAME} v{__version__} ===")
    print(f"mode: planner_only | NO MD EXECUTION | policy: "
          f"{cfg['optimizer']['method']} | seed: {cfg['optimizer']['seed']}")
    print(f"config: {cfg['_config_path']}")
    print(f"active run root untouched: {ACTIVE_RUN_ROOT}")
    print()
    print("-- Layer stack (L0..L7) --")
    print(stack.summary())
    print()
    print("-- Fidelity ladder --")
    for lvl in fladder.values():
        extra = (f" @ atoms {list(lvl.atom_targets)}" if lvl.atom_targets else "")
        print(f"  {lvl.name:<20} {lvl.steps:>7} steps{extra}  : {lvl.purpose}")
    print()
    print("-- Size ladder --")
    for st in sladder.values():
        print(f"  {st.name:<10} {list(st.atom_targets)!s:<28} : {st.role}")
    print()
    print("-- Planned queue (DRY DATA, nothing executed) --")
    print(f"  items: {notes['item_count']} | manual approval: "
          f"{notes['manual_approval_items']} | est upper bound: "
          f"~{notes['estimated_gpu_hours_if_everything_ran']} GPU-hours")
    print(f"  by stage:    {notes['by_stage']}")
    print(f"  by fidelity: {notes['by_fidelity']}")
    print("  first 10 items:")
    for it in items[:10]:
        manual = " [MANUAL]" if it.requires_manual_approval else ""
        print(f"    {it.trial_id:<44} {it.expected_runtime_class:<12}{manual}")
    print(f"  note: {notes['a0_note']}")
    print(f"  note: {notes['conditional_note']}")


def print_mock_scores(cfg: dict) -> None:
    print("-- Mock decision scenarios (rule_based_policy_v1) --")
    for rec in run_mock_scenarios(cfg):
        d = rec["decision"]
        s = d["scores"]
        print()
        print(rec["title"])
        print(f"  utility={s['science_utility']} (signal={s['defect_signal_score']}, "
              f"penalty={s['penalty']}, detected={s['has_defect_signal']}) "
              f"stability={s['stability_score']}")
        print(f"  decision: {d['action']} | label={d['promotion_label']} | "
              f"approval={'YES' if d['requires_human_approval'] else 'no'}")
        print(f"  why: {d['reason']}")
        for nt in d.get("next_trials", []):
            print(f"  next: {nt['fidelity']} @ {nt['atom_target']} atoms "
                  f"eps_z={nt['eps_z']} variant={nt.get('realism_variant')} "
                  f"design={nt.get('design', {})}")
        if "second_event_decision" in rec:
            d2 = rec["second_event_decision"]
            print(f"  second identical event -> {d2['action']} "
                  f"(label={d2['promotion_label']})")
        print(f"  expected: {rec['expected']}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(
        prog="run_layered_optimizer",
        description="Layered multi-fidelity optimizer - planner only, no MD.")
    ap.add_argument("--config", required=True,
                    help="configs/layered_optimizer_policy.yaml")
    ap.add_argument("--plan-only", action="store_true",
                    help="print layers/ladders/queue summary; write nothing")
    ap.add_argument("--dry-run", action="store_true",
                    help="plan + mock scenarios + write dry-run artifacts")
    ap.add_argument("--score-mock", action="store_true",
                    help="score the 4 canonical mock scenarios; write nothing")
    ap.add_argument("--export-queue", action="store_true",
                    help="write planned_queue.yaml/planned_trials.jsonl/"
                         "decision_report.md")
    args = ap.parse_args(argv)

    if not (args.plan_only or args.dry_run or args.score_mock or args.export_queue):
        ap.error("choose at least one of --plan-only / --dry-run / "
                 "--score-mock / --export-queue")

    try:
        cfg = load_policy_config(args.config)
    except PolicyConfigError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    if args.plan_only or args.dry_run:
        print_plan(cfg)
        print()

    if args.score_mock or args.dry_run:
        print_mock_scores(cfg)
        print()

    if args.dry_run or args.export_queue:
        paths = export_dry_run(cfg, REPO_ROOT)
        print("-- Dry-run artifacts written (NO execution) --")
        for name, p in paths.items():
            print(f"  {name}: {p.relative_to(REPO_ROOT)}")
        print()

    if args.plan_only and not (args.dry_run or args.export_queue):
        print("plan-only: no files written.")
    print("DONE: planner_only, no LAMMPS/MD was launched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
