from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import File, UploadFile
from pydantic import BaseModel

from morph.config.project import Schedule

# ================================================
# Success
# ================================================


class SuccessResponse(BaseModel):
    message: str


# ================================================
# RunFileWithType
# ================================================


class RunFileWithTypeRequestBody(BaseModel):
    variables: Optional[Dict[str, Any]] = None
    useCache: Optional[bool] = True


class RunFileWithTypeService(BaseModel):
    name: str
    type: Literal["json", "html", "image", "markdown"]
    variables: Optional[Dict[str, Any]] = None
    use_cache: Optional[bool] = True
    limit: Optional[int] = None
    skip: Optional[int] = None


class RunFileWithTypeResponse(BaseModel):
    type: Literal["json", "html", "image", "markdown"]
    data: Union[str, Dict[str, Any]]


# ================================================
# RunFile
# ================================================


class RunFileRequestBody(BaseModel):
    variables: Optional[Dict[str, Any]] = None
    runId: Optional[str] = None


class RunFileService(BaseModel):
    name: str
    variables: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None


# ================================================
# RunFileStream
# ================================================


class RunFileStreamRequestBody(BaseModel):
    variables: Optional[Dict[str, Any]] = None


class RunFileStreamService(BaseModel):
    name: str
    variables: Optional[Dict[str, Any]] = None


# ================================================
# CreateFile
# ================================================


class CreateFileRequestBody(BaseModel):
    filename: str
    template: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parentName: Optional[str] = None
    connection: Optional[str] = None


class CreateFileService(BaseModel):
    filename: str
    template: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parent_name: Optional[str] = None
    connection: Optional[str] = None


# ================================================
# ListRunResult
# ================================================


class ListRunResultService(BaseModel):
    name: str
    limit: Optional[int] = 50
    skip: Optional[int] = 0


class RunResultUnit(BaseModel):
    name: str
    status: str
    startedAt: str
    logs: List[str]
    outputs: List[str]
    endedAt: Optional[str] = None
    error: Optional[str] = None


class RunResult(BaseModel):
    runId: str
    cells: List[RunResultUnit]
    status: str
    startedAt: str
    endedAt: Optional[str] = None
    error: Optional[str] = None


class ListRunResultResponse(BaseModel):
    count: int
    items: List[RunResult]


# ================================================
# FindRunResult
# ================================================


class FindRunResultService(BaseModel):
    run_id: str


FindRunResultResponse = RunResult


# ================================================
# FindRunResultDetail
# ================================================


class FindRunResultDetailService(BaseModel):
    run_id: str
    name: str
    type: Literal["json", "html", "image", "markdown"]
    limit: Optional[int] = None
    skip: Optional[int] = None


class FindRunResultDetailResponse(BaseModel):
    type: Literal["json", "html", "image", "markdown"]
    data: Union[str, Dict[str, Any]]


# ================================================
# Find Scheduled Job
# ================================================


class FindScheduledJobService(BaseModel):
    name: str
    index: int


# ================================================
# Create Scheduled Job
# ================================================


class CreateScheduledJobService(BaseModel):
    name: str
    schedule: Schedule


# ================================================
# Update Scheduled Job
# ================================================


class UpdateScheduledJobService(BaseModel):
    name: str
    index: int
    schedule: Schedule


# ================================================
# Delete Scheduled Job
# ================================================


class DeleteScheduledJobService(BaseModel):
    name: str
    index: int


# ================================================
# Upload File
# ================================================


class UploadFileService(BaseModel):
    file: UploadFile = File(...)
