from enum import Enum
from typing import List


class Command(Enum):
    INIT = "init"
    RUN = "run"

    @classmethod
    def from_str(cls, s: str) -> "Command":
        try:
            return cls(s)
        except ValueError:
            raise Exception(f"No value '{s}' exists in Command enum")

    def to_list(self) -> List[str]:
        return {
            Command.RUN: ["run", "--dag"],
        }.get(self, [self.value])
