from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel


class RunStatus(str, Enum):
    DONE = "done"
    TIMEOUT = "timeout"
    IN_PROGRESS = "inProgress"
    FAILED = "failed"


class StackTraceFrame(BaseModel):
    filename: str
    lineno: Optional[int] = None
    name: str
    line: Optional[str] = None


class PythonError(BaseModel):
    type: str
    message: str
    code: str
    stacktrace: str
    structured_stacktrace: List[StackTraceFrame]


GeneralError = str


class CliError(BaseModel):
    type: Literal["python", "general"]
    details: Union[PythonError, GeneralError]
