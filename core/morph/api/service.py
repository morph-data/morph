import ast
import asyncio
import io
import json
import logging
import os
import tempfile
import time
import uuid
from contextlib import redirect_stdout
from datetime import datetime
from typing import Any, List

import click
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from morph.api.error import ErrorCode, ErrorMessage, RequestError, WarningError
from morph.api.types import (
    CreateFileService,
    CreateScheduledJobService,
    DeleteScheduledJobService,
    FindRunResultDetailResponse,
    FindRunResultDetailService,
    FindRunResultResponse,
    FindRunResultService,
    FindScheduledJobService,
    ListRunResultResponse,
    ListRunResultService,
    RunFileService,
    RunFileStreamService,
    RunFileWithTypeResponse,
    RunFileWithTypeService,
    RunResult,
    RunResultUnit,
    SuccessResponse,
    UpdateScheduledJobService,
    UploadFileService,
)
from morph.api.utils import (
    convert_file_output,
    convert_variables_values,
    convert_vg_json_to_html,
)
from morph.cli.flags import Flags
from morph.config.project import ScheduledJob, load_project, save_project
from morph.task.create import CreateTask
from morph.task.resource import PrintResourceTask
from morph.task.run import RunTask
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.errors import MorphFunctionLoadError
from morph.task.utils.run_backend.state import MorphGlobalContext
from morph.task.utils.sqlite import SqliteDBManager

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
    filepath = str(resource.id).split(":")[0]

    db_manager = SqliteDBManager(project_root)
    db_manager.initialize_database()

    if input.type == "html":
        filename = str(os.path.basename(filepath))
        if filename.endswith(".vg.json"):
            with open(filepath, "r") as file:
                content = file.read()
            return RunFileWithTypeResponse(
                type=input.type,
                data=convert_vg_json_to_html(content),
            )

    with click.Context(click.Command(name="")) as ctx:
        ctx.params["FILENAME"] = input.name
        ctx.params["RUN_ID"] = f"{int(time.time() * 1000)}"
        ctx.params["DAG"] = input.use_cache if input.use_cache else False
        ctx.params["DATA"] = convert_variables_values(input.variables)
        task = RunTask(Flags(ctx))

    try:
        task.run()
    except Exception as e:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            str(e),
        )

    run_results = db_manager.get_run_records_by_run_id(task.run_id)
    run_result = next(
        (result for result in run_results if result["cell_alias"] == input.name), None
    )
    if run_result is None:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "run result not found",
        )
    elif run_result["status"] == "failed":
        if run_result["error"] is not None:
            try:
                error = json.loads(run_result["error"])["details"]
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
        output_paths = ast.literal_eval(run_result["outputs"])
    except Exception:  # noqa
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "output not found",
        )
    output_path = output_paths[0]
    if input.type == "image" or input.type == "html":
        if len(output_paths) == 2:
            if input.type == "image" and output_path.endswith(".html"):
                output_path = output_paths[1]
            elif input.type == "html" and not output_path.endswith(".html"):
                output_path = output_paths[1]
        elif len(output_paths) == 1:
            if input.type == "image" and output_path.endswith(".html"):
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "image not found",
                )
            elif (
                input.type == "html"
                and not output_path.endswith(".html")
                and not output_path.endswith(".txt")
            ):
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "html not found",
                )

    ext = output_path.split(".")[-1]

    try:
        data = convert_file_output(
            input.type, output_path, ext, input.limit, input.skip
        )
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

    db_manager = SqliteDBManager(project_root)
    db_manager.initialize_database()

    with click.Context(click.Command(name="")) as ctx:
        run_id = input.run_id if input.run_id else f"{int(time.time() * 1000)}"
        ctx.params["FILENAME"] = input.name
        ctx.params["RUN_ID"] = run_id
        ctx.params["DAG"] = False
        ctx.params["DATA"] = convert_variables_values(input.variables)
        task = RunTask(Flags(ctx))

    try:
        task.run()
    except Exception as e:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            str(e),
        )

    run_results = db_manager.get_run_records_by_run_id(task.run_id)
    run_result = next(
        (result for result in run_results if result["cell_alias"] == input.name), None
    )
    if run_result is None:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "run result not found",
        )
    elif run_result["status"] == "failed":
        if run_result["error"] is not None:
            try:
                error = json.loads(run_result["error"])["details"]
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
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Alias not found {input.name}. Check the console for more detailed error information.",
        )

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
                    await asyncio.sleep(0.02)
                yield c + ","
                await asyncio.sleep(0.02)

            yield "]}"
        except Exception as e:
            error_detail = {
                "type": type(e).__name__,
                "message": str(e),
            }
            error_json = json.dumps(error_detail, ensure_ascii=False)
            raise Exception(error_json)


def list_resource_service() -> Any:
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


def create_file_service(input: CreateFileService) -> SuccessResponse:
    with click.Context(click.Command(name="")) as ctx:
        ctx.params["FILENAME"] = input.filename
        ctx.params["TEMPLATE"] = input.template
        ctx.params["NAME"] = input.name
        ctx.params["DESCRIPTION"] = input.description
        ctx.params["PARENT_NAME"] = input.parent_name
        ctx.params["CONNECTION"] = input.connection
        task = CreateTask(Flags(ctx))

        output = io.StringIO()
        with redirect_stdout(output):
            task.run()

        result = output.getvalue()
        if "Error" in result:
            raise WarningError(
                ErrorCode.FileError,
                ErrorMessage.FileErrorMessage["createFailed"],
                result,
            )
        return SuccessResponse(message="ok")


def list_run_result_service(input: ListRunResultService) -> ListRunResultResponse:
    project_root = find_project_root_dir()
    db_manager = SqliteDBManager(project_root)
    db_manager.initialize_database()

    run_records, count = db_manager.get_run_records(
        canvas=None,
        cell_alias=input.name,
        status=None,
        sort_by="started_at",
        order="DESC",
        limit=input.limit,
        skip=input.skip,
    )

    run_results: List[RunResult] = []
    for run_record in run_records:
        cells = db_manager.get_run_records_by_run_id(run_record["run_id"])

        run_result = RunResult(
            runId=run_record["run_id"],
            cells=[],
            status=run_record["status"],
            startedAt=run_record["started_at"],
        )

        ended_at = None
        error = None
        for cell in cells:
            outputs = []
            try:
                outputs = ast.literal_eval(cell["outputs"])
            except Exception:  # noqa
                pass
            cell_error = cell["error"]
            if cell["error"]:
                try:
                    cell_error = json.loads(cell["error"])["details"]
                except json.JSONDecodeError:
                    pass
            run_result.cells.append(
                RunResultUnit(
                    name=cell["cell_alias"],
                    status=cell["status"],
                    startedAt=cell["started_at"],
                    logs=[cell["log"]] if cell["log"] else [],
                    outputs=outputs,
                    endedAt=cell["ended_at"],
                    error=cell_error,
                )
            )
            if ended_at is None:
                ended_at = cell["ended_at"]
            if cell["error"]:
                error = cell["error"]
            if cell["ended_at"]:
                cell_ended_at = datetime.fromisoformat(cell["ended_at"])
                if ended_at and cell_ended_at > datetime.fromisoformat(ended_at):
                    ended_at = cell["ended_at"]

        if error:
            try:
                error = json.loads(error)["details"]
            except json.JSONDecodeError:
                pass
        run_result.error = error
        run_result.endedAt = ended_at

        run_results.append(run_result)

    return ListRunResultResponse(count=count, items=run_results)


def find_run_result_service(input: FindRunResultService) -> FindRunResultResponse:
    project_root = find_project_root_dir()
    db_manager = SqliteDBManager(project_root)
    db_manager.initialize_database()

    cells = db_manager.get_run_records_by_run_id(input.run_id)

    if len(cells) == 0:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            "run result not found",
        )

    run_result = FindRunResultResponse(
        runId=input.run_id,
        cells=[],
        status=cells[-1]["status"],
        startedAt=cells[0]["started_at"],
    )

    ended_at = None
    error = None
    for cell in cells:
        outputs = []
        try:
            outputs = ast.literal_eval(cell["outputs"])
        except Exception:  # noqa
            pass
        cell_error = cell["error"]
        if cell["error"]:
            try:
                cell_error = json.loads(cell["error"])["details"]
            except json.JSONDecodeError:
                pass
        run_result.cells.append(
            RunResultUnit(
                name=cell["cell_alias"],
                status=cell["status"],
                startedAt=cell["started_at"],
                logs=[cell["log"]] if cell["log"] else [],
                outputs=outputs,
                endedAt=cell["ended_at"],
                error=cell_error,
            )
        )
        if ended_at is None:
            ended_at = cell["ended_at"]
        if cell["error"]:
            error = cell["error"]
        if cell["ended_at"]:
            cell_ended_at = datetime.fromisoformat(cell["ended_at"])
            if ended_at and cell_ended_at > datetime.fromisoformat(ended_at):
                ended_at = cell["ended_at"]

    if error:
        try:
            error = json.loads(error)["details"]
        except json.JSONDecodeError:
            pass
    run_result.error = error
    run_result.endedAt = ended_at

    return run_result


def find_run_result_detail_service(
    input: FindRunResultDetailService,
) -> FindRunResultDetailResponse:
    project_root = find_project_root_dir()
    db_manager = SqliteDBManager(project_root)
    db_manager.initialize_database()

    run_records, _ = db_manager.get_run_records(
        canvas=None,
        cell_alias=input.name,
        status="done",
        sort_by="started_at",
        order="DESC",
        limit=1,
        skip=0,
        run_id=input.run_id,
    )

    if len(run_records) == 0:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "run result not found",
        )
    elif run_records[0]["outputs"] is None or len(run_records[0]["outputs"]) == 0:
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "output not found",
        )

    output_paths = []
    try:
        output_paths = ast.literal_eval(run_records[0]["outputs"])
    except Exception:  # noqa
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "output not found",
        )
    output_path = output_paths[0]
    if input.type == "image" or input.type == "html":
        if len(output_paths) == 2:
            if input.type == "image" and output_path.endswith(".html"):
                output_path = output_paths[1]
            elif input.type == "html" and not output_path.endswith(".html"):
                output_path = output_paths[1]
        elif len(output_paths) == 1:
            if input.type == "image" and output_path.endswith(".html"):
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "image not found",
                )
            elif (
                input.type == "html"
                and not output_path.endswith(".html")
                and not output_path.endswith(".txt")
            ):
                raise WarningError(
                    ErrorCode.ExecutionError,
                    ErrorMessage.ExecutionErrorMessage["executionFailed"],
                    "html not found",
                )

    ext = output_path.split(".")[-1]

    try:
        data = convert_file_output(
            input.type, output_path, ext, input.limit, input.skip
        )
    except Exception:  # noqa
        raise WarningError(
            ErrorCode.ExecutionError,
            ErrorMessage.ExecutionErrorMessage["executionFailed"],
            "file type invalid",
        )

    return FindRunResultDetailResponse(
        type=input.type,
        data=data,
    )


def list_scheduled_jobs_service() -> Any:
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if project is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["formatInvalid"],
            "Failed to load morph_project.yml",
        )

    if project.scheduled_jobs is None:
        return []

    return project.scheduled_jobs


def find_scheduled_job_service(input: FindScheduledJobService) -> Any:
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if project is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["formatInvalid"],
            "Failed to load morph_project.yml",
        )

    if project.scheduled_jobs is None or input.name not in project.scheduled_jobs:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Scheduled job not found {input.name}",
        )

    return project.scheduled_jobs[input.name].schedules[input.index]


def create_scheduled_job_service(input: CreateScheduledJobService) -> Any:
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if project is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["formatInvalid"],
            "Failed to load morph_project.yml",
        )

    if project.scheduled_jobs is None:
        project.scheduled_jobs = {}

    if input.name not in project.scheduled_jobs:
        project.scheduled_jobs[input.name] = ScheduledJob(schedules=[input.schedule])
    else:
        project.scheduled_jobs[input.name].schedules.append(input.schedule)

    save_project(project_root, project)

    return project.scheduled_jobs[input.name].schedules


def update_scheduled_job_service(input: UpdateScheduledJobService) -> Any:
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if project is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["formatInvalid"],
            "Failed to load morph_project.yml",
        )

    if project.scheduled_jobs is None or input.name not in project.scheduled_jobs:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Scheduled job not found {input.name}",
        )

    project.scheduled_jobs[input.name].schedules[input.index] = input.schedule
    save_project(project_root, project)

    return project.scheduled_jobs[input.name].schedules[input.index]


def delete_scheduled_job_service(input: DeleteScheduledJobService) -> Any:
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if project is None:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["formatInvalid"],
            "Failed to load morph_project.yml",
        )

    if project.scheduled_jobs is None or input.name not in project.scheduled_jobs:
        raise WarningError(
            ErrorCode.FileError,
            ErrorMessage.FileErrorMessage["notFound"],
            f"Scheduled job not found {input.name}",
        )

    del project.scheduled_jobs[input.name].schedules[input.index]
    save_project(project_root, project)

    return project.scheduled_jobs[input.name].schedules


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

        # Retrieve the result of the file_upload function
        project_root = find_project_root_dir()
        db_manager = SqliteDBManager(project_root)

        run_results = db_manager.get_run_records_by_run_id(run_id)
        run_result = next(
            (result for result in run_results if result["run_id"] == run_id), None
        )

        # Retrieve the saved file path from the output
        output_file = ast.literal_eval(run_result["outputs"])[0] if run_result else None
        with open(output_file, "r") as f:
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
