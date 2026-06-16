"""Layered Multi-Fidelity Scientific Optimizer (planner/scheduler layer).

This package is a *decision layer* above the existing stage_runner GPU
pipeline. It never launches LAMMPS and never touches active run roots.
It plans: what to run next, at which size scale, at which fidelity, and
when to stop / promote / pivot a branch.

Modes: planner_only. MD execution is forbidden by design (see
configs/layered_optimizer_policy.yaml: optimizer.no_md_execution).
"""

from __future__ import annotations

__version__ = "0.1.0"

PLANNER_NAME = "layered_multifidelity_optimizer"
