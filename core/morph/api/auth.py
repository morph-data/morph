from fastapi import Header

from morph.api.cloud.client import MorphApiClient, MorphApiTokenClientImpl
from morph.api.cloud.types import UserInfo
from morph.api.cloud.utils import is_cloud
from morph.api.context import request_context
from morph.api.error import AuthError, ErrorCode, ErrorMessage


async def auth(authorization: str = Header(default=None)) -> None:
    if not is_cloud():
        return
    if not authorization.startswith("Bearer "):
        raise AuthError(
            ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["notAuthorized"]
        )
    token = authorization.split(" ")[1]

    client = MorphApiClient(MorphApiTokenClientImpl, token=token)
    try:
        response = client.req.find_user()
    except Exception:  # noqa
        raise AuthError(
            ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["notAuthorized"]
        )
    if response.is_error():
        raise AuthError(
            ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["notAuthorized"]
        )
    response_json = response.json()
    user = UserInfo(
        username=response_json["user"]["username"],
        email=response_json["user"]["email"],
        first_name=response_json["user"]["firstName"],
        last_name=response_json["user"]["lastName"],
    )
    request_context.set({"user": user.model_dump()})
