from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Callable, List, Literal, Optional, Union

import pandas as pd
from jinja2 import BaseLoader, Environment
from morph_lib.error import RequestError
from pydantic import BaseModel

from morph.config.project import MorphProject
from morph.task.utils.connection import Connection, ConnectionYaml, DatabaseConnection
from morph.task.utils.connections.connector import Connector
from morph.task.utils.logging import get_morph_logger
from morph.task.utils.run_backend.errors import logging_file_error_exception
from morph.task.utils.run_backend.output import (
    convert_run_result,
    finalize_run,
    is_async_generator,
    is_generator,
    is_stream,
    stream_and_write,
)

from .cache import ExecutionCache
from .state import (
    MorphFunctionMetaObject,
    MorphFunctionMetaObjectCache,
    MorphGlobalContext,
)

# -----------------------------------------------------
# Global cache instance used throughout the module
# -----------------------------------------------------
execution_cache = ExecutionCache()


class RunDagArgs(BaseModel):
    run_id: str


class RunCellResult(BaseModel):
    result: Any
    is_cache_valid: Optional[bool] = True


def run_cell(
    project: Optional[MorphProject],
    cell: str | MorphFunctionMetaObject,
    vars: dict[str, Any] = {},
    logger: logging.Logger | None = None,
    dag: Optional[RunDagArgs] = None,
    meta_obj_cache: Optional[MorphFunctionMetaObjectCache] = None,
    mode: Literal["cli", "api"] = "api",
) -> RunCellResult:
    context = MorphGlobalContext.get_instance()

    # Resolve the meta object
    if isinstance(cell, str):
        meta_obj = context.search_meta_object_by_name(cell)
        if meta_obj is None:
            raise ValueError("Not registered as a Morph function.")
    else:
        meta_obj = cell

    if meta_obj.id is None:
        raise ValueError(f"Invalid metadata: {meta_obj}")

    # Attempt to get cached cell from meta_obj_cache
    # cached_cell = meta_obj_cache.find_by_name(meta_obj.name) if meta_obj_cache else None
    # is_cache_valid = True

    # If SQL, register data requirements
    ext = meta_obj.id.split(".")[-1]
    if ext == "sql":
        _regist_sql_data_requirements(meta_obj)
        meta_obj = context.search_meta_object_by_name(meta_obj.name or "")
        if meta_obj is None:
            raise ValueError("Not registered as a Morph function.")

    # Handle dependencies
    required_data = meta_obj.data_requirements or []
    for data_name in required_data:
        required_meta_obj = context.search_meta_object_by_name(data_name)
        if required_meta_obj is None:
            raise ValueError(
                f"Required data '{data_name}' is not registered as a Morph function."
            )

        if dag:
            required_data_result = _run_cell_with_dag(
                project, required_meta_obj, vars, dag, meta_obj_cache, mode
            )
        else:
            required_data_result = run_cell(
                project, required_meta_obj, vars, logger, None, meta_obj_cache, mode
            )
        # is_cache_valid = required_data_result.is_cache_valid or True
        context._add_data(data_name, required_data_result.result)

    # register variables to context
    context._clear_var()
    for var_name, var_value in vars.items():
        is_valid_var = True
        for var_name_, var_options in (meta_obj.variables or {}).items():
            if var_name == var_name_:
                if (
                    var_options
                    and "type" in var_options
                    and var_options.get("type", None) is not None
                ):
                    if var_options["type"] == "bool" and not isinstance(
                        var_value, bool
                    ):
                        is_valid_var = False
                        break
                    elif var_options["type"] == "int" and not isinstance(
                        var_value, int
                    ):
                        is_valid_var = False
                        break
                    elif var_options["type"] == "float" and not isinstance(
                        var_value, float
                    ):
                        is_valid_var = False
                        break
                    elif var_options["type"] == "dict" and not isinstance(
                        var_value, dict
                    ):
                        is_valid_var = False
                        break
                    elif var_options["type"] == "list" and not isinstance(
                        var_value, list
                    ):
                        is_valid_var = False
                        break
                    elif var_options["type"] == "str" and not isinstance(
                        var_value, str
                    ):
                        is_valid_var = False
                        break
        if is_valid_var:
            context._add_var(var_name, var_value)
        else:
            raise RequestError(f"Variable '{var_name}' is type invalid.")

    for var_name, var_options in (meta_obj.variables or {}).items():
        if var_name not in vars:
            if (
                var_options
                and "required" in var_options
                and var_options["required"]
                and var_options.get("type", None) is not None
            ):
                raise RequestError(f"Variable '{var_name}' is required.")
            if var_options and "default" in var_options:
                context._add_var(var_name, var_options["default"])
        else:
            if (
                var_options
                and "required" in var_options
                and var_options["required"]
                and vars[var_name] is None
            ):
                raise RequestError(f"Variable '{var_name}' is required.")

    # ------------------------------------------------------------------
    # Actual execution
    # ------------------------------------------------------------------
    if ext == "sql":
        if logger and mode == "cli":
            logger.info(f"Formatting SQL file: {meta_obj.id} with variables: {vars}")
        sql_text = _fill_sql(meta_obj, vars)
        result_df = _run_sql(project, meta_obj, sql_text, logger, mode)
        run_cell_result = RunCellResult(result=result_df, is_cache_valid=False)
    else:
        if not meta_obj.function:
            raise ValueError(f"Invalid metadata: {meta_obj}")
        run_result = execute_with_logger(meta_obj, context, logger)
        run_cell_result = RunCellResult(
            result=convert_run_result(run_result),
            is_cache_valid=False,
        )

    return run_cell_result


def execute_with_logger(meta_obj, context, logger):
    """
    Runs a Python function (sync or async) with logging.
    """
    try:
        if is_coroutine_function(meta_obj.function):

            async def run_async():
                # stdout is not formatted with colorlog and timestamp
                # async with redirect_stdout_to_logger_async(logger, logging.INFO):
                return await meta_obj.function(context)

            result = asyncio.run(run_async())
        else:
            # stdout is not formatted with colorlog and timestamp
            # with redirect_stdout_to_logger(logger, logging.INFO):
            result = meta_obj.function(context)
    except Exception as e:
        raise e
    return result


def is_coroutine_function(func: Callable) -> bool:
    return asyncio.iscoroutinefunction(func)


def _fill_sql(resource: MorphFunctionMetaObject, vars: dict[str, Any] = {}) -> str:
    """
    Reads a SQL file from disk and applies Jinja-based templating using the provided vars.
    """
    if not resource.id or not resource.name:
        raise ValueError("resource id or name is not set.")

    context = MorphGlobalContext.get_instance()
    filepath = resource.id

    def _config(**kwargs):
        return ""

    def _connection(v: Optional[str] = None) -> str:
        return ""

    def _load_data(v: Optional[str] = None) -> str:
        if v is not None and v != "":
            _resource = context.search_meta_object_by_name(v)
            if _resource is None:
                raise FileNotFoundError(f"A resource with alias {v} not found.")
            if v in context.data:
                return v
        return ""

    env = Environment(loader=BaseLoader())
    env.globals["config"] = _config
    env.globals["connection"] = _connection
    env.globals["load_data"] = _load_data

    sql_original = open(filepath, "r").read()
    template = env.from_string(sql_original)
    rendered_sql = template.render(vars)

    return str(rendered_sql)


def _regist_sql_data_requirements(resource: MorphFunctionMetaObject) -> List[str]:
    """
    Parses a SQL file to identify 'load_data()' references and sets data requirements accordingly.
    """
    if not resource.id or not resource.name:
        raise ValueError("resource id or name is not set.")

    context = MorphGlobalContext.get_instance()
    filepath = resource.id

    def _config(**kwargs):
        return ""

    def _connection(v: Optional[str] = None) -> str:
        return ""

    load_data: List[str] = []

    def _load_data(v: Optional[str] = None) -> str:
        nonlocal load_data
        if v is not None and v != "":
            _resource = context.search_meta_object_by_name(v)
            if _resource is None:
                raise FileNotFoundError(f"A resource with alias {v} not found.")
            load_data.append(v)
        return ""

    env = Environment(loader=BaseLoader())
    env.globals["config"] = _config
    env.globals["connection"] = _connection
    env.globals["load_data"] = _load_data

    sql_original = open(filepath, "r").read()
    template = env.from_string(sql_original)
    template.render()
    if len(load_data) > 0:
        meta = MorphFunctionMetaObject(
            id=resource.id,
            name=resource.name,
            function=resource.function,
            description=resource.description,
            title=resource.title,
            variables=resource.variables,
            data_requirements=load_data,
            connection=resource.connection,
        )
        context.update_meta_object(filepath, meta)

    return load_data


def _run_sql(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    sql: str,
    logger: Optional[logging.Logger],
    mode: Literal["api", "cli"] = "api",
) -> pd.DataFrame:
    """
    Execute SQL via DuckDB (if data_requirements exist) or via a configured connection.
    """
    load_data = resource.data_requirements or []
    connection = resource.connection

    # If data dependencies exist, load them into DuckDB.
    if load_data:
        from duckdb import connect

        context = MorphGlobalContext.get_instance()
        con = connect()
        for df_name, df_value in context.data.items():
            con.register(df_name, df_value)
        return con.sql(sql).to_df()  # type: ignore

    database_connection: Optional[Union[Connection, DatabaseConnection]] = None

    if connection:
        connection_yaml = ConnectionYaml.load_yaml()
        database_connection = ConnectionYaml.find_connection(
            connection_yaml, connection
        )
        if database_connection is None:
            database_connection = ConnectionYaml.find_cloud_connection(connection)
        connector = Connector(connection, database_connection)
    else:
        if project is None:
            raise ValueError("Could not find project.")
        elif project.default_connection is None:
            raise ValueError("Default connection is not set in morph_project.yml.")
        default_connection = project.default_connection
        connection_yaml = ConnectionYaml.load_yaml()
        database_connection = ConnectionYaml.find_connection(
            connection_yaml, default_connection
        )
        if database_connection is None:
            database_connection = ConnectionYaml.find_cloud_connection(
                default_connection
            )
        connector = Connector(default_connection, database_connection)

    if logger and mode == "cli":
        logger.info("Connecting to database...")
    df = connector.execute_sql(sql)
    if logger and mode == "cli":
        logger.info("Obtained results from database.")
    return df


def _run_cell_with_dag(
    project: Optional[MorphProject],
    cell: MorphFunctionMetaObject,
    vars: dict[str, Any] = {},
    dag: Optional[RunDagArgs] = None,
    meta_obj_cache: Optional[MorphFunctionMetaObjectCache] = None,
    mode: Literal["api", "cli"] = "api",
) -> RunCellResult:
    if dag is None:
        raise ValueError("No DAG settings provided.")

    logger = get_morph_logger()
    if sys.platform == "win32":
        if len(cell.id.split(":")) > 2:
            filepath = cell.id.rsplit(":", 1)[0] if cell.id else ""
        else:
            filepath = cell.id if cell.id else ""
    else:
        filepath = cell.id.split(":")[0]
    ext = os.path.splitext(os.path.basename(filepath))[1]

    try:
        if mode == "cli":
            logger.info(f"Running load_data file: {filepath}, with variables: {vars}")
        output = run_cell(project, cell, vars, logger, dag, meta_obj_cache, mode)
    except Exception as e:
        error_txt = (
            logging_file_error_exception(e, filepath) if ext == ".py" else str(e)
        )
        text = f"An error occurred while running the file: {error_txt}"
        logger.error(text)
        if mode == "cli":
            finalize_run(
                cell,
                None,
                logger,
            )
        raise Exception(text)

    if (
        is_stream(output.result)
        or is_async_generator(output.result)
        or is_generator(output.result)
    ):
        stream_and_write(
            cell,
            output.result,
            logger,
        )
    else:
        if mode == "cli":
            finalize_run(
                cell,
                output.result,
                logger,
            )
    if mode == "cli":
        logger.info(f"Successfully executed file: {filepath}")
    return output
