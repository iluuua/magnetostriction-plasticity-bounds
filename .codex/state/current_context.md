Objective: inspect unloaded long-NVT geometry before any Al/Fe4Al13 loading.
Verified: OVITO app is not installed in /Applications; ovito Python module missing; conda ovito fails with dyld Gui.so.
Verified: warning pair 232-260 is Al-Fe, internal Fe4Al13_slab, not cross-slab interface.
Verified: pair distance over 21 frames min/max/mean = 2.0268/2.3531/2.1170 A; below 2.1 A in 11 frames; below 1.8 A in 0 frames.
Verified: distance is not monotonic collapse; contact type is intermittent short contact.
Current hypothesis: warning is monitor-only for unloaded baseline, but geometry still needs visual/refinement before loading.
Files touched: inspect_warning_pairs.py, warning_pairs_long_nvt.json, warning-pair CSV/PNG/neighborhood, docs/reports.
Blockers: OVITO unavailable, internal warning pair unvisualized, negative pressure/skew remain; no physical validation claimed.
Exact next step: install official OVITO Basic for macOS or run further unloaded refinement; do not prepare/apply 120 MPa.
