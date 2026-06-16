"""Path layout and output-isolation guards for the stage sweep runner."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_ROOT = REPO_ROOT / "runs" / "stage_sweep_A0_A1_production"

A0_TEMPLATE_DIR = REPO_ROOT / "lammps" / "05_finite_t_ellipsoid" / "stage_A0_24k"
A0_BASELINE_DATA = (
    REPO_ROOT
    / "lammps"
    / "04_ellipsoid_inclusion"
    / "trial_001"
    / "01_nvt_300k"
    / "data.ellipsoid_nvt_300k"
)
AL13FE4_DATA = REPO_ROOT / "structures" / "converted" / "Al13Fe4" / "al13fe4.data"
MEAM_LIBRARY = REPO_ROOT / "potentials" / "meam" / "Jelinek_2012" / "Jelinek_2012_meamf"
MEAM_PARAMS = (
    REPO_ROOT / "potentials" / "meam" / "Jelinek_2012" / "Jelinek_2012_meam.alsimgcufe"
)

# A0 geometry facts (from the committed trial_001 build/eigenstrain pipeline).
A0_INCLUSION_ID_MIN = 23264
A0_INCLUSION_ID_MAX = 24259
A0_INCLUSION_ATOMS = 996
A0_MATRIX_MAX_ID = 23263
A0_CENTER = (32.4, 32.4, 48.6)
A0_INCLUSION_AXES = (12.0, 12.0, 24.0)


class PathEscapeError(RuntimeError):
    """A generated output path tried to escape the isolated runs directory."""


def posix(p: Path | str) -> str:
    return Path(p).resolve().as_posix()


def eps_tag(eps_z: float) -> str:
    """0.0 -> '0000', 0.0025 -> '0025', 0.01 -> '0100' (matches template names)."""
    return f"{round(eps_z * 10000):04d}"


def epsz_dirtag(eps_z: float) -> str:
    """Tag scheme of apply_ellipsoid_eigenstrain.py, e.g. 0.0025 -> epsz_p0p00250."""
    return f"epsz_{eps_z:+.5f}".replace("+", "p").replace("-", "m").replace(".", "p")


def a0_template_for_tag(tag: str) -> Path:
    return A0_TEMPLATE_DIR / f"in.nvt_eps_{tag}"


def ensure_inside_runs(path: Path | str) -> Path:
    rp = Path(path).resolve()
    if not rp.is_relative_to(RUNS_ROOT):
        raise PathEscapeError(f"output path escapes {RUNS_ROOT}: {rp}")
    return rp


def new_run_dir(timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS_ROOT / ts
    ensure_inside_runs(run_dir)
    run_dir.mkdir(parents=True, exist_ok=False)
    for sub in ("summaries", "tables", "logs"):
        (run_dir / sub).mkdir(exist_ok=True)
    return run_dir


def find_latest_run_dir() -> Path | None:
    if not RUNS_ROOT.is_dir():
        return None
    candidates = sorted(d for d in RUNS_ROOT.iterdir() if d.is_dir())
    return candidates[-1] if candidates else None


def case_dir(run_dir: Path, stage: str, tag: str, phase: str) -> Path:
    """e.g. case_dir(rd, 'A0', '0025', 'smoke') -> rd/A0/eps_0025/smoke (created)."""
    d = ensure_inside_runs(Path(run_dir) / stage / f"eps_{tag}" / phase)
    d.mkdir(parents=True, exist_ok=True)
    return d


def structure_dir(run_dir: Path, stage: str, tag: str) -> Path:
    """Run-local home for regenerated eigenstrain structures of one eps case."""
    d = ensure_inside_runs(Path(run_dir) / stage / f"eps_{tag}" / "structure")
    d.mkdir(parents=True, exist_ok=True)
    return d
