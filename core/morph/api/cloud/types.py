from typing import List

from pydantic import BaseModel


# ================================================
# User
# ================================================
class UserInfo(BaseModel):
    username: str
    email: str
    first_name: str
    last_name: str


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
