"""Run-local LAMMPS input preparation and execution with walltime enforcement.

Tracked templates are never modified: every run gets a rewritten copy inside its
own run directory, and LAMMPS executes with cwd = that directory so all outputs
(dumps, final data, restarts, logs) stay run-local.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import paths
from .log_parser import parse_log
from .resources import disk_free_gb


class TemplateRewriteError(RuntimeError):
    pass


def _sub_required(pattern: str, repl: str, text: str, what: str, count: int = 0) -> str:
    new_text, n = re.subn(pattern, repl, text, count=count, flags=re.MULTILINE)
    if n == 0:
        raise TemplateRewriteError(f"template rewrite failed: pattern for {what} not found")
    return new_text


def rewrite_template(
    template_text: str,
    *,
    repo_root: Path,
    read_data: Path | None = None,
    run_steps: int | None = None,
    dump_every: int | None = None,
    restart_every: int | None = None,
    inclusion_id_range: tuple[int, int] | None = None,
    velocity_seed: int | None = None,
) -> str:
    """Rewrite a committed A0 template into a run-local input (physics unchanged)."""
    text = template_text
    repo = Path(repo_root).resolve().as_posix()

    # Make ../../../ (and deeper) template-relative paths absolute, so the input
    # works from any run-local directory. Repo path contains no spaces.
    text = text.replace("../../../../", repo + "/")
    text = text.replace("../../../", repo + "/")

    if read_data is not None:
        text = _sub_required(
            r"^read_data\s+\S+",
            f"read_data       {Path(read_data).resolve().as_posix()}",
            text,
            "read_data",
            count=1,
        )
    if dump_every is not None:
        text = _sub_required(
            r"^(dump\s+d1\s+all\s+custom\s+)\d+",
            rf"\g<1>{int(dump_every)}",
            text,
            "dump frequency",
            count=1,
        )
    if run_steps is not None:
        text = _sub_required(
            r"^run\s+\d+",
            f"run             {int(run_steps)}",
            text,
            "run steps",
            count=1,
        )
    if inclusion_id_range is not None:
        lo, hi = inclusion_id_range
        text = _sub_required(
            r"^(group\s+inclusion id )\d+:\d+",
            rf"\g<1>{int(lo)}:{int(hi)}",
            text,
            "inclusion id range",
            count=1,
        )
    if velocity_seed is not None:
        text = _sub_required(
            r"^(velocity\s+matrix create [\d.]+ )\d+",
            rf"\g<1>{int(velocity_seed)}",
            text,
            "velocity seed",
            count=1,
        )
    if restart_every:
        text = _sub_required(
            r"^(run\s+\d+)",
            rf"restart         {int(restart_every)} restart.a.bin restart.b.bin\n\g<1>",
            text,
            "restart insertion",
            count=1,
        )
    return text


def build_command(
    *,
    mode: str,
    lmp: str,
    mpiexec: str | None,
    ranks: int,
    omp_threads: int,
    input_name: str,
    log_name: str,
) -> tuple[list[str], dict]:
    """Command + env overrides for one LAMMPS execution mode."""
    env_over = {}
    if mode == "cpu_mpi_meam":
        if not mpiexec:
            raise RuntimeError("cpu_mpi_meam mode requires mpiexec, none found")
        cmd = [mpiexec, "-np", str(ranks), lmp, "-in", input_name, "-log", log_name]
        env_over["OMP_NUM_THREADS"] = "1"  # plain MPI: avoid thread oversubscription
    elif mode == "kokkos_gpu_meam":
        if not mpiexec:
            raise RuntimeError("kokkos_gpu_meam mode requires mpiexec, none found")
        cmd = [
            mpiexec, "-np", "1", lmp,
            "-k", "on", "g", "1", "t", str(omp_threads), "-sf", "kk",
            "-in", input_name, "-log", log_name,
        ]
        env_over["OMP_NUM_THREADS"] = str(omp_threads)
    elif mode == "kokkos_cpu_meam":
        cmd = [
            lmp, "-k", "on", "t", str(omp_threads), "-sf", "kk",
            "-in", input_name, "-log", log_name,
        ]
        env_over["OMP_NUM_THREADS"] = str(omp_threads)
    else:
        raise RuntimeError(f"unknown LAMMPS execution mode: {mode}")
    return cmd, env_over


def _kill_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        timeout=60,
    )


def execute_lammps(
    *,
    name: str,
    run_dir: Path,
    input_text: str,
    input_name: str,
    log_name: str,
    mode: str,
    lmp: str,
    mpiexec: str | None,
    ranks: int,
    omp_threads: int,
    timeout_s: float,
) -> dict:
    """Write the run-local input, execute LAMMPS, parse the log, collect outputs."""
    run_dir = paths.ensure_inside_runs(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    input_path = run_dir / input_name
    input_path.write_text(input_text, encoding="utf-8", newline="\n")

    cmd, env_over = build_command(
        mode=mode,
        lmp=lmp,
        mpiexec=mpiexec,
        ranks=ranks,
        omp_threads=omp_threads,
        input_name=input_name,
        log_name=log_name,
    )
    env = dict(os.environ)
    env.update(env_over)

    record: dict = {
        "name": name,
        "mode": mode,
        "command": cmd,
        "cwd": str(run_dir),
        "started": datetime.now().isoformat(timespec="seconds"),
        "timeout_s": timeout_s,
        "disk_free_before_gb": round(disk_free_gb(run_dir), 2),
    }

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    t0 = time.monotonic()
    timed_out = False
    with stdout_path.open("w", encoding="utf-8") as out_f, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_f:
        proc = subprocess.Popen(
            cmd, cwd=str(run_dir), env=env, stdout=out_f, stderr=err_f
        )
        try:
            exit_code = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc.pid)
            try:
                exit_code = proc.wait(timeout=120)
            except subprocess.TimeoutExpired:
                exit_code = -9999

    record["finished"] = datetime.now().isoformat(timespec="seconds")
    record["duration_s"] = round(time.monotonic() - t0, 1)
    record["exit_code"] = exit_code
    record["timed_out"] = timed_out
    record["disk_free_after_gb"] = round(disk_free_gb(run_dir), 2)

    record["log"] = parse_log(run_dir / log_name)

    outputs = []
    for f in sorted(run_dir.iterdir()):
        if f.is_file() and f.name.startswith(("dump.", "data.", "log.", "restart.")):
            outputs.append({"name": f.name, "size_bytes": f.stat().st_size})
    record["outputs"] = outputs
    return record
