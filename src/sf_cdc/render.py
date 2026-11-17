from __future__ import annotations

import re
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")
ORDER = ["00_platform_rbac.sql", "01_ingest_snowpipe.sql", "02_core_objects.sql", "03_task.sql.j2"]


class MissingVariable(KeyError):
    pass


def render(text: str, variables: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in variables:
            raise MissingVariable(key)
        return str(variables[key])
    return _VAR.sub(sub, text)


def scd2_sql(target: str, changes: str) -> str:
    return render((SQL_DIR / "scd2_apply.sql").read_text(), {"target": target, "changes": changes})


def deployment_sql(variables: dict[str, str]) -> list[tuple[str, str]]:
    db = variables["database"]
    v = {**variables,
         "scd2_apply": scd2_sql(f"{db}.CORE.DIM_CUSTOMER", f"{db}.CORE.V_CUSTOMER_CHANGES").replace("\n", "\n  ")}
    return [(name, render((SQL_DIR / name).read_text(), v)) for name in ORDER]
