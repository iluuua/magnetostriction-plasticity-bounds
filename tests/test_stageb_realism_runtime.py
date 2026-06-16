import contextlib
import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
for _sub in ("analysis/python", "scripts"):
    _p = str(REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_pipeline_rnd_stageB_v2 import main as planner_main  # noqa: E402
from stage_runner import builder  # noqa: E402
from stage_runner.gpu_grid import (  # noqa: E402
    GpuGridRunner,
    GridConfigError,
    load_grid_config,
    validate_config_shape,
)


CONFIG_PATH = REPO_ROOT / "configs" / "stageB_realism_100k_smoke_production.yaml"


def load_config_doc() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def small_plan() -> dict:
    return builder.plan_for_target(12000, ranks=1, max_memory_gb=12)


class StageBRealismRuntimeTests(unittest.TestCase):
    def test_config_schema_accepts_stageb_realism_mode(self):
        cfg = load_grid_config(CONFIG_PATH)
        stage = cfg["stages"]["B3_realism_100k"]
        self.assertEqual(stage["structure_mode"], "build_stageB_realism_100k")
        self.assertEqual(len(stage["cases"]), 6)

    def test_unsupported_position_and_predefect_rejected(self):
        cfg = load_config_doc()
        bad = copy.deepcopy(cfg)
        bad["stages"]["B3_realism_100k"]["cases"][0]["position"] = "shifted_fake_gb"
        with self.assertRaises(GridConfigError):
            validate_config_shape(bad)

        bad = copy.deepcopy(cfg)
        bad["stages"]["B3_realism_100k"]["cases"][0]["predefect"] = "random_damage"
        with self.assertRaises(GridConfigError):
            validate_config_shape(bad)

    def test_seed_dislocation_rejected_until_real_tool_exists(self):
        cfg = load_config_doc()
        cfg["stages"]["B3_realism_100k"]["cases"][0]["predefect"] = (
            "seed_dislocation_if_available"
        )
        with self.assertRaises(GridConfigError):
            validate_config_shape(cfg)

    def test_vacancies_medium_deletes_only_matrix_atoms(self):
        with tempfile.TemporaryDirectory(prefix="stageb_vac_") as tmp:
            meta = builder.build_stageb_realism_structure(
                small_plan(),
                Path(tmp),
                case_id="vacancies",
                position="grain_interior",
                predefect="vacancies_medium",
                deterministic_seed=1234,
                vacancy_count=12,
            )
        self.assertEqual(meta["vacancy"]["vacancy_count_actual"], 12)
        self.assertTrue(meta["vacancy"]["no_inclusion_atoms_deleted"])
        self.assertTrue(meta["no_inclusion_atoms_deleted"])
        self.assertGreater(meta["matrix_atoms"], 0)
        self.assertGreater(meta["inclusion_atoms"], 0)

    def test_vacancies_medium_is_deterministic_for_same_seed(self):
        with tempfile.TemporaryDirectory(prefix="stageb_vac_a_") as tmp_a:
            meta_a = builder.build_stageb_realism_structure(
                small_plan(),
                Path(tmp_a),
                case_id="vac_a",
                position="grain_interior",
                predefect="vacancies_medium",
                deterministic_seed=5678,
                vacancy_count=15,
            )
        with tempfile.TemporaryDirectory(prefix="stageb_vac_b_") as tmp_b:
            meta_b = builder.build_stageb_realism_structure(
                small_plan(),
                Path(tmp_b),
                case_id="vac_b",
                position="grain_interior",
                predefect="vacancies_medium",
                deterministic_seed=5678,
                vacancy_count=15,
            )
        self.assertEqual(
            meta_a["vacancy"]["deleted_atom_ids"],
            meta_b["vacancy"]["deleted_atom_ids"],
        )

    def test_near_grain_boundary_writes_boundary_metadata(self):
        with tempfile.TemporaryDirectory(prefix="stageb_gb_") as tmp:
            meta = builder.build_stageb_realism_structure(
                small_plan(),
                Path(tmp),
                case_id="near_gb",
                position="near_grain_boundary",
                predefect="perfect",
                deterministic_seed=9101,
            )
        boundary = meta["boundary"]
        self.assertEqual(boundary["boundary_plane"], "x")
        self.assertIn("grain2_orientation", boundary)
        self.assertGreater(boundary["orientation_discontinuity_degrees"], 0.0)
        self.assertGreater(boundary["inclusion_surface_gap_to_boundary_A"], 0.0)

    def test_near_grain_boundary_not_identical_to_interior_perfect(self):
        with tempfile.TemporaryDirectory(prefix="stageb_cmp_") as tmp:
            root = Path(tmp)
            interior = builder.build_stageb_realism_structure(
                small_plan(),
                root / "interior",
                case_id="interior",
                position="grain_interior",
                predefect="perfect",
                deterministic_seed=1,
            )
            near_gb = builder.build_stageb_realism_structure(
                small_plan(),
                root / "near_gb",
                case_id="near_gb",
                position="near_grain_boundary",
                predefect="perfect",
                deterministic_seed=1,
            )
            self.assertNotEqual(interior["grain_label_counts"], near_gb["grain_label_counts"])
            self.assertNotEqual(interior["center_A"], near_gb["center_A"])
            self.assertTrue(near_gb["boundary"])

    def test_generated_lammps_input_safety(self):
        cfg = load_grid_config(CONFIG_PATH)
        runner = object.__new__(GpuGridRunner)
        runner.cfg = cfg
        template = """
units metal
atom_style atomic
read_data old.data
pair_style meam
pair_coeff * * old AlS FeS
neighbor 2.0 bin
neigh_modify delay 0 every 1 check yes
thermo 100
group inclusion id 1:2
velocity all create 300.0 123 mom yes rot no dist gaussian
fix nvt_all all nvt temp 300.0 300.0 0.1
dump d1 all custom 100 dump.old id type x y z
run 2000
write_data old_final
write_dump all custom dump.old_final id type x y z
"""
        text = runner.input_for_phase(
            template_text=template,
            data_path=Path("data.test"),
            stage="B3_realism_100k",
            atom_target=100000,
            eps_z=0.0025,
            phase="smoke",
            steps=2000,
            inclusion_id_min=1,
            inclusion_id_max=2,
            case_name="B3_test_smoke",
        )
        self.assertIn("neigh_modify    delay 0 every 10 check no", text)
        low = text.lower()
        self.assertNotIn("cuda_launch_blocking", low)
        self.assertNotIn("compute-sanitizer", low)
        self.assertNotRegex(text, r"(?mi)^\s*minimize\b")
        self.assertNotRegex(text, r"(?mi)^\s*min_style\b")
        self.assertNotRegex(text, r"(?mi)^\s*thermo\s+1\s*$")

    def test_chunked_production_uses_short_run_local_filenames(self):
        cfg = load_grid_config(CONFIG_PATH)
        runner = object.__new__(GpuGridRunner)
        runner.cfg = cfg
        case_name = "B3_nearGB_vacancies_medium_eps0025_production"
        chunk_tag = "chunk0000000_0010000"
        base = f"""
read_data data.test
dump d1 all custom 1000 dump.{case_name}.lammpstrj id type x y z
restart 10000 restart.{case_name}.*
run 100000
write_data data.{case_name}_final
write_dump all custom dump.{case_name}_final.lammpstrj id type x y z modify sort id
"""
        text = runner._chunk_input_text(
            base,
            case_name=case_name,
            start_step=0,
            end_step=10000,
            final_chunk=True,
            chunk_tag=chunk_tag,
        )
        self.assertIn(f"dump.{chunk_tag}.lammpstrj", text)
        self.assertIn("restart         10000 restart.*", text)
        self.assertIn("write_restart   restart.10000", text)
        self.assertIn("write_data data.final", text)
        self.assertIn("dump.final.lammpstrj", text)
        self.assertNotIn(f"dump.{case_name}.", text)
        self.assertNotIn(f"restart.{case_name}.", text)
        self.assertNotIn(f"data.{case_name}_final", text)

    def test_analysis_accepts_short_chunked_final_dump_name(self):
        cfg = load_grid_config(CONFIG_PATH)
        runner = object.__new__(GpuGridRunner)
        runner.cfg = cfg
        case_name = "B3_nearGB_vacancies_medium_eps0025_production"
        marked = {}
        runner.state = type(
            "FakeState",
            (),
            {"mark_case": lambda _self, cid, rec: marked.update({cid: rec})},
        )()
        runner.write_defect_summary = lambda: None
        with tempfile.TemporaryDirectory(prefix="stageb_short_dump_") as tmp:
            work_dir = Path(tmp)
            dump = work_dir / "dump.final.lammpstrj"
            dump.write_text("ITEM: TIMESTEP\n100000\n", encoding="utf-8")
            rec = {
                "case_id": case_name,
                "stage": "B3_realism_100k",
                "atom_target": 100000,
                "eps_z": 0.0025,
                "input": str(work_dir / "in.chunk0000000_0010000"),
                "outputs": [{"name": dump.name, "path": str(dump)}],
                "structure": {
                    "matrix_max_id": 10,
                    "center_A": [1.0, 2.0, 3.0],
                    "inclusion_axes_A": [4.0, 5.0, 6.0],
                },
            }
            with patch(
                "stage_runner.gpu_grid.analyze_dump",
                return_value={"dump": str(dump), "dislocation_segments": 0},
            ):
                ok = runner.analyze_case(rec)
        self.assertTrue(ok)
        self.assertIn(case_name, marked)
        self.assertEqual(Path(rec["analysis"]).name, "analysis.json")

    def test_bounded_config_has_no_large_or_factorial_scope(self):
        cfg = load_grid_config(CONFIG_PATH)
        text = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertNotIn("A2", text)
        self.assertNotIn("250k", text)
        self.assertNotIn("500k", text)
        self.assertNotIn("700k", text)
        self.assertNotIn("FeAl", text)
        self.assertNotIn("Fe3Al", text)
        self.assertNotIn("factorial", text.lower())
        stage = cfg["stages"]["B3_realism_100k"]
        self.assertEqual(max(stage["atom_targets"]), 100000)
        self.assertLessEqual(len(stage["cases"]), 6)
        self.assertLessEqual(stage["max_production_cases"], 6)

    def test_planner_cli_modes_still_pass(self):
        with tempfile.TemporaryDirectory(prefix="stageb_cli_") as tmp:
            modes = [
                ["--plan-only"],
                ["--cost-model"],
                ["--mock-decisions"],
                ["--export-policy", "--output-root", tmp],
                ["--generate-stageB-queue", "--output-root", tmp],
            ]
            for args in modes:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    rc = planner_main(args)
                self.assertEqual(rc, 0, args)


if __name__ == "__main__":
    unittest.main()
