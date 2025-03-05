import os
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from morph.constants import MorphConstant
from morph.task.utils.connection import (
    CONNECTION_TYPE,
    MORPH_DUCKDB_CONNECTION_SLUG,
    MorphConnection,
)
from morph.task.utils.morph import find_project_root_dir


class MorphProject(BaseModel):
    profile: Optional[str] = "default"
    source_paths: List[str] = Field(default_factory=lambda: ["src"])
    default_connection: Optional[str] = MORPH_DUCKDB_CONNECTION_SLUG
    project_id: Optional[str] = Field(default=None)
    package_manager: str = Field(
        default="pip", description="Package manager to use, e.g., pip or poetry."
    )

    class Config:
        arbitrary_types_allowed = True


def default_output_paths(ext: str, alias: str) -> List[str]:
    project_root = find_project_root_dir()
    if not os.access(project_root, os.W_OK):
        return [f"{MorphConstant.TMP_MORPH_DIR}/cache/{alias}{ext}"]
    return [f"{project_root}/.morph/cache/{alias}{ext}"]


def default_initial_project() -> MorphProject:
    return MorphProject()


def load_project(project_root: str) -> Optional[MorphProject]:
    config_path = os.path.join(project_root, "morph_project.yml")
    old_config_path = os.path.join(project_root, "morph_project.yaml")
    if not os.path.exists(config_path) and not os.path.exists(old_config_path):
        return None
    elif not os.path.exists(config_path):
        config_path = old_config_path

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        save_project(project_root, default_initial_project())
        return default_initial_project()

    if "default_connection" in data and isinstance(data["default_connection"], dict):
        connection_data = data["default_connection"]
        connection_type = connection_data.get("type")

        if connection_type == CONNECTION_TYPE.morph.value:
            default_connection_dict = MorphConnection(**connection_data)
            if default_connection_dict.connection_slug is not None:
                data["default_connection"] = default_connection_dict.connection_slug
            elif default_connection_dict.database_id is not None:
                data["default_connection"] = MORPH_DUCKDB_CONNECTION_SLUG
        else:
            raise ValueError(f"Unknown connection type: {connection_type}")

    return MorphProject(**data)


def save_project(project_root: str, project: MorphProject) -> None:
    old_config_path = os.path.join(project_root, "morph_project.yaml")
    if os.path.exists(old_config_path):
        with open(old_config_path, "w") as f:
            yaml.safe_dump(project.model_dump(), f)
        return

    config_path = os.path.join(project_root, "morph_project.yml")
    with open(config_path, "w") as f:
        yaml.safe_dump(project.model_dump(), f)
