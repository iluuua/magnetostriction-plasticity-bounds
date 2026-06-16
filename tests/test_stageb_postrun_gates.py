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

from stage_runner.stageb_postrun import (  # noqa: E402
    NEIGHBOR_WORKAROUND,
    analyze_run_root,
    input_preview_is_safe,
    make_500k_confirmation_config,
    no_dislocation_proposals,
    render_500k_input_safety_preview,
    validate_500k_gate,
    validate_no_dislocation_gate,
)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TempStageBRun:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="stageb_postrun_")
        self.root = Path(self.tmp.name)
        self.case_id = "B3_nearGB_perfect_eps0100"

    def __enter__(self):
        self.write_effective_config()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.tmp.cleanup()

    def write_effective_config(self):
        cfg = {
            "stages": {
                "B3_realism_100k": {
                    "structure_mode": "build_stageB_realism_100k",
                    "production_case_ids": [self.case_id],
                    "cases": [
                        {
                            "case_id": self.case_id,
                            "atom_target": 100000,
                            "position": "near_grain_boundary",
                            "predefect": "perfect",
                            "eps_z": 0.0100,
                            "deterministic_seed": 73002,
                        }
                    ],
                }
            }
        }
        (self.root / "effective_config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def write_state(self, *, status="success", success=True, analysis=True, failure=False, running=False):
        rec = {
            "case_id": f"{self.case_id}_production",
            "stage": "B3_realism_100k",
            "phase": "production",
            "success": success,
            "status": status,
            "steps_target": 100000,
            "steps_completed": 100000 if success else 20000,
            "structure": {"stageB_case": self.case_id, "structure_mode": "build_stageB_realism_100k"},
            "log_summary": {"has_error": False, "nan_found": False, "lost_atoms": False},
        }
        if analysis:
            rec["analysis"] = str(self.root / "cases" / self.case_id / "production" / "analysis.json")
        if failure:
            rec["status"] = "failed"
            rec["failure_reasons"] = ["cudaError illegal address"]
            rec["error_markers"] = {"cudaError": True}
        if running:
            rec["status"] = "running_chunked"
            rec["success"] = False
            rec["steps_completed"] = 50000
            rec["current_step"] = 50000
        write_json(self.root / "state.json", {"cases": {rec["case_id"]: rec}, "stages": {}, "gates": {}})

    def write_analysis(self, data: dict):
        path = self.root / "cases" / self.case_id / "production" / "analysis.json"
        data = {"case": self.case_id, **data}
        write_json(path, data)

    def write_decision(self, decision: dict):
        write_json(self.root / "postrun_decision.json", decision)


def confirmed_decision(root: Path) -> dict:
    return {
        "status": "confirmed_dislocation_signal",
        "branch": "A_500k_confirmation",
        "completed_cases": ["B3_nearGB_perfect_eps0100"],
        "failed_cases": [],
        "running_cases": [],
        "signal_cases": [
            {
                "case": "B3_nearGB_perfect_eps0100",
                "strength": "confirmed",
                "reasons": ["dislocation_segments_gt_0"],
            }
        ],
        "winner_case": "B3_nearGB_perfect_eps0100",
        "winner_reason": "dislocation_segments_gt_0",
        "production_logs_clean": True,
        "manual_approval_required": True,
        "run_root": str(root),
    }


class StageBPostrunGateTests(unittest.TestCase):
    def test_confirmed_dislocation_routes_to_500k_confirmation(self):
        with TempStageBRun() as run:
            run.write_state()
            run.write_analysis({"dislocation_segments": 2, "dislocation_length_A": 15.0})
            decision = analyze_run_root(run.root, dry_run=True)
        self.assertEqual(decision["status"], "confirmed_dislocation_signal")
        self.assertEqual(decision["branch"], "A_500k_confirmation")
        self.assertEqual(decision["winner_case"], "B3_nearGB_perfect_eps0100")

    def test_deformation_only_without_dxa_routes_to_no_dislocation_validation(self):
        with TempStageBRun() as run:
            run.write_state()
            run.write_analysis(
                {
                    "dislocation_segments": 0,
                    "dislocation_length_A": 0.0,
                    "matrix_displacement_p99_A": 1.1,
                    "matrix_displacement_max_A": 4.7,
                    "localization": {"interface_shell": True, "gb_band": True},
                }
            )
            decision = analyze_run_root(run.root, dry_run=True)
        self.assertEqual(decision["status"], "deformation_only_no_dxa")
        self.assertEqual(decision["branch"], "B_no_dislocation_validation")

    def test_no_signal_routes_to_no_dislocation_validation(self):
        with TempStageBRun() as run:
            run.write_state()
            run.write_analysis(
                {
                    "dislocation_segments": 0,
                    "dislocation_length_A": 0.0,
                    "plastic_zone": {"hcp_atoms_beyond_1p3_shell": 0, "defect_atoms_beyond_1p3_shell": 0},
                }
            )
            decision = analyze_run_root(run.root, dry_run=True)
        self.assertEqual(decision["status"], "no_dislocation_no_plasticity")
        self.assertEqual(decision["branch"], "B_no_dislocation_validation")

    def test_unstable_case_routes_to_geometry_or_protocol_debug(self):
        with TempStageBRun() as run:
            run.write_state(success=False, analysis=False, failure=True)
            decision = analyze_run_root(run.root, dry_run=True)
        self.assertEqual(decision["status"], "unstable")
        self.assertEqual(decision["branch"], "C_fix_geometry_or_protocol")

    def test_incomplete_case_routes_to_wait(self):
        with TempStageBRun() as run:
            run.write_state(success=False, analysis=False, running=True)
            decision = analyze_run_root(run.root, dry_run=True)
        self.assertEqual(decision["status"], "incomplete")
        self.assertEqual(decision["branch"], "wait")

    def test_500k_dry_run_refuses_without_postrun_decision(self):
        with TempStageBRun() as run:
            gate = validate_500k_gate(run.root, mode="dry-run", active_process_checker=lambda: [], disk_free_checker=lambda _p: 100.0)
        self.assertFalse(gate.allowed)
        self.assertIn("postrun_decision.json not found", gate.reasons[0])

    def test_500k_refuses_when_branch_is_not_A(self):
        with TempStageBRun() as run:
            run.write_decision({"status": "no_dislocation_no_plasticity", "branch": "B_no_dislocation_validation"})
            gate = validate_500k_gate(run.root, mode="dry-run", active_process_checker=lambda: [], disk_free_checker=lambda _p: 100.0)
        self.assertFalse(gate.allowed)
        self.assertTrue(any("not A_500k_confirmation" in r for r in gate.reasons))

    def test_500k_launch_refuses_without_manual_approval(self):
        with TempStageBRun() as run:
            run.write_decision(confirmed_decision(run.root))
            gate = validate_500k_gate(run.root, mode="launch", active_process_checker=lambda: [], disk_free_checker=lambda _p: 100.0)
        self.assertFalse(gate.allowed)
        self.assertTrue(any("manual approval" in r for r in gate.reasons))

    def test_500k_refuses_if_lammps_is_active(self):
        with TempStageBRun() as run:
            run.write_decision(confirmed_decision(run.root))
            gate = validate_500k_gate(
                run.root,
                mode="validate-only",
                active_process_checker=lambda: ["lmp_kokkos_cuda.exe 1234"],
                disk_free_checker=lambda _p: 100.0,
            )
        self.assertFalse(gate.allowed)
        self.assertTrue(any("active LAMMPS" in r for r in gate.reasons))

    def test_500k_refuses_if_disk_below_threshold(self):
        with TempStageBRun() as run:
            run.write_decision(confirmed_decision(run.root))
            gate = validate_500k_gate(run.root, mode="validate-only", active_process_checker=lambda: [], disk_free_checker=lambda _p: 10.0)
        self.assertFalse(gate.allowed)
        self.assertTrue(any("disk_free_gb" in r for r in gate.reasons))

    def test_500k_generated_config_contains_exactly_one_winner_case(self):
        with TempStageBRun() as run:
            decision = confirmed_decision(run.root)
            run.write_decision(decision)
            gate = validate_500k_gate(run.root, mode="validate-only", active_process_checker=lambda: [], disk_free_checker=lambda _p: 100.0)
        self.assertTrue(gate.allowed, gate.reasons)
        cases = gate.config["stages"]["B3_500k_confirmation"]["cases"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["source_winner_case"], "B3_nearGB_perfect_eps0100")

    def test_500k_generated_input_preview_contains_neighbor_workaround(self):
        with TempStageBRun() as run:
            text = render_500k_input_safety_preview(make_500k_confirmation_config(run.root, confirmed_decision(run.root)))
        self.assertIn(NEIGHBOR_WORKAROUND, text)

    def test_500k_generated_input_preview_excludes_forbidden_commands(self):
        with TempStageBRun() as run:
            text = render_500k_input_safety_preview(make_500k_confirmation_config(run.root, confirmed_decision(run.root)))
        ok, reasons = input_preview_is_safe(text)
        self.assertTrue(ok, reasons)
        self.assertNotIn("compute-sanitizer", text)
        self.assertNotIn("CUDA_LAUNCH_BLOCKING", text)
        self.assertNotRegex(text, r"(?mi)^\s*minimize\b")
        self.assertNotRegex(text, r"(?mi)^\s*thermo\s+1\s*$")

    def test_no_dislocation_branch_refuses_A_500k_branch(self):
        with TempStageBRun() as run:
            run.write_decision(confirmed_decision(run.root))
            gate = validate_no_dislocation_gate(run.root, mode="dry-run", active_process_checker=lambda: [])
        self.assertFalse(gate.allowed)
        self.assertTrue(any("does not allow" in r for r in gate.reasons))

    def test_no_dislocation_dry_run_proposes_positive_control_first(self):
        proposals = no_dislocation_proposals()
        self.assertEqual(proposals[0]["id"], "B6_positive_control_shear_30k")
        self.assertEqual(proposals[0]["priority"], 1)

    def test_no_dislocation_dry_run_and_validate_do_not_check_or_launch_lammps(self):
        with TempStageBRun() as run:
            run.write_decision({"status": "no_dislocation_no_plasticity", "branch": "B_no_dislocation_validation"})

            def should_not_be_called():
                raise AssertionError("dry-run/validate-only must not inspect or launch LAMMPS")

            dry = validate_no_dislocation_gate(run.root, mode="dry-run", active_process_checker=should_not_be_called)
            validate = validate_no_dislocation_gate(run.root, mode="validate-only", active_process_checker=should_not_be_called)
        self.assertTrue(dry.allowed, dry.reasons)
        self.assertTrue(validate.allowed, validate.reasons)


if __name__ == "__main__":
    unittest.main()

