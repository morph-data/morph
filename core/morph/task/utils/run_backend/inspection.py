from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from jinja2 import Environment, nodes
from pydantic import BaseModel

from morph.config.project import MorphProject, default_output_paths

from .errors import MorphFunctionLoadError, MorphFunctionLoadErrorCategory


class ScanResult(BaseModel):
    file_path: str
    checksum: str


class DirectoryScanResult(BaseModel):
    directory: str
    directory_checksums: Dict[str, str]
    items: List[ScanResult]
    sql_contexts: Dict[str, Any]
    errors: List[MorphFunctionLoadError]


def get_checksum(path: Path) -> str:
    """get checksum of file or directory."""
    hash_func = hashlib.sha256()

    if path.is_file():
        with open(str(path), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)

        return hash_func.hexdigest()
    elif path.is_dir():
        for file in sorted(path.glob("**/*")):
            if file.is_file() and (file.suffix == ".py" or file.suffix == ".sql"):
                with open(str(file), "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_func.update(chunk)

        return hash_func.hexdigest()
    else:
        raise ValueError(f"Path {path} is not a file or directory.")


def _import_python_file(
    file_path: str,
) -> tuple[Optional[ScanResult], Optional[MorphFunctionLoadError]]:
    file = Path(file_path)
    if file.suffix != ".py" or file.name == "__init__.py":
        # just skip files that are not python files or __init__.py
        # so it doesn't return neither ScanResult nor MorphFunctionLoadError
        return None, None

    module_name = file.stem
    module_path = file.as_posix()
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None:
        return None, MorphFunctionLoadError(
            category=MorphFunctionLoadErrorCategory.IMPORT_ERROR,
            file_path=module_path,
            name=module_name,
            error="Failed to load module.",
        )

    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        return None, MorphFunctionLoadError(
            category=MorphFunctionLoadErrorCategory.IMPORT_ERROR,
            file_path=module_path,
            name=module_name,
            error="Failed to load module.",
        )

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        import traceback

        error_message = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        return None, MorphFunctionLoadError(
            category=MorphFunctionLoadErrorCategory.IMPORT_ERROR,
            file_path=module_path,
            name=module_name,
            error=error_message,
        )

    return ScanResult(file_path=module_path, checksum=get_checksum(file)), None


def _import_sql_file(
    file_path: str,
) -> tuple[ScanResult | None, dict[str, Any], MorphFunctionLoadError | None]:
    file = Path(file_path)
    if file.suffix != ".sql":
        # just skip files that are not sql files
        # so it doesn't return neither ScanResult nor MorphFunctionLoadError
        return None, {}, None

    module_path = file_path
    sql_contexts: dict[str, Any] = {}
    result = ScanResult(file_path=file.as_posix(), checksum=get_checksum(file))
    with open(file_path, "r") as f:
        content = f.read()
        errors = None
        calls = _parse_jinja_sql(content)
        config = calls["config"][0] if "config" in calls else None
        load_data = calls["load_data"] if "load_data" in calls else []
        variables: Dict[str, Any] = {}
        for variable in calls["variables"] if "variables" in calls else []:
            variables.update({variable: None})
        data_requirements = []
        name = None
        description = None
        kwargs = {}
        if config is not None:
            if "kwargs" in config:
                kwargs = config["kwargs"]
                if "name" in kwargs:
                    name = kwargs["name"]
                if "alias" in kwargs:
                    name = kwargs["alias"]
                if "description" in kwargs:
                    description = kwargs["description"]
        for data in load_data:
            if "args" in data:
                data_requirements.extend(data["args"])

        if name is None:
            name = file.stem
        sql_contexts.update(
            {
                module_path: {
                    "id": module_path,
                    "name": name,
                    "description": description,
                    "output_paths": default_output_paths(
                        ext=".parquet", alias=f"{name}"
                    ),
                    "variables": variables,
                    "data_requirements": data_requirements,
                    **kwargs,
                },
            }
        )

        sql_content = calls["sql"] if "sql" in calls else content
        if ";" in sql_content:
            errors = MorphFunctionLoadError(
                category=MorphFunctionLoadErrorCategory.INVALID_SYNTAX,
                file_path=module_path,
                name=name,
                error="SQL file includes ';'. It's prohibited not to use multiple statements.",
            )

        return result, sql_contexts, errors


def import_files(
    project: Optional[MorphProject],
    directory: str,
    source_paths: list[str] = [],
    extra_paths: list[str] = [],
) -> DirectoryScanResult:
    """import python and sql files from the directory and evaluate morph functions.
    Args:
        directory (str): directory path to scan.
        source_paths (list[str]): list of source paths to scan, which are relative to the directory.
        extra_paths (list[str]): list of extra paths to scan. These paths are absolute paths.
    """
    p = Path(directory)
    results: list[ScanResult] = []
    errors: list[MorphFunctionLoadError] = []
    ignore_dirs = [".local", ".git", ".venv", "__pycache__"]

    search_paths: list[Path] = []
    if len(source_paths) == 0:
        search_paths.append(p)
    else:
        for source_path in source_paths:
            search_paths.append(p / source_path)

    if len(extra_paths) > 0:
        for epath in extra_paths:
            epath_p = Path(epath)
            if not epath_p.exists() or not epath_p.is_dir():
                continue
            search_paths.append(epath_p)

    directory_checksums: dict[str, str] = {}
    sql_contexts: Dict[str, Any] = {}
    for search_path in search_paths:
        for file in search_path.glob("**/*.py"):
            if any(ignore_dir in file.parts for ignore_dir in ignore_dirs):
                continue

            result, error = _import_python_file(file.as_posix())
            if result is not None:
                results.append(result)
            if error is not None:
                errors.append(error)

        for file in search_path.glob("**/*.sql"):
            if any(ignore_dir in file.parts for ignore_dir in ignore_dirs):
                continue

            module_path = file.as_posix()
            result, context, error = _import_sql_file(module_path)
            if result is not None:
                results.append(result)
                sql_contexts.update(context)
            if error is not None:
                errors.append(error)

        directory_checksums[search_path.as_posix()] = get_checksum(search_path)

    return DirectoryScanResult(
        directory=directory,
        directory_checksums=directory_checksums,
        items=results,
        sql_contexts=sql_contexts,
        errors=errors,
    )


def _parse_jinja_sql(template):
    env = Environment()
    parsed_content = env.parse(template)
    calls: Dict[str, Any] = {}
    sqls = []
    variables = []

    def visit_node(node):
        if isinstance(node, nodes.TemplateData):
            sql_query = "\n".join(
                line
                for line in node.data.splitlines()
                if not line.strip().startswith("--")
            )
            if sql_query.strip():
                sqls.append(sql_query.strip())

        elif isinstance(node, nodes.Call) and hasattr(node.node, "name"):
            func_name = cast(str, node.node.name)

            args = {
                "args": [arg.as_const() for arg in node.args],
                "kwargs": {kw.key: kw.value.as_const() for kw in node.kwargs},
            }

            if func_name in calls:
                calls[func_name].append(args)
            else:
                calls[func_name] = [args]

        elif isinstance(node, nodes.Output):
            for child in node.nodes:
                if isinstance(child, nodes.Name):
                    variables.append(child.name)
                elif isinstance(child, nodes.Filter):
                    if isinstance(child.node, nodes.Name):
                        variables.append(child.node.name)

        for child in node.iter_child_nodes():
            visit_node(child)

    visit_node(parsed_content)

    if len(sqls) > 0:
        calls["sql"] = sqls[-1]

    if variables:
        calls["variables"] = variables

    return calls
