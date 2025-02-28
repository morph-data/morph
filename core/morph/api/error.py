from __future__ import annotations

from typing import List, Optional


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


def render_error_html(error_messages: List[str]) -> str:
    error_traceback = "\n".join(
        [
            f"<p>Error {i+1}:</p><pre>{error}</pre>"
            for i, error in enumerate(error_messages)
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internal Server Error</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f8f9fa;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }}
        h1 {{
            color: #dc3545;
        }}
        pre {{
            background: #f1f1f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Internal Server Error</h1>
        <p>The server encountered an internal error and was unable to complete your request.</p>
        <h2>Traceback:</h2>
        {error_traceback}
    </div>
</body>
</html>"""
