"""OVITO render plan and manifest helpers."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .schema import MANIFEST_FIELDS
from .timeline import as_int, normalize_path, read_json, write_json


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class RenderPreset:
    mode: str
    camera_id: str
    coloring_mode: str
    visible_layers: str
    width: int = 1920
    height: int = 1080


RENDER_PRESETS = {
    "event": RenderPreset("event", "stageB_event_fixed_v1", "structure_type+dxa", "atoms,inclusion,gb,dxa,legend,scalebar,timestep_label"),
    "dxa": RenderPreset("dxa", "stageB_dxa_fixed_v1", "dxa_lines", "atoms,dxa,legend,scalebar,timestep_label"),
    "deformation": RenderPreset("deformation", "stageB_deformation_fixed_v1", "atomic_strain_or_Dmin2", "atoms,inclusion,gb,legend,scalebar,timestep_label"),
    "geometry": RenderPreset("geometry", "stageB_geometry_overview_v1", "particle_type", "atoms,inclusion,gb,legend,scalebar"),
    "figures": RenderPreset("figures", "stageB_paper_panel_v1", "event_class_aware", "atoms,inclusion,gb,dxa,legend,scalebar,timestep_label"),
}


def load_timeline(path: str | Path) -> list[dict[str, Any]]:
    data = read_json(normalize_path(path), {}) or {}
    return list(data.get("frames") or [])


def selected_rows_for_mode(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == "dxa":
        selected = [r for r in rows if r.get("event_class") == "confirmed_DXA"]
        return selected or [r for r in rows if r.get("dump_file")]
    if mode == "figures":
        confirmed = [r for r in rows if r.get("event_class") == "confirmed_DXA"]
        if confirmed:
            focus = sorted(confirmed, key=lambda r: as_int(r.get("timestep"), 10**18) or 10**18)[0]
        else:
            candidates = [r for r in rows if r.get("event_class") in ("weak_hcp", "deformation_only")]
            focus = sorted(candidates, key=lambda r: float(r.get("event_score") or 0.0), reverse=True)[0] if candidates else (rows[0] if rows else None)
        if not focus:
            return []
        same_case = [r for r in rows if r.get("case_id") == focus.get("case_id")]
        selected = same_case[:1] + [focus] + same_case[-1:]
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in selected:
            key = str(row.get("frame_id") or row.get("dump_file") or len(deduped))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped
    if mode == "geometry":
        seen: set[str] = set()
        out = []
        for row in rows:
            case = str(row.get("case_id"))
            if case not in seen and row.get("dump_file"):
                seen.add(case)
                out.append(row)
        return out
    return [r for r in rows if r.get("dump_file")]


def manifest_row(source: dict[str, Any], preset: RenderPreset, output_png: Path, index: int) -> dict[str, Any]:
    row = {field: source.get(field, "") for field in MANIFEST_FIELDS}
    row["frame_id"] = source.get("frame_id") or f"frame_{index:05d}"
    row["camera_id"] = preset.camera_id
    row["coloring_mode"] = preset.coloring_mode
    row["visible_layers"] = preset.visible_layers
    row["output_png"] = str(output_png)
    row["analysis_file"] = source.get("analysis_file", "")
    row["event_reasons"] = source.get("event_reasons", "")
    return row


def build_render_manifest(
    timeline_rows: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    mode: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    preset = RENDER_PRESETS[mode]
    out = normalize_path(output_dir)
    selected = selected_rows_for_mode(timeline_rows, mode)
    if limit is not None:
        selected = selected[:limit]
    rows: list[dict[str, Any]] = []
    for idx, source in enumerate(selected, start=1):
        case = str(source.get("case_id") or "case")
        frame_id = str(source.get("frame_id") or f"frame_{idx:05d}")
        subdir = "figures" if mode == "figures" else "frames"
        output_png = out / subdir / mode / case / f"{frame_id}.png"
        rows.append(manifest_row(source, preset, output_png, idx))
    return rows


def write_csv_rows(path: Path, headers: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_render_plan_outputs(
    run_root: str | Path,
    *,
    timeline_json: str | Path | None = None,
    output_dir: str | Path | None = None,
    mode: str = "event",
    limit: int | None = None,
) -> dict[str, Any]:
    root = normalize_path(run_root)
    timeline_path = normalize_path(timeline_json) if timeline_json else root / "event_pipeline" / "event_timeline.json"
    out = normalize_path(output_dir) if output_dir else root / "event_pipeline"
    rows = load_timeline(timeline_path)
    manifest = build_render_manifest(rows, out, mode=mode, limit=limit)
    manifest_name = "figure_manifest" if mode == "figures" else f"{mode}_frame_manifest"
    csv_path = out / f"{manifest_name}.csv"
    json_path = out / f"{manifest_name}.json"
    headers = MANIFEST_FIELDS + ["output_png", "analysis_file", "event_reasons"]
    write_csv_rows(csv_path, headers, manifest)
    write_json(
        json_path,
        {
            "generated_at": now_stamp(),
            "run_root": str(root),
            "mode": mode,
            "dry_run": True,
            "render_execute_required": True,
            "preset": RENDER_PRESETS[mode].__dict__,
            "frames": manifest,
        },
    )
    return {"mode": mode, "frame_count": len(manifest), "writes": [str(csv_path), str(json_path)]}


def render_one_with_ovito(row: dict[str, Any], preset: RenderPreset, overwrite: bool = False) -> Path:
    """Render one frame if scriptable OVITO is installed.

    This function is intentionally imported only by execute-mode CLIs, so normal
    tests and dry-runs do not require OVITO.
    """

    output = Path(str(row["output_png"]))
    if output.exists() and not overwrite:
        raise FileExistsError(f"output exists; pass --overwrite: {output}")
    dump = row.get("dump_file")
    if not dump:
        raise ValueError(f"frame has no dump_file: {row.get('frame_id')}")
    from ovito.io import import_file  # type: ignore
    from ovito.modifiers import CommonNeighborAnalysisModifier, DislocationAnalysisModifier  # type: ignore
    from ovito.vis import TachyonRenderer, Viewport  # type: ignore

    pipeline = import_file(str(dump))
    if preset.mode in ("event", "dxa", "figures"):
        pipeline.modifiers.append(CommonNeighborAnalysisModifier())
        dxa = DislocationAnalysisModifier()
        dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
        pipeline.modifiers.append(dxa)
    output.parent.mkdir(parents=True, exist_ok=True)
    viewport = Viewport(type=Viewport.Type.Perspective)
    viewport.zoom_all()
    viewport.render_image(
        filename=str(output),
        size=(preset.width, preset.height),
        renderer=TachyonRenderer(),
    )
    return output
