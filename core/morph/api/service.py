import asyncio
import io
import json
import logging
import os
import tempfile
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import click
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from morph.api.custom_types import (
    RunFileService,
    RunFileStreamService,
    RunFileWithTypeResponse,
    RunFileWithTypeService,
    SuccessResponse,
    UploadFileService,
)
from morph.api.error import ErrorCode, ErrorMessage, RequestError, WarningError
from morph.api.utils import (
    convert_file_output,
    convert_variables_values,
    set_command_args,
)
from morph.cli.flags import Flags
from morph.task.resource import PrintResourceTask
from morph.task.run import RunTask
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.errors import MorphFunctionLoadError
from morph.task.utils.run_backend.state import MorphGlobalContext
from morph.task.utils.run_backend.types import RunStatus

logger = logging.getLogger("uvicorn")


def run_file_with_type_service(
    input: RunFileWithTypeService,
) -> RunFileWithTypeResponse:
    project_root = find_project_root_dir()
    context = MorphGlobalContext.get_instance()

    errors = context.partial_load(
        project_root,
        input.name,
    )
    if len(errors) > 0:
        logger.error(MorphFunctionLoadError.format_errors(errors))
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information.",
        )
    resource = context.search_meta_object_by_name(input.name)
    if resource is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information.",
        )

    set_command_args()
    with click.Context(click.Command(name="")) as ctx:
        ctx.params["FILENAME"] = input.name
        ctx.params["RUN_ID"] = f"{int(time.time() * 1000)}"
        ctx.params["DAG"] = input.use_cache if input.use_cache else False
        ctx.params["DATA"] = convert_variables_values(input.variables)
        task = RunTask(Flags(ctx), "api")

    try:
        result = task.run()
    except Exception as e:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            str(e),
        )

    if task.final_state != RunStatus.DONE.value:
        if task.error is not None:
            try:
                error = json.loads(task.error)
            except Exception:  # noqa
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "run status failed",
                )
            if "RequestError" in error:
                raise RequestError(
                    ErrorCode.RequestError,
                    ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
                    str(error),
                )
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
        )

    try:
        data = convert_file_output(input.type, result, input.limit, input.skip)
    except Exception:  # noqa
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "file type invalid",
        )

    return RunFileWithTypeResponse(
        type=input.type,
        data=data,
    )


def run_file_service(input: RunFileService) -> SuccessResponse:
    project_root = find_project_root_dir()
    context = MorphGlobalContext.get_instance()

    errors = context.partial_load(
        project_root,
        input.name,
    )
    if len(errors) > 0:
        logger.error(MorphFunctionLoadError.format_errors(errors))
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information.",
        )
    resource = context.search_meta_object_by_name(input.name)
    if resource is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information.",
        )

    set_command_args()
    with click.Context(click.Command(name="")) as ctx:
        run_id = input.run_id if input.run_id else f"{int(time.time() * 1000)}"
        ctx.params["FILENAME"] = input.name
        ctx.params["RUN_ID"] = run_id
        ctx.params["DAG"] = False
        ctx.params["DATA"] = convert_variables_values(input.variables)
        task = RunTask(Flags(ctx), "api")

    try:
        task.run()
    except Exception as e:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            str(e),
        )

    if task.final_state != RunStatus.DONE.value:
        if task.error is not None:
            try:
                error = json.loads(task.error)
            except Exception:  # noqa
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "run status failed",
                )
            if "RequestError" in error:
                raise RequestError(
                    ErrorCode.RequestError,
                    ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
                    str(error),
                )
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
        )

    return SuccessResponse(message="ok")


async def run_file_stream_service(input: RunFileStreamService) -> Any:
    project_root = find_project_root_dir()
    context = MorphGlobalContext.get_instance()

    errors = context.partial_load(
        project_root,
        input.name,
    )
    if len(errors) > 0:
        logger.error(MorphFunctionLoadError.format_errors(errors))
        error_details = "".join([e.error for e in errors])
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information. details: {error_details}",
        )

    set_command_args()
    with click.Context(click.Command(name="")) as ctx:
        ctx.params.update(
            {
                "FILENAME": input.name,
                "RUN_ID": f"{int(time.time() * 1000)}",
                "DAG": False,
                "DATA": convert_variables_values(input.variables),
            }
        )

        try:
            task = RunTask(Flags(ctx), "api")
            generator = task.run()
        except Exception as e:
            error_detail = {
                "type": type(e).__name__,
                "message": str(e),
            }
            error_json = json.dumps(error_detail, ensure_ascii=False)
            raise Exception(error_json)

        first_chunk = True
        try:
            for c in generator:
                if first_chunk:
                    first_chunk = False
                    yield '{"chunks": ['
                    await asyncio.sleep(0)
                yield c + ","
                await asyncio.sleep(0)

            yield "]}"
        except Exception as e:
            error_detail = {
                "type": type(e).__name__,
                "message": str(e),
            }
            error_json = json.dumps(error_detail, ensure_ascii=False)
            raise Exception(error_json)


def list_resource_service() -> Any:
    set_command_args()
    with click.Context(click.Command(name="")) as ctx:
        ctx.params["ALL"] = True
        task = PrintResourceTask(Flags(ctx))

        output = io.StringIO()
        with redirect_stdout(output):
            task.run()

        result = output.getvalue()
        try:
            return json.loads(result)
        except json.JSONDecodeError:  # noqa
            raise WarningError(
                ErrorCode.FileError,
                ErrorMessage.FileErrorMessage["notFound"],
                result,
            )


async def file_upload_service(input: UploadFileService) -> Any:
    try:
        # Create a temporary directory
        run_id = uuid.uuid4().hex
        temp_dir = os.path.join(tempfile.gettempdir(), run_id)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # Save the uploaded file to the temporary directory
        temp_file_path = os.path.join(temp_dir, input.file.filename)
        with open(temp_file_path, "wb") as temp_file:
            content = await input.file.read()
            temp_file.write(content)

        # Intercept the file upload by running the file_upload python function
        run_file_service(
            RunFileService(
                name="file_upload", variables={"file": temp_file_path}, run_id=run_id
            )
        )

        # Read the saved file path from the cache (always created as following path)
        cache_file = Path(find_project_root_dir()).joinpath(
            ".morph/cache/file_upload.md"
        )
        with open(cache_file, "r") as f:
            saved_filepath = f.read()

        # Remove the temporary directory
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(temp_dir)

        # Return the saved file path
        return JSONResponse(
            content={"path": saved_filepath},
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the file: {str(e)}",
        )
