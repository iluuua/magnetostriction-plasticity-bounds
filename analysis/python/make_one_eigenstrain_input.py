#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]

tag = sys.argv[1]
run_dir = ROOT / f"lammps/04_ellipsoid_inclusion/trial_001/02_eigenstrain_relax/{tag}_minimize"
run_dir.mkdir(parents=True, exist_ok=True)

input_path = run_dir / f"in.ellipsoid_eigenstrain_{tag}_minimize"

input_path.write_text(f"""units           metal
dimension       3
boundary        p p p
atom_style      atomic

read_data       ../../../../../structures/interface/ellipsoid_inclusion/trial_001/eigenstrain/{tag}/data.ellipsoid_eigenstrain_{tag}

mass            1 26.9815385
mass            2 55.845

pair_style      meam
pair_coeff      * * ../../../../../potentials/meam/Jelinek_2012/Jelinek_2012_meamf AlS SiS MgS CuS FeS ../../../../../potentials/meam/Jelinek_2012/Jelinek_2012_meam.alsimgcufe AlS FeS

neighbor        2.0 bin
neigh_modify    delay 0 every 1 check yes

compute         pe_atom all pe/atom
compute         stress_atom all stress/atom NULL

thermo          100
thermo_style    custom step atoms temp pe etotal press pxx pyy pzz lx ly lz
thermo_modify   lost warn flush yes

dump            d0 all custom 100 dump.ellipsoid_eigenstrain_{tag}_minimize.lammpstrj id type x y z c_pe_atom c_stress_atom[1] c_stress_atom[2] c_stress_atom[3]
dump_modify     d0 sort id

run             0

min_style       cg
minimize        1.0e-8 1.0e-10 10000 100000

write_data      data.ellipsoid_eigenstrain_{tag}_minimized
write_dump      all custom dump.ellipsoid_eigenstrain_{tag}_minimized_final.lammpstrj id type x y z modify sort id

undump          d0
""")

print(input_path)
