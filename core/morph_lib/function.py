from __future__ import annotations

from typing import Any, Dict, Optional

from morph_lib.error import MorphApiError

from morph.config.project import load_project
from morph.task.utils.logging import get_morph_logger
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.execution import run_cell
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObjectCacheManager,
    MorphGlobalContext,
)


def load_data(alias: str, variables: Optional[Dict[str, Any]] = None) -> Any:
    """
    Get execution result of the alias.
    """
    project_root = find_project_root_dir()
    project = load_project(project_root)
    if not project:
        raise MorphApiError("Project configuration not found.")

    context = MorphGlobalContext.get_instance()
    context.partial_load(project_root, alias)

    resource = context.search_meta_object_by_name(alias)
    if not resource:
        raise MorphApiError(f"Resource {alias} not found.")

    meta_obj_cache = MorphFunctionMetaObjectCacheManager().get_cache()

    vars = variables or {}
    logger = get_morph_logger()

    return run_cell(
        project,
        resource,
        vars,
        logger,
        None,
        meta_obj_cache,
    ).result
