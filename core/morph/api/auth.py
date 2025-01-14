from fastapi import Header


async def auth(authorization: str = Header(default=None)) -> None:
    # if not authorization.startswith("Bearer "):
    #     raise AuthError(
    #         ErrorCode.AuthError, ErrorMessage.AuthErrorMessage["notAuthorized"]
    #     )
    # token = authorization.split(" ")[1]

    # TODO: required to verify api key and get user info
    # user = UserInfo(
    #     username=response_json["user"]["username"],
    #     email=response_json["user"]["email"],
    #     first_name=response_json["user"]["firstName"],
    #     last_name=response_json["user"]["lastName"],
    # )
    # request_context.set({"user": user.model_dump()})
    pass
