"""Markdown / CSV report writers for the stage sweep."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |"]
    out.append("|" + "|".join(" --- " for _ in headers) + "|")
    for row in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    return "\n".join(out) + "\n"


def _fmt(value, digits=2):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def case_table(records: dict, evals: dict | None = None) -> str:
    headers = [
        "case", "exit", "walltime_s", "timesteps/s", "ns/day", "T_final_K",
        "press_final_bar", "lost_atoms", "nan", "ERROR", "dangerous_builds",
        "disk_before_GB", "disk_after_GB", "verdict",
    ]
    rows = []
    for case, rec in records.items():
        log = rec.get("log", {})
        final = log.get("final_thermo") or {}
        verdict = ""
        if evals and case in evals:
            verdict = "PASS" if evals[case]["passed"] else "FAIL"
        rows.append([
            case,
            rec.get("exit_code"),
            _fmt(rec.get("duration_s"), 1),
            _fmt(log.get("timesteps_per_s"), 1),
            _fmt(log.get("ns_per_day"), 2),
            _fmt(final.get("Temp"), 1),
            _fmt(final.get("Press"), 1),
            "yes" if log.get("lost_atoms") else "no",
            "yes" if log.get("nan_found") else "no",
            "yes" if log.get("has_error") else "no",
            log.get("dangerous_builds", 0),
            _fmt(rec.get("disk_free_before_gb"), 1),
            _fmt(rec.get("disk_free_after_gb"), 1),
            verdict,
        ])
    return md_table(headers, rows)


def analysis_table(rows: list[dict]) -> str:
    headers = [
        "case", "eps_z", "matrix_atoms", "fcc_pct", "hcp_pct", "other_pct",
        "disloc_segments", "disloc_length_A", "disloc_density_per_m2",
        "defect_atoms_beyond_shell",
    ]
    table_rows = []
    for r in rows:
        pz = r.get("plastic_zone") or {}
        table_rows.append([
            r.get("case"),
            r.get("eps_z"),
            r.get("matrix_atoms"),
            r.get("fcc_pct"),
            r.get("hcp_pct"),
            r.get("other_pct"),
            r.get("dislocation_segments"),
            r.get("dislocation_length_A"),
            f"{r.get('dislocation_density_per_m2', 0.0):.3e}",
            pz.get("defect_atoms_beyond_1p3_shell"),
        ])
    return md_table(headers, table_rows)


def write_defect_csv(out_path: Path, rows: list[dict]) -> None:
    headers = [
        "case", "eps_z", "matrix_atoms", "fcc_pct", "hcp_pct", "other_pct",
        "dislocation_segments", "dislocation_length_A", "dislocation_density_per_m2",
        "matrix_defect_atoms_total", "defect_atoms_beyond_1p3_shell",
        "hcp_atoms_beyond_1p3_shell", "dump",
    ]
    with Path(out_path).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            pz = r.get("plastic_zone") or {}
            w.writerow([
                r.get("case"),
                r.get("eps_z"),
                r.get("matrix_atoms"),
                r.get("fcc_pct"),
                r.get("hcp_pct"),
                r.get("other_pct"),
                r.get("dislocation_segments"),
                r.get("dislocation_length_A"),
                f"{r.get('dislocation_density_per_m2', 0.0):.6e}",
                pz.get("matrix_defect_atoms_total"),
                pz.get("defect_atoms_beyond_1p3_shell"),
                pz.get("hcp_atoms_beyond_1p3_shell"),
                r.get("dump"),
            ])


def write_env_report(out_path: Path, host: dict, detect_info: dict, git_info: dict) -> None:
    lines = [
        "# Environment report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Host",
        "",
    ]
    for k, v in host.items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## LAMMPS / MPI", ""]
    for k in (
        "lmp_path", "mpiexec_path", "lammps_version", "has_meam", "has_meam_kk",
        "has_kokkos", "has_kokkos_cuda", "kokkos_api", "has_gpu_package", "gpu_api",
        "has_meam_gpu", "has_eam_alloy_gpu",
    ):
        lines.append(f"- {k}: {detect_info.get(k)}")
    lines += ["", "## Git", ""]
    for k, v in git_info.items():
        lines.append(f"- {k}: {v}")
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_acceleration_md(out_path: Path, decision: dict, detect_info: dict, resources_cfg: dict) -> None:
    mode = decision["mode"]
    cmd_examples = {
        "cpu_mpi_meam": f"mpiexec -np {resources_cfg['cpu_mpi_ranks']} lmp -in <run-local-input> -log <run-local-log>",
        "kokkos_gpu_meam": "mpiexec -np 1 lmp -k on g 1 t 8 -sf kk -in <run-local-input> -log <run-local-log>",
        "blocked": "(no valid execution mode)",
    }
    lines = [
        "# Acceleration decision",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"**Selected mode: `{mode}`**",
        "",
        f"Reason: {decision['reason']}",
        "",
        f"Command shape: `{cmd_examples.get(mode, '')}`",
        "",
        "## Capability classification",
        "",
    ]
    for k in (
        "has_meam", "has_meam_kk", "has_kokkos", "has_kokkos_cuda", "has_gpu_package",
        "has_meam_gpu", "has_eam_alloy_gpu",
    ):
        lines.append(f"- {k}: {detect_info.get(k)}")
    lines += [
        "",
        "## Policy notes",
        "",
        "- GPU-first but never fake GPU: KOKKOS/CUDA MEAM is used only if both "
        "meam/kk and a CUDA backend are actually present.",
        "- MEAM is never replaced by EAM/GPU for scientific production.",
        "- KOKKOS CPU benchmark: skipped (optional; would delay production).",
        "- EAM/GPU exploratory track: disabled; Al_zhou.eam.alloy covers Al only "
        "and cannot represent the Al+Fe4Al13 system.",
    ]
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
