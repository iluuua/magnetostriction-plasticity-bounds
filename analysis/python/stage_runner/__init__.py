"""Autopilot stage runner for the A0 / A1-small finite-T MD production sweep.

Al matrix + Fe4Al13 ellipsoid inclusion, magnetostriction-equivalent eigenstrain
surrogate (B = 0.7 T -> sigma_m ~ 147 MPa -> eps_z ~ 0.0025; overload probes
0.0050 / 0.0100). Orchestrates LAMMPS (MEAM) runs + OVITO DXA/CNA analysis.

All generated outputs live in isolated timestamped directories under
runs/stage_sweep_A0_A1_production/. Tracked templates are never modified.
"""

__version__ = "1.0.0"
