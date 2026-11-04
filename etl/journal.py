"""
Журнал загрузок ETL (п. 10 задания).
Одна запись на запуск — пишется только после завершения.
"""

from datetime import datetime
from typing import Optional

from load_staging import get_ch_client


def log_batch(
    batch_id: str,
    mode: str,
    started_at: datetime,
    status: str,
    rows_read: int = 0,
    rows_loaded: int = 0,
    rows_rejected: int = 0,
    error_message: Optional[str] = None,
) -> None:
    """
    Финальная регистрация запуска ETL.
    started_at передаётся из main (зафиксирован в начале прогона).
    """
    client = get_ch_client()
    client.execute(
        """
        INSERT INTO staging.etl_batch_log
            (batch_id, mode, started_at, finished_at, status,
             rows_read, rows_loaded, rows_rejected, error_message)
        VALUES
        """,
        [[
            batch_id,
            mode,
            started_at,
            datetime.utcnow(),
            status,
            rows_read,
            rows_loaded,
            rows_rejected,
            error_message,
        ]],
    )
