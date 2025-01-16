import logging
import sys

import click
import uvicorn


class UvicornLoggerHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        click.echo(log_entry, err=False)


logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)
handler = UvicornLoggerHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def parse_sys_argv():
    port = 8080

    args = sys.argv[1:]
    for i in range(len(args)):
        if args[i] == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                port = 8080

    return port


def start_server(port: int) -> None:
    uvicorn.run(
        "morph.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    port = parse_sys_argv()
    start_server(port)
