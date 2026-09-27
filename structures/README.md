# Crystallographic source and model geometry

The simulations are replayed from exact initial configurations in
`data/publication`. This directory holds their geometric descriptions rather
than an alternative structure-generation pipeline.

`raw/Al13Fe4/al13fe4.cif` is Crystallography Open Database entry 1571554.
Its header contains the source citation, authors and public-domain statement.
The cell contains 102 atoms with composition Al78Fe24, equivalent to Al13Fe4.
`converted/Al13Fe4/al13fe4_metadata.json` records cell lengths, angles, volume
and the Al/Fe type mapping of this crystallographic source.

`stageG4_tilted_solute/*/*_metadata.json` records the static interface and
dislocation-pair geometries. The retained directory names are identifiers of
the original calculations. Despite the historical word `solute`, these three
models contain no Mg or Si; the atom counts specify the actual composition.
Lengths and positions are in angstrom, strains are dimensionless, and angles
are in degrees. The imposed strain tensor is trace-free; this implies volume
conservation only to first order.

`stageG3_solute_mobility/G3_solute_relA/G3_solute_relA_metadata.json` describes
the separate 92,800-atom alloy comparator, including composition, seed, initial
dislocation positions and boundary slabs. Its type mapping is Al/Mg/Si, not the
Al/Fe/Mg/Si mapping of the interface cells.

The metadata describe the construction geometry. Relaxation changes atomic
coordinates, so measurements should use the deposited snapshots. Original
generation timestamps and commit identifiers are provenance, not claims that
a cell was regenerated for the current manuscript. The data manifest provides
content hashes that remain meaningful after Git author-history corrections.
