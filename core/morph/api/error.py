from __future__ import annotations

from typing import Optional


class ApiBaseError(Exception):
    status: int
    code: str
    message: str
    detail: Optional[str] = None

    def __init__(
        self, code: dict[str, str], message: str, detail: Optional[str] = None
    ):
        self.code = code["code"]
        self.message = message
        self.detail = detail


class WarningError(ApiBaseError):
    status = 200


class RequestError(ApiBaseError):
    status = 400


class AuthError(ApiBaseError):
    status = 401


class InternalError(ApiBaseError):
    status = 500

    def __init__(self):
        self.code = "internal_server_error"
        self.message = "Unexpected error occurred while processing the request."


class ErrorMessage:
    RequestErrorMessage = {
        "requestBodyInvalid": "Invalid request body.",
    }
    AuthErrorMessage = {
        "notAuthorized": "Not authorized.",
        "mockJsonInvalid": "Invalid mock json.",
        "tokenInvalid": "Invalid token.",
    }
    FileErrorMessage = {
        "notFound": "File not found.",
        "createFailed": "Failed to create file.",
        "formatInvalid": "Invalid file format.",
    }
    ExecutionErrorMessage = {
        "executionFailed": "Execution failed.",
        "unexpectedResult": "Unexpected result.",
    }


class ErrorCode:
    RequestError = {"code": "request_error"}
    AuthError = {"code": "auth_error"}
    FileError = {"code": "file_error"}
    ExecutionError = {"code": "execution_error"}
