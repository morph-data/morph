import configparser
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import click
import pydantic
from dotenv import dotenv_values, load_dotenv

from morph.api.cloud.client import MorphApiClient, MorphApiKeyClientImpl
from morph.api.cloud.types import EnvVarList
from morph.api.cloud.utils import is_cloud
from morph.cli.flags import Flags
from morph.config.project import (
    MorphProject,
    default_initial_project,
    load_project,
    save_project,
)
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.connection import MORPH_BUILTIN_DB_CONNECTION_SLUG
from morph.task.utils.logging import get_morph_logger
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.errors import (
    MorphFunctionLoadError,
    logging_file_error_exception,
)
from morph.task.utils.run_backend.execution import (
    RunDagArgs,
    generate_variables_hash,
    run_cell,
)
from morph.task.utils.run_backend.output import (
    finalize_run,
    is_async_generator,
    is_generator,
    is_stream,
    stream_and_write,
    stream_and_write_and_response,
    transform_output,
)
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObject,
    MorphGlobalContext,
    load_cache,
)
from morph.task.utils.sqlite import CliError, RunStatus, SqliteDBManager
from morph.task.utils.timezone import TimezoneManager


class RunTask(BaseTask):
    def __init__(self, args: Flags, mode: Optional[Literal["cli", "api"]] = "cli"):
        super().__init__(args)

        # parse arguments
        filename_or_alias: str = os.path.normpath(args.FILENAME)
        self.run_id: str = self.args.RUN_ID or f"{int(time.time() * 1000)}"
        self.is_dag: bool = args.DAG or False
        self.vars: Dict[str, Any] = args.DATA
        self.is_filepath = os.path.splitext(os.path.basename(filename_or_alias))[1]
        self.mode = mode

        # validate credentials
        config_path = MorphConstant.MORPH_CRED_PATH
        has_config = os.path.exists(config_path)
        if is_cloud() and not has_config:
            click.echo(
                click.style(
                    f"Error: No credentials found in {config_path}.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

        if has_config:
            # read credentials
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
                sys.exit(1)  # 1: General errors

            self.team_slug: str = config.get("default", "team_slug", fallback="")
            self.app_url: str = config.get("default", "app_url", fallback="")
            self.workspace_id: str = config.get(
                "default", "workspace_id", fallback=""
            ) or config.get("default", "database_id", fallback="")
            self.api_key: str = config.get("default", "api_key", fallback="")

            # env variable configuration
            os.environ["MORPH_WORKSPACE_ID"] = self.workspace_id
            os.environ["MORPH_BASE_URL"] = self.app_url
            os.environ["MORPH_TEAM_SLUG"] = self.team_slug
            os.environ["MORPH_API_KEY"] = self.api_key

        try:
            start_dir = filename_or_alias if os.path.isabs(filename_or_alias) else "./"
            self.project_root = find_project_root_dir(start_dir)
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red", bg="yellow"))
            sys.exit(1)  # 1: General errors

        self.project: Optional[MorphProject] = load_project(find_project_root_dir())
        if self.project is None:
            self.project = default_initial_project()
        if self.project.default_connection is None:
            self.project.default_connection = MORPH_BUILTIN_DB_CONNECTION_SLUG
        save_project(self.project_root, self.project)

        if not has_config:
            self.workspace_id = self.project.default_connection

        # Initialize database
        self.db_manager = SqliteDBManager(self.project_root)
        self.db_manager.initialize_database()

        context = MorphGlobalContext.get_instance()
        try:
            errors = context.partial_load(
                self.project_root,
                (
                    str(Path(filename_or_alias).resolve())
                    if self.is_filepath
                    else filename_or_alias
                ),
            )
        except (pydantic.ValidationError, json.decoder.JSONDecodeError):
            click.echo(
                click.style(
                    "Warning: Morph-cli project cache is corrupted. Recompiling...",
                    fg="yellow",
                ),
                err=False,
            )
            errors = context.load(self.project_root)
            context.dump()
        self.meta_obj_cache = load_cache(self.project_root)

        if len(errors) > 0:
            if self.mode == "api":
                raise ValueError(MorphFunctionLoadError.format_errors(errors))
            click.echo(
                click.style(
                    MorphFunctionLoadError.format_errors(errors),
                    fg="red",
                    bg="yellow",
                ),
                err=True,
            )
            sys.exit(1)  # 1: General errors

        resource: Optional[MorphFunctionMetaObject] = None
        if self.is_filepath:
            self.filename = str(Path(filename_or_alias).resolve())
            if not os.path.isfile(self.filename):
                click.echo(
                    click.style(
                        f"Error: File {self.filename} not found.",
                        fg="red",
                        bg="yellow",
                    ),
                    err=True,
                )
                sys.exit(2)  # 2: Misuse of shell builtins
            resources = context.search_meta_objects_by_path(self.filename)
            if len(resources) > 0:
                resource = resources[0]
        else:
            resource = context.search_meta_object_by_name(filename_or_alias)
            if resource is not None:
                # id is formatted as {filename}:{function_name}
                self.filename = str(resource.id).split(":")[0]

        if resource is None:
            if self.mode == "api":
                raise ValueError(
                    f"A resource with alias {filename_or_alias} not found."
                )
            click.echo(
                click.style(
                    f"Error: A resource with alias {filename_or_alias} not found.",
                    fg="red",
                    bg="yellow",
                ),
                err=True,
            )
            sys.exit(2)  # 2: Misuse of shell builtins

        self.resource = resource
        self.ext = os.path.splitext(os.path.basename(self.filename))[1]
        self.cell_alias = str(self.resource.name)

        # Set up run directory
        self.runs_dir = os.path.normpath(
            os.path.join(
                self.project_root,
                ".morph/runs",
                self.run_id,
            )
        )
        if not os.path.exists(self.runs_dir):
            os.makedirs(self.runs_dir)

        # Set up logger
        log_filename = f"{os.path.splitext(os.path.basename(self.cell_alias))[0]}.log"
        self.log_path = os.path.join(self.runs_dir, log_filename)
        self.logger = get_morph_logger(self.log_path)

        # load .env in project root and set timezone
        if is_cloud():
            client = MorphApiClient(MorphApiKeyClientImpl)
            cloud_env_vars = client.req.list_env_vars().to_model(EnvVarList)
            if cloud_env_vars:
                for cloud_env_var in cloud_env_vars.items:
                    os.environ[cloud_env_var.key] = cloud_env_var.value
        else:
            dotenv_path = os.path.join(self.project_root, ".env")
            load_dotenv(dotenv_path)
            env_vars = dotenv_values(dotenv_path)
            for e_key, e_val in env_vars.items():
                os.environ[e_key] = str(e_val)
        desired_tz = os.getenv("TZ")
        if desired_tz is not None:
            tz_manager = TimezoneManager()
            if not tz_manager.is_valid_timezone(desired_tz):
                self.logger.warning(
                    f"Invalid TZ value in .env. Falling back to {tz_manager.get_current_timezone()}."
                )
            if desired_tz != tz_manager.get_current_timezone():
                tz_manager.set_timezone(desired_tz)

    def run(self) -> Any:
        cached_cell = (
            self.meta_obj_cache.find_by_name(self.cell_alias)
            if self.meta_obj_cache
            else None
        )

        self.db_manager.insert_run_record(
            self.run_id,
            self.cell_alias,
            self.is_dag,
            self.log_path,
            cached_cell.checksum if cached_cell else None,
            generate_variables_hash(self.vars),
            self.vars,
        )

        if self.ext != ".sql" and self.ext != ".py":
            text = "Invalid file type. Please specify a .sql or .py file."
            self.logger.error(text)
            finalize_run(
                self.project,
                self.db_manager,
                self.resource,
                self.cell_alias,
                RunStatus.FAILED.value,
                None,
                self.logger,
                self.run_id,
                CliError(
                    type="general",
                    details=text,
                ),
            )
            return
        else:
            if not self.resource.name or not self.resource.id:
                raise FileNotFoundError(f"Invalid metadata: {self.resource}")

            cell = self.resource.name
            # id is formatted as {filename}:{function_name}
            filepath = self.resource.id.split(":")[0]
            self.logger.info(
                f"Running {self.ext[1:]} file: {filepath}, variables: {self.vars}"
            )

            try:
                dag = (
                    RunDagArgs(run_id=self.run_id, runs_dir=self.runs_dir)
                    if self.is_dag
                    else None
                )
                output = run_cell(
                    self.project,
                    self.resource,
                    self.workspace_id,
                    self.db_manager,
                    self.vars,
                    self.logger,
                    dag,
                    self.meta_obj_cache,
                )
            except Exception as e:
                if self.is_dag:
                    text = str(e)
                else:
                    error_txt = (
                        logging_file_error_exception(e, filepath)
                        if self.ext == ".py"
                        else str(e)
                    )
                    text = f"An error occurred while running the file 💥: {error_txt}"
                self.logger.error(text)
                click.echo(click.style(text, fg="red"))
                finalize_run(
                    self.project,
                    self.db_manager,
                    self.resource,
                    cell,
                    RunStatus.FAILED.value,
                    None,
                    self.logger,
                    self.run_id,
                    CliError(
                        type="general",
                        details=text,
                    ),
                )
                if self.mode == "api":
                    raise Exception(text)
                return

            if (
                is_stream(output.result)
                or is_async_generator(output.result)
                or is_generator(output.result)
            ):
                if self.mode == "api":
                    return stream_and_write_and_response(
                        self.project,
                        self.db_manager,
                        self.resource,
                        cell,
                        RunStatus.DONE.value,
                        transform_output(self.resource, output.result),
                        self.logger,
                        self.run_id,
                        None,
                    )
                else:
                    stream_and_write(
                        self.project,
                        self.db_manager,
                        self.resource,
                        cell,
                        RunStatus.DONE.value,
                        transform_output(self.resource, output.result),
                        self.logger,
                        self.run_id,
                        None,
                    )
            else:
                finalize_run(
                    self.project,
                    self.db_manager,
                    self.resource,
                    cell,
                    RunStatus.DONE.value,
                    transform_output(self.resource, output.result),
                    self.logger,
                    self.run_id,
                    None,
                )
            self.logger.info(f"Successfully ran file 🎉: {filepath}")
