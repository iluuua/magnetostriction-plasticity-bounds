#!/usr/bin/env python3
"""Stage G14: pictures of the cells, for the paper.

The supervisor's first request: "a picture, so a reader sees what was
modelled - here is the matrix, here is the inclusion, here are the axes". Two
renders, each from the actual structure file that was run:

  fig_cell_interface   the ~10^5-atom interface cell, viewed along y, atoms
                       coloured by species, with the inclusion, the matrix,
                       the strain axis and the fixed / free boundaries labelled
  fig_cell_loading     the loaded cell with the pre-existing dislocation pair
                       next to the inclusion: DXA dislocation lines drawn over
                       a faded atom background, with the applied shear shown

Rendered with OVITO's software renderer so it works without a display. Both
figures are emitted twice, EN and RU labels.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ovito.io import import_file
from ovito.modifiers import (DislocationAnalysisModifier, SelectTypeModifier,
                             AssignColorModifier, ComputePropertyModifier)
from ovito.vis import (Viewport, TachyonRenderer, TextLabelOverlay,
                       CoordinateTripodOverlay, ParticlesVis, DislocationVis)
from ovito.data import DataCollection
from ovito.pipeline import ModifierInterface
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

REPO = Path(__file__).resolve().parents[2]
PAPER = REPO / "docs" / "paper"
STRUCT = REPO / "structures"

TXT = {
    "en": dict(matrix="Al matrix (fcc)", incl="Al$_{13}$Fe$_4$ inclusion",
               fixed="fixed bottom layer", free="free surface (vacuum)",
               axis="strain axis, 45° to the interface",
               dip="edge dislocation pair", shear="applied shear τ, ramped 0 → 400 MPa",
               cell="interface cell, 9·10⁴ atoms", load="loaded cell, 9·10⁴ atoms"),
    "ru": dict(matrix="матрица Al (ГЦК)", incl="включение Al$_{13}$Fe$_4$",
               fixed="закреплённый нижний слой", free="свободная поверхность (вакуум)",
               axis="ось деформации, 45° к границе",
               dip="пара краевых дислокаций", shear="приложенный сдвиг τ, 0 → 400 МПа",
               cell="ячейка границы, 9·10⁴ атомов", load="нагружаемая ячейка, 9·10⁴ атомов"),
}
# matplotlib-style $..$ is not understood by OVITO overlays: use plain unicode
for L in TXT.values():
    L["incl"] = L["incl"].replace("$_{13}$", "₁₃").replace("$_4$", "₄")


def label(vp: Viewport, text: str, x: float, y: float, size=0.05, color=(0.1, 0.1, 0.1)):
    ov = TextLabelOverlay(text=text, offset_x=x, offset_y=y, font_size=size,
                          text_color=color, alignment=Qt.AlignLeft | Qt.AlignBottom)
    vp.overlays.append(ov)
    return ov


def render_interface(lang: str) -> Path:
    t = TXT[lang]
    src = next((STRUCT / "stageG4_tilted_solute" / "G4_tilted_eps0000_u100k").glob("*.start.data"))
    pipe = import_file(str(src), atom_style="atomic")
    # species colours: Al pale grey, Fe deep red so the intermetallic stands out
    pt = pipe.source.data.particles_.particle_types_
    pt.type_by_id_(1).color = (0.78, 0.80, 0.84)
    pt.type_by_id_(1).radius = 0.9
    pt.type_by_id_(2).color = (0.75, 0.12, 0.10)
    pt.type_by_id_(2).radius = 1.1
    pipe.add_to_scene()

    vp = Viewport(type=Viewport.Type.Front)      # looks along -y: the x-z plane
    vp.zoom_all()
    vp.fov = vp.fov * 0.92
    label(vp, t["cell"], 0.02, 0.955, 0.042)
    label(vp, t["matrix"], 0.66, 0.55, 0.042)
    label(vp, t["incl"], 0.66, 0.10, 0.042, (0.6, 0.08, 0.06))
    label(vp, t["fixed"], 0.02, 0.02, 0.036, (0.3, 0.3, 0.3))
    label(vp, t["free"], 0.02, 0.90, 0.034, (0.3, 0.3, 0.3))
    label(vp, t["axis"], 0.66, 0.30, 0.036, (0.05, 0.25, 0.55))
    tripod = CoordinateTripodOverlay(size=0.11, offset_x=0.86, offset_y=0.04)
    vp.overlays.append(tripod)
    out = PAPER / f"fig_cell_interface_{lang}.png"
    vp.render_image(size=(1600, 1150), filename=str(out), background=(1, 1, 1),
                    renderer=TachyonRenderer(antialiasing=True, ambient_occlusion=True))
    pipe.remove_from_scene()
    return out


def render_loading(lang: str) -> Path:
    t = TXT[lang]
    cand = sorted((STRUCT / "stageG4_tilted_solute" / "G4_tilted_eps0000_dipu100k").glob("*.start.data"))
    if not cand:
        print("no G1 structure found; skipping the loading figure")
        return None
    src = cand[0]
    pipe = import_file(str(src), atom_style="atomic")
    pt = pipe.source.data.particles_.particle_types_
    pt.type_by_id_(1).color = (0.86, 0.87, 0.90)
    pt.type_by_id_(1).radius = 0.6
    pt.type_by_id_(2).color = (0.75, 0.12, 0.10)
    pt.type_by_id_(2).radius = 1.0
    dxa = DislocationAnalysisModifier()
    dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
    pipe.modifiers.append(dxa)
    data = pipe.compute()
    # fade the perfect-fcc matrix so the defects and the inclusion carry the image
    pipe.modifiers.append(SelectTypeModifier(property="Structure Type",
                                             types={DislocationAnalysisModifier.Lattice.FCC}))
    pipe.modifiers.append(AssignColorModifier(color=(0.93, 0.93, 0.95)))
    # AssignColor creates a Color property, after which the type colours no
    # longer apply; give the inclusion its red back explicitly
    pipe.modifiers.append(SelectTypeModifier(property="Particle Type", types={2}))
    pipe.modifiers.append(AssignColorModifier(color=(0.75, 0.12, 0.10)))
    out_data = pipe.compute()
    vis = out_data.dislocations.vis
    vis.line_width = 3.0
    vis.shading = DislocationVis.Shading.Normal
    # the DXA defect mesh (interface surfaces, free surface) only clutters a
    # picture whose point is the pair and the inclusion
    if out_data.surfaces:
        for s in out_data.surfaces.values():
            s.vis.enabled = False
    pipe.add_to_scene()

    vp = Viewport(type=Viewport.Type.Front)
    vp.zoom_all()
    label(vp, t["load"], 0.02, 0.955, 0.042)
    label(vp, t["dip"], 0.60, 0.50, 0.040, (0.05, 0.35, 0.10))
    label(vp, t["incl"], 0.30, 0.10, 0.040, (0.6, 0.08, 0.06))
    label(vp, t["shear"], 0.02, 0.90, 0.036, (0.05, 0.25, 0.55))
    label(vp, t["fixed"], 0.02, 0.02, 0.036, (0.3, 0.3, 0.3))
    vp.overlays.append(CoordinateTripodOverlay(size=0.11, offset_x=0.86, offset_y=0.04))
    out = PAPER / f"fig_cell_loading_{lang}.png"
    vp.render_image(size=(1600, 1150), filename=str(out), background=(1, 1, 1),
                    renderer=TachyonRenderer(antialiasing=True, ambient_occlusion=True))
    n_seg = len(data.dislocations.segments)
    print("loading cell: %d atoms, DXA found %d dislocation segments" % (data.particles.count, n_seg))
    pipe.remove_from_scene()
    return out


def main() -> int:
    for lang in ("en", "ru"):
        print("interface:", render_interface(lang))
        print("loading:  ", render_loading(lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
