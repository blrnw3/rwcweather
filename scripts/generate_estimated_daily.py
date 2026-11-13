#!/usr/bin/env python3
"""CLI wrapper: python scripts/generate_estimated_daily.py --cache-dir ... --csv-out ..."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_module("rwcwx.estimated.generate", run_name="__main__")
