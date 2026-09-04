# Section 2 (Computational methods / Методика расчёта), subsections 2.1–2.4

## terms explained
- 2NN-MEAM potential — second-nearest-neighbour modified embedded-atom method; one potential describing all atoms, including both sides of the interface, by one set of interaction rules
- slip system {111}<110> — the planes and directions along which dislocations in fcc Al actually move; the cell is oriented so the (111) glide plane is parallel to the interface and [1-10] lies along x
- edge dislocation — the edge of an extra half-plane of atoms inserted into the crystal
- Burgers vector — the lattice translation that measures the displacement a dislocation carries (|b| = 2.86 Å)
- ridge / гребень — a half-elliptical bulge on the upper surface of the flat inclusion layer, running the length of the cell along y; its curved edges produce the non-uniform field, as the curvature of a real particle would
- periodic boundary conditions — the cell repeats in x and y: an atom leaving through one face re-enters through the opposite one, so the cell represents an interface unbounded in its plane
- commensurate cell — replaced by 'chosen so that both lattices are periodic in the plane' (38x13 = 7x8 sentence removed)
- bonded interface — atoms on both sides interact through the same potential; no constraint or artificial coupling; the interface neither slips nor opens except through displacements the potential allows
- energy minimisation (conjugate gradients) — atoms moved to positions of minimum energy without thermal motion; tolerances 1e-8 (energy), 1e-10 eV/Å (force)
- representation of the field — MD is classical mechanics; the field is absent from the calculation and its action is represented mechanically by the strain it is assumed to produce in the inclusion (no spins, quantum mechanics or DFT mentioned)
- magnetostriction — the elongation of the inclusion along the direction of the field (no constant quoted; λ_s/λ_m/ppm framing dropped)
- imposed strain ε = 1.94e-3 — the elastic strain σ_m/E_Al corresponding to the 147 MPa interface stress of the experimental papers, at constant volume: elongation ε along u, contraction ε/2 across u
- Kronecker delta δ_ij — equals 1 for i = j and 0 otherwise; the zero trace expresses constancy of volume
- eigenstrain / собственная деформация — the strain the inclusion would adopt if free of the matrix (Eshelby 1957, existing ref [7]); term kept because Results use it
- Schmid factor — the geometric factor converting a stress into the shear stress on a given slip system; exactly zero for u along z, which is why the axis is tilted 45°
- affine / uniform distortion — every inclusion atom displaced relative to the inclusion centre in proportion to its position, r -> r + ε*·r, stretching the inclusion uniformly along u and compressing it across u
- maintained case — each inclusion atom held at its displaced position by a stiff spring (20 eV/Å^2, ≈0.01 Å) while the matrix relaxes; springs applied identically in the control so they cancel
- free case (relaxation of a layer) — no springs; the ridge retains 0.30 ± 0.10 of the imposed strain after minimisation (flat layer 0.74 ± 0.08; shear component 0.39); stated as fact, no η symbol, no Green strain / affine-map / covariance derivation
- control cell — same cell with no strain, same script and seed, same tolerances, compared atom by atom
- dislocation dipole — two parallel dislocations of opposite sign whose stress fields attract, so the pair is stable until the applied stress lets the partners pass each other
- mutual stress μb/[8π(1-ν)h] ≈ 22 MPa — the attraction between the two dipole partners 206 Å apart, small compared with the applied 45–75 MPa (replaces 'well below the solute strength')
- smoothed ramp onset — the rate of rise switched on over 16 ps so the lowest shear vibration of the slab is not excited
- effective strain rate ~1e8 s^-1 — far faster than any laboratory test, so thresholds are upper estimates relative to slow loading
- stepped loading — a dislocation held by solute atoms moves by breaking away from them, a thermally activated event whose waiting time depends on stress; the stress is raised in steps (45/55/65/75 MPa, 30 ps each, 4 ps onsets) to find the level at which it does
- time step 1 fs — about a hundredth of the period of an atomic vibration
- Nosé–Hoover thermostat — holds the average kinetic energy of the unconstrained atoms at 300 K by a weak feedback on velocities (damping 0.1 ps)
- Volterra construction — the crystal is cut along a half-plane, the faces displaced by one Burgers vector and rejoined, with the displacement field made compatible with the periodic cell
- DXA — dislocation extraction algorithm: locates dislocation lines in an atomic configuration and determines their Burgers vectors (OVITO)
- per-atom virial stress — the atomic-scale counterpart of mechanical stress, computed for each atom from the forces between it and its neighbours and divided by the atomic volume Ω = 16.61 Å^3
- bin — replaced by 'slab 4 Å thick parallel to the interface'
- von Mises stress — the combination of stress components that enters yield criteria; formed only from the slab-averaged tensor because a single atom's stress fluctuates by several GPa
- resolved shear stress / RSS_max — the shear stress acting on a given slip plane in a given slip direction; RSS_max is the largest over the twelve {111}<110> systems, i.e. on the most favourably oriented system
- noise level 0.5 ± 0.6 MPa — mean and standard deviation of ΔRSS_max over the 15 slabs beyond r ≥ 60 Å on minimised structures; the level below which no field is resolved
- retired wording — 'survives/выживает' -> 'retains/сохраняет'; 'not cosmetic' -> 'the reason is geometric'; 'generous scale', 'solute strength / примесная прочность', 'metric of the potential', 'mode', 'Joule magnetostriction', 'saturation', 'affine surrogate', 'ppm' all removed

## figures requested
- FIG (Section 2.1): labelled cross-section of the interface cell in the x–z plane — aluminium matrix above, Al13Fe4 layer with its half-elliptical ridge, interface plane at z = 20 Å, fixed bottom 6 Å layer, 15 Å vacuum gap, crystallographic axes x = [1-10], y = [11-2], z = [111], the (111) glide plane parallel to the interface, and the direction u of the imposed strain at 45° to z. (Files fig_cell_interface_en.png / fig_cell_interface_ru.png dated today exist in docs/paper and may already be this figure; they are not referenced by either .tex yet.)
- FIG (Section 2.3): sketch of the loading scheme — the slab in the x–z plane with the fixed bottom layer, the top layers on which the force along x is applied, the dislocation dipole on its (111) glide planes next to the ridge, and beside it the two stress-versus-time programmes: the linear ramp to 400 MPa over 96 ps and the 45/55/65/75 MPa steps of 30 ps each.

## notes
1. \todo is not defined in either preamble (no todonotes package). A \providecommand{\todo}[1]{\textbf{[TODO: #1]}} is placed at the top of each pasted block so it compiles as is; delete it once the preamble defines the macro.

2. Table tab:eta (residual Green-strain components and η) was removed, as the supervisor's instruction for the free case ('one sentence, no eta') requires. I checked both files: nothing references \ref{tab:eta} anywhere, so no cross-reference breaks. The numbers it carried that matter for honesty (ridge 0.30 ± 0.10, flat layer 0.74 ± 0.08, shear component retained at 0.39) are kept as facts in the free-case paragraph without the symbol η. Consequence outside this section: Results 3.1 (main.tex line ~354, main_ru.tex line ~370) still says 'η is reported in Section 2.2 as a diagnostic', and the Data-availability section still mentions 'retained fraction η' for stageG12; those sentences need the same treatment when that section is redrafted.

3. eq:eigenstrain is kept as the only numbered equation in the section (it is referenced from the Fig. 3 caption in EN by \ref and in RU as '(1)' by hand, and Eq. (2) numbering in Results depends on it). It is now written with the imposed strain ε instead of λ_s; the tensor is identical (ε*_xz = 0.75 ε = 1.455e-3 matches the cell metadata).

4. Hall1959 / BormioNunes2012 are cited only in Section 2 (count 1 in main.tex; RU [11, 12] appear nowhere else) and the RU bibliography is numbered in order of citation, so dropping them would renumber [13]–[20]. They are kept in one sentence that quotes no magnetostriction constant: the adopted strain 'is well above the magnetostriction measured in Fe–Al alloys'. This also keeps the section honest about the amplitude; the 19–97× factor itself remains in the abstract and Results, outside this section. RU citation order [8],[9],[10],[3–6],[5],[7],[11,12],[13],[14] is preserved.

5. Honesty flag carried as a \todo in 2.3, not as paper prose: the onsets quoted in Section 3.2 (77–86 MPa dipole motion, ≈195 MPa nucleation) were measured in the 300,124-atom cell whose inclusion strain was along z, i.e. with zero shear on the glide plane and no maintained strain (stageG2 manifest: eps_z). The unified loaded cell (G4_tilted_eps00194_dipole100k) uses the 45° strain and a different dipole geometry (partners 70 Å apart, passing stress 66 MPa). Once G13 loaded runs exist the \todo is replaced by their values; if they do not, the sentence stating the z-orientation must be restored in the text.

6. 'About 10^5 atoms' anticipates G13 as instructed, but every Results number currently in the manuscript (6.3 MPa peak, 0.5 ± 0.6 MPa noise, 0.30 ± 0.10 retention) comes from the 66,698-atom interface cell, whose aluminium layer is thinner than the ≈220 Å of the unified cell. The \todo{G13: exact count and cell height} marks that these must be confirmed or updated from the unified cell before the todo is closed.

7. The maintained case is described from the protocol in lammps/stageG4_tilted_solute/in.fieldgate_held (spring/self, K = 20 eV/Å^2, holds atoms to ≈0.01 Å); no results exist yet, hence \todo{G13: report the maintained-case profile}. The 'maintained' terminology is what Results/Discussion already use ('maintained eigenstrain'), so the later sections stay consistent.

8. The residual-misfit sentence (+0.31 %/−0.26 %, taken up by the inclusion, cancels to first order) is kept in short form because the Results rely on the cancellation argument; the 38×13 = 7×8 sentence the supervisor objected to is gone. If he objects to the misfit numbers too, the sentence can be cut to 'chosen so that both lattices are periodic in the plane' without affecting any number.

9. Subsection titles 2.2 and 2.3 were renamed ('Magnetostriction surrogate' -> 'Representation of the field'; 'Dislocation cells and loading' -> 'Loaded cells and loading scheme') because 'surrogate' is on his opaque list; all labels (sec:methods, sec:cell, sec:eigenstrain, sec:loading, sec:stress, eq:eigenstrain) are unchanged.

10. Every number in the section was checked against the sources: cell geometry and removal radius (structures/stageG4_tilted_solute/*metadata.json), minimisation tolerances (in.fieldgate), ramp 0→400 MPa over 96 ps with 16 ps smoothing after 5 ps at zero stress (in.production_shear), staircase 45/55/65/75 MPa × 30 ps with 4 ps onsets after 10 ps (in.vstar), dipole separation 205.8 Å and 22.5 MPa (G3_solute_relA metadata), retention values (stageG12_eigenstrain_retention.json), noise floor 0.486 ± 0.548 MPa over 15 bins (stageG10_field_profile.json). Nothing was changed or rounded differently from the current text.

11. The one-word term 'eigenstrain / собственная деформация' is retained (explained at first use with the existing Eshelby reference [7]) because Results and Discussion use it repeatedly; replacing it there is outside this section.

12. The word 'ridge / гребень' is retained after being defined in 2.1 ('half-elliptical bulge, referred to below as the ridge') because Results and figure captions use 'ridge crest / вершина гребня' throughout.