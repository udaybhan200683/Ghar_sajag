"""Run the registered GS-178 production-code vertical against local PostgreSQL."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if os.environ.get("GS179_TEST_POSTGRES_ONLY") != "1":
        print("GS179 PostgreSQL E2E requires GS179_TEST_POSTGRES_ONLY=1", file=sys.stderr)
        return 2
    if not os.environ.get("GS179_TEST_POSTGRES_DSN"):
        print("GS179 PostgreSQL E2E requires a local GS179_TEST_POSTGRES_DSN", file=sys.stderr)
        return 2
    suite = unittest.TestSuite()
    for pattern in ("test_gs178*.py", "test_gs179*.py"):
        suite.addTests(unittest.defaultTestLoader.discover(
            str(ROOT / "tests" / "integration"), pattern=pattern,
            top_level_dir=str(ROOT / "tests" / "integration")))
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print(f"GS179 POSTGRES E2E PASS tests={count} physical=NOT_RUN")
        return 0
    print(f"GS179 POSTGRES E2E FAIL tests={count} failures={len(result.failures)} errors={len(result.errors)} physical=NOT_RUN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
