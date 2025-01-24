from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
from typing import Any, Callable, List, Optional, Union

import pandas as pd
from jinja2 import BaseLoader, Environment
from morph_lib.error import RequestError
from morph_lib.types import HtmlImageResponse, MarkdownResponse, MorphChatStreamChunk
from pydantic import BaseModel

from morph.config.project import MorphProject, default_output_paths
from morph.task.utils.connection import Connection, ConnectionYaml, DatabaseConnection
from morph.task.utils.connections.connector import Connector
from morph.task.utils.logging import (
    get_morph_logger,
    redirect_stdout_to_logger,
    redirect_stdout_to_logger_async,
)
from morph.task.utils.run_backend.errors import logging_file_error_exception
from morph.task.utils.run_backend.output import (
    convert_run_result,
    finalize_run,
    is_async_generator,
    is_generator,
    is_stream,
    stream_and_write,
    transform_output,
)
from morph.task.utils.run_backend.types import CliError, RunStatus

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
    cached_cell = meta_obj_cache.find_by_name(meta_obj.name) if meta_obj_cache else None
    is_cache_valid = True

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
                project,
                required_meta_obj,
                vars,
                dag,
                meta_obj_cache,
            )
        else:
            required_data_result = run_cell(
                project,
                required_meta_obj,
                vars,
                logger,
                None,
                meta_obj_cache,
            )
        is_cache_valid = required_data_result.is_cache_valid or True
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

    # -------------------------------------------------------------------------
    # Use the global _execution_cache. If project.result_cache_ttl is set, apply it.
    # project.result_cache_ttl is in SECONDS, so we directly assign it to expiration_seconds.
    # -------------------------------------------------------------------------
    if project and project.result_cache_ttl and project.result_cache_ttl > 0:
        execution_cache.expiration_seconds = project.result_cache_ttl

    # Check cache
    cache_entry = execution_cache.get_cache(meta_obj.name)
    if cache_entry:
        # If valid cache entry, try to load from disk
        if logger:
            logger.info(f"Running {meta_obj.name} using cached result.")

        cache_paths_obj = cache_entry.get("cache_paths", [])
        if not isinstance(cache_paths_obj, list):
            raise ValueError("Invalid cache entry: cache_paths is not a list.")

        for path in cache_paths_obj:
            if not os.path.exists(path):
                continue
            ext_ = path.split(".")[-1]
            if ext_ in {"parquet", "csv", "json", "md", "txt", "html", "png"}:
                cached_result = None
                if ext_ == "parquet":
                    cached_result = RunCellResult(result=pd.read_parquet(path))
                elif ext_ == "csv":
                    cached_result = RunCellResult(result=pd.read_csv(path))
                elif ext_ == "json":
                    json_dict = json.loads(open(path, "r").read())
                    if not MorphChatStreamChunk.is_chat_stream_chunk_json(json_dict):
                        cached_result = RunCellResult(
                            result=pd.read_json(path, orient="records")
                        )
                elif ext_ in {"md", "txt"}:
                    cached_result = RunCellResult(
                        result=MarkdownResponse(open(path, "r").read())
                    )
                elif ext_ == "html":
                    cached_result = RunCellResult(
                        result=HtmlImageResponse(html=open(path, "r").read())
                    )
                elif ext_ == "png":
                    cached_result = RunCellResult(
                        result=HtmlImageResponse(image=convert_image_base64(path))
                    )
                if cached_result:
                    return cached_result

    # ------------------------------------------------------------------
    # Legacy file-based cache logic
    # ------------------------------------------------------------------
    cache_ttl = (
        meta_obj.result_cache_ttl or (project.result_cache_ttl if project else 0) or 0
    )
    if project and cache_ttl > 0 and cached_cell and is_cache_valid:
        cache_outputs = default_output_paths()
        if len(cache_outputs) > 1:
            html_path = next((x for x in cache_outputs if x.endswith(".html")), None)
            image_path = next((x for x in cache_outputs if x.endswith(".png")), None)
            if (
                html_path
                and image_path
                and os.path.exists(html_path)
                and os.path.exists(image_path)
            ):
                if logger:
                    logger.info(
                        f"Running {meta_obj.name} using existing file-based cache (legacy)."
                    )
                return RunCellResult(
                    result=HtmlImageResponse(
                        html=open(html_path, "r").read(),
                        image=convert_image_base64(image_path),
                    )
                )
        if len(cache_outputs) > 0:
            cache_path = cache_outputs[0]
            cache_path_ext = cache_path.split(".")[-1]
            if cache_path_ext in {
                "parquet",
                "csv",
                "json",
                "md",
                "txt",
                "html",
                "png",
            } and os.path.exists(cache_path):
                cached_result = None
                if cache_path_ext == "parquet":
                    cached_result = RunCellResult(result=pd.read_parquet(cache_path))
                elif cache_path_ext == "csv":
                    cached_result = RunCellResult(result=pd.read_csv(cache_path))
                elif cache_path_ext == "json":
                    json_dict = json.loads(open(cache_path, "r").read())
                    if not MorphChatStreamChunk.is_chat_stream_chunk_json(json_dict):
                        cached_result = RunCellResult(
                            result=pd.read_json(cache_path, orient="records")
                        )
                elif cache_path_ext == "md" or cache_path_ext == "txt":
                    cached_result = RunCellResult(
                        result=MarkdownResponse(open(cache_path, "r").read())
                    )
                elif cache_path_ext == "html":
                    cached_result = RunCellResult(
                        result=HtmlImageResponse(html=open(cache_path, "r").read())
                    )
                elif cache_path_ext == "png":
                    cached_result = RunCellResult(
                        result=HtmlImageResponse(image=convert_image_base64(cache_path))
                    )
                if cached_result:
                    if logger:
                        logger.info(
                            f"{meta_obj.name} using existing file-based cache (legacy)."
                        )
                    return cached_result

    # ------------------------------------------------------------------
    # Actual execution
    # ------------------------------------------------------------------
    if ext == "sql":
        if logger:
            logger.info(f"Formatting SQL file: {meta_obj.id} with variables: {vars}")
        sql_text = _fill_sql(meta_obj, vars)
        result_df = _run_sql(project, meta_obj, sql_text, logger)
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
                async with redirect_stdout_to_logger_async(logger, logging.INFO):
                    return await meta_obj.function(context)

            result = asyncio.run(run_async())
        else:
            with redirect_stdout_to_logger(logger, logging.INFO):
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
            output_paths=resource.output_paths,
            output_type=resource.output_type,
            connection=resource.connection,
            result_cache_ttl=resource.result_cache_ttl,
        )
        context.update_meta_object(filepath, meta)

    return load_data


def _run_sql(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    sql: str,
    logger: Optional[logging.Logger],
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

    if logger:
        logger.info("Connecting to database...")
    df = connector.execute_sql(sql)
    if logger:
        logger.info("Obtained results from database.")
    return df


def _run_cell_with_dag(
    project: Optional[MorphProject],
    cell: MorphFunctionMetaObject,
    vars: dict[str, Any] = {},
    dag: Optional[RunDagArgs] = None,
    meta_obj_cache: Optional[MorphFunctionMetaObjectCache] = None,
) -> RunCellResult:
    if dag is None:
        raise ValueError("No DAG settings provided.")

    logger = get_morph_logger()
    filepath = cell.id.split(":")[0]
    ext = os.path.splitext(os.path.basename(filepath))[1]

    try:
        logger.info(f"Running load_data file: {filepath}, with variables: {vars}")
        output = run_cell(
            project,
            cell,
            vars,
            logger,
            dag,
            meta_obj_cache,
        )
    except Exception as e:
        error_txt = (
            logging_file_error_exception(e, filepath) if ext == ".py" else str(e)
        )
        text = f"An error occurred while running the file: {error_txt}"
        logger.error(text)
        finalize_run(
            project,
            cell,
            cell.name,
            RunStatus.FAILED.value,
            None,
            logger,
            dag.run_id,
            CliError(type="general", details=text),
        )
        raise Exception(text)

    if (
        is_stream(output.result)
        or is_async_generator(output.result)
        or is_generator(output.result)
    ):
        stream_and_write(
            project,
            cell,
            cell.name,
            RunStatus.DONE.value,
            transform_output(cell, output.result),
            logger,
            dag.run_id,
            None,
        )
    else:
        finalize_run(
            project,
            cell,
            cell.name,
            RunStatus.DONE.value,
            transform_output(cell, output.result),
            logger,
            dag.run_id,
            None,
        )
    logger.info(f"Successfully executed file: {filepath}")
    return output


def generate_variables_hash(vars: Optional[dict[str, Any]]) -> Optional[str]:
    if vars is None or len(vars) == 0:
        return None

    def make_hashable(item: Any) -> Any:
        if isinstance(item, dict):
            return tuple(sorted((k, make_hashable(v)) for k, v in item.items()))
        elif isinstance(item, list):
            return tuple(make_hashable(i) for i in item)
        elif isinstance(item, set):
            return frozenset(make_hashable(i) for i in item)
        return item

    hashable_vars = make_hashable(vars)
    sorted_items = frozenset(hashable_vars)
    sha256 = hashlib.sha256()
    sha256.update(str(sorted_items).encode("utf-8"))
    return sha256.hexdigest()


def convert_image_base64(filepath: str) -> str:
    from PIL import Image

    with open(filepath, "rb") as f:
        image = Image.open(f)
        image.load()
    buffered = io.BytesIO()
    image.save(buffered, format=image.format)
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return img_base64
