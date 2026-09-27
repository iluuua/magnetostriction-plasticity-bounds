"""Regression tests for the retained publication analysis, without MD runs.

Run ``python -m unittest discover -s tests -p test_publication_analysis.py``.
The paired interface dumps and reference records must be present in a clone.
NumPy and SciPy are required; the numerical tests do not require OVITO.
"""

# Standalone unittest needs the analysis path before importing its modules.
# ruff: noqa: E402
from __future__ import annotations

import copy
import csv
import gzip
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis" / "python"))

import _g4clean as snapshots
import stageG2_depinning as motion
import stageG5_two_scale_bridge as bridge
import stageG6_vstar_analysis as alloy
import stageG8_eshelby3d as eshelby
import stageG10_field_profile as profile
import stageG12_eigenstrain_retention as strain


def snapshot_text(columns=None, ids=(2, 1)):
    """A reordered two-atom snapshot with an unrelated energy column."""
    columns = columns or [
        "c_pe_atom",
        "z",
        "id",
        "type",
        "y",
        "x",
        *reversed(snapshots.STRESS_COLUMNS),
    ]
    header = (
        "ITEM: TIMESTEP\n235\nITEM: NUMBER OF ATOMS\n2\n"
        "ITEM: BOX BOUNDS pp pp ff\n0 155\n0 65\n-10 166\n"
        "ITEM: ATOMS " + " ".join(columns) + "\n"
    )
    rows = []
    for atom_id in ids:
        values = {"id": atom_id, "type": 1, "x": atom_id * 2, "y": 5, "z": 46, "c_pe_atom": -999}
        values.update({f"c_st[{i}]": atom_id * 10 + i for i in range(1, 7)})
        rows.append(" ".join(str(values[column]) for column in columns))
    return header + "\n".join(rows) + "\n"


class SnapshotTests(unittest.TestCase):
    def test_gzip_header_mapping_and_id_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.lammpstrj.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(snapshot_text())
            with snapshots.open_dump(Path(directory), "sample.lammpstrj") as stream:
                frame = snapshots.read_snapshot(stream, require_stress=True)
            np.testing.assert_array_equal(frame.ids, [1, 2])
            np.testing.assert_array_equal(frame.positions[:, 0], [2, 4])
            np.testing.assert_array_equal(
                frame.stress, [[11, 12, 13, 14, 15, 16], [21, 22, 23, 24, 25, 26]]
            )
            self.assertEqual(len(snapshots.file_provenance(path)["sha256"]), 64)

    def test_multiple_frames_and_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "one snapshot"):
            snapshots.read_snapshot(io.StringIO(snapshot_text() * 2))
        with self.assertRaisesRegex(ValueError, "Duplicate atom IDs"):
            snapshots.read_snapshot(io.StringIO(snapshot_text(ids=(1, 1))))

    def test_required_components_cannot_be_positional_substitutes(self):
        columns = ["id", "type", "x", "y", "z", "c_pe_atom", *snapshots.STRESS_COLUMNS[:-1]]
        with self.assertRaisesRegex(ValueError, "Missing atom columns"):
            snapshots.read_snapshot(io.StringIO(snapshot_text(columns)), require_stress=True)

    def test_pair_correspondence_and_box_validation(self):
        control = snapshots.read_snapshot(io.StringIO(snapshot_text()))
        field = copy.deepcopy(control)
        field.ids[0] = 99
        with self.assertRaisesRegex(ValueError, "different atom IDs"):
            snapshots.validate_pair(control, field)
        field = copy.deepcopy(control)
        field.bounds[0, 1] += 1
        with self.assertRaisesRegex(ValueError, "same fixed box"):
            snapshots.validate_pair(control, field)

    def test_zero_padded_trajectory_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in (2, 0, 1):
                (Path(directory) / f"trajectory.{index:03d}.lammpstrj.gz").touch()
            paths = snapshots.trajectory_paths(str(Path(directory) / "trajectory.*.lammpstrj.gz"))
            self.assertEqual(
                [path.name for path in paths],
                [f"trajectory.{i:03d}.lammpstrj.gz" for i in range(3)],
            )


class StressTests(unittest.TestCase):
    def test_twelve_distinct_orthonormal_slip_systems(self):
        systems = profile.slip_systems_lab()
        self.assertEqual(len(systems), 12)
        self.assertEqual(len({label for _, _, label in systems}), 12)
        for normal, direction, _ in systems:
            self.assertAlmostEqual(np.linalg.norm(normal), 1)
            self.assertAlmostEqual(np.linalg.norm(direction), 1)
            self.assertAlmostEqual(float(normal @ direction), 0)
        stress = profile.tensor([0, 0, 0, 0, 7, 0])
        maximum = max(abs(float(normal @ stress @ direction)) for normal, direction, _ in systems)
        self.assertAlmostEqual(maximum, 7)

    def test_tensor_difference_precedes_invariant(self):
        control = snapshots.DumpFrame(
            0,
            np.arange(1, 201),
            np.ones(200, dtype=int),
            np.column_stack((np.linspace(0, 154, 200), np.zeros(200), np.full(200, 46))),
            np.array([[0, 155], [0, 65], [-10, 166]]),
            (),
            np.tile(np.array([3, -1, 0, 0, 0, 0]) * (-10 * profile.V_AT), (200, 1)),
        )
        field = copy.deepcopy(control)
        field.stress *= -1
        control.types[-1] = field.types[-1] = 2
        control.positions[-1, 2] = field.positions[-1, 2] = 39
        row = profile.field_profile(control, field, matrix_atoms=199)["profile"][-1]
        self.assertEqual(row["diff_of_vm_MPa"], 0)
        self.assertGreater(row["vm_of_difference_MPa"], 0)
        self.assertGreater(row["max_RSS_MPa"], 0)


class PublishedPairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with snapshots.open_dump(snapshots.DEFAULT_DIR, snapshots.CONTROL) as stream:
            cls.control = snapshots.read_snapshot(stream, require_stress=True)
        with snapshots.open_dump(snapshots.DEFAULT_DIR, snapshots.FIELD) as stream:
            cls.field = snapshots.read_snapshot(stream, require_stress=True)

    def test_default_profile_matches_every_published_bin(self):
        expected = json.loads(
            (REPO / "docs/reports/stageG10_field_profile.json").read_text(encoding="utf-8")
        )
        actual = profile.field_profile(self.control, self.field)
        self.assertEqual(profile.R_MAX, 110)
        self.assertEqual(actual["profile"], expected["profile"])
        self.assertEqual(actual["peak"]["max_RSS_MPa"], 5.651)
        self.assertEqual(actual["ridge_apex_A"], 39.718591)
        self.assertEqual(sum(row["above_apex"] for row in actual["profile"]), 23)
        self.assertFalse(
            any(row["n_inclusion_al_atoms"] for row in actual["profile"] if row["above_apex"])
        )
        self.assertEqual(len(actual["profile"]), 28)
        self.assertEqual(actual["axis_window"]["width_A"], 20)
        self.assertEqual(actual["noise_floor_beyond_60A"]["n_bins"], 13)

    def test_retention_and_small_standard_error(self):
        expected = json.loads(
            (REPO / "docs/reports/stageG12_eigenstrain_retention.json").read_text(encoding="utf-8")
        )
        actual = strain.retention(self.control, self.field)
        self.assertEqual(actual["subsets"], expected["subsets"])
        self.assertEqual(actual["eta_used_for_rescaling"], 0.9728)
        self.assertEqual(actual["eta_used_for_rescaling_se"], 0.0038)
        self.assertEqual(actual["subsets"]["ridge_only_z_gt_22"]["n_atoms"], 1008)

    def test_inclusion_aluminium_in_either_snapshot_sets_cutoff(self):
        field = copy.deepcopy(self.field)
        index = np.flatnonzero((field.ids > profile.MATRIX_ATOMS) & (field.types == 1))[0]
        field.positions[index, 2] = 42.0
        actual = profile.field_profile(self.control, field)
        self.assertEqual(actual["ridge_apex_A"], 42.0)
        self.assertEqual(actual["inclusion_max_z_A"]["field"], 42.0)
        first = next(row for row in actual["profile"] if row["above_apex"])
        self.assertEqual(first["r_A"], 26.0)

    def test_noncontiguous_matrix_ids_are_rejected(self):
        control, field = copy.deepcopy(self.control), copy.deepcopy(self.field)
        control.ids[0] = field.ids[0] = 0
        with self.assertRaisesRegex(ValueError, "contiguous matrix IDs"):
            profile.field_profile(control, field)

    def test_profile_cli_writes_only_requested_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "profile.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(REPO / "analysis/python/stageG10_field_profile.py"),
                    "--out",
                    str(output),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("sha256", record["inputs"]["control"])
            with output.with_suffix(".csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(record["profile"]))
            self.assertIn("d_sigma_xz_axis_MPa", rows[0])


class OnsetTests(unittest.TestCase):
    def setUp(self):
        self.previous_lx = motion.LX
        motion.LX = 154.6442530455

    def tearDown(self):
        motion.LX = self.previous_lx

    @staticmethod
    def frames(displacements):
        rows = []
        for i, displacement in enumerate(displacements):
            rows.append(
                {
                    "frame": i,
                    "step": i * 2000,
                    "tau_nominal_MPa": 0 if i < 5 else 50 + 10 * (i - 5),
                    "x_plus": None if displacement is None else 50 + displacement,
                    "x_minus": 30,
                }
            )
        return rows

    def test_last_frame_cannot_establish_sustained_onset(self):
        result = motion.analyze_frames(self.frames([0, 0, 0, 0, 0, 20]))
        self.assertIsNone(result["per_line"]["plus"]["onset"])
        self.assertIsNone(result["onset"])

    def test_two_subsequent_frames_can_establish_departure(self):
        result = motion.analyze_frames(self.frames([0, 0, 0, 0, 0, 20, 21, 22]))
        self.assertEqual(result["per_line"]["plus"]["onset"]["step"], 10000)

    def test_missing_frames_sustain_departure_but_reacquisition_is_untrusted(self):
        result = motion.analyze_frames(self.frames([0, 0, 0, 0, 0, 20, None, None]))
        self.assertEqual(result["per_line"]["plus"]["onset"]["step"], 10000)
        result = motion.analyze_frames(self.frames([0, 0, 0, 0, 0, None, 20, 21, 22]))
        line = result["per_line"]["plus"]
        self.assertIsNone(line["onset"])
        self.assertEqual(line["candidate_onset"]["step"], 12000)
        self.assertEqual(line["lineage_status"], "untrusted_after_gap")
        self.assertIsNone(result["onset"])

    def test_saved_held_onsets_preserve_upper_and_reject_lower_reacquisition(self):
        for case, step in (("ctl", 38000), ("fld", 40000)):
            path = REPO / f"docs/reports/stageG2_depinning_G15_{case}_G15held.csv"
            with path.open(newline="", encoding="utf-8") as stream:
                frames = [
                    {
                        key: value
                        if key.startswith("lineage_")
                        else None
                        if value == ""
                        else float(value)
                        for key, value in row.items()
                    }
                    for row in csv.DictReader(stream)
                ]
            result = motion.analyze_frames(frames)
            self.assertEqual(result["per_line"]["minus"]["onset"]["step"], step)
            lower = result["per_line"]["plus"]
            self.assertEqual(lower["line_gone_at_step"], 10000)
            self.assertIsNone(lower["onset"])
            self.assertIsNotNone(lower["candidate_onset"])

    def test_command_overrides_and_nominal_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cmd.json"
            path.write_text(
                json.dumps(["lmp", "-var", "NSTEPS", "45000", "-var", "TAUMAX_MPA", "145.45"]),
                encoding="utf-8",
            )
            ramp, sources = motion.ramp_parameters(path)
        self.assertAlmostEqual(motion.tau_nominal_mpa(45000, ramp), 145.45)
        self.assertEqual(motion.tau_nominal_mpa(5000, ramp), 0)
        self.assertTrue(sources["tau_max_mpa"].endswith("cmd.json"))
        self.assertLess(motion.tau_nominal_mpa(44000, ramp), 145.45)

    def test_log_header_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log.lammps.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                stream.write(
                    "Step Temp Atoms v_tauUppMPa v_taubar v_tauLowMPa Extra\n"
                    "10000 300 100 8 1000 7 123\n"
                )
            data = motion.parse_log(path)
        np.testing.assert_array_equal(data["tauLow"], [7])
        np.testing.assert_array_equal(data["tauUpp"], [8])
        np.testing.assert_array_equal(data["taubar"], [1000])


class ContinuumTests(unittest.TestCase):
    def test_weak_bias_limit_and_inverse_bridge(self):
        volume = 70
        stress = 1.0
        x = volume * bridge.B3 * stress / bridge.KT_300
        self.assertAlmostEqual(
            bridge.enhancement(stress, volume) / (bridge.F_VOL * x * x / 2), 1, places=10
        )
        expected = [62.7, 39.7, 23.8, 17.0, 11.9, 8.4]
        actual = [round(bridge.required_sigma(v) / 1e6, 1) for v in (19, 30, 50, 70, 100, 142)]
        self.assertEqual(actual, expected)

    def test_sphere_and_cylinder_interior_reference(self):
        tensor = eshelby.eigenstrain_tensor()
        self.assertAlmostEqual(float(np.trace(tensor)), 0)
        stiffness = eshelby.stiffness()
        sphere = eshelby.interior_stress(eshelby.eshelby_sphere(), stiffness, tensor)
        cylinder = eshelby.interior_stress(eshelby.eshelby_cylinder(), stiffness, tensor)
        sphere_rss = eshelby.max_rss(sphere, eshelby.slip_systems())[0] / 1e6
        cylinder_rss = eshelby.max_rss(cylinder, eshelby.slip_systems())[0] / 1e6
        self.assertAlmostEqual(sphere_rss, 41.45, delta=0.01)
        self.assertAlmostEqual(cylinder_rss, 39.03, delta=0.01)


class AlloyTests(unittest.TestCase):
    def test_loading_displacement_excludes_initial_preload(self):
        path = REPO / "docs/reports/stageG6_vstar_relA_frames.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = [
                {"step": int(row["step"]), "ux_lo": float(row["ux_lo"])}
                for row in csv.DictReader(stream)
            ]
        measured = alloy.loading_motion(rows)
        self.assertEqual(measured["start_step"], 10000)
        self.assertEqual(measured["end_step"], 130000)
        self.assertAlmostEqual(measured["net_displacement_A"], 1.97543439318)
        self.assertAlmostEqual(measured["position_std_A"], 0.62520850411)
        self.assertAlmostEqual(rows[-1]["ux_lo"] - rows[0]["ux_lo"], 6.99107002966)

    def test_species_selections_are_explicit(self):
        positions = np.array([[20, 0, 80], [20, 1, 80], [20, 2, 80]], dtype=float)
        types = np.array([1, 2, 3])
        virials = np.zeros((3, 6))
        virials[:, 4] = -10 * alloy.V_AT * np.array([1, 10, 100])
        for selection, expected, count in (
            ("legacy", 50.5, 2),
            ("aluminium", 1.0, 1),
            ("alloy", 37.0, 3),
        ):
            value, sampled = alloy.sample_shear(positions, types, virials, selection)
            self.assertAlmostEqual(value, expected)
            self.assertEqual(sampled, count)

    def test_historical_activation_fit_remains_diagnostic(self):
        path = REPO / "docs/reports/stageG6_vstar_relA_summary.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        fit = alloy.diagnostic_activation_fit(record["rungs"])
        self.assertAlmostEqual(fit["V_star_b3"], record["V_star_b3"], places=9)
        self.assertAlmostEqual(fit["V_star_err_b3"], record["V_star_err_b3"], places=9)
        self.assertIn("diagnostic", fit["fit_status"])


if __name__ == "__main__":
    unittest.main()
