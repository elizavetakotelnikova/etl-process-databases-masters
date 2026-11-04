"""
Точка входа ETL.

Примеры:
  python -m generator.etl.main --mode initial
  python -m generator.etl.main --mode incremental
  python -m generator.etl.main --mode cleanup
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config import config, INCREMENTAL_TABLES
from extract import extract_table
from load_staging import (
    load_to_staging,
    make_batch_id,
    update_watermark,
    get_watermark,
    cleanup_staging,
)
from transform_load_dwh import run_transform_load


def run_initial():
    print("=" * 60)
    print("ETL INITIAL LOAD")
    print("=" * 60)

    batch_id = make_batch_id()
    extracted_at = datetime.utcnow()
    print(f"batch_id = {batch_id}")

    for table in INCREMENTAL_TABLES:
        print(f"  Extract {table} (full)...")
        rows, max_mod = extract_table(table, full=True)
        print(f"    rows = {len(rows)}")
        n = load_to_staging(table, rows, batch_id, extracted_at)
        print(f"    staging += {n}")
        if rows:
            update_watermark(table, max_mod, batch_id)

    run_transform_load(batch_id)
    print("Initial load завершён.")


def run_incremental():
    print("=" * 60)
    print("ETL INCREMENTAL LOAD")
    print("=" * 60)

    batch_id = make_batch_id()
    extracted_at = datetime.utcnow()
    print(f"batch_id = {batch_id}")

    total_rows = 0
    for table in INCREMENTAL_TABLES:
        wm = get_watermark(table)
        print(f"  Extract {table} (modified_at > {wm})...")
        rows, max_mod = extract_table(table, watermark=wm, full=False)
        print(f"    rows = {len(rows)}")
        if not rows:
            continue
        n = load_to_staging(table, rows, batch_id, extracted_at)
        total_rows += n
        update_watermark(table, max_mod, batch_id)

    if total_rows == 0:
        print("Нет новых/изменённых данных.")
        return

    run_transform_load(batch_id)
    print(f"Incremental load завершён. Строк: {total_rows}")


def main():
    parser = argparse.ArgumentParser(description="ETL PostgreSQL → ClickHouse")
    parser.add_argument(
        "--mode",
        choices=["initial", "incremental", "cleanup"],
        required=True,
    )
    args = parser.parse_args()

    if args.mode == "initial":
        run_initial()
    elif args.mode == "incremental":
        run_incremental()
    else:
        cleanup_staging()


if __name__ == "__main__":
    main()
