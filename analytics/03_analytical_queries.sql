-- аналитические запросы

-- топ-20 товаров по обороту (движению)
SELECT
    product_sk,
    product_name,
    category_name,
    sum(turnover_qty) AS total_turnover,
    sum(ops_count)    AS total_ops
FROM marts.mart_product_turnover
GROUP BY product_sk, product_name, category_name
ORDER BY total_turnover DESC
LIMIT 20;


-- товары с минимальным оборотом, при этом движения были
SELECT
    product_sk,
    product_name,
    sum(turnover_qty) AS total_turnover,
    sum(ops_count)    AS total_ops
FROM marts.mart_product_turnover
GROUP BY product_sk, product_name
HAVING total_turnover > 0
ORDER BY total_turnover ASC
LIMIT 20;


-- динамика поступлений и отгрузок по месяцам
SELECT
    toStartOfMonth(turnover_date) AS month,
    sum(qty_in)  AS total_in,
    sum(qty_out) AS total_out,
    sum(ops_count) AS ops
FROM marts.mart_product_turnover
GROUP BY month
ORDER BY month;


-- сезонность: оборот по месяцам и дням недели
SELECT
    d.month,
    d.month_name,
    d.day_of_week,
    d.day_name,
    sum(abs(f.quantity)) AS turnover_qty,
    count() AS ops
FROM dwh.fact_stock_movements f
JOIN dwh.dim_date d ON f.date_key = d.date_key
GROUP BY d.month, d.month_name, d.day_of_week, d.day_name
ORDER BY d.month, d.day_of_week;


-- средний объём операции по типу движения
SELECT
    mt.movement_type_name,
    count()                AS ops,
    avg(abs(f.quantity))   AS avg_qty,
    median(abs(f.quantity)) AS median_qty
FROM dwh.fact_stock_movements f
JOIN dwh.dim_movement_type mt ON f.movement_type_sk = mt.movement_type_sk
GROUP BY mt.movement_type_name
ORDER BY ops DESC;


-- изменение «стоимости» по товарам, топ по месяцам
SELECT
    product_sk,
    toStartOfMonth(movement_dt) AS month,
    sum(abs(amount)) AS amount_abs
FROM dwh.fact_stock_movements
WHERE amount != 0
GROUP BY product_sk, month
ORDER BY product_sk, month;


-- объём поставок и число операций
SELECT
    s.supplier_sk,
    s.supplier_name,
    count()              AS receipt_ops,
    sum(f.quantity)      AS qty_supplied,
    sum(f.amount)        AS amount_supplied
FROM dwh.fact_stock_movements f
JOIN dwh.dim_supplier s
    ON f.supplier_sk = s.supplier_sk AND s.is_current = 1
JOIN dwh.dim_movement_type mt ON f.movement_type_sk = mt.movement_type_sk
WHERE mt.movement_type_code = 'receipt'
  AND f.supplier_sk != 0
GROUP BY s.supplier_sk, s.supplier_name
ORDER BY qty_supplied DESC
LIMIT 30;


-- текущие остатки (на последнюю дату в витрине)
SELECT
    product_sk,
    product_name,
    warehouse_name,
    quantity,
    is_deficit
FROM marts.mart_stock_balances
WHERE balance_date = (SELECT max(balance_date) FROM marts.mart_stock_balances)
ORDER BY quantity ASC
LIMIT 50;


-- топ-5 товаров, у которых чаще всего был остаток < 0
SELECT
    balance_date,
    product_sk,
    product_name,
    warehouse_name,
    quantity,
    qty_change
FROM marts.mart_stock_balances
WHERE product_sk IN (
    SELECT product_sk
    FROM marts.mart_stock_balances
    WHERE is_deficit = 1
    GROUP BY product_sk
    ORDER BY count() DESC
    LIMIT 5
)
ORDER BY product_sk, balance_date;


-- потенциальный дефицит: остаток ≤ 0 или очень низкий при большом расходе
SELECT
    b.product_sk,
    b.product_name,
    b.warehouse_name,
    b.quantity AS current_qty,
    t.qty_out_30d,
    if(t.qty_out_30d > 0, b.quantity / t.qty_out_30d * 30, NULL) AS days_of_stock
FROM marts.mart_stock_balances b
LEFT JOIN
(
    SELECT
        product_sk,
        warehouse_sk,
        sum(qty_out) AS qty_out_30d
    FROM marts.mart_product_turnover
    WHERE turnover_date >= today() - 30
    GROUP BY product_sk, warehouse_sk
) t ON b.product_sk = t.product_sk AND b.warehouse_sk = t.warehouse_sk
WHERE b.balance_date = (SELECT max(balance_date) FROM marts.mart_stock_balances)
  AND (b.quantity <= 0 OR (t.qty_out_30d > 0 AND b.quantity / t.qty_out_30d * 30 < 7))
ORDER BY current_qty ASC
LIMIT 50;


-- показатели за разные периоды: текущий месяц vs предыдущий
SELECT
    product_sk,
    product_name,
    month,
    month_turnover,
    lagInFrame(month_turnover) OVER (
        PARTITION BY product_sk ORDER BY month
    ) AS prev_month_turnover,
    month_turnover - lagInFrame(month_turnover) OVER (
        PARTITION BY product_sk ORDER BY month
    ) AS diff_vs_prev
FROM (
    SELECT
        product_sk,
        any(product_name) AS product_name,
        toStartOfMonth(turnover_date) AS month,
        sum(turnover_qty) AS month_turnover
    FROM marts.mart_product_turnover
    GROUP BY product_sk, month
)
ORDER BY product_sk, month
LIMIT 100;


-- рейтинг товаров внутри категории
SELECT
    category_name,
    product_name,
    total_turnover,
    rank() OVER (PARTITION BY category_name ORDER BY total_turnover DESC) AS rank_in_category,
    sum(total_turnover) OVER (PARTITION BY category_name) AS category_turnover,
    total_turnover / sum(total_turnover) OVER (PARTITION BY category_name) AS share_in_category
FROM (
    SELECT
        category_name,
        product_name,
        sum(turnover_qty) AS total_turnover
    FROM marts.mart_product_turnover
    GROUP BY category_name, product_name
)
ORDER BY category_name, rank_in_category
LIMIT 100;


-- скользящее среднее оборота по дням
SELECT
    turnover_date,
    daily_turnover,
    avg(daily_turnover) OVER (
        ORDER BY turnover_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS seven_days_average
FROM (
    SELECT
        turnover_date,
        sum(turnover_qty) AS daily_turnover
    FROM marts.mart_product_turnover
    GROUP BY turnover_date
)
ORDER BY turnover_date;
