import configparser
import os
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from morph.api.cloud.base import MorphApiBaseClient, MorphClientResponse
from morph.api.cloud.types import EnvVarObject
from morph.constants import MorphConstant
from morph.task.utils.morph import find_project_root_dir

MORPH_API_BASE_URL = "https://api.morph-data.io/v0"


class MorphApiKeyClientImpl(MorphApiBaseClient):
    def __init__(self):
        self.project_id = os.environ.get("MORPH_PROJECT_ID", "")
        self.api_url = os.environ.get("MORPH_BASE_URL", MORPH_API_BASE_URL)
        self.api_key = os.environ.get("MORPH_API_KEY", "")

        if self.api_key == "":
            config_path = MorphConstant.MORPH_CRED_PATH
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                if not config.sections():
                    raise ValueError(
                        "No credential entries found. Please run 'morph init'."
                    )
                self.api_key = self.api_key or config.get(
                    "default", "api_key", fallback=""
                )
                if self.api_key == "":
                    raise ValueError(
                        "No api_key found in credential file. Please run 'morph config'."
                    )

        if self.project_id == "":
            from morph.config.project import load_project

            project = load_project(find_project_root_dir())
            if project is None:
                raise ValueError("No project found.")
            elif project.project_id is None:
                raise ValueError(
                    "No project id found. Please fill project_id in morph_project.yml"
                )
            self.project_id = project.project_id

    def get_headers(self) -> Dict[str, Any]:
        return {
            "Contet-Type": "application/json",
            "X-Api-Key": self.api_key,
            "project-id": self.project_id,
        }

    def get_base_url(self) -> str:
        return self.api_url

    def find_database_connection(self) -> MorphClientResponse:
        path = f"project/{self.project_id}/connection"
        return self.request(method="GET", path=path)

    def find_external_connection(self, connection_slug: str) -> MorphClientResponse:
        path = f"external-connection/{connection_slug}"
        return self.request(method="GET", path=path)

    def list_external_connections(self) -> MorphClientResponse:
        path = "external-connection"
        query = {"withAuth": True}
        return self.request(method="GET", path=path, query=query)

    def list_env_vars(self) -> MorphClientResponse:
        path = "env-vars"
        return self.request(method="GET", path=path)

    def override_env_vars(self, env_vars: List[EnvVarObject]) -> MorphClientResponse:
        path = "env-vars/override"
        body = {"envVars": [env_var.model_dump() for env_var in env_vars]}
        return self.request(method="POST", path=path, data=body)

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


T = TypeVar("T", bound=MorphApiBaseClient)


class MorphApiClient(Generic[T]):
    def __init__(self, client_class: Type[T], token: Optional[str] = None):
        self.req: T = self._create_client(client_class, token=token)

    def _create_client(self, client_class: Type[T], token: Optional[str] = None) -> T:
        if client_class is MorphApiKeyClientImpl:
            return cast(T, MorphApiKeyClientImpl())
        else:
            raise ValueError("Invalid client class.")
