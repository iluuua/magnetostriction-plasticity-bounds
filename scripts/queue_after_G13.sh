#!/usr/bin/env bash
# Wait for the stage G13 minimisations to finish, then run G16 (held field, no
# load) and G15 (shear ramp) on the unified cells, back to back on the GPU.
cd "$(dirname "$0")/.."
d=$(ls -dt runs/stageG13_interface100k/*/ | head -1)
while ! grep -q '"finished"' "$d/status.json" 2>/dev/null; do sleep 60; done
echo "[$(date +%H:%M:%S)] G13 done, starting G16"
.venv/Scripts/python.exe scripts/run_stageG15_unified_dynamics.py --only G16 --nsteps-g16 60000
echo "[$(date +%H:%M:%S)] G16 done, starting G15"
.venv/Scripts/python.exe scripts/run_stageG15_unified_dynamics.py --only G15
echo "[$(date +%H:%M:%S)] queue complete"
