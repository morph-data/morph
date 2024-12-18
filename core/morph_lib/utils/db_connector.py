from typing import Any, Dict, Union

from morph.task.utils.connection import (
    MysqlConnection,
    PostgresqlConnection,
    RedshiftConnection,
    SQLServerConnection,
)
from morph.task.utils.connections.database.mssql import SQLServerConnector
from morph.task.utils.connections.database.mysql import MysqlConnector
from morph.task.utils.connections.database.postgres import PostgresqlConnector
from morph.task.utils.connections.database.redshift import RedshiftConnector


class DBConnector:
    """
    Database connector implements sqlalchemy connection to the database
    Available mysql, postgres, redshift connection
    @param connection: Connection object from `get_service_connection` method or dict params
    """

    def __init__(
        self,
        connection: Union[
            PostgresqlConnection,
            MysqlConnection,
            SQLServerConnection,
            RedshiftConnection,
            Dict[str, Any],
        ],
    ):
        if isinstance(connection, dict):
            connection_type = connection.get("type")
            if connection_type == "mysql":
                connection = MysqlConnection(**connection)
            elif connection_type == "postgres":
                connection = PostgresqlConnection(**connection)
            elif connection_type == "mssql":
                connection = SQLServerConnection(**connection)
            elif connection_type == "redshift":
                connection = RedshiftConnection(**connection)
            else:
                raise ValueError(f"Invalid connection type: {connection_type}")
        self.connection = connection

    def execute_sql(self, sql: str) -> Any:
        """
        Execute sql query on the specified database
        """
        if isinstance(self.connection, PostgresqlConnection):
            pg_connection = PostgresqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return pg_connection.execute_sql(sql)
        elif isinstance(self.connection, MysqlConnection):
            mysql_connection = MysqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return mysql_connection.execute_sql(sql)
        elif isinstance(self.connection, SQLServerConnection):
            mssql_connection = SQLServerConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return mssql_connection.execute_sql(sql)
        elif isinstance(self.connection, RedshiftConnection):
            redshift_connection = RedshiftConnector(self.connection)
            return redshift_connection.execute_sql(sql)
        else:
            raise ValueError("Invalid connection type")

    def get_connection(
        self,
    ) -> Union[
        PostgresqlConnector, MysqlConnector, SQLServerConnector, RedshiftConnector
    ]:
        """
        Get db connection object
        """
        if isinstance(self.connection, PostgresqlConnection):
            pg_connection = PostgresqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return pg_connection
        elif isinstance(self.connection, MysqlConnection):
            mysql_connection = MysqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return mysql_connection
        elif isinstance(self.connection, SQLServerConnection):
            mssql_connection = SQLServerConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            return mssql_connection
        elif isinstance(self.connection, RedshiftConnection):
            redshift_connection = RedshiftConnector(self.connection)
            return redshift_connection
        else:
            raise ValueError("Invalid connection type")
