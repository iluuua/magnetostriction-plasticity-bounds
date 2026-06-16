"""Host resource checks: disk, RAM, CPU, LAMMPS memory estimates."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from pathlib import Path


def disk_free_gb(path: Path | str) -> float:
    usage = shutil.disk_usage(str(path))
    return usage.free / 1e9


def ram_info_gb() -> tuple[float | None, float | None]:
    """(total_gb, available_gb); (None, None) if the Win32 call is unavailable."""
    if os.name != "nt":
        return None, None
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None, None
        return st.ullTotalPhys / 1e9, st.ullAvailPhys / 1e9
    except Exception:
        return None, None


def estimate_lammps_memory_gb(atoms: int, ranks: int) -> float:
    """Conservative MEAM footprint: ~12 KB/atom total + ~0.3 GB/rank overhead."""
    return atoms * 12e3 / 1e9 + ranks * 0.3


def host_summary(repo_root: Path) -> dict:
    total_ram, avail_ram = ram_info_gb()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "ram_total_gb": round(total_ram, 2) if total_ram else None,
        "ram_available_gb": round(avail_ram, 2) if avail_ram else None,
        "disk_free_gb": round(disk_free_gb(repo_root), 2),
    }


def check_disk(repo_root: Path, min_free_gb: float) -> tuple[bool, str]:
    free = disk_free_gb(repo_root)
    ok = free >= float(min_free_gb)
    return ok, f"disk free {free:.1f} GB (threshold {min_free_gb} GB) -> {'OK' if ok else 'FAIL'}"


def check_memory_estimate(atoms: int, ranks: int, max_memory_gb: float) -> tuple[bool, str]:
    est = estimate_lammps_memory_gb(atoms, ranks)
    ok = est <= float(max_memory_gb)
    return ok, (
        f"estimated LAMMPS memory for {atoms} atoms on {ranks} ranks: "
        f"{est:.1f} GB (limit {max_memory_gb} GB) -> {'OK' if ok else 'FAIL'}"
    )
