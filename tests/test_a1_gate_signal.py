import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
for _sub in ("analysis/python", "scripts"):
    _p = str(REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from science_optimizer import pipeline_rnd_stageB_v2 as planner  # noqa: E402
from stage_runner.gpu_grid import GpuGridRunner  # noqa: E402


POLICY_PATH = REPO_ROOT / "configs" / "pipeline_rnd_stageB_v2_policy.template.yaml"


def a1_boundary_noise_metrics() -> dict:
    return {
        "matrix_atoms": 100560,
        "hcp_pct": 0.0089,
        "other_pct": 2.656,
        "dislocation_segments": 0,
        "dislocation_length_A": 0.0,
        "dislocation_density_per_m2": 0.0,
        "plastic_zone": {
            "defect_atoms_beyond_1p3_shell": 3,
            "hcp_atoms_beyond_1p3_shell": 0,
            "max_normalized_ellipsoid_distance": 1.3091253112203598,
        },
    }


class A1GateSignalTests(unittest.TestCase):
    def test_a1_metrics_with_three_boundary_defects_are_no_signal(self):
        self.assertFalse(
            GpuGridRunner.analysis_has_signal(None, a1_boundary_noise_metrics())
        )

    def test_dislocation_segments_are_signal(self):
        metrics = a1_boundary_noise_metrics()
        metrics["dislocation_segments"] = 1
        self.assertTrue(GpuGridRunner.analysis_has_signal(None, metrics))

    def test_hcp_atoms_beyond_shell_are_signal(self):
        metrics = a1_boundary_noise_metrics()
        metrics["plastic_zone"]["hcp_atoms_beyond_1p3_shell"] = 2
        self.assertTrue(GpuGridRunner.analysis_has_signal(None, metrics))

    def test_a1_no_signal_blocks_stale_a2_auto_escalation_flag(self):
        with tempfile.TemporaryDirectory(prefix="a1_gate_") as tmp:
            analysis_path = Path(tmp) / "analysis.json"
            analysis_path.write_text(
                json.dumps(a1_boundary_noise_metrics()),
                encoding="utf-8",
            )
            runner = object.__new__(GpuGridRunner)
            runner.production_records = lambda stage: [
                {
                    "stage": stage,
                    "phase": "production",
                    "success": True,
                    "science_signal": True,
                    "analysis": str(analysis_path),
                }
            ]
            self.assertFalse(runner.stage_has_science_signal("A1_custom_100k"))

    def test_a1_no_signal_recommends_b3_realism_pivot(self):
        policy = planner.load_policy(POLICY_PATH)
        recommendation = planner.recommend_from_mock_result(
            {
                "scenario": "A1_100k_no_signal",
                "stable": True,
                "dislocation_count": 0,
                "total_line_length": 0.0,
                "hcp_fraction": 0.0301,
                "baseline_hcp_fraction": 0.0300,
                "other_fraction": 0.0041,
                "baseline_other_fraction": 0.0040,
                "runtime_hours": 11.5,
            },
            policy,
        )
        self.assertEqual(recommendation["promotion_label"], "pivot_to_realism")
        self.assertEqual(recommendation["next_waves"], ["B3_position_predefects"])


if __name__ == "__main__":
    unittest.main()
