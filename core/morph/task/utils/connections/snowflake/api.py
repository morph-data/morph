import base64
import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from urllib.parse import urlencode

import jwt
import requests
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

from morph.task.utils.connections.snowflake.types import (
    SnowflakeException,
    SnowflakeExecuteSqlImplResponse,
)
from morph.task.utils.connections.utils import normalize_newlines


class SnowflakeApi:
    @staticmethod
    def is_valid_jwt(token: str) -> bool:
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            if (
                "iss" in decoded_token
                and "sub" in decoded_token
                and "iat" in decoded_token
                and "exp" in decoded_token
            ):
                return True
            return False
        except jwt.DecodeError:
            return False
        except jwt.ExpiredSignatureError:
            return True
        except jwt.InvalidTokenError:
            return False

    @staticmethod
    def execute_sql_impl(
        account: str,
        access_token: str,
        statement: str,
        timeout: Optional[int] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        warehouse: Optional[str] = None,
        role: Optional[str] = None,
    ) -> SnowflakeExecuteSqlImplResponse:
        if not account.startswith("http"):
            account = f"https://{account}"
        if not account.endswith(".snowflakecomputing.com"):
            account = f"{account}.snowflakecomputing.com"

        url = f"{account}/api/v2/statements"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if SnowflakeApi.is_valid_jwt(access_token):
            headers["X-Snowflake-Authorization-Token-Type"] = "KEYPAIR_JWT"

        body = {
            "statement": statement,
            "timeout": timeout,
            "database": database,
            "schema": schema,
            "warehouse": warehouse,
            "role": role,
        }

        response = requests.post(url, json=body, headers=headers)
        response_json = response.json()

        if (
            response.status_code >= 400
            and "sqlState" in response_json
            and response_json["sqlState"] != "00000"
        ):
            raise SnowflakeException(
                response_json["message"],
                response_json["code"],
                response_json["sqlState"],
                response_json["statementHandle"],
            )

        return SnowflakeExecuteSqlImplResponse.model_validate(
            {
                "data": response.json(),
                "status": response.status_code,
            }
        )

    @staticmethod
    def get_sql_statements(
        account: str,
        access_token: str,
        statement_handle: str,
        partition: Optional[int] = None,
    ) -> SnowflakeExecuteSqlImplResponse:
        if not account.startswith("http"):
            account = f"https://{account}"
        if not account.endswith(".snowflakecomputing.com"):
            account = f"{account}.snowflakecomputing.com"

        url = f"{account}/api/v2/statements/{statement_handle}"

        if partition is not None:
            url += f"?partition={partition}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if SnowflakeApi.is_valid_jwt(access_token):
            headers["X-Snowflake-Authorization-Token-Type"] = "KEYPAIR_JWT"

        response = requests.get(url, headers=headers)
        response_json = response.json()

        if (
            response.status_code >= 400
            and "sqlState" in response_json
            and response_json["sqlState"] != "00000"
        ):
            raise SnowflakeException(
                response_json["message"],
                response_json["code"],
                response_json["sqlState"],
                response_json["statementHandle"],
            )

        return SnowflakeExecuteSqlImplResponse.model_validate(
            {
                "data": response.json(),
                "status": response.status_code,
            }
        )

    @staticmethod
    def execute_sql(
        account: str,
        access_token: str,
        statement: str,
        timeout: Optional[int] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        warehouse: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Union[Dict[str, Any], int, str]]:
        execute_result = SnowflakeApi.execute_sql_impl(
            account=account,
            access_token=access_token,
            statement=statement,
            timeout=timeout,
            database=database,
            schema=schema,
            warehouse=warehouse,
            role=role,
        )
        statement_handle = execute_result.data.statementHandle
        if execute_result.status == 200:
            partition_num = len(execute_result.data.resultSetMetaData.partitionInfo)
            return {
                "data": execute_result.data.model_dump(),
                "statementHandle": statement_handle,
                "partitionNum": partition_num,
            }
        elif execute_result.status == 202:
            while execute_result.status == 202:
                execute_result = SnowflakeApi.get_sql_statements(
                    account=account,
                    access_token=access_token,
                    statement_handle=statement_handle,
                )
                time.sleep(1)
            partition_num = len(execute_result.data.resultSetMetaData.partitionInfo)
            return {
                "data": execute_result.data.model_dump(),
                "statementHandle": statement_handle,
                "partitionNum": partition_num,
            }
        else:
            raise Exception("Failed to execute sql")

    @staticmethod
    def get_account_identifier(account_identifier: str) -> str:
        account = account_identifier
        if account_identifier.startswith("http"):
            start_idx = account_identifier.find("https://") + 8
            end_idx = account_identifier.find(".snowflakecomputing.com")
            account_name = account_identifier[start_idx:end_idx]
            account = account_name

        if ".global" not in account:
            idx = account.find(".")
            if idx > 0:
                account = account[:idx]
        else:
            idx = account.find("-")
            if idx > 0:
                account = account[:idx]

        account = account.upper()
        return account

    @staticmethod
    def get_key_pair_access_token(
        account_identifier: str,
        username: str,
        private_key_raw: str,
        passphrase: Optional[str] = None,
    ) -> str:
        private_key_raw_: Optional[str] = None
        try:
            if os.path.exists(private_key_raw):
                private_key_raw_ = open(private_key_raw, "r").read()
            else:
                private_key_raw_ = private_key_raw
        except Exception as e:
            raise ValueError(f"Error invalid private key: {e}")

        if not private_key_raw_:
            raise ValueError("Error invalid private key")

        private_key_raw_ = normalize_newlines(private_key_raw_)

        account = SnowflakeApi.get_account_identifier(account_identifier)
        username = username.upper()
        qualified_username = f"{account}.{username}"
        passphrase = None if passphrase is None or passphrase == "" else passphrase

        now = datetime.utcnow()

        private_key_object = load_pem_private_key(
            private_key_raw_.encode("utf-8").replace(b"\\n", b"\n"),
            password=passphrase.encode("utf-8") if passphrase else None,
        )

        private_key = private_key_object.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

        public_key_object = private_key_object.public_key()
        public_key = public_key_object.public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo,
        )

        sha256hash = hashlib.sha256()
        sha256hash.update(public_key)
        public_key_fp = "SHA256:" + sha256hash.digest().hex()

        payload = {
            "iss": f"{qualified_username}.{public_key_fp}",
            "sub": qualified_username,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=60)).timestamp()),
        }

        token = jwt.encode(payload, private_key, algorithm="RS256")
        return cast(str, token)

    @staticmethod
    def refresh_access_token(
        refresh_token: str,
        account: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> Dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }

        data_encoded = urlencode(data)

        token = base64.urlsafe_b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()

        url = f"{account}/oauth/token-request"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {token}",
        }

        try:
            response = requests.post(url, headers=headers, data=data_encoded)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to refresh access token: {e}")

        access_token = response.json()["access_token"]
        expires_in = response.json()["expires_in"]

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        }

    @staticmethod
    def execute_sql_with_basic(
        sql: str,
        username: str,
        password: str,
        account: str,
        warehouse: str,
        database: str,
        schema: Optional[str],
    ) -> Tuple[Union[List[Tuple], List[Dict]], List[str]]:
        from snowflake import connector

        account_identifier = SnowflakeApi.get_account_identifier(account)

        try:
            conn = connector.connect(
                user=username,
                password=password,
                account=account_identifier,
                warehouse=warehouse,
                database=database,
                schema=schema,
                authenticator="snowflake",
            )
        except Exception as e:
            raise RuntimeError(f"Authentication failed: {e}")
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            result = cursor.fetchall()
            return result, columns
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")
        finally:
            cursor.close()
            conn.close()
