from __future__ import annotations

import json
from typing import Any, List, Optional, Union, get_args

import pandas as pd
from morph_lib.error import MorphApiError
from morph_lib.utils.db_connector import DBConnector
from morph_lib.utils.sql import SQLUtils
from pydantic import BaseModel, Field

from morph.api.cloud.client import MorphApiClient, MorphApiKeyClientImpl
from morph.config.project import MorphProject, load_project
from morph.task.utils.connection import (
    CONNECTION_TYPE,
    Connection,
    ConnectionYaml,
    DatabaseConnection,
    DuckDBConnection,
)
from morph.task.utils.connections.connector import Connector
from morph.task.utils.morph import find_project_root_dir


# ===============================================
#
# Class
#
# ===============================================
class FieldSchema(BaseModel):
    name: str
    type: str
    nullable: Optional[bool] = Field(default=True)
    primary: Optional[bool] = Field(default=False)
    comment: Optional[str] = Field(default=None)
    length: Optional[int] = Field(default=None)
    unsigned: Optional[bool] = Field(default=None)
    auto_increment: Optional[bool] = Field(default=None)
    default: Optional[Any] = Field(default=None)
    enums: Optional[List[str]] = Field(default=None)


class TableSchema(BaseModel):
    dialect: str
    name: str
    fields: List[FieldSchema]
    schema_name: Optional[str] = Field(default=None)

    def to_text(self):
        text = f"""# Database
{self.dialect}

"""
        if self.schema_name:
            text += f"""# Schema
{self.schema_name}
"""
        text += f"""# Table
{self.name}

"""
        text += "# Fields\n"
        for i, field in enumerate(self.fields):
            field_text = f"""col{i+1}. {field.name} type={field.type} nullable={field.nullable} """
            if field.primary is not None:
                field_text += f"primary={field.primary} "
            if field.comment:
                field_text += f"comment={field.comment}"
            if field.length:
                field_text += f"length={field.length}"
            if field.unsigned is not None:
                field_text += f"unsigned={field.unsigned}"
            if field.auto_increment is not None:
                field_text += f"auto_increment={field.auto_increment}"
            if field.default:
                field_text += f"default_value={field.default}"
            if field.enums:
                field_text += f"enums={field.enums}"
            text += field_text + "\n"
        return text


# ===============================================
#
# Implementation
#
# ===============================================


def __find_connection(connection: str | Connection | None) -> Connection:
    if isinstance(connection, get_args(Connection)):
        return connection  # type: ignore

    database_connection: Optional[Union[Connection, DatabaseConnection]] = None

    # return connection itself if it's DuckDBConnection
    if connection is not None and isinstance(connection, DuckDBConnection):
        return connection
    # find connection in connections.yml
    elif connection is not None and isinstance(connection, str):
        connection_yaml = ConnectionYaml.load_yaml()
        database_connection = ConnectionYaml.find_connection(
            connection_yaml, connection
        )
        if database_connection is None:
            database_connection = ConnectionYaml.find_cloud_connection(connection)
    else:
        # in case of no connection provided, find default connection
        project: Optional[MorphProject] = load_project(find_project_root_dir())
        if project is None:
            raise MorphApiError("Could not find project.")
        elif project.default_connection is None:
            raise MorphApiError(
                "Default connection is not set in morph_project.yml. Please set default_connection."
            )
        default_connection = project.default_connection
        connection_yaml = ConnectionYaml.load_yaml()
        database_connection = ConnectionYaml.find_connection(
            connection_yaml, default_connection
        )
        if database_connection is None:
            database_connection = ConnectionYaml.find_cloud_connection(
                default_connection
            )

    return database_connection


def __execute_sql_impl(
    sql: str,
    connection: str | Connection | None = None,
) -> pd.DataFrame:
    database_connection: Connection = __find_connection(connection)

    connector = Connector(
        connection if isinstance(connection, str) else "", database_connection
    )
    return connector.execute_sql(sql)


def __process_records(
    action: str,
    data: pd.DataFrame,
    table_name: str,
    primary_keys: List[str] = [],
    connection: Optional[str] = None,
) -> None:
    # Validate action
    if action not in {"insert", "update", "delete", "insert_or_update"}:
        raise MorphApiError(
            "Invalid action provided. Must be 'create', 'insert', or 'update'."
        )

    database_connection = __find_connection(connection)
    if (
        database_connection.type != CONNECTION_TYPE.postgres
        and database_connection.type != CONNECTION_TYPE.snowflake
        and database_connection.type != CONNECTION_TYPE.redshift
        and database_connection.type != CONNECTION_TYPE.mysql
        and database_connection.type != CONNECTION_TYPE.bigquery
    ):
        raise MorphApiError(
            "Only PostgreSQL, Snowflake, Redshift, BigQuery, and MySQL are supported for now."
        )

    if action == "update" or action == "delete" or action == "insert_or_update":
        if len(primary_keys) == 0:
            raise MorphApiError(
                "Primary keys are required for update, delete, and insert_or_update actions."
            )
        missing_keys = [key for key in primary_keys if key not in data.columns]
        if len(missing_keys) > 0:
            raise MorphApiError(
                f"Primary keys {missing_keys} are not present in the DataFrame columns."
            )

    sql_utils = SQLUtils(data, table_name, database_connection)

    if action == "insert":
        __execute_sql_impl(
            sql_utils.generate_insert_sql(), connection=database_connection
        )
    elif action == "update":
        __execute_sql_impl(
            sql_utils.generate_update_sql(primary_keys), connection=database_connection
        )
    elif action == "insert_or_update":
        if (
            database_connection.type == CONNECTION_TYPE.redshift
            or database_connection.type == CONNECTION_TYPE.bigquery
        ):
            raise MorphApiError("Redshift and BigQuery do not support UPSERT.")
        __execute_sql_impl(
            sql_utils.generate_insert_or_update_sql(primary_keys),
            connection=database_connection,
        )
    elif action == "delete":
        __execute_sql_impl(
            sql_utils.generate_delete_sql(primary_keys), connection=database_connection
        )


# ===============================================
#
# Functions
#
# ===============================================
def execute_sql(sql: str, connection: Optional[str] = None) -> pd.DataFrame:
    """
    Execute SQL query
    """
    return __execute_sql_impl(sql, connection)


def insert_records(
    data: pd.DataFrame,
    table_name: str,
    connection: Optional[str] = None,
) -> None:
    """
    Insert records into the table
    """
    __process_records("insert", data, table_name, connection=connection)


def update_records(
    data: pd.DataFrame,
    primary_keys: List[str],
    table_name: str,
    connection: Optional[str] = None,
) -> None:
    """
    Update records in the table
    """
    __process_records(
        "update", data, table_name, primary_keys=primary_keys, connection=connection
    )


def insert_or_update_records(
    data: pd.DataFrame,
    primary_keys: List[str],
    table_name: str,
    connection: Optional[str] = None,
) -> None:
    """
    Insert or Update records in the table
    """
    __process_records(
        "insert_or_update",
        data,
        table_name,
        primary_keys=primary_keys,
        connection=connection,
    )


def delete_records(
    data: pd.DataFrame,
    primary_keys: List[str],
    table_name: str,
    connection: Optional[str] = None,
) -> None:
    """
    Delete records in the table
    """
    __process_records(
        "delete", data, table_name, primary_keys=primary_keys, connection=connection
    )


def get_db_connector(connection: str) -> DBConnector:
    """
    Obtain a DBConnector object for PostgreSQL, Redshift, or MySQL
    """
    connection_yaml = ConnectionYaml.load_yaml()
    database_connection = ConnectionYaml.find_connection(connection_yaml, connection)
    if database_connection is None:
        raise MorphApiError(f"Could not find {connection} in connections.yml.")

    if (
        database_connection.type != CONNECTION_TYPE.postgres
        and database_connection.type != CONNECTION_TYPE.redshift
        and database_connection.type != CONNECTION_TYPE.mysql
    ):
        raise ValueError(f"Connection '{connection}' is not supported.")

    return DBConnector(database_connection)


def get_tables(
    table_names: List[str],
    schema_name: Optional[str],
    connection: Optional[str],
) -> List[TableSchema]:
    """
    Get the table structures
    """
    connection_ = __find_connection(connection)

    tables: List[TableSchema] = []
    client = MorphApiClient(MorphApiKeyClientImpl)
    for table in table_names:
        response = client.req.list_fields(table, schema_name, connection)
        try:
            response.is_error(True)
        except Exception as e:
            error_detail = {
                "type": type(e).__name__,
                "message": str(e),
            }
            error_json = json.dumps(error_detail, ensure_ascii=False)
            raise MorphApiError(error_json)

        fields: List[FieldSchema] = []
        for field in response.json()["fields"]:
            field_type = field["nativeType"] if "nativeType" in field else field["type"]
            fields.append(
                FieldSchema(
                    name=field["name"],
                    type=field_type,
                    nullable=field["nullable"] if "nullable" in field else True,
                    primary=field["primary"] if "primary" in field else None,
                    comment=field["comment"] if "comment" in field else None,
                    length=field["length"] if "length" in field else None,
                    unsigned=field["unsigned"] if "unsigned" in field else None,
                    auto_increment=(
                        field["autoIncrement"] if "autoIncrement" in field else None
                    ),
                    default=(field["default"] if "default" in field else None),
                    enums=field["members"] if "members" in field else None,
                )
            )

        tables.append(
            TableSchema(
                dialect=connection_.type,
                name=table,
                fields=fields,
                schema_name=schema_name,
            )
        )

    return tables
