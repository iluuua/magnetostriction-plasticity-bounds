"""pytest path setup so `science_optimizer` and the planner CLI import cleanly.

Only used when pytest is available; the test modules also set sys.path
themselves so they run standalone via `python <test_file>.py` with no pytest.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("analysis/python", "scripts"):
    _p = str(REPO_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
