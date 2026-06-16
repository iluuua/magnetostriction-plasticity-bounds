import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
for _sub in ("analysis/python", "scripts"):
    _p = str(REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_event_pipeline_dry_run import main as event_dry_run_main  # noqa: E402
from run_stage_sweep import main as stage_sweep_main  # noqa: E402
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
