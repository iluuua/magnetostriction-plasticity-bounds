"""Tests for the Stage B-aware R&D planner v2 (planner only, no MD).

Dual-mode: collected normally by pytest, and also runnable standalone with
``.venv\\Scripts\\python.exe tests\\science_optimizer\\test_pipeline_rnd_stageB_v2.py``
(a stdlib runner at the bottom executes every ``test_*`` function). This keeps
the planner verifiable without adding a pytest dependency to the venv.

Covers: policy/safety invariants, cost-model numbers, full-factorial rejection,
wave/candidate shape, proposal-only queue, mock decisions, scoring reuse of
objectives.py, cost reuse of fidelity.py, determinism, clobber-safety, safe CLI
modes, output-root confinement, and a dangerous-call source scan.
"""

import importlib
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = REPO_ROOT / "analysis" / "python"
SCRIPTS = REPO_ROOT / "scripts"
for _p in (str(ANALYSIS), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

from science_optimizer import fidelity as fid  # noqa: E402
from science_optimizer import objectives as obj  # noqa: E402
from science_optimizer import pipeline_rnd_stageB_v2 as planner  # noqa: E402

POLICY_PATH = REPO_ROOT / "configs" / "pipeline_rnd_stageB_v2_policy.template.yaml"


def _policy():
    return planner.load_policy(POLICY_PATH)


def _runner():
    return importlib.import_module("run_pipeline_rnd_stageB_v2")


def _tmpdir():
    return Path(tempfile.mkdtemp(prefix="stageb_test_"))


# --- 1. policy + safety invariants -----------------------------------------


def test_stageb_policy_loads():
    policy = _policy()
    assert policy["experiment"]["no_md_execution"] is True
    assert policy["experiment"]["mode"] == "template_only"
    axes = policy["policy"]["stage_B"]["axes"]
    assert axes["compositions_enabled"] == ["Fe4Al13"]
    assert "FeAl" in axes["compositions_disabled_until_validated"]
    assert "Fe3Al" in axes["compositions_disabled_until_validated"]


def test_policy_rejects_md_execution_flag():
    policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    policy["experiment"]["no_md_execution"] = False
    bad = _tmpdir() / "bad_no_md.yaml"
    bad.write_text(yaml.safe_dump(policy), encoding="utf-8")
    raised = False
    try:
        planner.load_policy(bad)
    except planner.StageBPolicyError:
        raised = True
    assert raised, "load_policy must reject no_md_execution != true"


def test_policy_rejects_extra_composition():
    policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    policy["policy"]["stage_B"]["axes"]["compositions_enabled"] = ["Fe4Al13", "FeAl"]
    bad = _tmpdir() / "bad_comp.yaml"
    bad.write_text(yaml.safe_dump(policy), encoding="utf-8")
    raised = False
    try:
        planner.load_policy(bad)
    except planner.StageBPolicyError:
        raised = True
    assert raised, "load_policy must reject compositions beyond Fe4Al13"


# --- 2. cost model numbers --------------------------------------------------


def test_runtime_cost_model_numbers():
    costs = planner.estimate_wave_cost(_policy())
    sr = costs["single_runs"]
    assert abs(sr["production_100k_1eps"]["estimated_hours"] - 13.92) < 0.1
    assert abs(sr["production_100k_two_eps_strategy"]["estimated_hours"] - 27.84) < 0.1
    assert abs(sr["production_250k_1eps"]["estimated_hours"] - 39.34) < 0.1
    assert abs(sr["production_500k_1eps"]["estimated_hours"] - 90.78) < 0.1
    assert abs(sr["production_700k_1eps"]["estimated_hours"] - 127.09) < 0.1


def test_runtime_base_matches_fidelity():
    """v2 base estimate (overhead=1.0) must equal v1 fidelity formula exactly."""
    cfg = {"costs": {"runtime_model": {
        "ref_steps_per_s": planner.REF_STEPS_PER_S,
        "ref_atoms": planner.REF_ATOMS}}}
    for atoms, steps in [(100000, 100000), (250000, 100000), (24259, 2000)]:
        v2 = planner.estimate_runtime_hours(atoms, steps, 1.0)
        v1 = fid.estimate_runtime_hours(cfg, atoms, steps)
        assert abs(v2 - v1) < 1e-9


def test_runtime_validation():
    for bad in [(0, 100, 1.0), (-1, 100, 1.0)]:
        raised = False
        try:
            planner.estimate_runtime_hours(*bad)
        except ValueError:
            raised = True
        assert raised, "atom_count <= 0 must raise"
    raised = False
    try:
        planner.estimate_runtime_hours(1000, -5, 1.0)
    except ValueError:
        raised = True
    assert raised, "negative steps must raise"


# --- 3. full factorial rejected --------------------------------------------


def test_full_factorial_rejected_count():
    ff = planner.estimate_full_factorial_cost(_policy())
    assert ff["case_count"] == 432
    assert 6000 < ff["smoke_plus_production_hours"] < 6800


def test_staged_is_far_cheaper_than_factorial():
    comp = planner.estimate_wave_cost(_policy())["comparison"]
    assert 100 < comp["B1_to_B4_staged_smoke_plus_winners_hours"] < 120
    assert comp["factorial_to_staged_ratio"] > 50


# --- 4. wave / candidate shape ---------------------------------------------


def test_stageb_waves_shape():
    waves = planner.generate_stageB_waves(_policy())
    names = [w["name"] for w in waves]
    assert names == [
        "B0_baseline_lock", "B1_size", "B2_shape",
        "B3_position_predefects", "B4_concentration", "B5_eps_threshold",
    ]
    counts = {w["name"]: w["candidate_count"] for w in waves}
    assert counts == {
        "B0_baseline_lock": 2, "B1_size": 6, "B2_shape": 6,
        "B3_position_predefects": 12, "B4_concentration": 6,
        "B5_eps_threshold": 2,
    }
    for w in waves:
        assert w["candidate_count"] == len(w["candidates"])


# --- 5. proposal-only queue -------------------------------------------------


def test_queue_is_proposal_only():
    queue = planner.generate_stageB_queue(_policy())
    assert len(queue) == 48
    for item in queue:
        assert item["will_launch_md"] is False
        assert item["status"] == "proposal_only"
        assert item["no_md_execution"] is True
        assert item["manual_approval_required"] is True
    by_fid = Counter(i["fidelity"] for i in queue)
    assert by_fid["smoke"] == 30
    assert by_fid["early_production_gate"] == 9
    assert by_fid["production"] == 9


# --- 6. mock decisions ------------------------------------------------------


def test_mock_decisions():
    scenarios = planner.generate_mock_decision_scenarios(_policy())
    rec = {s["mock_result"]["scenario"]: s["recommendation"] for s in scenarios}

    assert rec["A1_100k_eps_0025_signal"]["promotion_label"] == "confirm_250k"
    assert "B1_size" in rec["A1_100k_eps_0025_signal"]["next_waves"]

    assert rec["A1_100k_only_eps_0100_signal"]["next_waves"] == [
        "B5_eps_threshold", "B3_position_predefects"]

    assert rec["A1_100k_no_signal"]["promotion_label"] == "pivot_to_realism"
    assert rec["A1_100k_no_signal"]["next_waves"] == ["B3_position_predefects"]

    assert rec["B1_size_6nm_signal"]["next_waves"] == ["B2_shape"]
    assert rec["B3_near_grain_boundary_signal"]["promotion_label"] == "confirm_250k"
    assert rec["B4_concentration_unstable"]["promotion_label"] == "stop_branch"

    for r in rec.values():
        assert r["requires_manual_approval"] is True


# --- scoring reuse + pinned values -----------------------------------------

_SIGNAL_METRICS = {
    "scenario": "x", "stable": True, "dislocation_count": 3,
    "total_line_length": 125.0, "hcp_fraction": 0.031,
    "baseline_hcp_fraction": 0.03, "other_fraction": 0.0045,
    "baseline_other_fraction": 0.004, "plastic_zone_detected": True,
    "runtime_hours": 11.5,
}


def test_score_reuses_objectives():
    score = planner.score_science_utility(_SIGNAL_METRICS)
    r = planner._trial_result_from_metrics(_SIGNAL_METRICS)
    exp_signal, _ = obj.defect_signal_score(r)
    exp_pen, _ = obj.penalty(r)
    assert abs(score["defect_signal_score"] - round(exp_signal, 4)) < 1e-9
    assert abs(score["penalty"] - round(exp_pen, 4)) < 1e-9
    assert abs(score["science_utility"] - round(exp_signal - exp_pen, 4)) < 1e-9
    assert score["has_defect_signal"] is True


def test_score_known_values_unchanged():
    """Pin the audited mock values so the refactor cannot silently change them."""
    s = planner.score_science_utility(_SIGNAL_METRICS)
    assert s["defect_signal_score"] == 11.2558
    assert s["penalty"] == 1.15
    assert s["science_utility"] == 10.1058
    assert s["stability_score"] == 1.0


def test_unstable_case_scores_reject():
    s = planner.score_science_utility({
        "scenario": "x", "stable": False, "failed": True, "lost_atoms": True,
        "dislocation_count": 0, "total_line_length": 0.0, "runtime_hours": 4.0,
        "interpretability_flag": False,
    })
    assert s["promotion_label"] == "reject"
    assert s["has_defect_signal"] is False
    assert s["science_utility"] < 0


# --- determinism + clobber safety ------------------------------------------


def test_determinism():
    policy = _policy()
    assert planner.generate_stageB_waves(policy) == planner.generate_stageB_waves(policy)
    assert planner.generate_stageB_queue(policy) == planner.generate_stageB_queue(policy)
    assert planner.estimate_wave_cost(policy) == planner.estimate_wave_cost(policy)


def test_export_refuses_to_clobber():
    policy = _policy()
    out = _tmpdir() / "dry_run_fixed"
    planner.export_dry_run_outputs(policy, out)
    raised = False
    try:
        planner.export_dry_run_outputs(policy, out)
    except FileExistsError:
        raised = True
    assert raised, "export must not overwrite an existing dir (exist_ok=False)"


def test_export_writes_expected_files():
    policy = _policy()
    out = _tmpdir() / "dry_run_export"
    paths = planner.export_dry_run_outputs(policy, out)
    for name in ("policy_export", "strategy_summary", "cost_model",
                 "stageB_waves", "stageB_queue", "mock_decisions"):
        assert paths[name].is_file()


# --- 7/8. CLI safety --------------------------------------------------------


def test_cli_safe_modes_write_nothing():
    runner = _runner()
    tmp = _tmpdir()
    for mode in ("--plan-only", "--cost-model", "--mock-decisions"):
        rc = runner.main([mode, "--output-root", str(tmp)])
        assert rc == 0, f"{mode} should exit 0"
    assert list(tmp.glob("dry_run_*")) == [], "read-only modes must not write"


def test_cli_export_writes_only_under_allowed_root():
    runner = _runner()
    tmp = _tmpdir()
    rc = runner.main(["--generate-stageB-queue", "--output-root", str(tmp)])
    assert rc == 0
    dirs = list(tmp.glob("dry_run_*"))
    assert len(dirs) == 1
    out = dirs[0]
    for fname in ("policy_export.yaml", "strategy_summary.md", "cost_model.json",
                  "stageB_waves.yaml", "stageB_queue.jsonl", "mock_decisions.json"):
        assert (out / fname).is_file()
    # Confinement: everything is under the provided root, never an active run root.
    assert str(out.resolve()).startswith(str(tmp.resolve()))
    assert "stage_sweep_gpu_A1_100k" not in str(out)
    assert "stage_sweep_gpu_grid" not in str(out)


def test_cli_invalid_policy_fails_loudly():
    runner = _runner()
    bad = _tmpdir() / "missing.yaml"
    rc = runner.main(["--plan-only", "--config", str(bad)])
    assert rc == 2, "invalid/missing policy must return exit code 2"


# --- 9. dangerous-call source scan -----------------------------------------


def test_no_dangerous_process_calls():
    """Forbid execution/import forms in v2 source.

    Documented whitelist: the prose word "subprocess" may appear in
    docstrings (e.g. "never spawns subprocesses"); only the CALL/IMPORT forms
    below are forbidden, so harmless documentation is allowed.
    """
    files = [
        ANALYSIS / "science_optimizer" / "pipeline_rnd_stageB_v2.py",
        ANALYSIS / "science_optimizer" / "stageb_models.py",
        SCRIPTS / "run_pipeline_rnd_stageB_v2.py",
    ]
    forbidden = [
        "import subprocess", "subprocess.", "import os", "os.system",
        "Popen(", "eval(", "exec(", "Start-Process", "lmp_kokkos_cuda",
        "run_stage_sweep", "mpiexec", "compute-sanitizer",
    ]
    for f in files:
        text = f.read_text(encoding="utf-8")
        for pat in forbidden:
            assert pat not in text, f"{f.name} contains forbidden pattern {pat!r}"


# --- standalone runner (no pytest needed) ----------------------------------


def _run_all() -> int:
    import traceback
    tests = sorted(n for n, v in globals().items()
                   if n.startswith("test_") and callable(v))
    failures = []
    for name in tests:
        try:
            globals()[name]()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures.append(name)
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


def load_tests(loader, tests, pattern):  # noqa: D401 - unittest discovery hook
    """Expose pytest-style test functions to ``unittest discover``."""
    suite = unittest.TestSuite()
    for name in sorted(n for n, v in globals().items()
                       if n.startswith("test_") and callable(v)):
        suite.addTest(unittest.FunctionTestCase(globals()[name]))
    return suite


if __name__ == "__main__":
    raise SystemExit(_run_all())
