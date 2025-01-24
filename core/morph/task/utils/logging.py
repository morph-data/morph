import logging
import sys
from contextlib import asynccontextmanager, contextmanager

import colorlog


class LoggerStream:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.line_buffer = ""

    def write(self, message):
        self.line_buffer += message
        while "\n" in self.line_buffer:
            line, self.line_buffer = self.line_buffer.split("\n", 1)
            self.logger.log(self.level, line.strip())

    def flush(self):
        if self.line_buffer:
            self.logger.log(self.level, self.line_buffer.strip())
            self.line_buffer = ""


@contextmanager
def redirect_stdout_to_logger(logger, level):
    original_stdout = sys.stdout
    sys.stdout = LoggerStream(logger, level)  # type: ignore
    try:
        yield
    finally:
        sys.stdout.flush()
        sys.stdout = original_stdout


@asynccontextmanager
async def redirect_stdout_to_logger_async(logger, level=logging.INFO):
    with redirect_stdout_to_logger(logger, level):
        yield


def get_morph_logger() -> logging.Logger:
    logger = logging.getLogger("morph_logger")

    if not logger.hasHandlers():
        logger.setLevel(logging.DEBUG)

        # Console handler with color formatting
        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)s] %(message)s",
            log_colors={
                "DEBUG": "white",
                "INFO": "cyan",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
