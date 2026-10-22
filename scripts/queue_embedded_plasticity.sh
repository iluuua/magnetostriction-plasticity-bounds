#!/usr/bin/env bash
# Elastic or plastic? Calculations run after the static field pair.
#
#   bash scripts/queue_embedded_plasticity.sh <reference run dir> <new dislocation run dir> [eps]
#
# Waits until <reference run dir>/static/queue.log says "analysis done", then, one
# LAMMPS job at a time:
#
# 1. A straight edge dislocation 12 A above the sphere, with the sphere centre
#    15 A ahead of the line, where the line-averaged shear of the field is
#    largest (structures/embedded_inclusion/slab_sphere_R25_dx15):
#      ctl  the slab relaxed with the sphere held unstrained (in.disl_relax, CG only);
#      fld  the sphere given +eps, matrix relaxed again from ctl (plain start);
#      rev  the strain removed again (inclusion back at its ctl positions), relaxed.
#    The core positions (embedded_disl_states.py) answer whether the field moves
#    the line and whether it comes back when the strain is removed.
# 2. The plasticity margin of the field cell: the sphere at 4 eps (plain start
#    from the reference) and then at 10 eps (from the relaxed 4 eps matrix), each
#    relaxed by in.static_pair; DXA and structure census (embedded_dxa.py) and the
#    field (embedded_inclusion_field.py) of both.
# 3. If the control slab is clean (two partials, nothing else), strain-controlled
#    ramps from ctl and fld towards the sphere (in.disl_sweep, DELTA 0.0057 A,
#    about 1.3 MPa per step), and the depinning stresses (embedded_sweep.py).
#
# Exit codes are logged from the LAMMPS command itself; convergence is judged from
# the CHUNK lines of each log, not from these codes.
set -u
CTL="$(cd "$1" && pwd -W)"
DISL="$2"
EPS="${3:-1.94e-3}"
R="$(cd "$(dirname "$0")/.." && pwd)"
PY="$R/.venv/Scripts/python.exe"
LMP="B:/builds/lammps-kokkos-cuda-cuda124-msvc1439/build/lmp_kokkos_cuda.exe"
KK="-k on g 1 -sf kk -pk kokkos newton on neigh half gpu/aware off"
POT="$R/potentials/meam/Jelinek_2012"
STR="$R/structures/embedded_inclusion/slab_sphere_R25_dx15"
NAME="$(basename "$STR")"

until grep -q "analysis done" "$CTL/static/queue.log" 2>/dev/null; do sleep 120; done

mkdir -p "$DISL" "$CTL/margin"
DISL="$(cd "$DISL" && pwd -W)"
log() { echo "$(date +%F' '%T) $*" >> "$DISL/queue.log"; }
cp "$STR/data.$NAME" "$STR/${NAME}_metadata.json" "$R/lammps/embedded_inclusion/in.disl_relax" \
   "$R/lammps/embedded_inclusion/in.disl_sweep" "$DISL/"
read NAL ZBOT ZTOP ZGL LX H < <("$PY" -c "
import json; m = json.load(open('$DISL/${NAME}_metadata.json'))
zb = m['z_bottom_block_top_A'] + 0.01; zt = m['z_top_block_bottom_A'] - 0.01
print(m['N_AL'], round(zb, 3), round(zt, 3), round(m['z_glide_A'], 3), m['box_A'][0], round(zt - zb, 3))")

# --- 1. the dislocation without load: ctl, fld, rev ---------------------------
cd "$DISL"
log "start ctl relax"
$LMP $KK -in in.disl_relax -var DATA_FILE data.$NAME -var POT_DIR "$POT" -var OUT_PREFIX ctl \
     -var N_AL $NAL -var ZBOT $ZBOT -var ZTOP $ZTOP -var ANNEAL_STEPS 0 -var NZFIX 3 \
     -log log.ctl_relax > stdout.ctl_relax 2>&1
log "end ctl relax exit $?"
"$PY" "$R/scripts/make_strained_inclusion.py" --control ctl.relaxed.data --n-al $NAL --eps="$EPS" \
      --out fld.start.data > fld.make.log 2>&1
log "start fld relax"
$LMP $KK -in in.disl_relax -var DATA_FILE fld.start.data -var POT_DIR "$POT" -var OUT_PREFIX fld \
     -var N_AL $NAL -var ZBOT $ZBOT -var ZTOP $ZTOP -var NZFIX 1 -log log.fld_relax > stdout.fld_relax 2>&1
log "end fld relax exit $?"
"$PY" "$R/scripts/make_strained_inclusion.py" --control fld.relaxed.data --inclusion-from ctl.relaxed.data \
      --n-al $NAL --eps=0 --out rev.start.data > rev.make.log 2>&1
log "start rev relax"
$LMP $KK -in in.disl_relax -var DATA_FILE rev.start.data -var POT_DIR "$POT" -var OUT_PREFIX rev \
     -var N_AL $NAL -var ZBOT $ZBOT -var ZTOP $ZTOP -var NZFIX 1 -log log.rev_relax > stdout.rev_relax 2>&1
log "end rev relax exit $?"
"$PY" "$R/analysis/python/embedded_disl_states.py" --dir . --meta "${NAME}_metadata.json" \
      --states ctl fld rev --out states.json > states.log 2>&1
CLEAN=$?
log "states done, control clean: $([ $CLEAN -eq 0 ] && echo yes || echo no)"

# --- 2. plasticity margin of the field cell: 4 eps, then 10 eps ----------------
M="$CTL/margin"
cd "$M"
read CNAL RAD < <("$PY" -c "
import json, glob; m = json.load(open(glob.glob('$CTL/*_metadata.json')[0])); print(m['N_AL'], m['radius_A'])")
cp "$R/lammps/embedded_inclusion/in.static_pair" .
E4=$("$PY" -c "print(4 * $EPS)")
E10=$("$PY" -c "print(10 * $EPS)")
"$PY" "$R/scripts/make_strained_inclusion.py" --control ../static/ref.static.data --n-al $CNAL --eps="$E4" \
      --out x4.data > x4.make.log 2>&1
log "start margin x4"
$LMP $KK -in in.static_pair -var DATA_FILE x4.data -var POT_DIR "$POT" -var OUT_PREFIX x4 -var N_AL $CNAL \
     -var FTOL_A 0.003 -var FTOL_B 0.001 -var NCHUNK 5 -log log.x4 > stdout.x4 2>&1
log "end margin x4 exit $?"
"$PY" "$R/scripts/make_strained_inclusion.py" --control x4.static.data --inclusion-from ../static/ref.static.data \
      --n-al $CNAL --eps="$E10" --out x10.data > x10.make.log 2>&1
log "start margin x10"
$LMP $KK -in in.static_pair -var DATA_FILE x10.data -var POT_DIR "$POT" -var OUT_PREFIX x10 -var N_AL $CNAL \
     -var FTOL_A 0.003 -var FTOL_B 0.001 -var NCHUNK 5 -log log.x10 > stdout.x10 2>&1
log "end margin x10 exit $?"
"$PY" "$R/analysis/python/embedded_dxa.py" --dir . --cases x4 x10 --n-al $CNAL --radius $RAD \
      --out dxa.json > dxa.log 2>&1
for c in x4 x10; do
  "$PY" "$R/analysis/python/embedded_inclusion_field.py" --control ../static/ref.static.lammpstrj \
       --strained $c.static.lammpstrj --n-al $CNAL --radius $RAD \
       --label "sphere R=$RAD A, $c eps along x, inclusion held, fixed box" --out field_$c.json > field_$c.log 2>&1
done
log "margin analysis done"

# --- 3. loading ramps from ctl and fld ----------------------------------------
cd "$DISL"
if [ $CLEAN -eq 0 ]; then
  for c in ctl fld; do
    log "start ramp $c"
    $LMP $KK -in in.disl_sweep -var DATA_FILE $c.relaxed.data -var POT_DIR "$POT" -var OUT_PREFIX $c \
         -var N_AL $NAL -var ZBOT $ZBOT -var ZTOP $ZTOP -var ZGLIDE $ZGL -var NSTEP 20 -var DELTA 0.0057 \
         -var CG_FTOL 0.001 -var CGMAX 3000 -var NFULL 2 -log log.$c.sweep > stdout.$c.sweep 2>&1
    log "end ramp $c exit $?"
  done
  X0=$("$PY" -c "import json; print(json.load(open('states.json'))['states']['ctl']['core_x_A'])")
  "$PY" "$R/analysis/python/embedded_sweep.py" --control log.ctl.sweep --strained log.fld.sweep --delta 0.0057 \
       --lx $LX --h $H --x0 $X0 --full "ctl.full.*.lammpstrj" --out sweep.json > sweep.log 2>&1
  log "ramp analysis done"
else
  log "ramps skipped: control slab not clean (see states.log)"
fi
log "all done"
