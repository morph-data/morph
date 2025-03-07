import inspect
import json
import logging
import sys
import threading
import traceback
from typing import Any, Dict, Generator, List, Optional

import click
import pandas as pd
import pyarrow
from morph_lib.types import HtmlResponse, MarkdownResponse, MorphChatStreamChunk
from pydantic import BaseModel

from morph.config.project import default_output_paths
from morph.task.utils.logging import (
    redirect_stdout_to_logger,
    redirect_stdout_to_logger_async,
)
from morph.task.utils.morph import Resource
from morph.task.utils.run_backend.state import MorphFunctionMetaObject


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
    resource: MorphFunctionMetaObject,
    output: Any,
    logger: logging.Logger,
) -> Optional[List[str]]:
    return _save_output_to_file(
        resource,
        output,
        logger,
    )


def transform_output(output: Any) -> Any:
    transformed_output: Any = output

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

    if isinstance(output, pd.DataFrame) or (
        hasattr(output, "__class__") and output.__class__.__name__.endswith("DataFrame")
    ):
        transformed_output = try_parquet_conversion(output)
    elif isinstance(output, dict) or isinstance(output, list):
        transformed_output = json.dumps(output, indent=4, ensure_ascii=False)
    elif isinstance(output, StreamChatResponse):
        transformed_output = json.dumps(
            output.model_dump(), indent=4, ensure_ascii=False
        )
    elif isinstance(output, HtmlResponse):
        transformed_output = output.value
    elif isinstance(output, MarkdownResponse):
        transformed_output = output.value

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
    output: Any,
    logger: logging.Logger,
) -> Generator[str, None, None]:
    data: List[Dict[str, Any]] = []
    if inspect.isasyncgen(output):
        import asyncio
        from queue import Queue

        queue: Queue = Queue()
        sentinel = object()

        def async_thread():
            async def process_async_output():
                try:
                    async with redirect_stdout_to_logger_async(logger, logging.INFO):
                        async for chunk in output:
                            dumped_chunk = _dump_and_append_chunk(chunk, data)
                            queue.put(json.dumps(dumped_chunk, ensure_ascii=False))
                except Exception:
                    tb_str = traceback.format_exc()
                    text = f"An error occurred while running the file 💥: {tb_str}"
                    logger.error(f"Error: {text}")
                    queue.put(Exception(text))
                finally:
                    queue.put(sentinel)

            try:
                asyncio.run(process_async_output())
            except Exception as e:
                queue.put(e)
                queue.put(sentinel)

        thread = threading.Thread(target=async_thread)
        thread.start()

        while True:
            item = queue.get()
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            yield item

        thread.join()
    else:
        err = None
        try:
            with redirect_stdout_to_logger(logger, logging.INFO):
                for chunk in output:
                    dumped_chunk = _dump_and_append_chunk(chunk, data)
                    yield json.dumps(dumped_chunk, ensure_ascii=False)
        except Exception:
            tb_str = traceback.format_exc()
            text = f"An error occurred while running the file 💥: {tb_str}"
            err = text
            logger.error(f"Error: {text}")
            click.echo(click.style(text, fg="red"))
        finally:
            if err:
                raise Exception(err)


def stream_and_write(
    resource: MorphFunctionMetaObject,
    output: Any,
    logger: logging.Logger,
) -> None:
    data: List[Dict[str, Any]] = []
    if inspect.isasyncgen(output):

        async def process_async_output():
            response_data = None
            try:
                async with redirect_stdout_to_logger_async(logger, logging.INFO):
                    async for chunk in output:
                        _dump_and_append_chunk(chunk, data)
                response_data = _convert_stream_response_to_model(data)
            except Exception:
                tb_str = traceback.format_exc()
                text = f"An error occurred while running the file 💥: {tb_str}"
                logger.error(f"Error: {text}")
                click.echo(click.style(text, fg="red"))
                response_data = None
            finally:
                finalize_run(
                    resource,
                    response_data,
                    logger,
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
        except Exception:
            tb_str = traceback.format_exc()
            text = f"An error occurred while running the file 💥: {tb_str}"
            logger.error(f"Error: {text}")
            click.echo(click.style(text, fg="red"))
            response_data = None
        finally:
            finalize_run(
                resource,
                response_data,
                logger,
            )


def convert_run_result(output: Any) -> Any:
    return output


data_lock = threading.Lock()


def _dump_and_append_chunk(chunk: Any, data: List[Dict[str, Any]]) -> Any:
    if isinstance(chunk, MorphChatStreamChunk):
        dumped_chunk = chunk.model_dump()
    else:
        dumped_chunk = {"text": str(chunk), "content": None}
    with data_lock:
        data.append(dumped_chunk)
    return dumped_chunk


def _get_output_paths(output: Any, alias: str) -> List[str]:
    ext = ".txt"
    if isinstance(output, MarkdownResponse):
        ext = ".md"
    elif isinstance(output, HtmlResponse):
        ext = ".html"
    elif isinstance(output, StreamChatResponse):
        ext = ".stream.json"
    elif isinstance(output, dict) or isinstance(output, list):
        ext = ".json"
    elif isinstance(output, pd.DataFrame):
        ext = ".parquet"
    output_paths = default_output_paths(ext, alias)
    return output_paths


def _save_output_to_file(
    resource: MorphFunctionMetaObject,
    output: Any,
    logger: logging.Logger,
) -> Optional[List[str]]:
    if sys.platform == "win32":
        if len(resource.id.split(":")) > 2:
            path = resource.id.rsplit(":", 1)[0] if resource.id else ""
        else:
            path = resource.id if resource.id else ""
    else:
        path = resource.id.split(":")[0] if resource.id else ""
    resource_ = Resource(
        alias=resource.name if resource.name else "",
        path=path,
        connection=resource.connection,
        output_paths=_get_output_paths(output, resource.name if resource.name else ""),
    )

    resource_ = resource_.save_output_to_file(transform_output(output), logger)
    return resource_.output_paths


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
