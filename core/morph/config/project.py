import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from morph.constants import MorphConstant
from morph.task.utils.connection import (
    CONNECTION_TYPE,
    MORPH_DUCKDB_CONNECTION_SLUG,
    MorphConnection,
)
from morph.task.utils.morph import find_project_root_dir


class BuildConfig(BaseModel):
    runtime: Optional[str] = None
    framework: Optional[str] = "morph"
    package_manager: Optional[str] = None
    context: Optional[str] = None
    build_args: Optional[Dict[str, str]] = None


class DeploymentConfig(BaseModel):
    provider: Optional[str] = "aws"
    aws: Optional[Dict[str, Optional[str]]] = None
    gcp: Optional[Dict[str, Optional[str]]] = None


class MorphProject(BaseModel):
    profile: Optional[str] = "default"
    source_paths: List[str] = Field(default_factory=lambda: ["src"])
    default_connection: Optional[str] = MORPH_DUCKDB_CONNECTION_SLUG
    project_id: Optional[str] = Field(default=None)
    package_manager: str = Field(
        default="pip", description="Package manager to use, e.g., pip or poetry."
    )
    build: Optional[BuildConfig] = Field(default_factory=BuildConfig)
    deployment: Optional[DeploymentConfig] = Field(default_factory=DeploymentConfig)

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
            f.write(dump_project_yaml(project))
        return

    config_path = os.path.join(project_root, "morph_project.yml")
    with open(config_path, "w") as f:
        f.write(dump_project_yaml(project))


def dump_project_yaml(project: MorphProject) -> str:
    source_paths = "\n- ".join([""] + project.source_paths)

    # Default values
    build_runtime = ""
    build_framework = ""
    build_package_manager = ""
    build_context = "."
    build_args_str = "\n    # - ARG_NAME=value\n    # - ANOTHER_ARG=value"
    deployment_provider = "aws"
    deployment_aws_region = "us-east-1"
    deployment_aws_memory = "1024"
    deployment_aws_timeout = "300"
    deployment_aws_concurrency = "1"
    deployment_gcp_region = "us-central1"
    deployment_gcp_memory = "1Gi"
    deployment_gcp_cpu = "1"
    deployment_gcp_concurrency = "80"
    deployment_gcp_timeout = "300"

    # Set values if build exists
    if project.build:
        if project.build.runtime:
            build_runtime = project.build.runtime or ""
        if project.build.framework:
            build_framework = project.build.framework or ""
        if project.build.package_manager:
            build_package_manager = project.build.package_manager or ""
        if project.build.context:
            build_context = f"{project.build.context}" or "."
        if project.build.build_args:
            build_args_items = []
            for key, value in project.build.build_args.items():
                build_args_items.append(f"{key}={value}")
            build_args_str = (
                "\n    # - ".join([""] + build_args_items)
                if build_args_items
                else "\n    # - ARG_NAME=value\n    # - ANOTHER_ARG=value"
            )

    # Set values if deployment exists
    if project.deployment:
        if project.deployment.provider:
            deployment_provider = project.deployment.provider or "aws"
        if project.deployment.aws:
            deployment_aws_region = project.deployment.aws.get("region") or "us-east-1"
            deployment_aws_memory = project.deployment.aws.get("memory") or "1024"
            deployment_aws_timeout = project.deployment.aws.get("timeout") or "300"
            deployment_aws_concurrency = (
                project.deployment.aws.get("concurrency") or "1"
            )
        if project.deployment.gcp:
            deployment_gcp_region = (
                project.deployment.gcp.get("region") or "us-central1"
            )
            deployment_gcp_memory = project.deployment.gcp.get("memory") or "1Gi"
            deployment_gcp_cpu = project.deployment.gcp.get("cpu") or "1"
            deployment_gcp_concurrency = (
                project.deployment.gcp.get("concurrency") or "80"
            )
            deployment_gcp_timeout = project.deployment.gcp.get("timeout") or "300"
    else:
        # Use default DeploymentConfig
        deployment_provider = "aws"

    return f"""
version: '1'

# Framework Settings
default_connection: {project.default_connection}
source_paths:{source_paths}

# Cloud Settings
# profile: {project.profile} # Defined in the Profile Section in `~/.morph/credentials`
# project_id: {project.project_id or "null"}

# Build Settings
build:
    # These settings are required when there is no Dockerfile in the project root.
    # They define the environment in which the project will be built
    runtime: {build_runtime} # python3.9, python3.10, python3.11, python3.12
    framework: {build_framework}
    package_manager: {build_package_manager} # pip, poetry, uv
    # These settings are required when there is a Dockerfile in the project root.
    # They define how the Docker image will be built
    # context: {build_context}
    # build_args:{build_args_str}

# Deployment Settings
deployment:
    provider: {deployment_provider} # aws or gcp (default is aws)
    # These settings are used only when you want to customize the deployment settings
    # aws:
    #     region: {deployment_aws_region}
    #     memory: {deployment_aws_memory}
    #     timeout: {deployment_aws_timeout}
    #     concurrency: {deployment_aws_concurrency}
    # gcp:
    #     region: {deployment_gcp_region}
    #     memory: {deployment_gcp_memory}
    #     cpu: {deployment_gcp_cpu}
    #     concurrency: {deployment_gcp_concurrency}
    #     timeout: {deployment_gcp_timeout}
"""
