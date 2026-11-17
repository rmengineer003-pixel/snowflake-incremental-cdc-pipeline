-- SCD Type 2 apply. Portable SQL: the same two statements run in Snowflake (inside the task)
-- and in DuckDB (unit tests). Target and source names are templated.

-- 1) Expire current rows whose tracked attributes changed.
UPDATE {{target}} d
SET is_current = FALSE, valid_to = c.change_ts
FROM {{changes}} c
WHERE d.customer_id = c.customer_id AND d.is_current AND d.row_hash <> c.row_hash;

-- 2) Insert a new current version for new customers and for the rows expired above.
INSERT INTO {{target}} (customer_id, name, email_domain, segment, state, row_hash, valid_from, valid_to, is_current)
SELECT c.customer_id, c.name, c.email_domain, c.segment, c.state, c.row_hash, c.change_ts, NULL, TRUE
FROM {{changes}} c
LEFT JOIN {{target}} d ON d.customer_id = c.customer_id AND d.is_current
WHERE d.customer_id IS NULL;
