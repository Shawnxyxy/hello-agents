#!/usr/bin/env python3
"""运行 Harness Eval Suite。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.eval_runner import format_report, run_safety_eval


def main() -> int:
    report = run_safety_eval()
    print(format_report(report))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
