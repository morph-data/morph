import json
from typing import Any, Dict, List, Optional, Tuple

from morph.task.utils.connections.snowflake.api import SnowflakeApi
from morph.task.utils.connections.snowflake.types import (
    SnowflakeRowType,
    is_snowflake_network_error,
    is_snowflake_oauth_error,
)


class SnowflakeUsecase:
    def __init__(
        self,
        account: str,
        access_token: str,
        database: str,
        schema: Optional[str] = None,
        warehouse: Optional[str] = None,
        role: Optional[str] = None,
    ):
        self.account = account
        self.access_token = access_token
        self.database = database
        self.schema = schema
        self.warehouse = warehouse
        self.role = role

    def query(
        self,
        sql: str,
        statement_handle: Optional[str] = None,
        max_partition_num: Optional[int] = None,
        next_token: Optional[str] = None,
        row_type: Optional[List[SnowflakeRowType]] = [],
    ) -> List[Dict[str, Any]]:
        def _query(
            _statement_handle: Optional[str] = None,
            _max_partition_num: Optional[int] = None,
            _next_token: Optional[str] = None,
            _rowType: Optional[List[SnowflakeRowType]] = [],
        ) -> Tuple[
            List[Dict[str, Any]],
            Optional[str],
            Optional[int],
            Optional[str],
            Optional[List[SnowflakeRowType]],
        ]:
            __statement_handle = _statement_handle
            __max_partition_num = _max_partition_num
            __partition = 0 if _next_token is None else int(_next_token)
            __next_token = _next_token
            __data = None
            __row_type = _rowType

            if __statement_handle is not None:
                result = SnowflakeApi.get_sql_statements(
                    account=self.account,
                    access_token=self.access_token,
                    statement_handle=__statement_handle,
                    partition=__partition,
                )
                if is_snowflake_network_error(result) or is_snowflake_oauth_error(
                    result
                ):
                    raise Exception(json.dumps(result))
                __data = result["data"]["data"]  # type: ignore
                __partition += 1
                if __max_partition_num and __partition < __max_partition_num:
                    __next_token = str(__partition)
                else:
                    __next_token = None
            else:
                result = SnowflakeApi.execute_sql(  # type: ignore
                    account=self.account,
                    access_token=self.access_token,
                    statement=sql,
                    database=self.database,
                    schema=self.schema,
                    warehouse=self.warehouse,
                    role=self.role,
                )
                if is_snowflake_network_error(result) or is_snowflake_oauth_error(
                    result
                ):
                    raise Exception(json.dumps(result))
                __statement_handle = result["statementHandle"]  # type: ignore
                __max_partition_num = result["partitionNum"]  # type: ignore
                __rowType = result["data"]["resultSetMetaData"]["rowType"]  # type: ignore
                __data = result["data"]["data"]  # type: ignore

                __partition += 1
                if __max_partition_num and __partition < __max_partition_num:
                    __next_token = str(__partition)
                else:
                    __next_token = None

            rows = []
            for row in __data:
                obj = {}
                for i, t in enumerate(__rowType):
                    obj[t["name"]] = row[i]
                rows.append(obj)
            return (
                rows,
                __statement_handle,
                __max_partition_num,
                __next_token,
                __row_type,
            )

        items = []
        statement_handle_ = statement_handle
        max_partition_num_ = max_partition_num
        next_token_ = next_token
        row_type_ = row_type
        while True:
            (
                rows__,
                statement_handle__,
                max_partition_num__,
                next_token__,
                row_type__,
            ) = _query(statement_handle_, max_partition_num_, next_token_, row_type_)
            items.extend(rows__)
            if statement_handle__ is not None and next_token__ is not None:
                statement_handle_ = statement_handle__
                max_partition_num_ = max_partition_num__
                next_token_ = next_token__
                row_type_ = row_type__
            else:
                break
        return items
