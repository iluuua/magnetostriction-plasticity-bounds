import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
for _sub in ("analysis/python", "scripts"):
    _p = str(REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_event_pipeline_dry_run import main as event_dry_run_main  # noqa: E402
from run_stage_sweep import main as stage_sweep_main  # noqa: E402
import launch_stageC_1M_safe_prep_retry as safe_prep_retry  # noqa: E402
from stage_runner import builder  # noqa: E402
from stage_runner.gpu_grid import GpuGridRunner, load_grid_config  # noqa: E402
from stage_runner.stagec_1m import (  # noqa: E402
    BLOCKER_ACTIVE_FOCUS,
    FOCUS_RUN_ROOT_DEFAULT,
    REQUIRED_DUMP_FIELDS,
    STAGEC_CASE,
    STAGEC_OUTPUT_ROOT,
    STAGEC_STAGE,
    build_preflight,
    stagec_plan,
    validate_stagec_config,
)


CONFIG_PATH = REPO_ROOT / "configs" / "stageC_1M_nearGB_vacancies_eps0100_100k.template.yaml"


def load_stagec_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


class StageC1MQueueTests(unittest.TestCase):
    def test_stagec_config_contains_exactly_one_case(self):
        cfg = load_stagec_config()
        stage = cfg["stages"][STAGEC_STAGE]
        self.assertEqual(cfg["case_ids"], [STAGEC_CASE])
        self.assertEqual(stage["production_case_ids"], [STAGEC_CASE])
        self.assertEqual(stage["max_production_cases"], 1)
        self.assertEqual(len(stage["cases"]), 1)
        self.assertEqual(stage["cases"][0]["case_id"], STAGEC_CASE)
        self.assertEqual(validate_stagec_config(cfg), [])

    def test_stagec_target_estimate_is_1m_class_and_gpu_feasible(self):
        cfg = load_stagec_config()
        plan = stagec_plan(cfg)
        self.assertEqual(cfg["target_atoms"], 1000000)
        self.assertGreaterEqual(plan["estimated_atoms"], 900000)
        self.assertLessEqual(plan["estimated_atoms"], 1100000)
        self.assertTrue(plan["feasible_under_memory_limit"])
        self.assertLessEqual(plan["estimated_memory_gb"], 12)

    def test_stagec_io_policy_and_forbidden_tokens(self):
        cfg = load_stagec_config()
        io_policy = cfg["io_policy"]
        self.assertGreaterEqual(io_policy["dump_every"]["production"], 5000)
        self.assertEqual(io_policy["restart_every"], 10000)
        self.assertEqual(io_policy["thermo_every"]["production"], 1000)
        fields = tuple(io_policy["dump_fields"])
        for field in REQUIRED_DUMP_FIELDS:
            self.assertIn(field, fields)
        text = CONFIG_PATH.read_text(encoding="utf-8").lower()
        self.assertNotRegex(text, r"(?m)^\s*minimize\b")
        self.assertNotRegex(text, r"(?m)^\s*thermo\s+1\s*$")
        self.assertNotIn("compute-sanitizer", text)

    def test_generated_stagec_input_uses_required_dump_fields(self):
        cfg = load_grid_config(CONFIG_PATH)
        runner = object.__new__(GpuGridRunner)
        runner.cfg = cfg
        template = (REPO_ROOT / "lammps" / "05_finite_t_ellipsoid" / "stage_A0_24k" / "in.nvt_eps_0100").read_text(
            encoding="utf-8"
        )
        text = runner.input_for_phase(
            template_text=template,
            data_path=Path("data.test"),
            stage=STAGEC_STAGE,
            atom_target=950000,
            eps_z=0.0100,
            phase="production",
            steps=100000,
            inclusion_id_min=1,
            inclusion_id_max=2,
            case_name=f"{STAGEC_CASE}_production",
        )
        self.assertIn("custom 5000", text)
        self.assertIn("id type x y z c_pe_atom c_st[1] c_st[2] c_st[3]", text)
        self.assertIn("dump_modify     d1 sort id", text)
        self.assertIn("neigh_modify    delay 0 every 10 check no", text)
        self.assertIn("restart         10000 restart.", text)
        self.assertNotRegex(text, r"(?mi)^\s*minimize\b")
        self.assertNotRegex(text, r"(?mi)^\s*thermo\s+1\s*$")

    def test_segmented_safe_prep_uses_small_timesteps(self):
        text = builder.make_prep_input_gpu_safe(
            {"data_file": str(REPO_ROOT / "dummy.data")},
            segments=[
                {
                    "label": "ramp_50_to_150",
                    "timestep": 0.0001,
                    "temp_start_K": 50,
                    "temp_end_K": 150,
                    "steps": 10000,
                    "tdamp": 0.1,
                },
                {
                    "label": "ramp_150_to_300",
                    "timestep": 0.0001,
                    "temp_start_K": 150,
                    "temp_end_K": 300,
                    "steps": 20000,
                    "tdamp": 0.1,
                },
                {
                    "label": "hold_300",
                    "timestep": 0.0001,
                    "temp_start_K": 300,
                    "temp_end_K": 300,
                    "steps": 20000,
                    "tdamp": 0.1,
                },
            ],
            restart_every=2000,
            restart_prefix="case_prep",
            dump_every=2000,
        )
        self.assertEqual(text.count("timestep        0.0001"), 3)
        self.assertIn("# Segment 1: ramp_50_to_150.", text)
        self.assertIn("fix             prep_1 all nvt temp 50.0 150.0 0.1", text)
        self.assertIn("# Segment 2: ramp_150_to_300.", text)
        self.assertIn("fix             prep_2 all nvt temp 150.0 300.0 0.1", text)
        self.assertIn("# Segment 3: hold_300.", text)
        self.assertIn("fix             prep_3 all nvt temp 300.0 300.0 0.1", text)
        self.assertNotIn("timestep        0.00025", text)
        self.assertNotIn("timestep        0.001", text)
        self.assertIn("restart         2000 restart.case_prep.*", text)
        self.assertIn("dump            prep_dump all custom 2000", text)
        self.assertIn("write_restart   restart.case_prep.final", text)
        self.assertIn("write_data      data.a1_baseline_equil", text)
        self.assertIn("write_dump      all custom dump.a1_baseline_equil.lammpstrj", text)
        self.assertNotRegex(text, r"(?mi)^\s*minimize\b")

    def test_safe_prep_retry_config_is_prep_only(self):
        cfg = safe_prep_retry.safe_config(CONFIG_PATH)
        stage = cfg["stages"][safe_prep_retry.TARGET_STAGE]
        segments = stage["prep_segments"]
        self.assertEqual([seg["label"] for seg in segments], ["ramp_50_to_150K", "ramp_150_to_300K", "hold_300K"])
        self.assertEqual([seg["steps"] for seg in segments], [10000, 20000, 20000])
        self.assertTrue(all(float(seg["timestep"]) == 0.0001 for seg in segments))
        self.assertTrue(all(float(seg["tdamp"]) == 0.1 for seg in segments))
        self.assertEqual(stage["prep_restart_every"], 2000)
        self.assertEqual(stage["prep_dump_every"], 2000)
        self.assertEqual(stage["prep_dump_fields"], ["id", "type", "x", "y", "z"])
        self.assertTrue(stage["safe_prep_only"])
        self.assertFalse(stage["run_short_after_smoke_pass"])
        self.assertFalse(stage["run_production_after_smoke_pass"])
        self.assertFalse(stage["run_production_after_gate_pass"])
        self.assertEqual(cfg["experiment"]["output_root"], "runs/stageC_1M_nearGB_vacancies_eps0100_safe_prep")
        self.assertNotEqual(safe_prep_retry.SAFE_OUTPUT_ROOT.resolve(), safe_prep_retry.OLD_FAILED_ROOT.parent.resolve())

    def test_safe_prep_worker_runs_only_baseline(self):
        calls = []

        class FakeState:
            def mark_stage(self, stage, payload):
                calls.append(("mark_stage", stage, payload))

        class FakeRunner:
            def __init__(self, cfg, run_dir):
                self.cfg = cfg
                self.run_dir = run_dir
                self.state = FakeState()

            def ensure_stageb_baseline(self, stage, case):
                calls.append(("ensure_stageb_baseline", stage, case["case_id"]))
                return {"success": True, "final_temp": 299.8}

            def write_final_report(self):
                calls.append(("write_final_report",))

        cfg = {"stages": {safe_prep_retry.TARGET_STAGE: {"cases": [{"case_id": safe_prep_retry.TARGET_CASE}]}}}
        with tempfile.TemporaryDirectory(prefix="safe_prep_worker_") as tmp:
            root = Path(tmp)
            with (
                mock.patch.object(safe_prep_retry, "load_grid_config", return_value=cfg),
                mock.patch.object(safe_prep_retry, "active_md_processes", return_value=[]),
                mock.patch.object(safe_prep_retry, "GpuGridRunner", FakeRunner),
                mock.patch.object(safe_prep_retry, "write_json"),
                mock.patch.object(safe_prep_retry, "write_safe_final_report"),
            ):
                rc = safe_prep_retry.worker_run_prep("unused.yaml", root)
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0], ("ensure_stageb_baseline", safe_prep_retry.TARGET_STAGE, safe_prep_retry.TARGET_CASE))
        self.assertFalse(any("production" in str(call).lower() for call in calls))

    def test_safe_prep_temperature_guard_catches_runaway(self):
        log_text = """LAMMPS
   Step        Atoms         Temp          PotEng
       4300      938344   305.0         -1.0
       4400      938344   368.0         -1.0
       4500      938344   3792.0        -1.0
Loop time of 1.0 on 1 procs for 100 steps with 938344 atoms
"""
        with tempfile.TemporaryDirectory(prefix="safe_prep_guard_") as tmp:
            log_path = Path(tmp) / "log.lammps"
            log_path.write_text(log_text, encoding="utf-8")
            blockers = safe_prep_retry.prep_temperature_blockers({"log": str(log_path)})
        self.assertTrue(any("max Temp 3792" in blocker for blocker in blockers))
        self.assertTrue(any("jumped 368 -> 3792" in blocker for blocker in blockers))

    def test_preflight_blocks_when_focused_lammps_is_active(self):
        root = STAGEC_OUTPUT_ROOT / "unit-test-preflight"
        preflight = build_preflight(
            CONFIG_PATH,
            root,
            FOCUS_RUN_ROOT_DEFAULT,
            process_checker=lambda: [
                {
                    "Name": "lmp_kokkos_cuda.exe",
                    "ProcessId": 123,
                    "CommandLine": str(FOCUS_RUN_ROOT_DEFAULT),
                }
            ],
            disk_checker=lambda drive: 250.0 if drive.startswith("B") else 30.0,
        )
        self.assertIn(BLOCKER_ACTIVE_FOCUS, preflight["blocked_by"])
        self.assertFalse(preflight["allowed_to_launch_now"])
        self.assertTrue(preflight["queue_ready"])

    def test_preflight_refuses_stagec_root_matching_focus_root(self):
        preflight = build_preflight(
            CONFIG_PATH,
            FOCUS_RUN_ROOT_DEFAULT,
            FOCUS_RUN_ROOT_DEFAULT,
            process_checker=lambda: [],
            disk_checker=lambda drive: 250.0 if drive.startswith("B") else 30.0,
        )
        self.assertIn("stagec_run_root_outside_stagec_output_root", preflight["blocked_by"])
        self.assertIn("stagec_run_root_matches_focus_run_root", preflight["blocked_by"])
        self.assertFalse(preflight["queue_ready"])

    def test_stagec_plan_only_passes(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = stage_sweep_main(["--config", str(CONFIG_PATH), "--plan-only"])
        self.assertEqual(rc, 0)

    def test_event_pipeline_dry_run_allows_incomplete_stagec_root(self):
        with tempfile.TemporaryDirectory(prefix="stagec_event_") as tmp:
            root = Path(tmp)
            (root / "state.json").write_text(json.dumps({"cases": {}, "stages": {}}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = event_dry_run_main(["--run-root", str(root), "--allow-incomplete"])
            timeline = json.loads((root / "event_pipeline" / "event_timeline.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(timeline["frames"], [])


if __name__ == "__main__":
    unittest.main()
