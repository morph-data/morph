import re


def normalize_newlines(raw: str) -> str:
    normalized_str = re.sub(r"\\+n", "\n", raw)
    return normalized_str
