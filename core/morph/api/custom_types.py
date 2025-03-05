from typing import Any, Dict, List, Literal, Optional

from fastapi import File, UploadFile
from pydantic import BaseModel

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
    type: Literal["json", "html", "markdown"]
    variables: Optional[Dict[str, Any]] = None
    use_cache: Optional[bool] = True
    limit: Optional[int] = None
    skip: Optional[int] = None


class RunFileWithTypeResponse(BaseModel):
    type: Literal["json", "html", "image", "markdown"]
    data: Any


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
# RunResult
# ================================================


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


# ================================================
# Upload File
# ================================================


class UploadFileService(BaseModel):
    file: UploadFile = File(...)
