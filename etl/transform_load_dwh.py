"""
Transform + Load: Staging → DWH.
Бракованные movement_id из quarantine исключаются из факта.
"""

from typing import Optional
from load_staging import get_ch_client


def load_dim_product(batch_id: Optional[str] = None):
    client = get_ch_client()
    batch_filter = f"AND batch_id = '{batch_id}'" if batch_id else ""

    client.execute(f"""
        INSERT INTO dwh.dim_product
        (
            product_sk, product_id, sku, product_name,
            category_id, category_name, unit, is_active,
            valid_from, valid_to, is_current, load_dts
        )
        SELECT
            p.product_id AS product_sk,
            p.product_id,
            p.sku,
            p.name,
            p.category_id,
            c.name AS category_name,
            p.unit,
            p.is_active,
            p.created_at AS valid_from,
            toDateTime('2100-01-01 00:00:00') AS valid_to,
            1 AS is_current,
            now() AS load_dts
        FROM staging.products p
        LEFT JOIN staging.categories c
            ON p.category_id = c.category_id
            AND c.batch_id = p.batch_id
        WHERE 1=1 {batch_filter}
    """)


def load_dim_supplier(batch_id: Optional[str] = None):
    client = get_ch_client()
    batch_filter = f"AND batch_id = '{batch_id}'" if batch_id else ""

    client.execute(f"""
        INSERT INTO dwh.dim_supplier
        (
            supplier_sk, supplier_id, supplier_name, inn, is_active,
            valid_from, valid_to, is_current, load_dts
        )
        SELECT
            supplier_id,
            supplier_id,
            name,
            inn,
            is_active,
            created_at,
            toDateTime('2100-01-01 00:00:00'),
            1,
            now()
        FROM staging.suppliers
        WHERE 1=1 {batch_filter}
    """)


def load_dim_warehouse(batch_id: Optional[str] = None):
    client = get_ch_client()
    batch_filter = f"AND batch_id = '{batch_id}'" if batch_id else ""

    client.execute(f"""
        INSERT INTO dwh.dim_warehouse
        (warehouse_sk, warehouse_id, warehouse_name, address, is_active, load_dts)
        SELECT
            warehouse_id, warehouse_id, name, address, is_active, now()
        FROM staging.warehouses
        WHERE 1=1 {batch_filter}
    """)


def load_dim_zone(batch_id: Optional[str] = None):
    client = get_ch_client()
    batch_filter = f"AND batch_id = '{batch_id}'" if batch_id else ""

    client.execute(f"""
        INSERT INTO dwh.dim_zone
        (zone_sk, zone_id, warehouse_sk, zone_name, zone_type, load_dts)
        SELECT
            zone_id, zone_id, warehouse_id, name, zone_type, now()
        FROM staging.warehouse_zones
        WHERE 1=1 {batch_filter}
    """)


def load_fact_movements(batch_id: Optional[str] = None):
    """
    В факт не попадают movement_id, которые в quarantine по этому batch.
    """
    client = get_ch_client()
    batch_filter = f"AND m.batch_id = '{batch_id}'" if batch_id else ""
    quarantine_filter = ""
    if batch_id:
        quarantine_filter = f"""
            AND m.movement_id NOT IN (
                SELECT toUInt64OrZero(source_pk)
                FROM staging.quarantine
                WHERE batch_id = '{batch_id}'
                  AND source_table = 'stock_movements'
            )
        """

    client.execute(f"""
        INSERT INTO dwh.fact_stock_movements
        (
            movement_dt, date_key,
            product_sk, zone_sk, warehouse_sk, supplier_sk, movement_type_sk,
            quantity, amount,
            source_movement_id, load_dts
        )
        SELECT
            m.movement_dt,
            toYYYYMMDD(m.movement_dt) AS date_key,
            m.product_id AS product_sk,
            m.zone_id AS zone_sk,
            z.warehouse_id AS warehouse_sk,
            ifNull(r.supplier_id, 0) AS supplier_sk,
            mt.movement_type_sk,
            m.quantity,
            0 AS amount,
            m.movement_id,
            now()
        FROM staging.stock_movements m
        LEFT JOIN staging.warehouse_zones z
            ON m.zone_id = z.zone_id AND z.batch_id = m.batch_id
        LEFT JOIN staging.receipts r
            ON m.document_type = 'receipt'
            AND m.document_id = r.receipt_id
            AND r.batch_id = m.batch_id
        LEFT JOIN dwh.dim_movement_type mt
            ON m.movement_type = mt.movement_type_code
        WHERE 1=1
          {batch_filter}
          {quarantine_filter}
    """)


def load_fact_balances(batch_id: Optional[str] = None):
    client = get_ch_client()
    batch_filter = f"AND b.batch_id = '{batch_id}'" if batch_id else ""

    client.execute(f"""
        INSERT INTO dwh.fact_stock_balances_daily
        (balance_date, product_sk, zone_sk, warehouse_sk, quantity, load_dts)
        SELECT
            toDate(b.modified_at) AS balance_date,
            b.product_id,
            b.zone_id,
            z.warehouse_id,
            b.quantity,
            now()
        FROM staging.stock_balances b
        LEFT JOIN staging.warehouse_zones z
            ON b.zone_id = z.zone_id AND z.batch_id = b.batch_id
        WHERE 1=1 {batch_filter}
    """)


def run_transform_load(batch_id: Optional[str] = None):
    print("Transform + Load → DWH...")
    load_dim_warehouse(batch_id)
    load_dim_zone(batch_id)
    load_dim_product(batch_id)
    load_dim_supplier(batch_id)
    load_fact_movements(batch_id)
    load_fact_balances(batch_id)
    print("DWH load done.")
