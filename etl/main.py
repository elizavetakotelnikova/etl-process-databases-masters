"""
Точка входа ETL.

Примеры:
  python main.py --mode initial
  python main.py --mode incremental
  python main.py --mode cleanup
"""

import argparse
from datetime import datetime

from config import INCREMENTAL_TABLES
from extract import extract_table
from load_staging import (
    load_to_staging,
    make_batch_id,
    update_watermark,
    get_watermark,
    cleanup_staging,
)
from transform_load_dwh import run_transform_load
from quality import run_quality_checks
from journal import log_batch


def run_initial():
    print("=" * 60)
    print("ETL INITIAL LOAD")
    print("=" * 60)

    batch_id = make_batch_id()
    started_at = datetime.utcnow()
    extracted_at = started_at
    print(f"batch_id = {batch_id}")

    rows_read = 0
    rows_loaded = 0
    rows_rejected = 0

    try:
        for table in INCREMENTAL_TABLES:
            print(f"  Extract {table} (full)...")
            rows, max_mod = extract_table(table, full=True)
            print(f"    rows = {len(rows)}")
            rows_read += len(rows)
            n = load_to_staging(table, rows, batch_id, extracted_at)
            rows_loaded += n
            print(f"    staging += {n}")
            if rows:
                update_watermark(table, max_mod, batch_id)

        rows_rejected = run_quality_checks(batch_id)
        run_transform_load(batch_id)

        log_batch(
            batch_id=batch_id,
            mode="initial",
            started_at=started_at,
            status="success",
            rows_read=rows_read,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
        )
        print("Initial load завершён.")
        print(f"  read={rows_read}, loaded_staging={rows_loaded}, rejected={rows_rejected}")
    except Exception as e:
        log_batch(
            batch_id=batch_id,
            mode="initial",
            started_at=started_at,
            status="failed",
            rows_read=rows_read,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
            error_message=str(e),
        )
        raise


def run_incremental():
    print("=" * 60)
    print("ETL INCREMENTAL LOAD")
    print("=" * 60)

    batch_id = make_batch_id()
    started_at = datetime.utcnow()
    extracted_at = started_at
    print(f"batch_id = {batch_id}")

    rows_read = 0
    rows_loaded = 0
    rows_rejected = 0

    try:
        for table in INCREMENTAL_TABLES:
            wm = get_watermark(table)
            print(f"  Extract {table} (modified_at > {wm})...")
            rows, max_mod = extract_table(table, watermark=wm, full=False)
            print(f"    rows = {len(rows)}")
            if not rows:
                continue
            rows_read += len(rows)
            n = load_to_staging(table, rows, batch_id, extracted_at)
            rows_loaded += n
            update_watermark(table, max_mod, batch_id)

        if rows_loaded == 0:
            print("Нет новых или изменённых данных")
            log_batch(
                batch_id=batch_id,
                mode="incremental",
                started_at=started_at,
                status="success",
                rows_read=0,
                rows_loaded=0,
                rows_rejected=0,
            )
            return

        rows_rejected = run_quality_checks(batch_id)
        run_transform_load(batch_id)

        log_batch(
            batch_id=batch_id,
            mode="incremental",
            started_at=started_at,
            status="success",
            rows_read=rows_read,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
        )
        print(f"Incremental load завершён. read={rows_read}, rejected={rows_rejected}")
    except Exception as e:
        log_batch(
            batch_id=batch_id,
            mode="incremental",
            started_at=started_at,
            status="failed",
            rows_read=rows_read,
            rows_loaded=rows_loaded,
            rows_rejected=rows_rejected,
            error_message=str(e),
        )
        raise


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
