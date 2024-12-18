import configparser
import os
from typing import Any, List, Optional

import click
import pandas as pd
from colorama import Fore, Style

from morph.cli.flags import Flags
from morph.config.project import MorphProject, load_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.connection import CONNECTION_TYPE, Connection, ConnectionYaml
from morph.task.utils.connections.connector import Connector
from morph.task.utils.knowledge.inspection import (
    KnowledgeScanResult,
    MorphKnowledgeMetaObject,
    MorphKnowledgeMetaObjectSource,
)
from morph.task.utils.knowledge.state import MorphKnowledgeManager
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.errors import logging_file_error_exception
from morph.task.utils.run_backend.execution import run_cell
from morph.task.utils.run_backend.state import MorphGlobalContext
from morph.task.utils.sqlite import SqliteDBManager


class TestTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.alias: str = args.ALIAS
        self.no_cache: bool = args.NO_CACHE
        self.vars: dict[str, Any] = args.DATA

        config_path = MorphConstant.MORPH_CRED_PATH
        if not os.path.exists(config_path):
            click.echo(
                click.style(
                    f"Error: No credentials found in {config_path}.",
                    fg="red",
                    bg="yellow",
                )
            )
            return
        config = configparser.ConfigParser()
        config.read(config_path)
        if not config.sections():
            click.echo(
                click.style(
                    f"Error: No credentials entries found in {config_path}.",
                    fg="red",
                    bg="yellow",
                )
            )
            return
        self.workspace_id: str = config.get(
            "default", "workspace_id", fallback=""
        ) or config.get("default", "database_id", fallback="")

        try:
            self.project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            return

        self.db_manager = SqliteDBManager(self.project_root)
        self.db_manager.initialize_database()
        self.project: Optional[MorphProject] = load_project(find_project_root_dir())

    def run(self):
        manager = MorphKnowledgeManager.get_instance()
        errors = manager.load(self.project_root)

        if errors:
            click.echo(click.style("Failed to load knowledge.", fg="red"))
            for error in errors:
                click.echo(click.style(str(error), fg="red"))
            return

        knowledge = manager.find(self.alias)

        if knowledge is None:
            context = MorphGlobalContext.get_instance()
            errors = context.partial_load(
                self.project_root,
                self.alias,
            )
            if len(errors) > 0:
                click.echo(
                    click.style(
                        f"Error: Failed to load morph functions [{errors}]", fg="red"
                    )
                )
                return

            resource = context.search_meta_object_by_name(self.alias)
            if resource is not None:
                file_path = resource.id.split(":")[0]
                knowledge = KnowledgeScanResult(
                    spec=MorphKnowledgeMetaObject(
                        id=resource.id,
                        name=resource.name,
                        type="model",
                        title=resource.title,
                        description=resource.description,
                        source=MorphKnowledgeMetaObjectSource(
                            name=resource.name,
                            connection=resource.connection,
                        ),
                        schemas=resource.schemas,
                        terms=resource.terms,
                    ),
                    file_path=file_path,
                    checksum="",
                )

        if knowledge is None:
            click.echo(click.style(f"Knowledge '{self.alias}' not found.", fg="red"))
            return
        elif (
            knowledge.spec.schemas is None
            or len(knowledge.spec.schemas) < 1
            or knowledge.spec.type == "glossary"
        ):
            click.echo(
                click.style(
                    f"Knowledge '{self.alias}' has no schemas to test.", fg="red"
                )
            )
            return

        not_null_columns: List[str] = []
        unique_columns: List[str] = []
        for schema in knowledge.spec.schemas:
            if schema.test is not None:
                for test in schema.test:
                    if test == "not_null":
                        not_null_columns.append(schema.name)
                    elif test == "unique":
                        unique_columns.append(schema.name)
        if len(not_null_columns) < 1 and len(unique_columns) < 1:
            click.echo(
                click.style(
                    f"Knowledge '{knowledge.spec.name}' has no tests to run.",
                    fg="red",
                )
            )
            return

        test_result = False
        if knowledge.spec.type == "model":
            test_result = self._test_model(knowledge, not_null_columns, unique_columns)
        elif knowledge.spec.type == "datasource":
            test_result = self._test_datasource(
                knowledge, not_null_columns, unique_columns
            )

        passed_tests = 1 if test_result else 0
        failed_tests = 0 if test_result else 1
        if test_result:
            click.echo(f"{Fore.GREEN}✔ {self.alias} - PASSED{Style.RESET_ALL}")
        else:
            click.echo(f"{Fore.RED}✘ {self.alias} - FAILED{Style.RESET_ALL}")
        click.echo(
            f"\n{Fore.CYAN}Summary: {passed_tests} passed, {failed_tests} failed{Style.RESET_ALL}"
        )

    def _test_model(
        self,
        knowledge: KnowledgeScanResult,
        not_null_columns: List[str],
        unique_columns: List[str],
    ) -> bool:
        context = MorphGlobalContext.get_instance()
        resource = context.search_meta_object_by_name(knowledge.spec.name)
        if resource is None:
            click.echo(
                click.style(
                    f"Resource '{knowledge.spec.name}' not found.",
                    fg="red",
                )
            )
            return False
        filepath = resource.id.split(":")[0]

        try:
            output = run_cell(
                self.project,
                resource,
                self.workspace_id,
                self.db_manager,
                self.vars,
            )
        except Exception as e:
            click.echo(
                click.style(
                    f"Error: {e}",
                    fg="red",
                )
            )
            return False

        if not isinstance(output.result, pd.DataFrame):
            click.echo(
                click.style(
                    f"Error: Output is not a pandas DataFrame.",
                    fg="red",
                )
            )
            return False

        df = pd.DataFrame(output.result)
        if len(not_null_columns) > 0:
            for column in not_null_columns:
                try:
                    if df[column].isnull().any():
                        click.echo(
                            click.style(
                                f"Column '{column}' has null values.",
                                fg="red",
                            )
                        )
                        return False
                except Exception as e:
                    click.echo(
                        click.style(
                            f"Error: {logging_file_error_exception(e, filepath)}",
                            fg="red",
                        )
                    )
                    return False
        if len(unique_columns) > 0:
            for column in unique_columns:
                try:
                    if df[column].duplicated().any():
                        click.echo(
                            click.style(
                                f"Column '{column}' has duplicated values.",
                                fg="red",
                            )
                        )
                        return False
                except Exception as e:
                    click.echo(
                        click.style(
                            f"Error: {logging_file_error_exception(e, filepath)}",
                            fg="red",
                        )
                    )
                    return False
        return True

    def _test_datasource(
        self,
        knowledge: KnowledgeScanResult,
        not_null_columns: List[str],
        unique_columns: List[str],
    ) -> bool:
        if knowledge.spec.source is None:
            click.echo(
                click.style(
                    f"Knowledge '{knowledge.spec.name}' has no source to test.",
                    fg="red",
                )
            )
            return False

        connection: Optional[Connection] = None
        if knowledge.spec.source.connection is not None:
            connection = ConnectionYaml.find_cloud_connection(
                knowledge.spec.source.connection
            )
        else:
            connection_yaml = ConnectionYaml.load_yaml()
            connection = ConnectionYaml.find_connection(
                connection_yaml, self.workspace_id
            )
            if connection is None:
                db, connection = ConnectionYaml.find_builtin_db_connection()
                connection_yaml.add_connections({db: connection})
                connection_yaml.save_yaml(True)

        connector = Connector("", connection, True)
        if len(not_null_columns) > 0:
            sql = self._generate_not_null_sql(
                knowledge.spec.source.name, not_null_columns, connection
            )
            try:
                output = connector.execute_sql(sql)
            except Exception as e:
                click.echo(
                    click.style(
                        f"Error: {e}",
                        fg="red",
                    )
                )
                return False
            if len(output) > 0:
                click.echo(
                    click.style(
                        f"Columns '{output.columns}' have null values.",
                        fg="red",
                    )
                )
                return False
        if len(unique_columns) > 0:
            for unique_column in unique_columns:
                sql = self._generate_unique_sql(
                    knowledge.spec.source.name, unique_column, connection
                )
                try:
                    output = connector.execute_sql(sql)
                except Exception as e:
                    click.echo(
                        click.style(
                            f"Error: {e}",
                            fg="red",
                        )
                    )
                    return False
                if len(output) > 0:
                    click.echo(
                        click.style(
                            f"Column '{unique_column}' has duplicated values.",
                            fg="red",
                        )
                    )
                    return False
        return True

    def _generate_not_null_sql(
        self, table: str, columns: List[str], connection: Connection
    ) -> str:
        if (
            connection is None
            or connection.type == CONNECTION_TYPE.postgres
            or connection.type == CONNECTION_TYPE.redshift
        ):
            where_clause = " OR ".join([f'"{column}" IS NULL' for column in columns])
            return f'SELECT * FROM "{table}" WHERE {where_clause}'
        elif connection.type == CONNECTION_TYPE.mysql:
            where_clause = " OR ".join([f"`{column}` IS NULL" for column in columns])
            return f"SELECT * FROM `{table}` WHERE {where_clause}"
        elif connection.type == CONNECTION_TYPE.bigquery:
            where_clause = " OR ".join([f"{column} IS NULL" for column in columns])
            if "." in table:
                table = f"{connection.project}.{table}"
            else:
                table = f"{connection.project}.{connection.dataset}.{table}"
            return f"SELECT * FROM `{table}` WHERE {where_clause}"
        elif connection.type == CONNECTION_TYPE.snowflake:
            where_clause = " OR ".join([f"{column} IS NULL" for column in columns])
            if "." in table:
                schema_ = table.split(".")[0]
                table_ = table.split(".")[1]
                table = f'"{connection.database}"."{schema_}"."{table_}"'
            else:
                table = f'"{connection.database}"."{connection.schema_}"."{table}"'
            return f"SELECT * FROM {table} WHERE {where_clause}"
        elif connection.type == CONNECTION_TYPE.athena:
            where_clause = " OR ".join([f"{column} IS NULL" for column in columns])
            if "." in table:
                table = ".".join([f'"{part}"' for part in table.split(".")])
            else:
                table = f'"{connection.database}"."{table}"'
            return f"SELECT * FROM {table} WHERE {where_clause}"
        else:
            click.echo(
                click.style(
                    f"Unsupported connection {connection.type}.",
                    fg="red",
                )
            )
            raise click.Abort()

    def _generate_unique_sql(
        self, table: str, column: str, connection: Connection
    ) -> str:
        if (
            connection is None
            or connection.type == CONNECTION_TYPE.postgres
            or connection.type == CONNECTION_TYPE.redshift
        ):
            return f'SELECT "{column}", COUNT(*) FROM "{table}" GROUP BY "{column}" HAVING COUNT(*) > 1'
        elif connection.type == CONNECTION_TYPE.mysql:
            return f"SELECT `{column}`, COUNT(*) FROM `{table}` GROUP BY `{column}` HAVING COUNT(*) > 1"
        elif connection.type == CONNECTION_TYPE.bigquery:
            if "." in table:
                table = f"{connection.project}.{table}"
            else:
                table = f"{connection.project}.{connection.dataset}.{table}"
            return f"SELECT {column}, COUNT(*) FROM `{table}` GROUP BY {column} HAVING COUNT(*) > 1"
        elif connection.type == CONNECTION_TYPE.snowflake:
            if "." in table:
                schema_ = table.split(".")[0]
                table_ = table.split(".")[1]
                table = f'"{connection.database}"."{schema_}"."{table_}"'
            else:
                table = f'"{connection.database}"."{connection.schema_}"."{table}"'
            return f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} HAVING COUNT(*) > 1"
        elif connection.type == CONNECTION_TYPE.athena:
            if "." in table:
                table = ".".join([f'"{part}"' for part in table.split(".")])
            else:
                table = f'"{connection.database}"."{table}"'
            return f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} HAVING COUNT(*) > 1"
        else:
            click.echo(
                click.style(
                    f"Unsupported connection {connection.type}.",
                    fg="red",
                )
            )
            raise click.Abort()
