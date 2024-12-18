from abc import ABCMeta, abstractmethod

from morph.cli.flags import Flags


class BaseTask(metaclass=ABCMeta):
    def __init__(self, args: Flags) -> None:
        self.args = args

    @abstractmethod
    def run(self):
        raise Exception("Not implemented")
