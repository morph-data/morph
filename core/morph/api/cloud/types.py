from typing import List

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_snake


# ================================================
# User
# ================================================
class UserInfo(BaseModel):
    user_id: str = Field(alias="userId")
    username: str
    email: str
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    roles: List[str]

    model_config = ConfigDict(
        alias_generator=to_snake,
        populate_by_name=True,
        from_attributes=True,
    )


# ================================================
# EnvVar
# ================================================


class EnvVarObject(BaseModel):
    key: str
    value: str

    class Config:
        extra = "ignore"


class EnvVarList(BaseModel):
    items: List[EnvVarObject]
    count: int
