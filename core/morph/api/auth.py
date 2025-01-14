import json
import os

from fastapi import Header

from morph.api.cloud.types import UserInfo
from morph.api.context import request_context
from morph.api.error import AuthError, ErrorCode, ErrorMessage
from morph.task.utils.morph import find_project_root_dir


async def auth(authorization: str = Header(default=None)) -> None:
    if authorization == "Bearer dummy":
        # "dummy" is set when running in local
        project_root = find_project_root_dir()
        mock_json_path = f"{project_root}/.mock_user_context.json"
        if not os.path.exists(mock_json_path):
            request_context.set(
                {
                    "user": UserInfo(
                        user_id="cea122ea-b240-49d7-ae7f-8b1e3d40dd8f",
                        email="example@morph-data.io",
                        username="sample",
                        first_name="Sample",
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

    # TODO: deserialize token
    # user = UserInfo(
    #     username=response_json["user"]["username"],
    #     email=response_json["user"]["email"],
    #     first_name=response_json["user"]["firstName"],
    #     last_name=response_json["user"]["lastName"],
    # )
    # request_context.set({"user": user.model_dump()})
