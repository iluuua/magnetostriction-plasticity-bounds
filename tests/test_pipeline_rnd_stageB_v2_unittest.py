"""Unittest discovery wrapper for the pytest-style Stage B planner tests."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parent
    / "science_optimizer"
    / "test_pipeline_rnd_stageB_v2.py"
)

_spec = importlib.util.spec_from_file_location(
    "stageb_planner_pytest_style_tests",
    MODULE_PATH,
)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)


def load_tests(loader, tests, pattern):  # noqa: D401 - unittest discovery hook
    """Delegate discovery to the planner test module's ``load_tests`` hook."""
    return _module.load_tests(loader, tests, pattern)


if __name__ == "__main__":
    unittest.main()
