"""
Extract: чтение из PostgreSQL.
"""

from datetime import datetime
from typing import Optional, List, Any, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from config import config, INCREMENTAL_TABLES


def get_pg_conn():
    return psycopg2.connect(
        host=config.pg_host,
        port=config.pg_port,
        dbname=config.pg_db,
        user=config.pg_user,
        password=config.pg_password,
    )


def extract_table(
    table: str,
    watermark: Optional[datetime] = None,
    full: bool = False,
) -> Tuple[List[dict], datetime]:
    """
    Читает таблицу из PostgreSQL.
    full=True  → вся таблица (initial load)
    иначе      → только modified_at > watermark (incremental)
    Возвращает (строки, max_modified_at в выборке).
    """
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if full or watermark is None:
                cur.execute(f"SELECT * FROM {table}")
            else:
                cur.execute(
                    f"SELECT * FROM {table} WHERE modified_at > %s ORDER BY modified_at",
                    (watermark,),
                )
            rows = [dict(r) for r in cur.fetchall()]

    max_mod = watermark or datetime(1970, 1, 1)
    for r in rows:
        m = r.get("modified_at")
        if m and m > max_mod:
            max_mod = m

    return rows, max_mod
