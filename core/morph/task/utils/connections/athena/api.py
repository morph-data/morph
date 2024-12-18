import time
from typing import Any, Dict, Optional


class AthenaApi:
    @staticmethod
    def query(
        access_key: str,
        secret_key: str,
        session_token: str,
        region: str,
        sql: str,
        next_token: Optional[str] = None,
        limit: Optional[int] = None,
        catalog: Optional[str] = None,
        database: Optional[str] = None,
        work_group: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from boto3 import client

        athena_client = client(
            "athena",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region,
        )

        start_query_execution_input: Dict[str, Any] = {
            "QueryString": sql,
            "WorkGroup": work_group,
        }

        if catalog or database:
            start_query_execution_input["QueryExecutionContext"] = {}
            if catalog:
                start_query_execution_input["QueryExecutionContext"][
                    "Catalog"
                ] = catalog
            if database:
                start_query_execution_input["QueryExecutionContext"][
                    "Database"
                ] = database

        start_query: Dict[str, Any] = athena_client.start_query_execution(
            **start_query_execution_input
        )
        query_execution_id = start_query.get("QueryExecutionId")

        if query_execution_id is None:
            return None

        while True:
            get_query_execution: Dict[str, Any] = athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = get_query_execution["QueryExecution"]["Status"]["State"]

            if status in ["RUNNING", "QUEUED"]:
                time.sleep(0.5)
            else:
                break

        if get_query_execution is None or "QueryExecution" not in get_query_execution:
            return None

        if get_query_execution["QueryExecution"]["Status"]["State"] == "FAILED":
            if "AthenaError" in get_query_execution["QueryExecution"]["Status"]:
                error_message = get_query_execution["QueryExecution"]["Status"][
                    "AthenaError"
                ]["ErrorMessage"]
                raise Exception(error_message)

        get_query_results_input = {
            "QueryExecutionId": query_execution_id,
        }
        if next_token:
            get_query_results_input["NextToken"] = next_token
        if limit:
            get_query_results_input["MaxResults"] = limit

        result: Dict[str, Any] = athena_client.get_query_results(
            **get_query_results_input
        )
        return result
