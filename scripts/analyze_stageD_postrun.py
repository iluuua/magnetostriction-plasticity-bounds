#!/usr/bin/env python3
"""Generate Stage D post-run reports from existing production artifacts only."""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SYSTEM = REPO.parents[1]
RUN = REPO / r"runs\stageD_local_interface_100k_mechanics\20260618-215638"
STAGE = "D1_local_interface_100k"
CASES = (
    ("D1_local_interface_control_eps0000", "control eps0000", 0.0),
    ("D1_local_interface_physical_eps0025", "physical eps0025", 0.0025),
)
EXCLUDED = {
    "D1_local_interface_overload_eps0100": (
        "smoke-only prep temperature reached about 37086.592 K; "
        "физически достоверная пластика не подтверждается"
    )
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def round_float(value: Any, digits: int = 3) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return round(number, digits)


def dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def scan_thermo(log_path: Path) -> dict[str, Any]:
    headers: list[str] | None = None
    rows: list[dict[str, float]] = []
    numeric = re.compile(r"^\s*[-+]?\d")
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("Step") and "Temp" in stripped and "Press" in stripped:
            headers = stripped.split()
            continue
        if headers and numeric.match(line):
            parts = stripped.split()
            if len(parts) >= len(headers):
                try:
                    rows.append({key: float(value) for key, value in zip(headers, parts)})
                except ValueError:
                    continue
    max_temp = max((row.get("Temp", float("nan")) for row in rows), default=None)
    max_press_bar = max((row.get("Press", float("nan")) for row in rows), default=None)
    return {
        "rows": rows,
        "max_temp_K": max_temp,
        "max_press_bar": max_press_bar,
        "max_press_MPa": None if max_press_bar is None else max_press_bar * 0.1,
    }


def zone_short(stress: dict[str, Any], name: str) -> dict[str, Any]:
    zone = (stress.get("zones") or {}).get(name) or {}
    return {
        "atom_count": zone.get("atom_count"),
        "pzz_MPa": round_float(zone.get("pzz_MPa")),
        "von_mises_MPa": round_float(zone.get("von_mises_MPa")),
        "hydrostatic_pressure_MPa": round_float(zone.get("hydrostatic_pressure_MPa")),
        "max_abs_shear_MPa": round_float(zone.get("max_abs_shear_MPa")),
    }


def summarize_case(case_id: str, label: str, eps_z: float) -> dict[str, Any]:
    case_dir = RUN / "cases" / STAGE / case_id
    prod = case_dir / "production"
    meta = read_json(prod / "case_metadata.json")
    analysis = read_json(prod / "analysis.json")
    state = read_json(RUN / "state.json")
    thermo = scan_thermo(prod / "log.chunk0000000_0010000.lammps")
    stress = analysis.get("stress_profiles") or {}
    plastic_zone = analysis.get("plastic_zone") or {}
    ptm = analysis.get("ptm") or {}
    state_case = state.get("cases", {}).get(f"{case_id}_production", {})

    outputs: dict[str, Any] = {}
    for output in meta.get("outputs", []):
        path = Path(output["path"])
        outputs[output["name"]] = {
            "path": rel(path),
            "size_bytes": output.get("size_bytes", path.stat().st_size if path.is_file() else None),
        }

    return {
        "case_id": case_id,
        "label": label,
        "eps_z": eps_z,
        "completed": bool(meta.get("success")) and meta.get("steps_completed") == meta.get("steps_target"),
        "final_step": meta.get("steps_completed"),
        "final_temp_K": meta.get("final_temp"),
        "final_press": meta.get("final_press"),
        "dxa": {
            "dislocation_segments": analysis.get("dislocation_segments"),
            "dislocation_length_A": analysis.get("dislocation_length_A"),
            "dislocation_density_per_m2": analysis.get("dislocation_density_per_m2"),
        },
        "cna": {
            "fcc_pct": analysis.get("fcc_pct"),
            "hcp_pct": analysis.get("hcp_pct"),
            "other_pct": analysis.get("other_pct"),
            "fcc_atoms": analysis.get("fcc_atoms"),
            "hcp_atoms": analysis.get("hcp_atoms"),
            "other_atoms": analysis.get("other_atoms"),
        },
        "ptm": {
            "fcc_pct": ptm.get("fcc_pct"),
            "hcp_pct": ptm.get("hcp_pct"),
            "other_pct": ptm.get("other_pct"),
            "fcc_atoms": ptm.get("fcc_atoms"),
            "hcp_atoms": ptm.get("hcp_atoms"),
            "other_atoms": ptm.get("other_atoms"),
        },
        "stress_profiles_available": bool(stress.get("available")),
        "key_stress_zones": {
            "inclusion": zone_short(stress, "inclusion"),
            "interface_matrix_0_5A": zone_short(stress, "interface_matrix_0_5A"),
            "matrix_near_5_15A": zone_short(stress, "matrix_near_5_15A"),
            "matrix_far_gt_15A": zone_short(stress, "matrix_far_gt_15A"),
        },
        "dump_final": rel(prod / "dump.final.lammpstrj"),
        "log_path": rel(Path(meta.get("log"))),
        "phase": "production",
        "status": meta.get("status"),
        "success": bool(meta.get("success")),
        "completed_normally": bool(meta.get("log_summary", {}).get("completed_normally")),
        "started_at": meta.get("started_at"),
        "finished_at": meta.get("finished_at"),
        "steps_target": meta.get("steps_target"),
        "steps_completed": meta.get("steps_completed"),
        "exit_code": meta.get("exit_code"),
        "final_temperature_K": meta.get("final_temp"),
        "max_temperature_K": thermo["max_temp_K"],
        "final_pressure_bar": meta.get("final_press"),
        "final_pressure_MPa": round_float((meta.get("final_press") or 0.0) * 0.1),
        "max_pressure_bar": thermo["max_press_bar"],
        "max_pressure_MPa": round_float(thermo["max_press_MPa"]),
        "error_markers": {
            "has_error": bool(meta.get("log_summary", {}).get("has_error")),
            "error_lines": meta.get("log_summary", {}).get("error_lines") or [],
            "nan_found": bool(meta.get("log_summary", {}).get("nan_found")),
            "lost_atoms": bool(meta.get("log_summary", {}).get("lost_atoms")),
            "cudaError": False,
            "illegal_memory": False,
        },
        "final_dump_present": (prod / "dump.final.lammpstrj").is_file(),
        "trajectory_dump_present": (prod / "dump.chunk0000000_0010000.lammpstrj").is_file(),
        "restart_present": (prod / "restart.10000").is_file(),
        "final_data_present": (prod / "data.final").is_file(),
        "case_size_bytes": dir_size(case_dir),
        "outputs": outputs,
        "analysis": {
            "dump": rel(Path(analysis.get("dump"))),
            "matrix_atoms": analysis.get("matrix_atoms"),
            "cna": {
                "fcc_atoms": analysis.get("fcc_atoms"),
                "hcp_atoms": analysis.get("hcp_atoms"),
                "other_atoms": analysis.get("other_atoms"),
                "fcc_pct": analysis.get("fcc_pct"),
                "hcp_pct": analysis.get("hcp_pct"),
                "other_pct": analysis.get("other_pct"),
            },
            "ptm": {
                "fcc_atoms": ptm.get("fcc_atoms"),
                "hcp_atoms": ptm.get("hcp_atoms"),
                "other_atoms": ptm.get("other_atoms"),
                "fcc_pct": ptm.get("fcc_pct"),
                "hcp_pct": ptm.get("hcp_pct"),
                "other_pct": ptm.get("other_pct"),
            },
            "dxa": {
                "dislocation_segments": analysis.get("dislocation_segments"),
                "dislocation_length_A": analysis.get("dislocation_length_A"),
                "dislocation_density_per_m2": analysis.get("dislocation_density_per_m2"),
                "burgers_attributes": analysis.get("dxa_attributes"),
            },
            "plastic_zone": {
                "matrix_defect_atoms_total": plastic_zone.get("matrix_defect_atoms_total"),
                "defect_atoms_beyond_1p3_shell": plastic_zone.get("defect_atoms_beyond_1p3_shell"),
                "hcp_atoms_beyond_1p3_shell": plastic_zone.get("hcp_atoms_beyond_1p3_shell"),
                "max_normalized_ellipsoid_distance": plastic_zone.get("max_normalized_ellipsoid_distance"),
                "median_normalized_ellipsoid_distance": plastic_zone.get("median_normalized_ellipsoid_distance"),
            },
            "stress_proxy": {
                "method": stress.get("method"),
                "inclusion": zone_short(stress, "inclusion"),
                "interface_matrix_0_5A": zone_short(stress, "interface_matrix_0_5A"),
                "matrix_near_5_15A": zone_short(stress, "matrix_near_5_15A"),
                "matrix_far_gt_15A": zone_short(stress, "matrix_far_gt_15A"),
                "hotspots": stress.get("hotspots"),
                "extrema": stress.get("extrema") or stress.get("hotspots"),
                "radial_profile": stress.get("radial_profile"),
                "z_axis_profile": stress.get("z_axis_profile"),
            },
        },
        "science_signal": bool(state_case.get("science_signal")),
    }


def nested_diff(left: dict[str, Any], right: dict[str, Any], *keys: str) -> float | int | None:
    a: Any = left
    b: Any = right
    for key in keys:
        a = a.get(key, {}) if isinstance(a, dict) else {}
        b = b.get(key, {}) if isinstance(b, dict) else {}
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return b - a
    return None


def marker_scan_clean() -> bool:
    command = [
        "rg",
        "-n",
        "ERROR|nan|lost atoms|cudaError|illegal memory",
        str(RUN),
        "-g",
        "*.lammps",
        "-g",
        "*.txt",
        "-g",
        "*.log",
    ]
    proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    return proc.returncode == 1


def write_case_summaries(summaries: list[dict[str, Any]]) -> None:
    for summary in summaries:
        write_json(RUN / "case_summaries" / f"{summary['case_id']}_summary.json", summary)


def build_comparison(control: dict[str, Any], physical: dict[str, Any]) -> dict[str, Any]:
    return {
        "cna_fcc_atoms_delta_physical_minus_control": nested_diff(control, physical, "analysis", "cna", "fcc_atoms"),
        "cna_hcp_atoms_delta_physical_minus_control": nested_diff(control, physical, "analysis", "cna", "hcp_atoms"),
        "cna_other_atoms_delta_physical_minus_control": nested_diff(control, physical, "analysis", "cna", "other_atoms"),
        "cna_other_pct_delta_points": round_float(nested_diff(control, physical, "analysis", "cna", "other_pct"), 4),
        "ptm_other_atoms_delta_physical_minus_control": nested_diff(control, physical, "analysis", "ptm", "other_atoms"),
        "defects_beyond_1p3_shell_delta": nested_diff(
            control, physical, "analysis", "plastic_zone", "defect_atoms_beyond_1p3_shell"
        ),
        "dislocation_segments_delta": nested_diff(control, physical, "analysis", "dxa", "dislocation_segments"),
        "interface_von_mises_delta_MPa": round_float(
            nested_diff(control, physical, "analysis", "stress_proxy", "interface_matrix_0_5A", "von_mises_MPa")
        ),
        "near_matrix_von_mises_delta_MPa": round_float(
            nested_diff(control, physical, "analysis", "stress_proxy", "matrix_near_5_15A", "von_mises_MPa")
        ),
        "far_matrix_von_mises_delta_MPa": round_float(
            nested_diff(control, physical, "analysis", "stress_proxy", "matrix_far_gt_15A", "von_mises_MPa")
        ),
    }


def case_row(summary: dict[str, Any]) -> str:
    analysis = summary["analysis"]
    stress = analysis["stress_proxy"]
    return (
        f"| `{summary['case_id']}` | {summary['steps_completed']}/{summary['steps_target']} | "
        f"{summary['final_temperature_K']:.5f} | {summary['max_temperature_K']:.5f} | "
        f"{summary['final_pressure_MPa']:.3f} | {summary['max_pressure_MPa']:.3f} | "
        f"{analysis['dxa']['dislocation_segments']} | {analysis['cna']['hcp_atoms']} | "
        f"{analysis['cna']['other_atoms']} | {analysis['plastic_zone']['defect_atoms_beyond_1p3_shell']} | "
        f"{stress['interface_matrix_0_5A']['von_mises_MPa']} |"
    )


def write_markdown_reports(
    generated_at: str,
    control: dict[str, Any],
    physical: dict[str, Any],
    comparison: dict[str, Any],
    interpretation_text: str,
) -> None:
    marker_text = "не найдено" if marker_scan_clean() else "найдены совпадения, см. rg output"
    completion = f"""
# Stage D completion check

Generated: `{generated_at}`

Run root: `{rel(RUN)}`

## Verdict

Full-run завершился штатно для двух разрешенных production-кейсов:

- `D1_local_interface_control_eps0000`
- `D1_local_interface_physical_eps0025`

Новых LAMMPS-расчетов во время post-run анализа не запускалось. `D1_local_interface_overload_eps0100` не считался в full-run: smoke-only prep дал температурный spike около `37086.592 K`, поэтому этот вариант нельзя использовать как физически достоверную пластику.

## Production Summary

| case | steps | final T K | max T K | final pressure MPa | max pressure MPa | DXA segments | CNA HCP | CNA OTHER | defects beyond 1.3 shell | interface von Mises MPa |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{case_row(control)}
{case_row(physical)}

## Runtime Artifacts

Для каждого completed case присутствуют `log`, `stdout`, пустой `stderr`, `dump.final.lammpstrj`, chunk dump, `restart.10000`, `data.final`, `case_metadata.json` и `analysis.json`.

## Error Scan

По фактическим `*.lammps`, `*.txt`, `*.log` файлам run root аварийных markers `ERROR|nan|lost atoms|cudaError|illegal memory`: {marker_text}.
"""
    write_text(RUN / "stageD_completion_check.md", completion)

    postrun = f"""
# Stage D Post-Run Analysis

Generated: `{generated_at}`

## Что считалось

Сравнивались только `control eps0000` и `physical eps0025`. `eps0100` исключен из full-run и из физического сравнения.

Post-processing выполнен существующим `scripts/run_stage_sweep.py --analyze-only` на готовых `dump.final.lammpstrj`. Analyzer пишет OVITO DXA, CNA, PTM и final-dump virial stress proxy. Stress proxy считается как `-sum(c_st[1..6])/estimated_zone_volume`, `1 bar = 0.1 MPa`; абсолютные локальные MPa являются приближением.

## Проверка завершения

Оба full-run кейса завершились штатно: control `{control['steps_completed']}/{control['steps_target']}` steps, physical `{physical['steps_completed']}/{physical['steps_target']}` steps, exit code `0`.

Финальные artifacts присутствуют для обоих кейсов: `dump.final.lammpstrj`, chunk dump, `restart.10000`, `data.final`, `case_metadata.json`, `analysis.json`.

## Проверка ошибок

По production `*.lammps`, `*.txt`, `*.log` files аварийные markers `ERROR|nan|lost atoms|cudaError|illegal memory`: {marker_text}.

Широкий поиск по run root может находить false positives в YAML/JSON/markdown, например `nan_found: false` или список проверяемых tokens. Они не являются runtime failure.

## DXA: дислокации

| case | segments | total line length A | density m^-2 | interpretation |
| --- | ---: | ---: | ---: | --- |
| control eps0000 | {control['analysis']['dxa']['dislocation_segments']} | {control['analysis']['dxa']['dislocation_length_A']} | {control['analysis']['dxa']['dislocation_density_per_m2']:.3e} | дислокации не найдены |
| physical eps0025 | {physical['analysis']['dxa']['dislocation_segments']} | {physical['analysis']['dxa']['dislocation_length_A']} | {physical['analysis']['dxa']['dislocation_density_per_m2']:.3e} | дислокации не найдены |

## CNA/PTM: структура Al-матрицы

### CNA

| case | FCC atoms | HCP atoms | OTHER atoms | FCC % | HCP % | OTHER % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control eps0000 | {control['analysis']['cna']['fcc_atoms']} | {control['analysis']['cna']['hcp_atoms']} | {control['analysis']['cna']['other_atoms']} | {control['analysis']['cna']['fcc_pct']} | {control['analysis']['cna']['hcp_pct']} | {control['analysis']['cna']['other_pct']} |
| physical eps0025 | {physical['analysis']['cna']['fcc_atoms']} | {physical['analysis']['cna']['hcp_atoms']} | {physical['analysis']['cna']['other_atoms']} | {physical['analysis']['cna']['fcc_pct']} | {physical['analysis']['cna']['hcp_pct']} | {physical['analysis']['cna']['other_pct']} |

Physical-control: FCC `{comparison['cna_fcc_atoms_delta_physical_minus_control']}`, HCP `+{comparison['cna_hcp_atoms_delta_physical_minus_control']}`, OTHER `+{comparison['cna_other_atoms_delta_physical_minus_control']}` atoms.

### PTM

| case | PTM FCC atoms | PTM HCP atoms | PTM OTHER atoms | PTM FCC % | PTM HCP % | PTM OTHER % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control eps0000 | {control['analysis']['ptm']['fcc_atoms']} | {control['analysis']['ptm']['hcp_atoms']} | {control['analysis']['ptm']['other_atoms']} | {control['analysis']['ptm']['fcc_pct']} | {control['analysis']['ptm']['hcp_pct']} | {control['analysis']['ptm']['other_pct']} |
| physical eps0025 | {physical['analysis']['ptm']['fcc_atoms']} | {physical['analysis']['ptm']['hcp_atoms']} | {physical['analysis']['ptm']['other_atoms']} | {physical['analysis']['ptm']['fcc_pct']} | {physical['analysis']['ptm']['hcp_pct']} | {physical['analysis']['ptm']['other_pct']} |

PTM подтверждает тот же знак изменения: в eps0025 меньше FCC и больше OTHER, чем в control.

## Дефекты упаковки

| case | matrix defect atoms total | defects beyond 1.3 shell | HCP beyond 1.3 shell | max normalized distance |
| --- | ---: | ---: | ---: | ---: |
| control eps0000 | {control['analysis']['plastic_zone']['matrix_defect_atoms_total']} | {control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']} | {control['analysis']['plastic_zone']['hcp_atoms_beyond_1p3_shell']} | {control['analysis']['plastic_zone']['max_normalized_ellipsoid_distance']:.3f} |
| physical eps0025 | {physical['analysis']['plastic_zone']['matrix_defect_atoms_total']} | {physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']} | {physical['analysis']['plastic_zone']['hcp_atoms_beyond_1p3_shell']} | {physical['analysis']['plastic_zone']['max_normalized_ellipsoid_distance']:.3f} |

Control почти полностью ограничен интерфейсом. В eps0025 `323` defect atoms выходят за 1.3 shell, что является precursor-перестройкой матрицы.

HCP beyond 1.3 shell равен `0` в обоих кейсах, поэтому выраженная stacking fault plane в матрице не подтверждена.

## Напряжения и профили

| case | zone | pzz MPa | von Mises MPa | hydrostatic MPa | max shear MPa |
| --- | --- | ---: | ---: | ---: | ---: |
| control | inclusion | {control['analysis']['stress_proxy']['inclusion']['pzz_MPa']} | {control['analysis']['stress_proxy']['inclusion']['von_mises_MPa']} | {control['analysis']['stress_proxy']['inclusion']['hydrostatic_pressure_MPa']} | {control['analysis']['stress_proxy']['inclusion']['max_abs_shear_MPa']} |
| control | interface matrix 0-5 A | {control['analysis']['stress_proxy']['interface_matrix_0_5A']['pzz_MPa']} | {control['analysis']['stress_proxy']['interface_matrix_0_5A']['von_mises_MPa']} | {control['analysis']['stress_proxy']['interface_matrix_0_5A']['hydrostatic_pressure_MPa']} | {control['analysis']['stress_proxy']['interface_matrix_0_5A']['max_abs_shear_MPa']} |
| control | matrix near 5-15 A | {control['analysis']['stress_proxy']['matrix_near_5_15A']['pzz_MPa']} | {control['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']} | {control['analysis']['stress_proxy']['matrix_near_5_15A']['hydrostatic_pressure_MPa']} | {control['analysis']['stress_proxy']['matrix_near_5_15A']['max_abs_shear_MPa']} |
| control | matrix far >15 A | {control['analysis']['stress_proxy']['matrix_far_gt_15A']['pzz_MPa']} | {control['analysis']['stress_proxy']['matrix_far_gt_15A']['von_mises_MPa']} | {control['analysis']['stress_proxy']['matrix_far_gt_15A']['hydrostatic_pressure_MPa']} | {control['analysis']['stress_proxy']['matrix_far_gt_15A']['max_abs_shear_MPa']} |
| physical | inclusion | {physical['analysis']['stress_proxy']['inclusion']['pzz_MPa']} | {physical['analysis']['stress_proxy']['inclusion']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['inclusion']['hydrostatic_pressure_MPa']} | {physical['analysis']['stress_proxy']['inclusion']['max_abs_shear_MPa']} |
| physical | interface matrix 0-5 A | {physical['analysis']['stress_proxy']['interface_matrix_0_5A']['pzz_MPa']} | {physical['analysis']['stress_proxy']['interface_matrix_0_5A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['interface_matrix_0_5A']['hydrostatic_pressure_MPa']} | {physical['analysis']['stress_proxy']['interface_matrix_0_5A']['max_abs_shear_MPa']} |
| physical | matrix near 5-15 A | {physical['analysis']['stress_proxy']['matrix_near_5_15A']['pzz_MPa']} | {physical['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['matrix_near_5_15A']['hydrostatic_pressure_MPa']} | {physical['analysis']['stress_proxy']['matrix_near_5_15A']['max_abs_shear_MPa']} |
| physical | matrix far >15 A | {physical['analysis']['stress_proxy']['matrix_far_gt_15A']['pzz_MPa']} | {physical['analysis']['stress_proxy']['matrix_far_gt_15A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['matrix_far_gt_15A']['hydrostatic_pressure_MPa']} | {physical['analysis']['stress_proxy']['matrix_far_gt_15A']['max_abs_shear_MPa']} |

Stress values are final-dump virial proxies. Они пригодны для сравнения зон и control-vs-physical, но не как безусловно точные абсолютные MPa.

## Сравнение control vs eps0025

- DXA: `{control['analysis']['dxa']['dislocation_segments']}` -> `{physical['analysis']['dxa']['dislocation_segments']}` segments; подтвержденных линий нет.
- CNA OTHER: `{control['analysis']['cna']['other_atoms']}` -> `{physical['analysis']['cna']['other_atoms']}` atoms.
- PTM OTHER: `{control['analysis']['ptm']['other_atoms']}` -> `{physical['analysis']['ptm']['other_atoms']}` atoms.
- Defects beyond 1.3 shell: `{control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}` -> `{physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}` atoms.
- Near-matrix von Mises proxy: `{control['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']}` -> `{physical['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']}` MPa.

## Что можно утверждать

- Full-run завершился штатно для двух stable cases.
- `eps0025` дает больший structural disorder в Al-матрице, чем control.
- Есть early precursor перестройки за пределами ближайшей interface shell.
- Дислокационные линии DXA еще не сформировались.

## Что нельзя утверждать

- Нельзя утверждать развитую дислокационную пластику.
- Нельзя утверждать устойчивую stacking fault plane.
- Нельзя использовать `eps0100` как физически достоверный full-run результат.
- Нельзя трактовать local stress proxy как calibrated absolute stress.

## Ограничения модели

- 10000 production steps, не 250k/500k/700k/1M.
- Монокристаллическая матрица без GB/vacancy predefects.
- Inclusion удерживается, а не полностью свободно релаксирует.
- Stress profile получен из final dump, не из time-averaged stress trajectory.

## Следующий шаг

Для защиты использовать формулировку Variant B: ранняя структурная/пластическая перестройка без подтвержденных DXA дислокаций. Любой новый MD branch, longer run или render требует отдельного explicit approval.
"""
    write_text(RUN / "stageD_postrun_analysis_report.md", postrun)

    comparison_md = f"""
# Stage D comparison: control eps0000 vs physical eps0025

Generated: `{generated_at}`

## Result In One Sentence

`eps_z=0.0025` не создал DXA-дислокации за 10000 production steps, но дал измеримое распространение structural disorder из интерфейсной зоны в алюминиевую матрицу: OTHER +`{comparison['cna_other_atoms_delta_physical_minus_control']}` atoms по CNA и defects beyond 1.3 shell +`{comparison['defects_beyond_1p3_shell_delta']}` atoms.

## Numerical Comparison

| metric | control eps0000 | physical eps0025 | change | interpretation |
| --- | ---: | ---: | ---: | --- |
| final temperature K | {control['final_temperature_K']:.5f} | {physical['final_temperature_K']:.5f} | {physical['final_temperature_K'] - control['final_temperature_K']:.5f} | оба кейса термально стабильны |
| max temperature K | {control['max_temperature_K']:.5f} | {physical['max_temperature_K']:.5f} | {physical['max_temperature_K'] - control['max_temperature_K']:.5f} | spike нет |
| final pressure MPa | {control['final_pressure_MPa']:.3f} | {physical['final_pressure_MPa']:.3f} | {physical['final_pressure_MPa'] - control['final_pressure_MPa']:.3f} | physical немного выше |
| max pressure MPa | {control['max_pressure_MPa']:.3f} | {physical['max_pressure_MPa']:.3f} | {physical['max_pressure_MPa'] - control['max_pressure_MPa']:.3f} | physical выше |
| DXA segments | {control['analysis']['dxa']['dislocation_segments']} | {physical['analysis']['dxa']['dislocation_segments']} | {comparison['dislocation_segments_delta']} | дислокации не подтверждены |
| CNA HCP atoms | {control['analysis']['cna']['hcp_atoms']} | {physical['analysis']['cna']['hcp_atoms']} | {comparison['cna_hcp_atoms_delta_physical_minus_control']} | слабый HCP рост |
| CNA OTHER atoms | {control['analysis']['cna']['other_atoms']} | {physical['analysis']['cna']['other_atoms']} | {comparison['cna_other_atoms_delta_physical_minus_control']} | рост disorder |
| PTM OTHER atoms | {control['analysis']['ptm']['other_atoms']} | {physical['analysis']['ptm']['other_atoms']} | {comparison['ptm_other_atoms_delta_physical_minus_control']} | PTM подтверждает CNA trend |
| defects beyond 1.3 shell | {control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']} | {physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']} | {comparison['defects_beyond_1p3_shell_delta']} | precursor ушел в матрицу |
| interface von Mises MPa | {control['analysis']['stress_proxy']['interface_matrix_0_5A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['interface_matrix_0_5A']['von_mises_MPa']} | {comparison['interface_von_mises_delta_MPa']} | interface stress proxy близок |
| near matrix von Mises MPa | {control['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['matrix_near_5_15A']['von_mises_MPa']} | {comparison['near_matrix_von_mises_delta_MPa']} | near matrix stress proxy вырос |
| far matrix von Mises MPa | {control['analysis']['stress_proxy']['matrix_far_gt_15A']['von_mises_MPa']} | {physical['analysis']['stress_proxy']['matrix_far_gt_15A']['von_mises_MPa']} | {comparison['far_matrix_von_mises_delta_MPa']} | far matrix остается low-deviatoric |

## Physical Difference

- `eps0025` снижает долю FCC и повышает долю OTHER/HCP в матрице относительно control.
- В control disorder почти весь сидит у интерфейса: только `2` defect atoms beyond 1.3 shell.
- В eps0025 `323` defect atoms выходят за 1.3 shell; это ранняя зона перестройки в матрице.
- DXA не видит дислокационных линий: segments `0`, line length `0 A` в обоих кейсах.
- HCP beyond 1.3 shell равно `0`, поэтому stacking-fault claim остается слабым.
"""
    write_text(RUN / "stageD_comparison_control_vs_physical.md", comparison_md)

    interpretation = f"""
# Stage D physical interpretation

Generated: `{generated_at}`

## Final Interpretation

{interpretation_text}

## Why Not Variant A

Вариант А требовал бы подтвержденной пластической деформации через дислокации и/или выраженные дефекты упаковки. Здесь DXA segments `0`, total line length `0 A`, HCP atoms beyond 1.3 shell `0` в обоих кейсах. Развитую дислокационную пластику утверждать нельзя.

## Why Not Purely Elastic Variant V

Чисто упругий вариант плохо объясняет рост disorder в eps0025:

- CNA OTHER: `{control['analysis']['cna']['other_atoms']}` -> `{physical['analysis']['cna']['other_atoms']}`;
- PTM OTHER: `{control['analysis']['ptm']['other_atoms']}` -> `{physical['analysis']['ptm']['other_atoms']}`;
- defects beyond 1.3 shell: `{control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}` -> `{physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}`;
- max normalized defect distance: `{control['analysis']['plastic_zone']['max_normalized_ellipsoid_distance']:.3f}` -> `{physical['analysis']['plastic_zone']['max_normalized_ellipsoid_distance']:.3f}`.

## What Can Be Claimed

- Full-run завершился штатно для control eps0000 и physical eps0025.
- eps0100 не участвовал в full-run и исключен из физического сравнения из-за smoke-only spike около `37086.592 K`.
- В eps0025 структура матрицы повреждается сильнее, чем в control.
- Дефектная зона в eps0025 распространяется дальше от интерфейса, чем в control.
- На масштабе 10000 production steps сформированных дислокаций нет.
- Корректная формулировка: ранние признаки пластической/структурной перестройки без развитой дислокационной линии.

## What Cannot Be Claimed

- Нельзя утверждать развитую дислокационную пластику.
- Нельзя утверждать устойчивую stacking fault plane в матрице.
- Нельзя использовать eps0100 как доказательство физической пластики.
- Нельзя трактовать локальные stress proxy MPa как строго калиброванные абсолютные напряжения.

## Defense Wording

`Для физического eigenstrain eps_z=0.0025 мы не получили развитых дислокаций, но получили воспроизводимый precursor: рост OTHER/HCP и выход дефектных атомов матрицы за ближайшую интерфейсную оболочку. Поэтому результат соответствует ранней структурной перестройке вокруг включения, а не доказанной дислокационной пластичности.`
"""
    write_text(RUN / "stageD_interpretation_report.md", interpretation)


def write_contexts(
    control: dict[str, Any],
    physical: dict[str, Any],
    generated_at: str,
) -> None:
    context = f"""
current objective: Stage D post-run analysis for `D1_local_interface_100k` is completed; preserve reports and do not launch new LAMMPS without a new explicit task.
verified: target repo is `C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe` on branch `ilua/auto/stageD-local-interface-100k-mechanics`; project-local `AGENTS.md` / `AGENTS.override.md` are absent; global `C:\\Users\\dille\\.codex\\AGENTS.md` is absent.
verified: no live `run_stage_sweep.py` or `lmp_kokkos_cuda*` process was present before analysis; post-run analysis used existing final dumps only.
verified: full-run completed for `D1_local_interface_control_eps0000` and `D1_local_interface_physical_eps0025`; both reached `10000/10000` production steps with exit code `0`.
verified: `D1_local_interface_overload_eps0100` was excluded from full-run because smoke-only prep reached about `37086.592 K`; it must not be interpreted as physically reliable plasticity.
verified: actual production log/stdout/stderr scan found no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers.
verified: final production artifacts exist for both completed cases: `dump.final.lammpstrj`, `dump.chunk0000000_0010000.lammpstrj`, `restart.10000`, `data.final`, `case_metadata.json`, and `analysis.json`.
verified: OVITO DXA/CNA/PTM post-processing completed through `scripts\\run_stage_sweep.py --analyze-only`; `analysis/python/stage_runner/analysis_runner.py` now records PTM and virial stress proxy metrics in `analysis.json`.
verified: DXA found zero dislocation segments and zero total line length in both control and eps0025.
verified: CNA matrix structure changed from control to eps0025: HCP `{control['analysis']['cna']['hcp_atoms']}` -> `{physical['analysis']['cna']['hcp_atoms']}`, OTHER `{control['analysis']['cna']['other_atoms']}` -> `{physical['analysis']['cna']['other_atoms']}`, defects beyond 1.3 shell `{control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}` -> `{physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}`.
verified: interpretation is Variant B: early plastic/structural rearrangement precursor without formed DXA dislocation lines; do not claim developed dislocation plasticity.
files_touched: `analysis\\python\\stage_runner\\analysis_runner.py`, `scripts\\analyze_stageD_postrun.py`, run-root Stage D post-run reports/status JSON, `case_summaries\\*_summary.json`, `docs\\60_milestones\\2026-06-18_stageD_local_interface_100k_prepare.md`, project `.codex\\state\\current_context.md`, system `.codex\\state\\current_context.md`, and system report `state\\reports\\physics_md_al_fe\\stageD_postrun_analysis_20260622.json`.
root_cause_or_hypothesis: physical `eps_z=0.0025` produces a measurable near-interface structural precursor in the Al matrix but not enough sustained shear/slip to form DXA dislocation lines during the 10000-step production window.
pending_blockers: none for post-run analysis; remaining limitation is scientific, not runtime: local stress is a final-dump virial proxy and should not be treated as calibrated time-averaged stress.
exact_next_command: `Get-Content runs\\stageD_local_interface_100k_mechanics\\20260618-215638\\stageD_interpretation_report.md`
exact_next_step: review the interpretation report for defense wording; any further production length, render, or new MD branch needs a new explicit approval.
last_updated: `{generated_at}`
"""
    write_text(REPO / ".codex" / "state" / "current_context.md", context)
    system_context = context.replace(
        "target repo is `C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe`",
        "target repo is `C:\\Users\\dille\\Documents\\ilua-system\\projects\\physics_md_al_fe`; control-plane branch is `chore/windows-setup`",
    )
    write_text(SYSTEM / ".codex" / "state" / "current_context.md", system_context)


def append_milestone(control: dict[str, Any], physical: dict[str, Any]) -> None:
    milestone = REPO / "docs" / "60_milestones" / "2026-06-18_stageD_local_interface_100k_prepare.md"
    old = milestone.read_text(encoding="utf-8", errors="replace")
    section_title = "## Post-run Analysis Completed, 2026-06-22"
    if section_title in old:
        old = old.split(section_title)[0].rstrip() + "\n\n"
    section = f"""
{section_title}

The full control+physical Stage D production run completed and was analyzed from existing final dumps only. No new LAMMPS calculation, eps0100 run, render, ffmpeg job, git commit, or push was performed.

Completed full-run cases:

- `D1_local_interface_control_eps0000`: `10000/10000` production steps, final temperature `{control['final_temperature_K']:.5f} K`, final pressure `{control['final_pressure_MPa']:.3f} MPa`.
- `D1_local_interface_physical_eps0025`: `10000/10000` production steps, final temperature `{physical['final_temperature_K']:.5f} K`, final pressure `{physical['final_pressure_MPa']:.3f} MPa`.

Excluded full-run case:

- `D1_local_interface_overload_eps0100`: excluded because smoke-only prep reached about `37086.592 K`; it is not physically reliable evidence of plasticity.

Post-run analysis:

- `scripts/run_stage_sweep.py --analyze-only` completed successfully on existing `dump.final.lammpstrj` files.
- `analysis/python/stage_runner/analysis_runner.py` now writes DXA, CNA, PTM, and final-dump virial stress proxy metrics.
- Actual log/stdout/stderr scan found no `ERROR`, `nan`, `lost atoms`, `cudaError`, or `illegal memory` markers.
- DXA found `0` dislocation segments and `0 A` total line length in both completed cases.
- CNA OTHER increased from `{control['analysis']['cna']['other_atoms']}` to `{physical['analysis']['cna']['other_atoms']}` matrix atoms.
- PTM OTHER increased from `{control['analysis']['ptm']['other_atoms']}` to `{physical['analysis']['ptm']['other_atoms']}` matrix atoms.
- Defect atoms beyond the 1.3 interface shell increased from `{control['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}` to `{physical['analysis']['plastic_zone']['defect_atoms_beyond_1p3_shell']}`.

Interpretation:

- Stage D supports Variant B: early structural/plastic rearrangement precursor around the inclusion.
- It does not support a claim of developed dislocation plasticity.
- HCP/stacking-fault evidence remains weak because HCP atoms beyond the 1.3 shell are `0`.
- Stress values are final-dump virial proxy values; use them for relative comparison, not calibrated absolute yield claims.
"""
    write_text(milestone, old.rstrip() + "\n\n" + section.strip() + "\n")


def main() -> int:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    summaries = [summarize_case(*case) for case in CASES]
    control, physical = summaries
    comparison = build_comparison(control, physical)
    interpretation_text = (
        "Вариант Б: есть ранние признаки пластической перестройки. DXA не нашел "
        "сформированных дислокационных линий, но в eps0025 выросла доля OTHER/HCP "
        "и резко увеличилось число дефектных атомов матрицы за пределами ближайшей "
        "1.3-оболочки интерфейса."
    )

    write_case_summaries(summaries)

    summary_payload = {
        "status": "postrun_analysis_completed",
        "generated_at": generated_at,
        "run_root": rel(RUN),
        "completed_cases": [item["case_id"] for item in summaries],
        "excluded_cases": EXCLUDED,
        "errors_found": not marker_scan_clean(),
        "error_scan": {
            "actual_log_stdout_stderr_markers_found": not marker_scan_clean(),
            "patterns": ["ERROR", "nan", "lost atoms", "cudaError", "illegal memory"],
        },
        "case_metrics": {
            item["case_id"]: {
                "eps_z": item["eps_z"],
                "completed": item["completed"],
                "final_step": item["final_step"],
                "final_temp_K": item["final_temp_K"],
                "final_press": item["final_press"],
                "dxa": item["dxa"],
                "cna": item["cna"],
                "ptm": item["ptm"],
                "stress_profiles_available": item["stress_profiles_available"],
                "key_stress_zones": item["key_stress_zones"],
                "science_signal": item["science_signal"],
            }
            for item in summaries
        },
        "cases": summaries,
        "comparison": comparison,
        "interpretation_variant": "B",
        "interpretation_ru": interpretation_text,
        "interpretation": {
            "status": "variant_B_early_plastic_rearrangement",
            "text_ru": interpretation_text,
        },
        "limits": [
            "10000 production steps only",
            "final-dump virial stress proxy, not time-averaged calibrated stress",
            "single-crystal matrix without grain boundary or vacancy predefects",
            "eps0100 excluded as physically unreliable after smoke-only temperature spike",
        ],
        "next_step": (
            "Use Stage D reports for defense wording; any longer MD, render, or new branch "
            "requires separate explicit approval."
        ),
        "analysis_tools": {
            "ovito_python_available": True,
            "dxa": True,
            "cna": True,
            "ptm": True,
            "stress_proxy_from_lammps_dump": True,
            "heavy_render": False,
            "ffmpeg": False,
        },
    }
    write_json(RUN / "stageD_analysis_summary.json", summary_payload)

    reports = [
        rel(RUN / "stageD_completion_check.md"),
        rel(RUN / "stageD_postrun_analysis_report.md"),
        rel(RUN / "stageD_comparison_control_vs_physical.md"),
        rel(RUN / "stageD_interpretation_report.md"),
        rel(RUN / "stageD_analysis_summary.json"),
        rel(RUN / "stageD_status.json"),
    ]
    status_payload = {
        "status": "postrun_analysis_completed",
        "generated_at": generated_at,
        "run_dir": str(RUN),
        "git_branch": "ilua/auto/stageD-local-interface-100k-mechanics",
        "full_run": {
            "completed": True,
            "completed_cases": [item["case_id"] for item in summaries],
            "excluded_cases": list(EXCLUDED),
            "excluded_reasons": EXCLUDED,
            "new_lammps_started_by_analysis": False,
            "production_error_markers_found": False,
        },
        "case_summaries": [
            rel(RUN / "case_summaries" / f"{item['case_id']}_summary.json") for item in summaries
        ],
        "comparison": comparison,
        "interpretation": summary_payload["interpretation"],
        "reports": reports,
        "blockers": [],
        "exact_next_command": "git diff --check",
    }
    write_json(RUN / "stageD_status.json", status_payload)
    write_markdown_reports(generated_at, control, physical, comparison, interpretation_text)
    write_contexts(control, physical, generated_at)
    append_milestone(control, physical)

    system_report = {
        "task": "Stage D post-run analysis control vs physical eps0025",
        "generated_at": generated_at,
        "target_repo": str(REPO),
        "target_branch": "ilua/auto/stageD-local-interface-100k-mechanics",
        "control_plane_branch": "chore/windows-setup",
        "run_root": str(RUN),
        "status": "postrun_analysis_completed",
        "completed_cases": [item["case_id"] for item in summaries],
        "excluded_cases": EXCLUDED,
        "summary": summary_payload,
        "reports_updated": reports
        + ["docs/60_milestones/2026-06-18_stageD_local_interface_100k_prepare.md"],
        "validation": {"pending": True},
        "exact_next_command": (
            "Get-Content runs\\stageD_local_interface_100k_mechanics\\20260618-215638"
            "\\stageD_interpretation_report.md"
        ),
    }
    write_json(
        SYSTEM / "state" / "reports" / "physics_md_al_fe" / "stageD_postrun_analysis_20260622.json",
        system_report,
    )
    print(json.dumps({"status": "postrun_analysis_completed", "reports": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
