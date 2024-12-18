import json
import time
from typing import Any, Dict, Optional, Union, cast

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from morph.task.utils.connections.bigquery.types import (
    BigqueryException,
    BigqueryQueryResponse,
)
from morph.task.utils.connections.utils import normalize_newlines

BASE_URL = "https://bigquery.googleapis.com/bigquery/v2"


class BigqueryApi:
    @staticmethod
    def encode_next_token(
        job_id: str, page_token: str, location: Optional[str] = None
    ) -> str:
        return json.dumps(
            {"job_id": job_id, "page_token": page_token, "location": location}
        )

    @staticmethod
    def decode_next_token(next_token: str) -> Any:
        return json.loads(next_token or "{}")

    @staticmethod
    def post_query(
        project_id: str,
        query: str,
        access_token: str,
        location: Optional[str] = "asia-northeast1",
        limit: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> BigqueryQueryResponse:
        url = f"{BASE_URL}/projects/{project_id}/queries"
        if next_token:
            job_id, page_token, location = BigqueryApi.decode_next_token(
                next_token
            ).values()
            return BigqueryApi.get_extra_query_result(
                project_id, job_id, access_token, page_token, location, limit
            )

        body = {"query": query, "useLegacySql": False}
        if limit:
            body["maxResults"] = limit
        if location:
            body["location"] = location

        response = requests.post(
            url, json=body, headers={"Authorization": f"Bearer {access_token}"}
        )
        response_json = response.json()

        if "error" in response_json:
            raise BigqueryException(
                response_json["error"]["message"],
                response_json["error"]["code"],
                response_json["error"]["errors"],
                response_json["error"]["status"],
            )

        job_id = response_json["jobReference"]["jobId"]

        job_complete = cast(bool, response_json["jobComplete"])
        schema = response_json["schema"] if "schema" in response_json else None
        if not job_complete and schema is None:
            time.sleep(1)
            return BigqueryApi.get_extra_query_result(
                project_id, job_id, access_token, None, location, limit
            )

        page_token = (
            response_json["pageToken"] if "pageToken" in response_json else None
        )
        next_token = (
            BigqueryApi.encode_next_token(job_id, page_token, location)
            if job_id and page_token
            else None
        )
        if "rows" not in response_json:
            response_json["rows"] = []

        return BigqueryQueryResponse.model_validate(
            {**response_json, "next_token": next_token}
        )

    @staticmethod
    def get_extra_query_result(
        project_id: str,
        job_id: str,
        access_token: str,
        page_token: Optional[str] = None,
        location: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> BigqueryQueryResponse:
        url = f"{BASE_URL}/projects/{project_id}/queries/{job_id}"

        params = {}
        if page_token:
            params["pageToken"] = page_token
        if limit:
            params["maxResults"] = str(limit)
        if location:
            params["location"] = location

        response = requests.get(
            url, params=params, headers={"Authorization": f"Bearer {access_token}"}
        )
        response_json = response.json()

        if "error" in response_json:
            raise BigqueryException(
                response_json["error"]["message"],
                response_json["error"]["code"],
                response_json["error"]["errors"],
                response_json["error"]["status"],
            )

        job_id = response_json["jobReference"]["jobId"]

        job_complete = cast(bool, response_json["jobComplete"])
        schema = response_json["schema"] if "schema" in response_json else None
        if not job_complete and schema is None:
            time.sleep(1)
            return BigqueryApi.get_extra_query_result(
                project_id, job_id, access_token, page_token, location, limit
            )

        page_token = (
            response_json["pageToken"] if "pageToken" in response_json else None
        )
        next_token = (
            BigqueryApi.encode_next_token(job_id, page_token, location)
            if job_id and page_token
            else None
        )
        if "rows" not in response_json:
            response_json["rows"] = []

        return BigqueryQueryResponse.model_validate(
            {**response_json, "next_token": next_token}
        )

    @staticmethod
    def get_access_token_from_service_account(
        service_account_info: Union[Dict[str, Any], str]
    ) -> str:
        import jwt

        url = "https://oauth2.googleapis.com/token"

        credential: Optional[Dict[str, Any]] = None
        try:
            if isinstance(service_account_info, str):
                try:
                    credential_ = json.loads(service_account_info)
                    credential = cast(Dict[str, Any], json.loads(credential_))
                except Exception:  # noqa
                    credential_str = open(service_account_info, "r").read()
                    credential = cast(Dict[str, Any], json.loads(credential_str))
            else:
                credential = service_account_info
        except Exception as e:
            raise ValueError(f" Error invalid credential: {e}")

        if not credential:
            raise ValueError("Error Invalid credential")

        private_key = normalize_newlines(cast(str, credential["private_key"]))
        client_email = credential["client_email"]
        token_uri = credential["token_uri"]

        issued_at = int(time.time())
        expiration_time = issued_at + 3600

        payload = {
            "iss": client_email,
            "scope": "https://www.googleapis.com/auth/bigquery",
            "aud": token_uri,
            "iat": issued_at,
            "exp": expiration_time,
        }

        private_key_obj = load_pem_private_key(
            private_key.encode("utf-8"), password=None, backend=default_backend()
        )
        jwt_token = jwt.encode(payload, private_key_obj, algorithm="RS256")

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt_token,
        }

        response = requests.post(url, data=data)

        if response.status_code == 200:
            return cast(str, response.json()["access_token"])
        else:
            raise Exception(f"Error obtaining access token: {response.text}")

    @staticmethod
    def refresh_access_token(
        client_id: str, client_secret: str, refresh_token: str
    ) -> Dict[str, Any]:
        url = "https://oauth2.googleapis.com/token"

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = requests.post(url, data=data)
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
