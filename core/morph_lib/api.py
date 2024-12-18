from __future__ import annotations

import os
from typing import Any, Dict, cast

import requests
import urllib3
from morph_lib.error import MorphApiError
from pydantic import BaseModel
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)


# ===============================================
#
# Implementation
#
# ===============================================
class EnvVars(BaseModel):
    workspace_id: str
    base_url: str
    team_slug: str
    api_key: str


def _canonicalize_base_url(base_url: str) -> str:
    if base_url.startswith("http"):
        return base_url
    else:
        return f"https://{base_url}"


def _read_configuration_from_env() -> EnvVars:
    """
    Read configuration from environment variables
    These variables are loaded from ini file when the morph run command is executed
    """
    workspace_id_value = os.getenv("MORPH_WORKSPACE_ID", "")
    base_url_value = os.getenv("MORPH_BASE_URL", "")
    team_slug_value = os.getenv("MORPH_TEAM_SLUG", "")
    api_key_value = os.getenv("MORPH_API_KEY", "")

    return EnvVars(
        workspace_id=workspace_id_value,
        base_url=base_url_value,
        team_slug=team_slug_value,
        api_key=api_key_value,
    )


# ===============================================
#
# Functions
#
# ===============================================


def get_auth_token(connection_slug: str) -> str:
    """
    Get and refresh the authentication token from environment variables.
    Make sure to set the environment variables before calling this function.
    @param: connection_slug: The connection slug on morph app
    """
    config_from_env = _read_configuration_from_env()
    base_url = config_from_env.base_url
    team_slug = config_from_env.team_slug
    api_key = config_from_env.api_key

    headers = {
        "teamSlug": team_slug,
        "X-Api-Key": api_key,
    }

    url = f"{_canonicalize_base_url(base_url)}/external-connection/{connection_slug}"

    try:
        response = requests.get(url, headers=headers, verify=True)
    except Exception as e:
        raise MorphApiError(f"get_auth_token error: {e}")

    if response.status_code != 200:
        raise MorphApiError(response.text)
    response_json: Dict[str, Any] = response.json()
    if (
        "error" in response_json
        and "subCode" in response_json
        and "message" in response_json
    ):
        raise MorphApiError(response_json["message"])

    if (
        response_json["connectionType"] == "mysql"
        or response_json["connectionType"] == "postgres"
        or response_json["connectionType"] == "redshift"
    ):
        raise MorphApiError(f"No auth token in db connection {connection_slug}")
    elif (
        "accessToken" not in response_json["data"]
        or response_json["data"]["accessToken"] is None
    ):
        raise MorphApiError("Failed to get auth token")

    return cast(str, response_json["data"]["accessToken"])
