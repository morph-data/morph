import configparser
import os
import urllib.parse
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from morph.api.cloud.base import MorphApiBaseClient, MorphClientResponse
from morph.api.cloud.types import EnvVarObject
from morph.constants import MorphConstant

MORPH_API_BASE_URL = "https://api.morph-data.io/v0"


class MorphApiTokenClientImpl(MorphApiBaseClient):
    def __init__(self, token: str):
        self.team_slug = os.environ.get("MORPH_TEAM_SLUG", "")
        self.workspace_id = os.environ.get("MORPH_WORKSPACE_ID", "")
        self.api_url = os.environ.get("MORPH_BASE_URL", MORPH_API_BASE_URL)
        if self.team_slug == "" or self.workspace_id == "" or self.api_url == "":
            raise ValueError(
                "MORPH_TEAM_SLUG, MORPH_WORKSPACE_ID, MORPH_BASE_URL should be set in environment variables"
            )
        parsed_api_url = urllib.parse.urlparse(self.api_url)
        base_url = urllib.parse.urlunparse(
            (parsed_api_url.scheme, parsed_api_url.netloc, "", "", "", "")
        )
        self.api_url = base_url.replace("api", "dashboard-api")
        self.token = token

    def get_headers(self) -> Dict[str, Any]:
        return {
            "Contet-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "TeamSlug": self.team_slug,
        }

    def get_base_url(self) -> str:
        return self.api_url

    def find_user(self) -> MorphClientResponse:
        path = f"database/{self.workspace_id}/check-user"
        return self.request(method="GET", path=path)


class MorphApiKeyClientImpl(MorphApiBaseClient):
    def __init__(self):
        self.workspace_id = os.environ.get("MORPH_WORKSPACE_ID", "")
        self.api_url = os.environ.get("MORPH_BASE_URL", MORPH_API_BASE_URL)
        self.api_key = os.environ.get("MORPH_API_KEY", "")
        if self.workspace_id == "" or self.api_url == "" or self.api_key == "":
            config_path = MorphConstant.MORPH_CRED_PATH
            if os.path.exists(config_path):
                config = configparser.ConfigParser()
                config.read(config_path)
                if not config.sections():
                    raise ValueError(
                        "No credential entries found. Please run 'morph init'."
                    )
                self.api_url = self.api_url or (
                    config.get("default", "app_url", fallback="") or MORPH_API_BASE_URL
                )
                self.workspace_id = (
                    self.workspace_id
                    or config.get("default", "workspace_id", fallback="")
                    or config.get("default", "database_id", fallback="")
                )
                self.api_key = self.api_key or config.get(
                    "default", "api_key", fallback=""
                )

    def get_headers(self) -> Dict[str, Any]:
        return {
            "Contet-Type": "application/json",
            "X-Api-Key": self.api_key,
        }

    def get_base_url(self) -> str:
        return self.api_url

    def find_database_connection(self) -> MorphClientResponse:
        path = f"database/{self.workspace_id}/connection"
        return self.request(method="GET", path=path)

    def find_external_connection(self, connection_slug: str) -> MorphClientResponse:
        path = f"external-connection/{connection_slug}"
        return self.request(method="GET", path=path)

    def list_external_connections(self) -> MorphClientResponse:
        path = "external-connection"
        query = {"withAuth": True}
        return self.request(method="GET", path=path, query=query)

    def list_env_vars(self) -> MorphClientResponse:
        path = f"{self.workspace_id}/env-vars"
        return self.request(method="GET", path=path)

    def override_env_vars(self, env_vars: List[EnvVarObject]) -> MorphClientResponse:
        path = f"{self.workspace_id}/env-vars/override"
        body = {"envVars": [env_var.model_dump() for env_var in env_vars]}
        return self.request(method="POST", path=path, data=body)

    def list_fields(
        self,
        table_name: str,
        schema_name: Optional[str],
        connection: Optional[str],
    ) -> MorphClientResponse:
        path = f"{self.workspace_id}/field/{table_name}"
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

    def list_workspaces(self) -> MorphClientResponse:
        path = "database"
        return self.request(method="GET", path=path)

    def find_team(self) -> MorphClientResponse:
        path = "team"
        return self.request(method="GET", path=path)


T = TypeVar("T", bound=MorphApiBaseClient)


class MorphApiClient(Generic[T]):
    def __init__(self, client_class: Type[T], token: Optional[str] = None):
        self.req: T = self._create_client(client_class, token=token)

    def _create_client(self, client_class: Type[T], token: Optional[str] = None) -> T:
        if client_class is MorphApiKeyClientImpl:
            return cast(T, MorphApiKeyClientImpl())
        elif client_class is MorphApiTokenClientImpl:
            if not token:
                raise ValueError("token is missing.")
            return cast(T, MorphApiTokenClientImpl(token=token))
        else:
            raise ValueError("Invalid client class.")
