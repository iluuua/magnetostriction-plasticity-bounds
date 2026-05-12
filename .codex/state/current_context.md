Objective: package completed 147 MPa controlled sanity-run for interface trial_001 after OVITO review.
Verified: 147 MPa compression-ramp ran 15000 steps (5000 ramp + 10000 hold), fixed-bottom support, mobile NVT, no NPT.
Verified: no ERROR/nan/lost atoms; Dangerous builds=0/0; 151 frames x 618 atoms.
Verified: pairs <1.8 A = 0; cross-slab Al-Fe <2.1 A = 0; min cross-slab Al-Fe=2.59304 A.
Warning: pair 232-260 is internal Fe4Al13; intermittent short contact; min=1.95615 A; no monotonic collapse.
Hypothesis: highest hydrostatic proxy at z=5..10 A is fixed-bottom support artifact, not interface maximum.
Verified: manual OVITO review passed; no detachment, empty interface gap, atom ejection, whole-block drift, or pair collapse observed.
Files changed: 147 MPa check doc, milestone, 0/60/120/147 comparison CSV, README, run_report, DOC_INDEX.
Blockers: no final physical validation; stress/atom is virial proxy; highest hydrostatic proxy remains fixed-bottom artifact.
Do not run 200 MPa without explicit user approval and separate controlled-run plan.
Exact next step: decide whether 200 MPa is scientifically useful or stop and write up 0/60/120/147 MPa results.
