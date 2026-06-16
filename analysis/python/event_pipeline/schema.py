"""Shared schemas for event timeline and visualization manifests."""

from __future__ import annotations

from dataclasses import dataclass


EVENT_CLASSES = ("no_event", "deformation_only", "weak_hcp", "confirmed_DXA")

MANIFEST_FIELDS = [
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

TIMELINE_EXTRA_FIELDS = [
    "stage",
    "phase",
    "analysis_file",
    "event_score",
    "event_reasons",
]


@dataclass(frozen=True)
class EventThresholds:
    """Conservative, configurable thresholds for first-pass event classes."""

    confirmed_dxa_min_segments: int = 1
    confirmed_dxa_min_line_length_A: float = 1.0e-9
    weak_hcp_min_atoms: int = 5
    weak_hcp_min_pct: float = 0.01
    weak_other_min_atoms: int = 10
    deformation_strain_p95_min: float = 0.01
    deformation_strain_p99_min: float = 0.02
    deformation_dmin2_p95_min: float = 0.1
    deformation_dmin2_p99_min: float = 0.2
    deformation_displacement_p95_min_A: float = 0.75
    deformation_displacement_max_min_A: float = 2.0


def manifest_headers(extra: bool = False) -> list[str]:
    if extra:
        return MANIFEST_FIELDS + TIMELINE_EXTRA_FIELDS
    return list(MANIFEST_FIELDS)
