import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import click
import pandas as pd
import pydantic
from dotenv import dotenv_values, load_dotenv
from tabulate import tabulate

from morph.cli.flags import Flags
from morph.config.project import MorphProject, load_project
from morph.task.base import BaseTask
from morph.task.utils.logging import get_morph_logger
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.errors import (
    MorphFunctionLoadError,
    logging_file_error_exception,
)
from morph.task.utils.run_backend.execution import RunDagArgs, run_cell
from morph.task.utils.run_backend.output import (
    finalize_run,
    is_async_generator,
    is_generator,
    is_stream,
    stream_and_write,
    stream_and_write_and_response,
)
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObject,
    MorphFunctionMetaObjectCacheManager,
    MorphGlobalContext,
)
from morph.task.utils.run_backend.types import RunStatus


class RunTask(BaseTask):
    def __init__(self, args: Flags, mode: Literal["cli", "api"] = "cli"):
        super().__init__(args)

        # class state
        self.final_state: Optional[str] = None
        self.error: Optional[str] = None
        self.output_paths: Optional[List[str]] = None

        # parse arguments
        filename_or_alias: str = os.path.normpath(args.FILENAME)
        self.run_id: str = self.args.RUN_ID or f"{int(time.time() * 1000)}"
        self.is_dag: bool = args.DAG or False
        self.vars: Dict[str, Any] = args.DATA
        self.is_filepath = os.path.splitext(os.path.basename(filename_or_alias))[1]
        self.mode = mode
        self.api_key = ""

        try:
            start_dir = filename_or_alias if os.path.isabs(filename_or_alias) else "./"
            self.project_root = find_project_root_dir(start_dir)
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red", bg="yellow"))
            sys.exit(1)  # 1: General errors

        self.project: Optional[MorphProject] = load_project(find_project_root_dir())
        if self.project is None:
            click.echo(
                click.style(
                    "Error: Could not found morph_project.yml", fg="red", bg="yellow"
                )
            )
            sys.exit(1)  # 1: General errors
        if self.project.project_id is not None:
            os.environ["MORPH_PROJECT_ID"] = self.project.project_id

        # load .env in project root
        dotenv_path = os.path.join(self.project_root, ".env")
        load_dotenv(dotenv_path)
        env_vars = dotenv_values(dotenv_path)
        for e_key, e_val in env_vars.items():
            os.environ[e_key] = str(e_val)

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
        self.meta_obj_cache = MorphFunctionMetaObjectCacheManager().get_cache()

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
                if sys.platform == "win32":
                    if len(resource.id.split(":")) > 2:
                        self.filename = (
                            resource.id.rsplit(":", 1)[0] if resource.id else ""
                        )
                    else:
                        self.filename = resource.id if resource.id else ""
                else:
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
        self.logger = get_morph_logger()

    def run(self) -> Any:
        if self.ext != ".sql" and self.ext != ".py":
            self.error = "Invalid file type. Please specify a .sql or .py file."
            self.logger.error(self.error)
            self.final_state = RunStatus.FAILED.value
            if self.mode == "cli":
                self.output_paths = finalize_run(
                    self.resource,
                    None,
                    self.logger,
                )
            return

        if not self.resource.name or not self.resource.id:
            raise FileNotFoundError(f"Invalid metadata: {self.resource}")

        # id is formatted as {filename}:{function_name}
        if sys.platform == "win32":
            if len(self.resource.id.split(":")) > 2:
                filepath = (
                    self.resource.id.rsplit(":", 1)[0] if self.resource.id else ""
                )
            else:
                filepath = self.resource.id if self.resource.id else ""
        else:
            filepath = self.resource.id.split(":")[0]

        if self.mode == "cli":
            self.logger.info(
                f"Running {self.ext[1:]} file: {filepath}, variables: {self.vars}"
            )

        try:
            dag = RunDagArgs(run_id=self.run_id) if self.is_dag else None
            output = run_cell(
                self.project,
                self.resource,
                self.vars,
                self.logger,
                dag,
                self.meta_obj_cache,
                self.mode,
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
            self.error = text
            self.logger.error(self.error)
            click.echo(click.style(self.error, fg="red"))
            self.final_state = RunStatus.FAILED.value
            if self.mode == "cli":
                self.output_paths = finalize_run(
                    self.resource,
                    None,
                    self.logger,
                )
            elif self.mode == "api":
                raise Exception(text)
            return

        # print preview of the DataFrame
        if self.mode == "cli":
            if isinstance(output.result, pd.DataFrame):
                preview = tabulate(
                    output.result.head().values.tolist(),
                    headers=output.result.columns.tolist(),
                    tablefmt="grid",
                    showindex=True,
                )
                self.logger.info("DataFrame preview:\n" + preview)
            else:
                self.logger.info("Output: " + str(output.result))

        if (
            is_stream(output.result)
            or is_async_generator(output.result)
            or is_generator(output.result)
        ):
            if self.mode == "api":
                return stream_and_write_and_response(
                    output.result,
                    self.logger,
                )
            else:
                stream_and_write(
                    self.resource,
                    output.result,
                    self.logger,
                )
        else:
            self.final_state = RunStatus.DONE.value
            if self.mode == "cli":
                self.output_paths = finalize_run(
                    self.resource,
                    output.result,
                    self.logger,
                )
            else:
                return output.result
        if self.mode == "cli":
            self.logger.info(f"Successfully ran file 🎉: {filepath}")
