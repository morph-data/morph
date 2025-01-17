from typing import List

from pydantic import BaseModel


# ================================================
# User
# ================================================
class UserInfo(BaseModel):
    user_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    roles: List[str]


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
