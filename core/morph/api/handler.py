import json
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, Header, Security, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from morph.api.auth import auth
from morph.api.custom_types import (
    RunFileRequestBody,
    RunFileService,
    RunFileStreamRequestBody,
    RunFileStreamService,
    RunFileWithTypeRequestBody,
    RunFileWithTypeResponse,
    RunFileWithTypeService,
    SuccessResponse,
    UploadFileService,
)
from morph.api.error import (
    ApiBaseError,
    AuthError,
    ErrorCode,
    ErrorMessage,
    InternalError,
    RequestError,
)
from morph.api.service import (
    file_upload_service,
    list_resource_service,
    run_file_service,
    run_file_stream_service,
    run_file_with_type_service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/cli/run-stream/{name}")
async def vm_run_file_stream(
    name: str,
    body: RunFileStreamRequestBody,
    authorization: str = Header(None),
    x_api_key: str = Header(None),
) -> StreamingResponse:
    try:
        await auth(authorization, x_api_key)
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
        if isinstance(error, ApiBaseError):
            return StreamingResponse(
                content=json.dumps(
                    {
                        "error": {
                            "code": error.code,
                            "message": error.message,
                            "detail": error.detail,
                        }
                    }
                ),
                status_code=InternalError().status,
                media_type="text/event-stream",
                headers={
                    "Transfer-Encoding": "chunked",
                    "Content-Type": "text/event-stream",
                },
            )
        return StreamingResponse(
            content=json.dumps(
                {
                    "error": {
                        "code": InternalError().code,
                        "message": InternalError().message,
                        "detail": str(error),
                    }
                }
            ),
            status_code=InternalError().status,
            media_type="text/event-stream",
            headers={
                "Transfer-Encoding": "chunked",
                "Content-Type": "text/event-stream",
            },
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
    type: Literal["json", "html", "markdown"],
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
