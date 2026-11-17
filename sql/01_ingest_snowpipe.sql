-- Landing table + Snowpipe auto-ingest from cloud storage.
-- The storage integration is created once by an admin; no keys are stored here.

CREATE FILE FORMAT IF NOT EXISTS {{database}}.RAW.FF_JSON TYPE = JSON STRIP_OUTER_ARRAY = TRUE;

CREATE STAGE IF NOT EXISTS {{database}}.RAW.CUSTOMER_STAGE
  URL = '{{stage_url}}'
  STORAGE_INTEGRATION = {{storage_integration}}
  FILE_FORMAT = {{database}}.RAW.FF_JSON;

CREATE TABLE IF NOT EXISTS {{database}}.RAW.CUSTOMER_CHANGES (
  customer_id   STRING,
  name          STRING,
  email_domain  STRING,
  segment       STRING,
  state         STRING,
  change_ts     TIMESTAMP_NTZ,
  _file_name    STRING,
  _loaded_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE PIPE IF NOT EXISTS {{database}}.RAW.CUSTOMER_PIPE AUTO_INGEST = TRUE AS
  COPY INTO {{database}}.RAW.CUSTOMER_CHANGES (customer_id, name, email_domain, segment, state, change_ts, _file_name)
  FROM (
    SELECT $1:customer_id::STRING, $1:name::STRING, $1:email_domain::STRING, $1:segment::STRING,
           $1:state::STRING, $1:change_ts::TIMESTAMP_NTZ, METADATA$FILENAME
    FROM @{{database}}.RAW.CUSTOMER_STAGE
  )
  ON_ERROR = 'SKIP_FILE';
