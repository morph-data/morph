import json
import os
import sqlite3
from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional, Tuple, Union

from pydantic import BaseModel

from morph.constants import MorphConstant


class RunStatus(str, Enum):
    DONE = "done"
    TIMEOUT = "timeout"
    IN_PROGRESS = "inProgress"
    FAILED = "failed"


class StackTraceFrame(BaseModel):
    filename: str
    lineno: Optional[int] = None
    name: str
    line: Optional[str] = None


class PythonError(BaseModel):
    type: str
    message: str
    code: str
    stacktrace: str
    structured_stacktrace: List[StackTraceFrame]


GeneralError = str


class CliError(BaseModel):
    type: Literal["python", "general"]
    details: Union[PythonError, GeneralError]


class SqliteDBManager:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.db_path = os.path.join(self.project_root, MorphConstant.MORPH_PROJECT_DB)

    def initialize_database(self):
        # Connect to the SQLite database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create "runs" table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT,
                canvas TEXT,
                cell_alias TEXT,
                is_dag BOOLEAN,
                status TEXT,
                error TEXT,
                started_at TEXT,
                ended_at TEXT,
                log TEXT,
                outputs TEXT,
                PRIMARY KEY (run_id, canvas, cell_alias)
            )
            """
        )
        conn.commit()

        # Check if 'variables_hash' column exists, and add it if it doesn't
        cursor.execute("PRAGMA table_info(runs)")
        columns = [column[1] for column in cursor.fetchall()]
        if "variables_hash" not in columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN variables_hash TEXT")
        if "variables" not in columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN variables TEXT")
        if "file_hash" not in columns:
            cursor.execute("ALTER TABLE runs ADD COLUMN file_hash TEXT")

        # Create indexes for "runs" table
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_runs_cell_alias ON runs(cell_alias)
            """
        )

        # Commit changes and close the connection
        conn.commit()
        conn.close()

    def insert_run_record(
        self,
        run_id: str,
        cell_alias: str,
        is_dag: bool,
        log_path: str,
        file_hash: Optional[str],
        variables_hash: Optional[str],
        variables: Optional[dict],
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute(
                """
                INSERT INTO runs (run_id, canvas, cell_alias, is_dag, status, started_at, ended_at, log, outputs, variables_hash, variables, file_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    None,
                    cell_alias,
                    is_dag,
                    RunStatus.IN_PROGRESS.value,
                    datetime.now().isoformat(),
                    None,
                    log_path,
                    None,
                    variables_hash,
                    json.dumps(variables) if variables else None,
                    file_hash,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_run_record(
        self,
        run_id: str,
        cell_alias: str,
        new_status: str,
        error: Optional[CliError],
        outputs: Optional[Union[str, dict, List[str]]] = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        ended_at = datetime.now().isoformat()

        # Ensure error and outputs are JSON serializable strings
        error_str: Optional[str] = None
        if error:
            error_str = error.model_dump_json()
        if outputs and not isinstance(outputs, str):
            outputs = json.dumps(outputs)

        try:
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute(
                """
                UPDATE runs
                SET status = ?, error = ?, ended_at = ?, outputs = ?
                WHERE run_id = ? AND cell_alias = ?
                """,
                (new_status, error_str, ended_at, outputs, run_id, cell_alias),
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_run_records(
        self,
        canvas: Optional[str],
        cell_alias: str,
        status: Optional[str],
        sort_by: Optional[str],
        order: Optional[str],
        limit: Optional[int],
        skip: Optional[int],
        file_hash: Optional[str] = None,
        variables_hash: Optional[str] = None,
        greather_than_ended_at: Optional[datetime] = None,
        run_id: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            params = [cell_alias]
            base_query = "FROM runs WHERE cell_alias = ?"

            if canvas:
                base_query += " AND canvas = ?"
                params.append(canvas)
            if status:
                base_query += " AND status = ?"
                params.append(status)
            if file_hash:
                base_query += " AND file_hash = ?"
                params.append(file_hash)
            if variables_hash:
                base_query += " AND variables_hash = ?"
                params.append(variables_hash)
            if greather_than_ended_at:
                base_query += " AND ended_at >= ?"
                params.append(greather_than_ended_at.isoformat())
            if run_id:
                base_query += " AND run_id = ?"
                params.append(run_id)

            count_query = f"SELECT COUNT(*) {base_query}"
            cursor.execute(count_query, params)
            count = cursor.fetchone()[0]

            query = f"SELECT * {base_query}"
            if sort_by:
                if not order:
                    order = "DESC"
                query += f" ORDER BY {sort_by} {order}"
            if limit:
                query += f" LIMIT {limit}"
            if skip:
                query += f" OFFSET {skip}"

            cursor.execute(query, params)

            column_names = [description[0] for description in cursor.description]
            records = cursor.fetchall()
            result = [dict(zip(column_names, row)) for row in records]
        except sqlite3.Error as e:
            raise e
        finally:
            conn.close()

        return result, count

    def get_run_records_by_run_id(self, run_id: str) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM runs WHERE run_id = ? ORDER BY started_at ASC", (run_id,)
            )

            column_names = [description[0] for description in cursor.description]
            records = cursor.fetchall()
            result = [dict(zip(column_names, row)) for row in records]
        except sqlite3.Error as e:
            raise e
        finally:
            conn.close()

        return result
