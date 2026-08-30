# Atomistic bounds on the magnetostrictive mechanism in Al–Mg–Si

Molecular-dynamics test of a specific published claim: that pre-exposing an
Al–Mg–Si alloy containing Fe-bearing inclusions to a static 0.7 T field raises
its subsequent room-temperature creep by about 25% because magnetostriction of
the inclusion generates ≈147 MPa at the interface — above the 120 MPa yield
stress of the matrix — and plastifies the surrounding aluminium.

The claim does not survive the test. This repository holds the calculations that
establish that and the analysis code that turns them into numbers. The manuscript
built from them is still in co-author review and is added here on submission.

**The short version.** A magnetic field cannot be simulated in classical MD, so
its effect enters as a volume-preserving affine strain applied to the inclusion
before an unconstrained minimisation. At an amplitude 19–97× larger than any
magnetostriction measured in Fe–Al, the resolved shear stress this produces in
the matrix peaks at **6.3 MPa**, and beyond 60 Å from the interface its mean is
0.5 ± 0.6 MPa. The same cells, loaded in applied shear, place dislocation
activity at **77–86 MPa** (dipole motion), **≈195 MPa** (heterogeneous
nucleation at the interface) and **≥75 MPa** (depinning from a random Mg/Si
solute configuration). The field-induced stress falls one to two orders of
magnitude short of every threshold it would have to cross.

---

## The numbers

| Quantity | Value | Where it comes from |
|---|---|---|
| Peak resolved shear from the strain surrogate | 6.3 MPa at *r* = 30 Å | `stageG10_field_profile.py` |
| Noise floor, mean over *r* ≥ 60 Å | 0.5 ± 0.6 MPa | same |
| Fraction of the imposed distortion that survives minimisation | η = 0.30 ± 0.10 | `stageG12_eigenstrain_retention.py` |
| Maintained-eigenstrain amplitude at λ<sub>s</sub> = 100 ppm | ≤ 2.4 MPa | `stageG8_eshelby3d.py` |
| Generous analytical scale 2μ<sub>Al</sub>λ<sub>s</sub> | ≤ 5.3 MPa | analytic |
| Onset of dipole motion | 77–86 MPa applied shear | Stage G1/G6 |
| Heterogeneous nucleation at the interface | ≈195 MPa applied shear | Stage G1 |
| Solute pinning bound | ≥ 75 MPa | `stageG7_pinning_stats.py` |
| Stress the measured +25% creep actually requires | 8.7–65.2 MPa | `stageG5_two_scale_bridge.py` |
| What 147 MPa would predict instead | 2.2 × 10³ × the observed effect | same |

Three stresses are kept apart throughout and should not be conflated: the
**147 MPa** interface estimate from the experimental papers, the **≤5.3 MPa**
elastic scale that real Fe–Al magnetostriction can supply, and the **6.3 MPa**
relaxed response of the MD surrogate at a deliberately inflated amplitude.

## Reproducing the published numbers

The two minimised interface cells that every stress number is measured from are
in `data/stageG4_clean/` (gzipped, ~2 MB each). Nothing else is needed:

```bash
python analysis/python/stageG10_field_profile.py        # Fig. 1, the σ(r) profile
python analysis/python/stageG12_eigenstrain_retention.py # Table 1, retained strain
python analysis/python/stageG8_eshelby3d.py             # the analytic 3D comparison
python analysis/python/stageG5_two_scale_bridge.py      # Table 2, the two-scale bridge
python analysis/python/stageG11_figures.py              # all three figures
```

Each script writes a JSON record into `docs/reports/`, and the figures are drawn
from those records rather than from anything held in a notebook. A companion
check re-derives every number quoted in the manuscript from the same records and
fails if the two disagree; it ships with the manuscript.

## Layout

```
analysis/python/    analysis code, stage by stage; stageG* is what the paper uses
scripts/           structure generators and run drivers
data/stageG4_clean/ the two minimised cells the stress field is measured from
docs/reports/      the JSON/CSV records figures and tables are built from
docs/run_plans/    what was planned, including branches deliberately not run
configs/           YAML run configurations for stages A–E
lammps/            input decks and thermo logs for the early stages
structures/        starting structures and their build metadata
potentials/        interatomic potentials (third party — see below)
tests/             unit tests for the stage B/C planner and gates
```

## The stages, and why there are seven of them

The campaign ran A through G. Stages A–F are, honestly, one long null result
escalated four different ways; the reason it stayed null turned out to be
geometric, and finding it is the most useful thing in the history.

| Stage | Question | Outcome |
|---|---|---|
| **A** | Does an eigenstrained ellipsoid nucleate anything at finite *T*? | Null. 0 dislocation segments at every amplitude including 4× overload. The 4.5% "OTHER" atoms were the static interface shell, not damage. |
| **B** | Does microstructural realism help — inclusion at a grain boundary, vacancies present? | Null, and *stronger*: HCP defect count went **down** as the driving strain went up 4×. |
| **C** | Is the cell simply too small — does a million atoms change it? | Never got past preparation. Consumed on queueing and disk. |
| **D** | Strip it down: a local interface patch at 100k. | A disorder precursor only. |
| **E** | Scale up: 250k / 510k / 700k. | An 8–17 Å DXA segment present at one sampled frame and gone by the next. Not a dislocation. |
| **F** | Stop hunting dislocations; measure σ(*r*) from the interface, which is what was actually asked for. | Nearly information-free: forming the von Mises invariant *per atom* measures the GPa thermal virial, leaving a 133 MPa noise floor. The stage was then lost to a KOKKOS/CUDA MEAM crash that closed the GPU lane. |
| **G** | Ask the field to *move* a dislocation that already exists, rather than create one. | The null was explained, and the mechanism bounded. |

Two findings from Stage G are worth stating plainly because they invalidate
the earlier work and explain it at the same time:

**The driving force was zero by construction.** For the orientation used since
Stage A — glide plane (111) parallel to the interface, eigenstrain along *z* —
the Schmid factor on the (111)[1̄10] system is *identically* zero and the whole
Peach–Koehler force vanishes. Every null from A through G2 measured a driving
force that was zero for geometric reasons, not physical ones. The Stage G cells
tilt the strain axis 45° to fix this.

**Direct simulation of the mechanism is unreachable at any size.** The line-tension
bound *a*<sub>min</sub> = μ*b*/σ<sub>m</sub> gives 52 nm at the claimed 147 MPa —
about 2 × 10⁸ atoms against a 17 nm cell. MD cannot enact this mechanism. It can
bound it, and measure the quantities a mesoscale model would consume, which is
what the final work does.

A third, smaller lesson: the Stage F GPU crash that closed a whole stage was the
same neighbour-list bug the project had already diagnosed and worked around in
Stage A with `neigh_modify delay 0 every 10 check no`. The recovery ladder never
applied it. Stage G ran the same hardware for weeks without a crash.

## What is deliberately not here

- **`runs/`** — 14 GB of raw production output. Regenerable from the inputs here.
- **Raw trajectories** (`*.lammpstrj`) — with the single exception of
  `data/stageG4_clean/`, which is the manuscript's primary data.
- **Session logs** of the agents that ran the campaign, operator watchdog output,
  and machine-specific diagnostics. None of it is evidence.
- **The supervisor's source materials** — copyrighted PDFs and an unpublished
  manuscript, never redistributed.

## Potentials — third-party, not covered by this repository's licence

`potentials/` contains the 2NN-MEAM Al–Si–Mg–Cu–Fe potential of Jelinek *et al.*
([Phys. Rev. B 85, 245102 (2012)](https://doi.org/10.1103/PhysRevB.85.245102)),
obtained from the NIST Interatomic Potentials Repository, and `Al_zhou.eam.alloy`,
a DYNAMO `setfl` file distributed with LAMMPS. Neither carries an explicit
redistribution licence; they are included so the runs are reproducible. They are
**not** covered by the MIT licence on the rest of this repository, and their
respective authors and distributors retain all rights.

## Manuscript

The manuscript is in preparation and is **not** in this repository yet. It will
be added, with the figures and the text-against-data audit, once it has been
through co-author review and submitted. Until then this repository is the
calculation record: everything the paper will assert can be recomputed from what
is here.

The conclusion it will carry is a refutation with a constructive remainder. The
direct elastic magnetostrictive mechanism is quantitatively unsupported. But the
stress the experiment actually requires, 8.7–65.2 MPa, is the same order as what
real magnetostriction supplies — so if the effect is real it acts by lowering a
thermally activated barrier, not by exceeding a yield stress. Two open problems
remain: Al₁₃Fe₄ as identified is a dilute paramagnet and cannot carry Joule
magnetostriction at all, so the magnetic phase needs identifying; and the
30-minute field-off protocol is a *memory*, which points to a slow diffusional
channel these calculations do not test.

## Licence and contact

MIT, except `potentials/` as noted above. I. Mikhailovskiy, D. Pshonkin,
Moscow Polytechnic University.

---

### Кратко по-русски

Проверка методами молекулярной динамики конкретного published-утверждения: что
выдержка сплава Al–Mg–Si с железосодержащими включениями в поле 0,7 Тл повышает
последующую ползучесть на ~25%, поскольку магнитострикция включения создаёт на
границе ≈147 МПа. Утверждение проверки не выдерживает: при амплитуде, в 19–97
раз завышенной относительно измеренной магнитострикции Fe–Al, разрешённое
касательное напряжение достигает лишь 6,3 МПа, тогда как дислокационный отклик в
тех же ячейках начинается с 75–195 МПа. Двухмасштабная оценка показывает, что
эксперименту требуется 8,7–65,2 МПа, а заявленные 147 МПа предсказали бы эффект
в 2,2·10³ раза больше наблюдаемого.

Рукопись готовится и будет добавлена сюда после вычитки соавторами и подачи.
Пока репозиторий — это расчётная запись: всё, что статья утверждает, считается
командами из раздела «Reproducing the published numbers» выше.
