import re


def is_sql_returning_result(sql: str) -> bool:
    if sql is None or sql == "":
        return False
    non_select_patterns = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bCREATE\b",
        r"\bALTER\b",
        r"\bDROP\b",
        r"\bTRUNCATE\b",
        r"\bSET\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
    ]
    for pattern in non_select_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            return False

    select_pattern = r"\bSELECT\b"
    if re.search(select_pattern, sql, re.IGNORECASE):
        return True

    return False
