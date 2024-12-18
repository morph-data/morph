import io
import os
from typing import Any, Optional, Union

from colorama import Fore
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from morph.task.utils.connection import SQLServerConnection
from morph.task.utils.connections.database.utils import is_sql_returning_result
from morph.task.utils.connections.utils import normalize_newlines

CONNECTION_TIMEOUT = 10


class SQLServerConnector:
    def __init__(
        self,
        connection: SQLServerConnection,
        use_ssh: Optional[bool] = False,
    ):
        self.connection = connection
        self.use_ssh = use_ssh
        self.ssh_server: Optional[Any] = None
        self.session: Optional[sessionmaker[Session]] = None
        self.engine = self._create_engine()

    def _get_db_url(self, local_port: Optional[Union[str, int]] = None) -> str:
        user = self.connection.user
        password = self.connection.password
        host = "localhost" if local_port else self.connection.host
        port = local_port if local_port else self.connection.port
        database = self.connection.dbname
        return f"mssql+pytds://{user}:{password}@{host}:{port}/{database}"

    def _start_ssh_tunnel(self):
        from paramiko import RSAKey
        from sshtunnel import SSHTunnelForwarder

        ssh_host = self.connection.ssh_host
        ssh_port = int(self.connection.ssh_port) if self.connection.ssh_port else 22
        ssh_user = self.connection.ssh_user
        ssh_password = self.connection.ssh_password
        ssh_pkey = None
        if self.connection.ssh_private_key:
            _ssh_private_key = self.connection.ssh_private_key
            if _ssh_private_key.startswith("~"):
                _ssh_private_key = os.path.expanduser(_ssh_private_key)
            if os.path.exists(_ssh_private_key):
                ssh_pkey_str = open(_ssh_private_key).read()
            else:
                ssh_pkey_str = normalize_newlines(_ssh_private_key)
            private_key_file = io.StringIO(ssh_pkey_str)
            ssh_pkey = RSAKey.from_private_key(private_key_file)
        remote_bind_address = (
            self.connection.host,
            int(self.connection.port) if self.connection.port else 3306,
        )

        self.ssh_server = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_password=ssh_password,
            ssh_pkey=ssh_pkey,
            remote_bind_address=remote_bind_address,
            local_bind_address=("localhost", 10001),
        )
        if not self.ssh_server:
            raise RuntimeError("Failed to create SSH tunnel")

        self.ssh_server.start()

        return self.ssh_server.local_bind_port

    def _create_engine(self) -> Any:
        local_port = None
        if self.use_ssh:
            local_port = self._start_ssh_tunnel()
        db_url = self._get_db_url(local_port)
        return create_engine(db_url, echo=False)

    def get_session(self) -> Any:
        if not self.engine:
            self.engine = self._create_engine()
        if not self.session:
            Session = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.session = Session()
        return self.session

    def close_session(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
        if self.ssh_server:
            self.ssh_server.stop()
            self.ssh_server = None

    def execute_sql(self, sql: str) -> Any:
        session = self.get_session()
        try:
            if not is_sql_returning_result(sql):
                with session.begin():
                    session.execute(text(sql))
                    return None
            if sql.strip().lower().startswith("select"):
                result = session.execute(text(sql))
                return result.fetchall(), result.keys()
            else:
                with session.begin():
                    result = session.execute(text(sql))
                    return result.fetchall(), result.keys()
        except Exception as e:
            print(Fore.RED + f"{e}" + Fore.RESET)
            print(
                Fore.RED
                + "\n\n=== Executed SQL ===\n"
                + f"{sql}"
                + "\n===========\n"
                + Fore.RESET
            )
            if not sql.strip().lower().startswith("select"):
                session.rollback()
            raise RuntimeError(f"Error executing query: {e}")
        finally:
            self.close_session()
