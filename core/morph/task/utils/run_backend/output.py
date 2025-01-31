import base64
import inspect
import io
import json
import logging
import os
import threading
import traceback
from typing import Any, Dict, Generator, List, Literal, Optional, Union, cast

import click
import pandas as pd
import plotly.graph_objects
import plotly.io as pio
import pyarrow
from morph_lib.types import (
    HtmlImageResponse,
    HtmlResponse,
    MarkdownResponse,
    MorphChatStreamChunk,
)
from pydantic import BaseModel

from morph.config.project import MorphProject, default_output_paths
from morph.constants import MorphConstant
from morph.task.utils.logging import (
    redirect_stdout_to_logger,
    redirect_stdout_to_logger_async,
)
from morph.task.utils.morph import Resource
from morph.task.utils.run_backend.state import MorphFunctionMetaObject
from morph.task.utils.run_backend.types import CliError, RunStatus


class StreamChatResponse(BaseModel):
    data: List[Dict[str, Any]]

    @classmethod
    def to_model(cls, data: List[Dict[str, Any]]) -> "StreamChatResponse":
        return cls(
            data=[
                MorphChatStreamChunk(
                    text=d["text"],
                    content=d["content"],
                ).model_dump()
                for d in data
            ]
        )


def finalize_run(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    cell_alias: str,
    final_state: str,
    output: Any,
    logger: logging.Logger,
    run_id: str,
    error: Optional[CliError],
) -> Optional[List[str]]:
    return _save_output_to_file(
        project,
        resource,
        output,
        logger,
        run_id,
    )


def transform_output(resource: MorphFunctionMetaObject, output: Any) -> Any:
    transformed_output: Any = output
    output_type = resource.output_type if resource.output_type else None

    def try_parquet_conversion(df):
        try:
            return df.to_parquet(index=False, engine="pyarrow")
        except (pyarrow.lib.ArrowInvalid, pyarrow.lib.ArrowTypeError, ValueError) as e:
            click.echo(
                click.style(
                    f"Warning: Converting problematic columns to string. [{e}]",
                    fg="yellow",
                ),
                err=False,
            )
            df = df.astype(
                {col: "str" for col in df.select_dtypes(include="object").columns}
            )
            return df.to_parquet(index=False, engine="pyarrow")

    if output_type is not None:
        if output_type == "dataframe" and isinstance(output, pd.DataFrame):
            transformed_output = try_parquet_conversion(output)
        elif output_type == "csv" and isinstance(output, pd.DataFrame):
            transformed_output = output.to_csv(index=False)
        elif output_type == "markdown" and isinstance(output, str):
            transformed_output = str(output)
        elif output_type == "json" and isinstance(output, dict):
            transformed_output = json.dumps(output, indent=4, ensure_ascii=False)
        elif output_type == "json" and isinstance(output, pd.DataFrame):
            transformed_output = output.to_json(orient="records", indent=4)
            transformed_output = json.loads(transformed_output)
            transformed_output = json.dumps(
                transformed_output, ensure_ascii=False, indent=4
            )
        elif output_type == "visualization":
            transformed_output = [
                _get_html_from_plotly_image(output, "html"),
                _get_html_from_plotly_image(output, "png"),
            ]
    else:
        if isinstance(output, pd.DataFrame):
            transformed_output = try_parquet_conversion(output)
        elif isinstance(output, dict):
            transformed_output = json.dumps(output, indent=4, ensure_ascii=False)
        elif _is_matplotlib_figure(output):
            transformed_output = [
                _get_html_from_mpl_image(output, "html"),
                _get_html_from_mpl_image(output, "png"),
            ]
        elif isinstance(output, plotly.graph_objects.Figure):
            transformed_output = [
                _get_html_from_plotly_image(output, "html"),
                _get_html_from_plotly_image(output, "png"),
            ]

    return transformed_output


def is_stream(output: Any) -> bool:
    try:
        return hasattr(output, "__stream__") and callable(output.__stream__)
    except Exception:  # noqa
        return False


def is_async_generator(output: Any) -> bool:
    try:
        return inspect.isasyncgen(output) or inspect.isasyncgenfunction(output)
    except Exception:  # noqa
        return False


def is_generator(output: Any) -> bool:
    try:
        return inspect.isgenerator(output) or inspect.isgeneratorfunction(output)
    except Exception:  # noqa
        return False


def stream_and_write_and_response(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    cell_alias: str,
    final_state: str,
    output: Any,
    logger: logging.Logger,
    run_id: str,
    error: Optional[CliError],
) -> Generator[str, None, None]:
    data: List[Dict[str, Any]] = []
    if inspect.isasyncgen(output):

        async def process_async_output():
            err = None
            final_state_ = final_state
            error_ = error
            response_data = None
            try:
                async with redirect_stdout_to_logger_async(logger, logging.INFO):
                    async for chunk in output:
                        dumped_chunk = _dump_and_append_chunk(chunk, data)
                        yield json.dumps(dumped_chunk, ensure_ascii=False)
                response_data = _convert_stream_response_to_model(data)
            except Exception as e:
                tb_str = traceback.format_exc()
                text = f"An error occurred while running the file 💥: {tb_str}"
                err = text
                logger.error(f"Error: {text}")
                click.echo(click.style(text, fg="red"))
                final_state_ = RunStatus.FAILED.value
                error_ = CliError(
                    type="general",
                    details=str(e),
                )
                response_data = None
            finally:
                finalize_run(
                    project,
                    resource,
                    cell_alias,
                    final_state_,
                    response_data,
                    logger,
                    run_id,
                    error_,
                )
                if err:
                    raise Exception(err)
                else:
                    filepath = resource.id.split(":")[0]
                    logger.info(f"Successfully ran file 🎉: {filepath}")

        import asyncio

        asyncio.run(process_async_output())
    else:
        err = None
        response_data = None
        try:
            with redirect_stdout_to_logger(logger, logging.INFO):
                for chunk in output:
                    dumped_chunk = _dump_and_append_chunk(chunk, data)
                    yield json.dumps(dumped_chunk, ensure_ascii=False)
            response_data = _convert_stream_response_to_model(data)
        except Exception as e:
            tb_str = traceback.format_exc()
            text = f"An error occurred while running the file 💥: {tb_str}"
            err = text
            logger.error(f"Error: {text}")
            click.echo(click.style(text, fg="red"))
            final_state = RunStatus.FAILED.value
            error = CliError(
                type="general",
                details=str(e),
            )
            response_data = None
        finally:
            finalize_run(
                project,
                resource,
                cell_alias,
                final_state,
                response_data,
                logger,
                run_id,
                error,
            )
            if err:
                raise Exception(err)
            else:
                filepath = resource.id.split(":")[0]
                logger.info(f"Successfully ran file 🎉: {filepath}")


def stream_and_write(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    cell_alias: str,
    final_state: str,
    output: Any,
    logger: logging.Logger,
    run_id: str,
    error: Optional[CliError],
) -> None:
    data: List[Dict[str, Any]] = []

    if inspect.isasyncgen(output):

        async def process_async_output():
            final_state_ = final_state
            error_ = error
            response_data = None
            try:
                async with redirect_stdout_to_logger_async(logger, logging.INFO):
                    async for chunk in output:
                        _dump_and_append_chunk(chunk, data)
                response_data = _convert_stream_response_to_model(data)
            except Exception as e:
                tb_str = traceback.format_exc()
                text = f"An error occurred while running the file 💥: {tb_str}"
                logger.error(f"Error: {text}")
                click.echo(click.style(text, fg="red"))
                final_state_ = RunStatus.FAILED.value
                error_ = CliError(
                    type="general",
                    details=str(e),
                )
                response_data = None
            finally:
                finalize_run(
                    project,
                    resource,
                    cell_alias,
                    final_state_,
                    response_data,
                    logger,
                    run_id,
                    error_,
                )

        import asyncio

        asyncio.run(process_async_output())
    else:
        response_data = None
        try:
            with redirect_stdout_to_logger(logger, logging.INFO):
                for chunk in output:
                    _dump_and_append_chunk(chunk, data)
            response_data = _convert_stream_response_to_model(data)
        except Exception as e:
            tb_str = traceback.format_exc()
            text = f"An error occurred while running the file 💥: {tb_str}"
            logger.error(f"Error: {text}")
            click.echo(click.style(text, fg="red"))
            final_state = RunStatus.FAILED.value
            error = CliError(
                type="general",
                details=str(e),
            )
            response_data = None
        finally:
            finalize_run(
                project,
                resource,
                cell_alias,
                final_state,
                response_data,
                logger,
                run_id,
                error,
            )


def convert_run_result(output: Any) -> Any:
    if output is None:
        return None
    elif isinstance(output, str):
        return MarkdownResponse(output)
    elif isinstance(output, dict):
        return pd.DataFrame.from_dict(output, orient="index").T
    elif _is_matplotlib_figure(output):
        html = _get_html_from_mpl_image(output, "html")
        image = _get_html_from_mpl_image(output, "png")
        return HtmlImageResponse(html=html, image=image)
    elif isinstance(output, plotly.graph_objects.Figure):
        html = _get_html_from_plotly_image(output, "html")
        image = _get_html_from_plotly_image(output, "png")
        return HtmlImageResponse(html=html, image=image)

    return output


data_lock = threading.Lock()


def _dump_and_append_chunk(chunk: Any, data: List[Dict[str, Any]]) -> Any:
    dumped_chunk = chunk.model_dump()
    with data_lock:
        data.append(dumped_chunk)
    return dumped_chunk


def _infer_output_type(output: Any) -> Optional[str]:
    if isinstance(output, pd.DataFrame) or isinstance(output, bytes):
        return "dataframe"
    elif isinstance(output, dict) or isinstance(output, StreamChatResponse):
        return "json"
    elif isinstance(output, list):
        return "visualization"
    elif isinstance(output, HtmlResponse):
        return "visualization"
    elif isinstance(output, HtmlImageResponse):
        return "visualization"
    elif isinstance(output, MarkdownResponse):
        return "markdown"
    else:
        return None


def _get_output_paths(
    project: Optional[MorphProject], resource: MorphFunctionMetaObject
) -> List[str]:
    output_paths = default_output_paths()
    if resource.output_paths and len(resource.output_paths) > 0:
        output_paths = cast(list, resource.output_paths)
    output_type = resource.output_type if resource.output_type else None

    # if output_type exists and output_paths is not specified, set default output destination
    if output_type is not None and len(output_paths) < 1:
        output_dir = os.path.join(
            MorphConstant.TMP_MORPH_DIR,
            resource.name if resource.name else "",
        )
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if resource.output_type == "dataframe":
            output_paths = [os.path.join(output_dir, "result.parquet")]
        elif resource.output_type == "visualization":
            output_paths = [
                os.path.join(output_dir, "result.html"),
                os.path.join(output_dir, "result.png"),
            ]
        elif resource.output_type == "markdown":
            output_paths = [os.path.join(output_dir, "result.md")]
        elif resource.output_type == "csv":
            output_paths = [os.path.join(output_dir, "result.csv")]
        elif resource.output_type == "json":
            output_paths = [os.path.join(output_dir, "result.json")]

    return output_paths


def _save_output_to_file(
    project: Optional[MorphProject],
    resource: MorphFunctionMetaObject,
    output: Any,
    logger: logging.Logger,
    run_id: str,
) -> Optional[List[str]]:
    output_type = (
        resource.output_type if resource.output_type else _infer_output_type(output)
    )

    output_paths: List[str] = _get_output_paths(project, resource)

    if isinstance(output, MarkdownResponse):
        if len(output_paths) > 0:
            if output_paths[0].endswith("{ext()}"):
                output_paths = [
                    output_paths[0].replace("{ext()}", ".md"),
                ]
            else:
                output_paths = [os.path.splitext(output_paths[0])[0] + ".md"]
    elif isinstance(output, HtmlResponse):
        if len(output_paths) > 0:
            if output_paths[0].endswith("{ext()}"):
                output_paths = [
                    output_paths[0].replace("{ext()}", ".html"),
                ]
            else:
                output_paths = [os.path.splitext(output_paths[0])[0] + ".html"]
    elif isinstance(output, StreamChatResponse):
        if len(output_paths) > 0:
            if output_paths[0].endswith("{ext()}"):
                output_paths = [
                    output_paths[0].replace("{ext()}", ".stream.json"),
                ]
            else:
                output_paths = [os.path.splitext(output_paths[0])[0] + ".stream.json"]

    resource_ = Resource(
        alias=resource.name if resource.name else "",
        path=resource.id.split(":")[0] if resource.id else "",
        connection=resource.connection,
        output_paths=output_paths,
        output_type=output_type,
    )

    if isinstance(output, StreamChatResponse):
        output = json.dumps(output.model_dump(), indent=4, ensure_ascii=False)
    elif isinstance(output, HtmlResponse):
        output = output.value
    elif isinstance(output, MarkdownResponse):
        output = output.value
    elif isinstance(output, HtmlImageResponse):
        output = [output.html, output.image]

    resource_ = resource_.save_output_to_file(run_id, output, logger)
    return resource_.output_paths


VISUALIZATION_FORMAT = Literal["png", "html"]


def _get_html_from_mpl_image(fig: Any, format: VISUALIZATION_FORMAT = "html") -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    if format == "png":
        return base64.b64encode(buf.read()).decode()
    elif format == "html":
        return f'<img src="data:image/png;base64,{base64.b64encode(buf.read()).decode()}" />'


def _get_html_from_plotly_image(fig: Any, format: VISUALIZATION_FORMAT = "html") -> str:
    buf: Union[io.BytesIO, io.StringIO]
    if format == "png":
        pio.kaleido.scope.chromium_args += ("--single-process",)
        buf = io.BytesIO()
        fig.write_image(buf, format="png")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    elif format == "html":
        buf = io.StringIO()
        fig.write_html(
            buf,
            include_plotlyjs="cdn",
            full_html=False,
            config={
                "modeBarButtonsToRemove": [
                    "zoom",
                    "pan",
                    "select",
                    "zoomIn",
                    "zoomOut",
                    "autoScale",
                    "resetScale",
                    "lasso2d",
                ],
                "displaylogo": False,
            },
        )
        buf.seek(0)
        return buf.getvalue()


def _is_matplotlib_figure(output: Any) -> bool:
    try:
        return hasattr(output, "savefig") and callable(output.savefig)
    except Exception:  # noqa
        return False


def _is_openai_chunk(output: Any) -> bool:
    return (
        isinstance(output, dict)
        and "id" in output
        and "object" in output
        and "choices" in output
        and "created" in output
        and "system_fingerprint" in output
    )


def _convert_stream_response_to_model(data: List[Dict[str, Any]]) -> Any:
    if all("text" in d and "content" in d for d in data):
        return StreamChatResponse.to_model(data)
    elif all(_is_openai_chunk(d) for d in data):
        response: List[Dict[str, Any]] = []
        for d in data:
            response.append(
                {
                    "text": d["choices"][0]["delta"].get("content", ""),
                    "content": None,
                }
            )
        return StreamChatResponse.to_model(response)

    return data
