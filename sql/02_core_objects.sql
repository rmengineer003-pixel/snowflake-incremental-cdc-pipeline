-- Change stream on the landing table and the SCD Type 2 dimension.

CREATE STREAM IF NOT EXISTS {{database}}.CORE.CUSTOMER_CHANGES_STREAM
  ON TABLE {{database}}.RAW.CUSTOMER_CHANGES APPEND_ONLY = TRUE;

CREATE TABLE IF NOT EXISTS {{database}}.CORE.DIM_CUSTOMER (
  customer_sk   NUMBER AUTOINCREMENT,
  customer_id   STRING NOT NULL,
  name          STRING,
  email_domain  STRING,
  segment       STRING,
  state         STRING,
  row_hash      STRING,
  valid_from    TIMESTAMP_NTZ,
  valid_to      TIMESTAMP_NTZ,
  is_current    BOOLEAN
);

-- Latest change per customer from the stream (handles several changes in one batch).
CREATE OR REPLACE VIEW {{database}}.CORE.V_CUSTOMER_CHANGES AS
SELECT customer_id, name, email_domain, segment, state, change_ts,
       MD5(CONCAT_WS('|', COALESCE(name, ''), COALESCE(email_domain, ''),
                          COALESCE(segment, ''), COALESCE(state, ''))) AS row_hash
FROM {{database}}.CORE.CUSTOMER_CHANGES_STREAM
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY change_ts DESC) = 1;
