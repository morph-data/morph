from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, List, Literal, Optional, TypeVar

from typing_extensions import ParamSpec

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
    alias: str | None = None,
    **kwargs: dict[str, Any],
) -> Callable[[Callable[Param, RetType]], Callable[Param, RetType]]:
    name = alias or name

    context = MorphGlobalContext.get_instance()

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

        meta_obj = MorphFunctionMetaObject(
            id=fid,
            name=name or func.__name__,
            function=func,
            description=description,
            variables=variables,
            data_requirements=data_requirements,
            connection=connection,
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
                    connection=meta.connection,
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
                    variables={
                        var_name: {
                            "default": default,
                            "required": required,
                            "type": type,
                        }
                    },
                    data_requirements=None,
                    connection=None,
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
                    variables=meta.variables,
                    data_requirements=meta.data_requirements + [name],
                    connection=meta.connection,
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
                    variables=None,
                    data_requirements=[name],
                    connection=None,
                ),
            )

        @wraps(func)
        def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
            return func(*args, **kwargs)

        return wrapper

    return decorator
