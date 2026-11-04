# ETL: PostgreSQL → Staging → ClickHouse DWH

## Режимы

| Режим | Команда | Что делает |
|-------|---------|------------|
| Initial Load | `python -m generator.etl.main --mode initial` | Полная загрузка всей истории |
| Incremental | `python -m generator.etl.main --mode incremental` | Только новые/изменённые по `modified_at` |
| Cleanup | `python -m generator.etl.main --mode cleanup` | Удаление старых данных из staging |

## Механизм инкремента

**modified_at + watermark (high-water mark)**

1. В `staging.etl_watermarks` хранится последний успешно обработанный `modified_at` по каждой таблице.
2. При incremental читаем из PostgreSQL: `WHERE modified_at > watermark`.
3. После успешной загрузки watermark обновляется.

Полное перечитывание таблиц при инкременте **не выполняется**.

## Staging

- Назначение: буфер, аудит, повторная обработка, data quality.
- Тех. атрибуты: `source_id`, `extracted_at`, `batch_id`, `source_modified_at`.
- Срок хранения: 14 дней (настраивается в `config.py`).
- Очистка: `ALTER TABLE ... DELETE WHERE extracted_at < now() - INTERVAL N DAY`.

## Зависимости

```bash
pip install psycopg2-binary clickhouse-driver
```
