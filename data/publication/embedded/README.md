# Embedded-inclusion calculations

Configurations and logs behind the current manuscript. Every file is a
gzip-compressed copy of a LAMMPS output; `manifest.json` gives the source file,
its size and SHA-256 checksum, and the checksum of the compressed copy.
`python scripts/package_embedded_data.py --verify` checks them.

| Directory | Contents |
|---|---|
| `field/` | Reference relaxation (log and relaxed data), and the static cells `ref`, `plus` (+eps) and `minus` (-eps): final dumps with per-atom virials, data files, forces on the held inclusion, minimisation logs |
| `margin/` | Cells with 4 and 10 times the strain (`x4`, `x10`): final dumps, data files, logs |
| `dislocation/` | Slab with an edge dislocation 12 A above the inclusion: relaxed states with the inclusion unstrained (`ctl`), strained (`fld`) and unstrained again (`rev`), relaxation logs, and the logs of two loading ramps that the paper does not use |
| `peierls/` | Slab with a straight edge dislocation and no inclusion: relaxation and sweep logs, relaxed data, full dumps every ten steps |

The cell has 118,861 atoms: IDs 1 to 114,374 are the aluminium matrix and the
rest are the Al13Fe4 inclusion (types 1 Al, 2 Fe). In the dislocation slab
(117,363 atoms) the matrix IDs run to 112,876. Dumps of the field cells have the
columns `id type x y z c_st[1..6]`, where `c_st` is LAMMPS `stress/atom` with
`NULL virial`: stress times volume in bar A^3, tension positive (the global
pressure is minus their sum over 3V). The analysis divides by 16.6075 A^3.

The runs used LAMMPS 22 July 2025 with Kokkos on one GPU and the MEAM potential
of Jelinek et al. (2012). The inputs are in `lammps/embedded_inclusion/`, the
cell builders and queues in `scripts/`.
