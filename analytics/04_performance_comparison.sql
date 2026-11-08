-- исследование производительности
-- одинаковые по смыслу запросы: PostgreSQL (OLTP) vs ClickHouse (DWH/marts)

-- Clickhouse запросы
-- оборот по товарам
SELECT
    product_sk,
    sum(abs(quantity)) AS turnover,
    count() AS ops
FROM dwh.fact_stock_movements
GROUP BY product_sk
ORDER BY turnover DESC
LIMIT 50;

-- оборот по дням
SELECT
    toDate(movement_dt) AS d,
    sum(abs(quantity)) AS turnover,
    count() AS ops
FROM dwh.fact_stock_movements
GROUP BY d
ORDER BY d;

-- топ складов по отгрузкам
SELECT
    warehouse_sk,
    sumIf(abs(quantity), quantity < 0) AS qty_out,
    count() AS ops
FROM dwh.fact_stock_movements
GROUP BY warehouse_sk
ORDER BY qty_out DESC;


-- PostgreSQL запросы
SELECT product_id,
sum(abs(quantity)) AS turnover,
count(*) AS ops
FROM stock_movements
GROUP BY product_id
ORDER BY turnover DESC
LIMIT 50;

SELECT movement_dt::date AS d,
sum(abs(quantity)) AS turnover,
count(*) AS ops
FROM stock_movements
GROUP BY d
ORDER BY d;

SELECT z.warehouse_id,
sum(CASE WHEN m.quantity < 0 THEN abs(m.quantity) ELSE 0 END) AS qty_out,
count(*) AS ops
FROM stock_movements m
JOIN warehouse_zones z ON m.zone_id = z.zone_id
GROUP BY z.warehouse_id
ORDER BY qty_out DESC;
