import base64
import json
import os

from fastapi import Header

from morph.api.cloud.types import UserInfo
from morph.api.context import request_context
from morph.api.error import AuthError, ErrorCode, ErrorMessage
from morph.task.utils.morph import find_project_root_dir


async def auth(
    authorization: str = Header(default=None), x_api_key: str = Header(default=None)
) -> None:
    if x_api_key is not None:
        os.environ["MORPH_API_KEY"] = x_api_key

    if authorization is None or authorization == "Bearer dummy":
        # "dummy" is set when running in local
        project_root = find_project_root_dir()
        mock_json_path = f"{project_root}/.mock_user_context.json"
        if not os.path.exists(mock_json_path):
            request_context.set(
                {
                    "user": UserInfo(
                        user_id="cea122ea-b240-49d7-ae7f-8b1e3d40dd8f",
                        email="mock_user@morph-data.io",
                        username="mock_user",
                        first_name="Mock",
                        last_name="User",
                        roles=["Admin"],
                    ).model_dump()
                }
            )
            return
        try:
            mock_json = json.load(open(mock_json_path))
            request_context.set({"user": mock_json})
            return
        except Exception:
            raise AuthError(
                ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["mockJsonInvalid"]
            )

    try:
        token = authorization.split(" ")[1]
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthError(
                ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["tokenInvalid"]
            )

        payload_encoded = parts[1]
        payload_json = base64.urlsafe_b64decode(
            payload_encoded + "=" * (-len(payload_encoded) % 4)
        )
        user_context_json = json.loads(payload_json)
        request_context.set({"user": user_context_json})
    except Exception:
        raise AuthError(
            ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["tokenInvalid"]
        )
