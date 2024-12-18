from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class SnowflakeException(Exception):
    def __init__(self, message, code=None, sqlState=None, statementHandle=None):
        super().__init__(message)
        self.code = code
        self.sqlState = sqlState
        self.statementHandle = statementHandle


class SnowflakeNetworkResponse(BaseModel, Generic[T]):
    data: T
    status: int


class SnowflakeNetworkErrorResponse(BaseModel):
    code: str
    message: str
    sqlState: str
    statementHandle: str


def is_snowflake_network_error(input: Any) -> bool:
    return isinstance(input, SnowflakeNetworkErrorResponse) or (
        isinstance(input, dict)
        and "code" in input
        and "message" in input
        and "sqlState" in input
        and "statementHandle" in input
    )


class SnowflakeOAuthError(BaseModel):
    code: str
    message: str

    def __init__(self, **data):
        super().__init__(**data)
        if self.code != "390318":
            raise ValueError("code must be '390318'")


def is_snowflake_oauth_error(input: Any) -> bool:
    return isinstance(input, SnowflakeOAuthError) or (
        isinstance(input, dict)
        and "code" in input
        and input["code"] == "390318"
        and "message" in input
        and isinstance(input["message"], str)
    )


class SnowflakeRowTypeFieldType(str, Enum):
    NUMBER = "NUMBER"
    DECIMAL = "DECIMAL"
    NUMERIC = "NUMERIC"
    INT = "INT"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    SMALLINT = "SMALLINT"
    TINYINT = "TINYINT"
    BYTEINT = "BYTEINT"
    FLOAT = "FLOAT"
    FLOAT4 = "FLOAT4"
    FLOAT8 = "FLOAT8"
    FIXED = "FIXED"
    REAL = "REAL"
    DOUBLE = "DOUBLE"
    DOUBLE_PRECISION = "DOUBLE PRECISION"
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    CHARACTER = "CHARACTER"
    STRING = "STRING"
    TEXT = "TEXT"
    BINARY = "BINARY"
    VARBINARY = "VARBINARY"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIME = "TIME"
    TIMESTAMP = "TIMESTAMP"
    TIMESTAMP_LTZ = "TIMESTAMP_LTZ"
    TIMESTAMP_NTZ = "TIMESTAMP_NTZ"
    TIMESTAMP_TZ = "TIMESTAMP_TZ"
    VARIANT = "VARIANT"
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"
    GEOGRAPHY = "GEOGRAPHY"


class SnowflakeRowType(BaseModel):
    name: str
    database: str
    schema_: str = Field(..., alias="schema")
    table: str
    precision: Optional[int]
    byteLength: Optional[int]
    scale: Optional[int]
    type: SnowflakeRowTypeFieldType
    nullable: bool
    collation: Optional[str]
    length: Optional[int]

    @field_validator("type", mode="before")
    def convert_type_to_uppercase(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v


class PartitionInfo(BaseModel):
    rowCount: int
    uncompressedSize: int


class ResultSetMetaData(BaseModel):
    numRows: int
    format: str
    partitionInfo: List[PartitionInfo]
    rowType: List[SnowflakeRowType]

    @classmethod
    def parse_obj(cls, data: Dict[str, Any]) -> "ResultSetMetaData":
        partitionInfo = [
            PartitionInfo.model_validate(pi) for pi in data["partitionInfo"]
        ]
        rowType = [SnowflakeRowType.model_validate(rt) for rt in data["rowType"]]
        return cls(
            numRows=data["numRows"],
            format=data["format"],
            partitionInfo=partitionInfo,
            rowType=rowType,
        )


class SnowflakeExecuteSqlStatementsResponse(BaseModel):
    resultSetMetaData: ResultSetMetaData
    data: List[List[Union[str, int, float, bool, None]]]
    code: str
    statementStatusUrl: str
    requestId: str
    sqlState: str
    statementHandle: str
    message: str
    createdOn: int

    @classmethod
    def parse_obj(cls, data: Dict[str, Any]) -> "SnowflakeExecuteSqlStatementsResponse":
        resultSetMetaData = ResultSetMetaData.parse_obj(data["resultSetMetaData"])
        return cls(
            resultSetMetaData=resultSetMetaData,
            data=data["data"],
            code=data["code"],
            statementStatusUrl=data["statementStatusUrl"],
            requestId=data["requestId"],
            sqlState=data["sqlState"],
            statementHandle=data["statementHandle"],
            message=data["message"],
            createdOn=data["createdOn"],
        )


class SnowflakeExecuteSqlImplResponse(BaseModel):
    data: SnowflakeExecuteSqlStatementsResponse
    status: int

    @classmethod
    def parse_obj(cls, data: Dict[str, Any]) -> "SnowflakeExecuteSqlImplResponse":
        data_ = SnowflakeExecuteSqlStatementsResponse.parse_obj(data["data"])
        return cls(data=data_, status=data["status"])
