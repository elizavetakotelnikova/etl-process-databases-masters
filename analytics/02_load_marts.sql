-- наполнение витрин из DWH (перезапуск идемпотентен при TRUNCATE, а также повторной вставке)

-- очистка при полной пересборке витрин
TRUNCATE TABLE IF EXISTS marts.mart_product_turnover;
TRUNCATE TABLE IF EXISTS marts.mart_stock_balances;

-- оборот
INSERT INTO marts.mart_product_turnover
SELECT
    toDate(f.movement_dt)                     AS turnover_date,
    f.warehouse_sk,
    ifNull(w.warehouse_name, '')              AS warehouse_name,
    f.product_sk,
    ifNull(p.product_name, '')                AS product_name,
    ifNull(p.category_name, '')               AS category_name,

    sumIf(f.quantity, f.quantity > 0)         AS qty_in,
    sumIf(abs(f.quantity), f.quantity < 0)    AS qty_out,
    sum(f.quantity)                           AS qty_net,
    sum(abs(f.quantity))                      AS turnover_qty,
    count()                                   AS ops_count,
    sumIf(f.amount, f.quantity > 0)           AS amount_in,
    sumIf(abs(f.amount), f.quantity < 0)      AS amount_out,
    if(sum(abs(f.quantity)) = 0,
    toDecimal64(0, 2),
    toDecimal64(
       sum(abs(toFloat64(f.amount))) / sum(abs(toFloat64(f.quantity))),
       2
      )
    )                                         AS avg_price,

    now()                                     AS load_dts
FROM dwh.fact_stock_movements f
LEFT JOIN dwh.dim_warehouse w ON f.warehouse_sk = w.warehouse_sk
LEFT JOIN dwh.dim_product p
    ON f.product_sk = p.product_sk AND p.is_current = 1
GROUP BY
    turnover_date,
    f.warehouse_sk,
    warehouse_name,
    f.product_sk,
    product_name,
    category_name;


-- остатки
INSERT INTO marts.mart_stock_balances
SELECT
    b.balance_date,
    b.warehouse_sk,
    ifNull(w.warehouse_name, '')              AS warehouse_name,
    b.product_sk,
    ifNull(p.product_name, '')                AS product_name,
    ifNull(p.category_name, '')               AS category_name,

    b.quantity,
    ifNull(t.qty_in, 0)                       AS qty_in_day,
    ifNull(t.qty_out, 0)                      AS qty_out_day,
    ifNull(t.qty_net, 0)                      AS qty_change,
    if(b.quantity <= 0, 1, 0)                 AS is_deficit,

    now()                                     AS load_dts
FROM dwh.fact_stock_balances_daily b
LEFT JOIN dwh.dim_warehouse w ON b.warehouse_sk = w.warehouse_sk
LEFT JOIN dwh.dim_product p
    ON b.product_sk = p.product_sk AND p.is_current = 1
LEFT JOIN
(
    SELECT
        toDate(movement_dt) AS d,
        warehouse_sk,
        product_sk,
        sumIf(quantity, quantity > 0)       AS qty_in,
        sumIf(abs(quantity), quantity < 0)  AS qty_out,
        sum(quantity)                       AS qty_net
    FROM dwh.fact_stock_movements
    GROUP BY d, warehouse_sk, product_sk
) t
    ON b.balance_date = t.d
   AND b.warehouse_sk = t.warehouse_sk
   AND b.product_sk = t.product_sk;
