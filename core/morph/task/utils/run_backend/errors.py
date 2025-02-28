import linecache
import traceback
from enum import Enum
from typing import List

from colorama import Fore
from pydantic import BaseModel


class MorphFunctionLoadErrorCategory(str, Enum):
    IMPORT_ERROR = "IMPORT_ERROR"
    DUPLICATED_ALIAS = "DUPLICATED_ALIAS"
    MISSING_ALIAS = "MISSING_ALIAS"
    CYCLIC_ALIAS = "CYCLIC_ALIAS"
    INVALID_SYNTAX = "INVALID_SYNTAX"


class MorphFunctionLoadError(BaseModel):
    category: MorphFunctionLoadErrorCategory
    file_path: str
    name: str
    error: str

    @staticmethod
    def format_errors(errors: List["MorphFunctionLoadError"]) -> str:
        error_txt = [
            "BOOM!💣 Failed to compile file before executing. No log data is saved in case of compilation errors. Please resolve the errors and try again.🔧\n"
        ]
        for i, error in enumerate(errors):
            error_txt.append(
                f"""{Fore.RED}[ERROR No.{i+1}]
{Fore.RED}[error]: {error.category.value}
{Fore.RED}[name]: {error.name}
{Fore.RED}[filepath]: {error.file_path}
{Fore.RED}[detail]: {error.error}"""
            )
        return "\n".join(error_txt)


def logging_file_error_exception(exc: BaseException, target_file: str) -> str:
    tb = exc.__traceback__
    filtered_traceback = []
    error_txt = []

    error_txt.append(f"{type(exc).__name__}: {str(exc)}\n")

    while tb is not None:
        frame = tb.tb_frame
        code = frame.f_code
        if target_file in code.co_filename:
            filtered_traceback.append(
                {
                    "filename": code.co_filename,
                    "lineno": tb.tb_lineno,
                    "name": code.co_name,
                    "line": linecache.getline(code.co_filename, tb.tb_lineno).strip(),
                }
            )
        tb = tb.tb_next

    for entry in filtered_traceback:
        error_txt.append(
            f'File "{entry["filename"]}", line {entry["lineno"]}, in {entry["name"]}\n'
            f'    {entry["line"]}\n'
        )

    error_txt.append("\nFull traceback:\n")
    error_txt.append("".join(traceback.format_tb(exc.__traceback__)))

    return "".join(error_txt)
