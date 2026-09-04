# Section 1 (Introduction) — \section{Introduction} / \section{Введение}

## terms explained
- kT — 'the thermal energy kT' / 'тепловая энергия kT' (field energy per atom negligible against it)
- magnetoplastic effect — the broad class of observations in which weak magnetic fields change the plasticity of nonmagnetic crystals [Alshits2003, Molotskii2000]
- magnetostriction — 'the change of shape that a magnetized body undergoes' / 'изменение формы намагниченного тела'
- misfit stress — replaced by 'the stress caused by the mismatch between the strained inclusion and the surrounding matrix' / 'напряжение, вызванное несоответствием между деформированным включением и окружающей матрицей'
- creep — 'the slow deformation under a constant load' / 'медленное деформирование под постоянной нагрузкой'
- Taylor–Quinney coefficient — 'the fraction of the work of plastic deformation that is released as heat' / 'доля работы пластической деформации, выделяющаяся в виде тепла'
- the 147 MPa estimate — 'obtained from the field strength through an empirical proportionality coefficient' (λ_m symbol and formula dropped per instruction)
- dislocations — 'the line defects of the crystal lattice whose motion produces plastic flow' / 'линейные дефекты кристаллической решётки, движение которых и составляет пластическое течение'
- molecular dynamics (MD) — 'classical ... in which the atoms move according to Newton's equations under forces derived from an interatomic potential' / 'атомы движутся по уравнениям Ньютона под действием сил, задаваемых межатомным потенциалом'
- representation of the field — 'A magnetic field has no direct representation in classical MD, so its action is represented mechanically: the inclusion is taken to elongate along the field direction by ε = 1.94e-3 (0.194 %) at constant volume, the strain corresponding to the 147 MPa interface stress'
- transduction path — replaced by 'a seemingly straightforward mechanical route from the field to plastic flow'
- solutes — 'Mg and Si solute atoms dissolved in the aluminum' / 'растворённые в алюминии атомы Mg и Si'
- thermally activated glide — 'dislocation motion in which obstacles are overcome with the help of thermal fluctuations, so that the glide rate depends exponentially on the stress' / 'движение дислокаций, при котором препятствия преодолеваются с помощью тепловых флуктуаций, так что скорость скольжения экспоненциально зависит от напряжения'
- Eshelby exterior field — 'the elastic field outside a strained inclusion', decaying as r^-3 [Eshelby1957]
- 'survives' — replaced by 'remains' / 'сохраняется' (magnetic memory sentence)

## figures requested


## notes
1. The supervisor's dictated abstract text is not in the repository (nothing dated 1 Sept 2026 under docs/); the introduction follows the four-part shape given in the task (phenomenon, published 147 MPa explanation, why never checked at the atomic scale, what is computed) and ends with what is computed. The two-scale verdict, 'neither local plastification nor the thermally activated variant accounts for the observation', and the 'additional channel' sentence were removed from the introduction as instructed; they remain in Results/Conclusions.
2. Citations and labels: every existing \cite, \ref{sec:limitations} and \label{sec:intro} is kept; RU keeps [1,2], [3--6], [4], [5], [7]. One \ref was added to an existing label, \ref{sec:discussion}, in place of the deleted clause 'no affordable simulation cell can do [it] for geometric reasons alone' (a conclusion, now only pointed to). The RU file has no section labels, so it points by section name («Обсуждение», «Ограничения»); if labels are added to main_ru.tex later, replace those with \ref.
3. λ_m dropped per instruction: the 147 MPa is described as 'obtained from the field strength through an empirical proportionality coefficient' with no symbol. The Discussion subsection 'The parameter λ_m and the identity of the magnetic phase' (main.tex line ~610, main_ru.tex line ~591) still uses λ_m and σ_m = λ_m B and currently relies on the introduction to have defined them — whoever redrafts that subsection must define the coefficient there, or the supervisor's 'drop λ_m entirely' applies to it too.
4. Honesty flag for other sections: the imposed strain ε = 1.94e-3 is now stated as a given, matching 'our_eigenstrain_eps': 0.00194 in stageG5_two_scale_bridge.json (147 MPa / 75.7 GPa per the action plan). With the λ_s/ppm framing removed, the paper must still say somewhere (Results or Discussion) that this strain is far larger than any measured Fe–Al magnetostriction (currently '19–97 times'); the conclusion that the mechanism falls short depends on that comparison, and it is not in the introduction (it was not before either).
5. Citation for 'based on the earlier experimental work': only \cite{Friha2024JMMM} is attached, because that is the paper carrying the 147 MPa figure; Skvortsov2019JAP quotes a different coefficient and phase, so citing it for 'the 147 MPa estimated there' would be inaccurate. If the supervisor wants the plural 'studies [refs]', add the keys he names.
6. Minor wording change to an experimental statement: 'multiplies the heat release' → 'increases the heat release during deformation several-fold' (docs/reports/stageG_final_report_ru.md records ×5); no number is introduced.
7. Numbers unchanged: 0.4–0.7 T, 30 min, 160 MPa, ~25 %, 0.07 → 0.25, 147 MPa, 120 MPa, ε = 1.94e-3 (0.194 %), r^-3.
8. Naming of the phase: the interface is described as 'between aluminum and the intermetallic compound Al13Fe4' without asserting that the experiments identified the inclusions as that phase, since the identification is disputed in the Discussion.
9. No \todo macro is defined in either preamble (grep finds none). This section does not use it, but sections that will (G13 counts, FIG requests) need a \newcommand{\todo}[1]{...} added to both files. The cell picture and loading-scheme figure the supervisor asked for belong in Methods, so figures_requested is empty here.