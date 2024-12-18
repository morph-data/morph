from enum import Enum


class MorphTemplateLanguage(str, Enum):
    PYTHON = "python"
    SQL = "sql"
    JSON = "json"
    MDX = "mdx"
