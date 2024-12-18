from typing import Any, Dict, List, Optional, Tuple

from morph.task.utils.connections.bigquery.api import BigqueryApi


class BigqueryUsecase:
    def __init__(
        self,
        project_id: str,
        access_token: str,
        location: Optional[str] = "asia-northeast1",
    ):
        self.project_id = project_id
        self.access_token = access_token
        self.location = location

    def query(self, sql: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        def _query(
            _limit: Optional[int] = None, _next_token: Optional[str] = None
        ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
            _result = BigqueryApi.post_query(
                project_id=self.project_id,
                query=sql,
                access_token=self.access_token,
                location=self.location,
                limit=_limit,
                next_token=_next_token,
            )
            _rows: List[Dict[str, Any]] = []
            for _row in _result.rows:
                obj = {}
                for i, f in enumerate(_result.schema_.fields):
                    obj[f.name] = _row["f"][i]["v"]
                _rows.append(obj)
            return _rows, _result.next_token

        items = []
        next_token_ = None
        while True:
            rows, next_token = _query(limit, next_token_)
            items.extend(rows)
            if next_token is not None:
                next_token_ = next_token
            else:
                break
        return items
