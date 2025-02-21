from typing import Optional

import pandas as pd
from colorama import Fore

from morph.task.utils.connection import (
    AthenaConnection,
    BigqueryConnectionOAuth,
    BigqueryConnectionServiceAccount,
    BigqueryConnectionServiceAccountJson,
    Connection,
    ConnectionYaml,
    DuckDBConnection,
    MysqlConnection,
    PostgresqlConnection,
    RedshiftConnection,
    SnowflakeConnectionKeyPair,
    SnowflakeConnectionKeyPairFile,
    SnowflakeConnectionOAuth,
    SnowflakeConnectionUserPassword,
    SQLServerConnection,
)
from morph.task.utils.connections.athena.usecase import AthenaUsecase
from morph.task.utils.connections.bigquery.api import BigqueryApi
from morph.task.utils.connections.bigquery.usecase import BigqueryUsecase
from morph.task.utils.connections.database.mssql import SQLServerConnector
from morph.task.utils.connections.database.mysql import MysqlConnector
from morph.task.utils.connections.database.postgres import PostgresqlConnector
from morph.task.utils.connections.database.redshift import RedshiftConnector
from morph.task.utils.connections.snowflake.api import SnowflakeApi
from morph.task.utils.connections.snowflake.usecase import SnowflakeUsecase


class Connector:
    """
    Connector class to execute SQL queries on different databases
    @param connection_slug: Connection slug
    @param connection: Connection object (required to set value on cloud)
    """

    def __init__(
        self,
        connection_slug: str,
        connection: Optional[Connection] = None,
    ):
        if connection is None:
            connection = ConnectionYaml.find_connection(None, connection_slug)
        if connection is None:
            raise FileNotFoundError("No connections found")
        self.connection = connection

    def execute_sql(self, sql: str) -> pd.DataFrame:
        if isinstance(self.connection, PostgresqlConnection):
            pg_db = PostgresqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            result = pg_db.execute_sql(sql)
            if result is None:
                return pd.DataFrame()
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        elif isinstance(self.connection, MysqlConnection):
            mysql_db = MysqlConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            result = mysql_db.execute_sql(sql)
            if result is None:
                return pd.DataFrame()
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        elif isinstance(self.connection, SQLServerConnection):
            mssql_db = SQLServerConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            result, keys = mssql_db.execute_sql(sql)
            if result is None:
                return pd.DataFrame()
            return pd.DataFrame(result, columns=keys)
        elif isinstance(self.connection, RedshiftConnection):
            redshift_db = RedshiftConnector(
                self.connection,
                use_ssh=self.connection.ssh_host is not None
                and self.connection.ssh_host != "",
            )
            result = redshift_db.execute_sql(sql)
            if result is None:
                return pd.DataFrame()
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        elif isinstance(self.connection, SnowflakeConnectionUserPassword):
            result, columns = SnowflakeApi.execute_sql_with_basic(
                sql=sql,
                username=self.connection.user,
                password=self.connection.password,
                account=self.connection.account,
                database=self.connection.database,
                schema=self.connection.schema_,
                warehouse=self.connection.warehouse,
            )
            return pd.DataFrame(result, columns=columns)
        elif isinstance(self.connection, SnowflakeConnectionOAuth):
            access_token = self.connection.access_token
            if access_token is None:
                raise ValueError("Access token is required for cloud connection")
            result = SnowflakeUsecase(
                account=self.connection.account,
                access_token=access_token,
                database=self.connection.database,
                schema=self.connection.schema_,
                warehouse=self.connection.warehouse,
                role=self.connection.role,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, SnowflakeConnectionKeyPair):
            access_token = self.connection.access_token
            if access_token is None:
                raise ValueError("Access token is required for cloud connection")
            result = SnowflakeUsecase(
                account=self.connection.account,
                access_token=access_token,
                database=self.connection.database,
                schema=self.connection.schema_,
                warehouse=self.connection.warehouse,
                role=self.connection.role,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, SnowflakeConnectionKeyPairFile):
            access_token = SnowflakeApi.get_key_pair_access_token(
                account_identifier=self.connection.account,
                username=self.connection.username,
                private_key_raw=self.connection.key_pair_path,
                passphrase=self.connection.passphrase,
            )
            result = SnowflakeUsecase(
                account=self.connection.account,
                access_token=access_token,
                database=self.connection.database,
                schema=self.connection.schema_,
                warehouse=self.connection.warehouse,
                role=self.connection.role,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, BigqueryConnectionOAuth):
            access_token = self.connection.access_token
            if access_token is None:
                raise ValueError("Access token is required for cloud connection")
            result = BigqueryUsecase(
                project_id=self.connection.project,
                access_token=access_token,
                location=self.connection.location,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, BigqueryConnectionServiceAccount):
            access_token = BigqueryApi.get_access_token_from_service_account(
                service_account_info=self.connection.keyfile
            )
            result = BigqueryUsecase(
                project_id=self.connection.project,
                access_token=access_token,
                location=self.connection.location,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, BigqueryConnectionServiceAccountJson):
            access_token = self.connection.access_token
            if access_token is None:
                raise ValueError("Access token is required for cloud connection")
            result = BigqueryUsecase(
                project_id=self.connection.project,
                access_token=access_token,
                location=self.connection.location,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, AthenaConnection):
            result = AthenaUsecase(
                access_key=self.connection.access_key,
                secret_key=self.connection.secret_key,
                session_token=self.connection.session_token,
                region=self.connection.region,
                catalog=self.connection.catalog,
                database=self.connection.database,
                work_group=self.connection.work_group,
            ).query(sql)
            return pd.DataFrame(result)
        elif isinstance(self.connection, DuckDBConnection):
            from duckdb import connect

            try:
                con = connect()
                return con.sql(sql).to_df()  # type: ignore
            except Exception as e:
                print(Fore.RED + f"{e}" + Fore.RESET)
                print(
                    Fore.RED
                    + "\n\n=== Executed SQL ===\n"
                    + f"{sql}"
                    + "\n===========\n"
                    + Fore.RESET
                )
                raise RuntimeError(f"Error executing query: {e}")
        raise NotImplementedError("connection type not implemented")
