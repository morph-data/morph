from __future__ import annotations

import inspect
import os
from functools import wraps
from typing import Any, Callable, List, Literal, Optional, TypeVar

from typing_extensions import ParamSpec

from morph.config.project import load_project
from morph.constants import MorphConstant
from morph.task.utils.knowledge.inspection import (
    MorphKnowledgeMetaObjectGlossaryTerm,
    MorphKnowledgeMetaObjectSchema,
)
from morph.task.utils.morph import find_project_root_dir

from .state import MorphFunctionMetaObject, MorphGlobalContext

Param = ParamSpec("Param")
RetType = TypeVar("RetType")
F = TypeVar("F", bound=Callable)


def _get_morph_function_id(func: Callable) -> str:
    if hasattr(func, "__morph_fid__"):
        return str(func.__morph_fid__)
    else:
        filename = inspect.getfile(func)
        function_name = func.__name__
        new_fid = f"{filename}:{function_name}"
        func.__morph_fid__ = new_fid  # type: ignore
        return new_fid


def func(
    name: str | None = None,
    description: str | None = None,
    title: str | None = None,
    schemas: list[MorphKnowledgeMetaObjectSchema] | None = None,
    terms: list[MorphKnowledgeMetaObjectGlossaryTerm] | None = None,
    output_paths: list[str] | None = None,
    output_type: Optional[
        Literal["dataframe", "csv", "visualization", "markdown", "json"]
    ] = None,
    result_cache_ttl: Optional[int] = None,
    alias: str | None = None,
    **kwargs: dict[str, Any],
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    name = alias or name

    context = MorphGlobalContext.get_instance()
    project = load_project(find_project_root_dir())

    def decorator(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
        fid = _get_morph_function_id(func)

        variables = kwargs.get("variables", {})

        data_req_value = kwargs.get("data_requirements", [])  # type: ignore
        data_requirements: List[str] = (
            data_req_value if isinstance(data_req_value, list) else []
        )

        connection = kwargs.get("connection")
        if not isinstance(connection, (str, type(None))):
            connection = None

        output_paths_ = output_paths
        if project and project.output_paths and len(project.output_paths) > 0:
            project_output_paths: List[str] = []
            for project_output_path in project.output_paths:
                if (
                    os.path.isdir(project_output_path)
                    and "ext()" not in project_output_path
                ):
                    project_output_paths.append(
                        f"{project_output_path}/{{name}}/{{run_id}}{{ext()}}"
                    )
            output_paths_ = (
                project_output_paths if len(project_output_paths) > 0 else output_paths_
            )
        if output_paths_ is None:
            output_paths_ = [
                f"{MorphConstant.TMP_MORPH_DIR}/{{name}}/{{run_id}}{{ext()}}"
            ]

        meta_obj = MorphFunctionMetaObject(
            id=fid,
            name=name or func.__name__,
            function=func,
            description=description,
            title=title,
            schemas=schemas,
            terms=terms,
            variables=variables,
            data_requirements=data_requirements,
            output_paths=output_paths_,
            output_type=output_type,
            connection=connection,
            result_cache_ttl=result_cache_ttl,
        )
        context.update_meta_object(fid, meta_obj)

        @wraps(func)
        def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
            return func(*args, **kwargs)

        return wrapper

    # check if decorator is called with args
    if callable(name):
        func = name  # type: ignore
        name = func.__name__
        description = None
        return decorator(func)

    return decorator


def variables(
    var_name: str,
    default: Optional[Any] = None,
    required: Optional[bool] = False,
    type: Optional[Literal["str", "bool", "int", "float", "dict", "list"]] = None,
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    """
    variables
    {
        "var_name": {
            "default": default,
            "required": required,
            "type": type,
        }
    }
    """
    context = MorphGlobalContext.get_instance()

    def decorator(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
        fid = _get_morph_function_id(func)
        meta = context.search_meta_object(fid)
        if meta and meta.variables:
            context.update_meta_object(
                fid,
                MorphFunctionMetaObject(
                    id=fid,
                    name=meta.name,
                    function=meta.function,
                    description=meta.description,
                    title=meta.title,
                    schemas=meta.schemas,
                    terms=meta.terms,
                    variables={
                        **meta.variables,
                        **{
                            var_name: {
                                "default": default,
                                "required": required,
                                "type": type,
                            }
                        },
                    },
                    data_requirements=meta.data_requirements,
                    output_paths=meta.output_paths,
                    output_type=meta.output_type,
                    connection=meta.connection,
                    result_cache_ttl=meta.result_cache_ttl,
                ),
            )
        else:
            context.update_meta_object(
                fid,
                MorphFunctionMetaObject(
                    id=fid,
                    name=func.__name__,
                    function=func,
                    description=None,
                    title=None,
                    schemas=None,
                    terms=None,
                    variables={
                        var_name: {
                            "default": default,
                            "required": required,
                            "type": type,
                        }
                    },
                    data_requirements=None,
                    output_paths=None,
                    output_type=None,
                    connection=None,
                    result_cache_ttl=None,
                ),
            )

        @wraps(func)
        def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
            return func(*args, **kwargs)

        return wrapper

    return decorator


def load_data(
    name: str,
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    context = MorphGlobalContext.get_instance()

    def decorator(func: Callable[Param, RetType]) -> Callable[Param, RetType]:
        fid = _get_morph_function_id(func)
        meta = context.search_meta_object(fid)
        if meta and meta.data_requirements:
            context.update_meta_object(
                fid,
                MorphFunctionMetaObject(
                    id=fid,
                    name=meta.name,
                    function=meta.function,
                    description=meta.description,
                    title=meta.title,
                    schemas=meta.schemas,
                    terms=meta.terms,
                    variables=meta.variables,
                    data_requirements=meta.data_requirements + [name],
                    output_paths=meta.output_paths,
                    output_type=meta.output_type,
                    connection=meta.connection,
                    result_cache_ttl=meta.result_cache_ttl,
                ),
            )
        else:
            context.update_meta_object(
                fid,
                MorphFunctionMetaObject(
                    id=fid,
                    name=func.__name__,
                    function=func,
                    description=None,
                    title=None,
                    schemas=None,
                    terms=None,
                    variables=None,
                    data_requirements=[name],
                    output_paths=None,
                    output_type=None,
                    connection=None,
                    result_cache_ttl=None,
                ),
            )

        @wraps(func)
        def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
            return func(*args, **kwargs)

        return wrapper

    return decorator
