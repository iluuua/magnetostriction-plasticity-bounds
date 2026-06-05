# Scientific claims register

Companion to `claims_register.csv` (45 entries). Each claim was cross-checked against a local
source file. This register is the gate for what may appear in the article. Date: 2026-06-04.

**Distribution:** 23 verified facts, 4 derived metrics, 2 interpretations, 6 limitations,
7 prohibited (unsafe) claims, 3 references-to-verify.
**Article safety:** 27 safe, 11 safe only with caveat, 7 must never be asserted.

## How to read this
- `verified_fact` — directly supported by a local doc/log/table; safe to state as fact.
- `derived_metric` — a computed quantity (e.g. virial stress proxy); safe only with its caveat.
- `interpretation` — framing the data supports; safe if worded carefully.
- `limitation` — true statements about what was NOT done; safe and required.
- `hypothesis_unsafe` — claims the data does NOT support; must never be asserted.
- `reference_to_verify` — literature carried from the repo, not independently verified here.

---

## A. Verified facts (safe to state) — C01–C23

Baseline & structure: **C01** pure-Al relaxation clean; **C02** standalone Fe4Al13 sanity clean;
**C03** structure = COD 1571554; **C18** EAM-Zhou for Al vs Jelinek-2012 MEAM for interface/inclusion.

Flat interface: **C04** candidate Al(111)/Fe4Al13(100) (0.943% mismatch); **C05** 618 atoms;
**C06** boundary `p p f`; **C07** unloaded NVT 300 K (short+long); **C08** minimization converged;
**C09** 0/60/120/147 MPa controlled sanity-runs; **C10** 200 MPa upper-bound/failure-probe;
**C11** 147 & 200 MPa ran 15000 steps; **C12** no hard overlaps <1.8 Å in any scenario;
**C13** no cross-slab Al-Fe <2.1 Å at 147/200 MPa; **C16** loading forces per atom;
**C17** fixed-bottom support (28 fixed / 590 mobile).

Ellipsoid: **C19** 24259 atoms, box 64.8³·97.2, axes 12×12×24, `p p p`; **C20** NVT 300 K baseline
clean (8 Al-Fe warning contacts); **C21** eigenstrain series 0.0010–0.0100 passed script sanity;
**C22** ε_z=0.0100 = numerical stress-test point; **C23** artificial 2.2 Å clearance.

## B. Caveat-required claims — C14, C15, C20, C22, D01–D04, R01–R03

- **C14** warning pair 232-260 is internal Fe4Al13, non-monotonic — *monitor-warning, not proof of integrity.*
- **C15** OVITO review found no visible failure — *"in inspected frames" only; screenshots not in repo.*
- **D01** stress = comparative virial proxy — *never absolute/experimental.*
- **D02** highest |hydrostatic| sits at the fixed-bottom support (≈ −4.18 GPa, z=5–10 Å) — *likely boundary artifact.*
- **D03** time-averaging lowers interface-near proxy vs single frame — *diagnostic comparison only.*
- **D04** ~39 % Al interface-density drop; gaps likely visualization/structure artifact — *not a confirmed void.*

## C. Interpretations (safe if worded carefully) — I01–I02

- **I01** the magnetic field is **not** modeled; loading and eigenstrain are mechanical surrogates. **(Must appear.)**
- **I02** the contribution is a reproducible controlled MD **workflow**, not a final quantitative prediction.

## D. Limitations (true, required) — L01–L06

L01 not final physical validation · L02 no experimental/microscopy comparison · L03 no validated
defect/dislocation analysis · L04 single trial each (no alternative orientations/sizes) · L05 loading
protocols differ (5000/10000/15000 steps) · L06 negative fixed-box pressure + large triclinic skew.

## E. PROHIBITED claims — never assert — U01–U07

| id | Must NOT say | Say instead |
|---|---|---|
| U01 | "interface strength proven / interface validated" | "controlled sanity-run; no visible failure in inspected frames" |
| U02 | "experimentally validated stress" | "comparative virial stress proxy" |
| U03 | "confirmed by microscopy/experiment" | "no experimental comparison performed" |
| U04 | "material withstands 200 MPa / 200 MPa strength" | "200 MPa controlled upper-bound / numerical failure-probe" |
| U05 | "ellipsoid model proves real magnetostriction/inclusion behavior" | "numerical eigenstrain surrogate" |
| U06 | "defect/dislocation mechanism established" | "no validated defect analysis yet" |
| U07 | citing OVITO screenshots as present evidence | "manual review only; screenshots not saved in repo" |

## F. References to verify — R01–R03

Literature carried from `docs/article/references.md` (Feng 2023, Que 2024, SpringerMaterials Al13Fe4).
Software/potential/structure references (LAMMPS docs, OpenKIM/NIST Jelinek-2012, COD 1571554) are
verifiable from the repo's own usage and may be cited normally. The three literature items above were
**not** independently re-verified in this audit and belong under "References to verify" in the article
until their bibliographic details are confirmed. **Do not invent additional references or DOIs.**

## G. One-line audit conclusion
The data supports a **controlled numerical sanity / workflow** paper covering both branches through
0–200 MPa and ε_z = 0.0010–0.0100, with stress as a comparative virial proxy and no claim of physical
validation. Everything stronger than that is in section E and must be avoided.
