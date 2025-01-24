import os
from typing import Optional

import click

from morph.cli.flags import Flags
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.connection import (
    CONNECTION_DETAIL_TYPE,
    CONNECTION_TYPE,
    BigqueryConnectionServiceAccount,
    ConnectionYaml,
    DatabaseConnection,
    MysqlConnection,
    PostgresqlConnection,
    RedshiftConnection,
    SnowflakeConnectionUserPassword,
    SQLServerConnection,
)


class InitTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args

    def run(self):
        # Check if the .morph directory exists in the user's home directory; create it if not
        morph_dir = MorphConstant.INIT_DIR
        if not os.path.exists(morph_dir):
            os.makedirs(morph_dir)
            click.echo(f"\nCreated directory at {morph_dir}")

        click.echo("Select your database type:")
        db_mapping = {
            "1": "PostgreSQL",
            "2": "MySQL",
            "3": "Redshift",
            "4": "SQLServer",
            "5": "Snowflake (User/Password)",
            "6": "BigQuery (Service Account)",
        }
        for key, value in db_mapping.items():
            click.echo(f"{key}. {value}")

        db_type = input("Enter the number corresponding to your database type: ")

        click.echo(f"\n{db_mapping[db_type]} selected.\n")

        connection: Optional[DatabaseConnection] = None
        if db_type == "1":
            slug = input("Create a slug for your connection: ")
            host = (
                input("Enter your PostgreSQL host (default: localhost): ")
                or "localhost"
            )
            user = input("Enter your PostgreSQL username: ")
            password = input("Enter your PostgreSQL password: ")
            port = input("Enter your PostgreSQL port (default: 5432): ") or "5432"
            db_name = input("Enter your PostgreSQL database name: ")
            schema = (
                input("Enter your PostgreSQL schema name (default: public): ")
                or "public"
            )
            is_ssh = input("Select if you are using SSH tunneling (y/n): ")
            if is_ssh == "y":
                ssh_host = input("Enter your SSH host: ")
                ssh_user = input("Enter your SSH username:  ")
                ssh_password = input("Enter your SSH password: ")
                ssh_port = input("Enter your SSH port (default: 22): ") or "22"
                ssh_private_key = input("Enter your SSH private key path: ")

                connection = PostgresqlConnection(
                    type=CONNECTION_TYPE.postgres,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    schema=schema,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_password=ssh_password,
                    ssh_port=int(ssh_port) if ssh_port else None,
                    ssh_private_key=ssh_private_key,
                )
            else:
                connection = PostgresqlConnection(
                    type=CONNECTION_TYPE.postgres,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    schema=schema,
                )
        elif db_type == "2":
            slug = input("Create a slug for your connection: ")
            host = input("Enter your MySQL host (default: localhost): ") or "localhost"
            user = input("Enter your MySQL username: ")
            password = input("Enter your MySQL password: ")
            port = input("Enter your MySQL port (default: 3306): ") or "3306"
            db_name = input("Enter your MySQL database name: ")
            is_ssh = input("Select if you are using SSH tunneling (y/n): ")
            if is_ssh == "y":
                ssh_host = input("Enter your SSH host: ")
                ssh_user = input("Enter your SSH username: ")
                ssh_password = input("Enter your SSH password: ")
                ssh_port = input("Enter your SSH port (default: 22): ") or "22"
                ssh_private_key = input("Enter your SSH private key path: ")

                connection = MysqlConnection(
                    type=CONNECTION_TYPE.mysql,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_password=ssh_password,
                    ssh_port=int(ssh_port) if ssh_port else None,
                    ssh_private_key=ssh_private_key,
                )
            else:
                connection = MysqlConnection(
                    type=CONNECTION_TYPE.mysql,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                )
        elif db_type == "3":
            slug = input("Create a slug for your connection: ")
            host = (
                input("Enter your Redshift host (default: localhost): ") or "localhost"
            )
            user = input("Enter your Redshift username: ")
            password = input("Enter your Redshift password: ")
            port = input("Enter your Redshift port (default: 5439): ") or "5439"
            db_name = input("Enter your Redshift database name: ")
            schema = (
                input("Enter your Redshift schema name (default: public): ") or "public"
            )
            is_ssh = input("Select if you are using SSH tunneling (y/n): ")
            if is_ssh == "y":
                ssh_host = input("Enter your SSH host: ")
                ssh_user = input("Enter your SSH username: ")
                ssh_password = input("Enter your SSH password: ")
                ssh_port = input("Enter your SSH port (default: 22): ") or "22"
                ssh_private_key = input("Enter your SSH private key path: ")

                connection = RedshiftConnection(
                    type=CONNECTION_TYPE.redshift,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    schema=schema,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_password=ssh_password,
                    ssh_port=int(ssh_port) if ssh_port else None,
                    ssh_private_key=ssh_private_key,
                )
            else:
                connection = RedshiftConnection(
                    type=CONNECTION_TYPE.redshift,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    schema=schema,
                )
        elif db_type == "4":
            slug = input("Create a slug for your connection: ")
            host = (
                input("Enter your SQLServer host (default: localhost): ") or "localhost"
            )
            user = input("Enter your SQLServer username: ")
            password = input("Enter your SQLServer password: ")
            port = input("Enter your SQLServer port (default: 1433): ") or "1433"
            db_name = input("Enter your SQLServer database name: ")
            is_ssh = input("Select if you are using SSH tunneling (y/n): ")
            if is_ssh == "y":
                ssh_host = input("Enter your SSH host: ")
                ssh_user = input("Enter your SSH username: ")
                ssh_password = input("Enter your SSH password: ")
                ssh_port = input("Enter your SSH port (default: 22): ") or "22"
                ssh_private_key = input("Enter your SSH private key path: ")

                connection = SQLServerConnection(
                    type=CONNECTION_TYPE.mssql,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                    ssh_host=ssh_host,
                    ssh_user=ssh_user,
                    ssh_password=ssh_password,
                    ssh_port=int(ssh_port) if ssh_port else None,
                    ssh_private_key=ssh_private_key,
                )
            else:
                connection = SQLServerConnection(
                    type=CONNECTION_TYPE.mssql,
                    host=host,
                    user=user,
                    password=password,
                    port=int(port),
                    dbname=db_name,
                )
        elif db_type == "5":
            slug = input("Create a slug for your connection: ")
            account = input("Enter your Snowflake account: ")
            database = input("Enter your Snowflake database name: ")
            user = input("Enter your Snowflake username: ")
            password = input("Enter your Snowflake password: ")
            role = input("Enter your Snowflake role name: ")
            warehouse = input("Enter your Snowflake warehouse: ")
            schema = input("Enter your Snowflake schema name (optional): ")

            connection = SnowflakeConnectionUserPassword(
                type=CONNECTION_TYPE.snowflake,
                method=CONNECTION_DETAIL_TYPE.snowflake_user_password,
                account=account,
                database=database,
                user=user,
                password=password,
                role=role,
                warehouse=warehouse,
                schema=schema,
            )
        elif db_type == "6":
            slug = input("Create a slug for your connection: ")
            project = input("Enter your BigQuery project ID: ")
            keyfile = input("Enter your BigQuery keyfile path: ")
            dataset = input("Enter your BigQuery dataset name (Optional): ")
            location = input("Enter your BigQuery location (Optional): ")

            connection = BigqueryConnectionServiceAccount(
                type=CONNECTION_TYPE.bigquery,
                method=CONNECTION_DETAIL_TYPE.bigquery_service_account,
                project=project,
                keyfile=keyfile,
                dataset=dataset,
                location=location,
            )
        else:
            click.echo(
                click.style(
                    "Invalid database type. Please select a valid database type.",
                    fg="red",
                )
            )
            exit(1)

        connection_yaml = ConnectionYaml.load_yaml()
        connection_yaml.add_connections({slug: connection})
        connection_yaml.save_yaml(True)

        click.echo(
            click.style(
                "Successfully initialized! 🎉",
                fg="green",
            )
        )
        click.echo(
            click.style(
                f"You can edit your connection details in `{MorphConstant.INIT_DIR}/connections.yml`",
                fg="green",
            )
        )
