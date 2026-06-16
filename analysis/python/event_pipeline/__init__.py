"""Event detection, visualization, and traceability helpers.

The package is intentionally post-processing oriented. It reads existing run
artifacts and writes small plans/manifests, but it does not launch MD by
itself.
"""

from .schema import EVENT_CLASSES, MANIFEST_FIELDS, EventThresholds
from .timeline import build_event_timeline, classify_event, write_event_timeline_outputs
from .window import plan_event_window, write_event_window_outputs

__all__ = [
    "EVENT_CLASSES",
    "MANIFEST_FIELDS",
    "EventThresholds",
    "build_event_timeline",
    "classify_event",
    "write_event_timeline_outputs",
    "plan_event_window",
    "write_event_window_outputs",
]
