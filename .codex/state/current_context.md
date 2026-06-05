Objective: ellipsoid inclusion trial_001 baseline.

Completed:
- built Al matrix + Fe4Al13 ellipsoidal inclusion geometry
- fixed invalid atom type 0 issue
- corrected periodic-compatible Al box: 64.8 x 64.8 x 97.2 A
- minimization completed
- NVT 300 K completed for 5000 steps

NVT status:
- atoms: 24259
- Al atoms: 24027
- Fe atoms: 232
- final temp: 300.3553 K
- Dangerous builds: 0
- output data/dump/final dump/log written
- min pair distance: 1.9903 A
- pairs below 1.8 A: 0
- Al-Fe pairs below 2.1 A: 8
- safe_basic: true

Caveat:
This is not final physical validation. This is an unloaded thermal baseline for a simplified periodic ellipsoidal inclusion model.

Next:
After OVITO visual review, design magnetostriction surrogate by applying controlled inclusion eigenstrain/displacement, then relax and compare local stress/defect indicators.
