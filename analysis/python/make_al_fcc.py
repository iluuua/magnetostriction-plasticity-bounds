from ase.build import bulk
from ase.io import write
from pathlib import Path

out_dir = Path("structures/converted/Al")
out_dir.mkdir(parents=True, exist_ok=True)

# fcc aluminum, стартовый параметр решётки ~4.05 Å
al = bulk("Al", "fcc", a=4.05, cubic=True)

# 10x10x10 conventional cells
al = al.repeat((10, 10, 10))

write(out_dir / "al_fcc.data", al, format="lammps-data", atom_style="atomic")

print(f"Saved: {out_dir / 'al_fcc.data'}")
print(f"Atoms: {len(al)}")
