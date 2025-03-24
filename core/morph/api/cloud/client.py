import configparser
import os
from functools import wraps
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from morph.api.cloud.base import MorphApiBaseClient, MorphClientResponse
from morph.api.cloud.types import EnvVarObject
from morph.constants import MorphConstant
from morph.task.utils.morph import find_project_root_dir

MORPH_API_BASE_URL = "https://api.morph-data.io/v0"


def validate_project_id(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "project_id") or not self.project_id:
            raise ValueError(
                "No project id found. Please fill project_id in morph_project.yml"
            )
        return method(self, *args, **kwargs)

    return wrapper


class MorphApiKeyClientImpl(MorphApiBaseClient):
    def __init__(self):
        # Initialize default values
        self.project_id = os.environ.get("MORPH_PROJECT_ID", "")
        self.api_url = os.environ.get("MORPH_BASE_URL", MORPH_API_BASE_URL)
        self.api_key = os.environ.get("MORPH_API_KEY", "")

        from morph.config.project import load_project  # avoid circular import

        try:
            project_root = find_project_root_dir()
        except Exception:  # noqa
            project_root = None

        if project_root:
            project = load_project(project_root)
        else:
            project = None

        if project:
            profile = project.profile or "default"
        else:
            profile = "default"

        self.project_id = os.environ.get(
            "MORPH_PROJECT_ID", "" if not project else project.project_id or ""
        )

        self.api_key = os.environ.get("MORPH_API_KEY", "")
        if not self.api_key:
            config_path = MorphConstant.MORPH_CRED_PATH
            if not os.path.exists(config_path):
                raise ValueError(
                    f"Credential file not found at {config_path}. Please run 'morph init'."
                )
            config = configparser.ConfigParser()
            config.read(config_path)
            if not config.has_section(profile):
                raise ValueError(
                    f"No profile '{profile}' found in the credentials file."
                )
            self.api_key = config.get(profile, "api_key", fallback="")

        if not self.api_key:
            raise ValueError(f"No API key found for profile '{profile}'.")

    def get_headers(self) -> Dict[str, Any]:
        return {
            "Contet-Type": "application/json",
            "X-Api-Key": self.api_key,
            "project-id": self.project_id,
        }

    def get_base_url(self) -> str:
        return self.api_url

    @validate_project_id
    def find_database_connection(self) -> MorphClientResponse:
        path = f"project/{self.project_id}/connection"
        return self.request(method="GET", path=path)

    @validate_project_id
    def find_external_connection(self, connection_slug: str) -> MorphClientResponse:
        path = f"external-connection/{connection_slug}"
        return self.request(method="GET", path=path)

    @validate_project_id
    def list_env_vars(self) -> MorphClientResponse:
        path = "env-vars"
        return self.request(method="GET", path=path)

    @validate_project_id
    def override_env_vars(self, env_vars: List[EnvVarObject]) -> MorphClientResponse:
        path = "env-vars/override"
        body = {"envVars": [env_var.model_dump() for env_var in env_vars]}
        return self.request(method="POST", path=path, data=body)

    @validate_project_id
    def list_fields(
        self,
        table_name: str,
        schema_name: Optional[str],
        connection: Optional[str],
    ) -> MorphClientResponse:
        path = f"field/{table_name}"
        query = {}
        if connection:
            path = "external-database-field"
            query.update(
                {
                    "connectionSlug": connection,
                    "tableName": table_name,
                    "schemaName": schema_name,
                }
            )
        return self.request(method="GET", path=path, query=query)

    def check_api_secret(self) -> MorphClientResponse:
        path = "api-secret/check"
        return self.request(method="GET", path=path)

    @validate_project_id
    def verify_api_secret(self) -> MorphClientResponse:
        path = "api-secret/verify"
        body = {"projectId": self.project_id}
        return self.request(method="POST", path=path, data=body)

    @validate_project_id
    def initiate_deployment(
        self,
        project_id: str,
        image_build_log: str,
        image_checksum: str,
        config: Optional[dict[str, Any]] = None,
    ) -> MorphClientResponse:
        path = "deployment"
        body: dict[str, Any] = {
            "projectId": project_id,
            "imageBuildLog": image_build_log,
            "imageChecksum": image_checksum,
        }
        if config:
            body["config"] = config

        return self.request(method="POST", path=path, data=body)

    @validate_project_id
    def execute_deployment(
        self, user_function_deployment_id: str
    ) -> MorphClientResponse:
        path = f"deployment/{user_function_deployment_id}"

        return self.request(
            method="POST",
            path=path,
        )


T = TypeVar("T", bound=MorphApiBaseClient)


class MorphApiClient(Generic[T]):
    def __init__(self, client_class: Type[T], token: Optional[str] = None):
        self.req: T = self._create_client(client_class, token=token)

    def _create_client(self, client_class: Type[T], token: Optional[str] = None) -> T:
        if client_class is MorphApiKeyClientImpl:
            return cast(T, MorphApiKeyClientImpl())
        else:
            raise ValueError("Invalid client class.")
