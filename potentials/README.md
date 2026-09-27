# Interatomic potential

The published calculations use the original Jelinek et al. Al-Si-Mg-Cu-Fe
modified embedded-atom method parameterisation:

B. Jelinek et al., *Physical Review B* 85, 245102 (2012),
[doi:10.1103/PhysRevB.85.245102](https://doi.org/10.1103/PhysRevB.85.245102).

The two files in `meam/Jelinek_2012/` are the element library
(`Jelinek_2012_meamf`) and interaction parameters
(`Jelinek_2012_meam.alsimgcufe`). They are retained unchanged with their
original headers. The [NIST Interatomic Potentials Repository entry](https://www.ctcms.nist.gov/potentials/entry/2012--Jelinek-B-Groh-S-Horstemeyer-M-F-et-al--Al-Si-Mg-Cu-Fe/)
identifies the author-supplied files and accompanying tests. No new licence is
asserted over these third-party parameters.

The library element order is `AlS SiS MgS CuS FeS`. Interface-cell atom types
map to `AlS FeS MgS SiS`; the separate alloy cell maps to `AlS MgS SiS`.
The actual mapping is explicit in each retained LAMMPS input. A type number
must not be interpreted as the same chemical element across these two cells.

The potential supports a mechanical comparison in the chosen geometry.
Independent validation of the Al/Al13Fe4 interface and Mg/Si dislocation
barriers has not been established by this work. Reproducing a deposited run
does not establish the model's predictive accuracy for a real alloy.
