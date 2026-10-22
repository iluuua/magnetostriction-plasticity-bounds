#!/usr/bin/env bash
# Static pairs of the embedded-inclusion cell, run after the reference relaxation.
#
#   bash scripts/queue_embedded_static.sh <control run dir> [eps]
#
# 1. waits for <control run dir>/done.txt (written when in.relax_control ends);
# 2. builds the +eps cell (matrix started from the continuum displacement) and
#    the -eps cell (plain start) from the relaxed reference;
# 3. runs lammps/embedded_inclusion/in.static_pair for the reference (eps = 0),
#    +eps and -eps, one after the other, in <control run dir>/static/;
# 4. extracts the field at both CG stages (convergence check) and the forces
#    that hold the inclusion in shape.
set -u
CTL="$1"
EPS="${2:-1.94e-3}"
R="$(cd "$(dirname "$0")/.." && pwd)"
PY="$R/.venv/Scripts/python.exe"
LMP="B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe"
KK="-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off"
POT="$R/potentials/meam/Jelinek_2012"

while [ ! -f "$CTL/done.txt" ]; do sleep 60; done
grep -q "exit 0" "$CTL/done.txt" || { echo "reference relaxation failed"; exit 1; }

NAL=$("$PY" -c "import json,glob; print(json.load(open(glob.glob('$CTL/*_metadata.json')[0]))['N_AL'])")
RAD=$("$PY" -c "import json,glob; print(json.load(open(glob.glob('$CTL/*_metadata.json')[0]))['radius_A'])")
REF=$(ls "$CTL"/*.control.data | head -1)
OUT="$CTL/static"
mkdir -p "$OUT"
cp "$R/lammps/embedded_inclusion/in.static_pair" "$OUT/"
"$PY" "$R/scripts/make_strained_inclusion.py" --control "$REF" --n-al "$NAL" --eps="$EPS" --guess \
      --radius "$RAD" --out "$OUT/plus.data" > "$OUT/plus.make.log" 2>&1
# -eps from the plain start (inclusion moved, matrix not): the symmetric part
# (d(+eps) + d(-eps))/2 then bounds nonlinearity and start dependence together
"$PY" "$R/scripts/make_strained_inclusion.py" --control "$REF" --n-al "$NAL" --eps="-$EPS" \
      --out "$OUT/minus.data" > "$OUT/minus.make.log" 2>&1
cp "$REF" "$OUT/ref.data"

cd "$OUT"
for c in ref plus minus; do
  echo "$(date +%F' '%T) start $c" >> queue.log
  $LMP $KK -in in.static_pair -var DATA_FILE $c.data -var POT_DIR "$POT" -var OUT_PREFIX $c \
       -var N_AL "$NAL" -log log.$c > stdout.$c 2>&1
  echo "$(date +%F' '%T) end $c exit $?" >> queue.log
done

LABEL="sphere R=$RAD A, eps=$EPS along x, inclusion held, fixed box"
"$PY" "$R/analysis/python/embedded_inclusion_field.py" --control ref.static.lammpstrj \
     --strained plus.static.lammpstrj --minus minus.static.lammpstrj --n-al "$NAL" \
     --radius "$RAD" --label "$LABEL" --out field.json > field.log 2>&1
"$PY" "$R/analysis/python/embedded_inclusion_field.py" --control ref.static1.lammpstrj \
     --strained plus.static1.lammpstrj --minus minus.static1.lammpstrj --n-al "$NAL" \
     --radius "$RAD" --label "$LABEL (first CG stage)" --out field_stage1.json > field_stage1.log 2>&1
"$PY" "$R/analysis/python/embedded_holding_forces.py" --control ref.forces.lammpstrj \
     --strained plus.forces.lammpstrj --radius "$RAD" --out holding_forces.json > holding_forces.log 2>&1
echo "$(date +%F' '%T) analysis done" >> queue.log
