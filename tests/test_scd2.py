"""Run the exact SCD2 statements from sql/scd2_apply.sql on DuckDB."""
import duckdb
import pytest

from sf_cdc.render import MissingVariable, deployment_sql, render, scd2_sql

DDL = """
CREATE TABLE dim_customer (customer_sk INTEGER DEFAULT nextval('sk'), customer_id VARCHAR NOT NULL, name VARCHAR,
  email_domain VARCHAR, segment VARCHAR, state VARCHAR, row_hash VARCHAR, valid_from TIMESTAMP,
  valid_to TIMESTAMP, is_current BOOLEAN);
CREATE TABLE raw_changes (customer_id VARCHAR, name VARCHAR, email_domain VARCHAR, segment VARCHAR,
  state VARCHAR, change_ts TIMESTAMP);
CREATE VIEW v_changes AS
SELECT customer_id, name, email_domain, segment, state, change_ts,
       MD5(CONCAT_WS('|', COALESCE(name, ''), COALESCE(email_domain, ''),
                          COALESCE(segment, ''), COALESCE(state, ''))) AS row_hash
FROM raw_changes
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY change_ts DESC) = 1;
"""


@pytest.fixture
def db():
    con = duckdb.connect()
    con.execute("CREATE SEQUENCE sk")
    con.execute(DDL)
    return con


def load_batch(con, rows):
    con.execute("DELETE FROM raw_changes")  # emulates a stream consumed by the previous run
    con.executemany("INSERT INTO raw_changes VALUES (?, ?, ?, ?, ?, ?)", rows)
    for stmt in filter(str.strip, scd2_sql("dim_customer", "v_changes").split(";")):
        con.execute(stmt)


def rows(con, cid):
    return con.execute("SELECT state, segment, is_current, valid_from, valid_to FROM dim_customer "
                       "WHERE customer_id = ? ORDER BY valid_from", [cid]).fetchall()


def test_insert_change_and_no_change(db):
    load_batch(db, [("C1", "Ann", "x.com", "RETAIL", "TX", "2025-01-01"),
                    ("C2", "Bo", "y.com", "SMB", "CA", "2025-01-01")])
    assert db.execute("SELECT count(*) FROM dim_customer WHERE is_current").fetchone()[0] == 2

    load_batch(db, [("C1", "Ann", "x.com", "RETAIL", "FL", "2025-02-01"),   # changed
                    ("C2", "Bo", "y.com", "SMB", "CA", "2025-02-01")])      # unchanged
    c1 = rows(db, "C1")
    assert [(r[0], r[2]) for r in c1] == [("TX", False), ("FL", True)]
    assert str(c1[0][4]) == "2025-02-01 00:00:00"  # old row closed at change time
    assert len(rows(db, "C2")) == 1


def test_latest_change_in_batch_wins(db):
    load_batch(db, [("C1", "Ann", "x.com", "RETAIL", "TX", "2025-01-01"),
                    ("C1", "Ann", "x.com", "ENTERPRISE", "TX", "2025-01-03"),
                    ("C1", "Ann", "x.com", "SMB", "TX", "2025-01-02")])
    assert rows(db, "C1") == [("TX", "ENTERPRISE", True, rows(db, "C1")[0][3], None)]


def test_rerun_same_batch_is_idempotent(db):
    batch = [("C1", "Ann", "x.com", "RETAIL", "TX", "2025-01-01")]
    load_batch(db, batch)
    load_batch(db, batch)
    assert len(rows(db, "C1")) == 1


def test_one_current_row_per_customer(db):
    for i, st in enumerate(["TX", "CA", "NY", "NY", "WA"]):
        load_batch(db, [("C1", "Ann", "x.com", "RETAIL", st, f"2025-0{i + 1}-01")])
    assert db.execute("SELECT count(*) FROM dim_customer WHERE customer_id='C1' AND is_current").fetchone()[0] == 1
    assert len(rows(db, "C1")) == 4  # NY->NY is not a new version


def test_null_attributes_do_not_break_hash(db):
    load_batch(db, [("C1", None, None, None, None, "2025-01-01")])
    load_batch(db, [("C1", None, None, None, "TX", "2025-01-02")])
    assert len(rows(db, "C1")) == 2


def test_render_rejects_missing_variables():
    with pytest.raises(MissingVariable):
        render("USE {{database}}", {})


def test_deployment_renders_without_placeholders():
    import yaml
    with open("config/dev.yaml") as fh:
        cfg = yaml.safe_load(fh)
    scripts = deployment_sql(cfg)
    assert next(n for n, _ in scripts) == "00_platform_rbac.sql"
    assert all("{{" not in sql for _, sql in scripts)
    task = dict(scripts)["03_task.sql.j2"]
    assert "DEV_CUSTOMER_DB.CORE.DIM_CUSTOMER" in task and "SYSTEM$STREAM_HAS_DATA" in task
