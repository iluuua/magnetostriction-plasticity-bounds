"""Acceleration choice and gate-criteria evaluation (pure logic, no I/O)."""

from __future__ import annotations


def choose_acceleration(caps: dict) -> dict:
    """GPU-first but never fake GPU; MEAM stays MEAM (no EAM substitution)."""
    if not caps.get("has_meam"):
        return {
            "mode": "blocked",
            "reason": "LAMMPS build has no MEAM pair style; scientific track impossible.",
        }
    if caps.get("has_meam_kk") and caps.get("has_kokkos_cuda"):
        return {
            "mode": "kokkos_gpu_meam",
            "reason": (
                "meam/kk and a KOKKOS CUDA backend are both present -> "
                "GPU-accelerated MEAM via KOKKOS/CUDA."
            ),
        }
    detail = []
    if caps.get("has_meam_kk"):
        detail.append(
            f"meam/kk exists but KOKKOS backends are: {caps.get('kokkos_api') or 'unknown'} (no CUDA)"
        )
    else:
        detail.append("no meam/kk style")
    if caps.get("has_gpu_package"):
        detail.append(
            f"GPU package present ({caps.get('gpu_api') or 'unknown API'}) but no meam/gpu exists"
        )
    return {
        "mode": "cpu_mpi_meam",
        "reason": (
            "KOKKOS/CUDA MEAM unavailable -> CPU/MPI MEAM immediately. "
            + "; ".join(detail)
            + ". EAM/GPU is NOT a substitute for MEAM production (policy), and the "
            "repo's only EAM file (Al_zhou.eam.alloy) covers Al only, not Al+Fe."
        ),
    }


def evaluate_case_run(record: dict, expected_files: list[str]) -> dict:
    """Per-case pass/fail per the prompt gates: exit 0, no ERROR/nan/lost atoms,
    final outputs exist, walltime respected."""
    reasons = []
    log = record.get("log", {})
    if record.get("timed_out"):
        reasons.append(f"walltime exceeded ({record.get('timeout_s')} s) and run was killed")
    if record.get("exit_code") != 0:
        reasons.append(f"nonzero exit code: {record.get('exit_code')}")
    if not log.get("exists"):
        reasons.append("log file missing")
    if log.get("has_error"):
        reasons.append("ERROR in log: " + " | ".join(log.get("error_lines", [])[:3]))
    if log.get("nan_found"):
        reasons.append("nan detected in log")
    if log.get("lost_atoms"):
        reasons.append("lost atoms detected")
    if not log.get("completed_normally"):
        reasons.append("no 'Total wall time' line (run did not finish normally)")

    present = {o["name"]: o["size_bytes"] for o in record.get("outputs", [])}
    for fname in expected_files:
        if fname not in present:
            reasons.append(f"expected output missing: {fname}")
        elif present[fname] == 0:
            reasons.append(f"expected output is empty: {fname}")

    return {"passed": not reasons, "reasons": reasons}


def evaluate_stage(case_evals: dict, disk_ok: bool, disk_msg: str) -> dict:
    reasons = []
    for case, ev in case_evals.items():
        if not ev["passed"]:
            reasons.append(f"{case}: " + "; ".join(ev["reasons"]))
    if not disk_ok:
        reasons.append(disk_msg)
    return {"passed": not reasons, "reasons": reasons}


def production_eta_check(
    smoke_timesteps_per_s: float | None,
    production_steps: int,
    walltime_s: float,
    safety_factor: float = 1.5,
) -> dict:
    """Block a production stage that smoke timing predicts cannot finish in walltime."""
    if not smoke_timesteps_per_s or smoke_timesteps_per_s <= 0:
        return {
            "ok": True,
            "eta_s": None,
            "note": "no smoke rate available; relying on hard walltime kill",
        }
    eta = production_steps / smoke_timesteps_per_s
    ok = eta * safety_factor <= walltime_s
    return {
        "ok": ok,
        "eta_s": round(eta, 1),
        "note": (
            f"ETA {eta / 60:.1f} min vs walltime {walltime_s / 60:.0f} min "
            f"(safety factor {safety_factor})"
        ),
    }


GATE_APPROVED = "A1 production approved by autopilot gate"
GATE_BLOCKED = "A1 production blocked"


def pre_a1_gate_decision(
    *,
    a0_smoke_passed: bool,
    a0_production_passed: bool,
    a0_analysis_ok: bool,
    a1_build_ok: bool,
    a1_smoke_passed: bool,
    disk_ok: bool,
    memory_ok: bool,
    eta_ok: bool,
) -> tuple[bool, list[str]]:
    blockers = []
    if not a0_smoke_passed:
        blockers.append("A0 smoke did not pass")
    if not a0_production_passed:
        blockers.append("A0 production did not pass")
    if not a0_analysis_ok:
        blockers.append("A0 analysis incomplete")
    if not a1_build_ok:
        blockers.append("A1-small build/prep failed")
    if not a1_smoke_passed:
        blockers.append("A1-small smoke did not pass")
    if not disk_ok:
        blockers.append("free disk below production threshold")
    if not memory_ok:
        blockers.append("memory estimate above limit")
    if not eta_ok:
        blockers.append("production ETA exceeds configured walltime")
    return (not blockers), blockers
