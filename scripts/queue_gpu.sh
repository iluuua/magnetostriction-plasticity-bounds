#!/usr/bin/env bash
# One GPU, four jobs, in the order the paper needs them, as one chain:
#   1. G13 free pair, v2 protocol, unified cell    -> does v2 remove the residue?
#   2. G13 held pair, v2 protocol, unified cell    -> the paper's Fig. 1 numbers
#   3. G16 dipole under the maintained field, no load, ctl + fld (60 ps each)
#   4. G15 shear ramp to 400 MPa, ctl + fld (96 ps each)
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
step() { echo "[$(date +%H:%M:%S)] $*"; }
step "1/4 G13 free pair v2"
$PY scripts/run_stageG13_interface100k.py --cell u100k --protocol v2 --only ctl_free,fld_free || { step "FAILED at 1/4"; exit 1; }
step "2/4 G13 held pair v2"
$PY scripts/run_stageG13_interface100k.py --cell u100k --protocol v2 --only ctl_held,fld_held || { step "FAILED at 2/4"; exit 1; }
step "3/4 G16 dipole under maintained field"
$PY scripts/run_stageG15_unified_dynamics.py --only G16 --nsteps-g16 60000 || { step "FAILED at 3/4"; exit 1; }
step "4/4 G15 shear ramp"
$PY scripts/run_stageG15_unified_dynamics.py --only G15 || { step "FAILED at 4/4"; exit 1; }
step "queue complete"
