"""LAMMPS executable discovery and capability classification (lmp -h)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

HELP_TIMEOUT_S = 300


class DetectError(RuntimeError):
    pass


def find_lammps_executable(setting: str | None) -> Path | None:
    """Resolve the lmp executable: explicit path, PATH lookup, or known install glob."""
    if setting and setting != "auto":
        p = Path(setting)
        return p if p.is_file() else None
    which = shutil.which("lmp")
    if which:
        return Path(which)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        hits = sorted(Path(local_appdata).glob("LAMMPS*/bin/lmp.exe"))
        if hits:
            return hits[-1]
    return None


def find_mpiexec() -> Path | None:
    which = shutil.which("mpiexec")
    if which:
        return Path(which)
    known = Path(r"C:\Program Files\Microsoft MPI\Bin\mpiexec.exe")
    return known if known.is_file() else None


def get_help_text(lmp: Path, workdir: Path) -> str:
    """Run `lmp -h -log none` and capture the full help/capability listing."""
    proc = subprocess.run(
        [str(lmp), "-h", "-log", "none"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(workdir),
        timeout=HELP_TIMEOUT_S,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if not text.strip():
        raise DetectError(f"`{lmp} -h` produced no output (exit {proc.returncode})")
    return text


def parse_capabilities(help_text: str) -> dict:
    tokens = set(help_text.split())
    kokkos_api = ""
    m = re.search(r"KOKKOS package API:(.*)", help_text)
    if m:
        kokkos_api = m.group(1).strip()
    gpu_api = ""
    m = re.search(r"GPU package API:(.*)", help_text)
    if m:
        gpu_api = m.group(1).strip()
    version = ""
    m = re.search(
        r"Large-scale Atomic/Molecular Massively Parallel Simulator\s*-?\s*(.*)",
        help_text,
    )
    if m:
        version = m.group(1).strip()

    return {
        "lammps_version": version,
        "has_meam": "meam" in tokens,
        "has_meam_kk": "meam/kk" in tokens,
        "has_kokkos": "KOKKOS" in tokens,
        "has_kokkos_cuda": "CUDA" in kokkos_api.upper(),
        "kokkos_api": kokkos_api,
        "has_gpu_package": "GPU" in tokens,
        "gpu_api": gpu_api,
        "has_meam_gpu": "meam/gpu" in tokens,
        "has_eam_alloy_gpu": "eam/alloy/gpu" in tokens,
    }


def detect(lammps_setting: str | None, workdir: Path, save_help_to: Path | None = None) -> dict:
    lmp = find_lammps_executable(lammps_setting)
    if lmp is None:
        raise DetectError(
            f"LAMMPS executable not found (setting={lammps_setting!r}); "
            "checked PATH and %LOCALAPPDATA%\\LAMMPS*\\bin\\lmp.exe"
        )
    mpiexec = find_mpiexec()
    help_text = get_help_text(lmp, workdir)
    if save_help_to is not None:
        Path(save_help_to).write_text(help_text, encoding="utf-8")
    caps = parse_capabilities(help_text)
    return {
        "lmp_path": str(lmp),
        "mpiexec_path": str(mpiexec) if mpiexec else None,
        "help_saved_to": str(save_help_to) if save_help_to else None,
        **caps,
    }
