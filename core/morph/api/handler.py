import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, Header, Security, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from morph.api.auth import auth
from morph.api.error import AuthError, ErrorCode, ErrorMessage, RequestError
from morph.api.service import (
    create_file_service,
    create_scheduled_job_service,
    delete_scheduled_job_service,
    file_upload_service,
    find_run_result_detail_service,
    find_run_result_service,
    find_scheduled_job_service,
    list_resource_service,
    list_run_result_service,
    list_scheduled_jobs_service,
    run_file_service,
    run_file_stream_service,
    run_file_with_type_service,
    update_scheduled_job_service,
)
from morph.api.types import (
    CreateFileRequestBody,
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
    RunFileRequestBody,
    RunFileService,
    RunFileStreamRequestBody,
    RunFileStreamService,
    RunFileWithTypeRequestBody,
    RunFileWithTypeResponse,
    RunFileWithTypeService,
    SuccessResponse,
    UpdateScheduledJobService,
    UploadFileService,
)
from morph.config.project import Schedule

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/cli/run-stream/{name}")
async def vm_run_file_stream(
    name: str,
    body: RunFileStreamRequestBody,
    authorization: str = Header(...),
) -> StreamingResponse:
    try:
        await auth(authorization)
        input = RunFileStreamService(
            name=name,
            variables=body.variables,
        )
    except ValidationError:  # noqa
        content = '3:"Invalid request body."\n\n'
        return StreamingResponse(content=content, media_type="text/event-stream")
    except AuthError:
        content = '3:"Not Authorized."\n\n'
        return StreamingResponse(content=content, media_type="text/event-stream")

    is_error = False

    async def _wrapped_generator():
        nonlocal is_error
        try:
            async for chunk in run_file_stream_service(input):
                yield chunk
        except Exception as e:
            is_error = True
            raise e

    generator = _wrapped_generator()

    error = None
    first_chunk = None
    try:
        first_chunk = await generator.__anext__()
    except Exception as e:
        is_error = True
        error = e

    if is_error:
        return JSONResponse(
            content=str(error),
            status_code=500,
        )

    async def _generate_content():
        if first_chunk:
            yield first_chunk
        async for chunk in generator:
            yield chunk

    return StreamingResponse(
        content=_generate_content(),
        status_code=200,
        media_type="text/event-stream",
        headers={"Transfer-Encoding": "chunked", "Content-Type": "text/event-stream"},
    )


@router.post("/cli/run/{name}/{type}")
def run_file_with_type(
    name: str,
    type: Literal["json", "html", "image", "markdown"],
    body: RunFileWithTypeRequestBody,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    _: str = Security(auth),
) -> RunFileWithTypeResponse:
    try:
        input = RunFileWithTypeService(
            name=name,
            type=type,
            variables=body.variables,
            use_cache=body.useCache,
            limit=limit,
            skip=skip,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return run_file_with_type_service(input)


@router.post("/cli/run/{name}")
def run_file(
    name: str,
    body: RunFileRequestBody,
    _: str = Security(auth),
) -> SuccessResponse:
    try:
        input = RunFileService(
            name=name,
            variables=body.variables,
            run_id=body.runId,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return run_file_service(input)


@router.get("/cli/resource")
def list_resource(
    _: str = Security(auth),
) -> Any:
    return list_resource_service()


@router.post("/cli/file")
def create_file(
    body: CreateFileRequestBody,
    _: str = Security(auth),
) -> SuccessResponse:
    try:
        input = CreateFileService(
            filename=body.filename,
            template=body.template,
            name=body.name,
            description=body.description,
            parent_name=body.parentName,
            connection=body.connection,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return create_file_service(input)


@router.get("/cli/run/{name}")
def list_run_result(
    name: str,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    _: str = Security(auth),
) -> ListRunResultResponse:
    try:
        input = ListRunResultService(name=name, limit=limit, skip=skip)
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return list_run_result_service(input)


@router.get("/cli/run")
def find_run_result(
    runId: str,
    _: str = Security(auth),
) -> FindRunResultResponse:
    try:
        input = FindRunResultService(run_id=runId)
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return find_run_result_service(input)


@router.get("/cli/run/{name}/{runId}/{type}")
def find_run_result_detail(
    name: str,
    runId: str,
    type: Literal["json", "html", "image", "markdown"],
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    _: str = Security(auth),
) -> FindRunResultDetailResponse:
    try:
        input = FindRunResultDetailService(
            name=name,
            run_id=runId,
            type=type,
            limit=limit,
            skip=skip,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return find_run_result_detail_service(input)


@router.get("/cli/morph-project/scheduled-jobs")
def list_scheduled_jobs(
    _: str = Security(auth),
) -> Any:
    return list_scheduled_jobs_service()


@router.get("/cli/morph-project/scheduled-jobs/{name}/schedules/{index}")
def find_scheduled_jobs(
    name: str,
    index: int,
    _: str = Security(auth),
) -> Any:
    try:
        input = FindScheduledJobService(
            name=name,
            index=index,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return find_scheduled_job_service(input)


@router.post("/cli/morph-project/scheduled-jobs/{name}/schedules")
def create_scheduled_jobs(
    name: str,
    body: Schedule,
    _: str = Security(auth),
) -> Any:
    try:
        input = CreateScheduledJobService(
            name=name,
            schedule=body,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return create_scheduled_job_service(input)


@router.put("/cli/morph-project/scheduled-jobs/{name}/schedules/{index}")
def update_scheduled_jobs(
    name: str,
    index: int,
    body: Schedule,
    _: str = Security(auth),
) -> Any:
    try:
        input = UpdateScheduledJobService(
            name=name,
            index=index,
            schedule=body,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return update_scheduled_job_service(input)


@router.delete("/cli/morph-project/scheduled-jobs/{name}/schedules/{index}")
def delete_scheduled_jobs(
    name: str,
    index: int,
    _: str = Security(auth),
) -> Any:
    try:
        input = DeleteScheduledJobService(
            name=name,
            index=index,
        )
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return delete_scheduled_job_service(input)


@router.post("/cli/file-upload")
async def file_upload(
    file: UploadFile = File(...),
    _: str = Security(auth),
) -> Any:
    try:
        input = UploadFileService(file=file)
    except ValidationError as e:
        error_messages = " ".join([str(err["msg"]) for err in e.errors()])
        raise RequestError(
            ErrorCode.RequestError,
            ErrorMessage.RequestErrorMessage["requestBodyInvalid"],
            error_messages,
        )
    return await file_upload_service(input)
