import json
import math
from datetime import datetime
from typing import Optional

import pandas as pd
from pandas import DataFrame
from sqlglot import transpile

from morph.task.utils.connection import Connection


class SQLUtils:
    def __init__(
        self,
        dataframe: DataFrame,
        table_name: str,
        connection: Optional[Connection] = None,
    ):
        self.dataframe: DataFrame = dataframe
        self.table_name: str = table_name
        self.connection: Optional[Connection] = connection

    def generate_insert_sql(self) -> str:
        """Generate INSERT INTO SQL statements for each row in the DataFrame."""
        if self.connection and self.connection.type == "snowflake":
            sql = self._generate_insert_sql_snowflake()
        else:
            columns = ", ".join(f'"{col}"' for col in self.dataframe.columns)
            insert_sql = f"INSERT INTO {self._format_table_name(self.table_name)} ({columns}) VALUES "
            rows: list[str] = []
            for _, row in self.dataframe.iterrows():
                values: list[str] = []
                for item in row:
                    values.append(self._format_value(item))
                row_sql: str = f"({', '.join(values)})"
                rows.append(row_sql)
            all_rows_sql: str = ",\n".join(rows)
            sql = f"{insert_sql}\n{all_rows_sql}"
            if self.connection:
                sql = transpile(
                    sql,
                    read="postgres",
                    write=self.connection.type,
                    identity=True,
                )[0]

        return sql

    def generate_update_sql(self, primary_keys: list[str]) -> str:
        """Generate a single UPDATE SQL statement using CASE for each row in the DataFrame."""
        if not all(key in self.dataframe.columns for key in primary_keys):
            raise ValueError("All key columns must be present in the DataFrame.")

        set_clauses: list[str] = []
        for col in self.dataframe.columns:
            if col not in primary_keys:
                cases: list[str] = []
                for _, row in self.dataframe.iterrows():
                    key_conditions = " AND ".join(
                        f'"{key}" = {self._format_value(row[key])}'
                        for key in primary_keys
                    )
                    cases.append(
                        f"WHEN {key_conditions} THEN {self._format_value(row[col])}"
                    )
                cases_sql = " ".join(cases)
                set_clauses.append(
                    '"{col}" = CASE {cases_sql} ELSE "{col}" END'.format(
                        col=col, cases_sql=cases_sql
                    )
                )

        set_clauses_sql = ", ".join(set_clauses)
        sql = "UPDATE {table_name} SET {set_clauses_sql}".format(
            table_name=self._format_table_name(self.table_name),
            set_clauses_sql=set_clauses_sql,
        )
        if self.connection:
            if self.connection.type == "bigquery":
                sql += " WHERE 1=1"
            sql = transpile(
                sql, read="postgres", write=self.connection.type, identity=True
            )[0]
        return sql

    def generate_insert_or_update_sql(self, primary_keys: list[str]) -> str:
        """Generate an INSERT INTO ... ON CONFLICT ... DO UPDATE SQL statement for each row in the DataFrame."""
        if not all(key in self.dataframe.columns for key in primary_keys):
            raise ValueError("All key columns must be present in the DataFrame.")

        if self.connection is None:
            return self._generate_upsert_sql_postgres(primary_keys)
        elif self.connection.type == "postgres":
            return self._generate_upsert_sql_postgres(primary_keys)
        elif self.connection.type == "mysql":
            return self._generate_upsert_sql_mysql(primary_keys)
        elif self.connection.type == "snowflake":
            return self._generate_upsert_sql_snowflake(primary_keys)
        else:
            raise ValueError(
                f"Unsupported connection type for upsert: {self.connection.type}"
            )

    def generate_delete_sql(self, primary_keys: list[str]) -> str:
        """Generate a DELETE SQL statement for each row in the DataFrame."""
        if not all(key in self.dataframe.columns for key in primary_keys):
            raise ValueError("All key columns must be present in the DataFrame.")

        delete_conditions: list[str] = []
        for _, row in self.dataframe.iterrows():
            conditions = " AND ".join(
                f'"{key}" = {self._format_value(row[key])}' for key in primary_keys
            )
            delete_conditions.append(f"({conditions})")

        delete_conditions_sql = " OR ".join(delete_conditions)
        sql = "DELETE FROM {table_name} WHERE {delete_conditions_sql}".format(
            table_name=self._format_table_name(self.table_name),
            delete_conditions_sql=delete_conditions_sql,
        )
        if self.connection:
            sql = transpile(
                sql, read="postgres", write=self.connection.type, identity=True
            )[0]
        return sql

    def _format_value(self, value):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "NULL"

        elif isinstance(value, str):
            escaped_value = value.replace("'", "''")
            return f"'{escaped_value}'"

        elif isinstance(value, bool):
            return str(value).upper()

        elif isinstance(value, (int, float)):
            return str(value)

        elif isinstance(value, list):
            if self.connection is None:
                return f"ARRAY{value}"
            elif (
                self.connection.type == "mysql"
                or self.connection.type == "redshift"
                or self.connection.type == "bigquery"
            ):
                return f"'{json.dumps(value)}'"
            elif self.connection.type == "snowflake":
                return f"ARRAY_CONSTRUCT({', '.join(self._format_value(item) for item in value)})"
            else:
                return f"ARRAY{value}"

        elif isinstance(value, dict):
            if self.connection is None:
                f"'{json.dumps(value)}'"
            elif self.connection.type == "bigquery":
                dict_statements = []
                for key, val in value.items():
                    dict_statements.append(f"{self._format_value(val)} as {key}")
                return f"STRUCT({', '.join(dict_statements)})"
            elif self.connection.type == "snowflake":
                dict_statements = []
                for key, val in value.items():
                    dict_statements.append(f"'{key}'")
                    dict_statements.append(f"{self._format_value(val)}")
                return f"OBJECT_CONSTRUCT({', '.join(dict_statements)})"
            return f"'{json.dumps(value)}'"

        elif isinstance(value, pd.Timestamp) or isinstance(value, datetime):
            datetime_map = {
                "mysql": f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'",
                "redshift": f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'",
                "postgres": f"'{value.isoformat()}'",
                "bigquery": f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S')}'",
                "snowflake": f"'{value.isoformat()}'",
            }
            return datetime_map.get(
                self.connection.type if self.connection else "postgres",
                f"'{value.isoformat()}'",
            )

        else:
            return f"'{str(value)}'"

    def _format_table_name(self, table_name: str) -> str:
        if self.connection is None:
            return f'"{table_name}"'
        elif self.connection.type == "postgres" or self.connection.type == "redshift":
            return f'"{table_name}"'
        elif self.connection.type == "mysql" or self.connection.type == "bigquery":
            return f"`{table_name}`"
        elif self.connection.type == "snowflake":
            if "." in table_name:
                return ".".join(f'"{part}"' for part in table_name.split("."))
            else:
                return f'"{table_name}"'
        return f'"{table_name}"'

    def _generate_insert_sql_snowflake(self) -> str:
        """Generate Snowflake INSERT INTO SQL statements for each row in the DataFrame."""
        columns = ", ".join(f'"{col}"' for col in self.dataframe.columns)
        insert_sql = (
            f"INSERT INTO {self._format_table_name(self.table_name)} ({columns}) "
        )
        rows: list[str] = []
        for _, row in self.dataframe.iterrows():
            values: list[str] = []
            for item in row:
                values.append(self._format_value(item))
            row_sql: str = f"SELECT {', '.join(values)}"
            rows.append(row_sql)
        all_rows_sql: str = "\nUNION ALL\n".join(rows)
        sql = f"{insert_sql}\n{all_rows_sql}"
        sql = transpile(sql, read="postgres", write="snowflake", identity=True)[0]
        return sql

    def _generate_upsert_sql_postgres(self, primary_keys: list[str]) -> str:
        columns = ", ".join(f'"{col}"' for col in self.dataframe.columns)
        insert_sql = f"INSERT INTO {self._format_table_name(self.table_name)} ({columns}) VALUES "

        rows: list[str] = []
        for _, row in self.dataframe.iterrows():
            values: list[str] = []
            for item in row:
                values.append(self._format_value(item))
            row_sql: str = f"({', '.join(values)})"
            rows.append(row_sql)
        all_rows_sql: str = ",\n".join(rows)

        conflict_target = ", ".join(f'"{key}"' for key in primary_keys)
        update_clauses: list[str] = []
        for col in self.dataframe.columns:
            if col not in primary_keys:
                update_clauses.append(f'"{col}" = EXCLUDED."{col}"')

        sql = f"{insert_sql}\n{all_rows_sql}\nON CONFLICT ({conflict_target}) DO UPDATE SET {', '.join(update_clauses)};"
        return sql

    def _generate_upsert_sql_mysql(self, primary_keys: list[str]) -> str:
        columns = ", ".join(f"`{col}`" for col in self.dataframe.columns)
        insert_sql = f"INSERT INTO {self._format_table_name(self.table_name)} ({columns}) VALUES "

        rows = []
        for _, row in self.dataframe.iterrows():
            values = [self._format_value(item) for item in row]
            rows.append(f"({', '.join(values)})")
        all_rows_sql = ",\n".join(rows)

        update_clauses = [
            f"`{col}` = VALUES(`{col}`)"
            for col in self.dataframe.columns
            if col not in primary_keys
        ]
        sql = f"{insert_sql}\n{all_rows_sql}\nON DUPLICATE KEY UPDATE {', '.join(update_clauses)};"
        return sql

    def _generate_upsert_sql_snowflake(self, primary_keys: list[str]) -> str:
        columns = ", ".join(f'"{col}"' for col in self.dataframe.columns)

        table_name = self._format_table_name(self.table_name)
        merge_sql = f"MERGE INTO {table_name} AS target USING ("

        select_rows = []
        for _, row in self.dataframe.iterrows():
            row_values = [self._format_value(item) for item in row]
            select_rows.append(f"SELECT {', '.join(row_values)}")
        select_clause = " UNION ALL ".join(select_rows)

        merge_sql += f"{select_clause}) AS source ({columns}) ON "

        on_clauses = " AND ".join(
            [f'target."{col}" = source."{col}"' for col in primary_keys]
        )
        merge_sql += on_clauses

        update_clauses = [
            f'target."{col}" = source."{col}"'
            for col in self.dataframe.columns
            if col not in primary_keys
        ]
        merge_sql += " WHEN MATCHED THEN UPDATE SET " + ", ".join(update_clauses)

        merge_sql += (
            " WHEN NOT MATCHED THEN INSERT (" + columns + ") VALUES (" + columns + ");"
        )

        return merge_sql
