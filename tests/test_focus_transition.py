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
from stage_runner.focus_transition import (  # noqa: E402
    FOCUS_CASE_IDS,
    FOCUS_STAGE,
    PreflightInputs,
    focus_case_ids,
    focus_run_command,
    validate_focus_config,
    validate_focus_preflight,
)


CONFIG_PATH = REPO_ROOT / "configs" / "stageB_nearGB_vacancies_focus_100k.template.yaml"


def load_focus_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


class FocusTransitionTests(unittest.TestCase):
    def test_focus_config_contains_exactly_two_cases(self):
        cfg = load_focus_config()
        stage = cfg["stages"][FOCUS_STAGE]
        self.assertEqual(focus_case_ids(cfg), FOCUS_CASE_IDS)
        self.assertEqual(stage["max_production_cases"], 2)
        self.assertEqual(len(stage["cases"]), 2)
        self.assertEqual([c["case_id"] for c in stage["cases"]], FOCUS_CASE_IDS)
        self.assertEqual(validate_focus_config(cfg), [])

    def test_focus_config_dump_every_at_most_2000(self):
        cfg = load_focus_config()
        self.assertLessEqual(cfg["io_policy"]["dump_every"]["production"], 2000)
        self.assertEqual(cfg["io_policy"]["restart_every"], 10000)
        self.assertEqual(cfg["io_policy"]["thermo_every"]["production"], 1000)

    def test_focus_run_root_must_differ_from_old_run_root(self):
        with tempfile.TemporaryDirectory(prefix="focus_preflight_") as tmp:
            root = Path(tmp)
            manifest_dir = root / "snapshot"
            manifest_dir.mkdir()
            (manifest_dir / "completed_cases_manifest.json").write_text("{}", encoding="utf-8")
            cmd = focus_run_command(CONFIG_PATH, root)
            result = validate_focus_preflight(
                PreflightInputs(
                    old_run_root=root,
                    focus_run_root=root,
                    focus_config_path=CONFIG_PATH,
                    snapshot_dir=manifest_dir,
                    command=cmd,
                ),
                process_checker=lambda: [],
                disk_checker=lambda _drive: 200.0,
                gpu_checker=lambda: {"free": True},
            )
        self.assertIn("focus_run_root_matches_old_run_root", result["blockers"])

    def test_preflight_blocks_when_active_lammps_exists(self):
        with tempfile.TemporaryDirectory(prefix="focus_preflight_") as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            manifest_dir = old / "handoff_completed_cases_snapshot"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "completed_cases_manifest.json").write_text("{}", encoding="utf-8")
            result = validate_focus_preflight(
                PreflightInputs(
                    old_run_root=old,
                    focus_run_root=new,
                    focus_config_path=CONFIG_PATH,
                    snapshot_dir=manifest_dir,
                    command=focus_run_command(CONFIG_PATH, new),
                ),
                process_checker=lambda: [{"Name": "lmp_kokkos_cuda.exe", "ProcessId": 123}],
                disk_checker=lambda _drive: 200.0,
                gpu_checker=lambda: {"free": True},
            )
        self.assertIn("active_lammps_detected", result["blockers"])
        self.assertFalse(result["allowed_to_launch"])

    def test_preflight_blocks_if_snapshot_missing(self):
        with tempfile.TemporaryDirectory(prefix="focus_preflight_") as tmp:
            root = Path(tmp)
            result = validate_focus_preflight(
                PreflightInputs(
                    old_run_root=root / "old",
                    focus_run_root=root / "new",
                    focus_config_path=CONFIG_PATH,
                    snapshot_dir=root / "missing_snapshot",
                    command=focus_run_command(CONFIG_PATH, root / "new"),
                ),
                process_checker=lambda: [],
                disk_checker=lambda _drive: 200.0,
                gpu_checker=lambda: {"free": True},
            )
        self.assertIn("completed_cases_snapshot_missing", result["blockers"])

    def test_focus_launcher_has_no_ovito_or_ffmpeg(self):
        with tempfile.TemporaryDirectory(prefix="focus_cmd_") as tmp:
            cmd = focus_run_command(CONFIG_PATH, Path(tmp) / "new")
        low = cmd.lower()
        self.assertNotIn("ovito", low)
        self.assertNotIn("ffmpeg", low)
        self.assertNotIn("compute-sanitizer", low)

    def test_event_pipeline_dry_run_allows_incomplete_focus_run(self):
        with tempfile.TemporaryDirectory(prefix="focus_event_") as tmp:
            root = Path(tmp)
            (root / "state.json").write_text(json.dumps({"cases": {}, "stages": {}}), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = event_dry_run_main(["--run-root", str(root), "--allow-incomplete"])
            timeline = json.loads((root / "event_pipeline" / "event_timeline.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(timeline["frames"], [])

    def test_case_filter_selects_only_focus_cases(self):
        cfg = load_focus_config()
        selected = focus_case_ids(cfg)
        self.assertEqual(selected, FOCUS_CASE_IDS)
        self.assertNotIn("B3_interior_vacancies_medium_eps0100", selected)
        self.assertNotIn("B3_nearGB_perfect_eps0100", selected)


if __name__ == "__main__":
    unittest.main()
