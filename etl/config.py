"""
Конфигурация ETL: PostgreSQL (источник) → Staging → DWH (ClickHouse)
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()


@dataclass
class ETLConfig:
    # PostgreSQL (OLTP)
    pg_host: str = os.getenv("DB_HOST", "localhost")
    pg_port: int = int(os.getenv("DB_PORT", "5433"))
    pg_db: str = os.getenv("DB_NAME", "warehouse")
    pg_user: str = os.getenv("DB_USER", "postgres")
    pg_password: str = os.getenv("DB_PASSWORD", "postgres")

    # ClickHouse
    ch_host: str = os.getenv("CH_HOST", "localhost")
    ch_port: int = int(os.getenv("CH_PORT", "9000"))
    ch_http_port: int = int(os.getenv("CH_HTTP_PORT", "8123"))
    ch_user: str = os.getenv("CH_USER", "default")
    ch_password: str = os.getenv("CH_PASSWORD", "")
    ch_db_staging: str = "staging"
    ch_db_dwh: str = "dwh"

    # ETL
    source_id: str = "postgres_warehouse"
    batch_size: int = 50_000

    # Срок хранения staging (дней). Старше — удаляем.
    staging_retention_days: int = 14


config = ETLConfig()

# Таблицы, которые участвуют в инкрементальной загрузке
INCREMENTAL_TABLES = [
    "categories",
    "products",
    "suppliers",
    "warehouses",
    "warehouse_zones",
    "receipts",
    "receipt_items",
    "shipments",
    "shipment_items",
    "stock_movements",
    "stock_balances",
]
