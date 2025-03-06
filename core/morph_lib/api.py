from __future__ import annotations

from typing import cast

from morph_lib.error import MorphApiError

from morph.api.cloud.client import MorphApiClient, MorphApiKeyClientImpl
from morph.task.utils.connection import (
    AirtableConnectionOAuth,
    AttioConnectionOAuth,
    BigqueryConnectionOAuth,
    ConnectionYaml,
    FreeeConnectionOAuth,
    GoogleAnalyticsConnectionOAuth,
    HubspotConnectionOAuth,
    IntercomConnectionOAuth,
    LinearConnectionOAuth,
    MailchimpConnectionOAuth,
    NotionConnectionOAuth,
    SalesforceConnectionOAuth,
    StripeConnectionOAuth,
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
    connection_yaml = ConnectionYaml.load_yaml()
    database_connection = ConnectionYaml.find_connection(
        connection_yaml, connection_slug
    )

    if database_connection is not None and (
        isinstance(database_connection, BigqueryConnectionOAuth)
        or isinstance(database_connection, GoogleAnalyticsConnectionOAuth)
        or isinstance(database_connection, SalesforceConnectionOAuth)
        or isinstance(database_connection, NotionConnectionOAuth)
        or isinstance(database_connection, StripeConnectionOAuth)
        or isinstance(database_connection, AttioConnectionOAuth)
        or isinstance(database_connection, AirtableConnectionOAuth)
        or isinstance(database_connection, FreeeConnectionOAuth)
        or isinstance(database_connection, HubspotConnectionOAuth)
        or isinstance(database_connection, IntercomConnectionOAuth)
        or isinstance(database_connection, LinearConnectionOAuth)
        or isinstance(database_connection, MailchimpConnectionOAuth)
    ):
        return database_connection.access_token or ""

    client = MorphApiClient(MorphApiKeyClientImpl)
    response = client.req.find_external_connection(connection_slug)
    if response.is_error():
        raise MorphApiError(f"Failed to get auth token. {response.text}")

    response_json = response.json()
    if (
        response_json["connectionType"] == "mysql"
        or response_json["connectionType"] == "postgres"
        or response_json["connectionType"] == "redshift"
        or response_json["connectionType"] == "mssql"
    ):
        raise MorphApiError(f"No auth token in db connection {connection_slug}")
    elif (
        "accessToken" not in response_json["data"]
        or response_json["data"]["accessToken"] is None
    ):
        raise MorphApiError("Failed to get auth token")

    return cast(str, response_json["data"]["accessToken"])
