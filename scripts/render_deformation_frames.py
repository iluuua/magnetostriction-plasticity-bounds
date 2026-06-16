#!/usr/bin/env python3
"""Create or execute an OVITO render plan for deformation-map frames."""

from __future__ import annotations

from render_event_frames import main


if __name__ == "__main__":
    raise SystemExit(main(["--mode", "deformation"] + __import__("sys").argv[1:]))
