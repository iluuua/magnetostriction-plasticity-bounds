#!/usr/bin/env python3
"""Prepare Stage D local inclusion-interface mechanics inputs without launching LAMMPS."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "analysis" / "python"))

from stage_runner import builder, gpu_grid  # noqa: E402

DEFAULT_CONFIG = REPO_ROOT / "configs" / "stageD_local_interface_100k_mechanics.template.yaml"
DEFAULT_STAGEC_ROOT = (
    REPO_ROOT
    / "runs"
    / "stageC_1M_nearGB_vacancies_eps0100_safe_prep"
    / "20260617-063915"
)
STAGE_NAME = "D1_local_interface_100k"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git_capture(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return proc.stdout.strip()


def latest_thermo_from_stdout(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    last: list[str] | None = None
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 10 and parts[0].isdigit():
                last = parts
    if not last:
        return None
    return {
        "step": int(last[0]),
        "atoms": int(last[1]),
        "temperature_K": float(last[2]),
        "potential_energy_eV": float(last[3]),
        "kinetic_energy_eV": float(last[4]),
        "total_energy_eV": float(last[5]),
        "pressure_bar": float(last[6]),
        "pxx_bar": float(last[7]),
        "pyy_bar": float(last[8]),
        "pzz_bar": float(last[9]),
    }


def stagec_status(stagec_root: Path) -> dict[str, Any]:
    status: dict[str, Any] = {
        "run_root": str(stagec_root),
        "exists": stagec_root.is_dir(),
        "process_alive": False,
        "latest_thermo": None,
        "latest_restart": None,
    }
    procs = gpu_grid.active_process_snapshot()
    status["active_processes"] = procs
    status["process_alive"] = any(procs.get(name) for name in ("lmp.exe", "lmp_kokkos_cuda.exe"))
    if not stagec_root.is_dir():
        return status
    stdout_candidates = sorted(stagec_root.rglob("stdout.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if stdout_candidates:
        status["stdout"] = str(stdout_candidates[0])
        status["latest_thermo"] = latest_thermo_from_stdout(stdout_candidates[0])
    restarts = sorted(stagec_root.rglob("restart.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if restarts:
        status["latest_restart"] = {
            "path": str(restarts[0]),
            "size_bytes": restarts[0].stat().st_size,
            "last_write_time": datetime.fromtimestamp(restarts[0].stat().st_mtime).isoformat(timespec="seconds"),
        }
    return status


def gpu_busy(snapshot: Mapping[str, Any]) -> bool:
    for gpu in snapshot.get("gpus", []) or []:
        try:
            if int(str(gpu.get("utilization_gpu_percent", "0")).strip()) >= 90:
                return True
        except ValueError:
            continue
    return False


def write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def case_label(case_id: str) -> str:
    if "control" in case_id:
        return "Контрольный вариант без собственной заданной деформации включения"
    if "physical" in case_id:
        return "Физически близкая собственная заданная деформация включения"
    if "overload" in case_id:
        return "Усиленная собственная заданная деформация включения"
    return "Расчетный вариант"


def write_case_placeholders(
    case_dir: Path,
    case: Mapping[str, Any],
    meta: Mapping[str, Any],
    run_block_reasons: list[str],
    prep_input: Path,
    command_path: Path,
) -> None:
    summary = {
        "case_id": case["case_id"],
        "variant": case_label(str(case["case_id"])),
        "eps_z": float(case["eps_z"]),
        "status": "prepared_not_started",
        "launch_allowed_now": False,
        "launch_block_reasons": run_block_reasons,
        "geometry": {
            "total_atoms": meta.get("actual_atom_count") or meta.get("total_atoms"),
            "matrix_atoms": meta.get("matrix_atoms"),
            "inclusion_atoms": meta.get("inclusion_atoms"),
            "matrix_max_id": meta.get("matrix_max_id"),
            "inclusion_id_min": meta.get("inclusion_id_min"),
            "inclusion_id_max": meta.get("inclusion_id_max"),
            "center_A": meta.get("center_A"),
            "inclusion_axes_A": meta.get("inclusion_axes_A"),
            "position": meta.get("position"),
            "predefect": meta.get("predefect"),
            "safe_basic": meta.get("safe_basic"),
        },
        "prepared_files": {
            "prep_input": str(prep_input),
            "prep_command": str(command_path),
            "geometry_metadata": str(case_dir / "geometry_metadata.json"),
            "analysis_csv": str(case_dir / "analysis.csv"),
            "stress_profiles_csv": str(case_dir / "stress_profiles.csv"),
            "structure_profiles_csv": str(case_dir / "structure_profiles.csv"),
            "final_report_md": str(case_dir / "final_report.md"),
        },
        "results": {
            "dislocation_lines_found": None,
            "stacking_faults_found": None,
            "matrix_stress_MPa": None,
            "stress_transfer_to_matrix": None,
            "deformation_type": "not_evaluated",
        },
    }
    write_json(case_dir / "summary.json", summary)
    write_csv(
        case_dir / "analysis.csv",
        ["metric", "value", "unit", "status", "note_ru"],
        [
            ["количество дислокационных линий", "", "линии", "не рассчитано", "LAMMPS не запускался"],
            ["суммарная длина дислокационных линий", "", "ангстрем", "не рассчитано", "нужен анализ траектории"],
            ["атомы с гексагональной плотной упаковкой", "", "атомы", "не рассчитано", "нужен анализ OVITO или эквивалент"],
            ["атомы с гранецентрированной кубической структурой алюминия", "", "атомы", "не рассчитано", "нужен анализ OVITO или эквивалент"],
            ["атомы с нарушенной или неопределенной локальной структурой", "", "атомы", "не рассчитано", "нужен анализ OVITO или эквивалент"],
            ["эквивалентное напряжение по Мизесу в матрице", "", "мегапаскаль", "не рассчитано", "нужна траектория со stress/atom"],
        ],
    )
    write_csv(
        case_dir / "stress_profiles.csv",
        ["zone_ru", "distance_from_interface_A", "sigma_zz_MPa", "von_mises_MPa", "hydrostatic_pressure_MPa", "status"],
        [
            ["включение", "", "", "", "", "не рассчитано"],
            ["граница включение - матрица", "0", "", "", "", "не рассчитано"],
            ["матрица рядом с включением", "", "", "", "", "не рассчитано"],
            ["матрица дальше от включения", "", "", "", "", "не рассчитано"],
        ],
    )
    write_csv(
        case_dir / "structure_profiles.csv",
        ["zone_ru", "distance_from_interface_A", "fcc_fraction", "hcp_fraction", "other_fraction", "status"],
        [
            ["граница включение - матрица", "0", "", "", "", "не рассчитано"],
            ["матрица рядом с включением", "", "", "", "", "не рассчитано"],
            ["дальний фоновый объем матрицы", "", "", "", "", "не рассчитано"],
        ],
    )
    lines = [
        f"# {case_label(str(case['case_id']))}",
        "",
        "Статус: подготовлен, но не запущен.",
        "",
        "## Почему расчет не запущен",
        "",
        *[f"- {reason}" for reason in run_block_reasons],
        "",
        "## Геометрия",
        "",
        f"- всего атомов: {summary['geometry']['total_atoms']}",
        f"- атомов алюминиевой матрицы: {summary['geometry']['matrix_atoms']}",
        f"- атомов включения: {summary['geometry']['inclusion_atoms']}",
        f"- eps_z (относительная собственная заданная деформация включения вдоль оси Z): {float(case['eps_z']):.4f}",
        f"- положение включения: внутри однородной алюминиевой матрицы, без границы зерна",
        f"- предварительные вакансии: отсутствуют",
        "",
        "## Что уже создано",
        "",
        f"- входной файл подготовки для LAMMPS (программы молекулярной динамики): `{prep_input}`",
        f"- команда будущего запуска: `{command_path}`",
        "",
        "## Результаты",
        "",
        "Дислокационные линии, дефекты упаковки, поле напряжений, эквивалентное напряжение по Мизесу и остаточные смещения пока не рассчитаны, потому что расчет не стартовал.",
    ]
    (case_dir / "final_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_report(
    run_dir: Path,
    cfg: Mapping[str, Any],
    cases: list[dict[str, Any]],
    stagec: Mapping[str, Any],
    run_block_reasons: list[str],
    smoke_command: str,
) -> None:
    thermo = stagec.get("latest_thermo") or {}
    lammps_alive_ru = "да" if stagec.get("process_alive") else "нет"
    lines = [
        "# Серия Stage D (этап D): локальная механика границы включение - матрица",
        "",
        "## 1. Цель расчета",
        "",
        "Проверить, возникает ли пластическая деформация в алюминиевой матрице от собственной заданной деформации интерметаллидного включения.",
        "",
        "## 2. Что сказал физик и какую гипотезу проверяем",
        "",
        "Проверяется простая механическая постановка без магнитной физики: включение деформируется вдоль оси Z, а расчет должен показать, передается ли напряжение в матрицу.",
        "",
        "## 3. Геометрия модели",
        "",
        "Однородная алюминиевая матрица, внутри матрицы эллипсоидальное Fe4Al13-включение. Граница зерна и вакансии в базовых вариантах не используются.",
        "",
        "## 4. Как задана деформация включения",
        "",
        "Подготовлены три значения собственной заданной деформации включения вдоль оси Z: 0.0000, 0.0025 и 0.0100.",
        "",
        "## 5. Почему ось Z считается направлением поля",
        "",
        "По постановке встречи направление поля магнитной индукции пока принимается вдоль оси Z; механическое воздействие задано в том же направлении.",
        "",
        "## 6. Какие варианты подготовлены",
        "",
    ]
    for case in cases:
        lines.append(
            f"- {case['case_id']}: {case_label(case['case_id'])}, "
            f"eps_z (относительная деформация вдоль оси Z)={case['eps_z']}"
        )
    lines += [
        "",
        "## 7. Температурная стабильность расчета",
        "",
        "Новая серия не запускалась. Будущий запуск должен начинаться с безопасной подготовки: медленный нагрев, малый шаг интегрирования, контроль температуры и периодическая запись restart-файлов (файлов перезапуска).",
        "",
        "## 8. Напряжения во включении",
        "",
        "Не рассчитаны.",
        "",
        "## 9. Напряжения в матрице",
        "",
        "Не рассчитаны.",
        "",
        "## 10. Передача напряжения через границу включение - матрица",
        "",
        "Не рассчитана.",
        "",
        "## 11. Наличие или отсутствие дислокаций",
        "",
        "Не рассчитано.",
        "",
        "## 12. Наличие или отсутствие дефектов упаковки",
        "",
        "Не рассчитано.",
        "",
        "## 13. Наличие атомов с нарушенной структурой",
        "",
        "Не рассчитано.",
        "",
        "## 14. Упругая или пластическая деформация",
        "",
        "Не определено: расчет не запущен.",
        "",
        "## 15. Основной вывод",
        "",
        "Серия Stage D (этап D) подготовлена, но запуск заблокирован текущим большим расчетом и состоянием ресурсов.",
        "",
        "## 16. Что делать дальше",
        "",
        "После завершения текущего большого расчета и освобождения ресурсов запустить подготовку и короткую smoke-проверку (первичную короткую проверку запуска) командой:",
        "",
        f"`{smoke_command}`",
        "",
        "## Текущий большой расчет",
        "",
        f"- папка расчета: `{stagec.get('run_root')}`",
        f"- процесс LAMMPS (программы молекулярной динамики) жив: {lammps_alive_ru}",
        f"- последний шаг в логе: {thermo.get('step')}",
        f"- температура: {thermo.get('temperature_K')} К",
        "",
        "## Причины блокировки запуска сейчас",
        "",
        *[f"- {reason}" for reason in run_block_reasons],
        "",
        "Финальная интерпретация по вариантам А/Б/В/Г не назначена, потому что расчетные данные пока отсутствуют.",
    ]
    (run_dir / "stageD_interpretation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--run-dir", default=None)
    parser.add_argument("--stagec-run-root", default=str(DEFAULT_STAGEC_ROOT))
    args = parser.parse_args(argv)

    cfg = gpu_grid.load_grid_config(args.config)
    runner = gpu_grid.GpuGridRunner(cfg, run_dir=args.run_dir)
    run_dir = runner.run_dir

    stage = cfg["stages"][STAGE_NAME]
    stagec = stagec_status(Path(args.stagec_run_root))
    gpu_snapshot = gpu_grid.nvidia_smi_snapshot()
    disk_free_gb = gpu_grid.free_disk_gb(run_dir)
    git_status = git_capture(["status", "--short"]) or "<clean>"
    git_branch = git_capture(["branch", "--show-current"])

    run_block_reasons: list[str] = []
    if stagec.get("process_alive"):
        run_block_reasons.append("текущий большой расчет LAMMPS еще идет")
    if gpu_busy(gpu_snapshot):
        run_block_reasons.append("видеокарта занята примерно на 90 процентов или сильнее")
    min_disk = float(cfg["resources"]["min_free_disk_gb_before_stage"])
    if disk_free_gb < min_disk:
        run_block_reasons.append(f"свободно {disk_free_gb:.2f} ГиБ, меньше порога {min_disk:.2f} ГиБ")
    if not run_block_reasons:
        run_block_reasons.append("автоматический запуск отключен: сначала нужна ручная проверка подготовки")

    prepared_cases: list[dict[str, Any]] = []
    for case in stage["cases"]:
        meta = runner.ensure_stageb_geometry(STAGE_NAME, case)
        case_name = str(case["case_id"])
        prep_case = runner._stageb_runtime_case_id(case, "prep")
        prep_dir = runner.stageb_case_dir(STAGE_NAME, case_name, "prep")
        prep_input_text = builder.make_prep_input_gpu_safe(
            meta,
            t_start_K=float(stage.get("prep_t_start_K", 50.0)),
            t_target_K=float(cfg["experiment"]["temperature_K"]),
            ramp_steps=int(stage.get("prep_ramp_steps", 3000)),
            equil_steps=int(stage.get("prep_steps", stage["smoke_steps"])),
            seed=int(case["deterministic_seed"]),
            thermo_every=int(cfg["io_policy"]["thermo_every"]["smoke"]),
            neighbor_policy=cfg["gpu_profile"]["required_input_rewrites"]["neighbor_policy"],
            restart_every=int(stage.get("prep_restart_every", cfg["io_policy"].get("restart_every", 10000))),
            restart_prefix=prep_case,
            dump_every=stage.get("prep_dump_every"),
            dump_fields=stage.get("prep_dump_fields"),
        )
        runner._assert_prep_input_safe(prep_input_text, prep_case)
        runner.assert_generated_input_safe(prep_input_text, prep_case)
        prep_input = prep_dir / f"in.{prep_case}"
        prep_log = prep_dir / f"log.{prep_case}.lammps"
        prep_command = runner.lammps_cmd(prep_input, prep_log)
        command_path = prep_dir / "command.txt"
        prep_input.write_text(prep_input_text, encoding="utf-8", newline="\n")
        command_path.write_text(gpu_grid.command_text(prep_command) + "\n", encoding="utf-8")
        write_json(prep_dir / "geometry_metadata.json", meta)
        write_case_placeholders(prep_dir, case, meta, run_block_reasons, prep_input, command_path)
        prepared_cases.append(
            {
                "case_id": case_name,
                "eps_z": float(case["eps_z"]),
                "prep_input": str(prep_input),
                "prep_command": str(command_path),
                "geometry_atoms": meta.get("actual_atom_count") or meta.get("total_atoms"),
            }
        )

    smoke_command = (
        ".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py "
        f"--config {run_dir / 'effective_config.yaml'} "
        f"--run-dir {run_dir} --run-stage {STAGE_NAME} --gpu --smoke-only"
    )
    (run_dir / "launch_smoke_when_safe.txt").write_text(smoke_command + "\n", encoding="utf-8")
    (run_dir / "check_env_command.txt").write_text(
        f".venv\\Scripts\\python.exe scripts\\run_stage_sweep.py --config {run_dir / 'effective_config.yaml'} --check-env\n",
        encoding="utf-8",
    )
    write_csv(
        run_dir / "case_index.csv",
        ["case_id", "eps_z", "geometry_atoms", "prep_input", "prep_command"],
        [[c["case_id"], c["eps_z"], c["geometry_atoms"], c["prep_input"], c["prep_command"]] for c in prepared_cases],
    )
    status = {
        "status": "prepared_not_started",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "git_branch": git_branch,
        "git_status_short": git_status,
        "stageC_status": stagec,
        "nvidia_smi": gpu_snapshot,
        "disk_free_gb": round(disk_free_gb, 3),
        "launch_allowed_now": False,
        "launch_block_reasons": run_block_reasons,
        "prepared_cases": prepared_cases,
        "launch_smoke_when_safe": smoke_command,
    }
    write_json(run_dir / "stageD_status.json", status)
    write_json(run_dir / "state.json", {"run_dir": str(run_dir), "cases": {}, "stages": {}, "stageD_prepare": status})
    write_root_report(run_dir, cfg, prepared_cases, stagec, run_block_reasons, smoke_command)
    print(json.dumps({"run_dir": str(run_dir), "prepared_cases": prepared_cases, "launch_block_reasons": run_block_reasons}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
