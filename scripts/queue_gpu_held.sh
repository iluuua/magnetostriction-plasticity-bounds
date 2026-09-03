#!/usr/bin/env bash
# Tail of the GPU chain, 4 Sept 2026. The running chain finishes the
# untethered G15 ctl ramp to 400 MPa (nucleation check) and would then start
# an untethered fld ramp; that run is killed and replaced by a TETHERED pair
# (the strained ridge keeps its strain, as in the interface cells) ramped to
# 145 MPa in 45,000 steps - the same loading rate as the 400 MPa/96 ps ramp,
# covering the onsets seen in the control (95-125 MPa). G16 (30 ps, no load)
# runs last and may be cut.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
G=$(ls -dt runs/stageG15_unified/*/ | head -1)
step() { echo "[$(date +%H:%M:%S)] $*"; }
step "waiting for the untethered G15 ctl in $G"
until grep -q "Total wall time" "$G/G15_ctl/log.lammps" 2>/dev/null; do sleep 60; done
step "G15 ctl (untethered, to 400 MPa) finished"
until [ -f "$G/G15_fld/log.lammps" ]; do sleep 10; done
sleep 30
for pid in $(wmic process where "name='lmp_kokkos_cuda.exe'" get ProcessId 2>/dev/null | grep -o "[0-9]\+"); do MSYS_NO_PATHCONV=1 taskkill /PID $pid /F; done
for pid in $(wmic process where "name='python.exe'" get CommandLine,ProcessId 2>/dev/null | grep "run_stageG15" | grep -o "[0-9]\+ *$" | grep -o "[0-9]\+"); do MSYS_NO_PATHCONV=1 taskkill /PID $pid /F; done
sleep 15
step "killed the untethered fld; launching the tethered pair (45000 steps, 145 MPa)"
$PY scripts/run_stageG15_unified_dynamics.py --only G15 --cases ctl,fld --nsteps 45000 --taumax 145.45 --hold --tag _held || { step "FAILED G15 held pair"; exit 1; }
step "G15 held pair done; launching G16 (30 ps each)"
$PY scripts/run_stageG15_unified_dynamics.py --only G16 --nsteps-g16 30000 || { step "FAILED G16"; exit 1; }
step "held chain complete"
