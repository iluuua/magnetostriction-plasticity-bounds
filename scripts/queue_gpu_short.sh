#!/usr/bin/env bash
# Shortened tail of the GPU chain (4 Sept 2026, deadline pressure):
#   wait for G15 ctl (full ramp to 400 MPa) to finish, kill the automatic
#   full-length G15 fld that the running chain launches, and run instead
#   G15 fld to 60,000 steps (tau to 214 MPa: the onsets lie below 130 MPa in
#   the control) and G16 ctl+fld for 30 ps each.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
G=$(ls -dt runs/stageG15_unified/*/ | head -1)
step() { echo "[$(date +%H:%M:%S)] $*"; }
step "waiting for G15 ctl in $G"
until grep -q "Total wall time" "$G/G15_ctl/log.lammps" 2>/dev/null; do sleep 60; done
step "G15 ctl finished"
until [ -f "$G/G15_fld/log.lammps" ]; do sleep 10; done
sleep 30
for pid in $(wmic process where "name='lmp_kokkos_cuda.exe'" get ProcessId 2>/dev/null | grep -o "[0-9]\+"); do MSYS_NO_PATHCONV=1 taskkill /PID $pid /F; done
for pid in $(wmic process where "name='python.exe'" get CommandLine,ProcessId 2>/dev/null | grep "run_stageG15" | grep -o "[0-9]\+ *$" | grep -o "[0-9]\+"); do MSYS_NO_PATHCONV=1 taskkill /PID $pid /F; done
sleep 15
step "killed the full-length fld; launching G15 fld to 60000 steps"
$PY scripts/run_stageG15_unified_dynamics.py --only G15 --cases fld --nsteps 60000 || { step "FAILED G15 fld"; exit 1; }
step "G15 fld done; launching G16 (30 ps each)"
$PY scripts/run_stageG15_unified_dynamics.py --only G16 --nsteps-g16 30000 || { step "FAILED G16"; exit 1; }
step "short chain complete"
