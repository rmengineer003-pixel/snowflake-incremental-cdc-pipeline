"""Deploy to Snowflake, or print the rendered SQL with --dry-run.

Credentials come only from environment variables (key-pair auth recommended):
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH, SNOWFLAKE_ROLE."""
from __future__ import annotations

import argparse
import logging
import os
import sys

import yaml

from .render import deployment_sql

log = logging.getLogger("sf_cdc")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/dev.yaml")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    with open(a.config) as fh:
        variables = yaml.safe_load(fh)
    scripts = deployment_sql(variables)
    if a.dry_run:
        for name, sql in scripts:
            print(f"-- ===== {name} =====\n{sql}\n")
        return 0

    import snowflake.connector  # optional dependency
    from cryptography.hazmat.primitives import serialization
    with open(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"], "rb") as fh:
        pkey = serialization.load_pem_private_key(fh.read(), password=None)
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        private_key=pkey.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    try:
        for name, sql in scripts:
            log.info("running %s", name)
            for _ in conn.execute_string(sql):
                pass
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
