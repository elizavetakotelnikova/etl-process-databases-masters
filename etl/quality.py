"""
Контроль качества данных + запись в quarantine.
"""

from datetime import datetime, date
from typing import List, Dict, Any, Tuple
import json

from load_staging import get_ch_client


def _payload(row: dict) -> str:
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return str(o)
    return json.dumps(row, ensure_ascii=False, default=default)


def _reject(
    rejects: list,
    batch_id: str,
    table: str,
    pk: str,
    code: str,
    message: str,
    row: dict,
    extracted_at: datetime,
):
    rejects.append({
        "batch_id": batch_id,
        "source_table": table,
        "source_pk": str(pk),
        "reason_code": code,
        "reason_message": message,
        "record_payload": _payload(row),
        "extracted_at": extracted_at or datetime.utcnow(),
    })


def check_stock_movements(
    rows: List[Dict[str, Any]],
    batch_id: str,
    valid_product_ids: set,
    valid_zone_ids: set,
) -> Tuple[List[dict], List[dict]]:
    """
    Возвращает (good_rows, rejects).
    """
    good = []
    rejects = []

    for r in rows:
        extracted_at = r.get("extracted_at") or datetime.utcnow()
        pk = r.get("movement_id")
        bad = False

        if pk is None:
            _reject(rejects, batch_id, "stock_movements", "", "NULL_REQUIRED",
                    "movement_id is null", r, extracted_at)
            bad = True

        if r.get("product_id") is None:
            _reject(rejects, batch_id, "stock_movements", pk, "NULL_REQUIRED",
                    "product_id is null", r, extracted_at)
            bad = True
        elif valid_product_ids and r["product_id"] not in valid_product_ids:
            _reject(rejects, batch_id, "stock_movements", pk, "FK_VIOLATION",
                    f"product_id={r['product_id']} not found", r, extracted_at)
            bad = True

        if r.get("zone_id") is None:
            _reject(rejects, batch_id, "stock_movements", pk, "NULL_REQUIRED",
                    "zone_id is null", r, extracted_at)
            bad = True
        elif valid_zone_ids and r["zone_id"] not in valid_zone_ids:
            _reject(rejects, batch_id, "stock_movements", pk, "FK_VIOLATION",
                    f"zone_id={r['zone_id']} not found", r, extracted_at)
            bad = True

        qty = r.get("quantity")
        if qty is None:
            _reject(rejects, batch_id, "stock_movements", pk, "NULL_REQUIRED",
                    "quantity is null", r, extracted_at)
            bad = True
        elif qty == 0:
            _reject(rejects, batch_id, "stock_movements", pk, "BAD_QUANTITY",
                    "quantity must not be 0", r, extracted_at)
            bad = True

        mdt = r.get("movement_dt")
        if mdt is None:
            _reject(rejects, batch_id, "stock_movements", pk, "BAD_DATE",
                    "movement_dt is null", r, extracted_at)
            bad = True
        elif isinstance(mdt, datetime) and mdt > datetime.utcnow().replace(tzinfo=mdt.tzinfo):
            _reject(rejects, batch_id, "stock_movements", pk, "BAD_DATE",
                    "movement_dt in the future", r, extracted_at)
            bad = True

        mtype = r.get("movement_type")
        if not mtype:
            _reject(rejects, batch_id, "stock_movements", pk, "NULL_REQUIRED",
                    "movement_type is null", r, extracted_at)
            bad = True
        elif mtype not in ("receipt", "shipment", "transfer", "adjustment"):
            _reject(rejects, batch_id, "stock_movements", pk, "BAD_VALUE",
                    f"unknown movement_type={mtype}", r, extracted_at)
            bad = True

        # Логически странно: отгрузка с положительным quantity в нашей модели quantity уже со знаком
        # (приход +, расход -). Если shipment и quantity > 0 — подозрительно.
        if mtype == "shipment" and qty is not None and qty > 0:
            _reject(rejects, batch_id, "stock_movements", pk, "LOGIC_ERROR",
                    "shipment with positive quantity", r, extracted_at)
            bad = True
        if mtype == "receipt" and qty is not None and qty < 0:
            _reject(rejects, batch_id, "stock_movements", pk, "LOGIC_ERROR",
                    "receipt with negative quantity", r, extracted_at)
            bad = True

        if not bad:
            good.append(r)

    return good, rejects


def check_receipt_items(
    rows: List[Dict[str, Any]],
    batch_id: str,
    valid_product_ids: set,
) -> Tuple[List[dict], List[dict]]:
    good, rejects = [], []
    for r in rows:
        extracted_at = r.get("extracted_at") or datetime.utcnow()
        pk = r.get("receipt_item_id")
        bad = False

        if r.get("product_id") is None:
            _reject(rejects, batch_id, "receipt_items", pk, "NULL_REQUIRED",
                    "product_id is null", r, extracted_at)
            bad = True
        elif valid_product_ids and r["product_id"] not in valid_product_ids:
            _reject(rejects, batch_id, "receipt_items", pk, "FK_VIOLATION",
                    f"product_id={r['product_id']} not found", r, extracted_at)
            bad = True

        qty = r.get("quantity")
        if qty is None or qty <= 0:
            _reject(rejects, batch_id, "receipt_items", pk, "BAD_QUANTITY",
                    f"quantity must be > 0, got {qty}", r, extracted_at)
            bad = True

        price = r.get("price")
        if price is not None and price < 0:
            _reject(rejects, batch_id, "receipt_items", pk, "BAD_PRICE",
                    f"price < 0: {price}", r, extracted_at)
            bad = True

        if not bad:
            good.append(r)
    return good, rejects


def save_quarantine(rejects: List[dict]) -> int:
    if not rejects:
        return 0
    client = get_ch_client()
    data = [
        [
            r["batch_id"],
            r["source_table"],
            r["source_pk"],
            r["reason_code"],
            r["reason_message"],
            r["record_payload"],
            r["extracted_at"],
        ]
        for r in rejects
    ]
    client.execute(
        """
        INSERT INTO staging.quarantine
            (batch_id, source_table, source_pk, reason_code, reason_message,
             record_payload, extracted_at)
        VALUES
        """,
        data,
    )
    return len(rejects)


def fetch_staging_rows(table: str, batch_id: str) -> List[dict]:
    client = get_ch_client()
    # clickhouse_driver возвращает кортежи — читаем через WITH names если возможно
    rows = client.execute(
        f"SELECT * FROM staging.{table} WHERE batch_id = %(b)s",
        {"b": batch_id},
        with_column_types=True,
    )
    data, col_types = rows
    cols = [c[0] for c in col_types]
    return [dict(zip(cols, row)) for row in data]


def fetch_id_set(table: str, id_col: str, batch_id: str | None = None) -> set:
    client = get_ch_client()
    if batch_id:
        result = client.execute(
            f"SELECT DISTINCT {id_col} FROM staging.{table} WHERE batch_id = %(b)s",
            {"b": batch_id},
        )
    else:
        # для справочников можно брать все из staging или dwh; берём staging без фильтра batch
        result = client.execute(f"SELECT DISTINCT {id_col} FROM staging.{table}")
    return {r[0] for r in result if r[0] is not None}


def run_quality_checks(batch_id: str) -> int:
    """
    Проверяет ключевые таблицы batch'а.
    Бракованные → quarantine.
    Возвращает число отклонённых записей.
    """
    print("Data Quality checks...")
    product_ids = fetch_id_set("products", "product_id")
    zone_ids = fetch_id_set("warehouse_zones", "zone_id")

    total_rejected = 0

    # stock_movements
    mv_rows = fetch_staging_rows("stock_movements", batch_id)
    _, rejects_mv = check_stock_movements(mv_rows, batch_id, product_ids, zone_ids)
    total_rejected += save_quarantine(rejects_mv)
    print(f"  stock_movements: checked={len(mv_rows)}, rejected={len(rejects_mv)}")

    # receipt_items
    ri_rows = fetch_staging_rows("receipt_items", batch_id)
    _, rejects_ri = check_receipt_items(ri_rows, batch_id, product_ids)
    total_rejected += save_quarantine(rejects_ri)
    print(f"  receipt_items: checked={len(ri_rows)}, rejected={len(rejects_ri)}")

    return total_rejected
