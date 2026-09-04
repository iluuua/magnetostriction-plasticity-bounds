# Atomistic bounds on the magnetostrictive mechanism in Al–Mg–Si

Molecular-dynamics test of a specific published claim: that pre-exposing an
Al–Mg–Si alloy containing Al₁₃Fe₄ inclusions to a static 0.7 T field raises
its subsequent room-temperature creep by about 25% because magnetostriction of
the inclusion generates ≈147 MPa at the interface — above the 120 MPa yield
stress of the matrix — and plastifies the surrounding aluminium.

This repository holds the calculations and the analysis code that turn them
into numbers. The manuscript built from them is in co-author review and is
added on submission.

**The short version.** A magnetic field cannot be simulated in classical MD.
The inclusion is therefore elongated along the field by 0.194 % — the strain
that corresponds to the 147 MPa estimate — and held at that strain while the
matrix relaxes; the stress field is the difference between that cell and an
identical control. In one 91,428-atom cell (Al/Al₁₃Fe₄ interface with a
half-elliptical ridge) the resolved shear stress in the matrix is **15 MPa**
directly above the inclusion, decays to the far-field level within 80 Å,
and averages 5 MPa over the cell width; the analytical sphere held at the same
strain gives 41 MPa at its surface. The same cell, loaded in applied shear,
tears a pre-existing dislocation pair apart at **95–105 MPa** (inclusion free to relax; with the inclusion held rigid the pair is not stable even at zero stress, and strained and unstrained cells then coincide within one frame, 9 MPa);
a random Mg/Si configuration pins a dislocation through **≥75 MPa**. The field of the strained ridge where the pair sits is 5–14 MPa, comparable with the 9 MPa frame resolution of the ramp, so no shift of the onset is resolvable.
A two-scale estimate with the alloy's inclusion fraction reproduces the measured
+25 % creep for activation volumes of 30–75 b³ **if** the
inclusions really strain by 0.194 % — the magnetostriction measured for bulk
Fe–Al alloys is twenty times smaller, and the 30-minute field-off memory is not
an elastic effect.

---

## The numbers

| Quantity | Value | Where it comes from |
|---|---|---|
| Resolved shear stress above the held ridge (on its axis) | 15 MPa at 22 Å above the crest, 11–15 MPa out to 30 Å | `stageG10_field_profile.py` |
| Same, averaged over the cell width | 5.0 MPa peak | same |
| Far-field level beyond 60 Å (resolution of the minimisation) | 2.5 ± 0.5 MPa | same |
| Fraction of the imposed strain the held ridge retains | 0.97 ± 0.01 (free ridge: 0.2–0.4) | `stageG12_eigenstrain_retention.py` |
| Eshelby sphere held at 0.194 % | 41 MPa at its surface, ∝ r⁻³ outside | `stageG8_eshelby3d.py` |
| 2D continuum solution for the ridge alone | 20 MPa at the surface, 5 MPa at 10 Å | `stageG17_ridge_continuum.py` |
| Onset of motion of the pre-existing pair (lower partner) | 95–105 MPa applied shear (inclusion free to relax; with the inclusion held rigid the pair is not stable even at zero stress, and strained and unstrained cells then coincide within one frame, 9 MPa) | `stageG2_depinning.py` on stage G15 |
| Heterogeneous nucleation at the interface | none up to 400 MPa (end of ramp) | same |
| Solute pinning bound | ≥ 75 MPa | `stageG7_pinning_stats.py` |
| Stress the measured +25 % creep requires (f = 0.00246) | 8.4–62.7 MPa for V* = 19–142 b³ | `stageG5_two_scale_bridge.py` |
| What the computed 41 / 15 MPa predict | +25 % at V* ≈ 30 / 75 b³ | same |
| What 147 MPa would predict instead | ≥ 2.7 × 10³ × the observed effect | same |

Three stresses are kept apart throughout: the **147 MPa** interface estimate
of the experimental papers (E·ε of a rod, not of an embedded inclusion), the
**41 MPa** of a compact particle held at that strain, and the **15 MPa**
measured above the atomistic ridge held at the same strain.

## Reproducing the published numbers

The two minimised interface cells that every stress number is measured from are
in `data/stageG4_clean/` (gzipped LAMMPS dumps, ~4 MB each: the control and the
cell with the ridge held at 0.194 %, built from the same relaxed control).
Nothing else is needed for the stress field:

```bash
python analysis/python/stageG10_field_profile.py --r-max 110   # Fig. 3, the σ(r) profile
python analysis/python/stageG12_eigenstrain_retention.py       # retained strain
python analysis/python/stageG8_eshelby3d.py                    # the analytical sphere
python analysis/python/stageG17_ridge_continuum.py             # the 2D ridge solution
python analysis/python/stageG5_two_scale_bridge.py             # Table 2, the two-scale estimate
python analysis/python/stageG11_figures.py                     # Figs. 3-5
```

Each script writes a JSON record into `docs/reports/`, and the figures are drawn
from those records. The loaded-cell trajectories (stage G15, three ramps, 180–400 MB each) are
not in the repository; their records are (`stageG2_depinning_summary_G15ctl_free.json`,
`stageG2_depinning_summary_G15held.json` and the per-frame CSVs).

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

The conclusion it carries is conditional. The stress the experiment requires,
8.4–62.7 MPa at the inclusion surface for activation volumes of 19–142 b³, is
reproduced by the computed 15–41 MPa for V* = 30–75 b³ — a range that contains
the value measured for Al–Mg–Si — but only if the inclusions really strain by
0.194 % in the field: the magnetostriction measured for bulk Fe–Al alloys is
twenty times smaller and would give an enhancement below 0.4 %. Two open
problems remain: the ferromagnetic constituent of the inclusions has not been
identified (stoichiometric Al₁₃Fe₄ does not order magnetically), and the
30-minute field-off protocol is a *memory*, which an elastic stress cannot
carry; a slow diffusional channel is the remaining candidate and these
calculations do not test it.

## Licence and contact

MIT, except `potentials/` as noted above. I. Mikhailovskiy, D. Pshonkin,
Moscow Polytechnic University.

---

### Кратко по-русски

Проверка методами молекулярной динамики конкретного опубликованного
утверждения: что выдержка сплава Al–Mg–Si с включениями Al₁₃Fe₄ в поле 0,7 Тл
повышает последующую ползучесть на ~25 %, поскольку магнитострикция включения
создаёт на границе ≈147 МПа. Включение удлинено вдоль поля на 0,194 % —
деформация, отвечающая этой оценке, — и удерживается при ней. В единой ячейке
из 91 428 атомов разрешённое касательное напряжение над включением составляет
15 МПа и спадает до уровня дальнего поля в пределах 80 Å (в среднем по
ширине ячейки — 5 МПа); аналитическая сфера при той же деформации даёт 41 МПа.
Существующая пара дислокаций разрывается при 95–105 МПа приложенного
сдвига (включение свободно релаксирует; при жёстко удерживаемом включении пара неустойчива уже при нулевом напряжении, и ячейки с деформацией и без совпадают в пределах одного кадра, 9 МПа); примеси Mg/Si удерживают дислокацию до 75 МПа. Поле деформированного гребня там, где находится пара, — 5–14 МПа, сравнимо с разрешением рампы (9 МПа), поэтому сдвиг порога не разрешается.
Двухмасштабная оценка воспроизводит наблюдаемые +25 % при V* = 30–75 b³,
если включения действительно деформируются на 0,194 %; измеренная
магнитострикция Fe–Al в двадцать раз меньше, а 30-минутная память после
снятия поля упругим механизмом не объясняется.

Рукопись готовится и будет добавлена сюда после вычитки соавторами и подачи.
Пока репозиторий — это расчётная запись: всё, что статья утверждает, считается
командами из раздела «Reproducing the published numbers» выше.
