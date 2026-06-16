import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PY_ROOT = str(REPO_ROOT / "analysis" / "python")
if PY_ROOT not in sys.path:
    sys.path.insert(0, PY_ROOT)

from event_pipeline.schema import MANIFEST_FIELDS  # noqa: E402
from event_pipeline.timeline import build_event_timeline, classify_event, stable_frame_id, write_event_timeline_outputs  # noqa: E402
from event_pipeline.video import build_ffmpeg_command, write_video_plan_outputs  # noqa: E402
from event_pipeline.window import EventWindowPolicy, plan_event_window  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TempEventRun:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="event_pipeline_")
        self.root = Path(self.tmp.name)
        self.case = "B3_nearGB_perfect_eps0100"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.tmp.cleanup()

    def write_state_and_analysis(self, analysis: dict, *, step: int = 100000) -> None:
        analysis_path = self.root / "cases" / "B3_realism_100k" / self.case / "production" / "analysis.json"
        dump_path = analysis_path.parent / f"dump.{self.case}_production_final.lammpstrj"
        data = {
            "case": f"{self.case}_production",
            "dump": str(dump_path),
            **analysis,
        }
        write_json(analysis_path, data)
        rec = {
            "case_id": f"{self.case}_production",
            "stage": "B3_realism_100k",
            "phase": "production",
            "status": "success",
            "success": True,
            "eps_z": 0.01,
            "steps_target": step,
            "steps_completed": step,
            "final_temp": 300.0,
            "final_press": -2000.0,
            "analysis": str(analysis_path),
            "structure": {"stageB_case": self.case, "structure_mode": "build_stageB_realism_100k"},
        }
        write_json(self.root / "state.json", {"cases": {rec["case_id"]: rec}})
        for restart_step in (60000, 80000, 90000):
            (analysis_path.parent / f"restart.{self.case}_production.{restart_step}").write_text("", encoding="utf-8")


class EventPipelineTests(unittest.TestCase):
    def test_manifest_schema_contains_required_prompt_fields(self):
        required = [
            "frame_id",
            "case_id",
            "timestep",
            "time_ps",
            "dump_file",
            "restart_file",
            "camera_id",
            "coloring_mode",
            "visible_layers",
            "temperature",
            "pressure",
            "pe",
            "ke",
            "etotal",
            "pxx",
            "pyy",
            "pzz",
            "eps_z",
            "dislocation_segments",
            "dislocation_line_length_A",
            "hcp_atoms",
            "other_atoms",
            "atomic_strain_p95",
            "atomic_strain_p99",
            "Dmin2_p95",
            "Dmin2_p99",
            "max_displacement",
            "event_class",
        ]
        self.assertEqual(MANIFEST_FIELDS, required)

    def test_event_classification_confirmed_dxa(self):
        event_class, reasons, score, metrics = classify_event(
            {"dislocation_segments": 1, "dislocation_length_A": 12.5}
        )
        self.assertEqual(event_class, "confirmed_DXA")
        self.assertIn("dislocation_segments_gt_0", reasons)
        self.assertGreater(score, 1000.0)
        self.assertEqual(metrics["dislocation_segments"], 1)

    def test_event_classification_weak_hcp(self):
        event_class, reasons, _score, _metrics = classify_event(
            {"matrix_atoms": 100000, "hcp_pct": 0.02, "dislocation_segments": 0}
        )
        self.assertEqual(event_class, "weak_hcp")
        self.assertTrue(any("hcp" in r for r in reasons))

    def test_event_classification_deformation_only(self):
        event_class, reasons, _score, metrics = classify_event(
            {"matrix_displacement_p95_A": 0.9, "matrix_displacement_max_A": 2.5}
        )
        self.assertEqual(event_class, "deformation_only")
        self.assertIn("matrix_displacement_p95_threshold", reasons)
        self.assertEqual(metrics["max_displacement"], 2.5)

    def test_empty_input_writes_empty_timeline(self):
        with TempEventRun() as run:
            result = write_event_timeline_outputs(run.root)
            self.assertEqual(result["frame_count"], 0)
            timeline = json.loads((run.root / "event_pipeline" / "event_timeline.json").read_text(encoding="utf-8"))
        self.assertEqual(timeline["frames"], [])

    def test_stable_frame_id_uses_case_and_timestep(self):
        self.assertEqual(
            stable_frame_id("B3 nearGB", 1200, 1),
            "B3_nearGB__step_0000001200",
        )

    def test_timeline_reads_existing_analysis(self):
        with TempEventRun() as run:
            run.write_state_and_analysis({"dislocation_segments": 0, "matrix_displacement_max_A": 3.0})
            rows = build_event_timeline(run.root)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_class"], "deformation_only")
        self.assertEqual(rows[0]["case_id"], "B3_nearGB_perfect_eps0100")

    def test_confirmed_window_selects_restart_before_start(self):
        with TempEventRun() as run:
            run.write_state_and_analysis({"dislocation_segments": 2, "dislocation_length_A": 5.0}, step=100000)
            rows = build_event_timeline(run.root)
            plan = plan_event_window(run.root, rows, EventWindowPolicy(pre_steps=10000, post_steps=5000))
        self.assertEqual(plan["branch"], "confirmed_DXA")
        self.assertEqual(plan["start_step"], 90000)
        self.assertEqual(plan["restart_step"], 90000)

    def test_fallback_window_without_confirmed_dxa(self):
        with TempEventRun() as run:
            run.write_state_and_analysis({"dislocation_segments": 0, "matrix_displacement_max_A": 3.0}, step=100000)
            rows = build_event_timeline(run.root)
            plan = plan_event_window(run.root, rows)
        self.assertEqual(plan["branch"], "fallback_deformation")
        self.assertEqual(plan["event_class"], "deformation_only")
        self.assertTrue(plan["manual_approval_required"])

    def test_ffmpeg_command_is_30fps_and_no_overwrite_by_default(self):
        cmd = build_ffmpeg_command("frames/*.png", "out.mp4")
        self.assertIn("-framerate", cmd)
        self.assertEqual(cmd[cmd.index("-framerate") + 1], "30")
        self.assertIn("-n", cmd)
        self.assertNotIn("-y", cmd)

    def test_video_plan_blocks_empty_manifest(self):
        with TempEventRun() as run:
            manifest = run.root / "event_pipeline" / "event_frame_manifest.json"
            write_json(manifest, {"frames": []})
            result = write_video_plan_outputs(run.root, frame_manifest_json=manifest)
        self.assertEqual(result["status"], "blocked_no_frames")


if __name__ == "__main__":
    unittest.main()
