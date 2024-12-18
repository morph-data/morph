from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from morph.task.utils.connections.athena.api import AthenaApi


class AthenaUsecase:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        session_token: str,
        region: str,
        catalog: str,
        database: Optional[str],
        work_group: Optional[str],
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.session_token = session_token
        self.region = region
        self.catalog = catalog
        self.database = database
        self.work_group = work_group

    def query(self, sql: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        def _query(
            _limit: Optional[int] = None,
            _next_token: Optional[str] = None,
            _initial: Optional[bool] = False,
        ) -> Tuple[List[Dict[str, Any]], Optional[str], bool]:
            _result = AthenaApi.query(
                access_key=self.access_key,
                secret_key=self.secret_key,
                session_token=self.session_token,
                region=self.region,
                sql=sql,
                next_token=_next_token,
                limit=_limit,
                catalog=self.catalog,
                database=self.database,
                work_group=self.work_group,
            )
            if _result is None:
                raise Exception("Failed to query")

            columns: Dict[Any, Any] = _result["ResultSet"]["ResultSetMetadata"][
                "ColumnInfo"
            ]
            _rows: List[Dict[str, Any]] = []
            for idx, _row in enumerate(_result["ResultSet"]["Rows"]):
                obj: Dict[str, Any] = {}
                for i, column in enumerate(columns):
                    if i < len(_row["Data"]) and "VarCharValue" in _row["Data"][i]:
                        obj[column["Name"]] = _row["Data"][i]["VarCharValue"]
                    else:
                        obj[column["Name"]] = None
                if idx == 0 and _initial:
                    if all(key == value for key, value in obj.items()):
                        continue
                _rows.append(obj)
            return _rows, _result.get("NextToken", None), False

        items = []
        next_token_ = None
        initial_ = True
        while True:
            rows, next_token, initial = _query(limit, next_token_, initial_)
            initial_ = initial
            items.extend(rows)
            if next_token is not None:
                next_token_ = next_token
            else:
                break
        return items
