#!/usr/bin/env python3
"""Derive estimated daily mean temperature rows from an existing v5 Tmax/Tmin CSV.

Does not fetch sources or rewrite max/min/rain. Does not connect to the database
unless generate.py is invoked with --insert (never used in a dry run).

  PYTHONPATH=. python scripts/generate_estimated_means.py \
    --means-from-csv daily_estimated_v5.csv \
    --csv-out daily_estimated_mean_v5.csv \
    --sql-out daily_estimated_mean_v5.sql \
    --summary-out summary_mean.json
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_module("rwcwx.estimated.generate", run_name="__main__")
