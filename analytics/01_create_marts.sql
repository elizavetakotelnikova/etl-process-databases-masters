-- аналитические витрины

CREATE DATABASE IF NOT EXISTS marts;

-- витрина 1 - оборот товаров
-- зерно: день × склад × товар

CREATE TABLE IF NOT EXISTS marts.mart_product_turnover
(
    turnover_date       Date,
    warehouse_sk        UInt16,
    warehouse_name      String,
    product_sk          UInt32,
    product_name        String,
    category_name       String,

    qty_in              Decimal(15, 3),
    qty_out             Decimal(15, 3),
    qty_net             Decimal(15, 3),
    turnover_qty        Decimal(15, 3),
    ops_count           UInt64,
    amount_in           Decimal(15, 2),
    amount_out          Decimal(15, 2),
    avg_price           Decimal(15, 2),

    load_dts            DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(turnover_date)
ORDER BY (turnover_date, warehouse_sk, product_sk);

-- витрина 2 - складские остатки
-- зерно: день × склад × товар

CREATE TABLE IF NOT EXISTS marts.mart_stock_balances
(
    balance_date        Date,
    warehouse_sk        UInt16,
    warehouse_name      String,
    product_sk          UInt32,
    product_name        String,
    category_name       String,

    quantity            Decimal(15, 3),
    qty_in_day          Decimal(15, 3),
    qty_out_day         Decimal(15, 3),
    qty_change          Decimal(15, 3),
    is_deficit          UInt8,

    load_dts            DateTime
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(balance_date)
ORDER BY (balance_date, warehouse_sk, product_sk);
