import json
import os
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

import click
import requests
import yaml
from pydantic import BaseModel, ConfigDict, Field

from morph.api.cloud.client import MorphApiClient, MorphApiKeyClientImpl
from morph.constants import MorphConstant

MORPH_DUCKDB_CONNECTION_SLUG = "DUCKDB"


class CONNECTION_TYPE(str, Enum):
    morph = "morph"
    postgres = "postgres"
    mysql = "mysql"
    mssql = "mssql"
    redshift = "redshift"
    snowflake = "snowflake"
    bigquery = "bigquery"
    googleAnalytics = "googleAnalytics"
    salesforce = "salesforce"
    notion = "notion"
    stripe = "stripe"
    attio = "attio"
    airtable = "airtable"
    freee = "freee"
    hubspot = "hubspot"
    intercom = "intercom"
    linear = "linear"
    mailchimp = "mailchimp"
    athena = "athena"
    duckdb = "duckdb"


class CONNECTION_DETAIL_TYPE(str, Enum):
    morph = "morph"
    postgres = "postgres"
    mysql = "mysql"
    mssql = "mssql"
    redshift = "redshift"
    snowflake_user_password = "snowflake_user_password"
    snowflake_key_pair = "snowflake_key_pair"
    snowflake_key_pair_file = "snowflake_key_pair_file"
    snowflake_oauth = "snowflake_oauth"
    bigquery_oauth = "bigquery_oauth"
    bigquery_service_account = "bigquery_service_account"
    bigquery_service_account_json = "bigquery_service_account_json"
    google_analytics_oauth = "google_analytics_oauth"
    salesforce_oauth = "salesforce_oauth"
    notion_oauth = "notion_oauth"
    stripe_oauth = "stripe_oauth"
    attio_oauth = "attio_oauth"
    airtable_oauth = "airtable_oauth"
    freee_oauth = "freee_oauth"
    hubspot_oauth = "hubspot_oauth"
    intercom_oauth = "intercom_oauth"
    linear_oauth = "linear_oauth"
    mailchimp_oauth = "mailchimp_oauth"
    athena = "athena"
    duckdb = "duckdb"


class CONNECTION_METHOD(str, Enum):
    user_password = "user_password"
    oauth = "oauth"
    key_pair = "key_pair"
    key_pair_file = "key_pair_file"
    service_account = "service_account"
    service_account_json = "service_account_json"


class MorphConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.morph]
    database_id: Optional[str] = None
    connection_slug: Optional[str] = None

    @classmethod
    def validate(cls, v):
        if v.database_id is None and v.connection_slug is None:
            raise ValueError(
                "Either 'database_id' or 'connection_slug' must be provided, both cannot be None."
            )
        return v

    model_config = ConfigDict(use_enum_values=True)


class PostgresqlConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.postgres]
    host: str
    user: str
    password: str
    port: int
    dbname: str
    schema_: Optional[str] = Field(..., alias="schema")
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None
    timezone: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class MysqlConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.mysql]
    host: str
    user: str
    password: str
    port: int
    dbname: str
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class SQLServerConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.mssql]
    host: str
    user: str
    password: str
    port: int
    dbname: str
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class RedshiftConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.redshift]
    host: str
    user: str
    password: str
    port: int
    dbname: str
    schema_: Optional[str] = Field(..., alias="schema")
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class DuckDBConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.duckdb]

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class SnowflakeConnectionUserPassword(BaseModel):
    type: Literal[CONNECTION_TYPE.snowflake]
    method: Literal[CONNECTION_DETAIL_TYPE.snowflake_user_password]
    account: str
    database: str
    user: str
    password: str
    role: str
    warehouse: str
    schema_: Optional[str] = Field(..., alias="schema")

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class SnowflakeConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.snowflake]
    method: Literal[CONNECTION_DETAIL_TYPE.snowflake_oauth]
    account: str
    database: str
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    role: str
    warehouse: str
    code_verifier: str
    schema_: Optional[str] = Field(..., alias="schema")
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class SnowflakeConnectionKeyPair(BaseModel):
    type: Literal[CONNECTION_TYPE.snowflake]
    method: Literal[CONNECTION_DETAIL_TYPE.snowflake_key_pair]
    account: str
    username: str
    database: str
    key_pair: str
    role: str
    warehouse: str
    schema_: Optional[str] = Field(..., alias="schema")
    passphrase: Optional[str] = None
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class SnowflakeConnectionKeyPairFile(BaseModel):
    type: Literal[CONNECTION_TYPE.snowflake]
    method: Literal[CONNECTION_DETAIL_TYPE.snowflake_key_pair_file]
    account: str
    username: str
    database: str
    key_pair_path: str
    role: str
    warehouse: str
    schema_: Optional[str] = Field(..., alias="schema")
    passphrase: Optional[str] = None
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class BigqueryConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.bigquery]
    method: Literal[CONNECTION_DETAIL_TYPE.bigquery_oauth]
    project: str
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    dataset: Optional[str] = None
    location: Optional[str] = None
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class BigqueryConnectionServiceAccount(BaseModel):
    type: Literal[CONNECTION_TYPE.bigquery]
    method: Literal[CONNECTION_DETAIL_TYPE.bigquery_service_account]
    project: str
    keyfile: str
    dataset: Optional[str] = None
    location: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class BigqueryConnectionServiceAccountJsonKeyFile(BaseModel):
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str
    location: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class BigqueryConnectionServiceAccountJson(BaseModel):
    type: Literal[CONNECTION_TYPE.bigquery]
    method: Literal[CONNECTION_DETAIL_TYPE.bigquery_service_account_json]
    project: str
    keyfile_json: BigqueryConnectionServiceAccountJsonKeyFile
    dataset: Optional[str] = None
    location: Optional[str] = None
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class AthenaConnection(BaseModel):
    type: Literal[CONNECTION_TYPE.athena]
    access_key: str
    secret_key: str
    session_token: str
    region: str
    catalog: str
    database: Optional[str] = None
    work_group: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class GoogleAnalyticsConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.googleAnalytics]
    method: Literal[CONNECTION_DETAIL_TYPE.google_analytics_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class SalesforceConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.salesforce]
    method: Literal[CONNECTION_DETAIL_TYPE.salesforce_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None
    custom_domain_url: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class NotionConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.notion]
    method: Literal[CONNECTION_DETAIL_TYPE.notion_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class StripeConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.stripe]
    method: Literal[CONNECTION_DETAIL_TYPE.stripe_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class AttioConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.attio]
    method: Literal[CONNECTION_DETAIL_TYPE.attio_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class AirtableConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.airtable]
    method: Literal[CONNECTION_DETAIL_TYPE.airtable_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class FreeeConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.freee]
    method: Literal[CONNECTION_DETAIL_TYPE.freee_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class HubspotConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.hubspot]
    method: Literal[CONNECTION_DETAIL_TYPE.hubspot_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class IntercomConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.intercom]
    method: Literal[CONNECTION_DETAIL_TYPE.intercom_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class LinearConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.linear]
    method: Literal[CONNECTION_DETAIL_TYPE.linear_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class MailchimpConnectionOAuth(BaseModel):
    type: Literal[CONNECTION_TYPE.mailchimp]
    method: Literal[CONNECTION_DETAIL_TYPE.mailchimp_oauth]
    refresh_token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    access_token: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class ExternalConnectionAuth(BaseModel):
    authType: str
    data: Optional[Dict[str, Any]] = None


class ExternalConnection(BaseModel):
    connectionId: str
    connectionSlug: str
    connectionType: str
    data: Dict[str, Any]
    createdAt: str
    category: str
    connectionAuth: Optional[ExternalConnectionAuth] = None
    databaseIds: List[str] = Field(default_factory=list)


class ExternalConnectionListResponse(BaseModel):
    items: List[ExternalConnection]
    count: int


DatabaseConnection = Union[
    MorphConnection,
    PostgresqlConnection,
    MysqlConnection,
    SQLServerConnection,
    RedshiftConnection,
    SnowflakeConnectionUserPassword,
    SnowflakeConnectionKeyPair,
    BigqueryConnectionServiceAccount,
    BigqueryConnectionServiceAccountJson,
    AthenaConnection,
    DuckDBConnection,
]

Connection = Union[
    MorphConnection,
    PostgresqlConnection,
    MysqlConnection,
    SQLServerConnection,
    RedshiftConnection,
    SnowflakeConnectionOAuth,
    SnowflakeConnectionUserPassword,
    SnowflakeConnectionKeyPair,
    SnowflakeConnectionKeyPairFile,
    BigqueryConnectionOAuth,
    BigqueryConnectionServiceAccount,
    BigqueryConnectionServiceAccountJson,
    AthenaConnection,
    GoogleAnalyticsConnectionOAuth,
    SalesforceConnectionOAuth,
    NotionConnectionOAuth,
    StripeConnectionOAuth,
    AttioConnectionOAuth,
    AirtableConnectionOAuth,
    FreeeConnectionOAuth,
    HubspotConnectionOAuth,
    IntercomConnectionOAuth,
    LinearConnectionOAuth,
    MailchimpConnectionOAuth,
    DuckDBConnection,
]


class ConnectionYaml(BaseModel):
    connections: Dict[str, Connection] = Field(default_factory=dict)

    @staticmethod
    def is_file_exits() -> bool:
        return os.path.isfile(MorphConstant.MORPH_CONNECTION_PATH)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConnectionYaml":
        def cast_connection(info: Dict[str, Any]) -> Any:
            connection_type = info.get("type")
            if connection_type == CONNECTION_TYPE.postgres:
                return PostgresqlConnection(**info)
            elif connection_type == CONNECTION_TYPE.mysql:
                return MysqlConnection(**info)
            elif connection_type == CONNECTION_TYPE.mssql:
                return SQLServerConnection(**info)
            elif connection_type == CONNECTION_TYPE.redshift:
                return RedshiftConnection(**info)
            elif connection_type == CONNECTION_TYPE.athena:
                return AthenaConnection(**info)
            elif connection_type == CONNECTION_TYPE.duckdb:
                return DuckDBConnection(**info)
            elif connection_type == CONNECTION_TYPE.snowflake:
                method = info.get("method")
                if method == CONNECTION_DETAIL_TYPE.snowflake_user_password:
                    return SnowflakeConnectionUserPassword(**info)
                elif method == CONNECTION_DETAIL_TYPE.snowflake_oauth:
                    return SnowflakeConnectionOAuth(**info)
                elif method == CONNECTION_DETAIL_TYPE.snowflake_key_pair:
                    return SnowflakeConnectionKeyPair(**info)
                elif method == CONNECTION_DETAIL_TYPE.snowflake_key_pair_file:
                    return SnowflakeConnectionKeyPairFile(**info)
                else:
                    raise ValueError("Unknown connection type")
            elif connection_type == CONNECTION_TYPE.bigquery:
                method = info.get("method")
                if method == CONNECTION_DETAIL_TYPE.bigquery_oauth:
                    return BigqueryConnectionOAuth(**info)
                elif method == CONNECTION_DETAIL_TYPE.bigquery_service_account:
                    return BigqueryConnectionServiceAccount(**info)
                elif method == CONNECTION_DETAIL_TYPE.bigquery_service_account_json:
                    return BigqueryConnectionServiceAccountJson(**info)
                else:
                    raise ValueError("Unknown connection type")
            elif connection_type == CONNECTION_TYPE.googleAnalytics:
                return GoogleAnalyticsConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.salesforce:
                return SalesforceConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.notion:
                return NotionConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.stripe:
                return StripeConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.attio:
                return AttioConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.airtable:
                return AirtableConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.freee:
                return FreeeConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.hubspot:
                return HubspotConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.intercom:
                return IntercomConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.linear:
                return LinearConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.mailchimp:
                return MailchimpConnectionOAuth(**info)
            elif connection_type == CONNECTION_TYPE.morph:
                return MorphConnection(**info)
            else:
                raise ValueError("Unknown connection type")

        connections_data = data.get("connections", {})
        if isinstance(connections_data, dict):
            connections = {
                slug: cast_connection(connection_info)
                for slug, connection_info in connections_data.items()
            }
        else:
            connections = {}
        return ConnectionYaml(connections=connections)

    @staticmethod
    def load_yaml() -> "ConnectionYaml":
        if not ConnectionYaml.is_file_exits():
            return ConnectionYaml(connections={})

        with open(MorphConstant.MORPH_CONNECTION_PATH, "r") as file:
            data = yaml.safe_load(file)

        return ConnectionYaml.from_dict(data if data is not None else {})

    @staticmethod
    def find_connection(
        profile_yaml: Optional["ConnectionYaml"], connection_slug: str
    ) -> Optional[Connection]:
        if connection_slug == MORPH_DUCKDB_CONNECTION_SLUG:
            return DuckDBConnection(type=CONNECTION_TYPE.duckdb)
        profile_yaml = (
            ConnectionYaml.load_yaml() if profile_yaml is None else profile_yaml
        )
        return profile_yaml.connections.get(connection_slug)

    @staticmethod
    def find_connection_detail_type(connection: Connection) -> str:
        if isinstance(connection, MorphConnection):
            return CONNECTION_DETAIL_TYPE.morph.value
        elif isinstance(connection, PostgresqlConnection):
            return CONNECTION_DETAIL_TYPE.postgres.value
        elif isinstance(connection, MysqlConnection):
            return CONNECTION_DETAIL_TYPE.mysql.value
        elif isinstance(connection, SQLServerConnection):
            return CONNECTION_DETAIL_TYPE.mssql.value
        elif isinstance(connection, RedshiftConnection):
            return CONNECTION_DETAIL_TYPE.redshift.value
        elif isinstance(connection, AthenaConnection):
            return CONNECTION_DETAIL_TYPE.athena.value
        elif isinstance(connection, DuckDBConnection):
            return CONNECTION_DETAIL_TYPE.duckdb.value
        elif isinstance(connection, SnowflakeConnectionUserPassword):
            return CONNECTION_DETAIL_TYPE.snowflake_user_password.value
        elif isinstance(connection, SnowflakeConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.snowflake_oauth.value
        elif isinstance(connection, SnowflakeConnectionKeyPair):
            return CONNECTION_DETAIL_TYPE.snowflake_key_pair.value
        elif isinstance(connection, SnowflakeConnectionKeyPairFile):
            return CONNECTION_DETAIL_TYPE.snowflake_key_pair_file.value
        elif isinstance(connection, BigqueryConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.bigquery_oauth.value
        elif isinstance(connection, BigqueryConnectionServiceAccount):
            return CONNECTION_DETAIL_TYPE.bigquery_service_account.value
        elif isinstance(connection, BigqueryConnectionServiceAccountJson):
            return CONNECTION_DETAIL_TYPE.bigquery_service_account_json.value
        elif isinstance(connection, GoogleAnalyticsConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.google_analytics_oauth.value
        elif isinstance(connection, SalesforceConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.salesforce_oauth.value
        elif isinstance(connection, NotionConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.notion_oauth.value
        elif isinstance(connection, StripeConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.salesforce_oauth.value
        elif isinstance(connection, AttioConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.attio_oauth.value
        elif isinstance(connection, AirtableConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.airtable_oauth.value
        elif isinstance(connection, FreeeConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.freee_oauth.value
        elif isinstance(connection, HubspotConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.hubspot_oauth.value
        elif isinstance(connection, IntercomConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.intercom_oauth.value
        elif isinstance(connection, LinearConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.linear_oauth.value
        elif isinstance(connection, MailchimpConnectionOAuth):
            return CONNECTION_DETAIL_TYPE.mailchimp_oauth.value

    @staticmethod
    def find_cloud_connection(
        connection_slug: str,
    ) -> Connection:
        if connection_slug == MORPH_DUCKDB_CONNECTION_SLUG:
            return DuckDBConnection(type=CONNECTION_TYPE.duckdb)
        try:
            try:
                client = MorphApiClient(MorphApiKeyClientImpl)
                response = client.req.find_external_connection(connection_slug)
            except requests.exceptions.Timeout:  # noqa
                click.echo(
                    click.style(
                        "Error: Timeout to obtain connection.",
                        fg="red",
                    )
                )
                raise SystemError("Timeout to obtain connection.")

            if response.status_code > 500 or (
                response.status_code >= 400 and response.status_code < 500
            ):
                click.echo(
                    click.style(
                        "Error: Unable to fetch connections from cloud.",
                        fg="red",
                    )
                )
                raise SystemError("Unable to fetch connection from cloud.")
            else:
                response_json = response.json()
                if (
                    "error" in response_json
                    and "subCode" in response_json
                    and "message" in response_json
                ):
                    click.echo(
                        click.style(
                            "Error: Unable to fetch connection from cloud.",
                            fg="red",
                        )
                    )
                    message = response_json["message"]
                    raise SystemError(
                        f"Unable to fetch connection from cloud. error: {message}"
                    )

                connection_type = response_json["connectionType"]
                auth_type = response_json["authType"]
                data = response_json["data"]
                connection: Optional[Connection] = None
                if connection_type == "postgres":
                    connection = PostgresqlConnection(
                        type=CONNECTION_TYPE.postgres,
                        host=data.get("host", ""),
                        user=data.get("username", ""),
                        password=data.get("password", ""),
                        port=data.get("port", 5432),
                        dbname=data.get("database", ""),
                        schema=data.get("schema", ""),
                        ssh_host=data.get("bastionHost"),
                        ssh_port=data.get("bastionPort"),
                        ssh_user=data.get("bastionUsername"),
                        ssh_password=data.get("bastionPassword"),
                        ssh_private_key=data.get("bastionPrivateKey"),
                    )
                elif connection_type == "mysql":
                    connection = MysqlConnection(
                        type=CONNECTION_TYPE.mysql,
                        host=data.get("host", ""),
                        user=data.get("username", ""),
                        password=data.get("password", ""),
                        port=data.get("port", 3306),
                        dbname=data.get("database", ""),
                        ssh_host=data.get("bastionHost"),
                        ssh_port=data.get("bastionPort"),
                        ssh_user=data.get("bastionUsername"),
                        ssh_password=data.get("bastionPassword"),
                        ssh_private_key=data.get("bastionPrivateKey"),
                    )
                elif connection_type == "mssql":
                    connection = SQLServerConnection(
                        type=CONNECTION_TYPE.mssql,
                        host=data.get("host", ""),
                        user=data.get("username", ""),
                        password=data.get("password", ""),
                        port=data.get("port", 3306),
                        dbname=data.get("database", ""),
                        ssh_host=data.get("bastionHost"),
                        ssh_port=data.get("bastionPort"),
                        ssh_user=data.get("bastionUsername"),
                        ssh_password=data.get("bastionPassword"),
                        ssh_private_key=data.get("bastionPrivateKey"),
                    )
                elif connection_type == "redshift":
                    connection = RedshiftConnection(
                        type=CONNECTION_TYPE.redshift,
                        host=data.get("host", ""),
                        user=data.get("username", ""),
                        password=data.get("password", ""),
                        port=data.get("port", 5439),
                        dbname=data.get("database", ""),
                        schema=data.get("schema", ""),
                        ssh_host=data.get("bastionHost"),
                        ssh_port=data.get("bastionPort"),
                        ssh_user=data.get("bastionUsername"),
                        ssh_password=data.get("bastionPassword"),
                        ssh_private_key=data.get("bastionPrivateKey"),
                    )
                elif connection_type == "athena":
                    connection = AthenaConnection(
                        type=CONNECTION_TYPE.athena,
                        access_key=data.get("accessKey", ""),
                        secret_key=data.get("secretKey", ""),
                        session_token=data.get("sessionToken", ""),
                        region=data.get("region", ""),
                        catalog=data.get("catalog", ""),
                        database=data.get("database", ""),
                        work_group=data.get("workGroup"),
                    )
                elif connection_type == "snowflake" and auth_type == "oauth":
                    connection = SnowflakeConnectionOAuth(
                        type=CONNECTION_TYPE.snowflake,
                        method=CONNECTION_DETAIL_TYPE.snowflake_oauth,
                        account=data.get("server", ""),
                        database=data.get("database", ""),
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        role=data.get("role", ""),
                        schema=data.get("schema", ""),
                        warehouse=data.get("warehouse", ""),
                        code_verifier="",
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "snowflake" and auth_type == "keyPair":
                    connection = SnowflakeConnectionKeyPair(
                        type=CONNECTION_TYPE.snowflake,
                        method=CONNECTION_DETAIL_TYPE.snowflake_key_pair,
                        account=data.get("server", ""),
                        username=data.get("username", ""),
                        database=data.get("database", ""),
                        key_pair=data.get("privateKey", ""),
                        role=data.get("role", ""),
                        schema=data.get("schema", ""),
                        warehouse=data.get("warehouse", ""),
                        passphrase=data.get("passphrase"),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "bigquery" and auth_type == "oauth":
                    connection = BigqueryConnectionOAuth(
                        type=CONNECTION_TYPE.bigquery,
                        method=CONNECTION_DETAIL_TYPE.bigquery_oauth,
                        project=data.get("projectId", ""),
                        dataset=data.get("dataset", ""),
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        location=data.get("location"),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "bigquery" and auth_type == "serviceAccount":
                    credentials = (
                        json.loads(data.get("credentials", "{}"))
                        if type(data.get("credentials")) == str
                        else data.get("credentials", {})
                    )
                    connection = BigqueryConnectionServiceAccountJson(
                        type=CONNECTION_TYPE.bigquery,
                        method=CONNECTION_DETAIL_TYPE.bigquery_service_account_json,
                        project=data.get("projectId", ""),
                        dataset=data.get("dataset", ""),
                        keyfile_json=BigqueryConnectionServiceAccountJsonKeyFile(
                            project_id=credentials.get("project_id", ""),
                            private_key_id=credentials.get("private_key_id", ""),
                            private_key=credentials.get("private_key", ""),
                            client_email=credentials.get("client_email", ""),
                            client_id=credentials.get("client_id", ""),
                            auth_uri=credentials.get("auth_uri", ""),
                            token_uri=credentials.get("token_uri", ""),
                            auth_provider_x509_cert_url=credentials.get(
                                "auth_provider_x509_cert_url", ""
                            ),
                            client_x509_cert_url=credentials.get(
                                "client_x509_cert_url", ""
                            ),
                        ),
                        location=data.get("location"),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "googleAnalytics" and auth_type == "oauth":
                    connection = GoogleAnalyticsConnectionOAuth(
                        type=CONNECTION_TYPE.googleAnalytics,
                        method=CONNECTION_DETAIL_TYPE.google_analytics_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "salesforce" and auth_type == "oauth":
                    connection = SalesforceConnectionOAuth(
                        type=CONNECTION_TYPE.salesforce,
                        method=CONNECTION_DETAIL_TYPE.salesforce_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                        custom_domain_url=data.get("customDomainUrl", ""),
                    )
                elif connection_type == "notion" and auth_type == "oauth":
                    connection = NotionConnectionOAuth(
                        type=CONNECTION_TYPE.notion,
                        method=CONNECTION_DETAIL_TYPE.notion_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "stripe" and auth_type == "oauth":
                    connection = StripeConnectionOAuth(
                        type=CONNECTION_TYPE.stripe,
                        method=CONNECTION_DETAIL_TYPE.stripe_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "attio" and auth_type == "oauth":
                    connection = AttioConnectionOAuth(
                        type=CONNECTION_TYPE.attio,
                        method=CONNECTION_DETAIL_TYPE.attio_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "airtable" and auth_type == "oauth":
                    connection = AirtableConnectionOAuth(
                        type=CONNECTION_TYPE.airtable,
                        method=CONNECTION_DETAIL_TYPE.airtable_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "freee" and auth_type == "oauth":
                    connection = FreeeConnectionOAuth(
                        type=CONNECTION_TYPE.freee,
                        method=CONNECTION_DETAIL_TYPE.freee_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "hubspot" and auth_type == "oauth":
                    connection = HubspotConnectionOAuth(
                        type=CONNECTION_TYPE.hubspot,
                        method=CONNECTION_DETAIL_TYPE.hubspot_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "intercom" and auth_type == "oauth":
                    connection = IntercomConnectionOAuth(
                        type=CONNECTION_TYPE.intercom,
                        method=CONNECTION_DETAIL_TYPE.intercom_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "linear" and auth_type == "oauth":
                    connection = LinearConnectionOAuth(
                        type=CONNECTION_TYPE.linear,
                        method=CONNECTION_DETAIL_TYPE.linear_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                elif connection_type == "mailchimp" and auth_type == "oauth":
                    connection = MailchimpConnectionOAuth(
                        type=CONNECTION_TYPE.mailchimp,
                        method=CONNECTION_DETAIL_TYPE.mailchimp_oauth,
                        refresh_token=data.get("refreshToken", ""),
                        client_id=data.get("clientId", ""),
                        client_secret=data.get("clientSecret", ""),
                        redirect_uri=data.get("redirectUrl", ""),
                        access_token=data.get("accessToken", ""),
                    )
                else:
                    raise NotImplementedError(
                        f"connection type not implemented {connection_type} {auth_type}"
                    )
            return connection
        except Exception as e:
            raise SystemError(f"Unable to fetch connection from cloud. {e}")

    def add_connections(self, connections: Dict[str, Connection]) -> None:
        self.connections.update(connections)

    def save_yaml(self, override: Optional[bool] = False) -> None:
        if override or not self.connections:
            with open(MorphConstant.MORPH_CONNECTION_PATH, "w") as file:
                yaml.dump(self.model_dump(), file)
