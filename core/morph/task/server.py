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

    filtered_args = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue

        if arg == "--port" and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 2])
                skip_next = True
            except ValueError:
                port = 8080
            continue

        filtered_args.append(arg)

    sys.argv = [sys.argv[0]] + filtered_args

    return port


def start_server(port: int) -> None:
    uvicorn.run("morph.api.app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    port = parse_sys_argv()
    start_server(port)
