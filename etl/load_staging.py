"""
Load в Staging (ClickHouse) + технические атрибуты.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid

try:
    from clickhouse_driver import Client
except ImportError:
    Client = None

from config import config


def get_ch_client() -> "Client":
    if Client is None:
        raise RuntimeError("Установите: pip install clickhouse-driver")
    return Client(
        host=config.ch_host,
        port=config.ch_port,
        user=config.ch_user,
        password=config.ch_password,
    )


def make_batch_id() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]


def load_to_staging(
    table: str,
    rows: List[Dict[str, Any]],
    batch_id: str,
    extracted_at: datetime,
) -> int:
    """
    Пишет строки в staging.<table>, добавляя технические поля.
    """
    if not rows:
        return 0

    client = get_ch_client()
    source_id = config.source_id

    # Нормализуем строки + тех. атрибуты
    prepared = []
    for r in rows:
        item = dict(r)
        # Boolean → UInt8
        for k, v in list(item.items()):
            if isinstance(v, bool):
                item[k] = 1 if v else 0
        item["source_id"] = source_id
        item["extracted_at"] = extracted_at
        item["batch_id"] = batch_id
        item["source_modified_at"] = r.get("modified_at") or extracted_at
        prepared.append(item)

    cols = list(prepared[0].keys())
    data = [[row[c] for c in cols] for row in prepared]

    client.execute(
        f"INSERT INTO staging.{table} ({', '.join(cols)}) VALUES",
        data,
    )
    return len(prepared)


def update_watermark(table: str, watermark: datetime, batch_id: str):
    client = get_ch_client()
    if getattr(watermark, "tzinfo", None) is not None:
        watermark = watermark.replace(tzinfo=None)
    safe_wm = watermark + timedelta(milliseconds=1)
    client.execute(
        """
        INSERT INTO staging.etl_watermarks
            (source_table, watermark_value, batch_id, updated_at)
        VALUES
        """,
        [[table, safe_wm, batch_id, datetime.utcnow()]],
    )


def get_watermark(table: str) -> datetime | None:
    client = get_ch_client()
    result = client.execute(
        """
        SELECT watermark_value
        FROM staging.etl_watermarks
        FINAL
        WHERE source_table = %(t)s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        {"t": table},
    )
    if result:
        return result[0][0]
    return None


def cleanup_staging(retention_days: int | None = None):
    """Удаляет старые батчи из staging (по extracted_at)."""
    days = retention_days or config.staging_retention_days
    client = get_ch_client()
    tables = [
        "categories", "products", "suppliers", "warehouses", "warehouse_zones",
        "receipts", "receipt_items", "shipments", "shipment_items",
        "stock_movements", "stock_balances",
    ]
    for t in tables:
        client.execute(
            f"""
            ALTER TABLE staging.{t}
            DELETE WHERE extracted_at < now() - INTERVAL {days} DAY
            """
        )
    print(f"Staging cleanup: удалены данные старше {days} дней")
