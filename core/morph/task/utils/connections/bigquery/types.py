from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BigqueryException(Exception):
    def __init__(
        self, message: str, code: int, errors: List[Dict[str, Any]], status: str
    ):
        super().__init__(message)
        self.code = code
        self.errors = errors
        self.status = status


class BigqueryFieldTypes(str, Enum):
    INTEGER = "INTEGER"
    INT64 = "INT64"
    FLOAT = "FLOAT"
    FLOAT64 = "FLOAT64"
    STRING = "STRING"
    BYTES = "BYTES"
    BOOLEAN = "BOOLEAN"
    BOOL = "BOOL"
    TIMESTAMP = "TIMESTAMP"
    DATE = "DATE"
    TIME = "TIME"
    DATETIME = "DATETIME"
    GEOGRAPHY = "GEOGRAPHY"
    RECORD = "RECORD"
    STRUCT = "STRUCT"
    NUMERIC = "NUMERIC"
    BIGNUMERIC = "BIGNUMERIC"
    JSON = "JSON"


class BigqueryFieldModes(str, Enum):
    NULLABLE = "NULLABLE"
    REQUIRED = "REQUIRED"
    REPEATED = "REPEATED"


class BigqueryTableFieldSchema(BaseModel):
    name: str
    type: BigqueryFieldTypes
    mode: BigqueryFieldModes
    fields: List["BigqueryTableFieldSchema"] = Field(default_factory=list)
    description: Optional[str] = None


class BigqueryTableSchema(BaseModel):
    fields: List[BigqueryTableFieldSchema] = Field(default_factory=list)


class BigqueryQueryResponse(BaseModel):
    schema_: BigqueryTableSchema = Field(..., alias="schema")
    rows: List[Dict[str, Any]]
    next_token: Optional[str] = None


class BigqueryQueryErrorResponse(BaseModel):
    code: int
    message: str
